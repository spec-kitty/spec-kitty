"""WP05 migration tests: _default_upgrade_runner parity, event emission, history records.

T027 test cases:
1. UV_TOOL success  → UvToolInstallationVerified(HIGH or MEDIUM) + SUCCESS record
2. UV_TOOL failure  → UvToolInstallationVerified(LOW) + FAILURE record
3. PIPX success     → NO UvToolInstallationVerified + SUCCESS record
4. Store unreachable → _default_upgrade_runner returns normally (best-effort)
5. Event emission failure → runner returns normally (best-effort)
6. Set B deletion parity  → subprocess argv/env comes from RemediationCommand
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import specify_cli.readiness.upgrade_ux as _ux_mod
from specify_cli.compat._detect.install_method import InstallMethod
from specify_cli.compat._detect.runtime import InstalledCliRuntime, PackageSource
from specify_cli.compat.history import UpgradeAttemptStore
from specify_cli.compat.install_events import UvToolInstallationVerified, VerificationConfidence
from specify_cli.compat.remediation import RemediationCommand, RemediationIntent
from tests._support.eacces import deny_path_method

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Runtime + RemediationCommand factories
# ---------------------------------------------------------------------------

_SAFE_METHODS = frozenset({
    InstallMethod.UV_TOOL,
    InstallMethod.PIPX,
    InstallMethod.BREW,
    InstallMethod.PIP_USER,
    InstallMethod.PIP_SYSTEM,
})


def _make_runtime(
    install_method: InstallMethod,
    *,
    tool_dir: Path | None = None,
    is_default_tool_dir: bool | None = None,
    python: str | None = None,
) -> InstalledCliRuntime:
    return InstalledCliRuntime(
        install_method=install_method,
        executable="/fake/bin/python",
        receipt_path=None,
        tool_dir=tool_dir,
        bin_dir=None,
        is_default_tool_dir=is_default_tool_dir,
        is_default_bin_dir=None,
        python=python,
        requirements=(),
        package_source=PackageSource.UNKNOWN,
        platform="posix",
        safe_for_auto_upgrade=install_method in _SAFE_METHODS,
    )


def _uv_tool_runtime(
    *,
    python: str | None = None,
    tool_dir: Path | None = None,
    is_default_tool_dir: bool | None = True,
) -> InstalledCliRuntime:
    return _make_runtime(
        InstallMethod.UV_TOOL,
        python=python,
        tool_dir=tool_dir,
        is_default_tool_dir=is_default_tool_dir,
    )


def _uv_upgrade_cmd(
    *,
    target_version: str | None = None,
    tool_dir: Path | None = None,
    python: str | None = None,
) -> RemediationCommand:
    """Build a UV_TOOL UPGRADE RemediationCommand matching plan_remediation() output."""
    from specify_cli.compat.remediation import plan_remediation

    runtime = _make_runtime(
        InstallMethod.UV_TOOL,
        tool_dir=tool_dir,
        is_default_tool_dir=tool_dir is None,
        python=python,
    )
    return plan_remediation(runtime, RemediationIntent.UPGRADE, target_version)


def _pipx_upgrade_cmd() -> RemediationCommand:
    from specify_cli.compat.remediation import plan_remediation

    runtime = _make_runtime(InstallMethod.PIPX)
    return plan_remediation(runtime, RemediationIntent.UPGRADE, None)


def _completed(returncode: int = 0) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=[], returncode=returncode)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_events() -> None:
    _ux_mod._emitted_install_events.clear()


def _emitted() -> list[object]:
    return list(_ux_mod._emitted_install_events)


# ---------------------------------------------------------------------------
# Test: UV_TOOL success
# ---------------------------------------------------------------------------


class TestUvToolSuccess:
    """T027-1: UV_TOOL success → HIGH/MEDIUM event + SUCCESS record."""

    def test_uv_tool_success_emits_verified_event_high_confidence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """EXIT 0 + entrypoint found → HIGH confidence event emitted."""
        _clear_events()
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))

        # Fake receipt with a spec-kitty entrypoint (→ bin_dir not None → HIGH)
        receipt_toml = (
            "[tool]\n"
            'requirements = [{ name = "spec-kitty-cli", specifier = ">=1.2.0" }]\n'
            "[[tool.entrypoints]]\n"
            'name = "spec-kitty"\n'
            'install-path = "/fake/bin/spec-kitty"\n'
        )
        fake_exe_dir = tmp_path / "tool-env" / "bin"
        fake_exe_dir.mkdir(parents=True)
        (tmp_path / "tool-env" / "uv-receipt.toml").write_text(receipt_toml)
        fake_exe = str(fake_exe_dir / "python")

        with (
            patch("specify_cli.readiness.upgrade_ux.subprocess.run", return_value=_completed(0)),
            patch("sys.executable", fake_exe),
        ):
            cmd = _uv_upgrade_cmd()
            runtime = _uv_tool_runtime()
            result = _ux_mod._default_upgrade_runner(cmd, runtime, target_version="1.2.0")

        assert result.returncode == 0
        events = _emitted()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, UvToolInstallationVerified)
        assert evt.confidence == VerificationConfidence.HIGH
        assert evt.entrypoint_match is True
        assert evt.package_binding == "spec-kitty-cli>=1.2.0"

        # Also verify history record was written.
        store = UpgradeAttemptStore(tmp_path / "history.db")
        assert store.last_success_timestamp(InstallMethod.UV_TOOL) is not None

    def test_uv_tool_success_medium_confidence_when_no_entrypoint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """EXIT 0 + no entrypoint in receipt → MEDIUM confidence."""
        _clear_events()
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))

        # Receipt exists but NO entrypoint → bin_dir is None → MEDIUM
        receipt_toml = (
            "[tool]\n"
            'requirements = [{ name = "spec-kitty-cli" }]\n'
        )
        fake_exe_dir = tmp_path / "tool-env" / "bin"
        fake_exe_dir.mkdir(parents=True)
        (tmp_path / "tool-env" / "uv-receipt.toml").write_text(receipt_toml)
        fake_exe = str(fake_exe_dir / "python")

        with (
            patch("specify_cli.readiness.upgrade_ux.subprocess.run", return_value=_completed(0)),
            patch("sys.executable", fake_exe),
        ):
            cmd = _uv_upgrade_cmd()
            runtime = _uv_tool_runtime()
            result = _ux_mod._default_upgrade_runner(cmd, runtime)

        assert result.returncode == 0
        events = _emitted()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, UvToolInstallationVerified)
        assert evt.confidence == VerificationConfidence.MEDIUM
        assert evt.entrypoint_match is False


# ---------------------------------------------------------------------------
# Test: UV_TOOL failure
# ---------------------------------------------------------------------------


class TestUvToolFailure:
    """T027-2: UV_TOOL failure → LOW confidence event + FAILURE record."""

    def test_uv_tool_failure_emits_low_confidence_event(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _clear_events()
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))

        with (
            patch("specify_cli.readiness.upgrade_ux.subprocess.run", return_value=_completed(1)),
            patch("sys.executable", "/fake/bin/python"),
        ):
            cmd = _uv_upgrade_cmd()
            runtime = _uv_tool_runtime()
            result = _ux_mod._default_upgrade_runner(cmd, runtime)

        assert result.returncode == 1
        events = _emitted()
        assert len(events) == 1
        evt = events[0]
        assert isinstance(evt, UvToolInstallationVerified)
        assert evt.confidence == VerificationConfidence.LOW

        # History record written as FAILURE.
        store = UpgradeAttemptStore(tmp_path / "history.db")
        count = store.consecutive_failure_count(InstallMethod.UV_TOOL)
        assert count == 1


# ---------------------------------------------------------------------------
# Test: PIPX — no event
# ---------------------------------------------------------------------------


class TestPipxSuccess:
    """T027-3: PIPX success → NO UvToolInstallationVerified + SUCCESS record."""

    def test_pipx_success_no_verified_event(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _clear_events()
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))

        with patch("specify_cli.readiness.upgrade_ux.subprocess.run", return_value=_completed(0)):
            cmd = _pipx_upgrade_cmd()
            runtime = _make_runtime(InstallMethod.PIPX)
            result = _ux_mod._default_upgrade_runner(cmd, runtime)

        assert result.returncode == 0
        events = _emitted()
        assert len(events) == 0, "PIPX must not emit UvToolInstallationVerified"

        # History record written as SUCCESS.
        store = UpgradeAttemptStore(tmp_path / "history.db")
        ts = store.last_success_timestamp(InstallMethod.PIPX)
        assert ts is not None


# ---------------------------------------------------------------------------
# Test: Store unreachable
# ---------------------------------------------------------------------------


class TestStoreUnreachable:
    """T027-4: History store cannot be opened → runner returns normally (best-effort)."""

    def test_runner_returns_normally_when_store_unreachable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Deny the history-db open at its first filesystem call (the parent
        # mkdir in UpgradeAttemptStore._connect) instead of chmod: root
        # bypasses directory mode bits, so a chmod-based setup let the write
        # succeed as uid 0 and never reached the swallowed-error branch (#5654).
        db_dir = tmp_path / "history"
        db_path = db_dir / "history.db"
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(db_path))
        deny_path_method(monkeypatch, "mkdir", db_dir)

        connect_errors: list[BaseException] = []
        real_connect = UpgradeAttemptStore._connect

        def recording_connect(store: UpgradeAttemptStore) -> Any:
            try:
                return real_connect(store)
            except BaseException as exc:
                connect_errors.append(exc)
                raise

        monkeypatch.setattr(UpgradeAttemptStore, "_connect", recording_connect)

        with patch("specify_cli.readiness.upgrade_ux.subprocess.run", return_value=_completed(0)):
            cmd = _pipx_upgrade_cmd()
            runtime = _make_runtime(InstallMethod.PIPX)
            result = _ux_mod._default_upgrade_runner(cmd, runtime)

        # Must return normally despite the write failure...
        assert result.returncode == 0
        # ...because the store was reached and its open was denied, not
        # because the runner skipped recording.
        assert len(connect_errors) == 1
        assert isinstance(connect_errors[0], PermissionError)
        assert not db_path.exists()


# ---------------------------------------------------------------------------
# Test: Event emission failure
# ---------------------------------------------------------------------------


class TestEventEmissionFailure:
    """T027-5: _emit_install_verified_event raises → runner returns normally."""

    def test_runner_continues_when_event_emission_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))

        with (
            patch("specify_cli.readiness.upgrade_ux.subprocess.run", return_value=_completed(0)),
            patch.object(_ux_mod, "_emit_install_verified_event", side_effect=RuntimeError("boom")),
        ):
            cmd = _uv_upgrade_cmd()
            runtime = _uv_tool_runtime()
            result = _ux_mod._default_upgrade_runner(cmd, runtime)

        assert result.returncode == 0


# ---------------------------------------------------------------------------
# Test: Set B deletion parity (T027-6)
# ---------------------------------------------------------------------------


class TestSetBDeletionParity:
    """T027-6: argv/env from RemediationCommand match old argv_by_method output."""

    def test_uv_tool_default_dir_no_python_basic_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UV_TOOL with default tool_dir and no python → simple argv, no env override."""
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))
        calls: list[dict[str, Any]] = []

        def _fake_run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[bytes]:
            calls.append({"argv": argv, "env": kw.get("env")})
            return _completed(0)

        with (
            patch("specify_cli.readiness.upgrade_ux.subprocess.run", side_effect=_fake_run),
            patch("sys.executable", "/fake/bin/python"),
        ):
            runtime = _uv_tool_runtime(is_default_tool_dir=True)
            from specify_cli.compat.remediation import plan_remediation

            cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
            _ux_mod._default_upgrade_runner(cmd, runtime)

        assert len(calls) == 1
        assert calls[0]["argv"] == ["uv", "tool", "install", "--force", "spec-kitty-cli"]
        # No UV_TOOL_DIR when tool_dir is default.
        env = calls[0]["env"]
        assert env is None or "UV_TOOL_DIR" not in env

    def test_uv_tool_custom_dir_and_python_argv_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UV_TOOL with python='3.12' and custom tool_dir → --python flag + UV_TOOL_DIR."""
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))
        custom_tool_dir = tmp_path / "my-tools"
        calls: list[dict[str, Any]] = []

        def _fake_run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[bytes]:
            calls.append({"argv": argv, "env": kw.get("env")})
            return _completed(0)

        with (
            patch("specify_cli.readiness.upgrade_ux.subprocess.run", side_effect=_fake_run),
            patch("sys.executable", "/fake/bin/python"),
        ):
            runtime = _uv_tool_runtime(
                python="3.12",
                tool_dir=custom_tool_dir,
                is_default_tool_dir=False,
            )
            from specify_cli.compat.remediation import plan_remediation

            cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, "1.5.0")
            _ux_mod._default_upgrade_runner(cmd, runtime, target_version="1.5.0")

        assert len(calls) == 1
        assert calls[0]["argv"] == [
            "uv", "tool", "install", "--force", "--python", "3.12", "spec-kitty-cli==1.5.0"
        ]
        env = calls[0]["env"]
        assert env is not None
        assert env.get("UV_TOOL_DIR") == str(custom_tool_dir)

    def test_pipx_upgrade_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PIPX upgrade → pipx upgrade spec-kitty-cli (no env override)."""
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))
        calls: list[dict[str, Any]] = []

        def _fake_run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[bytes]:
            calls.append({"argv": argv, "env": kw.get("env")})
            return _completed(0)

        with patch("specify_cli.readiness.upgrade_ux.subprocess.run", side_effect=_fake_run):
            runtime = _make_runtime(InstallMethod.PIPX)
            from specify_cli.compat.remediation import plan_remediation

            cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
            _ux_mod._default_upgrade_runner(cmd, runtime)

        assert len(calls) == 1
        assert calls[0]["argv"] == ["pipx", "upgrade", "spec-kitty-cli"]
        env = calls[0]["env"]
        assert env is None or "UV_TOOL_DIR" not in env

    def test_pip_user_upgrade_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PIP_USER upgrade → pip install --user --upgrade spec-kitty-cli."""
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))
        calls: list[dict[str, Any]] = []

        def _fake_run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[bytes]:
            calls.append({"argv": argv, "env": kw.get("env")})
            return _completed(0)

        with patch("specify_cli.readiness.upgrade_ux.subprocess.run", side_effect=_fake_run):
            runtime = _make_runtime(InstallMethod.PIP_USER)
            from specify_cli.compat.remediation import plan_remediation

            cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
            _ux_mod._default_upgrade_runner(cmd, runtime)

        assert len(calls) == 1
        assert calls[0]["argv"] == ["pip", "install", "--user", "--upgrade", "spec-kitty-cli"]

    def test_pip_system_upgrade_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PIP_SYSTEM upgrade → pip install --upgrade spec-kitty-cli."""
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))
        calls: list[dict[str, Any]] = []

        def _fake_run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[bytes]:
            calls.append({"argv": argv, "env": kw.get("env")})
            return _completed(0)

        with patch("specify_cli.readiness.upgrade_ux.subprocess.run", side_effect=_fake_run):
            runtime = _make_runtime(InstallMethod.PIP_SYSTEM)
            from specify_cli.compat.remediation import plan_remediation

            cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
            _ux_mod._default_upgrade_runner(cmd, runtime)

        assert len(calls) == 1
        assert calls[0]["argv"] == ["pip", "install", "--upgrade", "spec-kitty-cli"]

    def test_brew_upgrade_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """BREW upgrade → brew upgrade spec-kitty-cli."""
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))
        calls: list[dict[str, Any]] = []

        def _fake_run(argv: list[str], **kw: Any) -> subprocess.CompletedProcess[bytes]:
            calls.append({"argv": argv, "env": kw.get("env")})
            return _completed(0)

        with patch("specify_cli.readiness.upgrade_ux.subprocess.run", side_effect=_fake_run):
            runtime = _make_runtime(InstallMethod.BREW)
            from specify_cli.compat.remediation import plan_remediation

            cmd = plan_remediation(runtime, RemediationIntent.UPGRADE, None)
            _ux_mod._default_upgrade_runner(cmd, runtime)

        assert len(calls) == 1
        assert calls[0]["argv"] == ["brew", "upgrade", "spec-kitty-cli"]


# ---------------------------------------------------------------------------
# Test: cmd.argv is None (MANUAL_GUIDANCE path) → returncode 1
# ---------------------------------------------------------------------------


class TestManualGuidanceCommand:
    """MANUAL_GUIDANCE commands (argv=None) → returncode 1, no subprocess call."""

    def test_manual_guidance_cmd_returns_failure_without_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_HISTORY_DB_PATH", str(tmp_path / "history.db"))
        manual_cmd = RemediationCommand(
            intent=RemediationIntent.MANUAL_GUIDANCE,
            argv=None,
            env={},
            note="Install manually.",
        )
        runtime = _make_runtime(InstallMethod.UNKNOWN)

        with patch("specify_cli.readiness.upgrade_ux.subprocess.run") as mock_run:
            result = _ux_mod._default_upgrade_runner(manual_cmd, runtime)

        mock_run.assert_not_called()
        assert result.returncode == 1
