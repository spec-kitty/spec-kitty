"""Tests for FR-021: implement --base <ref> flag.

Verifies:
- Valid ref creates lane workspace branching from the given ref.
- Invalid ref fails with the documented error message (no fallback).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from specify_cli.cli.commands.implement_phases import _validate_base_ref
from tests.specify_cli.cli.commands.test_implement_characterization import (
    ARGS,
    LANE_BRANCH,
    LANE_WORKTREE,
    MISSION_ID,
    SLUG,
    activate_repo,
    build_mission,
    git,
    implement_cli,
    init_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_git_repo(path: Path) -> None:
    """Create a minimal git repo with an initial commit on 'main'."""
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(path),
        capture_output=True,
        check=True,
    )


# ---------------------------------------------------------------------------
# Unit tests for _validate_base_ref
# ---------------------------------------------------------------------------


class TestValidateBaseRef:
    """Tests for the _validate_base_ref helper (called by implement --base)."""

    def test_valid_ref_returns_sha(self, tmp_path: Path) -> None:
        """A valid ref (e.g., 'main') should resolve successfully."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        sha = _validate_base_ref(repo, "main")
        assert len(sha) == 40, f"Expected full SHA, got: {sha!r}"
        assert all(c in "0123456789abcdef" for c in sha)

    def test_invalid_ref_raises_exit(self, tmp_path: Path) -> None:
        """An unknown ref should raise typer.Exit(1) with a clear message."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        with pytest.raises(typer.Exit) as exc_info:
            _validate_base_ref(repo, "bogus-ref-that-does-not-exist")

        assert exc_info.value.exit_code == 1

    def test_invalid_ref_error_message_contains_remediation(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """The error message for an invalid ref must mention the ref and remediation."""
        from rich.console import Console
        import specify_cli.cli.commands.implement as impl_mod

        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        # Capture output from the Rich console used by implement.py
        captured_messages: list[str] = []
        original_print = impl_mod.console.print

        def capturing_print(*args, **kwargs):
            captured_messages.append(str(args[0]) if args else "")
            original_print(*args, **kwargs)

        with patch.object(impl_mod.console, "print", side_effect=capturing_print):
            with pytest.raises(typer.Exit):
                _validate_base_ref(repo, "bogus-ref")

        all_output = " ".join(captured_messages)
        assert "bogus-ref" in all_output, f"Expected ref name in error: {all_output!r}"
        assert "does not resolve" in all_output, f"Expected 'does not resolve' in: {all_output!r}"


class TestImplementBaseFlagIntegration:
    """Integration tests for the implement --base flag."""

    def test_implement_base_flag_invalid_ref_fails_clearly(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """--base bogus-ref exits 1 with the documented message and allocates nothing.

        Exit code 1 alone is not the contract: ``implement`` exits 1 for many
        unrelated reasons. The contract is "no fallback" -- the unresolved ref is
        named in the error and no lane branch or worktree is created from it.
        Drives the real command against a real git repository; nothing in the
        implement command family is patched.
        """
        repo = init_repo(tmp_path / "repo")
        activate_repo(repo, monkeypatch, tmp_path)
        build_mission(repo, SLUG, MISSION_ID)

        result = implement_cli(*ARGS, "--base", "totally-bogus-ref-xyz")

        assert result.exit_code == 1, f"Expected exit code 1 for invalid ref, got {result.exit_code}: {result.output}"
        message = " ".join(result.output.split())
        assert "Base ref 'totally-bogus-ref-xyz' does not resolve" in message, message

        assert git(repo, "branch", "--list", LANE_BRANCH) == "", "no lane branch may be created from an unresolved --base"
        assert not (repo / LANE_WORKTREE).exists()
