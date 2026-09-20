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
* :class:`charter.activation.activation_engine.NoActivationRestrictionsError` (raised by
  the WP10 engine for a None-state kind) is caught and surfaced as a clean
  exit-1 with the upgrade guidance.
* :class:`charter.activation.pack_context.CharterPackConfigError` is caught and surfaced as
  fail-closed guidance before any mutation (FR-035, C1.5).
"""

from __future__ import annotations

from pathlib import Path

import typer
from specify_cli.cli.console import console

from charter.activation.activation_engine import NoActivationRestrictionsError
from charter.activation.cascade import CascadeScope, deactivation_plan
from charter.activation.catalog import resolve_doctrine_root
from charter.activation.drg_activation import load_org_drg
from charter.activation.invocation_context import ProjectContext
from charter.activation.kind_vocabulary import (
    UnknownArtifactIdError,
    resolve_artifact_urn,
)
from charter.activation.pack_context import CharterPackConfigError
from charter.activation.pack_manager import YAML_KEY_MAP, CharterPackManager
from charter.activation.kind_vocabulary import ArtifactKind, MissionTypeNotAnArtifactKind

from specify_cli.cli.commands.charter._cascade_shared import (
    drg_urn_to_config_id,
    render_kind_filtered_line,
)
from specify_cli.cli.commands.charter.activate import (
    NO_COMPILE_HELP,
    RESYNTHESIZE_HELP,
    recompile_or_notify,
    render_pack_config_error,
    resolve_write_root_or_exit,
    validate_pack_config,
)
from specify_cli.cli.commands.charter._layer_roots import (
    resolve_layer_roots,
    resolve_org_root_chain,
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
    ``specify_cli.cli.commands.charter._layer_roots.resolve_org_root_chain``.
    """
    try:
        kind_enum = ArtifactKind.from_operator_token(kind)
    except MissionTypeNotAnArtifactKind:
        return None
    try:
        return resolve_artifact_urn(
            kind_enum,
            artifact_id,
            doctrine_root=resolve_doctrine_root(),
            org_roots=org_roots,
            layer_roots=layer_roots,
        )
    except UnknownArtifactIdError:
        return None


def _active_urns(
    manager: CharterPackManager,
    ctx_project: ProjectContext,
    layer_roots: dict[str, Path] | None,
    org_roots: list[Path] | None = None,
) -> set[str]:
    """Return the set of currently-activated artifact URNs across all kinds.

    Resolves each activated config-stem ID back to its DRG URN. IDs with no
    resolvable DRG node (or mission-type, which is not an artifact kind) are
    skipped — they cannot participate in DRG reachability anyway.

    ``org_roots`` (T008/T010): full org-pack chain — without it, a currently-
    active artifact whose config-stem lives only in org pack 2..N could not
    resolve its DRG URN at all here, so it would silently drop out of the
    ``active`` set that :func:`charter.activation.cascade.deactivation_plan` uses for
    Contract C3.4 shared-reference safety (NFR-002: a dropped active URN is a
    silent-wrong-data risk, not merely a display gap).
    """
    doctrine_root = resolve_doctrine_root()
    urns: set[str] = set()
    for kind_token, ids in manager.list_activated(ctx_project).items():
        if ids is None:
            continue
        try:
            kind_enum = ArtifactKind.from_operator_token(kind_token)
        except MissionTypeNotAnArtifactKind:
            continue
        for config_id in ids:
            try:
                urns.add(
                    resolve_artifact_urn(
                        kind_enum,
                        config_id,
                        doctrine_root=doctrine_root,
                        org_roots=org_roots,
                        layer_roots=layer_roots,
                    )
                )
            except UnknownArtifactIdError:
                continue
    return urns


