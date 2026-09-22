"""Unit tests for the WP04 ``tasks_finalize_validation`` seam (issue #2058).

These exercise the extracted PURE functions directly — no CLI invocation —
covering WP coverage, cycle detection, the *disagree-loud* dependency-conflict
detection, and the frontmatter-update computation. The integration behaviour of
``finalize-tasks`` itself is covered by ``test_tasks_canonical_cleanup.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import tasks_finalize_validation as tfv
from specify_cli.cli.commands.agent.tasks_finalize_validation import (
    CoverageResult,
    FrontmatterUpdatePlan,
    _is_backward_transition,
    _lane_targets_for_emit,
    _read_transactional_wp_lane,
    _wp_lane_from_status_events,
    compute_expected_wp_ids,
    compute_wp_frontmatter_updates,
    detect_dependency_conflicts,
    read_existing_frontmatter,
    validate_wp_coverage,
)
from specify_cli.status import Lane, WPMetadata

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_wp(tasks_dir: Path, wp_id: str, *, deps: list[str] | None = None) -> Path:
    """Write a WP file with optional dependencies frontmatter."""
    lines = ["---", f"work_package_id: {wp_id}", f"title: Test {wp_id}"]
    if deps is not None:
        lines.append("dependencies:")
        lines.extend(f"- {d}" for d in deps)
    lines.extend(["---", "", f"# {wp_id}", ""])
    path = tasks_dir / f"{wp_id}-test.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


@pytest.fixture
def tasks_dir(tmp_path: Path) -> Path:
    d = tmp_path / "tasks"
    d.mkdir()
    return d


# ---------------------------------------------------------------------------
# WP coverage
# ---------------------------------------------------------------------------


class TestValidateWpCoverage:
    def test_full_coverage_is_ok(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        _write_wp(tasks_dir, "WP02")
        result = validate_wp_coverage({"WP01": [], "WP02": ["WP01"]}, tasks_dir)
        assert isinstance(result, CoverageResult)
        assert result.ok is True
        assert result.expected_wp_ids == ["WP01", "WP02"]
        assert result.missing_wp_sections == []
        assert result.extra_wp_sections == []

    def test_missing_section_for_wp_file_is_not_ok(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        _write_wp(tasks_dir, "WP02")
        # WP02 file exists but parser produced no section for it.
        result = validate_wp_coverage({"WP01": []}, tasks_dir)
        assert result.ok is False
        assert result.missing_wp_sections == ["WP02"]
        assert result.extra_wp_sections == []

    def test_extra_section_without_file_is_not_ok(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        result = validate_wp_coverage({"WP01": [], "WP09": ["WP01"]}, tasks_dir)
        assert result.ok is False
        assert result.missing_wp_sections == []
        assert result.extra_wp_sections == ["WP09"]

    def test_non_wp_files_are_ignored(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        (tasks_dir / "README.md").write_text("not a wp", encoding="utf-8")
        (tasks_dir / "WPxx-bad.md").write_text("bad id", encoding="utf-8")
        result = compute_expected_wp_ids(tasks_dir)
        assert result == ["WP01"]


# ---------------------------------------------------------------------------
# Disagree-loud conflict detection (the subtle / load-bearing behaviour)
# ---------------------------------------------------------------------------


class TestDetectDependencyConflicts:
    def test_no_conflict_when_frontmatter_empty(self, tasks_dir: Path) -> None:
        existing = {"WP02": WPMetadata(work_package_id="WP02", title="WP02")}
        errors = detect_dependency_conflicts({"WP02": ["WP01"]}, existing)
        assert errors == []

    def test_no_conflict_when_parser_empty(self) -> None:
        existing = {"WP02": WPMetadata(work_package_id="WP02", dependencies=["WP01"])}
        errors = detect_dependency_conflicts({"WP02": []}, existing)
        assert errors == []

    def test_no_conflict_when_sets_agree_regardless_of_order(self) -> None:
        existing = {"WP03": WPMetadata(work_package_id="WP03", dependencies=["WP02", "WP01"])}
        errors = detect_dependency_conflicts({"WP03": ["WP01", "WP02"]}, existing)
        assert errors == []

    def test_disagree_loud_when_both_present_and_differ(self) -> None:
        existing = {"WP02": WPMetadata(work_package_id="WP02", dependencies=["WP01"])}
        errors = detect_dependency_conflicts({"WP02": ["WP09"]}, existing)
        # KEY ASSERTION: the conflict is surfaced loudly with both sides quoted
        # and an explicit resolve instruction — never silently overwritten.
        assert len(errors) == 1
        assert errors[0] == (
            "WP02: frontmatter has ['WP01'], tasks.md parsed ['WP09']. "
            "Resolve the disagreement in tasks.md or WP frontmatter before finalizing."
        )

    def test_missing_existing_meta_defaults_to_no_deps(self) -> None:
        # No frontmatter entry at all -> treated as empty -> no conflict.
        errors = detect_dependency_conflicts({"WP02": ["WP01"]}, {})
        assert errors == []


# ---------------------------------------------------------------------------
# read_existing_frontmatter
# ---------------------------------------------------------------------------


class TestReadExistingFrontmatter:
    def test_reads_typed_dependencies(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        _write_wp(tasks_dir, "WP02", deps=["WP01"])
        existing = read_existing_frontmatter(tasks_dir)
        assert set(existing) == {"WP01", "WP02"}
        assert existing["WP02"].dependencies == ["WP01"]
        assert existing["WP01"].dependencies == []

    def test_unreadable_file_falls_back_to_minimal_meta(self, tasks_dir: Path) -> None:
        # A WP file with malformed/invalid frontmatter falls back gracefully.
        bad = tasks_dir / "WP03-bad.md"
        bad.write_text("---\nwork_package_id: NOTVALID\n---\n", encoding="utf-8")
        existing = read_existing_frontmatter(tasks_dir)
        assert "WP03" in existing
        assert existing["WP03"].work_package_id == "WP03"
        assert existing["WP03"].dependencies == []

    def test_non_wp_files_ignored(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        (tasks_dir / "WPzz-junk.md").write_text("---\n---\n", encoding="utf-8")
        existing = read_existing_frontmatter(tasks_dir)
        assert set(existing) == {"WP01"}


# ---------------------------------------------------------------------------
# compute_wp_frontmatter_updates (pure plan)
# ---------------------------------------------------------------------------


class TestComputeWpFrontmatterUpdates:
    def test_new_dependency_produces_write(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        _write_wp(tasks_dir, "WP02")  # no deps yet
        plan = compute_wp_frontmatter_updates({"WP01": [], "WP02": ["WP01"]}, tasks_dir)
        assert isinstance(plan, FrontmatterUpdatePlan)
        assert plan.updated_count == 1
        assert plan.modified_wps == ["WP02"]
        assert plan.unchanged_wps == ["WP01"]
        assert plan.preserved_wps == []
        (write,) = plan.writes
        assert write.wp_id == "WP02"
        assert write.dependencies == ["WP01"]
        assert write.updated_meta.dependencies == ["WP01"]
        # PURE: no file write occurred — file still has no deps on disk.
        assert read_existing_frontmatter(tasks_dir)["WP02"].dependencies == []

    def test_unchanged_when_deps_already_match(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        _write_wp(tasks_dir, "WP02", deps=["WP01"])
        plan = compute_wp_frontmatter_updates({"WP01": [], "WP02": ["WP01"]}, tasks_dir)
        assert plan.writes == []
        assert plan.updated_count == 0
        assert plan.unchanged_wps == ["WP01", "WP02"]

    def test_preserve_existing_when_parser_finds_none(self, tasks_dir: Path) -> None:
        # Parser found no deps but frontmatter already declares them -> preserve.
        _write_wp(tasks_dir, "WP02", deps=["WP01"])
        plan = compute_wp_frontmatter_updates({"WP02": []}, tasks_dir)
        assert plan.preserved_wps == ["WP02"]
        # deps unchanged (existing == resolved) so no write, not counted as modified.
        assert plan.writes == []
        assert plan.modified_wps == []
        assert plan.unchanged_wps == []

    def test_missing_file_emits_warning_and_skips(self, tasks_dir: Path) -> None:
        plan = compute_wp_frontmatter_updates({"WP99": ["WP01"]}, tasks_dir)
        assert plan.writes == []
        assert any("WP99" in w for w in plan.warnings)

    def test_processed_in_sorted_order(self, tasks_dir: Path) -> None:
        _write_wp(tasks_dir, "WP01")
        _write_wp(tasks_dir, "WP02")
        _write_wp(tasks_dir, "WP03")
        plan = compute_wp_frontmatter_updates(
            {"WP03": ["WP01"], "WP01": [], "WP02": ["WP01"]}, tasks_dir
        )
        # modified WPs follow the sorted iteration order.
        assert plan.modified_wps == ["WP02", "WP03"]

    def test_unreadable_file_in_loop_emits_warning_and_skips(
        self, tasks_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A matching WP file exists but read_wp_frontmatter raises -> warn+skip.
        _write_wp(tasks_dir, "WP02")

        def _boom(_path: Path) -> tuple[WPMetadata, str]:
            raise ValueError("corrupt frontmatter")

        monkeypatch.setattr(tfv, "read_wp_frontmatter", _boom)
        plan = compute_wp_frontmatter_updates({"WP02": ["WP01"]}, tasks_dir)
        assert plan.writes == []
        assert any("Could not read" in w and "WP02" in w for w in plan.warnings)


# ---------------------------------------------------------------------------
# Lane-metadata helpers (moved verbatim — covered here directly)
# ---------------------------------------------------------------------------


class TestLaneHelpers:
    def test_backward_transition_true_when_target_precedes(self) -> None:
        assert _is_backward_transition(Lane.IN_REVIEW, Lane.IN_PROGRESS) is True

    def test_backward_transition_false_when_forward(self) -> None:
        assert _is_backward_transition(Lane.PLANNED, Lane.APPROVED) is False

    def test_backward_transition_false_for_non_axis_lanes(self) -> None:
        # blocked/canceled are outside the directional axis.
        assert _is_backward_transition(Lane.BLOCKED, Lane.PLANNED) is False

    def test_lane_targets_expands_forward_hops(self) -> None:
        targets = _lane_targets_for_emit(Lane.FOR_REVIEW, Lane.APPROVED)
        assert targets == [Lane.IN_REVIEW, Lane.APPROVED]

    def test_lane_targets_alias_resolution(self) -> None:
        # "doing" aliases to in_progress at the input boundary.
        targets = _lane_targets_for_emit("doing", Lane.FOR_REVIEW)
        assert targets == [Lane.FOR_REVIEW]

    def test_lane_targets_non_forward_returns_target_only(self) -> None:
        assert _lane_targets_for_emit(Lane.APPROVED, Lane.IN_PROGRESS) == [Lane.IN_PROGRESS]

    def test_wp_lane_from_empty_events_is_genesis(self) -> None:
        assert _wp_lane_from_status_events([], "WP01") == Lane.GENESIS

    def test_wp_lane_unknown_wp_is_genesis(self) -> None:
        # Build a real event for one WP, then query a different (missing) one.
        from specify_cli.status import StatusEvent

        event = StatusEvent(
            event_id="evt-WP01",
            mission_slug="m",
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="t",
            force=False,
            execution_mode="worktree",
        )
        assert _wp_lane_from_status_events([event], "WP99") == Lane.GENESIS

    def test_wp_lane_reflects_latest_event(self) -> None:
        from specify_cli.status import StatusEvent

        event = StatusEvent(
            event_id="evt-WP01-claimed",
            mission_slug="m",
            wp_id="WP01",
            from_lane=Lane.GENESIS,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="t",
            force=False,
            execution_mode="worktree",
        )
        assert _wp_lane_from_status_events([event], "WP01") == Lane.CLAIMED

    def test_read_transactional_wp_lane_delegates_to_events(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from specify_cli.status import StatusEvent

        event = StatusEvent(
            event_id="evt-WP01-fr",
            mission_slug="m",
            wp_id="WP01",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.FOR_REVIEW,
            at="2026-01-01T00:00:00+00:00",
            actor="t",
            force=False,
            execution_mode="worktree",
        )

        def _fake_read(**_kwargs: object) -> list[StatusEvent]:
            return [event]

        monkeypatch.setattr(tfv, "read_events_transactional", _fake_read)
        lane = _read_transactional_wp_lane(
            feature_dir=tmp_path,
            mission_slug="m",
            wp_id="WP01",
            repo_root=tmp_path,
        )
        assert lane == Lane.FOR_REVIEW
