"""The ``mark-status`` command family, relocated out of ``tasks.py`` (WP08, #2058).

Mission ``tasks-py-degod-wave2-01KWH9EQ`` FR-001/FR-002: ``_do_mark_status`` +
the 9 ``_ms_*`` phase helpers + ``_MarkStatusState`` +
``_default_mark_status_ports`` live here, moved VERBATIM from ``tasks.py``.
The ``@app.command`` Typer wrapper (``mark_status``) stays in ``tasks.py`` and
delegates to :func:`_do_mark_status` (the byte-frozen ``--help`` surface is the
registration shim's).

**Orchestration shape**: the phase helpers run validate → resolve → identify →
emit canonical subtask state → history → dossier → output. Since #2816,
``tasks.md`` is a read-only task-roster/index surface for this command; no
checkbox or pipe-table status cell is written or committed. ``mark_status`` is
CORELESS (FR-007): it carries NO transition
decision core and does NOT route through ``move_task``'s ``decide_transition``
(the deferred #2300 unification, guarded structurally by the coreless
non-import gate).

**Commit contract (frozen no-commit — #2816 / #2300 WP03)**: ``mark_status`` is
event-log-only. Since #2816 canonical completion is appended through the status
event writer (``_ms_emit_subtask_state``); ``_do_mark_status`` never routes
through ``commit_for_mission`` and NEVER commits a task artifact — so it has
neither a ``_skip_target_branch_commit`` pre-gate (that skip-exit-0 pre-gate is
``move_task``-only) NOR the ``_protected_branch_status_commit_error`` refuse gate
(``_ms_resolve_context`` explicitly retires it: "the former protected-primary
artifact commit refusal does not apply"). ``--auto-commit`` is a compatibility
input with no commit behind it. The dead ``_ms_commit`` helper below is a
compat-shim/test-only symbol — it is defined for the frozen ``tasks.<name>``
re-export surface but is NOT reachable from ``_do_mark_status`` (reviving a
commit path here is a #2816 regression, structurally guarded by
``test_surface_authority_goldens.test_row3_mark_status_is_event_log_only_no_commit``
and ``test_tasks_surface_authority`` WP03). ``mark_status`` also owns the
no-IDs error byte case (research.md D3, routed through Render by WP04) — the
``_ms_report_none_resolved`` emission moved verbatim.

**Seam bridge** (research.md D1/D7): the relocated bodies reach every patched
seam symbol through a lazy in-function import of the ``tasks`` module
(``from specify_cli.cli.commands.agent import tasks as _tasks``) and call
``_tasks.<attr>(...)``, so every historical ``@patch("...agent.tasks.<sym>")``
/ ``monkeypatch.setattr(tasks, ...)`` keeps INTERCEPTING after the move —
including the heavy ``feature_status_lock`` (D7 ×21) and ``emit_history_added``
(×10) seams, the conftest ``console`` rebinding, ``_resolve_inline_subtasks``
(which stays ``tasks.py``-resident per the T007 partition record) and the port
adapters constructed by ``_default_mark_status_ports`` (the coord router built
by ``tasks.seam_coord_router()``, whose ``commit_artifact`` body routes
``commit_for_mission`` back through ``_tasks.<attr>``, WP03 / degod-follow-ups
constructor-DI collapse). ``tasks.py`` re-imports the family in the explicit ``as`` re-export
form, so ``tasks.<name>`` stays a module attribute. Symbols with ZERO patch
sites and a canonical home outside ``tasks.py`` are imported directly at
module scope (cycle-safe: none of those modules import ``tasks``).

Per-symbol routing/interception evidence:
``kitty-specs/tasks-py-degod-wave2-01KWH9EQ/seam-checklist.md`` (Layer 4 of
the parity contract).
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import typer

from mission_runtime import ActionContextError, MissionArtifactKind
from specify_cli.agent_tasks_ports import MissionHandle, TasksPorts
from specify_cli.cli.commands.agent.tasks_materialization import (
    _resolve_checkbox,
    _resolve_pipe_table,
)
from specify_cli.cli.commands.agent.tasks_outline import (
    TASKS_MD_FILENAME,
    TaskIdResolutionFormat,
    TaskIdResolutionOutcome,
    TaskIdResult,
    _INLINE_SUBTASKS_RE,
    _normalize_task_id_input,
    _resolve_history_wp_id,
    _resolve_wp_id,
)
from specify_cli.core.subtask_rows import (
    SubtaskRosterResolutionError,
    authored_subtask_roster,
)
from specify_cli.core.owned_mission import (
    OwnedMission,
    require_unstaged_index,
    resolve_owned_mission,
)
from specify_cli.upgrade.pre30_guard import Pre30LayoutError, check_pre30_layout

#: WP prompt directories carry a README that is not a work package.
_README_FILENAME = "readme.md"


@dataclass
class _MarkStatusState:
    """Mutable orchestration state threaded through ``mark_status``'s phases.

    The single-body command tracked ~15 loose locals across validate → resolve →
    apply → history → output; the phase helpers exchange this one value object
    instead. Not frozen: each phase fills its own slice in the SAME order the
    original body did, so the ``tasks.md`` write still precedes the auto-commit.
    """

    # --- raw command inputs ---
    task_ids: list[str]
    status: str
    mission: str | None
    auto_commit: bool | None
    json_output: bool
    owned_checkout: Path | None = None
    # --- phase A/B: resolved context ---
    repo_root: Path = field(default_factory=Path)
    main_repo_root: Path = field(default_factory=Path)
    target_branch: str = ""
    mission_slug: str = ""
    resolved_auto_commit: bool = False
    feature_dir: Path = field(default_factory=Path)
    status_dir: Path = field(default_factory=Path)
    tasks_md: Path = field(default_factory=Path)
    owned: OwnedMission | None = None
    applied_event_ids: list[str] = field(default_factory=list)
    applied_wps: list[str] = field(default_factory=list)
    # --- phase C: apply results ---
    results: list[TaskIdResult] = field(default_factory=list)
    updated_tasks: list[str] = field(default_factory=list)
    not_found_tasks: list[str] = field(default_factory=list)
    resolved_tasks: list[str] = field(default_factory=list)
    artifact_mutated: bool = False


def _default_mark_status_ports() -> TasksPorts:
    """Production port bundle for ``mark_status`` (coord router bound to tasks.py)."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    return TasksPorts(
        fs=_tasks.RealFsReader(),
        # mark_status routes only the commit seam through ``tasks`` and commits
        # target-branch-less (byte-parity with the pre-rewire inline call); it
        # inherited the base ``commit_status`` emitter binding.
        coord=_tasks.seam_coord_router(),
        git=_tasks.RealGitOps(),
        render=_tasks.RealRender(),
    )


