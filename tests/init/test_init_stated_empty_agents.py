"""`init` re-runs on a project that states no CLI-managed agents (#6493).

A project whose `.kittify/config.yaml` states `agents: {available: []}` has said
that Spec Kitty manages none of its agent surfaces (#6494) — the shape a
plugin-installed project has. Re-running `init` there used to claim it had
verified/restored command surfaces it never touched, and `init --ai claude` exited 1
telling the operator to add the agent, which writes a second copy of every command
surface the plugin already supplies. Both must instead recognise the project as set
up. The #4425 diagnosis for a *listed* agent with missing command skills stays.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands.init import register_init_command

pytestmark = [pytest.mark.integration]

_STATED_EMPTY_CONFIG = "agents:\n  available: []\n  auto_commit: true\n"


def _make_app() -> tuple[Typer, io.StringIO]:
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


def _run(app: Typer, buf: io.StringIO, args: list[str]) -> tuple[object, str]:
    """Invoke *args*, returning the result and the text the injected console wrote.

    ``init`` writes through the console injected by ``register_init_command``, so the
    assertions must read that buffer; ``result.output`` stays empty and asserting on
    it would make every message check vacuously pass.
    """
    result = CliRunner().invoke(app, args, catch_exceptions=True)
    return result, _flat(buf.getvalue())


def _flat(output: str) -> str:
    return " ".join(output.split())


def _project(tmp_path: Path, config_body: str) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    config = tmp_path / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(config_body, encoding="utf-8")
    mission = tmp_path / "kitty-specs" / "existing" / "spec.md"
    mission.parent.mkdir(parents=True)
    mission.write_text("Keep existing mission", encoding="utf-8")
    return config


def _skill_tree(root: Path) -> dict[Path, bytes]:
    """Every CLI-managed command-skill file, for a writes-nothing comparison."""
    return {path.relative_to(root): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file() and path.parts[0] in {".agents", ".claude", ".codex"}}


def test_init_rerun_on_stated_empty_project_claims_no_verification(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """FR-003: exit 0, no "verified" claim, and name the stated no-CLI-managed state."""
    _project(tmp_path, _STATED_EMPTY_CONFIG)
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app()

    result, output = _run(app, buf, ["init", "--non-interactive"])
    assert result.exit_code == 0, result.output
    assert "Agent skill surfaces were verified" not in output
    assert "no cli-managed agents" in output.lower()


def test_init_rerun_with_ai_ignores_the_flag_and_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """FR-004/FR-006/SC-002: the stated list wins, nothing installed, exit 0."""
    config = _project(tmp_path, _STATED_EMPTY_CONFIG)
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app()
    before = _skill_tree(tmp_path)

    result, output = _run(app, buf, ["init", "--ai", "claude", "--non-interactive"])
    assert result.exit_code == 0, result.output
    assert "no cli-managed agents" in output.lower()
    assert "--ai claude was ignored" in output
    assert "Initialization incomplete" not in output
    assert "Requested agents are not configured" not in output
    assert _skill_tree(tmp_path) == before
    assert config.read_text(encoding="utf-8") == _STATED_EMPTY_CONFIG


def test_init_rerun_still_fails_for_a_listed_agent_with_missing_skills(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """FR-007 ratchet: the #4425 diagnosis is not swallowed by the new branch."""
    _project(tmp_path, "agents:\n  available: [codex]\n")
    monkeypatch.chdir(tmp_path)
    app, buf = _make_app()

    result, output = _run(app, buf, ["init", "--non-interactive"])
    assert result.exit_code == 1, result.output
    assert "spec-kitty agent config sync --create-missing --keep-orphaned" in output
    assert not (tmp_path / ".agents/skills/spec-kitty-specify").exists()
