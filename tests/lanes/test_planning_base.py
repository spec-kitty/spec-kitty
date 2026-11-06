"""Unit tests for the one planning-base resolver (#7209 directory anchor, #7210 WP task anchor)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.planning_base import mission_dir_pathspec, mission_wp_tasks_pathspec, resolve_finalize_planning_base, resolve_planning_base_commit

pytestmark = pytest.mark.git_repo

SLUG = "demo-mission"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, rel: str, message: str) -> str:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(message + "\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    return root


def test_wp_tasks_anchor_is_the_commit_before_the_first_wp_task_file(repo: Path) -> None:
    _commit(repo, "README.md", "init")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/README.md", "tasks readme")
    before_wps = _commit(repo, f"kitty-specs/{SLUG}/spec.md", "spec")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "add WP01")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP02-second.md", "add WP02")

    assert resolve_planning_base_commit(repo, "main", mission_wp_tasks_pathspec(SLUG)) == before_wps


def test_directory_anchor_is_the_commit_before_the_mission_directory(repo: Path) -> None:
    base = _commit(repo, "README.md", "init")
    _commit(repo, f"kitty-specs/{SLUG}/meta.json", "create mission")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "add WP01")

    assert resolve_planning_base_commit(repo, "main", mission_dir_pathspec(SLUG)) == base


def test_a_side_branch_cut_from_an_old_tip_does_not_widen_the_window(repo: Path) -> None:
    """First-parent: a WP file committed on an old side branch and merged later anchors at the merge."""
    old = _commit(repo, "README.md", "init")
    _git(repo, "checkout", "-q", "-b", "planning")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "add WP01 on a side branch")
    _git(repo, "checkout", "-q", "main")
    unrelated = _commit(repo, "src/unrelated.py", "unrelated work on main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge planning", "planning")

    base = resolve_planning_base_commit(repo, "main", mission_wp_tasks_pathspec(SLUG))

    assert base == unrelated
    assert base != old


def test_other_missions_files_are_not_matched(repo: Path) -> None:
    _commit(repo, "README.md", "init")
    _commit(repo, "kitty-specs/demo-mission-two/tasks/WP01-x.md", "other mission")

    assert resolve_planning_base_commit(repo, "main", mission_wp_tasks_pathspec(SLUG)) is None


def test_a_root_introducing_commit_is_its_own_base(repo: Path) -> None:
    root = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "root adds WP01")
    _commit(repo, "src/code.py", "more")

    assert resolve_planning_base_commit(repo, "main", mission_wp_tasks_pathspec(SLUG)) == root


def test_none_when_the_target_does_not_resolve(repo: Path) -> None:
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "root adds WP01")

    assert resolve_planning_base_commit(repo, "no-such-branch", mission_wp_tasks_pathspec(SLUG)) is None


def test_none_outside_a_git_repository(tmp_path: Path) -> None:
    assert resolve_planning_base_commit(tmp_path, "main", mission_wp_tasks_pathspec(SLUG)) is None


def _branch(repo: Path, name: str, at: str) -> None:
    _git(repo, "branch", name, at)


def test_finalize_base_is_refused_when_a_lane_branch_does_not_contain_it(repo: Path) -> None:
    """A base the lane lacks reads the target's own content as the lane's implementation (#7210)."""
    cut = _commit(repo, "src/alpha.py", "init")
    _branch(repo, code_lane_branch_name(SLUG, "lane-a"), cut)
    _commit(repo, "src/alpha.py", "unrelated change on the target")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "add WP01")

    assert resolve_finalize_planning_base(repo, "main", SLUG) is None


def test_finalize_base_stands_when_every_lane_branch_contains_it(repo: Path) -> None:
    """The control: the same resolver, with a lane cut after the tasks reached the target."""
    base = _commit(repo, "README.md", "init")
    tasks = _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "add WP01")
    _branch(repo, code_lane_branch_name(SLUG, "lane-a"), tasks)

    assert resolve_finalize_planning_base(repo, "main", SLUG) == base


def test_a_shallow_repository_has_no_derivable_base(repo: Path, tmp_path: Path) -> None:
    """A shallow boundary has no parents, so without this check it would pass as a root commit."""
    _commit(repo, "README.md", "init")
    _commit(repo, f"kitty-specs/{SLUG}/tasks/WP01-first.md", "add WP01")
    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "-q", "--depth", "1", repo.as_uri(), shallow.as_posix())

    assert resolve_planning_base_commit(shallow, "main", mission_wp_tasks_pathspec(SLUG)) is None
