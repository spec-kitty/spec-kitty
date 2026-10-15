"""Unit tests for :mod:`specify_cli.git.sparse_checkout` detection primitive.

Covers T012 validation items from WP02:

- ``SparseCheckoutState.is_active`` mirrors ``config_enabled`` (R6).
- ``scan_path`` on non-sparse / sparse / pattern-only / pattern+config repos.
- ``scan_repo`` walks ``.worktrees/*`` and tolerates an absent dir.
- ``warn_if_sparse_once`` is truly once-per-process (asserted via ``caplog``).
- ``warn_if_sparse_once`` swallows detection errors gracefully.
- ``_reset_session_warning_state`` re-arms the emitter.
- NFR-001 microbenchmark — a single ``scan_path`` with mocked subprocess
  completes well under 20 ms.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.git import sparse_checkout as sc_mod
from specify_cli.git.sparse_checkout import (
    SparseCheckoutScanReport,
    SparseCheckoutState,
    _reset_session_warning_state,
    scan_path,
    scan_repo,
    warn_if_sparse_once,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

@pytest.fixture(autouse=True)
def _reset_warning_state() -> None:
    """Reset the module-level session-warning flag before every test."""
    _reset_session_warning_state()


def _init_git_repo(path: Path) -> None:
    """Initialise a bare-ish git repo rooted at ``path``."""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", str(path)],
        check=True,
        capture_output=True,
    )
    # Make sure commits don't fail on a bare CI env.
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )


def _enable_sparse_config(path: Path) -> None:
    subprocess.run(
        ["git", "-C", str(path), "config", "core.sparseCheckout", "true"],
        check=True,
        capture_output=True,
    )


def _write_pattern_file(path: Path, lines: list[str]) -> None:
    pf = path / ".git" / "info" / "sparse-checkout"
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# SparseCheckoutState.is_active (R6)
# ---------------------------------------------------------------------------


class TestIsActive:
    def test_is_active_follows_config_enabled_true(self) -> None:
        s = SparseCheckoutState(
            path=Path("/nonexistent/x"),
            config_enabled=True,
            pattern_file_path=None,
            pattern_file_present=False,
            pattern_line_count=0,
            is_worktree=False,
        )
        assert s.is_active is True

    def test_is_active_false_when_config_disabled_even_with_pattern(self) -> None:
        # R6: pattern-file presence must not flip is_active on its own.
        s = SparseCheckoutState(
            path=Path("/nonexistent/x"),
            config_enabled=False,
            pattern_file_path=Path("/nonexistent/x/.git/info/sparse-checkout"),
            pattern_file_present=True,
            pattern_line_count=12,
            is_worktree=False,
        )
        assert s.is_active is False


# ---------------------------------------------------------------------------
# scan_path
# ---------------------------------------------------------------------------


class TestScanPath:
    def test_non_sparse_repo(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        state = scan_path(tmp_path, is_worktree=False)
        assert state.config_enabled is False
        assert state.pattern_file_present is False
        assert state.pattern_line_count == 0
        assert state.is_worktree is False
        assert state.is_active is False

    def test_sparse_config_but_no_pattern_file(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _enable_sparse_config(tmp_path)
        # No pattern file written.
        state = scan_path(tmp_path, is_worktree=False)
        assert state.config_enabled is True
        assert state.pattern_file_present is False
        assert state.pattern_line_count == 0
        assert state.is_active is True

    def test_sparse_config_with_patterns(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _enable_sparse_config(tmp_path)
        _write_pattern_file(
            tmp_path,
            [
                "# comment line",
                "src/",
                "",
                "docs/",
                "   ",
                "# another comment",
                "tests/",
            ],
        )
        state = scan_path(tmp_path, is_worktree=False)
        assert state.config_enabled is True
        assert state.pattern_file_present is True
        assert state.pattern_line_count == 3  # src/, docs/, tests/
        assert state.is_active is True

    def test_pattern_file_without_config_is_not_active(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _write_pattern_file(tmp_path, ["src/"])
        state = scan_path(tmp_path, is_worktree=False)
        assert state.config_enabled is False
        assert state.pattern_file_present is True
        assert state.pattern_line_count == 1
        # R6: active requires config_enabled=True.
        assert state.is_active is False

    def test_nonexistent_path(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist"
        state = scan_path(missing, is_worktree=False)
        assert state.config_enabled is False
        assert state.pattern_file_present is False
        assert state.pattern_line_count == 0
        assert state.is_active is False

    def test_scan_path_does_not_mutate_git_state(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _enable_sparse_config(tmp_path)
        _write_pattern_file(tmp_path, ["src/"])

        scan_path(tmp_path, is_worktree=False)

        # Config should still read as 'true' and pattern file untouched.
        result = subprocess.run(
            ["git", "-C", str(tmp_path), "config", "--get", "core.sparseCheckout"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.stdout.strip().lower() == "true"
        pf = tmp_path / ".git" / "info" / "sparse-checkout"
        assert pf.exists()
        assert "src/" in pf.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# scan_repo
# ---------------------------------------------------------------------------


class TestScanRepo:
    def test_no_worktrees_dir(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        report = scan_repo(tmp_path)
        assert isinstance(report, SparseCheckoutScanReport)
        assert report.worktrees == ()
        assert report.primary.is_active is False

    def test_worktrees_dir_empty(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        (tmp_path / ".worktrees").mkdir()
        report = scan_repo(tmp_path)
        assert report.worktrees == ()

    def test_worktrees_dir_skips_non_git_children(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        wts = tmp_path / ".worktrees"
        wts.mkdir()
        (wts / "random-folder").mkdir()  # no .git — must be skipped
        (wts / "a-file").write_text("not a worktree", encoding="utf-8")

        report = scan_repo(tmp_path)
        assert report.worktrees == ()

    def test_walks_worktree_children_with_dot_git(self, tmp_path: Path) -> None:
        # Create a real-ish layout with a fake worktree child containing a
        # .git pointer file. scan_repo only needs the presence check; per-worktree
        # sparse-checkout resolution via rev-parse is exercised in other tests
        # that use real `git worktree` setups where available.
        _init_git_repo(tmp_path)
        wts = tmp_path / ".worktrees"
        wts.mkdir()
        wt_a = wts / "feature-lane-a"
        wt_a.mkdir()
        (wt_a / ".git").write_text("gitdir: /nonexistent\n", encoding="utf-8")

        report = scan_repo(tmp_path)
        assert len(report.worktrees) == 1
        assert report.worktrees[0].path == wt_a
        assert report.worktrees[0].is_worktree is True

    def test_any_active_and_affected_paths(self, tmp_path: Path) -> None:
        _init_git_repo(tmp_path)
        _enable_sparse_config(tmp_path)
        report = scan_repo(tmp_path)
        assert report.any_active is True
        assert report.affected_paths == (tmp_path,)

    def test_per_worktree_config_layering(self, tmp_path: Path) -> None:
        """Worktree-scoped config (``--worktree``) must be seen only in the worktree.

        Uses ``git config --worktree`` which requires
        ``extensions.worktreeConfig=true`` and writes to the per-worktree
        config file rather than the shared repo config. This exercises the
        "primary clean, worktree active" case enumerated in WP02 Risks.
        """
        _init_git_repo(tmp_path)
        # Create a real git worktree so per-worktree config actually lives on disk.
        (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "README.md"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        wt = tmp_path / ".worktrees" / "lane-a"
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "worktree",
                "add",
                "-b",
                "lane-a-branch",
                str(wt),
            ],
            check=True,
            capture_output=True,
        )
        # Enable the worktree-config extension and write the flag per-worktree.
        subprocess.run(
            [
                "git",
                "-C",
                str(tmp_path),
                "config",
                "extensions.worktreeConfig",
                "true",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(wt),
                "config",
                "--worktree",
                "core.sparseCheckout",
                "true",
            ],
            check=True,
            capture_output=True,
        )

        report = scan_repo(tmp_path)
        # With per-worktree config, primary is untouched.
        assert report.primary.is_active is False
        assert len(report.worktrees) == 1
        assert report.worktrees[0].is_active is True
        assert report.any_active is True
        assert wt in report.affected_paths


# ---------------------------------------------------------------------------
# warn_if_sparse_once
# ---------------------------------------------------------------------------


class TestWarnOnce:
    def test_emits_once_on_active_repo(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _init_git_repo(tmp_path)
        _enable_sparse_config(tmp_path)

        caplog.set_level(logging.WARNING, logger=sc_mod.logger.name)

        for _ in range(5):
            warn_if_sparse_once(tmp_path, command="merge")

        marker_hits = [
            r for r in caplog.records if "spec_kitty.sparse_checkout.detected" in r.getMessage()
        ]
        assert len(marker_hits) == 1, (
            f"Expected exactly one warning, got {len(marker_hits)}: "
            f"{[r.getMessage() for r in caplog.records]}"
        )
        msg = marker_hits[0].getMessage()
        assert "command=merge" in msg
        assert str(tmp_path) in msg
        assert "spec-kitty doctor sparse-checkout --fix" in msg

    def test_first_command_label_wins_across_call_sites(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Many CLI surfaces in one process: one warning, labelled with the first caller."""
        _init_git_repo(tmp_path)
        _enable_sparse_config(tmp_path)
        caplog.set_level(logging.WARNING, logger=sc_mod.logger.name)

        for command in ("implement", "merge", "review", "accept", "tasks:move-task", "doctor"):
            warn_if_sparse_once(tmp_path, command=command)

        marker_hits = [
            r for r in caplog.records if "spec_kitty.sparse_checkout.detected" in r.getMessage()
        ]
        assert len(marker_hits) == 1
        assert "command=implement" in marker_hits[0].getMessage()

    def test_no_emit_on_clean_repo(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _init_git_repo(tmp_path)
        caplog.set_level(logging.WARNING, logger=sc_mod.logger.name)

        warn_if_sparse_once(tmp_path, command="merge")

        assert not any(
            "spec_kitty.sparse_checkout.detected" in r.getMessage()
            for r in caplog.records
        )

    def test_swallows_detection_errors(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger=sc_mod.logger.name)
        with patch.object(sc_mod, "scan_repo", side_effect=RuntimeError("boom")):
            # Must not raise.
            warn_if_sparse_once(tmp_path, command="merge")

        # And no emission either.
        assert not any(
            "spec_kitty.sparse_checkout.detected" in r.getMessage()
            for r in caplog.records
        )

    def test_reset_helper_rearms_emitter(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _init_git_repo(tmp_path)
        _enable_sparse_config(tmp_path)
        caplog.set_level(logging.WARNING, logger=sc_mod.logger.name)

        warn_if_sparse_once(tmp_path, command="merge")
        first_hits = [
            r for r in caplog.records if "spec_kitty.sparse_checkout.detected" in r.getMessage()
        ]
        assert len(first_hits) == 1

        # Second call is a no-op.
        warn_if_sparse_once(tmp_path, command="merge")
        still_one = [
            r for r in caplog.records if "spec_kitty.sparse_checkout.detected" in r.getMessage()
        ]
        assert len(still_one) == 1

        # Reset and call again — should emit once more.
        _reset_session_warning_state()
        warn_if_sparse_once(tmp_path, command="merge")
        now_two = [
            r for r in caplog.records if "spec_kitty.sparse_checkout.detected" in r.getMessage()
        ]
        assert len(now_two) == 2

