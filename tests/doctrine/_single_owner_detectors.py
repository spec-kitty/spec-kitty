"""Shared detectors for the squad-doctrine single-owner test suite (WP04, #5219).

Two detectors, both driven off plain text so they can be pointed at any
extracted field (a step description, `notes`, a whole SKILL.md, directive
prose, ...):

- ``point_cut_hits`` / ``restates_point_cut_list`` — flags a text block that
  names >= 3 of the canonical point-cut tokens (a restatement of the single
  owning list, which must live only in the ``adversarial-squad-deployment``
  procedure).
- ``has_headcount_language`` — flags a digit range, a word-number range, or
  an "exactly N" headcount claim (squad size must stay example-only, never a
  requirement).

Owned by WP04; reused as-is by WP10 for the charter and reference-page
single-owner checks (see WP04 prompt, T015).
"""

from __future__ import annotations

import re

POINT_CUT_TOKENS: tuple[str, ...] = (
    "pre-spec",
    "post-spec",
    "post-plan",
    "post-tasks",
    "pre-merge",
)

_WORD_NUMBERS = "two|three|four|five|six"

_DIGIT_RANGE_RE = re.compile(r"\b\d+\s*[-–]\s*\d+\b")
_WORD_RANGE_RE = re.compile(
    rf"\b(?:{_WORD_NUMBERS})\s+(?:to|-|–)\s+(?:{_WORD_NUMBERS})\b",
    re.IGNORECASE,
)
_EXACTLY_N_RE = re.compile(
    r"\bexactly\s+(?:\d+|three|four|five)\b",
    re.IGNORECASE,
)


def point_cut_hits(text: str) -> frozenset[str]:
    """Return the canonical point-cut tokens named in ``text``."""
    return frozenset(token for token in POINT_CUT_TOKENS if token in text)


def restates_point_cut_list(text: str) -> bool:
    """True when ``text`` names >= 3 of the canonical point-cut tokens.

    Positive control: flags the pre-change SKILL.md "When to use" block and
    the deleted styleguide's cadence-trigger prose, both of which name 4-5
    point-cuts in one block.
    """
    return len(point_cut_hits(text)) >= 3


def has_headcount_language(text: str) -> bool:
    """True when ``text`` states a squad-size range or an exact count.

    Positive control: flags ``"Invariants: bounded (3-4)"`` (digit range) and
    ``"3-4 distinct lenses"`` (digit range), the two pre-change strings this
    detector was written to catch.
    """
    return bool(_DIGIT_RANGE_RE.search(text) or _WORD_RANGE_RE.search(text) or _EXACTLY_N_RE.search(text))