def _ms_validate_inputs(st: _MarkStatusState) -> None:
    """Phase A: validate ``--status`` + non-empty task IDs, then normalize IDs."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    if st.status not in ("done", "pending"):
        _tasks._output_error(st.json_output, f"Invalid status '{st.status}'. Must be 'done' or 'pending'.")
        raise typer.Exit(1)
    if not st.task_ids:
        _tasks._output_error(st.json_output, "At least one task ID is required")
        raise typer.Exit(1)
    # WP04/T022 (FR-017): accept both bare and mission-qualified task IDs
    # (``T001`` or ``<mission_slug>/T001`` / ``<mission_slug>:T001``). Normalize to
    # bare task IDs before validation. A garbage ID surfaces as "no task IDs found
    # in tasks.md" downstream — preserving the structured-error contract.
    st.task_ids = [_normalize_task_id_input(tid) for tid in st.task_ids]


def _ms_resolve_context(st: _MarkStatusState) -> None:
    """Phase B(i): resolve the repository, mission, and stored topology.

    ``--auto-commit`` is retained as a compatibility input, but ``mark-status``
    no longer mutates or commits ``tasks.md``. Canonical completion is appended
    through the status event writer, so the former protected-primary artifact
    commit refusal does not apply.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    repo_root = _tasks.locate_project_root()
    if repo_root is None:
        _tasks._output_error(st.json_output, "Could not locate project root")
        raise typer.Exit(1)
    if st.owned_checkout is not None:
        primary = _tasks.get_main_repo_root(repo_root)
        st.owned = resolve_owned_mission(primary, st.owned_checkout, st.mission)
        require_unstaged_index(st.owned)
        # #3980: the ``OWNED_SYNC_UNSUPPORTED`` refusal died with the launch
        # flip — owned checkouts publish moments like any checkout. The
        # fan-out handlers on the status emit seam are individually bounded
        # and non-raising, and the Zeitgeist moment handler no-ops without a
        # session/team, so an owned mark-status under active sync completes
        # with at worst a skipped fan-out warning.
        st.repo_root = st.owned.root
        _tasks._emit_sparse_session_warning(
            st.repo_root, command="spec-kitty agent tasks mark-status"
        )
        st.resolved_auto_commit = (
            _tasks.get_auto_commit_default(st.repo_root)
            if st.auto_commit is None
            else st.auto_commit
        )
        if not st.resolved_auto_commit:
            raise ActionContextError(
                "OWNED_OPTION_UNSUPPORTED",
                "Owned mark-status requires auto-commit.",
            )
        st.main_repo_root = st.owned.primary
        st.target_branch = st.owned.target
        st.mission_slug = st.owned.slug
        return

    st.repo_root = repo_root
    # FR-010 / FR-019: one-shot sparse-checkout session warning.
    _tasks._emit_sparse_session_warning(repo_root, command="spec-kitty agent tasks mark-status")
    st.resolved_auto_commit = (
        _tasks.get_auto_commit_default(repo_root) if st.auto_commit is None else st.auto_commit
    )
    st.mission_slug = _tasks._find_mission_slug(
        explicit_mission=st.mission, json_output=st.json_output, repo_root=repo_root
    )
    st.main_repo_root, st.target_branch = _tasks._ensure_target_branch_checked_out(
        repo_root, st.mission_slug, st.json_output
    )


