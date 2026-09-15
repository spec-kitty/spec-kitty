"""Tests for retrospective generator ingestor registrations (WP08 / T036–T040).

Covers:
- workflow-failures-log.md ingestor (T036)
- analysis-report.md ingestor (T037)
- mission-review-report.md ingestor (T037)
- "Helped only by contrast" rule relaxed when ingestor content is present (T038)
- Stale docstring removed: generate_retrospective no longer references quickstart.md (T039)
- Golden test: fixture with ingestor artifacts produces non-empty findings (T040)

FR refs: FR-008, Issue #1878
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

from specify_cli.retrospective.generator import (
    generate_retrospective,
    _build_ingestor_findings,
    _EvidenceRegistry,
)
from specify_cli.retrospective.policy import default_policy
from specify_cli.retrospective.schema import GenActor


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_ROOT = Path(__file__).parent / "fixtures"
SIMPLE_CLEAN = "simple-clean"

_TS = "2026-06-13T00:00:00+00:00"
_ACTOR = GenActor(kind="runtime", id="test-agent", display="Test Agent")


def _make_policy():
    return default_policy()


def _ingestor_finding_summaries(record) -> list[str]:
    """Return summaries of all findings in the record."""
    all_findings = record.helped + record.not_helpful + record.gaps
    return [f.summary for f in all_findings]


# ---------------------------------------------------------------------------
# T039 — Docstring correctness
# ---------------------------------------------------------------------------


class TestDocstring:
    """T039: The generate_retrospective docstring must not reference stale artifacts."""

    def test_docstring_does_not_reference_quickstart(self) -> None:
        """quickstart.md was listed in the old WP02-prompt artifact chain; it is now gone."""
        doc = inspect.getdoc(generate_retrospective) or ""
        assert "quickstart.md" not in doc, (
            "generate_retrospective docstring still references the deprecated quickstart.md artifact"
        )

    def test_docstring_references_new_ingestor_artifacts(self) -> None:
        """The docstring should list the new ingestor artifacts."""
        doc = inspect.getdoc(generate_retrospective) or ""
        assert "workflow-failures-log.md" in doc
        assert "analysis-report.md" in doc
        assert "mission-review-report.md" in doc


# ---------------------------------------------------------------------------
# T036 — workflow-failures-log.md ingestor
# ---------------------------------------------------------------------------


class TestWorkflowFailuresIngestor:
    """T036: workflow-failures-log.md is ingested and produces findings."""

    def _counters(self) -> dict:
        return {}

    def _ev_reg(self) -> _EvidenceRegistry:
        return _EvidenceRegistry()

    def test_absent_file_produces_no_findings(self) -> None:
        """None text → ingestor is a no-op."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        helped, not_helpful, _gaps = _build_ingestor_findings(
            workflow_failures_text=None,
            analysis_report_text=None,
            review_report_text=None,
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        assert helped == []
        assert not_helpful == []

    def test_empty_file_produces_clean_helped_finding(self) -> None:
        """Empty file (no failure entries) → helped finding noting no failures."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        helped, not_helpful, _gaps = _build_ingestor_findings(
            workflow_failures_text="# Workflow Failures\n\nNo failures recorded.\n",
            analysis_report_text=None,
            review_report_text=None,
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        assert len(helped) == 1
        assert "no recorded failures" in helped[0].summary
        assert helped[0].category == "process"
        assert not_helpful == []

    def test_fail_entries_produce_not_helpful_findings(self) -> None:
        """Lines starting with '- [ ] FAIL:' produce not_helpful findings."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        text = (
            "# Workflow Failures\n"
            "- [ ] FAIL: CI gate timed out on WP03\n"
            "- [ ] FAIL: lint check failed on main\n"
        )
        helped, not_helpful, _gaps = _build_ingestor_findings(
            workflow_failures_text=text,
            analysis_report_text=None,
            review_report_text=None,
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        assert helped == []
        assert len(not_helpful) == 2
        assert all(f.category == "process" for f in not_helpful)
        summaries = [f.summary for f in not_helpful]
        assert any("CI gate timed out" in s for s in summaries)
        assert any("lint check failed" in s for s in summaries)

    def test_hash_fail_entries_produce_not_helpful_findings(self) -> None:
        """Lines starting with '### FAIL:' also produce not_helpful findings."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        text = "### FAIL: deploy job crashed\n"
        helped, not_helpful, _gaps = _build_ingestor_findings(
            workflow_failures_text=text,
            analysis_report_text=None,
            review_report_text=None,
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        assert len(not_helpful) == 1
        assert "deploy job crashed" in not_helpful[0].summary

    def test_evidence_ref_registered_for_workflow_failures(self) -> None:
        """Evidence registry gets the workflow-failures-log.md path registered."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        wf_rel = "kitty-specs/test/workflow-failures-log.md"
        _build_ingestor_findings(
            workflow_failures_text="- [ ] FAIL: something broke\n",
            analysis_report_text=None,
            review_report_text=None,
            workflow_failures_rel=wf_rel,
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        paths = [r.path for r in ev_reg.refs]
        assert wf_rel in paths


# ---------------------------------------------------------------------------
# T037 — analysis-report.md and mission-review-report.md ingestors
# ---------------------------------------------------------------------------


class TestAnalysisAndReviewIngestors:
    """T037: analysis-report.md and mission-review-report.md produce findings."""

    def test_analysis_report_present_produces_not_helpful_finding(self) -> None:
        """Non-None analysis text → not_helpful finding with category 'doc'."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        helped, not_helpful, _gaps = _build_ingestor_findings(
            workflow_failures_text=None,
            analysis_report_text="# Analysis Report\n\n## Findings\n\n- C1: Something\n",
            review_report_text=None,
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        assert helped == []
        assert len(not_helpful) == 1
        finding = not_helpful[0]
        assert finding.category == "doc"
        assert "analysis-report.md" in finding.summary

    def test_review_report_absent_is_noop(self) -> None:
        """None review text → no finding."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        helped, not_helpful, _gaps = _build_ingestor_findings(
            workflow_failures_text=None,
            analysis_report_text=None,
            review_report_text=None,
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        assert not_helpful == []

    def test_review_report_present_produces_not_helpful_finding(self) -> None:
        """Non-None review text → not_helpful finding with category 'review_loop'."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        helped, not_helpful, _gaps = _build_ingestor_findings(
            workflow_failures_text=None,
            analysis_report_text=None,
            review_report_text="# Mission Review Report\n\n## Findings\n\n- R1: Something\n",
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        assert helped == []
        assert len(not_helpful) == 1
        finding = not_helpful[0]
        assert finding.category == "review_loop"
        assert "mission-review-report.md" in finding.summary

    def test_all_three_ingestors_present_produces_three_findings(self) -> None:
        """All three ingestors active → combined findings emitted."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        helped, not_helpful, _gaps = _build_ingestor_findings(
            workflow_failures_text="- [ ] FAIL: something broke\n",
            analysis_report_text="# Analysis\n",
            review_report_text="# Review\n",
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        assert helped == []
        # 1 workflow failure + 1 analysis + 1 review
        assert len(not_helpful) == 3
        categories = {f.category for f in not_helpful}
        assert "process" in categories
        assert "doc" in categories
        assert "review_loop" in categories

    def test_evidence_refs_registered_for_all_ingestors(self) -> None:
        """Evidence registry gets all three ingestor paths registered when present."""
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        wf_rel = "kitty-specs/test/workflow-failures-log.md"
        ar_rel = "kitty-specs/test/analysis-report.md"
        rr_rel = "kitty-specs/test/mission-review-report.md"
        _build_ingestor_findings(
            workflow_failures_text="- [ ] FAIL: x\n",
            analysis_report_text="content",
            review_report_text="content",
            workflow_failures_rel=wf_rel,
            analysis_report_rel=ar_rel,
            review_report_rel=rr_rel,
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )
        paths = {r.path for r in ev_reg.refs}
        assert wf_rel in paths
        assert ar_rel in paths
        assert rr_rel in paths

    # --- #3793: the T037 findings must assert only what the parsed
    # frontmatter establishes, never content inferred from file presence.

    def _ingestors(self, analysis_text: str | None, review_text: str | None):
        counters: dict = {}
        ev_reg = _EvidenceRegistry()
        return _build_ingestor_findings(
            workflow_failures_text=None,
            analysis_report_text=analysis_text,
            review_report_text=review_text,
            workflow_failures_rel="kitty-specs/test/workflow-failures-log.md",
            analysis_report_rel="kitty-specs/test/analysis-report.md",
            review_report_rel="kitty-specs/test/mission-review-report.md",
            finding_id_counters=counters,
            ev_reg=ev_reg,
        )

    def test_zero_finding_analysis_report_emits_helped_not_claims(self) -> None:
        """#3793: a ready verdict with an empty findings list and all-zero
        issue_counts must not be reported as 'present with findings'."""
        text = (
            "---\n"
            "verdict: ready\n"
            "issue_counts:\n"
            "  low: 0\n"
            "  medium: 0\n"
            "  critical: 0\n"
            "  high: 0\n"
            "  info: 0\n"
            "findings: []\n"
            "---\n"
            "\n"
            "# Analysis Report\n"
        )
        helped, not_helpful, _gaps = self._ingestors(text, None)
        assert not_helpful == []
        assert len(helped) == 1
        assert helped[0].category == "doc"
        assert "no recorded findings" in helped[0].summary

    def test_analysis_report_with_structured_findings_counts_them(self) -> None:
        """A report whose frontmatter actually records findings reports the
        real count, not the presence template."""
        text = (
            "---\n"
            "verdict: blocked\n"
            "issue_counts:\n"
            "  low: 1\n"
            "  medium: 1\n"
            "  critical: 0\n"
            "  high: 0\n"
            "  info: 0\n"
            "findings:\n"
            "  - id: C1\n"
            "    severity: medium\n"
            "    summary: something was off\n"
            "  - id: C2\n"
            "    severity: low\n"
            "    summary: minor drift\n"
            "---\n"
            "\n"
            "# Analysis Report\n"
        )
        helped, not_helpful, _gaps = self._ingestors(text, None)
        assert helped == []
        assert len(not_helpful) == 1
        assert not_helpful[0].category == "doc"
        assert "records 2 finding(s)" in not_helpful[0].summary

    def test_legacy_unknown_verdict_analysis_report_is_not_claimed(self) -> None:
        """#3793: verdict: unknown is what write_analysis_report records for a
        legacy report with no structured carrier — an empty findings list
        there does not establish 'no findings', so nothing is claimed."""
        text = (
            "---\n"
            "verdict: unknown\n"
            "issue_counts:\n"
            "  low: null\n"
            "  medium: null\n"
            "  critical: null\n"
            "  high: null\n"
            "  info: null\n"
            "findings: []\n"
            "---\n"
            "\n"
            "# Analysis Report\n"
            "\n"
            "C1 (medium): prose finding the carrier never captured\n"
        )
        helped, not_helpful, _gaps = self._ingestors(text, None)
        assert helped == []
        assert len(not_helpful) == 1
        assert "not machine-readable" in not_helpful[0].summary
        # #4065: the fallback must name the real gap — the verdict, not the
        # count, is what is missing (the findings list did parse).
        assert "no resolved verdict" in not_helpful[0].details
        assert "machine-readable findings count" in not_helpful[0].details

    def test_missing_verdict_analysis_report_fallback_names_the_verdict_gap(self) -> None:
        """#4065: a hand-edited or foreign report whose findings count parses
        cleanly but which carries no verdict key is not asserted — and the
        fallback must say the verdict is the gap, not claim the count itself
        was unreadable."""
        text = (
            "---\n"
            "issue_counts:\n"
            "  low: 1\n"
            "  medium: 1\n"
            "  critical: 0\n"
            "  high: 0\n"
            "  info: 0\n"
            "findings:\n"
            "  - id: C1\n"
            "    severity: medium\n"
            "    summary: something was off\n"
            "  - id: C2\n"
            "    severity: low\n"
            "    summary: minor drift\n"
            "---\n"
            "\n"
            "# Analysis Report\n"
        )
        helped, not_helpful, _gaps = self._ingestors(text, None)
        assert helped == []
        assert len(not_helpful) == 1
        finding = not_helpful[0]
        assert finding.category == "doc"
        assert "not machine-readable" in finding.summary
        # The count is machine-readable — the message must not deny that.
        assert "carries a machine-readable findings count" in finding.details
        assert "no resolved verdict" in finding.details
        assert "the verdict key is absent" in finding.details
        assert "does not carry a machine-readable findings count" not in finding.details

    def test_zero_finding_review_report_emits_helped(self) -> None:
        """#3793: mission-review-report.md with findings: 0 (verdict pass)
        must not be reported as 'present with findings'."""
        text = (
            "---\n"
            "verdict: pass\n"
            "mode: lightweight\n"
            "reviewed_at: 2026-06-13T00:00:00+00:00\n"
            "findings: 0\n"
            "gates_recorded: []\n"
            "---\n"
            "\n"
            "No findings.\n"
        )
        helped, not_helpful, _gaps = self._ingestors(None, text)
        assert not_helpful == []
        assert len(helped) == 1
        assert helped[0].category == "review_loop"
        assert "no findings" in helped[0].summary

    def test_review_report_with_findings_counts_them(self) -> None:
        """A review report whose frontmatter records a nonzero findings count
        reports the real count."""
        text = (
            "---\n"
            "verdict: pass_with_notes\n"
            "mode: lightweight\n"
            "reviewed_at: 2026-06-13T00:00:00+00:00\n"
            "findings: 3\n"
            "gates_recorded: []\n"
            "---\n"
            "\n"
            "## Findings\n"
        )
        helped, not_helpful, _gaps = self._ingestors(None, text)
        assert helped == []
        assert len(not_helpful) == 1
        assert not_helpful[0].category == "review_loop"
        assert "records 3 finding(s)" in not_helpful[0].summary


# ---------------------------------------------------------------------------
# T038 — "Helped only by contrast" rule relaxation
# ---------------------------------------------------------------------------


class TestHelpedByContrastRelaxation:
    """T038: clean WPs are surfaced as 'helped' even without rejection cycles
    when ingestor artifacts documenting failures are present.
    """

    def test_clean_wps_surfaced_when_analysis_report_present(
        self, tmp_path: Path
    ) -> None:
        """A mission with clean WPs and an analysis-report should emit helped findings."""
        # Build a minimal mission fixture in tmp_path/kitty-specs/test-mission/
        feature_dir = tmp_path / "kitty-specs" / "test-ingestor-contrast"
        feature_dir.mkdir(parents=True)
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()

        meta = {
            "mission_id": "01TESTCONTRAST0000000000",
            "mission_slug": "test-ingestor-contrast",
            "friendly_name": "Ingestor Contrast Test",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (feature_dir / "spec.md").write_text("# Spec\n\n## FR-001\n\nA requirement.\n", encoding="utf-8")

        # A single WP that completed cleanly (done, no rejections)
        (tasks_dir / "WP01.md").write_text("# WP01\n\nDo the thing.\n", encoding="utf-8")

        # Emit a clean done event for WP01
        events = [
            {
                "event_id": "01TESTEV00000000000000A",
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "done",
                "actor": "claude",
                "at": "2026-06-13T01:00:00+00:00",
                "feature_slug": "test-ingestor-contrast",
                "force": False,
                "evidence": None,
                "reason": None,
                "review_ref": None,
                "execution_mode": "worktree",
            }
        ]
        events_path = feature_dir / "status.events.jsonl"
        events_path.write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )

        # analysis-report.md present (triggers relaxation of contrast rule)
        (feature_dir / "analysis-report.md").write_text(
            "# Analysis Report\n\nC1 (medium): something was off.\n", encoding="utf-8"
        )

        policy = _make_policy()
        record = generate_retrospective(
            "test-ingestor-contrast",
            policy,
            tmp_path,
            invoked_at=_TS,
            actor=_ACTOR,
        )

        # WP01 completed without rejection → should appear as helped even without
        # other rejections, because analysis-report.md is present
        helped_summaries = [f.summary for f in record.helped]
        assert any("WP01" in s and "completed without rejection" in s for s in helped_summaries), (
            f"Expected WP01 clean helped finding; got helped={helped_summaries!r}"
        )

    def test_without_ingestor_content_clean_wps_not_surfaced(
        self, tmp_path: Path
    ) -> None:
        """Without ingestor artifacts and without rejection cycles, no helped finding."""
        feature_dir = tmp_path / "kitty-specs" / "test-no-ingestor"
        feature_dir.mkdir(parents=True)
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()

        meta = {
            "mission_id": "01TESTNOINGESTOR00000000",
            "mission_slug": "test-no-ingestor",
            "friendly_name": "No Ingestor Test",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (feature_dir / "spec.md").write_text("# Spec\n\n## FR-001\n\nA requirement.\n", encoding="utf-8")
        (tasks_dir / "WP01.md").write_text("# WP01\n\nDo the thing.\n", encoding="utf-8")

        events = [
            {
                "event_id": "01TESTEV00000000000000B",
                "wp_id": "WP01",
                "from_lane": "planned",
                "to_lane": "done",
                "actor": "claude",
                "at": "2026-06-13T01:00:00+00:00",
                "feature_slug": "test-no-ingestor",
                "force": False,
                "evidence": None,
                "reason": None,
                "review_ref": None,
                "execution_mode": "worktree",
            }
        ]
        (feature_dir / "status.events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )

        policy = _make_policy()
        record = generate_retrospective(
            "test-no-ingestor",
            policy,
            tmp_path,
            invoked_at=_TS,
            actor=_ACTOR,
        )

        # No rejection cycles, no ingestor content → clean WPs NOT surfaced as helped
        helped_summaries = [f.summary for f in record.helped]
        assert not any("completed without rejection" in s for s in helped_summaries), (
            f"WP01 should NOT appear as helped without ingestor content or rejection cycles; "
            f"got helped={helped_summaries!r}"
        )


# ---------------------------------------------------------------------------
# T040 — Golden test: fixture with ingestor artifacts → non-empty findings
# ---------------------------------------------------------------------------


class TestGoldenIngestorFixture:
    """T040: A fixture with all three ingestor artifacts produces non-empty findings."""

    def test_ingestor_fixture_produces_findings(self, tmp_path: Path) -> None:
        """Golden test: all three ingestor artifacts → record has non-empty findings."""
        feature_dir = tmp_path / "kitty-specs" / "mission-131-golden"
        feature_dir.mkdir(parents=True)
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()

        meta = {
            "mission_id": "01TESTGOLDEN000000000131",
            "mission_slug": "mission-131-golden",
            "friendly_name": "Mission 131 Golden Test",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n## FR-001\n\nRequirement one.\n\n## FR-002\n\nRequirement two.\n",
            encoding="utf-8",
        )

        # workflow-failures-log.md with structured failure entries
        (feature_dir / "workflow-failures-log.md").write_text(
            "# Workflow Failures\n\n"
            "- [ ] FAIL: CI pipeline timed out on WP02\n"
            "- [ ] FAIL: deploy smoke test failed\n",
            encoding="utf-8",
        )

        # analysis-report.md with findings
        (feature_dir / "analysis-report.md").write_text(
            "# Analysis Report\n\n"
            "## C1 (critical): coordination bug in topology resolver\n"
            "## C2 (medium): stale docstring in generator.py\n",
            encoding="utf-8",
        )

        # mission-review-report.md with review findings
        (feature_dir / "mission-review-report.md").write_text(
            "# Mission Review Report\n\n"
            "## Findings\n\n"
            "- R1: Naming inconsistency in API surface\n",
            encoding="utf-8",
        )

        policy = _make_policy()
        record = generate_retrospective(
            "mission-131-golden",
            policy,
            tmp_path,
            invoked_at=_TS,
            actor=_ACTOR,
        )

        # Record must have non-empty findings
        all_findings = record.helped + record.not_helpful + record.gaps
        assert len(all_findings) > 0, "Expected non-empty findings from ingestor fixture"

        # workflow failures should appear as not_helpful
        wf_summaries = [f.summary for f in record.not_helpful if f.category == "process"]
        assert any("CI pipeline timed out" in s for s in wf_summaries)
        assert any("deploy smoke test failed" in s for s in wf_summaries)

        # analysis-report.md finding should appear
        doc_summaries = [f.summary for f in record.not_helpful if f.category == "doc"]
        assert any("analysis-report.md" in s for s in doc_summaries)

        # mission-review-report.md finding should appear
        review_summaries = [f.summary for f in record.not_helpful if f.category == "review_loop"]
        assert any("mission-review-report.md" in s for s in review_summaries)

        # findings_status must be has_findings
        assert record.findings_status == "has_findings"

    def test_all_ingestors_absent_does_not_crash(self, tmp_path: Path) -> None:
        """A mission with no ingestor artifacts should run without error."""
        feature_dir = tmp_path / "kitty-specs" / "mission-no-ingestors"
        feature_dir.mkdir(parents=True)
        meta = {
            "mission_id": "01TESTNOINGEST000000000",
            "mission_slug": "mission-no-ingestors",
            "friendly_name": "No Ingestors",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        policy = _make_policy()
        # Must not raise
        record = generate_retrospective(
            "mission-no-ingestors",
            policy,
            tmp_path,
            invoked_at=_TS,
            actor=_ACTOR,
        )
        assert record is not None


# ---------------------------------------------------------------------------
# #3793 — end-to-end: findings assert only checked content
# ---------------------------------------------------------------------------


class TestIssue3793ContentCheckedFindings:
    """End-to-end reproduction of the reported mission: a zero-finding
    analysis-report.md, a zero-finding mission-review-report.md, and one
    arbiter override whose move-task emitted one event per lane hop.
    """

    def test_zero_finding_reports_and_single_hop_pair_override(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "mission-3793-repro"
        feature_dir.mkdir(parents=True)
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()

        meta = {
            "mission_id": "01TEST3793REPRO00000000",
            "mission_slug": "mission-3793-repro",
            "friendly_name": "3793 Repro",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-06-13T00:00:00+00:00",
        }
        (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (feature_dir / "spec.md").write_text("# Spec\n\n## FR-001\n\nA requirement.\n", encoding="utf-8")
        (tasks_dir / "WP05.md").write_text("# WP05\n\nDo the thing.\n", encoding="utf-8")

        # One arbiter override from for_review to approved: move-task emits
        # one event per lane hop, both carrying the same operator reason.
        events = [
            {
                "event_id": "01TESTEV0000000000000065",
                "wp_id": "WP05",
                "from_lane": "for_review",
                "to_lane": "in_review",
                "actor": "user",
                "at": "2026-06-13T01:00:00+00:00",
                "feature_slug": "mission-3793-repro",
                "force": False,
                "evidence": None,
                "reason": "Arbiter override: WP05 was reviewed and approved at cycle 2",
                "review_ref": None,
                "execution_mode": "worktree",
            },
            {
                "event_id": "01TESTEV0000000000000066",
                "wp_id": "WP05",
                "from_lane": "in_review",
                "to_lane": "approved",
                "actor": "user",
                "at": "2026-06-13T01:00:01+00:00",
                "feature_slug": "mission-3793-repro",
                "force": False,
                "evidence": None,
                "reason": "Arbiter override: WP05 was reviewed and approved at cycle 2",
                "review_ref": None,
                "execution_mode": "worktree",
            },
        ]
        (feature_dir / "status.events.jsonl").write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )

        # The reported zero-finding analysis-report.md frontmatter.
        (feature_dir / "analysis-report.md").write_text(
            "---\n"
            "verdict: ready\n"
            "issue_counts:\n"
            "  low: 0\n"
            "  medium: 0\n"
            "  critical: 0\n"
            "  high: 0\n"
            "  info: 0\n"
            "findings: []\n"
            "---\n"
            "\n"
            "# Analysis Report\n",
            encoding="utf-8",
        )
        # A clean mission-review-report.md (verdict pass, zero findings).
        (feature_dir / "mission-review-report.md").write_text(
            "---\n"
            "verdict: pass\n"
            "mode: lightweight\n"
            "reviewed_at: 2026-06-13T02:00:00+00:00\n"
            "findings: 0\n"
            "gates_recorded: []\n"
            "---\n"
            "\n"
            "No findings.\n",
            encoding="utf-8",
        )

        policy = _make_policy()
        record = generate_retrospective(
            "mission-3793-repro",
            policy,
            tmp_path,
            invoked_at=_TS,
            actor=_ACTOR,
        )

        # Neither report may be reported as carrying findings it does not have.
        all_summaries = [f.summary for f in record.helped + record.not_helpful + record.gaps]
        assert not any("present with findings" in s for s in all_summaries), (
            f"presence-only claim leaked into findings: {all_summaries!r}"
        )
        helped_summaries = [f.summary for f in record.helped]
        assert any("analysis-report.md" in s and "no recorded findings" in s for s in helped_summaries)
        assert any("mission-review-report.md" in s and "no findings" in s for s in helped_summaries)

        # The single override reads as 1x, not the 2x of its two lane hops.
        gap_summaries = [f.summary for f in record.gaps]
        assert any("Arbiter override needed for WP05 (1x)" in s for s in gap_summaries), (
            f"expected a single-count arbiter override finding; got gaps={gap_summaries!r}"
        )
        assert not any("(2x)" in s for s in gap_summaries)
