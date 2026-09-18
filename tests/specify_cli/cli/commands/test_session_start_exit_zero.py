"""Regression (#4703): the ``session-start`` hook must exit 0 unconditionally,
even when the runtime bootstrap that ``main_callback`` runs before dispatch would
fail.

``session_start()`` guarantees exit 0 via its own ``except Exception: pass``, but
that guard cannot catch a failure that happens in ``main_callback`` *before* the
command is dispatched. ``ensure_runtime()`` (e.g. #4703's Windows self-held-lock
crash) and the startup project gates (``check_schema_version`` can ``SystemExit``
on a stale project) both run there. The fix gives ``session-start`` the same
startup-fast-path posture as the live-work hook: neither the global runtime
repair nor the startup gates run before it, so ``session_start()`` alone owns the
exit-0 contract.

The fast-path detector reads ``sys.argv`` directly (like ``next`` and the
live-work hook), so the integration tests patch ``sys.argv``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import specify_cli
from specify_cli import _is_session_start_invocation

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


class TestSessionStartInvocationDetector:
    """The detector must recognize session-start and nothing else."""

    @pytest.mark.parametrize(
        "argv,expected",
        [
            (["spec-kitty", "session-start"], True),
            (["spec-kitty", "session-start", "--foo"], True),
            (["spec-kitty", "-x", "session-start"], True),
            (["spec-kitty", "session-stop"], False),
            (["spec-kitty", "next"], False),
            (["spec-kitty", "live-work", "hook", "claude-code"], False),
            (["spec-kitty", "doctor", "channel"], False),
            (["spec-kitty"], False),
        ],
    )
    def test_detector(self, argv: list[str], expected: bool) -> None:
        assert _is_session_start_invocation(argv) is expected


class TestSessionStartExitZeroThroughMainCallback:
    """AC-4: session-start exits 0 through the full app even when the pre-dispatch
    bootstrap / startup gates would abort."""

    @pytest.fixture()
    def isolated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """A cwd with no ``.kittify/`` so session_start finds no project and
        stays silent — the exit-0 path under test.

        No ``SPEC_KITTY_HOME`` pin is needed: session-start takes the
        startup-fast-path, so ``ensure_runtime`` (the only global-home reader)
        never runs, and the per-worker HOME isolation (conftest, WP04) already
        keeps the real ``~/.spec-kitty`` untouched.
        """
        monkeypatch.chdir(tmp_path)
        return tmp_path

    def test_exit_zero_when_ensure_runtime_would_raise(
        self,
        isolated: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """If ``ensure_runtime`` (the #4703 crash) ran before dispatch it would
        abort session-start with exit 1. The fast-path skips it — assert it is
        never called and the command exits 0.
        """
        import specify_cli.runtime.bootstrap as bootstrap

        def _boom() -> None:
            raise RuntimeError("[Errno 13] Permission denied")

        monkeypatch.setattr(bootstrap, "ensure_runtime", _boom)
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "session-start"])

        app = specify_cli._build_app()
        result = runner.invoke(app, ["session-start"])
        assert result.exit_code == 0, result.output

    def test_exit_zero_when_startup_gate_would_system_exit(
        self,
        isolated: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """NFR-003: the schema gate's ``SystemExit`` on a stale project must not
        break session-start either — the startup project gates are skipped, not
        just ``ensure_runtime``. Mirrors the live-work hook, not ``next``.
        """

        def _stale_schema_exit(ctx: object) -> None:
            raise SystemExit(1)

        monkeypatch.setattr(specify_cli, "_run_startup_project_gates", _stale_schema_exit)
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "session-start"])

        app = specify_cli._build_app()
        result = runner.invoke(app, ["session-start"])
        assert result.exit_code == 0, result.output
