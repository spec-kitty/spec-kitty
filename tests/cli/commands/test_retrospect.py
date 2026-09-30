"""CLI tests for WP05: spec-kitty retrospect create / backfill / summary / synthesize.

Tests:
- TestCreateCommand: success, RecordExists, MissionNotCompleted, AmbiguousSelector,
                      --overwrite, --update, --json
- TestBackfillCommand: dry-run, real run, since/until filtering, mission filter,
                       emit-skipped/failures, JSON shape
- TestSummaryReadOnlyInvariant: no filesystem mutation; 4-state output
- TestSynthesizeTighteningDefault: missing record error
- TestSynthesizeFabricateEmpty: --fabricate-empty flag

FR-016 env-mutation check: no SPEC_KITTY_RETROSPECTIVE or SPEC_KITTY_MODE setenv in this file.
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from kernel.clock import timedelta, now_utc_iso, now_utc
from pathlib import Path
from typing import Any, Literal
from unittest.mock import MagicMock, patch

import pytest
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
        json.dumps({
            "mission_id": mission_id,
            "mission_slug": mission_slug,
            "slug": mission_slug,
        }),
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


def _persisting_write_gen_record(
    captured_mode: list[str] | None = None,
) -> Any:
    """Build a `write_gen_record` stand-in that actually persists to disk.

    #3320 fix: `create_cmd` reads the record back via `read_gen_record(record_path)`
    after writing, so a mock that returns a `Path` with nothing written there
    (the pre-fix pattern) now raises FileNotFoundError. Delegate to the real
    writer so the on-disk read-back has a file to load, while still letting
    the caller observe the `mode` that was requested.
    """
    from specify_cli.retrospective.schema import GenRetrospectiveRecord
    from specify_cli.retrospective.writer import write_gen_record as _real_write_gen_record

    def _write(
        record: GenRetrospectiveRecord,
        *,
        mode: Literal["error", "overwrite", "update"],
        repo_root: Path,
    ) -> Path:
        if captured_mode is not None:
            captured_mode.append(mode)
        # `specify_cli.*` mypy override sets follow_imports="skip" (perf
        # workaround for the CLI bootstrap import graph), so the writer's real
        # `-> Path` annotation isn't visible here; the local annotation below
        # re-anchors the type instead of masking a real error with `# type: ignore`.
        written_path: Path = _real_write_gen_record(record, mode=mode, repo_root=repo_root)
        return written_path

    return _write


# ---------------------------------------------------------------------------
# TestCreateCommand
# ---------------------------------------------------------------------------


class TestCreateCommand:
    """Tests for `spec-kitty retrospect create`."""

    def test_create_success_json(self, tmp_path: Path) -> None:
        """Successful create with --json output matches contract shape."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)

        gen_record = _make_minimal_gen_record()

        resolved = _build_resolved_mission(
            MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir
        )

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)
        mock_policy_source = {}

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, mock_policy_source)),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch(
                "specify_cli.cli.commands.retrospect.write_gen_record",
                side_effect=_persisting_write_gen_record(),
            ),
            patch("specify_cli.cli.commands.retrospect.emit_captured", return_value=None),
            patch("specify_cli.cli.commands.retrospect._maybe_auto_commit"),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED, "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        # Contract shape assertions
        assert data["result"] == "success"
        assert data["mission_id"] == MISSION_ID_COMPLETED
        assert data["mission_slug"] == MISSION_SLUG_COMPLETED
        assert "record_path" in data
        assert "findings_status" in data
        assert "counts" in data
        assert "provenance_kind" in data
        assert data["provenance_kind"] == "explicit_create"
        assert "policy_source" in data
        assert "next_step" in data
        # Counts shape
        counts = data["counts"]
        for key in ("helped", "not_helpful", "gaps", "proposals", "evidence_refs"):
            assert key in counts

    def test_create_record_exists_error_json(self, tmp_path: Path) -> None:
        """RETROSPECTIVE_RECORD_EXISTS error matches contract shape."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)

        existing_path = missions_dir / MISSION_ID_COMPLETED / "retrospective.yaml"
        existing_path.parent.mkdir(parents=True, exist_ok=True)
        existing_path.write_text("exists: true\n", encoding="utf-8")

        gen_record = _make_minimal_gen_record()
        resolved = _build_resolved_mission(
            MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir
        )

        from specify_cli.retrospective.policy import RetrospectivePolicy
        from specify_cli.retrospective.writer import RecordExistsError
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch("specify_cli.cli.commands.retrospect.write_gen_record", side_effect=RecordExistsError(existing_path)),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED, "--json"])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["result"] == "blocked"
        assert data["code"] == "RETROSPECTIVE_RECORD_EXISTS"
        assert data["mission_id"] == MISSION_ID_COMPLETED
        assert data["mission_slug"] == MISSION_SLUG_COMPLETED
        assert "record_path" in data
        assert "blocked_reason" in data
        assert data["exit_code"] == 1

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

    def test_create_overwrite_flag(self, tmp_path: Path) -> None:
        """--overwrite flag passes mode='overwrite' to write_gen_record."""
        repo_root, _missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)

        gen_record = _make_minimal_gen_record()
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)
        captured_mode: list[str] = []

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch(
                "specify_cli.cli.commands.retrospect.write_gen_record",
                side_effect=_persisting_write_gen_record(captured_mode),
            ),
            patch("specify_cli.cli.commands.retrospect.emit_captured", return_value=None),
            patch("specify_cli.cli.commands.retrospect._maybe_auto_commit"),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED, "--overwrite"])

        assert result.exit_code == 0
        assert captured_mode == ["overwrite"]

    def test_create_update_flag(self, tmp_path: Path) -> None:
        """--update flag passes mode='update' to write_gen_record."""
        repo_root, _missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)

        gen_record = _make_minimal_gen_record()
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)
        captured_mode: list[str] = []

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch(
                "specify_cli.cli.commands.retrospect.write_gen_record",
                side_effect=_persisting_write_gen_record(captured_mode),
            ),
            patch("specify_cli.cli.commands.retrospect.emit_captured", return_value=None),
            patch("specify_cli.cli.commands.retrospect._maybe_auto_commit"),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED, "--update"])

        assert result.exit_code == 0
        assert captured_mode == ["update"]

    def test_create_overwrite_and_update_mutually_exclusive(self, tmp_path: Path) -> None:
        """--overwrite and --update together should produce an error."""
        repo_root, _, _ = _setup_project(tmp_path)

        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root):
            result = RUNNER.invoke(
                retrospect_app,
                ["create", "--mission", MISSION_SLUG_COMPLETED, "--overwrite", "--update"],
            )

        assert result.exit_code != 0

    def test_create_success_rich_output(self, tmp_path: Path) -> None:
        """Success without --json produces Rich panel output, not bare JSON."""
        repo_root, _missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)

        gen_record = _make_minimal_gen_record()
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch(
                "specify_cli.cli.commands.retrospect.write_gen_record",
                side_effect=_persisting_write_gen_record(),
            ),
            patch("specify_cli.cli.commands.retrospect.emit_captured", return_value=None),
            patch("specify_cli.cli.commands.retrospect._maybe_auto_commit"),
        ):
            result = RUNNER.invoke(retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED])

        assert result.exit_code == 0
        # Should not be parseable as raw JSON (it's Rich panel output)
        output = result.output
        assert "Retrospective authored" in output or "retrospective" in output.lower()


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

    def test_fabricate_empty_creates_record_when_missing(self, tmp_path: Path) -> None:
        """--fabricate-empty on a missing record runs the legacy creation path."""
        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)

        feature_dir = kitty_specs_dir / MISSION_SLUG_COMPLETED
        _write_kitty_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        _write_status_events_all_done(feature_dir, MISSION_SLUG_COMPLETED)

        # Add required artifacts for _mission_artifacts_sufficient_for_empty_record
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "WP01.md").write_text("# WP01\n", encoding="utf-8")

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        from specify_cli.retrospective.schema import (
            ActorRef,
            MissionIdentity,
            Mode,
            ModeSourceSignal,
            RecordProvenance,
            RetrospectiveRecord,
        )
        from specify_cli.doctrine_synthesizer import SynthesisResult

        # Build a real Pydantic RetrospectiveRecord for the read_record mock
        now_str = now_utc_iso()
        pydantic_record = RetrospectiveRecord(
            schema_version="1",
            mission=MissionIdentity(
                mission_id=MISSION_ID_COMPLETED,
                mid8=MISSION_ID_COMPLETED[:8],
                mission_slug=MISSION_SLUG_COMPLETED,
                mission_type="software-dev",
                mission_started_at=now_str,
                mission_completed_at=now_str,
            ),
            mode=Mode(
                value="autonomous",
                source_signal=ModeSourceSignal(kind="environment", evidence="test"),
            ),
            status="completed",
            started_at=now_str,
            completed_at=now_str,
            actor=ActorRef(kind="agent", id="test"),
            helped=[],
            not_helpful=[],
            gaps=[],
            proposals=[],
            provenance=RecordProvenance(
                authored_by=ActorRef(kind="agent", id="test"),
                runtime_version="spec-kitty-cli",
                written_at=now_str,
                schema_version="1",
            ),
        )

        retro_path = missions_dir / MISSION_ID_COMPLETED / "retrospective.yaml"

        empty_synthesis = SynthesisResult(
            dry_run=True, planned=[], applied=[], conflicts=[], rejected=[], events_emitted=[]
        )

        with (
            patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=resolved),
            patch(
                "specify_cli.cli.commands.agent_retrospect._create_empty_retrospective_record",
                return_value=retro_path,
            ),
            patch("specify_cli.cli.commands.agent_retrospect.read_record", return_value=pydantic_record),
            patch("specify_cli.cli.commands.agent_retrospect.apply_proposals", return_value=empty_synthesis),
        ):
            result = RUNNER.invoke(
                agent_retrospect_app,
                ["synthesize", "--mission", MISSION_SLUG_COMPLETED, "--fabricate-empty", "--json"],
            )

        # Should not exit 1 with RETROSPECTIVE_RECORD_MISSING
        # May exit 0 or other code depending on synthesis result
        assert result.exit_code != 1 or "RETROSPECTIVE_RECORD_MISSING" not in result.output

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
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", "nonexistent-mission"]
            )

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
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", "nonexistent-mission", "--json"]
            )

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
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", "ambiguous"]
            )

        assert result.exit_code == 2

    def test_resolve_handle_system_exit(self, tmp_path: Path) -> None:
        """SystemExit from resolve_mission is caught and converted to exit 1."""
        repo_root, _, _ = _setup_project(tmp_path)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_mission", side_effect=SystemExit(1)),
        ):
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", "anything"]
            )

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# TestCheckMissionCompleted
# ---------------------------------------------------------------------------


class TestCheckMissionCompleted:
    """Tests for _check_mission_completed helper."""

    def test_check_completed_feature_dir_none(self, tmp_path: Path) -> None:
        """Returns [] when feature_dir is None."""
        from specify_cli.cli.commands.retrospect import _check_mission_completed

        resolved = _build_resolved_mission(
            MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir=None
        )
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

    def test_auto_commit_disabled(self, tmp_path: Path) -> None:
        """When auto_commit is False, subprocess is not called."""
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        with (
            patch("specify_cli.cli.commands.retrospect.get_auto_commit_default", return_value=False),
            patch("subprocess.run") as mock_subprocess,
        ):
            _maybe_auto_commit(tmp_path, [tmp_path / "file.yaml"], "test commit")

        mock_subprocess.assert_not_called()

    def test_auto_commit_enabled_calls_git(self, tmp_path: Path) -> None:
        """When auto_commit is True, subprocess git add and commit are called."""
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        test_file = tmp_path / "file.yaml"
        test_file.write_text("content\n", encoding="utf-8")

        with (
            patch("specify_cli.cli.commands.retrospect.get_auto_commit_default", return_value=True),
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_subprocess.return_value = MagicMock(returncode=0)
            _maybe_auto_commit(tmp_path, [test_file], "test commit message")

        assert mock_subprocess.call_count == 2
        # First call: git add
        first_args = mock_subprocess.call_args_list[0][0][0]
        assert "git" in first_args
        assert "add" in first_args
        # Second call: git commit
        second_args = mock_subprocess.call_args_list[1][0][0]
        assert "git" in second_args
        assert "commit" in second_args

    def test_auto_commit_failure_is_nonfatal(self, tmp_path: Path) -> None:
        """Subprocess failure does not propagate; _maybe_auto_commit returns None."""
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        with (
            patch("specify_cli.cli.commands.retrospect.get_auto_commit_default", return_value=True),
            patch("subprocess.run", side_effect=Exception("git failure")),
        ):
            # Should not raise
            result = _maybe_auto_commit(tmp_path, [], "test")

        assert result is None

    def test_auto_commit_raises_is_nonfatal(self, tmp_path: Path) -> None:
        """get_auto_commit_default raising is caught non-fatally."""
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        with patch(
            "specify_cli.cli.commands.retrospect.get_auto_commit_default",
            side_effect=Exception("config error"),
        ):
            # Should not raise
            _maybe_auto_commit(tmp_path, [], "test")

    def test_auto_commit_file_outside_repo_root(self, tmp_path: Path) -> None:
        """Files not relative to repo_root still work (fallback to str)."""
        from specify_cli.cli.commands.retrospect import _maybe_auto_commit

        outside_file = Path("/nonexistent/nonexistent_file.yaml")

        with (
            patch("specify_cli.cli.commands.retrospect.get_auto_commit_default", return_value=True),
            patch("subprocess.run") as mock_subprocess,
        ):
            mock_subprocess.return_value = MagicMock(returncode=0)
            _maybe_auto_commit(tmp_path, [outside_file], "test")


# ---------------------------------------------------------------------------
# Real-git helpers (auto-commit contracts)
# ---------------------------------------------------------------------------

_FANOUT_EDGE = "specify_cli.retrospective.lifecycle_events._fanout_live_work_retrospective"


def _git(repo: Path, *args: str) -> str:
    """Run real git in *repo* and return stripped stdout."""
    completed = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _init_git_repo(repo: Path, *, auto_commit: bool) -> None:
    """``git init`` *repo* with a local identity, local hooks dir and the auto-commit setting."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
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
    _write_meta(feature_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
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
    """Hold ``index.lock`` as a concurrent git process would; returns git's error fragment."""
    (repo / ".git" / "index.lock").write_text("", encoding="utf-8")
    return "index.lock"


class TestAutoCommitFailureIsSurfaced:
    """A failed auto-commit is non-fatal but never silent (the operator must commit by hand)."""

    @pytest.mark.parametrize(
        "break_git",
        [_reject_every_commit, _lock_the_index],
        ids=["commit-rejected-by-hook", "add-blocked-by-index-lock"],
    )
    def test_create_warns_on_stderr_and_keeps_json_parseable_when_auto_commit_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, break_git: Any) -> None:
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
        # ... but nothing was committed, and stderr says so, naming git's own failure.
        assert _git(repo, "rev-parse", "HEAD") == head_before
        warning = strip_ansi(result.stderr)
        assert "auto-commit failed" in warning
        assert git_error in warning
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
# TestCreateCmdErrorPaths
# ---------------------------------------------------------------------------


