"""WP05/T020/T038 — merge sparse-checkout preflight blocks the flow.

FR-006: ``spec-kitty merge`` must refuse to start when legacy sparse-checkout
state is active, and must do so BEFORE any merge-state write or git mutation.

FR-009 / T038: ``--force`` does NOT bypass the preflight; only
``--allow-sparse-checkout`` does, and that override is covered in a separate
test file.

These tests exercise the real ``merge`` Typer command (live wiring), not a
helper in isolation.
"""

from __future__ import annotations

import subprocess
from contextlib import chdir
from functools import partial
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import consolidate as merge_module
from specify_cli.cli.commands.consolidate import consolidate as merge
from specify_cli.git.sparse_checkout import _reset_session_warning_state
from specify_cli.task_utils import find_repo_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _enable_sparse(repo: Path) -> None:
    _run(["git", "-C", str(repo), "config", "core.sparseCheckout", "true"])


def _seed_minimal_mission(repo: Path, slug: str) -> None:
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    # Minimal lanes.json so the command path that would call it has a fixture —
    # though the preflight should block before we ever reach it.
    (feature_dir / "lanes.json").write_text('{"target_branch":"main","lanes":[]}\n')


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMergePreflightBlocks:
    """FR-006 + FR-009 (T038): preflight must block merge before state writes."""

    @pytest.fixture(autouse=True)
    def _reset_warning(self) -> None:
        _reset_session_warning_state()
        yield
        _reset_session_warning_state()

    def _invoke(
        self, repo: Path, extra_args: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> object:
        """Invoke the real merge Typer command in ``repo``.

        ``find_repo_root()`` walks unboundedly in production. Bound the walk
        to ``repo`` (issue #128): nothing above it is under test control, and
        under a full parallel run a sibling test's shared ancestor can
        transiently gain a ``.git``/``.kittify``, which would make ``merge``
        resolve the wrong repo root instead of reaching the sparse-checkout
        preflight against *this* repo (same class of bug as #130/#139's
        ``_find_project_root``).
        """
        monkeypatch.setattr(
            merge_module, "find_repo_root", partial(find_repo_root, stop=repo)
        )
        runner = CliRunner()
        # The Typer command must be wrapped in a Typer app to receive options
        # correctly. The real CLI mounts merge() on the root app; here we
        # instantiate a minimal app for invocation.
        import typer

        app = typer.Typer()
        app.command()(merge)

        # CliRunner uses CWD from the system, so run it inside repo.
        try:
            with chdir(repo):
                return runner.invoke(app, extra_args, catch_exceptions=False)
        except SystemExit as exc:  # typer.Exit inherits from click.exceptions.Exit
            return exc

    def test_sparse_repo_blocks_merge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-006: merge exits non-zero under sparse-checkout, no state written, HEAD unchanged."""
        repo = tmp_path / "r"
        _init_git_repo(repo)
        _enable_sparse(repo)
        slug = "test-mission"
        _seed_minimal_mission(repo, slug)

        head_before = _run(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()

        result = self._invoke(repo, ["--mission", slug], monkeypatch)

        exit_code = getattr(result, "exit_code", None)
        if exit_code is None:
            exit_code = getattr(result, "code", None)
        assert exit_code is not None and exit_code != 0, (
            f"merge must exit non-zero under sparse-checkout; got {exit_code}"
        )

        output = getattr(result, "output", "") or getattr(result, "stdout", "") or ""
        assert "sparse-checkout" in output.lower(), (
            f"Expected sparse-checkout block message; got output:\n{output}"
        )

        merge_state_path = repo / ".kittify" / "runtime" / "merge-state.json"
        assert not merge_state_path.exists(), (
            "ConsolidationState must not be written when preflight aborts (FR-006)."
        )

        head_after = _run(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()
        assert head_before == head_after, (
            "HEAD must not advance when preflight aborts the merge."
        )

    def test_force_flag_does_not_bypass_preflight(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FR-009 / T038: ``--force`` must NOT open a bypass path.

        The merge command deliberately has no ``--force`` flag — the only
        supported override is ``--allow-sparse-checkout``. This test guards
        against a future regression where someone might add ``--force`` as a
        bypass. The expected behaviour is that ``--force`` either:

        1. is rejected by Typer as an unknown option (current state), or
        2. if ever added, the sparse-checkout preflight still blocks.

        Either outcome is a non-zero exit WITH no HEAD movement and no
        ConsolidationState write. A successful merge under sparse-checkout with
        ``--force`` would be the regression this test catches.
        """
        repo = tmp_path / "r"
        _init_git_repo(repo)
        _enable_sparse(repo)
        slug = "test-mission"
        _seed_minimal_mission(repo, slug)

        head_before = _run(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()

        result = self._invoke(repo, ["--mission", slug, "--force"], monkeypatch)

        exit_code = getattr(result, "exit_code", None)
        if exit_code is None:
            exit_code = getattr(result, "code", None)
        assert exit_code is not None and exit_code != 0, (
            f"--force must not open a bypass path under sparse-checkout; got exit={exit_code}"
        )

        merge_state_path = repo / ".kittify" / "runtime" / "merge-state.json"
        assert not merge_state_path.exists(), (
            "ConsolidationState must not be written when --force is passed under sparse-checkout."
        )

        head_after = _run(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()
        assert head_before == head_after, (
            "HEAD must not advance when --force is passed under sparse-checkout."
        )
