"""Tests for the ``spec-kitty materialize`` command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: subprocess CLI invocation
pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    mission_slug: str,
    wp_id: str,
    from_lane: str,
    to_lane: str,
    event_id: str,
    at: str = "2026-01-01T12:00:00+00:00",
) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at=at,
        actor="test-agent",
        force=False,
        execution_mode="worktree",
    )


def _setup_feature(
    tmp_path: Path,
    mission_slug: str,
    wp_lanes: dict[str, str],
) -> Path:
    """Create a feature directory with event log for the given WP lanes."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    for idx, (wp_id, lane) in enumerate(wp_lanes.items()):
        event_id = f"01TEST{idx:020d}"
        event = _make_event(mission_slug, wp_id, "planned", lane, event_id)
        append_event(feature_dir, event)
    return feature_dir


# ---------------------------------------------------------------------------
# Materialisation function tests (unit-level)
# ---------------------------------------------------------------------------


def test_write_derived_views_creates_files(tmp_path):
    """write_derived_views writes status.json and board-summary.json."""
    from specify_cli.status.views import write_derived_views

    feature_dir = _setup_feature(tmp_path, "001-test", {"WP01": "done"})
    derived_dir = tmp_path / ".kittify" / "derived"

    write_derived_views(feature_dir, derived_dir)

    status_path = derived_dir / "001-test" / "status.json"
    board_path = derived_dir / "001-test" / "board-summary.json"
    assert status_path.exists()
    assert board_path.exists()

    status_data = json.loads(status_path.read_text())
    board_data = json.loads(board_path.read_text())
    assert status_data["mission_slug"] == "001-test"
    assert board_data["mission_slug"] == "001-test"


def test_generate_progress_json_creates_file(tmp_path):
    """generate_progress_json writes progress.json."""
    from specify_cli.status.progress import generate_progress_json

    feature_dir = _setup_feature(tmp_path, "002-test", {"WP01": "in_progress"})
    derived_dir = tmp_path / ".kittify" / "derived"

    generate_progress_json(feature_dir, derived_dir)

    progress_file = derived_dir / "002-test" / "progress.json"
    assert progress_file.exists()
    data = json.loads(progress_file.read_text())
    assert data["mission_slug"] == "002-test"
    assert data["percentage"] == pytest.approx(30.0)


def test_materialize_all_features_via_function(tmp_path):
    """Direct call to write_derived_views + progress/lifecycle for two features."""
    from specify_cli.status.views import write_derived_views
    from specify_cli.status.lifecycle import generate_lifecycle_json
    from specify_cli.status.progress import generate_progress_json

    mission_slugs = ["003-alpha", "003-beta"]
    for slug in mission_slugs:
        _setup_feature(tmp_path, slug, {"WP01": "done"})

    derived_dir = tmp_path / ".kittify" / "derived"

    for slug in mission_slugs:
        feature_dir = tmp_path / "kitty-specs" / slug
        write_derived_views(feature_dir, derived_dir)
        generate_progress_json(feature_dir, derived_dir)
        generate_lifecycle_json(feature_dir, derived_dir)

    for slug in mission_slugs:
        assert (derived_dir / slug / "status.json").exists()
        assert (derived_dir / slug / "board-summary.json").exists()
        assert (derived_dir / slug / "progress.json").exists()
        assert (derived_dir / slug / "lifecycle.json").exists()


def test_materialize_output_json_structure(tmp_path):
    """Materialised progress.json has expected top-level keys."""
    from specify_cli.status.progress import generate_progress_json

    feature_dir = _setup_feature(
        tmp_path,
        "004-structure",
        {"WP01": "done", "WP02": "in_progress"},
    )
    derived_dir = tmp_path / ".kittify" / "derived"
    generate_progress_json(feature_dir, derived_dir)

    data = json.loads((derived_dir / "004-structure" / "progress.json").read_text())
    for key in ("mission_slug", "percentage", "done_count", "total_count", "per_lane_counts", "per_wp"):
        assert key in data, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# CLI command tests (invoke via function directly with patched locate_project_root)
