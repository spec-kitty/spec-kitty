"""Integration tests for spec-kitty init --ai pi/letta."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult
from specify_cli.core.agent_config import load_agent_config
from specify_cli.skills.command_installer import CANONICAL_COMMANDS

pytestmark = pytest.mark.integration


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


def _run(app: Typer, args: list[str]) -> object:
    return CliRunner().invoke(app, args, catch_exceptions=True)


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


@pytest.mark.parametrize(
    ("agent_key", "agent_dir", "install_snippet", "usage_snippet"),
    [
        ("pi", ".pi/", "https://pi.dev/install.sh", "/skill:spec-kitty.specify"),
        ("letta", ".letta/", "@letta-ai/letta-code", "/spec-kitty.specify"),
    ],
)
def test_init_pi_letta_installs_command_skills_and_prints_next_steps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    agent_key: str,
    agent_dir: str,
    install_snippet: str,
    usage_snippet: str,
) -> None:
    app, output = _make_app()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", f"{agent_key}-proj", "--ai", agent_key, "--non-interactive"])

    assert result.exit_code == 0, result.output
    project_path = tmp_path / f"{agent_key}-proj"
    assert agent_key in load_agent_config(project_path).available

    skills_root = project_path / ".agents" / "skills"
    for command in CANONICAL_COMMANDS:
        assert (skills_root / f"spec-kitty.{command}" / "SKILL.md").is_file()

    manifest = json.loads(
        (project_path / ".kittify" / "command-skills-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(manifest["entries"]) == len(CANONICAL_COMMANDS)
    for entry in manifest["entries"]:
        assert entry["agents"] == [agent_key]

    gitignore_lines = (project_path / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert agent_dir in gitignore_lines

    rendered = output.getvalue()
    assert install_snippet in rendered
    assert usage_snippet in rendered
