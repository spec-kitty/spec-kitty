"""Write-side check: #2404 / #2804 (FR-009 / SC-005, write-surface-coherence WP08).

Permanent guard — #2404 is fixed. Formerly a red-first
``@pytest.mark.regression`` reproduction under ``tests/regression/``;
relocated here and un-marked (2026-08 landing fold: make
``@pytest.mark.regression`` mean exactly one thing) once the write-surface
fix landed and this suite started passing.

The finalize-time scaffolder (``acceptance/matrix.py::scaffold_acceptance_matrix``,
called from ``mission_finalize.py::_scaffold_acceptance_matrix_if_lane_based``)
used to author ``acceptance-matrix.json`` with a bare, unrouted disk write
regardless of the mission's topology — the PRIMARY-husk producer #2404 names
(D-PLAN-16). WP08 T040/T041 route that write through the coord-aware write-seam
(mirroring the already-fixed sibling ``issue-matrix.json`` scaffold) so no code
path authors a PRIMARY-partition ``acceptance-matrix.json`` under a coordination
topology.

T042 (SC-005 / G1): this is the durable, WRITE-SIDE regression guard — not a
merge-outcome assertion (that is ``tests/merge/
test_issue_2804_merge_resets_gate_artifacts.py``, a defense-in-depth net for a
divergence that predates the write-surface fix, per D-PLAN-7). Two legs:

1. A static census of every ``write_acceptance_matrix(`` call site inside the two
   owned modules (``acceptance/matrix.py`` / ``acceptance/gates_core.py``),
   asserted exhaustive against a reviewed allowlist — a new call site added
   without updating this test is a conscious, reviewed decision, not silent drift.
2. A behavioral check driving the REAL ``scaffold_acceptance_matrix`` against a
   real coord-topology git fixture: the authored matrix lands on the
   coordination branch, and the PRIMARY checkout is left with no residue copy.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from ulid import ULID

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MATRIX_MODULE = Path("src/specify_cli/acceptance/matrix.py")
_GATES_CORE_MODULE = Path("src/specify_cli/acceptance/gates_core.py")
_MATRIX_FILENAME = "acceptance-matrix.json"

# Reviewed census (G1): every ``write_acceptance_matrix(`` call site as of WP08.
# A file's count is the number of CALL sites (never the ``def``). Adding a new
# call site must update this map — the whole point of a write-side check is
# that a future divergent-write regression cannot slip in silently.
_EXPECTED_CALL_SITE_COUNTS: dict[Path, int] = {
    # ``write_and_commit_acceptance_matrix``'s ``_stage`` thunk (coord-aware,
    # routed via the write-seam) + ``scaffold_acceptance_matrix``'s legacy
    # bare-write fallback (only reached when ``repo_root`` is omitted, T040)
    # + ``locked_reread_splice_and_write``'s ``commit=False`` leg (#4887).
    # That third site is the accept-fill leg T041 reviewed, relocated out of
    # ``gates_core.py`` by #4974: it still writes to the caller's
    # ``matrix_dir`` (``context.surface``, the coord-aware gate-context
    # surface, never a hardcoded PRIMARY dir) and still never commits.
    _MATRIX_MODULE: 3,
    # Since #4974 the accept gate reaches the matrix only through the shared
    # locked seam above; a direct write here would bypass the lock again.
    _GATES_CORE_MODULE: 0,
}


def _count_write_acceptance_matrix_calls(module_path: Path) -> int:
    """Count ``write_acceptance_matrix(`` occurrences that are CALLS, not the def."""
    text = (Path(__file__).resolve().parents[2] / module_path).read_text(encoding="utf-8")
    calls = re.findall(r"(?<!def )write_acceptance_matrix\(", text)
    return len(calls)


@pytest.mark.parametrize("module_path", sorted(_EXPECTED_CALL_SITE_COUNTS))
def test_write_acceptance_matrix_call_sites_are_censused(module_path: Path) -> None:
    """G1 static leg: every ``write_acceptance_matrix`` call site is accounted for.

    A new, un-reviewed call site changes this count and fails here — forcing the
    author to add it to :data:`_EXPECTED_CALL_SITE_COUNTS` (and, in review,
    justify that it never authors a PRIMARY-partition matrix under coord
    topology) instead of silently reintroducing the #2404 husk-producer class.
    """
    expected = _EXPECTED_CALL_SITE_COUNTS[module_path]
    actual = _count_write_acceptance_matrix_calls(module_path)
    assert actual == expected, (
        f"{module_path}: expected {expected} write_acceptance_matrix(...) call "
        f"site(s), found {actual}. A new call site must be reviewed for the "
        "#2404 write-surface guarantee (never author a PRIMARY-partition "
        "acceptance-matrix.json under coord topology) and added to "
        "_EXPECTED_CALL_SITE_COUNTS."
    )


# ---------------------------------------------------------------------------
# Behavioral leg (G1): scaffold_acceptance_matrix under REAL coord topology.
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@dataclass(frozen=True)
class _CoordMission:
    repo_root: Path
    mission_slug: str
    feature_dir: Path
    coordination_branch: str
    target_branch: str


def _build_coord_mission(tmp_path: Path) -> _CoordMission:
    """A real coord-topology mission — mirrors ``test_write_surface_placement_
    guard.py``'s fixture shape (production-shaped ULID identity, real branches).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    target_branch = "feat/write-surface-wp08-guard"
    _git(repo, "init", "-q", "-b", target_branch)
    _git(repo, "config", "user.email", "guard@example.com")
    _git(repo, "config", "user.name", "WP08 Guard")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("project: guard-suite\n", encoding="utf-8")

    mission_id = str(ULID())
    mid8 = mission_id[:8]
    slug = f"write-surface-wp08-guard-{mid8}"
    coordination_branch = f"kitty/mission-{slug}"

    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mid8": mid8,
                "mission_slug": slug,
                "target_branch": target_branch,
                "coordination_branch": coordination_branch,
                "topology": "coord",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n\n## Requirements\n\n- FR-001\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed coord mission")
    _git(repo, "branch", coordination_branch)

    return _CoordMission(
        repo_root=repo.resolve(),
        mission_slug=slug,
        feature_dir=feature_dir,
        coordination_branch=coordination_branch,
        target_branch=target_branch,
    )


@pytest.fixture
def coord_mission(tmp_path: Path) -> _CoordMission:
    from mission_runtime import resolve_topology, routes_through_coordination

    mission = _build_coord_mission(tmp_path)
    assert routes_through_coordination(
        resolve_topology(mission.repo_root, mission.mission_slug)
    ), "fixture precondition violated: mission must route through coordination"
    return mission


def _file_exists_on_branch(repo: Path, branch: str, rel_path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{branch}:{rel_path}"],
        capture_output=True,
    )
    return result.returncode == 0


def test_scaffold_acceptance_matrix_lands_on_coord_never_primary_husk(
    coord_mission: _CoordMission,
) -> None:
    """T040/T041 (#2404): under coord topology, scaffolding the acceptance
    matrix at finalize time authors it on the COORDINATION branch — with no
    PRIMARY-partition husk left on the target-branch checkout — instead of the
    pre-fix bare write straight into ``feature_dir`` regardless of topology.
    """
    from specify_cli.acceptance.matrix import MATRIX_FILENAME, scaffold_acceptance_matrix

    assert MATRIX_FILENAME == _MATRIX_FILENAME

    result = scaffold_acceptance_matrix(
        coord_mission.feature_dir,
        coord_mission.mission_slug,
        requirement_ids=["FR-001"],
        repo_root=coord_mission.repo_root,
    )
    assert result is not None, "scaffold was refused; expected a committed coord write"

    # No PRIMARY-partition husk survives on the working tree: the write-seam's
    # residue cleanup (R6) unlinks the staged primary copy once the coord
    # commit lands.
    assert not (coord_mission.feature_dir / _MATRIX_FILENAME).exists(), (
        "acceptance-matrix.json was left as a residue on the PRIMARY checkout "
        "after a coord-routed scaffold — exactly the #2404 husk-producer defect"
    )
    # Nor is it committed on the target/PRIMARY branch.
    assert not _file_exists_on_branch(
        coord_mission.repo_root, coord_mission.target_branch,
        f"kitty-specs/{coord_mission.mission_slug}/{_MATRIX_FILENAME}",
    ), "acceptance-matrix.json must not be committed on the PRIMARY target branch under coord topology"

    # It IS committed on the coordination branch — the single write surface.
    assert _file_exists_on_branch(
        coord_mission.repo_root, coord_mission.coordination_branch,
        f"kitty-specs/{coord_mission.mission_slug}/{_MATRIX_FILENAME}",
    ), "acceptance-matrix.json must be committed on the coordination branch (the single write surface)"


def test_scaffold_acceptance_matrix_without_repo_root_keeps_legacy_bare_write(
    tmp_path: Path,
) -> None:
    """Non-regression: omitting ``repo_root`` (every pre-existing caller/test)
    preserves the historical bare write to ``feature_dir`` byte-for-byte."""
    from specify_cli.acceptance.matrix import scaffold_acceptance_matrix

    feature_dir = tmp_path / "kitty-specs" / "010-legacy-caller"
    feature_dir.mkdir(parents=True)

    result = scaffold_acceptance_matrix(feature_dir, "010-legacy-caller", requirement_ids=["FR-001"])

    assert result == feature_dir / _MATRIX_FILENAME
    assert result is not None and result.exists()
