"""Unit tests for WP02: coord-aware status reads in implement.py and orchestrator_api.

T016: resolve_mission_read_path prefers coord worktree when it exists on disk.
T017: resolve_mission_read_path falls back to primary checkout when coord absent.
T018: _resolve_mission_dir (orchestrator_api) returns None when neither path exists.
T019: implement.py dependency gate uses resolved coord path (not raw repo_root/kitty-specs).
T020: mid8 extraction from slug works for slugs with 8-char ULID suffix.
T021: mid8 extraction returns empty string for legacy slugs without ULID suffix.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]
# ---------------------------------------------------------------------------
# T016 / T017: resolve_mission_read_path path selection
# ---------------------------------------------------------------------------

class TestResolveMissionReadPath:
    """Verify coord-worktree-first priority in resolve_mission_read_path."""

    def test_coord_candidate_preferred_when_exists(self, tmp_path: Path) -> None:
        """When coord worktree dir exists, resolve returns coord path (T016)."""
        from specify_cli.missions._read_path_resolver import (
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        slug = "my-feature"
        mid8 = "01KT3YBD"

        # Create coord worktree directory
        coord_mission_dir = (
            tmp_path / ".worktrees" / f"{slug}-{mid8}-coord" / "kitty-specs" / f"{slug}-{mid8}"
        )
        coord_mission_dir.mkdir(parents=True)

        result = resolve_mission_read_path(tmp_path, slug, mid8)
        assert result == coord_mission_dir

    def test_primary_checkout_fallback_when_coord_absent(self, tmp_path: Path) -> None:
        """When coord worktree absent, resolve falls back to primary checkout (T017)."""
        from specify_cli.missions._read_path_resolver import (
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        slug = "my-feature"
        mid8 = "01KT3YBD"

        # Create primary checkout directory only
        primary_mission_dir = tmp_path / "kitty-specs" / f"{slug}-{mid8}"
        primary_mission_dir.mkdir(parents=True)

        result = resolve_mission_read_path(tmp_path, slug, mid8)
        assert result == primary_mission_dir

    def test_declared_coord_topology_without_worktree_reads_primary(
        self, tmp_path: Path
    ) -> None:
        """Before coord worktree materialization, bootstrap status lives in primary."""
        from specify_cli.missions._read_path_resolver import (
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        slug = "my-feature"
        mid8 = "01KT3YBD"
        primary_mission_dir = tmp_path / "kitty-specs" / f"{slug}-{mid8}"
        primary_mission_dir.mkdir(parents=True)
        (primary_mission_dir / "meta.json").write_text(
            '{"coordination_branch":"kitty/mission-my-feature-01KT3YBD"}',
            encoding="utf-8",
        )
        (primary_mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")

        assert resolve_mission_read_path(tmp_path, slug, mid8) == primary_mission_dir

    def test_declared_coord_topology_materialized_empty_worktree_fails_closed(
        self, tmp_path: Path
    ) -> None:
        """Modern coord missions must not read primary once coord root exists."""
        from specify_cli.missions._read_path_resolver import (
            StatusReadPathNotFound,
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        slug = "my-feature"
        mid8 = "01KT3YBD"
        primary_mission_dir = tmp_path / "kitty-specs" / f"{slug}-{mid8}"
        primary_mission_dir.mkdir(parents=True)
        (primary_mission_dir / "meta.json").write_text(
            '{"coordination_branch":"kitty/mission-my-feature-01KT3YBD"}',
            encoding="utf-8",
        )
        (primary_mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")
        (tmp_path / ".worktrees" / f"{slug}-{mid8}-coord").mkdir(parents=True)

        with pytest.raises(StatusReadPathNotFound):
            resolve_mission_read_path(tmp_path, slug, mid8)

    def test_primary_returned_when_both_absent(self, tmp_path: Path) -> None:
        """When neither exists, returns primary candidate path (no error by default)."""
        from specify_cli.missions._read_path_resolver import (
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        slug = "my-feature"
        mid8 = "01KT3YBD"

        result = resolve_mission_read_path(tmp_path, slug, mid8)
        assert result == tmp_path / "kitty-specs" / f"{slug}-{mid8}"
        assert not result.exists()

    def test_require_exists_raises_when_neither_exists(self, tmp_path: Path) -> None:
        """require_exists=True raises StatusReadPathNotFound when both paths absent."""
        from specify_cli.missions._read_path_resolver import (
            StatusReadPathNotFound,
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        with pytest.raises(StatusReadPathNotFound):
            resolve_mission_read_path(tmp_path, "my-feature", "01KT3YBD", require_exists=True)

    def test_empty_mid8_skips_coord_check(self, tmp_path: Path) -> None:
        """Legacy callers with empty mid8 skip coord worktree, go to primary."""
        from specify_cli.missions._read_path_resolver import (
            _resolve_mission_read_path as resolve_mission_read_path,
        )

        slug = "legacy-feature"
        # Create primary
        primary_mission_dir = tmp_path / "kitty-specs" / slug
        primary_mission_dir.mkdir(parents=True)

        result = resolve_mission_read_path(tmp_path, slug, "")
        assert result == primary_mission_dir

    def test_runtime_bridge_uses_transitional_public_resolver(self, tmp_path: Path) -> None:
        """``spec-kitty next`` reads primary during create→first-write window."""
        from runtime.next.runtime_bridge_identity import _resolve_runtime_feature_dir

        mission_slug = "my-feature-01KT3YBD"
        primary_mission_dir = tmp_path / "kitty-specs" / mission_slug
        primary_mission_dir.mkdir(parents=True)
        (primary_mission_dir / "meta.json").write_text(
            '{"coordination_branch":"kitty/mission-my-feature-01KT3YBD"}',
            encoding="utf-8",
        )

        result = _resolve_runtime_feature_dir(tmp_path, mission_slug)
        assert result == primary_mission_dir


# ---------------------------------------------------------------------------
# T018: orchestrator_api _resolve_mission_dir returns None when absent
# ---------------------------------------------------------------------------

class TestResolveMissionDirOrchestratorApi:
    """Verify _resolve_mission_dir behaves correctly for coord and legacy missions."""

    def test_returns_none_when_neither_coord_nor_primary_exists(self, tmp_path: Path) -> None:
        """_resolve_mission_dir returns None when mission not found (T018)."""
        from specify_cli.orchestrator_api._common import _resolve_mission_dir

        result = _resolve_mission_dir(tmp_path, "nonexistent-mission-01KT3YBD")
        assert result is None

    def test_returns_coord_path_when_coord_exists(self, tmp_path: Path) -> None:
        """_resolve_mission_dir returns coord path when coord worktree present."""
        from specify_cli.orchestrator_api._common import _resolve_mission_dir

        slug = "my-feature"
        mid8 = "01KT3YBD"
        coord_mission_dir = (
            tmp_path / ".worktrees" / f"{slug}-{mid8}-coord" / "kitty-specs" / f"{slug}-{mid8}"
        )
        coord_mission_dir.mkdir(parents=True)

        result = _resolve_mission_dir(tmp_path, f"{slug}-{mid8}")
        assert result == coord_mission_dir

    def test_returns_primary_path_when_only_primary_exists(self, tmp_path: Path) -> None:
        """_resolve_mission_dir returns primary path when only primary exists."""
        from specify_cli.orchestrator_api._common import _resolve_mission_dir

        slug = "my-feature"
        mid8 = "01KT3YBD"
        primary_mission_dir = tmp_path / "kitty-specs" / f"{slug}-{mid8}"
        primary_mission_dir.mkdir(parents=True)

        result = _resolve_mission_dir(tmp_path, f"{slug}-{mid8}")
        assert result == primary_mission_dir

    def test_legacy_slug_without_mid8_uses_primary(self, tmp_path: Path) -> None:
        """Legacy slug without mid8 suffix resolves to primary checkout path."""
        from specify_cli.orchestrator_api._common import _resolve_mission_dir

        slug = "legacy-mission"
        primary_mission_dir = tmp_path / "kitty-specs" / slug
        primary_mission_dir.mkdir(parents=True)

        result = _resolve_mission_dir(tmp_path, slug)
        assert result == primary_mission_dir


# ---------------------------------------------------------------------------
# T019 / T020 / T021: mid8 extraction from mission slug
# ---------------------------------------------------------------------------

class TestMid8Extraction:
    """Verify mid8 extraction heuristic used in implement.py and tasks.py (T020, T021)."""

    @pytest.mark.parametrize("slug,expected_mid8", [
        # post-083 slug with ULID mid8 suffix (8 UPPER ALNUM chars)
        ("my-feature-01KT3YBD", "01KT3YBD"),
        ("execution-context-unification-01KT3YBD", "01KT3YBD"),
        # legacy slug — no ULID suffix
        ("legacy-feature", ""),
        ("012-old-style-mission", ""),
        # suffix present but not all-uppercase alphanumeric
        ("my-feature-abcd1234", ""),  # lowercase → not a ULID mid8
        # slug with numeric-only tail
        ("feature-12345678", "12345678"),
    ])
    def test_mid8_extraction(self, slug: str, expected_mid8: str) -> None:
        """mid8 is extracted iff tail is exactly 8 Crockford base32 chars (T020, T021)."""
        from specify_cli.lanes.branch_naming import mid8_from_slug

        assert mid8_from_slug(slug) == expected_mid8
