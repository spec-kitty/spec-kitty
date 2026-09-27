"""WP05/T021 FR-007 — ``agent action implement`` preflight blocks under sparse.

The preflight must run BEFORE any worktree creation or state change. When the
primary repo has ``core.sparseCheckout=true`` active, the command must refuse
with a non-zero exit and create NO worktree under ``.worktrees/``.
"""

from __future__ import annotations

import subprocess
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.workflow import implement
from specify_cli.git.sparse_checkout import _reset_session_warning_state


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _run(["git", "-C", str(repo), "config", "user.email", "test@test.com"])
    _run(["git", "-C", str(repo), "config", "user.name", "Test"])
    _run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"])
    (repo / "README.md").write_text("init\n")
    _run(["git", "-C", str(repo), "add", "."])
    _run(["git", "-C", str(repo), "commit", "-m", "init"])


def _seed_mission(repo: Path, slug: str) -> None:
    # .kittify marker so locate_project_root() identifies repo as the project root.
    (repo / ".kittify").mkdir(parents=True, exist_ok=True)
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (feature_dir / "lanes.json").write_text('{"target_branch":"main","lanes":[]}\n')
    # Minimal spec and WP file so the command has something to reference.
    (feature_dir / "spec.md").write_text("# test\n")
    (feature_dir / "tasks" / "WP01-test.md").write_text(
        "---\nwork_package_id: WP01\n---\n# WP01\n"
    )


def _invoke_implement(repo: Path, args: list[str]) -> object:
    """Invoke the implement Typer command inside ``repo``."""
    import typer

    app = typer.Typer()
    app.command()(implement)
    runner = CliRunner()

    with chdir(repo):
        return runner.invoke(app, args, catch_exceptions=True)


class TestImplementPreflightBlocks:
    @pytest.fixture(autouse=True)
    def _reset_warning(self) -> None:
        _reset_session_warning_state()
        yield
        _reset_session_warning_state()

    def test_sparse_repo_blocks_implement(self, tmp_path: Path) -> None:
        """FR-007: implement exits non-zero under sparse-checkout, creates no worktree."""
        repo = tmp_path / "r"
        _init_git_repo(repo)
        _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])
        slug = "test-mission"
        _seed_mission(repo, slug)

        result = _invoke_implement(
            repo, ["WP01", "--mission", slug, "--agent", "claude"]
        )

        exit_code = getattr(result, "exit_code", None)
        if exit_code is None:
            exit_code = getattr(result, "code", None)
        assert exit_code is not None and exit_code != 0, (
            f"implement must exit non-zero under sparse-checkout; got {exit_code}"
        )

        output = getattr(result, "output", "") or getattr(result, "stdout", "") or ""
        assert "sparse-checkout" in output.lower(), (
            f"Expected sparse-checkout block message; got output:\n{output}"
        )

        worktrees_dir = repo / ".worktrees"
        if worktrees_dir.exists():
            children = list(worktrees_dir.iterdir())
            assert children == [], (
                "FR-007: no worktree may be created when the preflight aborts; "
                f"found {children}"
            )

    def test_force_flag_does_not_bypass_implement_preflight(self, tmp_path: Path) -> None:
        """FR-009 / T038: ``--force`` does not open a bypass path on implement either.

        The implement command has no ``--force`` option; the only sanctioned
        override is ``--allow-sparse-checkout``. Passing ``--force`` must
        produce a non-zero exit AND leave no worktree behind.
        """
        repo = tmp_path / "r"
        _init_git_repo(repo)
        _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])
        slug = "test-mission"
        _seed_mission(repo, slug)

        result = _invoke_implement(
            repo, ["WP01", "--mission", slug, "--agent", "claude", "--force"]
        )

        exit_code = getattr(result, "exit_code", None)
        if exit_code is None:
            exit_code = getattr(result, "code", None)
        assert exit_code is not None and exit_code != 0, (
            f"--force must not open a bypass; got exit={exit_code}"
        )

        worktrees_dir = repo / ".worktrees"
        if worktrees_dir.exists():
            children = list(worktrees_dir.iterdir())
            assert children == [], (
                "FR-009 / T038: no worktree may be created when --force is passed "
                f"under sparse-checkout; found {children}"
            )
