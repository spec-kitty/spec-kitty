"""T1.7 — Regression tests: init --help output.

Verifies:
- --help does not show --no-git option
- --help mentions spec-kitty next
- Passing --no-git to init gives a typer "no such option" error
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands.init import register_init_command


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]


@pytest.fixture()
def init_app() -> Typer:
    """Return a minimal Typer app with the init command registered."""
    app = Typer()
    console = Console(file=io.StringIO(), force_terminal=False)

    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app


# ---------------------------------------------------------------------------
# T1.7a: --help does not show --no-git
# ---------------------------------------------------------------------------


def test_init_help_does_not_show_no_git_flag(init_app: Typer) -> None:
    """T1.7a: --help Options panel must not list '--no-git' as an available option.

    The help docstring may mention '--no-git' to explain it was removed in a
    previous version, but the Options panel must not offer it as a flag.
    """
    runner = CliRunner()
    result = runner.invoke(init_app, ["init", "--help"])

    assert result.exit_code == 0, f"--help failed: {result.output}"

    # Parse the Options section from the help output.  We look for lines that
    # start with whitespace + "--" (actual option declarations in the table).
    option_lines = [line for line in result.output.splitlines() if line.strip().startswith("--")]
    option_flags = "\n".join(option_lines)

    assert "--no-git" not in option_flags, (
        "Found '--no-git' listed as an option in the init --help Options panel. "
        "This option was removed in the post-#555 init-coherence change (T001). "
        f"\nOptions declared in --help:\n{option_flags}"
    )


# ---------------------------------------------------------------------------
# T1.7b: --help mentions spec-kitty next
# ---------------------------------------------------------------------------


def test_init_help_mentions_spec_kitty_next(init_app: Typer) -> None:
    """T1.7b: --help output must reference the canonical post-#555 workflow."""
    runner = CliRunner()
    result = runner.invoke(init_app, ["init", "--help"])

    assert result.exit_code == 0, f"--help failed: {result.output}"
    assert "spec-kitty next" in result.output, (
        f"init --help should describe 'spec-kitty next' as the canonical next step, but it was absent from help output.\nActual help output:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# T1.7c: Passing --no-git gives "no such option" error
# ---------------------------------------------------------------------------


def test_passing_no_git_flag_gives_error(
    init_app: Typer,
    tmp_path: Path,
) -> None:
    """T1.7c: Passing --no-git must result in a non-zero exit (typer 'no such option').

    This is an intentional breaking change. Users passing --no-git after this
    WP lands will get a typer error — that is the correct behavior.
    """
    runner = CliRunner()
    result = runner.invoke(
        init_app,
        ["init", "--no-git", str(tmp_path), "--ai", "codex", "--non-interactive"],
        catch_exceptions=True,
    )

    assert result.exit_code != 0, (
        f"Expected non-zero exit code when passing --no-git (option was removed), but got exit_code={result.exit_code}.\nOutput:\n{result.output}"
    )


# ---------------------------------------------------------------------------
# T1.7d: --help states the re-run diagnostic/restore contract (#4425)
# ---------------------------------------------------------------------------


def test_init_help_states_rerun_skill_contract(init_app: Typer) -> None:
    """T1.7d: --help must not claim a re-run always exits cleanly (#4425 acceptance 6).

    A re-run verifies agent skill surfaces: missing per-agent skill roots are
    restored, and missing shared command skills exit 1 with the recovery
    command. The old "exits cleanly (idempotent)" line described a contract
    the command no longer offers.
    """
    runner = CliRunner()
    result = runner.invoke(init_app, ["init", "--help"])

    assert result.exit_code == 0, f"--help failed: {result.output}"
    flattened = " ".join(result.output.split())
    assert "exits cleanly (idempotent)" not in flattened
    assert "spec-kitty agent config sync --create-missing --keep-orphaned" in flattened
    assert ".claude/skills/" in flattened
