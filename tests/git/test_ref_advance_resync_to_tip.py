"""``resync_checkouts_to_tip``: bring a branch's checkouts back to its CURRENT tip, never move the ref (#5638).

Real-git tests over throwaway temp repositories; nothing is mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.coherence import CheckoutRole, ResidueContext
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    RefAdvanceError,
    advance_branch_ref,
    restore_branch_ref,
    resync_checkouts_to_tip,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_BRANCH = "coord"
_STATUS = "status.events.jsonl"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


def _repo_with_checkout(tmp_path: Path) -> tuple[Path, Path, str]:
    """A repo whose ``coord`` branch is checked out in a linked worktree; returns (repo, worktree, tip)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "--quiet", "-m", "base")
    worktree = tmp_path / "coord-wt"
    _git(repo, "worktree", "add", "-q", "-b", _BRANCH, str(worktree))
    (worktree / _STATUS).write_text("approved\ndone\n", encoding="utf-8")
    (worktree / "notes.md").write_text("notes\n", encoding="utf-8")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "--quiet", "-m", "done")
    return repo, worktree, _git(repo, "rev-parse", f"refs/heads/{_BRANCH}")


def _is_status(path: str) -> bool:
    return path.endswith(_STATUS)


def test_residue_only_drift_is_reset_to_the_tip_and_the_ref_stays(tmp_path: Path) -> None:
    repo, worktree, tip = _repo_with_checkout(tmp_path)
    (worktree / _STATUS).write_text("approved\n", encoding="utf-8")

    reset = resync_checkouts_to_tip(repo, _BRANCH, is_residue=_is_status)

    assert [p.resolve() for p in reset] == [worktree.resolve()]
    assert (worktree / _STATUS).read_text(encoding="utf-8") == "approved\ndone\n"
    assert _git(repo, "rev-parse", f"refs/heads/{_BRANCH}") == tip
    assert _git(worktree, "status", "--porcelain") == ""


def test_a_consistent_checkout_is_left_alone(tmp_path: Path) -> None:
    repo, _worktree, _tip = _repo_with_checkout(tmp_path)

    assert resync_checkouts_to_tip(repo, _BRANCH, is_residue=_is_status) == []


def test_a_non_residue_edit_refuses_and_nothing_is_reset(tmp_path: Path) -> None:
    repo, worktree, _tip = _repo_with_checkout(tmp_path)
    (worktree / _STATUS).write_text("approved\n", encoding="utf-8")
    (worktree / "notes.md").write_text("operator edit\n", encoding="utf-8")

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        resync_checkouts_to_tip(repo, _BRANCH, is_residue=_is_status)

    assert (worktree / "notes.md").read_text(encoding="utf-8") == "operator edit\n"
    assert (worktree / _STATUS).read_text(encoding="utf-8") == "approved\n"


def test_a_missing_branch_raises(tmp_path: Path) -> None:
    repo, _worktree, _tip = _repo_with_checkout(tmp_path)

    with pytest.raises(RefAdvanceError, match="no-such-branch"):
        resync_checkouts_to_tip(repo, "no-such-branch")


# --- WP02 (#5965 / #5966): context-aware disposability -------------------------------------

_SLUG = "m-01ABCDEF"
_OTHER = "other-01ZZZZZZ"


def _ctx(role: CheckoutRole = CheckoutRole.REPOSITORY_ROOT) -> ResidueContext:
    return ResidueContext(role, _SLUG, MissionTopology.COORD)


