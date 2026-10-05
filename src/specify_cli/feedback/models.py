"""Value types of the Feedback Survey bounded context.

Every type here is an immutable value object that cannot be constructed in an
invalid state. Input validation of free-text answers (comment length, email
shape) is owned by the payload builder; :class:`SurveyAnswers` only carries
values that have already been validated.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NewType

__all__ = [
    "CLI_HARNESS",
    "OTHER_HARNESS",
    "RATING_MAX",
    "RATING_MIN",
    "Harness",
    "OfferAction",
    "OfferDecision",
    "OfferReason",
    "Rating",
    "SurveyAnswers",
    "SurveyTrigger",
    "normalize_harness",
]

RATING_MIN = 1
RATING_MAX = 5


class SurveyTrigger(StrEnum):
    """The moment at which a Feedback Survey is offered."""

    PLANNING_COMPLETE = "planning_complete"
    MISSION_END = "mission_end"
    OP_CLOSE = "op_close"
    ON_DEMAND = "on_demand"

    @property
    def is_automatic(self) -> bool:
        """Whether this trigger is subject to the weekly throttle and "don't ask again"."""
        return self is not SurveyTrigger.ON_DEMAND


@dataclass(frozen=True)
class Rating:
    """A 1-5 inclusive experience rating."""

    value: int

    def __post_init__(self) -> None:
        # bool is an int subclass; True/False are never a rating.
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError(f"rating must be an integer, got {self.value!r}")
        if not RATING_MIN <= self.value <= RATING_MAX:
            raise ValueError(f"rating must be between {RATING_MIN} and {RATING_MAX}, got {self.value}")

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True)
class SurveyAnswers:
    """The already-validated answers of one completed Feedback Survey."""

    rating: Rating
    comment: str | None = None
    email: str | None = None


Harness = NewType("Harness", str)
"""Where the survey was answered: ``cli``, a known agent key, or ``other``."""

CLI_HARNESS = Harness("cli")
OTHER_HARNESS = Harness("other")


@functools.cache
def _known_agent_keys() -> frozenset[str]:
    from specify_cli.agent_utils.directories import AGENT_DIR_TO_KEY
    from specify_cli.skills._agent_roster import SUPPORTED_AGENTS

    return frozenset(AGENT_DIR_TO_KEY.values()) | frozenset(SUPPORTED_AGENTS)


def normalize_harness(value: str | None) -> Harness:
    """Map *value* onto the harness allowlist; anything unrecognised becomes ``other``."""
    key = (value or "").strip().lower()
    if key == CLI_HARNESS:
        return CLI_HARNESS
    if key in _known_agent_keys():
        return Harness(key)
    return OTHER_HARNESS


class OfferReason(StrEnum):
    """Machine-readable reason attached to every :class:`OfferDecision`."""

    ELIGIBLE = "eligible"
    NO_ENDPOINT = "no_endpoint"
    PROMPTS_OFF = "prompts_off"
    THROTTLED = "throttled"
    NON_INTERACTIVE = "non_interactive"
    CI = "ci"
    PREFERENCES_UNREADABLE = "preferences_unreadable"
    CLOCK_SKEW = "clock_skew"
    LOCK_BUSY = "lock_busy"
    TRIGGER_NOT_ELIGIBLE = "trigger_not_eligible"


OfferAction = Literal["prompt", "none"]


@dataclass(frozen=True)
class OfferDecision:
    """Whether a Feedback Survey may be offered now, and why."""

    action: OfferAction
    reason: OfferReason
    trigger: SurveyTrigger
