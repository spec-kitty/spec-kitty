"""Unit tests for status models (Lane, StatusEvent, DoneEvidence, etc.)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from specify_cli.status.models import (
    NON_DISPLAY_LANES,
    DoneEvidence,
    Lane,
    RepoEvidence,
    ReviewApproval,
    StatusEvent,
    StatusSnapshot,
    ULID_PATTERN,
    VerificationResult,
)

pytestmark = pytest.mark.fast


class TestLaneEnum:
    def test_lane_member_names_exact(self) -> None:
        """11-lane model: the 9 display lanes plus the two non-display lanes.

        'genesis' models the pre-finalize state of a WP (created but not yet
        seeded into the lane lifecycle). 'uninitialized' models the lane-read
        sentinel for a WP with no events at all (empty log or absent from the
        snapshot) — distinct from genesis. Both are excluded from
        CANONICAL_LANES and never the current lane of a materialized WP, but
        both are valid enum members and 'genesis' is a valid from_lane
        ('uninitialized' is never a from_lane or to_lane — it is
        non-transitionable).

        Asserts the exact frozenset of member *names* (the canonical identity),
        not a golden count: adding, removing, or renaming a lane forces a
        content edit here rather than silently passing at an unchanged count.
        """
        assert frozenset(member.name for member in Lane) == frozenset(
            {
                "GENESIS",
                "UNINITIALIZED",
                "PLANNED",
                "CLAIMED",
                "IN_PROGRESS",
                "FOR_REVIEW",
                "IN_REVIEW",
                "APPROVED",
                "DONE",
                "BLOCKED",
                "CANCELED",
            }
        )

    def test_lane_enum_string_values(self) -> None:
        expected = {
            "genesis",
            "uninitialized",
            "planned",
            "claimed",
            "in_progress",
            "for_review",
            "in_review",
            "approved",
            "done",
            "blocked",
            "canceled",
        }
        assert {str(lane) for lane in Lane} == expected

    def test_lane_enum_rejects_alias(self) -> None:
        with pytest.raises(ValueError):
            Lane("doing")

    def test_lane_enum_from_string(self) -> None:
        assert Lane("in_progress") is Lane.IN_PROGRESS
        assert Lane("planned") is Lane.PLANNED
        assert Lane("done") is Lane.DONE

    def test_lane_str_serialization(self) -> None:
        """StrEnum serializes to string value, not member name."""
        assert str(Lane.IN_PROGRESS) == "in_progress"
        assert str(Lane.FOR_REVIEW) == "for_review"


class TestULIDPattern:
    def test_valid_ulid(self) -> None:
        assert ULID_PATTERN.match("01HXYZ0123456789ABCDEFGHJK")

    def test_invalid_ulid_too_short(self) -> None:
        assert not ULID_PATTERN.match("01HXYZ")

    def test_invalid_ulid_lowercase(self) -> None:
        assert not ULID_PATTERN.match("01hxyz0123456789abcdefghjk")

    def test_invalid_ulid_bad_chars(self) -> None:
        # I, L, O, U are excluded from Crockford base32
        assert not ULID_PATTERN.match("01IIOO0123456789LLUUUUGHJK")


class TestRepoEvidence:
    def test_to_dict(self, sample_repo_evidence: RepoEvidence) -> None:
        d = sample_repo_evidence.to_dict()
        assert d["repo"] == "my-org/my-repo"
        assert d["branch"] == "kitty/mission-034-feature-lane-a"
        assert d["commit"] == "abc1234"
        assert d["files_touched"] == ["src/models.py", "tests/test_models.py"]

    def test_to_dict_empty_files(self) -> None:
        re = RepoEvidence(repo="r", branch="b", commit="abc1234")
        d = re.to_dict()
        assert "files_touched" not in d

    def test_round_trip(self, sample_repo_evidence: RepoEvidence) -> None:
        d = sample_repo_evidence.to_dict()
        restored = RepoEvidence.from_dict(d)
        assert restored == sample_repo_evidence

    def test_from_dict_missing_files(self) -> None:
        d = {"repo": "r", "branch": "b", "commit": "abc1234"}
        re = RepoEvidence.from_dict(d)
        assert re.files_touched == []


class TestVerificationResult:
    def test_to_dict(self, sample_verification_result: VerificationResult) -> None:
        d = sample_verification_result.to_dict()
        assert d["command"] == "pytest tests/ -x -q"
        assert d["result"] == "pass"
        assert d["summary"] == "42 tests passed"

    def test_round_trip(self, sample_verification_result: VerificationResult) -> None:
        d = sample_verification_result.to_dict()
        restored = VerificationResult.from_dict(d)
        assert restored == sample_verification_result

    @pytest.mark.parametrize("result_val", ["pass", "fail", "skip"])
    def test_valid_results(self, result_val: str) -> None:
        vr = VerificationResult(command="cmd", result=result_val, summary="s")
        assert vr.result == result_val


class TestReviewApproval:
    def test_to_dict(self, sample_review_approval: ReviewApproval) -> None:
        d = sample_review_approval.to_dict()
        assert d["reviewer"] == "reviewer-1"
        assert d["verdict"] == "approved"
        assert d["reference"] == "review-ref-001"

    def test_round_trip(self, sample_review_approval: ReviewApproval) -> None:
        d = sample_review_approval.to_dict()
        restored = ReviewApproval.from_dict(d)
        assert restored == sample_review_approval

    @pytest.mark.parametrize("verdict", ["approved", "changes_requested"])
    def test_verdicts(self, verdict: str) -> None:
        ra = ReviewApproval(reviewer="r", verdict=verdict, reference="ref")
        assert ra.verdict == verdict


class TestDoneEvidence:
    def test_requires_review(self) -> None:
        with pytest.raises(KeyError):
            DoneEvidence.from_dict({})

    def test_to_dict_minimal(self, sample_review_approval: ReviewApproval) -> None:
        de = DoneEvidence(review=sample_review_approval)
        d = de.to_dict()
        assert "review" in d
        assert "repos" not in d
        assert "verification" not in d

    def test_to_dict_with_all_fields(self, sample_done_evidence: DoneEvidence) -> None:
        d = sample_done_evidence.to_dict()
        assert "review" in d
        assert "repos" in d
        assert "verification" in d
        assert len(d["repos"]) == 1
        assert len(d["verification"]) == 1

    def test_round_trip(self, sample_done_evidence: DoneEvidence) -> None:
        d = sample_done_evidence.to_dict()
        restored = DoneEvidence.from_dict(d)
        assert restored == sample_done_evidence


class TestStatusEvent:
    def test_creation_valid(self, sample_status_event: StatusEvent) -> None:
        assert sample_status_event.event_id == "01HXYZ0123456789ABCDEFGHJK"
        assert sample_status_event.from_lane is Lane.PLANNED
        assert sample_status_event.to_lane is Lane.CLAIMED
        assert sample_status_event.force is False

    def test_to_dict_round_trip(self, sample_status_event: StatusEvent) -> None:
        d = sample_status_event.to_dict()
        restored = StatusEvent.from_dict(d)
        assert restored == sample_status_event

    def test_to_dict_serializes_lane_as_string(self, sample_status_event: StatusEvent) -> None:
        d = sample_status_event.to_dict()
        assert d["from_lane"] == "planned"
        assert d["to_lane"] == "claimed"
        assert isinstance(d["from_lane"], str)

    def test_to_dict_with_evidence(self, sample_status_event_with_evidence: StatusEvent) -> None:
        d = sample_status_event_with_evidence.to_dict()
        assert d["evidence"] is not None
        assert d["evidence"]["review"]["reviewer"] == "reviewer-1"

    def test_round_trip_with_evidence(self, sample_status_event_with_evidence: StatusEvent) -> None:
        d = sample_status_event_with_evidence.to_dict()
        restored = StatusEvent.from_dict(d)
        assert restored == sample_status_event_with_evidence

    def test_none_evidence_serializes_as_none(self, sample_status_event: StatusEvent) -> None:
        d = sample_status_event.to_dict()
        assert d["evidence"] is None

    def test_from_dict_converts_string_lanes(self) -> None:
        d = {
            "event_id": "01HXYZ0123456789ABCDEFGHJK",
            "mission_slug": "034-feature",
            "wp_id": "WP01",
            "from_lane": "planned",
            "to_lane": "claimed",
            "at": "2026-02-08T12:00:00Z",
            "actor": "agent",
            "force": False,
            "execution_mode": "worktree",
        }
        event = StatusEvent.from_dict(d)
        assert event.from_lane is Lane.PLANNED
        assert event.to_lane is Lane.CLAIMED

    def test_ulid_pattern_matches_event_id(self, sample_status_event: StatusEvent) -> None:
        assert ULID_PATTERN.match(sample_status_event.event_id)

    def test_force_event_with_reason(self) -> None:
        event = StatusEvent(
            event_id="01HXYZ0123456789ABCDEFGHJK",
            mission_slug="034-feature",
            wp_id="WP01",
            from_lane=Lane.DONE,
            to_lane=Lane.IN_PROGRESS,
            at="2026-02-08T12:00:00Z",
            actor="admin",
            force=True,
            execution_mode="direct_repo",
            reason="reopening for rework",
        )
        d = event.to_dict()
        assert d["force"] is True
        assert d["reason"] == "reopening for rework"

    def test_review_ref_event(self) -> None:
        event = StatusEvent(
            event_id="01HXYZ0123456789ABCDEFGHJK",
            mission_slug="034-feature",
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2026-02-08T12:00:00Z",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref="review-feedback-123",
        )
        d = event.to_dict()
        assert d["review_ref"] == "review-feedback-123"
        restored = StatusEvent.from_dict(d)
        assert restored.review_ref == "review-feedback-123"


class TestStatusSnapshot:
    def test_to_dict_round_trip(self, sample_status_snapshot: StatusSnapshot) -> None:
        d = sample_status_snapshot.to_dict()
        restored = StatusSnapshot.from_dict(d)
        assert restored.mission_slug == sample_status_snapshot.mission_slug
        assert restored.event_count == sample_status_snapshot.event_count
        assert restored.work_packages == sample_status_snapshot.work_packages
        assert restored.summary == sample_status_snapshot.summary

    def test_summary_has_all_lane_keys(self, sample_status_snapshot: StatusSnapshot) -> None:
        # 'genesis' and 'uninitialized' are non-display lanes: neither ever
        # appears as the current lane of a materialized WP, so both are
        # excluded from board/summary surfaces (NON_DISPLAY_LANES).
        expected_keys = {str(lane) for lane in Lane if lane not in NON_DISPLAY_LANES}
        assert set(sample_status_snapshot.summary.keys()) == expected_keys

    def test_summary_counts_match_work_packages(self, sample_status_snapshot: StatusSnapshot) -> None:
        total_wps = len(sample_status_snapshot.work_packages)
        total_summary = sum(sample_status_snapshot.summary.values())
        assert total_summary == total_wps

    def test_empty_snapshot(self) -> None:
        snap = StatusSnapshot(
            mission_slug="001-test",
            materialized_at="2026-01-01T00:00:00Z",
            event_count=0,
            last_event_id=None,
            work_packages={},
            summary={lane.value: 0 for lane in Lane},
        )
        d = snap.to_dict()
        assert d["event_count"] == 0
        assert d["last_event_id"] is None
        assert d["work_packages"] == {}

    def test_from_dict_requires_mission_slug(self) -> None:
        data = {
            "materialized_at": "2026-01-01T00:00:00Z",
            "event_count": 0,
            "last_event_id": None,
            "work_packages": {},
            "summary": {
                "planned": 0,
                "claimed": 0,
                "in_progress": 0,
                "for_review": 0,
                "approved": 0,
                "done": 0,
                "blocked": 0,
                "canceled": 0,
            },
        }

        with pytest.raises(KeyError, match="mission_slug"):
            StatusSnapshot.from_dict(data)


class TestStatusEventSummaryRoundTrip:
    """#4327: the optional ``summary`` survives the JSONL round trip, stays
    absent for every event persisted before the field existed, and never
    rewrites a legacy line's bytes."""

    def test_summary_round_trips_through_to_dict_from_dict(self, sample_status_event: StatusEvent) -> None:
        event = replace(sample_status_event, summary="Claimed after the interview answers")
        d = event.to_dict()
        assert d["summary"] == "Claimed after the interview answers"
        assert StatusEvent.from_dict(d) == event

    def test_absent_summary_stays_absent_and_off_the_wire_line(self, sample_status_event: StatusEvent) -> None:
        # A summary-less event serialises WITHOUT the key (byte-compat with
        # every pre-#4327 persisted line), and decodes back to None.
        d = sample_status_event.to_dict()
        assert "summary" not in d
        assert StatusEvent.from_dict(d).summary is None

    def test_legacy_persisted_line_without_summary_decodes_as_none(self) -> None:
        legacy = {
            "event_id": "01HXYZ0123456789ABCDEFGHJK",
            "mission_slug": "034-test-feature",
            "wp_id": "WP01",
            "from_lane": "in_review",
            "to_lane": "approved",
            "at": "2026-01-01T00:00:00+00:00",
            "actor": "reviewer",
            "force": False,
            "execution_mode": "worktree",
            # Prose in review_ref: legal on any event persisted before #4327
            # -- legacy decoding stays compatible, no history rewrite.
            "review_ref": "Looks good to me, ship it after the focus-time fix",
        }
        event = StatusEvent.from_dict(legacy)
        assert event.summary is None
        assert event.review_ref == "Looks good to me, ship it after the focus-time fix"
