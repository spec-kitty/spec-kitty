"""Shared Feedback Survey wording for agents and the terminal form.

Question strings are contract constants (``agent-check.schema.json``);
``comment_max_length`` is sourced from :data:`payload.COMMENT_MAX_LENGTH`
so the agent contract and the payload builder cannot diverge. The comment
question and truncation notice are built from that same constant, so the
limit is stated before the user types and can never drift from enforcement.
"""

from __future__ import annotations

from specify_cli.feedback.payload import COMMENT_MAX_LENGTH

__all__ = [
    "CONSENT_QUESTION",
    "EMAIL_MALFORMED_NOTICE",
    "EMAIL_QUESTION",
    "NO_ENDPOINT_MESSAGE",
    "NOT_SENT_MESSAGE",
    "PROMPTS_OFF_MESSAGE",
    "RATING_QUESTION",
    "RATING_TERMINAL_HINT",
    "THANK_YOU",
    "agent_survey_payload",
    "comment_question",
    "comment_truncated_notice",
]

RATING_QUESTION = "How would you rate your experience? (1-5)"
EMAIL_QUESTION = "Email, only if you want to sign your feedback (optional)"
CONSENT_QUESTION = "Send feedback?"
RATING_TERMINAL_HINT = "Enter to skip, 'never' to stop asking"

THANK_YOU = "Thanks for your feedback."
NOT_SENT_MESSAGE = "Feedback was not sent."
PROMPTS_OFF_MESSAGE = "Automatic feedback prompts are off. Re-enable with: spec-kitty feedback --prompts on"
EMAIL_MALFORMED_NOTICE = "That email looks invalid."
NO_ENDPOINT_MESSAGE = "No feedback endpoint is configured."

_SURVEY_CHOICES: tuple[str, ...] = ("answer", "skip", "never")


def comment_question() -> str:
    """Return the comment question, stating the per-comment character limit."""
    return f"What would you change? (optional, up to {COMMENT_MAX_LENGTH} characters)"


def comment_truncated_notice() -> str:
    """Return the notice shown when a comment exceeded the limit."""
    return f"Your comment was truncated to {COMMENT_MAX_LENGTH} characters."


def agent_survey_payload() -> dict[str, object]:
    """Return the ``survey`` object from the agent-check contract."""
    return {
        "rating_question": RATING_QUESTION,
        "comment_question": comment_question(),
        "email_question": EMAIL_QUESTION,
        "consent_question": CONSENT_QUESTION,
        "comment_max_length": COMMENT_MAX_LENGTH,
        "choices": list(_SURVEY_CHOICES),
    }
