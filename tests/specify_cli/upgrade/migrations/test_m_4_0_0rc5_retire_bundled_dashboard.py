"""The rc5 migration that removes what the retired bundled dashboard left behind (#5530).

Pins both directions of the ownership guard: package-owned command files and the
dashboard's runtime state are removed; a user file that reuses the retired
command name is preserved with a diagnostic.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import psutil
import pytest

from specify_cli.upgrade.migrations import m_4_0_0rc5_retire_bundled_dashboard as retire_mod
from specify_cli.upgrade.migrations.m_4_0_0rc5_retire_bundled_dashboard import (
    RetireBundledDashboardMigration,
)

pytestmark = pytest.mark.unit

_MARKER = b"<!-- spec-kitty-command-version: 4.0.0rc4 -->\n"
_CLAUDE_CMD = ".claude/commands/spec-kitty.dashboard.md"
_GEMINI_CMD = ".gemini/commands/spec-kitty.dashboard.toml"
_COPILOT_CMD = ".github/prompts/spec-kitty.dashboard.prompt.md"
_META = ".kittify/.dashboard"
# Old .kittify/.dashboard layout: URL, port, token, PID.
_META_NO_PID = b"http://127.0.0.1:9237\n9237\ntoken\n"


def _meta_with_pid(pid: int) -> bytes:
    return _META_NO_PID + f"{pid}\n".encode()


class _FakeProcess:
    """Stands in for ``psutil.Process`` so a test controls what the PID looks like."""

    def __init__(self, cmdline: list[str], *, deny: bool = False) -> None:
        self._cmdline = cmdline
        self._deny = deny
        self.terminated = False

    def cmdline(self) -> list[str]:
        return self._cmdline

    def terminate(self) -> None:
        if self._deny:
            raise psutil.AccessDenied(pid=4242)
        self.terminated = True

    def wait(self, timeout: float) -> None:
        del timeout

    def kill(self) -> None:  # pragma: no cover - only reached on a terminate timeout
        self.terminated = True


def _project(tmp_path: Path, agents: tuple[str, ...] = ("claude", "gemini")) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    listed = "".join(f"    - {agent}\n" for agent in agents)
    (kittify / "config.yaml").write_text(f"agents:\n  available:\n{listed}", encoding="utf-8")
    return tmp_path


def _seed(project: Path, rel: str, content: bytes) -> Path:
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_owned_command_files_and_runtime_state_are_removed(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claude = _seed(project, _CLAUDE_CMD, _MARKER + b"spec-kitty dashboard $ARGUMENTS\n")
    gemini = _seed(project, _GEMINI_CMD, b'prompt = """\n' + _MARKER + b'spec-kitty dashboard {{args}}\n"""\n')
    meta = _seed(project, _META, _META_NO_PID)
    banner = _seed(project, ".kittify/preflight-warning.json", b'{"blocked_reason": "stale"}\n')
    migration = RetireBundledDashboardMigration()

    assert migration.detect(project)
    result = migration.apply(project)

    assert result.success
    assert not claude.exists()
    assert not gemini.exists()
    assert not meta.exists()
    assert not banner.exists()
    assert not result.preserved_paths
    assert not migration.detect(project)


def test_user_file_reusing_the_command_name_is_preserved(tmp_path: Path) -> None:
    project = _project(tmp_path)
    user_bytes = b"# my own dashboard notes, not the shipped command\n"
    path = _seed(project, _CLAUDE_CMD, user_bytes)

    result = RetireBundledDashboardMigration().apply(project)

    assert result.success
    assert path.read_bytes() == user_bytes
    assert str(path) in result.preserved_paths
    assert result.warnings


def test_a_preserved_user_file_does_not_retrigger_the_migration(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _seed(project, _CLAUDE_CMD, b"# my own dashboard notes\n")

    assert not RetireBundledDashboardMigration().detect(project)


def test_copilot_prompt_file_is_removed(tmp_path: Path) -> None:
    project = _project(tmp_path, agents=("copilot",))
    copilot = _seed(project, _COPILOT_CMD, _MARKER + b"spec-kitty dashboard $ARGUMENTS\n")

    result = RetireBundledDashboardMigration().apply(project)

    assert result.success
    assert not copilot.exists()


def test_dry_run_reports_without_removing(tmp_path: Path) -> None:
    project = _project(tmp_path)
    meta = _seed(project, _META, b"http://127.0.0.1:9237\n")

    result = RetireBundledDashboardMigration().apply(project, dry_run=True)

    assert result.success
    assert meta.exists()
    assert result.changes_made == ["Would remove retired .kittify/.dashboard"]


def test_dry_run_reports_a_user_file_as_preserved(tmp_path: Path) -> None:
    project = _project(tmp_path)
    user_bytes = b"# my own dashboard notes\n"
    path = _seed(project, _CLAUDE_CMD, user_bytes)

    result = RetireBundledDashboardMigration().apply(project, dry_run=True)

    assert path.read_bytes() == user_bytes
    assert not any("Would remove" in change for change in result.changes_made)
    assert str(path) in result.preserved_paths


def test_running_dashboard_server_is_stopped_before_its_record_goes(tmp_path: Path) -> None:
    project = _project(tmp_path)
    # A real process whose command line names the old server module, like a
    # detached ``python -m specify_cli.dashboard._server_main`` would.
    server = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)", "specify_cli.dashboard._server_main"],
    )
    try:
        meta = _seed(project, _META, _meta_with_pid(server.pid))

        result = RetireBundledDashboardMigration().apply(project)

        assert result.success
        assert server.wait(timeout=10) is not None
        assert not meta.exists()
        assert f"Stopped the running dashboard server (PID {server.pid})" in result.changes_made
    finally:
        if server.poll() is None:
            server.kill()
            server.wait()


def test_reused_pid_of_another_program_is_left_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    other = _FakeProcess(["/usr/bin/vim", "notes.md"])
    monkeypatch.setattr(retire_mod.psutil, "Process", lambda pid: other)
    meta = _seed(project, _META, _meta_with_pid(4242))

    result = RetireBundledDashboardMigration().apply(project)

    assert result.success
    assert not other.terminated
    assert not meta.exists()


def test_server_that_cannot_be_stopped_keeps_its_record_and_warns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    server = _FakeProcess([sys.executable, "-m", "specify_cli.dashboard._server_main"], deny=True)
    monkeypatch.setattr(retire_mod.psutil, "Process", lambda pid: server)
    meta = _seed(project, _META, _meta_with_pid(4242))

    result = RetireBundledDashboardMigration().apply(project)

    assert meta.exists()
    assert str(meta) in result.preserved_paths
    assert any("PID 4242, port 9237" in warning for warning in result.warnings)


def test_dry_run_names_the_server_it_would_stop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = _project(tmp_path)
    server = _FakeProcess([sys.executable, "-m", "specify_cli.dashboard._server_main"])
    monkeypatch.setattr(retire_mod.psutil, "Process", lambda pid: server)
    meta = _seed(project, _META, _meta_with_pid(4242))

    result = RetireBundledDashboardMigration().apply(project, dry_run=True)

    assert not server.terminated
    assert meta.exists()
    assert "Would stop the running dashboard server (PID 4242)" in result.changes_made


def test_unconfigured_agent_dirs_are_left_alone(tmp_path: Path) -> None:
    project = _project(tmp_path, agents=("claude",))
    gemini = _seed(project, _GEMINI_CMD, _MARKER + b"spec-kitty dashboard\n")

    migration = RetireBundledDashboardMigration()
    assert not migration.detect(project)
    result = migration.apply(project)

    assert result.success
    assert gemini.exists()
    assert result.changes_made == ["No retired dashboard files present"]
