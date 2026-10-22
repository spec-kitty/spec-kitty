"""WP06 (#2116) — ``move_task`` thin-orchestrator side-effect parity (T029).

The WP06 rewire routes ``move_task``'s execution through the WP02 coord WRITE
capabilities: each lane hop is emitted via ``commit_status`` and the primary
WP-file commit runs via ``commit_artifact``. This module injects the WP02 **Fake**
ports (``ports=`` on the extracted ``_do_move_task`` orchestrator — the C-005
injection seam that never touches the Typer surface) and asserts the executed
side-effects match the pre-rewire behaviour:

* a ``--no-auto-commit`` move records the transition on the ``commit_status`` seam
  ONLY — the primary ``commit_artifact`` seam stays untouched (coord-vs-primary
  disjointness);
* an auto-commit move records the transition on ``commit_status`` AND routes the
  ``WORK_PACKAGE_TASK`` primary commit (with the WP file in the bundle) through
  ``commit_artifact``, and writes the WP file to disk;
* the coord skip-exit-0 arm (``skip_primary``) suppresses the ``commit_artifact``
  call entirely and reports ``wp_file_update="skipped"`` while the transition is
  still emitted on the coord ``commit_status`` seam.

These are the Fake-port projections of the golden coord-topology cases (T004/T007);
they pin the routing without a real git worktree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind

from specify_cli.cli.commands.agent.tasks import _do_move_task, _MoveTaskArgs, seam_coord_router
from specify_cli.agent_tasks_ports import (
    CommitStatusResult,
    MissionHandle,
    TasksPorts,
)
from specify_cli.missions._read_path_resolver import (
    resolve_feature_dir_for_mission,
    resolve_planning_read_dir,
)
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeCoordCommitRouter,
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

pytestmark = pytest.mark.fast

_MISSION = "test-move-task-orchestration"


def _build_wp_file(tmp_path: Path, mission_slug: str, wp_id: str) -> tuple[Path, Path]:
    """Minimal WP + feature structure (mirrors the shared test_tasks helper)."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"execution_mode: code_change\n"
        f"agent: testbot\n"
        f"subtasks: [T001, T002, T003]\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir, wp_file


def _seed_wp_event(feature_dir: Path, wp_id: str, to_lane: str) -> None:
    """Seed a WP event so the canonical event log knows the WP exists."""
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-{to_lane}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(to_lane),
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _seed_claim_then_progress(feature_dir: Path, wp_id: str, *, claim_actor: str) -> None:
    """Seed ``planned -> claimed`` (carrying the claim-triple ``policy_metadata``
    sidecar) then ``claimed -> in_progress`` -- the SAME two-hop shape
    ``work_package_lifecycle.start_implementation_status`` emits for a real
    ``spec-kitty implement`` claim (FR-004 claim exception, reducer.py). Unlike
    :func:`_seed_wp_event` above (a single ``planned -> in_progress`` hop with
    no ``policy_metadata``), this is the only seed shape that actually
    populates the reduced snapshot's ``agent`` runtime slot -- required to
    reproduce FIX-M2-03's ``move-task`` ownership-guard bug at the
    orchestrator level (a WP seeded via ``_seed_wp_event`` alone always reads
    back ``current_agent=None``, which trivially bypasses the guard and would
    prove nothing).
    """
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-claimed",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor=claim_actor,
            force=True,
            execution_mode="worktree",
            policy_metadata={"agent": claim_actor},
        ),
    )
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{wp_id}-in-progress",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-01-01T00:00:01+00:00",
            actor=claim_actor,
            force=True,
            execution_mode="worktree",
        ),
    )


def _fake_ports(feature_dir: Path) -> tuple[TasksPorts, FakeCoordCommitRouter]:
    """A WP02 Fake bundle whose coord router resolves the REAL coord husk dir.

    ``feature_write_dir`` must return the on-disk feature dir the orchestrator's
    reads (``_read_transactional_wp_lane`` / pre30 guard) depend on; the two write
    capabilities record calls on their separate logs. ``commit_status`` returns a
    ``skipped=False`` result (event=None) so the emit loop threads through without
    a real event write — the CALL is the observable, not a persisted event.
    """
    coord = FakeCoordCommitRouter(
        write_dir=feature_dir,
        status_result=CommitStatusResult(event=None, skipped=False),
    )
    ports = TasksPorts(
        fs=FakeFsReader(), coord=coord, git=FakeGitOps(), render=FakeRender()
    )
    return ports, coord