def _ms_resolve_read_dir(st: _MarkStatusState, ports: TasksPorts) -> None:
    """Phase B(ii): resolve the TASKS_INDEX write surface (#2154) + pre30 guard.

    #2154 (FR-001 / T008): ``tasks.md`` is a TASKS_INDEX (primary-partition)
    artifact — resolve the WRITE leg through the SAME kind-aware authority the
    validation read and the commit leg use (now the ``FsReader`` port), so the
    subtask write lands on the PRIMARY surface a coord-topology mission reads back
    from. The kind-blind ``resolve_feature_dir_for_mission`` returns the ``-coord``
    husk under coord topology, so the write and the validation read would diverge.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    handle = MissionHandle(
        repo_root=st.main_repo_root,
        mission_slug=st.mission_slug,
        effective_root=st.owned.root if st.owned is not None else None,
    )
    st.feature_dir = ports.fs.planning_read_dir(handle, kind=MissionArtifactKind.TASKS_INDEX)
    # #3027: this TASKS_INDEX-resolved dir is also handed to
    # owning_wp_from_authored_roster, which reads WORK_PACKAGE_TASK-kinded
    # ``tasks/*.md`` files — see the pinning comment on that function.
    if st.owned is not None:
        st.status_dir = ports.coord.feature_write_dir(handle)
    else:
        from specify_cli.coordination import resolve_status_surface

        st.status_dir = resolve_status_surface(st.main_repo_root, st.mission_slug).parent
    # Boundary guard — hard-reject pre-3.0 layout before any WP mutation
    try:
        check_pre30_layout(st.feature_dir)
    except Pre30LayoutError as e:
        _tasks._output_error(st.json_output, str(e))
        raise typer.Exit(1) from None
    st.tasks_md = st.feature_dir / TASKS_MD_FILENAME


def _ms_report_none_resolved(st: _MarkStatusState) -> None:
    """Emit the contracted 'no task IDs resolved' error and exit 1."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    if st.json_output:
        render = _tasks.RealRender()
        print(render.json_envelope(_tasks._mark_status_json_payload(st.results)))
    elif any(result.format == TaskIdResolutionFormat.WP_ID for result in st.results):
        detail = "; ".join(result.message for result in st.results if result.message)
        _tasks._output_error(st.json_output, detail)
    else:
        _tasks._output_error(st.json_output, f"No task IDs found in tasks.md: {', '.join(st.not_found_tasks)}")
    raise typer.Exit(1)


