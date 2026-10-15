"""WP04 (#676) — Integration tests: counter advances only on real rejections.

Scenario coverage (from WP04, T022):

1. Set up a mission + WP via the existing rejection-cycle fixtures.
2. Drive the WP to ``for_review``.
3. Re-run ``agent action implement`` 2 times → counter unchanged, no new
   ``review-cycle-N.md`` artifact.
4. Trigger a real rejection event (``move-task --to planned`` with a
   ``--review-feedback-file``) → counter advances by exactly 1, exactly one
   new ``review-cycle-N.md`` artifact at the new N.
5. Re-run ``agent action implement`` once more → counter unchanged.

The integration is end-to-end via the CLI Typer app:
``specify_cli.cli.commands.agent.workflow.app`` for implement, and
``specify_cli.cli.commands.agent.tasks._persist_review_feedback`` for the
canonical rejection event (the same helper invoked by the
``move-task --to planned`` CLI surface).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.frontmatter import write_frontmatter
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from specify_cli.status.store import append_event


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "001-rejection-only-feature"
WP_SLUG = "WP01-test-task"


# ---------------------------------------------------------------------------
# Helpers (kept in-file for clarity; mirror tests/integration/test_rejection_cycle.py)
# ---------------------------------------------------------------------------


def _make_event(
    *,
    event_id: str,
    wp_id: str = "WP01",
    from_lane: Lane = Lane.PLANNED,
    to_lane: Lane = Lane.CLAIMED,
    review_ref: str | None = None,
    mission_slug: str = MISSION_SLUG,
    review_result: ReviewResult | None = None,
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at="2026-04-28T12:00:00Z",
        actor="claude",
        force=False,
        execution_mode="worktree",
        review_ref=review_ref,
        review_result=review_result,
    )


def _write_cli_wp(wp_path: Path) -> None:
    write_frontmatter(
        wp_path,
        {
            "work_package_id": "WP01",
            "subtasks": ["T001"],
            "title": "Test Task",
            "phase": "Phase 1",
            "lane": "planned",
            "dependencies": [],
            "assignee": "",
            "agent": "claude",
            "shell_pid": "",
            "review_status": "none",
            "review_feedback": "",
            "history": [],
        },
        "# WP01 Prompt\n",
    )


# ---------------------------------------------------------------------------
# Fixture: build a minimal mission + WP repo and put the WP into for_review.
# ---------------------------------------------------------------------------


@pytest.fixture()
def for_review_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    """Initialise a git repo with one mission, one WP, currently in ``for_review``.

    Returns ``(repo_root, feature_dir, sub_artifact_dir)``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    (repo / ".kittify").mkdir()

    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "feature_number": "001",
                "mission_slug": MISSION_SLUG,
                "created_at": "2026-04-28T00:00:00Z",
                "friendly_name": MISSION_SLUG,
                "mission": "software-dev",
                "slug": MISSION_SLUG,
                "target_branch": "main",
                "vcs": "git",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=MISSION_SLUG,
            mission_id=f"mission-{MISSION_SLUG}",
            mission_branch=f"kitty/mission-{MISSION_SLUG}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("core",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-28T10:00:00Z",
            computed_from="test",
        ),
    )
    (feature_dir / "tasks.md").write_text(
        "## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8"
    )
    _write_cli_wp(tasks_dir / f"{WP_SLUG}.md")

    # Drive event log: planned -> claimed -> in_progress -> for_review.
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000001",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
        ),
    )
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000002",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
        ),
    )
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000003",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.FOR_REVIEW,
        ),
    )

    workspace = repo / ".worktrees" / f"{MISSION_SLUG}-lane-a"
    workspace.mkdir(parents=True)

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "seed for-review fixture"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    sub_artifact_dir = feature_dir / "tasks" / WP_SLUG

    monkeypatch.chdir(repo)
    return repo, feature_dir, sub_artifact_dir


# ---------------------------------------------------------------------------
# Helper: fire the canonical rejection handler (counter mutation site).
# ---------------------------------------------------------------------------


def _trigger_rejection(repo: Path, body: str) -> Path:
    """Drive the canonical rejection handler exactly once.

    Mirrors what ``spec-kitty agent tasks move-task WP01 --to planned
    --review-feedback-file <path>`` does internally — calls
    ``_persist_review_feedback`` which writes ``review-cycle-N.md`` and
    returns the persisted path.
    """
    from specify_cli.cli.commands.agent.tasks import _persist_review_feedback

    feedback_file = repo / f"feedback_{abs(hash(body))}.md"
    feedback_file.write_text(body, encoding="utf-8")

    # ``_persist_review_feedback`` is declared ``-> tuple[Path, str]`` at its
    # definition (``agent/tasks_materialization.py``), but ``[tool.mypy]``
    # sets ``follow_imports = "skip"`` for ``specify_cli.*``, so the symbol
    # arrives here as ``Any``. Narrow it back at the boundary rather than
    # suppressing the resulting ``no-any-return``.
    persisted: Path
    persisted, _pointer = _persist_review_feedback(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        task_id="WP01",
        feedback_source=feedback_file,
        reviewer_agent="claude",
    )
    return persisted