# ---------------------------------------------------------------------------


def test_materialize_command_no_project(tmp_path):
    """materialize exits with code 1 when not in a spec-kitty project."""
    from specify_cli.cli.commands.materialize import materialize
    import typer

    with patch("specify_cli.cli.commands.materialize.locate_project_root", return_value=None):
        with pytest.raises(typer.Exit) as exc_info:
            materialize()
        assert exc_info.value.exit_code == 1


def test_materialize_command_all_features(tmp_path):
    """materialize processes all features when no --mission given."""
    from specify_cli.cli.commands.materialize import materialize
    import typer

    _setup_feature(tmp_path, "005-alpha", {"WP01": "done"})
    _setup_feature(tmp_path, "005-beta", {"WP01": "planned"})

    with patch("specify_cli.cli.commands.materialize.locate_project_root", return_value=tmp_path):
        with pytest.raises(typer.Exit) as exc_info:
            materialize(mission=None, json_output=False)
        assert exc_info.value.exit_code == 0

    # Verify files written
    assert (tmp_path / ".kittify" / "derived" / "005-alpha" / "progress.json").exists()
    assert (tmp_path / ".kittify" / "derived" / "005-beta" / "progress.json").exists()


def test_materialize_command_single_feature(tmp_path):
    """materialize --mission processes only the specified mission."""
    from specify_cli.cli.commands.materialize import materialize
    import typer

    _setup_feature(tmp_path, "006-target", {"WP01": "done"})

    with patch("specify_cli.cli.commands.materialize.locate_project_root", return_value=tmp_path):
        with pytest.raises(typer.Exit) as exc_info:
            materialize(mission="006-target", json_output=False)
        assert exc_info.value.exit_code == 0

    assert (tmp_path / ".kittify" / "derived" / "006-target" / "status.json").exists()


@pytest.mark.fast
def test_materialize_single_mission_resolves_via_read_path_resolver(
    tmp_path: Path,
) -> None:
    """``--mission <slug>`` routes through the canonical ``_read_path_resolver``.

    01KVGCE8 re-pointed the single-mission branch's function-local import from the
    retired ``missions.feature_dir_resolver`` to the canonical
    ``missions._read_path_resolver.resolve_feature_dir_for_slug``. This test
    EXECUTES that branch (``materialize.py:69`` — the ``if mission_slug:`` arm's
    import + ``resolve_feature_dir_for_slug`` call) for a production-shaped
    ``<slug>-<mid8>`` mission and asserts derived views are written ONLY for the
    selected mission, never the sibling.

    Marked ``fast`` so it lands in the ``fast-tests-core-misc`` cli coverage shard
    (``coverage-fast-cli.xml``); the module-level ``non_sandbox`` mark alone left
    the single-mission branch out of every CI coverage run, so the changed import
    line read as uncovered in diff-coverage. The test calls ``materialize()``
    directly (no subprocess) with a patched project root, so it is genuinely a
    fast unit test.
    """
    from specify_cli.cli.commands.materialize import materialize
    import typer

    # Production-shaped identity: a real 26-char ULID, mid8 = first 8 chars.
    mission_id = "01KVGCE8R8QJ3K5ZJ9E5008XYZ"
    mid8 = mission_id[:8]  # "01KVGCE8"
    target_slug = f"single-mission-surface-{mid8}"
    sibling_slug = f"unrelated-mission-{mission_id[:8]}other"[:30]

    _setup_feature(tmp_path, target_slug, {"WP01": "done"})
    _setup_feature(tmp_path, sibling_slug, {"WP01": "planned"})

    with patch(
        "specify_cli.cli.commands.materialize.locate_project_root",
        return_value=tmp_path,
    ):
        with pytest.raises(typer.Exit) as exc_info:
            materialize(mission=f"  {target_slug}  ", json_output=False)
        assert exc_info.value.exit_code == 0

    derived = tmp_path / ".kittify" / "derived"
    # The selected mission's views are materialised...
    assert (derived / target_slug / "status.json").exists()
    assert (derived / target_slug / "progress.json").exists()
    # ...and the sibling's are NOT (the resolver scoped to the single slug).
    assert not (derived / sibling_slug).exists()