def _ms_commit(st: _MarkStatusState, ports: TasksPorts) -> None:
    """DEAD compat-shim (event-log-only since #2816) — NOT reachable from ``_do_mark_status``.

    Retained only for the frozen ``tasks.<name>`` compat re-export surface and the
    unit tests that exercise it directly; the live ``mark-status`` flow
    (``_ms_apply_updates`` → ``_ms_emit_subtask_state``) writes completion to the
    event log and commits nothing. Do NOT re-wire ``_do_mark_status`` through this
    (that would undo the #2816 event-sourcing cutover — a #2300 WP03 regression).

    ``tasks.md`` is TASKS_INDEX (primary): route the commit through the coord WRITE
    ``commit_artifact`` capability (over the canonical ``commit_for_mission`` entry
    point). The router owns placement resolution AND the protected-primary refusal.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    # Extract spec number from mission_slug (e.g., "014" from "014-feature-name").
    spec_number = st.mission_slug.split("-")[0] if "-" in st.mission_slug else st.mission_slug
    if len(st.updated_tasks) == 1:
        commit_msg = f"chore: Mark {st.updated_tasks[0]} as {st.status} on spec {spec_number}"
    else:
        commit_msg = f"chore: Mark {len(st.updated_tasks)} subtasks as {st.status} on spec {spec_number}"
    try:
        actual_tasks_path = st.tasks_md.resolve()
        router_result = ports.coord.commit_artifact(
            MissionHandle(repo_root=st.main_repo_root, mission_slug=st.mission_slug),
            (actual_tasks_path,),
            commit_msg,
            kind=MissionArtifactKind.TASKS_INDEX,
            policy=_tasks.ProtectionPolicy.resolve(st.main_repo_root),
        )
        if router_result.status == "committed":
            if not st.json_output:
                _tasks.console.print(f"[cyan]→ Committed subtask changes to {st.target_branch} branch[/cyan]")
        elif not st.json_output:
            _tasks.console.print("[yellow]Warning:[/yellow] Failed to auto-commit subtask changes")
    except Exception as e:
        if not st.json_output:
            _tasks.console.print(f"[yellow]Warning:[/yellow] Auto-commit exception: {e}")


def _ms_apply_updates(st: _MarkStatusState, ports: TasksPorts) -> None:
    """Phase C: resolve task IDs without mutating the authored tasks index.

    Holds the feature status lock across the read → resolve → write → commit span,
    exactly as the pre-rewire single body did.

    WP04/T015 (FR-003/FR-008/C-001): the canonical subtask-completion surface
    (``CHECKBOX`` / ``INLINE_SUBTASKS``) is re-sourced from an
    ``InnerStateChanged`` emit (``_ms_emit_subtask_state``, called by
    ``_do_mark_status`` after this phase) — the reduced snapshot is the sole
    completion authority. Both legacy mutating resolvers therefore run against
    throwaway copies. Checkbox bytes and pipe-table status cells are authored
    reference material only; neither is persisted by ``mark-status``.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    del ports  # Stable phase signature; event-only apply has no commit port.
    lock = (
        contextlib.nullcontext()
        if st.owned is not None
        else _tasks.feature_status_lock(st.main_repo_root, st.mission_slug)
    )
    with lock:
        if not st.tasks_md.exists():
            _tasks._output_error(st.json_output, f"tasks.md not found: {st.tasks_md}")
            raise typer.Exit(1)

        content = st.tasks_md.read_text(encoding="utf-8")
        lines = content.split("\n")
        results: list[TaskIdResult] = []
        # Update all requested tasks in a single pass.
        for task_id in st.task_ids:
            before_content = "\n".join(lines)
            # Both legacy resolvers mutate their input as part of recognition.
            # Probe throwaway copies so only the event emit records completion.
            checkbox_lines = list(lines)
            pipe_table_lines = list(lines)
            result = (
                _resolve_checkbox(task_id, checkbox_lines, st.status)
                or _resolve_pipe_table(task_id, pipe_table_lines, st.status)
                or _tasks._resolve_inline_subtasks(task_id, before_content, st.status, st.feature_dir)
                or _resolve_wp_id(task_id, st.status, st.mission_slug, st.feature_dir)
                or _resolve_authored_roster(task_id, st.feature_dir)
                or TaskIdResult(
                    id=task_id,
                    outcome=TaskIdResolutionOutcome.NOT_FOUND,
                    format=None,
                    message=f"{task_id} was not found in any supported task format.",
                )
            )
            results.append(result)

        st.results = results
        st.updated_tasks = [r.id for r in results if r.outcome == TaskIdResolutionOutcome.UPDATED]
        st.not_found_tasks = [r.id for r in results if r.outcome == TaskIdResolutionOutcome.NOT_FOUND]
        st.resolved_tasks = [r.id for r in results if r.outcome != TaskIdResolutionOutcome.NOT_FOUND]
        st.artifact_mutated = False

        # Fail if no tasks were resolved.
        if not st.resolved_tasks:
            _ms_report_none_resolved(st)

        # The event append is the canonical mutation after #2816, so it belongs
        # inside the same feature lock as task-id resolution. Releasing the
        # lock between read/resolve and append would reintroduce a TOCTOU race.
        _ms_emit_subtask_state(st)

