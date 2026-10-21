"""spec-kitty charter deactivate — deactivate a doctrine artifact.

FR-005 (direct deactivation), FR-015/FR-016 (shared-reference-safe cascade),
FR-035 (fail-closed on invalid pack config).

Wiring (Contracts C3.3/C3.4, C1.5)
----------------------------------
The live caller for the WP10 plan/commit engine and the WP11 shared-reference-
safe cascade engine on the removal side:

* ``--cascade`` is parsed through :meth:`charter.activation.cascade.CascadeScope.parse`
  (WP11) into a real scope value object — never collapsed to a bool (C3.3).
* Cascade removal goes through :func:`charter.activation.cascade.deactivation_plan`, which
  removes only *exclusive* referenced artifacts and **never** removes a shared
  one (Contract C3.4); shared skips are reported with the still-referencing
  active source named.
* Deactivation records an exclusion (``deactivated_<kind>``), also when the
  kind has no allow-list ("absent = all"). An org-required id raises a
  :class:`charter.activation.pack_manager.DeactivationRefused`, surfaced as a
  clean exit-1 naming the pack(s) and the ``required_<kind>`` policy; nothing
  is written. A cascade records only the named id (D-11).
* :class:`charter.activation.pack_context.ActiveCharterConfigError` is caught and surfaced as
  fail-closed guidance before any mutation (FR-035, C1.5).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import typer
from specify_cli.cli.console import console

from charter.activation.cascade import CascadeScope, deactivation_plan
from charter.activation.catalog import resolve_offering_root
from charter.activation.drg_activation import load_org_drg
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import (
    ResolutionPass,
    UnknownArtifactIdError,
    resolve_artifact_urn,
)
from charter.activation.api import refuse_unmigrated_deny_write
from charter.activation.pack_context import ActiveCharterConfigError, load_denied
from charter.activation.pack_manager import YAML_KEY_MAP, ActiveCharterManager, DeactivationRefused
from charter.activation.kind_vocabulary import ArtifactKind, MissionTypeNotAnArtifactKind

from specify_cli.cli.commands.charter._cascade_shared import (
    drg_urn_to_config_id,
    render_kind_filtered_line,
)
from specify_cli.cli.commands.charter.activate import (
    NO_COMPILE_HELP,
    RESYNTHESIZE_HELP,
    mission_type_urn,
    recompile_or_notify,
    reproject_pack_skills,
    render_pack_config_error,
    resolve_write_root_or_exit,
    validate_pack_config,
)
from charter.activation.layer_roots import (
    resolve_layer_roots,
    resolve_pack_chain,
)
from specify_cli.mission_step_contracts.profile_defaults import (
    mission_default_profile_warning,
)

__all__ = ["deactivate_cmd"]


def _warn_mission_default_binding(profile_id: str) -> None:
    """#4115: warn when a deactivated agent profile is a built-in mission-step default.

    ``charter deactivate agent-profile researcher-robbie`` used to succeed
    silently while leaving every built-in mission step bound to that profile
    one dispatch away from a blocked composition. The warning is advisory
    (deactivation is legitimate); the executor's role-based fallback is the
    behavioral half of the fix.
    """
    warning = mission_default_profile_warning(profile_id)
    if warning is not None:
        console.print(f"[yellow]Warning[/yellow]: {warning}")



def _source_urn(
    kind: str,
    artifact_id: str,
    layer_roots: dict[str, Path] | None,
    org_roots: list[Path] | None = None,
) -> str | None:
    """Resolve the DRG source URN for ``(kind, config-stem artifact_id)`` or ``None``.

    ``org_roots`` (T008/T010, mission ``cascade-org-inert-01M07E9P``): the
    full declaration-ordered org-pack chain, additive to ``layer_roots``'s
    single-pack-only ``roots["org"]`` — see
    ``charter.activation.layer_roots.resolve_pack_chain``.
    """
    try:
        kind_enum = ArtifactKind.from_operator_token(kind)
    except MissionTypeNotAnArtifactKind:
        source: str = mission_type_urn(artifact_id)  # FR-022: the mission type's DRG node is the cascade source
        return source
    try:
        urn: str = resolve_artifact_urn(
            kind_enum,
            artifact_id,
            offering_root=resolve_offering_root(),
            org_roots=org_roots,
            layer_roots=layer_roots,
        )
    except UnknownArtifactIdError:
        return None
    return urn


def _active_urns(
    manager: ActiveCharterManager,
    ctx_project: ProjectContext,
    layer_roots: dict[str, Path] | None,
    org_roots: list[Path] | None = None,
    graph_urns: frozenset[str] = frozenset(),
    *,
    include_mission_types: bool = False,
) -> set[str]:
    """Return the set of currently-active artifact URNs across all kinds (C-007).

    Counts the effective allow state: a present list contributes its ids
    (resolved back to DRG URNs), an absent "all" list contributes every DRG
    node of that kind in *graph_urns*, and denied ids are left out. IDs with
    no resolvable DRG node (or mission-type, which is not an artifact kind) are
    skipped — they cannot participate in DRG reachability anyway.

    ``org_roots`` (T008/T010): full org-pack chain — without it, a currently-
    active artifact whose config-stem lives only in org pack 2..N could not
    resolve its DRG URN at all here, so it would silently drop out of the
    ``active`` set that :func:`charter.activation.cascade.deactivation_plan` uses for
    Contract C3.4 shared-reference safety (NFR-002: a dropped active URN is a
    silent-wrong-data risk, not merely a display gap).

    ``include_mission_types`` (FR-022): when a mission type is the cascade
    target, the other active mission types are sources too, so a child they
    still reach is kept (C-005). An artifact target keeps today's set.
    """
    offering_root = resolve_offering_root()

    def urns_of(kind_enum: ArtifactKind, ids: Iterable[str]) -> set[str]:
        found: set[str] = set()
        for config_id in ids:
            try:
                found.add(resolve_artifact_urn(kind_enum, config_id, offering_root=offering_root, org_roots=org_roots, layer_roots=layer_roots))
            except UnknownArtifactIdError:
                continue
        return found

    # D* (deny less the org required floor), so a stale deny of a required id keeps it active (FR-012, C-005).
    denied = dict(load_denied(ctx_project.require_repo_root(), org_roots=org_roots))
    urns: set[str] = set()
    for kind_token, ids in manager.list_activated(ctx_project).items():
        try:
            kind_enum = ArtifactKind.from_operator_token(kind_token)
        except MissionTypeNotAnArtifactKind:
            if include_mission_types:
                urns |= {mission_type_urn(mission_type) for mission_type in ids or ()}
            continue
        if ids is not None:
            urns |= urns_of(kind_enum, ids)
        elif kind_enum.effective_when_absent == "all":
            urns |= {urn for urn in graph_urns if urn.partition(":")[0] == kind_enum.value}
        if (deny := denied.get(kind_enum.plural)) is not None:
            urns -= deny.urns
    return urns


def _cascade_child(
    manager: ActiveCharterManager,
    ctx_project: ProjectContext,
    kind_token: str,
    config_id: str,
    *,
    layer_roots: dict[str, Path] | None,
    source_id: str,
    allow_absent: bool,
) -> None:
    """Drop one exclusive child's allow entry (no deny entry, D-11) and render the outcome."""
    label = f"{kind_token}/{config_id}"
    if allow_absent:
        console.print(f"[cyan]Cascade[/cyan]: {label}: still active (no allow-list; only {source_id} excluded)")
        return
    try:
        result = manager.deactivate(ctx_project, kind_token, config_id, cascade=False, layer_roots=layer_roots, record_exclusion=False)
    except DeactivationRefused as exc:
        packs = ", ".join(entry.pack for entry in getattr(exc, "requiring", ()))
        console.print(f"[yellow]Cascade[/yellow]: {label}: skipped (required by {packs})")
        return
    except ValueError as exc:
        console.print(f"[yellow]Warning[/yellow]: could not cascade-deactivate {label}: {exc}")
        return
    if not result.deactivated:
        return
    console.print(f"[cyan]Cascade-deactivated[/cyan]: {label}")
    # #4115: a cascade can remove agent profiles bound by built-in
    # mission steps exactly like a direct deactivation can.
    if kind_token == ArtifactKind.AGENT_PROFILE.operator_token:
        _warn_mission_default_binding(config_id)


