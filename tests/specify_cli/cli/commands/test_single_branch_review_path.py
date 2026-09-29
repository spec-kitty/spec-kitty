"""Review path for a single_branch repo-root WP (#5100 WP04 T020b).

Drives the REAL production seams ``review_resolve_wp_and_lane_gate`` (the
review claim/gate resolver, ``workflow_executor.py``) and
``_prepare_review_workspace`` (the ``-b`` worktree-creation step,
``workflow.py``) in the SAME sequence ``review()`` calls them -- covering:

* a repo-root-lane WP's review creates no ``.worktrees/`` entry;
* an unmigrated single_branch mission (``lanes.json`` still has a code lane)
  raises ``SINGLE_BRANCH_CODE_LANES_UNMIGRATED`` before any worktree work.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from tests.utils import _seed_canonical_wp_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01REVIEWPATHMISSION0000001"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "trunk")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, mission_slug: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": mission_slug,
                "slug": mission_slug,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "trunk",
                "topology": "single_branch",
                "created_at": "2026-09-28T00:00:00+00:00",
                "friendly_name": mission_slug,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_code_wp(feature_dir: Path, wp_id: str) -> None:
    lines = [
        "---",
        f"work_package_id: {wp_id}",
        "title: Code change",
        "dependencies: []",
        "execution_mode: code_change",
        "owned_files:",
        "- src/**",
        "---",
        "",
        "Body.",
        "",
    ]
    (feature_dir / "tasks" / f"{wp_id}-test.md").write_text("\n".join(lines), encoding="utf-8")


def _repo_root_manifest(mission_slug: str, wp_id: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=_MISSION_ID,
        mission_branch="",
        target_branch="trunk",
        lanes=[
            ExecutionLane(
                lane_id=PLANNING_LANE_ID,
                wp_ids=(wp_id,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )


def _unmigrated_code_lane_manifest(mission_slug: str, wp_id: str) -> LanesManifest:
    """A single_branch mission whose manifest was never re-stamped: WP01
    still sits on a real code lane (Invariant T-1 violation)."""
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=_MISSION_ID,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="trunk",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(wp_id,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-09-28T00:00:00Z",
        computed_from="test",
    )


def _build_mission(repo: Path, mission_slug: str, manifest: LanesManifest, wp_id: str = "WP01") -> Path:
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(feature_dir, mission_slug)
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    _write_code_wp(feature_dir, wp_id)
    write_lanes_json(feature_dir, manifest)
    _seed_canonical_wp_state(repo, mission_slug, wp_id, "for_review", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T01:00:00Z")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", f"planning+status: seed {mission_slug}")
    return feature_dir


def test_review_of_repo_root_wp_creates_no_worktree(tmp_path: Path) -> None:
    """Characterization (review cycle-1 nit 5): asserts the intended
    steady-state outcome of resolving a repo-root-lane WP for review, not a
    specific branch this WP's own guard added -- ``test_unmigrated_single_
    branch_review_raises`` below is the discriminating control for the T020b
    refusal this file's other coverage targets."""
    from specify_cli.cli.commands.agent.workflow import _prepare_review_workspace
    from specify_cli.cli.commands.agent.workflow_executor import review_resolve_wp_and_lane_gate

    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "review-repo-root"
    _build_mission(repo, mission_slug, _repo_root_manifest(mission_slug, "WP01"))

    ctx = review_resolve_wp_and_lane_gate(repo, repo, mission_slug, "WP01")
    workspace = _prepare_review_workspace(ctx.review_workspace, repo, "WP01", "claude")

    assert workspace.resolution_kind == "repo_root"
    assert workspace.worktree_path == repo
    assert not (repo / ".worktrees").exists() or not any((repo / ".worktrees").iterdir())


def test_unmigrated_single_branch_review_raises(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.workflow_executor import review_resolve_wp_and_lane_gate

    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "review-unmigrated"
    _build_mission(repo, mission_slug, _unmigrated_code_lane_manifest(mission_slug, "WP01"))

    with pytest.raises(typer.Exit):
        review_resolve_wp_and_lane_gate(repo, repo, mission_slug, "WP01")


def test_migrated_lanes_topology_review_control_still_creates_worktree(tmp_path: Path) -> None:
    """Control: an ordinary (non-single_branch) code-lane WP is unaffected
    by the unmigrated-single_branch guard and still gets a real worktree."""
    from specify_cli.cli.commands.agent.workflow import _prepare_review_workspace
    from specify_cli.cli.commands.agent.workflow_executor import review_resolve_wp_and_lane_gate

    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "review-lanes-control"
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": mission_slug,
                "slug": mission_slug,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "trunk",
                "topology": "lanes",
                "created_at": "2026-09-28T00:00:00+00:00",
                "friendly_name": mission_slug,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    _write_code_wp(feature_dir, "WP01")
    write_lanes_json(feature_dir, _unmigrated_code_lane_manifest(mission_slug, "WP01"))
    _seed_canonical_wp_state(repo, mission_slug, "WP01", "for_review", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T01:00:00Z")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed lanes-topology control")

    ctx = review_resolve_wp_and_lane_gate(repo, repo, mission_slug, "WP01")
    workspace = _prepare_review_workspace(ctx.review_workspace, repo, "WP01", "claude")

    assert workspace.resolution_kind == "lane_workspace"
    assert (repo / ".worktrees" / f"{mission_slug}-lane-a").exists()
