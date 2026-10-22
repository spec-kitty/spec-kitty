"""Tests for FR-021: scan_recovery_state with status-events consultation.

These tests verify the post-merge recovery deadlock fix:
- WPs whose dependency branches are merged-and-deleted are recognised
  correctly by consulting the event log.
- The legacy live-branch-only path (consult_status_events=False) is
  unchanged.
- Scenario 7 end-to-end: six placeholder WPs in a dependency chain,
  first five implemented/merged, sixth becomes ready-to-start.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.recovery import (
    RecoveryState,
    get_ready_to_start_from_target,
    scan_recovery_state,
)
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = pytest.mark.git_repo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_git_repo(path: Path) -> None:
    """Create a minimal git repo with an initial commit on 'main'."""
    subprocess.run(["git", "init", str(path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(path), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(path), capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=str(path), capture_output=True, check=True,
    )
    (path / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "."], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(path), capture_output=True, check=True,
    )


def _write_event(feature_dir: Path, wp_id: str, from_lane: str, to_lane: str,
                 mission_slug: str, event_id_suffix: str) -> None:
    """Append a minimal status event to the event log."""
    event = StatusEvent(
        event_id=f"01AAAAAAAAAAAAAAAAAAAAAAA{event_id_suffix}",
        mission_slug=mission_slug,
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at="2026-04-07T10:00:00+00:00",
        actor="test",
        force=False,
        execution_mode="worktree",
        reason="test event",
    )
    seed_status_event(feature_dir, event)


def _make_six_wp_manifest(mission_slug: str) -> LanesManifest:
    """Build a LanesManifest with six placeholder WPs in a dependency chain.

    WP01 → WP02 → WP03 → WP04 → WP05 → WP06
    Each WP lives in its own lane.  Lane IDs use the canonical single-letter
    format (lane-a … lane-f); WP IDs use the canonical numeric format (WP01 … WP06).
    """
    lanes = [
        ExecutionLane(
            lane_id=f"lane-{letter}",
            wp_ids=(f"WP{idx + 1:02d}",),
            write_scope=("src/**",),
            predicted_surfaces=(),
            depends_on_lanes=(),
            parallel_group=idx,
        )
        for idx, letter in enumerate("abcdef")
    ]
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_slug,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=lanes,
        computed_at="2026-04-07T10:00:00+00:00",
        computed_from="test",
    )


def _setup_six_wp_feature(repo: Path, mission_slug: str = "syn-six-wp") -> Path:
    """Set up a six-WP feature with dependency chain in WP files."""
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True, exist_ok=True)

    manifest = _make_six_wp_manifest(mission_slug)
    write_lanes_json(feature_dir, manifest)

    meta = {"mission_id": mission_slug, "mission_slug": mission_slug, "vcs": "git"}
    (feature_dir / "meta.json").write_text(json.dumps(meta))

    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    # WP01 has no dependencies
    (tasks_dir / "WP01-task.md").write_text("---\nwork_package_id: WP01\ndependencies: []\n---\n# WP01\n")
    # WP02 depends on WP01
    (tasks_dir / "WP02-task.md").write_text("---\nwork_package_id: WP02\ndependencies: [WP01]\n---\n# WP02\n")
    # WP03 depends on WP02
    (tasks_dir / "WP03-task.md").write_text("---\nwork_package_id: WP03\ndependencies: [WP02]\n---\n# WP03\n")
    # WP04 depends on WP03
    (tasks_dir / "WP04-task.md").write_text("---\nwork_package_id: WP04\ndependencies: [WP03]\n---\n# WP04\n")
    # WP05 depends on WP04
    (tasks_dir / "WP05-task.md").write_text("---\nwork_package_id: WP05\ndependencies: [WP04]\n---\n# WP05\n")
    # WP06 depends on WP05 — this is the downstream WP
    (tasks_dir / "WP06-task.md").write_text("---\nwork_package_id: WP06\ndependencies: [WP05]\n---\n# WP06\n")

    (repo / ".kittify" / "workspaces").mkdir(parents=True, exist_ok=True)

    return feature_dir


def _mark_wps_done_in_event_log(feature_dir: Path, mission_slug: str, wp_ids: list[str]) -> None:
    """Write planned→claimed→in_progress→for_review→approved→done events for each WP."""
    transitions = [
        ("planned", "claimed"),
        ("claimed", "in_progress"),
        ("in_progress", "for_review"),
        ("for_review", "approved"),
        ("approved", "done"),
    ]
    for idx, wp_id in enumerate(wp_ids):
        for t_idx, (from_l, to_l) in enumerate(transitions):
            suffix = str(idx * 10 + t_idx).zfill(1)
            _write_event(feature_dir, wp_id, from_l, to_l, mission_slug, suffix)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScanRecoveryStateMergedDeleted:
    """FR-021: Merged-and-deleted dep detection."""

    def test_scan_recovery_state_finds_merged_deleted_deps(self, tmp_path: Path) -> None:
        """Synthetic mission: WPa..WPe done-and-deleted; WPf is ready_to_start_from_target."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        mission_slug = "syn-six-wp"
        feature_dir = _setup_six_wp_feature(repo, mission_slug)

        # Mark WPa..WPe as done in the event log (no live branches).
        upstream_wps = ["WP01", "WP02", "WP03", "WP04", "WP05"]
        _mark_wps_done_in_event_log(feature_dir, mission_slug, upstream_wps)

        # No lane branches exist (simulating post-merge-cleanup state).
        states = scan_recovery_state(repo, mission_slug, consult_status_events=True)

        ready = get_ready_to_start_from_target(states)

        assert "WP06" in ready, (
            "WP06 should be in ready_to_start_from_target because all its deps (WP05) are done"
        )

    def test_merged_deleted_wps_have_resolution_note(self, tmp_path: Path) -> None:
        """WPs whose branch is absent but event-log says 'done' get resolution_note='merged_and_deleted'."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        mission_slug = "syn-six-wp"
        feature_dir = _setup_six_wp_feature(repo, mission_slug)
        _mark_wps_done_in_event_log(feature_dir, mission_slug, ["WP01"])

        states = scan_recovery_state(repo, mission_slug, consult_status_events=True)

        merged_states = [s for s in states if s.wp_id == "WP01"]
        assert merged_states, "WP01 should appear in states with resolution_note"
        assert any(
            s.resolution_note == "merged_and_deleted" for s in merged_states
        ), f"Expected resolution_note='merged_and_deleted', got {[s.resolution_note for s in merged_states]}"

    def test_scan_recovery_state_legacy_live_branch_path_unchanged(self, tmp_path: Path) -> None:
        """consult_status_events=False returns the same shape as before FR-021.

        Specifically: when there are no live branches and no event log, the
        result is an empty list (no crash state to recover).
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        mission_slug = "syn-six-wp"
        _setup_six_wp_feature(repo, mission_slug)

        # No live branches, no event log.
        states_old = scan_recovery_state(repo, mission_slug, consult_status_events=False)
        assert states_old == [], (
            "Legacy path (consult_status_events=False) should return [] when no live branches exist"
        )

    def test_legacy_path_finds_orphaned_branch_unchanged(self, tmp_path: Path) -> None:
        """consult_status_events=False still detects orphaned branches (existing behaviour)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        mission_slug = "syn-six-wp"
        feature_dir = _setup_six_wp_feature(repo, mission_slug)

        # Create a mission branch + lane-01 branch with a commit (no worktree).
        mission_branch = f"kitty/mission-{mission_slug}"
        subprocess.run(
            ["git", "branch", mission_branch, "main"],
            cwd=str(repo), capture_output=True, check=False,
        )
        lane_branch = f"kitty/mission-{mission_slug}-lane-a"
        subprocess.run(
            ["git", "branch", lane_branch, mission_branch],
            cwd=str(repo), capture_output=True, check=True,
        )
        tmp_wt = repo / ".worktrees" / "_tmp_lane_a"
        tmp_wt.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "worktree", "add", str(tmp_wt), lane_branch],
            cwd=str(repo), capture_output=True, check=True,
        )
        (tmp_wt / "feat.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=str(tmp_wt), capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: wp01"],
            cwd=str(tmp_wt), capture_output=True, check=True,
        )
        subprocess.run(
            ["git", "worktree", "remove", str(tmp_wt), "--force"],
            cwd=str(repo), capture_output=True, check=True,
        )

        states_legacy = scan_recovery_state(repo, mission_slug, consult_status_events=False)
        wpa_states = [s for s in states_legacy if s.wp_id == "WP01"]
        assert wpa_states, "Legacy path should still detect orphaned lane-01 branch for WP01"
        assert all(s.recovery_action == "recreate_worktree" for s in wpa_states)


class TestScenario7EndToEnd:
    """Scenario 7 reproduction: post-merge unblocking."""

    def test_post_merge_unblocking_scenario_end_to_end(self, tmp_path: Path) -> None:
        """Scenario 7: six placeholder WPs, first five done-and-deleted, sixth becomes ready.

        1. Set up a synthetic mission with WPa..WPf in a dependency chain.
        2. Simulate merge of WPa..WPe: write done events, no live branches.
        3. Run scan_recovery_state — assert WPf is in ready_to_start_from_target.
        4. Verify no manual .kittify/ state edits were needed.
        """
        repo = tmp_path / "repo"
        repo.mkdir()
        _make_git_repo(repo)

        mission_slug = "syn-e2e"
        feature_dir = _setup_six_wp_feature(repo, mission_slug)

        # Step 2: simulate successful merge of WPa..WPe.
        # In a real merge, branches would be deleted after merge.
        # We only write done events to the event log — no live branches.
        upstream_wps = ["WP01", "WP02", "WP03", "WP04", "WP05"]
        _mark_wps_done_in_event_log(feature_dir, mission_slug, upstream_wps)

        # Step 3: run scan.
        states = scan_recovery_state(repo, mission_slug, consult_status_events=True)
        ready = get_ready_to_start_from_target(states)

        assert "WP06" in ready, (
            "WP06 should be ready_to_start_from_target after all its deps are done"
        )

        # Step 4: verify no manual .kittify/ edits were needed.
        # The scan itself does not modify any files.
        kittify_contents = list((repo / ".kittify").rglob("*"))
        # Only the workspaces dir created by setup; no extra state files.
        modified_paths = [
            p for p in kittify_contents
            if p.is_file() and p.suffix not in (".md", ".yaml", ".json")
        ]
        assert not modified_paths, f"No extra .kittify state files should have been created: {modified_paths}"