def _render_cascade_deactivation(
    manager: CharterPackManager,
    ctx_project: ProjectContext,
    target_urn: str,
    scope: CascadeScope,
    repo_root: Path,
    layer_roots: dict[str, Path] | None,
) -> None:
    """Cascade-deactivate exclusive referenced artifacts; keep shared ones (FR-015/016).

    Uses the WP11 :func:`charter.activation.cascade.deactivation_plan` over the merged DRG.
    Exclusive candidates are removed through the same activation seam; shared
    candidates are reported (never removed — Contract C3.4) with the still-
    referencing active source named.

    T010 (mission ``cascade-org-inert-01M07E9P``): threads the full org-pack
    chain into the DRG load, the active-URN resolution, and the ID mapping
    below — same rationale as ``activate.py``'s ``_render_cascade_activation``.
    Previously this call carried NO org roots at all.
    """
    from charter.activation._drg_helpers import load_validated_graph  # noqa: PLC0415

    org_roots = resolve_org_root_chain(repo_root)
    graph = load_validated_graph(
        repo_root,
        org_roots=org_roots,
        org_fragments=load_org_drg(repo_root, strict=False),
    )
    active = _active_urns(manager, ctx_project, layer_roots, org_roots)
    plan = deactivation_plan(graph, target_urn, scope, active_urns=active)
    doctrine_root = resolve_doctrine_root()

    for urn in plan.deactivate:
        kind_value, _, _ = urn.partition(":")
        kind_token = ArtifactKind(kind_value).operator_token
        config_id = drg_urn_to_config_id(urn, doctrine_root, layer_roots, org_roots)
        try:
            manager.deactivate(
                ctx_project,
                kind_token,
                config_id,
                cascade=False,
                layer_roots=layer_roots,
            )
        except (ValueError, NoActivationRestrictionsError) as exc:
            console.print(
                f"[yellow]Warning[/yellow]: could not cascade-deactivate "
                f"{kind_token}/{config_id}: {exc}"
            )
            continue
        console.print(f"[cyan]Cascade-deactivated[/cyan]: {kind_token}/{config_id}")
        # #4115: a cascade can remove agent profiles bound by built-in
        # mission steps exactly like a direct deactivation can.
        if kind_token == ArtifactKind.AGENT_PROFILE.operator_token:
            _warn_mission_default_binding(config_id)

    for skip in plan.skipped_shared:
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
    for kind_value in sorted(plan.not_cascaded_kind_filtered):
        kind_token = ArtifactKind(kind_value).operator_token
        for filtered_id in plan.not_cascaded_kind_filtered[kind_value]:
            config_id = drg_urn_to_config_id(
                f"{kind_value}:{filtered_id}", doctrine_root, layer_roots, org_roots
            )
            render_kind_filtered_line(kind_token, config_id)


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

    # FR-035 fail-closed: reject invalid pack config before any mutation (C1.5).
    try:
        validate_pack_config(repo_root)
    except CharterPackConfigError as exc:
        render_pack_config_error(exc, console)
        raise typer.Exit(1) from exc

    ctx_project = ProjectContext(repo_root=repo_root)
    layer_roots = resolve_layer_roots(repo_root)
    manager = CharterPackManager()

    try:
        result = manager.deactivate(
            ctx_project,
            kind,
            artifact_id,
            cascade=scope is not None,
            layer_roots=layer_roots,
        )
    except NoActivationRestrictionsError as exc:
        # WP10 engine raises this for a None-state kind; surface the upgrade
        # guidance carried in the error and exit non-zero (no mutation).
        console.print(f"[red]Error:[/red] {exc}")
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

    # FR-015/FR-016: shared-reference-safe cascade deactivation via the WP11 engine.
    # Only runs when a scope was supplied and the direct deactivation actually
    # removed the target (so we never cascade off a no-op removal).
    if scope is not None and result.deactivated:
        target_urn = _source_urn(kind, artifact_id, layer_roots, resolve_org_root_chain(repo_root))
        if target_urn is not None:
            _render_cascade_deactivation(
                manager, ctx_project, target_urn, scope, repo_root, layer_roots
            )

    # FR-002/FR-003/FR-007: default catalog recompile keeps deactivation
    # coherent-by-construction too (symmetric with activate_cmd; issue #4785
    # Finding 1), run AFTER cascade so it reconciles the complete
    # post-deactivation config state. See `recompile_or_notify` for the
    # resynthesize/compile/no-compile precedence.
    recompile_or_notify(repo_root, resynthesize=resynthesize, compile_catalog=compile_catalog)
