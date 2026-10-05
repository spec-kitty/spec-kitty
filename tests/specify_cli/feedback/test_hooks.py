"""Unit tests for ``specify_cli.feedback.hooks`` (WP06 / T035).

Table-drives gate outcomes and form results. Never talks to a non-loopback
address; sender / form / eligibility collaborators are monkeypatched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from specify_cli.feedback.models import OfferDecision, OfferReason, Rating, SurveyAnswers, SurveyTrigger
from specify_cli.feedback.terminal_form import FormResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _prompt_decision(trigger: SurveyTrigger = SurveyTrigger.MISSION_END) -> OfferDecision:
    return OfferDecision("prompt", OfferReason.ELIGIBLE, trigger)


def _none_decision(
    reason: OfferReason,
    trigger: SurveyTrigger = SurveyTrigger.MISSION_END,
) -> OfferDecision:
    return OfferDecision("none", reason, trigger)


@pytest.fixture
def interactive_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.feedback.hooks.is_interactive", lambda: True)
    monkeypatch.setattr("specify_cli.feedback.hooks.is_ci_env", lambda: False)


@pytest.fixture
def endpoint_ok(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    from specify_cli.feedback.endpoint import ResolvedEndpoint

    resolved = ResolvedEndpoint(url="http://127.0.0.1:9/feedback", source="env", rejected_reason=None)
    monkeypatch.setattr(
        "specify_cli.feedback.hooks.resolve_feedback_endpoint",
        lambda **_kwargs: resolved,
    )
    monkeypatch.setattr("specify_cli.feedback.hooks._endpoint_override", lambda: None)
    return MagicMock()


def test_json_output_short_circuits(monkeypatch: pytest.MonkeyPatch, interactive_ok: None) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    claim = MagicMock()
    monkeypatch.setattr("specify_cli.feedback.hooks.claim_offer", claim)
    offer_after_trigger(SurveyTrigger.MISSION_END, json_output=True)
    claim.assert_not_called()


def test_non_interactive_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    monkeypatch.setattr("specify_cli.feedback.hooks.is_interactive", lambda: False)
    monkeypatch.setattr("specify_cli.feedback.hooks.is_ci_env", lambda: False)
    claim = MagicMock()
    monkeypatch.setattr("specify_cli.feedback.hooks.claim_offer", claim)
    offer_after_trigger(SurveyTrigger.MISSION_END, json_output=False)
    claim.assert_not_called()


def test_ci_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    monkeypatch.setattr("specify_cli.feedback.hooks.is_interactive", lambda: True)
    monkeypatch.setattr("specify_cli.feedback.hooks.is_ci_env", lambda: True)
    claim = MagicMock()
    monkeypatch.setattr("specify_cli.feedback.hooks.claim_offer", claim)
    offer_after_trigger(SurveyTrigger.MISSION_END, json_output=False)
    claim.assert_not_called()


def test_on_demand_trigger_is_not_automatic(monkeypatch: pytest.MonkeyPatch, interactive_ok: None) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    claim = MagicMock()
    monkeypatch.setattr("specify_cli.feedback.hooks.claim_offer", claim)
    offer_after_trigger(SurveyTrigger.ON_DEMAND, json_output=False)
    claim.assert_not_called()


def test_claim_none_skips_form(
    monkeypatch: pytest.MonkeyPatch,
    interactive_ok: None,
    endpoint_ok: MagicMock,
) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    monkeypatch.setattr(
        "specify_cli.feedback.hooks.claim_offer",
        lambda *a, **k: _none_decision(OfferReason.THROTTLED),
    )
    form = MagicMock()
    monkeypatch.setattr("specify_cli.feedback.hooks.run_form", form)
    offer_after_trigger(SurveyTrigger.MISSION_END, json_output=False)
    form.assert_not_called()


@pytest.mark.parametrize(
    "outcome",
    ["skipped", "declined", "aborted"],
)
def test_form_quiet_outcomes(
    monkeypatch: pytest.MonkeyPatch,
    interactive_ok: None,
    endpoint_ok: MagicMock,
    outcome: str,
) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    monkeypatch.setattr(
        "specify_cli.feedback.hooks.claim_offer",
        lambda *a, **k: _prompt_decision(),
    )
    monkeypatch.setattr(
        "specify_cli.feedback.hooks.run_form",
        lambda **_k: FormResult(outcome=outcome, answers=None),  # type: ignore[arg-type]
    )
    hand_off = MagicMock()
    monkeypatch.setattr("specify_cli.feedback.hooks.build_and_hand_off", hand_off)
    never = MagicMock()
    monkeypatch.setattr("specify_cli.feedback.hooks.set_automatic_prompts", never)

    offer_after_trigger(SurveyTrigger.PLANNING_COMPLETE, json_output=False)
    hand_off.assert_not_called()
    never.assert_not_called()


def test_form_never_disables_prompts(
    monkeypatch: pytest.MonkeyPatch,
    interactive_ok: None,
    endpoint_ok: MagicMock,
) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    monkeypatch.setattr(
        "specify_cli.feedback.hooks.claim_offer",
        lambda *a, **k: _prompt_decision(),
    )
    monkeypatch.setattr(
        "specify_cli.feedback.hooks.run_form",
        lambda **_k: FormResult(outcome="never", answers=None),
    )
    never = MagicMock(return_value=True)
    monkeypatch.setattr("specify_cli.feedback.hooks.set_automatic_prompts", never)
    hand_off = MagicMock()
    monkeypatch.setattr("specify_cli.feedback.hooks.build_and_hand_off", hand_off)

    offer_after_trigger(SurveyTrigger.OP_CLOSE, json_output=False)
    never.assert_called_once_with(False)
    hand_off.assert_not_called()


def test_form_submitted_hands_off_with_normalized_mission_type(
    monkeypatch: pytest.MonkeyPatch,
    interactive_ok: None,
    endpoint_ok: MagicMock,
) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger
    from specify_cli.feedback.payload import ContextFields

    answers = SurveyAnswers(rating=Rating(4), comment=None, email=None)
    monkeypatch.setattr(
        "specify_cli.feedback.hooks.claim_offer",
        lambda *a, **k: _prompt_decision(),
    )

    def _fake_form(**kwargs: Any) -> FormResult:
        assert kwargs["allow_never"] is True
        assert kwargs["first_question_timeout_s"] == 30.0
        return FormResult(outcome="submitted", answers=answers)

    monkeypatch.setattr("specify_cli.feedback.hooks.run_form", _fake_form)
    captured: dict[str, Any] = {}

    def _hand_off(ans: SurveyAnswers, context: ContextFields, endpoint: object, *, consent: bool) -> str:
        captured["answers"] = ans
        captured["context"] = context
        captured["consent"] = consent
        return "handed_off"

    monkeypatch.setattr("specify_cli.feedback.hooks.build_and_hand_off", _hand_off)
    monkeypatch.setattr(
        "specify_cli.feedback.hooks.collect_context",
        lambda trigger, harness, mission_type: ContextFields(
            spec_kitty_version="0.0.0-test",
            distribution="spec-kitty-cli",
            trigger=trigger,
            harness=harness,
            os="darwin",
            mission_type=mission_type,
        ),
    )

    offer_after_trigger(
        SurveyTrigger.MISSION_END,
        json_output=False,
        mission_type="software-dev",
    )
    assert captured["consent"] is True
    assert captured["answers"] is answers
    assert captured["context"].mission_type == "software-dev"
    assert captured["context"].trigger is SurveyTrigger.MISSION_END


def test_free_form_mission_type_becomes_other(
    monkeypatch: pytest.MonkeyPatch,
    interactive_ok: None,
    endpoint_ok: MagicMock,
) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger
    from specify_cli.feedback.payload import ContextFields

    answers = SurveyAnswers(rating=Rating(3), comment=None, email=None)
    monkeypatch.setattr(
        "specify_cli.feedback.hooks.claim_offer",
        lambda *a, **k: _prompt_decision(),
    )
    monkeypatch.setattr(
        "specify_cli.feedback.hooks.run_form",
        lambda **_k: FormResult(outcome="submitted", answers=answers),
    )
    seen: list[str | None] = []

    def _collect(trigger: SurveyTrigger, harness: object, mission_type: str | None) -> ContextFields:
        seen.append(mission_type)
        return ContextFields(
            spec_kitty_version="0.0.0-test",
            distribution="spec-kitty-cli",
            trigger=trigger,
            harness=harness,  # type: ignore[arg-type]
            os="darwin",
            mission_type=mission_type,
        )

    monkeypatch.setattr("specify_cli.feedback.hooks.collect_context", _collect)
    monkeypatch.setattr("specify_cli.feedback.hooks.build_and_hand_off", MagicMock(return_value="handed_off"))

    offer_after_trigger(
        SurveyTrigger.PLANNING_COMPLETE,
        json_output=False,
        mission_type="my-custom-mission-name",
    )
    assert seen == ["other"]


def test_keyboard_interrupt_inside_form_is_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    interactive_ok: None,
    endpoint_ok: MagicMock,
) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    monkeypatch.setattr(
        "specify_cli.feedback.hooks.claim_offer",
        lambda *a, **k: _prompt_decision(),
    )

    def _boom(**_kwargs: Any) -> FormResult:
        raise KeyboardInterrupt

    monkeypatch.setattr("specify_cli.feedback.hooks.run_form", _boom)
    # Must not propagate.
    assert offer_after_trigger(SurveyTrigger.MISSION_END, json_output=False) is None


def test_exception_inside_claim_is_swallowed(
    monkeypatch: pytest.MonkeyPatch,
    interactive_ok: None,
    endpoint_ok: MagicMock,
) -> None:
    from specify_cli.feedback.hooks import offer_after_trigger

    def _boom(*_a: object, **_k: object) -> OfferDecision:
        raise RuntimeError("prefs exploded")

    monkeypatch.setattr("specify_cli.feedback.hooks.claim_offer", _boom)
    assert offer_after_trigger(SurveyTrigger.MISSION_END, json_output=False) is None


def test_offer_after_op_close_filters_abandoned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.feedback.hooks import offer_after_op_close

    calls: list[object] = []
    monkeypatch.setattr(
        "specify_cli.feedback.hooks.offer_after_trigger",
        lambda *a, **k: calls.append((a, k)),
    )
    offer_after_op_close("abandoned", json_output=False)
    assert calls == []
    offer_after_op_close("done", json_output=False)
    assert len(calls) == 1
    offer_after_op_close("failed", json_output=True)
    assert len(calls) == 2
    assert calls[1][1]["json_output"] is True


def test_mission_type_for_normalizes(tmp_path: Path) -> None:
    from specify_cli.feedback.hooks import mission_type_for

    feature = tmp_path / "kitty-specs" / "demo"
    feature.mkdir(parents=True)
    (feature / "meta.json").write_text(
        '{"mission_type": "software-dev", "mission_slug": "demo"}\n',
        encoding="utf-8",
    )
    assert mission_type_for(tmp_path, "demo") == "software-dev"

    (feature / "meta.json").write_text(
        '{"mission_type": "weird-custom", "mission_slug": "demo"}\n',
        encoding="utf-8",
    )
    assert mission_type_for(tmp_path, "demo") == "other"

    assert mission_type_for(tmp_path, "missing") is None
