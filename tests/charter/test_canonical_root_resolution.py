"""Tests for ``charter.resolution.resolve_canonical_repo_root``.

Exercises every row of the R-2 behavioral matrix from
``contracts/canonical-root-resolver.contract.md``.
"""
from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from charter.resolution import (    GitCommonDirUnavailableError,
    NotInsideRepositoryError,
    resolve_canonical_repo_root,
)

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: trampoline bug: subprocess
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Local fixtures: explicit, side-effect-free repo / worktree builders.
# We deliberately avoid the autouse ``_git_init_tmp_path`` fixture's implicit
# repo for cases where we want a non-repo path or a freshly-built layout.
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """An isolated freshly-initialized git repo at ``tmp_path/repo``.

    Returns the absolute path to the repo (the canonical root).
    """
    root = tmp_path_factory.mktemp("repo")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    # Reset the resolver cache so prior tests don't shadow this path.
    resolve_canonical_repo_root.cache_clear()
    return root


@pytest.fixture
def repo_with_worktree(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """An isolated git repo with one linked worktree.

    Returns ``(main_checkout, linked_worktree)`` — the main checkout is the
    canonical root we expect the resolver to return for both inputs.
    """
    root = tmp_path_factory.mktemp("repo_with_worktree")
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    # Configure identity locally so commits succeed.
    for key, val in (("user.email", "test@example.com"), ("user.name", "Test")):
        subprocess.run(["git", "-C", str(root), "config", key, val], check=True, capture_output=True)
    # Need at least one commit before `git worktree add`.
    (root / "README.md").write_text("seed\n")
    subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-m", "seed", "--quiet"],
        check=True, capture_output=True,
    )
    worktree = root.parent / (root.name + "-wt")
    subprocess.run(
        ["git", "-C", str(root), "worktree", "add", "-B", "wt-branch", str(worktree)],
        check=True, capture_output=True,
    )
    resolve_canonical_repo_root.cache_clear()
    return root, worktree


# ---------------------------------------------------------------------------
# Behavioral matrix tests (R-2)
# ---------------------------------------------------------------------------


def test_main_checkout_root_returns_working_dir(fresh_repo: Path) -> None:
    result = resolve_canonical_repo_root(fresh_repo)
    assert result == fresh_repo.resolve()


def test_subdirectory_returns_main_checkout(fresh_repo: Path) -> None:
    sub = fresh_repo / "src" / "sub"
    sub.mkdir(parents=True)
    result = resolve_canonical_repo_root(sub)
    assert result == fresh_repo.resolve()


def test_file_input_normalized_to_parent(fresh_repo: Path) -> None:
    file_path = fresh_repo / "some_file.txt"
    file_path.write_text("hi")
    result = resolve_canonical_repo_root(file_path)
    assert result == fresh_repo.resolve()


def test_inside_dot_git_raises_not_inside_repo(fresh_repo: Path) -> None:
    inside_git = fresh_repo / ".git"
    assert inside_git.exists()
    with pytest.raises(NotInsideRepositoryError):
        resolve_canonical_repo_root(inside_git)


def test_linked_worktree_returns_main_checkout(repo_with_worktree: tuple[Path, Path]) -> None:
    main_root, worktree = repo_with_worktree
    result = resolve_canonical_repo_root(worktree)
    assert result == main_root.resolve(), (
        f"Expected main checkout {main_root}, got {result}"
    )
    # Subdirectory of the worktree must resolve the same way.
    (worktree / "deep" / "nest").mkdir(parents=True)
    sub_result = resolve_canonical_repo_root(worktree / "deep" / "nest")
    assert sub_result == main_root.resolve()


def test_non_repo_raises_not_inside_repo(tmp_path_factory: pytest.TempPathFactory) -> None:
    not_a_repo = tmp_path_factory.mktemp("not_a_repo")
    # Confirm there is no git repo at this path or its parents (within the
    # macOS pytest tmp tree there isn't one).
    resolve_canonical_repo_root.cache_clear()
    with pytest.raises(NotInsideRepositoryError):
        resolve_canonical_repo_root(not_a_repo)


