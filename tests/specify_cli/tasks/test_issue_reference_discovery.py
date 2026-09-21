"""Tests for ``specify_cli.tasks.issue_reference_discovery`` (WP08, T031, FR-004, #1738).

Covers the multi-file discovery contract: an issue referenced only in
``tasks/WP01.md`` (or ``plan.md``/``contracts/``) must be discovered, not just
one referenced in ``spec.md`` -- closing the single-file blind spot the
merge-time completeness gate (``policy.merge_gates``) and the three
enforcement sites depend on.

WP06 (#1738, FR-013) note: ``IssueReference`` gained a required
``source_file`` field (the basename of the file a reference was discovered
in). Every expected tuple below names it explicitly.

#4825 note: ``IssueReference`` equality now covers ALL five fields, so these
discovery/provenance asserts compare the identity triple
``(number, first_line_context, source_file)`` explicitly -- the fields they
actually mean -- rather than whole-tuple equality (which would pin, or mask
a regression in, the aggregate ``occurrences``/``classification`` fields).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.tasks.issue_reference_discovery import discover_issue_references

pytestmark = [pytest.mark.fast]


def _mission_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "099-demo"
    feature_dir.mkdir(parents=True)
    return feature_dir


class TestDiscoverIssueReferences:
    def test_spec_md_only_reference_is_discovered(self, tmp_path: Path) -> None:
        """Baseline: the single-file behavior is a strict subset (T028)."""
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text(
            "Addresses issue #1582.\n", encoding="utf-8"
        )

        refs = discover_issue_references(feature_dir)

        assert [(r.number, r.first_line_context, r.source_file) for r in refs] == [
            (1582, "Addresses issue #1582.", "spec.md")
        ]

    def test_reference_only_in_wp_file_is_discovered(self, tmp_path: Path) -> None:
        """The FR-004 headline case: a ref buried in ``tasks/WP01.md`` alone."""
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text("No issues here.\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text(
            "This WP fixes #4242 as a follow-up.\n", encoding="utf-8"
        )

        refs = discover_issue_references(feature_dir)

        assert [(r.number, r.first_line_context, r.source_file) for r in refs] == [
            (4242, "This WP fixes #4242 as a follow-up.", "WP01.md")
        ]

    def test_reference_only_in_plan_md_is_discovered(self, tmp_path: Path) -> None:
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "plan.md").write_text(
            "Design closes #9001.\n", encoding="utf-8"
        )

        refs = discover_issue_references(feature_dir)

        assert [(r.number, r.first_line_context, r.source_file) for r in refs] == [
            (9001, "Design closes #9001.", "plan.md")
        ]

    def test_reference_only_in_contracts_is_discovered(self, tmp_path: Path) -> None:
        feature_dir = _mission_dir(tmp_path)
        contracts_dir = feature_dir / "contracts"
        contracts_dir.mkdir()
        (contracts_dir / "commands.md").write_text(
            "Contract for #5555.\n", encoding="utf-8"
        )

        refs = discover_issue_references(feature_dir)

        assert [(r.number, r.first_line_context, r.source_file) for r in refs] == [
            (5555, "Contract for #5555.", "commands.md")
        ]

    def test_reference_only_in_research_or_analysis_report_is_discovered(
        self, tmp_path: Path
    ) -> None:
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "research.md").write_text(
            "Research note on #6001.\n", encoding="utf-8"
        )
        (feature_dir / "analysis-report.md").write_text(
            "Analysis of #6002.\n", encoding="utf-8"
        )

        refs = discover_issue_references(feature_dir)

        assert {r.number for r in refs} == {6001, 6002}

    def test_deduplicates_across_files_keeping_first_occurrence(
        self, tmp_path: Path
    ) -> None:
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text(
            "Addresses issue #1582 in spec.\n", encoding="utf-8"
        )
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text(
            "Also touches #1582 again here.\n", encoding="utf-8"
        )

        refs = discover_issue_references(feature_dir)

        assert [(r.number, r.first_line_context, r.source_file) for r in refs] == [
            (1582, "Addresses issue #1582 in spec.", "spec.md")
        ]

    def test_scan_order_is_deterministic_across_multiple_wp_files(
        self, tmp_path: Path
    ) -> None:
        feature_dir = _mission_dir(tmp_path)
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP02.md").write_text("Second file #200.\n", encoding="utf-8")
        (tasks_dir / "WP01.md").write_text("First file #100.\n", encoding="utf-8")

        refs = discover_issue_references(feature_dir)

        # tasks/ is scanned sorted by filename: WP01.md before WP02.md,
        # regardless of filesystem creation order.
        assert [r.number for r in refs] == [100, 200]

    def test_no_references_anywhere_returns_empty_list(self, tmp_path: Path) -> None:
        feature_dir = _mission_dir(tmp_path)
        (feature_dir / "spec.md").write_text(
            "No GitHub issue references here.\n", encoding="utf-8"
        )

        assert discover_issue_references(feature_dir) == []

    def test_missing_mission_artifacts_are_skipped_without_error(
        self, tmp_path: Path
    ) -> None:
        """A bare feature_dir with none of the scanned files/dirs is not an error."""
        feature_dir = _mission_dir(tmp_path)

        assert discover_issue_references(feature_dir) == []
