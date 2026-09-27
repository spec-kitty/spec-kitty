"""T021 — Charter interview emits Decision Moment events.

Tests that verify:
  a. service.open_decision is called once per question with
     origin_flow=OriginFlow.CHARTER and step_id matching "charter.<question_id>".
  b. After a question is answered (non-empty), service.resolve_decision is called
     with the user's answer as final_answer.
  c. After a question is answered with an empty string, service.defer_decision is
     called (NOT resolve_decision).
  d. answers.yaml is written for resolved answers and NOT written for deferred
     answers (preserving spec.md C-005 invariant — writes happen via
     write_interview_answers which is called after ALL answers are collected).
  e. A DecisionError raised by service.open_decision does not abort the interview
     — the charter loop continues and prompts the next question.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from specify_cli.cli.commands.charter import app as charter_app
from specify_cli.decisions.models import DecisionErrorCode, OriginFlow
from specify_cli.decisions.service import DecisionError


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]
MISSION_SLUG = "test-charter-dm-mission"
MISSION_ID = "01KCHARTERTESTMISSION0001"

runner = CliRunner()


def _setup_repo(tmp_path: Path) -> Path:
    """Create a minimal repo structure with .kittify/ and mission meta.json."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    # Charter interview directory for answers.yaml
    (kittify / "charter" / "interview").mkdir(parents=True, exist_ok=True)
    # Mission meta
    mission_dir = tmp_path / "kitty-specs" / MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
        encoding="utf-8",
    )
    return tmp_path


def _invoke_interview(
    tmp_path: Path,
    inputs: str,
    *,
    mission_slug: str | None = None,
    extra_args: list[str] | None = None,
) -> object:
    """Invoke 'charter interview' with the given stdin inputs."""
    with contextlib.chdir(tmp_path):
        args = ["interview", "--defaults"]
        # When we pass --defaults we skip interactive prompts; but we need
        # non-defaults to test the question loop. So we won't pass --defaults
        # and instead supply input lines.
        args = ["interview", "--profile", "minimal"]
        if mission_slug is not None:
            args += ["--mission-slug", mission_slug]
        if extra_args:
            args += extra_args
        return runner.invoke(charter_app, args, input=inputs, catch_exceptions=False)


def _make_open_response(decision_id: str = "01KTESTDECISION000000001") -> MagicMock:
    """Build a mock DecisionOpenResponse."""
    m = MagicMock()
    m.decision_id = decision_id
    return m


# ---------------------------------------------------------------------------
# T021a — open_decision called once per question with correct args
# ---------------------------------------------------------------------------


def test_open_decision_called_per_question(tmp_path: Path) -> None:
    """service.open_decision is called once per charter question."""
    _setup_repo(tmp_path)

    # Minimal profile has 3+ questions; supply one answer line per question
    # plus paradigms/directives/tools prompts
    from charter.activation.interview import MINIMAL_QUESTION_ORDER

    n_questions = len(MINIMAL_QUESTION_ORDER)
    # Supply a non-empty answer for every charter question + 3 meta-fields
    inputs = "\n".join(["my answer"] * n_questions + [""] * 3) + "\n"

    mock_open = MagicMock(return_value=_make_open_response())
    mock_resolve = MagicMock()
    mock_resolve.return_value = MagicMock()

    with (
        patch("specify_cli.cli.commands.charter._dm_service.open_decision", mock_open),
        patch(
            "specify_cli.cli.commands.charter._dm_service.resolve_decision",
            mock_resolve,
        ),
        patch("specify_cli.cli.commands.charter._dm_service.defer_decision"),
    ):
        result = _invoke_interview(tmp_path, inputs, mission_slug=MISSION_SLUG)

    assert result.exit_code == 0, f"charter interview failed: {result.output}"
    assert mock_open.call_count == n_questions

    # Verify each call has origin_flow=CHARTER and step_id="charter.<question_id>"
    for i, question_id in enumerate(MINIMAL_QUESTION_ORDER):
        kw = mock_open.call_args_list[i].kwargs
        assert kw.get("origin_flow") == OriginFlow.CHARTER
        assert kw.get("step_id") == f"charter.{question_id}"
        assert kw.get("input_key") == question_id


# ---------------------------------------------------------------------------
# T021b — resolve_decision called with user's answer as final_answer
# ---------------------------------------------------------------------------