def test_missing_git_binary_raises_git_common_dir_unavailable(fresh_repo: Path) -> None:
    resolve_canonical_repo_root.cache_clear()
    with (
        patch("kernel.git_topology.subprocess.run", side_effect=FileNotFoundError("git")),
        pytest.raises(GitCommonDirUnavailableError) as excinfo,
    ):
        resolve_canonical_repo_root(fresh_repo)
    assert "binary not found" in str(excinfo.value)


def test_corrupt_repo_raises_git_common_dir_unavailable(fresh_repo: Path) -> None:
    resolve_canonical_repo_root.cache_clear()
    fake_result = MagicMock(returncode=128, stderr="fatal: bad object HEAD\n", stdout="")
    with (
        patch("kernel.git_topology.subprocess.run", return_value=fake_result),
        pytest.raises(GitCommonDirUnavailableError) as excinfo,
    ):
        resolve_canonical_repo_root(fresh_repo)
    assert "bad object" in str(excinfo.value)


def test_warm_call_uses_cache_no_git_invocation(fresh_repo: Path) -> None:
    resolve_canonical_repo_root.cache_clear()
    real_run = subprocess.run
    spy = MagicMock(side_effect=lambda *a, **kw: real_run(*a, **kw))
    with patch("kernel.git_topology.subprocess.run", spy):
        resolve_canonical_repo_root(fresh_repo)
        resolve_canonical_repo_root(fresh_repo)
    assert spy.call_count == 1, f"Expected 1 git invocation, got {spy.call_count}"


def test_cache_clear_resets_invocation_count(fresh_repo: Path) -> None:
    resolve_canonical_repo_root.cache_clear()
    real_run = subprocess.run
    spy = MagicMock(side_effect=lambda *a, **kw: real_run(*a, **kw))
    with patch("kernel.git_topology.subprocess.run", spy):
        resolve_canonical_repo_root(fresh_repo)
        resolve_canonical_repo_root.cache_clear()
        resolve_canonical_repo_root(fresh_repo)
    assert spy.call_count == 2, f"Expected 2 git invocations after cache_clear, got {spy.call_count}"


def test_sparse_checkout_returns_main_root(fresh_repo: Path) -> None:
    # Enable sparse-checkout (no patterns; behavior should be unchanged).
    subprocess.run(
        ["git", "-C", str(fresh_repo), "config", "core.sparseCheckout", "true"],
        check=True, capture_output=True,
    )
    resolve_canonical_repo_root.cache_clear()
    result = resolve_canonical_repo_root(fresh_repo)
    assert result == fresh_repo.resolve()


def test_detached_head_returns_main_root(repo_with_worktree: tuple[Path, Path]) -> None:
    main_root, _worktree = repo_with_worktree
    # Detach HEAD on the main checkout.
    subprocess.run(
        ["git", "-C", str(main_root), "checkout", "--detach", "--quiet"],
        check=True, capture_output=True,
    )
    resolve_canonical_repo_root.cache_clear()
    result = resolve_canonical_repo_root(main_root)
    assert result == main_root.resolve()


def _git(*args: str) -> None:
    """Run one git command with a deterministic identity, raising on failure."""
    subprocess.run(
        ["git", "-c", "user.email=t@e.com", "-c", "user.name=T", *args],
        check=True,
        capture_output=True,
    )


_SUBMODULE_SKIP_REASON = "submodule edge cases differ on Windows; documented in resolver contract"


