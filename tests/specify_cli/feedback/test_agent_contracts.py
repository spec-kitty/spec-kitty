"""Contract tests: agent protocol outputs match the mission JSON schemas (WP04 / T019).

Source of truth:
``kitty-specs/in-harness-feedback-survey-01M3PK9W/contracts/agent-check.schema.json``
and ``.../agent-submit.schema.json``. Fixtures under ``fixtures/`` are verbatim
copies for offline validation; ``test_fixture_schemas_match_mission_contracts``
guards against drift when the mission contract files are present in the
checkout.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from kernel.clock import UTC, datetime
from kernel.locks import machine_file_lock
from specify_cli.distribution.profile import stock_distribution_profile
from specify_cli.feedback.endpoint import ENV_FEEDBACK_URL
from specify_cli.feedback.models import SurveyTrigger
from specify_cli.feedback.preferences import (
    lock_path_for,
    preferences_path,
    set_automatic_prompts,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_FIXTURES = Path(__file__).parent / "fixtures"
_MISSION_CONTRACTS = Path(__file__).resolve().parents[3] / "kitty-specs" / "in-harness-feedback-survey-01M3PK9W" / "contracts"
_ENDPOINT = "https://feedback.example.test/v1"
_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
_AUTO = SurveyTrigger.MISSION_END


@pytest.fixture(scope="module")
def check_validator() -> Draft202012Validator:
    schema = json.loads((_FIXTURES / "agent-check.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture(scope="module")
def submit_validator() -> Draft202012Validator:
    schema = json.loads((_FIXTURES / "agent-submit.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


@pytest.fixture
def endpoint_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Stock profile is dormant; supply a loopback-safe example HTTPS endpoint via env."""
    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        stock_distribution_profile,
    )
    return {ENV_FEEDBACK_URL: _ENDPOINT}


def _assert_valid(validator: Draft202012Validator, payload: dict[str, object]) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    assert errors == [], f"schema errors: {[e.message for e in errors]}; payload={payload!r}"


@pytest.mark.parametrize(
    "name",
    [
        "agent-check.schema.json",
        "agent-submit.schema.json",
        "feedback-submission.schema.json",
    ],
)
def test_fixture_schemas_match_mission_contracts(name: str) -> None:
    """Fixtures must stay byte-identical to mission contracts when those files exist."""
    fixture = _FIXTURES / name
    mission = _MISSION_CONTRACTS / name
    assert fixture.is_file(), f"missing fixture copy: {fixture}"
    if not mission.is_file():
        pytest.skip(f"mission contract {mission} is not present in this checkout (planning artifacts live on the mission primary partition / planning branch)")
    assert fixture.read_bytes() == mission.read_bytes(), f"fixture {name} drifted from mission contract at {mission}"


# --- agent_check -------------------------------------------------------------


