"""``consolidate`` keeps the only copy of review feedback and traces in a coordination worktree (#5965).

A coordination-topology Mission rejects a Work Package through the REAL
``spec-kitty agent tasks move-task WP02 --to planned --no-auto-commit``. That call
writes ``kitty-specs/<slug>/tasks/WP02-work/review-cycle-1.md`` into the coordination
worktree and leaves it uncommitted: it is the only copy of the reviewer's feedback.
An operator then keeps a hand-written ``traces/notes.md`` in the same worktree.
``consolidate`` reaches ``CoordinationWorkspace.teardown``, whose residue predicate
(``is_toolchain_generated_churn`` given the Mission slug but no checkout role) calls
both files residue, so ``guarded_worktree_remove`` force-removes the worktree and
``coordination/teardown.py::_destroy_coordination_worktree`` swallows any refusal.
``consolidate`` exits 0 and the feedback is gone.

Fixture choices, all driven through production entry points:

* ``build_coord_mission`` supplies the merge-ready coordination Mission (two approved WPs,
  each on its own lane branch, coordination worktree materialized).
* The terminus fixture writes WP files without a ``subtasks`` roster, which ``move-task``
  refuses (fail-closed roster resolution). Production WP files always carry the key, so the
  fixture adds ``subtasks: []`` to both WP files and commits it on the target branch and on
  the coordination branch. Nothing else is hand-placed.
* ``consolidate`` refuses a Mission whose WP02 is ``planned`` (not merge-ready), exactly as in
  the reporter's script, so WP02 is then canceled through ``move-task --to canceled
  --no-auto-commit``; its lane is skipped ("all WPs canceled with provenance"), WP01 lands, and
  ``consolidate`` reaches the coordination teardown. The review-cycle file written by the
  rejection stays uncommitted through the cancellation.

Before the fix, ``consolidate`` exited 0 and the feedback was gone; the guard now refuses
(``COORD_TEARDOWN_KEPT_ONLY_COPY``, exit 76) and keeps the worktree. Converted from the
red-first reproduction (ADR 2026-07-17-1): the transitional ``p0_repro`` / ``regression``
markers are dropped, the assertions are unchanged, and the positive control stays.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import CoordMission, build_coord_mission, run_terminus
from tests.terminus.rollback_harness import flat

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_AGENT = "claude"
_MOVE_TASK = ("agent", "tasks", "move-task")
_REVIEW_FEEDBACK = "Reviewer feedback: the retry path swallows the timeout. Fix before approval.\n"
_TRACE_NOTES = "# notes\nhand-written operator trace: see WP02 rejection.\n"
_SUBTASKS_ANCHOR = "agent: implementer-ivan\n"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _coord_worktree(mission: CoordMission) -> Path:
    return mission.repo / ".worktrees" / f"{mission.slug}-coord"


def _declare_subtask_rosters(mission: CoordMission) -> None:
    """Give each WP file the ``subtasks`` key every production WP file carries, committed on both branches."""
    for base in (mission.repo, _coord_worktree(mission)):
        for wp_file in sorted((base / "kitty-specs" / mission.slug / "tasks").glob("WP0?-work.md")):
            wp_file.write_text(wp_file.read_text(encoding="utf-8").replace(_SUBTASKS_ANCHOR, f"{_SUBTASKS_ANCHOR}subtasks: []\n"), encoding="utf-8")
        _git(base, "add", "-A", "kitty-specs")
        _git(base, "commit", "-qm", "chore(fixture): declare empty subtask rosters")


def _move_task(mission: CoordMission, wp: str, to: str, *extra: str) -> None:
    result = run_terminus(mission, [*_MOVE_TASK, wp, "--to", to, "--mission", mission.slug, "--agent", _AGENT, "--no-auto-commit", *extra])
    assert result.returncode == 0, f"fixture invalid: move-task {wp} --to {to} failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"


def _consolidate(mission: CoordMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])


@pytest.fixture
def two_wp_coord_mission(tmp_path: Path) -> CoordMission:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M5965A")
    _declare_subtask_rosters(mission)
    return mission


def test_5965_consolidate_keeps_uncommitted_review_feedback_and_traces(two_wp_coord_mission: CoordMission, tmp_path: Path) -> None:
    mission = two_wp_coord_mission
    worktree = _coord_worktree(mission)
    feedback_file = tmp_path / "feedback.md"
    feedback_file.write_text(_REVIEW_FEEDBACK, encoding="utf-8")

    _move_task(mission, "WP02", "planned", "--review-feedback-file", str(feedback_file))
    review_cycle = worktree / "kitty-specs" / mission.slug / "tasks" / "WP02-work" / "review-cycle-1.md"
    assert review_cycle.is_file(), "fixture invalid: move-task --to planned --no-auto-commit must write the review-cycle file in the coordination worktree"
    _move_task(mission, "WP02", "canceled", "--note", "dropped from scope")
    traces = worktree / "kitty-specs" / mission.slug / "traces" / "notes.md"
    traces.parent.mkdir(exist_ok=True)
    traces.write_text(_TRACE_NOTES, encoding="utf-8")
    review_bytes = review_cycle.read_bytes()

    result = _consolidate(mission)

    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert review_cycle.is_file() and review_cycle.read_bytes() == review_bytes, f"#5965: the only copy of the review feedback was destroyed by teardown\n{output}"
    assert traces.is_file() and traces.read_text(encoding="utf-8") == _TRACE_NOTES, f"#5965: the hand-written traces/notes.md was destroyed by teardown\n{output}"
    assert worktree.is_dir(), f"#5965: the coordination worktree holding the only copies was removed\n{output}"
    assert result.returncode != 0, f"#5965: consolidate must refuse (non-zero) instead of reporting success over the loss\n{output}"
    assert str(review_cycle.relative_to(worktree)) in flat(result) or review_cycle.name in flat(result), f"the refusal must name the kept file\n{output}"


def test_5965_control_regenerated_tool_output_alone_does_not_block_teardown(two_wp_coord_mission: CoordMission) -> None:
    """FR-002 no-op guard: the Mission's own status files are the only dirt, so teardown still removes the worktree.

    WP02 is canceled straight from ``approved`` (no rejection, so no review-cycle file); the
    cancellation leaves ``status.events.jsonl`` and ``status.json`` modified in the coordination
    worktree, which is regenerated tool output and genuine residue.
    """
    mission = two_wp_coord_mission
    worktree = _coord_worktree(mission)
    _move_task(mission, "WP02", "canceled", "--note", "dropped from scope")
    dirty = subprocess.run(["git", "-C", str(worktree), "status", "--porcelain", "-uall"], check=True, capture_output=True, text=True).stdout.splitlines()
    assert dirty, "fixture invalid: the cancellation must leave regenerated status output uncommitted"
    assert all(line.endswith(("status.events.jsonl", "status.json")) for line in dirty), f"fixture invalid: only tool output may be dirty: {dirty}"

    result = _consolidate(mission)

    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert result.returncode == 0, output
    assert not worktree.exists(), f"teardown must remove a worktree whose only dirt is regenerated tool output\n{output}"
