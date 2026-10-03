"""Allowlisted Feedback Submission payload builder.

The only place raw survey input becomes a wire payload. Emits exactly the
keys named in ``contracts/feedback-submission.schema.json`` and never
includes repository, mission, branch, user, host, or credential data.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Literal

from specify_cli.distribution.profile import resolve_distribution_profile
from specify_cli.feedback.models import Harness, Rating, SurveyAnswers, SurveyTrigger
from specify_cli.version_utils import get_version

__all__ = [
    "ALLOWED_KEYS",
    "COMMENT_MAX_LENGTH",
    "ContextFields",
    "EMAIL_MAX_LENGTH",
    "OsFamily",
    "SUBMISSION_FORMAT_VERSION",
    "build_submission",
    "collect_context",
    "normalize_comment",
    "parse_email",
    "parse_rating",
]

SUBMISSION_FORMAT_VERSION = 1
COMMENT_MAX_LENGTH = 2000
EMAIL_MAX_LENGTH = 254

ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "submission_format_version",
        "rating",
        "comment",
        "email",
        "spec_kitty_version",
        "distribution",
        "trigger",
        "harness",
        "os",
        "mission_type",
    }
)

OsFamily = Literal["linux", "darwin", "windows", "other"]

_DIGIT_RATING = re.compile(r"[1-5]")

# One address only: dot-atom local part, dotted domain of at least two labels.
_EMAIL_LOCAL = r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*"
_EMAIL_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
_EMAIL_SHAPE = re.compile(rf"{_EMAIL_LOCAL}@{_EMAIL_LABEL}(?:\.{_EMAIL_LABEL})+")

# Terminal escape sequences, in both 7-bit (ESC-prefixed) and 8-bit C1 forms:
# string types (OSC, DCS, SOS, PM, APC) run to BEL or ST; CSI ends at a final byte.
_ESCAPE_SEQUENCE = re.compile(
    r"(?:\x1b[\]PX^_]|[\x90\x98\x9d\x9e\x9f])[^\x07\x1b\x9c]*(?:\x07|\x1b\\|\x9c)?"
    r"|(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]"
    r"|\x1b[0-~]"
    r"|\x1b"
)
_WHITESPACE_RUN = re.compile(r"\s+")
_DROPPED_CATEGORIES = frozenset({"Cc", "Cf"})
_LINE_CONTROLS_TO_SPACE = {ord(ch): " " for ch in "\t\n\r\v\f"}


@dataclass(frozen=True)
class ContextFields:
    """Non-answer context attached to every Feedback Submission."""

    spec_kitty_version: str
    distribution: str
    trigger: SurveyTrigger
    harness: Harness
    os: OsFamily
    mission_type: str | None


def parse_rating(raw: str | int) -> Rating | None:
    """Parse a 1–5 rating from a string or int. Rejects bools and floats."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        try:
            return Rating(raw)
        except ValueError:
            return None
    if isinstance(raw, str) and _DIGIT_RATING.fullmatch(raw):
        return Rating(int(raw))
    return None


def _clean_comment_text(raw: str) -> str:
    """Remove escapes, control and format characters; collapse whitespace; NFC last.

    NFC runs after the drops so a removed format character between a base and
    a combining mark cannot defeat composition.
    """
    text = _ESCAPE_SEQUENCE.sub("", raw)
    # Line/tab controls become spaces first so they are not dropped as Cc.
    text = text.translate(_LINE_CONTROLS_TO_SPACE)
    text = "".join(ch for ch in text if unicodedata.category(ch) not in _DROPPED_CATEGORIES)
    text = _WHITESPACE_RUN.sub(" ", text).strip()
    return unicodedata.normalize("NFC", text)


def _truncate_comment(text: str) -> tuple[str, bool]:
    """Cap *text* at the limit by characters without orphaning combining marks."""
    if len(text) <= COMMENT_MAX_LENGTH:
        return text, False
    end = COMMENT_MAX_LENGTH
    while end > 0 and unicodedata.category(text[end]).startswith("M"):
        end -= 1
    return unicodedata.normalize("NFC", text[:end].rstrip()), True


def normalize_comment(raw: str | None) -> tuple[str | None, bool]:
    """Sanitise and cap a comment at :data:`COMMENT_MAX_LENGTH` characters.

    Policy: NFC-normalise; remove terminal escape sequences and characters in
    Unicode categories Cc and Cf; collapse every whitespace run (newlines and
    tabs included) to one space; leave markup untouched.

    Returns ``(text, truncated)``. Input that is empty after cleaning becomes
    ``(None, False)``.
    """
    if raw is None:
        return None, False
    text = _clean_comment_text(raw)
    if not text:
        return None, False
    return _truncate_comment(text)


def parse_email(raw: str | None) -> tuple[str | None, bool]:
    """Validate an optional email: exactly one well-formed address.

    Returns ``(value, ok)``:

    * blank / ``None`` → ``(None, True)`` (omit the field)
    * one valid address within :data:`EMAIL_MAX_LENGTH` → ``(value, True)``
      (value unchanged apart from outer-whitespace trimming)
    * anything else → ``(None, False)`` (caller should re-ask)
    """
    if raw is None:
        return None, True
    value = raw.strip()
    if not value:
        return None, True
    if len(value) > EMAIL_MAX_LENGTH or _EMAIL_SHAPE.fullmatch(value) is None:
        return None, False
    return value, True


def collect_context(
    trigger: SurveyTrigger,
    harness: Harness,
    mission_type: str | None,
) -> ContextFields:
    """Assemble context from the installed CLI version and distribution profile."""
    profile = resolve_distribution_profile()
    return ContextFields(
        spec_kitty_version=get_version(),
        distribution=profile.package_name,
        trigger=trigger,
        harness=harness,
        os=_os_family(sys.platform),
        mission_type=mission_type,
    )


def build_submission(answers: SurveyAnswers, context: ContextFields) -> dict[str, object]:
    """Build the allowlisted wire payload. Omits ``email`` when ``None``."""
    result: dict[str, object] = {
        "submission_format_version": SUBMISSION_FORMAT_VERSION,
        "rating": int(answers.rating),
        "comment": answers.comment,
        "spec_kitty_version": context.spec_kitty_version,
        "distribution": context.distribution,
        "trigger": context.trigger.value,
        "harness": str(context.harness),
        "os": context.os,
        "mission_type": context.mission_type,
    }
    if answers.email is not None:
        result["email"] = answers.email
    assert set(result) <= ALLOWED_KEYS, f"payload keys outside allowlist: {set(result) - ALLOWED_KEYS}"
    return result


def _os_family(platform: str) -> OsFamily:
    if platform.startswith("linux"):
        return "linux"
    if platform == "darwin":
        return "darwin"
    if platform.startswith("win"):
        return "windows"
    return "other"