def _run_move(
    tmp_path: Path,
    *,
    to: str,
    ports: TasksPorts,
    target_branch: str = "wip-lane",
    auto_commit: bool,
    json_output: bool = True,
    review_feedback_file: Path | None = None,
    extra_patches: dict[str, object] | None = None,
) -> None:
    with setup_mocked_env(
        tmp_path,
        mission_slug=_MISSION,
        target_branch=target_branch,
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
            **(extra_patches or {}),
        },
    ):
        _do_move_task(
            _MoveTaskArgs(
                task_id="WP01",
                to=to,
                mission=_MISSION,
                agent=None,
                assignee=None,
                shell_pid=None,
                note=None,
                review_feedback_file=review_feedback_file,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=auto_commit,
                json_output=json_output,
            ),
            ports=ports,
        )


def test_no_auto_commit_move_uses_commit_status_only(tmp_path: Path) -> None:
    """A ``--no-auto-commit`` for_review move emits the hop via ``commit_status``
    and NEVER touches the primary ``commit_artifact`` seam (C-001 disjointness)."""
    feature_dir, _wp = _build_wp_file(tmp_path, _MISSION, "WP01")
    _seed_wp_event(feature_dir, "WP01", "in_progress")
    ports, coord = _fake_ports(feature_dir)

    _run_move(tmp_path, to="for_review", ports=ports, auto_commit=False)

    # Exactly one lane hop, emitted through the coord status capability.
    assert len(coord.status_calls) == 1
    assert coord.status_calls[0][0] == _MISSION
    # The primary WRITE capability is UNTOUCHED (no auto-commit => no primary commit).
    assert coord.artifact_calls == []


