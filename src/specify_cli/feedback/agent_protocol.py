"""Agent ↔ CLI Feedback Survey handshake (JSON-ready dicts).

WP05 wires these functions to hidden CLI flags. This module never raises to
the agent caller (except :func:`agent_choice` on an invalid choice, which is
a CLI programmer error). Answer text never appears in returned dicts or logs.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Literal

from kernel.clock import datetime
from specify_cli.compat.planner import is_ci_env
from specify_cli.feedback.eligibility import claim_offer
from specify_cli.feedback.endpoint import resolve_feedback_endpoint
from specify_cli.feedback.models import SurveyAnswers, SurveyTrigger, normalize_harness
from specify_cli.feedback.payload import (
    collect_context,
    normalize_comment,
    parse_email,
    parse_rating,
)
from specify_cli.feedback.preferences import Unreadable, load_preferences, set_automatic_prompts
from specify_cli.feedback.sender import build_and_hand_off
from specify_cli.feedback import wording

__all__ = [
    "agent_check",
    "agent_choice",
    "agent_submit",
    "normalize_mission_type",
]

_LOG = logging.getLogger(__name__)

# Built-in mission-type vocabulary (pack stems under missions/mission_types/).
# Unknown values become ``other`` so free-form mission names never ship.
_KNOWN_MISSION_TYPES: frozenset[str] = frozenset(
    {
        "documentation",
        "plan",
        "research",
        "software-dev",
    }
)

_CONSENT_YES = "yes"
_Choice = Literal["skip", "never"]


def normalize_mission_type(value: str | None) -> str | None:
    """Map *value* onto the mission-type vocabulary; unknown becomes ``other``.

    Blank / ``None`` stays absent (``None``). Known built-in ids pass through.
    """
    if value is None:
        return None
    key = value.strip()
    if not key:
        return None
    if key in _KNOWN_MISSION_TYPES:
        return key
    return "other"


def _endpoint_override() -> str | None:
    prefs = load_preferences()
    if isinstance(prefs, Unreadable):
        return None
    override: str | None = prefs.endpoint_override
    return override


def _check_failure(trigger: SurveyTrigger) -> dict[str, object]:
    return {
        "schema_version": 1,
        "action": "none",
        "reason": "preferences_unreadable",
        "trigger": trigger.value,
    }


def agent_check(
    trigger: SurveyTrigger,
    agent: str | None,
    *,
    now: datetime | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Decide whether an agent should present the Feedback Survey. Never raises.

    Passes ``interactive=True`` to :func:`claim_offer` because the agent is
    the human's interactive intermediary; CI still suppresses via
    :func:`is_ci_env`. *agent* is accepted for CLI symmetry and unused here.
    """
    _ = agent  # CLI symmetry / future harness context; does not affect the decision.
    try:
        resolved = resolve_feedback_endpoint(override=_endpoint_override(), env=env)
        decision = claim_offer(
            trigger,
            endpoint_available=resolved.url is not None,
            interactive=True,
            ci=is_ci_env(),
            now=now,
        )
        result: dict[str, object] = {
            "schema_version": 1,
            "action": decision.action,
            "reason": decision.reason.value,
            "trigger": trigger.value,
        }
        if decision.action == "prompt":
            result["survey"] = wording.agent_survey_payload()
        return result
    except Exception:
        _LOG.debug("feedback agent_check failed", exc_info=False)
        return _check_failure(trigger)


def agent_submit(
    trigger: SurveyTrigger,
    agent: str | None,
    *,
    rating: str | int | None,
    comment: str | None,
    email: str | None,
    consent: str | None,
    mission_type: str | None = None,
) -> dict[str, object]:
    """Validate answers, build a submission, and hand it off. Never raises.

    Consent must be the exact string ``\"yes\"`` (case-sensitive). Delivery
    outcome is never reported; the result never includes answer text.
    """
    try:
        if consent != _CONSENT_YES:
            return {
                "schema_version": 1,
                "status": "not_sent",
                "message": wording.NOT_SENT_MESSAGE,
            }

        errors: list[str] = []
        parsed_rating = None if rating is None else parse_rating(rating)
        if parsed_rating is None:
            errors.append("rating_out_of_range")

        email_value, email_ok = parse_email(email)
        if not email_ok:
            errors.append("email_malformed")

        if errors:
            return {
                "schema_version": 1,
                "status": "invalid_input",
                "errors": errors,
            }

        assert parsed_rating is not None  # narrowed by errors check above
        comment_text, truncated = normalize_comment(comment)
        answers = SurveyAnswers(
            rating=parsed_rating,
            comment=comment_text,
            email=email_value,
        )

        resolved = resolve_feedback_endpoint(override=_endpoint_override())
        if resolved.url is None:
            return {
                "schema_version": 1,
                "status": "no_endpoint",
                "message": wording.NO_ENDPOINT_MESSAGE,
            }

        context = collect_context(
            trigger,
            normalize_harness(agent),
            normalize_mission_type(mission_type),
        )
        outcome = build_and_hand_off(answers, context, resolved, consent=True)
        if outcome == "no_endpoint":
            return {
                "schema_version": 1,
                "status": "no_endpoint",
                "message": wording.NO_ENDPOINT_MESSAGE,
            }
        if outcome == "not_sent":
            return {
                "schema_version": 1,
                "status": "not_sent",
                "message": wording.NOT_SENT_MESSAGE,
            }

        result: dict[str, object] = {
            "schema_version": 1,
            "status": "handed_off",
            "message": wording.THANK_YOU,
        }
        if truncated:
            result["errors"] = ["comment_truncated"]
        return result
    except Exception:
        _LOG.debug("feedback agent_submit failed", exc_info=False)
        return {
            "schema_version": 1,
            "status": "not_sent",
            "message": wording.NOT_SENT_MESSAGE,
        }


def agent_choice(choice: _Choice, trigger: SurveyTrigger) -> dict[str, object]:
    """Record skip / don't-ask-again. Raises :class:`ValueError` on unknown *choice*."""
    _ = trigger  # retained for CLI symmetry; skip does not mutate further state.
    if choice == "skip":
        return {"schema_version": 1, "status": "skipped"}
    if choice == "never":
        set_automatic_prompts(False)
        return {
            "schema_version": 1,
            "status": "prompts_off",
            "message": wording.PROMPTS_OFF_MESSAGE,
        }
    raise ValueError(f"unsupported agent choice: {choice!r}")
