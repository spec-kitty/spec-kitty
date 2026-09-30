"""Repro #5400 — consolidation must not delete an ignored file under a replaced directory.

The tracked directory ``src/store/`` (``default.txt``) is replaced, on the lane
and before approval, by the tracked file ``src/store``. Ignored
``src/store/local.txt`` is then created only in the target checkout. A real
``spec-kitty consolidate --mission`` must refuse that collision before the
target moves: nonzero exit naming the obstructing path, target SHA unchanged,
WP01 still approved, lane branch and worktree retained, local bytes intact.

Driven through the real CLI and real git. Nothing is mocked.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import lane_branch_name, mission_branch_name, worktree_path
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status import wp_snapshot_state
from tests.terminus.conftest import CoordMission, _approve_events, _now_iso, blob_present_at, git_rev, run_terminus
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import _git_out as git_out

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_TARGET = "develop"
_PARENT = "tracked parent\n"
_LOCAL = "operator local bytes\n"
_COLLAPSED = "collapsed\n"
_LOCAL_REL = "src/store/local.txt"
_PARENT_REL = "src/store/default.txt"


def _flat(stdout: str, stderr: str) -> str:
    return " ".join(f"{stdout}\n{stderr}".split())


def _object_type(repo: Path, ref: str, path: str) -> str:
    """``blob``, ``tree``, or ``""`` when *path* is absent from *ref*."""
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-t", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _wp_lane(feature_dir: Path) -> str:
    state = wp_snapshot_state(feature_dir, "WP01")
    assert state is not None, "WP01 has no reduced status; setup never reached a lane"
    return str(state["lane"])


def _prepare_tracked_store(tmp_path: Path) -> tuple[CoordMission, str, Path]:
    """One-WP lanes mission: tracked ``src/store/`` and the ignore rule exist before the lane."""
    mid8 = "01M5400A"
    mission_id = (mid8 + "0" * 26)[:26]
    slug = f"terminus-{mid8}"
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    mission_branch = mission_branch_name(slug, mission_id=mission_id)
    lane_branch = lane_branch_name(slug, "lane-a", target_branch=_TARGET)
    mission = CoordMission(
        repo=repo,
        home=home,
        feature_dir=repo / "kitty-specs" / slug,
        slug=slug,
        mission_id=mission_id,
        mid8=mid8,
        coord_branch=mission_branch,
        target_branch=_TARGET,
        lane_branches={"WP01": lane_branch},
    )

    repo.mkdir()
    git(repo, "init", "-qb", _TARGET)
    git(repo, "config", "user.email", "t@t.com")
    git(repo, "config", "user.name", "T")
    git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    (repo / ".gitignore").write_text(f".worktrees/\n{_LOCAL_REL}\n", encoding="utf-8")
    parent = repo / _PARENT_REL
    parent.parent.mkdir(parents=True)
    parent.write_text(_PARENT, encoding="utf-8")
    git(repo, "add", "--", "README.md", ".gitignore", _PARENT_REL)
    git(repo, "commit", "-qm", "track store directory and ignore local bytes")

    (mission.feature_dir / "tasks").mkdir(parents=True)
    (mission.feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": slug,
                "mission_id": mission_id,
                "mid8": mid8,
                "mission_number": None,
                "mission_type": "software-dev",
                "target_branch": _TARGET,
                "topology": "lanes",
                "purpose_tldr": "preserve ignored descendants",
                "purpose_context": "directory replaced by a file must not destroy ignored local bytes",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (mission.feature_dir / "tasks" / "WP01-work.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 work\n---\n# WP01\n",
        encoding="utf-8",
    )
    write_lanes_json(
        mission.feature_dir,
        LanesManifest(
            version=1,
            mission_slug=slug,
            mission_id=mission_id,
            mission_branch=mission_branch,
            target_branch=_TARGET,
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/store", "src/store/**"),
                    predicted_surfaces=("code",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at=_now_iso(),
            computed_from="5400-directory-collapse",
        ),
    )
    git(repo, "add", "--", str(mission.feature_dir.relative_to(repo)))
    git(repo, "commit", "-qm", f"chore({slug}): bootstrap lanes mission")
    git(repo, "branch", mission_branch)
    git(repo, "branch", lane_branch, mission_branch)
    return mission, lane_branch, worktree_path(repo, slug, lane_id="lane-a")


def _collapse_store_on_lane(mission: CoordMission, lane_branch: str) -> None:
    """Replace the tracked directory with a tracked file on the lane, before approval."""
    repo = mission.repo
    git(repo, "checkout", "-q", lane_branch)
    git(repo, "rm", "-qr", "--", "src/store")
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "store").write_text(_COLLAPSED, encoding="utf-8")
    git(repo, "add", "--", "src/store")
    git(repo, "commit", "-qm", "replace store directory with a file")
    git(repo, "checkout", "-q", mission.target_branch)


def _approve_wp01(mission: CoordMission) -> None:
    events = _approve_events(mission, "WP01")
    (mission.feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    git(mission.repo, "add", "--", str(mission.feature_dir.relative_to(mission.repo)))
    git(mission.repo, "commit", "-qm", "approve WP01")


def test_5400_consolidate_preserves_ignored_descendant_of_replaced_directory(tmp_path: Path) -> None:
    mission, lane_branch, worktree = _prepare_tracked_store(tmp_path)
    _collapse_store_on_lane(mission, lane_branch)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    git(mission.repo, "worktree", "add", str(worktree), lane_branch)
    _approve_wp01(mission)

    # Setup reached the collision this test exists for: WP01 is approved, the
    # lane carries the file that replaces the directory, and the target
    # checkout still has the directory.
    assert _wp_lane(mission.feature_dir) == "approved"
    lane_sha = git_rev(mission.repo, lane_branch)
    assert _object_type(mission.repo, lane_sha, "src/store") == "blob"
    assert not blob_present_at(mission.repo, lane_sha, _PARENT_REL)
    assert _object_type(mission.repo, mission.target_branch, "src/store") == "tree"
    assert blob_present_at(mission.repo, mission.target_branch, _PARENT_REL)
    assert (worktree / "src" / "store").is_file()

    local = mission.repo / _LOCAL_REL
    local.write_text(_LOCAL, encoding="utf-8")
    assert not (worktree / _LOCAL_REL).exists()
    target_before = git_rev(mission.repo, mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = _flat(result.stdout, result.stderr)

    assert result.returncode != 0, output
    assert _LOCAL_REL in output, output
    assert "would be overwritten" in output, output
    assert git_rev(mission.repo, mission.target_branch) == target_before
    assert git_rev(mission.repo, "HEAD") == target_before
    assert _wp_lane(mission.feature_dir) == "approved"
    assert git_rev(mission.repo, lane_branch) == lane_sha
    assert worktree.is_dir()
    assert lane_branch in git_out(mission.repo, "worktree", "list", "--porcelain")
    assert local.read_text(encoding="utf-8") == _LOCAL
    assert (mission.repo / _PARENT_REL).read_text(encoding="utf-8") == _PARENT
    assert (mission.repo / "src" / "store").is_dir()
    assert git_out(mission.repo, "stash", "list") == ""
