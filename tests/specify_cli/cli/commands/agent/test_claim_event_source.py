"""WP04 (coord-write-placement-closure-01KYCF83) / T014, T016, T018 — the claim
+ subtask-completion event-sourcing regression, driven through the real
``spec-kitty agent action implement`` / ``mark-status`` entry points
(DIRECTIVE_041).

**Landing note (2026-08, `tests/regression/` campsite clean).** This is a
permanent guard, not a red-first reproduction, so it carries no `regression`
marker and lives with the sibling claim/event-sourcing coverage here rather
than in `tests/regression/`. It partially overlaps
``test_implement_runtime_frontmatter_claim.py`` (frontmatter-diff /
byte-stability angle) and ``test_issue_2684_subtask_completion_event_sourced.py``
(``move-task`` gate-reads-the-log angle) but adds a real angle neither
covers: assertions on the CLAIM EVENT'S OWN payload (``policy_metadata``
carries ``shell_pid``/``agent``; the reduced snapshot exposes them) and on
idempotent re-completion of an already-``done`` subtask in the snapshot —
verified during this relocation, not assumed.

**Scope note (live-evidence finding, recorded per DIRECTIVE_041/failing-test
discipline — this is NOT a fabricated red).** WP04's own subtasks (T014/T015:
event-source the claim; T016: event-source subtask completion; T018: dual-write
parity) were planned against a description of the codebase where the claim
``shell_pid``/``agent`` frontmatter mirror and the ``tasks.md`` checkbox write
were still the live authoring paths for #2684. By the time this WP actually
executed, BOTH authoring paths had already been fully event-sourced and their
frontmatter/checkbox dual-writes already UNCONDITIONALLY retired by prior,
already-merged work predating this mission:

* the claim triple (``shell_pid``/``shell_pid_created_at``/``agent``) rides the
  ``planned -> claimed`` transition's ``policy_metadata`` sidecar
  (:func:`specify_cli.status.emit.build_claim_policy_metadata`,
  ``workflow_executor.py::_implement_start_claim``) and the WP frontmatter
  mirror was removed (``workflow_executor.py::_implement_write_claim_and_commit``:
  "the WP file is NOT mutated for the claim... this function writes 0 runtime
  bytes to the WP file"; see also the pre-existing
  ``tests/specify_cli/cli/commands/agent/test_implement_runtime_frontmatter_claim.py``);
  and
* subtask completion is recorded via an ``InnerStateChanged`` annotation
  (``tasks_mark_status.py::_ms_emit_subtask_state``) and the ``tasks.md``
  checkbox write was retired unconditionally too ("Checkbox bytes ... are
  authored reference material only; neither is persisted by ``mark-status``");
  see also the pre-existing
  ``tests/specify_cli/cli/commands/agent/test_issue_2684_subtask_completion_event_sourced.py``.

Both predate this WP and are GREEN already, run FIRST here as a live
confirmation. This file therefore cannot be red-first for the event-sourcing
addition itself (there is no addition left to make): it LOCKS IN the current,
already-correct behavior as WP04's own owned regression coverage (create_intent),
and documents the parity claim (T018) honestly — the frontmatter/checkbox side
carries NO runtime bytes at all (not merely mirrored), so "parity" here means
byte-stability on that side plus presence on the event side, not equality of
two live copies. The one genuinely NEW WP04 change (T017/FR-003: closing the
``_current_branch`` HEAD-derived write-target fallback, #1716) is covered by
``tests/architectural/test_wp05_write_target_drain.py`` and
``tests/architectural/test_no_write_side_rederivation.py`` instead, with true
red-before/green-after evidence (verified by stashing the production fix and
re-running).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from typer.testing import CliRunner

from tests.lane_test_utils import lane_worktree_path, write_single_lane_manifest

from specify_cli.analysis_report import write_analysis_report
from specify_cli.cli.commands.agent import tasks as agent_tasks
from specify_cli.cli.commands.agent import workflow
from specify_cli.frontmatter import write_frontmatter
from specify_cli.status import Lane, StatusEvent, read_events, reduce
from specify_cli.status.store import append_event, read_event_stream

pytestmark = pytest.mark.fast

_MISSION_SLUG = "wp04-claim-event-source-demo"


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str, *, actor: str = "test") -> None:
    """Seed a WP into a specific lane in the event log (genesis -> lane)."""
    event = StatusEvent(
        event_id=f"test-{wp_id}-{lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(lane),
        at="2026-01-01T00:00:00+00:00",
        actor=actor,
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def _write_wp_file(path: Path, wp_id: str, *, subtasks: tuple[str, ...] = ("T001",)) -> None:
    frontmatter = {
        "work_package_id": wp_id,
        "subtasks": list(subtasks),
        "title": f"{wp_id} Test",
        "phase": "Phase 0",
        "execution_mode": "code_change",
        "owned_files": [f"src/{wp_id.lower()}/**"],
        "authoritative_surface": f"src/{wp_id.lower()}/",
        "assignee": "",
        "agent": "",
        "shell_pid": "",
        "review_status": "",
        "reviewed_by": "",
        "dependencies": [],
    }
    body = f"# {wp_id} Prompt\n\n## Activity Log\n- 2026-01-01T00:00:00Z - system - Prompt created.\n"
    write_frontmatter(path, frontmatter, body)


def _write_current_analysis_report(feature_dir: Path, repo_root: Path) -> None:
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo_root,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )


def _mint_fake_worktree(repo_root: Path, workspace: Path) -> None:
    """Mark a fixture workspace as a git worktree (#1833 husk guard)."""
    workspace.mkdir(parents=True, exist_ok=True)
    gitdir = repo_root / ".git" / "worktrees" / workspace.name
    gitdir.mkdir(parents=True, exist_ok=True)
    (workspace / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")


@pytest.fixture()
def workflow_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo_root = tmp_path
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text(
        "vcs:\n  type: git\nproject:\n  uuid: test-project-uuid\n  slug: test-project\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.workflow._ensure_target_branch_checked_out",
        lambda repo_root, mission_slug: (repo_root, "main"),
    )
    monkeypatch.setattr(
        "specify_cli.cli.commands.agent.workflow.safe_commit",
        lambda **kwargs: True,
    )
    return repo_root


def _seed_mission(workflow_repo: Path, *, subtasks: tuple[str, ...] = ("T001",)) -> tuple[Path, Path]:
    """Seed a single-WP, planned-lane mission ready for an implementation claim."""
    feature_dir = workflow_repo / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), predicted_surfaces=("workflow",))
    subtask_rows = "\n".join(f"- [ ] {task_id} Placeholder task" for task_id in subtasks)
    (feature_dir / "tasks.md").write_text(f"## WP01 Test\n\n{subtask_rows}\n", encoding="utf-8")
    wp_path = tasks_dir / "WP01-test.md"
    _write_wp_file(wp_path, "WP01", subtasks=subtasks)
    _seed_wp_lane(feature_dir, "WP01", "planned")
    _write_current_analysis_report(feature_dir, workflow_repo)
    _mint_fake_worktree(workflow_repo, lane_worktree_path(workflow_repo, _MISSION_SLUG))
    return feature_dir, wp_path


