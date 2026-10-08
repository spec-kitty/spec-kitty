"""Tests for RetrospectiveSnapshot reducer integration (T013).

Verifies:
- RetrospectiveSnapshot.status == "absent" when no retro events.
- Counts derived correctly from proposal.* events.
- Retry semantics: second retrospective.completed becomes active snapshot;
  prior completed still exists in the log (append-only invariant).
- mode sourced from the most recent retrospective.requested event.
- record_path sourced from the most recent terminal event payload.
- emit_retrospective_event writes an append-only line to status.events.jsonl.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.retrospective.events import (
    CompletedPayload,
    ProposalAppliedPayload,
    ProposalRejectedPayload,
    RequestedPayload,
    StartedPayload,
    emit_retrospective_event,
)
from specify_cli.retrospective.schema import ActorRef, Mode, ModeSourceSignal
from specify_cli.status.models import RetrospectiveSnapshot, StatusSnapshot
from specify_cli.status.reducer import _reduce_retrospective, materialize
from specify_cli.status.store import read_events_raw

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RUNTIME_ACTOR = ActorRef(kind="runtime", id="spec-kitty-runtime", profile_id=None)
_HUMAN_ACTOR = ActorRef(kind="human", id="operator-01", profile_id=None)

_MODE_AUTO = Mode(
    value="autonomous",
    source_signal=ModeSourceSignal(kind="environment", evidence="SK_MODE=autonomous"),
)
_MODE_HIC = Mode(
    value="human_in_command",
    source_signal=ModeSourceSignal(kind="explicit_flag", evidence="--mode=hic"),
)

_MISSION_ID = "01KQ73CS2CCFY8BYYTTFV58FJT"
_MID8 = "01KQ73CS"
_MISSION_SLUG = "mission-test-retro-01KQ73CS"


def _write_raw_event(feature_dir: Path, event: dict) -> None:
    """Write a raw retrospective event directly to status.events.jsonl."""
    events_path = feature_dir / "status.events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True)
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _make_retro_event(
    event_name: str,
    payload: dict,
    at: str = "2026-04-27T10:00:00+00:00",
    event_id: str = "01KQ73CS2CCFY8BYYTTFV58FJT",
) -> dict:
    return {
        "actor": {"id": "spec-kitty-runtime", "kind": "runtime", "profile_id": None},
        "at": at,
        "event_id": event_id,
        "event_name": event_name,
        "mid8": _MID8,
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "payload": payload,
    }


# ---------------------------------------------------------------------------
# _reduce_retrospective unit tests
# ---------------------------------------------------------------------------


class TestReduceRetrospectiveAbsent:
    def test_absent_when_no_events(self) -> None:
        result = _reduce_retrospective([])
        assert result.status == "absent"

    def test_absent_when_only_lane_events(self) -> None:
        # Lane events have no event_name field
        lane_event = {
            "actor": "claude",
            "at": "2026-04-27T09:00:00+00:00",
            "event_id": "01KQ73CS2CCFY8BYYTTFV00001",
            "from_lane": "planned",
            "to_lane": "claimed",
            "wp_id": "WP01",
            "mission_slug": _MISSION_SLUG,
            "force": False,
            "execution_mode": "worktree",
        }
        result = _reduce_retrospective([lane_event])
        assert result.status == "absent"


class TestReduceRetrospectivePending:
    def test_pending_after_requested(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.requested",
                {
                    "mode": _MODE_AUTO.model_dump(mode="json"),
                    "terminus_step_id": "step-final",
                    "requested_by": _RUNTIME_ACTOR.model_dump(mode="json"),
                },
            )
        ]
        result = _reduce_retrospective(events)
        assert result.status == "pending"

    def test_pending_after_started(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.requested",
                {
                    "mode": _MODE_AUTO.model_dump(mode="json"),
                    "terminus_step_id": "step-final",
                    "requested_by": _RUNTIME_ACTOR.model_dump(mode="json"),
                },
                at="2026-04-27T10:00:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58001",
            ),
            _make_retro_event(
                "retrospective.started",
                {"facilitator_profile_id": "retrospective-facilitator", "action_id": "retrospect"},
                at="2026-04-27T10:01:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58002",
            ),
        ]
        result = _reduce_retrospective(events)
        assert result.status == "pending"


class TestReduceRetrospectiveCompleted:
    def test_completed_status(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.completed",
                {
                    "record_path": "/retro.yaml",
                    "record_hash": "abc123",
                    "findings_summary": {"helped": 2, "not_helpful": 1, "gaps": 0},
                    "proposals_count": 3,
                },
            )
        ]
        result = _reduce_retrospective(events)
        assert result.status == "completed"
        assert result.record_path == "/retro.yaml"

    def test_skipped_status(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.skipped",
                {
                    "record_path": "/skip.yaml",
                    "skip_reason": "Not needed this sprint",
                    "skipped_by": _HUMAN_ACTOR.model_dump(mode="json"),
                },
            )
        ]
        result = _reduce_retrospective(events)
        assert result.status == "skipped"
        assert result.record_path == "/skip.yaml"

    def test_failed_status(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.failed",
                {"failure_code": "internal_error", "message": "err", "record_path": None},
            )
        ]
        result = _reduce_retrospective(events)
        assert result.status == "failed"
        assert result.record_path is None


class TestReduceRetrospectiveRetrySemantics:
    """Verify that a second terminal event becomes the active snapshot.

    The append-only invariant: prior events remain in the log untouched.
    """

    def test_second_completed_wins(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.completed",
                {
                    "record_path": "/retro-v1.yaml",
                    "record_hash": "hash1",
                    "findings_summary": {"helped": 1, "not_helpful": 0, "gaps": 0},
                    "proposals_count": 1,
                },
                at="2026-04-27T10:00:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58001",
            ),
            _make_retro_event(
                "retrospective.completed",
                {
                    "record_path": "/retro-v2.yaml",
                    "record_hash": "hash2",
                    "findings_summary": {"helped": 3, "not_helpful": 1, "gaps": 2},
                    "proposals_count": 4,
                },
                at="2026-04-27T11:00:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58002",
            ),
        ]
        result = _reduce_retrospective(events)
        # Latest completed wins
        assert result.status == "completed"
        assert result.record_path == "/retro-v2.yaml"

    def test_failed_then_completed_picks_latest_by_at(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.failed",
                {"failure_code": "internal_error", "message": "err", "record_path": None},
                at="2026-04-27T10:00:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58001",
            ),
            _make_retro_event(
                "retrospective.completed",
                {
                    "record_path": "/retro.yaml",
                    "record_hash": "abc",
                    "findings_summary": {},
                    "proposals_count": 0,
                },
                at="2026-04-27T11:00:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58002",
            ),
        ]
        result = _reduce_retrospective(events)
        assert result.status == "completed"
        assert result.record_path == "/retro.yaml"


class TestReduceRetrospectiveProposalCounts:
    def test_proposal_counts(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.completed",
                {
                    "record_path": "/retro.yaml",
                    "record_hash": "abc",
                    "findings_summary": {},
                    "proposals_count": 3,
                },
                at="2026-04-27T10:00:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58001",
            ),
            _make_retro_event(
                "retrospective.proposal.generated",
                {"proposal_id": "01KQ73CS2CCFY8BYYTTFV58P01", "kind": "synthesize_directive", "record_path": "/retro.yaml"},
                at="2026-04-27T10:01:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58002",
            ),
            _make_retro_event(
                "retrospective.proposal.generated",
                {"proposal_id": "01KQ73CS2CCFY8BYYTTFV58P02", "kind": "add_glossary_term", "record_path": "/retro.yaml"},
                at="2026-04-27T10:02:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58003",
            ),
            _make_retro_event(
                "retrospective.proposal.generated",
                {"proposal_id": "01KQ73CS2CCFY8BYYTTFV58P03", "kind": "rewire_edge", "record_path": "/retro.yaml"},
                at="2026-04-27T10:03:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58004",
            ),
            _make_retro_event(
                "retrospective.proposal.applied",
                {
                    "proposal_id": "01KQ73CS2CCFY8BYYTTFV58P01",
                    "kind": "synthesize_directive",
                    "target_urn": "doctrine:directive:d001",
                    "provenance_ref": "prov:urn:001",
                    "applied_by": _RUNTIME_ACTOR.model_dump(mode="json"),
                },
                at="2026-04-27T10:04:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58005",
            ),
            _make_retro_event(
                "retrospective.proposal.rejected",
                {
                    "proposal_id": "01KQ73CS2CCFY8BYYTTFV58P02",
                    "kind": "add_glossary_term",
                    "reason": "human_decline",
                    "detail": "Not relevant",
                    "rejected_by": _HUMAN_ACTOR.model_dump(mode="json"),
                },
                at="2026-04-27T10:05:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58006",
            ),
        ]
        result = _reduce_retrospective(events)
        assert result.proposals_total == 3
        assert result.proposals_applied == 1
        assert result.proposals_rejected == 1
        assert result.proposals_pending == 1  # 3 - 1 applied - 1 rejected

    def test_urn_doctrine_prefix_parsed_with_warning(self) -> None:
        """CR-05 (mission ``charter-code-topology-01M152G1`` S4): a
        ``retrospective.proposal.applied`` event carrying the legacy
        ``doctrine:<kind>:<id>`` ``target_urn`` -- the shape every event
        written before this mission's producer cutover durably carries --
        must keep reducing exactly as before. ``target_urn`` is an
        intentionally opaque, unconstrained string everywhere it is consumed
        (``ProposalAppliedPayload.target_urn: str`` -- no format/prefix
        validation, see ``specify_cli.retrospective.events``), so there is no
        runtime ``warnings.warn`` to observe here; "parsed with warning"
        names the operator-facing deprecation this CR records for the
        producer side (``charter_pack_synthesizer.apply``), not a reducer-side
        side effect. This test is the durable-event-log tolerance pin: the
        legacy prefix must never start failing to parse.
        """
        payload = ProposalAppliedPayload(
            proposal_id="01KQ73CS2CCFY8BYYTTFV58P09",
            kind="synthesize_directive",
            target_urn="doctrine:directive:d001",
            provenance_ref="prov:urn:001",
            applied_by=_RUNTIME_ACTOR,
        )
        events = [
            _make_retro_event(
                "retrospective.proposal.generated",
                {"proposal_id": "01KQ73CS2CCFY8BYYTTFV58P09", "kind": "synthesize_directive", "record_path": "/retro.yaml"},
                at="2026-04-27T10:01:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58011",
            ),
            _make_retro_event(
                "retrospective.proposal.applied",
                payload.model_dump(mode="json"),
                at="2026-04-27T10:02:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58012",
            ),
        ]
        result = _reduce_retrospective(events)
        assert result.proposals_total == 1
        assert result.proposals_applied == 1

    def test_urn_charter_prefix_canonical(self) -> None:
        """CR-05 counterpart: the canonical ``charter:<kind>:<id>``
        ``target_urn`` (what ``charter_pack_synthesizer.apply`` now emits for
        every newly-applied ``synthesize_*`` proposal) reduces identically
        to the legacy ``doctrine:`` form above -- proposal counting never
        keyed on the prefix, so canonicalizing the producer changes nothing
        about how the reducer sees it.
        """
        payload = ProposalAppliedPayload(
            proposal_id="01KQ73CS2CCFY8BYYTTFV58P0A",
            kind="synthesize_directive",
            target_urn="charter:directive:d002",
            provenance_ref="prov:urn:002",
            applied_by=_RUNTIME_ACTOR,
        )
        events = [
            _make_retro_event(
                "retrospective.proposal.generated",
                {"proposal_id": "01KQ73CS2CCFY8BYYTTFV58P0A", "kind": "synthesize_directive", "record_path": "/retro.yaml"},
                at="2026-04-27T10:01:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58013",
            ),
            _make_retro_event(
                "retrospective.proposal.applied",
                payload.model_dump(mode="json"),
                at="2026-04-27T10:02:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58014",
            ),
        ]
        result = _reduce_retrospective(events)
        assert result.proposals_total == 1
        assert result.proposals_applied == 1

    def test_zero_proposal_counts_when_none(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.completed",
                {
                    "record_path": "/retro.yaml",
                    "record_hash": "abc",
                    "findings_summary": {},
                    "proposals_count": 0,
                },
            )
        ]
        result = _reduce_retrospective(events)
        assert result.proposals_total == 0
        assert result.proposals_applied == 0
        assert result.proposals_rejected == 0
        assert result.proposals_pending == 0


class TestReduceRetrospectiveMode:
    def test_mode_from_requested_event(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.requested",
                {
                    "mode": _MODE_AUTO.model_dump(mode="json"),
                    "terminus_step_id": "step-final",
                    "requested_by": _RUNTIME_ACTOR.model_dump(mode="json"),
                },
            )
        ]
        result = _reduce_retrospective(events)
        assert result.mode is not None
        assert result.mode.value == "autonomous"

    def test_mode_from_latest_requested_event(self) -> None:
        """When there are multiple requested events, mode from the latest."""
        events = [
            _make_retro_event(
                "retrospective.requested",
                {
                    "mode": _MODE_AUTO.model_dump(mode="json"),
                    "terminus_step_id": "step-a",
                    "requested_by": _RUNTIME_ACTOR.model_dump(mode="json"),
                },
                at="2026-04-27T09:00:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58001",
            ),
            _make_retro_event(
                "retrospective.failed",
                {"failure_code": "internal_error", "message": "err", "record_path": None},
                at="2026-04-27T09:30:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58002",
            ),
            _make_retro_event(
                "retrospective.requested",
                {
                    "mode": _MODE_HIC.model_dump(mode="json"),
                    "terminus_step_id": "step-b",
                    "requested_by": _HUMAN_ACTOR.model_dump(mode="json"),
                },
                at="2026-04-27T10:00:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58003",
            ),
            _make_retro_event(
                "retrospective.completed",
                {
                    "record_path": "/retro.yaml",
                    "record_hash": "abc",
                    "findings_summary": {},
                    "proposals_count": 0,
                },
                at="2026-04-27T10:30:00+00:00",
                event_id="01KQ73CS2CCFY8BYYTTFV58004",
            ),
        ]
        result = _reduce_retrospective(events)
        # Mode from the later requested event (HiC)
        assert result.mode is not None
        assert result.mode.value == "human_in_command"
        assert result.status == "completed"

    def test_invalid_requested_mode_is_ignored(self) -> None:
        events = [
            _make_retro_event(
                "retrospective.requested",
                {
                    "mode": {"value": "bogus", "source_signal": {"kind": "environment"}},
                    "terminus_step_id": "step-final",
                    "requested_by": _RUNTIME_ACTOR.model_dump(mode="json"),
                },
            )
        ]

        result = _reduce_retrospective(events)

        assert result.status == "pending"
        assert result.mode is None


# ---------------------------------------------------------------------------
# emit_retrospective_event + append-only invariant
# ---------------------------------------------------------------------------


class TestEmitRetrospectiveEvent:
    def test_emit_appends_to_jsonl(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        event_id = emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.requested",
            payload=RequestedPayload(
                mode=_MODE_AUTO,
                terminus_step_id="step-final",
                requested_by=_RUNTIME_ACTOR,
            ),
        )

        events_path = feature_dir / "status.events.jsonl"
        assert events_path.exists()
        lines = events_path.read_text().strip().splitlines()
        assert len(lines) == 1

        obj = json.loads(lines[0])
        assert obj["event_id"] == event_id
        assert obj["event_name"] == "retrospective.requested"
        assert obj["mission_id"] == _MISSION_ID
        assert obj["mission_slug"] == _MISSION_SLUG

    def test_emit_returns_ulid(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        event_id = emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.started",
            payload=StartedPayload(
                facilitator_profile_id="retrospective-facilitator",
                action_id="retrospect",
            ),
        )
        assert len(event_id) == 26

    def test_emit_materializes_status_json(self, tmp_path: Path) -> None:
        """Retrospective emits refresh status.json so snapshots do not drift."""
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.proposal.applied",
            payload=ProposalAppliedPayload(
                proposal_id="RP-001",
                kind="add_glossary_term",
                target_urn="glossary:term",
                provenance_ref=".kittify/glossary/.provenance/workflow_probe.yaml",
                applied_by=_RUNTIME_ACTOR,
            ),
        )

        status_path = feature_dir / "status.json"
        assert status_path.exists()
        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status["retrospective"]["proposals_applied"] == 1

    def test_emit_materializes_rejected_proposal_status_json(self, tmp_path: Path) -> None:
        """Conflict rejection events also refresh the derived retrospective snapshot."""
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.proposal.rejected",
            payload=ProposalRejectedPayload(
                proposal_id="RP-002",
                kind="add_glossary_term",
                reason="conflict",
                detail="target already changed",
                rejected_by=_RUNTIME_ACTOR,
            ),
        )

        status_path = feature_dir / "status.json"
        status = json.loads(status_path.read_text(encoding="utf-8"))
        assert status["retrospective"]["proposals_rejected"] == 1

    def test_emit_keeps_appended_event_when_materialization_fails(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The event log is authoritative; status.json refresh failure must not roll it back."""
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        def fail_materialize(feature_dir: Path) -> None:
            raise RuntimeError(f"cannot materialize {feature_dir.name}")

        # emit_retrospective_event resolves materialize through the status facade
        # (`from specify_cli.status import materialize`), so patch the facade name
        # it actually looks up — patching the reducer submodule would not be seen.
        monkeypatch.setattr("specify_cli.status.materialize", fail_materialize)

        with caplog.at_level("WARNING", logger="specify_cli.retrospective.events"):
            event_id = emit_retrospective_event(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                mission_id=_MISSION_ID,
                mid8=_MID8,
                actor=_RUNTIME_ACTOR,
                event_name="retrospective.proposal.applied",
                payload=ProposalAppliedPayload(
                    proposal_id="RP-001",
                    kind="add_glossary_term",
                    target_urn="glossary:term",
                    provenance_ref=".kittify/glossary/.provenance/workflow_probe.yaml",
                    applied_by=_RUNTIME_ACTOR,
                ),
            )

        events_path = feature_dir / "status.events.jsonl"
        events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines()]
        assert [event["event_id"] for event in events] == [event_id]
        assert not (feature_dir / "status.json").exists()
        assert "was appended, but status.json materialization failed" in caplog.text

    def test_emit_rejects_unknown_event_name(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        with pytest.raises(ValueError, match="Unknown retrospective event name"):
            emit_retrospective_event(
                feature_dir=feature_dir,
                mission_slug=_MISSION_SLUG,
                mission_id=_MISSION_ID,
                mid8=_MID8,
                actor=_RUNTIME_ACTOR,
                event_name="retrospective.nonexistent",
                payload=StartedPayload(
                    facilitator_profile_id="fp",
                    action_id="a",
                ),
            )

    def test_append_only_invariant(self, tmp_path: Path) -> None:
        """A second emit appends; does not overwrite existing lines."""
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        first_id = emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.completed",
            payload=CompletedPayload(
                record_path="/retro-v1.yaml",
                record_hash="hash1",
                findings_summary={"helped": 1, "not_helpful": 0, "gaps": 0},
                proposals_count=0,
            ),
        )

        second_id = emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.completed",
            payload=CompletedPayload(
                record_path="/retro-v2.yaml",
                record_hash="hash2",
                findings_summary={"helped": 3, "not_helpful": 0, "gaps": 1},
                proposals_count=2,
            ),
        )

        events_path = feature_dir / "status.events.jsonl"
        lines = events_path.read_text().strip().splitlines()

        # Both events must be present (append-only)
        assert len(lines) == 2
        ids = [json.loads(line)["event_id"] for line in lines]
        assert first_id in ids
        assert second_id in ids

    def test_sorted_keys_in_output(self, tmp_path: Path) -> None:
        """Emitted JSON lines must have sorted keys."""
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.started",
            payload=StartedPayload(
                facilitator_profile_id="fp",
                action_id="retrospect",
            ),
        )

        events_path = feature_dir / "status.events.jsonl"
        raw_line = events_path.read_text().strip()
        obj = json.loads(raw_line)
        keys = list(obj.keys())
        assert keys == sorted(keys), f"Keys not sorted: {keys}"


