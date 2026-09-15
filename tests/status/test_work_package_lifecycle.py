"""Tests for shared work-package lifecycle start operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.clock import now_utc_iso
from specify_cli.dashboard.scanner import _KANBAN_COLUMN_FOR_LANE
from specify_cli.status.models import InnerStateChanged, Lane, StatusEvent, WPInnerStateDelta
from specify_cli.status.reducer import materialize_snapshot, reduce
from specify_cli.status.store import (
    append_annotations_atomic_verified,
    append_event,
    read_event_stream,
    read_events,
)
from specify_cli.status.work_package_lifecycle import (
    GENERIC_IMPLEMENTATION_ACTORS,
    WorkPackageClaimConflict,
    WorkPackageStartRejected,
    _actor_key,
    _actors_compatible,
    start_implementation_status,
    start_review_status,
)

pytestmark = pytest.mark.fast

_SLUG = "099-lifecycle-test"


@pytest.fixture(autouse=True)
def _disable_status_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *args, **kwargs: None)


def _feature_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "099-lifecycle-test"
    feature_dir.mkdir(parents=True)
    return feature_dir


def _event(
    event_id: str,
    *,
    from_lane: Lane,
    to_lane: Lane,
    actor: str = "claude",
    wp_id: str = "WP01",
    at: str | None = None,
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_SLUG,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at or f"2026-04-26T10:00:0{event_id[-1]}+00:00",
        actor=actor,
        force=False,
        execution_mode="worktree",
    )


def _seed_reviewer_role_annotation(feature_dir: Path, *, actor: str, event_id: str, wp_id: str = "WP01") -> None:
    """Fold ``role="reviewer"`` onto ``wp_id`` (the resolved-binding review claim).

    The role-aware collision predicate keys off the reduced ``role`` slot, which
    is populated only when a claim carried a resolved binding
    (``workflow_executor`` writes ``role="reviewer"`` if ``resolved_binding`` is
    not None). Seeding it here is what makes the ``in_review`` re-claim collision
    fire; a binding-less holder (no such annotation) leaves ``role=None`` and
    degrades to ALLOW (best-effort collision).
    """
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id=event_id,
                wp_id=wp_id,
                at=now_utc_iso(),
                actor=actor,
                delta=WPInnerStateDelta(role="reviewer"),
            )
        ],
    )


# ---------------------------------------------------------------------------
# T013 — genesis parity tests (WP02)
# ---------------------------------------------------------------------------


def test_genesis_unseeded_wp_is_rejected_with_actionable_message(tmp_path: Path) -> None:
    """An unseeded WP (no events) raises WorkPackageStartRejected with the finalize-tasks hint."""
    feature_dir = _feature_dir(tmp_path)

    with pytest.raises(WorkPackageStartRejected, match="not finalized") as exc_info:
        start_implementation_status(
            feature_dir=feature_dir,
            mission_slug="099-lifecycle-test",
            wp_id="WP01",
            actor="claude",
            workspace_context="worktree:/nonexistent/wp01",
            execution_mode="worktree",
            repo_root=tmp_path,
        )

    # Message must contain the recovery hint.
    assert "finalize-tasks" in str(exc_info.value)


def test_genesis_unseeded_wp_with_other_wp_seeded_also_rejected(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """Genesis rejection fires even when other WPs in the same mission have events."""
    feature_dir = _feature_dir(tmp_path)
    # WP02 is seeded, but WP01 is not.
    seed_to_planned(feature_dir, "WP02", slug=_SLUG)

    with pytest.raises(WorkPackageStartRejected, match="not finalized"):
        start_implementation_status(
            feature_dir=feature_dir,
            mission_slug=_SLUG,
            wp_id="WP01",
            actor="claude",
            workspace_context="worktree:/nonexistent/wp01",
            execution_mode="worktree",
            repo_root=tmp_path,
        )


def test_seeded_wp_happy_path_unaffected_by_genesis_check(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """After finalize-tasks seeds genesis→planned, the WP proceeds normally."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)

    result = start_implementation_status(
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        actor="claude",
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.from_lane == Lane.PLANNED
    assert result.to_lane == Lane.IN_PROGRESS
    assert result.no_op is False


# ---------------------------------------------------------------------------
# Existing lifecycle tests (seeded WPs)
# ---------------------------------------------------------------------------


def test_start_implementation_batches_planned_to_in_progress(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)

    result = start_implementation_status(
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        actor="claude",
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.from_lane == Lane.PLANNED
    assert result.to_lane == Lane.IN_PROGRESS
    assert result.no_op is False

    events = read_events(feature_dir)
    # genesis->planned seed, then the planned->claimed->in_progress batch.
    assert [(event.from_lane, event.to_lane) for event in events] == [
        (Lane.GENESIS, Lane.PLANNED),
        (Lane.PLANNED, Lane.CLAIMED),
        (Lane.CLAIMED, Lane.IN_PROGRESS),
    ]
    snapshot = reduce(events)
    assert snapshot.work_packages["WP01"]["lane"] == Lane.IN_PROGRESS


def test_backgrounded_implementation_start_does_not_strand_claimed(tmp_path: Path, seed_to_planned: Callable[..., None]) -> None:
    """A normal start writes claim and progress evidence as one durable batch."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)

    result = start_implementation_status(
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        actor="claude",
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.to_lane == Lane.IN_PROGRESS
    events = read_events(feature_dir)
    # genesis->planned seed, then the claimed + in_progress batch.
    assert [event.to_lane for event in events] == [Lane.PLANNED, Lane.CLAIMED, Lane.IN_PROGRESS]
    assert reduce(events).work_packages["WP01"]["lane"] == Lane.IN_PROGRESS


def test_start_implementation_resumes_claimed_same_actor(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    append_event(feature_dir, _event("01AAAA0000000000000000001A", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED))

    result = start_implementation_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor="claude",
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.from_lane == Lane.CLAIMED
    assert result.status_changed is True
    assert read_events(feature_dir)[-1].to_lane == Lane.IN_PROGRESS


def test_real_implement_and_review_claims_persist_structured_latest_binding(
    tmp_path: Path,
    seed_to_planned: Callable[..., None],
) -> None:
    """The lifecycle entry points persist actor + binding in one claim unit."""
    feature_dir = _feature_dir(tmp_path)
    seed_to_planned(feature_dir, "WP01", slug=_SLUG)

    implement_actor = {
        "role": "implementer",
        "profile": "python-pedro",
        "tool": "claude",
        "model": "model-M1",
    }
    start_implementation_status(
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        actor=implement_actor,
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
        annotation_delta=WPInnerStateDelta(
            role="implementer",
            agent_profile="python-pedro",
            agent_profile_version="1.0",
            model="model-M1",
            provider="anthropic",
        ),
    )

    stream = read_event_stream(feature_dir)
    assert stream.transitions[-1].actor == implement_actor
    assert len(stream.annotations) == 1  # one atomic binding annotation
    assert stream.annotations[0].delta.agent_profile == "python-pedro"

    # #3157: this event must sort strictly BETWEEN the real `now()` timestamp
    # `start_implementation_status` (above) already recorded and the real
    # `now()` timestamp `start_review_status` (below) is about to record, in
    # `reduce()`'s `(e.at, e.event_id)` sort order -- forever, regardless of
    # what wall-clock date the suite happens to run on. A second
    # absolute-literal `at` (e.g. bumped to some later fixed year) would only
    # buy a longer fuse on the same defect (spec.md's Revision History calls
    # this out explicitly as the wrong fix). Capturing `datetime.now(UTC)`
    # HERE, between the two calls, relies only on wall-clock time being
    # monotonically non-decreasing during a single test run -- not on any
    # absolute date -- so it is strictly later than every timestamp
    # `start_implementation_status` already wrote (that call already
    # returned) and strictly earlier than every timestamp `start_review_
    # status` is about to write (that call has not started yet). This
    # ordering property holds at ANY future run date, including the system
    # clock advanced by ten years: it is derived relative to the call's own
    # execution moment, never a second fixed literal.
    append_event(
        feature_dir,
        _event(
            "01EEEE0000000000000000005E",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.FOR_REVIEW,
            actor="claude",
            # Stale-test fix (2026-08-05): this event's ``at`` must sort after
            # the real ``datetime.now(UTC)`` timestamps that
            # ``start_implementation_status`` just wrote above -- the
            # reducer's transition fold is chronological (sorted by
            # ``(at, event_id)``), so whichever event has the later
            # timestamp wins as the WP's current lane. Originally hardcoded
            # to a fixed "2026-08-01T10:00:00+00:00" (added 2026-07-21,
            # #2816), which relied on the wall clock never reaching that
            # date; once it did, this literal sorted *before* the
            # just-recorded "now" events, resurrecting in_progress as the
            # current lane and rejecting the subsequent
            # ``start_review_status`` call. Anchoring to real "now" removes
            # the wall-clock time bomb while preserving the test's intent
            # (a later, real transition into for_review).
            at=now_utc_iso(),
        ),
    )
    review_actor = {
        "role": "reviewer",
        "profile": "reviewer-renata",
        "tool": "claude",
        "model": "model-M2",
    }
    start_review_status(
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id="WP01",
        actor=review_actor,
        workspace_context="review:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
        annotation_delta=WPInnerStateDelta(
            role="reviewer",
            agent_profile="reviewer-renata",
            agent_profile_version="1.0",
            model="model-M2",
            provider="anthropic",
        ),
    )

    snapshot = materialize_snapshot(feature_dir).work_packages["WP01"]
    assert snapshot["agent_profile"] == "reviewer-renata"
    assert snapshot["model"] == "model-M2"
    assert snapshot["role"] == "reviewer"
    assert read_events(feature_dir)[-1].actor == review_actor


def test_interrupted_implementation_claim_recovers_with_progress_event(tmp_path: Path) -> None:
    """If only a claim exists, the same actor records recovery into progress."""
    feature_dir = _feature_dir(tmp_path)
    append_event(feature_dir, _event("01AAAA0000000000000000001A", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED))

    result = start_implementation_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor="claude",
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    events = read_events(feature_dir)
    assert result.from_lane == Lane.CLAIMED
    assert events[-1].from_lane == Lane.CLAIMED
    assert events[-1].to_lane == Lane.IN_PROGRESS
    assert reduce(events).work_packages["WP01"]["lane"] == Lane.IN_PROGRESS


def test_start_implementation_rejects_claimed_different_actor(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    append_event(
        feature_dir,
        _event("01AAAA0000000000000000001A", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED, actor="other-agent"),
    )

    with pytest.raises(WorkPackageClaimConflict) as exc_info:
        start_implementation_status(
            feature_dir=feature_dir,
            mission_slug="099-lifecycle-test",
            wp_id="WP01",
            actor="claude",
            workspace_context="worktree:/nonexistent/wp01",
            execution_mode="worktree",
            repo_root=tmp_path,
        )

    assert exc_info.value.claimed_by == "other-agent"
    assert len(read_events(feature_dir)) == 1


def test_interrupted_claim_by_different_actor_returns_claim_diagnostic(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    append_event(
        feature_dir,
        _event("01AAAA0000000000000000001A", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED, actor="other-agent"),
    )

    with pytest.raises(WorkPackageClaimConflict, match="already claimed") as exc_info:
        start_implementation_status(
            feature_dir=feature_dir,
            mission_slug="099-lifecycle-test",
            wp_id="WP01",
            actor="claude",
            workspace_context="worktree:/nonexistent/wp01",
            execution_mode="worktree",
            repo_root=tmp_path,
        )

    assert exc_info.value.claimed_by == "other-agent"
    assert exc_info.value.requesting_actor == "claude"
    assert reduce(read_events(feature_dir)).work_packages["WP01"]["lane"] == Lane.CLAIMED


def test_start_implementation_noops_in_progress_same_actor(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    append_event(feature_dir, _event("01AAAA0000000000000000001A", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED))
    append_event(feature_dir, _event("01BBBB0000000000000000002B", from_lane=Lane.CLAIMED, to_lane=Lane.IN_PROGRESS))

    result = start_implementation_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor="claude",
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.no_op is True
    assert len(read_events(feature_dir)) == 2


def test_start_implementation_rejects_in_progress_different_actor(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    append_event(feature_dir, _event("01AAAA0000000000000000001A", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED))
    append_event(
        feature_dir,
        _event("01BBBB0000000000000000002B", from_lane=Lane.CLAIMED, to_lane=Lane.IN_PROGRESS, actor="other-agent"),
    )

    with pytest.raises(WorkPackageClaimConflict) as exc_info:
        start_implementation_status(
            feature_dir=feature_dir,
            mission_slug="099-lifecycle-test",
            wp_id="WP01",
            actor="claude",
            workspace_context="worktree:/nonexistent/wp01",
            execution_mode="worktree",
            repo_root=tmp_path,
        )

    assert exc_info.value.claimed_by == "other-agent"


def test_start_implementation_allows_forced_rework_from_review_lane(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    append_event(
        feature_dir,
        _event("01CCCC0000000000000000003C", from_lane=Lane.IN_PROGRESS, to_lane=Lane.FOR_REVIEW, actor="implementer"),
    )

    result = start_implementation_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor="claude",
        workspace_context="worktree:/nonexistent/wp01",
        execution_mode="worktree",
        repo_root=tmp_path,
        allow_rework=True,
        rework_reason="review changes requested",
    )

    assert result.from_lane == Lane.FOR_REVIEW
    assert result.to_lane == Lane.IN_PROGRESS
    assert read_events(feature_dir)[-1].reason == "review changes requested"


def test_start_implementation_rejects_unstartable_lane(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    append_event(feature_dir, _event("01DDDD0000000000000000004D", from_lane=Lane.APPROVED, to_lane=Lane.DONE))

    with pytest.raises(WorkPackageStartRejected, match="cannot start implementation"):
        start_implementation_status(
            feature_dir=feature_dir,
            mission_slug="099-lifecycle-test",
            wp_id="WP01",
            actor="claude",
            workspace_context="worktree:/nonexistent/wp01",
            execution_mode="worktree",
            repo_root=tmp_path,
        )


def test_start_review_allows_reviewer_after_implementer_for_review(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    append_event(
        feature_dir,
        _event("01CCCC0000000000000000003C", from_lane=Lane.IN_PROGRESS, to_lane=Lane.FOR_REVIEW, actor="implementer"),
    )

    result = start_review_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor="reviewer",
        workspace_context="review:/nonexistent/repo",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.from_lane == Lane.FOR_REVIEW
    assert read_events(feature_dir)[-1].to_lane == Lane.IN_REVIEW


def test_slow_review_claim_uses_in_review_not_claimed(tmp_path: Path) -> None:
    """Review starts never reuse the implementation-only claimed lane."""
    feature_dir = _feature_dir(tmp_path)
    append_event(
        feature_dir,
        _event("01CCCC0000000000000000003C", from_lane=Lane.IN_PROGRESS, to_lane=Lane.FOR_REVIEW, actor="implementer"),
    )

    result = start_review_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor="reviewer",
        workspace_context="review:/nonexistent/repo",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    events = read_events(feature_dir)
    assert result.to_lane == Lane.IN_REVIEW
    assert events[-1].from_lane == Lane.FOR_REVIEW
    assert events[-1].to_lane == Lane.IN_REVIEW
    assert reduce(events).work_packages["WP01"]["lane"] == Lane.IN_REVIEW


def test_start_review_noops_same_reviewer(tmp_path: Path) -> None:
    """Same reviewer re-claiming an in_review WP is idempotent (predicate rule 3).

    Re-pointed (WP01): the holder's ``role="reviewer"`` is seeded via the binding
    annotation so the role-aware predicate is exercised; the same actor re-claim
    resolves to ALLOW (no_op)."""
    feature_dir = _feature_dir(tmp_path)
    append_event(
        feature_dir,
        _event("01DDDD0000000000000000004D", from_lane=Lane.FOR_REVIEW, to_lane=Lane.IN_REVIEW, actor="reviewer-a"),
    )
    _seed_reviewer_role_annotation(feature_dir, actor="reviewer-a", event_id="01DDDD00000000000000000A4E")

    result = start_review_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor="reviewer-a",
        workspace_context="review:/nonexistent/repo",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.no_op is True
    assert len(read_events(feature_dir)) == 1


def test_start_review_rejects_second_reviewer(tmp_path: Path) -> None:
    """Two distinct reviewers on an in_review WP collide (predicate rule 4).

    Re-pointed (WP01): the reject is now role-aware. The holder's
    ``role="reviewer"`` MUST be seeded via the binding annotation, or the
    predicate (correctly) degrades to ALLOW. This is the SINGLE genuine reject
    site — the FSM/guard/parity surfaces carry no role and assert ALLOW."""
    feature_dir = _feature_dir(tmp_path)
    append_event(
        feature_dir,
        _event("01DDDD0000000000000000004D", from_lane=Lane.FOR_REVIEW, to_lane=Lane.IN_REVIEW, actor="reviewer-a"),
    )
    _seed_reviewer_role_annotation(feature_dir, actor="reviewer-a", event_id="01DDDD00000000000000000A4E")

    with pytest.raises(WorkPackageClaimConflict) as exc_info:
        start_review_status(
            feature_dir=feature_dir,
            mission_slug="099-lifecycle-test",
            wp_id="WP01",
            actor="reviewer-b",
            workspace_context="review:/nonexistent/repo",
            execution_mode="worktree",
            repo_root=tmp_path,
        )

    assert exc_info.value.claimed_by == "reviewer-a"


def test_start_review_allows_second_reviewer_when_holder_binding_less(tmp_path: Path) -> None:
    """Best-effort collision (WP01): a binding-less holder (no reduced role) ALLOWs.

    Records the accepted degradation — when the holder claimed with a bare
    ``--agent`` (no resolved binding), the reduced ``role`` slot is ``None`` so
    predicate rule 2 fires and a distinct reviewer's claim is permitted rather
    than false-blocked. This prevents the mission's primary failure mode (never
    false-block a cross-profile review) from regressing into a hard block."""
    feature_dir = _feature_dir(tmp_path)
    append_event(
        feature_dir,
        _event(
            "01DDDD0000000000000000004D",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            actor="reviewer-a",
            # Anchored to real "now" (not `_event`'s hard-coded default) so
            # this test's whole event log is now()-stamped, matching the
            # `start_review_status` call below -- avoids mixing an absolute
            # literal with a real-clock event in the same test function
            # (FR-014 / #3157-class flakiness; see
            # tests/architectural/test_no_absolute_event_timestamp_mixture.py).
            at=now_utc_iso(),
        ),
    )
    # NOTE: deliberately NO role annotation -> current_role is None.

    result = start_review_status(
        feature_dir=feature_dir,
        mission_slug="099-lifecycle-test",
        wp_id="WP01",
        actor="reviewer-b",
        workspace_context="review:/nonexistent/repo",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.no_op is True
    assert len(read_events(feature_dir)) == 1


def test_start_review_rejects_non_review_lane(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)

    with pytest.raises(WorkPackageStartRejected, match="cannot start review"):
        start_review_status(
            feature_dir=feature_dir,
            mission_slug="099-lifecycle-test",
            wp_id="WP01",
            actor="reviewer-a",
            workspace_context="review:/nonexistent/repo",
            execution_mode="worktree",
            repo_root=tmp_path,
        )


def test_lifecycle_helpers_normalize_lock_roots_and_actors(tmp_path: Path) -> None:
    from specify_cli.workspace.root_resolver import resolve_status_lock_root

    # Explicit repo_root always wins — no resolution needed.
    assert resolve_status_lock_root(tmp_path / "any" / "path", repo_root=tmp_path) == tmp_path
    # Non-kitty-specs dir: returned as-is (no git resolution).
    assert resolve_status_lock_root(tmp_path / "loose-feature", None) == tmp_path / "loose-feature"
    assert _actor_key(None) is None
    assert _actors_compatible(None, "claude") is True


def test_generic_implementation_actors_exported_on_status_facade() -> None:
    """FIX-M2-03: the constant must be importable from ``specify_cli.status``
    (not just this module) so sibling ownership checks (e.g.
    ``tasks_transition_core._guard_agent_ownership``) share the ONE definition
    instead of hand-rolling their own copy that could drift out of sync.
    """
    import specify_cli.status as status_facade

    assert status_facade.GENERIC_IMPLEMENTATION_ACTORS is GENERIC_IMPLEMENTATION_ACTORS
    assert frozenset({"implement-command", "unknown"}) == GENERIC_IMPLEMENTATION_ACTORS


@pytest.mark.parametrize("generic_current", sorted(GENERIC_IMPLEMENTATION_ACTORS))
def test_actors_compatible_treats_generic_placeholder_as_unclaimed(generic_current: str) -> None:
    """A WP whose CURRENT assignee is a generic placeholder (the internal
    ``implement`` compat surface's default when invoked without ``--actor``,
    or the plain ``unknown`` fallback) is not a real owner -- any real
    requested actor is compatible without needing ``allow_generic_existing``
    to be a real-vs-real match.
    """
    assert _actors_compatible(generic_current, "claude", allow_generic_existing=True) is True
    # Without the allowance, a generic placeholder still fails raw equality --
    # proving the True result above comes from the allowance, not a no-op.
    assert _actors_compatible(generic_current, "claude", allow_generic_existing=False) is False


def test_claimed_lane_surfaces_as_doing_in_dashboard() -> None:
    assert _KANBAN_COLUMN_FOR_LANE[Lane.CLAIMED] == "doing"


def test_start_implementation_resume_is_not_regated_when_dependency_regresses(tmp_path: Path) -> None:
    """fsm-write-path-integrity WP04 pin: an ``in_progress`` WP re-invoked is a no-op
    resume. The dependency guard only fires on ``planned -> claimed`` and
    ``claimed -> in_progress``; a resume emits neither, so a dependency that
    regressed AFTER WP02 was legitimately claimed cannot block the resume."""
    feature_dir = _feature_dir(tmp_path)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text("---\nwork_package_id: WP01\ndependencies: []\nsubtasks: []\n---\n# WP01\n", encoding="utf-8")
    (tasks_dir / "WP02.md").write_text("---\nwork_package_id: WP02\ndependencies: [WP01]\nsubtasks: []\n---\n# WP02\n", encoding="utf-8")
    # WP01 reached approved; WP02 was then legitimately claimed and started.
    for event_id, (src, dst) in zip(
        ("01AAAA000000000000000001A", "01AAAA000000000000000002B", "01AAAA000000000000000003C", "01AAAA000000000000000004D", "01AAAA000000000000000005E"),
        (
            (Lane.PLANNED, Lane.CLAIMED),
            (Lane.CLAIMED, Lane.IN_PROGRESS),
            (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
            (Lane.FOR_REVIEW, Lane.IN_REVIEW),
            (Lane.IN_REVIEW, Lane.APPROVED),
        ),
        strict=True,
    ):
        # ``at=now_utc_iso()`` keeps this setup on the same clock as the
        # ``start_implementation_status`` call below -- avoids mixing an absolute
        # hard-coded event timestamp with a live-clock production call
        # (tests/architectural/test_no_absolute_event_timestamp_mixture.py).
        append_event(feature_dir, _event(event_id, from_lane=src, to_lane=dst, wp_id="WP01", at=now_utc_iso()))
    append_event(feature_dir, _event("01BBBB000000000000000001A", from_lane=Lane.PLANNED, to_lane=Lane.CLAIMED, wp_id="WP02", at=now_utc_iso()))
    append_event(feature_dir, _event("01BBBB000000000000000002B", from_lane=Lane.CLAIMED, to_lane=Lane.IN_PROGRESS, wp_id="WP02", at=now_utc_iso()))
    # The dependency regresses to in_progress afterwards (rework).
    append_event(feature_dir, _event("01CCCC000000000000000001A", from_lane=Lane.APPROVED, to_lane=Lane.IN_PROGRESS, wp_id="WP01", at=now_utc_iso()))

    result = start_implementation_status(
        feature_dir=feature_dir,
        mission_slug=_SLUG,
        wp_id="WP02",
        actor="claude",
        workspace_context="worktree:/nonexistent/wp02",
        execution_mode="worktree",
        repo_root=tmp_path,
    )

    assert result.no_op is True
    assert result.events == ()
    assert reduce(read_events(feature_dir)).work_packages["WP02"]["lane"] == Lane.IN_PROGRESS
