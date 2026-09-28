"""Red-first regression tests for #4940 (WP05, D6): settings.json data loss.

``ClaudeCodeHookRegistrar._load`` used to swallow ``UnicodeDecodeError`` into
``{}`` *before* the invalid-content backup branch, so a non-UTF-8
``.claude/settings.json`` (a cp1252 file saved by a Windows ANSI editor, or a
plain UTF-16 file) got silently replaced by a lint-only reconstruction: the
operator's permissions (incl. deny rules), env, their own hooks, and Spec
Kitty's own SessionStart/Stop hooks were gone, with no backup, exit 0.

Policy (Decision Moment ``01M3KDD2GHGFS7J5616ZNQHE6Y``): decode only
*provable* encodings (strict UTF-8, or a BOM for UTF-8/UTF-16/UTF-32); never
guess a code page. Anything else: leave the file byte-identical and fail
non-zero.

Covers FR-011..FR-014 / NFR-001..NFR-003 (plan D6, research R4,
contracts/failure-surface.md row "agent config sync --sync-hooks,
live-work install").
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands.agent.config import LINT_HOOK_COMMAND, _sync_claude_hooks
from specify_cli.live_work.install import install_hooks, uninstall_hooks
from specify_cli.session_presence.content import SECTION_OPEN
from specify_cli.session_presence.hooks.claude_code_hook import (
    SESSION_START_EVENT,
    STOP_EVENT,
    ClaudeCodeHookRegistrar,
    SettingsNotDecodableError,
)
from specify_cli.session_presence.writers.claude_code import (
    SESSION_START_CMD,
    SESSION_STOP_CMD,
    ClaudeCodeWriter,
)
from specify_cli.tool_surface.providers.session_presence import (
    SessionPresenceProvider,
    hook_definition,
)
from specify_cli.tool_surface.status import STATE_UNSAFE

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_SRC = Path(__file__).resolve().parents[3] / "src"


# ---------------------------------------------------------------------------
# Fixture builder: dict -> bytes in each of the encodings the mission cares
# about, always carrying a realistic mix of user + spec-kitty entries.
# ---------------------------------------------------------------------------


def _fixture_settings_dict() -> dict[str, Any]:
    return {
        "permissions": {
            "allow": ["Bash(ls:*)"],
            "deny": ["Read(./.env)"],
        },
        "env": {"OWNER": "José"},
        "hooks": {
            "PreToolUse": [{"hooks": [{"type": "command", "command": "user-owned-tool"}]}],
            SESSION_START_EVENT: [{"hooks": [{"type": "command", "command": SESSION_START_CMD}]}],
            STOP_EVENT: [{"hooks": [{"type": "command", "command": SESSION_STOP_CMD}]}],
        },
    }


def _utf8_bom_bytes(data: dict[str, Any]) -> bytes:
    return b"\xef\xbb\xbf" + json.dumps(data).encode("utf-8")


def _utf16_le_bom_bytes(data: dict[str, Any]) -> bytes:
    return ("﻿" + json.dumps(data)).encode("utf-16-le")


def _utf16_be_bom_bytes(data: dict[str, Any]) -> bytes:
    return ("﻿" + json.dumps(data)).encode("utf-16-be")


def _cp1252_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("cp1252")


def _write_settings_bytes(project_root: Path, raw: bytes) -> Path:
    path = project_root / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path


def _settings_path(project_root: Path) -> Path:
    return project_root / ".claude" / "settings.json"


def _write_orientation_marker(project_root: Path) -> None:
    """Write a minimal CLAUDE.md carrying the orientation marker.

    ``ClaudeCodeWriter.has_presence`` is ``super().has_presence() and
    <hooks registered>`` -- short-circuiting ``and``, so the hook check
    (where an undecodable settings.json raises) is only reached once the
    orientation file itself reports present.
    """
    (project_root / ".claude").mkdir(parents=True, exist_ok=True)
    (project_root / ".claude" / "CLAUDE.md").write_text(f"{SECTION_OPEN}\n", encoding="utf-8")


def _backups(project_root: Path) -> list[Path]:
    settings = _settings_path(project_root)
    return sorted(p for p in settings.parent.glob("settings.json.*") if p.name != "settings.json")


def _assert_refusal(excinfo: pytest.ExceptionInfo[SettingsNotDecodableError], path: Path) -> None:
    """NFR-003: every refusal names the offending file and the UTF-8 remedy.

    Pins the operator-visible message text (not just the exception type), so
    a change to the root error presenter that dropped the path or the
    "re-save it as UTF-8" remedy would go red here.
    """
    message = str(excinfo.value)
    assert str(path) in message
    assert "re-save it as UTF-8" in message


def _assert_fixture_entries_present(data: dict[str, Any]) -> None:
    assert data["permissions"]["deny"] == ["Read(./.env)"]
    assert data["permissions"]["allow"] == ["Bash(ls:*)"]
    assert data["env"]["OWNER"] == "José"
    pre_tool = data["hooks"]["PreToolUse"]
    assert any(h.get("command") == "user-owned-tool" for e in pre_tool for h in e.get("hooks", []))


# ---------------------------------------------------------------------------
# T024 / T025 -- the shared decode rule via _load/register/unregister/is_registered
# ---------------------------------------------------------------------------


class TestRegistrarDecodeRule:
    @pytest.mark.parametrize(
        "encode",
        [_utf8_bom_bytes, _utf16_le_bom_bytes, _utf16_be_bom_bytes],
        ids=["utf-8-bom", "utf-16-le-bom", "utf-16-be-bom"],
    )
    def test_bom_encoded_settings_all_entries_preserved_and_backed_up(self, tmp_path: Path, encode: Any) -> None:
        """FR-011/FR-012: every entry survives register(); the original bytes are backed up."""
        raw = encode(_fixture_settings_dict())
        path = _write_settings_bytes(tmp_path, raw)
        original = path.read_bytes()

        reg = ClaudeCodeHookRegistrar(event_key="PostToolUse")
        reg.register(tmp_path, LINT_HOOK_COMMAND, matcher="Edit|Write")

        data = json.loads(path.read_bytes().decode("utf-8"))
        _assert_fixture_entries_present(data)
        assert any(h.get("command") == SESSION_START_CMD for e in data["hooks"][SESSION_START_EVENT] for h in e.get("hooks", []))
        assert any(h.get("command") == SESSION_STOP_CMD for e in data["hooks"][STOP_EVENT] for h in e.get("hooks", []))
        assert any(h.get("command") == LINT_HOOK_COMMAND for e in data["hooks"]["PostToolUse"] for h in e.get("hooks", []))

        backups = _backups(tmp_path)
        assert backups, "expected a byte-exact backup sidecar for a non-plain-UTF-8 source"
        assert backups[0].read_bytes() == original

    def test_cp1252_settings_refused_bytes_untouched(self, tmp_path: Path) -> None:
        """FR-013: cp1252 (unprovable, must not be guessed) -> file untouched, typed refusal."""
        raw = _cp1252_bytes(_fixture_settings_dict())
        path = _write_settings_bytes(tmp_path, raw)
        original = path.read_bytes()

        reg = ClaudeCodeHookRegistrar(event_key="PostToolUse")
        with pytest.raises(SettingsNotDecodableError) as excinfo:
            reg.register(tmp_path, LINT_HOOK_COMMAND, matcher="Edit|Write")

        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original
        assert not _backups(tmp_path)

    def test_is_registered_never_returns_false_on_undecodable_file(self, tmp_path: Path) -> None:
        """is_registered() must raise, never return False (that would let register() overwrite)."""
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))
        reg = ClaudeCodeHookRegistrar(event_key="PostToolUse")
        with pytest.raises(SettingsNotDecodableError) as excinfo:
            reg.is_registered(tmp_path, LINT_HOOK_COMMAND)
        _assert_refusal(excinfo, path)

    def test_unregister_undecodable_refuses(self, tmp_path: Path) -> None:
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()
        reg = ClaudeCodeHookRegistrar(event_key="PostToolUse")
        with pytest.raises(SettingsNotDecodableError) as excinfo:
            reg.unregister(tmp_path, LINT_HOOK_COMMAND)
        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original

    # --- Controls: behaviour must stay exactly as before for these cases ---

    def test_plain_utf8_control_no_backup(self, tmp_path: Path) -> None:
        raw = json.dumps(_fixture_settings_dict()).encode("utf-8")
        path = _write_settings_bytes(tmp_path, raw)

        reg = ClaudeCodeHookRegistrar(event_key="PostToolUse")
        reg.register(tmp_path, LINT_HOOK_COMMAND, matcher="Edit|Write")

        data = json.loads(path.read_text(encoding="utf-8"))
        _assert_fixture_entries_present(data)
        assert not _backups(tmp_path), "a plain-UTF-8 source must not get a re-encode backup"

    def test_invalid_json_control_unchanged_dot_invalid_path(self, tmp_path: Path) -> None:
        path = _write_settings_bytes(tmp_path, b"{ not valid json")

        reg = ClaudeCodeHookRegistrar(event_key="PostToolUse")
        reg.register(tmp_path, LINT_HOOK_COMMAND, matcher="Edit|Write")

        invalid_backups = list(path.parent.glob("settings.json.invalid.*"))
        assert invalid_backups, "invalid JSON must still get the existing .invalid backup"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert any(h.get("command") == LINT_HOOK_COMMAND for e in data["hooks"]["PostToolUse"] for h in e.get("hooks", []))

    def test_absent_settings_file_is_unchanged_behaviour(self, tmp_path: Path) -> None:
        reg = ClaudeCodeHookRegistrar()
        reg.register(tmp_path, SESSION_START_CMD)
        assert _settings_path(tmp_path).exists()
        assert not _backups(tmp_path)


# ---------------------------------------------------------------------------
# T024 / T028 -- `spec-kitty agent config sync --sync-hooks` (`_sync_claude_hooks`)
# ---------------------------------------------------------------------------


class TestSyncClaudeHooksCLI:
    def test_utf8_bom_sync_preserves_entries_and_backs_up(self, tmp_path: Path) -> None:
        raw = _utf8_bom_bytes(_fixture_settings_dict())
        path = _write_settings_bytes(tmp_path, raw)
        original = path.read_bytes()

        assert _sync_claude_hooks(tmp_path, enabled=True) is True

        data = json.loads(path.read_bytes().decode("utf-8"))
        _assert_fixture_entries_present(data)
        assert any(h.get("command") == LINT_HOOK_COMMAND for e in data["hooks"]["PostToolUse"] for h in e.get("hooks", []))
        backups = _backups(tmp_path)
        assert backups and backups[0].read_bytes() == original

    def test_utf16_sync_preserves_entries_and_backs_up(self, tmp_path: Path) -> None:
        raw = _utf16_le_bom_bytes(_fixture_settings_dict())
        path = _write_settings_bytes(tmp_path, raw)
        original = path.read_bytes()

        assert _sync_claude_hooks(tmp_path, enabled=True) is True

        data = json.loads(path.read_bytes().decode("utf-8"))
        _assert_fixture_entries_present(data)
        backups = _backups(tmp_path)
        assert backups and backups[0].read_bytes() == original

    def test_cp1252_sync_refuses_non_zero_file_untouched(self, tmp_path: Path) -> None:
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()

        with pytest.raises(SettingsNotDecodableError) as excinfo:
            _sync_claude_hooks(tmp_path, enabled=True)

        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original

    def test_cp1252_sync_disable_path_also_refuses(self, tmp_path: Path) -> None:
        """The lint-hook disable branch of _sync_claude_hooks must refuse too."""
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()

        with pytest.raises(SettingsNotDecodableError) as excinfo:
            _sync_claude_hooks(tmp_path, enabled=False)

        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original

    def test_cli_subprocess_true_exit_code_for_sync_hooks(self, tmp_path: Path) -> None:
        """T028: verify the real process exit code (CliRunner bypasses the root error hook)."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".kittify").mkdir()
        (project / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n  lint_on_edit: false\n", encoding="utf-8")
        _write_settings_bytes(project, _cp1252_bytes(_fixture_settings_dict()))
        original = _settings_path(project).read_bytes()

        home = tmp_path / "home"
        home.mkdir()
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": str(_REPO_SRC),
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "SPEC_KITTY_NO_UPGRADE_CHECK": "1",
            }
        )

        result = subprocess.run(
            [sys.executable, "-m", "specify_cli", "agent", "config", "sync", "--sync-hooks"],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )

        output = result.stdout + result.stderr
        assert result.returncode == 1, output
        assert str(_settings_path(project)) in output, output
        assert "re-save it as UTF-8" in output, output
        assert "Sync complete" not in result.stdout
        assert _settings_path(project).read_bytes() == original


