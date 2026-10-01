"""Tests for T039 / FR-010 (F-04): retrospective event-log mining heuristics.

These cover the new detectors added by WP10:
- ``_detect_force_overrides``  — operator-driven --force events (not bootstrap)
- ``_detect_arbiter_overrides`` — events whose note/reason mentions "arbiter"
- ``_detect_implementation_cycles`` — WPs that needed >1 planned→in_progress

The detectors must be pure functions over the event dicts and must NOT regress
the existing empty-output behaviour (a clean event log yields no findings).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


from specify_cli.retrospective.generator import (
    _detect_arbiter_overrides,
    _detect_force_overrides,
    _detect_implementation_cycles,
    _detect_lane_friction,
    _is_arbiter_event,
    _is_force_override_event,
)


# ---------------------------------------------------------------------------
# _detect_force_overrides
# ---------------------------------------------------------------------------


class TestForceOverrideDetection:
    def test_finalize_tasks_force_is_excluded(self) -> None:
        """Bootstrap actors emit force=True legitimately; must NOT count."""
        events = [
            {
                "wp_id": "WP01",
                "actor": "finalize-tasks",
                "force": True,
                "from_lane": "planned",
                "to_lane": "planned",
                "event_id": "e1",
            },
        ]
        assert _detect_force_overrides(events) == {}

    def test_operator_force_counts(self) -> None:
        """User-driven --force on a real transition is an override."""
        events = [
            {
                "wp_id": "WP02",
                "actor": "claude",
                "force": True,
                "from_lane": "approved",
                "to_lane": "planned",
                "event_id": "e2",
            },
        ]
        assert _detect_force_overrides(events) == {"WP02": 1}

    def test_multiple_force_overrides_per_wp(self) -> None:
        events = [
            {
                "wp_id": "WP03",
                "actor": "claude",
                "force": True,
                "from_lane": "for_review",
                "to_lane": "in_progress",
                "event_id": "e3",
            },
            {
                "wp_id": "WP03",
                "actor": "user",
                "force": True,
                "from_lane": "approved",
                "to_lane": "planned",
                "event_id": "e4",
            },
        ]
        assert _detect_force_overrides(events) == {"WP03": 2}

    def test_documented_rejection_force_is_excluded(self) -> None:
        """#2267: the --force a documented rejection requires is no guard bypass."""
        events = [
            {
                "wp_id": "WP07",
                "actor": "reviewer",
                "force": True,
                "from_lane": "in_review",
                "to_lane": "planned",
                "review_ref": "review-cycle://m/WP07/review-cycle-1.md",
                "event_id": "f7",
            },
            {
                "wp_id": "WP07",
                "actor": "user",
                "force": True,
                "from_lane": "for_review",
                "to_lane": "in_progress",
                "review_ref": "force-override",
                "event_id": "f8",
            },
        ]
        assert _detect_force_overrides(events) == {"WP07": 1}

    @pytest.mark.parametrize("marker", ["action-review-claim", "workflow-review-claim"])
    def test_review_claim_force_is_excluded(self, marker: str) -> None:
        """#2267: a reviewer's forced for_review -> in_progress claim is the review path."""
        event = {
            "wp_id": "WP08",
            "actor": "reviewer",
            "force": True,
            "from_lane": "for_review",
            "to_lane": "in_progress",
            "review_ref": marker,
            "event_id": "f9",
        }
        assert _detect_force_overrides([event]) == {}
        assert _detect_lane_friction([event]) == {}

    def test_no_op_force_is_excluded(self) -> None:
        """force=True with from_lane == to_lane carries no signal."""
        events = [
            {
                "wp_id": "WP04",
                "actor": "claude",
                "force": True,
                "from_lane": "in_progress",
                "to_lane": "in_progress",
                "event_id": "e5",
            },
        ]
        assert _detect_force_overrides(events) == {}

    def test_force_false_is_excluded(self) -> None:
        events = [
            {
                "wp_id": "WP05",
                "actor": "claude",
                "force": False,
                "from_lane": "planned",
                "to_lane": "in_progress",
                "event_id": "e6",
            },
        ]
        assert _detect_force_overrides(events) == {}

    def test_is_force_override_event_predicate(self) -> None:
        """The predicate itself is the deciding gate."""
        good = {
            "wp_id": "WP10",
            "actor": "claude",
            "force": True,
            "from_lane": "approved",
            "to_lane": "planned",
        }
        bootstrap = {
            "wp_id": "WP10",
            "actor": "finalize-tasks",
            "force": True,
            "from_lane": "planned",
            "to_lane": "planned",
        }
        assert _is_force_override_event(good) is True
        assert _is_force_override_event(bootstrap) is False


