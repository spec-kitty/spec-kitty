"""Red-first real-CLI reproduction: the FR-013 closed world must not REFUSE a
mixed lane whose first-parent history carries a DEPENDENCY lane's commits
(#5046 landing review BLOCKER).

``lanes/worktree_allocator.py`` merges a dependency lane into the dependent
lane without ``--no-ff``, so the dependency lane's WP commits fast-forward onto
the dependent lane's first-parent spine. Those commits lie in no window of the
dependent lane's OWN WPs; before the fix the closed world called them
``commit_outside_windows`` and REFUSEd every such mission.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.terminus.conftest import blob_present_at, build_coord_mission_mixed_lane_with_dependency, run_terminus

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_REFUSE_HEADER = "Reconciliation refused (fail-closed)"
_FAIL_HEADER = "Reconciliation FAILED"


def _collapse(text: str) -> str:
    return " ".join(text.replace("`", "").split())


def test_dependency_lane_commits_are_not_outside_windows(tmp_path: Path) -> None:
    mission = build_coord_mission_mixed_lane_with_dependency(tmp_path, canceled_leaks=False, mid8="01M5046E")
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert "outside every WP's recorded work window" not in flat, f"dependency-lane commits are not stragglers:\n{flat}"
    assert result.returncode == 0, f"a clean dependent mixed lane must consolidate:\n{flat}"
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp03.py") is True
    assert blob_present_at(mission.repo, mission.target_branch, "src/pkg/wp01.py") is True


def test_dependency_lane_with_leaked_canceled_content_fails_not_refuses(tmp_path: Path) -> None:
    mission = build_coord_mission_mixed_lane_with_dependency(tmp_path, canceled_leaks=True, mid8="01M5046F")
    pre_sha = mission.rev(mission.target_branch)
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    flat = _collapse(result.stdout + "\n" + result.stderr)
    assert result.returncode != 0
    assert _REFUSE_HEADER not in flat, f"must be the content FAIL, not a closed-world REFUSE:\n{flat}"
    assert _FAIL_HEADER in flat and "'src/pkg/wp02_new.py'" in flat, flat
    assert mission.rev(mission.target_branch) == pre_sha
