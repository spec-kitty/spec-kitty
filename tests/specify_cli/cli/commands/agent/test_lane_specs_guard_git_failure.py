"""The kitty-specs/ lane-write guard fails closed when its git diff cannot be read.

Real-git tests (no git mocks), mission git-paths-are-data (#5392/#5400, FR-013):
``_list_wp_branch_mission_specs_changes`` must list exact paths (no ``.strip()``
mangling) and must refuse, never pass, when the merge-base diff is unreadable.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_runtime import ActionContextError
from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.cli.commands.agent.tasks import _list_wp_branch_mission_specs_changes
from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    LaneSpecsDiffUnreadableError,
    _check_kitty_specs_contamination,
)
from specify_cli.core.vcs.git import merge_base_changed_files, merge_base_changed_files_checked

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SPACED = "kitty-specs/x y/spec.md"
_TRAILING = "kitty-specs/m/notes.md "


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _lane_repo(tmp_path: Path, *paths: str) -> Path:
    """Repo on ``main`` with a ``lane`` branch that adds ``paths``; HEAD is ``lane``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("anchor\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "anchor")
    _git(repo, "checkout", "-q", "-b", "lane")
    for rel in paths:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("lane content\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "lane work")
    return repo


def test_spaced_and_trailing_space_paths_are_listed_exactly(tmp_path: Path) -> None:
    repo = _lane_repo(tmp_path, _SPACED, _TRAILING)

    assert sorted(_list_wp_branch_mission_specs_changes(repo, "main")) == sorted([_SPACED, _TRAILING])


def test_unresolvable_base_ref_refuses(tmp_path: Path) -> None:
    repo = _lane_repo(tmp_path, _SPACED)

    with pytest.raises(LaneSpecsDiffUnreadableError, match="could not be read"):
        _list_wp_branch_mission_specs_changes(repo, "no-such-base")


def test_contamination_check_turns_unreadable_diff_into_refusal_guidance(tmp_path: Path) -> None:
    repo = _lane_repo(tmp_path, _SPACED)

    guidance = _check_kitty_specs_contamination(
        worktree_path=repo,
        check_branch="no-such-base",
        feature_dir=tmp_path / "absent-feature-dir",
        wp_id="WP01",
        target_lane="for_review",
        list_wp_branch_specs_changes_for_guard=lambda **kw: _list_wp_branch_mission_specs_changes(**kw),
    )

    assert guidance is not None
    assert "could not be read" in guidance[0]
    assert "move-task WP01 --to for_review" in guidance[-1]


def _guard(repo: Path, feature_dir: Path, check_branch: str) -> list[str] | None:
    return _check_kitty_specs_contamination(
        worktree_path=repo,
        check_branch=check_branch,
        feature_dir=feature_dir,
        wp_id="WP01",
        target_lane="for_review",
        list_wp_branch_specs_changes_for_guard=lambda **kw: _list_wp_branch_mission_specs_changes(**kw),
    )


def test_deleted_planning_base_branch_refusal_names_the_ref_and_how_to_repoint_it(tmp_path: Path) -> None:
    """``planning_base_branch`` names a local branch that was deleted: no merge-base, refuse with the fix."""
    repo = _lane_repo(tmp_path, _SPACED)
    _git(repo, "branch", "planning")
    _git(repo, "branch", "-D", "planning")
    feature_dir = tmp_path / "mission"
    feature_dir.mkdir()
    (feature_dir / "meta.json").write_text(json.dumps({"planning_base_branch": "planning"}), encoding="utf-8")

    guidance = _guard(repo, feature_dir, check_branch="main")

    assert guidance is not None
    text = "\n".join(guidance)
    assert "Base ref tried: 'planning'" in text
    assert "`planning_base_branch`" in text
    assert str(feature_dir / "meta.json") in text
    assert "git branch planning <commit>" in text
    assert "--force" not in text
    assert guidance[-1] == "Then retry: spec-kitty agent tasks move-task WP01 --to for_review"


def test_missing_local_check_branch_refusal_names_the_fallback_ref(tmp_path: Path) -> None:
    """No meta.json: the guard falls back to the lane's base branch, which has no local ref."""
    repo = _lane_repo(tmp_path, _SPACED)

    guidance = _guard(repo, tmp_path / "absent-mission", check_branch="kitty/mission-gone")

    assert guidance is not None
    text = "\n".join(guidance)
    assert "Base ref tried: 'kitty/mission-gone' (the lane's base branch" in text
    assert "git branch kitty/mission-gone <commit>" in text
    assert "add `planning_base_branch`" in text


def test_owned_review_unreadable_diff_names_the_review_base_and_how_to_repoint_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Owned review: a review base the checkout cannot diff against refuses with the ref and the lanes.json fix."""
    repo = _lane_repo(tmp_path, "src/x.py")
    feature_dir = tmp_path / "mission"
    monkeypatch.setattr(move_task_module, "_mt_owned_file_patterns", lambda st: ("src/**",))
    st = SimpleNamespace(owned=SimpleNamespace(owned_root=repo), review_base_ref="deadbeef", feature_dir=feature_dir)

    with pytest.raises(ActionContextError) as excinfo:
        move_task_module._mt_require_owned_implementation(st)

    message = str(excinfo.value)
    assert "review base deadbeef" in message
    assert "`planning_commit_sha`" in message
    assert str(feature_dir / "lanes.json") in message
    assert str(repo) in message


class TestMergeBaseChangedFilesChecked:
    def test_success_returns_exact_paths(self, tmp_path: Path) -> None:
        repo = _lane_repo(tmp_path, _SPACED)

        assert merge_base_changed_files_checked(repo, "main") == (_SPACED,)

    def test_genuinely_empty_diff_is_an_empty_tuple_not_none(self, tmp_path: Path) -> None:
        repo = _lane_repo(tmp_path, _SPACED)

        assert merge_base_changed_files_checked(repo, "HEAD") == ()

    def test_unresolvable_base_is_none_and_wrapper_stays_empty(self, tmp_path: Path) -> None:
        repo = _lane_repo(tmp_path, _SPACED)

        assert merge_base_changed_files_checked(repo, "no-such-base") is None
        assert merge_base_changed_files(repo, "no-such-base") == ()

    def test_unrelated_histories_have_no_merge_base_and_fail_closed(self, tmp_path: Path) -> None:
        repo = _lane_repo(tmp_path, _SPACED)
        _git(repo, "checkout", "-q", "--orphan", "other")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "orphan root")

        assert merge_base_changed_files_checked(repo, "main") is None
        assert merge_base_changed_files(repo, "main") == ()