# ---------------------------------------------------------------------------
# T024 / T028 -- `spec-kitty live-work install claude` / `uninstall`
# ---------------------------------------------------------------------------


class TestLiveWorkInstall:
    def test_utf8_bom_install_backs_up_and_keeps_entries(self, tmp_path: Path) -> None:
        raw = _utf8_bom_bytes(_fixture_settings_dict())
        path = _write_settings_bytes(tmp_path, raw)
        original = path.read_bytes()

        outcome = install_hooks("claude", tmp_path)

        assert outcome.installed is True
        data = json.loads(path.read_bytes().decode("utf-8"))
        _assert_fixture_entries_present(data)
        backups = _backups(tmp_path)
        assert backups and backups[0].read_bytes() == original

    def test_cp1252_install_refuses_non_zero(self, tmp_path: Path) -> None:
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()

        with pytest.raises(SettingsNotDecodableError) as excinfo:
            install_hooks("claude", tmp_path)

        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original

    def test_cp1252_uninstall_refuses_non_zero(self, tmp_path: Path) -> None:
        """Today this is already byte-identical (no-op); only the exit code was red."""
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()

        with pytest.raises(SettingsNotDecodableError) as excinfo:
            uninstall_hooks("claude", tmp_path)

        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original


# ---------------------------------------------------------------------------
# T024 / T026 -- init/upgrade writer path (prepare_commands / apply_prepared)
# ---------------------------------------------------------------------------


