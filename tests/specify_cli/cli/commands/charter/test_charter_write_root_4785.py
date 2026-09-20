"""Regression tests for the worktree-safe charter-write root helper (#4785 Finding 3).

Mission ``charter-catalog-coherence-01M2XQQF`` WP02 introduces the ONE shared,
tested authority for charter-write checkout safety:
:func:`specify_cli.cli.commands.charter._charter_write_root.resolve_charter_write_root`.
Every charter write command (wired up in WP03/WP04) calls it so no charter
write can silently land in the PRIMARY checkout when invoked from a linked
git worktree (FR-006).

These tests pin the three branches from ``contracts/behavior-contracts.md``
Contract C3 / ``data-model.md``'s checkout-topology table:

* a repository-root checkout (or dedicated clone) resolves to its own
  toplevel;
* a linked git worktree fails closed with the exact remedy message; and
* a git-absent / not-a-repo invocation degrades safely (no crash, no raise).

Detection is topology-based (kernel ``git_topology``: git-dir vs
git-common-dir), never a ``.worktrees/`` path-substring match (NFR-003).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.git_topology import (
    GitTopologyUnavailableError,
    NotAGitRepositoryError,
    clear_caches,
)

from specify_cli.cli.commands.charter._charter_write_root import (
    LinkedWorktreeCharterWriteError,
    resolve_charter_write_root,
)

# Real subprocess git repos + worktrees, like the primitive's own suite
# (tests/git/test_git_topology.py) -- structurally incompatible with mutmut's
# forked sandbox.
pytestmark = [pytest.mark.regression, pytest.mark.non_sandbox, pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _reset_topology_cache() -> None:
    """Reset the shared probe caches so a prior test's path cannot shadow this one."""
    clear_caches()


@pytest.fixture
def fresh_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("cwr_repo")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    clear_caches()
    return root


@pytest.fixture
def repo_with_worktree(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("cwr_repo_wt")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    for key, val in (("user.email", "t@e.com"), ("user.name", "T")):
        subprocess.run(["git", "-C", str(root), "config", key, val], check=True, capture_output=True)
    (root / "README.md").write_text("seed\n")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "seed", "--quiet"], check=True, capture_output=True)
    worktree = root.parent / (root.name + "-lane-b")
    subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "-B", "lane-b", str(worktree)],
        check=True,
        capture_output=True,
    )
    clear_caches()
    return root, worktree


# ---------------------------------------------------------------------------
# Primary checkout / dedicated clone -> returns the checkout root
# ---------------------------------------------------------------------------


def test_primary_checkout_returns_toplevel(fresh_repo: Path) -> None:
    assert resolve_charter_write_root(fresh_repo) == fresh_repo.resolve()


def test_primary_checkout_from_subdirectory_returns_toplevel(fresh_repo: Path) -> None:
    sub = fresh_repo / "src" / "nested"
    sub.mkdir(parents=True)
    assert resolve_charter_write_root(sub) == fresh_repo.resolve()


def test_repo_with_worktree_main_checkout_still_resolves(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    main_root, _worktree = repo_with_worktree
    assert resolve_charter_write_root(main_root) == main_root.resolve()


# ---------------------------------------------------------------------------
# Linked git worktree -> fails closed
# ---------------------------------------------------------------------------


def test_linked_worktree_raises_fail_closed(repo_with_worktree: tuple[Path, Path]) -> None:
    _main_root, worktree = repo_with_worktree
    with pytest.raises(LinkedWorktreeCharterWriteError) as excinfo:
        resolve_charter_write_root(worktree)
    assert "use a repository-root checkout or dedicated clone for charter authoring" in str(excinfo.value)


def test_linked_worktree_error_does_not_return_primary_root(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    """The failure must be a raise, never a silent fallback to the PRIMARY checkout."""
    main_root, worktree = repo_with_worktree
    try:
        resolve_charter_write_root(worktree)
    except LinkedWorktreeCharterWriteError as exc:
        assert getattr(exc, "start", None) in {worktree, worktree.resolve()}
    else:  # pragma: no cover -- defensive; the raise assertion above already covers this
        pytest.fail("resolve_charter_write_root must raise for a linked worktree")
    # Sanity: the two checkouts really are distinct toplevels (would make this test vacuous otherwise).
    assert main_root.resolve() != worktree.resolve()


# ---------------------------------------------------------------------------
# git-absent / not-a-repo -> degrades safely (no raise)
# ---------------------------------------------------------------------------


def test_git_topology_unavailable_degrades_safely(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(_path: Path) -> Path:
        raise GitTopologyUnavailableError(_path, "git binary not found on PATH")

    monkeypatch.setattr("specify_cli.cli.commands.charter._charter_write_root.git_toplevel", _boom)
    monkeypatch.setattr("specify_cli.cli.commands.charter._charter_write_root.git_common_dir", _boom)

    result = resolve_charter_write_root(tmp_path)

    assert result == tmp_path.resolve()


def test_not_a_git_repository_degrades_safely(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _boom(_path: Path) -> Path:
        raise NotAGitRepositoryError(_path)

    monkeypatch.setattr("specify_cli.cli.commands.charter._charter_write_root.git_toplevel", _boom)
    monkeypatch.setattr("specify_cli.cli.commands.charter._charter_write_root.git_common_dir", _boom)

    result = resolve_charter_write_root(tmp_path)

    assert result == tmp_path.resolve()


def test_not_a_repo_real_probe_degrades_safely(tmp_path_factory: pytest.TempPathFactory) -> None:
    """End-to-end (no monkeypatch): a real non-repo directory never crashes the resolver."""
    not_a_repo = tmp_path_factory.mktemp("cwr_bare")
    assert resolve_charter_write_root(not_a_repo) == not_a_repo.resolve()


# ---------------------------------------------------------------------------
# NFR-003: detection must be topology-based, never a path-substring match
# ---------------------------------------------------------------------------


def test_worktrees_substring_in_primary_path_is_not_flagged(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """A primary checkout whose path happens to contain '.worktrees' must NOT be refused.

    Pins NFR-003: detection must use the kernel git_topology probe (git-dir vs
    git-common-dir), never a ``.worktrees/`` path-substring match.
    """
    parent = tmp_path_factory.mktemp("cwr_substring")
    trap = parent / ".worktrees" / "not-actually-a-worktree"
    trap.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(trap)], check=True, capture_output=True)
    clear_caches()

    assert resolve_charter_write_root(trap) == trap.resolve()
