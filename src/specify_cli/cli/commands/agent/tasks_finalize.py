"""The ``finalize-tasks`` command family, relocated out of ``tasks.py`` (WP08, #2058).

Mission ``tasks-py-degod-wave2-01KWH9EQ`` FR-001/FR-002: ``_do_finalize_tasks``
+ the 4 ``_ft_*`` phase helpers + ``_FinalizeState`` +
``_default_finalize_ports`` live here, moved VERBATIM from ``tasks.py`` — the
squad-recovered FIFTH family, completing the family relocations (after this
move ALL five command families are out of ``tasks.py``). The ``@app.command``
Typer wrapper (``finalize_tasks``) stays in ``tasks.py`` and delegates to
:func:`_do_finalize_tasks` (the byte-frozen ``--help`` surface is the
registration shim's).

**Orchestration shape** (unchanged): the phase helpers run in the SAME order
as the original single body — resolve → validate → apply → output — so the
frontmatter writes still fire only after every validation gate has passed
(NFR-002). ``finalize_tasks`` is CORELESS (FR-007/FR-010): it validates
through the existing ``tasks_finalize_validation`` seam and has ZERO direct
emission sites (research.md D3) — no byte case is owned by this family.

**Seam bridge** (research.md D1/D7): the relocated bodies reach every patched
seam symbol through a lazy in-function import of the ``tasks`` module
(``from specify_cli.cli.commands.agent import tasks as _tasks``) and call
``_tasks.<attr>(...)``, so every historical ``@patch("...agent.tasks.<sym>")``
/ ``monkeypatch.setattr(tasks, ...)`` keeps INTERCEPTING after the move —
including ``bootstrap_canonical_state`` (×7, test_tasks_canonical_cleanup),
the conftest ``console`` rebinding, and the port adapters constructed by
``_default_finalize_ports`` (which builds the plain ``RealCoordCommitRouter``
— finalize commits nothing itself; the router is the bundle's inert WRITE
authority). ``tasks.py`` re-imports the family in the explicit ``as``
re-export form, so ``tasks.<name>`` stays a module attribute. Symbols with
ZERO patch sites and a canonical home outside ``tasks.py`` (the
``tasks_finalize_validation`` gates, the pre30 guard, ``TASKS_MD_FILENAME``)
are imported directly at module scope (cycle-safe: none of those modules
import ``tasks``). read-surface-ssot-closeout WP08 (FR-001/NFR-001): the
former ``resolve_feature_dir_for_mission`` pre30-guard-wiring seam is
RETIRED — ``_ft_apply_writes`` now calls
``mission_runtime.placement_seam(...).read_dir(STATUS_STATE)`` directly
(module-scope import, not the ``_tasks.<attr>`` proxy).

Per-symbol routing/interception evidence:
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md`` (Layer 4 of
the parity contract).
"""

from __future__ import annotations

import contextlib
import logging
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.agent_tasks_ports import MissionHandle, TasksPorts
from specify_cli.cli.commands._coordination_doctor import check_and_warn_coord_staleness
from specify_cli.cli.commands.agent.tasks_finalize_validation import (
    FrontmatterUpdatePlan,
    compute_wp_frontmatter_updates,
    detect_dependency_conflicts,
    read_existing_frontmatter,
    validate_wp_coverage,
)
from specify_cli.cli.commands.agent.tasks_outline import TASKS_MD_FILENAME
from specify_cli.status import BootstrapResult
from specify_cli.upgrade.pre30_guard import Pre30LayoutError, check_pre30_layout

if TYPE_CHECKING:
    from specify_cli.status import WPMetadata

logger = logging.getLogger(__name__)


@dataclass
class _FinalizeState:
    """Mutable orchestration state threaded through ``finalize_tasks``'s phases.

    Not frozen: each phase fills its own slice in the SAME order the original body
    did (resolve → validate → apply → output), so the frontmatter writes still fire
    only after every validation gate has passed.
    """

    # --- raw command inputs ---
    mission: str | None
    json_output: bool
    validate_only: bool
    # --- phase A: resolved context ---
    repo_root: Path = field(default_factory=Path)
    main_repo_root: Path = field(default_factory=Path)
    target_branch: str = ""
    mission_slug: str = ""
    primary_feature_dir: Path = field(default_factory=Path)
    tasks_md: Path = field(default_factory=Path)
    tasks_dir: Path = field(default_factory=Path)
    # --- phase B: parsed/validated reads ---
    dependencies_map: dict[str, list[str]] = field(default_factory=dict)
    # --- phase C: applied writes + bootstrap ---
    update_plan: FrontmatterUpdatePlan | None = None
    would_modify: list[dict[str, object]] = field(default_factory=list)
    feature_dir: Path = field(default_factory=Path)
    bootstrap_result: BootstrapResult | None = None


