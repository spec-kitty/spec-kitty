"""FIX-M2-01: lane-worktree merges never activated the custom merge drivers
``spec-kitty init`` declares in ``.gitattributes``.

Root cause (docs/triage-TEST-M2-02-recent-ticket-decision-moment.md, Finding
1, root-caused): ``spec-kitty init`` (``cli/commands/init.py``) writes
``.gitattributes`` entries mapping ``kitty-specs/**/status.events.jsonl`` (and
siblings) to custom git merge drivers, but never registers the matching
``git config --local merge.<key>.driver`` entries. The only self-heal path
(:func:`specify_cli.lanes.consolidation._ensure_merge_driver_git_config`) was wired
into the mission->target squash merge (``_merge_branch_into``) and stale-lane
auto-rebase (``attempt_auto_rebase``), but NOT into
``worktree_allocator._merge_recorded_planning_commit`` /
``_merge_dependency_lane_tips`` -- the two merges ``spec-kitty implement``
actually runs when allocating a lane worktree.

On any fresh mission, the recorded planning commit (target/primary branch)
and the coordination branch each independently *add*
``kitty-specs/<slug>/status.events.jsonl`` with different content -- an
add/add divergence, the exact case the union driver exists to reconcile.
Without the driver's git-config definition, git falls back to a plain 3-way
merge and conflicts on that add/add divergence, so
``PlanningCommitMergeConflictError`` fires and ``spec-kitty implement WP01``
fails deterministically on essentially any fresh, real mission.

This module reproduces that exact add/add divergence against a repo shaped
like a genuine ``spec-kitty init`` output: the ``.gitattributes`` mapping is
committed, but the git-config half has NEVER been registered (asserted as an
explicit precondition below, so a regression that silently drops the
self-heal call is caught here, not just believed fixed). It drives the real
production entry point, :func:`allocate_lane_worktree`. Pre-fix this raises
``PlanningCommitMergeConflictError``; post-fix the union driver reconciles
both sides and the merge succeeds, with BOTH sides' events surviving in the
merged log -- proving the driver actually fired, not merely that no
exception was raised.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    _merge_dependency_lane_tips,
    allocate_lane_worktree,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "fix-m2-01-selfheal"
# Crockford-base32 ULID shape (26 chars, no I/L/O/U) -- reuses the known-good
# literal tests/lanes/test_issue_2993_lane_planning_ancestry.py already
# verified resolve_mid8 accepts; only used for isolated tmp_path repos here.
MISSION_ID = "01KYHQ9FTN3W7C5J4K2M6R8QDS"
WP_ID = "WP01"

_EVENT_LOG_GITATTRIBUTES_ENTRY = "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log"
_EXPECTED_DRIVER_COMMAND = "spec-kitty merge-driver-event-log %O %A %B"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    """A fresh repo shaped exactly like ``spec-kitty init`` leaves one:
    ``.gitattributes`` committed with the driver mapping, but the git-config
    half NEVER registered (the defect's precondition -- see the assertion in
    the test body that pins this precondition explicitly).
    """
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitattributes").write_text(
        _EVENT_LOG_GITATTRIBUTES_ENTRY + "\n", encoding="utf-8"
    )
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed (spec-kitty init shape)")


def _write_status_event(feature_dir: Path, *, event_id: str, at: str) -> None:
    events_path = feature_dir / "status.events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"event_id": event_id, "at": at, "kind": "wp_status_transition"}
    events_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _assert_driver_unregistered(repo: Path) -> None:
    """Pin the "fresh init" precondition: the driver git-config is unset.

    Without this, a test that happened to pass for an unrelated reason
    (e.g. the merge never actually diverged) could not be told apart from a
    real fix -- this is what makes the surrounding test red-before /
    green-after rather than merely "no exception raised".
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "merge.spec-kitty-event-log.driver"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        "test setup invariant violated: the merge driver git-config must be "
        "unregistered before the allocator merge runs, or this test cannot "
        "distinguish the fix from a no-op"
    )


