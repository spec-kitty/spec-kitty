"""Characterization tests for _canonicalize_status_row and _derive_migration_timestamp.

These tests capture today's observable behavior of:
- The monolithic ``_canonicalize_status_row`` pipeline (mission_state.py)
- The timestamp derivation logic ``_derive_migration_timestamp`` (rebuild_state.py)

Both are pre-refactor characterization tests that MUST remain green through
the WP03 refactors (NFR-003).

Tactic references:
- ``tdd-red-green-refactor``: characterization-first, NFR-003 binding.
- ``function-over-form-testing``: assert observable outcomes (row, actions,
  error), not implementation structure.

Rule coverage:
  Rule 1  — reject non-status event (event_type / event_name present)
  Rule 2  — apply STATUS_ROW_ALIASES (feature_slug -> mission_slug, work_package_id -> wp_id)
  Rule 3  — strip FORBIDDEN_LEGACY_KEYS (feature_number, etc.)
  Rule 4  — stamp mission_slug, mission_id
  Rule 5  — mint event_id deterministically when missing/invalid
  Rule 6  — default 'at' to epoch when missing
  Rule 7  — default 'from_lane' to 'planned' when missing
  Rule 8  — require 'to_lane' (short-circuit on missing)
  Rule 9  — require 'wp_id' (short-circuit on missing)
  Rule 10 — normalize and validate lane values (alias 'doing' -> 'in_progress';
             reject unknown lanes)

rebuild_state._derive_migration_timestamp coverage:
  Source 1 — collect 'at' timestamps from status.events.jsonl
  Source 2 — collect 'materialized_at' from status.json
  Source 3 — collect WP 'last_transition_at' from status.json
  Source 4 — collect 'created_at' from meta.json
  Boundary — empty dir falls back to MIGRATION_EPOCH
  Boundary — multiple sources: latest candidate wins
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.fast

from specify_cli.migration.mission_state import _canonicalize_status_row
from specify_cli.migration.rebuild_state import _derive_migration_timestamp

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    """Call _canonicalize_status_row with fixture inputs; return comparable output."""
    inp = fixture["input"]
    generated_ids: list[str] | None = list(inp["generated_ids"]) if inp["generated_ids"] is not None else None
    result = _canonicalize_status_row(
        inp["data"],
        mission_slug=inp["mission_slug"],
        mission_id=inp["mission_id"],
        line_number=inp["line_number"],
        generated_ids=generated_ids,
    )
    return {
        "row": result.row,
        "actions": list(result.actions),
        "error": result.error,
        "generated_ids_after": generated_ids,
    }


# ---------------------------------------------------------------------------
# Rule 1 — reject non-status events
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_preserves_generic_event_type_rows() -> None:
    """#4993 (FR-001 inversion): a row with a generic, unregistered 'event_type'
    is now PRESERVED verbatim, not quarantined.

    Before the inversion this pinned the opposite ("quarantined immediately");
    ``_is_preserved_non_lane_row`` now delegates to the durable reader
    (``is_non_lane_event``) with an EMPTY denylist, so ANY event_type-bearing
    row — registered or not — is preserved by construction. Canonical
    lifecycle events (whose only home is this file) were already preserved
    before this change — see test_lifecycle_events_preserved.py (#2376,
    #4897).
    """
    fixture = _load_fixture("01_non_status_event_type.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] == expected["row"]
    assert actual["actions"] == expected["actions"]
    assert actual["error"] == expected["error"]


def test_canonicalize_status_row_rejects_event_name_rows() -> None:
    """A row with 'event_name' key is quarantined immediately; no further processing."""
    fixture = _load_fixture("02_non_status_event_name.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] is None
    assert actual["actions"] == expected["actions"]
    assert actual["error"] == expected["error"]


# ---------------------------------------------------------------------------
# Rule 2 — apply STATUS_ROW_ALIASES
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_renames_legacy_alias_keys() -> None:
    """feature_slug renamed to mission_slug; work_package_id renamed to wp_id."""
    fixture = _load_fixture("03_legacy_alias_rename.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] == expected["row"]
    assert actual["actions"] == expected["actions"]
    assert actual["error"] == expected["error"]


# ---------------------------------------------------------------------------
# Rule 3 — strip FORBIDDEN_LEGACY_KEYS
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_strips_forbidden_legacy_key() -> None:
    """feature_number key is stripped; 'removed_key:feature_number' in actions."""
    fixture = _load_fixture("04_legacy_key_strip.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] == expected["row"]
    assert actual["actions"] == expected["actions"]
    assert actual["error"] == expected["error"]


# ---------------------------------------------------------------------------
# Rule 5 — mint event_id when missing
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_mints_event_id_deterministically() -> None:
    """A row with no event_id gets a deterministic ULID minted; id added to generated_ids."""
    fixture = _load_fixture("05_mint_event_id.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    # The minted ID must be deterministic (same seed → same ID)
    assert actual["row"] is not None
    assert actual["row"]["event_id"] == expected["row"]["event_id"]  # type: ignore[index]
    assert actual["actions"] == expected["actions"]
    assert actual["error"] == expected["error"]
    assert actual["generated_ids_after"] == expected["generated_ids_after"]


# ---------------------------------------------------------------------------
# Rule 6 — default 'at'
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_defaults_missing_at_to_epoch() -> None:
    """A row with no 'at' field gets the epoch default; 'at_defaulted' in actions."""
    fixture = _load_fixture("06_default_at.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] is not None
    assert actual["row"]["at"] == "1970-01-01T00:00:00+00:00"  # type: ignore[index]
    assert actual["actions"] == expected["actions"]
    assert actual["error"] == expected["error"]


# ---------------------------------------------------------------------------
# Rule 7 — default 'from_lane'
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_defaults_missing_from_lane_to_planned() -> None:
    """A row with no 'from_lane' gets 'planned'; 'from_lane_defaulted' in actions."""
    fixture = _load_fixture("07_default_from_lane.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] is not None
    assert actual["row"]["from_lane"] == "planned"  # type: ignore[index]
    assert actual["actions"] == expected["actions"]
    assert actual["error"] == expected["error"]


# ---------------------------------------------------------------------------
# Rule 8 — require 'to_lane'
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_errors_on_missing_to_lane() -> None:
    """A row with no 'to_lane' is rejected with 'missing required to_lane' error."""
    fixture = _load_fixture("08_require_to_lane_error.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] is None
    assert actual["error"] == "missing required to_lane"
    assert actual["error"] == expected["error"]


# ---------------------------------------------------------------------------
# Rule 9 — require 'wp_id'
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_errors_on_missing_wp_id() -> None:
    """A row with no 'wp_id' is rejected with 'missing required wp_id' error."""
    fixture = _load_fixture("09_require_wp_id_error.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] is None
    assert actual["error"] == "missing required wp_id"
    assert actual["error"] == expected["error"]


# ---------------------------------------------------------------------------
# Rule 10 — normalize and validate lane values
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_normalizes_lane_alias_doing_to_in_progress() -> None:
    """from_lane alias 'doing' is normalized to 'in_progress' in the output row."""
    fixture = _load_fixture("10_lane_alias_normalize.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] is not None
    assert actual["row"]["from_lane"] == "in_progress"  # type: ignore[index]
    assert actual["actions"] == expected["actions"]
    assert actual["error"] == expected["error"]


def test_canonicalize_status_row_errors_on_unknown_to_lane() -> None:
    """A row with an unrecognized to_lane value is rejected with an error."""
    fixture = _load_fixture("11_unknown_lane_error.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] is None
    assert actual["error"] == expected["error"]
    assert "flying" in (actual["error"] or "")


# ---------------------------------------------------------------------------
# Boundary case — fully canonical row passes through with no mutations
# ---------------------------------------------------------------------------


def test_canonicalize_status_row_passes_canonical_row_unchanged() -> None:
    """A fully-canonical row needs no transformations; actions list is empty."""
    fixture = _load_fixture("12_canonical_row.json")
    actual = _run_fixture(fixture)
    expected = fixture["expected"]
    assert actual["row"] == expected["row"]
    assert actual["actions"] == []
    assert actual["error"] is None


# ===========================================================================
# Characterization tests for rebuild_state._derive_migration_timestamp
# (T014 — added before refactoring rebuild_state.py)
# Tactic: tdd-red-green-refactor (NFR-003 binding)
# ===========================================================================


def test_derive_migration_timestamp_falls_back_to_epoch_when_no_sources() -> None:
    """Empty directory with no event/status/meta files returns the MIGRATION_EPOCH."""
    with tempfile.TemporaryDirectory() as td:
        result = _derive_migration_timestamp(Path(td))
    # The epoch constant is '2026-01-01T00:00:00+00:00'
    assert result == "2026-01-01T00:00:00+00:00"


def test_derive_migration_timestamp_collects_from_events_jsonl() -> None:
    """Latest 'at' timestamp from status.events.jsonl is selected and bumped by 1 second."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "status.events.jsonl").write_text('{"at": "2025-06-01T10:00:00+00:00", "wp_id": "WP01"}\n{"at": "2025-07-01T12:00:00+00:00", "wp_id": "WP02"}\n')
        result = _derive_migration_timestamp(p)
    # Latest is 2025-07-01T12:00:00+00:00; bumped by 1 second
    assert result == "2025-07-01T12:00:01+00:00"


def test_derive_migration_timestamp_collects_from_status_json_materialized_at() -> None:
    """materialized_at from status.json is used when no events are present."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        status = {"materialized_at": "2025-08-01T09:00:00+00:00", "work_packages": {}}
        (p / "status.json").write_text(json.dumps(status))
        result = _derive_migration_timestamp(p)
    assert result == "2025-08-01T09:00:01+00:00"


def test_derive_migration_timestamp_collects_from_meta_json_created_at() -> None:
    """created_at from meta.json is used when no other sources are present."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "meta.json").write_text(json.dumps({"created_at": "2025-09-01T08:00:00+00:00"}))
        result = _derive_migration_timestamp(p)
    assert result == "2025-09-01T08:00:01+00:00"


def test_derive_migration_timestamp_picks_latest_across_all_sources() -> None:
    """When multiple sources have timestamps, the latest one wins."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "status.events.jsonl").write_text('{"at": "2025-06-01T10:00:00+00:00"}\n')
        status = {
            "materialized_at": "2025-09-15T12:00:00+00:00",
            "work_packages": {"WP01": {"last_transition_at": "2025-10-01T00:00:00+00:00"}},
        }
        (p / "status.json").write_text(json.dumps(status))
        result = _derive_migration_timestamp(p)
    # WP last_transition_at is the latest: 2025-10-01T00:00:00+00:00 + 1 second
    assert result == "2025-10-01T00:00:01+00:00"