# ---------------------------------------------------------------------------
# _detect_arbiter_overrides
# ---------------------------------------------------------------------------


class TestArbiterOverrideDetection:
    def test_reason_contains_arbiter(self) -> None:
        events = [
            {
                "wp_id": "WP01",
                "actor": "claude",
                "reason": "Arbiter override after deadlock",
                "from_lane": "for_review",
                "to_lane": "approved",
                "event_id": "a1",
            },
        ]
        assert _detect_arbiter_overrides(events) == {"WP01": 1}

    def test_evidence_note_contains_arbiter(self) -> None:
        events = [
            {
                "wp_id": "WP02",
                "actor": "user",
                "evidence": {"note": "Arbiter intervened to break tie."},
                "from_lane": "for_review",
                "to_lane": "approved",
                "event_id": "a2",
            },
        ]
        assert _detect_arbiter_overrides(events) == {"WP02": 1}

    def test_no_arbiter_marker(self) -> None:
        events = [
            {
                "wp_id": "WP03",
                "actor": "claude",
                "reason": "Reviewer approved.",
                "from_lane": "for_review",
                "to_lane": "approved",
                "event_id": "a3",
            },
        ]
        assert _detect_arbiter_overrides(events) == {}

    def test_case_insensitive_match(self) -> None:
        events = [
            {
                "wp_id": "WP04",
                "actor": "user",
                "reason": "ARBITER OVERRIDE was required.",
                "from_lane": "for_review",
                "to_lane": "approved",
                "event_id": "a4",
            },
        ]
        assert _is_arbiter_event(events[0]) is True
        assert _detect_arbiter_overrides(events) == {"WP04": 1}

    def test_lane_hops_of_one_invocation_count_as_one_override(self) -> None:
        """#3793: move-task emits one event per lane hop, all sharing the
        operator's reason — a single override from for_review to approved
        spans two hops and must count once, not twice."""
        events = [
            {
                "wp_id": "WP05",
                "actor": "user",
                "reason": "Arbiter override: WP05 was reviewed and approved at cycle 2",
                "from_lane": "for_review",
                "to_lane": "in_review",
                "event_id": "65",
            },
            {
                "wp_id": "WP05",
                "actor": "user",
                "reason": "Arbiter override: WP05 was reviewed and approved at cycle 2",
                "from_lane": "in_review",
                "to_lane": "approved",
                "event_id": "66",
            },
        ]
        assert _detect_arbiter_overrides(events) == {"WP05": 1}

    def test_three_hop_override_from_in_progress_counts_once(self) -> None:
        """#3793: the same override issued from in_progress hops through
        for_review and in_review before approved — still one decision."""
        reason = "Arbiter override: skip review"
        events = [
            {
                "wp_id": "WP06",
                "actor": "user",
                "reason": reason,
                "from_lane": "in_progress",
                "to_lane": "for_review",
                "event_id": "b1",
            },
            {
                "wp_id": "WP06",
                "actor": "user",
                "reason": reason,
                "from_lane": "for_review",
                "to_lane": "in_review",
                "event_id": "b2",
            },
            {
                "wp_id": "WP06",
                "actor": "user",
                "reason": reason,
                "from_lane": "in_review",
                "to_lane": "approved",
                "event_id": "b3",
            },
        ]
        assert _detect_arbiter_overrides(events) == {"WP06": 1}

    def test_distinct_overrides_on_same_wp_count_separately(self) -> None:
        """Two genuinely separate decisions carry different operator reasons."""
        events = [
            {
                "wp_id": "WP07",
                "actor": "user",
                "reason": "Arbiter override: deadlock at cycle 1",
                "from_lane": "for_review",
                "to_lane": "approved",
                "event_id": "c1",
            },
            {
                "wp_id": "WP07",
                "actor": "user",
                "reason": "Arbiter override: re-approval after rework",
                "from_lane": "in_review",
                "to_lane": "approved",
                "event_id": "c2",
            },
        ]
        assert _detect_arbiter_overrides(events) == {"WP07": 2}

    def test_same_reason_on_different_wps_counts_per_wp(self) -> None:
        """The (wp_id, reason) group key keeps distinct WPs distinct."""
        events = [
            {
                "wp_id": "WP08",
                "actor": "user",
                "reason": "Arbiter override: batch approval",
                "from_lane": "for_review",
                "to_lane": "approved",
                "event_id": "d1",
            },
            {
                "wp_id": "WP09",
                "actor": "user",
                "reason": "Arbiter override: batch approval",
                "from_lane": "for_review",
                "to_lane": "approved",
                "event_id": "d2",
            },
        ]
        assert _detect_arbiter_overrides(events) == {"WP08": 1, "WP09": 1}


