"""Unit tests for specify_cli.decisions.store.

Covers atomic writes, index round-trips, sort order, logical key lookup,
artifact rendering, append/update helpers, and partial-failure safety.
"""

from __future__ import annotations

import json
import os
from kernel.clock import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.decisions.models import (
    DecisionIndex,
    DecisionStatus,
    IndexEntry,
    OriginFlow,
)
from specify_cli.decisions.store import (
    DecisionIndexReadError,
    append_entry,
    artifact_path,
    decisions_dir,
    find_by_logical_key,
    index_path,
    load_index,
    save_index,
    update_entry,
    write_artifact,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

ULID_A = "01KPWT8PNY8683QX3WBW6VXYM7"
ULID_B = "01KPWT8PNY8683QX3WBW6VXYM8"
ULID_C = "01KPWT8PNY8683QX3WBW6VXYM9"
MISSION = "mission-id-01"
SLUG = "my-slug"

T0 = datetime(2026, 4, 23, 10, 0, 0, tzinfo=UTC)
T1 = T0 + timedelta(seconds=60)
T2 = T0 + timedelta(seconds=120)


def _entry(
    decision_id: str = ULID_A,
    origin_flow: OriginFlow = OriginFlow.SPECIFY,
    step_id: str | None = "step1",
    slot_key: str | None = None,
    input_key: str = "auth_strategy",
    question: str = "Which auth?",
    status: DecisionStatus = DecisionStatus.OPEN,
    created_at: datetime = T0,
    mission_id: str = MISSION,
    mission_slug: str = SLUG,
    **kwargs: object,
) -> IndexEntry:
    return IndexEntry(
        decision_id=decision_id,
        origin_flow=origin_flow,
        step_id=step_id,
        slot_key=slot_key,
        input_key=input_key,
        question=question,
        status=status,
        created_at=created_at,
        mission_id=mission_id,
        mission_slug=mission_slug,
        **kwargs,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


class TestPathHelpers:
    def test_decisions_dir(self, tmp_path: Path) -> None:
        assert decisions_dir(tmp_path) == tmp_path / "decisions"

    def test_index_path(self, tmp_path: Path) -> None:
        assert index_path(tmp_path) == tmp_path / "decisions" / "index.json"

    def test_artifact_path_naming(self, tmp_path: Path) -> None:
        p = artifact_path(tmp_path, ULID_A)
        assert p.name == f"DM-{ULID_A}.md"
        assert p.parent == decisions_dir(tmp_path)


# ---------------------------------------------------------------------------
# load_index / save_index round-trip
# ---------------------------------------------------------------------------


class TestLoadSaveIndex:
    def test_missing_file_returns_empty_index(self, tmp_path: Path) -> None:
        idx = load_index(tmp_path)
        assert idx.version == 1
        assert idx.mission_id == ""
        assert idx.entries == ()

    def test_round_trip_three_entries(self, tmp_path: Path) -> None:
        e1 = _entry(decision_id=ULID_A, created_at=T0)
        e2 = _entry(decision_id=ULID_B, created_at=T1, step_id="step2")
        e3 = _entry(decision_id=ULID_C, created_at=T2, step_id="step3")
        idx = DecisionIndex(mission_id=MISSION, entries=(e1, e2, e3))
        save_index(tmp_path, idx)
        loaded = load_index(tmp_path)
        assert len(loaded.entries) == 3
        loaded_ids = {e.decision_id for e in loaded.entries}
        assert loaded_ids == {ULID_A, ULID_B, ULID_C}

    def test_valid_utf8_json_with_trailing_newline(self, tmp_path: Path) -> None:
        idx = DecisionIndex(mission_id=MISSION, entries=(_entry(),))
        save_index(tmp_path, idx)
        raw = index_path(tmp_path).read_bytes()
        text = raw.decode("utf-8")
        assert text.endswith("\n")
        parsed = json.loads(text)
        assert parsed["version"] == 1

    def test_json_keys_sorted(self, tmp_path: Path) -> None:
        idx = DecisionIndex(mission_id=MISSION, entries=(_entry(),))
        save_index(tmp_path, idx)
        raw = index_path(tmp_path).read_text(encoding="utf-8")
        # Re-parse and re-dump with sort_keys to compare
        reparsed = json.dumps(json.loads(raw), sort_keys=True, indent=2) + "\n"
        assert raw == reparsed

    def test_deterministic_two_saves(self, tmp_path: Path) -> None:
        idx = DecisionIndex(mission_id=MISSION, entries=(_entry(),))
        save_index(tmp_path, idx)
        bytes1 = index_path(tmp_path).read_bytes()
        save_index(tmp_path, idx)
        bytes2 = index_path(tmp_path).read_bytes()
        assert bytes1 == bytes2

    def test_entries_sorted_by_created_at_then_decision_id(self, tmp_path: Path) -> None:
        # Insert in reverse order — should come out sorted ASC
        e_latest = _entry(decision_id=ULID_C, created_at=T2, step_id="s3")
        e_mid = _entry(decision_id=ULID_B, created_at=T1, step_id="s2")
        e_earliest = _entry(decision_id=ULID_A, created_at=T0)
        idx = DecisionIndex(mission_id=MISSION, entries=(e_latest, e_mid, e_earliest))
        save_index(tmp_path, idx)
        loaded = load_index(tmp_path)
        ids = [e.decision_id for e in loaded.entries]
        assert ids == [ULID_A, ULID_B, ULID_C]

    def test_creates_decisions_subdir(self, tmp_path: Path) -> None:
        d = decisions_dir(tmp_path)
        assert not d.exists()
        idx = DecisionIndex(mission_id=MISSION, entries=(_entry(),))
        save_index(tmp_path, idx)
        assert d.is_dir()


# ---------------------------------------------------------------------------
# load_index fail-closed on corrupt index.json (#4642)
# ---------------------------------------------------------------------------


class TestLoadIndexFailsClosed:
    def test_malformed_json_raises_decision_index_read_error(self, tmp_path: Path) -> None:
        decisions_dir(tmp_path).mkdir(parents=True)
        index_path(tmp_path).write_text("{ not json", encoding="utf-8")

        with pytest.raises(DecisionIndexReadError) as excinfo:
            load_index(tmp_path)

        assert excinfo.value.index_path == index_path(tmp_path)
        assert "run: spec-kitty doctor" in str(excinfo.value)

    def test_non_utf8_bytes_raises_decision_index_read_error(self, tmp_path: Path) -> None:
        decisions_dir(tmp_path).mkdir(parents=True)
        index_path(tmp_path).write_bytes(b"\xff\xfe\x00corrupt")

        with pytest.raises(DecisionIndexReadError) as excinfo:
            load_index(tmp_path)

        assert "run: spec-kitty doctor" in str(excinfo.value)

    def test_wrong_shape_raises_decision_index_read_error(self, tmp_path: Path) -> None:
        decisions_dir(tmp_path).mkdir(parents=True)
        index_path(tmp_path).write_text(json.dumps({"entries": "not-a-list"}), encoding="utf-8")

        with pytest.raises(DecisionIndexReadError) as excinfo:
            load_index(tmp_path)

        assert "run: spec-kitty doctor" in str(excinfo.value)

    def test_missing_file_still_returns_empty_index(self, tmp_path: Path) -> None:
        """Regression guard: the preserved missing-file branch must not raise."""
        idx = load_index(tmp_path)
        assert idx.entries == ()

    def test_valid_index_round_trips_after_fix(self, tmp_path: Path) -> None:
        idx = DecisionIndex(mission_id=MISSION, entries=(_entry(),))
        save_index(tmp_path, idx)
        loaded = load_index(tmp_path)
        assert loaded.mission_id == MISSION
        assert len(loaded.entries) == 1
        assert loaded.entries[0].decision_id == ULID_A


# ---------------------------------------------------------------------------
# Atomic write safety
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_no_tmp_residue_after_success(self, tmp_path: Path) -> None:
        idx = DecisionIndex(mission_id=MISSION, entries=(_entry(),))
        save_index(tmp_path, idx)
        d = decisions_dir(tmp_path)
        leftover_tmps = [f for f in os.listdir(d) if not f.endswith(".json")]
        assert leftover_tmps == [], f"Temp files left behind: {leftover_tmps}"

    def test_destination_not_corrupted_on_replace_failure(self, tmp_path: Path) -> None:
        """If os.replace raises, the original file should be unchanged."""
        idx = DecisionIndex(mission_id=MISSION, entries=(_entry(),))
        save_index(tmp_path, idx)
        original_bytes = index_path(tmp_path).read_bytes()

        with patch("specify_cli.decisions.store.os.replace", side_effect=OSError("disk full")), pytest.raises(OSError):
            save_index(tmp_path, idx)

        # Original file unchanged
        assert index_path(tmp_path).read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# append_entry
# ---------------------------------------------------------------------------


class TestAppendEntry:
    def test_creates_decisions_dir_if_missing(self, tmp_path: Path) -> None:
        assert not decisions_dir(tmp_path).exists()
        entry = _entry()
        append_entry(tmp_path, entry)
        assert decisions_dir(tmp_path).is_dir()

    def test_appended_entry_present_in_returned_index(self, tmp_path: Path) -> None:
        e = _entry()
        result = append_entry(tmp_path, e)
        assert any(x.decision_id == ULID_A for x in result.entries)

    def test_multiple_appends_accumulate(self, tmp_path: Path) -> None:
        append_entry(tmp_path, _entry(decision_id=ULID_A, created_at=T0))
        result = append_entry(tmp_path, _entry(decision_id=ULID_B, created_at=T1, step_id="s2"))
        ids = {e.decision_id for e in result.entries}
        assert ids == {ULID_A, ULID_B}


# ---------------------------------------------------------------------------
# update_entry
# ---------------------------------------------------------------------------


class TestUpdateEntry:
    def test_updates_only_target_entry(self, tmp_path: Path) -> None:
        e1 = _entry(decision_id=ULID_A, created_at=T0)
        e2 = _entry(decision_id=ULID_B, created_at=T1, step_id="s2")
        idx = DecisionIndex(mission_id=MISSION, entries=(e1, e2))
        save_index(tmp_path, idx)

        updated_idx = update_entry(tmp_path, ULID_A, status=DecisionStatus.RESOLVED)
        by_id = {e.decision_id: e for e in updated_idx.entries}

        assert by_id[ULID_A].status == DecisionStatus.RESOLVED
        assert by_id[ULID_B].status == DecisionStatus.OPEN  # unchanged

    def test_raises_keyerror_for_missing_id(self, tmp_path: Path) -> None:
        idx = DecisionIndex(mission_id=MISSION, entries=(_entry(),))
        save_index(tmp_path, idx)
        with pytest.raises(KeyError):
            update_entry(tmp_path, "NONEXISTENT_ID_XXXXXXXXXX", status=DecisionStatus.CANCELED)


# ---------------------------------------------------------------------------
# find_by_logical_key
# ---------------------------------------------------------------------------


class TestFindByLogicalKey:
    def test_positive_match_step_id_path(self) -> None:
        e = _entry(decision_id=ULID_A, step_id="step1", slot_key=None)
        idx = DecisionIndex(mission_id=MISSION, entries=(e,))
        result = find_by_logical_key(
            idx,
            origin_flow=OriginFlow.SPECIFY,
            step_id="step1",
            slot_key=None,
            input_key="auth_strategy",
        )
        assert result is not None
        assert result.decision_id == ULID_A

    def test_positive_match_slot_key_path(self) -> None:
        e = _entry(decision_id=ULID_A, step_id=None, slot_key="specify.slot1")
        idx = DecisionIndex(mission_id=MISSION, entries=(e,))
        result = find_by_logical_key(
            idx,
            origin_flow=OriginFlow.SPECIFY,
            step_id=None,
            slot_key="specify.slot1",
            input_key="auth_strategy",
        )
        assert result is not None
        assert result.decision_id == ULID_A

    def test_negative_no_match(self) -> None:
        e = _entry(step_id="step1")
        idx = DecisionIndex(mission_id=MISSION, entries=(e,))
        result = find_by_logical_key(
            idx,
            origin_flow=OriginFlow.CHARTER,
            step_id="step1",
            slot_key=None,
            input_key="auth_strategy",
        )
        assert result is None

    def test_returns_most_recent_when_multiple_match(self) -> None:
        e_old = _entry(decision_id=ULID_A, step_id="step1", created_at=T0)
        e_new = _entry(decision_id=ULID_B, step_id="step1", created_at=T1)
        idx = DecisionIndex(mission_id=MISSION, entries=(e_old, e_new))
        result = find_by_logical_key(
            idx,
            origin_flow=OriginFlow.SPECIFY,
            step_id="step1",
            slot_key=None,
            input_key="auth_strategy",
        )
        assert result is not None
        assert result.decision_id == ULID_B

    def test_step_id_and_slot_key_not_confused(self) -> None:
        """An entry with step_id should NOT match a slot_key lookup of the same value."""
        e = _entry(decision_id=ULID_A, step_id="my-key", slot_key=None)
        idx = DecisionIndex(mission_id=MISSION, entries=(e,))
        # Look up by slot_key=my-key (no step_id)
        result = find_by_logical_key(
            idx,
            origin_flow=OriginFlow.SPECIFY,
            step_id=None,
            slot_key="my-key",
            input_key="auth_strategy",
        )
        assert result is None


# ---------------------------------------------------------------------------
# write_artifact
# ---------------------------------------------------------------------------


class TestWriteArtifact:
    def test_creates_dm_file_with_decision_id(self, tmp_path: Path) -> None:
        e = _entry()
        path = write_artifact(tmp_path, e)
        assert path.name == f"DM-{ULID_A}.md"
        assert path.exists()

    def test_artifact_contains_decision_id(self, tmp_path: Path) -> None:
        e = _entry()
        path = write_artifact(tmp_path, e)
        content = path.read_text(encoding="utf-8")
        assert ULID_A in content

    def test_artifact_contains_question(self, tmp_path: Path) -> None:
        e = _entry(question="Which deployment target?")
        path = write_artifact(tmp_path, e)
        content = path.read_text(encoding="utf-8")
        assert "Which deployment target?" in content

    def test_artifact_markdown_headers(self, tmp_path: Path) -> None:
        e = _entry()
        path = write_artifact(tmp_path, e)
        content = path.read_text(encoding="utf-8")
        assert "## Question" in content
        assert "## Options" in content
        assert "## Final answer" in content
        assert "## Rationale" in content
        assert "## Change log" in content

    def test_artifact_contains_all_fields(self, tmp_path: Path) -> None:
        e = _entry(
            step_id="step1",
            slot_key=None,
            options=("oauth2", "session"),
            final_answer="oauth2",
            status=DecisionStatus.RESOLVED,
            resolved_at=T1,
            resolved_by="rob@robshouse.net",
            rationale="best fit",
        )
        path = write_artifact(tmp_path, e)
        content = path.read_text(encoding="utf-8")
        assert "step1" in content
        assert "oauth2" in content
        assert "session" in content
        assert "resolved" in content
        assert "rob@robshouse.net" in content

    def test_artifact_path_naming_convention(self, tmp_path: Path) -> None:
        e = _entry(decision_id=ULID_B, step_id="step2")
        path = write_artifact(tmp_path, e)
        assert path == decisions_dir(tmp_path) / f"DM-{ULID_B}.md"

    def test_no_tmp_residue_after_write(self, tmp_path: Path) -> None:
        e = _entry()
        write_artifact(tmp_path, e)
        d = decisions_dir(tmp_path)
        leftover = [f for f in os.listdir(d) if not f.endswith(".md")]
        assert leftover == []
