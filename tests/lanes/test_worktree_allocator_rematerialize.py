"""#5160 friction 1: lane allocation must regenerate a both-sides-divergent
derived ``status.json`` from the union-merged event log instead of failing closed.

``status.json`` is a derived, disposable reduced snapshot of the append-only
``status.events.jsonl`` (the sole authority). The event log union-merges via its
``spec-kitty-event-log`` driver, but the snapshot has no driver, so a both-sides
divergence conflicts and the allocator raised
``PlanningCommitMergeConflictError`` / ``DependencyLaneMergeConflictError`` — a
hard stop on a routine, safe divergence with no operator-fixable cause. The fix
regenerates the snapshot from the merged log and completes the merge, while a
genuine human-authored conflict still fails closed (no green-washing).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.merge import _make_merge_env, reconcile_derived_status_snapshot_conflicts
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.worktree_allocator import (
    DependencyLaneMergeConflictError,
    _merge_dependency_lane_tips,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "rematerialize-5160"
MISSION_ID = "01KYHQ9FTN3W7C5J4K2M6R8QDS"
_EVENT_LOG_GITATTRIBUTES_ENTRY = "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".gitattributes").write_text(_EVENT_LOG_GITATTRIBUTES_ENTRY + "\n", encoding="utf-8")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", ".gitattributes", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed (spec-kitty init shape)")


def _write_event(feature_dir: Path, *, event_id: str, wp_id: str, at: str) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {
            "event_id": event_id,
            "mission_slug": MISSION_SLUG,
            "wp_id": wp_id,
            "from_lane": "genesis",
            "to_lane": "planned",
            "at": at,
            "actor": "seed",
            "force": False,
            "execution_mode": "worktree",
            "reason": None,
            "review_ref": None,
            "evidence": None,
        }
    )
    (feature_dir / "status.events.jsonl").write_text(line + "\n", encoding="utf-8")


def _write_divergent_snapshot(feature_dir: Path, marker: str) -> None:
    """Write a divergent (non-driver) status.json so the merge add/add conflicts."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "status.json").write_text(json.dumps({"stale_side": marker}) + "\n", encoding="utf-8")


def _use_venv_spec_kitty_on_path(monkeypatch: pytest.MonkeyPatch) -> None:
    venv_bin = str(Path(sys.executable).parent)
    monkeypatch.setenv("PATH", venv_bin + os.pathsep + os.environ.get("PATH", ""))


def _manifest() -> tuple[ExecutionLane, LanesManifest]:
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
        wp_ids=("WP01",),
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
        computed_at="2026-08-22T10:00:00Z",
        computed_from="test",
    )
    return dependent_lane, manifest


