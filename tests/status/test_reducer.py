"""Tests for the deterministic status reducer."""

from __future__ import annotations

import pytest
import json
from pathlib import Path
from unittest.mock import patch


from specify_cli.post_merge.review_artifact_consistency import (
    find_rejected_review_artifact_conflicts,
)
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status.models import (
    NON_DISPLAY_LANES,
    DoneEvidence,
    InnerStateChanged,
    Lane,
    ReviewApproval,
    ReviewOverride,
    ReviewResult,
    StatusEvent,
    StatusSnapshot,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import (
    SNAPSHOT_FILENAME,
    ReviewResultLookup,
    event_sourced_review_result,
    materialize,
    materialize_to_json,
    reduce,
    review_result_from_state,
)
from specify_cli.status.store import append_annotations_atomic_verified, append_event
from tests.reliability.fixtures import (
    MissionFixture,
    WorkPackageSpec,
    create_mission_fixture,
    write_work_package,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _make_event(
    *,
    event_id: str = "01HXYZ0000000000000000000A",
    mission_slug: str = "034-feature-name",
    wp_id: str = "WP01",
    from_lane: Lane = Lane.PLANNED,
    to_lane: Lane = Lane.CLAIMED,
    at: str = "2026-02-08T12:00:00Z",
    actor: str = "claude-opus",
    force: bool = False,
    execution_mode: str = "worktree",
    reason: str | None = None,
    review_ref: str | None = None,
    review_result: ReviewResult | None = None,
    evidence: DoneEvidence | None = None,
) -> StatusEvent:
    """Helper to build StatusEvent with sensible defaults."""
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor=actor,
        force=force,
        execution_mode=execution_mode,
        reason=reason,
        review_ref=review_ref,
        review_result=review_result,
        evidence=evidence,
    )


def _write_review_cycle_artifact(
    artifact_dir: Path,
    *,
    wp_id: str = "WP01",
    mission_slug: str = "034-feature-name",
    cycle_number: int,
    verdict: str,
) -> Path:
    """Write a real ``review-cycle-N.md`` artifact (WP07 T029 fixtures)."""
    artifact = ReviewCycleArtifact(
        cycle_number=cycle_number,
        wp_id=wp_id,
        mission_slug=mission_slug,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-02-08T12:00:00+00:00",
        body=f"# Review\n\nVerdict: {verdict}\n",
    )
    path = artifact_dir / f"review-cycle-{cycle_number}.md"
    artifact.write(path)
    return path


class TestReduceEmpty:
    """Tests for reducing an empty event list."""

    def test_reduce_empty_events(self) -> None:
        snapshot = reduce([])

        assert snapshot.mission_slug == ""
        assert snapshot.event_count == 0
        assert snapshot.last_event_id is None
        assert snapshot.work_packages == {}
        # NON_DISPLAY_LANES (genesis, uninitialized) are excluded from the summary
        assert snapshot.summary == {lane.value: 0 for lane in Lane if lane not in NON_DISPLAY_LANES}


class TestReduceSingleEvent:
    """Tests for reducing a single event."""

    def test_reduce_single_event(self) -> None:
        event = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
            actor="claude-opus",
        )
        snapshot = reduce([event])

        assert snapshot.mission_slug == "034-feature-name"
        assert snapshot.event_count == 1
        assert snapshot.last_event_id == "01HXYZ0000000000000000000A"
        assert "WP01" in snapshot.work_packages
        wp = snapshot.work_packages["WP01"]
        assert wp["lane"] == "claimed"
        assert wp["actor"] == "claude-opus"
        assert wp["last_transition_at"] == "2026-02-08T12:00:00Z"
        assert wp["last_event_id"] == "01HXYZ0000000000000000000A"
        assert wp["force_count"] == 0
        assert snapshot.summary["claimed"] == 1


class TestReduceOrderedEvents:
    """Tests for reducing events already in order."""

    def test_reduce_ordered_events(self) -> None:
        events = [
            _make_event(
                event_id="01HXYZ0000000000000000000A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T12:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000B",
                wp_id="WP01",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T13:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000C",
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.FOR_REVIEW,
                at="2026-02-08T14:00:00Z",
            ),
        ]
        snapshot = reduce(events)

        assert snapshot.event_count == 3
        assert snapshot.work_packages["WP01"]["lane"] == "for_review"
        assert snapshot.summary["for_review"] == 1


class TestReduceOutOfOrder:
    """Tests for reducing events that arrive out of order."""

    def test_reduce_out_of_order_events(self) -> None:
        """Events are sorted by (at, event_id), so order in list doesn't matter."""
        events = [
            _make_event(
                event_id="01HXYZ0000000000000000000C",
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.FOR_REVIEW,
                at="2026-02-08T14:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T12:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000B",
                wp_id="WP01",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T13:00:00Z",
            ),
        ]
        snapshot = reduce(events)

        assert snapshot.work_packages["WP01"]["lane"] == "for_review"
        assert snapshot.last_event_id == "01HXYZ0000000000000000000C"


class TestReduceDeduplication:
    """Tests for deduplication by event_id."""

    def test_reduce_deduplication(self) -> None:
        """Duplicate event_ids are deduplicated; first occurrence kept."""
        event = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
            actor="claude-opus",
        )
        # Same event_id but different actor (simulating corruption)
        duplicate = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
            actor="other-agent",
        )
        snapshot = reduce([event, duplicate])

        assert snapshot.event_count == 1
        assert snapshot.work_packages["WP01"]["actor"] == "claude-opus"


