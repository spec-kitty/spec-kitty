"""#5571 -- committing the staged deletions of an interrupted consolidate must not ship a mission without its code.

A REAL ``spec-kitty consolidate`` is SIGKILLed in the window #1826 describes: the
mission (coordination) branch ref has been advanced by the first lane merge, but
the ``git reset --hard`` that refreshes the coordination worktree never ran. The
worktree then sits behind its own HEAD and the lane's files read as STAGED
DELETIONS. The operator follows the advice the CLI used to print ("Commit ...")
with a plain ``git commit`` in the coordination worktree, which records a revert
of the lane's code on the mission branch. The ancestry skip now sees
the lane as an ancestor, so ``consolidate --resume`` used to skip it, marked every
WP ``done`` and exited 0 with the code missing.

The approved-content presence axis is the backstop: the resumed run must refuse
with ``APPROVED_CONTENT_MISSING`` naming the WP whose content is gone, mark no WP
``done`` and restore the target to the pre-mutation snapshot.

Nothing is mocked and no deletion is hand-written (no ``git rm``): the kill is the
shared fault hook (``tests.terminus.approved_content_support.InterruptedConsolidate``)
that SIGKILLs the ``spec-kitty`` process right after the mission-branch ref advance
and before the coordination worktree's ``reset --hard``; the staged deletions are what
that kill leaves behind. Each negative has a same-fixture positive control (the
"revert" remedy instead of "commit").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.reducer import materialize_snapshot
from tests.terminus.approved_content_support import InterruptedConsolidate
from tests.terminus.conftest import CoordMission, blob_present_at
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

STRATEGIES = ("squash", "merge")
ERROR_CODE = "APPROVED_CONTENT_MISSING"
WP_PATHS = {"WP01": "src/pkg/wp01.py", "WP02": "src/pkg/wp02.py"}


class Interrupted(InterruptedConsolidate):
    """The shared interrupted-consolidate fixture (killed at the coordination resync), plus what the operator may do next."""

    def __init__(self, tmp_path: Path, strategy: str, mid8: str) -> None:
        super().__init__(tmp_path, "kill_coord", strategy, mid8=mid8)
        self.coord_wt = self.lagging

    def operator_commits_staged_deletions(self) -> None:
        """The advice the CLI used to print: record what ``git status`` shows."""
        git(self.coord_wt, "commit", "-qm", "operator: commit the staged changes")

    def operator_reverts_staged_deletions(self) -> None:
        """The correct remedy: discard the phantom staged deletions."""
        git(self.coord_wt, "reset", "--hard", "HEAD")


def wp_lanes(mission: CoordMission, ref: str, scratch: Path) -> dict[str, str]:
    """Each WP's lane in the status log as of *ref*, reduced in a directory under *scratch* (nothing is written to the repository)."""
    events = git_out(mission.repo, "show", f"{ref}:kitty-specs/{mission.slug}/status.events.jsonl")
    feature_dir = scratch / f"snap-{mission.mid8}-{ref.replace('/', '_')}"
    feature_dir.mkdir(parents=True)
    (feature_dir / "status.events.jsonl").write_text(events, encoding="utf-8")
    snapshot = materialize_snapshot(feature_dir)
    return {wp: str(state["lane"]) for wp, state in snapshot.work_packages.items()}


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_5571_committed_staged_deletions_make_resume_refuse(tmp_path: Path, strategy: str) -> None:
    run = Interrupted(tmp_path, strategy, mid8="01M55710")
    mission = run.mission
    run.operator_commits_staged_deletions()
    assert blob_present_at(mission.repo, mission.coord_branch, WP_PATHS["WP01"]) is False, "fixture precondition: the committed deletions removed WP01's code"

    rc, flat = run.resume()

    assert rc != 0, f"resume after the operator committed the staged deletions must refuse, got exit 0 ({strategy}):\n{flat}"
    assert ERROR_CODE in flat, f"expected {ERROR_CODE} in the refusal:\n{flat}"
    assert "WP01" in flat, f"the refusal must name the WP whose content is missing:\n{flat}"
    assert mission.rev(mission.target_branch) == run.pre_target, "target must be restored to the pre-mutation snapshot"
    assert not blob_present_at(mission.repo, mission.target_branch, WP_PATHS["WP01"])
    for ref in (mission.target_branch, mission.coord_branch):
        lanes = wp_lanes(mission, ref, tmp_path)
        assert "done" not in lanes.values(), f"no WP may be marked done on {ref}: {lanes}"


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_5571_control_reverting_the_staged_deletions_lands_all_code(tmp_path: Path, strategy: str) -> None:
    """Same fixture and interruption; the operator discards the staged deletions instead of committing them."""
    run = Interrupted(tmp_path, strategy, mid8="01M55711")
    mission = run.mission
    run.operator_reverts_staged_deletions()

    rc, flat = run.resume()

    assert rc == 0, f"resume after discarding the staged deletions must land the mission ({strategy}):\n{flat}"
    for wp, path in WP_PATHS.items():
        assert blob_present_at(mission.repo, mission.target_branch, path), f"{wp}'s approved code must be on the target"
