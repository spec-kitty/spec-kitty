"""Reproduction of the linked-worktree charter write refusal in tests (#5317).

The charter commands ``generate``, ``synthesize`` and ``resynthesize`` call
``resolve_charter_write_root(Path.cwd())``. That guard refuses when the
**process working directory** is a linked worktree. Tests that aim a command at
a **test tmp project** by patching ``specify_cli.cli.commands.charter.find_repo_root``
never change directory, so the guard sees the checkout pytest was started from.
When pytest starts in a linked worktree (a Spec Kitty lane worktree), such a
test fails with ``Refusing charter write from linked git worktree``.

These tests build a real linked worktree in tmp and start the command from it,
which reproduces that condition from any checkout.

This file lives under ``tests/charter/``, whose conftest turns every test's
``tmp_path`` into a git repository. The reproduction needs three distinct
repositories under that one ``tmp_path``: the invoking repository and its linked
worktree, and the test tmp project. Each is created with its own ``git init``
(or ``git worktree add``), so each has its own ``.git`` and none is a plain
sub-directory of the enclosing ``tmp_path`` repository.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kernel.git_topology import clear_caches
from specify_cli.cli.commands.charter import app

pytestmark = [pytest.mark.integration, pytest.mark.non_sandbox, pytest.mark.git_repo]

REFUSAL_MESSAGE = "Refusing charter write from linked git worktree"

runner = CliRunner()


def _git(*args: str, cwd: Path | None = None) -> None:
    """Run git with an explicit identity so the test ignores developer git config."""
    subprocess.run(
        ["git", "-c", "user.name=Test User", "-c", "user.email=test@example.com", *args],
        check=True,
        capture_output=True,
        cwd=cwd,
    )


@pytest.fixture(autouse=True)
def _reset_topology_cache() -> None:
    """Reset the shared probe caches so a probe from another test cannot leak in."""
    clear_caches()


@pytest.fixture
def linked_worktree(tmp_path: Path) -> Path:
    """A linked worktree of a tmp repository, standing in for a lane worktree."""
    repository = tmp_path / "invoking_repository"
    repository.mkdir()
    _git("init", "--quiet", str(repository))
    (repository / "README.md").write_text("seed\n", encoding="utf-8")
    _git("add", "README.md", cwd=repository)
    _git("commit", "--quiet", "-m", "seed", cwd=repository)
    worktree = tmp_path / "invoking_repository-lane-a"
    _git("worktree", "add", "--quiet", "-B", "lane-a", str(worktree), cwd=repository)
    clear_caches()
    return worktree


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A test tmp project: its own normal git repository, outside the linked worktree."""
    root = tmp_path / "project"
    root.mkdir()
    _git("init", "--quiet", str(root))
    assert (root / ".git").is_dir(), "the test tmp project must be its own repository, not a sub-directory of tmp_path"
    (root / ".kittify" / "charter").mkdir(parents=True)
    return root


def test_isolated_generate_from_linked_worktree_succeeds(
    linked_worktree: Path,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    charter_cwd_isolation: Callable[..., Path],
) -> None:
    """The same start, once isolated, writes the charter under the test tmp project."""
    monkeypatch.chdir(linked_worktree)
    charter_cwd_isolation(project)

    result = runner.invoke(app, ["generate", "--no-from-interview"])

    assert result.exit_code == 0, result.output
    assert (project / ".kittify" / "charter" / "charter.yaml").is_file()


def test_guard_still_refuses_after_helper_when_cwd_returns_to_linked_worktree(
    linked_worktree: Path,
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
    charter_cwd_isolation: Callable[..., Path],
) -> None:
    """The helper must not neutralise the real guard (FR-008)."""
    charter_cwd_isolation(project)
    monkeypatch.chdir(linked_worktree)

    result = runner.invoke(app, ["generate", "--no-from-interview"])

    assert result.exit_code != 0
    assert REFUSAL_MESSAGE in result.output
    assert not (project / ".kittify" / "charter" / "charter.yaml").exists()


def test_helper_defaults_to_tmp_path_and_returns_the_root_it_used(
    tmp_path: Path,
    project: Path,
    charter_cwd_isolation: Callable[..., Path],
) -> None:
    default_root = charter_cwd_isolation()
    assert default_root == tmp_path
    # Resolved: the process working directory can differ by symlink (macOS /private/var vs /var).
    assert Path.cwd().resolve() == tmp_path.resolve()

    explicit_root = charter_cwd_isolation(project)
    assert explicit_root == project
    assert Path.cwd().resolve() == project.resolve()
