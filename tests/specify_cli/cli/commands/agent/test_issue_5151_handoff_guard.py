"""Live ``move-task`` coverage for coordination-born lane history (#5151).

The fixture creates a real coordination worktree, advances its canonical
mission state and task prompt, then claims a lane from that coordination tip
while the planning branch remains stale. The assertions go through the stable
``agent tasks move-task`` CLI surface, not the contamination helper alone.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import tasks_shared
from specify_cli.cli.commands.agent.tasks import (
    _filter_by_planning_tip_content,
    _list_wp_branch_mission_specs_changes,
    app as tasks_app,
)
from specify_cli.cli.commands.agent.tasks_shared import (
    _lane_authored_kitty_specs_paths,
    _merge_commit_authored_kitty_specs_paths,
    _trusted_handoff_snapshots,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_event
from specify_cli.workspace.context import WorkspaceContext, load_context, save_context
from tests.characterization.test_trio_json_envelope import _build_mission_repo
from tests.lane_test_utils import lane_branch_name, lane_worktree_path

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_runner = CliRunner()


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _git_bytes(cwd: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)
    return result.stdout


def _commit_all(cwd: Path, message: str) -> None:
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-q", "-m", message)


def _set_stale_coordination_status_snapshot(coord_dir: Path, *, stale: bool) -> None:
    if not stale:
        return
    snapshot_path = coord_dir / "status.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot["mission_type"] = ""
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _merge_identical_coordination_planning_snapshot(
    repo_root: Path,
    mission_slug: str,
    lane_worktree: Path,
    planning_commit: str,
    planning_path: str,
) -> str:
    """Merge an identical planning snapshot from the trusted coordination lane."""
    mission_meta = json.loads((repo_root / "kitty-specs" / mission_slug / "meta.json").read_text(encoding="utf-8"))
    coord_worktree = CoordinationWorkspace.worktree_path(
        repo_root,
        mission_slug,
        str(mission_meta["mission_id"])[:8],
    )
    target_path = coord_worktree / planning_path
    target_path.write_bytes(_git_bytes(coord_worktree, "show", f"{planning_commit}:{planning_path}"))
    _commit_all(coord_worktree, "coord: retain inherited planning snapshot")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", str(mission_meta["coordination_branch"]))
    return _git(lane_worktree, "rev-parse", "HEAD")


def _merge_coordination_update(
    lane_worktree: Path,
    coord_tip: str,
    *,
    force_merge_commit: bool,
    refresh_status_snapshot_dir: Path | None = None,
    resolve_path_to_pin: str | None = None,
    planning_pin: str | None = None,
    discard_path_to_pin: str | None = None,
) -> None:
    if refresh_status_snapshot_dir is not None:
        result = subprocess.run(
            ["git", "merge", "--no-commit", "--no-ff", coord_tip],
            cwd=lane_worktree,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        materialize(refresh_status_snapshot_dir)
        _git(lane_worktree, "add", "-A")
        _git(lane_worktree, "commit", "-q", "-m", "Merge coordination snapshot")
        assert len(_git(lane_worktree, "show", "-s", "--format=%P", "HEAD").split()) == 2
        return
    if force_merge_commit:
        (lane_worktree / "src").mkdir(parents=True, exist_ok=True)
        (lane_worktree / "src" / "pre_coord_sync.py").write_text("def anchor() -> None: pass\n", encoding="utf-8")
        _commit_all(lane_worktree, "lane: add pre-sync implementation anchor")
        _git(lane_worktree, "merge", "--no-edit", "--no-ff", coord_tip)
        assert len(_git(lane_worktree, "show", "-s", "--format=%P", "HEAD").split()) == 2
        return
    if discard_path_to_pin is not None:
        assert planning_pin is not None
        result = subprocess.run(
            ["git", "merge", "--no-edit", "--no-commit", "--no-ff", coord_tip],
            cwd=lane_worktree,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        target_path = lane_worktree / discard_path_to_pin
        target_path.write_bytes(_git_bytes(lane_worktree, "show", f"{planning_pin}:{discard_path_to_pin}"))
        _git(lane_worktree, "add", discard_path_to_pin)
        _git(lane_worktree, "commit", "-q", "-m", "lane: discard coordinator matrix update")
        assert len(_git(lane_worktree, "show", "-s", "--format=%P", "HEAD").split()) == 2
        return
    if resolve_path_to_pin is not None:
        assert planning_pin is not None
        result = subprocess.run(
            ["git", "merge", "--no-edit", coord_tip],
            cwd=lane_worktree,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, result.stdout + result.stderr
        assert f"UU {resolve_path_to_pin}" in _git(lane_worktree, "status", "--porcelain")
        target_path = lane_worktree / resolve_path_to_pin
        target_path.write_bytes(_git_bytes(lane_worktree, "show", f"{planning_pin}:{resolve_path_to_pin}"))
        _git(lane_worktree, "add", resolve_path_to_pin)
        _git(lane_worktree, "commit", "-q", "-m", "lane: resolve coordinator conflict to P1 bytes")
        assert len(_git(lane_worktree, "show", "-s", "--format=%P", "HEAD").split()) == 2
        return
    _git(lane_worktree, "merge", "--no-edit", coord_tip)


def _merge_planning_commit(
    lane_worktree: Path,
    planning_commit: str,
    *,
    fork_commit: str,
    resolve_path_to_fork: str | None,
) -> None:
    if resolve_path_to_fork is None:
        _git(lane_worktree, "merge", "--no-edit", planning_commit)
        return

    result = subprocess.run(
        ["git", "merge", "--no-edit", planning_commit],
        cwd=lane_worktree,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert f"UU {resolve_path_to_fork}" in _git(lane_worktree, "status", "--porcelain")
    target_path = lane_worktree / resolve_path_to_fork
    target_path.write_bytes(_git_bytes(lane_worktree, "show", f"{fork_commit}:{resolve_path_to_fork}"))
    _git(lane_worktree, "add", resolve_path_to_fork)
    _git(lane_worktree, "commit", "-q", "-m", "lane: resolve planning conflict to fork bytes")
    parents = _git(lane_worktree, "show", "-s", "--format=%P", "HEAD").split()
    assert len(parents) == 2
    resolved_bytes = target_path.read_bytes()
    assert resolved_bytes == _git_bytes(lane_worktree, "show", f"{fork_commit}:{resolve_path_to_fork}")
    assert all(resolved_bytes != _git_bytes(lane_worktree, "show", f"{parent}:{resolve_path_to_fork}") for parent in parents)


def _add_planning_conflict_revision(repo_root: Path, rel_path: str, *, enabled: bool) -> None:
    if not enabled:
        return
    planning_matrix = repo_root / rel_path
    planning_matrix.write_text(
        planning_matrix.read_text(encoding="utf-8") + "\nPlanning-owned matrix revision.\n",
        encoding="utf-8",
    )


def _fresh_planning_lane_base(
    repo_root: Path,
    plan_path: Path,
    planning_pin: str,
    *,
    base_at_pin: bool,
    base_at_later_tip: bool,
) -> str | None:
    if base_at_pin and base_at_later_tip:
        raise ValueError("fresh planning lane base can select only one snapshot")
    if base_at_pin:
        return planning_pin
    if not base_at_later_tip:
        return None
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nPlanning target advanced before fresh lane claim.\n", encoding="utf-8")
    _commit_all(repo_root, "planning: advance before fresh lane claim")
    return _git(repo_root, "rev-parse", "HEAD")


def _apply_lane_edit(
    lane_worktree: Path,
    primary_dir: Path,
    mission_slug: str,
    lane_edit: str | None,
    *,
    fork_commit: str,
    planning_commit: str,
) -> list[str]:
    """Apply one deliberate kitty-specs edit and return its exact path."""
    changed_paths: list[str] = []
    if lane_edit == "primary":
        spec_path = lane_worktree / "kitty-specs" / mission_slug / "spec.md"
        spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\nLane-authored planning change.\n", encoding="utf-8")
        changed_paths.append(f"kitty-specs/{mission_slug}/spec.md")
    elif lane_edit == "plan":
        plan_path = lane_worktree / "kitty-specs" / mission_slug / "plan.md"
        plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nLane-authored plan edit.\n", encoding="utf-8")
        changed_paths.append(f"kitty-specs/{mission_slug}/plan.md")
    elif lane_edit == "plan-match-p2":
        plan_path = lane_worktree / "kitty-specs" / mission_slug / "plan.md"
        plan_path.write_bytes((primary_dir / "plan.md").read_bytes())
        changed_paths.append(f"kitty-specs/{mission_slug}/plan.md")
    elif lane_edit == "coord":
        matrix_path = lane_worktree / "kitty-specs" / mission_slug / "acceptance-matrix.json"
        matrix_path.write_text(matrix_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        changed_paths.append(f"kitty-specs/{mission_slug}/acceptance-matrix.json")
    elif lane_edit == "coord-match-planning":
        matrix_path = lane_worktree / "kitty-specs" / mission_slug / "acceptance-matrix.json"
        matrix_path.write_bytes((primary_dir / "acceptance-matrix.json").read_bytes())
        changed_paths.append(f"kitty-specs/{mission_slug}/acceptance-matrix.json")
    elif lane_edit == "mission-events":
        events_path = lane_worktree / "kitty-specs" / mission_slug / "mission-events.jsonl"
        events_path.write_text(events_path.read_text(encoding="utf-8") + '{"event":"lane-edit"}\n', encoding="utf-8")
        changed_paths.append(f"kitty-specs/{mission_slug}/mission-events.jsonl")
    elif lane_edit in {
        "coord-revert",
        "wp-prompt-revert",
        "wp-prompt-match-p1",
        "mission-events-delete",
        "status-events-delete",
        "status-json-delete",
    }:
        rel_path = {
            "coord-revert": f"kitty-specs/{mission_slug}/acceptance-matrix.json",
            "wp-prompt-revert": f"kitty-specs/{mission_slug}/tasks/WP01.md",
            "wp-prompt-match-p1": f"kitty-specs/{mission_slug}/tasks/WP01.md",
            "mission-events-delete": f"kitty-specs/{mission_slug}/mission-events.jsonl",
            "status-events-delete": f"kitty-specs/{mission_slug}/status.events.jsonl",
            "status-json-delete": f"kitty-specs/{mission_slug}/status.json",
        }[lane_edit]
        target_path = lane_worktree / rel_path
        if lane_edit.endswith("-delete"):
            target_path.unlink()
        else:
            source_commit = planning_commit if lane_edit == "wp-prompt-match-p1" else fork_commit
            target_path.write_bytes(_git_bytes(lane_worktree, "show", f"{source_commit}:{rel_path}"))
        changed_paths.append(rel_path)
    elif lane_edit == "wp-prompt":
        prompt_path = lane_worktree / "kitty-specs" / mission_slug / "tasks" / "WP01.md"
        prompt_path.write_text(prompt_path.read_text(encoding="utf-8") + "\nLane-authored prompt edit.\n", encoding="utf-8")
        changed_paths.append(f"kitty-specs/{mission_slug}/tasks/WP01.md")
    elif lane_edit == "status-json-tamper":
        status_path = lane_worktree / "kitty-specs" / mission_slug / "status.json"
        snapshot = json.loads(status_path.read_text(encoding="utf-8"))
        snapshot["summary"]["done"] = 99
        status_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        changed_paths.append(f"kitty-specs/{mission_slug}/status.json")
    return changed_paths


def _build_handoff_repo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    lane_edit: str | None = None,
    missing_planning_ref: bool = False,
    planning_drift_after_lane_merge: bool = False,
    missing_workspace_base_commit: bool = False,
    refresh_planning_commit_after_lane_merge: bool = False,
    coordination_updates_after_lane_base: bool = False,
    d07_noncoord_inherited_paths: bool = False,
    status_events_at_lane_base: bool = False,
    include_status_artifacts_after_lane_base: bool = True,
    materialize_status_snapshot_after_lane_base: bool = True,
    include_issue_matrix_after_coord_update: bool = True,
    include_claim_time_planning_pin: bool = True,
    stale_coordination_status_snapshot: bool = False,
    refresh_status_snapshot_after_coord_merge: bool = False,
    merge_claim_time_planning_commit: bool = True,
    lane_edit_on_side_branch: bool = False,
    force_coordination_merge_commit: bool = False,
    resolve_planning_coord_conflict_to_fork: bool = False,
    lane_base_at_planning_pin: bool = False,
    lane_base_at_later_planning_tip: bool = False,
    resolve_coordination_conflict_to_planning_pin: bool = False,
    discard_coordination_update_to_planning_pin: bool = False,
) -> tuple[Path, str, Path, list[str]]:
    """Create a coord-parented lane with a later planning-tip commit.

    The coordination branch contains the current status files, matrices,
    mission event log, and WP prompt. The planning branch advances separately
    with a planning commit; the lane merges that commit after forking from the
    coordination branch, matching the production claim-time topology.
    """
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=True,
        mission_slug="issue-5151-handoff",
        wp_lane="planned",
        materialize_coord=True,
    )
    primary_dir = repo_root / "kitty-specs" / mission_slug
    meta = json.loads((primary_dir / "meta.json").read_text(encoding="utf-8"))
    mission_id = str(meta["mission_id"])
    coord_branch = str(meta["coordination_branch"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mission_id[:8])
    coord_dir = coord_worktree / "kitty-specs" / mission_slug
    if status_events_at_lane_base:
        append_event(
            coord_dir,
            StatusEvent(
                event_id="01KX5151HANDOFFBASESTATE000001",
                mission_slug=mission_slug,
                mission_id=mission_id,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-09-28T11:00:00+00:00",
                actor="test-runner",
                force=False,
                execution_mode="worktree",
                reason="seed status log before lane fork",
            ),
        )
        _commit_all(coord_worktree, "coord: seed status log before lane fork")
    coord_base_commit = _git(coord_worktree, "rev-parse", "HEAD")

    if include_status_artifacts_after_lane_base:
        append_event(
            coord_dir,
            StatusEvent(
                event_id="01KX5151HANDOFFINPROGRESS0001",
                mission_slug=mission_slug,
                mission_id=mission_id,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-09-28T12:00:00+00:00",
                actor="test-runner",
                force=False,
                execution_mode="worktree",
                reason="seed live handoff fixture",
            ),
        )
    if materialize_status_snapshot_after_lane_base:
        materialize(coord_dir)
    _set_stale_coordination_status_snapshot(coord_dir, stale=stale_coordination_status_snapshot)

    if not d07_noncoord_inherited_paths:
        # These updates are owned by the live coordination branch. Two of them
        # are classified as COORD artifacts; the event log and WP prompt are not.
        (coord_dir / "acceptance-matrix.json").write_text(
            (coord_dir / "acceptance-matrix.json").read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
        if include_issue_matrix_after_coord_update:
            (coord_dir / "issue-matrix.md").write_text(
                "# Issue Matrix\n\nCoordination-owned fixture row.\n",
                encoding="utf-8",
            )
    (coord_dir / "mission-events.jsonl").write_text('{"event":"coordination-update"}\n', encoding="utf-8")
    wp_prompt = coord_dir / "tasks" / "WP01.md"
    wp_prompt.write_text(
        wp_prompt.read_text(encoding="utf-8") + "\nCoordinator-owned prompt update after planning target moved.\n",
        encoding="utf-8",
    )
    _commit_all(coord_worktree, "coord: record current mission state")
    coord_tip = _git(coord_worktree, "rev-parse", "HEAD")

    # Move the planning target after the coordination snapshot. The lane will
    # merge this recorded planning commit, while the current coordinator state
    # remains its actual fork base.
    plan_path = primary_dir / "plan.md"
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8") + "\nPlanning target advanced after coordination snapshot.\n",
        encoding="utf-8",
    )
    conflict_path = f"kitty-specs/{mission_slug}/acceptance-matrix.json"
    _add_planning_conflict_revision(repo_root, conflict_path, enabled=resolve_planning_coord_conflict_to_fork)
    if missing_planning_ref:
        meta["planning_base_branch"] = "missing-planning-ref"
        (primary_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _commit_all(repo_root, "planning: advance after coordination snapshot")
    recorded_planning_commit = _git(repo_root, "rev-parse", "HEAD")
    fresh_lane_planning_base = _fresh_planning_lane_base(
        repo_root,
        plan_path,
        recorded_planning_commit,
        base_at_pin=lane_base_at_planning_pin,
        base_at_later_tip=lane_base_at_later_planning_tip,
    )
    if planning_drift_after_lane_merge:
        from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json

        lanes_manifest = read_lanes_json(primary_dir)
        assert lanes_manifest is not None
        lanes_manifest.planning_commit_sha = recorded_planning_commit
        write_lanes_json(primary_dir, lanes_manifest)
        _commit_all(repo_root, "planning: persist recorded planning commit")

    lane_branch = lane_branch_name(mission_slug, "lane-a")
    lane_worktree = lane_worktree_path(repo_root, mission_slug, "lane-a")
    lane_base_commit = fresh_lane_planning_base or (coord_base_commit if coordination_updates_after_lane_base else coord_tip)
    _git(repo_root, "worktree", "add", "-b", lane_branch, str(lane_worktree), lane_base_commit)
    if coordination_updates_after_lane_base:
        _merge_coordination_update(
            lane_worktree,
            coord_tip,
            force_merge_commit=force_coordination_merge_commit,
            refresh_status_snapshot_dir=(lane_worktree / "kitty-specs" / mission_slug if refresh_status_snapshot_after_coord_merge else None),
            resolve_path_to_pin=conflict_path if resolve_coordination_conflict_to_planning_pin else None,
            planning_pin=recorded_planning_commit if resolve_coordination_conflict_to_planning_pin or discard_coordination_update_to_planning_pin else None,
            discard_path_to_pin=conflict_path if discard_coordination_update_to_planning_pin else None,
        )
    if merge_claim_time_planning_commit:
        _merge_planning_commit(
            lane_worktree,
            recorded_planning_commit,
            fork_commit=lane_base_commit,
            resolve_path_to_fork=conflict_path if resolve_planning_coord_conflict_to_fork else None,
        )

    if planning_drift_after_lane_merge:
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8") + "\nPlanning target advanced again after lane claim (P2).\n",
            encoding="utf-8",
        )
        _commit_all(repo_root, "planning: advance target to P2 after lane claim")
        p2_commit = _git(repo_root, "rev-parse", "HEAD")
        if refresh_planning_commit_after_lane_merge:
            from specify_cli.lanes.persistence import read_lanes_json, write_lanes_json

            lanes_manifest = read_lanes_json(primary_dir)
            assert lanes_manifest is not None
            lanes_manifest.planning_commit_sha = p2_commit
            write_lanes_json(primary_dir, lanes_manifest)
            _commit_all(repo_root, "finalize: refresh planning commit to P2")

    changed_paths: list[str] = []
    if lane_edit_on_side_branch:
        side_branch = f"{lane_branch}-side"
        _git(lane_worktree, "switch", "-q", "-c", side_branch)
        changed_paths = _apply_lane_edit(
            lane_worktree,
            primary_dir,
            mission_slug,
            lane_edit,
            fork_commit=lane_base_commit,
            planning_commit=recorded_planning_commit,
        )
        _commit_all(lane_worktree, "lane-side: edit WP01 planning artifact")
        _git(lane_worktree, "switch", "-q", lane_branch)
        _git(lane_worktree, "merge", "--no-edit", "--no-ff", side_branch)

    # A real source commit satisfies move-task's implementation-commit guard.
    (lane_worktree / "src").mkdir(parents=True, exist_ok=True)
    (lane_worktree / "src" / "handoff_impl.py").write_text("def ready() -> bool:\n    return True\n", encoding="utf-8")
    if not lane_edit_on_side_branch:
        changed_paths = _apply_lane_edit(
            lane_worktree,
            primary_dir,
            mission_slug,
            lane_edit,
            fork_commit=lane_base_commit,
            planning_commit=recorded_planning_commit,
        )
    _commit_all(lane_worktree, "lane: implement WP01")

    context_path = save_context(
        repo_root,
        WorkspaceContext(
            wp_id="WP01",
            mission_slug=mission_slug,
            worktree_path=lane_worktree.relative_to(repo_root).as_posix(),
            branch_name=lane_branch,
            base_branch=coord_branch,
            base_commit=None if missing_workspace_base_commit else lane_base_commit,
            dependencies=[],
            created_at="2026-09-28T12:01:00+00:00",
            created_by="test-fixture",
            vcs_backend="git",
            lane_id="lane-a",
            lane_wp_ids=["WP01"],
            current_wp="WP01",
            planning_commit_sha=recorded_planning_commit if include_claim_time_planning_pin else None,
        ),
    )
    context_data = json.loads(context_path.read_text(encoding="utf-8"))
    if not include_claim_time_planning_pin:
        context_data.pop("planning_commit_sha", None)
    context_path.write_text(json.dumps(context_data, indent=2) + "\n", encoding="utf-8")
    return repo_root, mission_slug, lane_worktree, changed_paths


def _move_for_review(repo_root: Path, mission_slug: str):
    result = _runner.invoke(
        tasks_app,
        [
            "move-task",
            "WP01",
            "--to",
            "for_review",
            "--mission",
            mission_slug,
            "--no-auto-commit",
        ],
        catch_exceptions=False,
    )
    return result


def _criss_cross_merge_bases(worktree: Path, other_ref: str) -> set[str]:
    result = subprocess.run(
        ["git", "merge-base", "--all", "HEAD", other_ref],
        cwd=worktree,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def test_clean_coordination_inheritance_passes_move_task(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(tmp_path, monkeypatch)
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output


def test_canonical_derived_coordination_status_snapshot_passes_move_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        coordination_updates_after_lane_base=True,
        stale_coordination_status_snapshot=True,
        refresh_status_snapshot_after_coord_merge=True,
    )
    monkeypatch.chdir(repo_root)
    status_path = lane_worktree / "kitty-specs" / mission_slug / "status.json"
    assert json.loads(status_path.read_text(encoding="utf-8"))["mission_type"] == "software-dev"

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output


def test_stale_c2_status_is_rejected_after_c3_events_arrive_without_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        stale_coordination_status_snapshot=True,
    )
    mission_dir = repo_root / "kitty-specs" / mission_slug
    mission_meta = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    coordination_ref = str(mission_meta["coordination_branch"])
    mission_id = str(mission_meta["mission_id"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mission_id[:8])
    coord_dir = coord_worktree / "kitty-specs" / mission_slug
    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.planning_commit_sha is not None
    p1 = context.planning_commit_sha

    mission_meta["planning_revision"] = "P2"
    (mission_dir / "meta.json").write_text(json.dumps(mission_meta, indent=2) + "\n", encoding="utf-8")
    _commit_all(repo_root, "planning: advance metadata to P2")
    p2 = _git(repo_root, "rev-parse", "HEAD")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", p2)

    c2_event_id = "01KXQB5J00H5M8S6X6AEY12347"
    append_event(
        coord_dir,
        StatusEvent(
            event_id=c2_event_id,
            mission_slug=mission_slug,
            mission_id=mission_id,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-09-28T13:00:00+00:00",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
            reason="refresh status from coordination C2",
        ),
    )
    materialize(coord_dir)
    _commit_all(coord_worktree, "coord: append C2 status event")
    c2 = _git(coord_worktree, "rev-parse", "HEAD")
    assert json.loads(_git(coord_worktree, "show", f"{c2}:kitty-specs/{mission_slug}/status.json"))["last_event_id"] == c2_event_id
    merge_result = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", coordination_ref],
        cwd=lane_worktree,
        capture_output=True,
        text=True,
    )
    assert merge_result.returncode == 0, merge_result.stdout + merge_result.stderr
    _git(lane_worktree, "add", "-A")
    _git(lane_worktree, "commit", "-q", "-m", "Merge canonical coordination C2 refresh")
    c2_lane_refresh = _git(lane_worktree, "rev-parse", "HEAD")
    assert _git(lane_worktree, "show", f"{c2_lane_refresh}:kitty-specs/{mission_slug}/status.json") == _git(
        coord_worktree,
        "show",
        f"{c2}:kitty-specs/{mission_slug}/status.json",
    )

    mission_meta["planning_revision"] = "P3"
    (mission_dir / "meta.json").write_text(json.dumps(mission_meta, indent=2) + "\n", encoding="utf-8")
    plan_path = mission_dir / "plan.md"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nPlanning branch P3 before C3.\n", encoding="utf-8")
    _commit_all(repo_root, "planning: advance to P3")
    p3 = _git(repo_root, "rev-parse", "HEAD")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", p3)

    c3_event_id = "01KXQB5J00H5M8S6X6AEY12348"
    append_event(
        coord_dir,
        StatusEvent(
            event_id=c3_event_id,
            mission_slug=mission_slug,
            mission_id=mission_id,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-09-28T14:00:00+00:00",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
            reason="advance coordination events to C3 without status refresh",
        ),
    )
    _commit_all(coord_worktree, "coord: append C3 event without materializing status")
    c3 = _git(coord_worktree, "rev-parse", "HEAD")
    merge_result = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", coordination_ref],
        cwd=lane_worktree,
        capture_output=True,
        text=True,
    )
    assert merge_result.returncode == 0, merge_result.stdout + merge_result.stderr
    _git(lane_worktree, "add", "-A")
    _git(lane_worktree, "commit", "-q", "-m", "Merge C3 events without status refresh")
    c3_lane_merge = _git(lane_worktree, "rev-parse", "HEAD")

    status_path = f"kitty-specs/{mission_slug}/status.json"
    events_path = f"kitty-specs/{mission_slug}/status.events.jsonl"
    assert _git(lane_worktree, "show", f"{c2_lane_refresh}:{status_path}") == _git(lane_worktree, "show", f"{c3_lane_merge}:{status_path}")
    assert json.loads(_git(lane_worktree, "show", f"{c3_lane_merge}:{status_path}"))["last_event_id"] == c2_event_id
    assert _git(coord_worktree, "show", f"{c3}:{status_path}") == _git(lane_worktree, "show", f"{c2_lane_refresh}:{status_path}")
    assert c3_event_id in _git(lane_worktree, "show", f"{c3_lane_merge}:{events_path}")
    assert _git(lane_worktree, "merge-base", "HEAD", p3) == p3
    assert _git(lane_worktree, "merge-base", "HEAD", c3) == c3
    assert p1 != p2 != p3

    monkeypatch.chdir(repo_root)
    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert status_path in result.output


def test_stale_coordination_status_is_rejected_when_planning_mission_number_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(tmp_path, monkeypatch)
    mission_dir = repo_root / "kitty-specs" / mission_slug
    mission_meta = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    mission_meta["mission_number"] = 5151
    (mission_dir / "meta.json").write_text(json.dumps(mission_meta, indent=2) + "\n", encoding="utf-8")
    _commit_all(repo_root, "planning: change mission number without refreshing status")
    planning_p2 = _git(repo_root, "rev-parse", "HEAD")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", planning_p2)

    status_path = f"kitty-specs/{mission_slug}/status.json"
    status = json.loads(_git(lane_worktree, "show", f"HEAD:{status_path}"))
    assert status["mission_type"] == "software-dev"
    assert status["mission_number"] != 5151
    assert json.loads(_git(repo_root, "show", f"HEAD:{status_path}"))["mission_number"] != 5151
    lane_meta = json.loads(_git(lane_worktree, "show", f"HEAD:kitty-specs/{mission_slug}/meta.json"))
    assert lane_meta["mission_type"] == "software-dev"
    assert lane_meta["mission_number"] == 5151

    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.base_commit is not None
    primary_meta = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    raw_candidates = tasks_shared._kitty_specs_paths_changed(lane_worktree, context.base_commit, "HEAD")
    assert raw_candidates is not None
    meta_path = f"kitty-specs/{mission_slug}/meta.json"
    assert meta_path in raw_candidates
    assert status_path not in raw_candidates
    direct_changes = _list_wp_branch_mission_specs_changes(
        lane_worktree,
        str(primary_meta["coordination_branch"]),
        planning_base_branch=str(primary_meta["target_branch"]),
        workspace_base_commit=context.base_commit,
        planning_commit_sha=context.planning_commit_sha,
        coordination_ref=str(primary_meta["coordination_branch"]),
        mission_slug=mission_slug,
    )
    assert status_path in (direct_changes or [])

    monkeypatch.chdir(repo_root)
    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert status_path in result.output


def test_stale_inherited_c2_status_is_rejected_after_lane_merges_only_c3_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        status_events_at_lane_base=True,
        include_status_artifacts_after_lane_base=False,
    )
    mission_meta = json.loads((repo_root / "kitty-specs" / mission_slug / "meta.json").read_text(encoding="utf-8"))
    mission_id = str(mission_meta["mission_id"])
    coordination_ref = str(mission_meta["coordination_branch"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mission_id[:8])
    coord_dir = coord_worktree / "kitty-specs" / mission_slug
    status_path = f"kitty-specs/{mission_slug}/status.json"
    events_path = f"kitty-specs/{mission_slug}/status.events.jsonl"
    inherited_status = _git(lane_worktree, "show", f"HEAD:{status_path}")
    c3_event_id = "01KX5151LANEBASEC3EVENT0000001"

    append_event(
        coord_dir,
        StatusEvent(
            event_id=c3_event_id,
            mission_slug=mission_slug,
            mission_id=mission_id,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-09-28T15:30:00+00:00",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
            reason="advance coordination events after the lane fork",
        ),
    )
    _commit_all(coord_worktree, "coord: append C3 event after lane fork")
    coordinator_tip = _git(coord_worktree, "rev-parse", "HEAD")
    assert _git(coord_worktree, "show", f"{coordinator_tip}:{status_path}") == inherited_status

    merge_result = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", coordination_ref],
        cwd=lane_worktree,
        capture_output=True,
        text=True,
    )
    assert merge_result.returncode == 0, merge_result.stdout + merge_result.stderr
    _git(lane_worktree, "add", "-A")
    _git(lane_worktree, "commit", "-q", "-m", "Merge C3 events without status refresh")
    lane_tip = _git(lane_worktree, "rev-parse", "HEAD")

    assert _git(lane_worktree, "show", f"{lane_tip}:{status_path}") == inherited_status
    assert c3_event_id in _git(lane_worktree, "show", f"{lane_tip}:{events_path}")
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert status_path in result.output


def test_unmerged_coordinator_c3_does_not_invalidate_clean_lane_c2_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(tmp_path, monkeypatch)
    mission_meta = json.loads((repo_root / "kitty-specs" / mission_slug / "meta.json").read_text(encoding="utf-8"))
    mission_id = str(mission_meta["mission_id"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mission_id[:8])
    coord_dir = coord_worktree / "kitty-specs" / mission_slug
    status_path = f"kitty-specs/{mission_slug}/status.json"
    lane_status = _git(lane_worktree, "show", f"HEAD:{status_path}")
    c3_event_id = "01KX5151COORDONLYC30000000001"

    append_event(
        coord_dir,
        StatusEvent(
            event_id=c3_event_id,
            mission_slug=mission_slug,
            mission_id=mission_id,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-09-28T15:00:00+00:00",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
            reason="advance coordinator events without merging them into the lane",
        ),
    )
    _commit_all(coord_worktree, "coord: append unmerged C3 event")
    coordinator_tip = _git(coord_worktree, "rev-parse", "HEAD")

    assert _git(coord_worktree, "show", f"{coordinator_tip}:{status_path}") == lane_status
    assert c3_event_id in _git(coord_worktree, "show", f"{coordinator_tip}:kitty-specs/{mission_slug}/status.events.jsonl")
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    # Handoff validates the latest coordination snapshot already present in the
    # lane. Coordinator-only C3 events have not become lane history yet.
    assert result.exit_code == 0, result.output


def test_merge_commit_authorship_fails_closed_for_criss_cross_best_bases(tmp_path: Path) -> None:
    repo_root = tmp_path / "criss-cross"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    _git(repo_root, "config", "user.name", "Test Runner")
    _git(repo_root, "config", "commit.gpgsign", "false")

    artifact_path = Path("kitty-specs/issue-5151-handoff/spec.md")
    artifact = repo_root / artifact_path
    artifact.parent.mkdir(parents=True)
    artifact.write_text("base\n", encoding="utf-8")
    _commit_all(repo_root, "base")
    fork = _git(repo_root, "rev-parse", "HEAD")

    _git(repo_root, "checkout", "-q", "-b", "left", fork)
    artifact.write_text("left\n", encoding="utf-8")
    _commit_all(repo_root, "left side")
    left = _git(repo_root, "rev-parse", "HEAD")

    _git(repo_root, "checkout", "-q", "-b", "right", fork)
    artifact.write_text("right\n", encoding="utf-8")
    _commit_all(repo_root, "right side")
    right = _git(repo_root, "rev-parse", "HEAD")

    _git(repo_root, "checkout", "-q", "left")
    merge = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", right],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert merge.returncode != 0
    artifact.write_text("left\n", encoding="utf-8")
    _commit_all(repo_root, "left merge resolution")
    left_merge = _git(repo_root, "rev-parse", "HEAD")

    _git(repo_root, "checkout", "-q", "right")
    merge = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", left],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert merge.returncode != 0
    artifact.write_text("right\n", encoding="utf-8")
    _commit_all(repo_root, "right merge resolution")
    right_merge = _git(repo_root, "rev-parse", "HEAD")

    merge_bases = set(_git(repo_root, "merge-base", "--all", left_merge, right_merge).splitlines())
    assert merge_bases == {left, right}

    _git(repo_root, "checkout", "-q", "-b", "combined", left_merge)
    merge = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", right_merge],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert merge.returncode != 0
    artifact.write_text("left\n", encoding="utf-8")
    _commit_all(repo_root, "combined merge resolution")
    combined = _git(repo_root, "rev-parse", "HEAD")
    result_paths_by_parent = [set(tasks_shared._kitty_specs_paths_changed(repo_root, parent, combined) or ()) for parent in (left_merge, right_merge)]

    assert (
        _merge_commit_authored_kitty_specs_paths(
            repo_root,
            (left_merge, right_merge),
            result_paths_by_parent,
        )
        is None
    )


def test_ambiguous_planning_merge_base_is_rejected_by_move_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(tmp_path, monkeypatch)
    mission_dir = repo_root / "kitty-specs" / mission_slug
    mission_meta = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    planning_ref = str(mission_meta["target_branch"])
    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.planning_commit_sha is not None
    assert context.base_commit is not None

    plan_path = mission_dir / "plan.md"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nPlanning-side criss-cross commit.\n", encoding="utf-8")
    _commit_all(repo_root, "planning: create criss-cross side")
    planning_side = _git(repo_root, "rev-parse", "HEAD")

    lane_side = _git(lane_worktree, "rev-parse", "HEAD")

    _git(repo_root, "merge", "--no-edit", "--no-ff", lane_side)
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", planning_side)
    assert _criss_cross_merge_bases(lane_worktree, planning_ref) == {planning_side, lane_side}
    planning_snapshots = _trusted_handoff_snapshots(
        lane_worktree,
        planning_ref,
        context.planning_commit_sha,
        context.base_commit,
        str(mission_meta["coordination_branch"]),
    )
    assert planning_snapshots is None

    monkeypatch.chdir(repo_root)
    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "could not verify" in result.output.lower()
    assert "No handoff was made" in result.output


@pytest.mark.parametrize("failure_mode", ["os-error", "timeout"])
def test_unpinned_planning_snapshot_git_failure_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(tmp_path, monkeypatch)
    mission_meta = json.loads((repo_root / "kitty-specs" / mission_slug / "meta.json").read_text(encoding="utf-8"))
    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.base_commit is not None
    planning_ref = str(mission_meta["target_branch"])
    coordination_ref = str(mission_meta["coordination_branch"])
    original_run = subprocess.run

    def fail_shared_snapshot(args, **kwargs):
        if args[:3] == ["git", "merge-base", "--all"] and args[3] == "HEAD":
            if failure_mode == "timeout":
                raise subprocess.TimeoutExpired(args, timeout=30)
            raise OSError("merge-base is unavailable")
        return original_run(args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(subprocess, "run", fail_shared_snapshot)
        snapshots = _trusted_handoff_snapshots(
            lane_worktree,
            planning_ref,
            None,
            context.base_commit,
            coordination_ref,
        )

    assert snapshots is None


def test_unpinned_planning_snapshot_equal_to_workspace_fork_is_trusted(tmp_path: Path) -> None:
    """A single-branch workspace can fork exactly from its planning snapshot."""
    repo = tmp_path / "forked-planning-snapshot-repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("planning snapshot\n", encoding="utf-8")
    _commit_all(repo, "planning snapshot")
    workspace_base_commit = _git(repo, "rev-parse", "HEAD")

    snapshots = _trusted_handoff_snapshots(
        repo,
        "main",
        None,
        workspace_base_commit,
        None,
    )

    assert snapshots == (workspace_base_commit, None, None)


@pytest.mark.parametrize("unreachable_ref", ["planning-tip", "HEAD"])
def test_fallback_fork_pin_requires_planning_and_head_reachability(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unreachable_ref: str,
) -> None:
    workspace_base_commit = "immutable-fork"
    monkeypatch.setattr(tasks_shared, "capture_branch_tip", lambda *_args: "planning-tip")
    monkeypatch.setattr(tasks_shared, "_unique_shared_snapshot", lambda *_args: workspace_base_commit)

    def merge_base(_worktree: Path, left: str, right: str) -> str | None:
        assert right == workspace_base_commit
        return None if left == unreachable_ref else workspace_base_commit

    monkeypatch.setattr(tasks_shared, "git_merge_base", merge_base)

    snapshots = _trusted_handoff_snapshots(
        tmp_path,
        "planning-ref",
        None,
        workspace_base_commit,
        None,
    )

    assert snapshots is None


def test_ambiguous_coordination_merge_base_is_untrusted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(tmp_path, monkeypatch)
    mission_dir = repo_root / "kitty-specs" / mission_slug
    mission_meta = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    planning_ref = str(mission_meta["target_branch"])
    coordination_ref = str(mission_meta["coordination_branch"])
    mission_id = str(mission_meta["mission_id"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mission_id[:8])
    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.planning_commit_sha is not None
    assert context.base_commit is not None
    planning_side = context.planning_commit_sha

    anchor_path = coord_worktree / "src" / "coordination_history_anchor.py"
    anchor_path.parent.mkdir(parents=True, exist_ok=True)
    anchor_path.write_text("def coordination_anchor() -> None:\n    pass\n", encoding="utf-8")
    _commit_all(coord_worktree, "coord: create criss-cross side")
    coordination_side = _git(coord_worktree, "rev-parse", "HEAD")
    _git(coord_worktree, "merge", "--no-edit", "--no-ff", planning_side)

    _git(lane_worktree, "merge", "--no-edit", "--no-ff", coordination_side)

    assert _criss_cross_merge_bases(lane_worktree, coordination_ref) == {planning_side, coordination_side}
    assert (
        _trusted_handoff_snapshots(
            lane_worktree,
            planning_ref,
            context.planning_commit_sha,
            context.base_commit,
            coordination_ref,
        )
        is None
    )


def _authored_paths_for_handoff(
    repo_root: Path,
    mission_slug: str,
    lane_worktree: Path,
) -> tuple[str, ...]:
    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.base_commit is not None
    primary_meta = json.loads((repo_root / "kitty-specs" / mission_slug / "meta.json").read_text(encoding="utf-8"))
    planning_ref = _git(repo_root, "branch", "--show-current")
    coordination_ref = str(primary_meta["coordination_branch"])
    snapshots = _trusted_handoff_snapshots(
        lane_worktree,
        planning_ref,
        context.planning_commit_sha,
        context.base_commit,
        coordination_ref,
    )
    assert snapshots is not None and snapshots[2] is not None
    candidate_paths = tasks_shared._kitty_specs_paths_changed(lane_worktree, context.base_commit, "HEAD")
    assert candidate_paths is not None
    return (
        _lane_authored_kitty_specs_paths(
            lane_worktree,
            context.base_commit,
            tuple(snapshot for snapshot in snapshots if snapshot is not None),
            mission_slug=mission_slug,
            planning_pin=snapshots[0],
            planning_ref=planning_ref,
            coordination_snapshot=snapshots[2],
            coordination_ref=coordination_ref,
            candidate_paths=candidate_paths,
        )
        or ()
    )


@pytest.mark.parametrize(
    ("failure_mode", "mission_slug", "planning_pin", "coordination_snapshot"),
    [
        ("invalid-mission-slug", "unsafe/nested", "planning-pin", "coord-snapshot"),
        ("missing-planning-pin", "safe-mission", None, "coord-snapshot"),
        ("missing-coordination-snapshot", "safe-mission", "planning-pin", None),
        ("untrusted-coordination-snapshot", "safe-mission", "planning-pin", "coord-snapshot"),
    ],
)
def test_status_snapshot_replay_fails_closed_for_invalid_replay_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
    mission_slug: str,
    planning_pin: str | None,
    coordination_snapshot: str | None,
) -> None:
    status_path = f"kitty-specs/{mission_slug}/status.json"

    def fake_run(args, **kwargs):
        if args[:3] == ["git", "rev-list", "--parents"]:
            return subprocess.CompletedProcess(args, 0, stdout="lane-merge parent-a parent-b\n", stderr="")
        if args[:3] == ["git", "merge-base", "--all"]:
            shared = "planning-shared" if args[4] == "planning-history" else "coord-snapshot"
            return subprocess.CompletedProcess(args, 0, stdout=f"{shared}\n", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        tasks_shared,
        "_lane_commit_authored_kitty_specs_paths",
        lambda _worktree, _commit, _parents: (status_path,),
    )
    monkeypatch.setattr(tasks_shared, "_commit_is_post_fork_lane_ancestor", lambda *_args: True)
    monkeypatch.setattr(
        tasks_shared,
        "_commit_in_trusted_snapshots",
        lambda _worktree, commit, _snapshots: commit == "coord-snapshot" and failure_mode != "untrusted-coordination-snapshot",
    )

    derived_status_paths: set[str] = set()
    authored_paths = _lane_authored_kitty_specs_paths(
        tmp_path,
        "fork",
        (),
        mission_slug=mission_slug,
        planning_pin=planning_pin,
        merged_planning_tip="planning-history",
        coordination_snapshot=coordination_snapshot,
        derived_status_paths=derived_status_paths,
    )

    assert authored_paths == (status_path,)
    assert status_path not in derived_status_paths


@pytest.mark.parametrize("failure_mode", ["missing-refs", "missing-tip", "unresolved-snapshot", "mismatched-snapshot"])
def test_final_status_replay_fails_closed_when_refs_cannot_be_verified(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    mission_slug = "safe-mission"
    status_path = f"kitty-specs/{mission_slug}/status.json"
    planning_ref = None if failure_mode == "missing-refs" else "planning-ref"

    def fake_run(args, **kwargs):
        if args[:3] == ["git", "rev-list", "--parents"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:3] == ["git", "merge-base", "--all"]:
            if failure_mode == "unresolved-snapshot":
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="missing shared snapshot")
            shared = "different-planning" if args[4] == "planning-tip" else "different-coordination"
            return subprocess.CompletedProcess(args, 0, stdout=f"{shared}\n", stderr="")
        raise AssertionError(args)

    def fake_capture_branch_tip(_worktree: Path, branch: str) -> str | None:
        if failure_mode == "missing-tip" and branch == "planning-ref":
            return None
        return "planning-tip" if branch == "planning-ref" else "coordination-tip"

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(tasks_shared, "capture_branch_tip", fake_capture_branch_tip)

    derived_status_paths = {status_path}
    authored_paths = _lane_authored_kitty_specs_paths(
        tmp_path,
        "fork",
        (),
        mission_slug=mission_slug,
        planning_pin="planning-pin",
        planning_ref=planning_ref,
        merged_planning_tip="expected-planning",
        coordination_snapshot="expected-coordination",
        coordination_ref="coordination-ref",
        derived_status_paths=derived_status_paths,
    )

    assert authored_paths == ()
    assert derived_status_paths == set()


def test_status_snapshot_replay_fails_closed_without_verifiable_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        coordination_updates_after_lane_base=True,
        stale_coordination_status_snapshot=True,
        refresh_status_snapshot_after_coord_merge=True,
    )
    status_path = f"kitty-specs/{mission_slug}/status.json"

    original_run = subprocess.run

    def fail_event_blob(args, **kwargs):
        if args[:2] == ["git", "show"] and str(args[-1]).endswith("/status.events.jsonl"):
            raise subprocess.TimeoutExpired(args, timeout=30)
        return original_run(args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(subprocess, "run", fail_event_blob)
        authored_paths = _authored_paths_for_handoff(
            repo_root,
            mission_slug,
            lane_worktree,
        )
        assert status_path in authored_paths

    def invalid_event_blob(args, **kwargs):
        if args[:2] == ["git", "show"] and str(args[-1]).endswith("/status.events.jsonl"):
            return subprocess.CompletedProcess(args, 0, stdout=b"not-json", stderr=b"")
        return original_run(args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(subprocess, "run", invalid_event_blob)
        authored_paths = _authored_paths_for_handoff(
            repo_root,
            mission_slug,
            lane_worktree,
        )
        assert status_path in authored_paths


@pytest.mark.parametrize("failure_mode", ["ambiguous", "timeout"])
def test_status_snapshot_replay_fails_closed_without_unique_merge_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure_mode: str,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        coordination_updates_after_lane_base=True,
        stale_coordination_status_snapshot=True,
        refresh_status_snapshot_after_coord_merge=True,
    )
    status_path = f"kitty-specs/{mission_slug}/status.json"
    original_run = subprocess.run
    merge_base_calls = 0
    head_merge_base_calls = 0

    def untrusted_merge_base(args, **kwargs):
        nonlocal head_merge_base_calls, merge_base_calls
        if args[:3] == ["git", "merge-base", "--all"] and args[3] == "HEAD":
            head_merge_base_calls += 1
            if head_merge_base_calls > 2:
                merge_base_calls += 1
                if failure_mode == "timeout":
                    raise subprocess.TimeoutExpired(args, timeout=30)
                return subprocess.CompletedProcess(args, 0, stdout=f"{'a' * 40}\n{'b' * 40}\n", stderr="")
        return original_run(args, **kwargs)

    with monkeypatch.context() as patcher:
        patcher.setattr(subprocess, "run", untrusted_merge_base)
        authored_paths = _authored_paths_for_handoff(repo_root, mission_slug, lane_worktree)

    assert merge_base_calls > 0
    assert status_path in authored_paths


def test_lane_authored_status_snapshot_mutation_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        lane_edit="status-json-tamper",
        coordination_updates_after_lane_base=True,
        stale_coordination_status_snapshot=True,
        refresh_status_snapshot_after_coord_merge=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output


def test_identical_planning_content_on_both_coordination_merge_parents_is_inherited(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        include_claim_time_planning_pin=False,
        planning_drift_after_lane_merge=True,
    )
    monkeypatch.chdir(repo_root)

    mission_meta = json.loads((repo_root / "kitty-specs" / mission_slug / "meta.json").read_text(encoding="utf-8"))
    workspace_context = load_context(repo_root, lane_worktree.name)
    assert workspace_context is not None and workspace_context.base_commit is not None
    assert _git(lane_worktree, "merge-base", "HEAD", str(mission_meta["coordination_branch"])) == workspace_context.base_commit
    planning_ref = str(mission_meta["target_branch"])
    planning_commit = _git(lane_worktree, "merge-base", "HEAD", planning_ref)
    planning_path = f"kitty-specs/{mission_slug}/plan.md"
    dependency_merge = _merge_identical_coordination_planning_snapshot(
        repo_root,
        mission_slug,
        lane_worktree,
        planning_commit,
        planning_path,
    )
    merge_parents = _git(lane_worktree, "show", "-s", "--format=%P", dependency_merge).split()
    assert len(merge_parents) == 2
    assert _git(lane_worktree, "merge-base", *merge_parents) == workspace_context.base_commit
    result_bytes = _git_bytes(lane_worktree, "show", f"{dependency_merge}:{planning_path}")
    assert result_bytes == _git_bytes(lane_worktree, "show", f"{merge_parents[0]}:{planning_path}")
    assert result_bytes == _git_bytes(lane_worktree, "show", f"{merge_parents[1]}:{planning_path}")

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output


def test_recorded_p1_plan_stays_clean_after_planning_target_advances_to_p2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        planning_drift_after_lane_merge=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output


def test_merged_p2_plan_stays_trusted_after_planning_target_advances_to_p3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(tmp_path, monkeypatch)
    primary_dir = repo_root / "kitty-specs" / mission_slug
    mission_meta = json.loads((primary_dir / "meta.json").read_text(encoding="utf-8"))
    planning_ref = str(mission_meta["target_branch"])
    planning_path = f"kitty-specs/{mission_slug}/plan.md"
    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.base_commit is not None
    assert context.planning_commit_sha is not None
    p1 = context.planning_commit_sha

    plan_path = repo_root / planning_path
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nPlanning branch P2 before lane handoff.\n", encoding="utf-8")
    _commit_all(repo_root, "planning: advance to P2 before handoff")
    p2 = _git(repo_root, "rev-parse", "HEAD")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", p2)

    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nPlanning branch P3 before lane handoff.\n", encoding="utf-8")
    _commit_all(repo_root, "planning: advance to P3 before handoff")
    p3 = _git(repo_root, "rev-parse", "HEAD")

    # Pin P1 at claim, merge the authoritative P2 into the lane, then move
    # the planning branch to P3 while the lane remains at P2.
    assert context.planning_commit_sha == p1
    assert _git(repo_root, "merge-base", planning_ref, p2) == p2
    assert _git(repo_root, "merge-base", p1, p2) == p1
    assert _git(repo_root, "merge-base", p2, p3) == p2
    assert _git(lane_worktree, "merge-base", "HEAD", p2) == p2
    assert _git(lane_worktree, "merge-base", "HEAD", p3) == p2
    assert _git(repo_root, "show", f"{p2}:{planning_path}") != _git(repo_root, "show", f"{p1}:{planning_path}")

    trusted_snapshots = _trusted_handoff_snapshots(
        lane_worktree,
        planning_ref,
        p1,
        context.base_commit,
        str(mission_meta["coordination_branch"]),
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output
    assert trusted_snapshots is not None
    assert trusted_snapshots[0] == p1
    assert trusted_snapshots[1] == p2


def test_p2_meta_canonical_status_refresh_stays_trusted_after_planning_advances_to_p3(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        stale_coordination_status_snapshot=True,
    )
    mission_dir = repo_root / "kitty-specs" / mission_slug
    meta_path = f"kitty-specs/{mission_slug}/meta.json"
    meta_file = mission_dir / "meta.json"
    mission_meta = json.loads(meta_file.read_text(encoding="utf-8"))
    planning_ref = str(mission_meta["target_branch"])
    coordination_ref = str(mission_meta["coordination_branch"])
    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.base_commit is not None
    assert context.planning_commit_sha is not None
    p1 = context.planning_commit_sha
    p1_meta = _git_bytes(repo_root, "show", f"{p1}:{meta_path}")

    mission_meta["planning_revision"] = "P2"
    meta_file.write_text(json.dumps(mission_meta, indent=2) + "\n", encoding="utf-8")
    _commit_all(repo_root, "planning: update metadata to P2")
    p2 = _git(repo_root, "rev-parse", "HEAD")
    p2_meta = _git_bytes(repo_root, "show", f"{p2}:{meta_path}")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", p2)
    assert _git_bytes(lane_worktree, "show", f"HEAD:{meta_path}") == p2_meta

    mission_id = str(mission_meta["mission_id"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mission_id[:8])
    coord_dir = coord_worktree / "kitty-specs" / mission_slug
    refresh_event_id = "01KXQB5J00H5M8S6X6AEY12345"
    append_event(
        coord_dir,
        StatusEvent(
            event_id=refresh_event_id,
            mission_slug=mission_slug,
            mission_id=mission_id,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-09-28T13:00:00+00:00",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
            reason="refresh status after P2 metadata merge",
        ),
    )
    _commit_all(coord_worktree, "coord: append status event after P2 metadata merge")
    coordination_status_tip = _git(coord_worktree, "rev-parse", "HEAD")

    merge_result = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", coordination_ref],
        cwd=lane_worktree,
        capture_output=True,
        text=True,
    )
    assert merge_result.returncode == 0, merge_result.stdout + merge_result.stderr
    lane_mission_dir = lane_worktree / "kitty-specs" / mission_slug
    materialize(lane_mission_dir)
    _git(lane_worktree, "add", "-A")
    _git(lane_worktree, "commit", "-q", "-m", "Merge canonical coordination refresh after P2")
    coordination_merge = _git(lane_worktree, "rev-parse", "HEAD")
    coordination_merge_parents = _git(lane_worktree, "show", "-s", "--format=%P", coordination_merge).split()
    refreshed_status = json.loads(_git(lane_worktree, "show", f"{coordination_merge}:kitty-specs/{mission_slug}/status.json"))
    assert coordination_status_tip in coordination_merge_parents
    assert refreshed_status["last_event_id"] == refresh_event_id
    assert _git_bytes(lane_worktree, "show", f"{coordination_merge}:{meta_path}") == p2_meta
    assert p2_meta != p1_meta

    plan_path = mission_dir / "plan.md"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nPlanning branch P3 before handoff.\n", encoding="utf-8")
    _commit_all(repo_root, "planning: advance to P3 after coordination refresh")
    p3 = _git(repo_root, "rev-parse", "HEAD")
    trusted_snapshots = _trusted_handoff_snapshots(
        lane_worktree,
        planning_ref,
        p1,
        context.base_commit,
        coordination_ref,
    )

    assert context.planning_commit_sha == p1
    assert _git(repo_root, "merge-base", planning_ref, p2) == p2
    assert _git(repo_root, "merge-base", p1, p2) == p1
    assert _git(repo_root, "merge-base", p2, p3) == p2
    assert _git(lane_worktree, "merge-base", "HEAD", p2) == p2
    assert _git(lane_worktree, "merge-base", "HEAD", p3) == p2
    assert _git(lane_worktree, "merge-base", "HEAD", coordination_status_tip) == coordination_status_tip
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output
    assert trusted_snapshots is not None
    assert trusted_snapshots[0] == p1
    assert trusted_snapshots[1] == p2
    assert trusted_snapshots[2] == coordination_status_tip


def test_flat_primary_status_replay_accepts_planning_merge_and_rejects_lane_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug = _build_mission_repo(
        tmp_path,
        monkeypatch,
        coord=False,
        mission_slug="issue-5151-flat-status",
        wp_lane="planned",
    )
    mission_dir = repo_root / "kitty-specs" / mission_slug
    mission_meta = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    mission_id = str(mission_meta["mission_id"])
    planning_ref = str(mission_meta["target_branch"])
    append_event(
        mission_dir,
        StatusEvent(
            event_id="01KXQB5J00H5M8S6X6AEY12349",
            mission_slug=mission_slug,
            mission_id=mission_id,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-09-28T12:00:00+00:00",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
            reason="seed flat mission status at fork",
        ),
    )
    materialize(mission_dir)
    _commit_all(repo_root, "planning: seed flat mission status")
    fork_commit = _git(repo_root, "rev-parse", "HEAD")

    lane_branch = lane_branch_name(mission_slug, "lane-a")
    lane_worktree = lane_worktree_path(repo_root, mission_slug, "lane-a")
    _git(repo_root, "worktree", "add", "-b", lane_branch, str(lane_worktree), fork_commit)

    mission_meta["mission_type"] = "research"
    (mission_dir / "meta.json").write_text(json.dumps(mission_meta, indent=2) + "\n", encoding="utf-8")
    materialize(mission_dir)
    _commit_all(repo_root, "planning: update flat status after metadata change")
    planning_p2 = _git(repo_root, "rev-parse", "HEAD")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", planning_p2)

    status_path = f"kitty-specs/{mission_slug}/status.json"
    merged_status = json.loads(_git(lane_worktree, "show", f"HEAD:{status_path}"))
    assert merged_status["mission_type"] == "research"
    inherited_changes = _list_wp_branch_mission_specs_changes(
        lane_worktree,
        planning_ref,
        planning_base_branch=planning_ref,
        workspace_base_commit=fork_commit,
        planning_commit_sha=fork_commit,
        coordination_ref=None,
        mission_slug=mission_slug,
    )
    assert inherited_changes == []

    status_file = lane_worktree / status_path
    status = json.loads(status_file.read_text(encoding="utf-8"))
    status["summary"]["done"] = 99
    status_file.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _commit_all(lane_worktree, "lane: tamper with inherited primary status")

    authored_changes = _list_wp_branch_mission_specs_changes(
        lane_worktree,
        planning_ref,
        planning_base_branch=planning_ref,
        workspace_base_commit=fork_commit,
        planning_commit_sha=fork_commit,
        coordination_ref=None,
        mission_slug=mission_slug,
    )
    assert authored_changes == [status_path]


def test_repeated_planning_and_coordination_refreshes_replay_per_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        stale_coordination_status_snapshot=True,
    )
    mission_dir = repo_root / "kitty-specs" / mission_slug
    meta_path = f"kitty-specs/{mission_slug}/meta.json"
    events_path = f"kitty-specs/{mission_slug}/status.events.jsonl"
    status_path = f"kitty-specs/{mission_slug}/status.json"
    meta_file = mission_dir / "meta.json"
    mission_meta = json.loads(meta_file.read_text(encoding="utf-8"))
    planning_ref = str(mission_meta["target_branch"])
    coordination_ref = str(mission_meta["coordination_branch"])
    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.base_commit is not None
    assert context.planning_commit_sha is not None
    p1 = context.planning_commit_sha
    p1_meta = _git_bytes(repo_root, "show", f"{p1}:{meta_path}")

    mission_meta["planning_revision"] = "P2"
    meta_file.write_text(json.dumps(mission_meta, indent=2) + "\n", encoding="utf-8")
    _commit_all(repo_root, "planning: update metadata to P2")
    p2 = _git(repo_root, "rev-parse", "HEAD")
    p2_meta = _git_bytes(repo_root, "show", f"{p2}:{meta_path}")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", p2)

    mission_id = str(mission_meta["mission_id"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mission_id[:8])
    coord_dir = coord_worktree / "kitty-specs" / mission_slug
    c2_event_id = "01KXQB5J00H5M8S6X6AEY12345"
    append_event(
        coord_dir,
        StatusEvent(
            event_id=c2_event_id,
            mission_slug=mission_slug,
            mission_id=mission_id,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-09-28T13:00:00+00:00",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
            reason="refresh status from coordination C2",
        ),
    )
    _commit_all(coord_worktree, "coord: append C2 status event")
    c2 = _git(coord_worktree, "rev-parse", "HEAD")

    c2_merge_result = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", coordination_ref],
        cwd=lane_worktree,
        capture_output=True,
        text=True,
    )
    assert c2_merge_result.returncode == 0, c2_merge_result.stdout + c2_merge_result.stderr
    lane_mission_dir = lane_worktree / "kitty-specs" / mission_slug
    materialize(lane_mission_dir)
    _git(lane_worktree, "add", "-A")
    _git(lane_worktree, "commit", "-q", "-m", "Merge canonical coordination C2 refresh")
    c2_lane_refresh = _git(lane_worktree, "rev-parse", "HEAD")
    c2_lane_parents = _git(lane_worktree, "show", "-s", "--format=%P", c2_lane_refresh).split()

    mission_meta["planning_revision"] = "P3"
    meta_file.write_text(json.dumps(mission_meta, indent=2) + "\n", encoding="utf-8")
    plan_path = mission_dir / "plan.md"
    plan_path.write_text(plan_path.read_text(encoding="utf-8") + "\nPlanning branch P3 before C3.\n", encoding="utf-8")
    _commit_all(repo_root, "planning: advance to P3")
    p3 = _git(repo_root, "rev-parse", "HEAD")
    p3_meta = _git_bytes(repo_root, "show", f"{p3}:{meta_path}")
    _git(lane_worktree, "merge", "--no-edit", "--no-ff", p3)

    c3_event_id = "01KXQB5J00H5M8S6X6AEY12346"
    append_event(
        coord_dir,
        StatusEvent(
            event_id=c3_event_id,
            mission_slug=mission_slug,
            mission_id=mission_id,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.IN_PROGRESS,
            at="2026-09-28T14:00:00+00:00",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
            reason="refresh status from coordination C3",
        ),
    )
    _commit_all(coord_worktree, "coord: append C3 status event")
    c3 = _git(coord_worktree, "rev-parse", "HEAD")
    c3_merge_result = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", coordination_ref],
        cwd=lane_worktree,
        capture_output=True,
        text=True,
    )
    assert c3_merge_result.returncode == 0, c3_merge_result.stdout + c3_merge_result.stderr
    materialize(lane_mission_dir)
    _git(lane_worktree, "add", "-A")
    _git(lane_worktree, "commit", "-q", "-m", "Merge canonical coordination C3 refresh")
    c3_lane_refresh = _git(lane_worktree, "rev-parse", "HEAD")
    c3_lane_parents = _git(lane_worktree, "show", "-s", "--format=%P", c3_lane_refresh).split()

    c2_refreshed_status = json.loads(_git(lane_worktree, "show", f"{c2_lane_refresh}:{status_path}"))
    c3_refreshed_status = json.loads(_git(lane_worktree, "show", f"{c3_lane_refresh}:{status_path}"))
    assert c2 in c2_lane_parents
    assert c3 in c3_lane_parents
    assert _git_bytes(lane_worktree, "show", f"{c2_lane_refresh}:{meta_path}") == p2_meta
    assert _git_bytes(lane_worktree, "show", f"{c2_lane_refresh}:{events_path}") == _git_bytes(coord_worktree, "show", f"{c2}:{events_path}")
    assert c2_refreshed_status["last_event_id"] == c2_event_id
    assert _git_bytes(lane_worktree, "show", f"{c3_lane_refresh}:{meta_path}") == p3_meta
    assert _git_bytes(lane_worktree, "show", f"{c3_lane_refresh}:{events_path}") == _git_bytes(coord_worktree, "show", f"{c3}:{events_path}")
    assert c3_refreshed_status["last_event_id"] == c3_event_id
    assert p1_meta != p2_meta and p2_meta != p3_meta

    trusted_snapshots = _trusted_handoff_snapshots(
        lane_worktree,
        planning_ref,
        p1,
        context.base_commit,
        coordination_ref,
    )
    assert trusted_snapshots is not None
    assert _git(repo_root, "merge-base", p1, p2) == p1
    assert _git(repo_root, "merge-base", p2, p3) == p2
    assert _git(lane_worktree, "merge-base", c2_lane_refresh, p3) == p2
    assert _git(lane_worktree, "merge-base", c2_lane_refresh, c3) == c2
    assert _git(lane_worktree, "merge-base", c3_lane_refresh, p3) == p3
    assert _git(lane_worktree, "merge-base", c3_lane_refresh, c3) == c3
    assert trusted_snapshots[0] == p1
    assert trusted_snapshots[1] == p3
    assert trusted_snapshots[2] == c3

    authored_paths = _lane_authored_kitty_specs_paths(
        lane_worktree,
        context.base_commit,
        tuple(snapshot for snapshot in trusted_snapshots if snapshot is not None),
        mission_slug=mission_slug,
        planning_pin=trusted_snapshots[0],
        planning_ref=planning_ref,
        merged_planning_tip=trusted_snapshots[1],
        coordination_snapshot=trusted_snapshots[2],
        coordination_ref=coordination_ref,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output
    assert authored_paths is not None
    assert status_path not in authored_paths


def test_reachable_lane_authored_plan_pin_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, lane_worktree, changed_paths = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        lane_edit="plan",
        planning_drift_after_lane_merge=True,
    )
    planning_path = f"kitty-specs/{mission_slug}/plan.md"
    assert changed_paths == [planning_path]

    context = load_context(repo_root, lane_worktree.name)
    assert context is not None and context.base_commit is not None
    lane_authored_pin = _git(lane_worktree, "rev-parse", "HEAD")
    assert (
        planning_path
        in _git(
            lane_worktree,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            lane_authored_pin,
        ).splitlines()
    )
    assert _git(lane_worktree, "merge-base", context.base_commit, lane_authored_pin) != lane_authored_pin
    assert _git(lane_worktree, "merge-base", "HEAD", lane_authored_pin) == lane_authored_pin

    save_context(repo_root, replace(context, planning_commit_sha=lane_authored_pin))
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "could not verify" in result.output.lower()
    assert "No handoff was made" in result.output


@pytest.mark.parametrize(
    ("lane_base_at_planning_pin", "lane_base_at_later_planning_tip"),
    [(True, False), (False, True)],
)
def test_clean_claim_pin_equal_to_or_behind_lane_fork(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lane_base_at_planning_pin: bool,
    lane_base_at_later_planning_tip: bool,
) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        coordination_updates_after_lane_base=True,
        d07_noncoord_inherited_paths=True,
        merge_claim_time_planning_commit=False,
        lane_base_at_planning_pin=lane_base_at_planning_pin,
        lane_base_at_later_planning_tip=lane_base_at_later_planning_tip,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output


def test_conflicted_coordination_merge_cannot_discard_matrix_update_to_p1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        coordination_updates_after_lane_base=True,
        resolve_planning_coord_conflict_to_fork=True,
        lane_base_at_planning_pin=True,
        merge_claim_time_planning_commit=False,
        resolve_coordination_conflict_to_planning_pin=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert f"kitty-specs/{mission_slug}/acceptance-matrix.json" in result.output


def test_one_sided_coordination_merge_cannot_discard_matrix_update_to_p1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        coordination_updates_after_lane_base=True,
        lane_base_at_planning_pin=True,
        merge_claim_time_planning_commit=False,
        discard_coordination_update_to_planning_pin=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert f"kitty-specs/{mission_slug}/acceptance-matrix.json" in result.output


def test_lane_plan_edit_after_recorded_p1_is_still_rejected_after_p2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        lane_edit="plan",
        planning_drift_after_lane_merge=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output


def test_lane_plan_edit_matching_p2_is_still_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        lane_edit="plan-match-p2",
        planning_drift_after_lane_merge=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output


def test_claim_time_p1_survives_finalize_refresh_to_p2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        planning_drift_after_lane_merge=True,
        refresh_planning_commit_after_lane_merge=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output


def test_existing_lane_history_proves_p1_and_d07_coordination_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A legacy context can prove inherited content from its lane history."""
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        planning_drift_after_lane_merge=True,
        refresh_planning_commit_after_lane_merge=True,
        coordination_updates_after_lane_base=True,
        d07_noncoord_inherited_paths=True,
        include_claim_time_planning_pin=False,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output


