"""``restore_branch_ref(resync_checkouts=True)`` on REAL temp git repos (WP02 / T007).

No git mocking: every scenario builds a real repository (plus a linked
worktree) and asserts HEAD == index == working tree after the restore.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests.residue_predicate import residue_when
from specify_cli.git.ref_advance import (
    RefAdvanceDirtyWorktreeError,
    RefRestoreError,
    restore_branch_ref,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def advanced(tmp_path: Path) -> dict[str, object]:
    """Primary checkout on ``develop`` + linked worktree on ``feat``; both advanced by 2 commits."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-qb", "develop", str(repo)], check=True)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / "gone.txt").write_text("keep me\n")
    (repo / "base.txt").write_text("base\n")
    base = _commit(repo, "base")
    _git(repo, "branch", "feat")
    linked = tmp_path / "linked"
    _git(repo, "worktree", "add", "-q", str(linked), "feat")
    for checkout in (repo, linked):
        (checkout / "new.txt").write_text("new\n")
        (checkout / "gone.txt").unlink()
        _commit(checkout, "add new, drop gone")
        (checkout / "more.txt").write_text("more\n")
        _commit(checkout, "more")
    return {
        "repo": repo,
        "linked": linked,
        "base": base,
        "develop_tip": _git(repo, "rev-parse", "develop"),
        "feat_tip": _git(repo, "rev-parse", "feat"),
    }


def _assert_consistent(checkout: Path, sha: str) -> None:
    assert _git(checkout, "rev-parse", "HEAD") == sha
    assert _git(checkout, "status", "--porcelain", "--untracked-files=no") == ""
    assert _git(checkout, "diff", "--stat", sha) == ""


def test_resync_restores_head_index_and_worktree_in_every_checkout(advanced: dict[str, object]) -> None:
    repo, linked, base = advanced["repo"], advanced["linked"], str(advanced["base"])
    assert isinstance(repo, Path) and isinstance(linked, Path)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "keep.txt").write_text("untracked survives\n")

    restore_branch_ref(repo, "develop", base, expected_current_sha=str(advanced["develop_tip"]), resync_checkouts=True)
    restore_branch_ref(repo, "feat", base, expected_current_sha=str(advanced["feat_tip"]), resync_checkouts=True)

    for checkout in (repo, linked):
        _assert_consistent(checkout, base)
        assert not (checkout / "new.txt").exists()
        assert (checkout / "gone.txt").read_text() == "keep me\n"
    assert (repo / ".kittify" / "keep.txt").exists()


def test_dirty_tracked_change_refuses_and_moves_nothing(advanced: dict[str, object]) -> None:
    repo, linked = advanced["repo"], advanced["linked"]
    assert isinstance(repo, Path) and isinstance(linked, Path)
    (linked / "more.txt").write_text("operator edit\n")

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        restore_branch_ref(repo, "feat", str(advanced["base"]), expected_current_sha=str(advanced["feat_tip"]), resync_checkouts=True)

    assert _git(repo, "rev-parse", "feat") == advanced["feat_tip"]
    assert (linked / "more.txt").read_text() == "operator edit\n"


def test_residue_paths_are_excluded_from_the_dirty_check(advanced: dict[str, object]) -> None:
    repo, linked = advanced["repo"], advanced["linked"]
    assert isinstance(repo, Path) and isinstance(linked, Path)
    (linked / "more.txt").write_text("regenerated churn\n")

    restore_branch_ref(
        repo,
        "feat",
        str(advanced["base"]),
        expected_current_sha=str(advanced["feat_tip"]),
        resync_checkouts=True,
        context=residue_when(lambda path: path == "more.txt"),
    )

    assert _git(repo, "rev-parse", "feat") == advanced["base"]
    _assert_consistent(linked, str(advanced["base"]))


def test_stale_expected_sha_fails_closed_and_does_not_move(advanced: dict[str, object]) -> None:
    repo = advanced["repo"]
    assert isinstance(repo, Path)

    with pytest.raises(RefRestoreError):
        restore_branch_ref(repo, "feat", str(advanced["base"]), expected_current_sha=str(advanced["base"]), resync_checkouts=True)

    assert _git(repo, "rev-parse", "feat") == advanced["feat_tip"]


def test_default_moves_ref_only_and_leaves_checkout_untouched(advanced: dict[str, object]) -> None:
    repo, linked = advanced["repo"], advanced["linked"]
    assert isinstance(repo, Path) and isinstance(linked, Path)

    restore_branch_ref(repo, "feat", str(advanced["base"]), expected_current_sha=str(advanced["feat_tip"]))

    assert _git(repo, "rev-parse", "feat") == advanced["base"]
    # The documented hazard: HEAD moved under the checkout, files stay, reverse diff is staged.
    assert (linked / "new.txt").exists()
    assert _git(linked, "status", "--porcelain") != ""


