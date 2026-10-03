"""Contract test: Feedback Submission payloads match the mission wire schema.

Source of truth: ``kitty-specs/in-harness-feedback-survey-01M3PK9W/contracts/
feedback-submission.schema.json``. The fixture under ``fixtures/`` is a
verbatim copy for offline validation (WP03 / T018).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from specify_cli.feedback.models import Rating, SurveyAnswers, SurveyTrigger, normalize_harness
from specify_cli.feedback.payload import ContextFields, build_submission

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SCHEMA_PATH = Path(__file__).parent / "fixtures" / "feedback-submission.schema.json"


@pytest.fixture(scope="module")
def validator() -> Draft202012Validator:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _context(trigger: SurveyTrigger) -> ContextFields:
    return ContextFields(
        spec_kitty_version="3.2.7",
        distribution="spec-kitty-cli",
        trigger=trigger,
        harness=normalize_harness("cli"),
        os="linux",
        mission_type="software-dev" if trigger is not SurveyTrigger.ON_DEMAND else None,
    )


@pytest.mark.parametrize("trigger", list(SurveyTrigger))
@pytest.mark.parametrize("with_comment", [False, True])
@pytest.mark.parametrize("with_email", [False, True])
def test_build_submission_matches_schema(
    validator: Draft202012Validator,
    trigger: SurveyTrigger,
    with_comment: bool,
    with_email: bool,
) -> None:
    answers = SurveyAnswers(
        rating=Rating(3),
        comment="tighten the prompt" if with_comment else None,
        email="reviewer@example.test" if with_email else None,
    )
    payload = build_submission(answers, _context(trigger))
    errors = sorted(validator.iter_errors(payload), key=lambda e: e.path)
    assert errors == [], f"schema errors: {[e.message for e in errors]}"


def test_extra_key_fails_schema_negative_control(validator: Draft202012Validator) -> None:
    payload = build_submission(
        SurveyAnswers(rating=Rating(1)),
        _context(SurveyTrigger.MISSION_END),
    )
    # Positive control: the clean payload validates.
    validator.validate(payload)

    poisoned = dict(payload)
    poisoned["repo"] = "x"
    errors = list(validator.iter_errors(poisoned))
    assert errors, "extra key must fail validation (negative control)"