def test_clean_coordination_merge_commit_is_inherited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        coordination_updates_after_lane_base=True,
        d07_noncoord_inherited_paths=True,
        include_claim_time_planning_pin=False,
        force_coordination_merge_commit=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code == 0, result.output


def test_conflict_resolution_to_fork_bytes_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        coordination_updates_after_lane_base=True,
        resolve_planning_coord_conflict_to_fork=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert f"kitty-specs/{mission_slug}/acceptance-matrix.json" in result.output


@pytest.mark.parametrize("lane_edit", ["mission-events", "wp-prompt"])
def test_lane_authored_d07_coordination_content_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lane_edit: str,
) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        lane_edit=lane_edit,
        planning_drift_after_lane_merge=True,
        coordination_updates_after_lane_base=True,
        d07_noncoord_inherited_paths=True,
        include_claim_time_planning_pin=False,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output


@pytest.mark.parametrize(
    ("lane_edit", "d07_paths"),
    [
        ("coord-revert", False),
        ("wp-prompt-revert", True),
        ("wp-prompt-match-p1", True),
        ("mission-events-delete", True),
        ("status-events-delete", True),
        ("status-json-delete", True),
    ],
)
def test_lane_authored_reversal_of_post_fork_coord_content_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lane_edit: str,
    d07_paths: bool,
) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        lane_edit=lane_edit,
        planning_drift_after_lane_merge=True,
        coordination_updates_after_lane_base=True,
        d07_noncoord_inherited_paths=d07_paths,
        status_events_at_lane_base=lane_edit == "status-json-delete",
        include_status_artifacts_after_lane_base=lane_edit == "status-events-delete",
        materialize_status_snapshot_after_lane_base=lane_edit == "status-json-delete",
        include_issue_matrix_after_coord_update=lane_edit != "coord-revert",
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output


