"""Unit tests for the agent protocol service (WP04 / T020–T022)."""

from __future__ import annotations

import json

import pytest
from kernel.clock import UTC, datetime, timedelta
from specify_cli.distribution.profile import stock_distribution_profile
from specify_cli.feedback.endpoint import ENV_FEEDBACK_URL
from specify_cli.feedback.models import SurveyTrigger
from specify_cli.feedback.preferences import load_preferences, preferences_path

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ENDPOINT = "https://feedback.example.test/v1"
_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
_AUTO = SurveyTrigger.MISSION_END


@pytest.fixture
def endpoint_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        stock_distribution_profile,
    )
    return {ENV_FEEDBACK_URL: _ENDPOINT}


def test_agent_check_in_ci_leaves_preferences_untouched(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    monkeypatch.setattr("specify_cli.feedback.agent_protocol.is_ci_env", lambda: True)
    payload = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)

    assert payload["action"] == "none"
    assert payload["reason"] == "ci"
    assert not preferences_path().exists()


def test_agent_check_twice_within_seven_days_is_throttled(
    endpoint_env: dict[str, str],
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    first = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    second = agent_check(_AUTO, "cursor", now=_NOW + timedelta(days=1), env=endpoint_env)

    assert first["action"] == "prompt"
    assert second["action"] == "none"
    assert second["reason"] == "throttled"
    prefs = load_preferences()
    assert getattr(prefs, "last_shown_at", None) == _NOW


def test_agent_submit_consent_must_be_exact_yes(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback import sender as sender_mod
    from specify_cli.feedback.agent_protocol import agent_submit

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    calls: list[object] = []
    monkeypatch.setattr(sender_mod, "hand_off", lambda *a, **k: calls.append(1) or True)

    for bad in ("YES", "true", "Yes", None, ""):
        result = agent_submit(
            _AUTO,
            "cursor",
            rating=3,
            comment=None,
            email=None,
            consent=bad,
        )
        assert result["status"] == "not_sent", bad
    assert calls == []

    ok = agent_submit(
        _AUTO,
        "cursor",
        rating=3,
        comment=None,
        email=None,
        consent="yes",
    )
    assert ok["status"] == "handed_off"
    assert len(calls) == 1


def test_agent_submit_result_never_contains_comment_or_email(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback import sender as sender_mod
    from specify_cli.feedback.agent_protocol import agent_submit

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    monkeypatch.setattr(sender_mod, "hand_off", lambda *a, **k: True)

    secret_comment = "UNIQUE_COMMENT_TOKEN_WP04"
    secret_email = "unique-wp04@example.test"
    result = agent_submit(
        _AUTO,
        "cursor",
        rating=4,
        comment=secret_comment,
        email=secret_email,
        consent="yes",
    )
    dumped = json.dumps(result)
    assert secret_comment not in dumped
    assert secret_email not in dumped
    assert result["status"] == "handed_off"


def test_agent_choice_never_then_check_is_prompts_off(
    endpoint_env: dict[str, str],
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check, agent_choice

    choice = agent_choice("never", _AUTO)
    assert choice["status"] == "prompts_off"

    check = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    assert check["action"] == "none"
    assert check["reason"] == "prompts_off"


def test_agent_choice_rejects_unknown_value() -> None:
    from specify_cli.feedback.agent_protocol import agent_choice

    with pytest.raises(ValueError, match="unsupported agent choice"):
        # Intentional invalid choice: runtime must raise; Literal typing forbids it.
        agent_choice("maybe", _AUTO)  # type: ignore[arg-type]


def test_agent_submit_normalizes_unknown_mission_type(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback import sender as sender_mod
    from specify_cli.feedback.agent_protocol import agent_submit

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    captured: list[dict[str, object]] = []

    def _capture(body: dict[str, object], url: str) -> bool:
        captured.append(dict(body))
        return True

    monkeypatch.setattr(sender_mod, "hand_off", _capture)

    agent_submit(
        _AUTO,
        "cursor",
        rating=2,
        comment=None,
        email=None,
        consent="yes",
        mission_type="my-cool-mission-name",
    )
    assert len(captured) == 1
    assert captured[0]["mission_type"] == "other"


def test_normalize_mission_type_blank_and_known() -> None:
    from specify_cli.feedback.agent_protocol import normalize_mission_type

    assert normalize_mission_type(None) is None
    assert normalize_mission_type("   ") is None
    assert normalize_mission_type("software-dev") == "software-dev"
    assert normalize_mission_type("research") == "research"


def test_agent_check_swallows_unexpected_errors(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback import agent_protocol

    def _boom(**_kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(agent_protocol, "resolve_feedback_endpoint", _boom)
    payload = agent_protocol.agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    assert payload["action"] == "none"
    assert payload["reason"] == "preferences_unreadable"


def test_agent_submit_swallows_unexpected_errors(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback import agent_protocol

    def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    monkeypatch.setattr(agent_protocol, "build_and_hand_off", _boom)
    payload = agent_protocol.agent_submit(
        _AUTO,
        "cursor",
        rating=3,
        comment=None,
        email=None,
        consent="yes",
    )
    assert payload["status"] == "not_sent"


def test_agent_submit_honours_build_and_hand_off_outcomes(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback import agent_protocol

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    monkeypatch.setattr(agent_protocol, "build_and_hand_off", lambda *_a, **_k: "no_endpoint")
    assert agent_protocol.agent_submit(_AUTO, "cursor", rating=1, comment=None, email=None, consent="yes")["status"] == "no_endpoint"

    monkeypatch.setattr(agent_protocol, "build_and_hand_off", lambda *_a, **_k: "not_sent")
    assert agent_protocol.agent_submit(_AUTO, "cursor", rating=1, comment=None, email=None, consent="yes")["status"] == "not_sent"


def test_agent_submit_reports_all_invalid_fields_together_and_sends_nothing(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback import agent_protocol, sender as sender_mod

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    handed: list[object] = []
    monkeypatch.setattr(sender_mod, "hand_off", lambda *a, **k: handed.append(1) or True)
    built: list[object] = []
    monkeypatch.setattr(
        agent_protocol,
        "build_and_hand_off",
        lambda *a, **k: built.append(1) or "handed_off",
    )

    result = agent_protocol.agent_submit(
        _AUTO,
        "cursor",
        rating="9",
        comment="fine",
        email="a@example.test, b@example.test",
        consent="yes",
    )

    assert result["status"] == "invalid_input"
    assert result["errors"] == ["rating_out_of_range", "email_malformed"]
    assert built == []
    assert handed == []


@pytest.mark.parametrize(
    ("rating", "email", "expected"),
    [
        ("0", None, ["rating_out_of_range"]),
        (None, None, ["rating_out_of_range"]),
        (True, None, ["rating_out_of_range"]),
        (" 5 ", None, ["rating_out_of_range"]),
        (3, "a@b", ["email_malformed"]),
        (3, "a@@example.test", ["email_malformed"]),
    ],
)
def test_agent_submit_single_invalid_field_sends_nothing(
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    rating: str | int | None,
    email: str | None,
    expected: list[str],
) -> None:
    from specify_cli.feedback import agent_protocol

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    built: list[object] = []
    monkeypatch.setattr(
        agent_protocol,
        "build_and_hand_off",
        lambda *a, **k: built.append(1) or "handed_off",
    )

    result = agent_protocol.agent_submit(
        _AUTO,
        "cursor",
        rating=rating,
        comment=None,
        email=email,
        consent="yes",
    )

    assert result["status"] == "invalid_input"
    assert result["errors"] == expected
    assert built == []
