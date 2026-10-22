"""Acceptance + regression tests for the role-aware review-claim gate (WP01).

Red-first surface (T005): the cross-profile false-block manifests ONLY where the
holder is resolved from the reduction into the guard — the
``MissionStatus.transition`` **aggregate seam** (``aggregate.py`` builds a
``GuardContext(current_actor=...)`` from ``read_current_wp_state_transactional``
and runs ``validate_transition``). The ``move-task`` command never populates
``current_actor`` so it is vacuous pre-fix; it is deliberately NOT the repro.

Pre-fix behaviour (captured RED): a distinct reviewer claiming ``in_review`` on a
WP whose latest ``for_review`` event was authored by an implementer was refused
with "WP already claimed for review by <implementer>". Post-fix: the guard is
allow-only and the transition succeeds.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.clock import now_utc_iso
from specify_cli.coordination.status_service import wp_lane_actor_from_events
from specify_cli.status.aggregate import MissionStatus
from specify_cli.status.emit import TransitionError
from specify_cli.status.models import (
    GuardContext,
    InnerStateChanged,
    Lane,
    StatusEvent,
    TransitionRequest,
    WPInnerStateDelta,
)
from specify_cli.status.store import append_annotations_atomic_verified
from tests._support.status_seed import seed_status_event
from specify_cli.status.transitions import validate_transition

pytestmark = pytest.mark.fast

_SLUG = "099-review-claim-role-aware"


def _uid(suffix: str) -> str:
    """Build a valid 26-char Crockford-base32 ULID (no I/L/O/U) for seeding."""
    return ("01" + suffix.rjust(24, "0"))[:26]


@pytest.fixture(autouse=True)
def _disable_status_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *args, **kwargs: None)


def _feature_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    return feature_dir


def _transition(
    event_id: str,
    *,
    from_lane: Lane,
    to_lane: Lane,
    actor: object,
    at: str,
    wp_id: str = "WP01",
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_SLUG,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor=actor,  # type: ignore[arg-type]  -- ActorField accepts str | dict
        force=False,
        execution_mode="worktree",
    )


def _legacy_aggregate(feature_dir: Path, repo_root: Path) -> MissionStatus:
    """Construct a legacy-topology aggregate anchored on ``feature_dir``."""
    return MissionStatus(
        mission_slug=_SLUG,
        mission_id=None,
        mid8="",
        topology="legacy",
        read_dir=feature_dir,
        repo_root=repo_root,
        coordination_branch=None,
    )


def _seed_for_review_by_implementer(feature_dir: Path) -> None:
    """WP01 sits at ``for_review`` with the latest event authored by an implementer."""
    seed_status_event(
        feature_dir,
        _transition(
            _uid("A1"),
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.FOR_REVIEW,
            actor="implementer-ivan",
            at=now_utc_iso(),
        ),
    )


# ---------------------------------------------------------------------------
# T005 (a) — the aggregate (MissionStatus.transition) seam
# ---------------------------------------------------------------------------


def test_aggregate_seam_allows_cross_profile_review_claim(tmp_path: Path) -> None:
    """A distinct reviewer may claim in_review on an implementer-held for_review WP.

    This is the genuinely red-pre / green-post repro: the aggregate resolves
    ``current_actor='implementer-ivan'`` from the reduction into the guard, then
    a reviewer claims ``in_review``. Pre-fix this raised "WP already claimed for
    review by implementer-ivan"; post-fix the allow-only guard lets it through.
    """
    feature_dir = _feature_dir(tmp_path)
    _seed_for_review_by_implementer(feature_dir)

    aggregate = _legacy_aggregate(feature_dir, tmp_path)
    event = aggregate.transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=_SLUG,
            wp_id="WP01",
            to_lane=Lane.IN_REVIEW,
            actor="reviewer-renata",
            reason="Started review via aggregate seam",
            review_ref="action-review-claim",
            repo_root=tmp_path,
            execution_mode="worktree",
        )
    )

    assert event.to_lane == Lane.IN_REVIEW
    assert event.from_lane == Lane.FOR_REVIEW


# ---------------------------------------------------------------------------
# T005 (b) — validate_transition unit companion (the guard directly)
# ---------------------------------------------------------------------------


def test_validate_transition_allows_reviewer_over_implementer_holder() -> None:
    """The FSM guard is allow-only: a reviewer claim over an implementer holder ALLOWs."""
    ok, error = validate_transition(
        "for_review",
        "in_review",
        GuardContext(actor="reviewer-renata", current_actor="implementer-ivan"),
    )
    assert ok is True, f"expected allow-only guard, got error={error}"


def test_validate_transition_allows_distinct_reviewer_at_for_review() -> None:
    """Even a distinct reviewer at for_review ALLOWs — the guard never blocks."""
    ok, error = validate_transition(
        "for_review",
        "in_review",
        GuardContext(actor="reviewer-b", current_actor="reviewer-a"),
    )
    assert ok is True, f"guard must be allow-only; error={error}"


def test_validate_transition_still_requires_actor() -> None:
    """Allow-only removes the collision block but keeps the actor-presence guard."""
    ok, error = validate_transition(
        "for_review",
        "in_review",
        GuardContext(actor=""),
    )
    assert ok is False
    assert error and "actor" in error.lower()


# ---------------------------------------------------------------------------
# T005 — stale reviewer role at for_review still ALLOWs
# ---------------------------------------------------------------------------


def test_stale_reviewer_role_at_for_review_still_allows(tmp_path: Path) -> None:
    """A rework cycle can leave a stale reviewer role folded on a for_review WP.

    The allow-only guard must never block on it: a fresh reviewer claim ALLOWs.
    """
    feature_dir = _feature_dir(tmp_path)
    # A prior review cycle stamped role="reviewer" (resolved binding), then the
    # WP was reworked back to for_review by the implementer.
    #
    # All three events below are anchored to real "now" (never a hard-coded
    # absolute literal) so the whole test is a single timestamp kind. The
    # `_uid(...)` event ids are lexically ordered (A2 < A3 < A4), which is
    # the reducer's tie-break on `(at, event_id)` -- so even if two
    # `now_utc_iso()` calls land in the same instant, append order is still
    # preserved. Mixing a hard-coded literal here with `_transition(...,
    # at=now_utc_iso())` below is exactly the #3157-class flakiness this
    # test must not reintroduce (see
    # tests/architectural/test_no_absolute_event_timestamp_mixture.py).
    seed_status_event(
        feature_dir,
        _transition(
            _uid("A2"),
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            actor="reviewer-old",
            at=now_utc_iso(),
        ),
    )
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=_uid("A3"),
                wp_id="WP01",
                at=now_utc_iso(),
                actor="reviewer-old",
                delta=WPInnerStateDelta(role="reviewer"),
            )
        ],
    )
    seed_status_event(
        feature_dir,
        _transition(
            _uid("A4"),
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.FOR_REVIEW,
            actor="implementer-ivan",
            at=now_utc_iso(),
        ),
    )

    aggregate = _legacy_aggregate(feature_dir, tmp_path)
    event = aggregate.transition(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=_SLUG,
            wp_id="WP01",
            to_lane=Lane.IN_REVIEW,
            actor="reviewer-fresh",
            reason="Re-review after rework",
            review_ref="action-review-claim",
            repo_root=tmp_path,
            execution_mode="worktree",
        )
    )
    assert event.to_lane == Lane.IN_REVIEW


# ---------------------------------------------------------------------------
# T005 — NFR-004 / FR-007: same-identity self-review claim is ALLOWED (no new
# hard refusal). Independence remains an advisory-only signal.
# ---------------------------------------------------------------------------


def test_same_identity_self_review_claim_is_allowed(tmp_path: Path) -> None:
    """The implementer claiming their own WP for review is NOT hard-blocked."""
    feature_dir = _feature_dir(tmp_path)
    _seed_for_review_by_implementer(feature_dir)

    aggregate = _legacy_aggregate(feature_dir, tmp_path)
    # Same identity ("implementer-ivan") that authored for_review now claims review.
    try:
        event = aggregate.transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane=Lane.IN_REVIEW,
                actor="implementer-ivan",
                reason="Self review claim",
                review_ref="action-review-claim",
                repo_root=tmp_path,
                execution_mode="worktree",
            )
        )
    except TransitionError as exc:  # pragma: no cover - defensive: must not happen
        pytest.fail(f"same-identity self-review must not be hard-refused: {exc}")
    assert event.to_lane == Lane.IN_REVIEW


# ---------------------------------------------------------------------------
# T007 — #2861 regression: CurrentWpState.role comes from the reduced role slot,
# never from splitting the compound actor. Exercises the DERIVATION
# (wp_lane_actor_from_events), not the pure predicate.
# ---------------------------------------------------------------------------


def test_2861_current_wp_state_role_from_reduced_slot_not_actor_split() -> None:
    """A compound actor dict must not leak into ``.actor`` or source ``.role``.

    ``.actor`` must be the bare ``tool`` ("claude"), never the compound
    ``tool:model:profile:role``. ``.role`` must be the reduced ``role`` slot
    (folded from the binding annotation), not the actor dict's own ``role`` key
    — proven here by seeding a DIFFERENT value on the actor dict.
    """
    compound_actor = {
        "tool": "claude",
        "model": "sonnet",
        "profile": "reviewer-renata",
        "role": "DECOY-not-the-source",
    }
    transitions = [
        _transition(
            _uid("A5"),
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            actor=compound_actor,
            at="2026-08-05T10:00:00+00:00",
        )
    ]
    annotations = [
        InnerStateChanged(
            event_id=_uid("A6"),
            wp_id="WP01",
            at="2026-08-05T10:00:01+00:00",
            actor=compound_actor,  # type: ignore[arg-type]
            delta=WPInnerStateDelta(role="reviewer"),
        )
    ]

    state = wp_lane_actor_from_events(transitions, "WP01", annotations)

    assert state.lane == Lane.IN_REVIEW
    assert state.actor == "claude"  # bare tool, never the compound string
    assert state.role == "reviewer"  # from the reduced role slot, not the decoy


def test_2861_role_none_when_only_transition_present() -> None:
    """Without a role annotation, the derivation surfaces role=None (best-effort)."""
    transitions = [
        _transition(
            _uid("A7"),
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            actor="claude",
            at="2026-08-05T10:00:00+00:00",
        )
    ]
    state = wp_lane_actor_from_events(transitions, "WP01")
    assert state.actor == "claude"
    assert state.role is None
