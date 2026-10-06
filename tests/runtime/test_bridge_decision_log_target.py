"""``resolve_commit_target`` -- the pure commit-target selection (T019, NFR-003).

It lives in ``runtime_bridge_decision_log`` beside its only caller,
``_wrap_with_decision_git_log`` (moved there from ``runtime_bridge_io`` by
#2560 so the io seam no longer depends on the decision-log module). It is a
pure function: no disk I/O, so the candidate worktree path need not exist.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next.runtime_bridge_decision_log import DecisionGitLogUnavailable, resolve_commit_target

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_resolve_commit_target_non_coord_topology_lands_on_repo_root(tmp_path: Path) -> None:
    mid8, worktree_root, target = resolve_commit_target(
        coord_routing_topology=False,
        mission_slug="042-mission",
        mission_id="01HULIDXXXXXXXXXXXXXXXXXXX",
        coordination_branch="kitty/mission-042-mission",
        repo_root=tmp_path,
    )
    assert worktree_root == tmp_path
    assert target.ref == "kitty/mission-042-mission"
    assert mid8 == "01HULIDX"


def test_resolve_commit_target_coord_topology_computes_candidate_worktree_path(tmp_path: Path) -> None:
    mission_id = "01HULIDXXXXXXXXXXXXXXXXXXX"
    mid8, worktree_root_candidate, target = resolve_commit_target(
        coord_routing_topology=True,
        mission_slug="042-mission",
        mission_id=mission_id,
        coordination_branch="kitty/mission-042-mission-01hulidx-coord",
        repo_root=tmp_path,
    )
    assert mid8 == mission_id[:8]
    assert worktree_root_candidate == tmp_path / ".worktrees" / f"042-mission-{mid8}-coord"
    assert target.ref == "kitty/mission-042-mission-01hulidx-coord"
    # No disk I/O performed: the candidate path need not exist on disk.
    assert not worktree_root_candidate.exists()


def test_resolve_commit_target_raises_when_coord_topology_has_no_resolvable_mid8(tmp_path: Path) -> None:
    with pytest.raises(DecisionGitLogUnavailable):
        resolve_commit_target(
            coord_routing_topology=True,
            mission_slug="bare-slug-no-tail",
            mission_id=None,
            coordination_branch="kitty/mission-bare-slug-no-tail",
            repo_root=tmp_path,
        )
