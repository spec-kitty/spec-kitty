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
from charter.activation.pack_manager import ActiveCharterManager, DeactivationRefused
from charter.activation.kind_vocabulary import ArtifactKind, MissionTypeNotAnArtifactKind

from charter.activation.api import ActivationResult
from specify_cli.cli.commands.charter._activation_report import (
    ActivationChangeReport,
    ArtifactRef,
    CascadeEntry,
    CascadeOutcome,
    CascadeReport,
)
from specify_cli.cli.commands.charter._cascade_shared import (
    drg_urn_to_config_id,
    render_kind_filtered_line,
)
from specify_cli.cli.commands.charter.activate import (
    ACTIVATION_FAILED,
    DEACTIVATION_REFUSED_REQUIRED,
    NO_COMPILE_HELP,
    RESYNTHESIZE_HELP,
    CodedRefusal,
    check_activation_kind,
    config_refusal,
    emit_change_report_json,
    mission_type_urn,
    parse_cascade_scope,
    recompile_or_notify,
    render_refusal,
    reproject_pack_skills,
    resolve_write_root,
    scope_label,
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


def _cascade_child_entry(
    manager: ActiveCharterManager,
    ctx_project: ProjectContext,
    ref: ArtifactRef,
    *,
    layer_roots: dict[str, Path] | None,
    allow_absent: bool,
) -> CascadeEntry | None:
    """Drop one exclusive child's allow entry (no deny entry, D-11); return its outcome, or ``None`` when nothing changed."""
    if allow_absent:
        return CascadeEntry(CascadeOutcome.STILL_ACTIVE_UNRESTRICTED, ref)
    try:
        result = manager.deactivate(ctx_project, ref.kind, ref.id, cascade=False, layer_roots=layer_roots, record_exclusion=False)
    except DeactivationRefused as exc:
        return CascadeEntry(CascadeOutcome.SKIPPED_REQUIRED, ref, packs=tuple(entry.pack for entry in getattr(exc, "requiring", ())))
    except ValueError as exc:
        return CascadeEntry(CascadeOutcome.FAILED, ref, message=str(exc))
    if not result.deactivated:
        return None
    # #4115: a cascade can remove agent profiles bound by built-in
    # mission steps exactly like a direct deactivation can.
    warning = mission_default_profile_warning(ref.id) if ref.kind == ArtifactKind.AGENT_PROFILE.operator_token else None
    return CascadeEntry(CascadeOutcome.CASCADED, ref, message=warning)


def _render_cascade_entry(entry: CascadeEntry, source_id: str) -> None:
    """Print one cascade-deactivation line (plus a cascaded profile's mission-step warning)."""
    label = entry.ref.label
    if entry.outcome is CascadeOutcome.STILL_ACTIVE_UNRESTRICTED:
        console.print(f"[cyan]Cascade[/cyan]: {label}: still active (no allow-list; only {source_id} excluded)")
    elif entry.outcome is CascadeOutcome.SKIPPED_REQUIRED:
        console.print(f"[yellow]Cascade[/yellow]: {label}: skipped (required by {', '.join(entry.packs)})")
    elif entry.outcome is CascadeOutcome.FAILED:
        console.print(f"[yellow]Warning[/yellow]: could not cascade-deactivate {label}: {entry.message}")
    elif entry.outcome is CascadeOutcome.SKIPPED_SHARED:
        console.print(f"[yellow]Skipped (shared artifact)[/yellow]: {entry.ref.urn} (still referenced by {entry.referenced_by})")
    elif entry.outcome is CascadeOutcome.SKIPPED_KIND_FILTERED:
        render_kind_filtered_line(entry.ref.kind, entry.ref.id)
    else:
        console.print(f"[cyan]Cascade-deactivated[/cyan]: {label}")
        if entry.message is not None:
            console.print(f"[yellow]Warning[/yellow]: {entry.message}")


def _cascade_deactivation_report(
    manager: ActiveCharterManager,
    ctx_project: ProjectContext,
    target_urn: str,
    scope: CascadeScope,
    repo_root: Path,
    layer_roots: dict[str, Path] | None,
) -> CascadeReport:
    """Cascade-deactivate exclusive referenced artifacts; keep shared ones (FR-015/016, C-007).

    Uses the WP11 :func:`charter.activation.cascade.deactivation_plan` over the merged DRG.
    Exclusive candidates lose only their allow-list entry (no exclusion is
    recorded for them, D-11); a child of a kind with no allow-list stays
    active and is reported so; a required child is skipped naming its pack.
    Shared candidates are reported (never removed — Contract C3.4) with the
    still-referencing active source named.

    T010 (mission ``cascade-org-inert-01M07E9P``): threads the full org-pack
    chain into the DRG load, the active-URN resolution, and the ID mapping
    below — same rationale as ``activate.py``'s ``_cascade_activation_report``.
    The entries are in render order (:func:`render_cascade_deactivation`).
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

    def ref_of(urn: str, resolution_pass: ResolutionPass | None = None) -> ArtifactRef:
        kind_token = ArtifactKind(urn.partition(":")[0]).operator_token
        return ArtifactRef(kind_token, drg_urn_to_config_id(urn, offering_root, layer_roots, org_roots, resolution_pass), urn)

    entries: list[CascadeEntry] = []
    for urn in plan.deactivate:
        ref = ref_of(urn)
        entry = _cascade_child_entry(manager, ctx_project, ref, layer_roots=layer_roots, allow_absent=allow_state.get(ref.kind, ()) is None)
        if entry is not None:
            entries.append(entry)

    # The deactivations above are done; everything below only reads (#5526).
    render_pass = ResolutionPass()
    for skip in plan.skipped_shared:
        ref = ref_of(skip.urn, render_pass)
        if allow_state.get(ref.kind, ()) is None:
            # No allow-list: the child stays active whoever references it.
            entries.append(CascadeEntry(CascadeOutcome.STILL_ACTIVE_UNRESTRICTED, ref))
        else:
            entries.append(CascadeEntry(CascadeOutcome.SKIPPED_SHARED, ref, referenced_by=skip.referencing_active_urn))

    # FR-007 (issue #3705): the deactivation-side half of C-002's
    # cross-command symmetry (ADR 2026-08-20-1 Symmetry section) -- report
    # the kind-filtered nodes `deactivation_plan` collected via the shared
    # `_referenced_artifacts` seam instead of silently dropping them,
    # resolving each bare id to its config-stem id first (never the raw bare
    # id). The plan's kind-filtered field is kind-bucketed (issue #3772):
    # kinds sorted, then ids sorted within each kind.
    for kind_value in sorted(plan.not_cascaded_kind_filtered):
        for filtered_id in plan.not_cascaded_kind_filtered[kind_value]:
            entries.append(CascadeEntry(CascadeOutcome.SKIPPED_KIND_FILTERED, ref_of(f"{kind_value}:{filtered_id}", render_pass)))
    return CascadeReport(target_urn, scope_label(scope), tuple(entries))


def render_cascade_deactivation(report: CascadeReport, source_id: str) -> None:
    """Print a cascade deactivation report, one line per entry, in order."""
    for entry in report.entries:
        _render_cascade_entry(entry, source_id)


def render_deactivation_change(report: ActivationChangeReport, source_id: str) -> None:
    """Print a positional deactivation's change report, in the order the command has always printed it."""
    for msg in report.changed:
        console.print(f"[green]Deactivated[/green]: {msg}")
    for warn in report.warnings:
        console.print(f"[yellow]Warning[/yellow]: {warn}")
    if report.cascade is not None:
        render_cascade_deactivation(report.cascade, source_id)


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
        raise config_refusal(exc) from exc


def _deactivation_preflight(kind: str, cascade: str | None, repo_root: Path) -> tuple[Path, CascadeScope | None]:
    """Every check before the first write: kind, write root, scope, unmigrated refusal, pack config.

    Every refusal is a :class:`CodedRefusal`.
    """
    check_activation_kind(kind)
    # FR-006/Contract C3: fail closed from a linked git worktree before any
    # mutation, and resolve the ONE checkout root every downstream call in
    # this command shares from here on (symmetric with activate_cmd; issue
    # #4785 Finding 3).
    repo_root = resolve_write_root(repo_root)

    # FR-015/016: parse the scope value object — never collapsed to a bool (C3.3).
    scope = parse_cascade_scope(cascade)

    # FR-017, hole 2: an artifact deactivation records a deny entry, which an
    # unmigrated project cannot hold. Refuse the direct and the cascade path
    # alike, before any write and before the required-floor read (NFR-001).
    _refuse_unmigrated(kind, repo_root)

    # FR-035 fail-closed: reject invalid pack config before any mutation (C1.5).
    try:
        validate_pack_config(repo_root)
    except ActiveCharterConfigError as exc:
        raise config_refusal(exc) from exc
    return repo_root, scope


def _deactivation_refusal(exc: DeactivationRefused) -> CodedRefusal:
    """``DEACTIVATION_REFUSED_REQUIRED`` naming the requiring packs; any other policy reason is ``ACTIVATION_FAILED``."""
    if exc.reason != "required":
        return CodedRefusal(ACTIVATION_FAILED, str(exc))
    packs = [entry.pack for entry in getattr(exc, "requiring", ())]
    return CodedRefusal(DEACTIVATION_REFUSED_REQUIRED, str(exc), {"requiring_packs": packs})


def _apply_direct_deactivation(
    manager: ActiveCharterManager, ctx_project: ProjectContext, kind: str, artifact_id: str, *, cascade: bool, layer_roots: dict[str, Path] | None
) -> ActivationResult:
    """Deactivate the named artifact (the one direct write)."""
    try:
        return manager.deactivate(ctx_project, kind, artifact_id, cascade=cascade, layer_roots=layer_roots)
    except DeactivationRefused as exc:
        # FR-007 / US4.1: an org-required id; nothing was written (NFR-001).
        raise _deactivation_refusal(exc) from exc
    except ActiveCharterConfigError as exc:
        # FR-013: the strict required floor (or the ledger) cannot be read.
        raise config_refusal(exc) from exc
    except ValueError as exc:
        raise CodedRefusal(ACTIVATION_FAILED, str(exc)) from exc


def _deactivation_change_report(kind: str, artifact_id: str, cascade: str | None, repo_root: Path) -> tuple[Path, ActivationChangeReport, str]:
    """Run a positional deactivation (direct write, then cascade).

    Returns the write root, the change report and the source id the cascade lines name.
    """
    repo_root, scope = _deactivation_preflight(kind, cascade, repo_root)
    ctx_project = ProjectContext(repo_root=repo_root)
    layer_roots = resolve_layer_roots(repo_root)
    manager = ActiveCharterManager()
    result = _apply_direct_deactivation(manager, ctx_project, kind, artifact_id, cascade=scope is not None, layer_roots=layer_roots)

    # #4115: warn when the artifact just removed is a built-in mission-step
    # default profile (direct-deactivation half; the cascade path warns per
    # artifact through its cascaded entries).
    warnings = list(result.warnings)
    if result.deactivated and kind == ArtifactKind.AGENT_PROFILE.operator_token:
        warning = mission_default_profile_warning(artifact_id.removeprefix(f"{ArtifactKind.AGENT_PROFILE.value}:"))
        if warning is not None:
            warnings.append(warning)

    # FR-015/FR-016, D-11: shared-reference-safe cascade deactivation via the
    # WP11 engine. It runs whenever a scope was supplied, also when the named
    # id was only implicitly active ("absent = all"), and records no exclusion
    # for the children.
    cascade_report: CascadeReport | None = None
    if scope is not None:
        target_urn = _source_urn(kind, artifact_id, layer_roots, resolve_pack_chain(repo_root, strict=False))
        if target_urn is not None:
            cascade_report = _cascade_deactivation_report(manager, ctx_project, target_urn, scope, repo_root, layer_roots)
    report = ActivationChangeReport(
        command="deactivate", kind=kind, id=artifact_id, changed=tuple(result.deactivated), warnings=tuple(warnings), cascade=cascade_report
    )
    return repo_root, report, result.deactivated[0] if result.deactivated else artifact_id


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
    json_output: bool = typer.Option(False, "--json", help="Output the change report as JSON."),
    repo_root: Path = typer.Option(Path("."), hidden=True),
) -> None:
    """Deactivate a doctrine artifact by kind and ID (FR-005), with optional cascade."""
    if ctx.invoked_subcommand is not None:
        return
    if kind is None or artifact_id is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)

    if json_output:
        emit_change_report_json(
            lambda: _deactivation_change_report(kind, artifact_id, cascade, repo_root)[:2],
            kind=kind,
            resynthesize=resynthesize,
            compile_catalog=compile_catalog,
        )
        return
    try:
        repo_root, report, source_id = _deactivation_change_report(kind, artifact_id, cascade, repo_root)
    except CodedRefusal as refusal:
        render_refusal(refusal, json_output=False)
    render_deactivation_change(report, source_id)

    # FR-002/FR-003/FR-007: default catalog recompile keeps deactivation
    # coherent-by-construction too (symmetric with activate_cmd; issue #4785
    # Finding 1), run AFTER cascade so it reconciles the complete
    # post-deactivation config state. See `recompile_or_notify` for the
    # resynthesize/compile/no-compile precedence.
    recompile_or_notify(repo_root, resynthesize=resynthesize, compile_catalog=compile_catalog)
    reproject_pack_skills(repo_root, kind)