@pytest.mark.parametrize("lane_edit", ["coord-revert", "wp-prompt-revert", "mission-events-delete"])
def test_side_branch_lane_authored_reversal_of_post_fork_coord_content_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    lane_edit: str,
) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        lane_edit=lane_edit,
        lane_edit_on_side_branch=True,
        planning_drift_after_lane_merge=True,
        coordination_updates_after_lane_base=True,
        d07_noncoord_inherited_paths=lane_edit != "coord-revert",
        include_claim_time_planning_pin=False,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output


def test_legacy_context_without_post_fork_planning_pin_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        lane_edit="plan",
        planning_drift_after_lane_merge=True,
        include_claim_time_planning_pin=False,
        merge_claim_time_planning_commit=False,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "could not verify" in result.output.lower()
    assert "No handoff was made" in result.output


def test_quoted_kitty_specs_path_fails_closed(tmp_path: Path) -> None:
    """A quoted path from ``git diff --name-only`` must not disappear cleanly."""
    repo = tmp_path / "quoted-path-repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("anchor\n", encoding="utf-8")
    _commit_all(repo, "anchor")

    _git(repo, "checkout", "-q", "-b", "lane")
    mission_dir = repo / "kitty-specs" / "test-mission"
    mission_dir.mkdir(parents=True)
    (mission_dir / "odd\tname.json").write_text("lane content\n", encoding="utf-8")
    _commit_all(repo, "lane: add quoted path")

    output = _git(repo, "diff", "--name-only", "main", "HEAD", "--", "kitty-specs/")
    assert output.startswith('"kitty-specs/')

    flagged = _list_wp_branch_mission_specs_changes(repo, "main")

    assert flagged is None
    assert _filter_by_planning_tip_content(repo, [], "main") is None