def _claimed_transition(feature_dir: Path) -> StatusEvent:
    events = read_events(feature_dir)
    matches = [e for e in events if e.wp_id == "WP01" and str(e.to_lane) == "claimed"]
    assert matches, f"expected a planned -> claimed transition for WP01, got events: {events}"
    return matches[-1]


def _claim_wp01(mission_slug: str = _MISSION_SLUG, agent: str = "test-agent") -> Result:
    return CliRunner().invoke(
        workflow.app,
        ["implement", "WP01", "--mission", mission_slug, "--agent", agent],
    )


@contextmanager
def _null_lock(repo_root: Path, mission_slug: str):  # type: ignore[no-untyped-def]
    del repo_root, mission_slug
    yield


def _mark_status_done(repo_root: Path, *task_ids: str, mission_slug: str = _MISSION_SLUG) -> Result:
    """Invoke ``mark-status`` with the same git/lock seams stubbed as
    ``tests/specify_cli/cli/commands/agent/test_tasks_mark_status.py``'s
    ``_invoke_mark_status`` -- this fixture's ``workflow_repo`` is a bare
    directory tree (no real git checkout), matching that file's pattern
    rather than ``workflow.app``'s own ``_ensure_target_branch_checked_out``
    seam (a different module import site)."""
    with (
        patch(
            "specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out",
            return_value=(repo_root, "main"),
        ),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
    ):
        return CliRunner().invoke(
            agent_tasks.app,
            [
                "mark-status",
                *task_ids,
                "--status",
                "done",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )


# ---------------------------------------------------------------------------
# T014 — the claim event carries shell_pid/agent (reducible from the log).
# ---------------------------------------------------------------------------


class TestClaimEventCarriesShellPidAndAgent:
    def test_claimed_transition_policy_metadata_carries_the_claim_triple(self, workflow_repo: Path) -> None:
        feature_dir, _wp_path = _seed_mission(workflow_repo)

        result = _claim_wp01()
        assert result.exit_code == 0, result.stdout

        claimed_event = _claimed_transition(feature_dir)
        assert claimed_event.policy_metadata is not None
        assert claimed_event.policy_metadata["agent"] == "test-agent"
        assert isinstance(claimed_event.policy_metadata["shell_pid"], int)
        assert "shell_pid_created_at" in claimed_event.policy_metadata

    def test_reduced_snapshot_exposes_shell_pid_and_agent_after_claim(self, workflow_repo: Path) -> None:
        feature_dir, _wp_path = _seed_mission(workflow_repo)

        result = _claim_wp01()
        assert result.exit_code == 0, result.stdout

        stream = read_event_stream(feature_dir)
        snapshot = reduce(stream.transitions, stream.annotations)
        wp_state = snapshot.work_packages["WP01"]
        assert wp_state.get("agent") == "test-agent"
        assert isinstance(wp_state.get("shell_pid"), int)


# ---------------------------------------------------------------------------
# T018 — dual-write parity: the WP file is byte-stable, the event is present.
# ---------------------------------------------------------------------------


class TestClaimDualWriteParity:
    def test_claim_carries_no_status_phase_gate_and_wp_file_stays_byte_stable(self, workflow_repo: Path) -> None:
        """The frontmatter claim mirror is retired UNCONDITIONALLY (not gated
        on ``status_phase``): a mission with no ``status_phase`` set at all
        (this fixture's default -- and this WP04 mission's own live
        ``meta.json`` state) already gets a byte-stable WP file across the
        claim, with the claim triple living solely in the event log. This is
        the "parity" WP04's T018 asks for: the log is authoritative and the
        static WP file carries no divergent runtime copy to go stale."""
        feature_dir, wp_path = _seed_mission(workflow_repo)
        assert not json.loads((feature_dir / "meta.json").read_text(encoding="utf-8")).get(
            "status_phase"
        )
        before = wp_path.read_bytes()

        result = _claim_wp01()
        assert result.exit_code == 0, result.stdout

        after = wp_path.read_bytes()
        assert after == before, "the WP file must stay byte-identical across the claim"

        claimed_event = _claimed_transition(feature_dir)
        assert claimed_event.policy_metadata is not None
        assert claimed_event.policy_metadata["agent"] == "test-agent"


# ---------------------------------------------------------------------------
# T016 — subtask completion is event-sourced and idempotent.
# ---------------------------------------------------------------------------


class TestSubtaskCompletionIdempotent:
    def test_recompleting_an_already_done_subtask_stays_done_in_the_snapshot(
        self, workflow_repo: Path
    ) -> None:
        """The reduced snapshot converges to (and stays) DONE across a repeat
        ``mark-status ... --status done`` on an already-done subtask.

        **Scope note (live-evidence finding):** ``_resolve_checkbox``
        (``tasks_materialization.py``, outside WP04's owned files -- WP04 owns
        only ``status_transition.py`` / ``subtask_rows.py`` /
        ``tests/regression/test_claim_event_source.py``, per C-002) reports
        ``UPDATED`` whenever a task id is FOUND, regardless of its prior
        checkbox state, so ``_ms_emit_subtask_state`` appends a fresh
        (same-valued) ``InnerStateChanged`` annotation on every repeat
        ``mark-status`` call rather than suppressing it. WP04's T016 wording
        ("re-completing appends none") does not literally hold at the
        raw-event-count level for this pre-existing, out-of-scope emitter --
        but the property that actually matters (the completion authority
        never regresses/duplicates-as-corruption) DOES hold: the reduced
        snapshot's ``subtasks`` slot is a last-write-wins map keyed by task id
        (:func:`specify_cli.status.reducer.reduce`), so repeat identical
        annotations are idempotent IN EFFECT even though they are not
        deduplicated IN STORAGE. This test pins the effect that is actually
        load-bearing for the review gate
        (:func:`specify_cli.core.subtask_rows.unchecked_subtask_ids_from_snapshot`);
        deduplicating the raw event count would require touching
        ``tasks_mark_status.py``/``tasks_materialization.py``, which is out of
        this WP's scope.
        """
        feature_dir, _wp_path = _seed_mission(workflow_repo, subtasks=("T001", "T002"))

        first = _mark_status_done(workflow_repo, "T001")
        assert first.exit_code == 0, first.stdout

        stream_after_first = read_event_stream(feature_dir)
        annotations_after_first = [
            a for a in stream_after_first.annotations if a.wp_id == "WP01" and a.delta.subtasks
        ]
        assert len(annotations_after_first) == 1, (
            "exactly one subtask-completion annotation expected after the first "
            f"mark-status done, got {annotations_after_first!r}"
        )
        snapshot_after_first = reduce(stream_after_first.transitions, stream_after_first.annotations)
        assert snapshot_after_first.work_packages["WP01"]["subtasks"]["T001"] == str(Lane.DONE)

        # Re-completing the SAME already-done subtask must not regress the
        # completion authority -- the snapshot stays DONE.
        second = _mark_status_done(workflow_repo, "T001")
        assert second.exit_code == 0, second.stdout

        stream_after_second = read_event_stream(feature_dir)
        snapshot_after_second = reduce(stream_after_second.transitions, stream_after_second.annotations)
        assert snapshot_after_second.work_packages["WP01"]["subtasks"]["T001"] == str(Lane.DONE), (
            "the reduced snapshot's completion authority must remain DONE across "
            "a repeat mark-status done call"
        )
        # unchecked_subtask_ids_from_snapshot (the guard's actual read) reports
        # T001 as complete either way -- this is the property T016 protects.
        from specify_cli.core.subtask_rows import unchecked_subtask_ids_from_snapshot

        assert unchecked_subtask_ids_from_snapshot(feature_dir, "WP01", ["T001"]) == []


# ---------------------------------------------------------------------------
# #3938 — implement on an in_progress WP claimed by move-task's ``user``
# placeholder resumes (no conflict) and regenerates the prompt file.
# ---------------------------------------------------------------------------


class TestInProgressUserActorResume:
    """``move-task WP04 --to in_progress`` without ``--agent`` records the
    placeholder actor ``user`` (``tasks_move_task.py::_mt_execute``'s
    ``st.agent or "user"`` fallback). A recovering orchestrator then runs
    ``agent action implement WP04 --agent <agent>`` to hand the WP to a real
    implementer. Before #3938's fix that invocation refused with
    "WP WP04 is already claimed for implementation by 'user'" and exited
    before the prompt path was emitted, so the implementer was dispatched
    against either the raw kitty-specs WP prompt or a stale prompt path from
    another mission's ``spec-kitty-prompts`` directory (F-52/F-67). The
    documented behavior is the no-op resume: the claim succeeds as a resume,
    the WP stays ``in_progress`` with no new transition events, and the
    mission-scoped prompt file is (re)written and its path printed."""

    def test_implement_resumes_user_claimed_in_progress_and_rewrites_prompt(
        self, workflow_repo: Path
    ) -> None:
        from runtime.next._tmp_namespace import prompt_tmp_dir

        feature_dir, _wp_path = _seed_mission(workflow_repo)
        # The move-task-shaped history: planned (seeded) -> in_progress with
        # the ``user`` placeholder actor, exactly as a bare
        # ``move-task WP01 --to in_progress`` records it.
        append_event(
            feature_dir,
            StatusEvent(
                event_id="test-WP01-user-in-progress",
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-01-02T00:00:00+00:00",
                actor="user",
                force=True,
                execution_mode="worktree",
            ),
        )
        transitions_before = [e for e in read_events(feature_dir) if e.wp_id == "WP01"]

        result = _claim_wp01(agent="recovery-agent")
        assert result.exit_code == 0, result.stdout

        # No-op resume: the WP stays in_progress with no NEW transition events
        # (the resume refresh rides an InnerStateChanged annotation, not a
        # lane transition), and no "already claimed" refusal was printed.
        transitions_after = [e for e in read_events(feature_dir) if e.wp_id == "WP01"]
        assert transitions_after == transitions_before
        assert "already claimed" not in result.stdout
        snapshot = reduce(read_event_stream(feature_dir).transitions, read_event_stream(feature_dir).annotations)
        assert snapshot.work_packages["WP01"]["lane"] == Lane.IN_PROGRESS

        # F-67: the implementation prompt file is (re)generated at the
        # mission-scoped path and the path is emitted for the implementer.
        prompt_file = (
            prompt_tmp_dir(workflow_repo) / f"spec-kitty-implement-{_MISSION_SLUG}-WP01.md"
        )
        assert prompt_file.exists(), "resume must (re)write the implementation prompt file"
        assert "WP01" in prompt_file.read_text(encoding="utf-8")
        assert str(prompt_file) in result.stdout