class TestCreateCmdErrorPaths:
    """Tests for create_cmd error branches not yet covered."""

    def test_create_project_root_not_found(self, tmp_path: Path) -> None:
        """Exits 1 when project root cannot be located."""
        with patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=None):
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", "anything", "--json"]
            )

        assert result.exit_code == 1

    def test_create_policy_resolution_error_json(self, tmp_path: Path) -> None:
        """POLICY_RESOLUTION_ERROR in JSON mode."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.retrospective.policy import PolicyResolutionError
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch(
                "specify_cli.cli.commands.retrospect.resolve_policy",
                side_effect=PolicyResolutionError("config.yaml", "invalid key", "bad value"),
            ),
        ):
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED, "--json"]
            )

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["code"] == "POLICY_RESOLUTION_ERROR"
        assert data["result"] == "blocked"

    def test_create_policy_resolution_error_non_json(self, tmp_path: Path) -> None:
        """POLICY_RESOLUTION_ERROR in non-JSON mode writes text error."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.retrospective.policy import PolicyResolutionError
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch(
                "specify_cli.cli.commands.retrospect.resolve_policy",
                side_effect=PolicyResolutionError("config.yaml", "invalid key", "bad value"),
            ),
        ):
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED]
            )

        assert result.exit_code == 1
        assert "POLICY_RESOLUTION_ERROR" in result.output

    def test_create_generator_file_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError from generator exits 1 with appropriate message."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch(
                "specify_cli.cli.commands.retrospect.generate_retrospective",
                side_effect=FileNotFoundError("missing artifact"),
            ),
        ):
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED]
            )

        assert result.exit_code == 1
        assert "missing artifact" in result.output or "Could not find" in result.output

    def test_create_generator_generic_exception(self, tmp_path: Path) -> None:
        """Generic exception from generator exits 1."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch(
                "specify_cli.cli.commands.retrospect.generate_retrospective",
                side_effect=RuntimeError("generator crashed"),
            ),
        ):
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED]
            )

        assert result.exit_code == 1
        assert "generator crashed" in result.output or "Generator failed" in result.output

    def test_create_write_gen_record_generic_exception(self, tmp_path: Path) -> None:
        """Generic exception from write_gen_record exits 1."""
        repo_root, _, _ = _setup_project(tmp_path)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        mock_policy = MagicMock(spec=RetrospectivePolicy)
        gen_record = _make_minimal_gen_record()

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch(
                "specify_cli.cli.commands.retrospect.write_gen_record",
                side_effect=OSError("disk full"),
            ),
        ):
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED]
            )

        assert result.exit_code == 1

    def test_create_record_exists_non_json(self, tmp_path: Path) -> None:
        """RETROSPECTIVE_RECORD_EXISTS non-JSON mode writes text error."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        from specify_cli.retrospective.writer import RecordExistsError
        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED)
        mock_policy = MagicMock(spec=RetrospectivePolicy)
        gen_record = _make_minimal_gen_record()
        existing_path = missions_dir / MISSION_ID_COMPLETED / "retrospective.yaml"

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect._resolve_handle", return_value=resolved),
            patch("specify_cli.cli.commands.retrospect._check_mission_completed", return_value=[]),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch(
                "specify_cli.cli.commands.retrospect.write_gen_record",
                side_effect=RecordExistsError(existing_path),
            ),
        ):
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", MISSION_SLUG_COMPLETED]
            )

        assert result.exit_code == 1
        assert "RETROSPECTIVE_RECORD_EXISTS" in result.output

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
            result = RUNNER.invoke(
                retrospect_app, ["create", "--mission", MISSION_SLUG_OPEN]
            )

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

    def test_discover_missions_skips_non_dirs(self, tmp_path: Path) -> None:
        """Skips files in missions directory."""
        from specify_cli.cli.commands.retrospect import _discover_missions_for_backfill

        missions_root = tmp_path / ".kittify" / "missions"
        missions_root.mkdir(parents=True)
        # Create a file (not a directory)
        (missions_root / "not-a-dir.txt").write_text("file", encoding="utf-8")

        now = now_utc()
        result = _discover_missions_for_backfill(tmp_path, now - timedelta(days=30), now, None)
        # Should not crash; file is silently skipped
        assert isinstance(result, list)

    def test_discover_missions_unstattable_entry_is_not_silently_skipped(
        self, tmp_path: Path
    ) -> None:
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
        (dir_entry / "meta.json").write_text(
            json.dumps({"some_other_field": "value"}), encoding="utf-8"
        )

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
            json.dumps({
                "mission_id": MISSION_ID_COMPLETED,
                "mission_slug": MISSION_SLUG_COMPLETED,
            }),
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
            json.dumps({
                "mission_id": MISSION_ID_COMPLETED,
                "mission_slug": MISSION_SLUG_COMPLETED,
                "completed_at": "not-a-date",
            }),
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

    def test_backfill_process_candidate_real_run_success(self, tmp_path: Path) -> None:
        """Real backfill run invokes generator and writes record."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        gen_record = _make_minimal_gen_record()
        written_path = mission_dir / "retrospective.yaml"

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch("specify_cli.cli.commands.retrospect.write_gen_record", return_value=written_path),
            patch("specify_cli.cli.commands.retrospect.emit_captured", return_value=None),
            patch("specify_cli.cli.commands.retrospect._maybe_auto_commit"),
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["result"] == "success"
        assert data["created"] >= 1

    def test_backfill_process_candidate_file_not_found(self, tmp_path: Path) -> None:
        """FileNotFoundError in _process_candidate is added to failed list."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch(
                "specify_cli.cli.commands.retrospect.generate_retrospective",
                side_effect=FileNotFoundError("mission spec.md missing"),
            ),
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["failed"]) >= 1
        assert data["failed"][0]["failure_category"] == "missing_artifacts"

    def test_backfill_process_candidate_generic_exception(self, tmp_path: Path) -> None:
        """Generic exception in _process_candidate is added to failed list."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch(
                "specify_cli.cli.commands.retrospect.generate_retrospective",
                side_effect=RuntimeError("crash"),
            ),
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["failed"]) >= 1
        assert data["failed"][0]["failure_category"] == "generator_exception"

    def test_backfill_emit_failures_flag(self, tmp_path: Path) -> None:
        """--emit-failures causes emit_capture_failed to be called on failure."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch(
                "specify_cli.cli.commands.retrospect.generate_retrospective",
                side_effect=FileNotFoundError("missing"),
            ),
            patch("specify_cli.cli.commands.retrospect.emit_capture_failed", return_value=None) as mock_emit_failed,
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--emit-failures", "--json"])

        assert result.exit_code == 0
        # emit_capture_failed should have been called for the failure
        mock_emit_failed.assert_called()

    def test_backfill_no_json_rich_output(self, tmp_path: Path) -> None:
        """Non-JSON backfill uses progress bar path (Rich output)."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        gen_record = _make_minimal_gen_record()
        written_path = mission_dir / "retrospective.yaml"

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch("specify_cli.cli.commands.retrospect.write_gen_record", return_value=written_path),
            patch("specify_cli.cli.commands.retrospect.emit_captured", return_value=None),
            patch("specify_cli.cli.commands.retrospect._maybe_auto_commit"),
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill"])

        assert result.exit_code == 0
        # Should produce some output
        assert len(result.output) > 0

    def test_backfill_no_json_with_failures_shows_failure_list(self, tmp_path: Path) -> None:
        """Non-JSON backfill with failures prints failure details."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch(
                "specify_cli.cli.commands.retrospect.generate_retrospective",
                side_effect=RuntimeError("crash"),
            ),
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill"])

        assert result.exit_code == 0
        # Output should contain failure info
        output = result.output
        assert "Failures" in output or "failure" in output.lower() or "crash" in output


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

    def test_summary_unstattable_mission_candidate_is_not_silently_skipped(
        self, tmp_path: Path
    ) -> None:
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

        assert result.exit_code == 2, (
            "an unstattable mission candidate must not silently produce a "
            f"successful, misleadingly-complete summary: {result.output!r}"
        )
        assert "I/O error reading corpus" in strip_ansi(result.output), (
            f"expected the actionable I/O-error message, got: {result.output!r}"
        )

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
            json.dumps({
                "mission_id": MISSION_ID_COMPLETED,
                "mission_slug": MISSION_SLUG_COMPLETED,
                "completed_at": "2026-05-01T10:00:00",  # no tzinfo
            }),
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

    def test_backfill_process_candidate_record_exists_error(self, tmp_path: Path) -> None:
        """RecordExistsError from write_gen_record in backfill adds to skipped."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        gen_record = _make_minimal_gen_record()
        existing_path = mission_dir / "retrospective.yaml"

        from specify_cli.retrospective.policy import RetrospectivePolicy
        from specify_cli.retrospective.writer import RecordExistsError as WriterRecordExistsError
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch("specify_cli.cli.commands.retrospect.generate_retrospective", return_value=gen_record),
            patch(
                "specify_cli.cli.commands.retrospect.write_gen_record",
                side_effect=WriterRecordExistsError(existing_path),
            ),
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        skipped = data["skipped"]
        assert any(s.get("reason") == "already_exists" for s in skipped)

    def test_backfill_generic_exception_with_emit_failures(self, tmp_path: Path) -> None:
        """Generic exception + --emit-failures calls emit_capture_failed for generic category."""
        repo_root, missions_dir, _ = _setup_project(tmp_path)

        now = now_utc()
        completed_at = (now - timedelta(days=5)).isoformat()
        mission_dir = missions_dir / MISSION_ID_COMPLETED
        _write_meta(mission_dir, MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, completed_at=completed_at)

        from specify_cli.retrospective.policy import RetrospectivePolicy
        mock_policy = MagicMock(spec=RetrospectivePolicy)

        with (
            patch("specify_cli.cli.commands.retrospect.locate_project_root", return_value=repo_root),
            patch("specify_cli.cli.commands.retrospect.resolve_policy", return_value=(mock_policy, {})),
            patch(
                "specify_cli.cli.commands.retrospect.generate_retrospective",
                side_effect=RuntimeError("crash"),
            ),
            patch(
                "specify_cli.cli.commands.retrospect.emit_capture_failed",
                return_value=None,
            ) as mock_emit_failed,
        ):
            result = RUNNER.invoke(retrospect_app, ["backfill", "--emit-failures", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["failed"]) >= 1
        assert data["failed"][0]["failure_category"] == "generator_exception"
        mock_emit_failed.assert_called()

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

    def test_fabricate_empty_writes_synthesize_fabricate_provenance_to_disk(
        self, tmp_path: Path
    ) -> None:
        """--fabricate-empty: real writer path writes provenance.kind=synthesize_fabricate on disk.

        This test was MISSING before cycle-2 fix: the old test patched
        _create_empty_retrospective_record so the actual write was never exercised.
        Now we call the real function and assert the YAML on disk.
        """
        import yaml as _yaml
        from specify_cli.doctrine_synthesizer import SynthesisResult

        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)
        feature_dir = self._make_feature_dir(kitty_specs_dir)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)

        empty_synthesis = SynthesisResult(
            dry_run=True, planned=[], applied=[], conflicts=[], rejected=[], events_emitted=[]
        )

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
        assert not (missions_dir / MISSION_ID_COMPLETED / "retrospective.yaml").exists(), (
            "record must NOT be written to the gitignored .kittify/missions/ tree"
        )

        # Read back the YAML and verify provenance.kind
        raw = _yaml.safe_load(retro_path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict), "retrospective.yaml must be a YAML mapping"
        provenance = raw.get("provenance", {})
        assert provenance.get("kind") == "synthesize_fabricate", (
            f"provenance.kind MUST be 'synthesize_fabricate', got {provenance.get('kind')!r}"
        )
        assert raw.get("findings_status") == "ran_no_findings", (
            f"findings_status MUST be 'ran_no_findings', got {raw.get('findings_status')!r}"
        )

    def test_fabricate_empty_emits_captured_event_with_explicit_create_provenance_kind(
        self, tmp_path: Path
    ) -> None:
        """The RetrospectiveCaptured event emitted has provenance_kind='explicit_create'.

        The event's provenance_kind is distinct from the record's provenance.kind per contract.
        """
        import json as _json
        from specify_cli.doctrine_synthesizer import SynthesisResult

        repo_root, missions_dir, kitty_specs_dir = _setup_project(tmp_path)
        feature_dir = self._make_feature_dir(kitty_specs_dir)

        resolved = _build_resolved_mission(MISSION_ID_COMPLETED, MISSION_SLUG_COMPLETED, feature_dir)
        empty_synthesis = SynthesisResult(
            dry_run=True, planned=[], applied=[], conflicts=[], rejected=[], events_emitted=[]
        )

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
            raw_lines = [
                line.strip()
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            all_events = []
            for raw_line in raw_lines:
                try:
                    all_events.append(_json.loads(raw_line))
                except _json.JSONDecodeError:
                    continue
            captured_events = [e for e in all_events if e.get("type") == "RetrospectiveCaptured"]
            if captured_events:
                for evt in captured_events:
                    assert evt.get("provenance_kind") == "explicit_create", (
                        f"Event provenance_kind MUST be 'explicit_create', got {evt.get('provenance_kind')!r}"
                    )

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
        assert events_path.exists(), (
            "status.events.jsonl must exist after --emit-skipped (event must be written)"
        )
        raw_lines = [
            line.strip()
            for line in events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        all_events = [_json.loads(raw) for raw in raw_lines]
        skip_events = [e for e in all_events if e.get("type") == "RetrospectiveSkipped"]
        assert len(skip_events) >= 1, (
            f"Expected at least 1 RetrospectiveSkipped event in status.events.jsonl, "
            f"found {len(skip_events)}. All events: {all_events}"
        )
        # Verify the skip_reason is structured
        for evt in skip_events:
            assert evt.get("skip_reason", "").startswith("backfill_skip:"), (
                f"skip_reason must start with 'backfill_skip:', got {evt.get('skip_reason')!r}"
            )

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
            raw_lines = [
                line.strip()
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            all_events = [_json2.loads(raw) for raw in raw_lines]
            skip_events = [e for e in all_events if e.get("type") == "RetrospectiveSkipped"]
            assert len(skip_events) == 0, (
                "Without --emit-skipped, no RetrospectiveSkipped events should be written"
            )

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
            raw_lines = [
                line.strip()
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            all_events = [_json3.loads(raw) for raw in raw_lines]
            skip_events = [e for e in all_events if e.get("type") == "RetrospectiveSkipped"]
            assert len(skip_events) == 0, (
                "--dry-run + --emit-skipped must NOT emit events"
            )