def test_agent_check_prompt_matches_schema(
    check_validator: Draft202012Validator,
    endpoint_env: dict[str, str],
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    payload = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    _assert_valid(check_validator, payload)
    assert payload["action"] == "prompt"
    assert payload["reason"] == "eligible"
    assert "survey" in payload


def test_agent_check_no_endpoint_matches_schema(
    check_validator: Draft202012Validator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        stock_distribution_profile,
    )
    payload = agent_check(_AUTO, "cursor", now=_NOW, env={})
    _assert_valid(check_validator, payload)
    assert payload == {
        "schema_version": 1,
        "action": "none",
        "reason": "no_endpoint",
        "trigger": _AUTO.value,
    }


def test_agent_check_throttled_matches_schema(
    check_validator: Draft202012Validator,
    endpoint_env: dict[str, str],
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    first = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    assert first["action"] == "prompt"
    second = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    _assert_valid(check_validator, second)
    assert second["action"] == "none"
    assert second["reason"] == "throttled"


def test_agent_check_prompts_off_matches_schema(
    check_validator: Draft202012Validator,
    endpoint_env: dict[str, str],
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    assert set_automatic_prompts(False) is True
    payload = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    _assert_valid(check_validator, payload)
    assert payload["action"] == "none"
    assert payload["reason"] == "prompts_off"


def test_agent_check_ci_matches_schema(
    check_validator: Draft202012Validator,
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    monkeypatch.setattr("specify_cli.feedback.agent_protocol.is_ci_env", lambda: True)
    payload = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    _assert_valid(check_validator, payload)
    assert payload["action"] == "none"
    assert payload["reason"] == "ci"
    assert not preferences_path().exists()


def test_agent_check_lock_busy_matches_schema(
    check_validator: Draft202012Validator,
    endpoint_env: dict[str, str],
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    prefs = preferences_path()
    with machine_file_lock(lock_path_for(prefs), blocking=False):
        payload = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    _assert_valid(check_validator, payload)
    assert payload["action"] == "none"
    assert payload["reason"] == "lock_busy"


def test_agent_check_preferences_unreadable_matches_schema(
    check_validator: Draft202012Validator,
    endpoint_env: dict[str, str],
) -> None:
    from specify_cli.feedback.agent_protocol import agent_check

    prefs = preferences_path()
    prefs.parent.mkdir(parents=True, exist_ok=True)
    prefs.write_text("{not-json", encoding="utf-8")
    prefs.chmod(0o600)
    payload = agent_check(_AUTO, "cursor", now=_NOW, env=endpoint_env)
    _assert_valid(check_validator, payload)
    assert payload["action"] == "none"
    assert payload["reason"] == "preferences_unreadable"


# --- agent_submit ------------------------------------------------------------


def test_agent_submit_handed_off_matches_schema(
    submit_validator: Draft202012Validator,
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback.agent_protocol import agent_submit
    from specify_cli.feedback import sender as sender_mod

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    calls: list[object] = []
    monkeypatch.setattr(sender_mod, "hand_off", lambda body, url: calls.append((body, url)) or True)

    payload = agent_submit(
        _AUTO,
        "cursor",
        rating=4,
        comment="tighten the prompt",
        email=None,
        consent="yes",
        mission_type="software-dev",
    )
    _assert_valid(submit_validator, payload)
    assert payload["status"] == "handed_off"
    assert len(calls) == 1


def test_agent_submit_not_sent_matches_schema(submit_validator: Draft202012Validator) -> None:
    from specify_cli.feedback.agent_protocol import agent_submit

    payload = agent_submit(
        _AUTO,
        "cursor",
        rating=4,
        comment="secret",
        email="user@example.test",
        consent="no",
    )
    _assert_valid(submit_validator, payload)
    assert payload["status"] == "not_sent"
    dumped = json.dumps(payload)
    assert "secret" not in dumped
    assert "user@example.test" not in dumped


def test_agent_submit_invalid_rating_matches_schema(submit_validator: Draft202012Validator) -> None:
    from specify_cli.feedback.agent_protocol import agent_submit

    payload = agent_submit(
        _AUTO,
        "cursor",
        rating=9,
        comment=None,
        email=None,
        consent="yes",
    )
    _assert_valid(submit_validator, payload)
    assert payload["status"] == "invalid_input"
    assert payload["errors"] == ["rating_out_of_range"]


def test_agent_submit_malformed_email_matches_schema(submit_validator: Draft202012Validator) -> None:
    from specify_cli.feedback.agent_protocol import agent_submit

    payload = agent_submit(
        _AUTO,
        "cursor",
        rating=3,
        comment=None,
        email="not-an-email",
        consent="yes",
    )
    _assert_valid(submit_validator, payload)
    assert payload["status"] == "invalid_input"
    assert payload["errors"] == ["email_malformed"]


def test_agent_submit_no_endpoint_matches_schema(
    submit_validator: Draft202012Validator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback.agent_protocol import agent_submit

    monkeypatch.setattr(
        "specify_cli.feedback.endpoint.resolve_distribution_profile",
        stock_distribution_profile,
    )
    monkeypatch.delenv(ENV_FEEDBACK_URL, raising=False)
    payload = agent_submit(
        _AUTO,
        "cursor",
        rating=2,
        comment=None,
        email=None,
        consent="yes",
    )
    _assert_valid(submit_validator, payload)
    assert payload["status"] == "no_endpoint"


def test_agent_submit_comment_truncated_matches_schema(
    submit_validator: Draft202012Validator,
    endpoint_env: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback import sender as sender_mod
    from specify_cli.feedback.agent_protocol import agent_submit
    from specify_cli.feedback.payload import COMMENT_MAX_LENGTH

    monkeypatch.setenv(ENV_FEEDBACK_URL, endpoint_env[ENV_FEEDBACK_URL])
    monkeypatch.setattr(sender_mod, "hand_off", lambda body, url: True)

    payload = agent_submit(
        _AUTO,
        "cursor",
        rating=5,
        comment="x" * (COMMENT_MAX_LENGTH + 50),
        email=None,
        consent="yes",
    )
    _assert_valid(submit_validator, payload)
    assert payload["status"] == "handed_off"
    assert payload["errors"] == ["comment_truncated"]


# --- agent_choice ------------------------------------------------------------


def test_agent_choice_skip_matches_schema(submit_validator: Draft202012Validator) -> None:
    from specify_cli.feedback.agent_protocol import agent_choice

    payload = agent_choice("skip", _AUTO)
    _assert_valid(submit_validator, payload)
    assert payload == {"schema_version": 1, "status": "skipped"}


def test_agent_choice_never_matches_schema(submit_validator: Draft202012Validator) -> None:
    from specify_cli.feedback.agent_protocol import agent_choice

    payload = agent_choice("never", _AUTO)
    _assert_valid(submit_validator, payload)
    assert payload["status"] == "prompts_off"
    assert "message" in payload


def test_unknown_status_fails_submit_schema_negative_control(
    submit_validator: Draft202012Validator,
) -> None:
    poisoned = {"schema_version": 1, "status": "delivered"}
    errors = list(submit_validator.iter_errors(poisoned))
    assert errors, "unknown status must fail validation (negative control)"
