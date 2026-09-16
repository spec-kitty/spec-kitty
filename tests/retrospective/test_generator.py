"""Tests for the pure-Python retrospective generator (WP02).

Coverage target: ≥ 90% of src/specify_cli/retrospective/generator.py

Test classes:
    TestGeneratorDeterminism     — byte-identical records from consecutive calls
    TestGeneratorPerformance     — wall-clock < 2.0s for the largest fixture
    TestFindingsClassification   — per-fixture expectations for helped/not_helpful/gaps/proposals
    TestFindingsStatus           — has_findings vs ran_no_findings resolution (T010)
    TestRiskClass                — proposal risk_class classification (T011)

Env-var invariant: NO SPEC_KITTY_RETROSPECTIVE or SPEC_KITTY_MODE env mutations in this file.

FR refs: FR-006, FR-007, FR-010
"""

from __future__ import annotations

import dataclasses
import json
import time
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


from specify_cli.retrospective.generator import (
    GENERATOR_VERSION,
    LOW_RISK_PROPOSAL_KINDS,
    _EvidenceRegistry,
    _build_event_mining_findings,
    _classify_risk,
    generate_retrospective,
)
from specify_cli.status.lifecycle_events import emit_reviewer_self_approval
from specify_cli.retrospective.policy import default_policy
from specify_cli.retrospective.schema import (
    GenActor,
    GenEvidenceRef,
    GenFinding,
    GenProposal,
    GenProvenance,
    GenRetrospectiveRecord,
    RecordValidationError,
    validate_record,
)
from tests._perf_helpers import assert_timing_budget

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
# fixtures/kitty-specs/<mission>/ layout
SIMPLE_CLEAN = "simple-clean"
MID_WITH_REJECTIONS = "mid-with-rejections"
LARGE_WITH_GAPS = "large-with-gaps"


def make_policy():
    """Return a fresh default policy for each test."""
    return default_policy()


# ---------------------------------------------------------------------------
# TestGeneratorDeterminism
# ---------------------------------------------------------------------------


class TestGeneratorDeterminism:
    """Two consecutive calls with identical inputs produce byte-identical records."""

    def test_simple_clean_is_deterministic(self) -> None:
        """simple-clean fixture: two calls produce identical JSON with sort_keys."""
        policy = make_policy()
        ts = "2026-05-19T12:00:00+00:00"
        actor = GenActor(kind="runtime", id="test-agent", display="Test Agent")

        record1 = generate_retrospective(
            SIMPLE_CLEAN, policy, FIXTURES_ROOT,
            invoked_at=ts, actor=actor,
        )
        record2 = generate_retrospective(
            SIMPLE_CLEAN, policy, FIXTURES_ROOT,
            invoked_at=ts, actor=actor,
        )

        json1 = json.dumps(dataclasses.asdict(record1), sort_keys=True)
        json2 = json.dumps(dataclasses.asdict(record2), sort_keys=True)
        assert json1 == json2, "Consecutive calls produced different records"

    def test_large_with_gaps_is_deterministic(self) -> None:
        """large-with-gaps fixture: two calls produce byte-identical JSON."""
        policy = make_policy()
        ts = "2026-05-19T12:00:00+00:00"
        actor = GenActor(kind="runtime", id="test-agent", display="Test Agent")

        record1 = generate_retrospective(
            LARGE_WITH_GAPS, policy, FIXTURES_ROOT,
            invoked_at=ts, actor=actor,
        )
        record2 = generate_retrospective(
            LARGE_WITH_GAPS, policy, FIXTURES_ROOT,
            invoked_at=ts, actor=actor,
        )

        json1 = json.dumps(dataclasses.asdict(record1), sort_keys=True)
        json2 = json.dumps(dataclasses.asdict(record2), sort_keys=True)
        assert json1 == json2, "Consecutive calls produced different records for large fixture"

    def test_generator_version_is_stable(self) -> None:
        """GENERATOR_VERSION is a non-empty string."""
        assert isinstance(GENERATOR_VERSION, str)
        assert len(GENERATOR_VERSION) > 0
        assert GENERATOR_VERSION == "1.0"

    def test_record_generator_version_field(self) -> None:
        """Generated record carries the correct generator_version."""
        policy = make_policy()
        record = generate_retrospective(
            SIMPLE_CLEAN, policy, FIXTURES_ROOT, invoked_at="2026-01-01T00:00:00+00:00",
        )
        assert record.generator_version == GENERATOR_VERSION


# ---------------------------------------------------------------------------
# TestGeneratorPerformance
# ---------------------------------------------------------------------------


class TestGeneratorPerformance:
    """Wall-clock time constraint: largest fixture generates in < 2.0 seconds (NFR-005)."""

    def test_generates_large_fixture(self) -> None:
        """Functional half of the #4015 split: large-with-gaps fixture is produced."""
        policy = make_policy()
        record = generate_retrospective(
            LARGE_WITH_GAPS, policy, FIXTURES_ROOT,
            invoked_at="2026-05-19T12:00:00+00:00",
        )
        # Sanity check: record was actually produced
        assert record.mission_slug == LARGE_WITH_GAPS

    @pytest.mark.performance
    def test_large_fixture_under_2s(self) -> None:
        """Generating the large-with-gaps fixture takes < 2.0s wall clock (#4015 split)."""
        policy = make_policy()
        start = time.monotonic()
        generate_retrospective(
            LARGE_WITH_GAPS, policy, FIXTURES_ROOT,
            invoked_at="2026-05-19T12:00:00+00:00",
        )
        elapsed = time.monotonic() - start
        assert_timing_budget(elapsed, 2.0, name="elapsed")

    @pytest.mark.performance
    def test_simple_fixture_under_500ms(self) -> None:
        """Generating the simple-clean fixture takes < 500ms (should be very fast)."""
        policy = make_policy()
        start = time.monotonic()
        generate_retrospective(
            SIMPLE_CLEAN, policy, FIXTURES_ROOT,
            invoked_at="2026-05-19T12:00:00+00:00",
        )
        elapsed = time.monotonic() - start
        assert elapsed < 0.5, f"Simple fixture took {elapsed:.3f}s (limit: 500ms)"


