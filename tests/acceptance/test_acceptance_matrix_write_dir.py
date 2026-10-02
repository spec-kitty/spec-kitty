"""Red-first: ``acceptance-verdict`` resolves its write location via ``write_dir`` (WP10, T053/T057).

Mission coord-artifact-single-home-01M3V4BE, WP10 (single-home rule, lost-
update fix, FR-003 / FR-007 / SC-003). ``acceptance_verdict.py``'s two
``commit=True`` critical sections (criterion mode / negative-invariant mode)
resolve ``matrix_dir`` ONCE, before any lock, via the ONE write-location
authority (``write_dir(ACCEPTANCE_MATRIX)``) -- never the lenient READ-side
``read_dir`` projection, which can fall back to the PRIMARY dir on an
EMPTY/UNMATERIALIZED coordination surface. This pins the zero-write-refusal
and no-root-residue halves of that contract; the "lands on coord, not a
stranded primary copy" happy path is already covered by
``tests/specify_cli/acceptance/test_acceptance_verdict_command.py::
TestAcceptanceVerdictCommand::test_lands_on_coord_surface_not_a_stranded_primary_dir``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from mission_runtime import MissionTopology
from specify_cli.acceptance.matrix import AcceptanceCriterion, AcceptanceMatrix, write_acceptance_matrix
from specify_cli.cli.commands.agent.acceptance_verdict import acceptance_verdict
from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
from tests._factories.coord_mission import (
    CoordMission,
    make_coord_mission,
    make_prefix_coord_mission,
)
from tests.integration.test_placement_partition_golden_path import _create_mission, _init_git_repo

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _root_porcelain(coord: CoordMission) -> str:
    relpath = f"kitty-specs/{coord.mission_dir_name}"
    return subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", relpath],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _seed_matrix(feature_dir: Path, slug: str) -> None:
    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001",
                    description="the feature behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pending",
                )
            ],
        ),
    )


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _record_verdict(coord: CoordMission, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.chdir(coord.repo_root)
    try:
        acceptance_verdict(
            mission=coord.mission_dir_name,
            criterion="FR-001",
            result="pass",
            verification_method=None,
            actor="tester",
            evidence=None,
            json_output=True,
        )
    except typer.Exit as exc:
        return exc.exit_code or 0
    return 0


def test_prefix_empty_seeds_then_writes_in_place(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-fix EMPTY coordination surface: the matrix must first exist
    somewhere readable (seeded from root content via ``write_dir``'s own
    materialize/seed contract) before the verdict write lands in place on
    the coordination Mission dir."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    _seed_matrix(coord.root_mission_dir, coord.mission_dir_name)
    _git(coord.repo_root, "add", "-A")
    _git(coord.repo_root, "commit", "-q", "-m", "seed acceptance-matrix on root")

    exit_code = _record_verdict(coord, monkeypatch)

    assert exit_code == 0
    coord_file = coord.coord_mission_dir / "acceptance-matrix.json"
    assert coord_file.exists()
    assert '"pass_fail": "pass"' in coord_file.read_text(encoding="utf-8")


def test_remote_only_refuses_before_any_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A remote-only coordination branch (#4970 parity): the matrix read
    itself fails closed via ``write_dir`` -- the command must not strand a
    write anywhere, and the root checkout stays clean."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, remote_only=True)
    _seed_matrix(coord.root_mission_dir, coord.mission_dir_name)
    _git(coord.repo_root, "add", "-A")
    _git(coord.repo_root, "commit", "-q", "-m", "seed acceptance-matrix on root")
    root_status_before = _root_porcelain(coord)

    monkeypatch.chdir(coord.repo_root)
    with pytest.raises(CoordinationWorktreeUnmaterialized):
        acceptance_verdict(
            mission=coord.mission_dir_name,
            criterion="FR-001",
            result="pass",
            verification_method=None,
            actor="tester",
            evidence=None,
            json_output=True,
        )

    assert not coord.coord_worktree_path.exists()
    assert _root_porcelain(coord) == root_status_before


# ---------------------------------------------------------------------------
# WP10 cycle 2, B3: a discriminating test for the ``_matrix_write_dir`` fix.
#
# Mutation (reviewer probe): reverting ``_matrix_write_dir`` to
# ``placement_seam(...).read_dir(ACCEPTANCE_MATRIX)`` leaves every OTHER test
# in this module green -- the read-side projection happily serves a
# MATERIALIZED or pre-fix-EMPTY surface too. The one state that discriminates
# is a POST-fix UNMATERIALIZED local head (the coordination worktree was torn
# down after a commit already landed there): ``read_dir`` raises
# ``CoordinationWorktreeUnmaterialized`` for every state except EMPTY/
# MATERIALIZED (AH-2's declared-PRIMARY fallback does not apply here --
# ACCEPTANCE_MATRIX is a genuine COORD-partition kind on a coord topology),
# while ``write_dir`` materializes the local head and proceeds (D22).
# ---------------------------------------------------------------------------


def _seed_matrix_two_pending_criteria(feature_dir: Path, slug: str) -> None:
    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=slug,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="FR-001",
                    description="the feature behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pending",
                ),
                AcceptanceCriterion(
                    criterion_id="FR-002",
                    description="a second, independent criterion",
                    proof_type="automated_test",
                    pass_fail="pending",
                ),
            ],
        ),
    )


def _record(coord: CoordMission, criterion: str, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.chdir(coord.repo_root)
    try:
        acceptance_verdict(
            mission=coord.mission_dir_name,
            criterion=criterion,
            result="pass",
            verification_method=None,
            actor="tester",
            evidence=None,
            json_output=True,
        )
    except typer.Exit as exc:
        return exc.exit_code or 0
    return 0


def test_post_fix_unmaterialized_local_head_materializes_and_preserves_prior_verdict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B3: record FR-001, tear the coord worktree back down (a genuine
    post-fix UNMATERIALIZED local head carrying a committed verdict), then
    record FR-002 -- both land on the coordination branch, and the first
    verdict is never lost."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    _seed_matrix_two_pending_criteria(coord.root_mission_dir, coord.mission_dir_name)
    _git(coord.repo_root, "add", "-A")
    _git(coord.repo_root, "commit", "-q", "-m", "seed acceptance-matrix on root")

    exit_code_1 = _record(coord, "FR-001", monkeypatch)
    assert exit_code_1 == 0, f"acceptance_verdict(FR-001) failed: exit {exit_code_1}"

    # Tear the coordination worktree back down: the branch now has a
    # committed FR-001=pass verdict, but its worktree is gone -- an
    # UNMATERIALIZED local head, the exact #4970/D22 shape.
    subprocess.run(
        ["git", "-C", str(coord.repo_root), "worktree", "remove", "--force", str(coord.coord_worktree_path)],
        check=True,
        capture_output=True,
    )
    assert not coord.coord_worktree_path.exists()

    exit_code_2 = _record(coord, "FR-002", monkeypatch)
    assert exit_code_2 == 0, f"acceptance_verdict(FR-002) failed: exit {exit_code_2}"

    # Both verdicts must be present on the coordination branch tip -- read
    # via ``git show`` since the worktree may have been re-materialized at a
    # fresh checkout, not necessarily the same path contents cached in-process.
    rel = f"kitty-specs/{coord.mission_dir_name}/acceptance-matrix.json"
    shown = subprocess.run(
        ["git", "-C", str(coord.repo_root), "show", f"{coord.coordination_branch}:{rel}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    import json as _json

    document = _json.loads(shown)
    rows = {row["criterion_id"]: row["pass_fail"] for row in document["criteria"]}
    assert rows == {"FR-001": "pass", "FR-002": "pass"}, rows


def test_non_coord_topology_writes_at_same_primary_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """C-008: a ``lanes``-topology Mission (no coordination surface at all)
    writes at the SAME primary path as before this WP."""
    slug = "no-coord-acceptance-verdict-demo"
    _init_git_repo(tmp_path, branch="topic")
    result = _create_mission(tmp_path, slug, MissionTopology.LANES)
    feature_dir = result.feature_dir
    _seed_matrix(feature_dir, result.mission_slug)
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "seed acceptance-matrix")

    monkeypatch.chdir(tmp_path)
    exit_code = 0
    try:
        acceptance_verdict(
            mission=result.mission_slug,
            criterion="FR-001",
            result="pass",
            verification_method=None,
            actor="tester",
            evidence=None,
            json_output=True,
        )
    except typer.Exit as exc:
        exit_code = exc.exit_code or 0

    assert exit_code == 0
    primary_file = feature_dir / "acceptance-matrix.json"
    assert primary_file.exists()
    assert '"pass_fail": "pass"' in primary_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# WP10 cycle 2, B4: ``scaffold_acceptance_matrix`` must write IN PLACE at the
# declared/write ``home`` for a MATERIALIZED coordination Mission -- never
# stage at the PRIMARY ``feature_dir`` and rely on the router's legacy
# ``shutil.copy2`` to move it.
# ---------------------------------------------------------------------------


def test_scaffold_acceptance_matrix_materialized_mission_never_router_copies(tmp_path: Path) -> None:
    """Reviewer probe (cycle 1 B4): on a MATERIALIZED coordination Mission,
    ``scaffold_acceptance_matrix(..., home_dir=coord_dir, repo_root=repo)``
    must land the matrix directly on the coordination Mission dir -- no
    ``shutil.copy2`` call, and the returned path IS the coordination copy,
    never a stray primary one."""
    import shutil
    from unittest.mock import patch

    from specify_cli.acceptance.matrix import scaffold_acceptance_matrix

    coord = make_coord_mission(tmp_path, MissionTopology.COORD, materialized=True)

    real_copy2 = shutil.copy2
    with patch("shutil.copy2", side_effect=real_copy2) as copy2_spy:
        result_path = scaffold_acceptance_matrix(
            coord.root_mission_dir,
            coord.mission_dir_name,
            requirement_ids=["FR-001"],
            home_dir=coord.coord_mission_dir,
            repo_root=coord.repo_root,
        )

    copy2_spy.assert_not_called()
    assert result_path == coord.coord_mission_dir / "acceptance-matrix.json"
    assert result_path is not None and result_path.exists()
    assert not (coord.root_mission_dir / "acceptance-matrix.json").exists(), (
        "scaffold_acceptance_matrix must not strand a primary-checkout copy for a MATERIALIZED coordination Mission"
    )