class TestReduceMultipleWPs:
    """Tests for reducing events across multiple work packages."""

    def test_reduce_multiple_wps(self) -> None:
        events = [
            _make_event(
                event_id="01HXYZ0000000000000000000A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T12:00:00Z",
                actor="agent-a",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000B",
                wp_id="WP02",
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T12:30:00Z",
                actor="agent-b",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000C",
                wp_id="WP03",
                from_lane=Lane.PLANNED,
                to_lane=Lane.BLOCKED,
                at="2026-02-08T13:00:00Z",
                actor="agent-c",
            ),
        ]
        snapshot = reduce(events)

        assert len(snapshot.work_packages) == 3
        assert snapshot.work_packages["WP01"]["lane"] == "claimed"
        assert snapshot.work_packages["WP02"]["lane"] == "in_progress"
        assert snapshot.work_packages["WP03"]["lane"] == "blocked"
        assert snapshot.summary["claimed"] == 1
        assert snapshot.summary["in_progress"] == 1
        assert snapshot.summary["blocked"] == 1


class TestReduceForceCount:
    """Tests for force_count tracking."""

    def test_reduce_force_count_tracked(self) -> None:
        events = [
            _make_event(
                event_id="01HXYZ0000000000000000000A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T12:00:00Z",
                force=False,
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000B",
                wp_id="WP01",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T13:00:00Z",
                force=True,
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000C",
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.FOR_REVIEW,
                at="2026-02-08T14:00:00Z",
                force=True,
            ),
        ]
        snapshot = reduce(events)

        assert snapshot.work_packages["WP01"]["force_count"] == 2


class TestReduceConcurrentRollbackPrecedence:
    """Tests for rollback-aware conflict resolution."""

    def test_in_review_to_in_progress_rollback_beats_concurrent_approval(self) -> None:
        """Current reviewer rollback transition wins over same-timestamp approval."""
        at = "2026-02-08T15:00:00Z"
        events = [
            _make_event(
                event_id="01HXYZ0000000000000000000A",
                wp_id="WP01",
                from_lane=Lane.IN_REVIEW,
                to_lane=Lane.IN_PROGRESS,
                at=at,
                actor="reviewer-a",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000B",
                wp_id="WP01",
                from_lane=Lane.IN_REVIEW,
                to_lane=Lane.APPROVED,
                at=at,
                actor="reviewer-b",
                review_ref="review://WP01/approved",
            ),
        ]

        snapshot = reduce(events)

        assert snapshot.work_packages["WP01"]["lane"] == "in_progress"
        assert snapshot.work_packages["WP01"]["last_event_id"] == "01HXYZ0000000000000000000A"
        assert snapshot.summary["in_progress"] == 1
        assert snapshot.summary["approved"] == 0

    def test_legacy_for_review_to_in_progress_rollback_still_beats_concurrent_forward_event(self) -> None:
        """Legacy reviewer rollback shape keeps rollback precedence."""
        at = "2026-02-08T15:00:00Z"
        events = [
            _make_event(
                event_id="01HXYZ0000000000000000000A",
                wp_id="WP01",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.IN_PROGRESS,
                at=at,
                actor="reviewer-a",
                review_ref="review://WP01/changes-requested",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000B",
                wp_id="WP01",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.APPROVED,
                at=at,
                actor="reviewer-b",
                review_ref="review://WP01/approved",
            ),
        ]

        snapshot = reduce(events)

        assert snapshot.work_packages["WP01"]["lane"] == "in_progress"
        assert snapshot.work_packages["WP01"]["last_event_id"] == "01HXYZ0000000000000000000A"
        assert snapshot.summary["in_progress"] == 1
        assert snapshot.summary["approved"] == 0


class TestSummaryCounts:
    """Tests that summary counts match WP states."""

    def test_summary_counts_match_wp_states(self) -> None:
        events = [
            _make_event(
                event_id="01HXYZ0000000000000000000A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T12:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000B",
                wp_id="WP02",
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T12:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000C",
                wp_id="WP03",
                from_lane=Lane.PLANNED,
                to_lane=Lane.FOR_REVIEW,
                at="2026-02-08T13:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000000D",
                wp_id="WP04",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.DONE,
                at="2026-02-08T14:00:00Z",
                actor="reviewer",
            ),
        ]
        snapshot = reduce(events)

        # Count lanes from WP states manually (NON_DISPLAY_LANES excluded)
        lane_counts: dict[str, int] = {lane.value: 0 for lane in Lane if lane not in NON_DISPLAY_LANES}
        for wp_state in snapshot.work_packages.values():
            lane_counts[wp_state["lane"]] += 1

        assert snapshot.summary == lane_counts


