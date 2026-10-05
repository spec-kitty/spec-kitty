"""WP05 / T028 (FR-004, NFR-001, NFR-002): behaviour preservation for the 10
trio call sites this WP routed through ``mission_runtime.placement_seam``.

``read-side-seam-primary-primitive-closure-01KYKMMT`` WP05 replaced ten direct
calls to the drained primitives (``primary_feature_dir_for_mission`` /
``_canonicalize_primary_read_handle``) across the four trio rewrite targets
(``cli/commands/agent/workflow.py``, ``cli/commands/agent/workflow_executor.py``,
``cli/commands/implement.py``, ``acceptance/__init__.py``) with
``placement_seam(repo_root, handle).read_dir(<kind>)``. These tests pin, for a
REPRESENTATIVE site in each of the four files (covering all three kinds this
WP actually routes -- ``PRIMARY_METADATA``, ``WORK_PACKAGE_TASK``,
``ANALYSIS_REPORT``):

* **NFR-001** -- a materialized, non-backfilled mission resolves the IDENTICAL
  directory the pre-migration blind composition
  (:func:`~specify_cli.missions._read_path_resolver._compose_primary_feature_dir`)
  would have returned, for both a flat mission and a coord-topology mission
  whose coord side is genuinely materialized (a PRIMARY-partition kind never
  selects the coord surface even when one exists).
* **NFR-002** -- no NEW raise on a coord husk (worktree materialized, no
  ``meta.json``), an empty coord worktree (create-window), or a deleted
  coordination branch -- exactly the failure modes the corrected husk
  comments (T027) warn the KIND-BLIND resolvers, not the kind-aware seam,
  are prone to.

Every fixture is a real git repository + real filesystem state under pytest's
``tmp_path`` (never a bare ``/tmp`` path, per this project's NFR-003 test-data
convention) -- no resolver is patched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.acceptance import _primary_anchor_feature_dir
from specify_cli.cli.commands.agent.workflow import (
    _analysis_report_gate_dir,
    _mission_id_for_claim,
)
from specify_cli.cli.commands.agent.workflow_executor import (
    implement_resolve_mission_type,
)
from specify_cli.coordination.planning_commit import load_primary_anchored_mission_meta
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.missions._read_path_resolver import _compose_primary_feature_dir
from specify_cli.workspace.context import find_wp_file
from tests.specify_cli._read_seam_migration_fixtures import (
    build_coord_branch_deleted,
    build_coord_husk,
    build_coord_materialized,
    build_coord_worktree_empty,
    build_flat,
    coord_branch_name,
    make_git_repo,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# Production-shaped identity (NFR-003): a real 26-char Crockford ULID and the
# canonical on-disk ``<slug>-<mid8>`` layout.
_MISSION_ID = "01KYKMMTWP05TRIOFIXTURE001"
_MID8 = _MISSION_ID[:8]
_SLUG = "trio-read-seam-migration-fixture"
_HANDLE = f"{_SLUG}-{_MID8}"
_COORD_BRANCH = coord_branch_name(_HANDLE)


def _make_git_repo(tmp_path: Path, name: str) -> Path:
    return make_git_repo(
        tmp_path,
        name,
        user_email="wp05-fixture@spec-kitty.test",
        user_name="WP05 Fixture",
        readme_text="wp05 trio fixture repo\n",
        quiet=True,
    )


def _write_meta(feature_dir: Path, *, coordination_branch: str | None) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "mission_slug": _HANDLE,
        "slug": _HANDLE,
        "mission_type": "software-dev",
        "target_branch": "main",
        "vcs": "git",
        "topology": "coord" if coordination_branch else "single_branch",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _plant_wp_task(feature_dir: Path) -> None:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "WP01-sample.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Sample\n---\n\n# WP01\n",
        encoding="utf-8",
    )


def _plant_analysis_report(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "analysis-report.md").write_text("# analysis report\n", encoding="utf-8")


def _write_primary_meta(feature_dir: Path) -> None:
    _write_meta(feature_dir, coordination_branch=_COORD_BRANCH)


def _flat(tmp_path: Path) -> Path:
    """Flat (no coordination) topology -- the simplest materialized fixture."""
    repo = _make_git_repo(tmp_path, "flat")
    primary_dir = build_flat(
        repo, _HANDLE, write_primary_meta=lambda fd: _write_meta(fd, coordination_branch=None)
    )
    _plant_wp_task(primary_dir)
    _plant_analysis_report(primary_dir)
    return repo


def _coord_materialized(tmp_path: Path) -> Path:
    """Coord topology with a GENUINELY materialized coord worktree.

    Proves a PRIMARY-partition kind resolves PRIMARY even when a coord
    surface exists and is fully populated -- it is never a race with the
    coord side, unlike the kind-blind resolvers the corrected comments (T027)
    warn about.
    """
    repo = _make_git_repo(tmp_path, "coord-materialized")
    coord_root = CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8)
    primary_dir, coord_dir = build_coord_materialized(
        repo,
        _HANDLE,
        _COORD_BRANCH,
        coord_root,
        write_primary_meta=_write_primary_meta,
        write_coord_meta=_write_primary_meta,
    )
    _plant_wp_task(primary_dir)
    _plant_analysis_report(primary_dir)

    # A DIFFERENT WP task + analysis report on coord: if a routed site ever
    # silently selected the coord surface for a PRIMARY-partition kind, the
    # equality assertions below would read this decoy content instead of the
    # primary fixture's known-good content and go red.
    _plant_wp_task(coord_dir)
    (coord_dir / "analysis-report.md").write_text("# DECOY -- coord, not primary\n", encoding="utf-8")
    return repo


def _coord_husk(tmp_path: Path) -> Path:
    """Coord worktree materialized, but its mission dir has NO meta.json."""
    repo = _make_git_repo(tmp_path, "coord-husk")
    coord_root = CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8)
    primary_dir = build_coord_husk(
        repo, _HANDLE, _COORD_BRANCH, coord_root, write_primary_meta=_write_primary_meta
    )
    _plant_wp_task(primary_dir)
    _plant_analysis_report(primary_dir)
    return repo


def _coord_worktree_empty(tmp_path: Path) -> Path:
    """Coord root materialized (create window) but no mission dir under it."""
    repo = _make_git_repo(tmp_path, "coord-empty")
    coord_root = CoordinationWorkspace.worktree_path(repo, _SLUG, _MID8)
    primary_dir = build_coord_worktree_empty(
        repo, _HANDLE, _COORD_BRANCH, coord_root, write_primary_meta=_write_primary_meta
    )
    _plant_wp_task(primary_dir)
    _plant_analysis_report(primary_dir)
    return repo


def _coord_branch_deleted(tmp_path: Path) -> Path:
    """meta.json declares a coordination_branch that was never created in git."""
    repo = _make_git_repo(tmp_path, "coord-deleted")
    primary_dir = build_coord_branch_deleted(
        repo, _HANDLE, _COORD_BRANCH, write_primary_meta=_write_primary_meta
    )
    _plant_wp_task(primary_dir)
    _plant_analysis_report(primary_dir)
    return repo


_MATERIALIZED_FIXTURES = pytest.mark.parametrize(
    "builder",
    [_flat, _coord_materialized],
    ids=["flat", "coord_materialized"],
)
_NO_RAISE_FIXTURES = pytest.mark.parametrize(
    "builder",
    [_coord_husk, _coord_worktree_empty, _coord_branch_deleted],
    ids=["coord_husk", "coord_worktree_empty", "coord_branch_deleted"],
)


# --------------------------------------------------------------------------- #
# NFR-001 -- identical directory for a materialized, non-backfilled mission.
# --------------------------------------------------------------------------- #


@_MATERIALIZED_FIXTURES
def test_analysis_report_gate_dir_resolves_primary(tmp_path: Path, builder: object) -> None:
    """``workflow.py::_analysis_report_gate_dir`` (ANALYSIS_REPORT)."""
    repo = builder(tmp_path)  # type: ignore[operator]
    expected = _compose_primary_feature_dir(repo, _HANDLE)
    resolved = _analysis_report_gate_dir(repo, _HANDLE)
    assert resolved == expected
    assert (resolved / "analysis-report.md").read_text(encoding="utf-8") == "# analysis report\n"


@_MATERIALIZED_FIXTURES
def test_mission_id_for_claim_resolves_identity_from_primary(tmp_path: Path, builder: object) -> None:
    """``workflow.py::_mission_id_for_claim`` (PRIMARY_METADATA)."""
    repo = builder(tmp_path)  # type: ignore[operator]
    assert _mission_id_for_claim(repo, _HANDLE) == _MISSION_ID


@_MATERIALIZED_FIXTURES
def test_load_primary_anchored_mission_meta_resolves_primary(tmp_path: Path, builder: object) -> None:
    """``implement.py::load_primary_anchored_mission_meta`` (PRIMARY_METADATA)."""
    repo = builder(tmp_path)  # type: ignore[operator]
    meta = load_primary_anchored_mission_meta(repo, _HANDLE)
    assert meta is not None
    assert meta["mission_id"] == _MISSION_ID


@_MATERIALIZED_FIXTURES
def test_find_wp_file_resolves_tasks_dir_under_primary(tmp_path: Path, builder: object) -> None:
    """``workspace/context.py::find_wp_file`` (WORK_PACKAGE_TASK)."""
    repo = builder(tmp_path)  # type: ignore[operator]
    expected_dir = _compose_primary_feature_dir(repo, _HANDLE) / "tasks"
    wp_file = find_wp_file(repo, _HANDLE, "WP01")
    assert wp_file.parent == expected_dir
    assert ".worktrees" not in str(wp_file)


@_MATERIALIZED_FIXTURES
def test_primary_anchor_feature_dir_resolves_primary(tmp_path: Path, builder: object) -> None:
    """``acceptance/__init__.py::_primary_anchor_feature_dir`` (PRIMARY_METADATA)."""
    repo = builder(tmp_path)  # type: ignore[operator]
    expected = _compose_primary_feature_dir(repo, _HANDLE)
    # The ``read_dir`` argument mirrors what the real caller already resolved
    # (also PRIMARY_METADATA today) -- passing it through proves the function's
    # OWN primary re-derivation, not merely an echo of its argument.
    resolved = _primary_anchor_feature_dir(repo, _HANDLE, expected)
    assert resolved == expected


@_MATERIALIZED_FIXTURES
def test_implement_resolve_mission_type_reads_meta_from_primary(tmp_path: Path, builder: object) -> None:
    """``workflow_executor.py::implement_resolve_mission_type`` (PRIMARY_METADATA)."""
    repo = builder(tmp_path)  # type: ignore[operator]
    mission_type, deliverables_path = implement_resolve_mission_type(repo, _HANDLE)
    assert mission_type == "software-dev"
    assert deliverables_path is None


# --------------------------------------------------------------------------- #
# NFR-002 -- no NEW raise on husk / empty-coord / deleted-coord.
# --------------------------------------------------------------------------- #


@_NO_RAISE_FIXTURES
def test_analysis_report_gate_dir_does_not_raise(tmp_path: Path, builder: object) -> None:
    repo = builder(tmp_path)  # type: ignore[operator]
    expected = _compose_primary_feature_dir(repo, _HANDLE)
    resolved = _analysis_report_gate_dir(repo, _HANDLE)
    assert resolved == expected
    assert ".worktrees" not in str(resolved)


@_NO_RAISE_FIXTURES
def test_mission_id_for_claim_does_not_raise(tmp_path: Path, builder: object) -> None:
    repo = builder(tmp_path)  # type: ignore[operator]
    assert _mission_id_for_claim(repo, _HANDLE) == _MISSION_ID


@_NO_RAISE_FIXTURES
def test_load_primary_anchored_mission_meta_does_not_raise(tmp_path: Path, builder: object) -> None:
    repo = builder(tmp_path)  # type: ignore[operator]
    meta = load_primary_anchored_mission_meta(repo, _HANDLE)
    assert meta is not None
    assert meta["mission_id"] == _MISSION_ID


@_NO_RAISE_FIXTURES
def test_find_wp_file_does_not_raise(tmp_path: Path, builder: object) -> None:
    repo = builder(tmp_path)  # type: ignore[operator]
    expected_dir = _compose_primary_feature_dir(repo, _HANDLE) / "tasks"
    wp_file = find_wp_file(repo, _HANDLE, "WP01")
    assert wp_file.parent == expected_dir


@_NO_RAISE_FIXTURES
def test_primary_anchor_feature_dir_does_not_raise(tmp_path: Path, builder: object) -> None:
    repo = builder(tmp_path)  # type: ignore[operator]
    expected = _compose_primary_feature_dir(repo, _HANDLE)
    resolved = _primary_anchor_feature_dir(repo, _HANDLE, expected)
    assert resolved == expected


@_NO_RAISE_FIXTURES
def test_implement_resolve_mission_type_does_not_raise(tmp_path: Path, builder: object) -> None:
    repo = builder(tmp_path)  # type: ignore[operator]
    mission_type, _deliverables_path = implement_resolve_mission_type(repo, _HANDLE)
    assert mission_type == "software-dev"


# --------------------------------------------------------------------------- #
# T028 anti-vacuity: the fixtures actually diverge from a naive "always husk"
# reading -- a coord-materialized fixture's PRIMARY-partition reads must NOT
# equal the coord decoy content planted alongside it.
# --------------------------------------------------------------------------- #


def test_coord_materialized_fixture_primary_reads_are_not_the_coord_decoy(tmp_path: Path) -> None:
    repo = _coord_materialized(tmp_path)
    resolved = _analysis_report_gate_dir(repo, _HANDLE)
    content = (resolved / "analysis-report.md").read_text(encoding="utf-8")
    assert content == "# analysis report\n"
    assert "DECOY" not in content
