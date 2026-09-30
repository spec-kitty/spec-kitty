"""Coordination-topology pin for the claim-commit base in ``materialize_worktree_topology`` (WP12, FR-025).

A coordination mission's repository-root (planning-artifact) WP has its claim
event committed on the COORDINATION branch, which is not an ancestor of the
repository root checkout's ``HEAD`` where the base is consumed. The topology
entry must therefore fail closed (``base_branch is None``, nothing counted
ahead) rather than report a coordination-branch SHA as the base.
"""

from __future__ import annotations

import subprocess

import pytest

from specify_cli.core.worktree_topology import materialize_worktree_topology
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.integration.coord_topology_fixture import CoordTopologyContext, coord_topology_mission

__all__ = ["coord_topology_mission"]
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(root: object, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def test_claim_committed_on_the_coordination_branch_gives_no_base(coord_topology_mission: CoordTopologyContext) -> None:
    ctx = coord_topology_mission
    wp_file = ctx.primary_feature_dir / "tasks" / "WP01.md"
    wp_file.write_text(
        wp_file.read_text(encoding="utf-8").replace("subtasks: []", "subtasks: []\nexecution_mode: planning_artifact\nowned_files: []"), encoding="utf-8"
    )
    _git(ctx.repo, "commit", "-qam", "WP01 is a planning artifact")
    coord_root = ctx.coord_feature_dir.parents[1]
    append_event(
        ctx.coord_feature_dir,
        StatusEvent(
            event_id="01CLAIMCOORDAAAAAAAAAAAAA1",
            mission_slug=ctx.slug,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-09-29T00:00:00+00:00",
            actor="tester",
            force=True,
            execution_mode="direct_repo",
        ),
    )
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-qm", "status: claim WP01 on the coordination branch")
    coord_sha = _git(coord_root, "rev-parse", "HEAD")

    entry = next(e for e in materialize_worktree_topology(ctx.repo, ctx.slug).entries if e.wp_id == "WP01")

    assert entry.resolution_kind == "repo_root"
    assert entry.base_branch != coord_sha, "a coordination-branch SHA was reported as the repository-root base"
    assert entry.base_branch is None
    assert entry.commits_ahead_of_base == 0
