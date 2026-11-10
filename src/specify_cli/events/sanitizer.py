"""PII sanitizer for event envelope dicts.

Strips PII fields from event envelopes before they are written to any
git-committed file.  The function is intentionally *pure*: it accepts a
dict, returns a new dict, never mutates the input, and has no side effects.

Python 3.11+ required: parse_iso() handles the ``Z`` UTC suffix
only from 3.11 onward (PEP 680 / bpo-35829).
"""

from __future__ import annotations

import copy
import logging
from kernel.clock import datetime, parse_iso
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PII field registry
# ---------------------------------------------------------------------------

_PII_FIELDS: frozenset[str] = frozenset(
    {
        "machine_name",
        "hostname",
        "workspace_path",
        "developer_name",
        "developer_email",
    }
)

# Sentinel used to detect already-seen objects and break circular references.
_SEEN_TYPE = set[int]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_pii_recursive(obj: Any, seen: _SEEN_TYPE) -> Any:
    """Recursively strip PII fields from *obj* without mutating it.

    - dicts: PII keys are dropped; values are recursed into.
    - lists/tuples: elements are recursed into (non-dict scalars are kept as-is).
    - Everything else: returned unchanged.

    The *seen* set guards against circular references in object graphs (in
    practice event dicts should never be circular, but the guard is cheap).
    """
    if isinstance(obj, dict):
        obj_id = id(obj)
        if obj_id in seen:
            # Circular reference — return an empty dict rather than looping.
            return {}
        seen = seen | {obj_id}  # immutable update so sibling branches are unaffected
        return {
            k: _strip_pii_recursive(v, seen)
            for k, v in obj.items()
            if k not in _PII_FIELDS
        }
    if isinstance(obj, list):
        return [_strip_pii_recursive(item, seen) for item in obj]
    if isinstance(obj, tuple):
        return tuple(_strip_pii_recursive(item, seen) for item in obj)
    return obj


def _replace_session_timestamps(envelope: dict[str, Any]) -> dict[str, Any]:
    """Replace absolute session timestamps with a relative ``session_duration_s``.

    Rules (applied to *top-level* keys only):

    * Both ``session_started_at`` **and** ``session_ended_at`` present →
      compute ``session_duration_s = int((ended − started).total_seconds())``,
      remove both originals, add the computed value.
    * Only ``session_started_at`` present (session still running) →
      remove it, no replacement.
    * Only ``session_ended_at`` present → remove it, no replacement.
    * Neither present → envelope unchanged.
    * Malformed timestamp string → field removed (debug-logged), no exception
      raised.
    * One naive and one timezone-aware timestamp → treated as malformed: both
      removed, no ``session_duration_s``, debug log emitted (#7440).

    Returns a *new* dict (shallow copy of *envelope* with timestamp keys
    possibly replaced).
    """
    result = dict(envelope)

    started_raw: str | None = result.pop("session_started_at", None)
    ended_raw: str | None = result.pop("session_ended_at", None)

    started: datetime | None = None
    ended: datetime | None = None

    if started_raw is not None:
        try:
            started = parse_iso(started_raw)
        except (ValueError, TypeError):
            logger.debug(
                "sanitize_event_for_log: could not parse session_started_at=%r — field removed",
                started_raw,
            )

    if ended_raw is not None:
        try:
            ended = parse_iso(ended_raw)
        except (ValueError, TypeError):
            logger.debug(
                "sanitize_event_for_log: could not parse session_ended_at=%r — field removed",
                ended_raw,
            )

    if started is not None and ended is not None:
        if (started.tzinfo is None) != (ended.tzinfo is None):
            logger.debug(
                "sanitize_event_for_log: mixed naive/aware session pair %r / %r — fields removed",
                started_raw,
                ended_raw,
            )
        else:
            result["session_duration_s"] = int((ended - started).total_seconds())

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sanitize_event_for_log(envelope: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy of *envelope* with PII stripped.

    The function is **pure**:

    * Takes a ``dict[str, Any]`` as input.
    * Returns a brand-new ``dict[str, Any]``.
    * Never mutates *envelope* or any nested object inside it.
    * Has no side effects (no I/O, no global state).

    PII fields removed at **every nesting level** (including nested payload dicts):
      ``machine_name``, ``hostname``, ``workspace_path``, ``developer_name``,
      ``developer_email``.

    Session timestamp replacement (top-level only):
      If both ``session_started_at`` and ``session_ended_at`` are present they
      are replaced by ``session_duration_s`` (integer seconds).  If only one is
      present it is removed without replacement.  Malformed timestamps, and a
      pair mixing a naive with a timezone-aware timestamp, are removed (debug-logged).

    Fields that are explicitly **preserved**: ``node_id``, ``build_id``,
    ``mission_id``, ``project_uuid``, ``git_branch``, ``head_commit_sha``,
    ``session_duration_s``, and all event-type-specific payload fields.

    Args:
        envelope: The raw event envelope dict.  May contain nested dicts.

    Returns:
        A new dict with PII removed and session timestamps replaced.
    """
    # Deep-copy first so recursion operates on a mutable clone and the caller's
    # original object is provably untouched.
    working: dict[str, Any] = copy.deepcopy(envelope)

    # 1. Strip PII recursively across the whole tree.
    stripped: dict[str, Any] = _strip_pii_recursive(working, seen=set())

    # 2. Replace session timestamps at the top level only.
    result: dict[str, Any] = _replace_session_timestamps(stripped)

    return result