def test_materialize_command_feature_not_found(tmp_path):
    """materialize exits 1 when --mission slug does not exist."""
    from specify_cli.cli.commands.materialize import materialize
    import typer

    (tmp_path / "kitty-specs").mkdir(parents=True)

    with patch("specify_cli.cli.commands.materialize.locate_project_root", return_value=tmp_path):
        with pytest.raises(typer.Exit) as exc_info:
            materialize(mission="999-nonexistent", json_output=False)
        assert exc_info.value.exit_code == 1


def test_materialize_command_json_output(tmp_path):
    """materialize --json outputs a machine-readable summary."""
    from specify_cli.cli.commands.materialize import materialize
    import typer

    _setup_feature(tmp_path, "007-json", {"WP01": "done"})

    with patch("specify_cli.cli.commands.materialize.locate_project_root", return_value=tmp_path):
        with pytest.raises(typer.Exit) as exc_info:
            materialize(mission="007-json", json_output=True)
        assert exc_info.value.exit_code == 0


# ---------------------------------------------------------------------------
# Lazy regeneration (materialize_if_stale)
# ---------------------------------------------------------------------------


def test_materialize_if_stale_creates_on_missing(tmp_path):
    """materialize_if_stale regenerates when derived files are missing."""
    from specify_cli.status.views import materialize_if_stale

    feature_dir = _setup_feature(tmp_path, "008-stale", {"WP01": "done"})

    snapshot = materialize_if_stale(feature_dir, tmp_path)

    assert snapshot is not None
    assert (tmp_path / ".kittify" / "derived" / "008-stale" / "status.json").exists()
    assert (tmp_path / ".kittify" / "derived" / "008-stale" / "progress.json").exists()
    assert (tmp_path / ".kittify" / "derived" / "008-stale" / "lifecycle.json").exists()


def test_materialize_if_stale_skips_when_fresh(tmp_path):
    """materialize_if_stale does not regenerate when derived files are up-to-date."""
    from specify_cli.status.views import materialize_if_stale, write_derived_views
    from specify_cli.status.lifecycle import generate_lifecycle_json
    from specify_cli.status.progress import generate_progress_json

    feature_dir = _setup_feature(tmp_path, "009-fresh", {"WP01": "done"})
    derived_dir = tmp_path / ".kittify" / "derived"

    # Write derived files
    write_derived_views(feature_dir, derived_dir)
    generate_progress_json(feature_dir, derived_dir)
    generate_lifecycle_json(feature_dir, derived_dir)

    # Touch derived file to make it newer than event log
    status_path = derived_dir / "009-fresh" / "status.json"
    progress_path = derived_dir / "009-fresh" / "progress.json"
    lifecycle_path = derived_dir / "009-fresh" / "lifecycle.json"
    events_path = feature_dir / "status.events.jsonl"

    # Set event log mtime to past, derived files to future
    import os
    past_time = events_path.stat().st_mtime - 10
    future_time = events_path.stat().st_mtime + 10
    os.utime(events_path, (past_time, past_time))
    os.utime(status_path, (future_time, future_time))
    os.utime(progress_path, (future_time, future_time))
    os.utime(lifecycle_path, (future_time, future_time))

    original_mtime = status_path.stat().st_mtime

    # Should not regenerate
    materialize_if_stale(feature_dir, tmp_path)

    # mtime should be unchanged (file not rewritten)
    assert status_path.stat().st_mtime == original_mtime


