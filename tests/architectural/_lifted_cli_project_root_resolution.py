"""Single home of the project-root resolution and git-failure rendering tests (#5015).

``tests/specify_cli/cli/test_helpers.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_cli_project_root_resolution.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.helpers import get_project_root_or_exit


def test_get_project_root_or_exit_succeeds_in_worktree(tmp_path: Path) -> None:
    """get_project_root_or_exit returns main repo root when called from a git worktree."""
    main_repo = tmp_path / "main_repo"
    (main_repo / ".kittify").mkdir(parents=True)
    worktrees_dir = main_repo / ".git" / "worktrees" / "test_lane"
    worktrees_dir.mkdir(parents=True)

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {worktrees_dir}\n")

    result = get_project_root_or_exit(start=worktree)
    assert result == main_repo


def test_exit_git_resolution_failure_exits_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The human render prints the message and exits 1 (no traceback)."""
    import io

    import typer
    from rich.console import Console

    from charter.resolution import NotInsideRepositoryError
    from specify_cli.cli import helpers as helpers_mod
    from specify_cli.cli.helpers import exit_git_resolution_failure

    buf = io.StringIO()
    monkeypatch.setattr(helpers_mod, "console", Console(file=buf, force_terminal=False, highlight=False))

    with pytest.raises(typer.Exit) as excinfo:
        exit_git_resolution_failure(NotInsideRepositoryError(tmp_path), tmp_path)

    assert excinfo.value.exit_code == 1
    assert "git init" in buf.getvalue()


def test_exit_git_resolution_failure_json_envelope(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The --json render emits one canonical error envelope on stdout."""
    import json

    import typer

    from charter.resolution import NotInsideRepositoryError
    from specify_cli.cli.helpers import exit_git_resolution_failure

    with pytest.raises(typer.Exit) as excinfo:
        exit_git_resolution_failure(NotInsideRepositoryError(tmp_path), tmp_path, json_output=True)

    assert excinfo.value.exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    envelope = json.loads(captured.out)
    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "git_resolution_failed"
    assert "git init" in envelope["error"]["message"]
