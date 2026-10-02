"""Red-first: the migrated ``write_dir`` writers resolve PUBLISHED (D23) correctly (WP10 cycle 2, B5).

Mission coord-artifact-single-home-01M3V4BE, WP10. ``tests/specify_cli/cli/
commands/test_issue_3033_post_consolidation_write.py`` already pins the
E2-CONSOLIDATED outcome through the LOW-LEVEL ``write_artifact(files=...)``
entry point directly. It does not exercise the writers THIS WP migrated --
``append_tracer_finding`` / ``write_issue_matrix`` -- whose ``_stage=`` thunks
now resolve ``placement_seam(...).write_dir(kind)`` themselves (T055/T056).
``write_dir``'s PUBLISHED/E2 short-circuit (research D23,
``resolution.py::_published_e2_write_dir``) must fire BEFORE any coordination
probe, so a genuinely retired mission (coordination branch ALSO deleted, the
#3033 T007 fixture shape) never raises ``CoordinationBranchDeleted`` from
inside the writer's own staging thunk. This pins that both migrated writers
commit on the Primary Branch with exactly ONE ``primary`` ``SurfaceOutcome``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.mission_metadata import load_meta
from specify_cli.retrospective.tracer_writer import append_tracer_finding
from specify_cli.tasks.issue_matrix import IssueMatrixEntry, write_issue_matrix
from tests.specify_cli.cli.commands.test_issue_3033_post_consolidation_write import (
    _branch_exists,
    _build_e2_mission_coord,
    _current_branch,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _published_coord_mission(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    mission_slug, target_branch, coordination_branch = _build_e2_mission_coord(repo)
    feature_dir = repo / "kitty-specs" / mission_slug

    # Sanity: a genuine E2/PUBLISHED state -- BOTH the Target Ref and the
    # coordination branch are gone from git (the realistic fully-retired
    # end state), and we are on the Primary Branch.
    meta = load_meta(feature_dir)
    assert meta is not None
    assert meta["baseline_merge_commit"], meta
    assert not _branch_exists(repo, target_branch)
    assert not _branch_exists(repo, coordination_branch)
    assert _current_branch(repo) == "main"
    return repo, mission_slug


def test_append_tracer_finding_commits_on_main_with_one_primary_surface(tmp_path: Path) -> None:
    repo, mission_slug = _published_coord_mission(tmp_path)
    policy = ProtectionPolicy.resolve(repo)

    result = append_tracer_finding(
        repo_root=repo,
        mission_slug=mission_slug,
        category="tooling-friction",
        entry="a post-consolidation finding",
        actor="tester",
        policy=policy,
    )

    assert result.status == "committed", result.diagnostic
    assert result.destination_surface == "main"
    assert len(result.surfaces) == 1
    assert result.surfaces[0].surface == "primary"
    assert result.surfaces[0].branch == "main"
    assert result.surfaces[0].status == "committed"

    committed_file = repo / "kitty-specs" / mission_slug / "traces" / "tooling-friction.md"
    assert committed_file.exists()
    assert "a post-consolidation finding" in committed_file.read_text(encoding="utf-8")


def test_write_issue_matrix_commits_on_main_with_one_primary_surface(tmp_path: Path) -> None:
    repo, mission_slug = _published_coord_mission(tmp_path)
    policy = ProtectionPolicy.resolve(repo)

    rows = {"#4201": IssueMatrixEntry(verdict="fixed", evidence_ref="commit abc123")}
    result = write_issue_matrix(
        repo_root=repo,
        mission_slug=mission_slug,
        rows=rows,
        policy=policy,
        actor="tester",
    )

    assert result.status == "committed", result.diagnostic
    assert result.destination_surface == "main"
    assert len(result.surfaces) == 1
    assert result.surfaces[0].surface == "primary"
    assert result.surfaces[0].branch == "main"
    assert result.surfaces[0].status == "committed"

    committed_file = repo / "kitty-specs" / mission_slug / "issue-matrix.json"
    assert committed_file.exists()
    assert '"#4201"' in committed_file.read_text(encoding="utf-8")
