"""Repro #4997 Defect B — a merge-strategy "Already up to date" no-op must be adjudicated.

After the catastrophic "Commit" mis-remedy (the operator committed the phantom staged
deletions), the target carries a commit that DELETES the mission's content, yet the mission
branch is still an ancestor of the target. A resumed ``git merge <mission>`` is then
"Already up to date" — a no-op. Under the SQUASH strategy the FR-037 zero-diff adjudication
refuses this; under the MERGE strategy the no-op wrongly reported ``already_applied=False``
(``_merge_branch_into`` always returned ``changed=True``), so the guard never fired: every
WP was stamped ``done``, lanes/branch torn down, exit 0 — the target left with none of the
mission's code.

This drives the REAL ``spec-kitty merge --resume --strategy merge`` CLI and asserts the
no-op that would leave the target tree missing approved content REFUSES (``rc != 0``),
never reporting success / tearing the mission down. It is an END-TO-END fail-closed
regression for the #4997 mis-remedy scenario: two independent guards enforce it — the
merge-strategy no-op adjudication (Defect B, ``_merge_branch_into`` → the executor's
zero-diff guard) AND the reconciliation gate's closed-world/un-attributable axis. The
isolated red-first proof for the Defect-B code fix lives in
``tests/lanes/test_merge.py::test_merge_strategy_noop_*`` (unit level); this test guards
that the whole pipeline stays fail-closed regardless of which guard fires first.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import build_coord_mission, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out
from tests.terminus.test_repro_4997 import _interrupt_behind_own_head

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_merge_strategy_noop_refuses_when_target_tree_lost_mission_content(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M4997C")
    _interrupt_behind_own_head(mission, ["WP01", "WP02"])

    # The catastrophic mis-remedy: recover the checkout, then record a commit on the target
    # that DELETES the mission's integrated code. The mission branch stays an ancestor of
    # the target (reachability intact), but the target TREE no longer carries the content.
    git(mission.repo, "reset", "-q", "--hard", "HEAD")
    for wp in ("wp01", "wp02"):
        src = mission.repo / "src" / "pkg" / f"{wp}.py"
        if src.exists():
            git(mission.repo, "rm", "-q", str(src.relative_to(mission.repo)))
    git(mission.repo, "commit", "-q", "-m", "commit the phantom staged deletions (mis-remedy)")

    result = run_terminus(mission, ["merge", "--resume", "--strategy", "merge", "--yes"])

    assert result.returncode != 0, (
        f"a merge-strategy no-op that would leave the target tree missing approved content must REFUSE (rc != 0), got rc=0\nstdout:\n{result.stdout}"
    )
    # And it must NOT have torn the mission down as a success: the mission branch survives.
    branches = git_out(mission.repo, "branch", "--format=%(refname:short)")
    assert mission.coord_branch in branches, (
        f"the mission branch was torn down despite the no-op refusal — the merge reported false success (#4997 Defect B)\nbranches:\n{branches}"
    )
