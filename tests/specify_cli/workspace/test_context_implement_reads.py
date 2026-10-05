"""Zero-mock unit tests for the context reads implement delegates to `workspace/context.py` (FR-006).

Covers `resolve_lane_state_dir` (WP03 / #2052, absorbed from `tests/cli/commands/test_resolve_lanes_dir.py`),
`find_wp_file` and `resolve_mission_target_branch`.

`resolve_lane_state_dir` returns the primary checkout surface for every topology: ``lanes.json`` is
PRIMARY-partition state, so a materialised coordination worktree never hides it (#3371), and a
mission without a coordination branch resolves to the primary checkout too.

No ``unittest.mock``: the path reads run on a ``tmp_path`` filesystem alone; the target-branch
reads use a real (empty) git repository.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.workspace.context import find_wp_file, resolve_lane_state_dir, resolve_mission_target_branch
from specify_cli.core.constants import KITTY_SPECS_DIR

# Per class: the pure path reads are ``fast``; the target-branch reads run git (``git_repo``).
_FAST = pytest.mark.fast


# A Crockford base32 mid8 that ``mid8_from_slug`` will recognise as a valid
# tail when embedded in a slug (8 chars, charset [0-9A-HJKMNP-TV-Z]).
_TEST_MID8 = "01KVN754"
_COORD_BRANCH = "kitty/mission-my-mission-01KVN754"
#: A valid Crockford ULID whose mid8 is ``_TEST_MID8``.
_MISSION_ID = "01KVN754TY9CVJ8G10ERTQ6ZXA"


def _write_meta(feature_dir: Path, *, coordination_branch: str | None = None) -> None:
    """Write a minimal meta.json into *feature_dir*."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_slug": feature_dir.name,
        "mission_id": _MISSION_ID,
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


@_FAST
class TestResolveLaneStateDirCoordTopology:
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


@_FAST
class TestResolveLaneStateDirFlatTopology:
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


@_FAST
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


@pytest.mark.git_repo
class TestResolveMissionTargetBranch:
    @staticmethod
    def _mission(repo: Path, meta: dict[str, object], *, branch: str = "main") -> str:
        subprocess.run(["git", "init", "-q", "-b", branch, str(repo)], check=True)
        slug = "my-mission"
        feature_dir = repo / KITTY_SPECS_DIR / slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": slug, **meta}), encoding="utf-8")
        return slug

    def test_returns_the_target_branch_recorded_in_meta(self, tmp_path: Path) -> None:
        slug = self._mission(tmp_path, {"target_branch": "release/9.9"})

        assert resolve_mission_target_branch(slug, tmp_path) == "release/9.9"

    def test_falls_back_to_the_primary_branch_when_meta_records_none(self, tmp_path: Path) -> None:
        """Without a recorded ``target_branch`` the primary branch is the target; a repository with no
        ``origin/HEAD`` takes the checked-out branch as its primary branch."""
        slug = self._mission(tmp_path, {}, branch="develop")

        assert resolve_mission_target_branch(slug, tmp_path) == "develop"
