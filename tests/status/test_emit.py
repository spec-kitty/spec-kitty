"""Tests for the status emit orchestration pipeline.

Covers the full emit_status_transition pipeline, _saas_fan_out,
TransitionError, force transitions, done-evidence contracts,
alias resolution, and pipeline ordering guarantees.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import specify_cli.status.emit as emit_module
import specify_cli.status.transition_pipeline as _pipeline_module
from specify_cli.frontmatter import FrontmatterError
from specify_cli.status import adapters
from specify_cli.status.wp_metadata import WPMetadata
from specify_cli.status.emit import (
    TransitionError,
    _build_done_evidence,
    _derive_from_lane,
    _find_wp_file,
    _legacy_alias_collapses_to_current_lane,
    _legacy_lane_mirror_enabled,
    _load_mission_id,
    _mirror_phase1_frontmatter_lane,
    _saas_fan_out,
    emit_status_transition,
    emit_status_transition_batch,
)
from specify_cli.status.models import (
    DoneEvidence,
    Lane,
    ReviewResult,
    StatusEvent,
    TransitionRequest,
    WPInnerStateDelta,
)
from specify_cli.status.store import EVENTS_FILENAME, append_event, read_event_stream, read_events

from tests.status.conftest import seed_wp_to_planned as _seed_planned

pytestmark = pytest.mark.fast
# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    """Create a minimal feature directory for tests."""
    fd = tmp_path / "kitty-specs" / "034-test-feature"
    fd.mkdir(parents=True)
    return fd


@pytest.fixture
def valid_evidence_dict() -> dict:
    """A valid evidence dict for done transitions."""
    return {
        "review": {
            "reviewer": "reviewer-1",
            "verdict": "approved",
            "reference": "PR#42",
        },
        "repos": [
            {
                "repo": "org/repo",
                "branch": "feature-branch",
                "commit": "abc1234",
            }
        ],
        "verification": [
            {
                "command": "pytest tests/ -x",
                "result": "pass",
                "summary": "10 tests passed",
            }
        ],
    }


# ── _derive_from_lane ────────────────────────────────────────


class TestDeriveFromLane:
    """Tests for _derive_from_lane helper."""

    def test_no_events_returns_genesis(self, feature_dir: Path):
        """First WP with no lane-state events derives 'genesis' (pre-finalize)."""
        result = _derive_from_lane(feature_dir, "WP01")
        assert result == "genesis"

    def test_returns_last_to_lane_for_wp(self, feature_dir: Path):
        """Derives from_lane from the last event's to_lane for the WP."""
        event = StatusEvent(
            event_id="01HXYZ0000000000000000TEST",
            mission_slug="034-test-feature",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
            actor="test-actor",
            force=False,
            execution_mode="worktree",
        )
        from specify_cli.status.store import append_event

        append_event(feature_dir, event)

        result = _derive_from_lane(feature_dir, "WP01")
        assert result == "claimed"

    def test_filters_by_wp_id(self, feature_dir: Path):
        """Only considers events for the specified WP."""
        from specify_cli.status.store import append_event

        event_wp01 = StatusEvent(
            event_id="01HXYZ0000000000000000TST1",
            mission_slug="034-test-feature",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
            actor="test-actor",
            force=False,
            execution_mode="worktree",
        )
        event_wp02 = StatusEvent(
            event_id="01HXYZ0000000000000000TST2",
            mission_slug="034-test-feature",
            wp_id="WP02",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:01:00Z",
            actor="test-actor",
            force=False,
            execution_mode="worktree",
        )
        append_event(feature_dir, event_wp01)
        append_event(feature_dir, event_wp02)

        result = _derive_from_lane(feature_dir, "WP01")
        assert result == "claimed"

    def test_unknown_wp_returns_genesis(self, feature_dir: Path):
        """WP with no events in existing log derives 'genesis' (pre-finalize)."""
        from specify_cli.status.store import append_event

        event = StatusEvent(
            event_id="01HXYZ0000000000000000TST3",
            mission_slug="034-test-feature",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-02-08T12:00:00Z",
            actor="test-actor",
            force=False,
            execution_mode="worktree",
        )
        append_event(feature_dir, event)

        result = _derive_from_lane(feature_dir, "WP99")
        assert result == "genesis"

    def test_uses_reduced_state_not_append_order(self, feature_dir: Path):
        """Derivation uses canonical reducer order when log lines are out of order."""
        from specify_cli.status.store import append_event

        # Write a later transition first, then an earlier one.
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01HXYZ0000000000000000OO02",
                mission_slug="034-test-feature",
                wp_id="WP01",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T13:00:00Z",
                actor="test-actor",
                force=False,
                execution_mode="worktree",
            ),
        )
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01HXYZ0000000000000000OO01",
                mission_slug="034-test-feature",
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.CLAIMED,
                at="2026-02-08T12:00:00Z",
                actor="test-actor",
                force=False,
                execution_mode="worktree",
            ),
        )

        result = _derive_from_lane(feature_dir, "WP01")
        assert result == "in_progress"


# ── _build_done_evidence ─────────────────────────────────────


class TestBuildDoneEvidence:
    """Tests for _build_done_evidence helper."""

    def test_valid_evidence(self, valid_evidence_dict: dict):
        """Builds DoneEvidence from a valid dict."""
        result = _build_done_evidence(valid_evidence_dict)
        assert isinstance(result, DoneEvidence)
        assert result.review.reviewer == "reviewer-1"
        assert result.review.verdict == "approved"
        assert result.review.reference == "PR#42"
        assert len(result.repos) == 1
        assert len(result.verification) == 1

    def test_missing_review_raises(self):
        """Missing 'review' key raises TransitionError."""
        with pytest.raises(TransitionError, match="review.reviewer"):
            _build_done_evidence({"repos": []})

    def test_review_not_dict_raises(self):
        """Non-dict 'review' value raises TransitionError."""
        with pytest.raises(TransitionError, match="review.reviewer"):
            _build_done_evidence({"review": "just a string"})

    def test_missing_reviewer_raises(self):
        """Missing reviewer in review raises TransitionError."""
        with pytest.raises(TransitionError, match="review.reviewer"):
            _build_done_evidence({"review": {"verdict": "approved"}})

    def test_missing_verdict_raises(self):
        """Missing verdict in review raises TransitionError."""
        with pytest.raises(TransitionError, match="review.reviewer"):
            _build_done_evidence({"review": {"reviewer": "rev"}})

    def test_missing_reference_raises(self):
        """Missing approval reference in review raises TransitionError."""
        with pytest.raises(TransitionError, match="review.reference"):
            _build_done_evidence({"review": {"reviewer": "rev", "verdict": "approved"}})

    def test_empty_reviewer_raises(self):
        """Empty reviewer string raises TransitionError."""
        with pytest.raises(TransitionError, match="review.reviewer"):
            _build_done_evidence({"review": {"reviewer": "", "verdict": "approved"}})

    def test_minimal_evidence_works(self):
        """Minimal evidence with required review fields succeeds."""
        result = _build_done_evidence(
            {
                "review": {
                    "reviewer": "rev",
                    "verdict": "approved",
                    "reference": "PR#1",
                }
            }
        )
        assert result.review.reviewer == "rev"
        assert result.review.reference == "PR#1"
        assert result.repos == []
        assert result.verification == []

    def test_extra_fields_accepted(self):
        """Extra fields in evidence dict are silently ignored."""
        result = _build_done_evidence(
            {
                "review": {
                    "reviewer": "rev",
                    "verdict": "approved",
                    "reference": "PR#2",
                },
                "extra_field": "should_be_ignored",
            }
        )
        assert result.review.reviewer == "rev"


