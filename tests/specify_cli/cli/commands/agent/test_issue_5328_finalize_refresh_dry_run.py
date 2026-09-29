"""#5328: validate-only reports a planning-pin refresh without writing it."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_event
from tests.specify_cli.cli.commands.agent.test_feature_finalize_bootstrap import (
    MODULE,
    _common_patches,
    _make_bootstrap_result,
    _setup_lane_based_feature,
)

SEAM = "specify_cli.cli.commands.agent.mission_finalize"

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo_root: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _git_commit_marker(repo_root: Path) -> str:
    marker = repo_root / "PLANNING-AMENDMENT.txt"
    marker.write_text("planning amendment\n", encoding="utf-8")
    _git(repo_root, "add", "--", marker.name)
    _git(repo_root, "commit", "-q", "-m", "planning amendment")
    return _git(repo_root, "rev-parse", "--verify", "HEAD")


def _run_finalize(
    mission_slug: str,
    patches: dict[str, object],
    *,
    validate_only: bool,
    refresh: bool,
) -> None:
    from specify_cli.cli.commands.agent.mission import finalize_tasks

    handles = {name: patch(name, replacement) for name, replacement in patches.items()}
    for handle in handles.values():
        handle.start()
    try:
        finalize_tasks(
            feature=mission_slug,
            json_output=True,
            validate_only=validate_only,
            refresh_planning_commit=refresh,
        )
    except (typer.Exit, SystemExit):
        pass
    finally:
        for handle in handles.values():
            handle.stop()


def _snapshot_files(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file() and ".git" not in path.parts}


def _index_snapshot(repo_root: Path) -> tuple[str, str]:
    return (
        _git(repo_root, "diff", "--cached", "--binary"),
        _git(repo_root, "ls-files", "--stage"),
    )


def test_validate_only_reports_stale_pin_refresh_and_preserves_files(tmp_path: Path) -> None:
    mission_slug = "5328-refresh-dry-run"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test Runner")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial planning state")

    patches = _common_patches(tmp_path, mission_slug)
    patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())
    _run_finalize(mission_slug, patches, validate_only=False, refresh=False)

    established = read_lanes_json(feature_dir)
    assert established is not None and established.planning_commit_sha is not None
    recorded_sha = established.planning_commit_sha

    # A real execution event freezes the original planning pin; the following
    # commit models a legitimate planning amendment that makes the pin stale.
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01HXYZ0123456789ABCDEFGHJK",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-09-29T00:00:00Z",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
        ),
    )
    materialize(feature_dir)
    amended_sha = _git_commit_marker(tmp_path)
    assert amended_sha != recorded_sha

    before = _snapshot_files(tmp_path)
    refs_before = _git(tmp_path, "for-each-ref", "--format=%(refname) %(objectname)")
    index_before = _index_snapshot(tmp_path)
    event_path = feature_dir / "status.events.jsonl"
    events_before = event_path.read_bytes()
    status_before = _git(tmp_path, "status", "--porcelain=v1", "--untracked-files=all")
    assert "status.events.jsonl" in status_before
    assert "status.json" in status_before
    emitted: list[dict[str, object]] = []
    validate_patches = {**patches, f"{SEAM}._emit_json": emitted.append}
    _run_finalize(mission_slug, validate_patches, validate_only=True, refresh=True)

    payload = next(row for row in emitted if row.get("result") == "validation_passed")
    assert payload.get("planning_commit") == {
        "sha": amended_sha,
        "action": "refreshed",
        "previous_sha": recorded_sha,
        "branch_tip": amended_sha,
    }
    would_modify = payload.get("would_modify")
    assert isinstance(would_modify, list)
    pin_changes = [row for row in would_modify if isinstance(row, dict) and row.get("artifact") == "lanes.json"]
    assert len(pin_changes) == 1
    pin_change = pin_changes[0]
    assert pin_change.get("changes") == {"planning_commit_sha": {"from": recorded_sha, "to": amended_sha}}
    refresh_preflight = payload.get("planning_refresh_preflight")
    assert isinstance(refresh_preflight, dict)
    assert refresh_preflight.get("mutating_refresh_would_refuse_for_status_preflight") is True
    assert "would refuse" in str(payload.get("message", ""))
    findings = refresh_preflight.get("status_findings")
    assert isinstance(findings, list) and all(isinstance(finding, str) for finding in findings)
    assert any("primary worktree has pending changes" in finding for finding in findings)
    assert any("status.events.jsonl" in finding for finding in findings)
    assert any("status.json" in finding for finding in findings)
    assert _snapshot_files(tmp_path) == before, "validate-only must not write any artifact"
    assert _git(tmp_path, "for-each-ref", "--format=%(refname) %(objectname)") == refs_before
    assert _index_snapshot(tmp_path) == index_before
    assert event_path.read_bytes() == events_before, "validate-only must preserve event bytes exactly"
    assert _git(tmp_path, "status", "--porcelain=v1", "--untracked-files=all") == status_before


def test_pre_execution_refresh_previews_recorded_pin_and_commits_only_primary_lanes_pin(tmp_path: Path) -> None:
    mission_slug = "5328-pre-execution-refresh"
    feature_dir = _setup_lane_based_feature(tmp_path, mission_slug)
    _git(tmp_path, "init", "-q", "-b", "planning")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "config", "user.name", "Test Runner")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "initial planning state")

    patches = _common_patches(tmp_path, mission_slug)
    patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
    patches[f"{MODULE}._resolve_planning_branch"] = MagicMock(return_value="planning")
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result())
    _run_finalize(mission_slug, patches, validate_only=False, refresh=False)

    established = read_lanes_json(feature_dir)
    assert established is not None and established.planning_commit_sha is not None
    recorded_sha = established.planning_commit_sha
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=_make_bootstrap_result(seeded=0, existing=2))
    if _git(tmp_path, "status", "--porcelain=v1", "--untracked-files=all"):
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "finalize unclaimed mission")

    amended_sha = _git_commit_marker(tmp_path)
    assert amended_sha != recorded_sha
    files_before_preview = _snapshot_files(tmp_path)
    refs_before_preview = _git(tmp_path, "for-each-ref", "--format=%(refname) %(objectname)")
    index_before_preview = _index_snapshot(tmp_path)
    commits_before_refresh = int(_git(tmp_path, "rev-list", "--count", "planning"))

    preview_events: list[dict[str, object]] = []
    preview_patches = {**patches, f"{SEAM}._emit_json": preview_events.append}
    _run_finalize(mission_slug, preview_patches, validate_only=True, refresh=True)

    preview = next(row for row in preview_events if row.get("result") == "validation_passed")
    assert preview.get("planning_commit") == {
        "sha": amended_sha,
        "action": "refreshed",
        "previous_sha": recorded_sha,
        "branch_tip": amended_sha,
    }
    assert _snapshot_files(tmp_path) == files_before_preview, "validate-only must preserve every file"
    assert _git(tmp_path, "for-each-ref", "--format=%(refname) %(objectname)") == refs_before_preview
    assert _index_snapshot(tmp_path) == index_before_preview
    still_established = read_lanes_json(feature_dir)
    assert still_established is not None and still_established.planning_commit_sha == recorded_sha

    from specify_cli.coordination import commit_router

    mutation_events: list[dict[str, object]] = []
    mutation_patches = {
        **patches,
        "specify_cli.coordination.commit_router.commit_for_mission": commit_router.commit_for_mission,
        f"{SEAM}._emit_json": mutation_events.append,
    }
    _run_finalize(mission_slug, mutation_patches, validate_only=False, refresh=True)

    successes = [row for row in mutation_events if row.get("result") == "success"]
    assert successes, f"pre-execution refresh should commit successfully; emitted: {mutation_events!r}"
    mutated = read_lanes_json(feature_dir)
    assert mutated is not None and mutated.planning_commit_sha == amended_sha
    success = successes[0]
    assert success["files_committed"] == [f"kitty-specs/{mission_slug}/lanes.json"]
    assert success["commit_created"] is True
    assert success["commit_hashes"] == [{"branch": "planning", "hash": _git(tmp_path, "rev-parse", "planning")}]
    assert int(_git(tmp_path, "rev-list", "--count", "planning")) == commits_before_refresh + 1
    assert _git(tmp_path, "show", "--pretty=format:", "--name-only", "HEAD").splitlines() == [f"kitty-specs/{mission_slug}/lanes.json"]
    assert _git(tmp_path, "status", "--porcelain=v1", "--untracked-files=all") == ""
