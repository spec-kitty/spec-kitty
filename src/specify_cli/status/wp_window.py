"""The ``policy_metadata["wp_window"]`` value: one codec for its writer and its reader.

Mission ``consolidation-window-provenance-01M6Y84D`` records, on every non-migration move of
a lane-mapped work package into ``claimed`` or ``in_progress``, where that work package's
window opens: ``{"schema_version": 1, "open_sha": <sha>}`` or a typed gap. The status
pipeline writes the value (:func:`encode_open`, :func:`encode_gap`) and consolidation reads
it back (:func:`parse_wp_window`); both go through this module, so the schema version, the
closed reason and cause sets, the detail limit and the window-opening lanes live in one
place. Contract: the Mission's ``contracts/status-event-wp-window.md``.

Pure: no git, no I/O and no ``specify_cli`` imports, so the cold-import boundary of the
``status`` package is unaffected. Consumers outside ``specify_cli.status`` import these
names through the facade (SR-2).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Final

#: The ``policy_metadata`` key the window-open record is written under (FR-002/FR-003).
WP_WINDOW_KEY: Final = "wp_window"

#: The only ``schema_version`` this codec writes and accepts.
WP_WINDOW_SCHEMA_VERSION: Final = 1

#: Contract ``maxLength`` of ``gap.detail``.
GAP_DETAIL_MAX_LENGTH: Final = 500

#: The lanes a window-opening move enters (W-1, R-1(b)); ``blocked`` opens nothing.
WINDOW_OPENING_LANES: Final[frozenset[str]] = frozenset({"claimed", "in_progress"})

# A git object name: SHA-1 (40 hex) or SHA-256 (64 hex), lower case.
_OPEN_SHA = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_WINDOW_KEYS: frozenset[str] = frozenset({"schema_version", "open_sha", "gap"})
_GAP_KEYS: frozenset[str] = frozenset({"reason", "cause", "detail"})


class CaptureCause(StrEnum):
    """Why a lane-head reading of an applicable work package has no sha (closed set)."""

    LANE_BRANCH_MISSING = "lane_branch_missing"
    GIT_ERROR = "git_error"
    PROBE_ERROR = "probe_error"


class RecordedGapReason(StrEnum):
    """The ``gap.reason`` values a writer records (closed set)."""

    CAPTURE_FAILED = "capture_failed"
    LANE_BRANCH_MISSING = "lane_branch_missing"


#: The ``gap.cause`` values a ``capture_failed`` gap may carry; ``lane_branch_missing`` has its own reason.
CAPTURE_FAILED_CAUSES: Final[frozenset[str]] = frozenset({CaptureCause.GIT_ERROR.value, CaptureCause.PROBE_ERROR.value})


@dataclass(frozen=True, slots=True)
class ParsedWpWindow:
    """A contract-valid ``wp_window`` value: exactly one of ``open_sha`` / ``gap_reason``."""

    open_sha: str | None = None
    gap_reason: RecordedGapReason | None = None
    cause: str | None = None
    detail: str = ""


def encode_open(sha: str) -> dict[str, Any]:
    """The value recording that the window opens at *sha*."""
    return {"schema_version": WP_WINDOW_SCHEMA_VERSION, "open_sha": sha}


def encode_gap(cause: CaptureCause, detail: str) -> dict[str, Any]:
    """The gap value for a failed reading (W-3).

    A missing lane branch records ``lane_branch_missing`` with no ``cause``; any other
    failure records ``capture_failed`` with its cause. *detail* is cut to the contract limit.
    """
    gap: dict[str, Any]
    if cause is CaptureCause.LANE_BRANCH_MISSING:
        gap = {"reason": RecordedGapReason.LANE_BRANCH_MISSING.value, "detail": detail[:GAP_DETAIL_MAX_LENGTH]}
    else:
        gap = {"reason": RecordedGapReason.CAPTURE_FAILED.value, "cause": cause.value, "detail": detail[:GAP_DETAIL_MAX_LENGTH]}
    return {"schema_version": WP_WINDOW_SCHEMA_VERSION, "gap": gap}


def _parse_gap(gap: object) -> ParsedWpWindow | None:
    if not isinstance(gap, Mapping) or not set(gap) <= _GAP_KEYS:
        return None
    reason, cause, detail = gap.get("reason"), gap.get("cause"), gap.get("detail", "")
    if not isinstance(detail, str) or len(detail) > GAP_DETAIL_MAX_LENGTH:
        return None
    if reason == RecordedGapReason.CAPTURE_FAILED.value and isinstance(cause, str) and cause in CAPTURE_FAILED_CAUSES:
        return ParsedWpWindow(gap_reason=RecordedGapReason.CAPTURE_FAILED, cause=cause, detail=detail)
    if reason == RecordedGapReason.LANE_BRANCH_MISSING.value and "cause" not in gap:
        return ParsedWpWindow(gap_reason=RecordedGapReason.LANE_BRANCH_MISSING, detail=detail)
    return None


def parse_wp_window(value: object) -> ParsedWpWindow | None:
    """Validate one ``wp_window`` value against schema version 1; ``None`` when it violates it (R-5)."""
    if not isinstance(value, Mapping) or not set(value) <= _WINDOW_KEYS:
        return None
    version = value.get("schema_version")
    # ``True == 1`` in Python; the contract's ``const: 1`` is an integer, never a boolean.
    if type(version) is not int or version != WP_WINDOW_SCHEMA_VERSION:
        return None
    if ("open_sha" in value) == ("gap" in value):
        return None
    if "gap" in value:
        return _parse_gap(value["gap"])
    sha = value["open_sha"]
    return ParsedWpWindow(open_sha=sha) if isinstance(sha, str) and _OPEN_SHA.fullmatch(sha) else None