def test_auto_commit_move_is_event_only_no_primary_wp_file_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Post-cutover (#2816/IC-04, event-only): an auto-commit move emits the hop
    via ``commit_status`` but routes NO ``WORK_PACKAGE_TASK`` primary commit — the
    WP file carries no runtime state (byte-stable) so there is nothing to commit.
    The runtime-state god-write (WP04/WP05, FR-006/FR-007) was deleted, so
    auto-commit no longer resurrects a WP-file write; the activity-log note is
    event-sourced, never written into the file."""
    feature_dir, wp_file = _build_wp_file(tmp_path, _MISSION, "WP01")
    _seed_wp_event(feature_dir, "WP01", "in_progress")
    ports, coord = _fake_ports(feature_dir)
    wp_bytes_before = wp_file.read_bytes()

    _run_move(tmp_path, to="for_review", ports=ports, auto_commit=True)

    # Lane hop still on the status seam.
    assert len(coord.status_calls) == 1
    assert coord.status_calls[0][0] == _MISSION
    # No primary WP-file commit: the event log is the sole authority (event-only).
    assert coord.artifact_calls == []
    # The WP file is byte-stable across the move (no god-write, no activity-log write).
    assert wp_file.read_bytes() == wp_bytes_before
    assert "Moved to for_review" not in wp_file.read_text(encoding="utf-8")

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "success"
    assert payload["new_lane"] == "for_review"
    assert "wp_file_update" not in payload  # non-skip arm: no skip envelope keys


def test_fr010_move_task_coord_status_dir_stays_on_coord_husk(tmp_path: Path) -> None:
    """FR-010 (T027): the coord WRITE port ``move_task`` uses to resolve its shared
    status/event-log dir (``feature_write_dir``) MUST land on the kind-blind coord
    husk (``resolve_feature_dir_for_mission``), NEVER a primary-partition kind.

    ``_mt_resolve_targets`` sets ``mt_feature_dir = ports.coord.feature_write_dir(...)``
    and feeds it to the pre30 guard, the authoritative event-log lane read, and the
    coord override persist. Repointing it to a PRIMARY kind (WORK_PACKAGE_TASK) would
    move the event-log read off the coord husk and reintroduce the split-brain FR-010
    closes. This pins the production router's leg to the coord-husk resolver.
    """
    _build_wp_file(tmp_path, _MISSION, "WP01")
    handle = MissionHandle(repo_root=tmp_path, mission_slug=_MISSION)
    coord_husk = resolve_feature_dir_for_mission(tmp_path, _MISSION)
    # The production move_task router resolves the coord husk for the shared status dir.
    # (constructor-DI collapse: the move_task coord router is now built via
    # ``seam_coord_router(route_emit=True)`` rather than the deleted
    # ``_MoveTaskCoordRouter`` subclass.)
    assert seam_coord_router(route_emit=True).feature_write_dir(handle) == coord_husk
    # A PRIMARY-partition kind would resolve a DIFFERENT dir under coord topology —
    # the status read must never be collapsed onto it (guard against a wholesale
    # repoint). On this flat fixture the STATUS partition stays path-equal to the husk.
    assert (
        resolve_planning_read_dir(
            tmp_path, _MISSION, kind=MissionArtifactKind.STATUS_STATE
        )
        == coord_husk
    )


def test_coord_skip_arm_suppresses_commit_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The coord skip-exit-0 arm (``skip_primary``) emits the hop on ``commit_status``
    but suppresses the primary ``commit_artifact`` call and reports the skip envelope
    — the fall-through control shape, NOT an early exit."""
    feature_dir, wp_file = _build_wp_file(tmp_path, _MISSION, "WP01")
    _seed_wp_event(feature_dir, "WP01", "in_progress")
    ports, coord = _fake_ports(feature_dir)
    pre_commit_body = wp_file.read_text(encoding="utf-8")

    _run_move(
        tmp_path,
        to="for_review",
        ports=ports,
        auto_commit=True,
        # Force the coord skip decision (protected-primary + coord topology proxy).
        extra_patches={"_skip_target_branch_commit": True},
    )

    # The transition is still emitted on the coord status seam ...
    assert len(coord.status_calls) == 1
    # ... but the primary commit is suppressed (skip arm) and the WP file is not
    # rewritten on the primary partition.
    assert coord.artifact_calls == []
    assert wp_file.read_text(encoding="utf-8") == pre_commit_body

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "success"
    assert payload["wp_file_update"] == "skipped"
    assert "coordination branch" in payload["wp_file_update_reason"]


_TASKS_MD_WITH_CHECKED_WP01 = """\
## WP01 — Build widget

- [x] T001 Design the API
- [x] T002 Implement the handler
- [ ] T003 Write tests

## WP02 — Ship widget

- [x] T004 Ship it
"""


def test_wp06_t028_rollback_to_planned_is_fully_reimplementable(tmp_path: Path) -> None:
    """T027/T028 (FR-010, SC-006), re-pointed for the god-write cut (WP10
    closeout): a WP rolled back to ``planned`` is fully re-implementable — its
    subtask completion is RESET so the review gate re-blocks on the next
    ``for_review``.

    With subtask completion event-sourced (WP04, FR-003) the reset is an
    ``InnerStateChanged`` ``subtasks`` delta folded into the reduced snapshot,
    NOT a ``tasks.md`` checkbox rewrite. Driven at ``status_phase: 1`` (flag ON,
    the shipped event-sourced write path) it is proven two ways: the gate-source
    snapshot roster flips fully back to ``planned`` (re-blockable), AND the WP
    file + ``tasks.md`` stay byte-stable (AC-5, event-only). Drives the SAME
    ``_do_move_task`` entry point the CLI invokes.

    NB: at flag OFF the gate still reads the ``tasks.md`` checkboxes (which stay
    ``[x]`` — event-only), so the reimplementable property holds only once the
    reader is cut over (flag ON) — hence the flag-ON frame. The #2512 claim
    release on rollback is covered by ``test_move_task_rollback_clears_claim``.
    """
    from charter.hasher import hash_content
    from specify_cli.status import materialize
    from specify_cli.status.emit import emit_inner_state_changed
    from specify_cli.status.models import WPInnerStateDelta
    from tests.lane_test_utils import write_mission_meta

    feature_dir, wp_file = _build_wp_file(tmp_path, _MISSION, "WP01")
    # Flag ON: event-only writes; the reset rides the snapshot, not the file.
    write_mission_meta(feature_dir)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["status_phase"] = "1"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    (feature_dir / "tasks.md").write_text(_TASKS_MD_WITH_CHECKED_WP01, encoding="utf-8")
    _seed_wp_event(feature_dir, "WP01", "in_review")

    # Positive control: drive WP01's roster fully DONE on the snapshot first, so a
    # naive (no-reset) rollback would leave the gate satisfied on stale progress.
    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(
            subtasks={"T001": Lane.DONE, "T002": Lane.DONE, "T003": Lane.DONE}
        ),
        actor="test",
        mission_slug=_MISSION,
        at="2026-01-01T00:00:05+00:00",
    )
    before = materialize(feature_dir).work_packages.get("WP01", {}).get("subtasks") or {}
    assert before and all(str(s) == str(Lane.DONE) for s in before.values()), (
        f"positive control: roster must be fully done before the rollback; got {before!r}"
    )

    tasks_md = feature_dir / "tasks.md"
    tasks_hash_before = hash_content(tasks_md.read_text(encoding="utf-8"))
    wp_hash_before = hash_content(wp_file.read_text(encoding="utf-8"))

    coord = FakeCoordCommitRouter(
        write_dir=feature_dir, status_result=CommitStatusResult(event=None, skipped=False)
    )
    # planning_read_dir must resolve the real on-disk feature_dir so the
    # subtask-reset roster read can find tasks.md (mirrors production wiring).
    ports = TasksPorts(
        fs=FakeFsReader(default_planning_dir=feature_dir),
        coord=coord,
        git=FakeGitOps(),
        render=FakeRender(),
    )

    feedback_file = tmp_path / "feedback.md"
    feedback_file.write_text("**Issue**: rollback for rework\n", encoding="utf-8")

    _run_move(
        tmp_path,
        to="planned",
        ports=ports,
        auto_commit=False,
        review_feedback_file=feedback_file,
    )

    # The gate-source snapshot roster is RESET to planned -> re-blockable.
    after = materialize(feature_dir).work_packages.get("WP01", {}).get("subtasks") or {}
    assert after, "rollback did not emit a subtasks reset"
    assert set(after) == {"T001", "T002", "T003"}, f"reset roster mismatch: {after!r}"
    assert all(str(s) == str(Lane.PLANNED) for s in after.values()), (
        f"rollback must reset every WP01 subtask to planned; got {after!r}"
    )
    # Event-only (AC-5): the reset rewrote NEITHER the WP file NOR tasks.md.
    assert hash_content(tasks_md.read_text(encoding="utf-8")) == tasks_hash_before, (
        "rollback rewrote tasks.md bytes (must be event-only at flag ON)"
    )
    assert hash_content(wp_file.read_text(encoding="utf-8")) == wp_hash_before, (
        "rollback rewrote tasks/WP01.md bytes (must be event-only at flag ON)"
    )
    # The tasks.md checkboxes are intentionally still [x] (byte-stable) — the
    # reset lives in the snapshot, not the file.
    assert "- [x] T001" in tasks_md.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# FIX-M2-03 — orchestrator-level agent-ownership regression pin.
