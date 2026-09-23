"""Integration tests for spec-kitty init --ai vibe.

Tests cover T026 of WP05: end-to-end init for Mistral Vibe, including
config.yaml, gitignore, printed next-steps, and idempotency.
"""

from __future__ import annotations

import io
import tomllib
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult
from specify_cli.core.agent_config import load_agent_config

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_app() -> tuple[Typer, Console]:
    """Return a minimal Typer app with init registered and heavy I/O mocked."""
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
    return app, console


def _run(app: Typer, args: list[str]) -> object:
    runner = CliRunner()
    return runner.invoke(app, args, catch_exceptions=True)


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


# ---------------------------------------------------------------------------
# T026-A: end-to-end init exits 0
# ---------------------------------------------------------------------------


def test_init_vibe_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """spec-kitty init --ai vibe --non-interactive exits 0 on a clean tmpdir."""
    app, console = _make_app()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "vibe-proj", "--ai", "vibe", "--non-interactive"])

    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# T026-B: config.yaml has vibe in agents.available
# ---------------------------------------------------------------------------


def test_init_vibe_config_yaml(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """config.yaml must have 'vibe' in agents.available after init."""
    app, console = _make_app()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "cfg-proj", "--ai", "vibe", "--non-interactive"])
    assert result.exit_code == 0, result.output

    project_path = tmp_path / "cfg-proj"
    agent_config = load_agent_config(project_path)
    assert "vibe" in agent_config.available


# ---------------------------------------------------------------------------
# Integration: init --ai vibe actually installs the command-skill packages
# (post-mission-review regression guard: the mission's headline promise is
# that Vibe users can invoke /spec-kitty.specify in their TUI, which requires
# SKILL.md files to exist under .agents/skills/ after init.)
# ---------------------------------------------------------------------------


def test_init_vibe_installs_command_skills(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """init --ai vibe must write SKILL.md for every canonical command."""
    from specify_cli.skills.command_installer import CANONICAL_COMMANDS

    app, console = _make_app()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "skill-proj", "--ai", "vibe", "--non-interactive"])
    assert result.exit_code == 0, result.output

    project_path = tmp_path / "skill-proj"
    skills_root = project_path / ".agents" / "skills"
    assert skills_root.is_dir(), ".agents/skills/ was not created"

    # Every canonical command must produce a SKILL.md.
    for command in CANONICAL_COMMANDS:
        skill_md = skills_root / f"spec-kitty.{command}" / "SKILL.md"
        assert skill_md.is_file(), f"Missing {skill_md.relative_to(project_path)}"

    # Ownership manifest must record each install with agents=["vibe"].
    manifest_file = project_path / ".kittify" / "command-skills-manifest.json"
    assert manifest_file.is_file(), ".kittify/command-skills-manifest.json was not created"
    import json

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert len(manifest["entries"]) == len(CANONICAL_COMMANDS)
    for entry in manifest["entries"]:
        assert entry["agents"] == ["vibe"], entry

    vibe_config = project_path / ".vibe" / "config.toml"
    assert vibe_config.is_file(), ".vibe/config.toml was not created"
    with vibe_config.open("rb") as fh:
        vibe_data = tomllib.load(fh)
    assert vibe_data["skill_paths"] == [".agents/skills"]


# ---------------------------------------------------------------------------
# T026-C: .gitignore contains .vibe/
# ---------------------------------------------------------------------------


def test_init_vibe_gitignore(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """.gitignore must contain a .vibe/ or .vibe line after init --ai vibe."""
    app, console = _make_app()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "gi-proj", "--ai", "vibe", "--non-interactive"])
    assert result.exit_code == 0, result.output

    gitignore = tmp_path / "gi-proj" / ".gitignore"
    assert gitignore.exists(), ".gitignore was not created"
    content = gitignore.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in content.splitlines()]
    assert any(ln in (".vibe/", ".vibe") for ln in lines), (
        f".vibe/ not found in .gitignore; got:\n{content}"
    )


# ---------------------------------------------------------------------------
# T026-D: printed output contains Vibe install URL and /spec-kitty.specify
# ---------------------------------------------------------------------------


def test_init_vibe_next_steps_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Printed output must mention mistral-vibe and /spec-kitty.specify."""
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
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result = _run(app, ["init", "ns-proj", "--ai", "vibe", "--non-interactive"])
    assert result.exit_code == 0, result.output

    output = buf.getvalue()
    assert "mistral-vibe" in output, (
        f"Install command not found in output; got:\n{output[:500]}"
    )
    assert "/spec-kitty.specify" in output, (
        f"/spec-kitty.specify not found in output; got:\n{output[:500]}"
    )


# ---------------------------------------------------------------------------
# T026-E: idempotent — second run succeeds, no state corruption
# ---------------------------------------------------------------------------


def test_init_vibe_idempotent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Running init --ai vibe twice in-place: second run exits 0 (already-initialized)."""
    # First run: init in tmp_path directly (chdir into it, no project name arg)
    app, console = _make_app()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result1 = _run(app, ["init", "--ai", "vibe", "--non-interactive"])
    assert result1.exit_code == 0, result1.output

    # Second run in the same directory should exit 0 (already-initialized early return)
    result2 = _run(app, ["init", "--ai", "vibe", "--non-interactive"])
    assert result2.exit_code == 0, result2.output

    # Config must still have vibe (from first run)
    agent_config = load_agent_config(tmp_path)
    assert "vibe" in agent_config.available


# ---------------------------------------------------------------------------
# T026-F: no vibe binary required — init must not shell out to vibe
# ---------------------------------------------------------------------------


def test_init_vibe_no_binary_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Init must succeed even when 'vibe' is not on PATH."""
    import shutil as _shutil

    app, console = _make_app()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    original_which = _shutil.which

    def _no_vibe(name: str, *args: object, **kwargs: object) -> str | None:
        if name == "vibe":
            return None
        return original_which(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(_shutil, "which", _no_vibe)

    result = _run(app, ["init", "nobinary-proj", "--ai", "vibe", "--non-interactive"])
    assert result.exit_code == 0, result.output