def test_resync_failure_after_the_ref_moved_raises_ref_resync_error(advanced: dict[str, object], monkeypatch: pytest.MonkeyPatch) -> None:
    """Slice-10 F1: the restore's CAS won but the checkout resync failed -> ``RefResyncError`` (ref moved)."""
    from specify_cli.git import ref_advance
    from specify_cli.git.ref_advance import RefAdvanceError, RefResyncError

    repo, linked, base = Path(str(advanced["repo"])), Path(str(advanced["linked"])), str(advanced["base"])
    lock = Path(_git(linked, "rev-parse", "--absolute-git-dir")) / "index.lock"
    real_run_git = ref_advance._run_git

    def _lock_after_cas(cwd: Path, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        result = real_run_git(cwd, args, env=env)
        if args and args[0] == "update-ref":
            lock.write_text("")  # the linked checkout's reset --hard now fails
        return result

    monkeypatch.setattr(ref_advance, "_run_git", _lock_after_cas)
    with pytest.raises(RefResyncError, match="failed to resync") as raised:
        restore_branch_ref(repo, "feat", base, expected_current_sha=str(advanced["feat_tip"]), resync_checkouts=True)

    assert isinstance(raised.value, RefAdvanceError)
    assert _git(repo, "rev-parse", "feat") == base, "the CAS succeeded: the ref moved"


@pytest.fixture
def lagging(advanced: dict[str, object]) -> dict[str, object]:
    """The state a kill leaves between ``update-ref`` and the resync (FR-012).

    The linked worktree has ``feat`` checked out with index and worktree at
    ``A`` (the old tip), while ``refs/heads/feat`` was moved to ``C`` by a raw
    ``update-ref``: HEAD = C, index = worktree = A.
    """
    repo = Path(str(advanced["repo"]))
    landed_at = str(advanced["feat_tip"])
    moved_to = str(advanced["base"])
    _git(repo, "update-ref", "refs/heads/feat", moved_to)
    return {**advanced, "restore_to": landed_at, "moved_to": moved_to}


def test_restore_accepts_a_checkout_already_at_the_restore_target(lagging: dict[str, object]) -> None:
    repo, linked = Path(str(lagging["repo"])), Path(str(lagging["linked"]))
    restore_to, moved_to = str(lagging["restore_to"]), str(lagging["moved_to"])
    assert _git(linked, "status", "--porcelain", "--untracked-files=no") != "", "precondition: the checkout lags its HEAD"

    restore_branch_ref(repo, "feat", restore_to, expected_current_sha=moved_to, resync_checkouts=True)

    assert _git(repo, "rev-parse", "feat") == restore_to
    _assert_consistent(linked, restore_to)


def test_lagging_checkout_with_a_tracked_edit_still_refuses(lagging: dict[str, object]) -> None:
    repo, linked = Path(str(lagging["repo"])), Path(str(lagging["linked"]))
    restore_to, moved_to = str(lagging["restore_to"]), str(lagging["moved_to"])
    (linked / "more.txt").write_text("operator edit\n")

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        restore_branch_ref(repo, "feat", restore_to, expected_current_sha=moved_to, resync_checkouts=True)

    assert _git(repo, "rev-parse", "feat") == moved_to
    assert (linked / "more.txt").read_text() == "operator edit\n"


def test_lagging_checkout_with_a_staged_edit_still_refuses(lagging: dict[str, object]) -> None:
    repo, linked = Path(str(lagging["repo"])), Path(str(lagging["linked"]))
    restore_to, moved_to = str(lagging["restore_to"]), str(lagging["moved_to"])
    (linked / "more.txt").write_text("staged edit\n")
    _git(linked, "add", "more.txt")
    (linked / "more.txt").write_text("more\n")  # worktree back at the target; only the index differs

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        restore_branch_ref(repo, "feat", restore_to, expected_current_sha=moved_to, resync_checkouts=True)

    assert _git(repo, "rev-parse", "feat") == moved_to


def test_advance_does_not_accept_a_checkout_already_at_the_target(lagging: dict[str, object]) -> None:
    """The acceptance is restore-only: ``advance_branch_ref`` still refuses a lagging checkout."""
    from specify_cli.git.ref_advance import advance_branch_ref

    repo = Path(str(lagging["repo"]))
    restore_to, moved_to = str(lagging["restore_to"]), str(lagging["moved_to"])

    with pytest.raises(RefAdvanceDirtyWorktreeError):
        advance_branch_ref(repo, "feat", restore_to)

    assert _git(repo, "rev-parse", "feat") == moved_to


def _index_lock(checkout: Path) -> Path:
    return Path(_git(checkout, "rev-parse", "--absolute-git-dir")) / "index.lock"


def test_restore_over_a_lagging_checkout_never_resets_it_even_with_a_live_index_lock(lagging: dict[str, object]) -> None:
    """WP03 (orchestrator ruling): a checkout already at the restore target needs no reset once the CAS moves its HEAD.

    A planted ``index.lock`` (the #5571 lock arm) would make any ``reset --hard``
    fail; the restore succeeds, the ref moves, the checkout is consistent and the
    lock is left exactly as found.
    """
    repo, linked = Path(str(lagging["repo"])), Path(str(lagging["linked"]))
    restore_to, moved_to = str(lagging["restore_to"]), str(lagging["moved_to"])
    lock = _index_lock(linked)
    lock.write_text("held by another process\n")

    restore_branch_ref(repo, "feat", restore_to, expected_current_sha=moved_to, resync_checkouts=True)

    assert _git(repo, "rev-parse", "feat") == restore_to, "the CAS moved the ref"
    _assert_consistent(linked, restore_to)
    assert lock.read_text() == "held by another process\n", "the index.lock is untouched"


def test_restore_still_resets_a_checkout_that_needs_it_while_a_lock_blocks_it(advanced: dict[str, object]) -> None:
    """Positive control: a checkout at the OLD tip still needs a reset, so a live index.lock still fails the resync."""
    from specify_cli.git.ref_advance import RefResyncError

    repo, linked, base = advanced["repo"], advanced["linked"], str(advanced["base"])
    assert isinstance(repo, Path) and isinstance(linked, Path)
    _index_lock(linked).write_text("")

    with pytest.raises(RefResyncError):
        restore_branch_ref(repo, "feat", base, expected_current_sha=str(advanced["feat_tip"]), resync_checkouts=True)

    _index_lock(linked).unlink()
    restore_branch_ref(repo, "develop", base, expected_current_sha=str(advanced["develop_tip"]), resync_checkouts=True)
    _assert_consistent(repo, base)
