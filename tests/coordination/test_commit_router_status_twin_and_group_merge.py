"""Focused coverage for the #5513 remediation in the commit router.

Two seams change:

* ``_stage_artifacts_in_coord_worktree`` resolves a status log named by its
  PRIMARY path to its coordination twin when (and only when) the twin carries
  uncommitted content, committing it in place. It never copies the primary
  copy over the twin, and a clean twin stays skipped so a primary-only change
  still classifies as wrong-surface.
* ``_merge_group_results`` is unchanged: once the coord twin is committed, a
  coord group no longer reports ``unchanged`` for a dirty twin, so the caller's
  partition result stays authoritative.

The end-to-end invariant is pinned by
``test_commit_router_coord_only_dirty_status_log.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git import GitCommandError
from mission_runtime import MissionArtifactKind
from specify_cli.coordination.commit_router import (
    CommitRouterResult,
    _is_uncommitted_in_worktree,
    _merge_group_results,
    _stage_artifacts_in_coord_worktree,
)

pytestmark = [pytest.mark.git_repo]

_SLUG = "demo-01M5513A"
_STATUS_REL = Path("kitty-specs") / _SLUG / "status.events.jsonl"
_COMMITTED_ROW = '{"row": 1}\n'


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _repo_with_status_log(root: Path) -> Path:
    """A git repository holding one committed status log at ``_STATUS_REL``."""
    root.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@test.com")
    _git(root, "config", "user.name", "Test")
    log = root / _STATUS_REL
    log.parent.mkdir(parents=True)
    log.write_text(_COMMITTED_ROW, encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "baseline")
    return log


# ---------------------------------------------------------------------------
# _is_uncommitted_in_worktree
# ---------------------------------------------------------------------------


def test_uncommitted_probe_is_false_for_a_clean_tracked_file(tmp_path: Path) -> None:
    _repo_with_status_log(tmp_path / "wt")
    assert _is_uncommitted_in_worktree(tmp_path / "wt", _STATUS_REL) is False


def test_uncommitted_probe_is_true_for_a_modified_file(tmp_path: Path) -> None:
    log = _repo_with_status_log(tmp_path / "wt")
    log.write_text(_COMMITTED_ROW + '{"row": 2}\n', encoding="utf-8")
    assert _is_uncommitted_in_worktree(tmp_path / "wt", _STATUS_REL) is True


def test_uncommitted_probe_is_false_for_a_missing_file(tmp_path: Path) -> None:
    _repo_with_status_log(tmp_path / "wt")
    assert _is_uncommitted_in_worktree(tmp_path / "wt", Path("kitty-specs") / _SLUG / "status.json") is False


def test_uncommitted_probe_refuses_an_unreadable_status_instead_of_reading_clean(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    (plain / _STATUS_REL).parent.mkdir(parents=True)
    (plain / _STATUS_REL).write_text(_COMMITTED_ROW, encoding="utf-8")
    with pytest.raises(GitCommandError):
        _is_uncommitted_in_worktree(plain, _STATUS_REL)


# ---------------------------------------------------------------------------
# _stage_artifacts_in_coord_worktree: primary-path status log -> coord twin
# ---------------------------------------------------------------------------


def test_primary_path_status_log_resolves_to_its_dirty_coord_twin_without_copying(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    primary_log = _repo_with_status_log(repo_root)
    coord = tmp_path / "coord"
    twin = _repo_with_status_log(coord)
    twin_bytes = _COMMITTED_ROW + '{"row": "coord-only"}\n'
    twin.write_text(twin_bytes, encoding="utf-8")

    staged = _stage_artifacts_in_coord_worktree([primary_log], coord, repo_root)

    assert staged == [coord / _STATUS_REL]
    assert twin.read_text(encoding="utf-8") == twin_bytes, "the primary copy must never overwrite the coord twin"


def test_primary_path_status_log_with_a_clean_coord_twin_stays_skipped(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    primary_log = _repo_with_status_log(repo_root)
    primary_log.write_text(_COMMITTED_ROW + '{"row": "primary-only"}\n', encoding="utf-8")
    coord = tmp_path / "coord"
    _repo_with_status_log(coord)

    staged = _stage_artifacts_in_coord_worktree([primary_log], coord, repo_root)

    assert staged == [], "a clean twin has nothing to commit; the wrong-surface classifier must see an empty set"


def test_a_twin_named_both_ways_is_staged_once(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    primary_log = _repo_with_status_log(repo_root)
    coord = repo_root / ".worktrees" / f"{_SLUG}-coord"
    twin = _repo_with_status_log(coord)
    twin.write_text(_COMMITTED_ROW + '{"row": "coord-only"}\n', encoding="utf-8")

    staged = _stage_artifacts_in_coord_worktree([twin, primary_log], coord, repo_root)

    assert staged == [twin]


# ---------------------------------------------------------------------------
# _merge_group_results: caller-partition result stays authoritative
# ---------------------------------------------------------------------------

_PRIMARY_GROUP = (MissionArtifactKind.TASKS_INDEX, (Path("tasks.md"),))
_COORD_GROUP = (MissionArtifactKind.STATUS_STATE, (Path("status.events.jsonl"),))
_COMMITTED = CommitRouterResult(status="committed", placement_ref="main", commit_hash="abc", commit_hashes=(("main", "abc"),))
_UNCHANGED = CommitRouterResult(status="unchanged", placement_ref="kitty/coord", reason="no_op_already_committed")


@pytest.mark.unit
def test_merge_keeps_the_caller_partition_result_when_no_group_refused() -> None:
    merged = _merge_group_results([_COMMITTED, _UNCHANGED], [_PRIMARY_GROUP, _COORD_GROUP], MissionArtifactKind.TASKS_INDEX)

    assert merged.status == "committed"
    assert merged.commit_hash == "abc"