def _render_cascade_deactivation(
    manager: ActiveCharterManager,
    ctx_project: ProjectContext,
    target_urn: str,
    scope: CascadeScope,
    repo_root: Path,
    layer_roots: dict[str, Path] | None,
    source_id: str,
) -> None:
    """Cascade-deactivate exclusive referenced artifacts; keep shared ones (FR-015/016, C-007).

    Uses the WP11 :func:`charter.activation.cascade.deactivation_plan` over the merged DRG.
    Exclusive candidates lose only their allow-list entry (no exclusion is
    recorded for them, D-11); a child of a kind with no allow-list stays
    active and is rendered so; a required child is skipped naming its pack.
    Shared candidates are reported (never removed — Contract C3.4) with the
    still-referencing active source named.

    T010 (mission ``cascade-org-inert-01M07E9P``): threads the full org-pack
    chain into the DRG load, the active-URN resolution, and the ID mapping
    below — same rationale as ``activate.py``'s ``_render_cascade_activation``.
    """
    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415

    org_roots = resolve_pack_chain(repo_root, strict=False)
    graph = load_validated_graph(
        repo_root,
        org_roots=org_roots,
        org_fragments=load_org_drg(repo_root, strict=False),
    )
    graph_urns = frozenset(node.urn for node in graph.nodes)
    active = _active_urns(manager, ctx_project, layer_roots, org_roots, graph_urns, include_mission_types=target_urn.startswith(mission_type_urn("")))
    plan = deactivation_plan(graph, target_urn, scope, active_urns=active)
    offering_root = resolve_offering_root()
    allow_state = manager.list_activated(ctx_project)

    for urn in plan.deactivate:
        kind_value, _, _ = urn.partition(":")
        kind_token = ArtifactKind(kind_value).operator_token
        _cascade_child(
            manager,
            ctx_project,
            kind_token,
            drg_urn_to_config_id(urn, offering_root, layer_roots, org_roots),
            layer_roots=layer_roots,
            source_id=source_id,
            allow_absent=allow_state.get(kind_token, ()) is None,
        )

    for skip in plan.skipped_shared:
        kind_token = ArtifactKind(skip.urn.partition(":")[0]).operator_token
        if allow_state.get(kind_token, ()) is None:
            # No allow-list: the child stays active whoever references it.
            config_id = drg_urn_to_config_id(skip.urn, offering_root, layer_roots, org_roots)
            console.print(f"[cyan]Cascade[/cyan]: {kind_token}/{config_id}: still active (no allow-list; only {source_id} excluded)")
            continue
        console.print(
            f"[yellow]Skipped (shared artifact)[/yellow]: {skip.urn} "
            f"(still referenced by {skip.referencing_active_urn})"
        )


    # FR-007 (issue #3705): the deactivation-side half of C-002's
    # cross-command symmetry (ADR 2026-08-20-1 Symmetry section) -- render
    # the kind-filtered nodes `deactivation_plan` collected via the shared
    # `_referenced_artifacts` seam instead of silently dropping them, via the
    # SAME shared helper `activate.py`'s cascade-activation and no-cascade
    # warning render paths already use (FR-009), so the wording is identical
    # and never re-coined here. Resolves each URN's bare id to its
    # config-stem id FIRST, the SAME `drg_urn_to_config_id` call (with the
    # same fallback) the `plan.deactivate` loop above already makes -- never
    # the raw bare id from `urn.partition(":")` alone. The plan's
    # kind-filtered field is kind-bucketed (issue #3772), same
    # kind -> sorted-bare-IDs shape as the activate-side siblings, so the
    # render order (kinds sorted, then ids sorted within each kind) is
    # byte-identical to the previous flat sorted-URN iteration.
    # The deactivations above are done; this render only reads (#5526).
    render_pass = ResolutionPass()
    for kind_value in sorted(plan.not_cascaded_kind_filtered):
        kind_token = ArtifactKind(kind_value).operator_token
        for filtered_id in plan.not_cascaded_kind_filtered[kind_value]:
            config_id = drg_urn_to_config_id(
                f"{kind_value}:{filtered_id}", offering_root, layer_roots, org_roots, render_pass
            )
            render_kind_filtered_line(kind_token, config_id)