def _ms_emit_subtask_state(st: _MarkStatusState) -> None:
    """Emit the ``InnerStateChanged`` subtask-completion delta (T015, FR-003).

    This is the durable completion record the review gate re-sources from
    (``tasks_shared._check_unchecked_subtasks``, T016) — it replaces the
    ``tasks.md`` checkbox byte as the canonical subtask-completion authority.
    Grouped by owning WP so a batch mark of several task ids
    emits ONE delta per WP, never one event per task id (FR-003 "single or
    batch"). A resolved task id with no identifiable owning WP is a hard error:
    success without a canonical event would violate the sole-authority contract.
    The emit target is ``st.status_dir``, resolved from stored topology during
    ``_ms_resolve_read_dir`` — never the primary planning directory or
    ``Path.cwd()`` (C-003/#2647).
    """
    from specify_cli.status import Lane, Status, WPInnerStateDelta, emit_inner_state_changed

    if not st.updated_tasks:
        return

    target_status: Status = Lane.DONE if st.status == "done" else Lane.PLANNED
    tasks_content = st.tasks_md.read_text(encoding="utf-8")
    resolved_tasks_by_wp: dict[str, list[str]] = {}
    unresolved_tasks: list[str] = []
    for task_id in st.updated_tasks:
        history_wp_id = _resolve_history_wp_id(
            tasks_content, task_id
        ) or owning_wp_from_authored_roster(st.feature_dir, task_id)
        if history_wp_id is None:
            unresolved_tasks.append(task_id)
        else:
            resolved_tasks_by_wp.setdefault(history_wp_id, []).append(task_id)
    if unresolved_tasks:
        joined = ", ".join(unresolved_tasks)
        raise ValueError(f"Could not resolve owning work package for subtask event: {joined}")

    for wp_id, task_ids_for_wp in resolved_tasks_by_wp.items():
        delta = WPInnerStateDelta(subtasks=dict.fromkeys(task_ids_for_wp, target_status))
        if st.owned is not None:
            from specify_cli.coordination import status_transition

            event = status_transition.emit_inner_state_changed_transactional(
                st.status_dir,
                wp_id,
                delta,
                actor="user",
                mission_slug=st.mission_slug,
                repo_root=st.main_repo_root,
                operation=f"mark-status {wp_id}",
                effective_root=st.owned.root,
                # #3866: thread the validated value object so the per-WP
                # annotation identity does not re-run resolve_owned_mission.
                owned_mission=st.owned,
            )
            st.applied_event_ids.append(event.event_id)
            st.applied_wps.append(wp_id)
        else:
            emit_inner_state_changed(
                st.status_dir,
                wp_id,
                delta,
                actor="user",
                mission_slug=st.mission_slug,
                repo_root=st.main_repo_root,
            )


