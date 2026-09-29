"""Issue #87: the allocator's git merges must resolve ``spec-kitty`` without
the CLI being on the ambient PATH.

``worktree_allocator._merge_recorded_planning_commit`` and
``_merge_dependency_lane_tips`` ran ``git merge`` via ``subprocess.run`` with
no ``env=``, so the custom merge drivers the CLI registers
(``_ensure_merge_driver_git_config``; committed ``.gitattributes`` maps
``kitty-specs/**/status.events.jsonl`` to them) resolved bare ``spec-kitty``
through the ambient PATH. Any caller whose PATH omits this CLI — invoked by
absolute path, through a wrapper, from CI, or from an agent harness — got
``spec-kitty: command not found`` inside the driver (exit 127), so git
reported CONFLICT on an add/add divergence a successful driver run would have
reconciled, and :class:`PlanningCommitMergeConflictError` /
:class:`DependencyLaneMergeConflictError` fired on a merge that would have
succeeded.

The fix routes both merges (and their aborts) through
``lanes/merge.py::_make_merge_env``, which prepends THIS interpreter's venv
bin dir to the subprocess PATH. These tests strip that directory from PATH
entirely and drive the real production entry points: pre-fix both raise,
post-fix the union driver reconciles the add/add divergence and BOTH sides'
events survive — proving the driver actually fired via the routed env, not
merely that no exception was raised. Repo shape mirrors
``test_worktree_allocator_merge_driver_selfheal.py`` (same add/add divergence;
there the missing half was the driver's git-config, here it is the env).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import code_lane_branch_name
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    _merge_dependency_lane_tips,
    allocate_lane_worktree,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "issue-87-merge-env"
# Crockford-base32 ULID shape (26 chars) already accepted by resolve_mid8 in
# tests/lanes/test_issue_2993_lane_planning_ancestry.py.
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
    """A repo shaped like ``spec-kitty init`` output: ``.gitattributes``
    committed with the driver mapping, driver git-config unregistered."""
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitattributes").write_text(_EVENT_LOG_GITATTRIBUTES_ENTRY + "\n", encoding="utf-8")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed (spec-kitty init shape)")


def _write_status_event(feature_dir: Path, *, event_id: str, at: str) -> None:
    events_path = feature_dir / "status.events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"event_id": event_id, "at": at, "kind": "wp_status_transition"}
    events_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _assert_driver_unregistered(repo: Path) -> None:
    """Pin the precondition that only the env routing is under test: the
    driver's git-config is unset before the allocator runs (the self-heal in
    the allocator registers it — see
    ``test_worktree_allocator_merge_driver_selfheal.py``)."""
    result = subprocess.run(
        ["git", "-C", str(repo), "config", "--get", "merge.spec-kitty-event-log.driver"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "test setup invariant violated: the merge driver git-config must be unregistered before the allocator merge runs"


def _strip_this_venvs_spec_kitty_from_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove THIS interpreter's venv bin dir from the process PATH.

    This is the exact condition under which #87 reproduced: the ambient PATH
    cannot resolve ``spec-kitty`` (nor any other copy of it — asserted below),
    so only ``_make_merge_env()``'s prepend can put the CLI where git's driver
    invocation finds it.
    """
    venv_bin = Path(sys.executable).parent
    kept = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        path = Path(entry)
        if path == venv_bin or path.resolve() == venv_bin.resolve():
            continue
        if (path / "spec-kitty").is_file():
            continue
        kept.append(entry)
    monkeypatch.setenv("PATH", os.pathsep.join(kept))

    assert shutil.which("git") is not None, (
        "test setup broken: git itself must stay resolvable after stripping the venv bin dir, or the scenario does not model #87"
    )
    assert shutil.which("spec-kitty") is None, (
        "test setup invariant violated: spec-kitty still resolves on the "
        f"stripped PATH ({os.environ['PATH']!r}), so this test can no longer "
        "tell the fix apart from a no-op"
    )


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
        computed_at="2026-08-25T10:00:00Z",
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


