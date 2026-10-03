"""Acceptance: Feedback Submission fire-and-forget delivery (WP03 / T013).

Pins FR-014 / NFR-001 / NFR-002 / C-003 against a real loopback HTTP server.
Driven through ``build_and_hand_off`` / ``hand_off`` — the production entry
points WP04–WP06 will call. Never talks to a non-loopback address.
"""

from __future__ import annotations

import time

import pytest

from specify_cli.feedback.endpoint import ResolvedEndpoint
from specify_cli.feedback.models import Rating, SurveyAnswers, SurveyTrigger, normalize_harness
from tests.specify_cli.feedback.loopback_server import closed_port, loopback_server

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ALLOWED_KEYS = frozenset(
    {
        "submission_format_version",
        "rating",
        "comment",
        "email",
        "spec_kitty_version",
        "distribution",
        "trigger",
        "harness",
        "os",
        "mission_type",
    }
)

_AUTH_HEADERS = frozenset({"authorization", "cookie", "proxy-authorization"})

_COMMENT = "make the survey shorter"
_EMAIL = "user@example.test"
_RATING = 4


def _answers(*, email: str | None = None) -> SurveyAnswers:
    return SurveyAnswers(rating=Rating(_RATING), comment=_COMMENT, email=email)


def _context():
    from specify_cli.feedback.payload import collect_context

    return collect_context(
        SurveyTrigger.MISSION_END,
        normalize_harness("cursor"),
        mission_type="software-dev",
    )


def _endpoint(url: str) -> ResolvedEndpoint:
    return ResolvedEndpoint(url=url, source="env", rejected_reason=None)


def test_confirmed_submission_arrives_once_with_allowlisted_body() -> None:
    from specify_cli.feedback.sender import build_and_hand_off

    with loopback_server("ok") as server:
        outcome = build_and_hand_off(
            _answers(email=None),
            _context(),
            _endpoint(server.url),
            consent=True,
        )
        assert outcome == "handed_off"
        assert server.wait_for(1, timeout=5.0), f"no request received: {server.received!r}"

        body, headers = server.received[0]
        assert set(body) <= _ALLOWED_KEYS
        # Positive control: expected values are present on the same captured body.
        assert body["rating"] == _RATING
        assert body["trigger"] == "mission_end"
        assert body["harness"] == "cursor"
        assert "email" not in body

        header_names = {k.lower() for k in headers}
        assert header_names.isdisjoint(_AUTH_HEADERS)
        # Positive control: Content-Type is present.
        assert headers.get("Content-Type") == "application/json" or headers.get("content-type") == "application/json"


def test_email_present_when_provided() -> None:
    from specify_cli.feedback.sender import build_and_hand_off

    with loopback_server("ok") as server:
        build_and_hand_off(
            _answers(email=_EMAIL),
            _context(),
            _endpoint(server.url),
            consent=True,
        )
        assert server.wait_for(1, timeout=5.0)
        body, _headers = server.received[0]
        assert body["email"] == _EMAIL


@pytest.mark.parametrize("mode", ["hang", "error", "closed"])
def test_hand_off_returns_fast_and_silent_on_endpoint_failure(
    mode: str,
    capfd: pytest.CaptureFixture[str],
) -> None:
    from specify_cli.feedback.payload import build_submission
    from specify_cli.feedback.sender import hand_off

    body = build_submission(_answers(), _context())

    if mode == "closed":
        with closed_port() as url:
            started = time.monotonic()
            result = hand_off(body, url)
            elapsed = time.monotonic() - started
    else:
        with loopback_server(mode) as server:  # type: ignore[arg-type]
            started = time.monotonic()
            result = hand_off(body, server.url)
            elapsed = time.monotonic() - started

    assert result is True or result is False  # never raises; spawn may succeed
    assert elapsed < 1.0, f"hand_off blocked for {elapsed:.3f}s under mode={mode}"
    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_without_consent_sends_nothing_positive_control_with_consent() -> None:
    from specify_cli.feedback.sender import build_and_hand_off

    with loopback_server("ok") as server:
        outcome = build_and_hand_off(
            _answers(),
            _context(),
            _endpoint(server.url),
            consent=False,
        )
        assert outcome == "not_sent"
        time.sleep(0.3)
        assert server.received == []

        # Positive control on the same fixture: consent=True receives one.
        outcome_yes = build_and_hand_off(
            _answers(),
            _context(),
            _endpoint(server.url),
            consent=True,
        )
        assert outcome_yes == "handed_off"
        assert server.wait_for(1, timeout=5.0)
        assert len(server.received) == 1