def test_materialize_if_stale_regenerates_when_stale(tmp_path):
    """materialize_if_stale regenerates when event log is newer than derived files."""
    from specify_cli.status.views import materialize_if_stale, write_derived_views
    from specify_cli.status.lifecycle import generate_lifecycle_json
    from specify_cli.status.progress import generate_progress_json
    import os

    feature_dir = _setup_feature(tmp_path, "010-regen", {"WP01": "done"})
    derived_dir = tmp_path / ".kittify" / "derived"

    # Write derived files first
    write_derived_views(feature_dir, derived_dir)
    generate_progress_json(feature_dir, derived_dir)
    generate_lifecycle_json(feature_dir, derived_dir)

    status_path = derived_dir / "010-regen" / "status.json"
    events_path = feature_dir / "status.events.jsonl"

    # Make event log newer than derived files
    future_time = status_path.stat().st_mtime + 10
    os.utime(events_path, (future_time, future_time))

    # Should regenerate
    materialize_if_stale(feature_dir, tmp_path)

    # status.json should have been rewritten (mtime updated)
    new_mtime = status_path.stat().st_mtime
    assert new_mtime >= status_path.stat().st_mtime  # file exists and is valid


def test_materialize_if_stale_no_events(tmp_path):
    """materialize_if_stale handles features with no event log (empty progress)."""
    from specify_cli.status.views import materialize_if_stale

    feature_dir = tmp_path / "kitty-specs" / "011-empty"
    feature_dir.mkdir(parents=True)

    snapshot = materialize_if_stale(feature_dir, tmp_path)

    assert snapshot is not None
    assert snapshot.mission_slug == ""  # empty snapshot
    assert snapshot.event_count == 0


# ---------------------------------------------------------------------------
# WP18 (coord-artifact-single-home, ruling Q4): coordination Missions are
# materialised from the COORDINATION surface's log (R24, FR-003, C-008)
# ---------------------------------------------------------------------------