class TestPlanningCommitMergeResolvesDriverWithoutCliOnPath:
    def test_fresh_lane_allocation_merges_recorded_planning_commit_with_stripped_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        _assert_driver_unregistered(repo)

        coord_branch = f"kitty/mission-{MISSION_SLUG}"
        _git(repo, "branch", coord_branch)

        feature_dir = repo / "kitty-specs" / MISSION_SLUG

        # Coordination branch independently ADDS status.events.jsonl.
        _git(repo, "checkout", "-q", coord_branch)
        _write_status_event(feature_dir, event_id="evt-coord-claimed", at="2026-08-25T09:00:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "status: WP01 claimed")

        # Target branch independently ADDS the SAME path with DIFFERENT
        # content — the add/add divergence only the union driver reconciles.
        _git(repo, "checkout", "-q", "main")
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "spec.md").write_text("# Issue 87\n", encoding="utf-8")
        (feature_dir / "tasks.md").write_text("## WP01\n- [ ] T001\n", encoding="utf-8")
        _write_status_event(feature_dir, event_id="evt-mission-created", at="2026-08-25T08:00:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "docs: spec+tasks+mission-created event")
        planning_commit_sha = _git(repo, "rev-parse", "HEAD")

        manifest = _make_manifest(coord_branch, planning_commit_sha=planning_commit_sha)
        _strip_this_venvs_spec_kitty_from_path(monkeypatch)

        # Regression assertion: pre-fix the driver exits 127 ("command not
        # found") and this raises PlanningCommitMergeConflictError.
        _worktree_path, lane_branch = allocate_lane_worktree(
            repo_root=repo,
            mission_slug=MISSION_SLUG,
            wp_id=WP_ID,
            lanes_manifest=manifest,
        )

        post_check = _git(repo, "config", "--get", "merge.spec-kitty-event-log.driver")
        assert post_check == _EXPECTED_DRIVER_COMMAND

        # The union driver actually FIRED despite the stripped ambient PATH:
        # both sides' events survive in the merged lane branch (read via git
        # plumbing — a coord-topology lane worktree sparse-excludes the file
        # from disk by design, FR-024/FR-025/FR-029).
        merged_text = _git(repo, "show", f"{lane_branch}:kitty-specs/{MISSION_SLUG}/status.events.jsonl")
        assert "evt-coord-claimed" in merged_text, f"coordination-branch event lost from the merged log: {merged_text!r}"
        assert "evt-mission-created" in merged_text, f"planning-commit event lost from the merged log: {merged_text!r}"


class TestDependencyTipMergeResolvesDriverWithoutCliOnPath:
    """Same defect, second call site: ``_merge_dependency_lane_tips``."""

    def test_dependency_tip_merge_succeeds_with_stripped_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo = tmp_path / "repo"
        _init_repo(repo)
        _assert_driver_unregistered(repo)

        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        dep_branch = code_lane_branch_name(MISSION_SLUG, "lane-dep")

        # Dependency lane independently ADDS status.events.jsonl.
        _git(repo, "branch", dep_branch)
        _git(repo, "checkout", "-q", dep_branch)
        _write_status_event(feature_dir, event_id="evt-dep-lane", at="2026-08-25T09:00:00Z")
        _git(repo, "add", "kitty-specs")
        _git(repo, "commit", "-q", "-m", "status: dep lane event")
        _git(repo, "checkout", "-q", "main")

        # The dependent lane's worktree independently ADDS the SAME path with
        # DIFFERENT content before the dep-tip merge runs.
        dependent_branch = code_lane_branch_name(MISSION_SLUG, "lane-c")
        dependent_wt = repo / ".worktrees" / f"{MISSION_SLUG}-lane-c"
        dependent_wt.parent.mkdir(parents=True, exist_ok=True)
        _git(repo, "worktree", "add", "-b", dependent_branch, str(dependent_wt), "main")
        _write_status_event(
            dependent_wt / "kitty-specs" / MISSION_SLUG,
            event_id="evt-dependent-lane",
            at="2026-08-25T08:00:00Z",
        )
        _git(dependent_wt, "add", "kitty-specs")
        _git(dependent_wt, "commit", "-q", "-m", "status: dependent lane event")

        dep_lane = ExecutionLane(
            lane_id="lane-dep",
            wp_ids=("WP02",),
            write_scope=("src/**",),
            predicted_surfaces=("core",),
            depends_on_lanes=(),
            parallel_group=0,
        )
        dependent_lane = ExecutionLane(
            lane_id="lane-c",
            wp_ids=(WP_ID,),
            write_scope=("src/**",),
            predicted_surfaces=("core",),
            depends_on_lanes=("lane-dep",),
            parallel_group=1,
        )
        manifest = LanesManifest(
            version=1,
            mission_slug=MISSION_SLUG,
            mission_id=MISSION_ID,
            mission_branch=f"kitty/mission-{MISSION_SLUG}",
            target_branch="main",
            lanes=[dep_lane, dependent_lane],
            computed_at="2026-08-25T10:00:00Z",
            computed_from="test",
        )
        _strip_this_venvs_spec_kitty_from_path(monkeypatch)

        # Regression assertion: pre-fix this raises DependencyLaneMergeConflictError.
        _merge_dependency_lane_tips(repo, dependent_wt, MISSION_SLUG, dependent_lane, manifest)

        post_check = _git(repo, "config", "--get", "merge.spec-kitty-event-log.driver")
        assert post_check == _EXPECTED_DRIVER_COMMAND

        merged_text = (dependent_wt / "kitty-specs" / MISSION_SLUG / "status.events.jsonl").read_text(encoding="utf-8")
        assert "evt-dep-lane" in merged_text, f"dep-lane event lost: {merged_text!r}"
        assert "evt-dependent-lane" in merged_text, f"dependent-lane event lost: {merged_text!r}"