class TestByteIdenticalOutput:
    """Tests for deterministic JSON serialization."""

    def test_byte_identical_output(self) -> None:
        """Two calls to materialize_to_json with the same snapshot produce
        identical byte strings."""
        snapshot = StatusSnapshot(
            mission_slug="034-feature-name",
            materialized_at="2026-02-08T15:00:00Z",
            event_count=2,
            last_event_id="01HXYZ0000000000000000000B",
            work_packages={
                "WP01": {
                    "lane": "in_progress",
                    "actor": "claude-opus",
                    "last_transition_at": "2026-02-08T13:00:00Z",
                    "last_event_id": "01HXYZ0000000000000000000B",
                    "force_count": 0,
                },
            },
            summary={
                "planned": 0,
                "claimed": 0,
                "in_progress": 1,
                "for_review": 0,
                "in_review": 0,
                "approved": 0,
                "done": 0,
                "blocked": 0,
                "canceled": 0,
            },
        )

        json_a = materialize_to_json(snapshot)
        json_b = materialize_to_json(snapshot)

        assert json_a == json_b
        assert json_a.endswith("\n")

        # Verify it's valid JSON
        parsed = json.loads(json_a)
        assert parsed["mission_slug"] == "034-feature-name"

    def test_byte_identical_across_reduce_calls(self) -> None:
        """Two reduce calls with the same events and a fixed materialized_at
        produce identical JSON."""
        events = [
            _make_event(
                event_id="01HXYZ0000000000000000000A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T12:00:00Z",
            ),
        ]

        fixed_time = "2026-02-08T15:00:00+00:00"
        with patch("kernel.clock.now_utc_iso", return_value=fixed_time):
            snapshot_a = reduce(events)
            snapshot_b = reduce(events)

        json_a = materialize_to_json(snapshot_a)
        json_b = materialize_to_json(snapshot_b)
        assert json_a == json_b

    def test_sorted_keys_in_json_output(self) -> None:
        """JSON output has sorted keys for deterministic diff-friendly output."""
        snapshot = StatusSnapshot(
            mission_slug="034-parity-test",
            materialized_at="2026-02-08T15:00:00+00:00",
            event_count=1,
            last_event_id="01HXYZ0000000000000000000A",
            work_packages={
                "WP01": {
                    "lane": "claimed",
                    "actor": "agent",
                    "last_transition_at": "2026-02-08T12:00:00+00:00",
                    "last_event_id": "01HXYZ0000000000000000000A",
                    "force_count": 0,
                },
            },
            summary={
                "planned": 0,
                "claimed": 1,
                "in_progress": 0,
                "for_review": 0,
                "done": 0,
                "blocked": 0,
                "canceled": 0,
            },
        )

        json_str = materialize_to_json(snapshot)
        parsed = json.loads(json_str)

        # Top-level keys should be sorted
        top_keys = list(parsed.keys())
        assert top_keys == sorted(top_keys)


class TestRealisticEventLog:
    """Test determinism with a realistic multi-WP event sequence.

    Relocated from the retired ``tests/status/test_parity.py``
    (``TestFullEventLogParity``, WP09 / NFR-006): no other test pins these
    realistic-log invariants.
    """

    def _build_realistic_event_log(self) -> list[StatusEvent]:
        """Build a realistic event log covering multiple WPs and lanes."""
        evidence = DoneEvidence(
            review=ReviewApproval(
                reviewer="reviewer-1",
                verdict="approved",
                reference="PR#100",
            ),
        )
        return [
            # WP01: planned -> claimed -> in_progress -> for_review -> done
            _make_event(
                event_id="01HXYZ0000000000000000WP1A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T10:00:00+00:00",
                actor="agent-1",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000WP1B",
                wp_id="WP01",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T10:30:00+00:00",
                actor="agent-1",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000WP1C",
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.FOR_REVIEW,
                at="2026-02-08T14:00:00+00:00",
                actor="agent-1",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000WP1D",
                wp_id="WP01",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.DONE,
                at="2026-02-08T16:00:00+00:00",
                actor="reviewer-1",
                evidence=evidence,
            ),
            # WP02: planned -> claimed -> in_progress -> blocked
            _make_event(
                event_id="01HXYZ0000000000000000WP2A",
                wp_id="WP02",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T10:15:00+00:00",
                actor="agent-2",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000WP2B",
                wp_id="WP02",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T10:45:00+00:00",
                actor="agent-2",
            ),
            _make_event(
                event_id="01HXYZ0000000000000000WP2C",
                wp_id="WP02",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.BLOCKED,
                at="2026-02-08T12:00:00+00:00",
                actor="agent-2",
            ),
            # WP03: planned -> canceled
            _make_event(
                event_id="01HXYZ0000000000000000WP3A",
                wp_id="WP03",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CANCELED,
                at="2026-02-08T11:00:00+00:00",
                actor="lead",
                force=True,
                reason="Descoped from release",
            ),
            # WP04: stays planned (no events beyond initial state)
        ]

    def test_realistic_log_produces_expected_summary(self) -> None:
        """A realistic event log produces the expected lane summary."""
        events = self._build_realistic_event_log()

        with patch(
            "kernel.clock.now_utc_iso",
            return_value="2026-02-08T18:00:00+00:00",
        ):
            snap = reduce(events)

        assert snap.event_count == 8
        assert snap.work_packages["WP01"]["lane"] == "done"
        assert snap.work_packages["WP02"]["lane"] == "blocked"
        assert snap.work_packages["WP03"]["lane"] == "canceled"
        # WP04 has no events so it's not in the snapshot
        assert "WP04" not in snap.work_packages

        assert snap.summary["done"] == 1
        assert snap.summary["blocked"] == 1
        assert snap.summary["canceled"] == 1
        assert snap.summary["planned"] == 0
        assert snap.summary["claimed"] == 0
        assert snap.summary["in_progress"] == 0
        assert snap.summary["for_review"] == 0

    def test_realistic_log_json_roundtrip_stable(self) -> None:
        """Serialize -> parse -> re-serialize is stable for realistic log."""
        events = self._build_realistic_event_log()

        fixed_time = "2026-02-08T18:00:00+00:00"
        with patch("kernel.clock.now_utc_iso", return_value=fixed_time):
            snap = reduce(events)

        json_1 = materialize_to_json(snap)
        parsed = json.loads(json_1)
        roundtrip = StatusSnapshot.from_dict(parsed)
        json_2 = materialize_to_json(roundtrip)

        assert json_1 == json_2


