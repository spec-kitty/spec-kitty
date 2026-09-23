"""Regression tests: init next-steps output is concise and actionable.

Verifies:
- Captured output contains "spec-kitty next"
- Non-git targets promote git init as the required next action
- Captured output does NOT contain "spec-kitty implement WP" (bare top-level CLI)
- The literal string "Initial commit from Specify template" is absent from src/

NOTE: The init command writes to an *injected* console (not stdout), so we read
from the buffer that backs that console, not from result.output.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]

def _make_app_with_buf() -> tuple[Typer, io.StringIO]:
    """Return a minimal Typer app and the buffer backing the injected console."""
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, highlight=False)
    app = Typer()

    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app, buf


def _run(app: Typer, args: list[str]) -> object:
    runner = CliRunner()
    return runner.invoke(app, args, catch_exceptions=True)


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


# ---------------------------------------------------------------------------
# T1.4: Next-steps output names spec-kitty next + first workflow path
# ---------------------------------------------------------------------------

def test_init_next_steps_names_spec_kitty_next(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """T1.4: init output contains a concise first-run path and mission loop.

    Also asserts old dense per-WP command catalog entries are absent.
    """
    app, buf = _make_app_with_buf()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "next-steps-proj", "--ai", "codex", "--non-interactive"])

    assert result.exit_code == 0, f"init failed (exit_code={result.exit_code})"

    # Output goes to the injected console buffer, not result.output
    output = buf.getvalue()

    # The canonical loop entry must appear
    assert "spec-kitty next" in output, (
        "Expected 'spec-kitty next' in init console output, but it was absent.\n"
        f"Actual console output:\n{output}"
    )

    assert "$spec-kitty.specify" in output, (
        "Codex init next steps must use Codex skill invocation syntax.\n"
        f"Actual console output:\n{output}"
    )
    assert "$spec-kitty.plan" in output
    assert "$spec-kitty.tasks" in output
    assert "Required:" in output
    assert "git init" in output
    assert "4. Run the mission loop" in output
    assert "5." not in output

    # #4123: both non-git warning surfaces name the full affected command
    # set, not just "agent" — the user's next command after init is often
    # `dashboard` or `dispatch`, and those need git too. Whitespace and the
    # next-steps panel's ``│`` borders are normalized out because Rich wraps
    # these long lines at console width.
    flat_output = " ".join(output.replace("│", " ").split())
    assert "Target is not a git repository." in flat_output, (
        "Expected the non-git VCS warning in init console output.\n"
        f"Actual console output:\n{output}"
    )
    assert "`spec-kitty agent`, `dashboard`, `dispatch`, `next`, or `implement` commands" in flat_output, (
        "The non-git VCS warning must name the full affected command set (#4123).\n"
        f"Actual console output:\n{output}"
    )
    assert "agent, dashboard, dispatch, next, and implement commands" in flat_output, (
        "The required next-step must name the full affected command set (#4123).\n"
        f"Actual console output:\n{output}"
    )

    assert "/spec-kitty.dashboard" not in output, (
        "Codex init next steps must not list slash commands that are not installed as command skills.\n"
        f"Actual console output:\n{output}"
    )

    # The bare top-level CLI invocation must NOT appear
    assert "spec-kitty implement WP" not in output, (
        "Found forbidden string 'spec-kitty implement WP' in init console output — "
        "this is the old top-level CLI path and must not appear.\n"
        f"Actual console output:\n{output}"
    )
    assert "spec-kitty agent action implement" not in output


def test_init_letta_next_steps_use_slash_skill_syntax(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app, buf = _make_app_with_buf()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "letta-proj", "--ai", "letta", "--non-interactive"])

    assert result.exit_code == 0, f"init failed (exit_code={result.exit_code})"

    output = buf.getvalue()
    assert "/spec-kitty.specify" in output
    assert "Use spec-kitty.specify" not in output


def test_init_vibe_next_steps_list_only_installed_command_skills(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    app, buf = _make_app_with_buf()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "vibe-proj", "--ai", "vibe", "--non-interactive"])

    assert result.exit_code == 0, f"init failed (exit_code={result.exit_code})"

    output = buf.getvalue()
    assert "Build with command skills" in output
    assert "/spec-kitty.specify" in output
    assert "/spec-kitty.plan" in output
    assert "/spec-kitty.tasks" in output
    assert "/spec-kitty.dashboard" not in output
    assert "/spec-kitty.accept" not in output
    assert "/spec-kitty.merge" not in output


# ---------------------------------------------------------------------------
# T1.4b: The literal commit string must be absent from src/
# ---------------------------------------------------------------------------

def test_init_commit_string_absent_from_source() -> None:
    """T1.4b: The literal string 'Initial commit from Specify template' must not exist in src/.

    This ensures T001 (remove git side-effects) is complete and cannot regress.
    """
    forbidden = "Initial commit from Specify template"

    # src/ is two levels above tests/init/
    src_dir = Path(__file__).parent.parent.parent / "src"
    assert src_dir.is_dir(), f"src/ directory not found at {src_dir}"

    matches: list[Path] = []
    for path in src_dir.rglob("*.py"):
        try:
            if forbidden in path.read_text(encoding="utf-8", errors="replace"):
                matches.append(path)
        except OSError:
            pass

    assert matches == [], (
        f"Found forbidden literal string {forbidden!r} in source files:\n"
        + "\n".join(f"  {p}" for p in matches)
        + "\nThis string was removed as part of T001 (init coherence). "
        "A regression has reintroduced it."
    )
