"""T034 (coord-artifact-single-home-01M3V4BE, D6 "divergence model").

Table-driven coverage over REAL temporary git repositories for
``is_expected_coordination_divergence`` -- the one predicate shared by
``ensure_coordination_branch`` (create) and the doctor staleness finding
(T035), so neither re-derives "is this coordination branch ahead of target
BY DESIGN" (C-001 / DIRECTIVE_044).

Also covers ``ensure_coordination_branch`` driven directly against an
EXISTING coordination branch (post-tasks squad R-M7): the expected relation
lets a reuse through with no raise, and a genuinely diverged branch still
raises ``CoordinationBranchDiverged``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import mission_dir_name, resolve_mid8
from specify_cli.missions._create import (
    CoordinationBranchDiverged,
    coordination_branch_name,
    ensure_coordination_branch,
    is_expected_coordination_divergence,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_TARGET_BRANCH = "main"
# A syntactically-real-shaped ULID (Crockford base32) so ``resolve_mid8``
# derives a mid8 the same way production create does -- never a hand-picked
# ad-hoc string.
_MISSION_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
_MID8 = resolve_mid8("", mission_id=_MISSION_ID)
_MISSION_DIR = mission_dir_name("demo", mid8=_MID8)
_COORD_BRANCH = coordination_branch_name(_MISSION_DIR, _MISSION_ID)

_OTHER_MISSION_ID = "01BXYZ0000000000000000000"
_OTHER_MID8 = resolve_mid8("", mission_id=_OTHER_MISSION_ID)
_OTHER_MISSION_DIR = mission_dir_name("other", mid8=_OTHER_MID8)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", _TARGET_BRANCH)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    return repo


def _commit_file(repo: Path, relpath: str, content: str, message: str) -> str:
    path = repo / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", relpath)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _fork_coord_branch(repo: Path) -> None:
    _git(repo, "branch", _COORD_BRANCH, _TARGET_BRANCH)


def _expected(repo: Path) -> bool:
    return is_expected_coordination_divergence(
        repo,
        coordination_branch=_COORD_BRANCH,
        target_branch=_TARGET_BRANCH,
        mission_dir_name=_MISSION_DIR,
    )


# ---------------------------------------------------------------------------
# Table-driven predicate coverage
# ---------------------------------------------------------------------------


def test_coordination_only_commits_are_expected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)
    _git(repo, "checkout", _COORD_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/status.events.jsonl", "{}\n", "seed status log")
    _git(repo, "checkout", _TARGET_BRANCH)

    assert _expected(repo)


def test_coordination_commit_touching_spec_md_is_not_expected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)
    _git(repo, "checkout", _COORD_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/spec.md", "# Spec\n", "leak a PRIMARY file onto coord")
    _git(repo, "checkout", _TARGET_BRANCH)

    assert not _expected(repo)


def test_coordination_commit_touching_another_missions_paths_is_not_expected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)
    _git(repo, "checkout", _COORD_BRANCH)
    _commit_file(repo, f"kitty-specs/{_OTHER_MISSION_DIR}/status.events.jsonl", "{}\n", "wrong mission's log")
    _git(repo, "checkout", _TARGET_BRANCH)

    assert not _expected(repo)


def test_target_commit_touching_missions_status_log_is_not_expected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)
    _git(repo, "checkout", _COORD_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/status.events.jsonl", "{}\n", "seed status log")
    _git(repo, "checkout", _TARGET_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/status.events.jsonl", '{"bad": true}\n', "target touches the mission's status log too")

    assert not _expected(repo)


def test_target_ahead_with_unrelated_commits_is_still_expected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)
    _git(repo, "checkout", _COORD_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/status.events.jsonl", "{}\n", "seed status log")
    _git(repo, "checkout", _TARGET_BRANCH)
    _commit_file(repo, "README.md", "more\n", "unrelated target progress")

    assert _expected(repo)


def test_identical_tips_are_trivially_expected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)

    assert _expected(repo)


def test_unrelated_histories_fail_toward_reporting(tmp_path: Path) -> None:
    """A missing merge-base (e.g. a shallow clone) is NOT expected -- fail toward reporting."""
    repo = _init_repo(tmp_path)
    _git(repo, "checkout", "--orphan", _COORD_BRANCH)
    _git(repo, "rm", "-rf", "--cached", ".")
    for leftover in repo.glob("*"):
        if leftover.name != ".git":
            leftover.unlink()
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/status.events.jsonl", "{}\n", "orphan history seed")
    _git(repo, "checkout", _TARGET_BRANCH)

    assert not _expected(repo)


# ---------------------------------------------------------------------------
# ``ensure_coordination_branch`` driven directly (post-tasks squad R-M7)
# ---------------------------------------------------------------------------


def test_ensure_coordination_branch_accepts_expected_divergence(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)
    _git(repo, "checkout", _COORD_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/status.events.jsonl", "{}\n", "seed status log")
    _git(repo, "checkout", _TARGET_BRANCH)

    result = ensure_coordination_branch(
        repo_root=repo,
        mission_slug=_MISSION_DIR,
        mission_id=_MISSION_ID,
        target_branch=_TARGET_BRANCH,
    )
    assert result.branch_name == _COORD_BRANCH
    assert result.created is False
    assert _git(repo, "rev-parse", _COORD_BRANCH).stdout.strip() != _git(repo, "rev-parse", _TARGET_BRANCH).stdout.strip()


def test_ensure_coordination_branch_still_raises_for_genuine_divergence(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)
    _git(repo, "checkout", _COORD_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/spec.md", "# Spec\n", "leak a PRIMARY file onto coord")
    _git(repo, "checkout", _TARGET_BRANCH)

    with pytest.raises(CoordinationBranchDiverged):
        ensure_coordination_branch(
            repo_root=repo,
            mission_slug=_MISSION_DIR,
            mission_id=_MISSION_ID,
            target_branch=_TARGET_BRANCH,
        )


def test_ensure_coordination_branch_raises_when_target_touches_coord_paths(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _fork_coord_branch(repo)
    _git(repo, "checkout", _COORD_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/status.events.jsonl", "{}\n", "seed status log")
    _git(repo, "checkout", _TARGET_BRANCH)
    _commit_file(repo, f"kitty-specs/{_MISSION_DIR}/status.events.jsonl", '{"bad": true}\n', "target touches the mission's status log too")

    with pytest.raises(CoordinationBranchDiverged):
        ensure_coordination_branch(
            repo_root=repo,
            mission_slug=_MISSION_DIR,
            mission_id=_MISSION_ID,
            target_branch=_TARGET_BRANCH,
        )


# ---------------------------------------------------------------------------
# Fail-closed git-probe-failure branches (NFR-003: a focused test per helper)
# ---------------------------------------------------------------------------


def test_rev_list_returns_none_on_git_failure(tmp_path: Path) -> None:
    from specify_cli.missions._create import _rev_list

    repo = _init_repo(tmp_path)
    assert _rev_list(repo, "not-a-real-ref..also-not-real") is None


def test_changed_paths_for_commit_returns_none_on_git_failure(tmp_path: Path) -> None:
    from specify_cli.missions._create import _changed_paths_for_commit

    repo = _init_repo(tmp_path)
    assert _changed_paths_for_commit(repo, "0000000000000000000000000000000000000") is None


def test_commits_all_touch_only_coord_paths_fails_closed_on_unreadable_range(tmp_path: Path) -> None:
    """An unreadable commit range is NOT "all coord-only" -- fail toward reporting."""
    from specify_cli.missions._create import _commits_all_touch_only_coord_paths

    repo = _init_repo(tmp_path)
    assert _commits_all_touch_only_coord_paths(repo, "not-a-real-ref..also-not-real", mission_dir_name=_MISSION_DIR) is False


def test_commits_touch_any_coord_path_fails_closed_on_unreadable_range(tmp_path: Path) -> None:
    """An unreadable commit range IS treated as "touches" -- fail toward reporting,
    never a vacuous pass of the divergence check."""
    from specify_cli.missions._create import _commits_touch_any_coord_path

    repo = _init_repo(tmp_path)
    assert _commits_touch_any_coord_path(repo, "not-a-real-ref..also-not-real", mission_dir_name=_MISSION_DIR) is True


def test_merge_base_or_none_returns_none_for_unrelated_refs(tmp_path: Path) -> None:
    from specify_cli.missions._create import _merge_base_or_none

    repo = _init_repo(tmp_path)
    assert _merge_base_or_none(repo, "not-a-real-ref", _TARGET_BRANCH) is None
