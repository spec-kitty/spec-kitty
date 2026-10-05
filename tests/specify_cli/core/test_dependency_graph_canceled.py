"""Dependency-on-canceled closure at the claim gate (WP04, T016).

FR-009 / SC-005: a ``canceled`` dependency that carries operator-authored
provenance is a documented removal — its dependent must be claimable and able to
reach an acceptable ending. A ``canceled`` dependency *without* provenance (a
synthetic, undocumented cancellation) stays gated, consistent with FR-003.
approved/done dependencies are unchanged, and the optional-``provenance``
default keeps the legacy lane-only signature (the five deferred read-only
callers) behaving exactly as before.
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.core.dependency_graph import dependency_readiness_for_wp, ensure_wp_claim_preconditions
from specify_cli.status import read_events, reduce
from specify_cli.status_lanes import OPERATOR_REASON_SOURCE

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _operator_canceled() -> dict[str, Any]:
    """A reduced snapshot state for a canceled WP with operator provenance."""
    return {"lane": "canceled", "reason_source": OPERATOR_REASON_SOURCE}


def _synthetic_canceled() -> dict[str, Any]:
    """A reduced snapshot state for a canceled WP with a synthetic reason."""
    return {"lane": "canceled", "reason_source": "auto"}


class TestCanceledWithProvenance:
    def test_canceled_operator_provenance_dependency_is_satisfied(self) -> None:
        # SC-005: a documented cancellation resolves the dependency, so the
        # dependent is claimable rather than permanently stranded.
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "canceled"},
            provenance={"WP01": _operator_canceled()},
        )

        assert readiness.satisfied is True
        assert readiness.unsatisfied == ()

    def test_canceled_operator_provenance_unblocks_among_mixed_deps(self) -> None:
        readiness = dependency_readiness_for_wp(
            "WP03",
            ["WP01", "WP02"],
            {"WP01": "approved", "WP02": "canceled"},
            provenance={"WP02": _operator_canceled()},
        )

        assert readiness.satisfied is True
        assert readiness.unsatisfied == ()


class TestCanceledSyntheticStaysGated:
    def test_canceled_synthetic_provenance_dependency_stays_unsatisfied(self) -> None:
        # FR-003: an undocumented cancellation is not a valid removal.
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "canceled"},
            provenance={"WP01": _synthetic_canceled()},
        )

        assert readiness.satisfied is False
        assert readiness.unsatisfied == ("WP01",)

    def test_canceled_without_provenance_entry_stays_unsatisfied(self) -> None:
        # A provenance map missing the dependency entry resolves to no provenance.
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "canceled"},
            provenance={},
        )

        assert readiness.satisfied is False
        assert readiness.unsatisfied == ("WP01",)

    def test_canceled_none_snapshot_stays_unsatisfied(self) -> None:
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "canceled"},
            provenance={"WP01": None},
        )

        assert readiness.satisfied is False
        assert readiness.unsatisfied == ("WP01",)


class TestApprovedDoneUnchangedWithProvenance:
    def test_approved_dependency_still_satisfied_with_provenance_map(self) -> None:
        # approved/done ignore provenance entirely (has_provenance is irrelevant).
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "approved"},
            provenance={"WP01": {"lane": "approved"}},
        )

        assert readiness.satisfied is True
        assert readiness.unsatisfied == ()

    def test_done_dependency_still_satisfied_with_provenance_map(self) -> None:
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "done"},
            provenance={"WP01": {"lane": "done"}},
        )

        assert readiness.satisfied is True
        assert readiness.unsatisfied == ()

    def test_non_terminal_dependency_still_unsatisfied_with_provenance_map(self) -> None:
        # A stray operator reason_source on a non-terminal lane must not satisfy
        # the gate — only canceled acceptability turns on provenance.
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "in_progress"},
            provenance={"WP01": {"lane": "in_progress", "reason_source": OPERATOR_REASON_SOURCE}},
        )

        assert readiness.satisfied is False
        assert readiness.unsatisfied == ("WP01",)


class TestOptionalParamDefaultPreservesLegacyBehavior:
    """The default (no provenance) keeps the five deferred lane-only callers working."""

    def test_legacy_lane_only_signature_still_callable(self) -> None:
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "approved"},
        )

        assert readiness.satisfied is True
        assert readiness.unsatisfied == ()

    def test_canceled_without_provenance_param_stays_gated(self) -> None:
        # Legacy callers pass no provenance; a canceled dependency stays
        # non-satisfying exactly as under the retired lane-set behaviour.
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "canceled"},
        )

        assert readiness.satisfied is False
        assert readiness.unsatisfied == ("WP01",)

    def test_done_without_provenance_param_satisfied(self) -> None:
        readiness = dependency_readiness_for_wp(
            "WP02",
            ["WP01"],
            {"WP01": "done"},
        )

        assert readiness.satisfied is True
        assert readiness.unsatisfied == ()


class TestImplementClaimGateThreadsProvenance:
    """The `spec-kitty implement WP##` claim gate (`ensure_wp_claim_preconditions`
    in `core/dependency_graph.py`, fed by the reduced event log) is the primary claim command (CLAUDE.md: "the only supported
    way to prepare a workspace"). It must thread provenance so a dependent of a
    canceled-with-operator-provenance WP is claimable — otherwise the #2945 strand
    trap stays open on the main path even though the pure gate is fixed (review REJECT).
    """

    @staticmethod
    def _seed(status_dir: Any, wp01_reason_source: str) -> None:
        from specify_cli.status.models import Lane, StatusEvent
        from specify_cli.status.store import append_event

        def ev(event_id: str, wp: str, frm: Lane, to: Lane, reason_source: str | None = None) -> StatusEvent:
            return StatusEvent(
                event_id=event_id,
                mission_slug="099-terminal-state",
                wp_id=wp,
                from_lane=frm,
                to_lane=to,
                at="2026-08-28T00:00:00+00:00",
                actor="claude",
                force=False,
                execution_mode="worktree",
                reason=("replan" if reason_source else None),
                reason_source=reason_source,
            )

        # WP01: bootstrapped then canceled (provenance varies per case).
        append_event(status_dir, ev("01AA", "WP01", Lane.GENESIS, Lane.PLANNED))
        append_event(status_dir, ev("01AB", "WP01", Lane.PLANNED, Lane.CANCELED, wp01_reason_source))
        # WP02: the dependent, finalized to planned (non-genesis) so the gate runs.
        append_event(status_dir, ev("01AC", "WP02", Lane.GENESIS, Lane.PLANNED))

    def test_operator_canceled_dependency_admits_claim(self, tmp_path: Any) -> None:
        from specify_cli.status_lanes import OPERATOR_REASON_SOURCE

        self._seed(tmp_path, OPERATOR_REASON_SOURCE)
        # Must NOT raise: the documented cancellation resolves WP02's dependency.
        ensure_wp_claim_preconditions("WP02", ["WP01"], reduce(read_events(tmp_path)).work_packages)

    def test_synthetic_canceled_dependency_still_blocks_claim(self, tmp_path: Any) -> None:
        import pytest as _pytest

        self._seed(tmp_path, "synthetic")
        with _pytest.raises(ValueError, match="dependencies_not_satisfied"):
            ensure_wp_claim_preconditions("WP02", ["WP01"], reduce(read_events(tmp_path)).work_packages)