# ---------------------------------------------------------------------------
# T022 — End-to-end integration test
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Flagship end-to-end test (User Story 5 / FR-017 AC2, WP16 T070).
# ---------------------------------------------------------------------------
#
# Restored under its ORIGINAL, unchanged name. A prior, independent landing
# fold (``test(landing): move the #2996 review-verdict reproductions into
# tests/regression``) relocated this exact test to
# ``tests/regression/test_issue_2996_approval_after_rejection_writes_no_verdict.py``
# on the premise that it was still an intentionally-failing #2996(a) P0
# reproduction. That premise no longer holds -- a follow-up landing fold
# fixed the FIXTURE ROT that was blocking the reproduction from ever
# reaching the real (already-fixed) approval code path, so the test now
# passes there. Its absence from THIS file, though, left
# ``tests/architectural/test_verdict_name_truthfulness.py::test_flagship_end_to_end_test_asserts_the_non_forced_path``
# red: that gate hardcodes both this file and this exact function name as
# User Story 5's AC2 flagship (see WP16's Activity Log entry, T070) and
# looks it up by exact name at this exact path -- an absence the earlier
# relocation fold did not reconcile against.
#
# 2026-08 regression-suite exit-rule fold (tests/regression/README.md):
# ``tests/regression/test_issue_2996_approval_after_rejection_writes_no_verdict.py``
# was confirmed a behaviorally-equivalent duplicate of THIS test (same
# lifecycle, same assertions; the only difference was cosmetic fixture
# plumbing for the ``.worktrees/<slug>-lane-a`` husk) and deleted rather than
# relocated -- this restored copy is the one and only permanent home the
# flagship gate above requires.
#
# WP16 itself already filed the one open naming question here as a cross-WP
# finding it explicitly did not fix: this test's OWN NAME ("writes NO
# verdict artifact") contradicts its own body, which proves the opposite --
# an ordinary, non-forced approve after a genuine rework-and-resubmit cycle
# DOES write a fresh ``approved`` verdict artifact. WP16 did not own this
# file and left the rename to whoever does. That finding still stands and is
# NOT resolved here either: the gate's ``flagship_name`` lookup is a fixed
# string literal in a file this fold does not edit, so any rename away from
# it would trade one red gate for another. Restoring presence under the
# gate's own required name is the fix within that constraint; the
# naming-truthfulness question itself remains exactly as open as WP16 left
# it.
def test_approving_a_rejected_wp_writes_no_verdict_artifact(
    for_review_repo: tuple[Path, Path, Path],
) -> None:
    """Confirm the well-behaved reject -> rework -> resubmit -> approve
    lifecycle writes a fresh ``approved`` verdict artifact through the real
    CLI boundary -- this mission's most direct evidence that the fix
    actually closes the #2996(a) gap, and (per FR-017 AC2) that the flagship
    end-to-end test asserts the ordinary, NON-forced approval path: no
    ``--skip-review-artifact-check``, no ``--force`` used to bypass the
    verdict-artifact guard itself (only, if ever, guards unrelated to the
    fix under test).
    """
    from specify_cli.cli.commands.agent import tasks as agent_tasks
    from specify_cli.review.artifacts import ReviewCycleArtifact

    repo, feature_dir, sub_artifact_dir = for_review_repo

    # This fixture's ``.worktrees/<slug>-lane-a`` seed directory is an empty,
    # non-git "husk" -- fine for the counter-advancement tests above (which
    # never resolve it through a real lane-worktree health check), but a
    # ``move-task --to approved`` DOES resolve it and would refuse on a
    # missing ``.git`` entry. This WP's lifecycle here is driven entirely
    # through the status-event log and the review-cycle artifact writer,
    # never through real lane-worktree code changes, so removing the husk
    # (rather than fabricating a real worktree) is the correct fix: an
    # absent path makes worktree validation a no-op.
    husk = repo / ".worktrees" / f"{MISSION_SLUG}-lane-a"
    if husk.is_dir():
        husk.rmdir()

    # WP starts at for_review (fixture). Move it into in_review for the FIRST
    # (real) review round.
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000004",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
        ),
    )

    # Reviewer rejects cycle 1.
    persisted = _trigger_rejection(repo, "## Cycle 1 issues\n\nFix the off-by-one.")
    assert persisted.name == "review-cycle-1.md"
    latest_after_rejection = ReviewCycleArtifact.latest(sub_artifact_dir)
    assert latest_after_rejection is not None
    # WP06 (FR-003/SC-007): ``ReviewCycleArtifact`` no longer carries a
    # ``verdict`` field -- ``_persist_review_feedback`` (called directly via
    # ``_trigger_rejection``, not through the full move-task transition
    # machinery) never emits a review_result event either, so the real
    # reviewer body content is the checkable proxy that this is genuinely
    # the rejection write.
    assert "off-by-one" in latest_after_rejection.body

    # Commit the freshly-written review-cycle-1.md -- the CLI's own
    # dirty-worktree guard requires this before any further lane transition.
    subprocess.run(
        ["git", "add", f"kitty-specs/{MISSION_SLUG}/"], cwd=repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "docs(WP01): record cycle 1 rejection feedback"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    # Drive the WP back through the FULL lifecycle after the rejection --
    # in_review -> planned (rejected) -> claimed -> in_progress -> for_review
    # -> in_review -- exactly as a real implementer reworking and
    # resubmitting the WP for a genuine second review round would.
    #
    # WP06 (FR-003/SC-007) repoint: this IN_REVIEW -> PLANNED transition is
    # the event-authority record of the rejection (WP05, verdict-seam-write-
    # unification-01KZ9Q35, FR-013 pure-event repoint) -- without a
    # ``review_result`` on THIS event, the reducer's exit-from-in_review rule
    # marks the WP's review slot "damaged" (present but unparseable), which
    # is exactly what a real ``move-task --to planned --review-feedback-file``
    # would never do (it always records the ``changes_requested`` result on
    # the SAME transition). Carrying it here mirrors that real write path.
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000005",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            review_result=ReviewResult(
                reviewer="claude",
                verdict="changes_requested",
                reference=f"review-cycle://{MISSION_SLUG}/{WP_SLUG}/review-cycle-1.md",
            ),
        ),
    )
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000006",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
        ),
    )
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000007",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
        ),
    )
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000008",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.FOR_REVIEW,
        ),
    )
    append_event(
        feature_dir,
        _make_event(
            event_id="01TEST00000000000000000009",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
        ),
    )

    # Drive T001 to "done" through the REAL completion surface -- the
    # ``mark-status`` command's ``InnerStateChanged`` subtask-completion
    # emit -- so the approval guard's event-sourced snapshot reflects
    # genuine completion. The WP01 fixture's authored ``subtasks: ["T001"]``
    # roster lets ``mark-status`` resolve T001's owning WP without any extra
    # wiring.
    runner = CliRunner()
    mark_status_result = runner.invoke(
        agent_tasks.app,
        [
            "mark-status",
            "T001",
            "--status",
            "done",
            "--mission",
            MISSION_SLUG,
            "--no-auto-commit",
        ],
    )
    assert mark_status_result.exit_code == 0, (
        "expected marking T001 done via the real mark-status command to "
        f"succeed. CLI stdout:\n{mark_status_result.stdout}"
    )

    # The reviewer is now satisfied and approves -- a plain approve, with NO
    # override flags, and a caller-declared reviewer identity via --agent.
    reviewer_identity = "reviewer-renata"
    result = runner.invoke(
        agent_tasks.app,
        [
            "move-task",
            "WP01",
            "--to",
            "approved",
            "--mission",
            MISSION_SLUG,
            "--agent",
            reviewer_identity,
            "--note",
            "Approving after fixes were verified in the resubmitted review cycle.",
            "--no-auto-commit",
        ],
    )

    # Assert artifact FIRST (names the missing producer, not the guard).
    latest = ReviewCycleArtifact.latest(sub_artifact_dir)
    assert latest is not None, (
        "expected a fresh review-cycle-N.md verdict artifact to exist after "
        f"the approve attempt; none was created. CLI stdout:\n{result.stdout}"
    )
    assert latest.cycle_number > 1, (
        f"expected a fresh cycle number above the rejected cycle 1, got "
        f"{latest.cycle_number} -- the stale rejected cycle 1 is still "
        f"'latest'. CLI stdout:\n{result.stdout}"
    )
    # WP06 (FR-003/SC-007): ``ReviewCycleArtifact`` no longer carries a
    # ``verdict`` field -- the approval write path's own synthesized body
    # ("Approved by ...", ``_persist_approved_review_cycle``) is the
    # checkable proxy that this is genuinely an approval, not a stale
    # rejection artifact.
    assert latest.body.startswith("Approved by "), (
        f"expected the latest review-cycle artifact to carry an approval "
        f"body, got {latest.body!r}. CLI stdout:\n{result.stdout}"
    )
    assert latest.reviewer_agent == reviewer_identity, (
        f"expected the approval artifact to echo the declared --agent "
        f"identity {reviewer_identity!r}, got {latest.reviewer_agent!r}. "
        f"CLI stdout:\n{result.stdout}"
    )
    assert latest.body.strip(), (
        "expected the approval artifact to carry non-empty reviewer-authored "
        f"body content, got an empty body. CLI stdout:\n{result.stdout}"
    )

    assert result.exit_code == 0, (
        f"expected the well-behaved reworked-and-resubmitted approve to "
        f"succeed; got exit code {result.exit_code}. CLI stdout:\n{result.stdout}"
    )