def _default_finalize_ports() -> TasksPorts:
    """Production port bundle for ``finalize_tasks`` (FsReader read authority)."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    return TasksPorts(
        fs=_tasks.RealFsReader(),
        coord=_tasks.RealCoordCommitRouter(),
        git=_tasks.RealGitOps(),
        render=_tasks.RealRender(),
    )


def _ft_resolve_context(st: _FinalizeState, ports: TasksPorts) -> None:
    """Phase A: repo/branch/read-dir resolution + the pre30 guard + existence checks.

    FR-010 / T035: the pre30-guard read is GUARD-ONLY (the coord-husk var fed ONLY
    ``check_pre30_layout`` before being reassigned to the primary read), so migrate
    it onto the kind-aware WORK_PACKAGE_TASK authority via the ``FsReader`` port.
    ``tasks.md`` and ``tasks/`` are PRIMARY-partition (FR-001 / C-001 per-leg split),
    so this single read feeds BOTH the guard and the parse. The WP02 T013 proof
    establishes the guard outcome is byte-identical across legs on a modern mission
    (SC-002/NFR-001). Only the STATUS artifacts (bootstrap, event log) use the
    coord-aware resolver in phase C.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    repo_root = _tasks.locate_project_root()
    if repo_root is None:
        _tasks._output_error(st.json_output, "Could not locate project root")
        raise typer.Exit(1)
    st.repo_root = repo_root
    # FR-010 / FR-019: one-shot sparse-checkout session warning.
    _tasks._emit_sparse_session_warning(repo_root, command="spec-kitty agent tasks finalize-tasks")
    st.mission_slug = _tasks._find_mission_slug(explicit_mission=st.mission, json_output=st.json_output, repo_root=repo_root)
    st.main_repo_root, st.target_branch = _tasks._ensure_target_branch_checked_out(repo_root, st.mission_slug, st.json_output)
    handle = MissionHandle(repo_root=st.main_repo_root, mission_slug=st.mission_slug)
    st.primary_feature_dir = ports.fs.planning_read_dir(handle, kind=MissionArtifactKind.WORK_PACKAGE_TASK)
    # Boundary guard — hard-reject pre-3.0 layout before any WP mutation (#1057)
    try:
        check_pre30_layout(st.primary_feature_dir)
    except Pre30LayoutError as e:
        _tasks._output_error(st.json_output, str(e))
        raise typer.Exit(1) from None
    st.tasks_md = st.primary_feature_dir / TASKS_MD_FILENAME
    st.tasks_dir = st.primary_feature_dir / "tasks"

    if not st.tasks_md.exists():
        _tasks._output_error(st.json_output, f"tasks.md not found: {st.tasks_md}")
        raise typer.Exit(1)
    if not st.tasks_dir.exists():
        _tasks._output_error(st.json_output, f"Tasks directory not found: {st.tasks_dir}")
        raise typer.Exit(1)


