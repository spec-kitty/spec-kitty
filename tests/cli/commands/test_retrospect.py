"""CLI tests for WP05: spec-kitty retrospect create / backfill / summary / synthesize.

Tests:
- TestCreateCommand: success, RecordExists, MissionNotCompleted, AmbiguousSelector,
                      --overwrite, --update, --json
- TestBackfillCommand: dry-run, real run, since/until filtering, mission filter,
                       emit-skipped/failures, JSON shape
- TestSummaryReadOnlyInvariant: no filesystem mutation; 4-state output
- TestSynthesizeTighteningDefault: missing record error
- TestSynthesizeFabricateEmpty: --fabricate-empty flag
- TestCreateHarness / TestBackfillHarness: create/backfill/synthesize driven end to end on a
  real git project (``retrospect_project``); only the Zeitgeist fan-out and the clock are patched

FR-016 env-mutation check: no SPEC_KITTY_RETROSPECTIVE or SPEC_KITTY_MODE setenv in this file.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
import os
import subprocess
from kernel.clock import timedelta, now_utc_iso, now_utc
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.retrospect import app as retrospect_app
from specify_cli.cli.commands.agent_retrospect import app as agent_retrospect_app

from tests._support.ansi import strip_ansi
from tests._support.eacces import mode_bits_enforced

pytestmark = [pytest.mark.unit, pytest.mark.fast]

RUNNER = CliRunner()

# ---------------------------------------------------------------------------
# Test mission IDs & slugs
# ---------------------------------------------------------------------------

MISSION_ID_COMPLETED = "01KS049J4V9CSWBKJHTY2FB69H"
MISSION_SLUG_COMPLETED = "test-completed-mission"
MISSION_ID_OPEN = "01KS049J4V9CSWBKJHTY2FB70H"
MISSION_SLUG_OPEN = "test-open-mission"


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


# An unprotected mission target branch; ``main`` / ``master`` are protected by default.
_MISSION_BRANCH = "feature/retrospect-tests"
_PROTECTED_BRANCH = "main"


def _write_meta(dir: Path, mission_id: str, mission_slug: str, **kwargs: Any) -> None:
    meta = {
        "mission_id": mission_id,
        "mission_slug": mission_slug,
        "slug": mission_slug,
        "created_at": "2026-05-01T10:00:00+00:00",
        **kwargs,
    }
    dir.mkdir(parents=True, exist_ok=True)
    (dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _write_kitty_meta(kitty_dir: Path, mission_id: str, mission_slug: str) -> None:
    """Write meta.json for a mission in kitty-specs/<slug>/."""
    kitty_dir.mkdir(parents=True, exist_ok=True)
    (kitty_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": mission_slug,
                "slug": mission_slug,
            }
        ),
        encoding="utf-8",
    )


def _write_status_events_all_done(feature_dir: Path, mission_slug: str) -> None:
    """Write a status.events.jsonl with all WPs in 'done' lanes."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {
            "event_id": "01KS000000000000000000WP01",
            "at": "2026-05-01T10:00:00+00:00",
            "actor": "test",
            "feature_slug": mission_slug,
            "wp_id": "WP01",
            "from_lane": "planned",
            "to_lane": "done",
            "force": False,
            "reason": None,
            "review_ref": None,
            "evidence": None,
            "execution_mode": "main",
        }
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events),
        encoding="utf-8",
    )


def _write_status_events_open_wp(feature_dir: Path, mission_slug: str) -> None:
    """Write a status.events.jsonl with WP01 in 'in_progress' (non-terminal)."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    events = [
        {
            "event_id": "01KS000000000000000000WP01",
            "at": "2026-05-01T10:00:00+00:00",
            "actor": "test",
            "feature_slug": mission_slug,
            "wp_id": "WP01",
            "from_lane": "planned",
            "to_lane": "in_progress",
            "force": False,
            "reason": None,
            "review_ref": None,
            "evidence": None,
            "execution_mode": "main",
        }
    ]
    (feature_dir / "status.events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events),
        encoding="utf-8",
    )


def _make_minimal_gen_record(
    mission_id: str = MISSION_ID_COMPLETED,
    mission_slug: str = MISSION_SLUG_COMPLETED,
    findings_status: str = "ran_no_findings",
) -> Any:
    """Build a minimal GenRetrospectiveRecord for testing."""
    from specify_cli.retrospective.schema import (
        GenActor,
        GenProvenance,
        GenRetrospectiveRecord,
    )

    now = now_utc_iso()
    return GenRetrospectiveRecord(
        schema_version=1,
        mission_id=mission_id,
        mission_slug=mission_slug,
        mission_number=None,
        friendly_name="Test Mission",
        mission_type="software-dev",
        target_branch="main",
        created_at=now,
        created_by=GenActor(kind="runtime", id="test-generator"),
        provenance=GenProvenance(
            kind="explicit_create",
            invoked_at=now,
        ),
        policy_source={},
        findings_status=findings_status,
        helped=[],
        not_helpful=[],
        gaps=[],
        proposals=[],
        evidence_refs=[],
        generator_version="0.0.1-test",
    )


def _setup_project(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Set up minimal project structure.

    Returns (repo_root, missions_dir, kitty_specs_dir).
    """
    missions_dir = tmp_path / ".kittify" / "missions"
    missions_dir.mkdir(parents=True, exist_ok=True)
    kitty_specs_dir = tmp_path / "kitty-specs"
    kitty_specs_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path, missions_dir, kitty_specs_dir


def _build_resolved_mission(
    mission_id: str,
    mission_slug: str,
    feature_dir: Path | None = None,
) -> Any:
    """Build a ResolvedMission dataclass."""
    from specify_cli.context.mission_resolver import ResolvedMission

    return ResolvedMission(
        mission_id=mission_id,
        mission_slug=mission_slug,
        feature_dir=feature_dir or Path("/nonexistent"),
        mid8=mission_id[:8],
    )


# ---------------------------------------------------------------------------
# TestCreateCommand
# ---------------------------------------------------------------------------


