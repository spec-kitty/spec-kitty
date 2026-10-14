"""Local Decision-Moment interview helper tests (post hosted-surface removal, #6164).

Hosted "Widen Mode" dispatch was removed with the frozen hosted surfaces; the
local Decision-Moment interview loop remains. These tests cover the kept
local helpers in :mod:`specify_cli.cli.commands.charter._widen`:

- ``_get_mission_id`` reads correctly from meta.json.
- ``_is_already_widened`` short-circuits and tolerates store failures.
- ``_resolve_dm_terminal`` applies the correct terminal transition.
- ``_run_blocked_prompt_loop`` resolves locally / defers, re-prompting on
  write-back failure instead of faking terminal progress.
- ``_schedule_inactivity_reminder`` fires on a daemon timer.
- The charter interview completes normally with no ``[w]iden`` affordance.
"""

from __future__ import annotations

import contextlib
import json
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from charter.activation.interview import MINIMAL_QUESTION_ORDER
from rich.console import Console
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import (
    _get_mission_id,
    _is_already_widened,
    _resolve_dm_terminal,
    _schedule_inactivity_reminder,
    app as charter_app,
)

# ---------------------------------------------------------------------------
# Constants / helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "test-charter-dm-mission"
MISSION_ID = "01KWIDENCHARTERTESTMISSION01"

# Number of questions in the minimal profile + 3 metadata prompts (paradigms/directives/tools)
_N_QUESTIONS = len(MINIMAL_QUESTION_ORDER)
_META_PROMPTS = 3  # selected_paradigms, selected_directives, available_tools

runner = CliRunner()