# ── _load_mission_id ────────────────────────────────────────


class TestLoadMissionId:
    """Tests for tolerant mission_id reads from meta.json (on_malformed="none" contract).

    Both missing and malformed meta.json must return None — the converted
    site uses load_meta(allow_missing=True, on_malformed="none").
    """

    def test_malformed_meta_returns_none(self, feature_dir: Path) -> None:
        """Malformed meta.json degrades to None instead of raising."""
        (feature_dir / "meta.json").write_text("{bad json", encoding="utf-8")

        assert _load_mission_id(feature_dir) is None

    def test_missing_meta_returns_none(self, feature_dir: Path) -> None:
        """Missing meta.json degrades to None instead of raising FileNotFoundError."""
        assert not (feature_dir / "meta.json").exists()

        assert _load_mission_id(feature_dir) is None


# ── emit_status_transition ───────────────────────────────────


class TestEmitStatusTransition:
    """Tests for the main emit orchestration function."""

    def test_transition_request_rejects_mixed_legacy_args(self, feature_dir: Path):
        """TransitionRequest calls must not also pass legacy arguments."""
        request = TransitionRequest(
            feature_dir=feature_dir,
            mission_slug="034-test-feature",
            wp_id="WP01",
            to_lane="claimed",
            actor="claude-opus",
        )

        with pytest.raises(TypeError, match="either a TransitionRequest or legacy transition arguments"):
            emit_status_transition(request, wp_id="WP02")

    def test_happy_path_planned_to_claimed(self, feature_dir: Path):
        """Basic transition from planned to claimed persists and returns event."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="claude-opus",
            )
        )

        assert isinstance(event, StatusEvent)
        assert event.from_lane == Lane.PLANNED
        assert event.to_lane == Lane.CLAIMED
        assert event.wp_id == "WP01"
        assert event.mission_slug == "034-test-feature"
        assert event.actor == "claude-opus"
        assert event.force is False
        assert event.execution_mode == "worktree"
        assert len(event.event_id) == 26  # ULID length

        # Verify event is persisted (genesis->planned seed + planned->claimed)
        events = read_events(feature_dir)
        assert len(events) == 2
        assert events[-1].event_id == event.event_id

    def test_force_cannot_persist_genesis_as_target_lane(self, feature_dir: Path):
        """Genesis is a non-display seed source, never a persisted target lane."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")

        with pytest.raises(TransitionError, match="Illegal transition: planned -> genesis"):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="genesis",
                    actor="admin",
                    force=True,
                    reason="force regression",
                )
            )

        events = read_events(feature_dir)
        assert [(str(event.from_lane), str(event.to_lane)) for event in events] == [("genesis", "planned")]

    def test_snapshot_materialized(self, feature_dir: Path):
        """Snapshot file is written after successful emit."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="claude-opus",
            )
        )

        snapshot_path = feature_dir / "status.json"
        assert snapshot_path.exists()
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert data["work_packages"]["WP01"]["lane"] == "claimed"

    def test_transition_holds_feature_lock_through_canonical_mutation(
        self,
        feature_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Derive, append, and materialize must share the feature status lock."""
        # Seed out of genesis before installing the tracking spies so the
        # observed sequence reflects only the claimed transition under test.
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        lock_root = feature_dir.parent.parent
        lock_state = {"held": False}
        observed: list[str] = []

        @contextmanager
        def tracking_lock(repo_root: Path, mission_slug: str):  # type: ignore[no-untyped-def]
            assert repo_root == lock_root
            assert mission_slug == "034-test-feature"
            lock_state["held"] = True
            try:
                yield lock_root / ".git" / "spec-kitty-locks" / f"{mission_slug}.status.lock"
            finally:
                lock_state["held"] = False

        real_derive = emit_module._derive_from_lane
        real_append = emit_module._store.append_event_stream_atomic_verified
        real_materialize = emit_module._reducer.materialize

        def tracking_derive(*args: object, **kwargs: object):
            assert lock_state["held"] is True
            observed.append("derive")
            return real_derive(*args, **kwargs)

        def tracking_append(*args: object, **kwargs: object):
            assert lock_state["held"] is True
            observed.append("append")
            return real_append(*args, **kwargs)

        def tracking_materialize(*args: object, **kwargs: object):
            assert lock_state["held"] is True
            observed.append("materialize")
            return real_materialize(*args, **kwargs)

        monkeypatch.setattr(emit_module, "feature_status_lock", tracking_lock, raising=False)
        monkeypatch.setattr(emit_module, "_derive_from_lane", tracking_derive)
        monkeypatch.setattr(
            emit_module._store,
            "append_event_stream_atomic_verified",
            tracking_append,
        )
        monkeypatch.setattr(emit_module._reducer, "materialize", tracking_materialize)

        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="claude-opus",
                repo_root=lock_root,
            ),
            ensure_sync_daemon=False,
        )

        assert event.to_lane == Lane.CLAIMED
        assert observed == ["derive", "append", "materialize"]

    def test_chained_transitions(self, feature_dir: Path):
        """Multiple transitions chain correctly, deriving from_lane."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        e1 = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        assert e1.from_lane == Lane.PLANNED
        assert e1.to_lane == Lane.CLAIMED

        e2 = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="agent-1",
            )
        )
        assert e2.from_lane == Lane.CLAIMED
        assert e2.to_lane == Lane.IN_PROGRESS

        # WP02/T009: a genuinely-absent tasks.md is unprovable and now blocks
        # (fail-open removal) -- this test exercises chaining, not the
        # subtasks-completeness gate, so it supplies the input explicitly like
        # a real caller with known-complete subtasks would.
        e3 = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="for_review",
                actor="agent-1",
                subtasks_complete=True,
            )
        )
        assert e3.from_lane == Lane.IN_PROGRESS
        assert e3.to_lane == Lane.FOR_REVIEW

        # Verify 3 lifecycle events in JSONL (plus the genesis->planned seed)
        events = read_events(feature_dir)
        assert len(events) == 4

    def test_alias_resolution_doing(self, feature_dir: Path):
        """'doing' alias resolves to 'in_progress'."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        # First move to claimed
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        # Now use 'doing' alias
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="doing",
                actor="agent-1",
            )
        )
        assert event.to_lane == Lane.IN_PROGRESS

    def test_alias_collapse_noop_returns_without_new_event(self, feature_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Legacy alias to the current lane is a locked no-op, not a duplicate event."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="doing",
                actor="agent-1",
            )
        )

        with caplog.at_level("INFO"):
            event = emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="doing",
                    actor="agent-1",
                )
            )

        assert event.from_lane == Lane.IN_PROGRESS
        assert event.to_lane == Lane.IN_PROGRESS
        # genesis->planned seed + planned->claimed + claimed->in_progress; the
        # final doing alias collapses to a no-op (no new event).
        assert len(read_events(feature_dir)) == 3
        assert "Collapsing legacy alias doing to existing lane in_progress" in caplog.text

    def test_invalid_transition_rejected_no_persistence(self, feature_dir: Path):
        """Invalid transition raises TransitionError and persists nothing."""
        with pytest.raises(TransitionError):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="done",
                    actor="agent-1",
                )
            )

        # Verify nothing was persisted
        events_path = feature_dir / EVENTS_FILENAME
        assert not events_path.exists()

    def test_invalid_lane_rejected(self, feature_dir: Path):
        """Unknown lane value raises TransitionError."""
        with pytest.raises(TransitionError):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="invalid_lane",
                    actor="agent-1",
                )
            )

    def test_execution_mode_direct_repo(self, feature_dir: Path):
        """Non-default execution_mode is recorded in event."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
                execution_mode="direct_repo",
            )
        )
        assert event.execution_mode == "direct_repo"

    def test_multiple_wps_independent(self, feature_dir: Path):
        """Events for different WPs are independent."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        _seed_planned(feature_dir, "WP02", slug="034-test-feature")
        e1 = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        e2 = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP02",
                to_lane="claimed",
                actor="agent-2",
            )
        )

        assert e1.wp_id == "WP01"
        assert e2.wp_id == "WP02"
        assert e1.from_lane == Lane.PLANNED
        assert e2.from_lane == Lane.PLANNED

        # Both should show in snapshot
        snapshot_path = feature_dir / "status.json"
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert "WP01" in data["work_packages"]
        assert "WP02" in data["work_packages"]