# ---------------------------------------------------------------------------
# TestFindingsClassification
# ---------------------------------------------------------------------------


class TestFindingsClassification:
    """Per-fixture expectations for helped, not_helpful, gaps, proposals."""

    def test_simple_clean_runs_no_findings(self) -> None:
        """simple-clean: no rejection cycles, no clarification markers → ran_no_findings."""
        policy = make_policy()
        record = generate_retrospective(SIMPLE_CLEAN, policy, FIXTURES_ROOT)
        # Zero rejection cycles means all-clean: not worth reporting
        assert record.not_helpful == [], "No rejection cycles expected"
        # No open clarification markers or unmapped FRs
        assert record.gaps == [], "No gaps expected for simple clean mission"
        # Clean WPs don't generate helped findings (tautology rule R-4)
        assert record.helped == [], "Tautological helped findings should be omitted"
        # No proposals from a clean mission
        assert record.proposals == [], "No proposals expected"

    def test_reviewer_feedback_transition_is_review_loop(self) -> None:
        """Only documented reviewer feedback counts as a rejection cycle."""
        from specify_cli.retrospective.generator import (
            _detect_lane_friction,
            _detect_rejection_cycles,
        )

        events = [
            {
                "wp_id": "WP01",
                "from_lane": "for_review",
                "to_lane": "in_progress",
                "actor": "user",
                "force": True,
                "event_id": "e1",
            },
            {
                "wp_id": "WP02",
                "from_lane": "in_review",
                "to_lane": "planned",
                "actor": "user",
                "review_ref": "review-cycle://mission/WP02/review-cycle-1.md",
                "event_id": "e2",
            },
            {
                "wp_id": "WP03",
                "from_lane": "in_progress",
                "to_lane": "planned",
                "actor": "user",
                "force": True,
                "event_id": "e3",
            },
        ]

        assert _detect_rejection_cycles(events) == {"WP02": 1}
        assert _detect_lane_friction(events) == {"WP01": 1, "WP03": 1}

    def test_reviewer_self_approval_is_process_finding(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "demo"
        feature_dir.mkdir(parents=True)
        event = emit_reviewer_self_approval(
            feature_dir,
            mission_slug="demo",
            wp_id="WP02",
            implementing_actor="codex",
            intended_reviewer="claude",
            failure_reason="exit 1",
        )
        assert event is not None

        not_helpful, gaps = _build_event_mining_findings(
            events=[event],
            events_rel="kitty-specs/demo/status.events.jsonl",
            finding_id_counters={},
            ev_reg=_EvidenceRegistry(),
        )

        assert gaps == []
        assert len(not_helpful) == 1
        finding = not_helpful[0]
        assert finding.category == "process"
        assert "self-review fallback" in finding.summary
        assert "claude failed" in finding.details

    def test_single_arbiter_override_details_do_not_read_as_recurring(self) -> None:
        """#4065: a first and only arbiter override must not read as a
        recurring pattern — the "recurring use" clause is count > 1 only."""
        events = [
            {
                "wp_id": "WP04",
                "actor": "user",
                "reason": "Arbiter override: deadlock at cycle 1",
                "from_lane": "for_review",
                "to_lane": "approved",
                "event_id": "a1",
            },
        ]
        not_helpful, gaps = _build_event_mining_findings(
            events=events,
            events_rel="kitty-specs/demo/status.events.jsonl",
            finding_id_counters={},
            ev_reg=_EvidenceRegistry(),
        )

        assert not_helpful == []
        assert len(gaps) == 1
        finding = gaps[0]
        assert finding.summary == "Arbiter override needed for WP04 (1x)"
        assert "escape hatch" in finding.details
        assert "ecurring use" not in finding.details, (
            f"a 1x override must not read as a pattern: {finding.details!r}"
        )

    def test_repeated_arbiter_overrides_keep_recurring_use_reading(self) -> None:
        """#4065: two genuinely separate overrides on one WP still read as a
        recurring pattern worth a policy/guard look."""
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
        not_helpful, gaps = _build_event_mining_findings(
            events=events,
            events_rel="kitty-specs/demo/status.events.jsonl",
            finding_id_counters={},
            ev_reg=_EvidenceRegistry(),
        )

        assert not_helpful == []
        assert len(gaps) == 1
        finding = gaps[0]
        assert finding.summary == "Arbiter override needed for WP07 (2x)"
        assert "escape hatch" in finding.details
        assert "Recurring use suggests the normal review path is blocked" in finding.details

    def test_mid_with_backward_moves_has_lane_friction(self) -> None:
        """Backward moves without reviewer feedback are process friction, not rejections."""
        policy = make_policy()
        record = generate_retrospective(MID_WITH_REJECTIONS, policy, FIXTURES_ROOT)

        not_helpful_wps = {f.summary for f in record.not_helpful}
        assert any("WP02" in s for s in not_helpful_wps), "WP02 lane friction expected"
        assert any("WP03" in s for s in not_helpful_wps), "WP03 lane friction expected"
        assert len(record.not_helpful) == 2
        assert {f.category for f in record.not_helpful} == {"process"}
        assert all("rejection" not in f.summary.lower() for f in record.not_helpful)

    def test_mid_with_lane_friction_clean_wps_in_helped(self) -> None:
        """WPs with no backward movement are still notable by contrast."""
        policy = make_policy()
        record = generate_retrospective(MID_WITH_REJECTIONS, policy, FIXTURES_ROOT)

        helped_wps = {f.summary for f in record.helped}
        assert any("WP01" in s for s in helped_wps), "WP01 clean completion expected in helped"
        assert any("WP04" in s for s in helped_wps), "WP04 clean completion expected in helped"

    def test_large_with_gaps_has_clarification_gap(self) -> None:
        """large-with-gaps: spec.md contains [NEEDS CLARIFICATION:] markers → gaps."""
        policy = make_policy()
        record = generate_retrospective(LARGE_WITH_GAPS, policy, FIXTURES_ROOT)

        clarification_gaps = [g for g in record.gaps if "clarification marker" in g.summary.lower()]
        assert len(clarification_gaps) >= 2, (
            f"Expected ≥2 clarification gaps, got {len(clarification_gaps)}: "
            f"{[g.summary for g in clarification_gaps]}"
        )

    def test_large_with_gaps_has_unmapped_frs(self) -> None:
        """large-with-gaps: FR-007 and FR-008 appear in spec.md but no WP covers them."""
        policy = make_policy()
        record = generate_retrospective(LARGE_WITH_GAPS, policy, FIXTURES_ROOT)

        unmapped_gaps = [g for g in record.gaps if "no WP coverage" in g.summary]
        unmapped_fr_ids = {g.summary.split()[0] for g in unmapped_gaps}
        assert "FR-007" in unmapped_fr_ids, "FR-007 should be flagged as unmapped"
        assert "FR-008" in unmapped_fr_ids, "FR-008 should be flagged as unmapped"

    def test_large_with_gaps_has_lane_friction(self) -> None:
        """large-with-gaps: WP02 and WP04 had backward moves without reviewer feedback."""
        policy = make_policy()
        record = generate_retrospective(LARGE_WITH_GAPS, policy, FIXTURES_ROOT)

        not_helpful_wps = {f.summary for f in record.not_helpful}
        assert any("WP02" in s for s in not_helpful_wps)
        assert any("WP04" in s for s in not_helpful_wps)
        assert {f.category for f in record.not_helpful} == {"process"}

    def test_all_findings_have_evidence_refs(self) -> None:
        """Every finding must carry ≥1 evidence_ref that resolves to top-level evidence_refs."""
        policy = make_policy()
        record = generate_retrospective(LARGE_WITH_GAPS, policy, FIXTURES_ROOT)
        known_ids = {e.id for e in record.evidence_refs}

        for finding in (*record.helped, *record.not_helpful, *record.gaps):
            assert len(finding.evidence_refs) >= 1, (
                f"Finding {finding.id!r} has no evidence_refs"
            )
            for ref_id in finding.evidence_refs:
                assert ref_id in known_ids, (
                    f"Finding {finding.id!r} references unknown evidence_ref {ref_id!r}"
                )

    def test_snapshot_large_with_gaps(self) -> None:
        """Snapshot regression check for large-with-gaps fixture.

        Compares key structural properties against the expected snapshot file.
        We check finding counts, finding IDs, and finding summaries to detect regressions.
        """
        policy = make_policy()
        record = generate_retrospective(
            LARGE_WITH_GAPS, policy, FIXTURES_ROOT,
            invoked_at="2026-05-19T12:00:00+00:00",
            actor=GenActor(kind="runtime", id="spec-kitty-generator", display="Spec Kitty Generator"),
        )
        snapshot_path = FIXTURES_ROOT / "expected" / "large-with-gaps.expected.yaml"
        assert snapshot_path.exists(), f"Snapshot file not found: {snapshot_path}"

        # Load and parse the YAML snapshot for key assertions
        from ruamel.yaml import YAML
        yaml = YAML(typ="safe")
        expected = yaml.load(snapshot_path.read_text(encoding="utf-8"))

        # Check structural counts
        assert len(record.helped) == len(expected["helped"]), (
            f"helped count mismatch: got {len(record.helped)}, expected {len(expected['helped'])}"
        )
        assert len(record.not_helpful) == len(expected["not_helpful"]), (
            "not_helpful count mismatch"
        )
        assert len(record.gaps) == len(expected["gaps"]), (
            f"gaps count mismatch: got {len(record.gaps)}, expected {len(expected['gaps'])}"
        )
        assert len(record.proposals) == len(expected["proposals"]), (
            "proposals count mismatch"
        )
        assert len(record.evidence_refs) == len(expected["evidence_refs"]), (
            "evidence_refs count mismatch"
        )

        # Check findings_status
        assert record.findings_status == expected["findings_status"]

        # Check finding summaries (order-insensitive)
        actual_gap_summaries = {g.summary for g in record.gaps}
        expected_gap_summaries = {g["summary"] for g in expected["gaps"]}
        assert actual_gap_summaries == expected_gap_summaries, (
            "Gap summaries differ.\n"
            f"  Actual: {sorted(actual_gap_summaries)}\n"
            f"  Expected: {sorted(expected_gap_summaries)}"
        )

    def test_sorting_is_stable(self) -> None:
        """Each finding list is sorted by (category, summary) for byte-stable ordering."""
        policy = make_policy()
        record = generate_retrospective(LARGE_WITH_GAPS, policy, FIXTURES_ROOT)

        for lst, name in (
            (record.helped, "helped"),
            (record.not_helpful, "not_helpful"),
            (record.gaps, "gaps"),
            (record.proposals, "proposals"),
        ):
            sort_keys = [(f.category, f.summary) for f in lst]
            assert sort_keys == sorted(sort_keys), (
                f"{name} list is not sorted by (category, summary)"
            )

    def test_missing_optional_artifacts_do_not_raise(self) -> None:
        """Generator tolerates missions with missing optional artifacts (research.md etc)."""
        # mid-with-rejections has no research.md — should not raise
        policy = make_policy()
        # Should complete without exception
        record = generate_retrospective(MID_WITH_REJECTIONS, policy, FIXTURES_ROOT)
        assert record is not None


# ---------------------------------------------------------------------------
# TestRejectionAfterApproval (#3687)
# ---------------------------------------------------------------------------


def _ev(
    n: int,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    *,
    actor: str = "claude",
    force: bool = False,
    reason: str | None = None,
    review_ref: str | None = None,
) -> dict:
    """Build a minimal status event for retrospective generator tests."""
    return {
        "actor": actor,
        "at": f"2026-01-01T00:{n:02d}:00+00:00",
        "event_id": f"01TESTRR00000000000000000{n:02d}",
        "evidence": None,
        "force": force,
        "from_lane": from_lane,
        "reason": reason,
        "review_ref": review_ref,
        "to_lane": to_lane,
        "wp_id": wp_id,
    }


def _write_mission(root: Path, slug: str, mission_number: int, events: list[dict]) -> None:
    """Write a minimal kitty-specs/<slug>/ mission with the given status events."""
    feature_dir = root / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    meta = {
        "mission_id": f"01RRRRRRRRRRRRRRRRRRRRRRR{mission_number:02d}",
        "mission_slug": slug,
        "friendly_name": slug.replace("-", " ").title(),
        "mission_type": "software-dev",
        "target_branch": "main",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n\n### FR-001\nReq.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )


_CLEAN_RUN = [
    ("planned", "in_progress"),
    ("in_progress", "for_review"),
    ("for_review", "in_review"),
    ("in_review", "approved"),
    ("approved", "done"),
]


class TestRejectionAfterApproval:
    """Rewinds out of approved/done are rework — never a helped/not_helpful contradiction.

    Regression tests for #3687: a WP sent back from ``approved`` counts as a
    rejection cycle when the event carries review feedback and as lane friction
    otherwise, and a WP with >1 implementation cycle never appears in
    ``helped`` even when the lane-history detectors call it clean.
    """

    def test_approved_rewind_with_feedback_is_rejection(self) -> None:
        """approved→planned with review feedback is a rejection; without it, friction."""
        from specify_cli.retrospective.generator import (
            _detect_lane_friction,
            _detect_rejection_cycles,
        )

        events = [
            # Rejection after approval, documented feedback (#3687 repro shape:
            # move-task WP02 --to planned --force --review-feedback-file <path>)
            {
                "wp_id": "WP02",
                "from_lane": "approved",
                "to_lane": "planned",
                "actor": "orchestrator",
                "force": True,
                "reason": "live verification failed",
                "review_ref": "review-cycle://mission/WP02/review-cycle-2.md",
                "event_id": "e1",
            },
            # Feedback-free force rewind out of approved → lane friction
            {
                "wp_id": "WP03",
                "from_lane": "approved",
                "to_lane": "planned",
                "actor": "user",
                "force": True,
                "reason": "rewind without documented feedback",
                "event_id": "e2",
            },
            # Force rewind out of terminal done → lane friction
            {
                "wp_id": "WP04",
                "from_lane": "done",
                "to_lane": "planned",
                "actor": "user",
                "force": True,
                "reason": "post-merge rework",
                "event_id": "e3",
            },
        ]

        assert _detect_rejection_cycles(events) == {"WP02": 1}
        assert _detect_lane_friction(events) == {"WP03": 1, "WP04": 1}

    def test_rejection_after_approval_never_lands_in_helped(self, tmp_path: Path) -> None:
        """#3687 repro: a WP rejected from approved must not get a helped finding."""
        # WP02: implement → review → approve, then rejected after approval
        # (move-task --to planned --force --review-feedback-file), re-implemented,
        # re-reviewed, re-approved, done. WP01 runs the same mission cleanly.
        wp02_moves = [
            ("planned", "in_progress", {}),
            ("in_progress", "for_review", {}),
            ("for_review", "in_review", {}),
            ("in_review", "approved", {}),
            (
                "approved",
                "planned",
                {
                    "actor": "orchestrator",
                    "force": True,
                    "reason": "approved fix failed live verification",
                    "review_ref": "review-cycle://mission/rje/WP02/review-cycle-2.md",
                },
            ),
            ("planned", "in_progress", {}),
            ("in_progress", "for_review", {}),
            ("for_review", "in_review", {}),
            ("in_review", "approved", {}),
            ("approved", "done", {}),
        ]
        events: list[dict] = []
        n = 0
        for from_lane, to_lane, extra in wp02_moves:
            n += 1
            events.append(_ev(n, "WP02", from_lane, to_lane, **extra))
        for from_lane, to_lane in _CLEAN_RUN:
            n += 1
            events.append(_ev(n, "WP01", from_lane, to_lane))
        _write_mission(tmp_path, "rejection-after-approval", 1, events)

        policy = make_policy()
        record = generate_retrospective("rejection-after-approval", policy, tmp_path)

        helped_wps = {h.summary.split()[0] for h in record.helped}
        not_helpful_wps = {f.summary.split()[0] for f in record.not_helpful}
        # WP02 had a real rejection cycle — it must not be called clean.
        assert "WP01" in helped_wps, "WP01 clean completion expected in helped"
        assert "WP02" not in helped_wps, (
            f"#3687 contradiction: WP02 appears in helped ({record.helped}) "
            "while also being flagged in not_helpful"
        )
        assert helped_wps & not_helpful_wps == set(), (
            f"helped/not_helpful contradiction for {helped_wps & not_helpful_wps}"
        )
        not_helpful_summaries = {f.summary for f in record.not_helpful}
        assert "WP02 required 1 rejection cycle(s) before approval" in not_helpful_summaries
        assert "WP02 needed 2 implementation cycles" in not_helpful_summaries

    def test_multi_impl_cycle_wp_excluded_from_helped(self, tmp_path: Path) -> None:
        """Belt-and-suspenders: >1 impl cycle excludes a WP from helped (#3687).

        WP01 re-enters in_progress via blocked→planned (not in the backward-move
        set), so the lane-history detectors call it clean while the cycle
        detector flags it — helped must lose that disagreement.
        """
        events: list[dict] = []
        n = 0
        wp01_moves = [
            ("planned", "in_progress", {}),
            ("in_progress", "blocked", {"reason": "waiting on upstream"}),
            ("blocked", "planned", {"actor": "user", "force": True, "reason": "unblocked"}),
            ("planned", "in_progress", {}),
            ("in_progress", "for_review", {}),
            ("for_review", "in_review", {}),
            ("in_review", "approved", {}),
            ("approved", "done", {}),
        ]
        for from_lane, to_lane, extra in wp01_moves:
            n += 1
            events.append(_ev(n, "WP01", from_lane, to_lane, **extra))
        for from_lane, to_lane in _CLEAN_RUN:
            n += 1
            events.append(_ev(n, "WP02", from_lane, to_lane))
        # WP03 rejection keeps the helped gate open (rejection_counts non-empty).
        for from_lane, to_lane, extra in [
            ("planned", "in_progress", {}),
            ("in_progress", "for_review", {}),
            ("for_review", "in_review", {}),
            (
                "in_review",
                "planned",
                {"review_ref": "review-cycle://mission/ico/WP03/review-cycle-1.md"},
            ),
            ("planned", "in_progress", {}),
            ("in_progress", "for_review", {}),
            ("for_review", "in_review", {}),
            ("in_review", "approved", {}),
            ("approved", "done", {}),
        ]:
            n += 1
            events.append(_ev(n, "WP03", from_lane, to_lane, **extra))
        _write_mission(tmp_path, "impl-cycle-only", 2, events)

        policy = make_policy()
        record = generate_retrospective("impl-cycle-only", policy, tmp_path)

        helped_wps = {h.summary.split()[0] for h in record.helped}
        not_helpful_wps = {f.summary.split()[0] for f in record.not_helpful}
        assert "WP02" in helped_wps, "WP02 clean completion expected in helped"
        assert "WP01" not in helped_wps, (
            f"#3687 contradiction: WP01 needed 2 implementation cycles yet appears "
            f"in helped ({record.helped})"
        )
        assert helped_wps & not_helpful_wps == set()
        assert "WP01 needed 2 implementation cycles" in {f.summary for f in record.not_helpful}


# ---------------------------------------------------------------------------
# TestFindingsStatus
# ---------------------------------------------------------------------------


class TestFindingsStatus:
    """findings_status resolution: has_findings vs ran_no_findings (T010).

    Invariant: ONLY "has_findings" or "ran_no_findings" may appear in a persisted record.
    "missing" and "failed" are event-payload-only states.
    """

    def test_simple_clean_has_ran_no_findings(self) -> None:
        """Zero-problem mission → ran_no_findings (no tautological 'all fine' signal)."""
        policy = make_policy()
        record = generate_retrospective(SIMPLE_CLEAN, policy, FIXTURES_ROOT)
        assert record.findings_status == "ran_no_findings"

    def test_mid_with_rejections_has_has_findings(self) -> None:
        """Mission with rejection cycles → has_findings."""
        policy = make_policy()
        record = generate_retrospective(MID_WITH_REJECTIONS, policy, FIXTURES_ROOT)
        assert record.findings_status == "has_findings"

    def test_large_with_gaps_has_has_findings(self) -> None:
        """Mission with gaps/rejections/clarifications → has_findings."""
        policy = make_policy()
        record = generate_retrospective(LARGE_WITH_GAPS, policy, FIXTURES_ROOT)
        assert record.findings_status == "has_findings"

    def test_no_record_can_have_missing_status(self) -> None:
        """validate_record rejects findings_status='missing' (event-payload-only state)."""
        record = GenRetrospectiveRecord(
            schema_version=1,
            mission_id="01TEST00000000000000000000",
            mission_slug="test-mission",
            mission_number=None,
            friendly_name="Test",
            mission_type="software-dev",
            target_branch="main",
            created_at="2026-01-01T00:00:00+00:00",
            created_by=GenActor(kind="runtime", id="test"),
            provenance=GenProvenance(kind="runtime_post_completion", invoked_at="2026-01-01T00:00:00+00:00"),
            policy_source={},
            findings_status="missing",  # type: ignore[arg-type]  # intentional invalid value
            helped=[],
            not_helpful=[],
            gaps=[],
            proposals=[],
            evidence_refs=[],
            generator_version="1.0",
        )
        with pytest.raises(RecordValidationError) as exc_info:
            validate_record(record)
        assert "invalid_findings_status" in str(exc_info.value)
        assert "missing" in str(exc_info.value)

    def test_no_record_can_have_failed_status(self) -> None:
        """validate_record rejects findings_status='failed' (event-payload-only state)."""
        record = GenRetrospectiveRecord(
            schema_version=1,
            mission_id="01TEST00000000000000000000",
            mission_slug="test-mission",
            mission_number=None,
            friendly_name="Test",
            mission_type="software-dev",
            target_branch="main",
            created_at="2026-01-01T00:00:00+00:00",
            created_by=GenActor(kind="runtime", id="test"),
            provenance=GenProvenance(kind="runtime_post_completion", invoked_at="2026-01-01T00:00:00+00:00"),
            policy_source={},
            findings_status="failed",  # type: ignore[arg-type]  # intentional invalid value
            helped=[],
            not_helpful=[],
            gaps=[],
            proposals=[],
            evidence_refs=[],
            generator_version="1.0",
        )
        with pytest.raises(RecordValidationError) as exc_info:
            validate_record(record)
        assert "invalid_findings_status" in str(exc_info.value)

    def test_validate_has_findings_with_empty_lists_raises(self) -> None:
        """findings_status='has_findings' + all empty lists → RecordValidationError."""
        record = GenRetrospectiveRecord(
            schema_version=1,
            mission_id="01TEST00000000000000000000",
            mission_slug="test-mission",
            mission_number=None,
            friendly_name="Test",
            mission_type="software-dev",
            target_branch="main",
            created_at="2026-01-01T00:00:00+00:00",
            created_by=GenActor(kind="runtime", id="test"),
            provenance=GenProvenance(kind="runtime_post_completion", invoked_at="2026-01-01T00:00:00+00:00"),
            policy_source={},
            findings_status="has_findings",
            helped=[],
            not_helpful=[],
            gaps=[],
            proposals=[],
            evidence_refs=[],
            generator_version="1.0",
        )
        with pytest.raises(RecordValidationError) as exc_info:
            validate_record(record)
        assert "has_findings_but_all_lists_empty" in str(exc_info.value)

    def test_validate_ran_no_findings_with_nonempty_list_raises(self) -> None:
        """findings_status='ran_no_findings' + non-empty list → RecordValidationError."""
        ev = GenEvidenceRef(id="e-001", kind="file", path="test.md")
        finding = GenFinding(
            id="g-001", category="spec_quality", summary="some gap", evidence_refs=["e-001"]
        )
        record = GenRetrospectiveRecord(
            schema_version=1,
            mission_id="01TEST00000000000000000000",
            mission_slug="test-mission",
            mission_number=None,
            friendly_name="Test",
            mission_type="software-dev",
            target_branch="main",
            created_at="2026-01-01T00:00:00+00:00",
            created_by=GenActor(kind="runtime", id="test"),
            provenance=GenProvenance(kind="runtime_post_completion", invoked_at="2026-01-01T00:00:00+00:00"),
            policy_source={},
            findings_status="ran_no_findings",
            helped=[],
            not_helpful=[],
            gaps=[finding],  # non-empty!
            proposals=[],
            evidence_refs=[ev],
            generator_version="1.0",
        )
        with pytest.raises(RecordValidationError) as exc_info:
            validate_record(record)
        assert "ran_no_findings_but_lists_non_empty" in str(exc_info.value)

    def test_validate_synthesize_fabricate_requires_no_findings(self) -> None:
        """synthesize_fabricate provenance must have ran_no_findings (FR-014 invariant)."""
        ev = GenEvidenceRef(id="e-001", kind="file", path="test.md")
        finding = GenFinding(
            id="h-001", category="implementation", summary="some help", evidence_refs=["e-001"]
        )
        record = GenRetrospectiveRecord(
            schema_version=1,
            mission_id="01TEST00000000000000000000",
            mission_slug="test-mission",
            mission_number=None,
            friendly_name="Test",
            mission_type="software-dev",
            target_branch="main",
            created_at="2026-01-01T00:00:00+00:00",
            created_by=GenActor(kind="runtime", id="test"),
            provenance=GenProvenance(
                kind="synthesize_fabricate",  # fabrication path
                invoked_at="2026-01-01T00:00:00+00:00",
            ),
            policy_source={},
            findings_status="has_findings",
            helped=[finding],
            not_helpful=[],
            gaps=[],
            proposals=[],
            evidence_refs=[ev],
            generator_version="1.0",
        )
        with pytest.raises(RecordValidationError) as exc_info:
            validate_record(record)
        assert "synthesize_fabricate_must_have_no_findings" in str(exc_info.value)

    def test_validate_unresolved_evidence_ref_raises(self) -> None:
        """Finding references an evidence_ref id not in top-level evidence_refs → error."""
        finding = GenFinding(
            id="h-001", category="implementation", summary="some help",
            evidence_refs=["e-999"]  # not in evidence_refs list
        )
        record = GenRetrospectiveRecord(
            schema_version=1,
            mission_id="01TEST00000000000000000000",
            mission_slug="test-mission",
            mission_number=None,
            friendly_name="Test",
            mission_type="software-dev",
            target_branch="main",
            created_at="2026-01-01T00:00:00+00:00",
            created_by=GenActor(kind="runtime", id="test"),
            provenance=GenProvenance(kind="runtime_post_completion", invoked_at="2026-01-01T00:00:00+00:00"),
            policy_source={},
            findings_status="has_findings",
            helped=[finding],
            not_helpful=[],
            gaps=[],
            proposals=[],
            evidence_refs=[],  # e-999 not here!
            generator_version="1.0",
        )
        with pytest.raises(RecordValidationError) as exc_info:
            validate_record(record)
        assert "unresolved_evidence_ref" in str(exc_info.value)
        assert "e-999" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TestRiskClass
# ---------------------------------------------------------------------------


class TestRiskClass:
    """Proposal risk_class classification: low vs structural (T011).

    LOW_RISK_PROPOSAL_KINDS = frozenset({"flag_not_helpful"})
    auto_applicable = False at generation time.
    """

    def test_low_risk_proposal_kinds_contains_flag_not_helpful(self) -> None:
        """LOW_RISK_PROPOSAL_KINDS must contain 'flag_not_helpful' per T011."""
        assert "flag_not_helpful" in LOW_RISK_PROPOSAL_KINDS

    def test_flag_not_helpful_action_is_low_risk(self) -> None:
        """A suggested_action starting with 'flag_not_helpful:' → risk_class='low'."""
        risk_class, auto_applicable = _classify_risk("flag_not_helpful: directive DIR-042")
        assert risk_class == "low"
        assert auto_applicable is False

    def test_glossary_rename_is_structural(self) -> None:
        """Glossary rename proposal → risk_class='structural'."""
        risk_class, auto_applicable = _classify_risk("add_glossary_term: new-term")
        assert risk_class == "structural"
        assert auto_applicable is False

    def test_synthesize_directive_is_structural(self) -> None:
        """Synthesize directive action → risk_class='structural'."""
        risk_class, auto_applicable = _classify_risk("synthesize_directive: new directive body")
        assert risk_class == "structural"
        assert auto_applicable is False

    def test_no_structural_proposal_can_be_auto_applicable(self) -> None:
        """No structural proposal may have auto_applicable=True (FR-010 invariant)."""
        ev = GenEvidenceRef(id="e-001", kind="file", path="spec.md")
        structural_proposal = GenProposal(
            id="p-001",
            category="glossary",
            risk_class="structural",
            summary="Rename term 'feature' to 'mission'",
            evidence_refs=["e-001"],
            suggested_action="update_glossary_term: feature -> mission",
            auto_applicable=True,  # this is WRONG — should be caught
        )
        _record = GenRetrospectiveRecord(
            schema_version=1,
            mission_id="01TEST00000000000000000000",
            mission_slug="test-mission",
            mission_number=None,
            friendly_name="Test",
            mission_type="software-dev",
            target_branch="main",
            created_at="2026-01-01T00:00:00+00:00",
            created_by=GenActor(kind="runtime", id="test"),
            provenance=GenProvenance(kind="runtime_post_completion", invoked_at="2026-01-01T00:00:00+00:00"),
            policy_source={},
            findings_status="has_findings",
            helped=[],
            not_helpful=[],
            gaps=[],
            proposals=[structural_proposal],
            evidence_refs=[ev],
            generator_version="1.0",
        )
        # The generator itself never sets auto_applicable=True for structural proposals,
        # but validate_record does NOT check this (it's a generator contract, not schema invariant).
        # We verify here that _classify_risk never returns auto_applicable=True for structural.
        risk_class, auto = _classify_risk("update_glossary_term: feature -> mission")
        assert risk_class == "structural"
        assert auto is False, "_classify_risk must not set auto_applicable=True for structural proposals"

    def test_low_risk_proposal_auto_applicable_stays_false_at_generation(self) -> None:
        """At generation time, even low-risk proposals have auto_applicable=False.

        The runtime/CLI decides auto_applicable based on policy.apply_low_risk_changes
        at apply time, not at generation time.
        """
        risk_class, auto_applicable = _classify_risk("flag_not_helpful: some-directive")
        assert risk_class == "low"
        assert auto_applicable is False, (
            "auto_applicable should be False at generation time; "
            "the runtime sets it based on policy.permissions.apply_low_risk_changes"
        )

    def test_classify_risk_with_no_colon_is_structural(self) -> None:
        """suggested_action without colon separator → structural (safe default)."""
        risk_class, _ = _classify_risk("just a free-form suggestion")
        assert risk_class == "structural"

    def test_classify_risk_empty_is_structural(self) -> None:
        """Empty suggested_action → structural (safe default)."""
        risk_class, _ = _classify_risk("")
        assert risk_class == "structural"

    def test_unknown_action_type_is_structural(self) -> None:
        """Unknown action prefix → structural (allowlist-only logic)."""
        risk_class, _ = _classify_risk("rewrite_everything: now")
        assert risk_class == "structural"

    # ----- Generator-level risk class tests -----

    def test_generator_not_helpful_findings_have_evidence(self) -> None:
        """Rejection-cycle not_helpful findings must each have evidence_refs."""
        policy = make_policy()
        record = generate_retrospective(MID_WITH_REJECTIONS, policy, FIXTURES_ROOT)
        for f in record.not_helpful:
            assert len(f.evidence_refs) >= 1, (
                f"not_helpful finding {f.id!r} has no evidence_refs"
            )

    def test_generator_raises_on_missing_mission(self) -> None:
        """FileNotFoundError is raised for an unknown mission handle."""
        policy = make_policy()
        with pytest.raises(FileNotFoundError) as exc_info:
            generate_retrospective("no-such-mission-xyz", policy, FIXTURES_ROOT)
        assert "no-such-mission-xyz" in str(exc_info.value)

    def test_generator_schema_version_is_1(self) -> None:
        """Generated record always has schema_version=1."""
        policy = make_policy()
        record = generate_retrospective(SIMPLE_CLEAN, policy, FIXTURES_ROOT)
        assert record.schema_version == 1

    def test_generator_mission_identity_fields_populated(self) -> None:
        """mission_id, mission_slug, mission_type, target_branch are populated from meta.json."""
        policy = make_policy()
        record = generate_retrospective(LARGE_WITH_GAPS, policy, FIXTURES_ROOT)
        assert record.mission_id == "01TESTLARGEGAPS000000000LG"
        assert record.mission_slug == "large-with-gaps"
        assert record.mission_type == "software-dev"
        assert record.target_branch == "main"
        assert record.friendly_name == "Large Mission With Gaps"


# ---------------------------------------------------------------------------
# TestMissionResolution — coverage for resolver edge cases
# ---------------------------------------------------------------------------


class TestMissionResolution:
    """Coverage for _resolve_mission_dir paths and mission identity edge cases."""

    def test_resolve_by_mission_id(self, tmp_path: Path) -> None:
        """Mission can be resolved by full mission_id from meta.json."""
        from specify_cli.retrospective.generator import _resolve_mission_dir

        (tmp_path / "kitty-specs" / "my-mission").mkdir(parents=True)
        meta = {"mission_id": "01AAAAAAAAAAAAAAAAAAAAAAA1", "mission_slug": "my-mission"}
        (tmp_path / "kitty-specs" / "my-mission" / "meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        result = _resolve_mission_dir("01AAAAAAAAAAAAAAAAAAAAAAA1", tmp_path)
        assert result is not None
        assert result.name == "my-mission"

    def test_resolve_by_slug_via_meta(self, tmp_path: Path) -> None:
        """Mission can be resolved by mission_slug from meta.json."""
        from specify_cli.retrospective.generator import _resolve_mission_dir

        (tmp_path / "kitty-specs" / "001-my-mission").mkdir(parents=True)
        meta = {"mission_id": "01BBBBBBBBBBBBBBBBBBBBBBB2", "mission_slug": "my-mission"}
        (tmp_path / "kitty-specs" / "001-my-mission" / "meta.json").write_text(
            json.dumps(meta), encoding="utf-8"
        )
        result = _resolve_mission_dir("my-mission", tmp_path)
        assert result is not None
        assert result.name == "001-my-mission"

    def test_resolve_returns_none_when_no_kitty_specs(self, tmp_path: Path) -> None:
        """Returns None when kitty-specs/ directory does not exist."""
        from specify_cli.retrospective.generator import _resolve_mission_dir

        result = _resolve_mission_dir("anything", tmp_path)
        assert result is None

    def test_mission_number_as_int(self, tmp_path: Path) -> None:
        """meta.json mission_number as int is preserved in the record."""
        (tmp_path / "kitty-specs" / "numbered-mission").mkdir(parents=True)
        meta = {
            "mission_id": "01CCCCCCCCCCCCCCCCCCCCCCC3",
            "mission_slug": "numbered-mission",
            "friendly_name": "Numbered Mission",
            "mission_type": "software-dev",
            "target_branch": "main",
            "mission_number": 42,
        }
        feature_dir = tmp_path / "kitty-specs" / "numbered-mission"
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (feature_dir / "spec.md").write_text("# Spec\n\n### FR-001\nRequirement.\n", encoding="utf-8")
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        (feature_dir / "research.md").write_text("# Research\n", encoding="utf-8")
        (feature_dir / "data-model.md").write_text("# DM\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text("---\nwork_package_id: WP01\nrequirement_refs:\n- FR-001\n---\n", encoding="utf-8")
        (feature_dir / "status.events.jsonl").write_text(
            '{"actor":"claude","at":"2026-01-01T00:00:00+00:00","event_id":"01XXXX","from_lane":"planned","to_lane":"done","wp_id":"WP01","feature_slug":"numbered-mission"}\n',
            encoding="utf-8",
        )
        policy = make_policy()
        record = generate_retrospective("numbered-mission", policy, tmp_path)
        assert record.mission_number == 42

    def test_mission_number_as_string(self, tmp_path: Path) -> None:
        """meta.json mission_number as string '042' is coerced to int 42."""
        (tmp_path / "kitty-specs" / "str-numbered").mkdir(parents=True)
        meta = {
            "mission_id": "01DDDDDDDDDDDDDDDDDDDDDDD4",
            "mission_slug": "str-numbered",
            "friendly_name": "Str Numbered",
            "mission_type": "software-dev",
            "target_branch": "main",
            "mission_number": "042",
        }
        feature_dir = tmp_path / "kitty-specs" / "str-numbered"
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (feature_dir / "spec.md").write_text("# Spec\n\n### FR-001\nReq.\n", encoding="utf-8")
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        (feature_dir / "research.md").write_text("# Research\n", encoding="utf-8")
        (feature_dir / "data-model.md").write_text("# DM\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text("---\nwork_package_id: WP01\nrequirement_refs:\n- FR-001\n---\n", encoding="utf-8")
        (feature_dir / "status.events.jsonl").write_text(
            '{"actor":"claude","at":"2026-01-01T00:00:00+00:00","event_id":"01XXXX","from_lane":"planned","to_lane":"done","wp_id":"WP01","feature_slug":"str-numbered"}\n',
            encoding="utf-8",
        )
        policy = make_policy()
        record = generate_retrospective("str-numbered", policy, tmp_path)
        assert record.mission_number == 42

    def test_clean_wp_uses_events_evidence_when_no_wp_file(self, tmp_path: Path) -> None:
        """When a clean WP has no matching WP file, events file is used as evidence."""
        (tmp_path / "kitty-specs" / "no-wp-files").mkdir(parents=True)
        meta = {
            "mission_id": "01EEEEEEEEEEEEEEEEEEEEEEE5",
            "mission_slug": "no-wp-files",
            "friendly_name": "No WP Files",
            "mission_type": "software-dev",
            "target_branch": "main",
        }
        feature_dir = tmp_path / "kitty-specs" / "no-wp-files"
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (feature_dir / "spec.md").write_text("# Spec\n\n### FR-001\nReq.\n", encoding="utf-8")
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        (feature_dir / "research.md").write_text("# Research\n", encoding="utf-8")
        (feature_dir / "data-model.md").write_text("# DM\n", encoding="utf-8")
        # No tasks/ directory — no WP files
        # But have status events with a rejection (so clean WPs are notable)
        (feature_dir / "status.events.jsonl").write_text(
            '{"actor":"claude","at":"2026-01-01T00:00:00+00:00","event_id":"01AAA","from_lane":"planned","to_lane":"done","wp_id":"WP01","feature_slug":"no-wp-files"}\n'
            '{"actor":"claude","at":"2026-01-01T00:01:00+00:00","event_id":"01BBB","from_lane":"planned","to_lane":"for_review","wp_id":"WP02","feature_slug":"no-wp-files"}\n'
            '{"actor":"human","at":"2026-01-01T00:02:00+00:00","event_id":"01CCC","from_lane":"for_review","to_lane":"in_progress","wp_id":"WP02","feature_slug":"no-wp-files"}\n'
            '{"actor":"claude","at":"2026-01-01T00:03:00+00:00","event_id":"01DDD","from_lane":"in_progress","to_lane":"done","wp_id":"WP02","feature_slug":"no-wp-files"}\n',
            encoding="utf-8",
        )
        policy = make_policy()
        record = generate_retrospective("no-wp-files", policy, tmp_path)
        # WP01 clean + WP02 rejected → WP01 should appear in helped with events file as evidence
        clean_helped = [h for h in record.helped if "WP01" in h.summary]
        assert len(clean_helped) == 1
        assert len(clean_helped[0].evidence_refs) >= 1  # uses events file as fallback
