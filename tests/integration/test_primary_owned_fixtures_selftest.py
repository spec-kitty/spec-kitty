"""Self-test for the shared primary-owned fixtures (#5457, WP01/T004).

Non-vacuity guard: WP02 to WP05 build their red tests on these builders, so each
shape is proved to really contain the per-branch divergence they depend on.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from packaging.version import Version

from specify_cli.state.contract import primary_owned_paths
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from tests.integration.primary_owned_fixtures import (
    DECISION_INDEX_GITATTRIBUTES_LINE,
    OLDER_VERSION,
    WORKTREE_MIGRATION_ID,
    METADATA_PATH,
    LanesProject,
    Topology,
    build_older_version_lanes_project,
    commit_broken_upgrade_state,
    gitattributes_blob,
    metadata_blob,
    observe_upgrade_divergence,
    output_names_auto_rebase_failure,
    output_names_merge_failed,
    output_names_stale_metadata_refusal,
    output_names_target_content_conflict,
    output_shows_primary_owned_defect,
    upgrade_commits_on,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def _assert_older_everywhere(project: LanesProject) -> None:
    for ref in [project.target_branch, *project.branches()]:
        blob = metadata_blob(project.repo, ref)
        assert blob is not None and f"version: {OLDER_VERSION}" in blob, ref


def test_fixture_metadata_path_is_the_contract_primary_owned_path() -> None:
    assert primary_owned_paths() == frozenset({METADATA_PATH})


def test_older_version_is_below_a_registered_worktree_migration() -> None:
    auto_discover_migrations()
    migration = next(m for m in MigrationRegistry.get_all() if m.migration_id == WORKTREE_MIGRATION_ID)
    assert migration.runs_on_worktrees is True
    assert Version(migration.target_version) > Version(OLDER_VERSION)


def test_lanes_shape(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=2)
    assert project.target_branch == "work"
    assert _git(project.repo, "branch", "--show-current").strip() == "work"
    assert project.coord_branch is None and project.coord_worktree is None
    assert project.lane_ids == ["lane-a", "lane-b"]
    for lane_id, worktree in project.lane_worktrees.items():
        assert worktree.is_dir()
        assert _git(worktree, "branch", "--show-current").strip() == project.lane_branches[lane_id]
        assert (worktree / "src" / lane_id.replace("-", "_") / "m.py").is_file()
        assert (worktree / ".kittify" / "metadata.yaml").is_file()
        assert _git(worktree, "status", "--porcelain").strip() == ""
    _assert_older_everywhere(project)


def test_lanes_with_coord_shape_materialises_coordination_worktree(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes_with_coord", lanes=2)
    assert project.coord_branch and project.coord_worktree is not None
    assert project.coord_worktree.is_dir()
    assert _git(project.coord_worktree, "branch", "--show-current").strip() == project.coord_branch
    assert project.coord_branch in project.branches()
    _assert_older_everywhere(project)


@pytest.mark.parametrize("topology", ["lanes", "lanes_with_coord"])
def test_broken_state_diverges_per_branch_with_identical_gitattributes(tmp_path: Path, topology: Topology) -> None:
    project = build_older_version_lanes_project(tmp_path, topology=topology, lanes=2)
    commits = commit_broken_upgrade_state(project)
    refs = [project.target_branch, *project.branches()]
    assert set(commits) == set(refs)

    blobs = {ref: metadata_blob(project.repo, ref) for ref in refs}
    assert all(blobs.values())
    assert len(set(blobs.values())) == len(refs), "metadata.yaml must differ on every branch"
    attributes = {gitattributes_blob(project.repo, ref) for ref in refs}
    assert attributes == {DECISION_INDEX_GITATTRIBUTES_LINE}
    for ref in project.branches():
        assert len(upgrade_commits_on(project.repo, ref)) == 1
    for worktree in project.lane_worktrees.values():
        assert _git(worktree, "status", "--porcelain").strip() == ""


def test_broken_state_can_target_a_subset_of_branches(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=2)
    only = project.lane_branches["lane-a"]
    commit_broken_upgrade_state(project, branches=[only])
    assert upgrade_commits_on(project.repo, only)
    assert not upgrade_commits_on(project.repo, project.lane_branches["lane-b"])


def test_observe_upgrade_divergence_reports_every_branch(tmp_path: Path) -> None:
    """Run today's ``upgrade --yes`` and check only facts true before AND after the fix.

    Whether lane metadata diverges is deliberately NOT asserted here: that
    verdict belongs to WP02's own red test over the same ``UpgradeObservation``.
    """
    project = build_older_version_lanes_project(tmp_path, topology="lanes_with_coord", lanes=2)
    observed = observe_upgrade_divergence(project)
    assert observed.returncode == 0, observed.output
    assert observed.root_metadata is not None
    assert f"version: {OLDER_VERSION}" not in observed.root_metadata
    assert set(observed.metadata_by_branch) == set(project.branches())
    assert all(blob is not None for blob in observed.metadata_by_branch.values())
    assert set(observed.upgrade_commits_by_branch) == set(project.branches())


def test_depends_on_lanes_knob_is_recorded_in_the_manifest(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=2, depends_on_lanes={"lane-b": ("lane-a",)})
    lanes = {lane["lane_id"]: lane for lane in json.loads((project.feature_dir / "lanes.json").read_text(encoding="utf-8"))["lanes"]}
    assert lanes["lane-b"]["depends_on_lanes"] == ["lane-a"]
    assert lanes["lane-a"]["depends_on_lanes"] == []


def test_status_json_divergence_knob_makes_both_sides_differ(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=2, status_json_divergence=True)
    path = f"kitty-specs/{project.slug}/status.json"
    sides = {ref: _git(project.repo, "show", f"{ref}:{path}") for ref in [project.mission_branch, *project.lane_branches.values()]}
    assert len(set(sides.values())) == 3
    base = _git(project.repo, "show", f"{project.target_branch}:{path}")
    assert all(side != base for side in sides.values())


def test_remove_lane_worktrees_keeps_branches(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=2)
    paths = list(project.lane_worktrees.values())
    project.remove_lane_worktrees()
    assert not any(p.exists() for p in paths)
    assert project.lane_worktrees == {}
    for branch in project.lane_branches.values():
        _git(project.repo, "rev-parse", "--verify", branch)


def test_extra_worktree_modes(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=1)
    on_branch = project.extra_worktree(branch="feature/x")
    assert _git(on_branch, "branch", "--show-current").strip() == "feature/x"
    detached = project.extra_worktree(detached=True)
    assert _git(detached, "branch", "--show-current").strip() == ""
    with pytest.raises(ValueError, match="exactly one"):
        project.extra_worktree()
    with pytest.raises(ValueError, match="exactly one"):
        project.extra_worktree(branch="b", detached=True)


def test_analysis_report_knob_writes_a_report(tmp_path: Path) -> None:
    project = build_older_version_lanes_project(tmp_path, topology="lanes", lanes=1, with_analysis_report=True)
    assert (project.feature_dir / "analysis-report.md").is_file()


def test_defect_text_matchers() -> None:
    stale = "Lane lane-b is stale: overlapping files ['.gitattributes', '.kittify/metadata.yaml']"
    conflict = "TARGET_BRANCH_CONTENT_CONFLICT conflicting_path: .kittify/metadata.yaml"
    failed = "RuntimeError: Merge of kitty/x-lane-a into kitty/x failed: CONFLICT"
    rebase = "LANE_AUTO_REBASE_FAILED: no classifier rule matched /w/.kittify/metadata.yaml"
    assert output_names_stale_metadata_refusal(stale)
    assert output_names_target_content_conflict(conflict)
    assert output_names_merge_failed(failed)
    assert output_names_auto_rebase_failure(rebase)
    for text in (stale, conflict, failed, rebase):
        assert output_shows_primary_owned_defect(text)
    assert not output_shows_primary_owned_defect("Lane lane-b is stale: overlapping files ['src/a.py']")
    assert not output_names_target_content_conflict("TARGET_BRANCH_CONTENT_CONFLICT conflicting_path: src/a.py")
