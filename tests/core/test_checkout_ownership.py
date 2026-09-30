"""Unit tests for the checkout-ownership validation primitive (WP01).

Mission ``worktree-owned-root-3328-01KZRG01``, work package WP01. These tests
exercise :func:`resolve_ownership_claim` against REAL temporary git
repositories/worktrees (``tmp_path`` + real ``git init`` / ``git worktree
add`` subprocess calls) mirroring the house pattern in
``tests/runtime/test_paths_unit.py`` and
``tests/git_ops/test_safe_commit_helper_integration.py`` — no mocked git
output. See ``kitty-specs/worktree-owned-root-3328-01KZRG01/data-model.md``
for the entity/validation-rule model under test.
"""

from __future__ import annotations

import subprocess
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.core import checkout_ownership
from specify_cli.core.checkout_ownership import (
    BrokenPointerCheckoutError,
    CheckoutOwnershipError,
    ForeignOrMismatchedCheckoutError,
    NestedCheckoutError,
    OwnershipClaim,
    OwnershipValidationResult,
    UnownedNoOptInError,
    error_for_claim,
    resolve_ownership_claim,
)
from specify_cli.coordination.surface_resolver import WorktreeRegistryUnavailable
from specify_cli.git.commit_helpers import is_worktree_of

pytestmark = [pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Fixtures — real git repositories, mirroring
# tests/git_ops/test_safe_commit_helper_integration.py's `git_repo` fixture.
# ---------------------------------------------------------------------------


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a real, initialized git repository with one commit."""
    repo = tmp_path / "primary"
    repo.mkdir()
    _run_git(["init"], cwd=repo)
    _run_git(["config", "user.email", "test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Test User"], cwd=repo)
    (repo / "README.md").write_text("# Test Repo\n")
    _run_git(["add", "README.md"], cwd=repo)
    _run_git(["commit", "-m", "Initial commit"], cwd=repo)
    _run_git(["branch", "-M", "main"], cwd=repo)
    return repo


def _add_worktree(repo: Path, path: Path, branch: str) -> Path:
    """Create a real linked worktree of ``repo`` at ``path`` on a new branch."""
    _run_git(["worktree", "add", "-b", branch, str(path)], cwd=repo)
    return path


# ---------------------------------------------------------------------------
# T002 — UNOWNED_NO_OPT_IN (no claim, zero subprocess calls, NFR-001)
# ---------------------------------------------------------------------------


def test_no_claim_returns_unowned_no_opt_in(
    git_repo: Path,
) -> None:
    """``claimed_checkout=None`` returns UNOWNED_NO_OPT_IN with no git calls."""
    with patch("subprocess.run") as run:
        claim = resolve_ownership_claim(None, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.UNOWNED_NO_OPT_IN
    assert claim.opted_in is False
    assert claim.detail
    assert str(git_repo.resolve()) in claim.detail
    run.assert_not_called()


def test_no_claim_error_for_claim_maps_to_unowned_error(git_repo: Path) -> None:
    claim = resolve_ownership_claim(None, resolved_primary=git_repo)
    err = error_for_claim(claim)
    assert isinstance(err, UnownedNoOptInError)
    assert isinstance(err, CheckoutOwnershipError)
    assert err.validation_result is OwnershipValidationResult.UNOWNED_NO_OPT_IN


# ---------------------------------------------------------------------------
# T002 — trivial self-ownership (primary claiming itself) is OWNED
# ---------------------------------------------------------------------------


def test_primary_self_ownership_is_owned(git_repo: Path) -> None:
    claim = resolve_ownership_claim(git_repo, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.OWNED
    assert claim.opted_in is True
    assert claim.claimed_checkout == git_repo.resolve()
    assert claim.resolved_primary == git_repo.resolve()
    assert error_for_claim(claim) is None


# ---------------------------------------------------------------------------
# T002/T003 — valid linked (non-nested) worktree is OWNED
# ---------------------------------------------------------------------------


def test_valid_linked_worktree_is_owned(git_repo: Path, tmp_path: Path) -> None:
    worktree = _add_worktree(git_repo, tmp_path / "linked-wt", "feature-a")

    claim = resolve_ownership_claim(worktree, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.OWNED
    assert claim.opted_in is True
    assert claim.claimed_checkout == worktree.resolve()
    assert error_for_claim(claim) is None


def test_managed_linked_worktree_under_primary_is_owned(git_repo: Path) -> None:
    worktrees_dir = git_repo / ".worktrees"
    worktrees_dir.mkdir()
    worktree = _add_worktree(git_repo, worktrees_dir / "linked-wt", "feature-managed")

    claim = resolve_ownership_claim(worktree, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.OWNED


def test_public_worktree_comparator_reuses_safe_commit_topology(git_repo: Path, tmp_path: Path) -> None:
    worktree = _add_worktree(git_repo, tmp_path / "comparator-wt", "feature-compare")

    assert is_worktree_of(git_repo, worktree) is True


def test_primary_subdirectory_is_not_an_owned_checkout_root(git_repo: Path) -> None:
    subdirectory = git_repo / "package" / "nested"
    subdirectory.mkdir(parents=True)

    claim = resolve_ownership_claim(subdirectory, resolved_primary=git_repo)

    assert is_worktree_of(git_repo, subdirectory) is False
    assert claim.validation_result is OwnershipValidationResult.NESTED
    assert claim.detail
    assert str(subdirectory.resolve()) in claim.detail
    assert str(git_repo.resolve()) in claim.detail


def test_linked_worktree_subdirectory_is_not_an_owned_checkout_root(git_repo: Path, tmp_path: Path) -> None:
    worktree = _add_worktree(git_repo, tmp_path / "linked-root", "root-check")
    subdirectory = worktree / "package" / "nested"
    subdirectory.mkdir(parents=True)

    claim = resolve_ownership_claim(subdirectory, resolved_primary=git_repo)

    assert is_worktree_of(git_repo, subdirectory) is False
    assert claim.validation_result is OwnershipValidationResult.NESTED
    assert claim.detail
    assert str(subdirectory.resolve()) in claim.detail
    assert str(worktree.resolve()) in claim.detail

    root_claim = resolve_ownership_claim(worktree, resolved_primary=git_repo)
    assert is_worktree_of(git_repo, worktree) is True
    assert root_claim.validation_result is OwnershipValidationResult.OWNED


# ---------------------------------------------------------------------------
# T003 — nested worktree (registry-based, not `.worktrees`-literal) is NESTED
# ---------------------------------------------------------------------------


def test_nested_worktree_is_nested(git_repo: Path, tmp_path: Path) -> None:
    outer = _add_worktree(git_repo, tmp_path / "outer-wt", "feature-outer")
    inner = _add_worktree(git_repo, outer / "nested-inner-wt", "feature-inner")

    claim = resolve_ownership_claim(inner, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.NESTED
    assert claim.opted_in is True
    assert claim.detail
    assert str(inner.resolve()) in claim.detail
    assert str(outer.resolve()) in claim.detail

    err = error_for_claim(claim)
    assert isinstance(err, NestedCheckoutError)
    assert err.validation_result is OwnershipValidationResult.NESTED


def test_nested_worktree_uses_generic_registry_not_dot_worktrees_literal(git_repo: Path, tmp_path: Path) -> None:
    """C-006: nested detection must work for paths with NO ``.worktrees`` segment.

    ``outer``/``inner`` below live under a plain ``tmp_path`` tree — neither
    path contains a literal ``.worktrees`` component, so a detector keyed on
    that literal would miss this case entirely (the exact C-006 gap this WP
    closes).
    """
    outer = _add_worktree(git_repo, tmp_path / "generic-outer", "feature-generic-outer")
    inner = _add_worktree(git_repo, outer / "generic-inner", "feature-generic-inner")
    assert ".worktrees" not in inner.parts

    claim = resolve_ownership_claim(inner, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.NESTED


# ---------------------------------------------------------------------------
# T004 — foreign repository (unrelated common-dir) is FOREIGN_OR_MISMATCHED
# ---------------------------------------------------------------------------


def test_foreign_repo_is_foreign_or_mismatched(git_repo: Path, tmp_path: Path) -> None:
    foreign = tmp_path / "foreign-repo"
    foreign.mkdir()
    _run_git(["init"], cwd=foreign)
    _run_git(["config", "user.email", "test@example.com"], cwd=foreign)
    _run_git(["config", "user.name", "Test User"], cwd=foreign)
    (foreign / "README.md").write_text("# Foreign Repo\n")
    _run_git(["add", "README.md"], cwd=foreign)
    _run_git(["commit", "-m", "Initial commit"], cwd=foreign)

    claim = resolve_ownership_claim(foreign, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.FOREIGN_OR_MISMATCHED
    assert claim.opted_in is True
    assert claim.detail
    assert str(foreign.resolve()) in claim.detail
    assert str((foreign / ".git").resolve()) in claim.detail
    assert str((git_repo / ".git").resolve()) in claim.detail

    err = error_for_claim(claim)
    assert isinstance(err, ForeignOrMismatchedCheckoutError)
    assert err.validation_result is OwnershipValidationResult.FOREIGN_OR_MISMATCHED


# ---------------------------------------------------------------------------
# T004 — corrupted/broken gitdir pointer is BROKEN_POINTER (fail-closed)
# ---------------------------------------------------------------------------


def test_broken_gitdir_pointer_is_broken_pointer(git_repo: Path, tmp_path: Path) -> None:
    worktree = _add_worktree(git_repo, tmp_path / "to-corrupt-wt", "feature-corrupt")

    # Hand-corrupt the .git pointer file after creation (per WP guidance):
    # point it at a gitdir that does not exist.
    git_file = worktree / ".git"
    assert git_file.is_file()
    # Git marks this pointer hidden on Windows; update without recreating it.
    with git_file.open("r+", encoding="utf-8") as pointer:
        pointer.write("gitdir: /nonexistent/path/.git/worktrees/to-corrupt-wt\n")
        pointer.truncate()

    claim = resolve_ownership_claim(worktree, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.BROKEN_POINTER
    assert claim.opted_in is True
    assert claim.detail
    assert str(worktree.resolve()) in claim.detail
    assert str(git_repo.resolve()) in claim.detail

    err = error_for_claim(claim)
    assert isinstance(err, BrokenPointerCheckoutError)
    assert err.validation_result is OwnershipValidationResult.BROKEN_POINTER


def test_missing_git_binary_is_broken_pointer(git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing/unexecutable git binary must fold into BROKEN_POINTER, never raise."""
    worktree = _add_worktree(git_repo, tmp_path / "no-git-binary-wt", "feature-no-git")

    def _raise_file_not_found(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("git: command not found")

    monkeypatch.setattr(subprocess, "run", _raise_file_not_found)

    claim = resolve_ownership_claim(worktree, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.BROKEN_POINTER
    assert claim.detail
    assert str(worktree.resolve()) in claim.detail
    assert str(git_repo.resolve()) in claim.detail


def test_unavailable_worktree_registry_is_broken_pointer(git_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worktree = _add_worktree(git_repo, tmp_path / "registry-wt", "feature-registry")

    def _raise_registry_unavailable(repo_root: Path) -> frozenset[Path]:
        raise WorktreeRegistryUnavailable(repo_root=repo_root, detail="registry failed")

    monkeypatch.setattr(
        checkout_ownership,
        "read_worktree_registry",
        _raise_registry_unavailable,
    )

    claim = resolve_ownership_claim(worktree, resolved_primary=git_repo)

    assert claim.validation_result is OwnershipValidationResult.BROKEN_POINTER
    assert claim.detail
    assert str(worktree.resolve()) in claim.detail
    assert str(git_repo.resolve()) in claim.detail


# ---------------------------------------------------------------------------
# T001 — OwnershipClaim / OwnershipValidationResult / error vocabulary shape
# ---------------------------------------------------------------------------


def test_ownership_validation_result_has_exactly_five_values() -> None:
    assert {member.value for member in OwnershipValidationResult} == {
        "OWNED",
        "UNOWNED_NO_OPT_IN",
        "NESTED",
        "FOREIGN_OR_MISMATCHED",
        "BROKEN_POINTER",
    }


def test_ownership_claim_is_frozen_dataclass(git_repo: Path) -> None:
    claim = resolve_ownership_claim(git_repo, resolved_primary=git_repo)
    assert isinstance(claim, OwnershipClaim)
    with pytest.raises(FrozenInstanceError):
        type(claim).__setattr__(claim, "opted_in", False)


@pytest.mark.parametrize(
    ("validation_result", "opted_in", "error_type", "error_code"),
    [
        (
            OwnershipValidationResult.UNOWNED_NO_OPT_IN,
            False,
            UnownedNoOptInError,
            "WORKTREE_INVOCATION_REFUSED",
        ),
        (
            OwnershipValidationResult.NESTED,
            True,
            NestedCheckoutError,
            "OWNERSHIP_NESTED",
        ),
        (
            OwnershipValidationResult.FOREIGN_OR_MISMATCHED,
            True,
            ForeignOrMismatchedCheckoutError,
            "OWNERSHIP_FOREIGN",
        ),
        (
            OwnershipValidationResult.BROKEN_POINTER,
            True,
            BrokenPointerCheckoutError,
            "OWNERSHIP_BROKEN_POINTER",
        ),
    ],
)
def test_error_for_claim_exposes_cli_error_contract(
    git_repo: Path,
    validation_result: OwnershipValidationResult,
    opted_in: bool,
    error_type: type[CheckoutOwnershipError],
    error_code: str,
) -> None:
    path = git_repo.resolve()
    claim = OwnershipClaim(path, path, validation_result, opted_in, "refused")
    error = error_for_claim(claim)
    assert isinstance(error, error_type)
    assert error.error_code == error_code
    assert error.to_dict()["error_code"] == error_code


def test_error_for_claim_returns_none_for_owned(git_repo: Path) -> None:
    claim = resolve_ownership_claim(git_repo, resolved_primary=git_repo)
    assert claim.validation_result is OwnershipValidationResult.OWNED
    assert error_for_claim(claim) is None


# ---------------------------------------------------------------------------
# WP02 (owned-checkout-lifecycle-authority) — claims_repository_root predicate
# ---------------------------------------------------------------------------


def test_claims_repository_root_is_true_for_self_ownership(git_repo: Path) -> None:
    from specify_cli.core.checkout_ownership import claims_repository_root

    claim = resolve_ownership_claim(git_repo, resolved_primary=git_repo)
    assert claims_repository_root(claim) is True


def test_claims_repository_root_is_false_for_linked_worktree(git_repo: Path, tmp_path: Path) -> None:
    from specify_cli.core.checkout_ownership import claims_repository_root

    worktree = _add_worktree(git_repo, tmp_path / "linked-wt-root-check", "feature-root-check")
    claim = resolve_ownership_claim(worktree, resolved_primary=git_repo)
    assert claims_repository_root(claim) is False


def test_claims_repository_root_is_false_for_nested_claim(git_repo: Path, tmp_path: Path) -> None:
    from specify_cli.core.checkout_ownership import claims_repository_root

    outer = _add_worktree(git_repo, tmp_path / "outer-root-check", "feature-outer-root-check")
    inner = _add_worktree(git_repo, outer / "nested-inner-root-check", "feature-inner-root-check")
    claim = resolve_ownership_claim(inner, resolved_primary=git_repo)
    assert claim.validation_result is OwnershipValidationResult.NESTED
    assert claims_repository_root(claim) is False


def test_claims_repository_root_is_false_for_foreign_claim(tmp_path: Path, git_repo: Path) -> None:
    from specify_cli.core.checkout_ownership import claims_repository_root

    foreign = tmp_path / "foreign-root-check"
    foreign.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=foreign, check=True)  # noqa: TID251
    claim = resolve_ownership_claim(foreign, resolved_primary=git_repo)
    assert claim.validation_result is OwnershipValidationResult.FOREIGN_OR_MISMATCHED
    assert claims_repository_root(claim) is False
