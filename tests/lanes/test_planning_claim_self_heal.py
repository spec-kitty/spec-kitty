"""#3912: planning materialization and claim self-heal must agree."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.implement_support import (
    check_claim_ancestry,
    create_lane_workspace,
    reenter_lane_self_heal,
    resolve_claim_ancestry_gate,
)
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.lanes.worktree_allocator import DirtyWorktreeError, DependencyLaneMergeConflictError
from specify_cli.git.commit_helpers import ProtectedBranchCommitError
from specify_cli.ownership.workspace_strategy import create_planning_workspace
from specify_cli.status.models import Lane
from specify_cli.workspace.context import ResolvedWorkspace
from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
    _MISSION_SLUG,
    _WP_DEP,
    _WP_SELF,
    _create_lane_a_branch,
    _feature_dir,
    _git,
    _init_repo,
    _seed_wp_lane,
    _write_meta_and_lanes,
)

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]


@pytest.fixture(autouse=True)
def _enable_saas_sync_feature_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")


def _planning_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_meta_and_lanes(repo)
    lanes_path = _feature_dir(repo) / "lanes.json"
    payload = json.loads(lanes_path.read_text())
    payload["lanes"][1]["lane_id"] = PLANNING_LANE_ID
    payload["planning_artifact_wps"] = [_WP_SELF]
    lanes_path.write_text(json.dumps(payload))
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("{}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "planning lane")
    tip = _create_lane_a_branch(repo)
    _git(repo, "checkout", "-qb", "feat/planning")
    _seed_wp_lane(repo, _WP_DEP, Lane.APPROVED)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "approved dependency")
    return repo, tip


def test_planning_materialization_claim_merges_approved_dependency(tmp_path: Path) -> None:
    repo, tip = _planning_repo(tmp_path)
    root = create_planning_workspace(_MISSION_SLUG, _WP_SELF, [], repo)
    workspace = ResolvedWorkspace(
        mission_slug=_MISSION_SLUG,
        wp_id=_WP_SELF,
        execution_mode="planning_artifact",
        mode_source="explicit",
        resolution_kind="repo_root",
        workspace_name=f"{_MISSION_SLUG}-{PLANNING_LANE_ID}",
        worktree_path=root,
        branch_name=None,
        lane_id=PLANNING_LANE_ID,
        lane_wp_ids=[_WP_SELF],
        context=None,
    )
    materialized = create_lane_workspace(
        repo,
        _MISSION_SLUG,
        _WP_SELF,
        _feature_dir(repo) / "tasks" / "WP02.md",
        workspace,
        read_lanes_json(_feature_dir(repo)),
        [_WP_DEP],
        "git",
    )
    assert materialized.workspace_path == repo
    assert not (repo / ".worktrees" / workspace.workspace_name).exists()
    assert not check_claim_ancestry(repo, _MISSION_SLUG, _feature_dir(repo), _WP_SELF, root).ok

    healed = resolve_claim_ancestry_gate(repo, _MISSION_SLUG, _feature_dir(repo), _WP_SELF, root)

    assert healed.ok, healed.missing_refs
    _git(repo, "merge-base", "--is-ancestor", tip, "HEAD")
    assert (root / "lane_a_output.txt").read_text() == "lane-a code\n"
    head = _git(repo, "rev-parse", "HEAD")
    assert resolve_claim_ancestry_gate(repo, _MISSION_SLUG, _feature_dir(repo), _WP_SELF, root).ok
    assert _git(repo, "rev-parse", "HEAD") == head
    assert not (repo / ".worktrees" / workspace.workspace_name).exists()


def test_protected_root_refused_without_mutation(tmp_path: Path) -> None:
    repo, _tip = _planning_repo(tmp_path)
    (repo / ".kittify" / "config.yaml").write_text("protection:\n  protected_branches: [feat/planning]\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "protect target")
    head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(ProtectedBranchCommitError):
        reenter_lane_self_heal(repo, _MISSION_SLUG, _WP_SELF)
    assert _git(repo, "rev-parse", "HEAD") == head
    assert not (repo / "lane_a_output.txt").exists()


def test_dirty_root_refused_without_losing_work(tmp_path: Path) -> None:
    repo, _tip = _planning_repo(tmp_path)
    (repo / "seed.txt").write_text("uncommitted work\n")
    head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(DirtyWorktreeError):
        reenter_lane_self_heal(repo, _MISSION_SLUG, _WP_SELF)
    assert _git(repo, "rev-parse", "HEAD") == head
    assert (repo / "seed.txt").read_text() == "uncommitted work\n"


def test_unapproved_dependency_not_merged_into_root(tmp_path: Path) -> None:
    repo, _tip = _planning_repo(tmp_path)
    _seed_wp_lane(repo, _WP_DEP, Lane.IN_PROGRESS)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "dependency needs further work")
    head = _git(repo, "rev-parse", "HEAD")
    assert reenter_lane_self_heal(repo, _MISSION_SLUG, _WP_SELF) == repo
    assert _git(repo, "rev-parse", "HEAD") == head
    assert not (repo / "lane_a_output.txt").exists()


def test_conflicting_dependency_refuses_claim_and_restores_root(tmp_path: Path) -> None:
    repo, _tip = _planning_repo(tmp_path)
    (repo / "lane_a_output.txt").write_text("independent root output\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "divergent root output")
    head = _git(repo, "rev-parse", "HEAD")
    with pytest.raises(DependencyLaneMergeConflictError):
        resolve_claim_ancestry_gate(repo, _MISSION_SLUG, _feature_dir(repo), _WP_SELF, repo)
    assert _git(repo, "rev-parse", "HEAD") == head
    assert (repo / "lane_a_output.txt").read_text() == "independent root output\n"
    assert not (repo / ".git" / "MERGE_HEAD").exists()


def test_recorded_planning_commit_heals_without_pulling_unapproved_code(tmp_path: Path) -> None:
    repo, _tip = _planning_repo(tmp_path)
    _git(repo, "checkout", "-qb", "recorded-planning")
    (repo / "plan.md").write_text("recorded plan\n")
    _git(repo, "add", "plan.md")
    _git(repo, "commit", "-qm", "recorded planning commit")
    recorded = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "feat/planning")
    lanes_path = _feature_dir(repo) / "lanes.json"
    payload = json.loads(lanes_path.read_text())
    payload["planning_commit_sha"] = recorded
    # #4827: this fixture's ``target_branch`` (inherited "main" from
    # `_write_meta_and_lanes`) never advances past the initial "chore:
    # planning artifacts" commit in this scenario -- the whole test operates
    # on "feat/planning" / "recorded-planning" instead. `recorded` is a
    # SIBLING of "feat/planning"'s own further commits (both branched off
    # "approved dependency"), so it is not reachable from either "main" or
    # "feat/planning" -- under the #4827 orphan classifier that reads as
    # ORPHANED, not the "genuinely recorded but not yet self-healed into
    # THIS workspace" shape this test means to exercise. Point
    # ``target_branch`` at "recorded-planning" itself (trivially an ancestor
    # of its own tip) so the pin classifies ADVANCED and the self-heal MERGE
    # mechanics this test locks are what actually runs.
    payload["target_branch"] = "recorded-planning"
    lanes_path.write_text(json.dumps(payload))
    _seed_wp_lane(repo, _WP_DEP, Lane.IN_PROGRESS)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "record frozen planning SHA and dependency status")

    assert not check_claim_ancestry(repo, _MISSION_SLUG, _feature_dir(repo), _WP_SELF, repo).ok
    assert resolve_claim_ancestry_gate(repo, _MISSION_SLUG, _feature_dir(repo), _WP_SELF, repo).ok
    _git(repo, "merge-base", "--is-ancestor", recorded, "HEAD")
    assert (repo / "plan.md").read_text() == "recorded plan\n"
    assert not (repo / "lane_a_output.txt").exists()
