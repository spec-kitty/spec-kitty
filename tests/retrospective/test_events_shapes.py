"""Tests for retrospective event payload shapes (T013).

Verifies:
- Each payload model validates with required fields.
- Each payload model rejects extra fields (extra='forbid').
- The eight event names do not collide with existing mission event names.
- RETROSPECTIVE_EVENT_NAMES contains exactly the eight stable names.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from spec_kitty_events import retrospective as upstream_retrospective

from specify_cli.retrospective.events import (
    RETROSPECTIVE_EVENT_NAMES,
    CompletedPayload,
    FailedPayload,
    ProposalAppliedPayload,
    ProposalGeneratedPayload,
    ProposalRejectedPayload,
    RequestedPayload,
    SkippedPayload,
    StartedPayload,
)
from specify_cli.retrospective.schema import ActorRef, Mode, ModeSourceSignal

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_RUNTIME_ACTOR = ActorRef(kind="runtime", id="spec-kitty-runtime", profile_id=None)
_HUMAN_ACTOR = ActorRef(kind="human", id="operator-01", profile_id=None)
_AGENT_ACTOR = ActorRef(kind="agent", id="claude", profile_id="retrospective-facilitator")

_MODE = Mode(
    value="autonomous",
    source_signal=ModeSourceSignal(kind="environment", evidence="SK_MODE=autonomous"),
)


# ---------------------------------------------------------------------------
# RequestedPayload
# ---------------------------------------------------------------------------


class TestRequestedPayload:
    def test_valid(self) -> None:
        p = RequestedPayload(
            mode=_MODE,
            terminus_step_id="step-final",
            requested_by=_RUNTIME_ACTOR,
        )
        assert p.terminus_step_id == "step-final"

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            RequestedPayload(
                mode=_MODE,
                terminus_step_id="step-final",
                requested_by=_RUNTIME_ACTOR,
                extra_field="bad",  # type: ignore[call-arg]
            )

    def test_requires_mode(self) -> None:
        with pytest.raises(ValidationError):
            RequestedPayload(
                terminus_step_id="step-final",
                requested_by=_RUNTIME_ACTOR,
            )  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# StartedPayload
# ---------------------------------------------------------------------------


class TestStartedPayload:
    def test_valid(self) -> None:
        p = StartedPayload(
            facilitator_profile_id="retrospective-facilitator",
            action_id="retrospect",
        )
        assert p.facilitator_profile_id == "retrospective-facilitator"

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            StartedPayload(
                facilitator_profile_id="retrospective-facilitator",
                action_id="retrospect",
                extra_field="bad",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# CompletedPayload
# ---------------------------------------------------------------------------


class TestCompletedPayload:
    def test_valid(self) -> None:
        p = CompletedPayload(
            record_path="/kitty-specs/mission-foo/retrospective.yaml",
            record_hash="abc123",
            findings_summary={"helped": 2, "not_helpful": 1, "gaps": 3},
            proposals_count=5,
        )
        assert p.proposals_count == 5
        assert p.findings_summary["helped"] == 2

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            CompletedPayload(
                record_path="/path",
                record_hash="abc",
                findings_summary={},
                proposals_count=0,
                extra_field="bad",  # type: ignore[call-arg]
            )

    def test_requires_all_fields(self) -> None:
        with pytest.raises(ValidationError):
            CompletedPayload(record_path="/path")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# SkippedPayload
# ---------------------------------------------------------------------------


class TestSkippedPayload:
    def test_valid(self) -> None:
        p = SkippedPayload(
            record_path="/path/to/skip.yaml",
            skip_reason="No time this sprint",
            skipped_by=_HUMAN_ACTOR,
        )
        assert p.skip_reason == "No time this sprint"

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            SkippedPayload(
                record_path="/path",
                skip_reason="reason",
                skipped_by=_HUMAN_ACTOR,
                extra_field="bad",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# FailedPayload
# ---------------------------------------------------------------------------


class TestFailedPayload:
    def test_valid_with_record_path(self) -> None:
        p = FailedPayload(
            failure_code="writer_io_error",
            message="Could not write file",
            record_path="/partial.yaml",
        )
        assert p.record_path == "/partial.yaml"

    def test_valid_without_record_path(self) -> None:
        p = FailedPayload(
            failure_code="internal_error",
            message="Unknown error",
        )
        assert p.record_path is None

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            FailedPayload(
                failure_code="internal_error",
                message="err",
                extra_field="bad",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# ProposalGeneratedPayload
# ---------------------------------------------------------------------------


class TestProposalGeneratedPayload:
    def test_valid(self) -> None:
        p = ProposalGeneratedPayload(
            proposal_id="01KQ73CS2CCFY8BYYTTFV58FJT",
            kind="synthesize_directive",
            record_path="/retro.yaml",
        )
        assert p.kind == "synthesize_directive"

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            ProposalGeneratedPayload(
                proposal_id="01KQ73CS2CCFY8BYYTTFV58FJT",
                kind="synthesize_directive",
                record_path="/retro.yaml",
                extra_field="bad",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# ProposalAppliedPayload
# ---------------------------------------------------------------------------


class TestProposalAppliedPayload:
    def test_valid(self) -> None:
        p = ProposalAppliedPayload(
            proposal_id="01KQ73CS2CCFY8BYYTTFV58FJT",
            kind="add_glossary_term",
            target_urn="glossary:term:foo",
            provenance_ref="provenance:urn:bar",
            applied_by=_RUNTIME_ACTOR,
        )
        assert p.target_urn == "glossary:term:foo"

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            ProposalAppliedPayload(
                proposal_id="01KQ73CS2CCFY8BYYTTFV58FJT",
                kind="add_glossary_term",
                target_urn="glossary:term:foo",
                provenance_ref="provenance:urn:bar",
                applied_by=_RUNTIME_ACTOR,
                extra_field="bad",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# ProposalRejectedPayload
# ---------------------------------------------------------------------------


class TestProposalRejectedPayload:
    def test_valid_human_decline(self) -> None:
        p = ProposalRejectedPayload(
            proposal_id="01KQ73CS2CCFY8BYYTTFV58FJT",
            kind="synthesize_directive",
            reason="human_decline",
            detail="Not aligned with doctrine",
            rejected_by=_HUMAN_ACTOR,
        )
        assert p.reason == "human_decline"

    def test_valid_conflict(self) -> None:
        p = ProposalRejectedPayload(
            proposal_id="01KQ73CS2CCFY8BYYTTFV58FJT",
            kind="rewire_edge",
            reason="conflict",
            detail="Conflicting edge already exists",
            rejected_by=_RUNTIME_ACTOR,
        )
        assert p.reason == "conflict"

    def test_rejects_invalid_reason(self) -> None:
        with pytest.raises(ValidationError):
            ProposalRejectedPayload(
                proposal_id="01KQ73CS2CCFY8BYYTTFV58FJT",
                kind="rewire_edge",
                reason="not_a_valid_reason",  # type: ignore[arg-type]
                detail="some detail",
                rejected_by=_RUNTIME_ACTOR,
            )

    def test_rejects_extra(self) -> None:
        with pytest.raises(ValidationError):
            ProposalRejectedPayload(
                proposal_id="01KQ73CS2CCFY8BYYTTFV58FJT",
                kind="rewire_edge",
                reason="stale_evidence",
                detail="stale",
                rejected_by=_RUNTIME_ACTOR,
                extra_field="bad",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# RETROSPECTIVE_EVENT_NAMES constant
# ---------------------------------------------------------------------------


class TestRetroEventNames:
    def test_contains_expected_names(self) -> None:
        expected = {
            "retrospective.requested",
            "retrospective.started",
            "retrospective.completed",
            "retrospective.skipped",
            "retrospective.failed",
            "retrospective.proposal.generated",
            "retrospective.proposal.applied",
            "retrospective.proposal.rejected",
        }
        assert expected == RETROSPECTIVE_EVENT_NAMES

    def test_is_frozenset(self) -> None:
        assert isinstance(RETROSPECTIVE_EVENT_NAMES, frozenset)

    def test_matches_upstream_registry(self) -> None:
        # spec_kitty_events is a declared dependency (pyproject.toml pins
        # spec-kitty-events>=10.4.0), which already ships RETROSPECTIVE_EVENT_NAMES —
        # both its absence and an unimportable module are a stale-venv defect
        # (FR-004), not a platform condition, so neither is a skip any more.
        upstream_names = getattr(
            upstream_retrospective,
            "RETROSPECTIVE_EVENT_NAMES",
            None,
        )
        assert upstream_names is not None, (
            "spec_kitty_events.retrospective is missing RETROSPECTIVE_EVENT_NAMES; "
            "the declared floor spec-kitty-events>=10.4.0 ships it — re-sync the "
            "venv (uv sync --frozen --all-extras)"
        )

        assert upstream_names == RETROSPECTIVE_EVENT_NAMES

    def test_no_collision_with_lane_values(self) -> None:
        """Retrospective event names must not overlap with 9-lane state values."""
        from specify_cli.status.models import get_all_lane_values

        lane_values = get_all_lane_values()
        # Lane values are strings like "planned", "claimed", etc. — no dots.
        # Retrospective names all contain dots. Zero overlap expected.
        overlap = RETROSPECTIVE_EVENT_NAMES & lane_values
        assert not overlap, f"Unexpected overlap between retro event names and lane values: {overlap}"

    def test_all_names_start_with_retrospective(self) -> None:
        for name in RETROSPECTIVE_EVENT_NAMES:
            assert name.startswith("retrospective."), f"{name!r} does not start with 'retrospective.'"