class TestMaterializeFile:
    """Tests for materialize() writing to disk."""

    def test_materialize_creates_status_json(self, tmp_path: Path) -> None:
        """materialize() reads events and writes status.json."""
        feature_dir = tmp_path / "kitty-specs" / "034-feature"
        feature_dir.mkdir(parents=True)

        event = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
        )
        append_event(feature_dir, event)

        snapshot = materialize(feature_dir)

        status_path = feature_dir / SNAPSHOT_FILENAME
        assert status_path.exists()

        content = status_path.read_text(encoding="utf-8")
        parsed = json.loads(content)
        assert parsed["mission_slug"] == "034-feature-name"
        assert parsed["event_count"] == 1
        assert "WP01" in parsed["work_packages"]

        # Snapshot returned matches file content
        assert snapshot.mission_slug == "034-feature-name"
        assert snapshot.event_count == 1

    def test_materialize_atomic_write(self, tmp_path: Path) -> None:
        """materialize() does not leave .tmp files behind."""
        feature_dir = tmp_path / "kitty-specs" / "034-feature"
        feature_dir.mkdir(parents=True)

        event = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
        )
        append_event(feature_dir, event)

        materialize(feature_dir)

        # The .tmp file should not remain
        tmp_file = feature_dir / (SNAPSHOT_FILENAME + ".tmp")
        assert not tmp_file.exists()
        # But the final file should exist
        assert (feature_dir / SNAPSHOT_FILENAME).exists()

    def test_materialize_empty_events(self, tmp_path: Path) -> None:
        """materialize() with no events file still writes status.json."""
        feature_dir = tmp_path / "kitty-specs" / "034-feature"
        feature_dir.mkdir(parents=True)

        snapshot = materialize(feature_dir)

        status_path = feature_dir / SNAPSHOT_FILENAME
        assert status_path.exists()
        assert snapshot.mission_slug == ""
        assert snapshot.event_count == 0

    def test_materialize_overwrites_existing(self, tmp_path: Path) -> None:
        """materialize() overwrites an existing status.json."""
        feature_dir = tmp_path / "kitty-specs" / "034-feature"
        feature_dir.mkdir(parents=True)

        # Write initial event and materialize
        event1 = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
        )
        append_event(feature_dir, event1)
        materialize(feature_dir)

        # Add another event and re-materialize
        event2 = _make_event(
            event_id="01HXYZ0000000000000000000B",
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-02-08T13:00:00Z",
        )
        append_event(feature_dir, event2)
        snapshot = materialize(feature_dir)

        assert snapshot.event_count == 2
        assert snapshot.work_packages["WP01"]["lane"] == "in_progress"


class TestReduceDeterministicMaterializedAt:
    """Tests for deterministic materialized_at after T001 fix."""

    def test_same_events_produce_same_materialized_at(self) -> None:
        """Same input → same materialized_at (no wall-clock dependency)."""
        event = _make_event(at="2026-02-08T12:00:00Z")
        snapshot1 = reduce([event])
        snapshot2 = reduce([event])
        assert snapshot1.materialized_at == snapshot2.materialized_at

    def test_materialized_at_equals_last_event_at(self) -> None:
        """materialized_at is the timestamp of the last event."""
        e1 = _make_event(event_id="01A", at="2026-01-01T00:00:00Z")
        e2 = _make_event(
            event_id="01B",
            at="2026-02-01T00:00:00Z",
            wp_id="WP02",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
        )
        snapshot = reduce([e1, e2])
        assert snapshot.materialized_at == "2026-02-01T00:00:00Z"

    def test_empty_events_stable_materialized_at(self) -> None:
        """Empty event list → materialized_at is stable empty string."""
        s1 = reduce([])
        s2 = reduce([])
        assert s1.materialized_at == s2.materialized_at == ""


class TestMaterializeIdempotency:
    """Tests for skip-write guard in materialize()."""

    def test_first_call_writes_file(self, tmp_path: Path) -> None:
        """First call to materialize() creates status.json."""
        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        event = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
        )
        append_event(feature_dir, event)

        materialize(feature_dir)
        assert (feature_dir / SNAPSHOT_FILENAME).exists()

    def test_second_call_with_same_events_does_not_write(self, tmp_path: Path) -> None:
        """Second call produces identical JSON — file mtime must not change."""
        import time

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        event = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
        )
        append_event(feature_dir, event)

        # First call: writes the file
        materialize(feature_dir)
        mtime_before = (feature_dir / SNAPSHOT_FILENAME).stat().st_mtime

        # Ensure mtime would differ if written again
        time.sleep(0.05)

        # Second call: same events, should skip write
        materialize(feature_dir)
        mtime_after = (feature_dir / SNAPSHOT_FILENAME).stat().st_mtime

        assert mtime_before == mtime_after

    def test_new_event_triggers_write(self, tmp_path: Path) -> None:
        """New event → JSON changes → write occurs → mtime changes."""
        import time

        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        event1 = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
        )
        append_event(feature_dir, event1)
        materialize(feature_dir)
        mtime_before = (feature_dir / SNAPSHOT_FILENAME).stat().st_mtime

        time.sleep(0.05)

        # Add a new event and re-materialize
        event2 = _make_event(
            event_id="01HXYZ0000000000000000000B",
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-02-08T13:00:00Z",
        )
        append_event(feature_dir, event2)
        materialize(feature_dir)
        mtime_after = (feature_dir / SNAPSHOT_FILENAME).stat().st_mtime

        assert mtime_after > mtime_before


