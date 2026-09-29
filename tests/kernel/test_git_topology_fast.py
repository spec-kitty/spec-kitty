"""Fast, subprocess-mocked unit tests for :mod:`kernel.git_topology`.

These pin the primitive's parsing / canonicalization / error-classification
logic WITHOUT a real git repo (``subprocess.run`` is mocked), so the
``fast``-only ``kernel-tests`` CI job (``-m fast --cov=src/kernel``) covers
``src/kernel/git_topology.py`` — the module lives on the ``kernel``
critical-path and is subject to the diff-coverage floor. The real-git
integration parity tests (linked worktrees, live ``git init``) live in
``tests/git/test_git_topology.py`` and run under the ``git_repo`` marker.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from kernel.git_topology import (
    GitTopologyError,
    GitTopologyUnavailableError,
    NotAGitRepositoryError,
    clear_caches,
    git_common_dir,
    git_configured_worktree,
    git_toplevel,
)

pytestmark = pytest.mark.fast

_RUN = "kernel.git_topology.subprocess.run"


@pytest.fixture(autouse=True)
def _reset_caches() -> None:
    """The probes are module-level ``lru_cache``d — reset around every test so
    a mocked result never leaks across cases."""
    clear_caches()
    yield
    clear_caches()


def _fake(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["git", "rev-parse"], returncode=returncode, stdout=stdout, stderr=stderr
    )


# --- git_common_dir ---------------------------------------------------------


def test_common_dir_relative_output_resolved_against_cwd(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with patch(_RUN, return_value=_fake(stdout=".git\n")):
        assert git_common_dir(repo) == (repo / ".git").resolve()


def test_common_dir_absolute_output_preserved(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    shared = tmp_path / "shared.git"
    with patch(_RUN, return_value=_fake(stdout=f"{shared}\n")):
        assert git_common_dir(repo) == shared.resolve()


def test_common_dir_file_input_normalized_to_parent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    f = repo / "file.txt"
    f.write_text("x", encoding="utf-8")
    with patch(_RUN, return_value=_fake(stdout=".git\n")) as m:
        result = git_common_dir(f)
    assert m.call_args.kwargs["cwd"] == str(repo)  # probed the PARENT dir
    assert result == (repo / ".git").resolve()


def test_common_dir_not_a_repo_raises(tmp_path: Path) -> None:
    with patch(_RUN, return_value=_fake(returncode=128, stderr="fatal: not a git repository")), pytest.raises(NotAGitRepositoryError):
        git_common_dir(tmp_path / "nope")


def test_common_dir_other_failure_is_unavailable(tmp_path: Path) -> None:
    with patch(_RUN, return_value=_fake(returncode=128, stderr="fatal: bad object HEAD")), pytest.raises(GitTopologyUnavailableError):
        git_common_dir(tmp_path / "corrupt")


def test_common_dir_interior_of_common_dir_raises(tmp_path: Path) -> None:
    # stdout "." makes the common dir equal the probed dir → not a valid root.
    repo = tmp_path / "repo"
    repo.mkdir()
    with patch(_RUN, return_value=_fake(stdout=".\n")), pytest.raises(NotAGitRepositoryError):
        git_common_dir(repo)


def test_common_dir_missing_binary_is_unavailable(tmp_path: Path) -> None:
    with patch(_RUN, side_effect=FileNotFoundError("git")), pytest.raises(GitTopologyUnavailableError, match="git binary not found"):
        git_common_dir(tmp_path / "repo")


# --- git_toplevel -----------------------------------------------------------


def test_toplevel_happy_path(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with patch(_RUN, return_value=_fake(stdout=f"{repo}\n")):
        assert git_toplevel(repo) == repo.resolve()


def test_toplevel_not_a_repo_raises(tmp_path: Path) -> None:
    with patch(_RUN, return_value=_fake(returncode=128, stderr="fatal: not a git repository")), pytest.raises(NotAGitRepositoryError):
        git_toplevel(tmp_path / "nope")


def test_toplevel_empty_output_is_unavailable(tmp_path: Path) -> None:
    # returncode 0 but no output → undeterminable, fail closed.
    with patch(_RUN, return_value=_fake(returncode=0, stdout="")), pytest.raises(GitTopologyUnavailableError, match="exit 0"):
        git_toplevel(tmp_path / "repo")


def test_toplevel_missing_binary_is_unavailable(tmp_path: Path) -> None:
    with patch(_RUN, side_effect=FileNotFoundError("git")), pytest.raises(GitTopologyUnavailableError):
        git_toplevel(tmp_path / "repo")


# --- git_configured_worktree ------------------------------------------------


def test_configured_worktree_relative_value_resolved_against_common_dir(tmp_path: Path) -> None:
    # A submodule's absorbed git dir records ``core.worktree = ../../../submod``.
    common = tmp_path / "super" / ".git" / "modules" / "submod"
    common.mkdir(parents=True)
    with patch(_RUN, return_value=_fake(stdout="../../../submod\n")):
        assert git_configured_worktree(common) == (tmp_path / "super" / "submod").resolve()


def test_configured_worktree_unset_key_is_none(tmp_path: Path) -> None:
    # ``git config --get`` exits 1 with no output when the key is unset.
    with patch(_RUN, return_value=_fake(returncode=1)):
        assert git_configured_worktree(tmp_path) is None


def test_configured_worktree_config_failure_is_unavailable(tmp_path: Path) -> None:
    bad_config = _fake(returncode=3, stderr="fatal: bad config line 1")
    with patch(_RUN, return_value=bad_config), pytest.raises(GitTopologyUnavailableError, match="bad config line"):
        git_configured_worktree(tmp_path)


def test_configured_worktree_missing_binary_is_unavailable(tmp_path: Path) -> None:
    with patch(_RUN, side_effect=FileNotFoundError("git")), pytest.raises(GitTopologyUnavailableError, match="git binary not found"):
        git_configured_worktree(tmp_path)


def test_clear_caches_resets_configured_worktree_probe(tmp_path: Path) -> None:
    with patch(_RUN, return_value=_fake(returncode=1)) as m:
        git_configured_worktree(tmp_path)
        git_configured_worktree(tmp_path)
        clear_caches()
        git_configured_worktree(tmp_path)
    assert m.call_count == 2


# --- caching + error hierarchy ---------------------------------------------


def test_warm_cache_makes_no_second_invocation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with patch(_RUN, return_value=_fake(stdout=".git\n")) as m:
        git_common_dir(repo)
        git_common_dir(repo)
    assert m.call_count == 1


def test_clear_caches_forces_reinvocation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with patch(_RUN, return_value=_fake(stdout=".git\n")) as m:
        git_common_dir(repo)
        clear_caches()
        git_common_dir(repo)
    assert m.call_count == 2


def test_typed_errors_share_base_class() -> None:
    assert issubclass(NotAGitRepositoryError, GitTopologyError)
    assert issubclass(GitTopologyUnavailableError, GitTopologyError)
