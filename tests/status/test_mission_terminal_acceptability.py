"""RED-first truth-table tests for the shared mission-terminal-readiness aggregate.

Mission ``terminus-safety-invariant-01M2XFT7``, WP01 (T001). Spec FR-009, US4;
contract ``contracts/terminus-safety-contract.md`` -> ``C-SHARED-AUTHORITY``;
data-model ``mission_terminal_acceptability(work_packages) -> (ok, missing_wp_ids)``.

``mission_terminal_acceptability`` is a pure, provenance-aware aggregate over a
``StatusSnapshot.work_packages``-shaped mapping (WP id -> reduced snapshot dict
carrying at least a ``lane`` key and, for canceled WPs, an optional
``reason_source`` provenance slot). It reuses the single shared per-lane
authority :func:`~specify_cli.status_lanes.is_acceptable_ending` and the
provenance reader :func:`~specify_cli.status_lanes.has_operator_provenance` —
it must NOT re-derive the acceptable-ending rule (C-001).

These tests are RED until T002 adds the function to ``status_lanes.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.status_lanes import OPERATOR_REASON_SOURCE, mission_terminal_acceptability

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _wp(lane: str, *, reason_source: str | None = None) -> dict[str, Any]:
    """Build a reduced WP snapshot dict in the shape ``StatusSnapshot.work_packages`` uses."""
    snapshot: dict[str, Any] = {"lane": lane}
    if reason_source is not None:
        snapshot["reason_source"] = reason_source
    return snapshot


def _operator_canceled() -> dict[str, Any]:
    return _wp("canceled", reason_source=OPERATOR_REASON_SOURCE)


def _synthetic_canceled() -> dict[str, Any]:
    return _wp("canceled", reason_source="auto")


class TestAllAcceptableEndings:
    def test_every_wp_approved_is_ready(self) -> None:
        work_packages = {
            "WP01": _wp("approved"),
            "WP02": _wp("approved"),
        }

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is True
        assert missing == []

    def test_every_wp_done_is_ready(self) -> None:
        work_packages = {
            "WP01": _wp("done"),
            "WP02": _wp("done"),
        }

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is True
        assert missing == []


class TestProvenanceAwareCancellation:
    """US4-2 / US1-6: provenance is the load-bearing distinguisher for ``canceled``."""

    @pytest.mark.regression
    def test_canceled_with_operator_provenance_is_acceptable(self) -> None:
        # US4-2: a documented cancellation is an acceptable mission ending under
        # every completion command.
        work_packages = {
            "WP01": _wp("approved"),
            "WP02": _operator_canceled(),
        }

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is True
        assert "WP02" not in missing
        assert missing == []

    @pytest.mark.regression
    def test_canceled_without_operator_provenance_is_not_ready(self) -> None:
        # US1-6: a synthetic (undocumented) cancellation must NOT be laundered
        # into an acceptable ending — the operator-provenance check is
        # load-bearing and must not be dropped.
        work_packages = {
            "WP01": _wp("approved"),
            "WP02": _synthetic_canceled(),
        }

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is False
        assert missing == ["WP02"]

    @pytest.mark.regression
    def test_canceled_with_no_reason_source_key_is_not_ready(self) -> None:
        # A legacy/absent ``reason_source`` slot must read as "no provenance",
        # per ``has_operator_provenance``'s documented default.
        work_packages = {"WP01": _wp("canceled")}

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is False
        assert missing == ["WP01"]


class TestActiveLanesAreNotReady:
    @pytest.mark.parametrize("lane", ["in_progress", "for_review", "planned", "claimed", "in_review", "blocked"])
    def test_active_lane_is_not_ready(self, lane: str) -> None:
        work_packages = {"WP01": _wp(lane)}

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is False
        assert missing == ["WP01"]


class TestMixedMission:
    def test_one_unapproved_wp_among_approved_is_reported(self) -> None:
        work_packages = {
            "WP01": _wp("approved"),
            "WP02": _wp("done"),
            "WP03": _wp("in_progress"),
        }

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is False
        assert missing == ["WP03"]

    def test_missing_wp_ids_are_sorted_deterministically(self) -> None:
        work_packages = {
            "WP05": _wp("in_progress"),
            "WP01": _wp("planned"),
            "WP03": _wp("approved"),
        }

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is False
        assert missing == ["WP01", "WP05"]


class TestBoundaries:
    def test_empty_mission_is_vacuously_ready(self) -> None:
        # No WPs to check -> nothing is missing, matching the merge-ready
        # boundary in the spec's Edge Cases (an empty non-cancelled WP set is
        # trivially all-acceptable).
        ok, missing = mission_terminal_acceptability({})

        assert ok is True
        assert missing == []

    def test_all_canceled_with_provenance_is_ready(self) -> None:
        # Every WP acceptably canceled -> the whole mission is a ready
        # boundary case, matching the merge-ready boundary in spec Edge Cases.
        work_packages = {
            "WP01": _operator_canceled(),
            "WP02": _operator_canceled(),
        }

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is True
        assert missing == []


class TestExpectedWpIdsFailClosed:
    """Landing-pass remediation (dedup fold, #4764): the "declared-but-absent
    -from-snapshot WP is NOT ready" rule now lives in this ONE shared
    aggregate via the optional ``expected_wp_ids`` keyword, instead of being
    re-derived by each caller (``merge.executor``) or re-inlined by
    ``policy.merge_gates``'s evidence gate."""

    def test_default_none_preserves_prior_behavior(self) -> None:
        # Omitting expected_wp_ids must be byte-for-byte the pre-existing
        # behavior: only WPs actually present in work_packages are checked.
        work_packages = {"WP01": _wp("approved")}

        ok, missing = mission_terminal_acceptability(work_packages)

        assert ok is True
        assert missing == []

    def test_declared_wp_absent_from_snapshot_is_not_ready(self) -> None:
        # WP02 is declared (expected) but has no entry in work_packages at
        # all -- strictly less evidence of readiness than an in_progress
        # entry, so it must fail closed, not be silently dropped.
        work_packages = {"WP01": _wp("approved")}

        ok, missing = mission_terminal_acceptability(work_packages, expected_wp_ids=["WP01", "WP02"])

        assert ok is False
        assert missing == ["WP02"]

    def test_all_expected_present_and_acceptable_is_ready(self) -> None:
        work_packages = {
            "WP01": _wp("approved"),
            "WP02": _wp("done"),
        }

        ok, missing = mission_terminal_acceptability(work_packages, expected_wp_ids=["WP01", "WP02"])

        assert ok is True
        assert missing == []

    def test_absent_and_in_snapshot_missing_are_merged_and_sorted(self) -> None:
        work_packages = {
            "WP01": _wp("approved"),
            "WP03": _wp("in_progress"),
        }

        ok, missing = mission_terminal_acceptability(work_packages, expected_wp_ids=["WP01", "WP02", "WP03"])

        assert ok is False
        assert missing == ["WP02", "WP03"]

    def test_empty_expected_wp_ids_collection_is_a_noop(self) -> None:
        work_packages = {"WP01": _wp("approved")}

        ok, missing = mission_terminal_acceptability(work_packages, expected_wp_ids=[])

        assert ok is True
        assert missing == []
