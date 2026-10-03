"""Unit tests for ``specify_cli.feedback.models``."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from specify_cli.agent_utils.directories import AGENT_DIR_TO_KEY
from specify_cli.feedback import models
from specify_cli.feedback.models import (
    CLI_HARNESS,
    OTHER_HARNESS,
    OfferDecision,
    OfferReason,
    Rating,
    SurveyAnswers,
    SurveyTrigger,
    normalize_harness,
)
from specify_cli.skills._agent_roster import SUPPORTED_AGENTS

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("value", [1, 3, 5])
def test_rating_accepts_one_to_five(value: int) -> None:
    rating = Rating(value)

    assert rating.value == value
    assert int(rating) == value


@pytest.mark.parametrize("value", [0, 6, -1])
def test_rating_rejects_out_of_range(value: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 5"):
        Rating(value)


@pytest.mark.parametrize("value", [True, False, 3.0, "3", None])
def test_rating_rejects_non_integers(value: Any) -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        Rating(value)


def test_rating_is_immutable() -> None:
    rating = Rating(4)

    with pytest.raises(dataclasses.FrozenInstanceError):
        rating.value = 5  # type: ignore[misc]  # deliberately mutating a frozen dataclass


def test_survey_answers_defaults_optional_fields_to_none() -> None:
    answers = SurveyAnswers(rating=Rating(2))

    assert answers.comment is None
    assert answers.email is None


@pytest.mark.parametrize(
    ("trigger", "automatic"),
    [
        (SurveyTrigger.PLANNING_COMPLETE, True),
        (SurveyTrigger.MISSION_END, True),
        (SurveyTrigger.OP_CLOSE, True),
        (SurveyTrigger.ON_DEMAND, False),
    ],
)
def test_survey_trigger_is_automatic(trigger: SurveyTrigger, automatic: bool) -> None:
    assert trigger.is_automatic is automatic


def test_survey_trigger_values_match_contract() -> None:
    assert [t.value for t in SurveyTrigger] == ["planning_complete", "mission_end", "op_close", "on_demand"]


def test_offer_reason_values_match_agent_check_contract() -> None:
    # Pinned copy of contracts/agent-check.schema.json -> properties.reason.enum.
    assert [r.value for r in OfferReason] == [
        "eligible",
        "no_endpoint",
        "prompts_off",
        "throttled",
        "non_interactive",
        "ci",
        "preferences_unreadable",
        "clock_skew",
        "lock_busy",
        "trigger_not_eligible",
    ]


@pytest.mark.parametrize("key", sorted({*AGENT_DIR_TO_KEY.values(), *SUPPORTED_AGENTS}))
def test_normalize_harness_keeps_every_known_agent_key(key: str) -> None:
    assert normalize_harness(key) == key


def test_normalize_harness_accepts_cli_and_normalises_case_and_whitespace() -> None:
    assert normalize_harness("cli") == CLI_HARNESS
    assert normalize_harness("  Cursor ") == "cursor"


@pytest.mark.parametrize("value", ["unknown-agent", "", "   ", None, "claude code"])
def test_normalize_harness_maps_anything_else_to_other(value: str | None) -> None:
    assert normalize_harness(value) == OTHER_HARNESS


def test_offer_decision_is_a_frozen_value() -> None:
    decision = OfferDecision("none", OfferReason.CI, SurveyTrigger.OP_CLOSE)

    assert decision == OfferDecision("none", OfferReason.CI, SurveyTrigger.OP_CLOSE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.action = "prompt"  # type: ignore[misc]  # deliberately mutating a frozen dataclass


def test_package_exports_model_names() -> None:
    import specify_cli.feedback as package

    assert set(package.__all__) <= set(models.__all__)
    for name in package.__all__:
        assert getattr(package, name) is getattr(models, name)