#
# Reproduces the reported defect at the SAME layer ``move_task``'s Typer
# command actually runs at (``_do_move_task``, real event log via
# ``seed_status_event``/``_seed_claim_then_progress``), not just the pure decision
# core (``tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py``
# covers that layer). See ``_guard_agent_ownership``'s docstring in
# ``tasks_transition_core.py`` for the root-cause narrative.
# ---------------------------------------------------------------------------


def test_agent_ownership_generic_placeholder_claim_allows_real_agent_no_force(tmp_path: Path) -> None:
    """``spec-kitty implement WP01`` (invoked without ``--actor`` -- a
    documented, supported call shape per that command's own docstring)
    claims WP01 under the generic ``implement-command`` placeholder. The
    canonical next step, ``agent tasks move-task WP01 --to for_review --agent
    claude``, must succeed WITHOUT ``--force``. Before the fix this always
    raised the agent-ownership-mismatch guard (``RefuseExit1`` ->
    ``typer.Exit(1)``) for EVERY real ``--agent``, because
    ``'implement-command' != 'claude'`` under raw equality -- even though no
    real agent had ever claimed the WP.
    """
    feature_dir, _wp = _build_wp_file(tmp_path, _MISSION, "WP01")
    _seed_claim_then_progress(feature_dir, "WP01", claim_actor="implement-command")
    ports, coord = _fake_ports(feature_dir)

    with setup_mocked_env(
        tmp_path,
        mission_slug=_MISSION,
        target_branch="wip-lane",
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        # Must NOT raise typer.Exit(1) — the pre-fix ownership-mismatch refusal.
        _do_move_task(
            _MoveTaskArgs(
                task_id="WP01",
                to="for_review",
                mission=_MISSION,
                agent="claude",
                assignee=None,
                shell_pid=None,
                note=None,
                review_feedback_file=None,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=False,
                json_output=True,
            ),
            ports=ports,
        )

    # The transition actually proceeded (not silently swallowed elsewhere).
    assert len(coord.status_calls) == 1


def test_agent_ownership_real_owner_mismatch_still_refuses_at_orchestrator_level(tmp_path: Path) -> None:
    """Control case for the fix above: a genuine two-real-agent mismatch must
    still refuse (``typer.Exit(1)``) without ``--force`` — proving the
    generic-placeholder allowance does not widen to real agent identities.
    """
    import typer

    feature_dir, _wp = _build_wp_file(tmp_path, _MISSION, "WP01")
    _seed_claim_then_progress(feature_dir, "WP01", claim_actor="codex")
    ports, _coord = _fake_ports(feature_dir)

    with setup_mocked_env(
        tmp_path,
        mission_slug=_MISSION,
        target_branch="wip-lane",
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ), pytest.raises(typer.Exit):
        _do_move_task(
            _MoveTaskArgs(
                task_id="WP01",
                to="for_review",
                mission=_MISSION,
                agent="claude",
                assignee=None,
                shell_pid=None,
                note=None,
                review_feedback_file=None,
                approval_ref=None,
                reviewer=None,
                self_review_fallback=False,
                intended_reviewer=None,
                reviewer_failure_reason=None,
                done_override_reason=None,
                force=False,
                tracker_ref=None,
                skip_review_artifact_check=False,
                auto_commit=False,
                json_output=True,
            ),
            ports=ports,
        )
