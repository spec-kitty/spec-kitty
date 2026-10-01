"""Consolidation must never overwrite or delete an ignored local file in the target checkout.

Two end-to-end scenarios, each driven through the real ``spec-kitty consolidate
--mission`` CLI and real git (nothing is mocked). Provenance: #5392/#5400.

* An ignored file whose path git quotes (``src/local data/notes.txt``) collides
  with a path the lane force-adds as tracked. ``git status --porcelain`` prints the
  ignored directory quoted, so a text comparison against ``ls-tree`` never matched.
* An ignored descendant (``src/store/local.txt``) of a tracked directory that the
  lane replaces with a file.

Both must refuse before the target moves: nonzero exit naming the obstructing
path, target SHA unchanged, WP01 still approved, lane branch and worktree
retained, local bytes intact.
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

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET = "develop"
_LOCAL = "operator local bytes\n"

# Quoted-path scenario.
_INCOMING = "tracked on the lane\n"
_QUOTED_DIR = "src/local data"
_QUOTED_REL = "src/local data/notes.txt"

# Replaced-directory scenario.
_PARENT = "tracked parent\n"
_COLLAPSED = "collapsed\n"
_STORE_LOCAL_REL = "src/store/local.txt"
_STORE_PARENT_REL = "src/store/default.txt"


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


def _prepare_mission(
    tmp_path: Path,
    *,
    mid8: str,
    gitignore: str,
    tracked: dict[str, str],
    write_scope: tuple[str, ...],
    purpose_tldr: str,
) -> tuple[CoordMission, str, Path]:
    """One-WP lanes mission: *tracked* files and the ignore rules exist before the lane."""
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
    (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
    for rel, content in tracked.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", "--", "README.md", ".gitignore", *tracked)
    git(repo, "commit", "-qm", "track base files and ignore local bytes")

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
                "purpose_tldr": purpose_tldr,
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
                    write_scope=write_scope,
                    predicted_surfaces=("code",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at=_now_iso(),
            computed_from="preserve-local-files",
        ),
    )
    git(repo, "add", "--", str(mission.feature_dir.relative_to(repo)))
    git(repo, "commit", "-qm", f"chore({slug}): bootstrap lanes mission")
    git(repo, "branch", mission_branch)
    git(repo, "branch", lane_branch, mission_branch)
    return mission, lane_branch, worktree_path(repo, slug, lane_id="lane-a")


def _approve_wp01(mission: CoordMission) -> None:
    events = _approve_events(mission, "WP01")
    (mission.feature_dir / "status.events.jsonl").write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )
    git(mission.repo, "add", "--", str(mission.feature_dir.relative_to(mission.repo)))
    git(mission.repo, "commit", "-qm", "approve WP01")


def _add_lane_worktree_and_approve(mission: CoordMission, lane_branch: str, worktree: Path) -> None:
    worktree.parent.mkdir(parents=True, exist_ok=True)
    git(mission.repo, "worktree", "add", str(worktree), lane_branch)
    _approve_wp01(mission)


def test_consolidate_preserves_ignored_file_with_quoted_path(tmp_path: Path) -> None:
    # A tracked sibling keeps ``src/`` itself from collapsing into one ``!! src/`` entry.
    mission, lane_branch, worktree = _prepare_mission(
        tmp_path,
        mid8="01M5392A",
        gitignore=f".worktrees/\n{_QUOTED_DIR}/\n",
        tracked={"src/README.md": "src\n"},
        write_scope=(_QUOTED_DIR, f"{_QUOTED_DIR}/**"),
        purpose_tldr="preserve ignored files with quoted paths",
    )
    repo = mission.repo
    # Force-add a tracked file inside the ignored directory on the lane, before approval.
    git(repo, "checkout", "-q", lane_branch)
    incoming = repo / _QUOTED_REL
    incoming.parent.mkdir(parents=True, exist_ok=True)
    incoming.write_text(_INCOMING, encoding="utf-8")
    git(repo, "add", "-f", "--", _QUOTED_REL)
    git(repo, "commit", "-qm", "track notes inside the ignored directory")
    git(repo, "checkout", "-q", mission.target_branch)
    _add_lane_worktree_and_approve(mission, lane_branch, worktree)

    # Setup reached the collision: WP01 is approved, the lane tracks the file,
    # the target does not, and git prints the ignored directory quoted.
    assert _wp_lane(mission.feature_dir) == "approved"
    lane_sha = git_rev(repo, lane_branch)
    assert blob_present_at(repo, lane_sha, _QUOTED_REL)
    assert not blob_present_at(repo, mission.target_branch, _QUOTED_REL)
    local = repo / _QUOTED_REL
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(_LOCAL, encoding="utf-8")
    assert '!! "src/local data/"' in git_out(repo, "status", "--porcelain", "--ignored")
    target_before = git_rev(repo, mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = _flat(result.stdout, result.stderr)

    assert result.returncode != 0, output
    assert _QUOTED_DIR in output, output
    assert "would be overwritten" in output, output
    assert git_rev(repo, mission.target_branch) == target_before
    assert git_rev(repo, "HEAD") == target_before
    assert _wp_lane(mission.feature_dir) == "approved"
    assert git_rev(repo, lane_branch) == lane_sha
    assert worktree.is_dir()
    assert local.read_text(encoding="utf-8") == _LOCAL
    assert git_out(repo, "stash", "list") == ""


def test_consolidate_preserves_ignored_descendant_of_replaced_directory(tmp_path: Path) -> None:
    mission, lane_branch, worktree = _prepare_mission(
        tmp_path,
        mid8="01M5400A",
        gitignore=f".worktrees/\n{_STORE_LOCAL_REL}\n",
        tracked={_STORE_PARENT_REL: _PARENT},
        write_scope=("src/store", "src/store/**"),
        purpose_tldr="preserve ignored descendants",
    )
    repo = mission.repo
    # Replace the tracked directory with a tracked file on the lane, before approval.
    git(repo, "checkout", "-q", lane_branch)
    git(repo, "rm", "-qr", "--", "src/store")
    (repo / "src").mkdir(parents=True, exist_ok=True)
    (repo / "src" / "store").write_text(_COLLAPSED, encoding="utf-8")
    git(repo, "add", "--", "src/store")
    git(repo, "commit", "-qm", "replace store directory with a file")
    git(repo, "checkout", "-q", mission.target_branch)
    _add_lane_worktree_and_approve(mission, lane_branch, worktree)

    # Setup reached the collision: WP01 is approved, the lane carries the file
    # that replaces the directory, and the target checkout still has the directory.
    assert _wp_lane(mission.feature_dir) == "approved"
    lane_sha = git_rev(repo, lane_branch)
    assert _object_type(repo, lane_sha, "src/store") == "blob"
    assert not blob_present_at(repo, lane_sha, _STORE_PARENT_REL)
    assert _object_type(repo, mission.target_branch, "src/store") == "tree"
    assert blob_present_at(repo, mission.target_branch, _STORE_PARENT_REL)
    assert (worktree / "src" / "store").is_file()

    local = repo / _STORE_LOCAL_REL
    local.write_text(_LOCAL, encoding="utf-8")
    assert not (worktree / _STORE_LOCAL_REL).exists()
    target_before = git_rev(repo, mission.target_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])
    output = _flat(result.stdout, result.stderr)

    assert result.returncode != 0, output
    assert _STORE_LOCAL_REL in output, output
    assert "would be overwritten" in output, output
    assert git_rev(repo, mission.target_branch) == target_before
    assert git_rev(repo, "HEAD") == target_before
    assert _wp_lane(mission.feature_dir) == "approved"
    assert git_rev(repo, lane_branch) == lane_sha
    assert worktree.is_dir()
    assert lane_branch in git_out(repo, "worktree", "list", "--porcelain")
    assert local.read_text(encoding="utf-8") == _LOCAL
    assert (repo / _STORE_PARENT_REL).read_text(encoding="utf-8") == _PARENT
    assert (repo / "src" / "store").is_dir()
    assert git_out(repo, "stash", "list") == ""