def _ft_validate_occurrence_map_ready(st: _FinalizeState) -> None:
    """Bulk-edit occurrence-map gate (mirrors ``mission_finalize._validate_occurrence_map_ready``).

    ``spec-kitty agent tasks finalize-tasks`` (this legacy command family) and
    ``spec-kitty agent mission finalize-tasks`` are two independently-dispatched
    commands that both advance a mission past the tasks-finalize boundary.
    Gating only the ``mission`` variant left this one able to complete
    finalize-tasks for a bulk-edit mission with a missing / schema-invalid /
    inadmissible ``occurrence_map.yaml`` with zero gate friction — the exact
    late-failure timing the occurrence-map gate exists to eliminate (found by
    the pre-hand-off adversarial squad, architect-alphonso lens, during
    landing). Reuses ``ensure_occurrence_classification_ready`` unchanged (no
    new validation logic) and self-conditions on stored ``change_mode``, so
    non-bulk-edit missions are unaffected — same contract as the other
    enforcement points.
    """
    from specify_cli.bulk_edit.gate import (
        FINALIZE_TASKS_GATE_BLOCKED_MESSAGE,
        ensure_occurrence_classification_ready,
        finalize_tasks_gate_error_payload,
        render_gate_failure,
    )
    from specify_cli.cli.commands.agent import tasks as _tasks

    result = ensure_occurrence_classification_ready(st.primary_feature_dir)
    if result.passed:
        return
    if st.json_output:
        _tasks._output_error(
            st.json_output,
            FINALIZE_TASKS_GATE_BLOCKED_MESSAGE,
            finalize_tasks_gate_error_payload(result),
        )
    else:
        render_gate_failure(result, _tasks.console)
    raise typer.Exit(1)