# ── Force Transition Tests ───────────────────────────────────


class TestForceTransitions:
    """Tests for force transition handling."""

    def test_force_illegal_transition_succeeds(self, feature_dir: Path):
        """Force allows normally-illegal transitions (e.g. planned -> done)."""
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="done",
                actor="admin",
                force=True,
                reason="Emergency fix deployed directly",
            )
        )
        assert event.to_lane == Lane.DONE
        assert event.force is True
        assert event.reason == "Emergency fix deployed directly"

    def test_force_without_actor_rejected(self, feature_dir: Path):
        """Force transition without actor raises TransitionError."""
        with pytest.raises(TransitionError):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="done",
                    actor="",
                    force=True,
                    reason="Some reason",
                )
            )

    def test_force_without_reason_rejected(self, feature_dir: Path):
        """Force transition without reason raises TransitionError."""
        with pytest.raises(TransitionError):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="done",
                    actor="admin",
                    force=True,
                    reason=None,
                )
            )

    def test_force_with_invalid_lane_rejected(self, feature_dir: Path):
        """Force does not bypass invalid lane names."""
        with pytest.raises(TransitionError):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="imaginary",
                    actor="admin",
                    force=True,
                    reason="testing",
                )
            )

    def test_force_no_persistence_on_failure(self, feature_dir: Path):
        """Force transition that fails validation persists nothing."""
        with pytest.raises(TransitionError):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="done",
                    actor="",
                    force=True,
                    reason="some reason",
                )
            )
        events_path = feature_dir / EVENTS_FILENAME
        assert not events_path.exists()

    def test_force_from_done_state(self, feature_dir: Path):
        """Force can exit the terminal done state."""
        # First force to done
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="done",
                actor="admin",
                force=True,
                reason="Initial done",
            )
        )
        # Force back to in_progress
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="admin",
                force=True,
                reason="Reopening for fixes",
            )
        )
        assert event.from_lane == Lane.DONE
        assert event.to_lane == Lane.IN_PROGRESS

    def test_force_to_done_without_evidence(self, feature_dir: Path):
        """Force to done bypasses evidence requirement."""
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="done",
                actor="admin",
                force=True,
                reason="Emergency override, no evidence needed",
            )
        )
        assert event.to_lane == Lane.DONE
        assert event.evidence is None


# ── Done-Evidence Contract ───────────────────────────────────


class TestDoneEvidence:
    """Tests for the done-evidence contract in emit.

    In the 9-lane model, the path to done goes through in_review:
    planned → claimed → in_progress → for_review → in_review → done
    (with review_result required for in_review outbound transitions).
    """

    def test_done_without_evidence_rejected(self, feature_dir: Path):
        """Transition to done without evidence is rejected."""

        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        # Move through the pipeline: planned → claimed → in_progress → for_review → in_review
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="a",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="a",
            )
        )
        # WP02/T009: fail-open removal means a genuinely-absent tasks.md now
        # blocks; these tests exercise the done/evidence guards downstream of
        # for_review, not the subtasks-completeness gate itself.
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="for_review",
                actor="a",
                subtasks_complete=True,
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_review",
                actor="reviewer",
            )
        )

        # in_review → done requires both review_result AND evidence
        with pytest.raises(TransitionError, match="review_result|evidence"):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="done",
                    actor="reviewer",
                )
            )

    def test_done_with_valid_evidence(self, feature_dir: Path, valid_evidence_dict: dict):
        """Transition to done with valid evidence via in_review succeeds."""
        from specify_cli.status.models import ReviewResult

        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="a",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="a",
            )
        )
        # WP02/T009: fail-open removal means a genuinely-absent tasks.md now
        # blocks; these tests exercise the done/evidence guards downstream of
        # for_review, not the subtasks-completeness gate itself.
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="for_review",
                actor="a",
                subtasks_complete=True,
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_review",
                actor="reviewer",
            )
        )

        review_result = ReviewResult(verdict="approved", reviewer="reviewer-1", reference="PR#42")
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="done",
                actor="reviewer",
                evidence=valid_evidence_dict,
                review_result=review_result,
            )
        )
        assert event.to_lane == Lane.DONE
        assert event.evidence is not None
        assert event.evidence.review.reviewer == "reviewer-1"
        assert event.evidence.review.verdict == "approved"

    def test_done_with_bad_evidence_rejected(self, feature_dir: Path):
        """Transition to done with malformed evidence is rejected."""
        from specify_cli.status.models import ReviewResult

        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="a",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="a",
            )
        )
        # WP02/T009: fail-open removal means a genuinely-absent tasks.md now
        # blocks; these tests exercise the done/evidence guards downstream of
        # for_review, not the subtasks-completeness gate itself.
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="for_review",
                actor="a",
                subtasks_complete=True,
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_review",
                actor="reviewer",
            )
        )

        review_result = ReviewResult(verdict="approved", reviewer="reviewer", reference="PR#1")
        with pytest.raises(TransitionError, match="review.reviewer"):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="done",
                    actor="reviewer",
                    evidence={"not_review": "data"},
                    review_result=review_result,
                )
            )

        # Verify no done event was persisted (genesis->planned seed + 4 prior events)
        events = read_events(feature_dir)
        assert len(events) == 5