# ---------------------------------------------------------------------------
# StatusSnapshot.retrospective additive integration
# ---------------------------------------------------------------------------


class TestStatusSnapshotRetrospectiveField:
    def test_retrospective_absent_by_default(self, tmp_path: Path) -> None:
        """When no retrospective events exist, snapshot.retrospective is None."""
        from specify_cli.status.store import append_event
        from specify_cli.status.models import Lane, StatusEvent

        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        # Write a regular lane event
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01KQ73CS2CCFY8BYYTTFV58001",
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-04-27T09:00:00+00:00",
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )

        raw_events = read_events_raw(feature_dir)
        retro = _reduce_retrospective(raw_events)
        assert retro.status == "absent"

    def test_retrospective_reflects_completed(self, tmp_path: Path) -> None:
        """After a completed event, snapshot.retrospective.status == 'completed'."""
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.completed",
            payload=CompletedPayload(
                record_path="/retro.yaml",
                record_hash="abc",
                findings_summary={"helped": 1, "not_helpful": 0, "gaps": 0},
                proposals_count=1,
            ),
        )

        raw_events = read_events_raw(feature_dir)
        retro = _reduce_retrospective(raw_events)
        assert retro.status == "completed"
        assert retro.record_path == "/retro.yaml"

    def test_retry_semantics_second_completed_wins(self, tmp_path: Path) -> None:
        """Second retrospective.completed event becomes active; prior stays in log."""
        feature_dir = tmp_path / "kitty-specs" / "test-mission"
        feature_dir.mkdir(parents=True)

        first_id = emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.completed",
            payload=CompletedPayload(
                record_path="/retro-v1.yaml",
                record_hash="hash1",
                findings_summary={},
                proposals_count=0,
            ),
        )

        second_id = emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.completed",
            payload=CompletedPayload(
                record_path="/retro-v2.yaml",
                record_hash="hash2",
                findings_summary={},
                proposals_count=0,
            ),
        )

        raw_events = read_events_raw(feature_dir)
        retro = _reduce_retrospective(raw_events)

        # Latest completed wins as active snapshot
        assert retro.status == "completed"
        assert retro.record_path == "/retro-v2.yaml"

        # But both events still exist in the log (append-only invariant)
        event_ids = [e["event_id"] for e in raw_events if "event_name" in e]
        assert first_id in event_ids
        assert second_id in event_ids
        assert len(event_ids) == 2

    def test_status_snapshot_round_trips_retrospective(self) -> None:
        snap = StatusSnapshot(
            mission_slug=_MISSION_SLUG,
            materialized_at="2026-04-27T10:00:00+00:00",
            event_count=1,
            last_event_id="01KQ73CS2CCFY8BYYTTFV58001",
            work_packages={},
            summary={},
            retrospective=RetrospectiveSnapshot(
                status="completed",
                mode=_MODE_AUTO,
                record_path="/retro.yaml",
                proposals_total=2,
                proposals_applied=1,
                proposals_rejected=0,
                proposals_pending=1,
            ),
        )

        data = snap.to_dict()
        loaded = StatusSnapshot.from_dict(data)

        assert data["retrospective"]["status"] == "completed"
        assert loaded.retrospective is not None
        assert loaded.retrospective.status == "completed"
        assert loaded.retrospective.mode is not None
        assert loaded.retrospective.mode.value == "autonomous"

    def test_materialize_attaches_non_absent_retrospective_snapshot(self, tmp_path: Path) -> None:
        from specify_cli.status.models import Lane, StatusEvent
        from specify_cli.status.store import append_event

        feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": _MISSION_ID,
                    "mission_slug": _MISSION_SLUG,
                    "mission_type": "software-dev",
                }
            ),
            encoding="utf-8",
        )
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01KQ73CS2CCFY8BYYTTFV58001",
                mission_slug=_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.DONE,
                at="2026-04-27T09:00:00+00:00",
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )
        emit_retrospective_event(
            feature_dir=feature_dir,
            mission_slug=_MISSION_SLUG,
            mission_id=_MISSION_ID,
            mid8=_MID8,
            actor=_RUNTIME_ACTOR,
            event_name="retrospective.completed",
            payload=CompletedPayload(
                record_path="/retro.yaml",
                record_hash="abc",
                findings_summary={},
                proposals_count=0,
            ),
        )

        snapshot = materialize(feature_dir)

        assert snapshot.retrospective is not None
        assert snapshot.retrospective.status == "completed"
        assert snapshot.retrospective.record_path == "/retro.yaml"


class TestRetrospectiveSnapshotModel:
    def test_default_values(self) -> None:
        snap = RetrospectiveSnapshot(status="absent")
        assert snap.mode is None
        assert snap.record_path is None
        assert snap.proposals_total == 0
        assert snap.proposals_applied == 0
        assert snap.proposals_rejected == 0
        assert snap.proposals_pending == 0

    def test_model_dump_json(self) -> None:
        snap = RetrospectiveSnapshot(status="completed", proposals_total=3, proposals_applied=1, proposals_rejected=1, proposals_pending=1)
        d = snap.model_dump(mode="json")
        assert d["status"] == "completed"
        assert d["proposals_total"] == 3
