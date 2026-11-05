"""Guard extensions for the landed-worktree prune (#7173, WP02).

Covers the no-force removal mode of :func:`guarded_worktree_remove`
(``force=False``: never ``git worktree remove --force``; git's own refusal of a
locked worktree surfaces as ``WORKTREE_REMOVE_REFUSED_BY_GIT``) and the
``LANDED_INTENT`` branch deletion, which records a tip found on no other ref
under ``refs/spec-kitty/discarded/<branch>`` before ``git branch -D``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.coherence import CheckoutRole, ResidueContext
from specify_cli.git import destructive_guard
from specify_cli.git.destructive_guard import (
    BRANCH_CHECKED_OUT,
    BRANCH_TIP_MOVED,
    DESTRUCTIVE_OP_ONLY_COPY,
    DISCARD_INTENT,
    LANDED_INTENT,
    MERGE_UNSAFE_WORKTREE_DIRTY,
    WORKTREE_REMOVE_REFUSED_BY_GIT,
    DestructiveOpRefused,
    RemoveOutcome,
    guarded_branch_delete,
    guarded_worktree_remove,
    keep_detached_tip,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "m-01ABCDEF"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def _ctx() -> ResidueContext:
    return ResidueContext(CheckoutRole.LANE, _SLUG, MissionTopology.COORD)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    (root / "src.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "seed")
    return root


def _worktree(root: Path, tmp_path: Path, branch: str = "lane-x") -> Path:
    worktree = tmp_path / f"wt-{branch}"
    _git(root, "worktree", "add", "-q", "-b", branch, str(worktree), "main")
    return worktree


def _registered(root: Path, worktree: Path) -> bool:
    return str(worktree.resolve()) in _git(root, "worktree", "list", "--porcelain")


def _branch_with_commit(root: Path, name: str) -> str:
    _git(root, "checkout", "-q", "-b", name)
    (root / f"{name}.txt").write_text(name, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", name)
    _git(root, "checkout", "-q", "main")
    return _git(root, "rev-parse", name).strip()


def _spec_kitty_refs(root: Path) -> list[str]:
    return _git(root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/spec-kitty/").splitlines()


def _advance_branch(root: Path, branch: str, name: str) -> str:
    """A new commit on ``branch`` (a concurrent actor moving the ref); returns its SHA."""
    _git(root, "checkout", "-q", branch)
    (root / f"{name}.txt").write_text(name, encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", name)
    _git(root, "checkout", "-q", "main")
    return _git(root, "rev-parse", branch).strip()


# --- force=False removal ----------------------------------------------------------


def test_no_force_removes_a_clean_worktree_without_the_force_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    worktree = _worktree(root, tmp_path)
    calls: list[list[str]] = []
    real_run_git = destructive_guard._run_git

    def spy(
        cwd: Path,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
        stdin: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return real_run_git(cwd, args, env=env, stdin=stdin)

    monkeypatch.setattr(destructive_guard, "_run_git", spy)

    result = guarded_worktree_remove(worktree, retain=False, context=_ctx(), force=False)

    assert result.outcome is RemoveOutcome.REMOVED
    assert not worktree.exists()
    removals = [args for args in calls if args[:2] == ["worktree", "remove"]]
    assert removals == [["worktree", "remove", "--", str(worktree)]]


def test_no_force_refuses_a_locked_worktree_and_keeps_it(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    worktree = _worktree(root, tmp_path)
    _git(root, "worktree", "lock", str(worktree))

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_worktree_remove(worktree, retain=False, context=_ctx(), force=False)

    assert info.value.error_code == WORKTREE_REMOVE_REFUSED_BY_GIT
    assert info.value.worktree_path == worktree
    assert info.value.dirty_entries, "git's own refusal text is carried for the operator"
    assert worktree.exists()
    assert _registered(root, worktree)

    # Positive control: the same worktree, unlocked, is removed.
    _git(root, "worktree", "unlock", str(worktree))
    assert guarded_worktree_remove(worktree, retain=False, context=_ctx(), force=False).outcome is RemoveOutcome.REMOVED
    assert not worktree.exists()


def test_no_force_with_retain_refuses_a_locked_clean_worktree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    worktree = _worktree(root, tmp_path)
    _git(root, "worktree", "lock", str(worktree))

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_worktree_remove(worktree, retain=True, context=_ctx(), force=False)

    assert info.value.error_code == WORKTREE_REMOVE_REFUSED_BY_GIT
    assert worktree.exists()


def test_no_force_refuses_an_untracked_file_by_the_guards_own_proof(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    worktree = _worktree(root, tmp_path)
    (worktree / "notes.md").write_text("only copy\n", encoding="utf-8")

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_worktree_remove(worktree, retain=False, context=_ctx(), force=False)

    assert info.value.error_code == MERGE_UNSAFE_WORKTREE_DIRTY
    assert (worktree / "notes.md").read_text(encoding="utf-8") == "only copy\n"
    assert _registered(root, worktree)


def test_no_force_removes_a_worktree_holding_only_an_ignored_venv(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    worktree = _worktree(root, tmp_path)
    (worktree / ".venv" / "bin").mkdir(parents=True)
    (worktree / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    result = guarded_worktree_remove(worktree, retain=False, context=_ctx(), force=False)

    assert result.outcome is RemoveOutcome.REMOVED
    assert not worktree.exists()
    assert not _registered(root, worktree)


def test_default_force_fails_on_a_locked_worktree_as_a_runtime_error_not_a_refusal(tmp_path: Path) -> None:
    """Existing callers keep a single ``--force``: git still refuses a locked worktree, raised as before (not ``DestructiveOpRefused``)."""
    root = _repo(tmp_path)
    worktree = _worktree(root, tmp_path)
    _git(root, "worktree", "lock", str(worktree))

    with pytest.raises(RuntimeError, match="worktree remove --force"):
        # A locked worktree needs ``--force`` twice; the default path's failure stays a RuntimeError.
        guarded_worktree_remove(worktree, retain=False, context=_ctx())
    _git(root, "worktree", "unlock", str(worktree))
    assert guarded_worktree_remove(worktree, retain=False, context=_ctx()).outcome is RemoveOutcome.REMOVED


# --- LANDED_INTENT ----------------------------------------------------------------


@pytest.mark.parametrize("other_ref", ["refs/heads/other", "refs/tags/v1"])
def test_landed_intent_deletes_a_branch_found_on_another_local_ref_without_a_record(tmp_path: Path, other_ref: str) -> None:
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "landed")
    _git(root, "update-ref", other_ref, tip)

    assert guarded_branch_delete(root, "landed", creation_base=None, operator_intent=LANDED_INTENT, expected_tip=tip) is None

    assert _git(root, "for-each-ref", "refs/heads/landed") == ""
    assert _spec_kitty_refs(root) == []


def test_landed_intent_records_a_tip_held_only_by_a_remote_tracking_ref(tmp_path: Path) -> None:
    """Fold C: a stale ``refs/remotes/*`` can vouch for a commit later rewritten off the remote; keep the tip."""
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "landed")
    _git(root, "update-ref", "refs/remotes/origin/main", tip)

    assert guarded_branch_delete(root, "landed", creation_base=None, operator_intent=LANDED_INTENT, expected_tip=tip) == tip

    assert _git(root, "for-each-ref", "refs/heads/landed") == ""
    assert _spec_kitty_refs(root) == [f"refs/spec-kitty/discarded/landed {tip}"]


def test_discard_intent_still_counts_remote_tracking_refs(tmp_path: Path) -> None:
    """Fold C is scoped to ``LANDED_INTENT``: the discard keeps its original reachability rule."""
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "dropped")
    _git(root, "update-ref", "refs/remotes/origin/dropped", tip)

    assert guarded_branch_delete(root, "dropped", creation_base=None, operator_intent=DISCARD_INTENT) is None

    assert _spec_kitty_refs(root) == []


# --- keep_detached_tip (fold D) -----------------------------------------------------


def test_keep_detached_tip_records_the_sha_create_only(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "det")

    ref = keep_detached_tip(root, tip)

    assert ref == f"refs/spec-kitty/discarded/detached/{tip}"
    assert _spec_kitty_refs(root) == [f"{ref} {tip}"]
    assert keep_detached_tip(root, tip) == ref, "idempotent once written"


def test_keep_detached_tip_refuses_when_the_ref_cannot_be_written(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "det")
    # A file-shaped ref where the namespace directory must go: the create cannot succeed.
    _git(root, "update-ref", "refs/spec-kitty/discarded/detached", "HEAD")

    with pytest.raises(DestructiveOpRefused) as info:
        keep_detached_tip(root, tip)

    assert info.value.error_code == DESTRUCTIVE_OP_ONLY_COPY


def test_landed_intent_records_a_unique_tip_before_deleting(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "squashed")

    assert guarded_branch_delete(root, "squashed", creation_base=None, operator_intent=LANDED_INTENT, expected_tip=tip) == tip

    assert _git(root, "for-each-ref", "refs/heads/squashed") == ""
    assert _spec_kitty_refs(root) == [f"refs/spec-kitty/discarded/squashed {tip}"]
    _git(root, "branch", "squashed", tip)
    assert _git(root, "rev-parse", "squashed").strip() == tip


def test_landed_intent_refuses_and_keeps_the_branch_when_the_tip_cannot_be_recorded(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _git(root, "update-ref", "refs/spec-kitty/discarded/x", "HEAD")
    _branch_with_commit(root, "tmp")
    _git(root, "branch", "-m", "tmp", "x/y")
    tip = _git(root, "rev-parse", "x/y").strip()

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_branch_delete(root, "x/y", creation_base=None, operator_intent=LANDED_INTENT, expected_tip=tip)

    assert info.value.error_code == DESTRUCTIVE_OP_ONLY_COPY
    assert _git(root, "for-each-ref", "refs/heads/x/y") != ""


def test_an_unknown_operator_intent_still_raises(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    _branch_with_commit(root, "keep-me")

    with pytest.raises(ValueError, match="landed"):
        guarded_branch_delete(root, "keep-me", creation_base=None, operator_intent="pruned")
    assert _git(root, "for-each-ref", "refs/heads/keep-me") != ""


# --- LANDED_INTENT is a compare-and-swap (issue #7212) ------------------------------


def test_landed_intent_requires_the_approved_tip(tmp_path: Path) -> None:
    """A LANDED delete that names no tip is refused before any git call: it cannot be bound."""
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "squashed")

    with pytest.raises(ValueError, match="expected_tip"):
        guarded_branch_delete(root, "squashed", creation_base=None, operator_intent=LANDED_INTENT)

    assert _git(root, "rev-parse", "squashed").strip() == tip
    assert _spec_kitty_refs(root) == [], "nothing recorded for a refused call"


@pytest.mark.parametrize("intent", [None, DISCARD_INTENT])
def test_an_expected_tip_outside_the_landed_intent_is_refused_not_ignored(tmp_path: Path, intent: str | None) -> None:
    """A bound-tip argument on a path that ignores it would read as a guarantee it does not give."""
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "squashed")

    with pytest.raises(ValueError, match="expected_tip"):
        guarded_branch_delete(root, "squashed", creation_base=None, operator_intent=intent, expected_tip=tip)

    assert _git(root, "rev-parse", "squashed").strip() == tip


def test_landed_intent_refuses_a_branch_that_moved_past_the_approved_tip(tmp_path: Path) -> None:
    """The approved tip was proven absorbed; the commit now on the branch was not."""
    root = _repo(tmp_path)
    approved = _branch_with_commit(root, "squashed")
    moved = _advance_branch(root, "squashed", "late")
    assert moved != approved

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_branch_delete(root, "squashed", creation_base=None, operator_intent=LANDED_INTENT, expected_tip=approved)

    assert info.value.error_code == BRANCH_TIP_MOVED
    assert _git(root, "rev-parse", "squashed").strip() == moved
    assert _spec_kitty_refs(root) == [], "a refused delete records nothing"


def test_landed_intent_refuses_a_branch_checked_out_in_a_worktree(tmp_path: Path) -> None:
    """``update-ref -d`` bypasses git's checked-out protection, so the guard keeps it explicitly."""
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "squashed")
    worktree = tmp_path / "wt-checked-out"
    _git(root, "worktree", "add", "-q", str(worktree), "squashed")

    with pytest.raises(DestructiveOpRefused) as info:
        guarded_branch_delete(root, "squashed", creation_base=None, operator_intent=LANDED_INTENT, expected_tip=tip)

    assert info.value.error_code == BRANCH_CHECKED_OUT
    assert _git(root, "rev-parse", "squashed").strip() == tip
    # The keep-record is written before the delete (crash safety), so this refusal
    # may leave one behind; it must hold the approved tip and nothing else.
    assert [line for line in _spec_kitty_refs(root) if not line.endswith(f" {tip}")] == []


def test_landed_intent_compare_and_swap_deletes_the_branch_at_the_approved_tip(tmp_path: Path) -> None:
    """Positive control for the two refusals above: the same fixture deletes when the ref did not move."""
    root = _repo(tmp_path)
    tip = _branch_with_commit(root, "squashed")

    assert guarded_branch_delete(root, "squashed", creation_base=None, operator_intent=LANDED_INTENT, expected_tip=tip) == tip

    assert _git(root, "for-each-ref", "refs/heads/squashed") == ""
    assert _spec_kitty_refs(root) == [f"refs/spec-kitty/discarded/squashed {tip}"]