def _setup_divergent_lanes(tmp_path: Path, *, human_conflict: bool) -> tuple[Path, Path]:
    """Build a dep branch and dependent worktree that both add status.events.jsonl
    (union-able) AND status.json (divergent). Optionally add a human-authored
    both-sides conflict (src/app.py). Returns (repo, dependent_worktree)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    dep_branch = lane_branch_name(MISSION_SLUG, "lane-dep")

    _git(repo, "branch", dep_branch)
    _git(repo, "checkout", "-q", dep_branch)
    _write_event(feature_dir, event_id="01EVTDEP0000000000000000AA", wp_id="WP02", at="2026-08-22T09:00:00Z")
    _write_divergent_snapshot(feature_dir, "dep")
    if human_conflict:
        (repo / "src").mkdir(exist_ok=True)
        (repo / "src" / "app.py").write_text("DEP_SIDE = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "status: dep lane event + snapshot")
    _git(repo, "checkout", "-q", "main")

    dependent_branch = lane_branch_name(MISSION_SLUG, "lane-c")
    dependent_wt = repo / ".worktrees" / f"{MISSION_SLUG}-lane-c"
    dependent_wt.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", dependent_branch, str(dependent_wt), "main")
    dep_feature = dependent_wt / "kitty-specs" / MISSION_SLUG
    _write_event(dep_feature, event_id="01EVTDEPENDENT000000000BB", wp_id="WP01", at="2026-08-22T08:00:00Z")
    _write_divergent_snapshot(dep_feature, "dependent")
    if human_conflict:
        (dependent_wt / "src").mkdir(exist_ok=True)
        (dependent_wt / "src" / "app.py").write_text("DEPENDENT_SIDE = 2\n", encoding="utf-8")
    _git(dependent_wt, "add", "-A")
    _git(dependent_wt, "commit", "-q", "-m", "status: dependent lane event + snapshot")
    return repo, dependent_wt


def test_divergent_status_json_regenerated_not_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, dependent_wt = _setup_divergent_lanes(tmp_path, human_conflict=False)
    dependent_lane, manifest = _manifest()
    _use_venv_spec_kitty_on_path(monkeypatch)

    # Pre-fix this raised DependencyLaneMergeConflictError on the status.json
    # add/add divergence; post-fix the snapshot is regenerated and the merge
    # completes.
    _merge_dependency_lane_tips(repo, dependent_wt, MISSION_SLUG, dependent_lane, manifest)

    feature_dir = dependent_wt / "kitty-specs" / MISSION_SLUG
    snapshot_text = (feature_dir / "status.json").read_text(encoding="utf-8")
    assert "<<<<<<<" not in snapshot_text
    parsed = json.loads(snapshot_text)  # regenerated, valid JSON snapshot
    assert "stale_side" not in parsed  # not either divergent hand-written copy

    # The union driver still fired: both sides' events survive.
    events_text = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8")
    assert "01EVTDEP0000000000000000AA" in events_text
    assert "01EVTDEPENDENT000000000BB" in events_text


def test_human_authored_conflict_still_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, dependent_wt = _setup_divergent_lanes(tmp_path, human_conflict=True)
    dependent_lane, manifest = _manifest()
    _use_venv_spec_kitty_on_path(monkeypatch)

    # A genuine human-authored both-sides conflict (src/app.py) must still fail
    # closed — the derived-snapshot regeneration must never green-wash it.
    with pytest.raises(DependencyLaneMergeConflictError):
        _merge_dependency_lane_tips(repo, dependent_wt, MISSION_SLUG, dependent_lane, manifest)


def test_reconcile_fails_closed_when_no_event_log_to_derive_from(tmp_path: Path) -> None:
    """Squad fold (all 3 pre-PR lenses): the reconcile helper must fail closed —
    never stage a conflict-markered status.json — when it has no authoritative
    event log to regenerate from. This is the sparse-coord-lane situation in the
    small (status.events.jsonl off-disk / absent): git leaves conflict markers in
    the unmerged file, reconcile_status_snapshot no-ops, and the helper must
    refuse rather than `git add` the markers.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    other = "other-side"
    _git(repo, "branch", other)

    # Both sides ADD status.json (add/add) with DIFFERENT content and NO event log.
    _git(repo, "checkout", "-q", other)
    _write_divergent_snapshot(feature_dir, "other")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "other: snapshot only, no event log")
    _git(repo, "checkout", "-q", "main")
    _write_divergent_snapshot(feature_dir, "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "main: snapshot only, no event log")

    env = _make_merge_env()
    merge = subprocess.run(
        ["git", "-C", str(repo), "merge", "--no-commit", "--no-ff", other],
        capture_output=True,
        text=True,
        env=env,
    )
    assert merge.returncode != 0  # add/add conflict on the driver-less status.json

    # No event log exists, so the helper must fail closed (not stage markers).
    assert reconcile_derived_status_snapshot_conflicts(repo, env) is False
    # status.json is still unmerged — nothing was green-washed into the index.
    unmerged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", "--diff-filter=U"],
        capture_output=True,
        text=True,
        env=env,
    ).stdout
    assert "status.json" in unmerged