class TestPhase1CompatibilityBridge:
    """``status_phase`` gate parsing on the RETAINED lane-mirror gate.

    The #2816 cutover deleted the runtime-slot authority predicate
    (``_phase1_snapshot_authority_active``): runtime-slot reads are now
    unconditional. The lane-mirror gate (``_legacy_lane_mirror_enabled``, C-004)
    keeps the identical ``status_phase`` parsing contract these tests pin —
    reconciled onto the surviving gate (SC-002)."""

    def test_lane_mirror_disabled_on_invalid_meta(
        self,
        feature_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Write malformed JSON to meta.json — observable contract: returns False
        # and logs a warning about the invalid file (not a call-graph assertion).
        (feature_dir / "meta.json").write_text("{bad json", encoding="utf-8")

        with caplog.at_level("WARNING"):
            assert _legacy_lane_mirror_enabled(feature_dir) is False

        assert "Invalid meta.json" in caplog.text

    def test_lane_mirror_disabled_on_missing_meta(
        self,
        feature_dir: Path,
    ) -> None:
        """Missing meta.json silently disables the lane mirror (returns False)."""
        assert not (feature_dir / "meta.json").exists()

        assert _legacy_lane_mirror_enabled(feature_dir) is False

    def test_status_phase_1_enables_lane_mirror(self, feature_dir: Path) -> None:
        (feature_dir / "meta.json").write_text('{"status_phase": "1"}', encoding="utf-8")
        assert _legacy_lane_mirror_enabled(feature_dir) is True

    def test_status_phase_2_keeps_lane_mirror_enabled(self, feature_dir: Path) -> None:
        """A mission advanced to ``status_phase: 2`` must keep the lane mirror ON.

        Regression for the ``== "1"`` bug: strict equality would silently drop a
        phase-2 mission's lane mirror. ``>= 1`` semantics keep the retained
        lane-mirror gate ON.
        """
        (feature_dir / "meta.json").write_text('{"status_phase": 2}', encoding="utf-8")
        assert _legacy_lane_mirror_enabled(feature_dir) is True

    def test_status_phase_0_is_off(self, feature_dir: Path) -> None:
        (feature_dir / "meta.json").write_text('{"status_phase": "0"}', encoding="utf-8")
        assert _legacy_lane_mirror_enabled(feature_dir) is False

    def test_non_numeric_status_phase_is_off(self, feature_dir: Path) -> None:
        (feature_dir / "meta.json").write_text('{"status_phase": "later"}', encoding="utf-8")
        assert _legacy_lane_mirror_enabled(feature_dir) is False

    def test_find_wp_file_handles_missing_tasks_and_multiple_matches(
        self,
        feature_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        assert _find_wp_file(feature_dir, "WP01") is None

        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01-alpha.md").write_text("# WP01\n", encoding="utf-8")
        (tasks_dir / "WP01-beta.md").write_text("# WP01\n", encoding="utf-8")

        with caplog.at_level("WARNING"):
            assert _find_wp_file(feature_dir, "WP01") is None

        assert "Multiple work package files matched" in caplog.text

    def test_mirror_phase1_frontmatter_lane_skips_missing_lane_field(
        self,
        feature_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        wp_file = feature_dir / "tasks" / "WP01.md"
        wp_file.parent.mkdir()
        wp_file.write_text("---\nwork_package_id: WP01\n---\n", encoding="utf-8")

        write_mock = MagicMock()
        # The lane mirror gates on _legacy_lane_mirror_enabled (the #2816 split),
        # not the runtime-slot authority gate — patch the gate it actually reads.
        monkeypatch.setattr(emit_module, "_legacy_lane_mirror_enabled", lambda feature_dir: True)
        monkeypatch.setattr(emit_module, "_find_wp_file", lambda feature_dir, wp_id: wp_file)
        # WPMetadata with no lane field — mirror should be a no-op (no lane to update)
        monkeypatch.setattr(
            emit_module,
            "read_wp_frontmatter",
            lambda path: (WPMetadata(work_package_id="WP01"), "body"),
        )
        monkeypatch.setattr(emit_module, "read_frontmatter", lambda path: ({"work_package_id": "WP01"}, "body"))
        monkeypatch.setattr(emit_module, "write_frontmatter", write_mock)

        _mirror_phase1_frontmatter_lane(feature_dir, "WP01", "for_review")

        write_mock.assert_not_called()

    def test_mirror_phase1_frontmatter_lane_handles_frontmatter_read_and_write_errors(
        self,
        feature_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        wp_file = feature_dir / "tasks" / "WP01.md"
        wp_file.parent.mkdir()
        wp_file.write_text("---\nwork_package_id: WP01\nlane: planned\n---\n", encoding="utf-8")

        # The lane mirror gates on _legacy_lane_mirror_enabled (the #2816 split),
        # not the runtime-slot authority gate — patch the gate it actually reads.
        monkeypatch.setattr(emit_module, "_legacy_lane_mirror_enabled", lambda feature_dir: True)
        monkeypatch.setattr(emit_module, "_find_wp_file", lambda feature_dir, wp_id: wp_file)

        # Part 1: read_wp_frontmatter raises FrontmatterError → logged as "Failed to read"
        monkeypatch.setattr(
            emit_module,
            "read_wp_frontmatter",
            lambda path: (_ for _ in ()).throw(FrontmatterError("read failed")),
        )
        with caplog.at_level("WARNING"):
            _mirror_phase1_frontmatter_lane(feature_dir, "WP01", "for_review")
        assert "Failed to read" in caplog.text

        caplog.clear()
        # Part 2: read_wp_frontmatter succeeds (lane="planned"), write_frontmatter raises FrontmatterError
        monkeypatch.setattr(
            emit_module,
            "read_wp_frontmatter",
            lambda path: (WPMetadata(work_package_id="WP01", lane="planned"), "body"),
        )
        monkeypatch.setattr(emit_module, "read_frontmatter", lambda path: ({"work_package_id": "WP01", "lane": "planned"}, "body"))
        monkeypatch.setattr(
            emit_module,
            "write_frontmatter",
            lambda path, frontmatter, body: (_ for _ in ()).throw(FrontmatterError("write failed")),
        )
        with caplog.at_level("WARNING"):
            _mirror_phase1_frontmatter_lane(feature_dir, "WP01", "for_review")
        assert "Failed to write" in caplog.text

    def test_legacy_alias_collapses_only_when_alias_resolves_to_current_lane(self) -> None:
        # With in_review now a first-class lane, this collapse no longer applies.
        # The function still works for any OTHER alias that might collapse, so
        # test with a hypothetical scenario using "doing" -> "in_progress".
        assert _legacy_alias_collapses_to_current_lane("doing", "in_progress", "in_progress") is True
        assert _legacy_alias_collapses_to_current_lane("in_progress", "in_progress", "in_progress") is False
        assert _legacy_alias_collapses_to_current_lane("doing", "in_progress", "planned") is False
        # in_review is no longer an alias — it resolves to itself, so raw == resolved
        assert _legacy_alias_collapses_to_current_lane("in_review", "in_review", "in_review") is False

    def test_emit_status_transition_accepts_mission_alias_for_review_to_in_review(
        self,
        feature_dir: Path,
    ) -> None:
        """in_review is now a first-class lane; transition for_review -> in_review works."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="agent-1",
            )
        )
        # WP02/T009: fail-open removal means a genuinely-absent tasks.md now
        # blocks; this test exercises the for_review -> in_review alias, not
        # the subtasks-completeness gate itself.
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="for_review",
                actor="agent-1",
                subtasks_complete=True,
            )
        )

        event = emit_status_transition(
            TransitionRequest(
                mission_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_review",
                actor="reviewer-1",
            )
        )

        assert event.to_lane == Lane.IN_REVIEW
        assert event.from_lane == Lane.FOR_REVIEW

    def test_emit_status_transition_requires_all_identity_fields(
        self,
        feature_dir: Path,
    ) -> None:
        with pytest.raises(TypeError, match="feature_dir/mission_dir"):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="claimed",
                )
            )


# ── SaaS Fan-Out Tests ───────────────────────────────────────


class TestSaasFanOut:
    """Tests for _saas_fan_out.

    The fan-out seam is the status/adapters handler registry: production
    registrants died with the sync transport (issue #5), so these tests
    register a capturing handler exactly the way a future E3 emitter would.
    """

    def _make_event(
        self,
        *,
        from_lane: Lane = Lane.PLANNED,
        to_lane: Lane = Lane.CLAIMED,
    ) -> StatusEvent:
        return StatusEvent(
            event_id="01HXYZ0000000000000000SAAS",
            mission_slug="034-test-feature",
            wp_id="WP01",
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-02-08T12:00:00Z",
            actor="test-actor",
            force=False,
            execution_mode="worktree",
        )

    @pytest.fixture(autouse=True)
    def _clean_registry(self):
        adapters.reset_handlers()
        yield
        adapters.reset_handlers()

    def test_saas_called_when_available(self):
        """A registered fan-out handler receives the full canonical call shape."""
        from specify_cli.status.wp_status_metadata import WPStatusChangeMetadata

        event = self._make_event(
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
        )
        captured: list[dict] = []

        def _handler(**kwargs):
            captured.append(dict(kwargs))

        adapters.register_saas_fanout_handler(_handler)
        _saas_fan_out(event, "034-test-feature", None)

        assert len(captured) == 1, "fan-out handler must be invoked exactly once"
        # ``occurred_at`` is the canonical local lane-transition time threaded
        # through _saas_fan_out (mission cli-saas-fanout-preserves-local-at-01KRNS87).
        assert captured[0] == {
            "wp_id": "WP01",
            "from_lane": "claimed",
            "to_lane": "in_progress",
            "actor": "test-actor",
            "mission_slug": "034-test-feature",
            "mission_id": None,
            "metadata": WPStatusChangeMetadata(
                causation_id="01HXYZ0000000000000000SAAS",
                policy_metadata=None,
                force=False,
                reason=None,
                review_ref=None,
                execution_mode="worktree",
                evidence=None,
                occurred_at=event.at,
            ),
            "ensure_daemon": True,
            "repo_root": None,
        }

    def test_planned_to_claimed_now_emits(self):
        """planned->claimed now emits (no longer collapsed to no-op)."""
        event = self._make_event(
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
        )
        captured: list[dict] = []
        adapters.register_saas_fanout_handler(lambda **kwargs: captured.append(dict(kwargs)))
        _saas_fan_out(event, "034-test-feature", None)
        assert len(captured) == 1

    def test_saas_exception_does_not_propagate(self):
        """Exception from SaaS emit is caught and logged."""
        event = self._make_event(
            from_lane=Lane.CLAIMED,
            to_lane=Lane.IN_PROGRESS,
        )

        def _boom(**kwargs):
            raise RuntimeError("network error")

        with patch("specify_cli.status.adapters.logger") as mock_logger:
            # Should not raise. After P1.3 the warning is logged by the
            # adapter (specify_cli.status.adapters) rather than by
            # status.emit, since the try/except moved into fire_saas_fanout.
            adapters.register_saas_fanout_handler(_boom)
            _saas_fan_out(event, "034-test-feature", None)
            mock_logger.warning.assert_called_once()

    def test_saas_failure_does_not_block_emit(self, feature_dir: Path):
        """Full emit succeeds even when SaaS fan-out fails."""

        def _boom(**kwargs):
            raise RuntimeError("network down")

        adapters.register_saas_fanout_handler(_boom)
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        assert event.to_lane == Lane.CLAIMED
        # Event was still persisted (genesis->planned seed + planned->claimed)
        events = read_events(feature_dir)
        assert len(events) == 2


# ── Pipeline Order Tests ─────────────────────────────────────


class TestPipelineOrder:
    """Tests verifying the critical pipeline ordering."""

    def test_validation_before_persistence(self, feature_dir: Path):
        """Validation failure means nothing is written to disk."""
        with pytest.raises(TransitionError):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="done",  # illegal from planned
                    actor="agent-1",
                )
            )

        events_path = feature_dir / EVENTS_FILENAME
        assert not events_path.exists()
        snapshot_path = feature_dir / "status.json"
        assert not snapshot_path.exists()

    def test_event_persisted_even_if_materialize_fails(self, feature_dir: Path):
        """If materialize fails, the event is still in the JSONL log."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with patch(
            "specify_cli.status.emit._reducer.materialize",
            side_effect=OSError("disk error during materialize"),
        ):
            event = emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="claimed",
                    actor="agent-1",
                )
            )

        # Event was persisted even though materialize failed (seed + claimed)
        events = read_events(feature_dir)
        assert len(events) == 2
        assert events[-1].event_id == event.event_id

    def test_no_legacy_bridge_in_emit(self):
        """Verify emit.py does not import legacy_bridge (it was deleted in WP05)."""
        import ast
        import inspect

        import specify_cli.status.emit as emit_mod

        source = inspect.getsource(emit_mod)
        tree = ast.parse(source)

        # Confirm no ImportFrom for legacy_bridge exists anywhere
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or "legacy_bridge" not in node.module, "legacy_bridge was deleted in WP05 — it must not be imported in emit.py"


# ── Review-Ref Guard Tests ───────────────────────────────────


class TestReviewRefGuard:
    """Tests for review_result requirement on in_review -> in_progress.

    In the 9-lane model, rework goes through in_review:
    for_review → in_review → in_progress (with review_result required).
    """

    def test_in_review_to_in_progress_requires_review_result(self, feature_dir: Path):
        """in_review -> in_progress without review_result is rejected."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="a",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="a",
            )
        )
        # WP02/T009: fail-open removal means a genuinely-absent tasks.md now
        # blocks; these tests exercise the done/evidence guards downstream of
        # for_review, not the subtasks-completeness gate itself.
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="for_review",
                actor="a",
                subtasks_complete=True,
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_review",
                actor="reviewer",
            )
        )

        with pytest.raises(TransitionError, match="review_result"):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="in_progress",
                    actor="reviewer",
                )
            )

    def test_in_review_to_in_progress_with_review_result(self, feature_dir: Path):
        """in_review -> in_progress with review_result succeeds."""
        from specify_cli.status.models import ReviewResult

        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="a",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="a",
            )
        )
        # WP02/T009: fail-open removal means a genuinely-absent tasks.md now
        # blocks; these tests exercise the done/evidence guards downstream of
        # for_review, not the subtasks-completeness gate itself.
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="for_review",
                actor="a",
                subtasks_complete=True,
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_review",
                actor="reviewer",
            )
        )

        review_result = ReviewResult(verdict="changes_requested", reviewer="reviewer", reference="PR#42-comment-3")
        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="in_progress",
                actor="reviewer",
                review_result=review_result,
            )
        )
        assert event.from_lane == Lane.IN_REVIEW
        assert event.to_lane == Lane.IN_PROGRESS


# ── Reason Guard Tests ───────────────────────────────────────


class TestReasonGuard:
    """Tests for reason requirement on in_progress -> planned."""

    def test_in_progress_to_planned_requires_reason(self, feature_dir: Path):
        """in_progress -> planned without reason is rejected."""
        _seed_planned(feature_dir, "WP01", slug="034-test")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test",
                wp_id="WP01",
                to_lane="claimed",
                actor="a",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test",
                wp_id="WP01",
                to_lane="in_progress",
                actor="a",
            )
        )

        with pytest.raises(TransitionError, match="reason"):
            emit_status_transition(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test",
                    wp_id="WP01",
                    to_lane="planned",
                    actor="a",
                )
            )

    def test_in_progress_to_planned_with_reason(self, feature_dir: Path):
        """in_progress -> planned with reason succeeds."""
        _seed_planned(feature_dir, "WP01", slug="034-test")
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test",
                wp_id="WP01",
                to_lane="claimed",
                actor="a",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test",
                wp_id="WP01",
                to_lane="in_progress",
                actor="a",
            )
        )

        event = emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug="034-test",
                wp_id="WP01",
                to_lane="planned",
                actor="a",
                reason="Needs more planning",
            )
        )
        assert event.reason == "Needs more planning"
        assert event.to_lane == Lane.PLANNED


class TestMergeLightweightEmit:
    def test_emit_status_transition_can_skip_daemon_start(
        self,
        feature_dir: Path,
    ) -> None:
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with patch.object(emit_module, "_saas_fan_out") as mock_fanout:
            event = emit_status_transition(
                feature_dir=feature_dir,
                mission_slug="034-test-feature",
                wp_id="WP01",
                to_lane="claimed",
                actor="merge",
                repo_root=feature_dir.parent.parent,
                ensure_sync_daemon=False,
            )

        assert event.to_lane == Lane.CLAIMED
        mock_fanout.assert_called_once()
        assert mock_fanout.call_args.kwargs["ensure_sync_daemon"] is False


class TestBatchEmit:
    def test_empty_batch_returns_empty(self) -> None:
        assert emit_status_transition_batch([]) == []

    def test_empty_batch_accepts_retired_326_dossier_keyword(self) -> None:
        assert emit_status_transition_batch([], sync_dossier=False) == []

    def test_batch_requires_first_request_identity(self) -> None:
        with pytest.raises(TypeError, match="requires feature_dir"):
            emit_status_transition_batch([TransitionRequest()])

    def test_batch_requires_each_request_identity(self, feature_dir: Path) -> None:
        # Seed so the first (valid) request's transition succeeds and the loop
        # reaches the second request's identity guard.
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with pytest.raises(TypeError, match="Each batch transition"):
            emit_status_transition_batch(
                [
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP01",
                        to_lane="claimed",
                        actor="agent",
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP01",
                    ),
                ]
            )

    def test_batch_rejects_mixed_work_packages(self, feature_dir: Path) -> None:
        # Seed so the first request's transition succeeds and the loop reaches
        # the mixed-WP guard on the second request.
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with pytest.raises(TypeError, match="one feature/mission/wp"):
            emit_status_transition_batch(
                [
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP01",
                        to_lane="claimed",
                        actor="agent",
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP02",
                        to_lane="claimed",
                        actor="agent",
                    ),
                ]
            )

    def test_batch_all_alias_collapses_returns_empty(self, feature_dir: Path) -> None:
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01HXYZ0000000000000000CLPS",
                mission_slug="034-test-feature",
                wp_id="WP01",
                from_lane=Lane.CLAIMED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-02-08T12:00:00Z",
                actor="agent",
                force=False,
                execution_mode="worktree",
            ),
        )

        events = emit_status_transition_batch(
            [
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug="034-test-feature",
                    wp_id="WP01",
                    to_lane="doing",
                    actor="agent",
                )
            ]
        )

        assert events == []
        assert len(read_events(feature_dir)) == 1

    def test_batch_invalid_transition_is_rejected_without_persisting(self, feature_dir: Path) -> None:
        with pytest.raises(TransitionError, match="Illegal transition"):
            emit_status_transition_batch(
                [
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP01",
                        to_lane="done",
                        actor="agent",
                    )
                ]
            )

        assert read_events(feature_dir) == []

    def test_batch_infers_review_readiness_and_builds_evidence(self, feature_dir: Path, valid_evidence_dict: dict) -> None:
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with patch.object(emit_module, "_saas_fan_out"):
            events = emit_status_transition_batch(
                [
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP01",
                        to_lane="claimed",
                        actor="agent",
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP01",
                        to_lane="in_progress",
                        actor="agent",
                        workspace_context="worktree:/nonexistent/wp01",
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP01",
                        to_lane="for_review",
                        actor="agent",
                        force=True,
                        reason="ready for review",
                    ),
                ],
            )

        assert [event.to_lane for event in events] == [Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW]

        _seed_planned(feature_dir, "WP02", slug="034-test-feature")
        with patch.object(emit_module, "_saas_fan_out"):
            done = emit_status_transition_batch(
                [
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP02",
                        to_lane="claimed",
                        actor="agent",
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP02",
                        to_lane="in_progress",
                        actor="agent",
                        workspace_context="worktree:/nonexistent/wp02",
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP02",
                        to_lane="for_review",
                        actor="agent",
                        force=True,
                        reason="ready for review",
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP02",
                        to_lane="in_review",
                        actor="reviewer",
                        review_ref="review-1",
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP02",
                        to_lane="approved",
                        actor="reviewer",
                        review_result=ReviewResult(
                            reviewer="reviewer",
                            verdict="approved",
                            reference="review-1",
                        ),
                    ),
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP02",
                        to_lane="done",
                        actor="reviewer",
                        evidence=valid_evidence_dict,
                    ),
                ],
            )

        assert done[-1].evidence is not None
        assert done[-1].to_lane == Lane.DONE

    def test_batch_materialize_failure_keeps_persisted_events(self, feature_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with (
            patch.object(emit_module, "_saas_fan_out"),
            patch.object(emit_module._reducer, "materialize", side_effect=RuntimeError("boom")),
        ):
            events = emit_status_transition_batch(
                [
                    TransitionRequest(
                        feature_dir=feature_dir,
                        mission_slug="034-test-feature",
                        wp_id="WP01",
                        to_lane="claimed",
                        actor="agent",
                    )
                ],
            )

        assert len(events) == 1
        # Last persisted event is the claimed transition (after the seed).
        assert read_events(feature_dir)[-1].to_lane == Lane.CLAIMED
        assert "Materialization failed after batch" in caplog.text


# ── Genesis SaaS fan-out capability gate tests (T023, WP04) ──────────────────


class TestGenesisSaasFanOutCompatibilityGate:
    """Tests for the genesis compatibility gate in _saas_fan_out (T022/T023, WP04).

    The gate in emit.py._saas_fan_out skips fan-out when the installed
    spec_kitty_events lacks the genesis lane, producing an explicit INFO log
    instead of a silently swallowed pydantic ValidationError.

    The capability-present case (genesis-aware events) is exercised via
    monkeypatching emit_module._EVENTS_SUPPORTS_GENESIS = True so the tests
    run correctly against the installed 5.2.0 package (which has no genesis).
    """

    def test_genesis_transition_skipped_when_events_lacks_genesis(
        self,
        feature_dir: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """With genesis-unaware events: genesis fan-out is explicitly skipped, not crashed.

        The skip is deliberate (logged INFO) and canonical local persistence
        is completely unaffected.
        """
        from specify_cli.status import adapters as _adapters

        _adapters.reset_handlers()
        captured: list[dict] = []

        def fake_saas(**kwargs: object) -> None:
            captured.append(dict(kwargs))

        _adapters.register_saas_fanout_handler(fake_saas)
        try:
            # Ensure the capability flag reports no genesis support (mirror current 5.2.0 reality)
            with patch.object(emit_module, "_EVENTS_SUPPORTS_GENESIS", False):
                caplog.set_level(logging.INFO, logger="specify_cli.status.emit")
                # Build a genesis -> planned event and call _saas_fan_out directly
                genesis_event = StatusEvent(
                    event_id="01GENESIS00000000000000001",
                    mission_slug="test-feature",
                    wp_id="WP01",
                    from_lane=Lane.GENESIS,
                    to_lane=Lane.PLANNED,
                    at="2026-06-07T12:00:00+00:00",
                    actor="seed",
                    force=True,
                    execution_mode="worktree",
                    reason="seed",
                )
                _saas_fan_out(genesis_event, "test-feature", None)

            # The skip path must fire: no handler was called
            assert len(captured) == 0, "SaaS fan-out handler must NOT be called for genesis when events lacks genesis"
            # The explicit skip log must be present — NOT a ValidationError
            assert "Skipping SaaS fan-out for genesis transition" in caplog.text, "Explicit skip log must be emitted when genesis fan-out is gated out"
            assert "genesis lane (needs >=6.0.0)" in caplog.text
            # Canonical persistence is unaffected — no StoreError, the feature dir is intact
            assert feature_dir.exists()
        finally:
            _adapters.reset_handlers()

    def test_genesis_transition_fans_out_when_events_supports_genesis(
        self,
        feature_dir: Path,
    ) -> None:
        """With genesis-aware events: genesis -> planned fans out as a normal payload.

        Simulates spec_kitty_events 6.0.0 via monkeypatch of _EVENTS_SUPPORTS_GENESIS.
        The fan-out handler is called exactly once; no ValidationError is raised.
        """
        from specify_cli.status import adapters as _adapters

        _adapters.reset_handlers()
        captured: list[dict] = []

        def fake_saas(**kwargs: object) -> None:
            captured.append(dict(kwargs))

        _adapters.register_saas_fanout_handler(fake_saas)
        try:
            # Simulate 6.0.0+ (genesis-aware events installed)
            with patch.object(emit_module, "_EVENTS_SUPPORTS_GENESIS", True):
                genesis_event = StatusEvent(
                    event_id="01GENESIS00000000000000002",
                    mission_slug="test-feature",
                    wp_id="WP01",
                    from_lane=Lane.GENESIS,
                    to_lane=Lane.PLANNED,
                    at="2026-06-07T12:00:00+00:00",
                    actor="seed",
                    force=True,
                    execution_mode="worktree",
                    reason="seed",
                )
                _saas_fan_out(genesis_event, "test-feature", None)

            # The handler must have been called exactly once
            assert len(captured) == 1, "SaaS fan-out handler must be called when events supports genesis"
            call = captured[0]
            assert call["wp_id"] == "WP01"
            assert call["from_lane"] == "genesis"
            assert call["to_lane"] == "planned"
            assert call["actor"] == "seed"
            assert call["mission_slug"] == "test-feature"
        finally:
            _adapters.reset_handlers()

    def test_normal_transition_fans_out_unchanged_without_genesis_support(
        self,
        feature_dir: Path,
    ) -> None:
        """With genesis-unaware events: a normal (non-genesis) transition fans out unchanged."""
        from specify_cli.status import adapters as _adapters

        _adapters.reset_handlers()
        captured: list[dict] = []

        def fake_saas(**kwargs: object) -> None:
            captured.append(dict(kwargs))

        _adapters.register_saas_fanout_handler(fake_saas)
        try:
            with patch.object(emit_module, "_EVENTS_SUPPORTS_GENESIS", False):
                normal_event = StatusEvent(
                    event_id="01NORMAL000000000000000001",
                    mission_slug="test-feature",
                    wp_id="WP01",
                    from_lane=Lane.PLANNED,
                    to_lane=Lane.CLAIMED,
                    at="2026-06-07T12:00:00+00:00",
                    actor="agent",
                    force=False,
                    execution_mode="worktree",
                )
                _saas_fan_out(normal_event, "test-feature", None)

            assert len(captured) == 1, "Normal (non-genesis) transition must still fan out with genesis-unaware events"
            call = captured[0]
            assert call["from_lane"] == "planned"
            assert call["to_lane"] == "claimed"
        finally:
            _adapters.reset_handlers()

    def test_normal_transition_fans_out_unchanged_with_genesis_support(
        self,
        feature_dir: Path,
    ) -> None:
        """With genesis-aware events: a normal transition still fans out unchanged (no regression)."""
        from specify_cli.status import adapters as _adapters

        _adapters.reset_handlers()
        captured: list[dict] = []

        def fake_saas(**kwargs: object) -> None:
            captured.append(dict(kwargs))

        _adapters.register_saas_fanout_handler(fake_saas)
        try:
            with patch.object(emit_module, "_EVENTS_SUPPORTS_GENESIS", True):
                normal_event = StatusEvent(
                    event_id="01NORMAL000000000000000002",
                    mission_slug="test-feature",
                    wp_id="WP01",
                    from_lane=Lane.PLANNED,
                    to_lane=Lane.CLAIMED,
                    at="2026-06-07T12:00:00+00:00",
                    actor="agent",
                    force=False,
                    execution_mode="worktree",
                )
                _saas_fan_out(normal_event, "test-feature", None)

            assert len(captured) == 1, "Normal (non-genesis) transition must still fan out with genesis-aware events"
        finally:
            _adapters.reset_handlers()


# ── WP02 (fsm-write-path-integrity): flat/primary shell composition pins ─────
#
# The shells compose ``status/transition_pipeline.py::prepare_transition``
# (contract ``emit-pipeline.md`` §2). These tests pin the shell contract:
# the fan-out seam, the FR-004 lock key, exactly one ``validate_transition``
# per emit, and the batch door's single lock acquisition (FR-018) with its
# all-or-nothing failure policy.


def _wp02_request(feature_dir: Path, to_lane: str, **overrides: Any) -> TransitionRequest:
    base: dict[str, Any] = {
        "feature_dir": feature_dir,
        "mission_slug": "034-test-feature",
        "wp_id": "WP01",
        "to_lane": to_lane,
        "actor": "agent-1",
    }
    base.update(overrides)
    return TransitionRequest(**base)


@contextmanager
def _recording_lock(record: dict[str, object]) -> Iterator[Path]:
    """Stand-in ``feature_status_lock`` that records its key and hold state."""
    record["held"] = True
    yield Path("/nonexistent.lock")
    record["held"] = False


class TestFlatShellFanOutSeam:
    """``fan_out=False`` skips step 7 entirely; persistence is unchanged.

    ``tests/status/conftest.py`` neuters ``_saas_fan_out`` for this file, so
    these pins observe the seam at the shell's own call sites; the adapter-
    registry (zero handler calls) proof lives in
    ``tests/status/test_emit_fanout_after_adapter.py``.
    """

    def test_single_fan_out_false_skips_both_fan_out_calls(self, feature_dir: Path) -> None:
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with (
            patch.object(emit_module, "_saas_fan_out") as saas_fan_out,
            patch.object(emit_module, "_resolved_binding_fan_out") as binding_fan_out,
        ):
            event = emit_status_transition(
                _wp02_request(
                    feature_dir,
                    "claimed",
                    annotation_delta=WPInnerStateDelta(role="implementer", agent_profile="python-pedro"),
                ),
                fan_out=False,
            )
        assert event.to_lane == Lane.CLAIMED
        saas_fan_out.assert_not_called()
        binding_fan_out.assert_not_called()
        # Persistence is untouched by the seam: transition + annotation landed.
        stream = read_event_stream(feature_dir)
        assert stream.transitions[-1].event_id == event.event_id
        assert len(stream.annotations) == 1

    def test_single_fan_out_default_fires_after_release(self, feature_dir: Path) -> None:
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with (
            patch.object(emit_module, "_saas_fan_out") as saas_fan_out,
            patch.object(emit_module, "_resolved_binding_fan_out") as binding_fan_out,
        ):
            event = emit_status_transition(
                _wp02_request(
                    feature_dir,
                    "claimed",
                    annotation_delta=WPInnerStateDelta(role="implementer", agent_profile="python-pedro"),
                ),
            )
        saas_fan_out.assert_called_once()
        assert saas_fan_out.call_args.args[0] is event
        binding_fan_out.assert_called_once()

    def test_batch_fan_out_false_skips_both_fan_out_calls(self, feature_dir: Path) -> None:
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with (
            patch.object(emit_module, "_saas_fan_out") as saas_fan_out,
            patch.object(emit_module, "_resolved_binding_fan_out") as binding_fan_out,
        ):
            events = emit_status_transition_batch(
                [
                    _wp02_request(
                        feature_dir,
                        "claimed",
                        annotation_delta=WPInnerStateDelta(role="implementer", agent_profile="python-pedro"),
                    ),
                    _wp02_request(feature_dir, "in_progress", workspace_context="worktree:/nonexistent/wp01"),
                ],
                fan_out=False,
            )
        assert [event.to_lane for event in events] == [Lane.CLAIMED, Lane.IN_PROGRESS]
        saas_fan_out.assert_not_called()
        binding_fan_out.assert_not_called()
        assert len(read_event_stream(feature_dir).annotations) == 1


class TestFlatShellLockAndValidation:
    def test_single_lock_is_keyed_on_feature_dir_name(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FR-004: the lock key is the mission directory NAME, not the slug."""
        feature_dir = tmp_path / "kitty-specs" / "demo-mission-01ABCDEF"
        feature_dir.mkdir(parents=True)
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        keys: list[str] = []

        @contextmanager
        def recording_lock(repo_root: Path, key: str) -> Iterator[Path]:
            keys.append(key)
            yield repo_root / key

        monkeypatch.setattr(emit_module, "feature_status_lock", recording_lock)
        with patch.object(emit_module, "_saas_fan_out"):
            emit_status_transition(_wp02_request(feature_dir, "claimed"))
        assert keys == ["demo-mission-01ABCDEF"]

    def test_validate_transition_runs_exactly_once_per_emit(self, feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """P-2: the shell never validates itself; the pipeline validates once."""
        calls: list[tuple[object, ...]] = []
        real = _pipeline_module.validate_transition

        def counting(*args: object, **kwargs: object) -> object:
            calls.append(args)
            return real(*args, **kwargs)

        monkeypatch.setattr(_pipeline_module, "validate_transition", counting)
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with patch.object(emit_module, "_saas_fan_out"):
            emit_status_transition(_wp02_request(feature_dir, "claimed"))
        assert len(calls) == 1
        assert calls[0][:2] == (Lane.PLANNED, Lane.CLAIMED)


class TestBatchShellLock:
    def test_batch_holds_feature_lock_across_derive_prepare_and_append(self, feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """FR-018: ONE acquisition covers derive, prepare, append, materialize, mirror."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        state: dict[str, object] = {"held": False}
        acquisitions: list[tuple[Path, str]] = []
        observed: list[str] = []

        @contextmanager
        def tracking_lock(repo_root: Path, key: str) -> Iterator[Path]:
            acquisitions.append((repo_root, key))
            with _recording_lock(state):
                yield repo_root / key

        real_derive = emit_module._derive_from_lane
        real_prepare = emit_module.prepare_transition
        real_append = emit_module._store.append_event_stream_atomic_verified
        real_materialize = emit_module._reducer.materialize
        real_mirror = emit_module._mirror_phase1_frontmatter_lane

        def spy(name: str, real: Callable[..., object]) -> Callable[..., object]:
            def wrapped(*args: object, **kwargs: object) -> object:
                assert state["held"] is True, f"{name} ran outside the lock"
                observed.append(name)
                return real(*args, **kwargs)

            return wrapped

        monkeypatch.setattr(emit_module, "feature_status_lock", tracking_lock)
        monkeypatch.setattr(emit_module, "_derive_from_lane", spy("derive", real_derive))
        monkeypatch.setattr(emit_module, "prepare_transition", spy("prepare", real_prepare))
        monkeypatch.setattr(emit_module._store, "append_event_stream_atomic_verified", spy("append", real_append))
        monkeypatch.setattr(emit_module._reducer, "materialize", spy("materialize", real_materialize))
        monkeypatch.setattr(emit_module, "_mirror_phase1_frontmatter_lane", spy("mirror", real_mirror))

        with patch.object(emit_module, "_saas_fan_out") as fan_out:
            events = emit_status_transition_batch(
                [
                    _wp02_request(feature_dir, "claimed"),
                    _wp02_request(feature_dir, "in_progress", workspace_context="worktree:/nonexistent/wp01"),
                ]
            )

        assert [event.to_lane for event in events] == [Lane.CLAIMED, Lane.IN_PROGRESS]
        assert acquisitions == [(feature_dir.parent.parent, feature_dir.name)]
        assert observed == ["derive", "prepare", "prepare", "append", "materialize", "mirror", "mirror"]
        # Fan-out fires after release, once per event.
        assert fan_out.call_count == 2
        assert state["held"] is False

    def test_batch_mid_sequence_refusal_persists_nothing(self, feature_dir: Path) -> None:
        """Failure policy (C-007): a refused member aborts before ANY append."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        before = read_events(feature_dir)
        with pytest.raises(TransitionError, match="Illegal transition"):
            emit_status_transition_batch(
                [
                    _wp02_request(feature_dir, "claimed"),
                    _wp02_request(feature_dir, "done", actor="reviewer"),
                ]
            )
        assert read_events(feature_dir) == before

    def test_batch_claimed_to_in_progress_without_workspace_context_is_refused(self, feature_dir: Path) -> None:
        """Fail-closed pin (#946; D-2 in design-notes/WP02-pipeline.md; mission-review DRIFT-3).

        The plain batch door deliberately does NOT synthesise the
        ``<execution_mode>:<root>`` workspace-context default on
        ``claimed -> in_progress`` (#946). Mission
        ``fsm-write-path-integrity-01M1TZV6`` WP02 dropped that skip for
        parity with the other doors; the operator reverted it on 2026-09-07
        (DRIFT-3). The pipeline stays the single validation authority: the
        batch door passes ``default_workspace_context=False`` and the guard
        refuses with the historical message, persisting nothing. Production
        callers always supply ``workspace_context`` for this edge
        (``status/work_package_lifecycle.py``); the flat single door and both
        transactional doors keep applying the default.
        """
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        before = read_events(feature_dir)
        with patch.object(emit_module, "_saas_fan_out"), pytest.raises(TransitionError, match="requires workspace context"):
            emit_status_transition_batch(
                [
                    _wp02_request(feature_dir, "claimed"),
                    _wp02_request(feature_dir, "in_progress"),
                ]
            )
        assert read_events(feature_dir) == before

    def test_batch_claimed_to_in_progress_with_explicit_workspace_context_succeeds(self, feature_dir: Path) -> None:
        """The #946 refusal is only for an OMITTED context; an explicit one passes."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with patch.object(emit_module, "_saas_fan_out"):
            events = emit_status_transition_batch(
                [
                    _wp02_request(feature_dir, "claimed"),
                    _wp02_request(feature_dir, "in_progress", workspace_context="worktree:/nonexistent/wp01"),
                ]
            )
        assert [event.to_lane for event in events] == [Lane.CLAIMED, Lane.IN_PROGRESS]

    def test_batch_annotation_shares_its_transition_timestamp(self, feature_dir: Path) -> None:
        """D-3: a batch annotation is stamped with its own transition's ``at``."""
        _seed_planned(feature_dir, "WP01", slug="034-test-feature")
        with patch.object(emit_module, "_saas_fan_out"), patch.object(emit_module, "_resolved_binding_fan_out"):
            events = emit_status_transition_batch(
                [
                    _wp02_request(
                        feature_dir,
                        "claimed",
                        annotation_delta=WPInnerStateDelta(role="implementer", agent_profile="python-pedro"),
                    ),
                    _wp02_request(feature_dir, "in_progress", workspace_context="worktree:/nonexistent/wp01"),
                ]
            )
        stream = read_event_stream(feature_dir)
        assert len(stream.annotations) == 1
        assert stream.annotations[0].at == events[0].at
        snapshot = json.loads((feature_dir / "status.json").read_text(encoding="utf-8"))
        assert snapshot["work_packages"]["WP01"]["lane"] == "in_progress"