def test_resolve_decision_called_with_answer(tmp_path: Path) -> None:
    """After a non-empty answer, resolve_decision is called with that answer."""
    _setup_repo(tmp_path)

    from charter.activation.interview import MINIMAL_QUESTION_ORDER

    n_questions = len(MINIMAL_QUESTION_ORDER)
    test_answer = "my specific answer"
    inputs = "\n".join([test_answer] * n_questions + [""] * 3) + "\n"

    decision_id = "01KTESTDECISION000000042"
    mock_open = MagicMock(return_value=_make_open_response(decision_id))
    mock_resolve = MagicMock(return_value=MagicMock())

    with (
        patch("specify_cli.cli.commands.charter._dm_service.open_decision", mock_open),
        patch(
            "specify_cli.cli.commands.charter._dm_service.resolve_decision",
            mock_resolve,
        ),
        patch("specify_cli.cli.commands.charter._dm_service.defer_decision"),
    ):
        result = _invoke_interview(tmp_path, inputs, mission_slug=MISSION_SLUG)

    assert result.exit_code == 0, f"charter interview failed: {result.output}"
    assert mock_resolve.call_count == n_questions

    # Every resolve call should carry the decision_id and final_answer
    for resolve_call in mock_resolve.call_args_list:
        kw = resolve_call.kwargs
        assert kw.get("decision_id") == decision_id
        assert kw.get("final_answer") == test_answer


# ---------------------------------------------------------------------------
# T021c — defer_decision called for empty answer (not resolve)
# ---------------------------------------------------------------------------


def test_defer_decision_called_on_empty_answer(tmp_path: Path) -> None:
    """An empty string answer triggers defer_decision, not resolve_decision.

    To produce truly empty answers (not defaults), we patch default_interview
    so all answer defaults are empty strings.
    """
    _setup_repo(tmp_path)

    from charter.activation.interview import MINIMAL_QUESTION_ORDER, default_interview

    # Build a version of the interview data where all answers are empty
    real_data = default_interview(mission="software-dev", profile="minimal")
    empty_answers = dict.fromkeys(MINIMAL_QUESTION_ORDER, "")
    from charter.activation.interview import apply_answer_overrides

    empty_data = apply_answer_overrides(real_data, answers=empty_answers)

    n_questions = len(MINIMAL_QUESTION_ORDER)
    # With empty defaults, hitting Enter produces an empty string for each question
    inputs = "\n" * n_questions + "\n" * 3

    decision_id = "01KTESTDECISION000000099"
    mock_open = MagicMock(return_value=_make_open_response(decision_id))
    mock_defer = MagicMock(return_value=MagicMock())
    mock_resolve = MagicMock()

    with (
        patch("specify_cli.cli.commands.charter._dm_service.open_decision", mock_open),
        patch("specify_cli.cli.commands.charter._dm_service.resolve_decision", mock_resolve),
        patch("specify_cli.cli.commands.charter._dm_service.defer_decision", mock_defer),
        patch(
            "specify_cli.cli.commands.charter.default_interview",
            return_value=empty_data,
        ),
    ):
        result = _invoke_interview(tmp_path, inputs, mission_slug=MISSION_SLUG)

    assert result.exit_code == 0, f"charter interview failed: {result.output}"
    # resolve should not have been called for empty answers
    mock_resolve.assert_not_called()
    assert mock_defer.call_count == n_questions


# ---------------------------------------------------------------------------
# T021d — answers.yaml is written (C-005: write happens after all answers)
# ---------------------------------------------------------------------------


def test_answers_yaml_written_after_interview(tmp_path: Path) -> None:
    """answers.yaml is written after collecting all answers (C-005 preserved)."""
    _setup_repo(tmp_path)

    from charter.activation.interview import MINIMAL_QUESTION_ORDER

    n_questions = len(MINIMAL_QUESTION_ORDER)
    inputs = "\n".join(["answer"] * n_questions + [""] * 3) + "\n"

    with (
        patch(
            "specify_cli.cli.commands.charter._dm_service.open_decision",
            return_value=_make_open_response(),
        ),
        patch("specify_cli.cli.commands.charter._dm_service.resolve_decision", return_value=MagicMock()),
        patch("specify_cli.cli.commands.charter._dm_service.defer_decision"),
    ):
        result = _invoke_interview(tmp_path, inputs, mission_slug=MISSION_SLUG)

    assert result.exit_code == 0, f"charter interview failed: {result.output}"
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    assert answers_path.exists(), "answers.yaml was not written"


# ---------------------------------------------------------------------------
# T021e — DecisionError from open_decision is non-fatal
# ---------------------------------------------------------------------------


