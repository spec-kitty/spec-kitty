"""#6271: the timestamp-continuity check skips seeds through the shared predicate.

``validate_timestamp_continuity`` must recognise a reconstruction seed the way the
reducer does (``specify_cli.status.is_migration_actor``), so a structured (dict)
actor whose ``tool`` is ``migration:…`` is skipped exactly like the plain-string
form, while a non-seed structured actor is still judged.
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.status.validate import validate_timestamp_continuity

pytestmark = [pytest.mark.fast]

_SEED_EVENT_ID = "01J0000000000000000000SEED"
_LATE_EVENT_ID = "01J0000000000000000000LATE"


def _event(event_id: str, at: str, from_lane: str, to_lane: str, actor: Any) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "at": at,
        "wp_id": "WP01",
        "from_lane": from_lane,
        "to_lane": to_lane,
        "actor": actor,
        "force": False,
    }


def _log_with_middle_actor(actor: Any) -> list[dict[str, Any]]:
    """planned -> claimed, then a mismatched-``from_lane`` row by ``actor``, then claimed -> in_progress."""
    return [
        _event("01J0000000000000000000AAAA", "2026-10-27T10:00:00+00:00", "planned", "claimed", "claude"),
        _event(_SEED_EVENT_ID, "2026-10-27T10:01:00+00:00", "for_review", "approved", actor),
        _event(_LATE_EVENT_ID, "2026-10-27T10:02:00+00:00", "claimed", "in_progress", "claude"),
    ]


def _structured(tool: str) -> dict[str, str | None]:
    return {"tool": tool, "role": None, "profile": None, "model": None}


def test_structured_migration_actor_is_skipped_as_seed() -> None:
    findings = validate_timestamp_continuity(_log_with_middle_actor(_structured("migration:backfill")))

    assert findings == []


def test_string_migration_actor_is_skipped_as_seed() -> None:
    findings = validate_timestamp_continuity(_log_with_middle_actor("migration:backfill"))

    assert findings == []


def test_structured_non_seed_actor_with_mismatched_from_lane_is_flagged() -> None:
    findings = validate_timestamp_continuity(_log_with_middle_actor(_structured("claude")))

    assert len(findings) == 1
    assert _SEED_EVENT_ID in findings[0]
    assert "from_lane 'for_review'" in findings[0]


@pytest.mark.parametrize("actor", [None, 42, ["migration:backfill"]])
def test_non_str_non_dict_actor_is_not_a_seed(actor: Any) -> None:
    findings = validate_timestamp_continuity(_log_with_middle_actor(actor))

    assert len(findings) == 1
    assert _SEED_EVENT_ID in findings[0]