def _mission_repo_on_main(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    for key, value in (("user.email", "t@example.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    mission = repo / "kitty-specs" / _SLUG
    mission.mkdir(parents=True)
    (mission / "status.json").write_text("{}\n", encoding="utf-8")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "base")
    return repo


def test_context_and_is_residue_together_is_a_type_error(tmp_path: Path) -> None:
    repo, _worktree, _tip = _repo_with_checkout(tmp_path)

    with pytest.raises(TypeError, match="exactly one"):
        resync_checkouts_to_tip(repo, _BRANCH, is_residue=_is_status, context=_ctx())
    with pytest.raises(TypeError, match="exactly one"):
        advance_branch_ref(repo, _BRANCH, _git(repo, "rev-parse", "HEAD"), is_residue=_is_status, context=_ctx())
    with pytest.raises(TypeError, match="exactly one"):
        restore_branch_ref(repo, _BRANCH, "0" * 40, expected_current_sha="0" * 40, resync_checkouts=True, is_residue=_is_status, context=_ctx())


def test_a_coordination_checkouts_uncommitted_review_cycle_refuses_the_resync(tmp_path: Path) -> None:
    repo, worktree, _tip = _repo_with_checkout(tmp_path)
    review = worktree / "kitty-specs" / _SLUG / "tasks" / "WP01"
    review.mkdir(parents=True)
    (review / "review-cycle-1.md").write_text("feedback\n", encoding="utf-8")
    (worktree / _STATUS).write_text("approved\n", encoding="utf-8")

    # The worktree lives outside .worktrees, so it resolves to the strictest role.
    with pytest.raises(RefAdvanceDirtyWorktreeError):
        resync_checkouts_to_tip(repo, _BRANCH, context=_ctx())
    assert (review / "review-cycle-1.md").read_text(encoding="utf-8") == "feedback\n"


def test_the_repository_root_refuses_another_missions_traces(tmp_path: Path) -> None:
    repo = _mission_repo_on_main(tmp_path)
    other = repo / "kitty-specs" / _OTHER
    other.mkdir(parents=True)
    (other / "status.json").write_text("{}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "other mission")
    (other / "status.json").write_text('{"edited": true}\n', encoding="utf-8")

    with pytest.raises(RefAdvanceDirtyWorktreeError) as info:
        resync_checkouts_to_tip(repo, "main", context=_ctx())

    assert any(_OTHER in entry for entry in info.value.dirty_entries)
    assert (other / "status.json").read_text(encoding="utf-8") == '{"edited": true}\n'


def test_the_repository_root_cleans_its_own_stale_status_copy(tmp_path: Path) -> None:
    repo = _mission_repo_on_main(tmp_path)
    status = repo / "kitty-specs" / _SLUG / "status.json"
    status.write_text('{"stale": true}\n', encoding="utf-8")

    reset = resync_checkouts_to_tip(repo, "main", context=_ctx())

    assert [p.resolve() for p in reset] == [repo.resolve()]
    assert status.read_text(encoding="utf-8") == "{}\n"


def test_advance_with_context_judges_each_checkout_by_its_own_role(tmp_path: Path) -> None:
    repo = _mission_repo_on_main(tmp_path)
    status = repo / "kitty-specs" / _SLUG / "status.json"
    status.write_text('{"stale": true}\n', encoding="utf-8")
    _git(repo, "stash", "push", "--quiet")
    _git(repo, "checkout", "--quiet", "-b", "ahead")
    (repo / "a.txt").write_text("c\n", encoding="utf-8")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "--quiet", "-m", "ahead")
    ahead = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "--quiet", "main")
    status.write_text('{"stale": true}\n', encoding="utf-8")

    advance_branch_ref(repo, "main", ahead, context=_ctx())

    assert _git(repo, "rev-parse", "refs/heads/main") == ahead
    assert status.read_text(encoding="utf-8") == "{}\n"


def test_a_refusal_message_truncates_at_twenty_entries(tmp_path: Path) -> None:
    repo = _mission_repo_on_main(tmp_path)
    other = repo / "kitty-specs" / _OTHER
    other.mkdir(parents=True)
    for i in range(23):
        (other / f"f{i:02d}.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "other mission")
    for i in range(23):
        (other / f"f{i:02d}.md").write_text("edited\n", encoding="utf-8")

    with pytest.raises(RefAdvanceDirtyWorktreeError) as info:
        resync_checkouts_to_tip(repo, "main", context=_ctx())

    message = str(info.value)
    assert len(info.value.dirty_entries) == 23
    assert message.count(".md") == 20
    assert "... and 3 more" in message
