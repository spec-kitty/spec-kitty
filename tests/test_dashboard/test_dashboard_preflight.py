"""Tests for the charter preflight hook in the dashboard (T025 / T026).

Verifies the FR-006 caller contract for the dashboard consumer:

* Server still launches on preflight failure (no abort).
* Blocking reasons and passed advisories are persisted under ``.kittify/``
  and surfaced as ``preflight_warning`` in the ``/api/health`` response.
* On a clean success the field is absent and stale persistence is cleared.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from specify_cli.charter_runtime.preflight.dashboard_warning import (
    clear_preflight_warning,
    preflight_warning_path,
    read_preflight_warning,
    write_preflight_warning,
)
from specify_cli.charter_runtime.preflight.result import CharterPreflightResult


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _pass_result() -> CharterPreflightResult:
    return CharterPreflightResult(
        passed=True,
        checks=[],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=None,
    )


def _fail_result(reason: str) -> CharterPreflightResult:
    return CharterPreflightResult(
        passed=False,
        checks=[],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=reason,
    )


def _advisory_result(warning: str) -> CharterPreflightResult:
    return CharterPreflightResult(
        passed=True,
        checks=[],
        auto_refresh_applied=False,
        auto_refresh_actions=[],
        blocked_reason=None,
        warnings=[warning],
    )


# ---------------------------------------------------------------------------
# Persistence helpers (.kittify/preflight-warning.json)
# ---------------------------------------------------------------------------


def test_write_then_read_preflight_warning_roundtrip(tmp_path: Path) -> None:
    reason = "doctrine stale; run: spec-kitty charter sync"
    write_preflight_warning(tmp_path, reason)

    path = preflight_warning_path(tmp_path)
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {"blocked_reason": reason}

    assert read_preflight_warning(tmp_path) == reason


def test_clear_preflight_warning_is_idempotent(tmp_path: Path) -> None:
    # Clear when absent — no error.
    clear_preflight_warning(tmp_path)
    assert read_preflight_warning(tmp_path) is None

    write_preflight_warning(tmp_path, "x")
    clear_preflight_warning(tmp_path)
    assert read_preflight_warning(tmp_path) is None


def test_read_preflight_warning_returns_none_for_corrupt_payload(tmp_path: Path) -> None:
    path = preflight_warning_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    assert read_preflight_warning(tmp_path) is None


# ---------------------------------------------------------------------------
# Hook wiring — dashboard CLI command
# ---------------------------------------------------------------------------


def test_dashboard_hook_persists_warning_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``run_preflight_for_dashboard`` returns the result; the CLI persists it.

    We exercise the persistence directly (the CLI command's branching is
    a thin wrapper) so the test stays focused on the contract.
    """
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    monkeypatch.setattr(
        hook_mod,
        "run_charter_preflight",
        lambda **_: _fail_result("synthesized DRG missing; run: spec-kitty charter synthesize"),
    )

    result = hook_mod.run_preflight_for_dashboard(tmp_path)
    assert result.passed is False
    assert result.blocked_reason is not None

    # Mimic the dashboard CLI branch: write the warning when not-passed.
    write_preflight_warning(tmp_path, result.blocked_reason)
    assert read_preflight_warning(tmp_path) == result.blocked_reason


def test_dashboard_hook_keeps_its_own_consumer_label_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """#4731: the consumer label is parameterised, but dashboard keeps its own."""
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    monkeypatch.setattr(
        hook_mod,
        "run_charter_preflight",
        lambda **_: _fail_result("synthesized DRG missing; run: spec-kitty charter synthesize"),
    )

    with caplog.at_level(logging.WARNING, logger=hook_mod.__name__):
        hook_mod.run_preflight_for_dashboard(tmp_path)

    assert any("consumer=dashboard" in record.getMessage() for record in caplog.records)


