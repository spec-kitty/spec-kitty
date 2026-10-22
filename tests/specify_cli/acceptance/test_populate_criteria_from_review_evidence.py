"""FR-008 (governance-at-the-gate WP04 / IC-04, T3) — acceptance-matrix
criterion auto-population from WP review evidence.

Design decision (recorded on the function's own docstring too):
population is AUTO-DERIVED from the T1/T2 gate-side evidence capture
(status events' ``review_result`` + the auto-authored ``review-cycle-N.md``),
never a new hand-filled artifact (NFR-005). Scope is deliberately narrow to
``code_review``-typed criteria — the one proof type whose evidence IS
"every tracked WP carries a durable, gate-captured review verdict".

These are pure-unit tests against :func:`~specify_cli.acceptance.matrix.
populate_criteria_from_review_evidence` directly, seeding a real
``status.events.jsonl`` via the canonical ``seed_status_event`` writer (no git
required — filesystem only, mirroring ``tests/acceptance/
test_provenance_and_deferral.py``'s approach to the sibling
``enforce_negative_invariants``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.acceptance.matrix import (
    SCAFFOLD_TODO_MARKER,
    AcceptanceCriterion,
    populate_criteria_from_review_evidence,
)
from specify_cli.status import Lane, ReviewResult, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = pytest.mark.fast


def _approve_event(
    mission_slug: str,
    wp_id: str,
    *,
    reviewer: str = "reviewer-renata",
    reference: str | None = None,
) -> StatusEvent:
    return StatusEvent(
        event_id=f"evt-{wp_id}-approved",
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane.IN_REVIEW,
        to_lane=Lane.APPROVED,
        at="2026-08-29T00:00:00+00:00",
        actor=reviewer,
        force=False,
        execution_mode="worktree",
        review_result=ReviewResult(
            reviewer=reviewer,
            verdict="approved",
            reference=reference or f"review-cycle://{mission_slug}/{wp_id}/1",
        ),
    )


def _in_progress_event(mission_slug: str, wp_id: str) -> StatusEvent:
    return StatusEvent(
        event_id=f"evt-{wp_id}-in-progress",
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane.CLAIMED,
        to_lane=Lane.IN_PROGRESS,
        at="2026-08-29T00:00:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
    )


def _criterion(
    *,
    criterion_id: str = "AC-001",
    proof_type: str = "code_review",
    pass_fail: str = "pending",  # noqa: S107  # test-fixture default, not a secret
    description: str = "Verify the change was code-reviewed",
    **overrides: object,
) -> AcceptanceCriterion:
    return AcceptanceCriterion(
        criterion_id=criterion_id,
        description=description,
        proof_type=proof_type,
        pass_fail=pass_fail,
        **overrides,
    )


def test_populates_pending_code_review_criterion_when_all_wps_approved(
    tmp_path: Path,
) -> None:
    """T3 (red-first): once every tracked WP is approved with a durable,
    event-sourced review verdict, a pending ``code_review`` criterion is
    auto-populated to ``pass`` -- closing the "criterion rows never
    populated" gap."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    seed_status_event(feature_dir, _approve_event("demo", "WP01"))
    seed_status_event(feature_dir, _approve_event("demo", "WP02", reviewer="reviewer-bob"))

    updated = populate_criteria_from_review_evidence(feature_dir, [_criterion()])

    assert updated[0].pass_fail == "pass"
    assert updated[0].verified_at
    assert "reviewer-renata" in (updated[0].verified_by or "")
    assert "reviewer-bob" in (updated[0].verified_by or "")
    assert "WP01" in (updated[0].evidence or "")
    assert "WP02" in (updated[0].evidence or "")
    assert "Auto-derived" in (updated[0].notes or "")


def test_does_not_re_judge_an_already_judged_criterion(tmp_path: Path) -> None:
    """Forward-only (NI-2-style preservation): a criterion already judged
    (``pass_fail != "pending"``) is NEVER re-touched, even with full WP
    evidence on disk -- including an operator hand-authored verdict via
    ``agent mission acceptance-verdict``."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    seed_status_event(feature_dir, _approve_event("demo", "WP01"))

    original = _criterion(pass_fail="fail", verified_by="human", evidence="manual review")
    updated = populate_criteria_from_review_evidence(feature_dir, [original])

    assert updated[0] is original
    assert updated[0].pass_fail == "fail"
    assert updated[0].verified_by == "human"
    assert updated[0].evidence == "manual review"


@pytest.mark.parametrize("proof_type", ["automated_test", "manual_qa", "negative_invariant"])
def test_ignores_non_code_review_proof_types(tmp_path: Path, proof_type: str) -> None:
    """Scope guard: only ``code_review`` is auto-derivable -- these proof
    types need their own evidence this gate cannot fabricate."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    seed_status_event(feature_dir, _approve_event("demo", "WP01"))

    updated = populate_criteria_from_review_evidence(feature_dir, [_criterion(proof_type=proof_type)])

    assert updated[0].pass_fail == "pending"


