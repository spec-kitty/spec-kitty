"""T1.5 — Regression tests: init idempotency on re-run.

Verifies:
- Running init twice in the same directory exits 0 (idempotent).
- The second run does NOT silently merge or overwrite state.
- A clear "Already initialized" message appears (in the injected console output).
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path

import pytest
from rich.console import Console
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.integration]

def _make_app_with_buf() -> tuple[Typer, io.StringIO]:
    """Return app and the buffer backing the injected console."""
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


def _fake_copy_package(project_path: Path) -> Path:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return kittify / "templates" / "command-templates"


# ---------------------------------------------------------------------------
# T1.5: Idempotency check
# ---------------------------------------------------------------------------

def test_init_is_idempotent_on_rerun(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """T1.5: Running init twice exits 0 on both runs (idempotent).

    The second run must NOT silently merge or overwrite state — it exits
    cleanly with an "Already initialized" message in console output.
    """
    # First run — fresh directory
    app1, buf1 = _make_app_with_buf()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    result1 = _run(app1, ["init", "--ai", "codex", "--non-interactive"])
    assert result1.exit_code == 0, f"First init failed (exit_code={result1.exit_code})"

    # Record state after first run
    config_path = tmp_path / ".kittify" / "config.yaml"
    assert config_path.exists(), "config.yaml should exist after first init"
    config_content_after_first = config_path.read_text(encoding="utf-8")

    # Second run — already-initialized directory; use a fresh app/buffer
    app2, buf2 = _make_app_with_buf()
    result2 = _run(app2, ["init", "--ai", "codex", "--non-interactive"])

    # Must exit 0 (idempotent path, not fail-fast)
    assert result2.exit_code == 0, (
        f"Second init should exit 0 (idempotent), got {result2.exit_code}."
    )

    # Must emit a clear "already initialized" message in console output (not silent)
    console_out = buf2.getvalue().lower()
    assert "already" in console_out or "initialized" in console_out, (
        "Second init console output should mention 'already initialized', but got:\n"
        f"{buf2.getvalue()!r}"
    )

    # Config must be unchanged (no silent merge/overwrite)
    config_content_after_second = config_path.read_text(encoding="utf-8")
    assert config_content_after_first == config_content_after_second, (
        "config.yaml was modified by the second init run — silent merge/overwrite detected."
    )


def test_init_repairs_requested_command_skills_in_initialized_clone(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit --ai repairs an ignored agent surface in an initialized clone."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)

    app1, _ = _make_app_with_buf()
    result1 = _run(app1, ["init", "--ai", "codex", "--non-interactive"])
    assert result1.exit_code == 0, result1.output

    config_path = tmp_path / ".kittify" / "config.yaml"
    config_before = config_path.read_text(encoding="utf-8")
    skills_root = tmp_path / ".agents" / "skills"
    assert skills_root.is_dir()

    # Agent surfaces are intentionally ignored and therefore absent after a clone.
    shutil.rmtree(tmp_path / ".agents")
    assert not skills_root.exists()

    app2, buf2 = _make_app_with_buf()
    result2 = _run(app2, ["init", "--ai", "codex", "--non-interactive"])

    assert result2.exit_code == 0, result2.output
    assert (skills_root / "spec-kitty.plan" / "SKILL.md").is_file()
    assert "command skills installed" in buf2.getvalue().lower()
    assert config_path.read_text(encoding="utf-8") == config_before
