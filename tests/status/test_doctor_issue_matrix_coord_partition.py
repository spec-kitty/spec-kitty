"""``check_issue_matrix`` on the coordination partition (#5222, F1/leg 2).

``check_issue_matrix(feature_dir, repo_root=..., mission_slug=...)`` resolves
its matrix source through :func:`~mission_runtime.issue_matrix_partition.
resolve_issue_matrix_partition` (via ``_resolve_check_issue_matrix_source``)
only AFTER gating references are discovered -- but that resolution call
itself can raise ``IssueMatrixRefReadError`` when GATING references exist and
neither partition ever authored a matrix at all (an unmaterialized coord
worktree with no matrix committed on the retained branch ref either). Before
the fix that call was unguarded and the exception escaped as a bare
traceback; this file pins the RED-before / GREEN-after shape as a WARNING
finding instead.

Fixtures reuse ``tests/policy/test_merge_gates_issue_matrix.py``'s real-git
coordination-mission builder rather than re-authoring it a fourth time.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.doctor import Category, Severity, check_issue_matrix
from tests.policy import test_merge_gates_issue_matrix as merge_gate_fixtures

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def test_gating_refs_no_matrix_on_either_partition_is_a_warning_not_a_crash(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    merge_gate_fixtures._init_git_repo(repo)
    mission_slug, feature_dir = merge_gate_fixtures._build_coord_mission(repo, mid8="01KZR6AA", primary_matrix=None, coord_matrix=None)

    findings = check_issue_matrix(feature_dir, repo_root=repo, mission_slug=mission_slug)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == Severity.WARNING
    assert finding.category == Category.ISSUE_MATRIX
    assert "could not be read from the coordination partition" in finding.message


def test_zero_gating_refs_coord_mission_is_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The paired positive control: zero gating references never even
    attempts the coord-partition probe, so it is clean, not a crash and not a
    warning."""
    repo = tmp_path / "repo"
    merge_gate_fixtures._init_git_repo(repo)
    monkeypatch.setattr(merge_gate_fixtures, "_GATING_SPEC_TEXT", "# Spec\n\nNo issue references here.\n")
    mission_slug, feature_dir = merge_gate_fixtures._build_coord_mission(repo, mid8="01KZR6BB", primary_matrix=None, coord_matrix=None)

    findings = check_issue_matrix(feature_dir, repo_root=repo, mission_slug=mission_slug)

    assert findings == []


def test_gating_refs_with_coord_matrix_present_resolves_clean(tmp_path: Path) -> None:
    """Positive control on the CRASH fixture's exact fixture shape: once the
    coord ref carries a valid terminal row, resolution succeeds and there is
    nothing to warn about."""
    repo = tmp_path / "repo"
    merge_gate_fixtures._init_git_repo(repo)
    mission_slug, feature_dir = merge_gate_fixtures._build_coord_mission(
        repo,
        mid8="01KZR6CC",
        primary_matrix={merge_gate_fixtures._ISSUE_KEY: "in-mission"},
        coord_matrix={merge_gate_fixtures._ISSUE_KEY: "fixed"},
    )

    findings = check_issue_matrix(feature_dir, repo_root=repo, mission_slug=mission_slug)

    assert findings == []