@pytest.fixture
def repo_with_submodule(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A superproject with one real submodule at ``<super>/submod``.

    Returns ``(superproject, submodule_working_tree)``. The submodule's git dir
    is absorbed into ``<super>/.git/modules/submod`` (its ``.git`` is a FILE),
    which is the layout ``git submodule add`` produces.
    """
    superproject = tmp_path_factory.mktemp("super")
    subproject = tmp_path_factory.mktemp("sub_src")
    for repo in (superproject, subproject):
        _git("init", "--quiet", str(repo))
        (repo / "README.md").write_text("seed\n")
        _git("-C", str(repo), "add", "README.md")
        _git("-C", str(repo), "commit", "-m", "seed", "--quiet")
    add_result = subprocess.run(
        [
            "git", "-C", str(superproject), "-c", "protocol.file.allow=always",
            "submodule", "add", str(subproject), "submod",
        ],
        capture_output=True, text=True,
    )
    if add_result.returncode != 0:
        pytest.skip(f"git submodule add unsupported in this environment: {add_result.stderr}")
    submod_dir = superproject / "submod"
    assert (submod_dir / ".git").is_file(), "fixture must build an absorbed-gitdir submodule"
    resolve_canonical_repo_root.cache_clear()
    return superproject, submod_dir


@pytest.mark.skipif(platform.system() == "Windows", reason=_SUBMODULE_SKIP_REASON)
def test_submodule_resolves_to_submodule_working_tree(
    repo_with_submodule: tuple[Path, Path],
) -> None:
    """Inside a submodule, the canonical root is the submodule's own working
    tree: never the superproject (#2011) and never its ``.git/modules`` dir.
    """
    _superproject, submod_dir = repo_with_submodule
    expected = submod_dir.resolve()

    assert resolve_canonical_repo_root(submod_dir) == expected
    (submod_dir / "deep" / "nest").mkdir(parents=True)
    assert resolve_canonical_repo_root(submod_dir / "deep" / "nest") == expected


@pytest.mark.skipif(platform.system() == "Windows", reason=_SUBMODULE_SKIP_REASON)
def test_linked_worktree_of_submodule_resolves_to_submodule_main_working_tree(
    repo_with_submodule: tuple[Path, Path],
) -> None:
    """A linked worktree of a submodule resolves to the submodule's MAIN
    working tree, mirroring the plain linked-worktree row.
    """
    superproject, submod_dir = repo_with_submodule
    linked = superproject.parent / (superproject.name + "-submod-wt")
    _git("-C", str(submod_dir), "worktree", "add", "--quiet", "-b", "wt-branch", str(linked))
    resolve_canonical_repo_root.cache_clear()

    assert resolve_canonical_repo_root(linked) == submod_dir.resolve()


@pytest.mark.skipif(platform.system() == "Windows", reason=_SUBMODULE_SKIP_REASON)
def test_submodule_worktree_probe_failure_raises_git_common_dir_unavailable(
    repo_with_submodule: tuple[Path, Path],
) -> None:
    """A failing ``core.worktree`` probe keeps the typed error surface: no
    silent fallback to the ``.git/modules`` parent (C-001).
    """
    _superproject, submod_dir = repo_with_submodule
    real_run = subprocess.run

    def _fail_config(cmd: list[str], **kwargs: object) -> object:
        if "config" in cmd:
            return MagicMock(returncode=3, stdout="", stderr="fatal: bad config line 7\n")
        return real_run(cmd, **kwargs)

    with (
        patch("kernel.git_topology.subprocess.run", side_effect=_fail_config),
        pytest.raises(GitCommonDirUnavailableError, match="bad config line 7"),
    ):
        resolve_canonical_repo_root(submod_dir)


@pytest.mark.skipif(platform.system() == "Windows", reason=_SUBMODULE_SKIP_REASON)
def test_submodule_warm_call_uses_cache_no_git_invocation(
    repo_with_submodule: tuple[Path, Path],
) -> None:
    """Resolving a submodule costs git probes only on the cold call; a warm
    call runs no git at all.
    """
    _superproject, submod_dir = repo_with_submodule
    cold = resolve_canonical_repo_root(submod_dir)
    real_run = subprocess.run
    spy = MagicMock(side_effect=lambda *a, **kw: real_run(*a, **kw))
    with patch("kernel.git_topology.subprocess.run", spy):
        warm = resolve_canonical_repo_root(submod_dir)
    assert warm == cold
    assert spy.call_count == 0, f"Expected 0 git invocations when warm, got {spy.call_count}"