def _use_this_venvs_spec_kitty_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prepend THIS interpreter's venv bin to PATH for the test process.

    The allocator's merge subprocesses do not override env -- they inherit
    the current process env. The driver is invoked bare as ``spec-kitty ...``
    per the real ``_MERGE_DRIVERS`` registry, so it must resolve to the SAME
    spec-kitty under test rather than any other ``spec-kitty`` a developer
    machine happens to have on PATH -- mirrors
    ``lanes/merge.py::_make_merge_env``'s identical concern.
    """
    venv_bin = str(Path(sys.executable).parent)
    monkeypatch.setenv("PATH", venv_bin + os.pathsep + os.environ.get("PATH", ""))


def _make_manifest(coordination_branch: str, *, planning_commit_sha: str) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        mission_branch=coordination_branch,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=(WP_ID,),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-08-22T10:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


class TestPlanningCommitMergeSelfHeals:
    def test_fresh_project_implement_no_longer_conflicts_on_divergent_event_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        _assert_driver_unregistered(repo)

        coord_branch = f"kitty/mission-{MISSION_SLUG}"
        _git(repo, "branch", coord_branch)

        feature_dir = repo / "kitty-specs" / MISSION_SLUG

        # Coordination branch independently ADDS status.events.jsonl -- a
        # real WP lifecycle event (e.g. the "claimed" transition, written
        # before implement allocates the worktree).
        _git(repo, "checkout", "-q", coord_branch)
        _write_status_event(feature_dir, event_id="evt-coord-claimed", at="2026-08-22T09:00:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "status: WP01 claimed")

        # Target/primary branch independently ADDS the SAME path with
        # DIFFERENT content (the MissionCreated lineage) -- the add/add
        # divergence the union driver exists to reconcile.
        _git(repo, "checkout", "-q", "main")
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "spec.md").write_text("# Fix M2-01\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("## WP01\n- [ ] T001\n", encoding="utf-8")
        _write_status_event(feature_dir, event_id="evt-mission-created", at="2026-08-22T08:00:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "docs: spec+tasks+mission-created event")
        planning_commit_sha = _git(repo, "rev-parse", "HEAD")

        manifest = _make_manifest(coord_branch, planning_commit_sha=planning_commit_sha)
        _use_this_venvs_spec_kitty_on_path(monkeypatch)

        # This is the regression assertion: pre-fix, this raises
        # PlanningCommitMergeConflictError. Post-fix, the self-heal call
        # registers the driver's git-config and the union driver reconciles
        # the add/add divergence cleanly.
        _worktree_path, lane_branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
        )

        # The git-config half must now be registered (the self-heal ran).
        post_check = _git(repo, "config", "--get", "merge.spec-kitty-event-log.driver")
        assert post_check == _EXPECTED_DRIVER_COMMAND

        # And the union driver actually FIRED (not just "no exception"):
        # both sides' events must survive in the merged lane branch. Read via
        # git plumbing (not the worktree filesystem) since a coord-topology
        # lane worktree sparse-excludes status.events.jsonl from disk by
        # design (FR-024/FR-025/FR-029) -- the object store is unaffected.
        merged_text = _git(
            repo, "show", f"{lane_branch}:kitty-specs/{MISSION_SLUG}/status.events.jsonl"
        )
        assert "evt-coord-claimed" in merged_text, (
            f"coordination-branch event lost from the merged log: {merged_text!r}"
        )
        assert "evt-mission-created" in merged_text, (
            f"planning-commit event lost from the merged log: {merged_text!r}"
        )


class TestDependencyLaneTipsMergeSelfHeals:
    """Same defect, second call site: ``_merge_dependency_lane_tips``.

    A dependent lane's worktree base independently added
    ``status.events.jsonl`` before a sibling dependency lane's tip (with its
    own independent add of the same path) is merged in -- the same add/add
    shape :func:`_merge_recorded_planning_commit` reproduces above, at the
    other call site the fix packet names.
    """

    def test_dependency_tip_merge_no_longer_conflicts_on_divergent_event_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        _assert_driver_unregistered(repo)

        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        dep_branch = lane_branch_name(MISSION_SLUG, "lane-dep")

        # Dependency lane branches off main and independently ADDS
        # status.events.jsonl (its own lifecycle event).
        _git(repo, "branch", dep_branch)
        _git(repo, "checkout", "-q", dep_branch)
        _write_status_event(feature_dir, event_id="evt-dep-lane", at="2026-08-22T09:00:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "status: dep lane event")
        _git(repo, "checkout", "-q", "main")

        # The dependent lane's own worktree, branched off main, independently
        # ADDS the SAME path with DIFFERENT content before the dep-tip merge
        # runs -- the add/add divergence.
        dependent_branch = lane_branch_name(MISSION_SLUG, "lane-c")
        dependent_wt = repo / ".worktrees" / f"{MISSION_SLUG}-lane-c"
        dependent_wt.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "-b", dependent_branch, str(dependent_wt), "main")
        _write_status_event(
            dependent_wt / "kitty-specs" / MISSION_SLUG,
            event_id="evt-dependent-lane",
            at="2026-08-22T08:00:00Z",
        )
        _git(dependent_wt, "add", "kitty-specs")
        _git(dependent_wt, "commit", "-q", "-m", "status: dependent lane event")

        dep_lane = ExecutionLane(
            lane_id="lane-dep", wp_ids=("WP02",), write_scope=("src/**",),
            predicted_surfaces=("core",), depends_on_lanes=(), parallel_group=0,
        )
        dependent_lane = ExecutionLane(
            lane_id="lane-c", wp_ids=(WP_ID,), write_scope=("src/**",),
            predicted_surfaces=("core",), depends_on_lanes=("lane-dep",), parallel_group=1,
        )
        manifest = LanesManifest(
            version=1,
            mission_slug=MISSION_SLUG,
            mission_id=MISSION_ID,
            mission_branch=f"kitty/mission-{MISSION_SLUG}",
            target_branch="main",
            lanes=[dep_lane, dependent_lane],
            computed_at="2026-08-22T10:00:00Z",
            computed_from="test",
        )
        _use_this_venvs_spec_kitty_on_path(monkeypatch)

        # Regression assertion: pre-fix, this raises
        # DependencyLaneMergeConflictError on the add/add divergence.
        _merge_dependency_lane_tips(repo, dependent_wt, MISSION_SLUG, dependent_lane, manifest)

        post_check = _git(repo, "config", "--get", "merge.spec-kitty-event-log.driver")
        assert post_check == _EXPECTED_DRIVER_COMMAND

        merged_text = (dependent_wt / "kitty-specs" / MISSION_SLUG / "status.events.jsonl").read_text(
            encoding="utf-8"
        )
        assert "evt-dep-lane" in merged_text, f"dep-lane event lost: {merged_text!r}"
        assert "evt-dependent-lane" in merged_text, f"dependent-lane event lost: {merged_text!r}"