def _ms_output(st: _MarkStatusState) -> None:
    """Emit the mark-status success envelope + not-found warnings."""
    from specify_cli.cli.commands.agent import tasks as _tasks
    result = _tasks._mark_status_json_payload(st.results)
    if st.owned is not None:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=st.owned.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        result.update(
            {
                "owned_checkout": str(st.owned.root),
                "destination_ref": st.owned.target,
                "commit_sha": head.stdout.strip() if head.returncode == 0 else None,
                "status_events_path": str(st.status_dir / "status.events.jsonl"),
                "status_snapshot_path": str(st.status_dir / "status.json"),
                "event_ids": list(st.applied_event_ids),
                "applied_wps": list(st.applied_wps),
                "state_applied": bool(st.applied_event_ids),
            }
        )
    if st.not_found_tasks and not st.json_output:
        _tasks.console.print(f"[yellow]Warning:[/yellow] Not found: {', '.join(st.not_found_tasks)}")
    if len(st.updated_tasks) == 1:
        success_msg = f"[green]✓[/green] Marked {st.updated_tasks[0]} as {st.status}"
    elif not st.updated_tasks:
        success_msg = f"[green]✓[/green] Requested status already satisfied for: {', '.join(st.resolved_tasks)}"
    else:
        success_msg = f"[green]✓[/green] Marked {len(st.updated_tasks)} subtasks as {st.status}: {', '.join(st.updated_tasks)}"
    _tasks._output_result(st.json_output, result, success_msg)


def _recovery_commit_sha(error: BaseException) -> str | None:
    """Return the first ``commit_sha`` riding *error*'s cause/context chain.

    A transactional owned-mode emit may commit a recovery commit before the
    failure surfaces, stamping the commit sha on the exception it raises —
    possibly one or more ``raise … from`` hops down the chain. The walk is
    cycle-safe (an exception graph that loops back on itself terminates) and
    ignores non-string/empty ``commit_sha`` attributes.
    """
    cause: BaseException | None = error
    visited_causes: set[int] = set()
    while cause is not None and id(cause) not in visited_causes:
        visited_causes.add(id(cause))
        candidate_sha = getattr(cause, "commit_sha", None)
        if isinstance(candidate_sha, str) and candidate_sha:
            return candidate_sha
        cause = cause.__cause__ or cause.__context__
    return None


