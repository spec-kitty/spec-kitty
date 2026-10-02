"""``materialize_coord_surface_for_write`` (#5113, D1) — one arm per test.

The write-gate helper every coordination write (``decision open`` / resolve /
defer / cancel) calls before touching a ledger, so a fresh coordination
Mission's absent worktree is materialized BEFORE the write rather than left
half-recorded after an uncaught
:class:`~specify_cli.coordination.surface_resolver.CoordinationWorktreeUnmaterialized`.

Reuses the REAL ``create_mission_core`` fixture helpers from
``tests/integration/test_placement_partition_golden_path.py`` (canonical
sources, DIRECTIVE_044) — real git, real mission scaffolding, no fakes.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.surface_resolver import (
    CoordinationWorktreeUnmaterialized,
    materialize_coord_surface_for_write,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _worktree_list(repo: Path) -> str:
    return _git(repo, "worktree", "list", "--porcelain").stdout


def _fresh_coord_mission(tmp_path: Path, slug: str = "materialize-coord-surface"):
    _init_git_repo(tmp_path)
    return tmp_path, _create_mission(tmp_path, slug, MissionTopology.COORD)


def _unmaterialize_coord_worktree(repo: Path, slug: str, mid8: str) -> Path:
    """Remove the coordination worktree create seeded, keeping its branch (UNMATERIALIZED).

    #5440: create now seeds the coordination worktree, so the seam's
    unmaterialized arms must establish that state explicitly.
    """
    coord_worktree = CoordinationWorkspace.worktree_path(repo, slug, mid8)
    _git(repo, "worktree", "remove", "--force", str(coord_worktree))
    assert not coord_worktree.exists()
    return coord_worktree


# ---------------------------------------------------------------------------
# 1. no coordination_branch declared -> no-op (flat / SINGLE_BRANCH mission)
# ---------------------------------------------------------------------------


def test_no_coordination_branch_is_a_noop(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    result = _create_mission(tmp_path, "no-coord-branch", MissionTopology.SINGLE_BRANCH)
    assert result.coordination_branch is None

    materialize_coord_surface_for_write(tmp_path, result.mission_slug)

    assert not (tmp_path / ".worktrees").exists()


def test_explicit_coordination_branch_without_mid8_raises(tmp_path: Path) -> None:
    """Review cycle 2 (coord-artifact-single-home-01M3V4BE WP09, B1-residual):
    the optional ``coordination_branch``/``mid8`` override pair is a caller
    contract -- passing one without the other must never silently fall
    through to a half-resolved materialization attempt."""
    with pytest.raises(ValueError, match="mid8 must accompany an explicit coordination_branch override"):
        materialize_coord_surface_for_write(tmp_path, "whatever", coordination_branch="kitty/mission-whatever-01ABCDEF")


def test_explicit_mid8_without_coordination_branch_raises(tmp_path: Path) -> None:
    """Review cycle 3 nit: the symmetric caller-contract guard -- passing
    ``mid8`` alone would otherwise silently fall into the meta re-derivation
    branch and OVERWRITE that ``mid8``, contradicting the docstring."""
    with pytest.raises(ValueError, match="coordination_branch must accompany an explicit mid8 override"):
        materialize_coord_surface_for_write(tmp_path, "whatever", mid8="01ABCDEF")


# ---------------------------------------------------------------------------
# 2. MATERIALIZED -> no-op, no second worktree created
# ---------------------------------------------------------------------------


def test_materialized_surface_is_a_noop(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path, "materialized-coord")
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])

    coord_root = CoordinationWorkspace.resolve(repo, slug, mid8)
    coord_mission_dir = coord_root / "kitty-specs" / slug
    coord_mission_dir.mkdir(parents=True, exist_ok=True)
    (coord_mission_dir / ".keep").write_text("", encoding="utf-8")
    _git(coord_root, "add", "-A")
    _git(coord_root, "commit", "-qm", "materialize coord mission dir")

    before = _worktree_list(repo)
    materialize_coord_surface_for_write(repo, slug)
    after = _worktree_list(repo)

    assert before == after
    assert coord_root.exists()


# ---------------------------------------------------------------------------
# 3. EMPTY (worktree root exists, mission dir absent) -> no-op
# ---------------------------------------------------------------------------


def test_empty_surface_is_a_noop(tmp_path: Path) -> None:
    """Re-pinned (coord-artifact-single-home-01M3V4BE WP06, T031): create now
    seeds the coordination surface eagerly, so a fresh mission's worktree is
    MATERIALIZED (non-empty), never EMPTY, by the time this test runs. The
    EMPTY arm (worktree root present, mission dir absent) is engineered
    explicitly instead, mirroring a pre-fix-shaped Mission whose dir was
    removed.
    """
    repo, result = _fresh_coord_mission(tmp_path, "empty-coord")
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])

    coord_root = CoordinationWorkspace.worktree_path(repo, slug, mid8)
    assert coord_root.exists(), "T031 already materializes the coordination worktree at create time"
    shutil.rmtree(coord_root / "kitty-specs" / slug)
    assert not (coord_root / "kitty-specs" / slug).exists()

    before = _worktree_list(repo)
    materialize_coord_surface_for_write(repo, slug)
    after = _worktree_list(repo)

    assert before == after
    assert coord_root.exists()
    assert not (coord_root / "kitty-specs" / slug).exists()


# ---------------------------------------------------------------------------
# 4. UNMATERIALIZED + local branch -> the worktree exists afterwards
# ---------------------------------------------------------------------------


def test_unmaterialized_local_branch_materializes(tmp_path: Path) -> None:
    """Re-pinned (coord-artifact-single-home-01M3V4BE WP06, T031): create now
    materializes the coordination worktree eagerly, so the genuine
    UNMATERIALIZED precondition (no worktree at all) is engineered by
    tearing it back down first.
    """
    repo, result = _fresh_coord_mission(tmp_path, "unmaterialized-local")
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo, slug, mid8)
    assert coord_worktree.exists(), "T031 already materializes the coordination worktree at create time"
    CoordinationWorkspace.teardown(repo, slug, mid8)
    assert not coord_worktree.exists()

    materialize_coord_surface_for_write(repo, slug)

    assert coord_worktree.exists()


# ---------------------------------------------------------------------------
# 5. remote-only branch -> raises, nothing created
# ---------------------------------------------------------------------------


def test_remote_only_branch_raises_and_creates_nothing(tmp_path: Path) -> None:
    """Re-pinned (coord-artifact-single-home-01M3V4BE WP06, T031): the branch
    is checked out in the worktree T031 already materialized at create time,
    so it must be torn down before the branch can be deleted (git refuses to
    delete a branch checked out in a worktree).
    """
    repo, result = _fresh_coord_mission(tmp_path, "remote-only-coord")
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])
    coord_branch = result.coordination_branch
    assert coord_branch is not None
    coord_worktree = _unmaterialize_coord_worktree(repo, slug, mid8)

    _git(repo, "update-ref", f"refs/remotes/origin/{coord_branch}", coord_branch)
    CoordinationWorkspace.teardown(repo, slug, mid8)
    _git(repo, "branch", "-D", coord_branch)

    with pytest.raises(CoordinationWorktreeUnmaterialized) as exc_info:
        materialize_coord_surface_for_write(repo, slug)

    assert exc_info.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"
    assert not coord_worktree.exists()


# ---------------------------------------------------------------------------
# 6. resolve() raising a real obstacle -> raises with __cause__
# ---------------------------------------------------------------------------


def test_resolve_failure_raises_with_cause(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path, "resolve-obstacle")
    slug = result.mission_slug
    # #5440: create now seeds the coordination worktree; drop it (and the
    # ``.worktrees`` container) so the obstacle below sits in its place.
    _unmaterialize_coord_worktree(repo, slug, str(result.meta["mid8"]))
    shutil.rmtree(repo / ".worktrees")

    # A REAL obstacle (per Test Strategy: no mocks for failure injection):
    # ``.worktrees`` as a regular file makes ``mkdir(parents=True)`` raise
    # ``FileExistsError`` (an ``OSError`` subclass) inside
    # ``CoordinationWorkspace.resolve``. Re-pinned (coord-artifact-single-
    # home-01M3V4BE WP06, T031): create already materialized a REAL
    # ``.worktrees/`` directory for this mission, so it is cleared first --
    # a regular file cannot otherwise take its place.
    worktrees_dir = repo / ".worktrees"
    if worktrees_dir.exists():
        shutil.rmtree(worktrees_dir)
    worktrees_dir.write_text("obstacle", encoding="utf-8")

    with pytest.raises(CoordinationWorktreeUnmaterialized) as exc_info:
        materialize_coord_surface_for_write(repo, slug)

    assert exc_info.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"
    assert isinstance(exc_info.value.__cause__, OSError)


# ---------------------------------------------------------------------------
# 7. the race: a concurrent process materializes between the probe and
#    ``resolve()`` -- the ONE sanctioned monkeypatch (wraps the real call).
# ---------------------------------------------------------------------------


def test_concurrent_materialization_race_returns_without_raising(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path, "race-coord")
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])

    real_resolve = CoordinationWorkspace.resolve

    def _materialize_then_raise(cls: type[CoordinationWorkspace], *args: object, **kwargs: object) -> Path:
        # Simulate a sibling CLI process winning the race: materialize for
        # real via the SAME canonical call, then report the failure this
        # process's own attempt would have hit.
        real_resolve(*args, **kwargs)
        raise OSError("simulated concurrent worktree-add collision")

    with patch.object(CoordinationWorkspace, "resolve", classmethod(_materialize_then_raise)):
        materialize_coord_surface_for_write(repo, slug)

    coord_worktree = CoordinationWorkspace.worktree_path(repo, slug, mid8)
    assert coord_worktree.exists()
