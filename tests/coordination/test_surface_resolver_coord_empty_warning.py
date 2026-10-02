"""WP04/WP08 coord-empty Option B — the loud primary-fallback warning (NON-FAKEABLE).

Mission ``mission-surface-resolver-safety-net-01KVN754`` applies the operator-
decided **Option B**: a materialized-but-empty coordination worktree no longer
hard-fails. ``resolve_status_surface_with_anchor`` falls back to the PRIMARY
checkout and proceeds. WP08 (#2533) refines WHEN the fallback is loud:

* a coord mission WITH lanes (``MissionTopology.LANES_WITH_COORD`` — lane
  worktrees were provisioned to write there) hitting an empty coord root is
  genuinely unexpected, so the fallback still emits a single **loud,
  observable** warning so an operator or orchestrating agent can intervene
  (FR-001 / FR-003 / NFR-003 / #1716) — the TRUE-POSITIVE case this module
  pins;
* a solo coord mission with no lanes (``MissionTopology.COORD``) hitting an
  empty coord root is the EXPECTED steady state before its first
  coordination-branch write self-materializes it — the fallback stays quiet,
  no warning, no manual-flatten prompt for a condition that is not an error
  (#2533 / WP08 T029-T031, pinned by
  ``tests/coordination/test_surface_resolver_solo_coord_primary.py``).

The true-positive centerpiece is a **3-part conjunctive** assertion that a
``print`` or a ``logging.DEBUG`` line could NOT satisfy:

  (a) a record at EXACTLY ``logging.WARNING`` from the named module logger
      ``specify_cli.coordination.surface_resolver``;
  (b) the message names BOTH operator recovery paths — flatten (drop the
      ``coordination_branch`` key) AND ``spec-kitty agent worktree repair``;
  (c) the resolver returns the PRIMARY dir (not the coord dir, not a raise).

Grep anchors for the reviewer:
  * logger name:   ``specify_cli.coordination.surface_resolver``
  * warning const: ``surface_resolver._COORD_EMPTY_FALLBACK_WARNING``

ADR: ``docs/adr/3.x/2026-06-19-1-coord-empty-surface-fallback.md``.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from specify_cli.coordination.surface_resolver import (
    resolve_status_surface_with_anchor,
)
from specify_cli.coordination.workspace import CoordinationWorkspace

from tests._factories.coord_mission import make_coord_mission, make_prefix_coord_mission

pytestmark = pytest.mark.git_repo

# Production-shaped identity (Mission Identity Model 083+): a real 26-char ULID.
MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"
MID8 = MISSION_ID[:8]
BARE_SLUG = "coord-empty-warning-mission"
SLUG_WITH_MID8 = f"{BARE_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{SLUG_WITH_MID8}"

# A distinct solo-mission identity for the legitimate-empty (no-warning) case,
# so the two scenarios never share a fixture slug/branch.
SOLO_MISSION_ID = "01KTDVJ2N8VZ0A5C1XKJH0Q9RB"
SOLO_MID8 = SOLO_MISSION_ID[:8]
SOLO_SLUG = f"solo-pr-bound-coord-mission-{SOLO_MID8}"
SOLO_COORD_BRANCH = f"kitty/mission-{SOLO_SLUG}"

# The single named logger the resolver emits through (grep anchor for review).
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
    _git(repo_root, "config", "user.email", "warn@example.test")
    _git(repo_root, "config", "user.name", "Coord Empty Warning")
    _git(repo_root, "commit", "--allow-empty", "-qm", "init")


def _write_meta(feature_dir: Path, **fields: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(fields), encoding="utf-8")


def _materialise_coord_empty(
    repo_root: Path,
    slug: str,
    *,
    mission_id: str = MISSION_ID,
    coordination_branch: str = COORD_BRANCH,
    topology: str = "lanes_with_coord",
) -> Path:
    """Primary declares coord branch; coord worktree ROOT exists but is empty.

    ``topology`` defaults to the WITH-lanes shape (``lanes_with_coord`` — the
    true-positive warning scenario this module pins): the stored ``topology``
    field is written explicitly, matching the real post-083 production shape
    (``meta.json`` is authoritative — mirrors ``tests/mission_runtime/
    test_placement_seam.py``'s ``_build_mission``), rather than relying on the
    legacy no-stored-topology derivation path.

    Returns the expected PRIMARY mission dir the resolver must fall back to.
    """
    _init_repo(repo_root)
    primary_dir = repo_root / "kitty-specs" / slug
    _write_meta(
        primary_dir,
        mission_id=mission_id,
        coordination_branch=coordination_branch,
        topology=topology,
    )
    _git(repo_root, "branch", coordination_branch)
    mid8 = mission_id[:8]
    coord_root = CoordinationWorkspace.worktree_path(repo_root, slug, mid8)
    coord_root.mkdir(parents=True)  # materialised, NO mission dir inside
    return primary_dir


@pytest.mark.parametrize("slug", [BARE_SLUG, SLUG_WITH_MID8], ids=["bare", "slug-mid8"])
def test_coord_empty_with_lanes_warns_loudly_and_returns_primary(
    tmp_path: Path, slug: str, caplog: pytest.LogCaptureFixture
) -> None:
    """3-part conjunction: WARNING level + BOTH recovery tokens + PRIMARY dir.

    The TRUE-POSITIVE case (WP08 T031): a coord mission WITH lanes
    (``lanes_with_coord``) whose coord worktree is unexpectedly empty STILL
    warns — a ``print`` (no log record), a ``logging.DEBUG`` line (wrong
    level), or a message missing either recovery token all FAIL this test.
    The fallback must be observable AND actionable AND must resolve to the
    primary checkout.
    """
    primary_dir = _materialise_coord_empty(tmp_path, slug, topology="lanes_with_coord")

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(tmp_path, slug)

    # (a) EXACTLY one record, at EXACTLY logging.WARNING, from the named logger.
    warning_records = [
        r
        for r in caplog.records
        if r.name == _LOGGER_NAME and r.levelno == logging.WARNING
    ]
    assert warning_records, (
        "coord-empty WITH lanes must emit a record at EXACTLY logging.WARNING "
        f"from {_LOGGER_NAME!r} — a print or DEBUG line must NOT satisfy this. "
        f"Records seen: {[(r.name, r.levelname) for r in caplog.records]}"
    )
    # No DEBUG/INFO downgrade smuggled the message in below WARNING.
    assert all(r.levelno >= logging.WARNING for r in warning_records)

    message = warning_records[0].getMessage()
    lowered = message.lower()
    # (b) BOTH recovery paths named — discriminating tokens, not "an error".
    assert "flatten" in lowered and "coordination_branch" in message, (
        "warning must name recovery path (a): flatten the mission by removing "
        f"the `coordination_branch` key. Got: {message!r}"
    )
    assert "doctor workspaces --fix" in message, (
        "warning must name recovery path (b): the real repair command "
        "(spec-kitty doctor workspaces --fix, per FR-007/#1890). "
        f"Got: {message!r}"
    )
    # (c) The resolver RETURNS the PRIMARY dir — Option B fallback, not a raise,
    #     not the coord dir.
    assert resolved.read_dir.resolve() == primary_dir.resolve(), (
        "coord-empty Option B must resolve to the PRIMARY checkout, not the "
        f"coord dir. Got: {resolved.read_dir}"
    )
    assert resolved.primary_anchor.resolve() == primary_dir.resolve()


def test_coord_empty_solo_no_lanes_stays_quiet_and_returns_primary(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """WP08 T031/T032: the legitimate-solo-empty case does NOT warn.

    A solo (no-lanes) coord-topology mission (``MissionTopology.COORD``)
    whose coord worktree is materialized-but-empty is the EXPECTED
    pre-first-write state (#2533) — the resolver must still return the
    PRIMARY surface (Option B fallback unchanged), but MUST NOT emit
    ``_COORD_EMPTY_FALLBACK_WARNING``: this is not an error condition and
    should not prompt a manual flatten.
    """
    primary_dir = _materialise_coord_empty(
        tmp_path,
        SOLO_SLUG,
        mission_id=SOLO_MISSION_ID,
        coordination_branch=SOLO_COORD_BRANCH,
        topology="coord",
    )

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(tmp_path, SOLO_SLUG)

    warning_records = [
        r
        for r in caplog.records
        if r.name == _LOGGER_NAME and r.levelno == logging.WARNING
    ]
    assert not warning_records, (
        "a solo (no-lanes) coord mission's legitimately empty coord worktree "
        "must NOT emit the split-brain warning — it is an expected, "
        f"self-healing pre-first-write state. Records seen: "
        f"{[(r.name, r.levelname, r.getMessage()) for r in warning_records]}"
    )
    assert resolved.read_dir.resolve() == primary_dir.resolve(), (
        "the legitimate-solo-empty case must still resolve to the PRIMARY "
        f"checkout (Option B routing unchanged). Got: {resolved.read_dir}"
    )
    assert resolved.primary_anchor.resolve() == primary_dir.resolve()


# ---------------------------------------------------------------------------
# T033/R6 (coord-artifact-single-home-01M3V4BE, #2533): a fresh coordination
# create no longer trips the split-brain warning, because T031 seeds the
# coordination surface eagerly at create time -- by the time anything probes
# it, the worktree is MATERIALIZED, never EMPTY. The legacy pre-fix shape
# (built explicitly, never through today's create) is the control: it still
# warns, unchanged.
# ---------------------------------------------------------------------------


def test_no_split_brain_warning_after_new_coord_create(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """RED at the WP06 lane base: pre-fix, ``create_mission_core`` never seeds
    the coordination surface, so a fresh ``lanes_with_coord`` mission's coord
    worktree is materialized (by the time something resolves it) but EMPTY --
    the true-positive warning above fires for it too. Post-fix (T031), create
    seeds + commits the Mission dir onto the coordination branch itself, so
    the surface is already MATERIALIZED and this warning must stay silent.
    """
    coord = make_coord_mission(tmp_path, MissionTopology.LANES_WITH_COORD, via="core")
    # Force materialization (idempotent under the fix: T031 already
    # materialized + seeded the worktree at create time, so this is a no-op
    # returning the same, non-empty path). At the WP06 lane BASE, pre-fix
    # create never touches the worktree at all, so this is the first thing
    # that creates it -- with no Mission dir inside, reproducing the real
    # #2533 "materialized but EMPTY" shape the warning exists for.
    CoordinationWorkspace.resolve(coord.repo_root, coord.mission_dir_name, coord.mid8)

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolved = resolve_status_surface_with_anchor(coord.repo_root, coord.mission_dir_name)

    warning_records = [r for r in caplog.records if r.name == _LOGGER_NAME and r.levelno == logging.WARNING]
    assert not warning_records, (
        "a freshly created coordination-routed mission must not trip the coord-empty "
        f"split-brain warning (#2533, R6). Records seen: {[(r.name, r.levelname, r.getMessage()) for r in warning_records]}"
    )
    assert resolved.read_dir.resolve() == coord.coord_mission_dir.resolve(), (
        f"a materialized, seeded coordination surface must resolve to the COORD dir, not fall back to PRIMARY. Got: {resolved.read_dir}"
    )


def test_legacy_empty_coord_still_warns(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Control (R6): WP02's explicit pre-fix shape (committed root log, coordination
    branch cut BEFORE it, EMPTY worktree) still trips the split-brain warning --
    T031 changes create's OWN placement going forward; it never silently heals an
    existing pre-fix Mission's already-empty worktree.
    """
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.LANES_WITH_COORD, worktree="empty")

    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        resolve_status_surface_with_anchor(coord.repo_root, coord.mission_dir_name)

    warning_records = [r for r in caplog.records if r.name == _LOGGER_NAME and r.levelno == logging.WARNING]
    assert warning_records, "a legacy pre-fix, genuinely empty coord surface must still warn (control, unchanged by T031)"