class TestPrepareCommandsApplyPrepared:
    def test_utf16_backed_up_before_rewrite(self, tmp_path: Path) -> None:
        """Today this silently re-encodes with no backup; must back up first."""
        raw = _utf16_le_bom_bytes(_fixture_settings_dict())
        path = _write_settings_bytes(tmp_path, raw)
        original = path.read_bytes()

        registrar = ClaudeCodeHookRegistrar()
        prepared = registrar.prepare_commands(
            tmp_path,
            ((SESSION_START_EVENT, SESSION_START_CMD), (STOP_EVENT, SESSION_STOP_CMD)),
        )
        assert prepared.changed is False, "hooks already present in the fixture; nothing should change"

        # Force a change so apply_prepared actually writes, to exercise the backup path.
        prepared_changed = registrar.prepare_commands(tmp_path, ((SESSION_START_EVENT, "a-new-command"),))
        assert prepared_changed.changed is True
        registrar.apply_prepared(tmp_path, prepared_changed)

        data = json.loads(path.read_bytes().decode("utf-8"))
        _assert_fixture_entries_present(data)
        assert any(h.get("command") == "a-new-command" for e in data["hooks"][SESSION_START_EVENT] for h in e.get("hooks", []))
        backups = _backups(tmp_path)
        assert backups and backups[0].read_bytes() == original

    def test_cp1252_prepare_commands_raises(self, tmp_path: Path) -> None:
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()

        registrar = ClaudeCodeHookRegistrar()
        with pytest.raises(SettingsNotDecodableError) as excinfo:
            registrar.prepare_commands(
                tmp_path,
                ((SESSION_START_EVENT, SESSION_START_CMD), (STOP_EVENT, SESSION_STOP_CMD)),
            )
        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original

    def test_full_writer_write_path_cp1252_refuses(self, tmp_path: Path) -> None:
        """ClaudeCodeWriter.write() (the actual init/upgrade entry point) refuses too."""
        (tmp_path / ".claude").mkdir()
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()

        from specify_cli.session_presence.content import SessionPresenceContent

        content = SessionPresenceContent("3.2.0", tmp_path.name, "healthy", None)
        with pytest.raises(SettingsNotDecodableError) as excinfo:
            ClaudeCodeWriter().write(tmp_path, content)

        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original

    def test_upgrade_migration_refuses_non_zero_settings_untouched(self, tmp_path: Path) -> None:
        """T024-3: spec-kitty upgrade's session-presence migration must not report success.

        Isolated to only ``SessionPresenceClaudeCodeMigration`` (rather than
        ``auto_discover_migrations()``'s full set): an unrelated earlier
        migration failing in this minimal fixture project would otherwise
        break the ``for migration in migrations`` loop before ever reaching
        this one, and the runner would return a failed ``UpgradeResult``
        instead of propagating -- a false negative for the assertion this
        test exists to make (detect() itself must raise).
        """
        from kernel.clock import now_utc
        from specify_cli.upgrade.metadata import ProjectMetadata
        from specify_cli.upgrade.migrations.m_3_3_0_session_presence_claude_code import (
            SessionPresenceClaudeCodeMigration,
        )
        from specify_cli.upgrade.registry import MigrationRegistry
        from specify_cli.upgrade.runner import MigrationRunner

        project = tmp_path / "project"
        kittify_dir = project / ".kittify"
        kittify_dir.mkdir(parents=True)
        (kittify_dir / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")
        metadata = ProjectMetadata(
            version="0.0.0",
            initialized_at=now_utc(),
            python_version="3.11",
            platform="test",
            platform_version="test",
        )
        metadata.save(kittify_dir)
        _write_orientation_marker(project)
        path = _write_settings_bytes(project, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()

        original_migrations = dict(MigrationRegistry._migrations)
        try:
            MigrationRegistry.clear()
            MigrationRegistry.register(SessionPresenceClaudeCodeMigration)
            runner = MigrationRunner(project)
            with pytest.raises(SettingsNotDecodableError) as excinfo:
                runner.upgrade("3.2.0rc39", include_worktrees=False, force=True)
        finally:
            MigrationRegistry._migrations = original_migrations

        _assert_refusal(excinfo, path)
        assert path.read_bytes() == original

    def test_cli_subprocess_upgrade_refuses_non_zero_settings_untouched(self, tmp_path: Path) -> None:
        """T024-3: the real `spec-kitty upgrade` command surface refuses too.

        The runner-level test above isolates ``SessionPresenceClaudeCodeMigration``
        to prove ``detect()``/``apply()`` themselves raise; this test instead
        goes through the actual CLI process (``python -m specify_cli upgrade``,
        the same entrypoint `spec-kitty` installs), which is where the root
        error-presentation hook lives (``CliRunner`` bypasses it -- see the
        module docstring pattern used by the sync-hooks subprocess test above).
        A project one migration below its target, with a cp1252
        ``.claude/settings.json``, is confirmed (review cycle 1) to make
        `spec-kitty upgrade --project --yes --target 3.2.0rc39 --no-worktrees`
        exit 1, print the path and remedy, leave the file byte-identical, and
        never record `3_3_0_session_presence_claude_code` as applied.
        """
        project = tmp_path / "project"
        kittify_dir = project / ".kittify"
        kittify_dir.mkdir(parents=True)
        (kittify_dir / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")

        from kernel.clock import now_utc
        from specify_cli.upgrade.metadata import ProjectMetadata

        ProjectMetadata(
            version="3.2.0rc38",
            initialized_at=now_utc(),
            python_version="3.11",
            platform="test",
            platform_version="test",
        ).save(kittify_dir)

        path = _write_settings_bytes(project, _cp1252_bytes(_fixture_settings_dict()))
        original = path.read_bytes()

        home = tmp_path / "home"
        home.mkdir()
        env = os.environ.copy()
        env.update(
            {
                "PYTHONPATH": str(_REPO_SRC),
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "XDG_CACHE_HOME": str(home / ".cache"),
                "SPEC_KITTY_NO_UPGRADE_CHECK": "1",
            }
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "specify_cli",
                "upgrade",
                "--project",
                "--yes",
                "--target",
                "3.2.0rc39",
                "--no-worktrees",
            ],
            cwd=project,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )

        output = result.stdout + result.stderr
        assert result.returncode == 1, output
        assert str(path) in output, output
        assert "re-save it as UTF-8" in output, output
        assert not any("3_3_0_session_presence_claude_code" in line and "✓" in line for line in output.splitlines()), output
        assert path.read_bytes() == original


# ---------------------------------------------------------------------------
# T024 / T027 -- probes (doctor tool-surfaces): report, never crash
# ---------------------------------------------------------------------------


class TestDoctorProbe:
    def test_undecodable_settings_reported_as_finding_not_traceback(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / "CLAUDE.md").touch()
        _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))

        provider = SessionPresenceProvider()
        instances = provider.expand(hook_definition(), "claude", tmp_path)
        assert instances, "expected the settings.json hook instance to be expanded"

        for instance in instances:
            status = provider.probe(instance)
            assert status.state == STATE_UNSAFE
            assert status.findings
            assert any("re-save" in f.message and str(instance.path) in f.message for f in status.findings)

    def test_has_presence_propagates_for_undecodable_settings(self, tmp_path: Path) -> None:
        _write_orientation_marker(tmp_path)
        path = _write_settings_bytes(tmp_path, _cp1252_bytes(_fixture_settings_dict()))

        with pytest.raises(SettingsNotDecodableError) as excinfo:
            ClaudeCodeWriter().has_presence(tmp_path)
        _assert_refusal(excinfo, path)
