"""M6 error-contract regression + coord-empty Option B convergence (post-WP06).

Amended by Mission lane-worktree-model-hardening WP05 (ADR 2026-11-06-2): the loud warning
is replaced by the read door's declared pre-seed fallback; the PRIMARY resolution below holds.

Both coord-empty handle forms now CONVERGE on WP04's Option B (loud primary
fallback at the canonical surface, #1716/FR-003) — the transitional WP04 boundary
split is closed by WP06's read-path boundary absorption (T015 / FR-004):

* **canonical ``<slug>-<mid8>`` dirname** and **backfilled bare dirname** alike →
  status-surface resolution, where Option B returns the PRIMARY checkout + a loud
  ``logging.WARNING`` instead of raising. The boundary surfaces a resolved context
  (no ``ActionContextError``), and the fallback stays observable on the surface
  logger (no silent fallback).

The earlier divergence (canonical → translated ``StatusReadPathNotFound`` refusal;
backfilled → primary + warning) was a transitional WP04 artifact: the mission's
fixture stored NO ``topology`` field, so the canonical leg fell into the legacy
``topology is None`` fail-closed band-aid. WP06 absorbs that absent field at the
read boundary to a concrete COORD topology, so the canonical leg now folds onto the
SAME Option-B primary+warning as the backfilled leg — matching the equivalence
matrix's ``coord-empty/slug-mid8`` PRIMARY cell. ``ActionContextError`` translation
(PR #1850 M6) is still exercised by the genuine fail-closed paths (e.g. the DELETED
coord-branch carve-out) elsewhere; coord-EMPTY is Option-B primary, not a refusal.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from mission_runtime import (
    MissionArtifactKind,
    resolve_action_context,
    resolve_placement_only,
)

_SURFACE_LOGGER = "specify_cli.coordination.surface_resolver"

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_MID8 = "01KTM6EC"
_MISSION_ID = f"{_MID8}000000000000000000"  # 26-char ULID-shaped
# Canonical post-WP03 shape: the directory name carries the mid8 suffix.
_CANONICAL_DIRNAME = f"m6-error-contract-{_MID8}"
# Backfilled/legacy shape: bare directory name; mid8 lives only in meta.json.
_BACKFILLED_DIRNAME = "m6-backfilled-mission"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / ".kittify").mkdir()
    (r / ".kittify" / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\n", encoding="utf-8"
    )
    return r


def _build_mission(repo: Path, *, dirname: str) -> Path:
    """Coord-topology mission in the primary checkout + commit.

    No ``topology`` field is stored in ``meta.json`` (the un-backfilled-legacy
    shape this module's WP06-absorption tests exercise) — the ``lanes.json``
    disk signal instead makes the derived shape ``LANES_WITH_COORD`` (a coord
    mission WITH lanes). WP08 (#2533) makes the coord-empty warning's
    true-positive signal conditional on that derived shape (a solo, no-lanes
    ``MissionTopology.COORD`` mission stays quiet instead — see
    ``tests/coordination/test_surface_resolver_solo_coord_primary.py``), so
    every one of THIS module's coord-empty fixtures declares lanes to keep
    pinning the still-warns case.
    """
    feature_dir = repo / "kitty-specs" / dirname
    feature_dir.mkdir(parents=True)
    meta = {
        "mission_id": _MISSION_ID,
        "mid8": _MID8,
        "mission_slug": dirname,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": f"kitty/mission-{dirname}",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (feature_dir / "tasks").mkdir()
    lanes_manifest = {
        "version": 1,
        "mission_slug": dirname,
        "mission_id": _MISSION_ID,
        "mission_branch": f"kitty/mission-{dirname}",
        "target_branch": "main",
        "lanes": [
            {"lane_id": "lane-a", "wp_ids": ["WP01"]},
        ],
        "computed_at": "2026-07-12T00:00:00+00:00",
        "computed_from": "dependency_graph+ownership",
    }
    (feature_dir / "lanes.json").write_text(
        json.dumps(lanes_manifest), encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    return feature_dir


def _materialize_coord_root_without_mission_dir(repo: Path, dirname: str) -> Path:
    """The fail-closed window: coord worktree root exists, mission dir absent."""
    composed = dirname if dirname.endswith(f"-{_MID8}") else f"{dirname}-{_MID8}"
    coord_root = repo / ".worktrees" / f"{composed}-coord"
    coord_root.mkdir(parents=True)
    return coord_root


def _assert_option_b_warning(caplog: pytest.LogCaptureFixture) -> None:
    """The loud Option B warning is gone (ADR 2026-11-06-2, Mission lane-worktree-model-hardening WP05).

    These fixtures' coordination branch holds no log, so the read is the declared pre-seed
    fallback to the write checkout, stamped as ``fallback_reason`` on the read door's surface
    (``tests/status/test_read_surface_door.py``), not a log warning.
    """
    assert not any(r.name == _SURFACE_LOGGER and r.levelno == logging.WARNING for r in caplog.records)


def test_action_context_canonical_dirname_resolves_primary_with_warning(
    repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """``<slug>-<mid8>`` coord-empty folds onto Option B primary+warning (post-WP06).

    WP06's read-path boundary absorption (T015) classifies the absent ``topology``
    field to a concrete COORD topology, so the canonical-dirname leg no longer takes
    the legacy ``topology is None`` fail-closed refusal — it converges with the
    backfilled leg on Option B: PRIMARY checkout + a loud surface warning, no
    ``ActionContextError``. Negative control: the warning MUST fire (no silent
    fallback). This matches the equivalence matrix ``coord-empty/slug-mid8`` PRIMARY
    cell — the transitional WP04 split is closed."""
    _build_mission(repo, dirname=_CANONICAL_DIRNAME)
    _materialize_coord_root_without_mission_dir(repo, _CANONICAL_DIRNAME)

    with caplog.at_level(logging.WARNING, logger=_SURFACE_LOGGER):
        context = resolve_action_context(
            repo, action="status", feature=_CANONICAL_DIRNAME
        )

    assert context.feature_dir == str(repo / "kitty-specs" / _CANONICAL_DIRNAME)
    _assert_option_b_warning(caplog)


def test_action_context_backfilled_dirname_resolves_primary_with_warning(
    repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """WP04 Option B: bare-dir coord-empty resolves PRIMARY + loud warning.

    The backfilled bare dirname travels status-surface resolution, where Option B
    (#1716/FR-003) returns the primary checkout and emits a loud warning rather
    than raising. The boundary therefore surfaces a resolved context (no
    ``ActionContextError``), and the fallback is observable on the surface logger.
    """
    _build_mission(repo, dirname=_BACKFILLED_DIRNAME)
    _materialize_coord_root_without_mission_dir(repo, _BACKFILLED_DIRNAME)

    with caplog.at_level(logging.WARNING, logger=_SURFACE_LOGGER):
        context = resolve_action_context(
            repo, action="status", feature=_BACKFILLED_DIRNAME
        )

    assert context.feature_dir == str(repo / "kitty-specs" / _BACKFILLED_DIRNAME)
    _assert_option_b_warning(caplog)


def test_placement_only_canonical_dirname_resolves_with_warning(
    repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """``<slug>-<mid8>`` coord-empty placement folds onto Option B (post-WP06).

    The shared placement fragment builder travels the same status-surface resolution;
    after WP06's boundary absorption the canonical-dirname leg no longer raises for
    coord-empty — it returns a placement and the surface emits the loud warning,
    converging with the backfilled leg."""
    _build_mission(repo, dirname=_CANONICAL_DIRNAME)
    _materialize_coord_root_without_mission_dir(repo, _CANONICAL_DIRNAME)

    with caplog.at_level(logging.WARNING, logger=_SURFACE_LOGGER):
        placement = resolve_placement_only(
            repo, _CANONICAL_DIRNAME, kind=MissionArtifactKind.STATUS_STATE
        )

    assert placement is not None
    _assert_option_b_warning(caplog)


def test_placement_only_backfilled_dirname_resolves_with_warning(
    repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """WP04 Option B: bare-dir coord-empty placement resolves (no refusal) + warns.

    The shared placement fragment builder travels the same status-surface
    resolution; under Option B it no longer raises for the bare-dir coord-empty
    handle — it returns a placement and the surface emits the loud warning.
    """
    _build_mission(repo, dirname=_BACKFILLED_DIRNAME)
    _materialize_coord_root_without_mission_dir(repo, _BACKFILLED_DIRNAME)

    with caplog.at_level(logging.WARNING, logger=_SURFACE_LOGGER):
        placement = resolve_placement_only(
            repo, _BACKFILLED_DIRNAME, kind=MissionArtifactKind.STATUS_STATE
        )

    assert placement is not None
    _assert_option_b_warning(caplog)