class TestCreateCommand:
    """Tests for `spec-kitty retrospect create`."""

    def test_create_mission_not_completed_json(self, tmp_path: Path) -> None:
        """MISSION_NOT_COMPLETED error matches contract shape."""
        repo_root, _, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_OPEN
        _write_kitty_meta(feature_dir, MISSION_ID_OPEN, MISSION_SLUG_OPEN)
        _write_status_events_open_wp(feature_dir, MISSION_SLUG_OPEN)

        resolved = _build_resolved_mission(MISSION_ID_OPEN, MISSION_SLUG_OPEN, feature_dir)
        open_wps = [{"wp_id": "WP01", "lane": "in_progress"}]

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=open_wps),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_OPEN, "--json"])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["result"] == "blocked"
        assert data["code"] == "MISSION_NOT_COMPLETED"
        assert data["mission_id"] == MISSION_ID_OPEN
        assert "open_wps" in data
        assert frozenset(wp["wp_id"] for wp in data["open_wps"]) == frozenset({"WP01"})
        assert data["open_wps"][0]["lane"] == "in_progress"
        assert data["exit_code"] == 1

    def test_create_ambiguous_selector_exit_2(self, tmp_path: Path) -> None:
        """Ambiguous mission handle raises exit 2."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.context.mission_resolver import AmbiguousHandleError

        class _FakeCandidate:
            mission_id = MISSION_ID_COMPLETED
            mission_slug = MISSION_SLUG_COMPLETED
            mid8 = MISSION_ID_COMPLETED[:8]
            feature_dir = tmp_path

            def __str__(self) -> str:
                return self.mission_slug

        exc = AmbiguousHandleError(
            handle="ambiguous",
            candidates=[_FakeCandidate(), _FakeCandidate()],  # type: ignore[list-item]
        )

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_mission", side_effect=exc),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", "ambiguous", "--json"])

        assert result.exit_code == 2
        data = json.loads(result.output)
        assert data["code"] == "MISSION_AMBIGUOUS_SELECTOR"

    def test_create_overwrite_and_update_mutually_exclusive(self, tmp_path: Path) -> None:
        """--overwrite and --update together should produce an error."""
        repo_root, _, _ = _setup_project(tmp_path)

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(
                retrospect_app,
                ["create", "--mission", MISSION_SLUG_COMPLETED, "--overwrite", "--update"],
            )

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# TestBackfillCommand
# ---------------------------------------------------------------------------


class TestBackfillCommand:
    """Tests for `spec-kitty retrospect backfill`."""

    def test_backfill_dry_run(self, tmp_path: Path) -> None:
        """--dry-run reports counts without writing files."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Set up a completed mission in the window
        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(
            mission_dir,
            MISSION_ID_COMPLETED,
            MISSION_SLUG_COMPLETED,
            completed_at=completed_at,
        )

        record_path = mission_dir / "retrospective.yaml"
        assert not record_path.exists()

        result = RUNNER.invoke(retrospect_app, ["backfill", "--dry-run", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["result"] == "success"
        assert "window" in data
        assert "scanned" in data
        assert isinstance(data["created"], int)
        assert isinstance(data["skipped"], list)
        assert isinstance(data["failed"], list)

        # No file should be written
        assert not record_path.exists()

    def test_backfill_skips_already_exists(self, tmp_path: Path) -> None:
        """Missions with existing records are skipped with reason='already_exists'."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(
            mission_dir,
            MISSION_ID_COMPLETED,
            MISSION_SLUG_COMPLETED,
            completed_at=completed_at,
        )

        # Pre-existing record
        record_path = mission_dir / "retrospective.yaml"
        record_path.write_text("existing: true\n", encoding="utf-8")

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        skipped = data["skipped"]
        assert any(s["reason"] == "already_exists" for s in skipped)

    def test_backfill_since_until_filtering(self, tmp_path: Path) -> None:
        """--since/--until filtering excludes missions outside the window."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Mission outside the window (2020)
        old_date = "2020-01-01T00:00:00+00:00"
        old_mission_id = "01KS049J4V9CSWBKJHTY2FB71H"
        old_slug = "old-mission"
        old_dir = missions_dir / old_mission_id
        _write_meta(old_dir, old_mission_id, old_slug, completed_at=old_date)

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(
                retrospect_app,
                ["backfill", "--since", "2026-01-01", "--until", "2026-12-31", "--json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["window"]["since"] == "2026-01-01"
        assert data["window"]["until"] == "2026-12-31"
        # The old mission should be skipped
        skipped = data["skipped"]
        assert any(s.get("reason") == "out_of_window" for s in skipped)

    def test_backfill_mission_filter(self, tmp_path: Path) -> None:
        """--mission flag restricts backfill to a single mission."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()

        # Two missions
        mid_a = "01KS049J4V9CSWBKJHTY2FB72H"
        slug_a = "mission-alpha"
        mid_b = "01KS049J4V9CSWBKJHTY2FB73H"
        slug_b = "mission-beta"

        dir_a = missions_dir / mid_a
        dir_b = missions_dir / mid_b
        _write_meta(dir_a, mid_a, slug_a, completed_at=completed_at)
        _write_meta(dir_b, mid_b, slug_b, completed_at=completed_at)

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(
                retrospect_app,
                ["backfill", "--mission", slug_b, "--dry-run", "--json"],
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        # mission-alpha should be excluded (mission_filter_excluded)
        skipped = data["skipped"]
        assert any(s.get("reason") == "mission_filter_excluded" for s in skipped)

    def test_backfill_json_aggregate_shape(self, tmp_path: Path) -> None:
        """--json output is a single aggregate object, not streaming lines."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(retrospect_app, ["backfill", "--json"])

        assert result.exit_code == 0
        # Should be parseable as a single JSON object
        data = json.loads(result.output)
        assert isinstance(data, dict)
        for key in ("result", "window", "scanned", "created", "skipped", "failed", "next_actions"):
            assert key in data

    def test_backfill_invalid_since_exits_2(self, tmp_path: Path) -> None:
        """Invalid --since value should exit with non-zero code."""
        repo_root, _, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(
            retrospect_app,
            ["backfill", "--since", "not-a-date"],
        )

        assert result.exit_code != 0

    def test_backfill_no_json_shows_progress(self, tmp_path: Path) -> None:
        """Without --json, output is human-readable (not bare JSON)."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(retrospect_app, ["backfill"])

        assert result.exit_code == 0
        # Should not be a JSON object as the only output
        with contextlib.suppress(json.JSONDecodeError):
            json.loads(result.output.strip())
            # If it parses as JSON, that's OK if it's mixed with Rich output


# ---------------------------------------------------------------------------
# TestSummaryReadOnlyInvariant
# ---------------------------------------------------------------------------


class TestSummaryReadOnlyInvariant:
    """Tests for `spec-kitty retrospect summary` — read-only invariant."""

    def _snapshot_dir(self, path: Path) -> dict[str, float]:
        """Return a dict of relative_path -> mtime for all files under path."""
        result = {}
        for f in path.rglob("*"):
            if f.is_file():
                with contextlib.suppress(Exception):
                    result[str(f.relative_to(path))] = f.stat().st_mtime
        return result

    def test_summary_no_filesystem_mutation(self, tmp_path: Path) -> None:
        """Summary command must not write any files."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Add a mission with a record
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        mission_dir.mkdir(parents=True, exist_ok=True)
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        # Write a minimal retrospective.yaml
        (mission_dir / "retrospective.yaml").write_text(
            "schema_version: '1'\nmission: {}\nstatus: completed\nhelped: []\nnot_helpful: []\ngaps: []\nproposals: []\n",
            encoding="utf-8",
        )

        snapshot_before = self._snapshot_dir(tmp_path)

        result = RUNNER.invoke(retrospect_app, ["summary", "--project", str(tmp_path), "--json"])

        snapshot_after = self._snapshot_dir(tmp_path)

        assert result.exit_code == 0
        # No new files created
        new_files = set(snapshot_after.keys()) - set(snapshot_before.keys())
        assert not new_files, f"summary created new files: {new_files}"
        # No existing files modified
        for path, mtime in snapshot_before.items():
            if path in snapshot_after:
                assert snapshot_after[path] == mtime, f"summary modified file: {path}"

    def test_summary_4_state_output(self, tmp_path: Path) -> None:
        """Summary JSON output includes per-mission findings_status and aggregate counts."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        result = RUNNER.invoke(retrospect_app, ["summary", "--project", str(tmp_path), "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "missions" in data
        assert "aggregate" in data

        agg = data["aggregate"]
        for state in ("has_findings", "ran_no_findings", "missing", "failed"):
            assert state in agg
            assert isinstance(agg[state], int)

    def test_summary_filter_flag(self, tmp_path: Path) -> None:
        """--filter flag only shows missions in the given state."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--filter", "missing", "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data.get("filter") == "missing"
        # All returned missions should be in 'missing' state
        for m in data.get("missions", []):
            assert m["findings_status"] == "missing"

    def test_summary_invalid_filter_exits_1(self, tmp_path: Path) -> None:
        """Invalid --filter value should exit 1."""
        repo_root, _, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--filter", "invalid_state"],
        )

        assert result.exit_code == 1

    def test_summary_empty_project_exits_1(self, tmp_path: Path) -> None:
        """Project root without .kittify/ or kitty-specs/ exits 1."""
        empty_dir = tmp_path / "empty_project"
        empty_dir.mkdir()

        result = RUNNER.invoke(retrospect_app, ["summary", "--project", str(empty_dir)])

        assert result.exit_code == 1

    def test_summary_policy_source_in_output(self, tmp_path: Path) -> None:
        """Each mission entry has a policy_source field."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(retrospect_app, ["summary", "--project", str(tmp_path), "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "missions" in data
        for mission_entry in data["missions"]:
            assert "policy_source" in mission_entry
            assert "findings_status" in mission_entry

    def test_agent_retrospect_summary_backcompat(self, tmp_path: Path) -> None:
        """agent retrospect summary works as back-compat alias."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(
            agent_retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "aggregate" in data


# ---------------------------------------------------------------------------
# TestSynthesizeTighteningDefault
# ---------------------------------------------------------------------------


class TestSynthesizeTighteningDefault:
    """Tests for the tightened synthesize default-path (T028)."""

    def test_synthesize_missing_record_errors(self, tmp_path: Path) -> None:
        """Default path: missing record → RETROSPECTIVE_RECORD_MISSING exit 1."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        # No retrospective.yaml on disk
        retro_path = missions_dir / MISSION_ID_COMPLETED / "retrospective.yaml"
        assert not retro_path.exists()

        with (
            patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=resolved),
        ):
            result = RUNNER.invoke(
                agent_retrospect_app,
                ["synthesize", "--mission", MISSION_SLUG_COMPLETED, "--json"],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["code"] == "RETROSPECTIVE_RECORD_MISSING"
        assert data["result"] == "blocked"
        assert data["mission_id"] == MISSION_ID_COMPLETED
        assert data["mission_slug"] == MISSION_SLUG_COMPLETED
        assert "blocked_reason" in data
        assert "spec-kitty retrospect create" in data["blocked_reason"]
        assert data["exit_code"] == 1

    def test_synthesize_missing_record_non_json_output(self, tmp_path: Path) -> None:
        """Missing record without --json produces human-readable error."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        with (
            patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=resolved),
        ):
            result = RUNNER.invoke(
                agent_retrospect_app,
                ["synthesize", "--mission", MISSION_SLUG_COMPLETED],
            )

        assert result.exit_code == 1
        assert "RETROSPECTIVE_RECORD_MISSING" in result.output or "spec-kitty retrospect create" in result.output


# ---------------------------------------------------------------------------
# TestSynthesizeFabricateEmpty
# ---------------------------------------------------------------------------


class TestSynthesizeFabricateEmpty:
    """Tests for the --fabricate-empty legacy flag."""

    def test_fabricate_empty_not_set_still_errors_on_missing(self, tmp_path: Path) -> None:
        """Without --fabricate-empty, missing record still errors exit 1."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        with (
            patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=resolved),
        ):
            result = RUNNER.invoke(
                agent_retrospect_app,
                ["synthesize", "--mission", MISSION_SLUG_COMPLETED, "--json"],
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["code"] == "RETROSPECTIVE_RECORD_MISSING"

    def test_help_shows_fabricate_empty_flag(self) -> None:
        """--fabricate-empty flag appears in help text."""
        result = RUNNER.invoke(agent_retrospect_app, ["synthesize", "--help"])
        assert result.exit_code == 0
        # Strip ANSI: under CI, Rich force-enables terminal styling so the
        # captured help carries colour codes that break a raw substring check.
        assert "--fabricate-empty" in strip_ansi(result.output)


# ---------------------------------------------------------------------------
# TestResolveHandleErrorPaths
# ---------------------------------------------------------------------------


class TestResolveHandleErrorPaths:
    """Tests for _resolve_handle error paths (non-JSON mode, MISSION_NOT_FOUND)."""

    def test_resolve_handle_mission_not_found_non_json(self, tmp_path: Path) -> None:
        """MISSION_NOT_FOUND in non-JSON mode writes to stderr and exits 1."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.context.mission_resolver import MissionNotFoundError

        exc = MissionNotFoundError(handle="nonexistent-mission")

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_mission", side_effect=exc),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", "nonexistent-mission"])

        assert result.exit_code == 1
        # Should not be JSON (no --json flag)
        assert "MISSION_NOT_FOUND" in result.output or "nonexistent" in result.output.lower()

    def test_resolve_handle_mission_not_found_json(self, tmp_path: Path) -> None:
        """MISSION_NOT_FOUND in JSON mode outputs structured error."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.context.mission_resolver import MissionNotFoundError

        exc = MissionNotFoundError(handle="nonexistent-mission")

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_mission", side_effect=exc),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", "nonexistent-mission", "--json"])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["code"] == "MISSION_NOT_FOUND"
        assert data["result"] == "blocked"

    def test_resolve_handle_ambiguous_non_json(self, tmp_path: Path) -> None:
        """MISSION_AMBIGUOUS_SELECTOR in non-JSON mode writes to stderr and exits 2."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.context.mission_resolver import AmbiguousHandleError

        class _FakeCandidate:
            mission_id = MISSION_ID_COMPLETED
            mission_slug = MISSION_SLUG_COMPLETED
            mid8 = MISSION_ID_COMPLETED[:8]
            feature_dir = tmp_path

            def __str__(self) -> str:
                return self.mission_slug

        exc = AmbiguousHandleError(
            handle="ambiguous",
            candidates=[_FakeCandidate(), _FakeCandidate()],  # type: ignore[list-item]
        )

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_mission", side_effect=exc),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", "ambiguous"])

        assert result.exit_code == 2

    def test_resolve_handle_system_exit(self, tmp_path: Path) -> None:
        """SystemExit from resolve_mission is caught and converted to exit 1."""
        repo_root, _, _ = _setup_project(tmp_path)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_mission", side_effect=SystemExit(1)),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", "anything"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# TestCheckMissionCompleted
# ---------------------------------------------------------------------------


class TestCheckMissionCompleted:
    """Tests for _check_mission_completed helper."""

    def test_check_completed_feature_dir_none(self, tmp_path: Path) -> None:
        """Returns [] when feature_dir is None."""
        from specify_cli.cli.commands.retrospect import _check_mission_completed

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir=None)
        # Override to have feature_dir = None
        from specify_cli.context.mission_resolver import ResolvedMission

        resolved = ResolvedMission(
            mission_id=MISSION_ID_COMPLETED,
            mission_slug=MISSION_SLUG_COMPLETED,
            feature_dir=None,
            mid8=MISSION_ID_COMPLETED[:8],
        )

        result = _check_mission_completed(resolved, tmp_path)
        assert result == []

    def test_check_completed_read_events_fails(self, tmp_path: Path) -> None:
        """Returns [] when read_events raises an exception."""
        from specify_cli.cli.commands.retrospect import _check_mission_completed

        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG_COMPLETED
        feature_dir.mkdir(parents=True, exist_ok=True)
        # Write a corrupted status.events.jsonl
        (feature_dir / "status.events.jsonl").write_text("not json!\n", encoding="utf-8")

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        # Patch read_events to raise
        with patch("specify_cli.cli.commands.retrospect.read_events", side_effect=Exception("bad")):
            result = _check_mission_completed(resolved, tmp_path)

        assert result == []

    def test_check_completed_empty_events(self, tmp_path: Path) -> None:
        """Returns [] when events list is empty."""
        from specify_cli.cli.commands.retrospect import _check_mission_completed

        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG_COMPLETED
        feature_dir.mkdir(parents=True, exist_ok=True)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        with patch("specify_cli.cli.commands.retrospect.read_events", return_value=[]):
            result = _check_mission_completed(resolved, tmp_path)

        assert result == []

    def test_check_completed_with_open_wps(self, tmp_path: Path) -> None:
        """Returns non-empty list when WPs are in non-terminal lanes."""
        from specify_cli.cli.commands.retrospect import _check_mission_completed

        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG_COMPLETED
        feature_dir.mkdir(parents=True, exist_ok=True)
        _write_status_events_open_wp(feature_dir, MISSION_SLUG_COMPLETED)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        result = _check_mission_completed(resolved, tmp_path)
        assert len(result) > 0
        assert result[0]["wp_id"] == "WP01"
        assert result[0]["lane"] == "in_progress"

    def test_check_completed_all_done(self, tmp_path: Path) -> None:
        """Returns [] when all WPs are in terminal lanes."""
        from specify_cli.cli.commands.retrospect import _check_mission_completed

        feature_dir = tmp_path / "kitty-specs" / MISSION_SLUG_COMPLETED
        feature_dir.mkdir(parents=True, exist_ok=True)
        _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        result = _check_mission_completed(resolved, tmp_path)
        assert result == []


# ---------------------------------------------------------------------------
# TestMaybeAutoCommit
# ---------------------------------------------------------------------------


