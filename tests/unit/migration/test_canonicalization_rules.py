"""Per-rule unit tests for the canonicalization rule pipeline.

Each ``_rule_*`` function is tested as a pure value transformer: given an
input state and context, assert the exact ``CanonicalStepResult`` produced.
No structural assertions (no mock-call-count, no constructor tests).

Tactic: function-over-form-testing — observable input → output assertions.

Coverage:
  _rule_reject_non_status_event  — happy (rejected), no-op (pass-through)
  _rule_apply_aliases            — happy (renamed), no-op (no legacy keys)
  _rule_strip_legacy_keys        — happy (stripped), no-op (no forbidden keys)
  _rule_stamp_identity           — happy (stamped, uses ctx slug), no-op (already stamped)
  _rule_mint_event_id            — happy (minted + appended), no-op (valid id present), side-effect (generated_ids None)
  _rule_default_at               — happy (defaulted), no-op (at present)
  _rule_default_from_lane        — happy (defaulted), no-op (from_lane present)
  _rule_require_to_lane          — happy (pass-through), error (missing)
  _rule_require_wp_id            — happy (pass-through), error (missing)
  _rule_normalize_lanes          — happy (no alias needed), alias-normalization, unknown-lane error
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.fast

from specify_cli.migration.canonicalization import CanonicalStepResult, MigrationContext
from specify_cli.migration.mission_state import (
    _rule_apply_aliases,
    _rule_default_at,
    _rule_default_from_lane,
    _rule_mint_event_id,
    _rule_normalize_lanes,
    _rule_reject_non_status_event,
    _rule_require_to_lane,
    _rule_require_wp_id,
    _rule_stamp_identity,
    _rule_strip_legacy_keys,
)

_Row = dict[str, Any]

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_MISSION_SLUG = "test-mission"
_MISSION_ID = "TESTMISSIONID12345678901234"
_KNOWN_EVENT_ID = "01KJ5V38J914TCB4CZF1N0S7WX"


def _ctx(line_number: int = 1, generated_ids: list[str] | None = None) -> MigrationContext:
    return MigrationContext(
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        line_number=line_number,
        generated_ids=generated_ids,
    )


def _base_row(**overrides: Any) -> _Row:
    """Return a minimal valid row with optional overrides."""
    row: _Row = {
        "mission_slug": _MISSION_SLUG,
        "wp_id": "WP01",
        "to_lane": "done",
        "from_lane": "planned",
        "at": "2025-01-01T00:00:00+00:00",
        "event_id": _KNOWN_EVENT_ID,
        "actor": "migration",
        "force": True,
        "execution_mode": "direct_repo",
    }
    row.update(overrides)
    return row


# ===========================================================================
# _rule_reject_non_status_event
# ===========================================================================


@pytest.mark.parametrize(
    "row, expect_error",
    [
        # generic event_type (not a canonical lifecycle event, not registered) →
        # PRESERVED by default (#4993 FR-001 inversion): the durable reader
        # treats any event_type-bearing row as non-lane, and the repair now
        # delegates to that reader with an EMPTY denylist, so an unregistered
        # type is preserved rather than silently dropped (#2376 / #980 / #4897).
        ({"event_type": "some_event", "wp_id": "WP01"}, "preserved_non_lane_event"),
        # canonical lifecycle event whose only per-mission home is this file →
        # PRESERVED in place, never quarantined (#2376)
        ({"event_type": "MissionCreated", "wp_id": "WP01"}, "preserved_non_lane_event"),
        # bare event_name present → quarantine error
        ({"event_name": "custom_event"}, "quarantined_non_status_event"),
        # retrospective lifecycle type events → preserved in place, never quarantined
        ({"type": "RetrospectiveCaptured", "wp_id": "WP01"}, "preserved_non_lane_event"),
        ({"type": "RetrospectiveCaptureFailed"}, "preserved_non_lane_event"),
        ({"type": "RetrospectiveSkipped"}, "preserved_non_lane_event"),
        # no-op — neither key present → pass-through
        ({"wp_id": "WP01", "to_lane": "done"}, None),
    ],
)
def test_rule_reject_non_status_event(row: _Row, expect_error: str | None) -> None:
    result = _rule_reject_non_status_event(row, _ctx())
    assert isinstance(result, CanonicalStepResult)
    if expect_error == "quarantined_non_status_event":
        assert result.error == expect_error
        assert result.actions == ("quarantined_non_status_event",)
    elif expect_error == "preserved_non_lane_event":
        assert result.error == expect_error
        assert result.actions == ()
        assert result.state is row  # preserved untouched
    else:
        assert result.error is None
        assert result.state is row  # exact passthrough


# ===========================================================================
# _rule_apply_aliases
# ===========================================================================


@pytest.mark.parametrize(
    "row, expected_actions, expected_keys",
    [
        # happy — feature_slug renamed to mission_slug
        (
            {"feature_slug": "old-feature", "to_lane": "done"},
            ("renamed_key:feature_slug->mission_slug",),
            {"mission_slug": "old-feature"},
        ),
        # happy — work_package_id renamed to wp_id
        (
            {"mission_slug": "m", "work_package_id": "WP02", "to_lane": "done"},
            ("renamed_key:work_package_id->wp_id",),
            {"wp_id": "WP02"},
        ),
        # no-op — no legacy alias keys present
        ({"mission_slug": "m", "wp_id": "WP01"}, (), None),
    ],
)
def test_rule_apply_aliases(
    row: _Row,
    expected_actions: tuple[str, ...],
    expected_keys: dict[str, Any] | None,
) -> None:
    result = _rule_apply_aliases(row, _ctx())
    assert result.actions == expected_actions
    assert result.error is None
    if expected_keys is not None:
        for k, v in expected_keys.items():
            assert result.state[k] == v


# ===========================================================================
# _rule_strip_legacy_keys
# ===========================================================================


@pytest.mark.parametrize(
    "row, expected_actions, stripped_keys",
    [
        # happy — feature_number stripped
        (
            {**_base_row(), "feature_number": 42},
            ("removed_key:feature_number",),
            ["feature_number"],
        ),
        # happy — mission_key stripped
        (
            {**_base_row(), "mission_key": "abc"},
            ("removed_key:mission_key",),
            ["mission_key"],
        ),
        # no-op — no forbidden keys
        (_base_row(), (), []),
    ],
)
def test_rule_strip_legacy_keys(row: _Row, expected_actions: tuple[str, ...], stripped_keys: list[str]) -> None:
    result = _rule_strip_legacy_keys(row, _ctx())
    assert result.actions == expected_actions
    assert result.error is None
    for k in stripped_keys:
        assert k not in result.state


# ===========================================================================
# _rule_stamp_identity
# ===========================================================================


@pytest.mark.parametrize(
    "row, expected_mission_slug, expected_mission_id",
    [
        # happy — missing mission_slug: falls back to ctx.mission_slug
        ({"wp_id": "WP01"}, _MISSION_SLUG, _MISSION_ID),
        # happy — existing mission_slug is preserved (not overwritten)
        ({"mission_slug": "custom-slug", "wp_id": "WP01"}, "custom-slug", _MISSION_ID),
        # always stamps mission_id
        (_base_row(mission_id="old-id"), _MISSION_SLUG, _MISSION_ID),
    ],
)
def test_rule_stamp_identity(row: _Row, expected_mission_slug: str, expected_mission_id: str) -> None:
    result = _rule_stamp_identity(row, _ctx())
    assert result.error is None
    assert result.state["mission_slug"] == expected_mission_slug
    assert result.state["mission_id"] == expected_mission_id


# ===========================================================================
# _rule_mint_event_id
# ===========================================================================


@pytest.mark.parametrize(
    "row, generated_ids, expect_minted",
    [
        # happy — missing event_id: mints deterministically + appends to generated_ids
        (_base_row(event_id=None), [], True),
        # no-op — valid event_id already present
        (_base_row(), None, False),
        # happy — invalid event_id (not ULID/UUID): minted, generated_ids=None (no append)
        (_base_row(event_id="not-valid"), None, True),
    ],
)
def test_rule_mint_event_id(row: _Row, generated_ids: list[str] | None, expect_minted: bool) -> None:
    ctx = _ctx(generated_ids=generated_ids)
    result = _rule_mint_event_id(row, ctx)
    assert result.error is None
    if expect_minted:
        assert result.actions == ("event_id_deterministically_backfilled",)
        assert isinstance(result.state.get("event_id"), str)
        assert len(result.state["event_id"]) == 26  # ULID length
        if generated_ids is not None:
            assert result.state["event_id"] in ctx.generated_ids  # type: ignore[operator]
    else:
        assert result.actions == ()
        assert result.state["event_id"] == row["event_id"]


# ===========================================================================
# _rule_default_at
# ===========================================================================


@pytest.mark.parametrize(
    "row, expected_at, expected_action",
    [
        # happy — missing 'at': default to epoch
        (_base_row(at=None), "1970-01-01T00:00:00+00:00", "at_defaulted"),
        # happy — empty string 'at': default to epoch
        (_base_row(at=""), "1970-01-01T00:00:00+00:00", "at_defaulted"),
        # no-op — 'at' already present
        (_base_row(), "2025-01-01T00:00:00+00:00", None),
    ],
)
def test_rule_default_at(row: _Row, expected_at: str, expected_action: str | None) -> None:
    result = _rule_default_at(row, _ctx())
    assert result.error is None
    assert result.state["at"] == expected_at
    if expected_action is not None:
        assert expected_action in result.actions
    else:
        assert result.actions == ()


# ===========================================================================
# _rule_default_from_lane
# ===========================================================================


@pytest.mark.parametrize(
    "row, expected_from_lane, expect_action",
    [
        # happy — from_lane is None: default to 'planned'
        (_base_row(from_lane=None), "planned", True),
        # no-op — from_lane already set
        (_base_row(from_lane="in_progress"), "in_progress", False),
        # no-op — from_lane is empty string (not None): no default
        (_base_row(from_lane=""), "", False),
    ],
)
def test_rule_default_from_lane(row: _Row, expected_from_lane: str, expect_action: bool) -> None:
    result = _rule_default_from_lane(row, _ctx())
    assert result.error is None
    assert result.state["from_lane"] == expected_from_lane
    if expect_action:
        assert "from_lane_defaulted" in result.actions
    else:
        assert result.actions == ()


# ===========================================================================
# _rule_require_to_lane
# ===========================================================================


@pytest.mark.parametrize(
    "row, expect_error",
    [
        # happy — to_lane present: pass-through
        (_base_row(to_lane="done"), None),
        # error — to_lane missing (None)
        (_base_row(to_lane=None), "missing required to_lane"),
        # error — to_lane empty string
        (_base_row(to_lane=""), "missing required to_lane"),
    ],
)
def test_rule_require_to_lane(row: _Row, expect_error: str | None) -> None:
    result = _rule_require_to_lane(row, _ctx())
    if expect_error is not None:
        assert result.error == expect_error
    else:
        assert result.error is None
        assert result.state is row  # exact pass-through


# ===========================================================================
# _rule_require_wp_id
# ===========================================================================


@pytest.mark.parametrize(
    "row, expect_error",
    [
        # happy — wp_id present: pass-through
        (_base_row(wp_id="WP01"), None),
        # error — wp_id missing (None → removed from row)
        ({k: v for k, v in _base_row().items() if k != "wp_id"}, "missing required wp_id"),
        # error — wp_id empty string
        (_base_row(wp_id=""), "missing required wp_id"),
    ],
)
def test_rule_require_wp_id(row: _Row, expect_error: str | None) -> None:
    result = _rule_require_wp_id(row, _ctx())
    if expect_error is not None:
        assert result.error == expect_error
    else:
        assert result.error is None
        assert result.state is row  # exact pass-through


# ===========================================================================
# _rule_normalize_lanes
# ===========================================================================


@pytest.mark.parametrize(
    "row, expected_from_lane, expected_to_lane, expected_error, has_lane_alias_action",
    [
        # happy — no alias, valid lanes
        (_base_row(from_lane="planned", to_lane="done"), "planned", "done", None, False),
        # alias — from_lane 'doing' normalized to 'in_progress'
        (
            _base_row(from_lane="doing", to_lane="in_progress"),
            "in_progress",
            "in_progress",
            None,
            True,
        ),
        # error — unknown to_lane
        (
            _base_row(from_lane="planned", to_lane="unknownlane"),
            "planned",
            "unknownlane",
            "unknown to_lane 'unknownlane'",
            False,
        ),
        # error — unknown from_lane
        (
            _base_row(from_lane="limbo", to_lane="done"),
            "limbo",
            "done",
            "unknown from_lane 'limbo'",
            False,
        ),
    ],
)
def test_rule_normalize_lanes(
    row: _Row,
    expected_from_lane: str,
    expected_to_lane: str,
    expected_error: str | None,
    has_lane_alias_action: bool,
) -> None:
    result = _rule_normalize_lanes(row, _ctx())
    if expected_error is not None:
        assert result.error == expected_error
    else:
        assert result.error is None
        assert result.state["from_lane"] == expected_from_lane
        assert result.state["to_lane"] == expected_to_lane
        if has_lane_alias_action:
            assert any("lane_alias" in a for a in result.actions)