def test_dashboard_hook_clears_warning_on_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On clean success the persisted warning is cleared, even if one was stale."""
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    write_preflight_warning(tmp_path, "stale from a previous run")
    monkeypatch.setattr(hook_mod, "run_charter_preflight", lambda **_: _pass_result())

    result = hook_mod.run_preflight_for_dashboard(tmp_path)
    assert result.passed is True

    # Mimic the dashboard CLI branch: clear on clean success.
    clear_preflight_warning(tmp_path)
    assert read_preflight_warning(tmp_path) is None


def test_dashboard_hook_does_not_warning_log_optional_missing_charter(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Fresh projects without charter state are advisory, not warning-level spam."""
    import subprocess

    from specify_cli.charter_runtime.preflight import hook as hook_mod

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)

    with caplog.at_level(logging.WARNING, logger=hook_mod.__name__):
        result = hook_mod.run_preflight_for_dashboard(tmp_path)

    assert result.passed is True
    assert result.blocked_reason is None
    assert result.warnings
    assert caplog.records == []


def test_dashboard_hook_surfaces_legacy_bundle_warning_detail(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """#3498/#2831: legacy charter.md-only bundle gets the detailed, distinct warning.

    Uses the REAL runner (no mocking of ``run_charter_preflight``) to prove
    the shared result carries detailed copy. The separate command-boundary
    test below proves dashboard-specific persistence renders that advisory.
    """
    import subprocess

    from specify_cli.charter_runtime.preflight import hook as hook_mod

    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True)
    (charter_dir / "charter.md").write_text("# Charter\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger=hook_mod.__name__):
        result = hook_mod.run_preflight_for_dashboard(tmp_path)

    assert result.passed is True
    assert result.blocked_reason is None
    assert result.warnings
    assert "charter.md" in result.warnings[0]
    assert "spec-kitty charter generate" in result.warnings[0]
    # And it must NOT be the fresh-project warning text.
    assert "not initialized" not in result.warnings[0]
    assert caplog.records == []


def test_dashboard_command_persists_passed_advisory_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A passed advisory reaches the persisted SPA warning instead of being cleared."""
    import importlib

    from specify_cli.charter_runtime.preflight import hook as hook_mod

    dashboard_mod = importlib.import_module("specify_cli.cli.commands.dashboard")
    warning = (
        "a legacy charter.md-only bundle was detected; run "
        "`spec-kitty charter generate --no-from-interview`"
    )
    json_modes: list[bool] = []

    def fake_project_root(*, json_output: bool = False) -> Path:
        json_modes.append(json_output)
        return tmp_path

    monkeypatch.setattr(dashboard_mod, "get_project_root_or_exit", fake_project_root)
    monkeypatch.setattr(
        dashboard_mod,
        "ensure_dashboard_running",
        lambda *_args, **_kwargs: ("http://127.0.0.1:9238", 9238, True),
    )
    monkeypatch.setattr(
        hook_mod,
        "run_preflight_for_dashboard",
        lambda _root: _advisory_result(warning),
    )

    dashboard_mod.dashboard(
        port=None,
        kill=False,
        open_browser=False,
        emit_json=False,
    )

    assert json_modes == [False]
    assert read_preflight_warning(tmp_path) == warning


def test_null_project_config_enabled_still_runs_dashboard_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Null enabled must not silently skip the dashboard warning gate."""
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    config_path = tmp_path / ".kittify" / "config.yaml"
    config_path.parent.mkdir()
    config_path.write_text("preflight:\n  enabled: null\n", encoding="utf-8")
    runner_calls: list[dict] = []

    def _run_charter_preflight(**kwargs):
        runner_calls.append(kwargs)
        return _pass_result()

    monkeypatch.setattr(hook_mod, "run_charter_preflight", _run_charter_preflight)

    result = hook_mod.run_preflight_for_dashboard(tmp_path)

    assert result.passed is True
    assert runner_calls == [
        {
            "repo_root": tmp_path,
            "auto_refresh": False,
            "allow_missing_charter": True,
            "strict": False,
        }
    ]


# ---------------------------------------------------------------------------
# API surface — /api/health response shape
# ---------------------------------------------------------------------------


class _StubRequestHandler:
    """Minimal stand-in for ``DashboardRouter`` to test ``handle_health``."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = str(project_dir)
        self.project_token = "tok-12345"
        self._headers: list[tuple[str, str]] = []
        self._status: int | None = None
        self._body: bytes = b""

    # The handler calls these BaseHTTPRequestHandler methods.
    def send_response(self, code: int) -> None:
        self._status = code

    def send_header(self, key: str, value: str) -> None:
        self._headers.append((key, value))

    def end_headers(self) -> None:
        pass

    class _WFile:
        def __init__(self, parent: _StubRequestHandler) -> None:
            self._parent = parent

        def write(self, data: bytes) -> None:
            self._parent._body += data

    @property
    def wfile(self) -> _StubRequestHandler._WFile:
        return self._WFile(self)

    @property
    def response_payload(self) -> dict:
        return json.loads(self._body.decode("utf-8"))


def _invoke_handle_health(project_dir: Path) -> dict:
    """Invoke ``APIHandler.handle_health`` against a stub request handler."""
    from specify_cli.dashboard.handlers.api import APIHandler

    handler = _StubRequestHandler(project_dir)
    APIHandler.handle_health(handler)  # type: ignore[arg-type]
    assert handler._status == 200
    return handler.response_payload


def test_api_health_omits_preflight_warning_when_absent(tmp_path: Path) -> None:
    """No persisted warning ⇒ ``preflight_warning`` is not present in the payload."""
    clear_preflight_warning(tmp_path)
    payload = _invoke_handle_health(tmp_path)
    assert "preflight_warning" not in payload


def test_api_health_populates_preflight_warning_when_present(tmp_path: Path) -> None:
    """Persisted warning ⇒ exposed verbatim in ``/api/health`` response."""
    reason = "uncommitted generated artifacts; commit or stash and retry"
    write_preflight_warning(tmp_path, reason)

    payload = _invoke_handle_health(tmp_path)
    assert payload["preflight_warning"] == reason


# ---------------------------------------------------------------------------
# #4123: never-git-init-ed projects — charter resolution failure rendering
# ---------------------------------------------------------------------------


def test_dashboard_command_non_git_project_exits_1_with_git_init_advice(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A charter-resolution git failure must not escape the dashboard command
    as a traceback, and must not reach the server-start path (#4123)."""
    import importlib
    import io

    import typer
    from rich.console import Console

    from charter.resolution import NotInsideRepositoryError
    from specify_cli.cli import helpers as helpers_mod
    from specify_cli.charter_runtime.preflight import hook as hook_mod

    dashboard_mod = importlib.import_module("specify_cli.cli.commands.dashboard")

    buf = io.StringIO()
    recording_console = Console(file=buf, force_terminal=False, highlight=False)
    monkeypatch.setattr(dashboard_mod, "console", recording_console)
    monkeypatch.setattr(helpers_mod, "console", recording_console)

    json_modes: list[bool] = []

    def fake_project_root(*, json_output: bool = False) -> Path:
        json_modes.append(json_output)
        return tmp_path

    monkeypatch.setattr(dashboard_mod, "get_project_root_or_exit", fake_project_root)

    def _raise_not_inside_repository(_root: Path) -> None:
        raise NotInsideRepositoryError(tmp_path)

    monkeypatch.setattr(hook_mod, "run_preflight_for_dashboard", _raise_not_inside_repository)

    def _server_must_not_start(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dashboard server must not start on a git-resolution failure")

    monkeypatch.setattr(dashboard_mod, "ensure_dashboard_running", _server_must_not_start)

    with pytest.raises(typer.Exit) as excinfo:
        dashboard_mod.dashboard(
            port=None,
            kill=False,
            open_browser=False,
            emit_json=False,
        )

    assert excinfo.value.exit_code == 1
    assert json_modes == [False]
    output = buf.getvalue()
    assert "not inside a git repository" in output
    assert "git init" in output
    # The old misdirection from the generic handler ("re-run init") is gone.
    assert "spec-kitty init ." not in output