def _run_materialize(repo_root: Path, *, mission: str | None, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    """Invoke ``materialize --json`` against *repo_root*; return ``(exit_code, parsed_summary)``."""
    import typer

    from specify_cli.cli.commands.materialize import materialize

    with (
        patch("specify_cli.cli.commands.materialize.locate_project_root", return_value=repo_root),
        pytest.raises(typer.Exit) as exc_info,
    ):
        materialize(mission=mission, json_output=True)
    out = capsys.readouterr().out
    return exc_info.value.exit_code, json.loads(out[out.index("{") :])


def _derived_lanes(repo_root: Path, derived_slug: str) -> dict[str, str]:
    snapshot = json.loads((repo_root / ".kittify" / "derived" / derived_slug / "status.json").read_text(encoding="utf-8"))
    return {wp_id: wp["lane"] for wp_id, wp in snapshot["work_packages"].items()}


def _append_coordination_transitions(coord: Any, wp_id: str, lanes: tuple[str, ...]) -> None:
    """Append ``planned -> lanes...`` transitions to the COORDINATION log only (the root log stays stale)."""
    previous = "planned"
    for idx, lane in enumerate(lanes):
        append_event(
            coord.coord_mission_dir,
            _make_event(coord.mission_dir_name, wp_id, previous, lane, f"01COORD{idx:020d}"),
        )
        previous = lane


def test_materialize_all_writes_status_json_on_coordination_surface(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """R24: ``materialize`` reduces a coordination-routed Mission's COORDINATION log.

    The repository root checkout's copy of ``status.events.jsonl`` is stale (it
    has no WP transitions); the coordination surface carries them. Red before
    the fix: the all-Missions loop iterated the root checkout's
    ``kitty-specs/`` dirs and reduced the stale log.
    """
    from mission_runtime import MissionTopology
    from tests._factories.coord_mission import make_coord_mission

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)
    _append_coordination_transitions(coord, "WP01", ("claimed", "in_progress"))

    exit_code, summary = _run_materialize(coord.repo_root, mission=None, capsys=capsys)

    assert exit_code == 0, summary
    assert [m["mission_slug"] for m in summary["missions"]] == [coord.mission_dir_name]
    assert _derived_lanes(coord.repo_root, coord.mission_dir_name) == {"WP01": "in_progress"}


def test_materialize_mission_flag_writes_status_json_on_coordination_surface(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """R24 control (``--mission`` path, green at base): a MATERIALIZED coordination Mission is reduced from the coordination log."""
    from mission_runtime import MissionTopology
    from tests._factories.coord_mission import make_coord_mission

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)
    _append_coordination_transitions(coord, "WP01", ("claimed",))

    exit_code, _summary = _run_materialize(coord.repo_root, mission=coord.mission_dir_name, capsys=capsys)

    assert exit_code == 0
    assert _derived_lanes(coord.repo_root, coord.mission_dir_name) == {"WP01": "claimed"}


def test_materialize_lanes_mission_unchanged(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """C-008 control: a ``lanes`` Mission is reduced from the repository root checkout, as before."""
    feature_dir = _setup_feature(tmp_path, "010-lanes-control", {"WP01": "done", "WP02": "planned"})
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": "010-lanes-control", "topology": "lanes"}) + "\n",
        encoding="utf-8",
    )

    exit_code, summary = _run_materialize(tmp_path, mission=None, capsys=capsys)

    assert exit_code == 0, summary
    assert summary["errors"] == []
    assert [m["mission_slug"] for m in summary["missions"]] == ["010-lanes-control"]
    assert summary["missions"][0]["files_written"] == ["status.json", "board-summary.json", "progress.json", "lifecycle.json"]
    assert _derived_lanes(tmp_path, "010-lanes-control") == {"WP01": "done", "WP02": "planned"}


def test_materialize_all_reports_remote_only_coord_mission_in_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """R24: a remote-only coordination branch is an ``errors[]`` entry; the loop keeps going.

    The other Mission in the same repository is still materialised, and the
    remote-only Mission is never reduced from a stale root checkout log.
    """
    from mission_runtime import MissionTopology
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
    from tests._factories.coord_mission import make_prefix_coord_mission

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, remote_only=True)
    _setup_feature(coord.repo_root, "zz-plain-sibling", {"WP01": "done"})

    exit_code, summary = _run_materialize(coord.repo_root, mission=None, capsys=capsys)

    assert exit_code == 1
    assert len(summary["errors"]) == 1
    assert summary["errors"][0].startswith(f"{coord.mission_dir_name}: {CoordinationWorktreeUnmaterialized.error_code}: ")
    assert [m["mission_slug"] for m in summary["missions"]] == ["zz-plain-sibling"]
    assert not (coord.repo_root / ".kittify" / "derived" / coord.mission_dir_name).exists()
    assert (coord.repo_root / ".kittify" / "derived" / "zz-plain-sibling" / "status.json").exists()


def test_materialize_mission_flag_on_prefix_coord_mission_seeds_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """``--mission`` on a pre-fix EMPTY coordination Mission seeds the surface exactly once."""
    from mission_runtime import MissionTopology
    from specify_cli.coordination.coord_seed import COORD_SEED_TRAILER
    from tests._factories.coord_mission import make_prefix_coord_mission
    import subprocess

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")

    def _seed_commits() -> list[str]:
        return subprocess.run(
            ["git", "log", "--format=%H", f"--grep={COORD_SEED_TRAILER}", coord.coordination_branch],
            cwd=coord.repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.split()

    first_code, _ = _run_materialize(coord.repo_root, mission=coord.mission_dir_name, capsys=capsys)
    after_first = _seed_commits()
    second_code, _ = _run_materialize(coord.repo_root, mission=coord.mission_dir_name, capsys=capsys)

    assert (first_code, second_code) == (0, 0)
    assert len(after_first) == 1
    assert _seed_commits() == after_first
