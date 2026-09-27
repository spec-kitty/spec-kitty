"""Tests for specify_cli.status.views — derived view generation.

Verifies that views.py generates correct output-only artefacts from the
event log. Views are never authoritative (event log is sole authority).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import TransitionRequest
from specify_cli.status.reducer import materialize
from specify_cli.status.views import (
    BOARD_SUMMARY_FILENAME,
    generate_status_view,
    write_derived_views,
)

pytestmark = pytest.mark.fast

_SLUG = "034-test-feature"


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    """Create a minimal feature directory with tasks/."""
    fd = tmp_path / "kitty-specs" / _SLUG
    (fd / "tasks").mkdir(parents=True)
    return fd


class TestGenerateStatusView:
    def test_empty_event_log_returns_empty_snapshot(self, feature_dir: Path) -> None:
        """generate_status_view on empty feature returns empty snapshot dict."""
        result = generate_status_view(feature_dir)
        assert isinstance(result, dict)
        assert result.get("work_packages", {}) == {}

    def test_returns_snapshot_after_events(self, feature_dir: Path, seed_to_planned: Callable) -> None:
        """generate_status_view reflects emitted transitions."""
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        result = generate_status_view(feature_dir)
        wps = result.get("work_packages", {})
        assert "WP01" in wps
        assert wps["WP01"]["lane"] == "claimed"

    def test_snapshot_matches_materialize(self, feature_dir: Path, seed_to_planned: Callable) -> None:
        """generate_status_view result matches materialize().to_dict()."""
        seed_to_planned(feature_dir, "WP02", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP02",
                to_lane="claimed",
                actor="agent-2",
            )
        )
        view_result = generate_status_view(feature_dir)
        materialize_result = materialize(feature_dir).to_dict()
        assert view_result["work_packages"] == materialize_result["work_packages"]


class TestWriteDerivedViews:
    def test_writes_status_json(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        """write_derived_views produces status.json."""
        derived_dir = tmp_path / "derived"
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        write_derived_views(feature_dir, derived_dir)
        status_file = derived_dir / _SLUG / "status.json"
        assert status_file.exists()
        data = json.loads(status_file.read_text())
        assert "work_packages" in data

    def test_writes_board_summary_json(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        """write_derived_views produces board-summary.json."""
        derived_dir = tmp_path / "derived"
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        write_derived_views(feature_dir, derived_dir)
        board_file = derived_dir / _SLUG / BOARD_SUMMARY_FILENAME
        assert board_file.exists()
        data = json.loads(board_file.read_text())
        assert "lanes" in data
        assert "summary" in data

    def test_board_summary_lanes_match_snapshot(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        """Board summary lanes match the event log snapshot."""
        derived_dir = tmp_path / "derived"
        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        seed_to_planned(feature_dir, "WP02", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP02",
                to_lane="claimed",
                actor="agent-1",
            )
        )
        write_derived_views(feature_dir, derived_dir)
        board_file = derived_dir / _SLUG / BOARD_SUMMARY_FILENAME
        data = json.loads(board_file.read_text())
        claimed_wps = data["lanes"].get("claimed", [])
        assert "WP01" in claimed_wps
        assert "WP02" in claimed_wps

    def test_creates_output_directory(self, feature_dir: Path, tmp_path: Path) -> None:
        """write_derived_views creates the output directory if missing."""
        derived_dir = tmp_path / "does_not_exist" / "derived"
        write_derived_views(feature_dir, derived_dir)
        assert (derived_dir / _SLUG).exists()

    def test_atomic_write_no_partial_files_on_success(self, feature_dir: Path, tmp_path: Path) -> None:
        """No .tmp files remain after successful write."""
        derived_dir = tmp_path / "derived"
        write_derived_views(feature_dir, derived_dir)
        feature_out = derived_dir / _SLUG
        tmp_files = list(feature_out.glob("*.tmp"))
        assert tmp_files == [], f"Unexpected .tmp files: {tmp_files}"


class TestEmitHasNoLegacyBridge:
    """Verify emit.py pipeline has no dual-write after WP05."""

    def test_emit_does_not_write_frontmatter(self, feature_dir: Path, tmp_path: Path, seed_to_planned: Callable) -> None:
        """emit_status_transition must not write lane to WP frontmatter.

        The event log is the sole authority. Frontmatter writes were
        removed in WP05.
        """
        # Create a WP file with no lane field
        wp_file = feature_dir / "tasks" / "WP01.md"
        wp_file.write_text(
            "---\nwork_package_id: WP01\ntitle: Test WP\n---\n\n## Content\n",
            encoding="utf-8",
        )

        seed_to_planned(feature_dir, "WP01", slug=_SLUG)
        emit_status_transition(
            TransitionRequest(
                feature_dir=feature_dir,
                mission_slug=_SLUG,
                wp_id="WP01",
                to_lane="claimed",
                actor="agent-1",
            )
        )

        # WP file must NOT have lane field written
        content = wp_file.read_text(encoding="utf-8")
        assert "lane:" not in content, "emit_status_transition must not write lane: to WP frontmatter"


def test_materialize_if_stale_uses_feature_dir_name_for_derived_paths(feature_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.status import views as views_module
    from specify_cli.status import progress as progress_module

    calls: list[tuple[str, Path]] = []
    seen_snapshots: list[object | None] = []

    def _record_write(fd: Path, dd: Path, *, snapshot: object | None = None) -> None:
        calls.append(("write", dd))
        seen_snapshots.append(snapshot)

    def _record_progress(fd: Path, dd: Path, *, snapshot: object | None = None) -> None:
        calls.append(("progress", dd))
        seen_snapshots.append(snapshot)

    def _record_lifecycle(fd: Path, dd: Path, *, snapshot: object | None = None) -> None:
        calls.append(("lifecycle", dd))
        seen_snapshots.append(snapshot)

    snapshot = materialize(feature_dir)
    monkeypatch.setattr(views_module, "write_derived_views", _record_write)
    monkeypatch.setattr(progress_module, "generate_progress_json", _record_progress)
    monkeypatch.setattr(views_module, "generate_lifecycle_json", _record_lifecycle)
    monkeypatch.setattr(views_module, "materialize", lambda _: snapshot)
    monkeypatch.setattr(views_module, "materialize_snapshot", lambda _: snapshot)

    result = views_module.materialize_if_stale(feature_dir, tmp_path)

    expected_derived = tmp_path / ".kittify" / "derived"
    assert calls == [
        ("write", expected_derived),
        ("progress", expected_derived),
        ("lifecycle", expected_derived),
    ]
    assert result.mission_slug == snapshot.mission_slug
    # N4 (review cycle 1): all three generators must receive the SAME
    # write-free snapshot instance built once by materialize_if_stale, not
    # None (the "fall back to materialize() internally" default) and not
    # three independently-built snapshots.
    assert seen_snapshots == [snapshot, snapshot, snapshot]
