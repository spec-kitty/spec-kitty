"""Tests for deterministic git preflight checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from specify_cli.core.git_preflight import (
    build_git_preflight_failure_payload,
    run_git_preflight,
)

pytestmark = pytest.mark.git_repo

def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=path, check=True, capture_output=True)
    (path / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)


def test_run_git_preflight_blocks_non_repo(tmp_path: Path) -> None:
    result = run_git_preflight(tmp_path)
    assert not result.passed
    assert result.first_error is not None
    assert result.first_error.code == "NOT_A_GIT_REPOSITORY"
    assert "git status" in (result.first_error.command or "")


def test_run_git_preflight_missing_origin_is_warning(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)

    result = run_git_preflight(repo)

    assert result.passed
    assert any(issue.code == "MISSING_ORIGIN_REMOTE" for issue in result.warnings)


@dataclass
class _FakeCmdResult:
    returncode: int
    stdout: str
    stderr: str


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("fatal: detected dubious ownership in repository at '/srv/checkout'", True),
        (
            "fatal: unsafe repository ('/srv/checkout' is owned by someone else)\n"
            "to add an exception for this directory, call: safe.directory",
            True,
        ),
        ("fatal: not a git repository (or any of the parent directories): .git", False),
        ("", False),
        pytest.param(
            "fatal: not a git repository: /nonexistent/safe.directory/gitdir",
            False,
            id="path-word-not-ownership",
        ),
        pytest.param(
            "\tgit config --global --add safe.directory /srv/checkout",
            True,
            id="ownership-exception-hint",
        ),
    ],
)
def test_the_ownership_refusal_predicate_has_one_owner(stderr: str, expected: bool) -> None:
    """`kernel.git.refuses_ownership` is the single classifier git_preflight consumes.

    Ownership diagnosis lines and the explicit exception hint are signals; words in an
    echoed non-repository path are not. Positive and negative cases share one parametrization
    so a probe that always answers True (or always False) cannot pass.
    """
    from kernel.git import refuses_ownership

    assert refuses_ownership(stderr) is expected


def test_run_git_preflight_detects_dubious_ownership(tmp_path: Path) -> None:
    dubious = _FakeCmdResult(
        returncode=128,
        stdout="",
        stderr="fatal: detected dubious ownership in repository at '/nonexistent/repo'",
    )
    with patch("specify_cli.core.git_preflight._run_git", return_value=dubious):
        result = run_git_preflight(tmp_path)

    assert not result.passed
    assert result.first_error is not None
    assert result.first_error.code == "UNTRUSTED_REPOSITORY"
    assert "safe.directory" in (result.first_error.command or "")


def test_run_git_preflight_detects_worktree_listing_failure(tmp_path: Path) -> None:
    responses = iter(
        [
            _FakeCmdResult(returncode=0, stdout="true\n", stderr=""),
            _FakeCmdResult(returncode=1, stdout="", stderr="fatal: could not list worktrees"),
        ]
    )
    with patch("specify_cli.core.git_preflight._run_git", side_effect=lambda *_args, **_kwargs: next(responses)):
        result = run_git_preflight(tmp_path, check_worktree_list=True)

    assert not result.passed
    assert result.first_error is not None
    assert result.first_error.code == "WORKTREE_LIST_FAILED"


def test_run_git_preflight_detects_dubious_ownership_in_worktree_listing(tmp_path: Path) -> None:
    """Worktree listing dubious-ownership error should be reported as UNTRUSTED_REPOSITORY."""
    responses = iter(
        [
            _FakeCmdResult(returncode=0, stdout="true\n", stderr=""),
            _FakeCmdResult(
                returncode=128,
                stdout="",
                stderr="fatal: detected dubious ownership in repository at '/nonexistent/repo'",
            ),
        ]
    )
    with patch("specify_cli.core.git_preflight._run_git", side_effect=lambda *_args, **_kwargs: next(responses)):
        result = run_git_preflight(tmp_path, check_worktree_list=True)

    assert not result.passed
    assert result.first_error is not None
    assert result.first_error.code == "UNTRUSTED_REPOSITORY"
    assert result.first_error.check == "repository_trust"
    assert "safe.directory" in (result.first_error.command or "")


def test_run_git_handles_file_not_found(tmp_path: Path) -> None:
    """_run_git should return code 127 when git executable is missing."""
    from specify_cli.core.git_preflight import _run_git

    with patch("specify_cli.core.git_preflight.subprocess.run", side_effect=FileNotFoundError("git")):
        cmd_result = _run_git(tmp_path, ["status"])

    assert cmd_result.returncode == 127
    assert "not found" in cmd_result.stderr


def test_run_git_handles_timeout(tmp_path: Path) -> None:
    """_run_git should return code 124 when command times out."""
    from specify_cli.core.git_preflight import _run_git

    with patch(
        "specify_cli.core.git_preflight.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="git status", timeout=15),
    ):
        cmd_result = _run_git(tmp_path, ["status"])

    assert cmd_result.returncode == 124
    assert "timed out" in cmd_result.stderr


def test_first_line_returns_empty_for_blank_text() -> None:
    """_first_line should return empty string for whitespace-only input."""
    from specify_cli.core.git_preflight import _first_line

    assert _first_line("") == ""
    assert _first_line("   \n  \n") == ""


def test_build_git_preflight_failure_payload_contains_remediation(tmp_path: Path) -> None:
    result = run_git_preflight(tmp_path)
    payload = build_git_preflight_failure_payload(result, command_name="spec-kitty merge")

    assert payload["error_code"] == "GIT_PREFLIGHT_FAILED"
    assert payload["command"] == "spec-kitty merge"
    assert isinstance(payload["remediation"], list)


def test_build_git_preflight_failure_payload_no_errors(tmp_path: Path) -> None:
    """Payload should still be valid when there are no errors (defensive)."""
    from specify_cli.core.git_preflight import GitPreflightResult

    result = GitPreflightResult(repo_root=tmp_path)
    payload = build_git_preflight_failure_payload(result, command_name="test")

    assert payload["error"] == "Git preflight failed."
    assert payload["remediation"] == []
