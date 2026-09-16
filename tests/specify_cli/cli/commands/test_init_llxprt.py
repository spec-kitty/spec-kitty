"""Integration tests for spec-kitty init --ai llxprt.

LLxprt Code is a slash-command agent (a fork of Gemini CLI), so its commands are
rendered as TOML files into the user-global command root (the
envPaths('llxprt-code') config dir, ``~/Library/Preferences/llxprt-code/commands/``
on macOS, overridable via ``LLXPRT_CONFIG_HOME``). LLxprt
also consumes ``SKILL.md`` Agent Skills from ``.agents/skills/`` and
``.llxprt/skills/``, but that is a separate surface which ``init`` does not
install; these tests cover the command surface only.
"""

from __future__ import annotations

import io
import sys
import tomllib
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner, Result

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.core.agent_config import load_agent_config
from specify_cli.core.config import AGENT_COMMAND_CONFIG
from specify_cli.runtime.agent_commands import get_global_command_dir
from specify_cli.template.asset_generator import render_command_template

pytestmark = pytest.mark.integration

TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "packs" / "built-in" / "missions" / "mission-steps" / "software-dev"


def _make_app() -> tuple[Typer, io.StringIO]:
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False)
    app = Typer()

    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )
    return app, buf


def _run(app: Typer, args: list[str]) -> Result:
    return CliRunner().invoke(app, args, catch_exceptions=True)


def _fake_copy_package(project_path: Path) -> Path:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return kittify / "templates" / "command-templates"


def _render_llxprt(command: str) -> str:
    """Render *command* for llxprt through the production command-file path."""
    config = AGENT_COMMAND_CONFIG["llxprt"]
    return render_command_template(
        template_path=TEMPLATES_DIR / command / "prompt.md",
        script_type="sh",
        agent_key="llxprt",
        arg_format=str(config["arg_format"]),
        extension=str(config["ext"]),
    )


def test_init_llxprt_registers_agent_and_gitignores_directory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    app, output = _make_app()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "llxprt-proj", "--ai", "llxprt", "--non-interactive"])

    assert result.exit_code == 0, result.output
    project_path = tmp_path / "llxprt-proj"
    assert "llxprt" in load_agent_config(project_path).available

    gitignore_lines = (project_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".llxprt/" in gitignore_lines

    assert "/spec-kitty.specify" in output.getvalue()


@pytest.mark.skipif(sys.platform == "win32", reason="Windows APPDATA resolution is not exercised")
def test_llxprt_global_command_dir_is_platform_config_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The user-global root resolves via envPaths('llxprt-code'), not ~/.llxprt."""
    monkeypatch.delenv("LLXPRT_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    if sys.platform == "darwin":
        expected = Path.home() / "Library" / "Preferences" / "llxprt-code" / "commands"
    else:
        expected = Path.home() / ".config" / "llxprt-code" / "commands"

    assert get_global_command_dir("llxprt") == expected


@pytest.mark.parametrize("command", ["specify", "plan", "tasks"])
def test_llxprt_commands_render_as_valid_toml(command: str) -> None:
    """Rendered llxprt command files parse as TOML with the v1 command schema."""
    produced = _render_llxprt(command)

    parsed = tomllib.loads(produced)
    assert isinstance(parsed.get("prompt"), str) and parsed["prompt"].strip()
    assert isinstance(parsed.get("description"), str) and parsed["description"].strip()


def test_llxprt_prompt_carries_gemini_style_arg_placeholder() -> None:
    """LLxprt inherits Gemini CLI's ``{{args}}`` substitution semantics."""
    parsed = tomllib.loads(_render_llxprt("specify"))
    assert "{{args}}" in parsed["prompt"]
    assert "$ARGUMENTS" not in parsed["prompt"]


def test_llxprt_uses_the_same_toml_schema_as_gemini() -> None:
    """LLxprt is a Gemini CLI fork, so both hosts get the same TOML key set."""
    gemini_config = AGENT_COMMAND_CONFIG["gemini"]
    gemini = render_command_template(
        template_path=TEMPLATES_DIR / "specify" / "prompt.md",
        script_type="sh",
        agent_key="gemini",
        arg_format=str(gemini_config["arg_format"]),
        extension=str(gemini_config["ext"]),
    )

    assert tomllib.loads(gemini).keys() == tomllib.loads(_render_llxprt("specify")).keys()