def _refuse_unmigrated(kind: str, repo_root: Path) -> None:
    """Exit 1 with the rendered refusal when an artifact *kind* is deactivated on an unmigrated project.

    A ``mission-type`` deactivation records no deny entry (nor do its cascade
    children, D-11), so it keeps the legacy target as on ``main``.
    """
    try:
        ArtifactKind.from_operator_token(kind)
    except MissionTypeNotAnArtifactKind:
        return
    try:
        refuse_unmigrated_deny_write(repo_root)
    except ActiveCharterConfigError as exc:
        render_pack_config_error(exc, console)
        raise typer.Exit(1) from exc


def deactivate_cmd(
    ctx: typer.Context,
    kind: str | None = typer.Argument(None, help="Activation kind (e.g. directive, agent-profile)."),
    artifact_id: str | None = typer.Argument(None, help="Artifact ID to deactivate."),
    cascade: str | None = typer.Option(
        None,
        "--cascade",
        help=(
            "Cascade deactivation scope: 'all' for every exclusively-referenced "
            "kind, or a comma-separated kind list. Shared artifacts are never "
            "removed. Omit to deactivate only the named artifact."
        ),
    ),
    resynthesize: bool = typer.Option(
        False,
        "--resynthesize/--no-resynthesize",
        help=RESYNTHESIZE_HELP,
    ),
    compile_catalog: bool = typer.Option(
        True,
        "--compile/--no-compile",
        help=NO_COMPILE_HELP,
    ),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Deactivate a doctrine artifact by kind and ID (FR-005), with optional cascade."""
    if ctx.invoked_subcommand is not None:
        return
    if kind is None or artifact_id is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)
    if kind not in YAML_KEY_MAP:
        console.print(f"[red]Error:[/red] Unknown kind '{kind}'. Valid kinds: {', '.join(sorted(YAML_KEY_MAP))}.")
        raise typer.Exit(1)

    # FR-006/Contract C3: fail closed from a linked git worktree before any
    # mutation, and resolve the ONE checkout root every downstream call in
    # this command shares from here on (symmetric with activate_cmd; issue
    # #4785 Finding 3).
    repo_root = resolve_write_root_or_exit(repo_root)

    # FR-015/016: parse the scope value object — never collapsed to a bool (C3.3).
    try:
        scope = CascadeScope.parse(cascade)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    # FR-017, hole 2: an artifact deactivation records a deny entry, which an
    # unmigrated project cannot hold. Refuse the direct and the cascade path
    # alike, before any write and before the required-floor read (NFR-001).
    _refuse_unmigrated(kind, repo_root)

    # FR-035 fail-closed: reject invalid pack config before any mutation (C1.5).
    try:
        validate_pack_config(repo_root)
    except ActiveCharterConfigError as exc:
        render_pack_config_error(exc, console)
        raise typer.Exit(1) from exc

    ctx_project = ProjectContext(repo_root=repo_root)
    layer_roots = resolve_layer_roots(repo_root)
    manager = ActiveCharterManager()

    try:
        result = manager.deactivate(
            ctx_project,
            kind,
            artifact_id,
            cascade=scope is not None,
            layer_roots=layer_roots,
        )
    except DeactivationRefused as exc:
        # FR-007 / US4.1: an org-required id; nothing was written (NFR-001).
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except ActiveCharterConfigError as exc:
        # FR-013: the strict required floor (or the ledger) cannot be read.
        render_pack_config_error(exc, console)
        raise typer.Exit(1) from exc
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    for msg in result.deactivated:
        console.print(f"[green]Deactivated[/green]: {msg}")
    for warn in result.warnings:
        console.print(f"[yellow]Warning[/yellow]: {warn}")

    # #4115: warn when the artifact just removed is a built-in mission-step
    # default profile (direct-deactivation half; the cascade path warns per
    # artifact inside ``_render_cascade_deactivation``).
    if result.deactivated and kind == ArtifactKind.AGENT_PROFILE.operator_token:
        _warn_mission_default_binding(
            artifact_id.removeprefix(f"{ArtifactKind.AGENT_PROFILE.value}:")
        )

    # FR-015/FR-016, D-11: shared-reference-safe cascade deactivation via the
    # WP11 engine. It runs whenever a scope was supplied, also when the named
    # id was only implicitly active ("absent = all"), and records no exclusion
    # for the children.
    if scope is not None:
        target_urn = _source_urn(kind, artifact_id, layer_roots, resolve_pack_chain(repo_root, strict=False))
        if target_urn is not None:
            _render_cascade_deactivation(
                manager, ctx_project, target_urn, scope, repo_root, layer_roots, result.deactivated[0] if result.deactivated else artifact_id
            )

    # FR-002/FR-003/FR-007: default catalog recompile keeps deactivation
    # coherent-by-construction too (symmetric with activate_cmd; issue #4785
    # Finding 1), run AFTER cascade so it reconciles the complete
    # post-deactivation config state. See `recompile_or_notify` for the
    # resynthesize/compile/no-compile precedence.
    recompile_or_notify(repo_root, resynthesize=resynthesize, compile_catalog=compile_catalog)
    reproject_pack_skills(repo_root, kind)
