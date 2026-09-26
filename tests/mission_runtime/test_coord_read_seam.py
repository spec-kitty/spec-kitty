"""coord-commit-integrity SURFACE A: the shared coord-read seam + classifier.

Pins the two mission_runtime additions this surface lands:

* ``coord_read_dir_for(repo_root, slug, kind)`` (#5) — the ONE topology-guarded
  coord-read helper both ``gates_core._acceptance_matrix_read_dir`` and
  ``accept._coord_worktree_root`` now consume. It resolves the COORDINATION read
  dir for a coord-classified kind under coord / lanes-with-coord topology (proven
  against the SAME canonical ``CoordinationWorkspace.resolve`` materialiser the
  writers use) and returns ``None`` for a coord-less mission.
* ``kind_for_mission_file("baseline-tests.json")`` (#3) — the baseline classifier
  entry so its PRIMARY (``WORK_PACKAGE_TASK``) partition is DERIVABLE from the
  basename, not caller-asserted.

Real-git fixtures reuse #2462's golden-path scaffolding verbatim (do NOT
duplicate the git/mission-creation primitives), mirroring
``tests/integration/test_accept_matrix_coord_partition.py``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    coord_read_dir_for,
    is_primary_artifact_kind,
    kind_for_mission_file,
)
from specify_cli.coordination.workspace import CoordinationWorkspace

from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
    _materialize_coord_worktree,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_WORK_BRANCH = "coord-read-seam-work"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo, branch=_WORK_BRANCH)
    return repo


@pytest.mark.parametrize(
    "topology",
    [MissionTopology.COORD, MissionTopology.LANES_WITH_COORD],
)
def test_coord_read_dir_for_routes_to_materialised_coord_surface(
    tmp_path: Path, topology: MissionTopology
) -> None:
    """Under COORD *and* LANES_WITH_COORD, a coord-classified kind resolves the
    materialised coordination worktree — the SAME dir the canonical materialiser
    yields — NOT the primary checkout."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, "coord-read-demo", topology)
    coord_root = _materialize_coord_worktree(repo, result)
    # Populate the coord mission dir so the read resolver reports MATERIALIZED
    # (the way a real coord-kind ``commit_for_mission`` write does).
    coord_mission_dir = coord_root / "kitty-specs" / result.mission_slug
    coord_mission_dir.mkdir(parents=True, exist_ok=True)
    (coord_mission_dir / "issue-matrix.md").write_text("# issues\n", encoding="utf-8")

    resolved = coord_read_dir_for(
        repo, result.mission_slug, MissionArtifactKind.ISSUE_MATRIX
    )
    assert resolved is not None
    expected = coord_root / "kitty-specs" / result.mission_slug
    assert resolved.resolve() == expected.resolve()
    # Never the primary checkout under coord topology.
    assert resolved.resolve() != (repo / "kitty-specs" / result.mission_slug).resolve()


def test_coord_read_dir_for_returns_none_for_coordless_mission(tmp_path: Path) -> None:
    """A coord-less (SINGLE_BRANCH) mission routes through coordination for
    nothing: the seam returns ``None`` so the caller reads its own PRIMARY dir."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, "coordless-read-demo", MissionTopology.SINGLE_BRANCH)

    resolved = coord_read_dir_for(
        repo, result.mission_slug, MissionArtifactKind.ACCEPTANCE_MATRIX
    )
    assert resolved is None


def test_coord_read_dir_for_coord_declared_unmaterialised_is_not_coord(
    tmp_path: Path,
) -> None:
    """When the coord worktree is NOT materialised the seam must not hand back a
    fabricated ``-coord`` husk path — it resolves the primary candidate (which the
    coord-worktree-root consumer then rejects via its own ``== repo_root`` guard),
    never a non-existent coord dir."""
    repo = _repo(tmp_path)
    result = _create_mission(repo, "coord-unmat-demo", MissionTopology.COORD)

    resolved = coord_read_dir_for(
        repo, result.mission_slug, MissionArtifactKind.ISSUE_MATRIX
    )
    # No coord worktree materialised, so the resolved dir is NOT the coord husk.
    if resolved is not None:
        meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
        mid8 = str(meta["mission_id"])[:8]
        coord_root = CoordinationWorkspace.worktree_path(repo, result.mission_slug, mid8)
        assert (
            resolved.resolve()
            != (coord_root / "kitty-specs" / result.mission_slug).resolve()
        )


def test_baseline_tests_json_classifies_as_primary_work_package_task() -> None:
    """#3: ``baseline-tests.json`` classifies to the PRIMARY ``WORK_PACKAGE_TASK``
    partition, so its home is DERIVABLE from the basename (not caller-asserted)."""
    kind = kind_for_mission_file(
        "kitty-specs/demo-01ABCDEF/baseline-tests.json", mission_slug="demo-01ABCDEF"
    )
    assert kind is MissionArtifactKind.WORK_PACKAGE_TASK
    assert is_primary_artifact_kind(kind)


# ===========================================================================
# coord-read-fail-closed-01M38VVH WP01 T001 — UNMATERIALIZED must raise
# (#4959, DM-01M38VWD)
# ===========================================================================
#
# Pre-fix behavior (red): ``_classify_artifact_surface`` falls through the
# EMPTY/UNMATERIALIZED/NONE tail to ``return TopologySurface.PRIMARY, None`` —
# a coord-partition read on an UNMATERIALIZED coordination worktree (branch
# declared + present in git, worktree never created) silently returns the
# empty PRIMARY checkout instead of raising. Readers then act on that
# emptiness as if it were the real document.
#
# Post-fix behavior (green): the same read raises
# ``CoordinationWorktreeUnmaterialized`` instead.


def test_unmaterialized_coord_read_raises_instead_of_empty_primary(
    tmp_path: Path,
) -> None:
    """AC-S1: a coord-partition ``read_dir`` on ``CoordState.UNMATERIALIZED``
    raises ``CoordinationWorktreeUnmaterialized`` — never an empty-PRIMARY path.

    Builds a COORD-topology mission via ``_create_mission`` (the real
    ``mission create`` core, which mints the coordination branch in git and
    writes ``coordination_branch`` into ``meta.json``) and deliberately never
    materializes the coord worktree — the same fixture shape as
    ``test_coord_read_dir_for_coord_declared_unmaterialised_is_not_coord``
    above, which pins that the branch-declared-but-unmaterialized state is
    real and reachable without any coord worktree on disk.
    """
    from mission_runtime import placement_seam
    from specify_cli.coordination.surface_resolver import (
        CoordinationWorktreeUnmaterialized,
    )

    repo = _repo(tmp_path)
    result = _create_mission(repo, "coord-unmat-raise-demo", MissionTopology.COORD)
    # No `_materialize_coord_worktree` call: the coord branch exists in git
    # (minted by `_create_mission`) but its worktree was never created —
    # exactly `CoordState.UNMATERIALIZED`.

    seam = placement_seam(repo, result.mission_slug)

    with pytest.raises(CoordinationWorktreeUnmaterialized) as excinfo:
        seam.read_dir(MissionArtifactKind.STATUS_STATE)

    assert excinfo.value.error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"
    # The recovery text must point at materializing, never at flattening —
    # the branch exists; flattening would be a false, destructive recovery.
    assert "materializ" in excinfo.value.next_step.lower()
    assert "flatten" not in excinfo.value.next_step.lower()
