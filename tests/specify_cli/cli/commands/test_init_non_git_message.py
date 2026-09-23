"""Tests for FR-005 (#636): non-git target message in `spec-kitty init`.

Canonical invariant (Decision Moment 01KQ84P1AJ8H3FPJN9J5C12CBY):
non-git init is allowed; silent non-git init is not. The command MUST:
- complete the scaffold (exit 0, populate `.kittify/`, etc.)
- NOT auto-run `git init`
- NOT bail out before writing files
- Loudly emit the actionable message
"""

from __future__ import annotations

import io
import re
import subprocess
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult


pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

NOT_A_GIT_REPO = re.compile(r"not\s+a\s+git\s+repository", re.IGNORECASE)
GIT_INIT_HINT = re.compile(r"\bgit\s+init\b", re.IGNORECASE)


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


@pytest.fixture()
def cli_app() -> tuple[Typer, Console]:
    """Return a minimal Typer app with init registered and heavy I/O mocked."""
    console = Console(file=io.StringIO(), force_terminal=False)
    app = Typer()
    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app, console


def test_init_in_non_git_dir_emits_actionable_message(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-005: non-git target prints the actionable message and does NOT auto-init git.

    Verifies the canonical invariant: scaffold completes (exit 0), `.git/` is
    not created by spec-kitty, and the output mentions both "not a git
    repository" and "git init".
    """
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    target = tmp_path / "demo"

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["init", str(target), "--ai", "claude", "--non-interactive"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output

    # The Rich console is wired to a StringIO buffer; read both that and
    # the CliRunner-captured stdout so we don't miss either surface.
    console_output = console.file.getvalue() if hasattr(console.file, "getvalue") else ""
    output = result.output + "\n" + console_output

    assert NOT_A_GIT_REPO.search(output), (
        f"Expected 'not a git repository' in output, got:\n{output}"
    )
    assert GIT_INIT_HINT.search(output), (
        f"Expected 'git init' guidance in output, got:\n{output}"
    )
    assert "1. Enter the project:" in output
    assert "2. Required:" in output
    assert "Git: not initialized" in output
    assert "spec-kitty dashboard" in output
    assert output.index("spec-kitty dashboard") > output.index("Optional")

    # Scaffold completed: .kittify/ exists, .git/ was NOT auto-created.
    assert (target / ".kittify").is_dir()
    assert not (target / ".git").exists()


def test_init_in_existing_git_repo_does_not_emit_non_git_message(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """FR-005 negative case: no false-positive 'not a git repository' message.

    When the target lives inside an existing git work tree, the new info
    line MUST NOT appear (and the post-init "Run git init" bullet must not
    appear either).
    """
    # Arrange: tmp_path is a git repo
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    target = tmp_path / "demo"

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["init", str(target), "--ai", "claude", "--non-interactive"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output

    console_output = console.file.getvalue() if hasattr(console.file, "getvalue") else ""
    output = result.output + "\n" + console_output

    assert not NOT_A_GIT_REPO.search(output), (
        f"Did not expect 'not a git repository' in output, got:\n{output}"
    )
    assert "Git: ready" in output
