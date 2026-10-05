"""Unit tests for Feedback Survey wording: the comment limit is shown up front."""

from __future__ import annotations

import pytest

from specify_cli.feedback import wording
from specify_cli.feedback.payload import COMMENT_MAX_LENGTH

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_comment_question_states_the_limit() -> None:
    assert wording.comment_question() == (f"What would you change? (optional, up to {COMMENT_MAX_LENGTH} characters)")


def test_comment_question_follows_the_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wording, "COMMENT_MAX_LENGTH", 123)
    assert "up to 123 characters" in wording.comment_question()
    assert str(COMMENT_MAX_LENGTH) not in wording.comment_question()


def test_truncated_notice_follows_the_constant(monkeypatch: pytest.MonkeyPatch) -> None:
    assert wording.comment_truncated_notice() == (f"Your comment was truncated to {COMMENT_MAX_LENGTH} characters.")
    monkeypatch.setattr(wording, "COMMENT_MAX_LENGTH", 77)
    assert wording.comment_truncated_notice() == "Your comment was truncated to 77 characters."


def test_agent_survey_payload_carries_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = wording.agent_survey_payload()
    assert payload["comment_question"] == wording.comment_question()
    assert payload["comment_max_length"] == COMMENT_MAX_LENGTH
    monkeypatch.setattr(wording, "COMMENT_MAX_LENGTH", 55)
    patched = wording.agent_survey_payload()
    assert "up to 55 characters" in str(patched["comment_question"])
    assert patched["comment_max_length"] == 55
