"""Tests for WP15: spec-kitty charter activate in-flight warning (FR-008).

Covers T087–T092:
- T087: charter activate command exists and is wired into charter_app
- T088: _find_removed_steps logic
- T089: scan_inflight_missions scans status.events.jsonl for in-flight WPs
- T090: emit_step_removal_warnings output format
- T091: activation completes non-blockingly (override file always written)
- T092: full set of acceptance test cases

Test strategy:
- Unit tests for pure functions (find_removed_steps, emit_step_removal_warnings)
- Integration tests using tmp_path + synthetic status.events.jsonl + typer CliRunner
- No git required; tmp_path fixtures provide fully isolated filesystem state

Owner: src/specify_cli/charter_activate.py
Mission: charter-doctrine-mission-type-configuration-01KSWJVX
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from specify_cli.charter_activate import (
    AffectedMission,
    StepRemovalWarning,
    emit_step_removal_warnings,
    find_removed_steps,
    scan_inflight_missions,
)
from specify_cli.cli.commands.charter import charter_app
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

runner = CliRunner()

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_console() -> tuple[Console, StringIO]:
    """Return a (Console, buffer) pair for capturing Rich output."""
    buf = StringIO()
    console = Console(file=buf, highlight=False, markup=True)
    return console, buf


def _write_mission_events(
    kitty_specs_dir: Path,
    mission_slug: str,
    events: list[dict[str, object]],
) -> Path:
    """Create a kitty-specs/<slug>/status.events.jsonl with synthetic events."""
    mission_dir = kitty_specs_dir / mission_slug
    mission_dir.mkdir(parents=True, exist_ok=True)

    # Write meta.json so slug is readable.
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_slug": mission_slug, "mission_type": "software-dev"}),
        encoding="utf-8",
    )

    events_path = mission_dir / "status.events.jsonl"
    lines = [json.dumps(e, sort_keys=True) for e in events]
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return mission_dir


def _make_status_event(
    *,
    event_id: str,
    mission_slug: str,
    wp_id: str,
    from_lane: Lane,
    to_lane: Lane,
    at: str = "2026-01-01T00:00:00+00:00",
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=at,
        actor="fixture",
        force=False,
        execution_mode="worktree",
    )


def _seed_mission_via_append(
    kitty_specs_dir: Path,
    mission_slug: str,
    wp_lane_pairs: list[tuple[str, Lane]],
) -> Path:
    """Use seed_status_event to create a mission with WPs in given lanes."""
    mission_dir = kitty_specs_dir / mission_slug
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_slug": mission_slug, "mission_type": "software-dev"}),
        encoding="utf-8",
    )
    for i, (wp_id, lane) in enumerate(wp_lane_pairs):
        seed_status_event(
            mission_dir,
            _make_status_event(
                event_id=f"seed-{mission_slug}-{wp_id}",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=lane,
                at=f"2026-01-01T00:00:0{i}+00:00",
            ),
        )
    return mission_dir


# ---------------------------------------------------------------------------
# T088 — find_removed_steps
# ---------------------------------------------------------------------------


class TestFindRemovedSteps:
    def test_no_change_returns_empty(self) -> None:
        current = ["specify", "plan", "tasks", "implement", "review"]
        incoming = ["specify", "plan", "tasks", "implement", "review"]
        assert find_removed_steps(current, incoming) == []

    def test_removal_at_end(self) -> None:
        current = ["specify", "plan", "implement", "review"]
        incoming = ["specify", "plan", "implement"]
        assert find_removed_steps(current, incoming) == ["review"]

    def test_removal_in_middle(self) -> None:
        current = ["specify", "plan", "review", "merge"]
        incoming = ["specify", "plan", "merge"]
        assert find_removed_steps(current, incoming) == ["review"]

    def test_multiple_removals(self) -> None:
        current = ["specify", "plan", "tasks", "implement", "review", "merge"]
        incoming = ["specify", "plan", "implement", "merge"]
        assert find_removed_steps(current, incoming) == ["tasks", "review"]

    def test_addition_only_returns_empty(self) -> None:
        current = ["specify", "plan"]
        incoming = ["specify", "plan", "extra-step"]
        assert find_removed_steps(current, incoming) == []

    def test_empty_current_returns_empty(self) -> None:
        assert find_removed_steps([], ["specify"]) == []

    def test_empty_incoming_removes_all(self) -> None:
        current = ["specify", "plan"]
        assert find_removed_steps(current, []) == ["specify", "plan"]

    def test_preserves_order_from_current(self) -> None:
        current = ["c", "b", "a"]
        incoming = ["a"]
        assert find_removed_steps(current, incoming) == ["c", "b"]


# ---------------------------------------------------------------------------
# T089 — scan_inflight_missions
# ---------------------------------------------------------------------------


class TestScanInflightMissions:
    def test_returns_empty_when_no_removed_steps(self, tmp_path: Path) -> None:
        kitty_specs = tmp_path / "kitty-specs"
        kitty_specs.mkdir()
        result = scan_inflight_missions([], kitty_specs)
        assert result == []

    def test_returns_warning_per_removed_step(self, tmp_path: Path) -> None:
        kitty_specs = tmp_path / "kitty-specs"
        _seed_mission_via_append(kitty_specs, "001-demo", [("WP01", Lane.FOR_REVIEW)])
        result = scan_inflight_missions(["review"], kitty_specs)
        assert len(result) == 1
        assert result[0].removed_step_id == "review"
        assert len(result[0].affected_missions) == 1
        am = result[0].affected_missions[0]
        assert am.mission_slug == "001-demo"
        assert am.wp_id == "WP01"
        assert am.current_lane == "for_review"

    def test_no_warning_when_no_inflight_wps(self, tmp_path: Path) -> None:
        kitty_specs = tmp_path / "kitty-specs"
        # WP01 is in 'done' — not in-flight.
        _seed_mission_via_append(kitty_specs, "002-done", [("WP01", Lane.DONE)])
        result = scan_inflight_missions(["review"], kitty_specs)
        assert len(result) == 1
        assert result[0].affected_missions == []

    def test_multiple_missions_aggregated(self, tmp_path: Path) -> None:
        kitty_specs = tmp_path / "kitty-specs"
        _seed_mission_via_append(kitty_specs, "aaa-first", [("WP01", Lane.FOR_REVIEW)])
        _seed_mission_via_append(kitty_specs, "bbb-second", [("WP02", Lane.IN_REVIEW)])
        result = scan_inflight_missions(["review"], kitty_specs)
        assert len(result) == 1
        slugs = {am.mission_slug for am in result[0].affected_missions}
        assert "aaa-first" in slugs
        assert "bbb-second" in slugs

    def test_multiple_removed_steps_each_get_same_inflight(self, tmp_path: Path) -> None:
        kitty_specs = tmp_path / "kitty-specs"
        _seed_mission_via_append(kitty_specs, "multi", [("WP01", Lane.IN_PROGRESS)])
        result = scan_inflight_missions(["tasks", "review"], kitty_specs)
        assert len(result) == 2
        assert result[0].removed_step_id == "tasks"
        assert result[1].removed_step_id == "review"
        # Both steps reference the same in-flight WP.
        assert len(result[0].affected_missions) == 1
        assert len(result[1].affected_missions) == 1

    def test_skips_missions_without_events_file(self, tmp_path: Path) -> None:
        kitty_specs = tmp_path / "kitty-specs"
        kitty_specs.mkdir()
        # Create a mission directory with no status.events.jsonl.
        (kitty_specs / "phantom-mission").mkdir()
        result = scan_inflight_missions(["review"], kitty_specs)
        assert result == [StepRemovalWarning(removed_step_id="review", affected_missions=[])]

    def test_handles_nonexistent_kitty_specs_dir(self, tmp_path: Path) -> None:
        kitty_specs = tmp_path / "kitty-specs"  # does not exist
        result = scan_inflight_missions(["review"], kitty_specs)
        assert len(result) == 1
        assert result[0].affected_missions == []


# ---------------------------------------------------------------------------
# T090 — emit_step_removal_warnings
# ---------------------------------------------------------------------------


class TestEmitStepRemovalWarnings:
    def test_no_output_for_empty_warnings(self) -> None:
        console, buf = _make_console()
        emit_step_removal_warnings([], console)
        assert buf.getvalue() == ""

    def test_no_output_when_no_affected_missions(self) -> None:
        console, buf = _make_console()
        warnings = [StepRemovalWarning(removed_step_id="review", affected_missions=[])]
        emit_step_removal_warnings(warnings, console)
        assert buf.getvalue() == ""

    def test_warning_line_contains_step_id(self) -> None:
        console, buf = _make_console()
        warnings = [
            StepRemovalWarning(
                removed_step_id="review",
                affected_missions=[
                    AffectedMission(
                        mission_slug="001-demo",
                        wp_id="WP03",
                        current_lane="in_review",
                    )
                ],
            )
        ]
        emit_step_removal_warnings(warnings, console)
        output = buf.getvalue()
        assert "review" in output

    def test_warning_line_contains_mission_slug(self) -> None:
        console, buf = _make_console()
        warnings = [
            StepRemovalWarning(
                removed_step_id="review",
                affected_missions=[
                    AffectedMission(
                        mission_slug="083-my-feature",
                        wp_id="WP03",
                        current_lane="in_review",
                    )
                ],
            )
        ]
        emit_step_removal_warnings(warnings, console)
        assert "083-my-feature" in buf.getvalue()

    def test_warning_line_contains_wp_id(self) -> None:
        console, buf = _make_console()
        warnings = [
            StepRemovalWarning(
                removed_step_id="review",
                affected_missions=[
                    AffectedMission(
                        mission_slug="001-demo",
                        wp_id="WP05",
                        current_lane="for_review",
                    )
                ],
            )
        ]
        emit_step_removal_warnings(warnings, console)
        assert "WP05" in buf.getvalue()

    def test_warning_line_contains_current_lane(self) -> None:
        console, buf = _make_console()
        warnings = [
            StepRemovalWarning(
                removed_step_id="review",
                affected_missions=[
                    AffectedMission(
                        mission_slug="001-demo",
                        wp_id="WP03",
                        current_lane="for_review",
                    )
                ],
            )
        ]
        emit_step_removal_warnings(warnings, console)
        assert "for_review" in buf.getvalue()

    def test_multiple_missions_each_listed(self) -> None:
        console, buf = _make_console()
        warnings = [
            StepRemovalWarning(
                removed_step_id="review",
                affected_missions=[
                    AffectedMission("mission-a", "WP01", "in_review"),
                    AffectedMission("mission-b", "WP02", "for_review"),
                ],
            )
        ]
        emit_step_removal_warnings(warnings, console)
        output = buf.getvalue()
        assert "mission-a" in output
        assert "mission-b" in output


# ---------------------------------------------------------------------------
# T087 — CLI command wired into charter_app
# ---------------------------------------------------------------------------


class TestCharterActivateCLI:
    def test_activate_subgroup_registered(self) -> None:
        """``charter activate --help`` exits 0 (sub-group is registered)."""
        result = runner.invoke(charter_app, ["activate", "--help"])
        assert result.exit_code == 0, result.output
        assert "activate" in result.output.lower()

    def test_activate_mission_type_emits_warning_when_inflight(self, tmp_path: Path) -> None:
        """CLI activate mission-type emits in-flight step-removal warning (FR-008)."""
        from unittest.mock import MagicMock

        kitty_specs = tmp_path / "kitty-specs"
        _seed_mission_via_append(kitty_specs, "live-mission", [("WP02", Lane.FOR_REVIEW)])
        (tmp_path / ".kittify").mkdir(exist_ok=True)
        (tmp_path / ".kittify" / "config.yaml").write_text("# empty\n", encoding="utf-8")

        mock_mt = MagicMock()
        mock_mt.action_sequence = ["specify", "plan"]

        with (
            patch(
                "charter.activation.mission_type_profiles.resolve_mission_type_context",
                return_value=SimpleNamespace(action_sequence=["specify", "plan", "review"]),
            ),
            patch(
                "specify_cli.cli.commands.charter.mission_type.resolve_layered_roster",
                return_value={"software-dev": mock_mt},
            ),
        ):
            result = runner.invoke(
                charter_app,
                ["activate", "--repo-root", str(tmp_path), "mission-type", "software-dev"],
                catch_exceptions=False,
            )

        assert result.exit_code == 0, result.output
        # Step removal warning emitted for in-flight WPs.
        assert "review" in result.output

    def test_activate_mission_type_surfaces_resolution_failure_not_silenced(
        self, tmp_path: Path
    ) -> None:
        """FR-009 edge case (spec.md Edge Cases): a previous action_sequence
        resolution failure (WP06's ``MissionTypeEmptyActionSequenceError``)
        MUST surface, not be silently folded into "no steps were removed"
        by the bare ``except Exception`` this fix replaces.

        CL-006/NFR-002 (post-fix verification sweep, mission
        up-mission-type-seam-01KZY1JB): "surface" was pinned here as "let the
        raw exception propagate all the way out of the CLI" -- which was
        itself the bug the sweep flagged (an uncaught traceback, not
        ``typer.Exit``). ``MissionTypeEmptyActionSequenceError`` IS a
        ``ValueError`` subclass, so it is now caught by the same CLI-boundary
        handler that catches a malformed-YAML ``ValueError`` from the layered
        roster scan -- "surfaced" now means a clean, operator-readable
        ``typer.Exit(1)`` naming the failure, not a raw traceback.
        """
        from charter.activation.mission_type_profiles import MissionTypeEmptyActionSequenceError

        (tmp_path / ".kittify").mkdir(exist_ok=True)
        (tmp_path / ".kittify" / "config.yaml").write_text("# empty\n", encoding="utf-8")

        with patch(
            "charter.activation.mission_type_profiles.resolve_mission_type_context",
            side_effect=MissionTypeEmptyActionSequenceError("qa", "org"),
        ):
            result = runner.invoke(
                charter_app,
                ["activate", "--repo-root", str(tmp_path), "mission-type", "qa"],
                catch_exceptions=True,
            )

        assert result.exit_code == 1, result.output
        assert isinstance(result.exception, SystemExit), (
            f"expected a clean typer.Exit(1) (SystemExit), got a raw "
            f"{type(result.exception).__name__}: {result.exception!r}"
        )
        assert "qa" in result.output and "org" in result.output, result.output
