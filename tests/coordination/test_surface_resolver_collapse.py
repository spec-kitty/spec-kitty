"""Surface-resolver collapse + WP04 coord-empty Option B (mutation-verified).

These tests pin the behavioral contract on the **single** canonical surface
resolver (``coordination.surface_resolver.resolve_status_surface_with_anchor`` —
FR-001/FR-007 sole authority):

* **WP04 coord-empty Option B (#1716 / FR-001 / FR-003).** A materialized-but-
  empty coordination worktree no longer hard-fails: the resolver falls back to
  the PRIMARY checkout and proceeds, emitting a loud ``logging.WARNING`` that
  names BOTH operator recovery paths (flatten OR ``spec-kitty agent worktree
  repair``). The 3-part non-fakeable WARNING-level + both-tokens + primary-dir
  assertion lives in the sibling
  ``tests/coordination/test_surface_resolver_coord_empty_warning.py``; here we
  pin the *handle-invariant* primary-resolve outcome (the fallback fires for
  BOTH the bare-slug and the ``<slug>-<mid8>`` handle forms) and the explicit
  no-raise posture (a regression that re-introduced the old
  ``CoordinationWorktreeEmpty`` hard-fail is caught here).
* **The two adjacent benign states still resolve to primary** (regression
  guards that Option B did NOT over-reach): the no-coord state and the
  create→first-write window (coord declared, worktree NOT materialized).

ADR: ``docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md``.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.surface_resolver import (
    resolve_status_surface_with_anchor,
)
from specify_cli.coordination.workspace import CoordinationWorkspace

pytestmark = pytest.mark.git_repo

# Production-shaped identity (Mission Identity Model 083+): a real 26-char ULID.
MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"
MID8 = MISSION_ID[:8]
BARE_SLUG = "surface-collapse-mission"
SLUG_WITH_MID8 = f"{BARE_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

_LOGGER_NAME = "specify_cli.coordination.surface_resolver"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo_root: Path) -> None:
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "collapse@example.test")
    _git(repo_root, "config", "user.name", "Collapse Gate")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, **fields: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(fields), encoding="utf-8")


def _materialise_coord_empty(repo_root: Path, slug: str) -> Path:
    """Primary declares coord branch; coord worktree ROOT exists but is empty.

    ``topology`` is explicit ``lanes_with_coord`` (WP08 / #2533): this module
    tests the TRUE-POSITIVE "coord worktree unexpectedly empty" case (a coord
    mission WITH lanes, where lane worktrees were provisioned to write there),
    which still warns after WP08 differentiated it from the legitimate solo
    (no-lanes, ``MissionTopology.COORD``) empty-coord state — see
    ``tests/coordination/test_surface_resolver_solo_coord_primary.py`` and
    ``test_surface_resolver_coord_empty_warning.py`` for the quiet-primary
    sibling.

    Returns the expected PRIMARY mission dir the Option-B fallback resolves to.
    """
    _init_repo(repo_root)
    primary_dir = repo_root / "kitty-specs" / slug
    _write_meta(
        primary_dir,
        mission_id=MISSION_ID,
        coordination_branch=COORD_BRANCH,
        topology="lanes_with_coord",
    )
    _git(repo_root, "branch", COORD_BRANCH)
    coord_root = CoordinationWorkspace.worktree_path(repo_root, slug, MID8)
    coord_root.mkdir(parents=True)  # materialised, NO mission dir inside
    return primary_dir


# ---------------------------------------------------------------------------
# WP04 — coord-empty Option B loud primary fallback (handle-invariant)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("slug", [BARE_SLUG, SLUG_WITH_MID8], ids=["bare", "slug-mid8"])
def test_coord_empty_resolves_primary_with_warning_for_both_handle_forms(
    tmp_path: Path, slug: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A materialized-but-empty coord worktree → PRIMARY surface + loud warning.

    Mutation-killing: a regression that re-raised the old
    ``CoordinationWorktreeEmpty`` hard-fail (instead of falling back to primary),
    OR that fell back SILENTLY (no WARNING), is caught here for BOTH handle forms.
    """
    primary_dir = _materialise_coord_empty(tmp_path, slug)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(tmp_path, slug)

    # Option B: PRIMARY dir, never a raise, never the coord dir.
    assert resolved.read_dir.resolve() == primary_dir.resolve()
    assert resolved.primary_anchor.resolve() == primary_dir.resolve()

    # ADR 2026-11-06-2 (WP05): the loud warning is gone; the branch holds no log, so this
    # is the read door's declared pre-seed fallback (``fallback_reason`` on the surface).
    assert not any(r.name == _LOGGER_NAME and r.levelno == logging.WARNING for r in caplog.records)


def test_coord_empty_no_longer_raises_status_read_path_not_found(
    tmp_path: Path,
) -> None:
    """Option B replaces the #1716 hard-fail — coord-empty does NOT raise.

    The old contract raised ``CoordinationWorktreeEmpty`` (a
    ``StatusReadPathNotFound`` subclass). Under Option B the surface returns a
    value; this guards against a regression that re-introduced the raise.
    """
    _materialise_coord_empty(tmp_path, SLUG_WITH_MID8)

    # Must NOT raise — returns the primary surface.
    resolved = resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)
    assert resolved.read_dir.name == SLUG_WITH_MID8


# ---------------------------------------------------------------------------
# Regression guards — Option B must NOT over-reach onto benign states
# ---------------------------------------------------------------------------


def test_no_coord_resolves_primary(tmp_path: Path) -> None:
    """A mission with no coordination_branch → primary surface, never a fallback warning."""
    _init_repo(tmp_path)
    _write_meta(tmp_path / "kitty-specs" / SLUG_WITH_MID8, mission_id=MISSION_ID)

    resolved = resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)

    expected = (tmp_path / "kitty-specs" / SLUG_WITH_MID8).resolve()
    assert resolved.read_dir.resolve() == expected
    assert resolved.primary_anchor.resolve() == expected


def test_create_window_unmaterialized_coord_resolves_primary(tmp_path: Path) -> None:
    """Create→first-write window (coord declared, NOT materialized) → primary anchor.

    The companion to the coord-empty fallback: when ``coordination_branch`` is
    declared but the coord worktree root does NOT yet exist, the primary checkout
    stays authoritative for the create→first-write window (#1718). A regression
    that warned/fell back here (treating an unmaterialized coord as empty) would
    break first-write on a freshly created coord mission. The surface composes the
    coord path (the worktree will live there once materialised); the CWD-invariant
    primary anchor remains the primary dir.
    """
    _init_repo(tmp_path)
    _write_meta(
        tmp_path / "kitty-specs" / SLUG_WITH_MID8,
        mission_id=MISSION_ID,
        coordination_branch=COORD_BRANCH,
    )
    _git(tmp_path, "branch", COORD_BRANCH)
    # NB: no .worktrees/<slug>-<mid8>-coord/ root is materialised.

    resolved = resolve_status_surface_with_anchor(tmp_path, SLUG_WITH_MID8)

    expected_primary = (tmp_path / "kitty-specs" / SLUG_WITH_MID8).resolve()
    assert resolved.primary_anchor.resolve() == expected_primary, (
        "create→first-write window must keep the PRIMARY checkout as the "
        "anchor — coord-empty fallback must not over-reach here"
    )