class TestMaterializeGitClean:
    """Integration test: materialize() leaves clean git tree after read-only calls."""

    def test_materialize_leaves_clean_git_tree(self, tmp_path: Path) -> None:
        """Calling materialize() twice does not dirty the git working tree."""
        import subprocess

        # Init git repo
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )

        # Create feature dir with events and initial status.json
        feature_dir = tmp_path / "kitty-specs" / "069-test"
        feature_dir.mkdir(parents=True)

        event = _make_event(
            event_id="01HXYZ0000000000000000000A",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
        )
        append_event(feature_dir, event)

        # First materialize to create status.json, then commit
        materialize(feature_dir)
        subprocess.run(
            ["git", "-C", str(tmp_path), "add", "-A"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "initial"],
            check=True,
            capture_output=True,
        )

        # Second materialize (same events) should skip write → clean tree
        materialize(feature_dir)

        result = subprocess.run(
            ["git", "-C", str(tmp_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "", f"Unexpected dirty files: {result.stdout}"


def _in_review_exit_events(
    *,
    review_result: ReviewResult | None,
    target: Lane = Lane.APPROVED,
    force: bool = False,
    reason: str | None = None,
) -> list[StatusEvent]:
    """Build a planned->claimed->in_review->target event chain for WP01.

    The final hop is the ONLY transition class that writes the new
    ``review_result`` slot (from_lane == IN_REVIEW) — see
    ``reducer._wp_state_from_event``'s docstring.
    """
    return [
        _make_event(
            event_id="01HXYZ00000000000000000A1",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T10:00:00Z",
        ),
        _make_event(
            event_id="01HXYZ00000000000000000A2",
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_REVIEW,
            at="2026-02-08T11:00:00Z",
        ),
        _make_event(
            event_id="01HXYZ00000000000000000A3",
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=target,
            at="2026-02-08T12:00:00Z",
            actor="reviewer-a",
            force=force,
            reason=reason,
            review_result=review_result,
        ),
    ]


class TestReviewResultSlot:
    """T025/T026 (WP07) — the reducer's new ``review_result`` slot."""

    def test_approved_review_result_populates_slot(self) -> None:
        rr = ReviewResult(reviewer="reviewer-a", verdict="approved", reference="review-cycle://m/WP01/review-cycle-1.md")
        snapshot = reduce(_in_review_exit_events(review_result=rr, target=Lane.APPROVED))
        state = snapshot.work_packages["WP01"]
        assert "review_result" in state
        assert state["review_result"] == rr.to_dict()

    def test_changes_requested_review_result_populates_slot_identically(self) -> None:
        """Edge case (T025): a rejection populates the slot the same way as an approval."""
        rr = ReviewResult(reviewer="reviewer-a", verdict="changes_requested", reference="feedback://m/WP01/review-cycle-1.md")
        snapshot = reduce(_in_review_exit_events(review_result=rr, target=Lane.IN_PROGRESS))
        state = snapshot.work_packages["WP01"]
        assert "review_result" in state
        assert state["review_result"] == rr.to_dict()

    def test_slot_absent_for_never_reviewed_wp(self) -> None:
        """T027: a WP that never exits in_review carries no review_result key at all."""
        events = [
            _make_event(
                event_id="01A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T10:00:00Z",
            ),
            _make_event(
                event_id="01B",
                wp_id="WP01",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T11:00:00Z",
            ),
        ]
        snapshot = reduce(events)
        assert "review_result" not in snapshot.work_packages["WP01"]

    def test_slot_carried_forward_after_unrelated_transition(self) -> None:
        """Once set, a later transition NOT from in_review must not erase it (sticky)."""
        rr = ReviewResult(reviewer="reviewer-a", verdict="approved", reference="review-cycle://m/WP01/review-cycle-1.md")
        events = _in_review_exit_events(review_result=rr, target=Lane.DONE)
        events.append(
            _make_event(
                event_id="01HXYZ00000000000000000A4",
                wp_id="WP01",
                from_lane=Lane.DONE,
                to_lane=Lane.BLOCKED,
                at="2026-02-08T13:00:00Z",
                actor="ops",
                force=True,
                reason="unrelated block, unforced FSM edge",
            )
        )
        snapshot = reduce(events)
        state = snapshot.work_packages["WP01"]
        assert state["lane"] == "blocked"
        assert state["review_result"] == rr.to_dict()

    def test_forced_in_review_exit_with_no_review_result_records_null(self) -> None:
        """T028: a --force in_review exit with no ReviewResult records an
        explicit ``None`` — present in the snapshot, distinct from absent."""
        events = _in_review_exit_events(
            review_result=None,
            target=Lane.PLANNED,
            force=True,
            reason="operator override, no review performed",
        )
        snapshot = reduce(events)
        state = snapshot.work_packages["WP01"]
        assert "review_result" in state
        assert state["review_result"] is None

    def test_single_hop_in_progress_to_approved_with_review_result_populates_slot(
        self,
    ) -> None:
        """Reviewer finding: emit applies no ``from_lane`` filter, so a
        single-hop ``in_progress -> approved`` (a legal edge per
        ``InProgressState.allowed_targets``, e.g. the external
        ``orchestrator_api`` ``transition`` ingress) carrying evidence AND a
        populated ``ReviewResult`` is constructible without ever passing
        through ``in_review``. A trigger keyed solely on
        ``from_lane == IN_REVIEW`` would silently drop this verdict -- the
        slot must be populated regardless of which edge carried it."""
        rr = ReviewResult(reviewer="reviewer-a", verdict="approved", reference="review-cycle://m/WP01/review-cycle-1.md")
        events = [
            _make_event(
                event_id="01HXYZ00000000000000000D1",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T10:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ00000000000000000D2",
                wp_id="WP01",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T11:00:00Z",
            ),
            _make_event(
                event_id="01HXYZ00000000000000000D3",
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.APPROVED,
                at="2026-02-08T12:00:00Z",
                actor="reviewer-a",
                review_result=rr,
            ),
        ]
        snapshot = reduce(events)
        state = snapshot.work_packages["WP01"]
        assert state["lane"] == "approved"
        assert "review_result" in state
        assert state["review_result"] == rr.to_dict()

    def test_single_hop_in_progress_to_approved_overrides_stale_carried_forward_verdict(
        self,
    ) -> None:
        """Reviewer finding: a prior in_review cycle's carried-forward
        ``changes_requested`` must NOT survive a later single-hop
        ``in_progress -> approved`` that carries its OWN, new ``review_result``
        -- the new event's verdict wins, never the stale carry-forward."""
        stale = ReviewResult(reviewer="old", verdict="changes_requested", reference="feedback://m/WP01/review-cycle-1.md")
        fresh = ReviewResult(reviewer="reviewer-a", verdict="approved", reference="review-cycle://m/WP01/review-cycle-2.md")
        events = _in_review_exit_events(review_result=stale, target=Lane.IN_PROGRESS)
        events.append(
            _make_event(
                event_id="01HXYZ00000000000000000E1",
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.APPROVED,
                at="2026-02-08T13:00:00Z",
                actor="reviewer-a",
                review_result=fresh,
            )
        )
        snapshot = reduce(events)
        state = snapshot.work_packages["WP01"]
        assert state["lane"] == "approved"
        assert state["review_result"] == fresh.to_dict()
        assert state["review_result"] != stale.to_dict()


class TestReviewResultPrecedence:
    """T026 (WP07) — ``review_result`` and ``review`` (arbiter override) never collapse."""

    def test_both_slots_populated_independently(self) -> None:
        """An override recorded after a standing rejection: both facts survive,
        neither erases the other (T026's precedence rule)."""
        rr = ReviewResult(reviewer="reviewer-a", verdict="changes_requested", reference="feedback://m/WP01/review-cycle-1.md")
        events = _in_review_exit_events(review_result=rr, target=Lane.IN_PROGRESS)
        override = ReviewOverride(at="2026-02-08T13:00:00Z", actor="arbiter-a", wp_id="WP01", reason="ship anyway")
        annotation = InnerStateChanged(
            event_id="01HXYZ00000000000000000B1",
            wp_id="WP01",
            at="2026-02-08T13:00:00Z",
            actor="arbiter-a",
            delta=WPInnerStateDelta(review=override),
        )
        snapshot = reduce(events, [annotation])
        state = snapshot.work_packages["WP01"]
        assert state["review_result"] == rr.to_dict()
        assert state["review"] == override.to_dict()

    def test_review_result_alone_unaffected_by_absent_override(self) -> None:
        """Edge case: the single-slot-populated case is unchanged by T026's addition."""
        rr = ReviewResult(reviewer="reviewer-a", verdict="approved", reference="review-cycle://m/WP01/review-cycle-1.md")
        snapshot = reduce(_in_review_exit_events(review_result=rr, target=Lane.APPROVED))
        state = snapshot.work_packages["WP01"]
        assert state["review_result"] == rr.to_dict()
        assert "review" not in state


class TestEventSourcedReviewResultReader:
    """T027/T028 (WP07) — ``review_result_from_state`` / ``event_sourced_review_result``."""

    def test_lookup_from_state_slot_absent(self) -> None:
        lookup = review_result_from_state({"lane": "in_progress"})
        assert lookup == ReviewResultLookup(slot_present=False, result=None)

    def test_lookup_from_state_slot_null(self) -> None:
        lookup = review_result_from_state({"lane": "planned", "review_result": None})
        assert lookup == ReviewResultLookup(slot_present=True, result=None)

    def test_lookup_from_state_slot_populated(self) -> None:
        rr = ReviewResult(reviewer="r", verdict="approved", reference="review-cycle://m/WP01/1.md")
        lookup = review_result_from_state({"lane": "approved", "review_result": rr.to_dict()})
        assert lookup == ReviewResultLookup(slot_present=True, result=rr)

    def test_lookup_from_state_malformed_slot_fails_closed(self) -> None:
        """A slot value that is not a mapping (or missing required fields) is
        treated as ``slot_present=True, result=None`` — fail-closed, not a crash."""
        lookup = review_result_from_state({"lane": "approved", "review_result": "not-a-mapping"})
        assert lookup == ReviewResultLookup(slot_present=True, result=None)

        lookup_missing_fields = review_result_from_state({"lane": "approved", "review_result": {"reviewer": "r"}})
        assert lookup_missing_fields == ReviewResultLookup(slot_present=True, result=None)

    def test_event_sourced_review_result_migrated_wp(self, tmp_path: Path) -> None:
        """A migrated mission (slot populated) reads its verdict from the
        snapshot without touching any frontmatter fallback path at all."""
        feature_dir = tmp_path / "kitty-specs" / "069-migrated"
        feature_dir.mkdir(parents=True)
        rr = ReviewResult(reviewer="r", verdict="approved", reference="review-cycle://m/WP01/1.md")
        for event in _in_review_exit_events(review_result=rr, target=Lane.APPROVED):
            append_event(feature_dir, event)

        lookup = event_sourced_review_result(feature_dir, "WP01")

        assert lookup.slot_present is True
        assert lookup.result == rr

    def test_event_sourced_review_result_never_reviewed_wp_slot_absent(self, tmp_path: Path) -> None:
        """T027 (synthetic): a WP with no in_review exit -> slot absent (fallback
        applies at the CALLER, e.g. find_rejected_review_artifact_conflicts)."""
        feature_dir = tmp_path / "kitty-specs" / "069-unreviewed"
        feature_dir.mkdir(parents=True)
        append_event(
            feature_dir,
            _make_event(
                event_id="01A",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T10:00:00Z",
            ),
        )

        lookup = event_sourced_review_result(feature_dir, "WP01")

        assert lookup == ReviewResultLookup(slot_present=False, result=None)

    def test_event_sourced_review_result_coord_primary_partition_slot_absent(self, tmp_path: Path) -> None:
        """T027 DoD (#3220 fold): a coord-topology mission's PRIMARY-partition
        checkout has no reduced entry for a WP whose lane transitions live on
        the coordination branch instead -- slot-absent, the un-migrated shape
        T027 exists to handle. The reader is never gated on ``status_phase``;
        the synthetic ``meta.json`` below omits it only to preserve that
        framing, matching :func:`test_event_sourced_review_result_never_reviewed_wp_slot_absent`'s
        pattern.

        Landing-pass fold, #3220: this test used to read this repository's
        OWN, live, un-migrated ``kitty-specs/review-cycle-verdict-seam-rebuild-01KZ2W7W/meta.json``
        as a "not only a synthetic one" fixture. That mission was later
        migrated (it now carries a ``status_phase`` key), so the live
        precondition silently stopped holding and the test went red for a
        reason unrelated to the reader it exists to cover. The synthetic
        fixture here reproduces the same shape deterministically: a WP that
        was created and moved through a lane transition (so it is not simply
        absent from history) but has no reduced entry in THIS checkout's own
        event log, exactly what a coord-topology mission's primary partition
        looks like for a WP whose authoritative transitions live on the
        coordination branch.
        """
        feature_dir = tmp_path / "kitty-specs" / "069-coord-primary"
        feature_dir.mkdir(parents=True)
        meta_path = feature_dir / "meta.json"
        meta = {"mission_slug": "069-coord-primary", "topology": "coord"}
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        assert "status_phase" not in meta

        append_event(
            feature_dir,
            _make_event(
                event_id="01A",
                wp_id="WP07",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T10:00:00Z",
            ),
        )

        lookup = event_sourced_review_result(feature_dir, "WP99")

        # WP99 never appears in this checkout's event log at all -- the
        # coord-primary shape: its authoritative status.events.jsonl lives on
        # the coordination branch, not here, so this checkout's own reduced
        # snapshot has no entry for it. Slot-absent, and NOT gated on the
        # (absent) status_phase key above.
        assert lookup == ReviewResultLookup(slot_present=False, result=None)

    def test_event_sourced_review_result_fails_closed_on_corrupted_event_log(self, tmp_path: Path) -> None:
        """T027: an unreadable event log must not crash the reader — fail-closed
        to slot-absent, consistent with the module's declared polarity."""
        feature_dir = tmp_path / "kitty-specs" / "069-corrupted"
        feature_dir.mkdir(parents=True)
        (feature_dir / "status.events.jsonl").write_text("{not valid json\n", encoding="utf-8")

        lookup = event_sourced_review_result(feature_dir, "WP01")

        assert lookup == ReviewResultLookup(slot_present=False, result=None)


def _append_mission_events(mission: MissionFixture, events: list[StatusEvent]) -> None:
    """Re-stamp each event's mission identity onto ``mission`` and append it.

    ``_in_review_exit_events``/``_make_event`` default to a fixed
    ``mission_slug`` for the plain-reducer tests above; the gate-level tests
    below need each event to carry the SAME fixture mission's identity so
    ``find_rejected_review_artifact_conflicts``' partition resolution (keyed
    off ``feature_dir.name``) matches. Centralizing the re-stamp here (rather
    than repeating the ``StatusEvent(...)`` reconstruction per test) is the
    Sonar S1192 response for this module.
    """
    for event in events:
        append_event(
            mission.mission_dir,
            StatusEvent(
                event_id=event.event_id,
                mission_slug=mission.mission_slug,
                mission_id=mission.mission_id,
                wp_id=event.wp_id,
                from_lane=event.from_lane,
                to_lane=event.to_lane,
                at=event.at,
                actor=event.actor,
                force=event.force,
                execution_mode=event.execution_mode,
                reason=event.reason,
                review_result=event.review_result,
            ),
        )


class TestFindRejectedReviewArtifactConflictsEventSourced:
    """T029 (WP07) — the merge/lane gate consults the event-sourced answer too,
    with the event winning on disagreement (FR-001)."""

    def test_event_approved_overrides_frontmatter_rejected(self, tmp_path: Path) -> None:
        mission = create_mission_fixture(tmp_path, mission_slug="034-verdict-seam")
        write_work_package(mission, WorkPackageSpec(lane="approved"))
        rr = ReviewResult(
            reviewer="reviewer-a",
            verdict="approved",
            reference="review-cycle://034-verdict-seam/WP01/review-cycle-2.md",
        )
        _append_mission_events(mission, _in_review_exit_events(review_result=rr, target=Lane.APPROVED))
        artifact_dir = mission.tasks_dir / "WP01-regression-harness"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        _write_review_cycle_artifact(
            artifact_dir,
            wp_id="WP01",
            mission_slug=mission.mission_slug,
            cycle_number=2,
            verdict="rejected",
        )

        findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

        assert findings == []

    def test_event_changes_requested_overrides_frontmatter_approved(self, tmp_path: Path) -> None:
        """The reverse disagreement (T029): event says changes_requested, the
        frontmatter's latest artifact reads approved -- the gate refuses."""
        mission = create_mission_fixture(tmp_path, mission_slug="034-verdict-seam")
        write_work_package(mission, WorkPackageSpec(lane="approved"))
        rr = ReviewResult(
            reviewer="reviewer-a",
            verdict="changes_requested",
            reference="feedback://034-verdict-seam/WP01/review-cycle-2.md",
        )
        _append_mission_events(mission, _in_review_exit_events(review_result=rr, target=Lane.APPROVED))
        artifact_dir = mission.tasks_dir / "WP01-regression-harness"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        _write_review_cycle_artifact(
            artifact_dir,
            wp_id="WP01",
            mission_slug=mission.mission_slug,
            cycle_number=2,
            verdict="approved",
        )

        findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

        assert len(findings) == 1
        assert findings[0].wp_id == "WP01"
        assert findings[0].verdict == "changes_requested"

    def test_forced_null_review_result_yields_no_findings(self, tmp_path: Path) -> None:
        """T028's edge case, at the gate -- REPOINTED by WP05
        (verdict-seam-write-unification-01KZ9Q35, T028/FR-013/D-PLAN-8): a
        forced transition with no ``ReviewResult`` used to defer to the
        gate's (then-active) frontmatter-based check. That check is now
        retired outright: the pure-event gate never reads
        ``review-cycle-N.md`` frontmatter at all, and G2
        (contracts/verdict-authority-read.md) requires a damaged/absent
        event slot to read as "no block", never a fabricated rejection
        sourced from frontmatter. A rejected on-disk artifact is still
        written here to prove it is genuinely never consulted -- if it
        were, this test would fail the OTHER way (a spurious finding)."""
        mission = create_mission_fixture(tmp_path, mission_slug="034-verdict-seam")
        write_work_package(mission, WorkPackageSpec(lane="approved"))
        _append_mission_events(
            mission,
            _in_review_exit_events(review_result=None, target=Lane.APPROVED, force=True, reason="forced, no review"),
        )
        artifact_dir = mission.tasks_dir / "WP01-regression-harness"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        _write_review_cycle_artifact(
            artifact_dir,
            wp_id="WP01",
            mission_slug=mission.mission_slug,
            cycle_number=2,
            verdict="rejected",
        )

        findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

        assert findings == [], (
            "G2: a damaged (slot-present, result=None) event-sourced verdict "
            "must never fall back to reading frontmatter -- fail-closed-safe "
            "means 'no block', not a fabricated rejection"
        )

    def test_absent_event_sourced_verdict_yields_no_findings(self, tmp_path: Path) -> None:
        """REPOINTED by WP05 (verdict-seam-write-unification-01KZ9Q35,
        T028/FR-013/D-PLAN-8): this pinned the pre-existing
        frontmatter-only fallback path (T027's slot-absent case). That
        fallback is now retired -- the pure-event gate never reads
        ``review-cycle-N.md`` frontmatter, so a WP with no ``review_result``
        ever emitted produces NO finding, regardless of what a stray
        on-disk artifact says (G2: absent means 'no block')."""
        mission = create_mission_fixture(tmp_path, mission_slug="034-verdict-seam")
        write_work_package(mission, WorkPackageSpec(lane="approved"))
        append_event(
            mission.mission_dir,
            StatusEvent(
                event_id="01KQKV85APPROVED000000001",
                mission_slug=mission.mission_slug,
                mission_id=mission.mission_id,
                wp_id="WP01",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.APPROVED,
                at="2026-02-08T12:00:00Z",
                actor="reviewer-a",
                force=False,
                execution_mode="worktree",
            ),
        )
        artifact_dir = mission.tasks_dir / "WP01-regression-harness"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        _write_review_cycle_artifact(
            artifact_dir,
            wp_id="WP01",
            mission_slug=mission.mission_slug,
            cycle_number=2,
            verdict="rejected",
        )

        findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

        assert findings == [], "G2: an absent event-sourced verdict must never fall back to reading frontmatter -- fail-closed-safe means 'no block'"

    def test_arbiter_override_clears_gate_over_changes_requested_review_result(self, tmp_path: Path) -> None:
        """T026's precedence rule, exercised at the gate: an arbiter override
        clears the gate over a ``review_result`` of ``changes_requested`` --
        without erasing that ``review_result`` value (asserted separately via
        the reducer-level ``TestReviewResultPrecedence`` above)."""
        mission = create_mission_fixture(tmp_path, mission_slug="034-verdict-seam")
        write_work_package(mission, WorkPackageSpec(lane="approved"))
        rr = ReviewResult(
            reviewer="reviewer-a",
            verdict="changes_requested",
            reference="feedback://034-verdict-seam/WP01/review-cycle-2.md",
        )
        _append_mission_events(mission, _in_review_exit_events(review_result=rr, target=Lane.APPROVED))
        override = ReviewOverride(at="2026-02-08T13:00:00Z", actor="arbiter-a", wp_id="WP01", reason="ship anyway")
        append_annotations_atomic_verified(
            mission.mission_dir,
            [
                InnerStateChanged(
                    event_id="01HXYZ000000000000000000C1",
                    wp_id="WP01",
                    at="2026-02-08T13:00:00Z",
                    actor="arbiter-a",
                    delta=WPInnerStateDelta(review=override),
                )
            ],
        )
        artifact_dir = mission.tasks_dir / "WP01-regression-harness"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        _write_review_cycle_artifact(
            artifact_dir,
            wp_id="WP01",
            mission_slug=mission.mission_slug,
            cycle_number=2,
            verdict="rejected",
        )

        findings = find_rejected_review_artifact_conflicts(mission.mission_dir)

        assert findings == []
