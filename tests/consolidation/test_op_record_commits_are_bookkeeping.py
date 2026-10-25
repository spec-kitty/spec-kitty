"""An Op record committed on a lane after approval is not post-approval content (#6564).

Since #6564 an Op opened and closed in a lane worktree is committed on the lane
branch. The approval-stamp bound (``approved_bound.content_commits``) must read
that commit as bookkeeping through the gate's own ``_is_bookkeeping``, so it
never refuses ``LANE_MOVED_AFTER_APPROVAL``; a real file in the same position
still counts.
"""

from __future__ import annotations

import functools
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.consolidation.approved_bound import content_commits
from specify_cli.consolidation.reconciliation import _is_bookkeeping
from specify_cli.invocation.executor import ProfileInvocationExecutor
from tests.specify_cli.invocation._op_git import run_git, track_op_record_on_current_branch

pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]

PROFILES = Path(__file__).parents[1] / "specify_cli" / "invocation" / "fixtures" / "profiles"
SLUG = "demo-mission"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"


@pytest.fixture
def lane(tmp_path: Path) -> tuple[Path, Path]:
    primary = tmp_path / "primary"
    profiles_dir = primary / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in PROFILES.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    run_git(primary, "init", "-b", "main")
    run_git(primary, "config", "user.email", "t@example.com")
    run_git(primary, "config", "user.name", "T")
    run_git(primary, "add", ".kittify")
    run_git(primary, "commit", "-m", "init")
    track_op_record_on_current_branch(primary)
    lane_root = tmp_path / "lane"
    run_git(primary, "worktree", "add", "-b", f"kitty/mission-{SLUG}-lane-a", str(lane_root))
    return primary, lane_root.resolve()


def _bookkeeping() -> functools.partial[bool]:
    return functools.partial(_is_bookkeeping, mission_slug=SLUG, planning_prefix=f"kitty-specs/{SLUG}")


def test_op_record_commit_on_a_lane_is_not_content(lane: tuple[Path, Path]) -> None:
    primary, lane_root = lane
    stamp = run_git(lane_root, "rev-parse", "HEAD")
    executor = ProfileInvocationExecutor(primary, record_root=lane_root)
    with patch("specify_cli.invocation.executor.build_charter_context", return_value=_COMPACT_CTX):
        invocation_id = executor.invoke("review the work package", profile_hint="implementer-fixture").invocation_id
    executor.complete_invocation(invocation_id=invocation_id, outcome="done", closed_by="agent")
    assert executor.last_op_commit is not None and executor.last_op_commit.committed

    commits = run_git(lane_root, "rev-list", f"{stamp}..HEAD").splitlines()

    assert len(commits) == 1
    assert content_commits(lane_root, commits, _bookkeeping()) == []


def test_a_real_file_after_approval_is_still_content(lane: tuple[Path, Path]) -> None:
    _, lane_root = lane
    stamp = run_git(lane_root, "rev-parse", "HEAD")
    (lane_root / "app.py").write_text("print('late')\n", encoding="utf-8")
    run_git(lane_root, "add", "app.py")
    run_git(lane_root, "commit", "-m", "late change")

    commits = run_git(lane_root, "rev-list", f"{stamp}..HEAD").splitlines()

    assert content_commits(lane_root, commits, _bookkeeping()) == [(commits[0], "app.py")]
