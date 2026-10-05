"""Feedback Survey bounded context.

A **Feedback Survey** is the short, optional questionnaire (1-5 rating, "What
would you change?", optional email, "Send feedback?") offered at a Survey
Trigger or on demand. A **Feedback Submission** is the allowlisted, anonymous
payload built from a completed survey after explicit consent.

This package exports the shared value types only; callers import the
behavioural modules (``preferences``, ``eligibility``, ...) by path.
"""

from __future__ import annotations

from specify_cli.feedback.models import (
    Harness,
    OfferDecision,
    OfferReason,
    Rating,
    SurveyAnswers,
    SurveyTrigger,
    normalize_harness,
)

__all__ = [
    "Harness",
    "OfferDecision",
    "OfferReason",
    "Rating",
    "SurveyAnswers",
    "SurveyTrigger",
    "normalize_harness",
]