def test_open_decision_error_does_not_abort_interview(tmp_path: Path) -> None:
    """A DecisionError raised by open_decision is silently swallowed."""
    _setup_repo(tmp_path)

    from charter.activation.interview import MINIMAL_QUESTION_ORDER

    n_questions = len(MINIMAL_QUESTION_ORDER)
    inputs = "\n".join(["answer"] * n_questions + [""] * 3) + "\n"

    def _failing_open(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise DecisionError(
            code=DecisionErrorCode.MISSION_NOT_FOUND,
            message="simulated failure",
        )

    with patch(
        "specify_cli.cli.commands.charter._dm_service.open_decision",
        side_effect=_failing_open,
    ):
        result = _invoke_interview(tmp_path, inputs, mission_slug=MISSION_SLUG)

    # Charter should still complete successfully despite DM errors
    assert result.exit_code == 0, f"charter interview failed: {result.output}"
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    assert answers_path.exists(), "answers.yaml was not written"


# ---------------------------------------------------------------------------
# T021f — No DM calls when --mission-slug is absent (backwards compat)
# ---------------------------------------------------------------------------


def test_no_dm_calls_without_mission_slug(tmp_path: Path) -> None:
    """When --mission-slug is not provided, no DM service calls are made."""
    _setup_repo(tmp_path)

    from charter.activation.interview import MINIMAL_QUESTION_ORDER

    n_questions = len(MINIMAL_QUESTION_ORDER)
    inputs = "\n".join(["answer"] * n_questions + [""] * 3) + "\n"

    mock_open = MagicMock()
    mock_resolve = MagicMock()
    mock_defer = MagicMock()

    with (
        patch("specify_cli.cli.commands.charter._dm_service.open_decision", mock_open),
        patch("specify_cli.cli.commands.charter._dm_service.resolve_decision", mock_resolve),
        patch("specify_cli.cli.commands.charter._dm_service.defer_decision", mock_defer),
    ):
        # No --mission-slug
        result = _invoke_interview(tmp_path, inputs, mission_slug=None)

    assert result.exit_code == 0, f"charter interview failed: {result.output}"
    mock_open.assert_not_called()
    mock_resolve.assert_not_called()
    mock_defer.assert_not_called()


# ---------------------------------------------------------------------------
# T021g — cancel_decision called when answer is "!cancel" (FR-012)
# ---------------------------------------------------------------------------


def test_cancel_decision_called_on_cancel_sentinel(tmp_path: Path) -> None:
    """FR-012: an answer of '!cancel' triggers cancel_decision, not resolve or defer.

    The '!cancel' sentinel signals that the question is no longer applicable.
    charter continues normally; answers.yaml is still written (C-005 preserved).
    """
    _setup_repo(tmp_path)

    from charter.activation.interview import MINIMAL_QUESTION_ORDER

    n_questions = len(MINIMAL_QUESTION_ORDER)
    # Supply "!cancel" for every question so cancel_decision is called each time
    inputs = "\n".join(["!cancel"] * n_questions + [""] * 3) + "\n"

    decision_id = "01KTESTCANCEL000000000001"
    mock_open = MagicMock(return_value=_make_open_response(decision_id))
    mock_cancel = MagicMock(return_value=MagicMock())
    mock_resolve = MagicMock()
    mock_defer = MagicMock()

    with (
        patch("specify_cli.cli.commands.charter._dm_service.open_decision", mock_open),
        patch("specify_cli.cli.commands.charter._dm_service.cancel_decision", mock_cancel),
        patch("specify_cli.cli.commands.charter._dm_service.resolve_decision", mock_resolve),
        patch("specify_cli.cli.commands.charter._dm_service.defer_decision", mock_defer),
    ):
        result = _invoke_interview(tmp_path, inputs, mission_slug=MISSION_SLUG)

    assert result.exit_code == 0, f"charter interview failed: {result.output}"

    # cancel_decision must be called for each question
    assert mock_cancel.call_count == n_questions

    # resolve and defer must NOT be called
    mock_resolve.assert_not_called()
    mock_defer.assert_not_called()

    # Each cancel call must carry the correct decision_id and a rationale
    for cancel_call in mock_cancel.call_args_list:
        kw = cancel_call.kwargs
        assert kw.get("decision_id") == decision_id
        assert kw.get("rationale"), "cancel must supply a non-empty rationale"

    # answers.yaml is still written (C-005: answers.yaml behavior preserved)
    # Note: "!cancel" is stored as the raw answer; it does not write to answers.yaml
    # because only resolved-with-answer decisions do so (FR-012 final sentence).
    answers_path = tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"
    assert answers_path.exists(), "answers.yaml was not written"
