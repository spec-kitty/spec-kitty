"""Tests for fail-closed next query mode (FR-004 / WP03 / Issue #1883).

Verifies that ``spec-kitty next`` exits non-zero with a structured
MISSION_NOT_FOUND error — in both human and ``--json`` modes — when the
supplied mission handle does not resolve to an existing mission directory.

Two culprits fixed:
  1. ``query_current_state()`` in ``runtime.next.runtime_bridge`` used to
     return a silent ``mission_state="unknown"`` Decision (exit 0).
  2. ``_resolve_mission_slug()`` in ``next_cmd`` used to swallow
     ``StatusReadPathNotFound`` and return the raw handle, collapsing into
     the same silent-exit path.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app

pytestmark = pytest.mark.fast

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bypass_preflight_and_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass charter preflight and worktree-location guards.

    These tests focus on the mission-not-found error path; they do not
    exercise charter freshness or git context detection.
    """
    from pathlib import Path as _Path

    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult
    from specify_cli.core.context_validation import CurrentContext, ExecutionContext

    ok = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_a, **_kw: ok,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_for_dashboard",
        lambda *_a, **_kw: ok,
    )
    # Make require_main_repo think we are in the main repo.
    _fake_ctx = CurrentContext(
        location=ExecutionContext.MAIN_REPO,
        cwd=_Path.cwd(),
        repo_root=_Path.cwd(),
        worktree_name=None,
        worktree_path=None,
    )
    monkeypatch.setattr(
        "specify_cli.core.context_validation.get_current_context",
        lambda: _fake_ctx,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _invoke_next_query(
    handle: str,
    *,
    json_output: bool = False,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[int, str]:
    """Invoke ``spec-kitty next --mission <handle>`` with a mocked not-found bridge.

    Returns ``(exit_code, combined_output)``.  We patch ``query_current_state``
    on the canonical runtime module so both the legacy shim and the direct
    import path are covered.
    """
    from runtime.next.runtime_bridge import MissionNotFoundError

    def _raise_not_found(agent: object, mission_slug: str, repo_root: object) -> object:
        raise MissionNotFoundError(mission_slug)

    monkeypatch.setattr(
        "runtime.next.runtime_bridge.query_current_state",
        _raise_not_found,
    )

    args = ["next", "--mission", handle]
    if json_output:
        args.append("--json")

    result = runner.invoke(cli_app, args, catch_exceptions=False)
    return result.exit_code, result.output


# ---------------------------------------------------------------------------
# T014 — non-zero exit + named error in human mode
# ---------------------------------------------------------------------------


class TestNextFailClosedHumanMode:
    """spec-kitty next --mission <bad-handle> must exit 1 with a human-readable error."""

    def test_exit_code_is_1_for_missing_mission(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exit_code, _ = _invoke_next_query(
            "no-such-mission-xyz", json_output=False, monkeypatch=monkeypatch
        )
        assert exit_code == 1, f"Expected exit code 1, got {exit_code}"

    def test_output_contains_mission_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exit_code, output = _invoke_next_query(
            "no-such-mission-xyz", json_output=False, monkeypatch=monkeypatch
        )
        assert "Mission not found" in output, (
            f"Expected 'Mission not found' in output:\n{output}"
        )
        assert exit_code == 1

    def test_output_contains_handle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, output = _invoke_next_query(
            "no-such-mission-xyz", json_output=False, monkeypatch=monkeypatch
        )
        assert "no-such-mission-xyz" in output, (
            f"Expected handle 'no-such-mission-xyz' in output:\n{output}"
        )

    def test_output_contains_remediation_hint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, output = _invoke_next_query(
            "no-such-mission-xyz", json_output=False, monkeypatch=monkeypatch
        )
        # #4723: 'spec-kitty mission list' enumerates mission TYPES, never
        # real mission handles, so it cannot reveal a colliding pair of
        # missions — the hint now points at 'spec-kitty doctor topology',
        # which enumerates every mission's real handle.
        assert "spec-kitty doctor topology" in output, (
            f"Expected remediation hint in output:\n{output}"
        )


# ---------------------------------------------------------------------------
# T014 — non-zero exit + named error in --json mode
# ---------------------------------------------------------------------------


class TestNextFailClosedJsonMode:
    """spec-kitty next --mission <bad-handle> --json must exit 1 with structured JSON."""

    def test_exit_code_is_1_in_json_mode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exit_code, _ = _invoke_next_query(
            "no-such-mission-xyz", json_output=True, monkeypatch=monkeypatch
        )
        assert exit_code == 1, f"Expected exit code 1 in JSON mode, got {exit_code}"

    def test_json_has_error_code_mission_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        exit_code, output = _invoke_next_query(
            "no-such-mission-xyz", json_output=True, monkeypatch=monkeypatch
        )
        payload = json.loads(output)
        assert payload.get("error_code") == "MISSION_NOT_FOUND", (
            f"Expected error_code=MISSION_NOT_FOUND; got: {payload}"
        )
        assert exit_code == 1

    def test_json_has_handle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, output = _invoke_next_query(
            "no-such-mission-xyz", json_output=True, monkeypatch=monkeypatch
        )
        payload = json.loads(output)
        assert payload.get("handle") == "no-such-mission-xyz", (
            f"Expected handle='no-such-mission-xyz'; got: {payload}"
        )

    def test_json_has_result_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, output = _invoke_next_query(
            "no-such-mission-xyz", json_output=True, monkeypatch=monkeypatch
        )
        payload = json.loads(output)
        assert payload.get("result") == "error", (
            f"Expected result='error'; got: {payload}"
        )

    def test_json_has_remediation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _, output = _invoke_next_query(
            "no-such-mission-xyz", json_output=True, monkeypatch=monkeypatch
        )
        payload = json.loads(output)
        assert "remediation" in payload, f"Expected 'remediation' key; got: {payload}"
        # #4723: see the human-mode assertion above for why this points at
        # 'doctor topology' now rather than 'mission list'.
        assert "spec-kitty doctor topology" in payload["remediation"]


# ---------------------------------------------------------------------------
# MissionNotFoundError unit tests
# ---------------------------------------------------------------------------


class TestMissionNotFoundErrorClass:
    """Unit tests for the MissionNotFoundError exception class."""

    def test_handle_attribute(self) -> None:
        from runtime.next.runtime_bridge import MissionNotFoundError

        exc = MissionNotFoundError("my-test-mission")
        assert exc.handle == "my-test-mission"

    def test_error_code_attribute(self) -> None:
        from runtime.next.runtime_bridge import MissionNotFoundError

        exc = MissionNotFoundError("my-test-mission")
        assert exc.error_code == "MISSION_NOT_FOUND"

    def test_str_contains_handle(self) -> None:
        from runtime.next.runtime_bridge import MissionNotFoundError

        exc = MissionNotFoundError("my-test-mission")
        assert "my-test-mission" in str(exc)

    def test_is_exception(self) -> None:
        from runtime.next.runtime_bridge import MissionNotFoundError

        exc = MissionNotFoundError("x")
        assert isinstance(exc, Exception)

    def test_default_next_step_points_at_doctor_topology_not_mission_list(
        self,
    ) -> None:
        """#4723: 'spec-kitty mission list' enumerates mission TYPES
        (software-dev, research, …), never real mission handles — following
        it can never reveal a colliding pair of missions. 'spec-kitty doctor
        topology' enumerates every mission's real handle from kitty-specs/."""
        from runtime.next.runtime_bridge import MissionNotFoundError

        exc = MissionNotFoundError("payment")

        assert "spec-kitty doctor topology" in exc.next_step
        assert "spec-kitty mission list" not in exc.next_step
