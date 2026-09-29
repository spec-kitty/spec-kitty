"""In-memory event replay must preserve the canonical status snapshot."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.retrospective.events import CompletedPayload, emit_retrospective_event
from specify_cli.retrospective.schema import ActorRef
from specify_cli.status import (
    InnerStateChanged,
    Lane,
    ReviewOverride,
    StatusEvent,
    WPInnerStateDelta,
    materialize_snapshot_from_text,
    materialize_to_json,
    read_event_stream_from_text,
)
from specify_cli.status.store import StoreError, append_annotations_atomic_verified, append_event
from tests.reliability.fixtures import create_mission_fixture

pytestmark = [pytest.mark.fast]


def test_text_replay_matches_current_snapshot_with_legacy_id_annotation_and_retrospective(tmp_path: Path) -> None:
    """Replay preserves schema, legacy identity, annotations, and retrospective projection."""
    mission = create_mission_fixture(tmp_path, mission_slug="5151-handoff-provenance")
    append_event(
        mission.mission_dir,
        StatusEvent(
            event_id="01HXYZ0000000000000000000A",
            mission_slug=mission.mission_slug,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-09-28T12:00:00+00:00",
            actor="impl-alice",
            force=False,
            execution_mode="worktree",
            policy_metadata={"agent": "impl-alice"},
        ),
    )
    append_annotations_atomic_verified(
        mission.mission_dir,
        [
            InnerStateChanged(
                event_id="01HXYZ0000000000000000000B",
                wp_id="WP01",
                at="2026-09-28T12:01:00+00:00",
                actor="reviewer-renata",
                delta=WPInnerStateDelta(
                    review=ReviewOverride(
                        at="2026-09-28T12:01:00+00:00",
                        actor="reviewer-renata",
                        wp_id="WP01",
                        reason="fixture override",
                    )
                ),
            )
        ],
    )
    emit_retrospective_event(
        feature_dir=mission.mission_dir,
        mission_slug=mission.mission_slug,
        mission_id=mission.mission_id,
        mid8=mission.mission_id[:8],
        actor=ActorRef(kind="human", id="test-runner"),
        event_name="retrospective.completed",
        payload=CompletedPayload(
            record_path="retrospectives/5151-handoff-provenance.md",
            record_hash="a" * 64,
            findings_summary={"helped": 1, "not_helpful": 0, "gaps": 0},
            proposals_count=0,
        ),
    )

    expected_status = mission.status_snapshot_path.read_bytes()
    events_text = mission.status_events_path.read_text(encoding="utf-8")
    replay_dir = tmp_path / "detached-replay-root"
    replay_dir.mkdir()
    (replay_dir / "meta.json").write_bytes((mission.mission_dir / "meta.json").read_bytes())
    (replay_dir / "status.json").write_bytes(expected_status)

    stream = read_event_stream_from_text(
        replay_dir,
        events_text,
        mission_ids_by_slug={mission.mission_slug: mission.mission_id},
    )
    assert stream.transitions[0].mission_id == mission.mission_id
    assert len(stream.annotations) == 1

    replayed = materialize_snapshot_from_text(replay_dir, events_text, mission_slug=mission.mission_slug)
    disambiguated_slug = f"{mission.mission_slug}-{mission.mission_id[:8]}"
    disambiguated_stream = read_event_stream_from_text(
        replay_dir,
        events_text,
        mission_ids_by_slug={mission.mission_slug: mission.mission_id, disambiguated_slug: mission.mission_id},
    )
    assert disambiguated_stream.transitions[0].mission_id == mission.mission_id
    disambiguated_replay = materialize_snapshot_from_text(
        replay_dir,
        events_text,
        mission_slug=disambiguated_slug,
    )
    assert materialize_to_json(replayed).encode("utf-8") == expected_status
    assert materialize_to_json(disambiguated_replay).encode("utf-8") == expected_status
    assert replayed.schema_version == 2
    assert replayed.work_packages["WP01"]["review"]["reason"] == "fixture override"
    assert replayed.retrospective is not None
    assert replayed.retrospective.status == "completed"


def test_text_replay_unknown_legacy_slug_does_not_read_unrelated_metadata(tmp_path: Path) -> None:
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    event_text = json.dumps(
        {
            "event_id": "01HXYZ0000000000000000000A",
            "mission_slug": "other-mission",
            "wp_id": "WP01",
            "from_lane": "planned",
            "to_lane": "claimed",
            "at": "2026-09-28T12:00:00+00:00",
            "actor": "impl-alice",
            "force": False,
            "execution_mode": "worktree",
        }
    )
    unrelated_meta = tmp_path / "other-mission" / "meta.json"
    unrelated_meta.parent.mkdir()
    unrelated_meta.write_text('{"mission_id":"01KQKV85RELIABILITY000000000"}', encoding="utf-8")

    stream = read_event_stream_from_text(
        replay_dir,
        event_text,
        mission_ids_by_slug={"requested-mission": "01KQKV85RELIABILITY000000000"},
    )

    assert stream.transitions[0].mission_id is None


def test_text_replay_rejects_metadata_for_another_valid_slug(tmp_path: Path) -> None:
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    (replay_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KQKV85RELIABILITY000000000",
                "mission_slug": "other-valid-mission",
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )
    (replay_dir / "status.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match the requested status replay slug"):
        materialize_snapshot_from_text(replay_dir, "", mission_slug="requested-mission")


def test_text_replay_rejects_a_divergent_mid8_directory_slug(tmp_path: Path) -> None:
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    (replay_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01KQKV85RELIABILITY000000000",
                "mission_slug": "requested-mission",
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )
    (replay_dir / "status.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="does not match the requested status replay slug"):
        materialize_snapshot_from_text(
            replay_dir,
            "",
            mission_slug="requested-mission-01KQKV86",
        )


def test_text_replay_rejects_invalid_json(tmp_path: Path) -> None:
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    (replay_dir / "meta.json").write_text("{}", encoding="utf-8")
    (replay_dir / "status.json").write_text("{}", encoding="utf-8")

    with pytest.raises(StoreError, match="Invalid JSON on line 1"):
        materialize_snapshot_from_text(replay_dir, "{not json", mission_slug="requested-mission")
