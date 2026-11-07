"""Focused tests for the private helpers behind ``resolve_status_surface_with_anchor``.

The ``CoordState.EMPTY`` helper (``_empty_coord_surface``, the loud repository-root fallback)
was removed in Mission lane-worktree-model-hardening WP05: the one read door
(``specify_cli.status.read_surface``) now reads the committed coordination branch for an
empty coordination worktree, or takes the declared pre-seed fallback
(``tests/status/test_read_surface_door.py``). The ``meta is None`` arm moved into the door's
decision and is pinned here at the unit level.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.read_surface import _meta_unreadable_decision


class TestMetaUnreadableFallback:
    """``_meta_unreadable_decision`` — the ``meta is None`` arm, now decided by the read door (WP05)."""

    def test_prefers_primary_dir_when_it_exists(self, tmp_path: Path) -> None:
        primary_dir = tmp_path / "kitty-specs" / "demo-mission"
        primary_dir.mkdir(parents=True)
        feature_dir = tmp_path / ".worktrees" / "demo-mission-coord" / "kitty-specs" / "demo-mission"

        surface = _meta_unreadable_decision(tmp_path, "demo-mission", primary_dir, feature_dir)

        assert surface.primary_anchor == primary_dir
        assert surface.legacy_path == primary_dir / "status.events.jsonl"

    def test_falls_back_to_feature_dir_when_primary_missing(self, tmp_path: Path) -> None:
        primary_dir = tmp_path / "kitty-specs" / "demo-mission"
        feature_dir = tmp_path / ".worktrees" / "demo-mission-coord" / "kitty-specs" / "demo-mission"
        feature_dir.mkdir(parents=True)

        surface = _meta_unreadable_decision(tmp_path, "demo-mission", primary_dir, feature_dir)

        assert surface.primary_anchor == feature_dir
        assert surface.legacy_path == feature_dir / "status.events.jsonl"

    def test_raises_file_not_found_when_neither_exists(self, tmp_path: Path) -> None:
        primary_dir = tmp_path / "kitty-specs" / "demo-mission"
        feature_dir = tmp_path / ".worktrees" / "demo-mission-coord" / "kitty-specs" / "demo-mission"

        with pytest.raises(FileNotFoundError, match="demo-mission"):
            _meta_unreadable_decision(tmp_path, "demo-mission", primary_dir, feature_dir)
