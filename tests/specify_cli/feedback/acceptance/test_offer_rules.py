"""Acceptance: automatic Feedback Survey offer rules (spec US2; FR-011, FR-013, FR-018).

Driven only through the production entry points ``claim_offer()`` and
``set_automatic_prompts()``; ``now`` is injected everywhere so no assertion
depends on the real clock.
"""

from __future__ import annotations

import pytest

from kernel.clock import UTC, datetime, timedelta
from specify_cli.feedback.eligibility import claim_offer
from specify_cli.feedback.models import OfferDecision, OfferReason, SurveyTrigger
from specify_cli.feedback.preferences import (
    SurveyPreferences,
    load_preferences,
    preferences_path,
    set_automatic_prompts,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

NOW = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
WEEK = timedelta(days=7)


def _claim(
    now: datetime,
    *,
    trigger: SurveyTrigger = SurveyTrigger.MISSION_END,
    endpoint_available: bool = True,
    interactive: bool = True,
    ci: bool = False,
) -> OfferDecision:
    return claim_offer(
        trigger,
        endpoint_available=endpoint_available,
        interactive=interactive,
        ci=ci,
        now=now,
    )


def _last_shown_at() -> datetime | None:
    prefs = load_preferences(preferences_path())
    assert isinstance(prefs, SurveyPreferences)
    return prefs.last_shown_at


def test_first_automatic_trigger_prompts_and_marks_shown() -> None:
    decision = _claim(NOW)

    assert decision == OfferDecision("prompt", OfferReason.ELIGIBLE, SurveyTrigger.MISSION_END)
    assert _last_shown_at() == NOW


def test_second_trigger_inside_the_week_is_throttled_but_exactly_seven_days_prompts() -> None:
    assert _claim(NOW).action == "prompt"

    throttled = _claim(NOW + timedelta(days=6, hours=23), trigger=SurveyTrigger.OP_CLOSE)
    assert throttled == OfferDecision("none", OfferReason.THROTTLED, SurveyTrigger.OP_CLOSE)
    assert _last_shown_at() == NOW

    # Positive control on the same preferences fixture: the window reopens at exactly 7 days.
    reopened = _claim(NOW + WEEK, trigger=SurveyTrigger.PLANNING_COMPLETE)
    assert reopened == OfferDecision("prompt", OfferReason.ELIGIBLE, SurveyTrigger.PLANNING_COMPLETE)
    assert _last_shown_at() == NOW + WEEK


def test_dont_ask_again_silences_until_re_enabled() -> None:
    # Positive control: offered before opting out.
    assert _claim(NOW).action == "prompt"

    assert set_automatic_prompts(False) is True
    silenced = _claim(NOW + WEEK + timedelta(days=1))
    assert silenced == OfferDecision("none", OfferReason.PROMPTS_OFF, SurveyTrigger.MISSION_END)

    assert set_automatic_prompts(True) is True
    resumed = _claim(NOW + WEEK + timedelta(days=1))
    assert resumed == OfferDecision("prompt", OfferReason.ELIGIBLE, SurveyTrigger.MISSION_END)


def test_non_interactive_run_is_skipped_without_consuming_the_window() -> None:
    skipped = _claim(NOW, interactive=False)

    assert skipped == OfferDecision("none", OfferReason.NON_INTERACTIVE, SurveyTrigger.MISSION_END)
    assert _last_shown_at() is None

    # Positive control on the same fixture: an interactive run at the same moment is offered.
    assert _claim(NOW).action == "prompt"
    assert _last_shown_at() == NOW


def test_non_interactive_run_leaves_an_existing_mark_unchanged() -> None:
    assert _claim(NOW).action == "prompt"

    later = NOW + WEEK + timedelta(days=1)
    assert _claim(later, interactive=False).reason is OfferReason.NON_INTERACTIVE
    assert _last_shown_at() == NOW


def test_ci_run_is_skipped() -> None:
    decision = _claim(NOW, ci=True)

    assert decision == OfferDecision("none", OfferReason.CI, SurveyTrigger.MISSION_END)
    assert _last_shown_at() is None


def test_no_endpoint_means_no_offer() -> None:
    decision = _claim(NOW, endpoint_available=False)

    assert decision == OfferDecision("none", OfferReason.NO_ENDPOINT, SurveyTrigger.MISSION_END)
    assert _last_shown_at() is None


def test_on_demand_prompts_when_throttled_and_prompts_off_and_never_marks() -> None:
    assert _claim(NOW).action == "prompt"
    assert set_automatic_prompts(False) is True

    on_demand = _claim(NOW + timedelta(days=1), trigger=SurveyTrigger.ON_DEMAND)

    assert on_demand == OfferDecision("prompt", OfferReason.ELIGIBLE, SurveyTrigger.ON_DEMAND)
    assert _last_shown_at() == NOW


def test_on_demand_does_not_create_preferences() -> None:
    decision = _claim(NOW, trigger=SurveyTrigger.ON_DEMAND)

    assert decision.action == "prompt"
    assert not preferences_path().exists()