def _setup_repo(tmp_path: Path) -> Path:
    """Create a minimal repo with .kittify/ and mission meta.json."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "charter" / "interview").mkdir(parents=True, exist_ok=True)

    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
        encoding="utf-8",
    )
    return tmp_path


def _make_inputs(answers: list[str], meta: list[str] | None = None) -> str:
    """Build a newline-joined input string."""
    if meta is None:
        meta = [""] * _META_PROMPTS
    return "\n".join(answers + meta) + "\n"


def _invoke_interview(
    tmp_path: Path,
    inputs: str,
    *,
    mission_slug: str | None = MISSION_SLUG,
) -> Any:
    with contextlib.chdir(tmp_path):
        args = ["interview", "--profile", "minimal"]
        if mission_slug is not None:
            args += ["--mission-slug", mission_slug]
        return runner.invoke(charter_app, args, input=inputs, catch_exceptions=False)


def _make_decision_error() -> Exception:
    from specify_cli.decisions.models import DecisionErrorCode
    from specify_cli.decisions.service import DecisionError

    return DecisionError(code=DecisionErrorCode.TERMINAL_CONFLICT)


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestGetMissionId:
    def test_reads_mission_id_from_meta_json(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        result = _get_mission_id(tmp_path, MISSION_SLUG)
        assert result == MISSION_ID

    def test_returns_none_if_meta_missing(self, tmp_path: Path) -> None:
        result = _get_mission_id(tmp_path, "nonexistent-slug")
        assert result is None

    def test_returns_none_if_json_malformed(self, tmp_path: Path) -> None:
        mission_dir = tmp_path / "kitty-specs" / "bad-slug"
        mission_dir.mkdir(parents=True, exist_ok=True)
        (mission_dir / "meta.json").write_text("not json", encoding="utf-8")
        result = _get_mission_id(tmp_path, "bad-slug")
        assert result is None

    def test_returns_none_if_mission_id_key_absent(self, tmp_path: Path) -> None:
        mission_dir = tmp_path / "kitty-specs" / "slug-no-id"
        mission_dir.mkdir(parents=True, exist_ok=True)
        (mission_dir / "meta.json").write_text(json.dumps({"mission_slug": "slug-no-id"}), encoding="utf-8")
        result = _get_mission_id(tmp_path, "slug-no-id")
        assert result is None


class TestIsAlreadyWidened:
    """``_is_already_widened`` is retained for API compatibility.

    Hosted Widen Mode is gone (#6164), so the store is always ``None`` at call
    sites and the helper short-circuits to ``False``.
    """

    def test_returns_false_for_none_store(self) -> None:
        assert _is_already_widened(None, "some-decision-id") is False

    def test_returns_true_when_decision_pending(self) -> None:
        store = MagicMock()
        entry = MagicMock()
        entry.decision_id = "dec-001"
        store.list_pending.return_value = [entry]
        assert _is_already_widened(store, "dec-001") is True
        assert _is_already_widened(store, "dec-002") is False

    def test_returns_false_on_exception(self) -> None:
        bad_store = MagicMock()
        bad_store.list_pending.side_effect = RuntimeError("boom")
        assert _is_already_widened(bad_store, "any") is False


class TestResolveDmTerminal:
    def test_cancel_on_exclamation_cancel(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        cancel_mock = MagicMock()
        with patch(
            "specify_cli.cli.commands.charter._dm_service.cancel_decision",
            cancel_mock,
        ):
            _resolve_dm_terminal(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                decision_id="dec-001",
                actual_answer="!cancel",
                actor="test",
            )
        cancel_mock.assert_called_once()

    def test_resolve_on_nonempty_answer(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        resolve_mock = MagicMock()
        with patch(
            "specify_cli.cli.commands.charter._dm_service.resolve_decision",
            resolve_mock,
        ):
            _resolve_dm_terminal(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                decision_id="dec-001",
                actual_answer="PostgreSQL",
                actor="test",
            )
        resolve_mock.assert_called_once()

    def test_defer_on_empty_answer(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        defer_mock = MagicMock()
        with patch(
            "specify_cli.cli.commands.charter._dm_service.defer_decision",
            defer_mock,
        ):
            _resolve_dm_terminal(
                repo_root=tmp_path,
                mission_slug=MISSION_SLUG,
                decision_id="dec-001",
                actual_answer="",
                actor="test",
            )
        defer_mock.assert_called_once()


# ---------------------------------------------------------------------------
# Blocked-prompt loop (local resolve / defer)
# ---------------------------------------------------------------------------


class TestBlockedPromptWriteBackFailures:
    """Blocked-prompt write-back failures must not fake terminal progress."""

    def test_local_answer_failure_reprompts_before_advancing(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.charter import _run_blocked_prompt_loop

        console = Console(file=StringIO(), highlight=False, markup=False)
        timer = MagicMock()

        with (
            patch.object(console, "input", side_effect=["first answer", "second answer"]),
            patch(
                "specify_cli.cli.commands.charter._widen._schedule_inactivity_reminder",
                return_value=timer,
            ),
            patch(
                "specify_cli.cli.commands.charter._widen._dm_service.resolve_decision",
                side_effect=[_make_decision_error(), MagicMock()],
            ) as mock_resolve,
        ):
            _run_blocked_prompt_loop(
                decision_id="dec-001",
                question_text="Which DB?",
                invited=["Alice"],
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                actor="tester",
            )

        assert mock_resolve.call_count == 2
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "not saved" in output.lower()
        assert "Resolved locally" in output

    def test_defer_failure_reprompts_before_advancing(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands.charter import _run_blocked_prompt_loop

        console = Console(file=StringIO(), highlight=False, markup=False)
        timer = MagicMock()

        with (
            patch.object(console, "input", side_effect=["d", "not ready", "d", "ready"]),
            patch(
                "specify_cli.cli.commands.charter._widen._schedule_inactivity_reminder",
                return_value=timer,
            ),
            patch(
                "specify_cli.cli.commands.charter._widen._dm_service.defer_decision",
                side_effect=[_make_decision_error(), MagicMock()],
            ) as mock_defer,
        ):
            _run_blocked_prompt_loop(
                decision_id="dec-001",
                question_text="Which DB?",
                invited=["Alice"],
                mission_slug=MISSION_SLUG,
                repo_root=tmp_path,
                console=console,
                actor="tester",
            )

        assert mock_defer.call_count == 2
        output = console.file.getvalue()  # type: ignore[union-attr]
        assert "not saved" in output.lower()
        assert "Decision deferred" in output


class TestInactivityReminder:
    """NFR-004: inactivity reminder fires after delay_seconds on a daemon timer."""

    def test_inactivity_timer_fires_at_configured_delay(self) -> None:
        buf = StringIO()
        console = Console(file=buf, highlight=False, markup=True)

        timer = _schedule_inactivity_reminder(console, delay_seconds=0.05)  # type: ignore[arg-type]
        timer.join(timeout=1.0)

        output = buf.getvalue()
        assert "waiting" in output.lower(), f"Inactivity reminder not found in output: {output!r}"

    def test_inactivity_timer_is_daemon(self) -> None:
        buf = StringIO()
        console = Console(file=buf, highlight=False, markup=True)

        timer = _schedule_inactivity_reminder(console, delay_seconds=3600)
        assert timer.daemon is True
        timer.cancel()  # clean up


# ---------------------------------------------------------------------------
# Integration: no widen affordance is ever offered
# ---------------------------------------------------------------------------


class TestWidenAffordanceAbsent:
    """``[w]iden`` must never appear now that hosted Widen Mode is removed."""

    def test_widen_option_not_shown(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        inputs = _make_inputs([""] * _N_QUESTIONS)
        result = _invoke_interview(tmp_path, inputs)
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output

    def test_widen_option_not_shown_without_mission_slug(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        inputs = _make_inputs([""] * _N_QUESTIONS)
        result = _invoke_interview(tmp_path, inputs, mission_slug=None)
        assert result.exit_code == 0, result.output
        assert "[w]iden" not in result.output


# ---------------------------------------------------------------------------
# Regression: existing non-widen charter behavior is unaffected
# ---------------------------------------------------------------------------


class TestNonWidenRegressions:
    """Verify the local charter interview behavior is unaffected."""

    def test_normal_answer_saved_to_yaml(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        inputs = _make_inputs([""] * _N_QUESTIONS)
        result = _invoke_interview(tmp_path, inputs)
        assert result.exit_code == 0, result.output
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()

    def test_defaults_flag_skips_prompts(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        with contextlib.chdir(tmp_path):
            result = runner.invoke(
                charter_app,
                ["interview", "--defaults"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
        assert answers_path.exists()

    def test_json_output_flag(self, tmp_path: Path) -> None:
        _setup_repo(tmp_path)
        with contextlib.chdir(tmp_path):
            result = runner.invoke(
                charter_app,
                ["interview", "--defaults", "--json"],
                catch_exceptions=False,
            )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["result"] == "success"