def test_lane_authorship_history_command_failure_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _failed_git(*args, **_kwargs):
        return subprocess.CompletedProcess(args, 128, stdout="", stderr="git history unavailable")

    monkeypatch.setattr("specify_cli.cli.commands.agent.tasks.subprocess.run", _failed_git)

    result = _lane_authored_kitty_specs_paths(tmp_path, "fork", ("planning", "coordination"))

    assert result is None


def test_lane_authorship_history_timeout_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _timed_out(args, **_kwargs):
        raise subprocess.TimeoutExpired(args, timeout=30)

    monkeypatch.setattr("specify_cli.cli.commands.agent.tasks.subprocess.run", _timed_out)

    result = _lane_authored_kitty_specs_paths(tmp_path, "fork", ("planning", "coordination"))

    assert result is None


def test_unrelated_explicit_planning_pin_fails_closed(tmp_path: Path) -> None:
    repo = tmp_path / "unrelated-planning-pin-repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test Runner")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("fork\n", encoding="utf-8")
    _commit_all(repo, "fork")
    fork_commit = _git(repo, "rev-parse", "HEAD")

    _git(repo, "switch", "-q", "--orphan", "unrelated-pin")
    _git(repo, "commit", "--allow-empty", "-q", "-m", "unrelated planning pin")
    planning_pin = _git(repo, "rev-parse", "HEAD")
    _git(repo, "switch", "-q", "main")

    result = _trusted_handoff_snapshots(repo, "main", planning_pin, fork_commit, None)

    assert result is None