def test_skips_empty_scaffold_placeholder(tmp_path: Path) -> None:
    """The ``finalize-tasks`` empty-scaffold placeholder carries no real
    ``code_review`` intent -- the ``_is_empty_scaffold`` exemption is
    preserved, unchanged from the negative-invariant gate's own rule."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    seed_status_event(feature_dir, _approve_event("demo", "WP01"))

    updated = populate_criteria_from_review_evidence(feature_dir, [_criterion(description=SCAFFOLD_TODO_MARKER)])

    assert updated[0].pass_fail == "pending"


def test_stays_pending_when_a_wp_is_not_yet_approved(tmp_path: Path) -> None:
    """All-or-nothing: any tracked WP short of approved/done leaves the
    matrix exactly as it was -- ``pending`` -- never a partial derivation."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    seed_status_event(feature_dir, _approve_event("demo", "WP01"))
    seed_status_event(feature_dir, _in_progress_event("demo", "WP02"))

    updated = populate_criteria_from_review_evidence(feature_dir, [_criterion()])

    assert updated[0].pass_fail == "pending"


def test_stays_pending_when_review_evidence_chain_is_incomplete(tmp_path: Path) -> None:
    """A WP that reached ``approved`` WITHOUT a recorded ``review_result``
    (e.g. approved before T1 landed) leaves the matrix ``pending`` -- this
    gate never derives a verdict it cannot prove."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="evt-WP01-approved-no-evidence",
            mission_slug="demo",
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-08-29T00:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
        ),
    )

    updated = populate_criteria_from_review_evidence(feature_dir, [_criterion()])

    assert updated[0].pass_fail == "pending"


def test_stays_pending_when_a_wp_carries_a_stale_rejection_verdict(tmp_path: Path) -> None:
    """M1 (WP04 review, evidence-integrity) — red-first negative test.

    A WP force-approved from a NON-``in_review`` lane (e.g. ``planned ->
    approved`` via an operator/arbiter override) whose event-sourced
    ``review_result`` slot still holds the REJECTING reviewer's stale
    ``changes_requested`` verdict — inherited FORWARD by the reducer because
    the force-approve's ``from_lane != IN_REVIEW``
    (``reducer._wp_state_from_event``'s ``elif previous is not None and
    "review_result" in previous`` carry-forward branch) — must NEVER be read
    as approval proof. Before the verdict check (``lookup.result.verdict !=
    "approved"``), this fabricated an approval attribution: the criterion
    was stamped ``pass`` citing the REJECTING reviewer and the rejection's
    OWN review-cycle reference — an evidence-integrity violation this
    acceptance-evidence-capture mission exists to prevent.
    """
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    # A genuine in_review -> planned rejection: the durable review_result slot.
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="evt-WP01-rejected",
            mission_slug="demo",
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-08-29T00:00:00+00:00",
            actor="reviewer-renata",
            force=True,
            execution_mode="worktree",
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="changes_requested",
                reference="review-cycle://demo/WP01/1",
            ),
        ),
    )
    # A forced planned -> approved that carries NO fresh review_result at
    # all -- the reducer inherits the stale rejection forward onto the
    # snapshot's review_result slot, even though the WP's LANE is approved.
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id="evt-WP01-force-approved",
            mission_slug="demo",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.APPROVED,
            at="2026-08-29T01:00:00+00:00",
            actor="operator",
            force=True,
            execution_mode="worktree",
        ),
    )

    updated = populate_criteria_from_review_evidence(feature_dir, [_criterion()])

    assert updated[0].pass_fail == "pending"
    assert updated[0].verified_by is None
    assert updated[0].evidence is None


def test_no_op_when_status_log_is_missing(tmp_path: Path) -> None:
    """A missing ``status.events.jsonl`` degrades to a no-op, never a crash --
    this is an additive enrichment on top of the pre-existing block-on-pending
    gate, not a new hard dependency."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)

    updated = populate_criteria_from_review_evidence(feature_dir, [_criterion()])

    assert updated[0].pass_fail == "pending"


def test_short_circuits_when_no_pending_targets(tmp_path: Path) -> None:
    """No pending ``code_review`` criteria -> returns the SAME list object
    (no status-log read at all)."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    criteria = [_criterion(proof_type="automated_test")]

    updated = populate_criteria_from_review_evidence(feature_dir, criteria)

    assert updated is criteria
