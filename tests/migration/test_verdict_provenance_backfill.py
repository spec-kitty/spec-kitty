"""Tests for the verdict-provenance backfill + provenance gate (FR-012, WP02).

Covers:

- T006: SC-008 hermetic pin -- a mission whose only rejection is a pre-event
  ``.md`` still refuses approval after backfill.
- T007: terminal-verdict discovery, including tolerance of a legacy
  pre-frontmatter ``review-cycle-N.md`` (a real, measured shape in this
  repository's own ``kitty-specs/`` corpus -- see
  ``kitty-specs/single-mission-surface-resolver-01KVGCE8/tasks/
  WP02-differential-equivalence-test/review-cycle-1.md``).
- T008: idempotent backfill via ``append_events_atomic_verified`` -- a re-run
  appends nothing.
- T009: reducer ordering -- a historical rejection followed by a later real
  approval reduces to ``approved`` (and the inverse: a later rejection wins
  over an earlier approval). A dedicated sanity test also proves that
  swapping in a ``now()``-like (non-historical) timestamp for the backfilled
  event would flip the outcome -- the concrete failure D-PLAN-10 exists to
  prevent.
- T010: the provenance predicate (``stranded_verdict_findings``) is a pure
  function returning non-zero findings before backfill and zero after.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.migration.verdict_provenance_backfill import (
    BACKFILL_ACTOR,
    ProvenanceFinding,
    backfill_verdict_provenance,
    discover_wp_ids_with_review_cycles,
    stranded_verdict_findings,
    terminal_review_artifact,
)
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from specify_cli.status.reducer import event_sourced_review_result
from specify_cli.status.store import append_events_atomic_verified, read_events

# 2026-08-07 (landing fix, verdict-seam-write-unification #3245): this module
# shipped with no module-level pytestmark, orphaning all 15 of its tests (0 CI
# gates select them). Every test here is hermetic (tmp_path fixtures only, no
# real git/subprocess), matching the sibling tests/migration/
# test_backfill_provenance.py's `[pytest.mark.unit, pytest.mark.fast]`
# convention -- this routes the file into fast-tests-core-misc's
# "core-misc" shard (tests/migration is not in that shard's --ignore list).
pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "042-verdict-backfill-demo"
REJECTED_AT = "2026-01-01T00:00:00+00:00"
APPROVED_AT = "2026-06-01T00:00:00+00:00"


def _make_feature_dir(tmp_path: Path, slug: str = MISSION_SLUG) -> Path:
    feature_dir = tmp_path / slug
    feature_dir.mkdir()
    return feature_dir


def _write_review_cycle(
    feature_dir: Path,
    wp_id: str,
    *,
    cycle_number: int,
    verdict: str,
    reviewed_at: str,
    wp_slug: str | None = None,
    reviewer_agent: str = "reviewer-renata",
) -> Path:
    """Write a ``review-cycle-N.md`` artifact that carries a LEGACY ``verdict``
    frontmatter key, simulating a file written before WP06's schema change
    (FR-003/SC-007 -- ``ReviewCycleArtifact`` no longer has a ``verdict``
    field, but every already-committed historical ``.md`` still carries the
    key in its frontmatter forever). Writes the artifact via the live schema
    (no ``verdict`` field), then splices ``verdict: <value>`` into the
    frontmatter directly -- this module's own subject under test
    (``_legacy_frontmatter_verdict``) reads exactly this raw key back.
    """
    dir_name = f"{wp_id}-{wp_slug}" if wp_slug else wp_id
    sub_dir = feature_dir / "tasks" / dir_name
    artifact = ReviewCycleArtifact(
        cycle_number=cycle_number,
        wp_id=wp_id,
        mission_slug=feature_dir.name,
        reviewer_agent=reviewer_agent,
        reviewed_at=reviewed_at,
    )
    path = sub_dir / f"review-cycle-{cycle_number}.md"
    artifact.write(path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"expected frontmatter delimiter in {path}"
    path.write_text(f"---\nverdict: {verdict}\n{text[4:]}", encoding="utf-8")
    return path


def _write_legacy_prose_review_cycle(feature_dir: Path, wp_id: str, *, cycle_number: int) -> Path:
    """Write a pre-frontmatter review-cycle-N.md (plain prose, no ``---``).

    Mirrors the real, on-disk legacy shape this repository still carries
    (see module docstring).
    """
    sub_dir = feature_dir / "tasks" / wp_id
    sub_dir.mkdir(parents=True, exist_ok=True)
    path = sub_dir / f"review-cycle-{cycle_number}.md"
    path.write_text(
        "# WP Review — Cycle 1 (Reviewer Renata)\n\n**Verdict: REJECT**\n",
        encoding="utf-8",
    )
    return path


def _append_real_event(
    feature_dir: Path,
    *,
    wp_id: str,
    from_lane: Lane,
    to_lane: Lane,
    at: str,
    review_result: ReviewResult | None,
    event_id: str,
) -> None:
    """Append a hand-built "real" (non-backfilled) event, simulating a live
    recording-path write for test purposes."""
    event = StatusEvent(
        event_id=event_id,
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor="claude",
        force=False,
        execution_mode="worktree",
        review_result=review_result,
    )
    append_events_atomic_verified(feature_dir, [event])


# ---------------------------------------------------------------------------
# T006 -- SC-008 hermetic pin
# ---------------------------------------------------------------------------


class TestSC008HermeticPin:
    def test_pre_event_rejection_still_refuses_after_backfill(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="only-rejection",
        )

        # Before backfill: no event log exists at all -- the event-sourced
        # reader has no opinion (slot_present=False), the un-migrated case.
        before = event_sourced_review_result(feature_dir, "WP01")
        assert before.slot_present is False

        outcome = backfill_verdict_provenance(feature_dir)
        assert outcome.appended_wp_ids == ("WP01",)

        after = event_sourced_review_result(feature_dir, "WP01")
        assert after.slot_present is True
        assert after.result is not None
        assert after.result.verdict == "changes_requested"
        # The approval guard's own polarity check: "approved" must never be
        # the answer for a WP whose only recorded verdict is a rejection.
        assert after.result.verdict != "approved"


# ---------------------------------------------------------------------------
# T007 -- terminal-verdict discovery + legacy tolerance
# ---------------------------------------------------------------------------


class TestTerminalVerdictDiscovery:
    def test_terminal_is_highest_cycle_number(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP02",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="multi-cycle",
        )
        _write_review_cycle(
            feature_dir,
            "WP02",
            cycle_number=2,
            verdict="approved",
            reviewed_at=APPROVED_AT,
            wp_slug="multi-cycle",
        )

        terminal = terminal_review_artifact(feature_dir, "WP02")
        assert terminal is not None
        artifact, path, legacy_verdict = terminal
        assert artifact.cycle_number == 2
        assert legacy_verdict == "approved"
        assert path.name == "review-cycle-2.md"

    def test_legacy_pre_frontmatter_artifact_is_skipped_not_crashed(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_legacy_prose_review_cycle(feature_dir, "WP03", cycle_number=1)

        # No crash; no fabricated terminal verdict from an unparseable file.
        assert terminal_review_artifact(feature_dir, "WP03") is None
        # Discovery is filename-based (a review-cycle-*.md sibling exists), so
        # WP03 IS discovered -- but since its terminal artifact cannot be
        # parsed, it never surfaces as a stranded finding: never fabricates a
        # false "stranded" alarm from unreadable prose.
        assert "WP03" in discover_wp_ids_with_review_cycles(feature_dir)
        assert stranded_verdict_findings(feature_dir) == []

    def test_no_tasks_dir_returns_none_and_empty(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        assert terminal_review_artifact(feature_dir, "WP01") is None
        assert discover_wp_ids_with_review_cycles(feature_dir) == []


# ---------------------------------------------------------------------------
# T008 -- idempotent backfill
# ---------------------------------------------------------------------------


class TestIdempotentBackfill:
    def test_rerun_appends_nothing(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="idempotent",
        )

        first = backfill_verdict_provenance(feature_dir)
        assert first.appended_count == 1
        events_path = feature_dir / "status.events.jsonl"
        first_line_count = len(events_path.read_text(encoding="utf-8").splitlines())

        second = backfill_verdict_provenance(feature_dir)
        assert second.appended_count == 0
        assert second.appended_wp_ids == ()
        second_line_count = len(events_path.read_text(encoding="utf-8").splitlines())
        assert second_line_count == first_line_count

    def test_deterministic_event_id_is_stable_across_runs(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="approved",
            reviewed_at=APPROVED_AT,
            wp_slug="deterministic",
        )
        backfill_verdict_provenance(feature_dir)
        events = read_events(feature_dir)
        assert len(events) == 1
        assert events[0].actor == BACKFILL_ACTOR
        assert events[0].event_id  # non-empty deterministic ULID

    def test_wp_with_existing_event_slot_is_skipped(self, tmp_path: Path) -> None:
        """A lane-only approval (from_lane=IN_REVIEW, no ReviewResult) already
        sets slot_present=True; backfill must not layer a conflicting
        rejection event on top of it (T007 supersession guard)."""
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="lane-only-approval",
        )
        _append_real_event(
            feature_dir,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at=APPROVED_AT,
            review_result=None,
            event_id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        )
        lookup_before = event_sourced_review_result(feature_dir, "WP01")
        assert lookup_before.slot_present is True

        outcome = backfill_verdict_provenance(feature_dir)
        assert outcome.appended_wp_ids == ()
        assert len(read_events(feature_dir)) == 1


# ---------------------------------------------------------------------------
# T009 -- reducer ordering discipline
# ---------------------------------------------------------------------------


class TestReducerOrdering:
    def test_historical_rejection_then_later_real_approval_resolves_approved(self, tmp_path: Path) -> None:
        """#5279 re-pin: spec_kitty_events 10.4.0 (#4990,
        ``diary._should_apply_event`` arm ii) drops a forward event whose
        ``from_lane`` does not causally follow the rollback's ``to_lane`` --
        a bare later approval no longer resurrects a rejection on its own
        (see ``test_bare_approval_after_rejection_resolves_changes_requested``
        below, the positive pin for that contract). The backfilled rejection
        lands WP01 on ``in_progress`` (``in_review -> in_progress``), so this
        test now threads a REAL causal rework chain -- ``in_progress ->
        for_review -> in_review`` -- between the backfilled rejection and the
        real approval, each hop's ``from_lane`` matching the lane the prior
        hop left the WP in, before the approval (``in_review -> approved``)
        can apply.
        """
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="rejection-then-approval",
        )
        backfill_verdict_provenance(feature_dir)

        # Causal rework chain: each hop's from_lane matches the lane the
        # prior event (the backfilled rejection, then this hop) left WP01 in.
        _append_real_event(
            feature_dir,
            wp_id="WP01",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.FOR_REVIEW,
            at="2026-03-01T00:00:00+00:00",
            review_result=None,
            event_id="01ARZ3NDEKTSV4RRFFQ69G5FB0",
        )
        _append_real_event(
            feature_dir,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            at="2026-04-01T00:00:00+00:00",
            review_result=None,
            event_id="01ARZ3NDEKTSV4RRFFQ69G5FB1",
        )

        # A real, later approval recorded on the live path (later `at`),
        # now causally following the rework chain above.
        _append_real_event(
            feature_dir,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at=APPROVED_AT,
            review_result=ReviewResult(reviewer="reviewer-renata", verdict="approved", reference="approval:WP01"),
            event_id="01ARZ3NDEKTSV4RRFFQ69G5FAW",
        )

        result = event_sourced_review_result(feature_dir, "WP01")
        assert result.slot_present is True
        assert result.result is not None
        assert result.result.verdict == "approved"

    def test_bare_approval_after_rejection_resolves_changes_requested(self, tmp_path: Path) -> None:
        """Positive pin (#4990 contract, #5279): a real approval with NO
        rework causally following the backfilled rejection carries
        ``from_lane=in_review`` -- the SAME lane the rejection itself
        branched off of, not the ``in_progress`` lane the rejection left the
        WP in -- so it is causally concurrent with the rejection, not a
        rework of it, and ``diary._should_apply_event`` correctly drops it
        (arm ii). This is the same two-event shape
        ``test_historical_rejection_then_later_real_approval_resolves_approved``
        used before #4990/#5279; that test now additionally threads a real
        rework chain to reach ``approved``, and this test keeps the original
        bare-approval shape as the contract pin for the drop.
        """
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="bare-approval-after-rejection",
        )
        backfill_verdict_provenance(feature_dir)

        _append_real_event(
            feature_dir,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at=APPROVED_AT,
            review_result=ReviewResult(reviewer="reviewer-renata", verdict="approved", reference="approval:WP01"),
            event_id="01ARZ3NDEKTSV4RRFFQ69G5FB2",
        )

        result = event_sourced_review_result(feature_dir, "WP01")
        assert result.slot_present is True
        assert result.result is not None
        assert result.result.verdict == "changes_requested"

    def test_later_rejection_wins_over_earlier_approval(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="approved",
            reviewed_at=REJECTED_AT,
            wp_slug="approval-then-rejection",
        )
        backfill_verdict_provenance(feature_dir)

        _append_real_event(
            feature_dir,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at=APPROVED_AT,
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="changes_requested",
                reference="review:WP01",
            ),
            event_id="01ARZ3NDEKTSV4RRFFQ69G5FAX",
        )

        result = event_sourced_review_result(feature_dir, "WP01")
        assert result.slot_present is True
        assert result.result is not None
        assert result.result.verdict == "changes_requested"

    def test_now_like_at_would_wrongly_resurrect_the_rejection(self, tmp_path: Path) -> None:
        """Sanity guard (T009): construct the SAME two-event scenario as
        ``test_bare_approval_after_rejection_resolves_changes_requested``
        (#5279 re-pin -- that test now carries the bare, no-rework shape this
        docstring describes; the sibling ``..._resolves_approved`` test
        gained a real rework chain and no longer matches it) but stamp the
        rejection with a ``now()``-like (i.e. LATER than the real approval)
        timestamp instead of its true historical one -- proving
        the discipline in ``_backfill_event_for_wp`` (using the artifact's own
        ``reviewed_at``, never ``now()``) is load-bearing, not incidental.
        """
        feature_dir = _make_feature_dir(tmp_path)
        now_like_at = "2026-12-31T23:59:59+00:00"  # later than APPROVED_AT

        _append_real_event(
            feature_dir,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at=APPROVED_AT,
            review_result=ReviewResult(reviewer="reviewer-renata", verdict="approved", reference="approval:WP01"),
            event_id="01ARZ3NDEKTSV4RRFFQ69G5FAY",
        )
        # A hand-built rejection event using a now()-like `at` -- the exact
        # bug D-PLAN-10 forbids, reproduced here deliberately to prove the
        # anti-resurrection guard is real.
        _append_real_event(
            feature_dir,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at=now_like_at,
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="changes_requested",
                reference="review:WP01",
            ),
            event_id="01ARZ3NDEKTSV4RRFFQ69G5FAZ",
        )

        result = event_sourced_review_result(feature_dir, "WP01")
        # The late-stamped rejection wrongly wins -- this is the failure mode
        # the production backfill's historical-`at` discipline prevents.
        assert result.result is not None
        assert result.result.verdict == "changes_requested"


# ---------------------------------------------------------------------------
# T010 -- provenance predicate (pure function)
# ---------------------------------------------------------------------------


class TestStrandedVerdictFindings:
    def test_nonzero_before_zero_after_backfill(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="stranded",
        )

        before = stranded_verdict_findings(feature_dir)
        assert before == [ProvenanceFinding(wp_id="WP01", has_md_verdict=True, has_event_slot=False)]

        backfill_verdict_provenance(feature_dir)

        after = stranded_verdict_findings(feature_dir)
        assert after == []

    def test_empty_mission_has_no_findings(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        assert stranded_verdict_findings(feature_dir) == []

    def test_multiple_wps_only_stranded_ones_reported(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="stranded",
        )
        _write_review_cycle(
            feature_dir,
            "WP02",
            cycle_number=1,
            verdict="approved",
            reviewed_at=APPROVED_AT,
            wp_slug="also-migrated",
        )
        backfill_verdict_provenance(feature_dir)  # migrates both

        _write_review_cycle(
            feature_dir,
            "WP03",
            cycle_number=1,
            verdict="rejected",
            reviewed_at=REJECTED_AT,
            wp_slug="freshly-stranded",
        )

        findings = stranded_verdict_findings(feature_dir)
        assert findings == [ProvenanceFinding(wp_id="WP03", has_md_verdict=True, has_event_slot=False)]


# ---------------------------------------------------------------------------
# mission_id propagation (best-effort, tolerant)
# ---------------------------------------------------------------------------


class TestMissionIdPropagation:
    def test_mission_id_read_from_meta_json(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        (feature_dir / "meta.json").write_text(json.dumps({"mission_id": "01JMISSIONULID0000000000AA"}), encoding="utf-8")
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="approved",
            reviewed_at=APPROVED_AT,
            wp_slug="with-mission-id",
        )

        backfill_verdict_provenance(feature_dir)
        events = read_events(feature_dir)
        assert events[0].mission_id == "01JMISSIONULID0000000000AA"

    def test_missing_meta_json_yields_none_mission_id(self, tmp_path: Path) -> None:
        feature_dir = _make_feature_dir(tmp_path)
        _write_review_cycle(
            feature_dir,
            "WP01",
            cycle_number=1,
            verdict="approved",
            reviewed_at=APPROVED_AT,
            wp_slug="no-meta",
        )
        backfill_verdict_provenance(feature_dir)
        events = read_events(feature_dir)
        assert events[0].mission_id is None