def _reconstruct_applied_events(
    owned: OwnedMission,
    error: BaseException,
    events_path: Path | None,
) -> list[dict[str, object]]:
    """Reconstruct which status events a failed owned mark-status applied (#3865).

    Diffs the ``status.events.jsonl`` blob recorded in the recovery commit named
    by *error*'s cause chain against the same blob in that commit's parent, so
    the error payload reports exactly the events this command landed — never a
    concurrent writer's. Returns ``[]`` when no recovery commit sha rides the
    chain or *events_path* is unknown; a malformed or key-incomplete log row
    suppresses detection wholesale rather than crashing the error path.
    """
    recovery_commit_sha = _recovery_commit_sha(error)
    if recovery_commit_sha is None or events_path is None:
        return []
    relative_events = events_path.relative_to(owned.root).as_posix()
    committed_log = subprocess.run(
        ["git", "show", f"{recovery_commit_sha}:{relative_events}"],
        cwd=owned.root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    parent_log = subprocess.run(
        ["git", "show", f"{recovery_commit_sha}^:{relative_events}"],
        cwd=owned.root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    with contextlib.suppress(ValueError, KeyError):
        parent_ids = {
            str(row["event_id"])
            for line in parent_log.stdout.splitlines()
            if parent_log.returncode == 0 and line.strip()
            for row in (json.loads(line),)
        }
        return [
            row
            for line in committed_log.stdout.splitlines()
            if committed_log.returncode == 0 and line.strip()
            for row in (json.loads(line),)
            if str(row["event_id"]) not in parent_ids
        ]
    return []


def _do_mark_status(
    task_ids: list[str],
    status: str,
    mission: str | None,
    auto_commit: bool | None,
    json_output: bool,
    owned_checkout: Path | None = None,
    *,
    ports: TasksPorts | None = None,
) -> None:
    """Orchestrate ``mark-status`` over the WP02 ports (C-005 seam), CORELESS.

    ``mark_status`` carries NO transition decision core (FR-007): it resolves task
    IDs against ``tasks.md`` and writes completion only to the event log. It does NOT route through
    ``move_task``'s ``decide_transition`` core — that is the deferred #2300
    unification, guarded structurally by the T036 non-import gate. ``ports=None``
    builds the production bundle (coord router bound to this module's patchable
    ``commit_for_mission``). The phase helpers run in the SAME order as the original
    single body: validate → resolve → apply → history → dossier → output.
    """
    from specify_cli.cli.commands.agent import tasks as _tasks
    st = _MarkStatusState(
        task_ids=list(task_ids),
        status=status,
        mission=mission,
        auto_commit=auto_commit,
        json_output=json_output,
        owned_checkout=owned_checkout,
    )
    try:
        _ms_validate_inputs(st)
        _ms_resolve_context(st)
        ports = ports or _default_mark_status_ports()
        _ms_resolve_read_dir(st, ports)
        _ms_apply_updates(st, ports)
        _ms_output(st)
    except typer.Exit:
        raise
    except Exception as e:
        if st.owned_checkout is not None:
            events_path = (
                st.status_dir / "status.events.jsonl"
                if st.status_dir != Path()
                else st.owned.directory / "status.events.jsonl"
                if st.owned is not None
                else None
            )
            detected: list[dict[str, object]] = []
            if st.owned is not None and events_path is not None:
                detected = _reconstruct_applied_events(st.owned, e, events_path)
            event_ids = list(dict.fromkeys([
                *st.applied_event_ids,
                *(str(row["event_id"]) for row in detected),
            ]))
            applied_wps = list(dict.fromkeys([
                *st.applied_wps,
                *(str(row["wp_id"]) for row in detected if row.get("wp_id")),
            ]))
            dirty = None
            if st.owned is not None:
                git_status = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=st.owned.root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                dirty = (
                    bool(git_status.stdout.strip())
                    if git_status.returncode == 0
                    else None
                )
            error_code = getattr(e, "code", None) or getattr(e, "error_code", None) or "MARK_STATUS_FAILED"
            payload = {
                "result": "error",
                "error_code": error_code,
                "error": str(e),
                "state_applied": bool(event_ids),
                "event_ids": event_ids,
                "applied_wps": applied_wps,
                "destination_ref": st.owned.target if st.owned is not None else None,
                "status_events_path": str(events_path) if events_path is not None else None,
                "status_snapshot_path": (
                    str(st.status_dir / "status.json") if st.status_dir != Path() else None
                ),
                "dirty": dirty,
            }
            if st.json_output:
                print(json.dumps(payload))
            else:
                _tasks.console.print(f"[red]{error_code}: {e}[/red]")
            raise typer.Exit(1) from e
        _tasks._output_error(json_output, str(e))
        raise typer.Exit(1) from None


# ===========================================================================
# WP09 (tasks-py-degod-wave2-01KWH9EQ / FR-008, IC-07): the final
# registration-shim sweep relocates the mark_status-family straggler that
# remained ``tasks.py``-resident after WP08 — the inline-Subtasks resolver
# (``_resolve_inline_subtasks``). Moved VERBATIM (``_INLINE_SUBTASKS_RE`` /
# ``_persist_inline_subtask_status`` and the ``TaskIdResult`` vocabulary are
# module-scope imports here; none is a ``tasks``-namespace patch seam). The
# ``_ms_apply_updates`` call site above keeps routing through
# ``_tasks.<attr>``, so the seam-interception contract
# (``@patch("...agent.tasks._resolve_inline_subtasks")``,
# test_tasks_mark_status_seam.py) keeps INTERCEPTING; ``tasks.py`` re-imports
# the name in the explicit ``as`` re-export form (NFR-002).
# ===========================================================================



def _resolve_authored_roster(task_id: str, feature_dir: Path) -> TaskIdResult | None:
    """Resolve *task_id* against the authored ``subtasks:`` frontmatter rosters.

    The four legacy resolvers each require a particular ``tasks.md`` row shape —
    a checkbox, a pipe-table row, or an inline ``Subtasks: T001, T002`` list.
    Since #2816 IC-10 subtask completion is solely event-sourced and the shipped
    ``software-dev`` template instructs authors that subtasks are *reference
    rows, not checkboxes*, so a conforming ``tasks.md`` matches none of them and
    every id reports ``NOT_FOUND`` (#2962).

    This resolver reads the same source the lane-transition guard already treats
    as canonical static intent — :func:`authored_subtask_roster` — so the two
    surfaces agree on what a WP's subtasks are.

    It runs **last** in the chain: every legacy shape resolves exactly as before,
    and this only catches ids those shapes cannot see.

    An unresolvable roster yields ``None`` rather than propagating. The guard is
    right to treat a missing tasks directory as corruption and fail closed, but
    here the caller already has a ``NOT_FOUND`` path whose message is the useful
    one; raising would turn an ordinary miss into a crash.
    """
    wp_id = owning_wp_from_authored_roster(feature_dir, task_id)
    if wp_id is None:
        return None
    return TaskIdResult(
        id=task_id,
        outcome=TaskIdResolutionOutcome.UPDATED,
        format=TaskIdResolutionFormat.AUTHORED_ROSTER,
        message=f"{task_id} resolved from {wp_id}'s authored subtasks roster.",
    )


def owning_wp_from_authored_roster(feature_dir: Path, task_id: str) -> str | None:
    """Return the WP whose authored ``subtasks:`` roster contains *task_id*.

    One source for two surfaces. ``_resolve_authored_roster`` uses it to decide
    whether an id exists at all, and the event emit uses it to attribute the id
    to a work package — previously each re-derived ownership from ``tasks.md``
    row shapes, which is why fixing only the first left the emit failing with
    "Could not resolve owning work package" (#2962).

    An unreadable or ambiguous WP file is skipped rather than raised: the guard
    already reports roster corruption on its own path, and the callers here have
    a NOT_FOUND route whose message is the more useful one.

    Pinned assumption (#3027): ``feature_dir`` is resolved by the caller via
    ``planning_read_dir(handle, kind=MissionArtifactKind.TASKS_INDEX)``
    (``_ms_resolve_read_dir``), but the ``tasks/*.md`` files read here are
    ``WORK_PACKAGE_TASK``-kinded artifacts. This is a no-op today only because
    ``mission_runtime.artifacts._PRIMARY_ARTIFACT_KINDS`` places both kinds in
    the same partition, so they resolve to the same directory — the same
    co-membership :func:`authored_subtask_roster` (``core/subtask_rows.py``)
    and its other callers (``status/emit.py``, ``tasks_shared.py``,
    ``tasks_move_task.py``) all rely on implicitly via a shared ``feature_dir``.
    Declaring the kind explicitly here alone would not close the risk (the
    sibling callers would still assume it), so this is intentionally a pinning
    comment rather than a partial fix; see
    ``test_owning_wp_from_authored_roster_kind_co_membership_is_pinned`` in
    ``test_mark_status_authored_roster.py``, which fails loud if
    ``WORK_PACKAGE_TASK`` and ``TASKS_INDEX`` are ever placed in different
    partitions (e.g. a future re-home like ``ANALYSIS_REPORT``'s COORD→PRIMARY
    move, recorded in ``artifacts.py``).
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return None

    normalized = task_id.upper()
    for path in sorted(tasks_dir.glob("*.md")):
        if path.name.lower() == _README_FILENAME:
            continue
        wp_id = path.name.split("-", 1)[0].removesuffix(".md")
        try:
            roster = authored_subtask_roster(feature_dir, wp_id)
        except (SubtaskRosterResolutionError, OSError, ValueError):
            continue
        if normalized in {entry.upper() for entry in roster}:
            return wp_id
    return None


def _resolve_inline_subtasks(
    task_id: str,
    tasks_content: str,
    status: str,
    feature_dir: Path,
) -> TaskIdResult | None:
    """
    Search tasks_content for 'Subtasks: T001, T002' lines containing task_id.

    WP04/T015 (FR-003/FR-008): inline references are discovery hints used to
    map ``task_id`` to its owning WP context — completion is no longer
    persisted as a materialized ``tasks.md`` checkbox row. The durable record
    is the ``InnerStateChanged`` ``subtasks`` delta ``_ms_emit_subtask_state``
    emits from the ``UPDATED``/``INLINE_SUBTASKS`` result this resolver now
    returns unconditionally on a match. ``feature_dir`` is accepted for call-site
    compatibility but no longer used to persist a row.
    """
    del feature_dir
    normalized_task_id = task_id.upper()
    for match in _INLINE_SUBTASKS_RE.finditer(tasks_content):
        ids = [value.strip().upper() for value in match.group("ids").split(",")]
        if normalized_task_id in ids:
            return TaskIdResult(
                id=task_id,
                outcome=TaskIdResolutionOutcome.UPDATED,
                format=TaskIdResolutionFormat.INLINE_SUBTASKS,
                message=f"Recorded inline Subtasks reference {task_id} as {status} (event-sourced).",
            )
    return None