def _ft_validate(st: _FinalizeState) -> None:
    """Phase B: occurrence-map gate + parse deps + WP04 coverage/graph/disagree-loud conflict gates.

    Each gate is a PRE-write refusal — the frontmatter writes in phase C fire only
    after every gate below passes. The occurrence-map gate runs FIRST (fail-fast,
    before the more expensive dependency-graph validators), mirroring the
    placement in ``mission_finalize.finalize_tasks``.

    #4890: the dependency-graph gate validates the EFFECTIVE PERSISTED graph —
    ``compute_wp_frontmatter_updates``'s ``effective_dependencies`` (tasks.md-parsed
    deps merged with any PRESERVED frontmatter deps, i.e. the graph phase C is
    about to write) — not just the raw tasks.md-parsed map. A cycle/self-ref/
    unknown-WP hiding only in preserved frontmatter must be rejected before any
    write, using the SAME validator ``agent mission finalize-tasks`` already
    uses (single authority — ``mission_finalize._validate_dependency_graph``,
    which runs both ``detect_cycles`` and ``validate_dependencies``). The
    computed plan is stashed on ``st.update_plan`` so phase C does not
    recompute it (it is side-effect-free/pure, but reads disk).
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.cli.commands.agent.mission_finalize import _validate_dependency_graph
    from specify_cli.core.dependency_parser import (
        parse_dependencies_from_tasks_md as _shared_parse_deps,
    )

    _ft_validate_occurrence_map_ready(st)

    tasks_content = st.tasks_md.read_text(encoding="utf-8")
    st.dependencies_map = _shared_parse_deps(tasks_content)

    coverage = validate_wp_coverage(st.dependencies_map, st.tasks_dir)
    if not coverage.ok:
        _tasks._output_error(
            st.json_output,
            (
                "tasks.md work package coverage is incomplete. finalize-tasks could not match "
                "all WP files to parsed sections, so dependency lanes would be unreliable."
            ),
        )
        raise typer.Exit(1)

    st.update_plan = compute_wp_frontmatter_updates(st.dependencies_map, st.tasks_dir)
    _validate_dependency_graph(st.update_plan.effective_dependencies, json_output=st.json_output)

    # --- Dependency conflict detection (T004: disagree-loud) ---
    existing_frontmatter = read_existing_frontmatter(st.tasks_dir)
    dep_conflict_errors = detect_dependency_conflicts(st.dependencies_map, existing_frontmatter)
    if dep_conflict_errors:
        error_msg = "Dependency disagreement detected:\n" + "\n".join(dep_conflict_errors)
        _tasks._output_error(st.json_output, error_msg)
        raise typer.Exit(1)


def _ft_apply_writes(st: _FinalizeState) -> None:
    """Phase C: apply the computed frontmatter writes (validate-only-gated) + bootstrap.

    The frontmatter updates are computed side-effect-free, then applied gating ALL
    writes on ``validate_only`` (T005/T006). Bootstrap reads the event log/meta.json
    via the topology-aware (STATUS-partition) resolver — it MUST stay coord-aware.

    ``_gather_wp_frontmatter_and_bodies``/``_finalize_lanes`` below (WP01,
    #4758) are nested rather than module-level: this module's compat surface
    is tracked by an exhaustive census guard
    (``tests/specify_cli/cli/commands/agent/test_tasks_compat_surface.py``)
    that re-derives every natively-defined, module-scope callable from
    source — nesting keeps these two helpers purely an implementation detail
    of this phase without adding new entries to that unrelated inventory.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    from specify_cli.frontmatter import write_frontmatter as _write_fm

    def _gather_wp_frontmatter_and_bodies(
        tasks_dir: Path,
    ) -> tuple[dict[str, WPMetadata], dict[str, str]]:
        """Read every WP file's frontmatter + body from ``tasks_dir`` (#4758).

        Mirrors ``tasks_finalize_validation.read_existing_frontmatter``'s file
        discovery (``tasks_dir.glob("WP*.md")``) but also keeps the body
        text, since ``specify_cli.lanes.compute.compute_lanes`` uses WP
        bodies for surface inference. Unreadable files are skipped outright
        (unlike the conflict-detection reader, a WP whose frontmatter cannot
        be parsed contributes nothing meaningful to lane computation).
        """
        from specify_cli.cli.commands.agent.tasks_finalize_validation import _is_wp_id, _wp_id_from_file
        from specify_cli.status import read_wp_frontmatter

        frontmatters: dict[str, WPMetadata] = {}
        bodies: dict[str, str] = {}
        for wp_file in tasks_dir.glob("WP*.md"):
            wp_id = _wp_id_from_file(wp_file)
            if not _is_wp_id(wp_id):
                continue
            try:
                meta, body = read_wp_frontmatter(wp_file)
            except Exception as exc:  # noqa: BLE001 — degrade, don't block finalize
                logger.debug(
                    "Skipping unreadable WP frontmatter for lane computation: %s (%s)",
                    wp_file,
                    exc,
                )
                continue
            frontmatters[wp_id] = meta
            bodies[wp_id] = body
        return frontmatters, bodies

    def _finalize_lanes() -> None:
        """Co-locate the ``lanes.json`` write with the event-log bootstrap (#4758).

        The historical bug: this legacy command bootstrapped canonical
        status (seeding ``genesis -> planned`` events) but never wrote
        ``lanes.json``, so ``move-task`` could walk a WP straight out of
        ``planned`` with no lanes to resolve a worktree from. This phase
        runs BEFORE the bootstrap call below so it never seeds events
        without lanes (FR-001, SC-001).

        Three outcomes:

        1. ``lanes.json`` already exists -- #3311's guard: never rewrite
           existing lanes. No-op.
        2. ``lanes.json`` absent AND the shared wedge predicate
           (``specify_cli.lanes.persistence.is_execution_wedged``) holds
           (execution has begun with no lanes on disk) -- the mission is
           already wedged by some earlier run; refuse rather than guess a
           ``planning_commit_sha``, naming the ``doctor mission-state --fix``
           repair path (mirrors ``mission_finalize``'s re-finalize refusal).
        3. ``lanes.json`` absent AND execution has not begun (the ordinary,
           first-ever finalize of this mission) -- compute and write it for
           real via the WP01 pure core, capturing the current
           ``target_branch`` tip as ``planning_commit_sha`` (the same
           "captured" action ``_preserve_or_capture_planning_commit_sha``
           uses pre-execution). When no WP declares ownership
           (``owned_files``/``execution_mode``), there is nothing
           meaningful to compute -- this legacy command predates
           ``lanes.json`` and is also used purely for dependency injection
           on ownerless WPs, so that degenerate case is a silent no-op
           rather than a hard failure.
        """
        from specify_cli.cli.commands.agent.mission_finalize import (
            _capture_target_branch_tip,
            _execution_has_begun,
        )
        from specify_cli.lanes.compute_and_persist import (
            LaneGlobValidationError,
            compute_and_write_lanes,
        )
        from specify_cli.lanes.persistence import is_execution_wedged, read_lanes_json
        from specify_cli.mission_metadata import load_meta_or_empty
        from specify_cli.ownership.frontmatter_source import (
            InMemoryFrontmatterSource,
            resolve_wp_manifests,
        )

        if read_lanes_json(st.primary_feature_dir) is not None:
            return  # #3311 guard: never rewrite existing lanes.

        execution_has_begun = _execution_has_begun(st.main_repo_root, st.mission_slug)
        if is_execution_wedged(execution_has_begun=execution_has_begun, lanes_present=False):
            error_msg = (
                f"Cannot finalize mission {st.mission_slug!r}: execution has "
                "begun (a WP is past 'planned') but no lanes.json exists on "
                "disk. Refusing to seed further canonical events without "
                "lanes.json. Run 'spec-kitty doctor mission-state --fix "
                f"--mission {st.mission_slug}' to rebuild lanes.json from "
                "the event log."
            )
            _tasks._output_error(st.json_output, error_msg)
            raise typer.Exit(1)

        wp_frontmatters, wp_bodies = _gather_wp_frontmatter_and_bodies(st.tasks_dir)
        wp_manifests = resolve_wp_manifests(InMemoryFrontmatterSource(wp_frontmatters))
        if not wp_manifests:
            return  # No WP declares ownership — nothing meaningful to lane-compute.

        # Canonical reader (#4758 rebase fix): route through
        # ``mission_metadata.load_meta_or_empty`` instead of an inline
        # ``json.loads``/``read_text`` decode (test_inline_meta_read_gate.py).
        # ``load_meta_or_empty`` already absorbs a missing OR malformed
        # meta.json to ``{}`` -- the same silent-degrade contract the old
        # ``contextlib.suppress(Exception)`` block implemented by hand.
        raw_meta = load_meta_or_empty(st.primary_feature_dir)
        raw_mission_id = raw_meta.get("mission_id")
        mission_id: str | None = raw_mission_id if isinstance(raw_mission_id, str) else None

        planning_commit_sha = _capture_target_branch_tip(st.main_repo_root, st.target_branch)
        try:
            compute_and_write_lanes(
                st.primary_feature_dir,
                st.main_repo_root,
                st.mission_slug,
                wp_manifests,
                st.dependencies_map,
                wp_frontmatters,
                wp_bodies,
                st.target_branch,
                planning_commit_sha=planning_commit_sha,
                mission_id=mission_id,
            )
        except LaneGlobValidationError as exc:
            # Single-source the abort message through the exception the pure core
            # raises rather than re-hardcoding the identical literal (SSOT — squad MINOR).
            error_msg = str(exc)
            _tasks._output_error(
                st.json_output,
                error_msg,
                {"error": error_msg, "ownership_literal_path_errors": exc.result.errors},
            )
            raise typer.Exit(1) from None

    # #4890: the plan was already computed (and its effective graph validated)
    # in phase B (``_ft_validate``) — reuse it rather than recomputing it here.
    assert st.update_plan is not None, "_ft_validate must set st.update_plan before _ft_apply_writes runs"
    update_plan = st.update_plan
    for warning in update_plan.warnings:
        _tasks.console.print(f"[yellow]Warning:[/yellow] {warning}")

    would_modify: list[dict[str, object]] = []
    for write in update_plan.writes:
        if not st.validate_only:
            _write_fm(write.wp_file, write.updated_meta.model_dump(exclude_none=True), write.body)
        else:
            would_modify.append({"wp_id": write.wp_id, "changes": {"dependencies": write.dependencies}})
    st.would_modify = would_modify

    # Bootstrap canonical status state for all WPs — STATUS-partition: reads the
    # event log and meta.json via the topology-aware resolver (C-001, coord-husk).
    # read-surface-ssot-closeout WP08 / FR-001 / NFR-001: routed through the
    # kind-aware placement seam directly (no longer proxied through
    # ``_tasks.resolve_feature_dir_for_mission`` — the kind-blind resolver's
    # module re-export was retired in the same WP; ``STATUS_STATE`` resolves
    # the SAME coord-aware dir the kind-blind resolver produced for this read).
    st.feature_dir = placement_seam(st.main_repo_root, st.mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    # #4758 (WP01): co-locate the lanes.json write with the event-log
    # bootstrap below so this command never seeds genesis->planned events
    # with no lanes.json for move-task to wedge against (FR-001, SC-001).
    # --validate-only never mutates (NFR-002) — bootstrap itself already
    # runs with dry_run=True in that mode, so lanes.json is left untouched.
    if not st.validate_only:
        _finalize_lanes()
    st.bootstrap_result = _tasks.bootstrap_canonical_state(st.feature_dir, st.mission_slug, dry_run=st.validate_only)


def _ft_output(st: _FinalizeState) -> None:
    """Phase D: build the validate-only / success envelope and emit it."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    assert st.update_plan is not None and st.bootstrap_result is not None
    update_plan = st.update_plan
    bootstrap_result = st.bootstrap_result
    bootstrap_payload = {
        "total_wps": bootstrap_result.total_wps,
        "already_initialized": bootstrap_result.already_initialized,
        "newly_seeded": bootstrap_result.newly_seeded,
        "skipped": bootstrap_result.skipped,
        "wp_details": bootstrap_result.wp_details,
    }
    # #4890 (T022): the ``dependencies`` payload must equal the EFFECTIVE
    # persisted graph (parsed deps merged with any preserved frontmatter
    # deps) — not the raw tasks.md-parsed map, which silently omits any
    # preserved (frontmatter-only) dependency and falsifies what was
    # actually written to disk.
    if st.validate_only:
        result: dict[str, object] = {
            "result": "validation_passed",
            "validate_only": True,
            "would_modify": st.would_modify,
            "would_preserve": update_plan.preserved_wps,
            "unchanged": update_plan.unchanged_wps,
            "updated_wp_count": update_plan.updated_count,
            "dependencies": update_plan.effective_dependencies,
            **_tasks._mission_identity_payload(st.feature_dir),
            "bootstrap": bootstrap_payload,
        }
    else:
        result = {
            "result": "success",
            "updated_wp_count": update_plan.updated_count,
            "modified_wps": update_plan.modified_wps,
            "unchanged_wps": update_plan.unchanged_wps,
            "preserved_wps": update_plan.preserved_wps,
            "dependencies": update_plan.effective_dependencies,
            **_tasks._mission_identity_payload(st.feature_dir),
            "bootstrap": bootstrap_payload,
        }

    _tasks._output_result(
        st.json_output,
        result,
        f"[green]✓[/green] Updated {update_plan.updated_count} WP files with dependencies"
        f" (bootstrap: {bootstrap_result.newly_seeded} seeded,"
        f" {bootstrap_result.already_initialized} existing)",
    )


def _do_finalize_tasks(
    mission: str | None,
    json_output: bool,
    validate_only: bool,
    *,
    ports: TasksPorts | None = None,
) -> None:
    """Orchestrate ``finalize-tasks`` over the WP02 ``FsReader`` port, CORELESS.

    ``finalize_tasks`` carries NO decision core (FR-007): it parses/validates deps
    through the existing ``tasks_finalize_validation`` seam and applies the computed
    writes. It does NOT route through any transition core (deferred #2300; guarded by
    the T036 non-import gate). ``ports=None`` builds the production bundle. The phase
    helpers run in the SAME order as the original single body: resolve → validate →
    apply → output.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks

    ports = ports or _default_finalize_ports()
    st = _FinalizeState(mission=mission, json_output=json_output, validate_only=validate_only)
    try:
        _ft_resolve_context(st, ports)
        # WP06 (coord-commit-integrity-01KY5JS8, FR-008, DIRECTIVE_024 declared
        # out-of-map one-liner): this module is outside WP06's owned_files, but
        # FR-008 requires a non-blocking coord-vs-target staleness WARN woven
        # into finalize-tasks. `_coordination_doctor` (Cluster K) owns the
        # detector; `check_and_warn_coord_staleness` never raises on its own,
        # and `contextlib.suppress` is belt-and-braces so this can NEVER block
        # finalize-tasks. Gated on human mode: the advisory WARN prints via
        # `console.print` to stdout, which would corrupt the machine-readable
        # `--json` payload (that leg is consumed by `json.loads`), so it is
        # emitted only when NOT in `--json` mode.
        if not st.json_output:
            with contextlib.suppress(Exception):
                check_and_warn_coord_staleness(st.primary_feature_dir, st.main_repo_root)
        _ft_validate(st)
        _ft_apply_writes(st)
        _ft_output(st)
    except typer.Exit:
        raise
    except Exception as e:
        # Emit ErrorLogged event (T016).
        with contextlib.suppress(Exception):
            _tasks.emit_error_logged(
                error_type="runtime",
                error_message=str(e),
                stack_trace=traceback.format_exc(),
            )
        _tasks._output_error(json_output, str(e))
        raise typer.Exit(1) from None
