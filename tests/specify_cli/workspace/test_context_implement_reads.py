"""Zero-mock unit tests for the context reads implement delegates to `workspace/context.py` (FR-006).

Covers `resolve_lane_state_dir` (WP03 / #2052, absorbed from `tests/cli/commands/test_resolve_lanes_dir.py`),
`find_wp_file` and `resolve_mission_target_branch`.

Original `resolve_lane_state_dir` notes:

Verifies:
- Coord topology: returns the coord-worktree surface when the worktree and
  its mission dir are materialised and meta.json declares coordination_branch.
- Flat/legacy topology: returns the primary checkout surface when no
  coordination_branch is declared.

No ``unittest.mock`` — the point is that the function is testable with a
``tmp_path`` filesystem alone (pure path after coord-worktree materialisation).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.workspace.context import find_wp_file, resolve_lane_state_dir, resolve_mission_target_branch
from specify_cli.core.constants import KITTY_SPECS_DIR

pytestmark = pytest.mark.fast


# A Crockford base32 mid8 that ``mid8_from_slug`` will recognise as a valid
# tail when embedded in a slug (8 chars, charset [0-9A-HJKMNP-TV-Z]).
_TEST_MID8 = "01KVN754"
_COORD_BRANCH = "kitty/mission-my-mission-01KVN754"


def _write_meta(feature_dir: Path, *, coordination_branch: str | None = None) -> None:
    """Write a minimal meta.json into *feature_dir*."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_slug": feature_dir.name,
        "mission_id": f"01KVN754TY9CVJ8G10ERT{feature_dir.name[:5].upper()}",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


class TestResolveLinesDirCoordTopology:
    """Coord-worktree materialised: ``resolve_lane_state_dir`` must STILL return the
    PRIMARY surface, never the coord husk.

    ``lanes.json`` is the ``LANE_STATE`` artifact — a PRIMARY-partition kind with
    INV-5 read/write symmetry — so it resolves to the primary checkout for EVERY
    topology. This is the #3371 regression guard: WP02 writes ``lanes.json`` to
    the PRIMARY target branch, and reading it off the coordination surface (the
    pre-symmetry C-LANES-1 behaviour) broke coord-topology ``implement``.
    """

    def test_returns_primary_surface_even_when_coord_worktree_exists(self, tmp_path: Path) -> None:
        # Slug embeds the mid8 so mid8_from_slug can extract it.
        slug = f"my-mission-{_TEST_MID8}"

        # Primary checkout: meta.json declares coordination_branch.
        primary_dir = tmp_path / KITTY_SPECS_DIR / slug
        _write_meta(primary_dir, coordination_branch=_COORD_BRANCH)

        # Coord worktree materialised (would be the WRONG home for lanes.json).
        coord_worktree_root = tmp_path / ".worktrees" / f"{slug}-coord"
        coord_mission_dir = coord_worktree_root / KITTY_SPECS_DIR / slug
        coord_mission_dir.mkdir(parents=True)

        result = resolve_lane_state_dir(tmp_path, slug)

        # PRIMARY partition — the primary checkout dir, NOT the coord husk.
        assert result == primary_dir
        assert result != coord_mission_dir

    def test_lanes_dir_is_never_the_coord_husk(self, tmp_path: Path) -> None:
        slug = f"my-mission-{_TEST_MID8}"

        primary_dir = tmp_path / KITTY_SPECS_DIR / slug
        _write_meta(primary_dir, coordination_branch=_COORD_BRANCH)

        coord_mission_dir = tmp_path / ".worktrees" / f"{slug}-coord" / KITTY_SPECS_DIR / slug
        coord_mission_dir.mkdir(parents=True)

        result = resolve_lane_state_dir(tmp_path, slug)

        # The resolved lanes dir never lives under a coord worktree.
        assert ".worktrees" not in result.parts
        assert result == primary_dir