# ---------------------------------------------------------------------------
# _detect_implementation_cycles
# ---------------------------------------------------------------------------


class TestImplementationCycleDetection:
    def test_single_cycle_is_not_reported(self) -> None:
        """One implementation cycle is normal flow; only multi-cycle is interesting."""
        events = [
            {
                "wp_id": "WP01",
                "actor": "claude",
                "from_lane": "planned",
                "to_lane": "in_progress",
                "event_id": "i1",
            },
        ]
        assert _detect_implementation_cycles(events) == {}

    def test_multiple_cycles_reported(self) -> None:
        events = [
            {
                "wp_id": "WP02",
                "actor": "claude",
                "from_lane": "planned",
                "to_lane": "in_progress",
                "event_id": "i2",
            },
            {
                "wp_id": "WP02",
                "actor": "claude",
                "from_lane": "claimed",
                "to_lane": "in_progress",
                "event_id": "i3",
            },
            {
                "wp_id": "WP02",
                "actor": "claude",
                "from_lane": "planned",
                "to_lane": "in_progress",
                "event_id": "i4",
            },
        ]
        # Three entries, none explained by a documented rejection: two re-entries.
        assert _detect_implementation_cycles(events) == {"WP02": 2}

    def test_reentry_after_documented_rejection_is_expected(self) -> None:
        """#2267: a documented rejection licenses the next re-entry."""
        ref = "review-cycle://m/WP04/review-cycle-1.md"
        events = [
            {"wp_id": "WP04", "actor": "a", "from_lane": "planned", "to_lane": "in_progress"},
            {"wp_id": "WP04", "actor": "r", "from_lane": "for_review", "to_lane": "planned", "force": True, "review_ref": ref},
            {"wp_id": "WP04", "actor": "a", "from_lane": "planned", "to_lane": "in_progress"},
        ]
        assert _detect_implementation_cycles(events) == {}

    def test_sentinel_review_ref_does_not_license(self) -> None:
        """A ``force-override`` sentinel is no feedback: the re-entry is undocumented."""
        events = [
            {"wp_id": "WP05", "actor": "a", "from_lane": "planned", "to_lane": "in_progress"},
            {"wp_id": "WP05", "actor": "u", "from_lane": "for_review", "to_lane": "planned", "force": True, "review_ref": "force-override"},
            {"wp_id": "WP05", "actor": "a", "from_lane": "planned", "to_lane": "in_progress"},
        ]
        assert _detect_implementation_cycles(events) == {"WP05": 1}

    def test_rejection_into_in_progress_consumes_its_licence(self) -> None:
        """An in_review -> in_progress rejection is the re-entry; it licenses nothing later."""
        ref = "review-cycle://m/WP06/review-cycle-1.md"
        events = [
            {"wp_id": "WP06", "actor": "a", "from_lane": "planned", "to_lane": "in_progress"},
            {"wp_id": "WP06", "actor": "r", "from_lane": "in_review", "to_lane": "in_progress", "review_ref": ref},
            {"wp_id": "WP06", "actor": "a", "from_lane": "in_progress", "to_lane": "blocked"},
            {"wp_id": "WP06", "actor": "u", "from_lane": "blocked", "to_lane": "planned", "force": True},
            {"wp_id": "WP06", "actor": "a", "from_lane": "planned", "to_lane": "in_progress"},
        ]
        assert _detect_implementation_cycles(events) == {"WP06": 1}

    def test_finalize_tasks_excluded(self) -> None:
        events = [
            {
                "wp_id": "WP03",
                "actor": "finalize-tasks",
                "from_lane": "planned",
                "to_lane": "in_progress",
                "event_id": "i5",
            },
            {
                "wp_id": "WP03",
                "actor": "finalize-tasks",
                "from_lane": "planned",
                "to_lane": "in_progress",
                "event_id": "i6",
            },
        ]
        assert _detect_implementation_cycles(events) == {}


# ---------------------------------------------------------------------------
# Empty-event-log regression guard (FR-010 stability invariant)
# ---------------------------------------------------------------------------


class TestEmptyLogStability:
    def test_no_events_yields_no_findings(self) -> None:
        assert _detect_force_overrides([]) == {}
        assert _detect_arbiter_overrides([]) == {}
        assert _detect_implementation_cycles([]) == {}

    def test_events_without_wp_id_are_skipped(self) -> None:
        """Mission-level events (no wp_id) must not break the detectors."""
        events = [
            {"actor": "user", "force": True, "from_lane": "x", "to_lane": "y"},
            {"actor": "user", "reason": "arbiter ruling"},
        ]
        assert _detect_force_overrides(events) == {}
        assert _detect_arbiter_overrides(events) == {}
        assert _detect_implementation_cycles(events) == {}