def test_lane_authorship_octopus_merge_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _octopus_history(args, **_kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="merge p1 p2 p3\n", stderr="")

    monkeypatch.setattr("specify_cli.cli.commands.agent.tasks.subprocess.run", _octopus_history)
    monkeypatch.setattr("specify_cli.cli.commands.agent.tasks_shared.git_merge_base", lambda *_args: "not-commit")

    result = _lane_authored_kitty_specs_paths(tmp_path, "fork", ("trusted",))

    assert result is None


def test_lane_authorship_missing_trusted_merge_base_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _single_commit_history(args, **_kwargs):
        return subprocess.CompletedProcess(args, 0, stdout="lane-commit lane-parent\n", stderr="")

    monkeypatch.setattr("specify_cli.cli.commands.agent.tasks.subprocess.run", _single_commit_history)
    monkeypatch.setattr("specify_cli.cli.commands.agent.tasks_shared.git_merge_base", lambda *_args: None)

    result = _lane_authored_kitty_specs_paths(tmp_path, "fork", ("trusted",))

    assert result is None


def test_lane_authored_coordination_matrix_change_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(tmp_path, monkeypatch, lane_edit="coord")
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output
    assert "git restore --source" not in result.output


def test_lane_coord_edit_that_matches_planning_tip_is_still_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(tmp_path, monkeypatch, lane_edit="coord-match-planning")
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output


def test_lane_authored_primary_planning_change_remains_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, changed_paths = _build_handoff_repo(tmp_path, monkeypatch, lane_edit="primary")
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "kitty-specs/ changes are not allowed on lane branches" in result.output
    assert changed_paths[0] in result.output


def test_unresolvable_planning_ref_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(tmp_path, monkeypatch, missing_planning_ref=True)
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "could not verify" in result.output.lower()
    assert "kitty-specs/" in result.output


def test_missing_claim_time_workspace_snapshot_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, mission_slug, _lane_worktree, _ = _build_handoff_repo(
        tmp_path,
        monkeypatch,
        missing_workspace_base_commit=True,
    )
    monkeypatch.chdir(repo_root)

    result = _move_for_review(repo_root, mission_slug)

    assert result.exit_code != 0
    assert "could not verify" in result.output.lower()
    assert "claim-time workspace snapshot" in result.output.lower()