class TestResolveLinesDirFlatTopology:
    """No coord worktree: ``resolve_lane_state_dir`` must return the primary dir."""

    def test_returns_primary_when_no_coordination_branch(self, tmp_path: Path) -> None:
        # Flat slug — no mid8 tail; no coord worktree created.
        slug = "my-mission-flat"

        primary_dir = tmp_path / KITTY_SPECS_DIR / slug
        _write_meta(primary_dir)  # no coordination_branch

        result = resolve_lane_state_dir(tmp_path, slug)

        assert result == primary_dir

    def test_returns_primary_when_meta_omits_coordination_branch(self, tmp_path: Path) -> None:
        """Explicit check that a meta without coordination_branch → primary."""
        slug = "legacy-mission"

        primary_dir = tmp_path / KITTY_SPECS_DIR / slug
        _write_meta(primary_dir, coordination_branch=None)

        result = resolve_lane_state_dir(tmp_path, slug)

        assert result == primary_dir


# ---------------------------------------------------------------------------
# find_wp_file (moved from implement, FR-006)
# ---------------------------------------------------------------------------


class TestFindWpFile:
    """``find_wp_file`` resolves the authored WP prompt through the seam (PRIMARY surface)."""

    @staticmethod
    def _tasks_dir(repo: Path, slug: str) -> Path:
        tasks = repo / KITTY_SPECS_DIR / slug / "tasks"
        tasks.mkdir(parents=True)
        return tasks

    def test_valid_id_returns_the_matching_prompt(self, tmp_path: Path) -> None:
        tasks = self._tasks_dir(tmp_path, "my-mission")
        wp_file = tasks / "WP01-setup.md"
        wp_file.write_text("# WP01", encoding="utf-8")
        (tasks / "WP02-other.md").write_text("# WP02", encoding="utf-8")

        assert find_wp_file(tmp_path, "my-mission", "WP01") == wp_file

    def test_id_is_stripped_and_case_insensitive(self, tmp_path: Path) -> None:
        tasks = self._tasks_dir(tmp_path, "my-mission")
        wp_file = tasks / "WP03.md"
        wp_file.write_text("# WP03", encoding="utf-8")

        assert find_wp_file(tmp_path, "my-mission", "  wp03 ") == wp_file

    def test_invalid_id_names_the_expected_shape(self, tmp_path: Path) -> None:
        self._tasks_dir(tmp_path, "my-mission")

        with pytest.raises(FileNotFoundError, match=r"Invalid work package ID: WP1\. Expected format WP## \(for example, WP01\)\."):
            find_wp_file(tmp_path, "my-mission", "WP1")

    def test_missing_tasks_dir_is_reported(self, tmp_path: Path) -> None:
        (tmp_path / KITTY_SPECS_DIR / "my-mission").mkdir(parents=True)

        with pytest.raises(FileNotFoundError, match="Tasks directory not found"):
            find_wp_file(tmp_path, "my-mission", "WP01")

    def test_no_matching_prompt_is_reported(self, tmp_path: Path) -> None:
        tasks = self._tasks_dir(tmp_path, "my-mission")
        (tasks / "WP02-other.md").write_text("# WP02", encoding="utf-8")

        with pytest.raises(FileNotFoundError, match="WP file not found for WP01"):
            find_wp_file(tmp_path, "my-mission", "WP01")

    def test_multiple_matches_return_the_first_sorted(self, tmp_path: Path) -> None:
        tasks = self._tasks_dir(tmp_path, "my-mission")
        (tasks / "WP01-b.md").write_text("b", encoding="utf-8")
        first = tasks / "WP01-a.md"
        first.write_text("a", encoding="utf-8")

        assert find_wp_file(tmp_path, "my-mission", "WP01") == first


# ---------------------------------------------------------------------------
# resolve_mission_target_branch (moved from implement, FR-006)
# ---------------------------------------------------------------------------


class TestResolveMissionTargetBranch:
    def test_returns_the_target_branch_recorded_in_meta(self, tmp_path: Path) -> None:
        subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
        slug = "my-mission"
        feature_dir = tmp_path / KITTY_SPECS_DIR / slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_slug": slug, "target_branch": "release/9.9"}),
            encoding="utf-8",
        )

        assert resolve_mission_target_branch(slug, tmp_path) == "release/9.9"
