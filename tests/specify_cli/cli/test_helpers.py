"""Integration tests for specify_cli.cli.helpers — T007.

Verifies that get_project_root_or_exit correctly resolves the main repo root
when called from a git worktree, exercising the real delegation chain through
the project_resolver shim → paths.locate_project_root (no mocking of the
resolver).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# The tests and helpers shared with this suite's always-on lift live once, in
# ``tests/architectural/_lifted_cli_project_root_resolution.py`` (#5015); importing a test is what makes pytest collect it here.
from tests.architectural._lifted_cli_project_root_resolution import (
    test_get_project_root_or_exit_succeeds_in_worktree as test_get_project_root_or_exit_succeeds_in_worktree,
)
from tests.architectural._lifted_cli_project_root_resolution import test_exit_git_resolution_failure_exits_1 as test_exit_git_resolution_failure_exits_1
from tests.architectural._lifted_cli_project_root_resolution import test_exit_git_resolution_failure_json_envelope as test_exit_git_resolution_failure_json_envelope

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# #4123: git-resolution failure rendering (never-git-init-ed projects)
# ---------------------------------------------------------------------------


def test_git_resolution_failure_message_names_git_init(
    tmp_path: Path,
) -> None:
    """NotInsideRepositoryError maps to the actionable git-init advice."""
    from charter.resolution import NotInsideRepositoryError

    from specify_cli.cli.helpers import git_resolution_failure_message

    message = git_resolution_failure_message(NotInsideRepositoryError(tmp_path), tmp_path)

    assert "not inside a git repository" in message
    assert "git init" in message
    assert str(tmp_path) in message
    # The old misdirection (tell the user to re-run init) must stay absent.
    assert "spec-kitty init ." not in message


def test_git_resolution_failure_message_passes_unavailable_detail_through(
    tmp_path: Path,
) -> None:
    """GitCommonDirUnavailableError keeps its own recovery text verbatim."""
    from charter.resolution import GitCommonDirUnavailableError

    from specify_cli.cli.helpers import git_resolution_failure_message

    exc = GitCommonDirUnavailableError(tmp_path, "no git binary on PATH")
    message = git_resolution_failure_message(exc, tmp_path)

    assert "no git binary on PATH" in message
    assert "git init" not in message
