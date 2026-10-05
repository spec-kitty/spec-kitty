"""Flow-parity tests: the shared input tables behave the same in every flow.

The shared tables (``RATING_CASES``, ``COMMENT_CASES``, ``EMAIL_CASES``) are run
through three entry points:

(a) the parsers in ``payload.py`` (the reference behaviour),
(b) the interactive terminal form (``run_form``), and
(c) the agent hand-off (``agent_submit``) with the sender patched so nothing is
    ever sent.

Each case must produce the same accept/reject outcome and the same cleaned
value in all three flows, and each flow must really call the shared parsers.

Documented differences by design (each asserted explicitly below):

* The terminal form re-asks on an invalid answer instead of returning an
  error, so "rejected" there means "asked again". The test supplies a bounded
  answer queue and observes the re-ask; it never loops.
* The terminal form strips surrounding whitespace from the rating before
  parsing, so ``" 5 "`` and ``"5\\n"`` are accepted there while the strict
  parser (and the agent flow) rejects them.
* An empty rating answer in the terminal form means "skip the survey", not
  "invalid rating".
* Rating cases that are not text (integers, floats, booleans, ``None``) cannot
  be typed at a prompt, so they are exercised through the parser and the agent
  flow only.
* The terminal form stops after a second invalid email; the email is then
  dropped. The test still treats that as a rejection.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from specify_cli.distribution.profile import stock_distribution_profile
from specify_cli.feedback import agent_protocol, terminal_form, wording
from specify_cli.feedback.endpoint import ENV_FEEDBACK_URL
from specify_cli.feedback.models import SurveyAnswers, SurveyTrigger
from specify_cli.feedback.payload import normalize_comment, parse_email, parse_rating

from .test_validation_table import COMMENT_CASES, EMAIL_CASES, RATING_CASES

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TRIGGER = SurveyTrigger.ON_DEMAND
_ENDPOINT = "https://feedback.example.test/v1"
_CONSENT_PROMPT = f"{wording.CONSENT_QUESTION} [y/N]"

# Terminal-form differences by design for rating text (see module docstring).
_TERMINAL_RATING_OVERRIDES: dict[str, int | str] = {
    " 5 ": 5,
    "5\n": 5,
    "": "skipped",
}


class _Recorder:
    """Captures what the agent flow would hand to the sender."""

    def __init__(self) -> None:
        self.answers: list[SurveyAnswers] = []

    def __call__(self, answers: SurveyAnswers, *_args: object, **_kwargs: object) -> str:
        self.answers.append(answers)
        return "handed_off"


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> _Recorder:
    """Point the agent flow at a placeholder endpoint and patch the sender."""
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        stock_distribution_profile,
    )
    monkeypatch.setenv(ENV_FEEDBACK_URL, _ENDPOINT)
    rec = _Recorder()
    monkeypatch.setattr(agent_protocol, "build_and_hand_off", rec)
    return rec


def _agent(
    *,
    rating: Any = 3,
    comment: str | None = None,
    email: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = agent_protocol.agent_submit(
        _TRIGGER,
        "cursor",
        rating=rating,
        comment=comment,
        email=email,
        consent="yes",
    )
    return result


def _terminal(
    *,
    rating: str = "3",
    comment: str = "",
    email: str = "",
) -> tuple[terminal_form.FormResult, dict[str, int]]:
    """Drive the form with a bounded script and count how often each question is asked.

    A prompt asked more times than it has scripted answers raises ``EOFError``,
    which the form turns into outcome ``aborted``; that bounds every re-ask.
    """
    scripts = {
        wording.RATING_QUESTION: [rating],
        wording.comment_question(): [comment],
        wording.EMAIL_QUESTION: [email, email],
        _CONSENT_PROMPT: ["y"],
    }
    asked: dict[str, int] = {}

    def ask(prompt: str) -> str:
        asked[prompt] = asked.get(prompt, 0) + 1
        pending = scripts[prompt]
        if not pending:
            raise EOFError
        return pending.pop(0)

    return terminal_form.run_form(allow_never=False, ask=ask), asked


# --- rating -----------------------------------------------------------------


@pytest.mark.parametrize(("raw", "expected"), RATING_CASES)
def test_rating_parity_parser_and_agent(recorder: _Recorder, raw: Any, expected: int | None) -> None:
    parsed = parse_rating(raw)
    result = _agent(rating=raw)
    if expected is None:
        assert parsed is None
        assert result["status"] == "invalid_input"
        assert result["errors"] == ["rating_out_of_range"]
        assert recorder.answers == []
    else:
        assert parsed is not None and int(parsed) == expected
        assert result["status"] == "handed_off"
        assert int(recorder.answers[0].rating) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(raw, exp) for raw, exp in RATING_CASES if isinstance(raw, str)],
)
def test_rating_parity_terminal_form(raw: str, expected: int | None) -> None:
    result, asked = _terminal(rating=raw)
    if raw in _TERMINAL_RATING_OVERRIDES:
        outcome = _TERMINAL_RATING_OVERRIDES[raw]
        if outcome == "skipped":
            assert result.outcome == "skipped"
        else:
            assert result.outcome == "submitted"
            assert result.answers is not None and int(result.answers.rating) == outcome
        return
    if expected is None:
        # Rejected means re-asked: the second ask has no scripted answer.
        assert asked[wording.RATING_QUESTION] == 2
        assert result.outcome == "aborted"
        assert result.answers is None
    else:
        assert asked[wording.RATING_QUESTION] == 1
        assert result.outcome == "submitted"
        assert result.answers is not None and int(result.answers.rating) == expected


# --- comment ----------------------------------------------------------------


@pytest.mark.parametrize(("raw", "text", "truncated"), COMMENT_CASES)
def test_comment_parity_all_flows(
    recorder: _Recorder,
    raw: str | None,
    text: str | None,
    truncated: bool,
) -> None:
    assert normalize_comment(raw) == (text, truncated)

    agent_result = _agent(comment=raw)
    assert agent_result["status"] == "handed_off"
    assert recorder.answers[0].comment == text
    assert agent_result.get("errors") == (["comment_truncated"] if truncated else None)

    form_result, _asked = _terminal(comment=raw or "")
    assert form_result.outcome == "submitted"
    assert form_result.answers is not None
    assert form_result.answers.comment == text
    assert form_result.comment_truncated is truncated


# --- email ------------------------------------------------------------------


@pytest.mark.parametrize(("raw", "value", "ok"), EMAIL_CASES)
def test_email_parity_all_flows(recorder: _Recorder, raw: str | None, value: str | None, ok: bool) -> None:
    assert parse_email(raw) == (value, ok)

    agent_result = _agent(email=raw)
    form_result, asked = _terminal(email=raw or "")
    assert form_result.outcome == "submitted"
    assert form_result.answers is not None

    if ok:
        assert agent_result["status"] == "handed_off"
        assert recorder.answers[0].email == value
        assert asked[wording.EMAIL_QUESTION] == 1
        assert form_result.answers.email == value
    else:
        # Agent: error and no hand-off. Terminal: asked twice, then dropped.
        assert agent_result["status"] == "invalid_input"
        assert agent_result["errors"] == ["email_malformed"]
        assert recorder.answers == []
        assert asked[wording.EMAIL_QUESTION] == 2
        assert form_result.answers.email is None


# --- every flow really calls the shared parsers ------------------------------


def test_agent_flow_calls_each_shared_parser(recorder: _Recorder, monkeypatch: pytest.MonkeyPatch) -> None:
    spies = {
        "parse_rating": MagicMock(wraps=parse_rating),
        "parse_email": MagicMock(wraps=parse_email),
        "normalize_comment": MagicMock(wraps=normalize_comment),
    }
    for name, spy in spies.items():
        monkeypatch.setattr(agent_protocol, name, spy)

    result = _agent(rating="4", comment="fine", email="person@example.test")

    assert result["status"] == "handed_off"
    for name, spy in spies.items():
        assert spy.call_count == 1, name


def test_terminal_flow_calls_each_shared_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    spies = {
        "parse_rating": MagicMock(wraps=parse_rating),
        "parse_email": MagicMock(wraps=parse_email),
        "normalize_comment": MagicMock(wraps=normalize_comment),
    }
    for name, spy in spies.items():
        monkeypatch.setattr(terminal_form, name, spy)

    result, _asked = _terminal(rating="4", comment="fine", email="person@example.test")

    assert result.outcome == "submitted"
    for name, spy in spies.items():
        assert spy.call_count == 1, name


def test_agent_flow_hands_nothing_off_when_any_answer_is_invalid(recorder: _Recorder) -> None:
    result = _agent(rating="9", comment="fine", email="a@example.test, b@example.test")

    assert result["status"] == "invalid_input"
    assert result["errors"] == ["rating_out_of_range", "email_malformed"]
    assert recorder.answers == []