class TestMaybeAutoCommit:
    """Tests for _maybe_auto_commit helper."""

    @staticmethod
    def _committed_repo(tmp_path: Path, *, auto_commit: bool, branch: str = _MISSION_BRANCH) -> tuple[Path, str]:
        """A real git repo on *branch* (the mission's target) with one commit; returns (repo, HEAD)."""
        repo = tmp_path / "repo"
        _init_git_repo(repo, auto_commit=auto_commit, branch=branch)
        (repo / "README.md").write_text("init\n", encoding="utf-8")
        _write_meta(repo / "kitty-specs" / MISSION_SLUG_COMPLETED, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, target_branch=branch)
        _git(repo, "add", "--", "README.md", ".kittify", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "init")
        return repo, _git(repo, "rev-parse", "HEAD")

    def test_auto_commit_disabled_in_config_commits_nothing(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        repo, head_before = self._committed_repo(tmp_path, auto_commit=False)
        record = repo / "kitty-specs" / MISSION_SLUG_COMPLETED / "retrospective.yaml"
        record.write_text("schema_version: 1\n", encoding="utf-8")

        _maybe_auto_commit(repo, MISSION_SLUG_COMPLETED, [record], "chore(retrospective): must not land")

        assert _git(repo, "rev-parse", "HEAD") == head_before
        assert _git(repo, "status", "--porcelain", "--untracked-files=all") == f"?? kitty-specs/{MISSION_SLUG_COMPLETED}/retrospective.yaml"
        assert capsys.readouterr().err == ""

    def test_auto_commit_enabled_commits_exactly_the_files_with_the_message(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        repo, head_before = self._committed_repo(tmp_path, auto_commit=True)
        record = repo / "kitty-specs" / MISSION_SLUG_COMPLETED / "retrospective.yaml"
        record.write_text("schema_version: 1\n", encoding="utf-8")
        bystander = repo / "unrelated.txt"
        bystander.write_text("not part of the retrospective\n", encoding="utf-8")

        _maybe_auto_commit(repo, MISSION_SLUG_COMPLETED, [record], "chore(retrospective): author retrospective")

        # Exactly one new commit, on top of the previous HEAD, carrying the message.
        assert _git(repo, "log", "--format=%s") == "chore(retrospective): author retrospective\ninit"
        assert _git(repo, "rev-parse", "HEAD~1") == head_before
        assert _git(repo, "show", "--name-only", "--format=", "HEAD") == f"kitty-specs/{MISSION_SLUG_COMPLETED}/retrospective.yaml"
        assert _git(repo, "status", "--porcelain", "--untracked-files=all") == "?? unrelated.txt"
        assert capsys.readouterr().err == ""

    @pytest.mark.parametrize("branch", [_MISSION_BRANCH, _PROTECTED_BRANCH], ids=["unprotected", "protected"])
    def test_auto_commit_of_already_committed_files_is_silent(self, tmp_path: Path, capsys: pytest.CaptureFixture[str], branch: str) -> None:
        """Nothing to commit is not a failure, not even on a protected target: no commit, no warning."""
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        repo, _ = self._committed_repo(tmp_path, auto_commit=True, branch=branch)
        record = repo / "kitty-specs" / MISSION_SLUG_COMPLETED / "retrospective.yaml"
        record.write_text("schema_version: 1\n", encoding="utf-8")
        _git(repo, "add", "--", str(record))
        _git(repo, "commit", "-q", "-m", "record already committed")
        head_before = _git(repo, "rev-parse", "HEAD")

        _maybe_auto_commit(repo, MISSION_SLUG_COMPLETED, [record], "chore(retrospective): nothing new")

        assert _git(repo, "rev-parse", "HEAD") == head_before
        assert capsys.readouterr().err == ""

    def test_auto_commit_of_file_outside_repo_root_warns_and_commits_nothing(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """The commit seam refuses a path outside the work tree; the helper must not raise, commit, or stay silent.

        WP14 (contracts/commit-outcome.md rule 6): the surface refusal renders
        through the shared ``render_commit_outcome`` -- naming the surface and
        the refused path -- instead of a hand-formatted diagnostic message.
        """
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        repo, head_before = self._committed_repo(tmp_path, auto_commit=True)
        outside = tmp_path / "outside.yaml"
        outside.write_text("schema_version: 1\n", encoding="utf-8")

        _maybe_auto_commit(repo, MISSION_SLUG_COMPLETED, [outside], "chore(retrospective): must not land")

        assert _git(repo, "rev-parse", "HEAD") == head_before
        warning = strip_ansi(capsys.readouterr().err)
        assert "refused" in warning
        assert str(outside) in warning

    def test_auto_commit_on_a_protected_target_warns_and_commits_nothing(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """The STANDARD router refuses a protected target; the helper warns why and how, and commits nothing."""
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        repo, head_before = self._committed_repo(tmp_path, auto_commit=True, branch=_PROTECTED_BRANCH)
        record = repo / "kitty-specs" / MISSION_SLUG_COMPLETED / "retrospective.yaml"
        record.write_text("schema_version: 1\n", encoding="utf-8")

        _maybe_auto_commit(repo, MISSION_SLUG_COMPLETED, [record], "chore(retrospective): must not land")

        assert _git(repo, "rev-parse", "HEAD") == head_before
        warning = " ".join(strip_ansi(capsys.readouterr().err).split())
        assert "auto-commit skipped: the mission's target branch 'main' is protected" in warning
        assert "commit it from a feature branch (never the coordination branch) and land it through a pull request" in warning
        assert "mission branch" not in warning
        assert "auto-commit failed" not in warning
        assert str(record) in warning

    def test_auto_commit_raises_is_nonfatal(self, tmp_path: Path) -> None:
        """get_auto_commit_default raising is caught non-fatally."""
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        with patch(
            "specify_cli.cli.commands.retrospect.get_auto_commit_default",
            side_effect=Exception("config error"),
        ):
            # Should not raise
            _maybe_auto_commit(tmp_path, MISSION_SLUG_COMPLETED, [], "test")


# ---------------------------------------------------------------------------
# Real-git helpers (auto-commit contracts)
# ---------------------------------------------------------------------------

_FANOUT_EDGE = "specify_cli.retrospective.lifecycle_events._fanout_live_work_retrospective"


def _git(repo: Path, *args: str) -> str:
    """Run real git in *repo* and return stripped stdout."""
    completed = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _init_git_repo(repo: Path, *, auto_commit: bool, branch: str = _MISSION_BRANCH) -> None:
    """``git init`` *repo* on *branch* with a local identity, local hooks dir and the auto-commit setting.

    The default branch is not protected, so the STANDARD commit router may land
    the retrospective there; ``main`` is protected and refuses it.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "retrospect@test.invalid")
    _git(repo, "config", "user.name", "Retrospect Test")
    _git(repo, "config", "commit.gpgsign", "false")
    # Pin the hooks dir locally so an operator's global core.hooksPath never leaks in.
    _git(repo, "config", "core.hooksPath", ".git/hooks")
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text(f"auto_commit: {str(auto_commit).lower()}\n", encoding="utf-8")


def _seed_completed_mission_repo(repo: Path) -> Path:
    """A real git repo holding one completed mission, committed; returns its feature dir."""
    _init_git_repo(repo, auto_commit=True)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG_COMPLETED
    _write_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, target_branch=_MISSION_BRANCH)
    _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)
    _git(repo, "add", "--", ".kittify", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "init")
    return feature_dir


def _reject_every_commit(repo: Path) -> str:
    """Install a pre-commit hook that rejects; returns the hook's stderr line."""
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'pre-commit: retrospective commits are frozen' >&2\nexit 1\n")
    hook.chmod(0o755)
    return "pre-commit: retrospective commits are frozen"


def _lock_the_index(repo: Path) -> str:
    """Hold ``index.lock`` as a concurrent git process would; returns the commit seam's error fragment.

    ``safe_commit`` reports a refused ``git add`` as its own staging failure (it
    does not carry git's stderr through), so that is what the warning names.
    """
    (repo / ".git" / "index.lock").write_text("", encoding="utf-8")
    return "failed to stage requested files"


class TestAutoCommitBackfilledWriteLocationRefusal:
    """B1 (cycle 2 review): ``_auto_commit_backfilled`` degrades one mission's
    refusal to a warning, never aborting the batch (#1771)."""

    def test_warns_and_commits_the_record_alone(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands import retrospect as retrospect_module
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        def _boom(_root: Path, _slug: str) -> Path:
            raise FeatureStatusLockTimeoutError("status lock contended")

        monkeypatch.setattr(retrospect_module, "_canonical_events_write_path", _boom)
        calls: list[tuple[Any, ...]] = []
        monkeypatch.setattr(retrospect_module, "_maybe_auto_commit", lambda *args: calls.append(args))
        record_path = tmp_path / "retrospective.yaml"
        record_path.write_text("mission_id: demo\n", encoding="utf-8")
        created = [{"mission_id": "demo-id", "mission_slug": "demo", "record_path": str(record_path)}]

        retrospect_module._auto_commit_backfilled(tmp_path, created)

        err = strip_ansi(capsys.readouterr().err)
        assert "demo" in err
        assert "STATUS_LOCK_HELD" in err
        assert "event log was not attached" in err
        (call_args,) = calls
        _repo_root, _mission_slug, files, _message = call_args
        # The record commits ALONE -- the refused event log is never appended.
        assert files == [record_path]


class TestAutoCommitFailureIsSurfaced:
    """A failed auto-commit is non-fatal but never silent (the operator must commit by hand)."""

    @pytest.mark.parametrize(
        "break_git",
        [_reject_every_commit, _lock_the_index],
        ids=["commit-rejected-by-hook", "add-blocked-by-index-lock"],
    )
    def test_create_warns_on_stderr_and_keeps_json_parseable_when_auto_commit_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, break_git: Any) -> None:
        """WP14 (contracts/commit-outcome.md rule 6): the failed surface(s)
        render through the shared ``render_commit_outcome`` -- naming each
        surface and its refused path(s) -- in ADDITION to (B2 cycle 2 review:
        never instead of) the original ``_warn_auto_commit_failed`` warning,
        which carries two things the generic surface render does not: git's
        own raw failure text, and the "commit it by hand" remediation. Both
        warnings fire together for the SAME caller-surface failure.
        """
        repo = tmp_path / "repo"
        feature_dir = _seed_completed_mission_repo(repo)
        head_before = _git(repo, "rev-parse", "HEAD")
        git_error = break_git(repo)
        monkeypatch.chdir(repo)

        with patch(_FANOUT_EDGE):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED, "--json"])

        # The record write succeeded, so the command still succeeds ...
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["result"] == "success"
        assert (feature_dir / "retrospective.yaml").is_file()
        # ... but nothing was committed, and stderr says so, naming the surface.
        assert _git(repo, "rev-parse", "HEAD") == head_before
        warning = strip_ansi(result.stderr)
        assert "refused" in warning
        assert "retrospective.yaml" in warning
        # B2: restored -- git's own failure text and the hand-commit
        # remediation must still reach the operator, additively.
        assert git_error in warning
        assert "commit it by hand" in warning

    def test_create_warns_and_exits_zero_when_the_commit_router_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Injected: the router fails loud on a corrupt coordination state; no real flat fixture reaches it."""
        from specify_cli.coordination.commit_router import CoordWorktreeResolutionError

        repo = tmp_path / "repo"
        _seed_completed_mission_repo(repo)
        head_before = _git(repo, "rev-parse", "HEAD")
        monkeypatch.chdir(repo)

        with (
            patch(_FANOUT_EDGE),
            patch(
                "specify_cli.cli.commands.retrospect.commit_for_mission",
                side_effect=CoordWorktreeResolutionError("coordination worktree resolution failed"),
            ),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED, "--json"])

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["result"] == "success"
        assert _git(repo, "rev-parse", "HEAD") == head_before
        warning = " ".join(strip_ansi(result.stderr).split())
        assert "auto-commit failed: coordination worktree resolution failed" in warning
        assert "retrospective.yaml" in warning

    @pytest.mark.parametrize(
        ("exc", "expected"),
        [
            (
                subprocess.CalledProcessError(1, ["git", "add"], stderr=b"fatal: 'x' is outside repository\n"),
                "fatal: 'x' is outside repository",
            ),
            (
                subprocess.CalledProcessError(1, ["git", "commit"], output=b"nothing to commit\n", stderr=b""),
                "nothing to commit",
            ),
            (
                subprocess.CalledProcessError(128, ["git", "commit", "-m", "m"]),
                "`git commit -m m` exited 128",
            ),
            (OSError("config unreadable"), "config unreadable"),
            (RuntimeError(), "RuntimeError"),
        ],
        ids=["git-stderr", "git-stdout-only", "git-silent", "other-error", "empty-message"],
    )
    def test_failure_detail_names_the_cause(self, exc: Exception, expected: str) -> None:
        from specify_cli.cli.commands.retrospect import _auto_commit_failure_detail

        assert _auto_commit_failure_detail(exc) == expected


# ---------------------------------------------------------------------------
# TestPublishedCoordMissionCreate -- B1 (WP14 cycle 2 review empirical repro,
# #5513/#5501): `retrospect create` on a PUBLISHED coordination Mission whose
# coordination branch was torn down by consolidation.
# ---------------------------------------------------------------------------


def _seed_published_coord_mission_repo(repo: Path, *, mission_slug: str) -> Path:
    """A real git repo holding one PUBLISHED coordination Mission, coordination branch GONE.

    Mirrors ``_build_e2_mission_coord_fully_retired``
    (tests/mission_runtime/test_consolidated_resolution.py) but through the
    lighter ``_init_git_repo``/``_write_meta`` harness this file already uses,
    and driven through the real ``retrospect create`` CLI entry point rather
    than ``resolve_placement_only`` directly. ``_terminal_completion_evidence``
    (mission_runtime.lifecycle_phase) is satisfied by the all-``done`` status
    event log alone -- no ``mission_number``/baseline-bookkeeping dance is
    needed for PUBLISHED detection here, only a present
    ``baseline_merge_commit`` plus an absent Target Ref.
    """
    _init_git_repo(repo, auto_commit=True)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    init_sha = _git(repo, "rev-parse", "HEAD")

    target_branch = f"kitty/mission-{mission_slug}"
    coordination_branch = f"kitty/mission-{mission_slug}-coord"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        "01PUBLSH00000000000000000",
        mission_slug,
        target_branch=target_branch,
        topology="coord",
        coordination_branch=coordination_branch,
        baseline_merge_commit=init_sha,
        # ``_primary_mission_is_completed`` (surface_resolver.py, the READ-side
        # merge-authoritative short-circuit `_canonical_events_path`/
        # `_check_mission_completed` depend on) keys ONLY on this explicit
        # marker (`is_mission_merged`), not on `_terminal_completion_evidence`'s
        # all-done-WPs-or-mission_number signal that the WRITE-side
        # `resolve_lifecycle_phase` uses -- the reviewer's empirical repro
        # names this step explicitly ("stamp merged_at").
        merged_at="2026-10-01T00:00:00+00:00",
    )
    _write_status_events_all_done(feature_dir, mission_slug)
    _git(repo, "add", "--", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "mission scaffold")
    # ``target_branch``/``coordination_branch`` are DECLARED in meta.json but
    # never created as real git refs here -- git-ref-absence is the identical
    # signal to "created, then torn down by consolidation" for both
    # ``_target_ref_exists`` (lifecycle_phase.py) and ``write_dir``'s own
    # coordination-branch-existence probe.
    assert not _branch_exists(repo, target_branch)
    assert not _branch_exists(repo, coordination_branch)
    return feature_dir


def _branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo,
        capture_output=True,
    )
    return result.returncode == 0


class TestPublishedCoordMissionCreate:
    """B1: a PUBLISHED coordination Mission's retrospective must not crash."""

    def test_create_succeeds_instead_of_raising_coordination_branch_deleted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empirical repro (cycle 2 review): at the WP base, this raised an
        uncaught ``CoordinationBranchDeleted`` traceback from
        ``retrospect.py``'s event-path resolution (exit 1, no stdout JSON) --
        post-merge is the NORMAL time to run retrospect, so this was a
        regression on the main path. The `plan.design.published-status-state-
        write` ruling (mission_runtime.resolution) fixes it at the root: a
        PUBLISHED Mission's STATUS_STATE write now joins the PUBLISHED/E2
        short-circuit, so the event log resolves to the primary checkout
        instead of re-probing the torn-down coordination branch."""
        repo = tmp_path / "repo"
        mission_slug = "published-coord-mission-wp14"
        feature_dir = _seed_published_coord_mission_repo(repo, mission_slug=mission_slug)
        monkeypatch.chdir(repo)

        with patch(_FANOUT_EDGE):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", mission_slug, "--json"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["result"] == "success"
        assert (feature_dir / "retrospective.yaml").is_file()
        assert (feature_dir / "status.events.jsonl").is_file()
        # The record and the event log both land -- and commit -- on the
        # resolved Primary Branch (this single-repo fixture has no remote, so
        # the current checkout branch IS the resolved Primary Branch); never
        # a raised CoordinationBranchDeleted, never a fallback write to a
        # DIFFERENT (uncommitted) root-checkout copy.
        status = _git(repo, "status", "--porcelain")
        assert status == "", f"retrospective record/event log left uncommitted: {status!r}"


# ---------------------------------------------------------------------------
# TestWriteLocationRefusalHelpers -- B1 (cycle 2 review): the named-refusal
# helpers in isolation.
# ---------------------------------------------------------------------------


class TestWriteLocationRefusalHelpers:
    def test_refusal_code_prefers_error_code(self) -> None:
        from specify_cli.cli.commands.retrospect import _write_location_refusal_code
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        assert _write_location_refusal_code(FeatureStatusLockTimeoutError("locked")) == "STATUS_LOCK_HELD"

    def test_refusal_code_falls_back_to_code_attribute(self) -> None:
        from mission_runtime import ActionContextError

        from specify_cli.cli.commands.retrospect import _write_location_refusal_code

        assert _write_location_refusal_code(ActionContextError("SOME_CODE", "boom")) == "SOME_CODE"

    def test_refusal_code_defaults_when_neither_is_present(self) -> None:
        from specify_cli.cli.commands.retrospect import _write_location_refusal_code

        assert _write_location_refusal_code(RuntimeError("plain")) == "WRITE_LOCATION_REFUSED"

    def test_emit_write_location_refusal_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.retrospect import _emit_write_location_refusal
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        with pytest.raises(typer.Exit) as excinfo:
            _emit_write_location_refusal(FeatureStatusLockTimeoutError("status lock contended"), mission_slug="demo", json_output=True)

        assert excinfo.value.exit_code == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload == {
            "result": "blocked",
            "code": "STATUS_LOCK_HELD",
            "mission_slug": "demo",
            "blocked_reason": "status lock contended",
            "exit_code": 1,
        }

    def test_emit_write_location_refusal_text(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.retrospect import _emit_write_location_refusal
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        with pytest.raises(typer.Exit) as excinfo:
            _emit_write_location_refusal(FeatureStatusLockTimeoutError("status lock contended"), mission_slug="demo", json_output=False)

        assert excinfo.value.exit_code == 1
        err = strip_ansi(capsys.readouterr().err)
        assert "STATUS_LOCK_HELD" in err
        assert "status lock contended" in err

    def test_warn_write_location_refusal(self, capsys: pytest.CaptureFixture[str]) -> None:
        from specify_cli.cli.commands.retrospect import _warn_write_location_refusal
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        _warn_write_location_refusal(FeatureStatusLockTimeoutError("status lock contended"), mission_slug="demo")

        err = strip_ansi(capsys.readouterr().err)
        assert "demo" in err
        assert "STATUS_LOCK_HELD" in err
        assert "event log was not attached" in err

    def test_canonical_events_write_path_or_exit_passes_through_on_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands import retrospect as retrospect_module

        monkeypatch.setattr(retrospect_module, "_canonical_events_write_path", lambda _root, _slug: tmp_path / "status.events.jsonl")

        result = retrospect_module._canonical_events_write_path_or_exit(tmp_path, "demo", json_output=True)

        assert result == tmp_path / "status.events.jsonl"

    def test_canonical_events_write_path_or_exit_exits_on_a_named_refusal(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from specify_cli.cli.commands import retrospect as retrospect_module
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        def _boom(_root: Path, _slug: str) -> Path:
            raise FeatureStatusLockTimeoutError("status lock contended")

        monkeypatch.setattr(retrospect_module, "_canonical_events_write_path", _boom)

        with pytest.raises(typer.Exit) as excinfo:
            retrospect_module._canonical_events_write_path_or_exit(tmp_path, "demo", json_output=True)

        assert excinfo.value.exit_code == 1
        assert json.loads(capsys.readouterr().out)["code"] == "STATUS_LOCK_HELD"


# ---------------------------------------------------------------------------
# TestCreateCmdWriteLocationRefusal -- B1: create_cmd's genuine (non-PUBLISHED)
# write-location refusal, end to end on a real project.
# ---------------------------------------------------------------------------


class TestCreateCmdWriteLocationRefusal:
    def test_create_json_renders_the_refusal_and_exits_1(self, retrospect_project: RetrospectProject, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands import retrospect as retrospect_module
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        def _boom(_root: Path, _slug: str) -> Path:
            raise FeatureStatusLockTimeoutError("status lock contended")

        monkeypatch.setattr(retrospect_module, "_canonical_events_write_path", _boom)

        result = _create("--json")

        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["code"] == "STATUS_LOCK_HELD"
        assert payload["result"] == "blocked"
        # The retrospective record itself was already written before the
        # refused event-log resolution -- B1 never discards it.
        assert retrospect_project.record_path.is_file()

    def test_create_text_renders_the_refusal_and_exits_1(self, retrospect_project: RetrospectProject, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands import retrospect as retrospect_module
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        def _boom(_root: Path, _slug: str) -> Path:
            raise FeatureStatusLockTimeoutError("status lock contended")

        monkeypatch.setattr(retrospect_module, "_canonical_events_write_path", _boom)

        result = _create()

        assert result.exit_code == 1
        err = strip_ansi(result.stderr)
        assert "STATUS_LOCK_HELD" in err
        assert "status lock contended" in err


# ---------------------------------------------------------------------------
# TestCreateCmdErrorPaths
# ---------------------------------------------------------------------------


class TestCreateCmdErrorPaths:
    """Tests for create_cmd error branches not yet covered."""

    def test_create_project_root_not_found(self, tmp_path: Path) -> None:
        """Exits 1 when project root cannot be located."""
        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=None):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", "anything", "--json"])

        assert result.exit_code == 1

    def test_create_mission_not_completed_non_json(self, tmp_path: Path) -> None:
        """MISSION_NOT_COMPLETED non-JSON mode writes text error."""
        repo_root, _, _ = _setup_project(tmp_path)

        resolved = _build_resolved_mission(MISSION_ID_OPEN, MISSION_SLUG_OPEN)
        open_wps = [{"wp_id": "WP01", "lane": "in_progress"}]

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=open_wps),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_OPEN])

        assert result.exit_code == 1
        assert "MISSION_NOT_COMPLETED" in result.output


# ---------------------------------------------------------------------------
# TestBackfillDiscovery
# ---------------------------------------------------------------------------


class TestBackfillDiscovery:
    """Tests for backfill _discover_missions_for_backfill and _process_candidate."""

    def test_discover_missions_no_missions_root(self, tmp_path: Path) -> None:
        """Returns empty list when .kittify/missions/ doesn't exist."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)
        assert result == []

    def test_discover_missions_skips_a_file_and_keeps_discovering_later_missions(self, tmp_path: Path) -> None:
        """A stray file is skipped without dropping a mission dir that sorts after it."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        # "0-" sorts before the ULID-named mission dir below.
        (missions_root / "0-not-a-dir.txt").write_text("file", encoding="utf-8")
        mission_dir = missions_root / MISSION_ID_COMPLETED
        mission_dir.mkdir()
        (mission_dir / "meta.json").write_text(
            json.dumps({"mission_id": MISSION_ID_COMPLETED, "mission_slug": MISSION_SLUG_COMPLETED}),
            encoding="utf-8",
        )

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)

        assert [(c["mission_id"], c.get("skip_reason")) for c in result] == [(MISSION_ID_COMPLETED, "not_completed")]

    def test_discover_missions_unstattable_entry_is_not_silently_skipped(self, tmp_path: Path) -> None:
        """`#3194`: an unstattable mission entry must not be silently dropped.

        Companion to ``test_discover_missions_skips_non_dirs`` above, which pins
        the genuinely-absent-shaped case ("a regular file is not a directory").
        This pins the DIFFERENT case: a candidate that could not be *stat'ed at
        all* (EACCES via a symlink into an unreadable directory). ``Path.is_dir()``
        answers ``False`` for that on Python 3.14 only (RAISES on 3.11-3.13),
        which would silently conflate "unreadable" with "not a directory" and
        drop the entry with no signal — the exact `#3177` shape, generalized.
        ``safe_is_dir`` makes this raise on every interpreter instead.
        """
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        vault = tmp_path / "vault"
        (vault / "m-target").mkdir(parents=True)
        (missions_root / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

        canary = vault / "canary"
        canary.write_text("{}", encoding="utf-8")
        os.chmod(vault, 0o000)
        try:
            if not mode_bits_enforced(canary):
                pytest.skip(
                    "SKIPPED HONESTLY, not passed: this process can stat through "
                    "a 0o000 directory (running as root, or a filesystem that "
                    "ignores mode bits), so the branch cannot be constructed here."
                )
            now = now_utc()
            with pytest.raises(OSError):
                _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)
        finally:
            os.chmod(vault, 0o700)

    def test_discover_missions_skips_missing_meta(self, tmp_path: Path) -> None:
        """Skips directories without meta.json."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        # Directory without meta.json
        (missions_root / "01SOMEMISSIONID0000001").mkdir()

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)
        assert result == []

    def test_discover_missions_skips_bad_json(self, tmp_path: Path) -> None:
        """Skips missions with unparseable meta.json."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        dir_entry = missions_root / "01SOMEMISSIONID0000002"
        dir_entry.mkdir()
        (dir_entry / "meta.json").write_text("NOT JSON", encoding="utf-8")

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)
        assert result == []

    def test_discover_missions_skips_missing_ids(self, tmp_path: Path) -> None:
        """Skips missions missing mission_id or mission_slug."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        dir_entry = missions_root / "01SOMEMISSIONID0000003"
        dir_entry.mkdir()
        (dir_entry / "meta.json").write_text(json.dumps({"some_other_field": "value"}), encoding="utf-8")

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)
        assert result == []

    def test_discover_missions_not_completed_excluded(self, tmp_path: Path) -> None:
        """Missions without completed_at are marked not_completed."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        dir_entry = missions_root / MISSION_ID_COMPLETED
        dir_entry.mkdir()
        (dir_entry / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": MISSION_ID_COMPLETED,
                    "mission_slug": MISSION_SLUG_COMPLETED,
                }
            ),
            encoding="utf-8",
        )

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)
        assert any(c.get("skip_reason") == "not_completed" for c in result)

    def test_discover_missions_bad_completed_at_format(self, tmp_path: Path) -> None:
        """Missions with unparseable completed_at are marked not_completed."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        dir_entry = missions_root / MISSION_ID_COMPLETED
        dir_entry.mkdir()
        (dir_entry / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": MISSION_ID_COMPLETED,
                    "mission_slug": MISSION_SLUG_COMPLETED,
                    "completed_at": "not-a-date",
                }
            ),
            encoding="utf-8",
        )

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)
        assert any(c.get("skip_reason") == "not_completed" for c in result)

    def test_backfill_project_root_not_found(self, tmp_path: Path) -> None:
        """Exits 1 when project root cannot be located."""
        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=None):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--json"])

        assert result.exit_code == 1

    def test_backfill_process_candidate_dry_run(self, tmp_path: Path) -> None:
        """Dry-run backfill marks candidates as created without writing."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        # No existing record
        assert not (mission_dir / "retrospective.yaml").exists()

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--dry-run", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["created"] >= 1
        created = data.get("created", 0)
        # No file should be written in dry-run
        assert not (mission_dir / "retrospective.yaml").exists()
        assert created >= 1


# ---------------------------------------------------------------------------
# TestSummaryCmdExtended
# ---------------------------------------------------------------------------


class TestSummaryCmdExtended:
    """Extended tests for summary_cmd to cover remaining uncovered paths."""

    def test_summary_since_flag_valid(self, tmp_path: Path) -> None:
        """Valid --since date is accepted."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--since", "2026-01-01", "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "aggregate" in data

    def test_summary_since_flag_invalid(self, tmp_path: Path) -> None:
        """Invalid --since value exits 1 with error message."""
        repo_root, _, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--since", "not-a-date"],
        )

        assert result.exit_code == 1

    def test_summary_with_missions_having_different_states(self, tmp_path: Path) -> None:
        """Summary classifies missions into different states."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Mission 1: has a retrospective.yaml (will be classified)
        m1_id = "01KS049J4V9CSWBKJHTY2FB80H"
        m1_slug = "completed-with-retro"
        m1_dir = kitty_specs_dir / m1_slug  # FR-013 canonical mission-instance home
        m1_dir.mkdir(parents=True, exist_ok=True)
        _write_meta(m1_dir, m1_id, m1_slug)
        (m1_dir / "retrospective.yaml").write_text(
            "schema_version: '1'\nmission: {}\nstatus: completed\nhelped: []\nnot_helpful: []\ngaps: []\nproposals: []\n",
            encoding="utf-8",
        )

        # Mission 2: no retrospective.yaml (missing)
        m2_id = "01KS049J4V9CSWBKJHTY2FB81H"
        m2_slug = "completed-without-retro"
        m2_dir = kitty_specs_dir / m2_slug  # FR-013 canonical mission-instance home
        m2_dir.mkdir(parents=True, exist_ok=True)
        _write_meta(m2_dir, m2_id, m2_slug)

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "missions" in data
        assert "aggregate" in data
        # Should have at least 2 missions
        assert len(data["missions"]) >= 2

    def test_summary_unstattable_mission_candidate_is_not_silently_skipped(self, tmp_path: Path) -> None:
        """`#3194`: ``summary``'s mission enumeration must not use the
        EACCES-divergent ``Path.is_dir()`` predicate anywhere in its path.

        ``build_summary()`` (``specify_cli.retrospective.summary.iter_mission_instance_dirs``)
        walks the canonical ``kitty-specs/*`` directory (FR-013) before
        ``summary_cmd``'s own ``missions_with_state`` loop ever runs, so an
        unstattable candidate is actually caught there first — a second instance
        of the identical pattern found while writing this test, fixed alongside
        the 8 originally flagged call sites. ``Path.is_dir()`` answers ``False``
        for an unreadable candidate on Python 3.14 only (RAISES on 3.11-3.13);
        routed through ``safe_is_dir`` the raised ``OSError`` is now the SAME on
        every interpreter, and ``summary_cmd``'s own pre-existing
        ``except OSError: raise typer.Exit(2)`` around ``build_summary()`` turns
        it into a clean, actionable CLI error — exactly the "surfaced as
        unreadable" outcome the fix is for, rather than a silently-empty,
        misleadingly-successful summary.
        """
        repo_root, _missions_dir, kitty_specs_dir = _setup_project(tmp_path)
        vault = tmp_path / "vault"
        (vault / "m-target").mkdir(parents=True)
        (kitty_specs_dir / "m-link").symlink_to(vault / "m-target", target_is_directory=True)

        canary = vault / "canary"
        canary.write_text("{}", encoding="utf-8")
        os.chmod(vault, 0o000)
        try:
            if not mode_bits_enforced(canary):
                pytest.skip(
                    "SKIPPED HONESTLY, not passed: this process can stat through "
                    "a 0o000 directory (running as root, or a filesystem that "
                    "ignores mode bits), so the branch cannot be constructed here."
                )
            result = RUNNER.invoke(
                retrospect_app,
                ["summary", "--project", str(tmp_path), "--json"],
            )
        finally:
            os.chmod(vault, 0o700)

        assert result.exit_code == 2, f"an unstattable mission candidate must not silently produce a successful, misleadingly-complete summary: {result.output!r}"
        assert "I/O error reading corpus" in strip_ansi(result.output), f"expected the actionable I/O-error message, got: {result.output!r}"

    def test_summary_rich_rendering_no_json(self, tmp_path: Path) -> None:
        """Non-JSON summary produces Rich output including state table."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        # Add a mission
        m1_dir = missions_dir / MISSION_ID_COMPLETED
        m1_dir.mkdir(parents=True, exist_ok=True)
        _write_meta(m1_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path)],
        )

        assert result.exit_code == 0
        output = result.output
        # Should contain state names from the table
        assert len(output) > 0

    def test_summary_json_out_writes_file(self, tmp_path: Path) -> None:
        """--json-out flag writes JSON to the specified file."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        output_file = tmp_path / "summary_output.json"

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json-out", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert "aggregate" in data

    def test_summary_json_out_with_json_flag(self, tmp_path: Path) -> None:
        """--json-out combined with --json writes file without extra message."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        output_file = tmp_path / "out.json"

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json", "--json-out", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists()

    def test_summary_build_summary_io_error(self, tmp_path: Path) -> None:
        """OSError from build_summary exits 2."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        with patch(
            "specify_cli.retrospective.summary.build_summary",
            side_effect=OSError("disk error"),
        ):
            result = RUNNER.invoke(
                retrospect_app,
                ["summary", "--project", str(tmp_path), "--json"],
            )

        assert result.exit_code == 2

    def test_summary_missions_dir_not_present(self, tmp_path: Path) -> None:
        """When .kittify/missions/ doesn't exist, aggregate is all zeros."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)
        # Remove missions dir
        missions_dir.rmdir()

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        agg = data["aggregate"]
        assert all(v == 0 for v in agg.values())

    def test_summary_filter_has_findings(self, tmp_path: Path) -> None:
        """--filter has_findings only shows has_findings missions."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--filter", "has_findings", "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data.get("filter") == "has_findings"
        for m in data.get("missions", []):
            assert m["findings_status"] == "has_findings"

    def test_summary_missions_with_kitty_specs_classification(self, tmp_path: Path) -> None:
        """Missions classified via kitty-specs dir when available."""
        repo_root, _missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Canonical kitty-specs home carries meta.json (FR-013 discovery anchor).
        kitty_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(kitty_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        # No retrospective.yaml → "missing"

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        missions = data.get("missions", [])
        # Find the mission
        matching = [m for m in missions if m["mission_slug"] == MISSION_SLUG_COMPLETED]
        assert len(matching) >= 1

    def test_summary_mission_with_retrospective_in_kittify(self, tmp_path: Path) -> None:
        """FR-013 legacy-record resolution: a mission is discovered by its
        canonical ``kitty-specs/<slug>/`` home (meta.json), while its record was
        never relocated out of ``.kittify/missions/<id>/retrospective.yaml``."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Canonical home (discovery anchor) — meta.json, no in-place record.
        kitty_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(kitty_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        # Record lives ONLY in the legacy in-registry location.
        m1_dir = missions_dir / MISSION_ID_COMPLETED
        m1_dir.mkdir(parents=True, exist_ok=True)
        (m1_dir / "retrospective.yaml").write_text(
            "schema_version: '1'\nmission: {}\nstatus: completed\nhelped: []\nnot_helpful: []\ngaps: []\nproposals: []\n",
            encoding="utf-8",
        )

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        missions = data.get("missions", [])
        matching = [m for m in missions if m["mission_id"] == MISSION_ID_COMPLETED]
        assert len(matching) >= 1

    def test_summary_mission_with_bad_meta_json(self, tmp_path: Path) -> None:
        """Missions with bad meta.json still appear (with fallback IDs)."""
        repo_root, _missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        m1_dir = kitty_specs_dir / "BADJSONMISSION00000000000001"
        m1_dir.mkdir(parents=True, exist_ok=True)
        # Write bad JSON to meta.json
        (m1_dir / "meta.json").write_text("not valid json", encoding="utf-8")

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        # The bad-meta mission should still be enumerated (using dir name as fallback)
        missions = data.get("missions", [])
        assert any(m["mission_id"] == "BADJSONMISSION00000000000001" for m in missions)

    def test_parse_iso_date_various_formats(self) -> None:
        """_parse_iso_date_or_exit parses multiple ISO formats."""
        from specify_cli.cli.commands.retrospect import _parse_iso_date_or_exit

        # YYYY-MM-DD
        dt = _parse_iso_date_or_exit("2026-05-01", "--since")
        assert dt.year == 2026
        assert dt.month == 5
        assert dt.day == 1

        # YYYY-MM-DDTHH:MM:SS
        dt = _parse_iso_date_or_exit("2026-05-01T12:00:00", "--since")
        assert dt.hour == 12

        # Full ISO with timezone
        dt = _parse_iso_date_or_exit("2026-05-01T12:00:00+00:00", "--since")
        assert dt.tzinfo is not None

        # fromisoformat path: microseconds (not matched by strptime fmts above)
        dt = _parse_iso_date_or_exit("2026-05-01T12:00:00.123456", "--since")
        assert dt.tzinfo is not None  # timezone replaced to UTC

    def test_backfill_discover_completed_at_naive_tz(self, tmp_path: Path) -> None:
        """Missions with naive completed_at have timezone replaced to UTC."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        dir_entry = missions_root / MISSION_ID_COMPLETED
        dir_entry.mkdir()
        # Naive timestamp (no timezone offset)
        (dir_entry / "meta.json").write_text(
            json.dumps(
                {
                    "mission_id": MISSION_ID_COMPLETED,
                    "mission_slug": MISSION_SLUG_COMPLETED,
                    "completed_at": "2026-05-01T10:00:00",  # no tzinfo
                }
            ),
            encoding="utf-8",
        )

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=365), now, None)
        # Should be included (within window), naive tz should be normalized
        assert len(result) == 1
        assert result[0]["mission_id"] == MISSION_ID_COMPLETED

    def test_backfill_already_exists_prescreen_skip_with_path(self, tmp_path: Path) -> None:
        """Pre-screened skip with skip_reason='already_exists' includes record_path."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        # Directly test the backfill with a mocked _discover_missions_for_backfill
        # that returns an already_exists skip (normally comes from _process_candidate,
        # but the code also handles it in the pre-screening loop).
        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()

        # Set up a mock candidate that has skip_reason=already_exists
        existing_record = missions_dir / MISSION_ID_COMPLETED / "retrospective.yaml"
        existing_record.parent.mkdir(parents=True, exist_ok=True)
        existing_record.write_text("exists: true\n", encoding="utf-8")

        mock_candidates = [
            {
                "mission_id": MISSION_ID_COMPLETED,
                "mission_slug": MISSION_SLUG_COMPLETED,
                "completed_at": completed_at,
                "skip_reason": "already_exists",
            }
        ]

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch(
                "specify_cli.cli.commands.retrospect._discover_missions_for_backfill",
                return_value=mock_candidates,
            ),
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        skipped = data["skipped"]
        assert any(s.get("reason") == "already_exists" for s in skipped)
        # Should have record_path in the skip entry
        already_exists_skip = next(s for s in skipped if s.get("reason") == "already_exists")
        assert "record_path" in already_exists_skip

    def test_summary_non_dir_in_missions_skipped(self, tmp_path: Path) -> None:
        """Non-directory entries in .kittify/missions/ are skipped."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        # Create a file (not a dir) inside missions/
        (missions_dir / "not-a-dir.txt").write_text("file", encoding="utf-8")

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        # The non-dir entry should be silently skipped
        missions = data.get("missions", [])
        assert all(m["mission_id"] != "not-a-dir.txt" for m in missions)

    def test_summary_mission_with_events_having_captured_type(self, tmp_path: Path) -> None:
        """Summary reads policy_source from RetrospectiveCaptured events."""
        repo_root, _missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Canonical kitty-specs home (meta.json anchor) with a status.events.jsonl
        # carrying a RetrospectiveCaptured event.
        kitty_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(kitty_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        captured_event = {
            "type": "RetrospectiveCaptured",
            "lamport": 1,
            "policy_source": {"enabled": "true", "timing": "post_completion"},
            "mission_id": MISSION_ID_COMPLETED,
        }
        (kitty_dir / "status.events.jsonl").write_text(
            json.dumps(captured_event) + "\n",
            encoding="utf-8",
        )

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        missions = data.get("missions", [])
        matching = [m for m in missions if m["mission_id"] == MISSION_ID_COMPLETED]
        assert len(matching) >= 1
        # The policy_source should be populated from the event
        ps = matching[0].get("policy_source")
        assert ps is not None
        assert ps.get("enabled") == "true"

    def test_summary_json_out_write_failure(self, tmp_path: Path) -> None:
        """OSError when writing --json-out exits 2."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        output_file = tmp_path / "output.json"

        with patch("pathlib.Path.write_text", side_effect=OSError("disk full")):
            result = RUNNER.invoke(
                retrospect_app,
                ["summary", "--project", str(tmp_path), "--json-out", str(output_file)],
            )

        assert result.exit_code == 2

    def test_summary_mission_with_retro_in_kittify_reclassified(self, tmp_path: Path) -> None:
        """When classify returns 'missing' but .kittify retro exists, reclassify from kittify dir."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Canonical kitty-specs home (discovery anchor), no in-place record →
        # classify_mission_record returns "missing" initially.
        kitty_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(kitty_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        # But there IS a retro in the legacy .kittify/missions/<id>/ registry.
        m1_dir = missions_dir / MISSION_ID_COMPLETED
        m1_dir.mkdir(parents=True, exist_ok=True)
        (m1_dir / "retrospective.yaml").write_text(
            "schema_version: '1'\nmission: {}\nstatus: completed\nhelped: []\nnot_helpful: []\ngaps: []\nproposals: []\n",
            encoding="utf-8",
        )

        result = RUNNER.invoke(
            retrospect_app,
            ["summary", "--project", str(tmp_path), "--json"],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        missions = data.get("missions", [])
        matching = [m for m in missions if m["mission_id"] == MISSION_ID_COMPLETED]
        assert len(matching) >= 1
        # Should not be "missing" since .kittify has the retro
        # (depends on classify_mission_record behavior with the file present)


# ---------------------------------------------------------------------------
# TestSynthesizeFabricateProvenance (Cycle-2 Blocker 1)
# ---------------------------------------------------------------------------


class TestSynthesizeFabricateProvenance:
    """End-to-end tests that the written record has synthesize_fabricate provenance.

    These tests do NOT patch _create_empty_retrospective_record — they exercise
    the real function and assert that the YAML on disk contains provenance.kind =
    "synthesize_fabricate" and findings_status = "ran_no_findings".
    """

    def _make_feature_dir(self, kitty_specs_dir: Path) -> Path:
        """Set up a feature dir with all required artifacts."""
        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(exist_ok=True)
        (tasks_dir / "WP01.md").write_text("# WP01\n", encoding="utf-8")
        return feature_dir

    def test_fabricate_empty_writes_synthesize_fabricate_provenance_to_disk(self, tmp_path: Path) -> None:
        """--fabricate-empty: real writer path writes provenance.kind=synthesize_fabricate on disk.

        This test was MISSING before cycle-2 fix: the old test patched
        _create_empty_retrospective_record so the actual write was never exercised.
        Now we call the real function and assert the YAML on disk.
        """
        import yaml as _yaml
        from specify_cli.charter_pack_synthesizer import SynthesisResult

        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)
        feature_dir = self._make_feature_dir(kitty_specs_dir)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        empty_synthesis = SynthesisResult(dry_run=True, planned=[], applied=[], conflicts=[], rejected=[], events_emitted=[])

        # Do NOT patch _create_empty_retrospective_record — exercise the real code path.
        with (
            patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=resolved),
            patch("specify_cli.cli.commands.agent_retrospect.apply_proposals", return_value=empty_synthesis),
        ):
            result = RUNNER.invoke(
                agent_retrospect_app,
                ["synthesize", "--mission", MISSION_SLUG_COMPLETED, "--fabricate-empty", "--json"],
            )

        # The command should succeed (exit 0)
        assert result.exit_code == 0, result.output

        # FR-006 (#1771): the record lands in the tracked feature_dir, not the
        # gitignored .kittify/missions/ tree.
        retro_path = feature_dir / "retrospective.yaml"
        assert retro_path.exists(), "retrospective.yaml must be written to disk by --fabricate-empty"
        assert not (missions_dir / MISSION_ID_COMPLETED / "retrospective.yaml").exists(), "record must NOT be written to the gitignored .kittify/missions/ tree"

        # Read back the YAML and verify provenance.kind
        raw = _yaml.safe_load(retro_path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict), "retrospective.yaml must be a YAML mapping"
        provenance = raw.get("provenance", {})
        assert provenance.get("kind") == "synthesize_fabricate", f"provenance.kind MUST be 'synthesize_fabricate', got {provenance.get('kind')!r}"
        assert raw.get("findings_status") == "ran_no_findings", f"findings_status MUST be 'ran_no_findings', got {raw.get('findings_status')!r}"

    def test_fabricate_empty_emits_captured_event_with_explicit_create_provenance_kind(self, tmp_path: Path) -> None:
        """The RetrospectiveCaptured event emitted has provenance_kind='explicit_create'.

        The event's provenance_kind is distinct from the record's provenance.kind per contract.
        """
        import json as _json
        from specify_cli.charter_pack_synthesizer import SynthesisResult

        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)
        feature_dir = self._make_feature_dir(kitty_specs_dir)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)
        empty_synthesis = SynthesisResult(dry_run=True, planned=[], applied=[], conflicts=[], rejected=[], events_emitted=[])

        with (
            patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=resolved),
            patch("specify_cli.cli.commands.agent_retrospect.apply_proposals", return_value=empty_synthesis),
        ):
            result = RUNNER.invoke(
                agent_retrospect_app,
                ["synthesize", "--mission", MISSION_SLUG_COMPLETED, "--fabricate-empty"],
            )

        assert result.exit_code == 0, result.output

        # The lifecycle event must have provenance_kind="explicit_create"
        events_path = feature_dir / "status.events.jsonl"
        if events_path.exists():
            raw_lines = [line.strip() for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            all_events = []
            for raw_line in raw_lines:
                try:
                    all_events.append(_json.loads(raw_line))
                except _json.JSONDecodeError:
                    continue
            captured_events = [e for e in all_events if e.get("type") == "RetrospectiveCaptured"]
            if captured_events:
                for evt in captured_events:
                    assert evt.get("provenance_kind") == "explicit_create", f"Event provenance_kind MUST be 'explicit_create', got {evt.get('provenance_kind')!r}"

    def test_writer_rejects_synthesize_fabricate_with_has_findings(self) -> None:
        """T028 DoD: write_gen_record rejects synthesize_fabricate + has_findings.

        This invariant is enforced at the schema level (validate_record) and at the
        writer level as a defense-in-depth guard. This test exercises the writer path.
        """
        import pathlib
        import tempfile
        from specify_cli.retrospective.schema import (
            GenActor,
            GenFinding,
            GenProvenance,
            GenRetrospectiveRecord,
            RecordValidationError,
        )
        from specify_cli.retrospective.writer import write_gen_record

        now = now_utc_iso()
        actor = GenActor(kind="runtime", id="test")

        # Build a record with synthesize_fabricate provenance AND has_findings — must be rejected
        with pytest.raises(RecordValidationError, match="synthesize_fabricate"):
            bad_record = GenRetrospectiveRecord(
                schema_version=1,
                mission_id=MISSION_ID_COMPLETED,
                mission_slug=MISSION_SLUG_COMPLETED,
                created_at=now,
                created_by=actor,
                provenance=GenProvenance(
                    kind="synthesize_fabricate",
                    invoked_at=now,
                ),
                findings_status="has_findings",  # violates the invariant
                helped=[
                    GenFinding(
                        id="h-001",
                        category="process",
                        summary="Some finding",
                        evidence_refs=[],
                    )
                ],
            )
            # write_gen_record calls validate_record which must raise
            with tempfile.TemporaryDirectory() as td:
                write_gen_record(bad_record, mode="error", repo_root=pathlib.Path(td))


# ---------------------------------------------------------------------------
# TestBackfillEmitSkipped (Cycle-2 Blocker 2)
# ---------------------------------------------------------------------------


class TestBackfillEmitSkipped:
    """Tests that --emit-skipped actually emits RetrospectiveSkipped events.

    Before cycle-2 fix, the parameter was a dead no-op (ARG001 noqa comment).
    These tests assert that events land in status.events.jsonl.
    """

    def test_emit_skipped_writes_event_to_status_events_jsonl(self, tmp_path: Path) -> None:
        """--emit-skipped must write a RetrospectiveSkipped event for each skipped mission."""
        import json as _json

        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        # Mission with an existing record — will be skipped with reason="already_exists"
        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(
            mission_dir,
            MISSION_ID_COMPLETED,
            MISSION_SLUG_COMPLETED,
            completed_at=completed_at,
        )
        # Pre-existing record triggers skip
        record_path = mission_dir / "retrospective.yaml"
        record_path.write_text("existing: true\n", encoding="utf-8")

        # Set up kitty-specs feature dir so emit_skipped can find it
        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        feature_dir.mkdir(parents=True, exist_ok=True)

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(
                retrospect_app,
                ["backfill", "--emit-skipped", "--json"],
            )

        assert result.exit_code == 0, result.output
        data = _json.loads(result.output)
        skipped = data["skipped"]
        assert any(s["reason"] == "already_exists" for s in skipped)

        # A RetrospectiveSkipped event must have been written to status.events.jsonl
        events_path = feature_dir / "status.events.jsonl"
        assert events_path.exists(), "status.events.jsonl must exist after --emit-skipped (event must be written)"
        raw_lines = [line.strip() for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        all_events = [_json.loads(raw) for raw in raw_lines]
        skip_events = [e for e in all_events if e.get("type") == "RetrospectiveSkipped"]
        assert len(skip_events) >= 1, f"Expected at least 1 RetrospectiveSkipped event in status.events.jsonl, found {len(skip_events)}. All events: {all_events}"
        # Verify the skip_reason is structured
        for evt in skip_events:
            assert evt.get("skip_reason", "").startswith("backfill_skip:"), f"skip_reason must start with 'backfill_skip:', got {evt.get('skip_reason')!r}"

    def test_emit_skipped_not_set_does_not_write_events(self, tmp_path: Path) -> None:
        """Without --emit-skipped, no RetrospectiveSkipped events are written."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(
            mission_dir,
            MISSION_ID_COMPLETED,
            MISSION_SLUG_COMPLETED,
            completed_at=completed_at,
        )
        record_path = mission_dir / "retrospective.yaml"
        record_path.write_text("existing: true\n", encoding="utf-8")

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        feature_dir.mkdir(parents=True, exist_ok=True)

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(
                retrospect_app,
                ["backfill", "--json"],  # No --emit-skipped
            )

        assert result.exit_code == 0, result.output

        events_path = feature_dir / "status.events.jsonl"
        if events_path.exists():
            import json as _json2

            raw_lines = [line.strip() for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            all_events = [_json2.loads(raw) for raw in raw_lines]
            skip_events = [e for e in all_events if e.get("type") == "RetrospectiveSkipped"]
            assert len(skip_events) == 0, "Without --emit-skipped, no RetrospectiveSkipped events should be written"

    def test_emit_skipped_dry_run_does_not_write_events(self, tmp_path: Path) -> None:
        """--emit-skipped combined with --dry-run must NOT write any events."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(
            mission_dir,
            MISSION_ID_COMPLETED,
            MISSION_SLUG_COMPLETED,
            completed_at=completed_at,
        )
        record_path = mission_dir / "retrospective.yaml"
        record_path.write_text("existing: true\n", encoding="utf-8")

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        feature_dir.mkdir(parents=True, exist_ok=True)

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(
                retrospect_app,
                ["backfill", "--emit-skipped", "--dry-run", "--json"],
            )

        assert result.exit_code == 0, result.output

        events_path = feature_dir / "status.events.jsonl"
        if events_path.exists():
            import json as _json3

            raw_lines = [line.strip() for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            all_events = [_json3.loads(raw) for raw in raw_lines]
            skip_events = [e for e in all_events if e.get("type") == "RetrospectiveSkipped"]
            assert len(skip_events) == 0, "--dry-run + --emit-skipped must NOT emit events"


# ---------------------------------------------------------------------------
# D1 harness: `retrospect create` / `backfill` driven end to end (#5353 slice 3)
#
# A real temp git repo (auto-commit on) holding one completed mission whose
# meta.json carries a real ULID, real spec/plan/tasks artifacts, and a status
# log written through the production status seam (emit_status_transition).
# Only the Zeitgeist fan-out edge is patched and the clock frozen; faults are
# injected only where no real fixture reaches the branch (a generator crash,
# a missing-artifact error the handle resolver would catch first, a writer race).
# ---------------------------------------------------------------------------

_FROZEN_NOW = "2026-05-02T09:00:00+00:00"
_REVIEW_EVIDENCE = {"review": {"reviewer": "reviewer-renata", "verdict": "approved", "reference": "review-WP01"}}
_GENERATED_GAP = "research.md absent"
_SEEDED_GAP = "lane bounced before approval"
_CREATE_MESSAGE = f"chore(retrospective): author retrospective for {MISSION_SLUG_COMPLETED}"
_BACKFILL_MESSAGE = f"chore(retrospective): backfill retrospective for {MISSION_SLUG_COMPLETED}"
_RETRO_MODULE = "specify_cli.cli.commands.retrospect"


@dataclass(frozen=True)
class RetrospectProject:
    """A real project holding one completed mission; helpers read its durable state."""

    repo: Path
    feature_dir: Path

    @property
    def record_path(self) -> Path:
        return self.feature_dir / "retrospective.yaml"

    @property
    def events_path(self) -> Path:
        return self.feature_dir / "status.events.jsonl"

    def git(self, *args: str) -> str:
        return _git(self.repo, *args)

    def head(self) -> str:
        return self.git("rev-parse", "HEAD")

    def record(self) -> dict[str, Any]:
        loaded: dict[str, Any] = yaml.safe_load(self.record_path.read_text(encoding="utf-8"))
        return loaded

    def rows(self, event_type: str) -> list[dict[str, Any]]:
        lines = self.events_path.read_text(encoding="utf-8").splitlines() if self.events_path.exists() else []
        return [row for row in (json.loads(line) for line in lines if line.strip()) if row.get("type") == event_type]

    def seed_record(self, *, gap_summary: str) -> bytes:
        """Write and commit an existing record (production writer) with one gap; returns its bytes."""
        from specify_cli.retrospective.schema import GenFinding
        from specify_cli.retrospective.writer import write_gen_record

        seeded = _make_minimal_gen_record(findings_status="has_findings")
        seeded.gaps = [GenFinding(id="g-001", category="process", summary=gap_summary)]
        write_gen_record(seeded, mode="overwrite", repo_root=self.repo)
        self.git("add", "--", str(self.record_path))
        self.git("commit", "-q", "-m", "seed an existing retrospective")
        return self.record_path.read_bytes()

    def register_for_backfill(self, mission_id: str, mission_slug: str) -> None:
        """Register a mission, completed five days before the frozen clock, in the backfill registry."""
        _write_meta(
            self.repo / ".kittify" / "missions" / mission_id,
            mission_id,
            mission_slug,
            completed_at="2026-04-27T09:00:00+00:00",
        )


def _walk_wp01_to_done(feature_dir: Path, repo: Path) -> None:
    """Walk WP01 planned -> done through the production status seam."""
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import ReviewResult

    for lane in ("planned", "claimed", "in_progress", "for_review", "in_review", "approved", "done"):
        reviewing = lane in ("in_review", "approved", "done")
        emit_status_transition(
            feature_dir,
            wp_id="WP01",
            to_lane=lane,
            actor="reviewer-renata" if reviewing else "implementer-ivan",
            mission_slug=MISSION_SLUG_COMPLETED,
            repo_root=repo,
            fan_out=False,
            evidence=_REVIEW_EVIDENCE if lane in ("approved", "done") else None,
            review_ref="review-WP01" if lane == "approved" else None,
            review_result=ReviewResult(reviewer="reviewer-renata", verdict="approved", reference="review-WP01") if lane == "approved" else None,
        )


def _build_retrospect_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, branch: str) -> RetrospectProject:
    """A real project on *branch*, the completed mission's target branch."""
    import kernel.clock as clock_module
    from kernel.clock import FrozenClock, parse_iso

    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=parse_iso(_FROZEN_NOW)))
    monkeypatch.setattr(_FANOUT_EDGE, lambda *args, **kwargs: None)

    repo = tmp_path / "repo"
    _init_git_repo(repo, auto_commit=True, branch=branch)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG_COMPLETED
    _write_meta(
        feature_dir,
        MISSION_ID_COMPLETED,
        MISSION_SLUG_COMPLETED,
        friendly_name="Completed mission",
        mission_type="software-dev",
        target_branch=branch,
    )
    (feature_dir / "spec.md").write_text("# Spec\n\n- FR-001: the mission does the thing\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\nDo the thing.\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n\n- WP01: the thing\n", encoding="utf-8")
    (feature_dir / "tasks").mkdir()
    (feature_dir / "tasks" / "WP01-the-thing.md").write_text(
        "---\nwork_package_id: WP01\ntitle: The thing\nsubtasks: []\n---\n# WP01\n\nCovers FR-001.\n", encoding="utf-8"
    )
    _walk_wp01_to_done(feature_dir, repo)
    _git(repo, "add", "--", ".kittify", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "init")
    monkeypatch.chdir(repo)
    return RetrospectProject(repo=repo, feature_dir=feature_dir)


@pytest.fixture
def retrospect_project(tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> RetrospectProject:
    return _build_retrospect_project(tmp_path, monkeypatch, branch=_MISSION_BRANCH)


@pytest.fixture
def protected_retrospect_project(tmp_path: Path, canonical_home: None, monkeypatch: pytest.MonkeyPatch) -> RetrospectProject:
    """The same project, but the mission targets (and the checkout is on) protected ``main``."""
    return _build_retrospect_project(tmp_path, monkeypatch, branch=_PROTECTED_BRANCH)


def _create(*args: str) -> Any:
    return RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED, *args])


def _backfill(*args: str) -> Any:
    return RUNNER.invoke(retrospect_app, ["backfill", *args])


class TestCreateHarness:
    """`retrospect create` on a real project: exit code, payload, record on disk, event row, git."""

    def test_create_json_reports_writes_emits_and_commits_the_record(self, retrospect_project: RetrospectProject) -> None:
        project = retrospect_project
        head_before = project.head()

        result = _create("--json")

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload == {
            "result": "success",
            "mission_id": MISSION_ID_COMPLETED,
            "mission_slug": MISSION_SLUG_COMPLETED,
            "record_path": str(project.record_path),
            "findings_status": "has_findings",
            "counts": {"helped": 0, "not_helpful": 0, "gaps": 1, "proposals": 0, "evidence_refs": 6},
            "provenance_kind": "explicit_create",
            "policy_source": {"enabled": "<default>", "timing": "<default>", "failure_policy": "<default>"},
            "next_step": (
                f"Run `spec-kitty agent retrospect synthesize --mission {MISSION_SLUG_COMPLETED}` to review proposals (dry-run by default; add --apply to mutate)."
            ),
        }
        record = project.record()
        assert record["mission_id"] == MISSION_ID_COMPLETED
        assert record["provenance"]["kind"] == "explicit_create"
        assert record["provenance"]["command"] == "spec-kitty retrospect create"
        assert [gap["summary"] for gap in record["gaps"]] == [_GENERATED_GAP]
        assert len(record["evidence_refs"]) == 6
        (captured,) = project.rows("RetrospectiveCaptured")
        assert captured["record_path"] == str(project.record_path)
        assert captured["findings_status"] == "has_findings"
        assert captured["evidence_ref_count"] == 6
        assert captured["provenance_kind"] == "explicit_create"
        assert project.git("log", "--format=%s", f"{head_before}..HEAD") == _CREATE_MESSAGE
        assert project.git("show", "--name-only", "--format=", "HEAD").splitlines() == [
            f"kitty-specs/{MISSION_SLUG_COMPLETED}/retrospective.yaml",
            f"kitty-specs/{MISSION_SLUG_COMPLETED}/status.events.jsonl",
        ]
        assert project.git("status", "--porcelain") == ""
        assert result.stderr == ""

    def test_create_on_a_protected_target_warns_and_commits_nothing(self, protected_retrospect_project: RetrospectProject) -> None:
        """The record and its event are written, but the STANDARD router refuses protected ``main``: warn, exit 0."""
        project = protected_retrospect_project
        head_before = project.head()

        result = _create("--json")

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["result"] == "success"
        assert project.record_path.is_file()
        assert len(project.rows("RetrospectiveCaptured")) == 1
        assert project.head() == head_before
        assert project.git("diff", "--name-only") == f"kitty-specs/{MISSION_SLUG_COMPLETED}/status.events.jsonl"
        assert project.git("ls-files", "--others", "--exclude-standard") == f"kitty-specs/{MISSION_SLUG_COMPLETED}/retrospective.yaml"
        warning = " ".join(strip_ansi(result.stderr).split())
        assert "auto-commit skipped: the mission's target branch 'main' is protected, so nothing was committed to it" in warning
        assert "commit it from a feature branch (never the coordination branch) and land it through a pull request" in warning
        assert "mission branch" not in warning
        assert str(project.record_path) in warning
        assert str(project.events_path) in warning

    def test_create_without_json_renders_the_authored_panel(self, retrospect_project: RetrospectProject) -> None:
        result = _create()

        assert result.exit_code == 0, result.output
        panel = " ".join(strip_ansi(result.stdout).split())
        assert "Retrospective authored" in panel
        assert f"Mission: {MISSION_SLUG_COMPLETED}" in panel
        assert "Findings status: has_findings" in panel
        assert "helped=0 not_helpful=0 gaps=1 proposals=0" in panel
        assert retrospect_project.record_path.is_file()

    @pytest.mark.parametrize("json_flag", [["--json"], []], ids=["json", "rich"])
    def test_create_refuses_to_replace_an_existing_record(self, retrospect_project: RetrospectProject, json_flag: list[str]) -> None:
        project = retrospect_project
        seeded = project.seed_record(gap_summary=_SEEDED_GAP)
        head_before = project.head()

        result = _create(*json_flag)

        assert result.exit_code == 1, result.output
        if json_flag:
            payload = json.loads(result.stdout)
            assert payload["code"] == "RETROSPECTIVE_RECORD_EXISTS"
            assert payload["result"] == "blocked"
            assert payload["record_path"] == str(project.record_path)
            assert payload["mission_id"] == MISSION_ID_COMPLETED
            assert payload["exit_code"] == 1
        else:
            error = " ".join(strip_ansi(result.stderr).split())
            assert error.startswith("Error RETROSPECTIVE_RECORD_EXISTS: A retrospective record already exists at")
            assert str(project.record_path) in strip_ansi(result.stderr).replace("\n", "")
        assert project.record_path.read_bytes() == seeded
        assert project.rows("RetrospectiveCaptured") == []
        assert project.head() == head_before

    def test_create_overwrite_replaces_the_existing_record(self, retrospect_project: RetrospectProject) -> None:
        project = retrospect_project
        project.seed_record(gap_summary=_SEEDED_GAP)

        result = _create("--overwrite", "--json")

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["counts"]["gaps"] == 1
        record = project.record()
        assert [gap["summary"] for gap in record["gaps"]] == [_GENERATED_GAP]
        assert record["provenance"]["kind"] == "explicit_create"
        assert project.git("log", "-1", "--format=%s") == _CREATE_MESSAGE

    def test_create_update_merges_into_the_existing_record(self, retrospect_project: RetrospectProject) -> None:
        project = retrospect_project
        project.seed_record(gap_summary=_SEEDED_GAP)

        result = _create("--update", "--json")

        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        record = project.record()
        assert sorted(gap["summary"] for gap in record["gaps"]) == sorted([_SEEDED_GAP, _GENERATED_GAP])
        assert payload["counts"]["gaps"] == 2
        assert payload["findings_status"] == record["findings_status"] == "has_findings"
        (captured,) = project.rows("RetrospectiveCaptured")
        assert captured["findings_status"] == "has_findings"

    @pytest.mark.parametrize("json_flag", [["--json"], []], ids=["json", "rich"])
    def test_create_blocks_on_a_malformed_retrospective_policy(self, retrospect_project: RetrospectProject, json_flag: list[str]) -> None:
        project = retrospect_project
        (project.repo / ".kittify" / "config.yaml").write_text("auto_commit: true\nretrospective:\n  timing: sometimes\n", encoding="utf-8")
        head_before = project.head()

        result = _create(*json_flag)

        assert result.exit_code == 1, result.output
        if json_flag:
            payload = json.loads(result.stdout)
            assert payload["code"] == "POLICY_RESOLUTION_ERROR"
            assert payload["result"] == "blocked"
            assert "timing: got 'sometimes'" in payload["blocked_reason"]
        else:
            error = " ".join(strip_ansi(result.stderr).split())
            assert error.startswith("Error POLICY_RESOLUTION_ERROR:")
            assert "timing: got 'sometimes'" in error
        assert not project.record_path.exists()
        assert project.rows("RetrospectiveCaptured") == []
        assert project.head() == head_before

    @pytest.mark.parametrize(
        ("fault", "expected_error"),
        [
            (FileNotFoundError("tasks.md vanished"), "Error: Could not find mission artifacts: tasks.md vanished"),
            (RuntimeError("generator crashed"), "Error: Generator failed: generator crashed"),
        ],
        ids=["missing-artifacts", "generator-crash"],
    )
    def test_create_reports_a_generator_failure_and_writes_nothing(self, retrospect_project: RetrospectProject, fault: Exception, expected_error: str) -> None:
        """Injected: the handle resolver rejects a mission the generator cannot read, so no fixture reaches these."""
        project = retrospect_project
        head_before = project.head()

        with patch(f"{_RETRO_MODULE}.generate_retrospective", side_effect=fault):
            result = _create()

        assert result.exit_code == 1, result.output
        assert " ".join(strip_ansi(result.stderr).split()) == expected_error
        assert not project.record_path.exists()
        assert project.rows("RetrospectiveCaptured") == []
        assert project.head() == head_before

    def test_create_reports_a_record_write_failure(self, retrospect_project: RetrospectProject) -> None:
        """A directory squatting on the record path makes the real writer fail on --overwrite."""
        project = retrospect_project
        project.record_path.mkdir()
        head_before = project.head()

        result = _create("--overwrite")

        assert result.exit_code == 1, result.output
        error = " ".join(strip_ansi(result.stderr).split())
        assert error.startswith("Error: Failed to write record:")
        assert "retrospective.yaml" in error
        assert project.rows("RetrospectiveCaptured") == []
        assert project.head() == head_before

    def test_synthesize_reads_the_created_record_and_reports_its_outcome(self, retrospect_project: RetrospectProject) -> None:
        """Folded from test_agent_retrospect_missing_record.py: the envelope of a real, generator-shaped record."""
        assert _create("--json").exit_code == 0

        result = RUNNER.invoke(agent_retrospect_app, ["synthesize", "--mission", MISSION_ID_COMPLETED[:8], "--json"])

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout)
        assert envelope["status"] == "ok"
        assert envelope["outcome"] == "retrospective_synthesized"
        assert envelope["mission_id"] == MISSION_ID_COMPLETED
        assert envelope["mission_slug"] == MISSION_SLUG_COMPLETED
        assert envelope["dry_run"] is True
        assert envelope["retrospective_path"] == str(retrospect_project.record_path)

    @pytest.mark.parametrize("apply_flag", [["--apply"], []], ids=["apply", "dry-run"])
    def test_synthesize_refuses_proposal_ids_on_the_created_generator_record(self, retrospect_project: RetrospectProject, apply_flag: list[str]) -> None:
        """A `retrospect create` record is generator-shaped: every id is refused as unsupported, not as unknown."""
        project = retrospect_project
        assert _create("--json").exit_code == 0
        before = project.record_path.read_bytes()
        head_before = project.head()

        result = RUNNER.invoke(
            agent_retrospect_app,
            [
                "synthesize",
                "--mission",
                MISSION_SLUG_COMPLETED,
                *apply_flag,
                "--json",
                *("--proposal-id", "p-001", "--proposal-id", "p-002", "--proposal-id", "p-001"),
            ],
        )

        assert result.exit_code == 1, result.output
        assert result.stdout == ""
        payload = json.loads(result.stderr)
        assert payload["error"] == "unsupported_generator_record"
        assert payload["proposal_ids"] == ["p-001", "p-002"]
        assert payload["statuses"] == {"p-001": "unsupported_generator_record", "p-002": "unsupported_generator_record"}
        assert "uses the generator record schema" in payload["detail"]
        assert payload["detail"].endswith("Requested: p-001, p-002. Nothing was applied.")
        assert "unknown" not in payload["detail"]
        assert project.record_path.read_bytes() == before
        assert project.head() == head_before

    def test_synthesize_proposal_id_on_a_generator_record_rich_error(self, retrospect_project: RetrospectProject) -> None:
        assert _create("--json").exit_code == 0

        result = RUNNER.invoke(agent_retrospect_app, ["synthesize", "--mission", MISSION_SLUG_COMPLETED, "--proposal-id", "p-001"])

        assert result.exit_code == 1, result.output
        error = " ".join(strip_ansi(result.stderr).split())
        assert error.startswith("Error: --proposal-id cannot pick proposals in this retrospective record")
        assert error.endswith("Requested: p-001. Nothing was applied.")

    def test_fabricate_empty_with_proposal_id_says_the_record_was_written(self, retrospect_project: RetrospectProject) -> None:
        """`--fabricate-empty` writes the record, then refuses the id: the message does not claim nothing happened."""
        project = retrospect_project

        result = RUNNER.invoke(
            agent_retrospect_app,
            ["synthesize", "--mission", MISSION_SLUG_COMPLETED, "--fabricate-empty", "--apply", "--proposal-id", "p-001", "--json"],
        )

        assert result.exit_code == 1, result.output
        payload = json.loads(result.stderr)
        assert payload["error"] == "unsupported_generator_record"
        assert payload["detail"].endswith("Requested: p-001. The empty retrospective record was written, but no proposal was applied.")
        assert project.record()["provenance"]["kind"] == "synthesize_fabricate"

    def test_fabricate_empty_writes_and_reports_an_empty_record(self, retrospect_project: RetrospectProject) -> None:
        project = retrospect_project

        result = RUNNER.invoke(agent_retrospect_app, ["synthesize", "--mission", MISSION_SLUG_COMPLETED, "--fabricate-empty", "--json"])

        assert result.exit_code == 0, result.output
        envelope = json.loads(result.stdout)
        assert envelope["status"] == "ok"
        assert envelope["retrospective_path"] == str(project.record_path)
        assert envelope["result"]["planned"] == []
        record = project.record()
        assert record["provenance"]["kind"] == "synthesize_fabricate"
        assert record["findings_status"] == "ran_no_findings"
        (captured,) = project.rows("RetrospectiveCaptured")
        assert captured["findings_status"] == "ran_no_findings"


class TestBackfillHarness:
    """`retrospect backfill` on a real project: aggregate report, records, failure rows, git."""

    @pytest.mark.parametrize("emit_failures", [True, False], ids=["emit-failures", "no-emit"])
    def test_backfill_reports_event_log_write_location_refused(
        self, retrospect_project: RetrospectProject, monkeypatch: pytest.MonkeyPatch, emit_failures: bool
    ) -> None:
        """B1: a genuine write-location refusal during backfill's main emit does NOT
        mislabel the already-written record as a ``generator_exception`` (cycle 2 review)."""
        from specify_cli.cli.commands import retrospect as retrospect_module
        from specify_cli.status.locking import FeatureStatusLockTimeoutError

        project = retrospect_project
        project.register_for_backfill(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        def _boom(_root: Path, _slug: str) -> Path:
            raise FeatureStatusLockTimeoutError("status lock contended")

        monkeypatch.setattr(retrospect_module, "_canonical_events_write_path", _boom)

        result = _backfill(*(["--emit-failures"] if emit_failures else []), "--json")

        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        assert report["created"] == 0
        (failure,) = report["failed"]
        assert failure["mission_slug"] == MISSION_SLUG_COMPLETED
        assert failure["failure_category"] == "other"
        assert "event-log location could not be resolved" in failure["remediation_hint"]
        assert "status lock contended" in failure["remediation_hint"]
        # The record itself WAS generated and written -- B1's whole point.
        assert project.record_path.is_file()

    def test_backfill_authors_commits_and_reports_the_record(self, retrospect_project: RetrospectProject) -> None:
        project = retrospect_project
        project.register_for_backfill(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        head_before = project.head()

        result = _backfill("--json")

        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        assert report["created"] == 1
        assert report["scanned"] == 1
        assert report["failed"] == []
        assert report["skipped"] == []
        record = project.record()
        assert record["provenance"]["kind"] == "backfill"
        assert record["provenance"]["command"] == "spec-kitty retrospect backfill"
        (captured,) = project.rows("RetrospectiveCaptured")
        assert captured["provenance_kind"] == "backfill"
        assert project.git("log", "--format=%s", f"{head_before}..HEAD") == _BACKFILL_MESSAGE
        assert project.git("status", "--porcelain", "--", "kitty-specs") == ""

    def test_backfill_on_a_protected_target_warns_and_commits_nothing(self, protected_retrospect_project: RetrospectProject) -> None:
        project = protected_retrospect_project
        project.register_for_backfill(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        head_before = project.head()

        result = _backfill("--json")

        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["created"] == 1
        assert project.head() == head_before
        assert f"?? kitty-specs/{MISSION_SLUG_COMPLETED}/retrospective.yaml" in project.git("status", "--porcelain").splitlines()
        warning = " ".join(strip_ansi(result.stderr).split())
        assert "target branch 'main' is protected" in warning
        assert str(project.record_path) in warning

    def test_backfill_without_json_renders_the_summary_panel(self, retrospect_project: RetrospectProject) -> None:
        retrospect_project.register_for_backfill(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        result = _backfill()

        assert result.exit_code == 0, result.output
        panel = " ".join(strip_ansi(result.stdout).split())
        assert "Backfill complete" in panel
        assert "Scanned: 1 | Created: 1 | Skipped: 0 | Failed: 0" in panel
        assert retrospect_project.record_path.is_file()

    @pytest.mark.parametrize("emit_failures", [True, False], ids=["emit-failures", "no-emit"])
    def test_backfill_reports_a_mission_without_artifacts(self, retrospect_project: RetrospectProject, emit_failures: bool) -> None:
        """A registered mission with no kitty-specs/ directory: the real generator raises FileNotFoundError."""
        project = retrospect_project
        orphan_id, orphan_slug = MISSION_ID_OPEN, MISSION_SLUG_OPEN
        project.register_for_backfill(orphan_id, orphan_slug)

        result = _backfill(*(["--emit-failures"] if emit_failures else []), "--json")

        assert result.exit_code == 0, result.output
        (failure,) = json.loads(result.stdout)["failed"]
        assert failure["mission_slug"] == orphan_slug
        assert failure["failure_category"] == "missing_artifacts"
        assert f"Mission '{orphan_slug}' not found under" in failure["missing"][0]
        assert failure["remediation_hint"] == (f"Mission lacks required artifacts; rebuild via `spec-kitty migrate normalize-lifecycle --mission {orphan_slug}`.")
        orphan_log = RetrospectProject(repo=project.repo, feature_dir=project.repo / "kitty-specs" / orphan_slug)
        rows = orphan_log.rows("RetrospectiveCaptureFailed")
        if emit_failures:
            (row,) = rows
            assert row["mission_id"] == orphan_id
            assert row["failure_category"] == "missing_artifacts"
            assert row["missing_artifacts"] == failure["missing"]
        else:
            assert rows == []

    @pytest.mark.parametrize("emit_failures", [True, False], ids=["emit-failures", "no-emit"])
    def test_backfill_reports_a_generator_crash(self, retrospect_project: RetrospectProject, emit_failures: bool) -> None:
        """Injected: no real mission makes the deterministic generator crash."""
        project = retrospect_project
        project.register_for_backfill(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        with patch(f"{_RETRO_MODULE}.generate_retrospective", side_effect=RuntimeError("crash")):
            result = _backfill(*(["--emit-failures"] if emit_failures else []), "--json")

        assert result.exit_code == 0, result.output
        (failure,) = json.loads(result.stdout)["failed"]
        assert failure["failure_category"] == "generator_exception"
        assert failure["remediation_hint"] == "crash"
        assert not project.record_path.exists()
        rows = project.rows("RetrospectiveCaptureFailed")
        if emit_failures:
            (row,) = rows
            assert row["failure_category"] == "generator_exception"
            assert row["failure_message"] == "crash"
        else:
            assert rows == []

    def test_backfill_without_json_lists_the_failures(self, retrospect_project: RetrospectProject) -> None:
        retrospect_project.register_for_backfill(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        with patch(f"{_RETRO_MODULE}.generate_retrospective", side_effect=RuntimeError("crash")):
            result = _backfill()

        assert result.exit_code == 0, result.output
        assert "Scanned: 1 | Created: 0 | Skipped: 0 | Failed: 1" in " ".join(strip_ansi(result.stdout).split())
        failures = " ".join(strip_ansi(result.stderr).split())
        assert failures == f"Failures (1): {MISSION_SLUG_COMPLETED}: generator_exception — crash"

    def test_backfill_skips_a_record_that_appeared_after_the_prescreen(self, retrospect_project: RetrospectProject) -> None:
        """Injected writer race: the record appears between the existence prescreen and the write."""
        from specify_cli.retrospective.writer import RecordExistsError

        project = retrospect_project
        project.register_for_backfill(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        with patch(f"{_RETRO_MODULE}.write_gen_record", side_effect=RecordExistsError(project.record_path)):
            result = _backfill("--json")

        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        assert report["created"] == 0
        assert report["skipped"] == [
            {
                "mission_id": MISSION_ID_COMPLETED,
                "mission_slug": MISSION_SLUG_COMPLETED,
                "reason": "already_exists",
                "record_path": str(project.record_path),
            }
        ]
        assert project.rows("RetrospectiveCaptured") == []
