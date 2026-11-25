"""DestroyedLaneError names the caller's own next step (#7806 review follow-up).

The allocator keeps its historical "re-run the implement command" wording; a
caller on another path (review) passes ``rerun_command`` so the remedy names the
command the operator actually ran.
"""

from __future__ import annotations

import pytest

from specify_cli.lanes.worktree_allocator import DestroyedLaneError

pytestmark = pytest.mark.fast

_BRANCH = "kitty/mission-demo-01ABCDEF-lane-a"


@pytest.mark.parametrize("tip_sha", [None, "0123456789abcdef0123456789abcdef01234567"])
def test_default_remedy_keeps_the_implement_wording(tip_sha: str | None) -> None:
    error = DestroyedLaneError(lane_id="lane-a", wp_id="WP01", branch_name=_BRANCH, tip_sha=tip_sha)

    assert "re-run the implement command for 'WP01'" in str(error)
    assert error.next_step.endswith("re-run the implement command for 'WP01'.")


@pytest.mark.parametrize("tip_sha", [None, "0123456789abcdef0123456789abcdef01234567"])
def test_rerun_command_replaces_the_implement_wording(tip_sha: str | None) -> None:
    error = DestroyedLaneError(
        lane_id="lane-a",
        wp_id="WP01",
        branch_name=_BRANCH,
        tip_sha=tip_sha,
        rerun_command="spec-kitty agent action review WP01",
    )

    assert "re-run `spec-kitty agent action review WP01`." in str(error)
    assert "implement command" not in str(error)
