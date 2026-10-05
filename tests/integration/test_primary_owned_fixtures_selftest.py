"""Self-test for the shared primary-owned fixtures (#5457, WP01/T004).

Non-vacuity guard: the consumer tests build on these builders, so the per-branch
divergence they depend on is proved to really exist, and the defect-text matchers
they use are pinned. Plain knob and shape behaviour is not tested here: every
consumer fails loudly if a knob breaks.
"""

from __future__ import annotations

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
    Topology,
    build_older_version_lanes_project,
    commit_broken_upgrade_state,
    gitattributes_blob,
    metadata_blob,
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


def test_fixture_metadata_path_is_the_contract_primary_owned_path() -> None:
    assert primary_owned_paths() == frozenset({METADATA_PATH})


def test_older_version_is_below_a_registered_worktree_migration() -> None:
    auto_discover_migrations()
    migration = next(m for m in MigrationRegistry.get_all() if m.migration_id == WORKTREE_MIGRATION_ID)
    assert migration.runs_on_worktrees is True
    assert Version(migration.target_version) > Version(OLDER_VERSION)


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
