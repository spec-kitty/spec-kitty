"""#7755 / #7754 through ``spec-kitty consolidate``: a stale refusal caused by a sibling lane is recoverable.

Two approved, independent lanes edit adjacent hunks of one file. ``consolidate``
folds ``lane-a`` into the Mission branch, finds ``lane-b`` stale, its in-run
auto-rebase stops on the conflict, and the run rolls the Mission branch back to
its pre-run tip. Before the fix the refusal named that rolled-back Mission branch
(refreshing from it brought in nothing, so every re-run refused the same way,
#7755) and started with ``agent action implement``, which refuses an approved
work package (#7754).

The recovery test follows the printed remedy literally: it reopens the work
package (approved -> planned with review feedback, through the production status
shell, as the printed ``move-task`` does), incorporates the sibling lane the remedy
names at its approval stamp (what the printed ``implement --incorporate`` runs,
WP07), resolves, commits, has the work package reviewed and approved again, and
re-runs ``consolidate``, which must pass lane-b and land the Mission.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests.consolidation.stale_sibling_lane_support import (
    IMPLEMENTER,
    POPUP,
    RESOLVED_TEXT,
    StaleSiblingMission,
    approve,
    build_stale_sibling_mission,
)
from tests.terminus.conftest import _git, run_terminus
from tests.terminus.mixed_lane_support import transition

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.slow]


def _flat(result: subprocess.CompletedProcess[str]) -> str:
    """Console output with the terminal wrapping undone."""
    return " ".join(((result.stdout or "") + (result.stderr or "")).split())


def _consolidate(scenario: StaleSiblingMission) -> subprocess.CompletedProcess[str]:
    return run_terminus(scenario.mission, ["consolidate", "--mission", scenario.mission.slug])


def _show(repo: Path, ref: str, path: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "show", f"{ref}:{path}"], capture_output=True, text=True, check=True).stdout


def _assert_refusal_is_actionable(flat: str, scenario: StaleSiblingMission) -> str:
    """The refusal names the sibling branch and starts with a step an approved WP can run; return the named branch."""
    assert "lane-b is stale" in flat, flat
    # #7754: the first step reopens the approved work package and states the review cost.
    reopen = flat.find("spec-kitty agent tasks move-task WP02 --to planned --review-feedback-file")
    implement = flat.find("spec-kitty agent action implement WP02")
    assert reopen != -1, flat
    assert "re-review" in flat, flat
    assert implement == -1 or reopen < implement, flat
    # #7755: the change to incorporate is the sibling lane's branch, never the rolled-back Mission branch.
    assert f"incorporate changes from {scenario.mission.coord_branch}" not in flat, flat
    # WP07: the sibling is incorporated at its approval stamp through the CLI, never ``git merge``d.
    assert not re.search(r"git merge(?! --abort)", flat), flat
    named = re.findall(r"--incorporate (\S+)", flat)
    assert named == ["lane-a"], flat
    assert scenario.lane_a_branch in flat, flat
    return str(named[0])


def test_operator_who_follows_the_remedy_lands_the_mission(tmp_path: Path) -> None:
    scenario = build_stale_sibling_mission(tmp_path)
    mission = scenario.mission

    first = _consolidate(scenario)
    flat = _flat(first)
    assert first.returncode != 0, flat
    assert "restored" in flat, flat  # precondition: the run rolled the Mission branch back
    # FR-001: the refusal says the in-run auto-rebase stopped, with its reason.
    assert re.search(r"in-run auto-rebase .{0,80}stopped: \S", flat), flat
    sibling_lane = _assert_refusal_is_actionable(flat, scenario)

    # Follow the remedy: reopen WP02 with review feedback, re-enter it, incorporate the named lane, resolve, commit.
    transition(mission, "WP02", "planned", actor=IMPLEMENTER, review_ref="review-WP02-incorporate-lane-a")
    transition(mission, "WP02", "claimed", actor=IMPLEMENTER)
    transition(mission, "WP02", "in_progress", actor=IMPLEMENTER)
    checkout = scenario.lane_b_worktree
    from specify_cli.lanes.incorporate import incorporate_sibling, prepare_incorporation

    outcome = incorporate_sibling(checkout, prepare_incorporation(mission.repo, mission.slug, "WP02", sibling_lane))
    assert outcome.conflicted_paths == (POPUP,), outcome  # the conflict the auto-rebase hit
    (checkout / POPUP).write_text(RESOLVED_TEXT, encoding="utf-8")
    _git(checkout, "add", POPUP)
    _git(checkout, "commit", "-q", "--no-edit")
    approve(mission, "WP02", reference="review-WP02-after-incorporating-lane-a")

    second = _consolidate(scenario)
    second_flat = _flat(second)
    assert "lane-b is stale" not in second_flat, second_flat
    assert second.returncode == 0, second_flat
    assert "Reconciliation verified" in second_flat, second_flat
    assert _show(mission.repo, mission.target_branch, POPUP) == RESOLVED_TEXT


def test_refusal_without_a_lane_worktree_still_names_the_sibling(tmp_path: Path) -> None:
    """No worktree: no auto-rebase runs, and the refusal says so (FR-003, squad-3 F1); the sibling branch is still the source."""
    scenario = build_stale_sibling_mission(tmp_path)
    _git(scenario.mission.repo, "worktree", "remove", "--force", str(scenario.lane_b_worktree))

    result = _consolidate(scenario)

    flat = _flat(result)
    assert result.returncode != 0, flat
    assert "Lane lane-b has no lane checkout, so no in-run auto-rebase ran onto" in flat, flat
    assert "auto-rebase of lane lane-b" not in flat and "stopped:" not in flat, flat
    _assert_refusal_is_actionable(flat, scenario)
