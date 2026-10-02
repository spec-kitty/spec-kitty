"""``lanes/recovery.reconcile_status`` writes through the single
write-location accessor (coord-artifact-single-home-01M3V4BE, WP07, T041).

``reconcile_status`` used to resolve its write location via
``resolve_feature_dir_for_mission`` -- kind-blind, substituting the
repository root checkout on an EMPTY/UNMATERIALIZED coordination surface
instead of materializing/seeding it. It now resolves through
``placement_seam(...).write_dir(STATUS_STATE)``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import ulid as _ulid_mod

from kernel.clock import now_utc_iso
from mission_runtime import MissionTopology
from specify_cli.lanes.recovery import RecoveryState, reconcile_status
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests._factories.coord_mission import event_ids, make_prefix_coord_mission

pytestmark = [pytest.mark.fast]

_STATUS_LOG = "status.events.jsonl"


def _seed_planned(feature_dir: Path, mission_slug: str, wp_id: str = "WP01") -> None:
    """Register ``wp_id``'s canonical ``planned`` status (what ``finalize-tasks``
    does) -- ``reconcile_status``'s emitted transitions derive ``from_lane``
    from the real event log, so a genuine ``genesis -> claimed`` hop needs
    this precondition, same as a real post-finalize mission."""
    append_event(
        feature_dir,
        StatusEvent(
            event_id=str(_ulid_mod.ULID()),
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.GENESIS,
            to_lane=Lane.PLANNED,
            at=now_utc_iso(),
            actor="fixture",
            force=False,
            execution_mode="worktree",
        ),
    )


def _recovery_state(wp_id: str = "WP01") -> RecoveryState:
    return RecoveryState(
        wp_id=wp_id,
        lane_id="lane-a",
        branch_name="kitty/mission-demo-lane-a",
        branch_exists=True,
        worktree_exists=True,
        context_exists=True,
        status_lane="planned",
        has_commits=True,
        recovery_action="emit_transitions",
    )


def test_reconcile_status_on_prefix_empty_mission_seeds_then_writes_coord(tmp_path: Path) -> None:
    """A pre-fix EMPTY mission with a WP branch that has commits: ``reconcile_
    status`` returns the emitted count, and the catch-up transitions land on
    the coordination log -- the root copy is restored, with exactly one seed
    commit on the coordination branch."""
    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty")
    _seed_planned(coord.root_mission_dir, coord.mission_dir_name)
    subprocess.run(["git", "-C", str(coord.repo_root), "add", "kitty-specs"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(coord.repo_root), "commit", "-q", "-m", "seed WP01 planned"], check=True, capture_output=True)
    root_ids_before = event_ids(coord.root_mission_dir / _STATUS_LOG)
    assert root_ids_before

    emitted = reconcile_status(coord.repo_root, coord.mission_dir_name, _recovery_state())

    assert emitted > 0
    coord_ids_after = event_ids(coord.coord_mission_dir / _STATUS_LOG)
    assert set(root_ids_before) <= set(coord_ids_after)
    assert len(coord_ids_after) == len(set(coord_ids_after))

    trailer = subprocess.run(
        [
            "git",
            "-C",
            str(coord.repo_root),
            "log",
            "--format=%(trailers:key=Spec-Kitty-Coordination-Seed,valueonly)",
            coord.coordination_branch,
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    seed_lines = [line for line in trailer.splitlines() if line.strip()]
    assert len(seed_lines) == 1, trailer

    root_status = subprocess.run(
        ["git", "-C", str(coord.repo_root), "status", "--porcelain", "--", f"kitty-specs/{coord.mission_dir_name}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert root_status == ""


def test_reconcile_status_on_lanes_topology_targets_the_same_root(tmp_path: Path) -> None:
    """``lanes`` (coord-less) topology: ``reconcile_status`` writes to the
    SAME primary dir as before the accessor migration (C-008 control)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True, capture_output=True)
    (repo / ".kittify").mkdir()
    feature_dir = repo / "kitty-specs" / "flat-demo"
    feature_dir.mkdir(parents=True)
    import json

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01FLATDEMO0000000000000000",
                "mission_slug": "flat-demo",
                "mission_type": "software-dev",
                "target_branch": "main",
                "friendly_name": "flat demo",
                "topology": MissionTopology.LANES.value,
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True, capture_output=True)
    _seed_planned(feature_dir, "flat-demo")

    emitted = reconcile_status(repo, "flat-demo", _recovery_state())

    assert emitted > 0
    assert (feature_dir / _STATUS_LOG).exists()


def test_reconcile_status_logs_a_warning_and_stops_on_an_unexpected_emit_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Review cycle 1 B3: recovery is best-effort -- an unexpected failure
    from the transactional emit (never one this WP's write-side fix governs)
    is logged with a WARNING naming the WP/mission/target lane and the
    exception, then the catch-up loop stops rather than propagating or
    silently swallowing it."""
    import logging

    import specify_cli.coordination.status_transition as status_transition_module

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True, capture_output=True)
    (repo / ".kittify").mkdir()
    feature_dir = repo / "kitty-specs" / "flat-demo"
    feature_dir.mkdir(parents=True)
    import json

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01FLATDEMO0000000000000000",
                "mission_slug": "flat-demo",
                "mission_type": "software-dev",
                "target_branch": "main",
                "friendly_name": "flat demo",
                "topology": MissionTopology.LANES.value,
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True, capture_output=True)
    _seed_planned(feature_dir, "flat-demo")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("unexpected emit failure")

    monkeypatch.setattr(status_transition_module, "emit_status_transition_transactional", _boom)

    with caplog.at_level(logging.WARNING):
        emitted = reconcile_status(repo, "flat-demo", _recovery_state())

    assert emitted == 0
    matching = [r for r in caplog.records if "stopped emitting catch-up transitions" in r.message]
    assert matching, caplog.records
    assert "WP01" in matching[0].message
    assert "flat-demo" in matching[0].message
    assert "RuntimeError" in matching[0].message
