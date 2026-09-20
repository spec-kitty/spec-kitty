"""#4786 archive-freeze fix: the materialized-snapshot ``schema_version``.

The canonical replay the archive-freeze gate performs
(``tests/architectural/test_archive_root_byte_identical.py``) re-materializes
each archived mission's ``status.json`` with the CURRENT reducer and asserts
byte-identity with the frozen, committed snapshot. #4786 added a new derived
read-root field (``implementer_of_record``, ``reducer._project_implementer_attribution``)
that is injected unconditionally by ``reduce()`` -- which is exactly right for
every LIVE consumer of that function (``wp_snapshot_state``,
``event_sourced_review_result``, the accept gate) but wrong for a canonical
replay of a snapshot written before the field existed: injecting it there
would make the replay diverge from the frozen bytes and red the freeze gate.

``materialize_snapshot`` (the file-scoped entry point the freeze gate replays
through) is made version-aware instead: it keys the target schema off the
EXISTING on-disk ``status.json``'s ``schema_version`` key (absent -> legacy,
present-and-current -> current), and only a NEW mission (no ``status.json`` on
disk yet) always materializes at the current schema. This file proves both
halves of that contract directly against ``materialize_snapshot`` /
``materialize`` -- not the frozen archive fixtures themselves, which stay
untouched (see the architectural test file above).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import (
    CURRENT_SNAPSHOT_SCHEMA_VERSION,
    IMPLEMENTER_OF_RECORD_SLOT,
    materialize,
    materialize_snapshot,
    materialize_to_json,
)
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.fast]


def _claim_event(*, event_id: str, wp_id: str, at: str, agent: str) -> StatusEvent:
    """A real ``planned -> claimed`` transition carrying the claimant sidecar."""
    return StatusEvent(
        event_id=event_id,
        mission_slug="schema-version-4786",
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at=at,
        actor=agent,
        force=False,
        execution_mode="worktree",
        policy_metadata={"agent": agent},
    )


def _seed_claimed_wp(feature_dir: Path, *, event_id: str, agent: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    append_event(
        feature_dir,
        _claim_event(event_id=event_id, wp_id="WP01", at="2026-09-20T00:00:01+00:00", agent=agent),
    )


class TestNewMissionMaterializesAtCurrentSchema:
    """A mission with no pre-existing ``status.json`` is never "legacy"."""

    def test_new_mission_carries_schema_version_and_implementer_of_record(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "schema-version-4786"
        _seed_claimed_wp(feature_dir, event_id="01HXYZ0000000000000000000A", agent="impl-alice")

        snapshot = materialize(feature_dir)

        assert snapshot.schema_version == CURRENT_SNAPSHOT_SCHEMA_VERSION
        assert snapshot.work_packages["WP01"][IMPLEMENTER_OF_RECORD_SLOT] == "impl-alice"

        on_disk = json.loads((feature_dir / "status.json").read_text(encoding="utf-8"))
        assert on_disk["schema_version"] == CURRENT_SNAPSHOT_SCHEMA_VERSION
        assert on_disk["work_packages"]["WP01"][IMPLEMENTER_OF_RECORD_SLOT] == "impl-alice"

    def test_materialize_snapshot_alone_matches_materialize_write(self, tmp_path: Path) -> None:
        """The freeze gate's read path (``materialize_snapshot``) agrees with
        the write path (``materialize``) for a brand-new mission too."""
        feature_dir = tmp_path / "kitty-specs" / "schema-version-4786"
        _seed_claimed_wp(feature_dir, event_id="01HXYZ0000000000000000000A", agent="impl-alice")

        snapshot = materialize_snapshot(feature_dir)

        assert snapshot.schema_version == CURRENT_SNAPSHOT_SCHEMA_VERSION
        assert snapshot.work_packages["WP01"][IMPLEMENTER_OF_RECORD_SLOT] == "impl-alice"


class TestLegacySnapshotReplaysWithoutTheNewField:
    """An existing snapshot with no ``schema_version`` key stays legacy forever."""

    def _write_legacy_status_json(self, feature_dir: Path) -> None:
        """Simulate a pre-#4786 committed snapshot: no ``schema_version`` key,
        no ``implementer_of_record`` -- exactly what every frozen archive
        carries on disk today."""
        legacy = {
            "mission_slug": "schema-version-4786",
            "materialized_at": "2026-09-01T00:00:00+00:00",
            "event_count": 1,
            "last_event_id": "01HXYZ0000000000000000000A",
            "work_packages": {
                "WP01": {
                    "lane": "claimed",
                    "agent": "impl-alice",
                    "force_count": 0,
                    "last_event_id": "01HXYZ0000000000000000000A",
                    "last_transition_at": "2026-09-20T00:00:01+00:00",
                    "actor": "impl-alice",
                }
            },
            "summary": {"claimed": 1},
        }
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "status.json").write_text(json.dumps(legacy, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def test_legacy_snapshot_materializes_without_the_new_field_or_marker(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "schema-version-4786"
        self._write_legacy_status_json(feature_dir)
        # The real event log a canonical replay reads, matching the frozen
        # status.json's own WP01 claim above.
        _seed_claimed_wp(feature_dir, event_id="01HXYZ0000000000000000000A", agent="impl-alice")

        snapshot = materialize_snapshot(feature_dir)

        assert snapshot.schema_version is None
        assert IMPLEMENTER_OF_RECORD_SLOT not in snapshot.work_packages["WP01"]

        canonical_json = json.loads(materialize_to_json(snapshot))
        assert "schema_version" not in canonical_json
        assert IMPLEMENTER_OF_RECORD_SLOT not in canonical_json["work_packages"]["WP01"]

    def test_legacy_snapshot_is_never_upgraded_by_a_bare_replay(self, tmp_path: Path) -> None:
        """Reading (never writing) a legacy snapshot must not flip it forward --
        the freeze gate's replay is read-only by design."""
        feature_dir = tmp_path / "kitty-specs" / "schema-version-4786"
        self._write_legacy_status_json(feature_dir)
        _seed_claimed_wp(feature_dir, event_id="01HXYZ0000000000000000000A", agent="impl-alice")

        before = (feature_dir / "status.json").read_text(encoding="utf-8")
        materialize_snapshot(feature_dir)
        after = (feature_dir / "status.json").read_text(encoding="utf-8")

        assert before == after
