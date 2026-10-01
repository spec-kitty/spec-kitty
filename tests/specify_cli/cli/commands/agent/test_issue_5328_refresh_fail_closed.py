"""#5328: refresh planning provenance without crossing into coordination writes."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.specify_cli.cli.commands.agent.test_feature_finalize_bootstrap import (
    MODULE,
    _common_patches,
)
from tests.specify_cli.cli.commands.agent.test_issue_4905_coord_staging import (
    _build_two_lane_coord_mission,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

SEAM = "specify_cli.cli.commands.agent.mission_finalize"
TARGET_BRANCH = "mission-target"


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _commit_marker(repo_root: Path, name: str) -> str:
    marker = repo_root / name
    marker.write_text(f"{name}\n", encoding="utf-8")
    _git(repo_root, "add", "--", name)
    _git(repo_root, "commit", "-q", "-m", f"planning amendment: {name}")
    return _git(repo_root, "rev-parse", "--verify", TARGET_BRANCH)


def _finish_wp_frontmatter(repo_root: Path, feature_dir: Path) -> None:
    """Commit the finalized, byte-stable frontmatter needed by the pin-only path."""
    from specify_cli.cli.commands.agent.mission_finalize import (
        _apply_bootstrap_fields,
        _apply_ownership_inference,
        _branch_strategy_text,
        _read_wp_frontmatter,
    )
    from specify_cli.frontmatter import write_frontmatter

    for wp_file in sorted((feature_dir / "tasks").glob("WP*.md")):
        metadata, body = _read_wp_frontmatter(wp_file)
        raw = wp_file.read_text(encoding="utf-8")
        builder = metadata.builder()
        changed_fields: dict[str, object] = {}
        _apply_bootstrap_fields(
            builder,
            metadata,
            deps=[],
            has_dependencies_line=True,
            requirement_refs=["FR-001" if metadata.work_package_id == "WP01" else "FR-002"],
            target_branch=TARGET_BRANCH,
            merge_target_branch=TARGET_BRANCH,
        )
        _apply_ownership_inference(builder, metadata, raw, feature_dir.name, changed_fields)
        finished = builder.build()
        assert finished.branch_strategy == _branch_strategy_text(TARGET_BRANCH, TARGET_BRANCH)
        write_frontmatter(wp_file, finished.model_dump(exclude_none=True, mode="json"), body)
    _git(repo_root, "add", "--", str(feature_dir.relative_to(repo_root) / "tasks"))
    _git(repo_root, "commit", "-q", "-m", "planning: finish WP metadata")


def _prepare_coord_mission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path, Path, str, str, str]:
    """Return a clean real-Git coord mission with stale primary planning provenance."""
    repo_root, mission_slug, coord_branch = _build_two_lane_coord_mission(
        tmp_path,
        monkeypatch,
        mission_slug="5328-refresh-safety",
    )
    feature_dir = repo_root / "kitty-specs" / mission_slug
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    coord_root = CoordinationWorkspace.worktree_path(repo_root, mission_slug, str(meta["mid8"]))
    (repo_root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(repo_root, "add", "--", ".gitignore")
    _git(repo_root, "commit", "-q", "-m", "test: ignore coordination worktrees")

    established = read_lanes_json(feature_dir)
    assert established is not None and established.planning_commit_sha is not None
    recorded_pin = established.planning_commit_sha

    _finish_wp_frontmatter(repo_root, feature_dir)
    _seed_execution_event(coord_root, mission_slug)
    _commit_marker(repo_root, "PLANNING-AMENDMENT.txt")
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert _git(coord_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    return repo_root, feature_dir, coord_root, mission_slug, coord_branch, recorded_pin


def _seed_execution_event(coord_root: Path, mission_slug: str) -> None:
    event_dir = coord_root / "kitty-specs" / mission_slug
    append_event(
        event_dir,
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
    _git(coord_root, "add", "--", f"kitty-specs/{mission_slug}/status.events.jsonl", f"kitty-specs/{mission_slug}/status.json")
    _git(coord_root, "commit", "-q", "-m", "coord: reconcile execution status")


def _file_snapshot(root: Path) -> dict[Path, bytes]:
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file() and ".git" not in path.parts}


def _index_snapshot(worktree: Path) -> tuple[str, str]:
    return (
        _git(worktree, "diff", "--cached", "--binary"),
        _git(worktree, "ls-files", "--stage"),
    )


def test_pin_refresh_failure_restores_only_its_unchanged_candidate(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.mission_finalize import _restore_planning_pin_candidate

    lanes_path = tmp_path / "lanes.json"
    original = b'{"planning_commit_sha":"old"}\n'
    candidate = b'{"planning_commit_sha":"new"}\n'
    concurrent = b'{"planning_commit_sha":"concurrent"}\n'

    lanes_path.write_bytes(candidate)
    assert _restore_planning_pin_candidate(lanes_path, candidate, original) is None
    assert lanes_path.read_bytes() == original

    lanes_path.write_bytes(concurrent)
    refusal = _restore_planning_pin_candidate(lanes_path, candidate, original)
    assert refusal is not None and "changed during the failed commit" in refusal
    assert lanes_path.read_bytes() == concurrent, "CAS rollback must preserve a concurrent lanes.json edit"


def test_conditional_lanes_rollback_rechecks_full_bytes_before_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.lanes.persistence import write_lanes_json_if_bytes_match

    lanes_path = tmp_path / "lanes.json"
    expected = b'{"planning_commit_sha":"candidate"}\n'
    replacement = b'{"planning_commit_sha":"original"}\n'
    concurrent = b'{ "planning_commit_sha": "concurrent" }\n'
    lanes_path.write_bytes(expected)
    read_bytes = Path.read_bytes
    reads = 0

    def edit_before_conditional_replace(path: Path) -> bytes:
        nonlocal reads
        if path == lanes_path:
            reads += 1
            if reads == 2:
                lanes_path.write_bytes(concurrent)
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", edit_before_conditional_replace)

    restored = write_lanes_json_if_bytes_match(tmp_path, expected, replacement)

    assert not restored
    assert lanes_path.read_bytes() == concurrent, "the second full-byte guard must preserve a change made after the first comparison"


def _run_refresh(
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    *,
    extra_patches: dict[str, object] | None = None,
) -> tuple[int, list[dict[str, object]]]:
    from specify_cli.cli.commands.agent.mission import finalize_tasks
    from specify_cli.coordination import commit_router
    from specify_cli.git.protection_policy import ProtectionPolicy

    patches = _common_patches(repo_root, mission_slug)
    patches[f"{MODULE}._find_feature_directory"] = MagicMock(return_value=feature_dir)
    patches[f"{MODULE}._resolve_planning_branch"] = MagicMock(return_value=TARGET_BRANCH)
    patches[f"{MODULE}.bootstrap_canonical_state"] = MagicMock(return_value=MagicMock(total_wps=2, newly_seeded=0, already_initialized=2, skipped=0))
    patches[f"{SEAM}._scaffold_issue_matrix_if_present"] = MagicMock()
    patches[f"{SEAM}._validate_requirement_mapping"] = MagicMock()
    patches["specify_cli.coordination.commit_router.commit_for_mission"] = commit_router.commit_for_mission
    if extra_patches:
        patches.update(extra_patches)

    emitted: list[dict[str, object]] = []
    with ExitStack() as stack:
        for target, replacement in patches.items():
            stack.enter_context(patch(target, replacement))
        stack.enter_context(
            patch(
                "specify_cli.git.protection_policy.ProtectionPolicy.resolve",
                return_value=ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False),
            )
        )
        stack.enter_context(patch(f"{SEAM}._emit_json", side_effect=emitted.append))
        try:
            finalize_tasks(
                feature=mission_slug,
                json_output=True,
                validate_only=False,
                refresh_planning_commit=True,
            )
        except typer.Exit as exc:
            return int(exc.exit_code or 0), emitted
    return 0, emitted


def _append_dirty_coord_event(coord_root: Path, mission_slug: str) -> None:
    event_dir = coord_root / "kitty-specs" / mission_slug
    append_event(
        event_dir,
        StatusEvent(
            event_id="01HXYZ0123456789ABCDEFGHJL",
            mission_slug=mission_slug,
            wp_id="WP02",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-09-29T00:01:00Z",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
        ),
    )


def test_refresh_wrong_surface_status_residue_refuses_before_any_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01HXYZ0123456789ABCDEFGHJM",
            mission_slug=mission_slug,
            wp_id="WP01",
            from_lane=None,
            to_lane=Lane.PLANNED,
            at="2026-09-29T00:00:30Z",
            actor="test-runner",
            force=False,
            execution_mode="worktree",
        ),
    )
    primary_before = _git(repo_root, "rev-parse", TARGET_BRANCH)
    coord_before = _git(repo_root, "rev-parse", coord_branch)
    files_before = _file_snapshot(repo_root)
    primary_index_before = _index_snapshot(repo_root)
    coord_index_before = _index_snapshot(coord_root)

    exit_code, emitted = _run_refresh(repo_root, feature_dir, mission_slug)

    assert exit_code != 0, f"wrong-surface status residue must refuse refresh; emitted={emitted!r}"
    assert any("refresh" in str(row.get("error", "")).lower() for row in emitted), f"refusal must identify the refresh guard; emitted={emitted!r}"
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == primary_before
    assert _git(repo_root, "rev-parse", coord_branch) == coord_before
    assert _file_snapshot(repo_root) == files_before, "refusal must preserve primary and coordination history byte-for-byte"
    assert _index_snapshot(repo_root) == primary_index_before
    assert _index_snapshot(coord_root) == coord_index_before


def test_refresh_dirty_coord_history_refuses_without_touching_either_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    _append_dirty_coord_event(coord_root, mission_slug)
    primary_before = _git(repo_root, "rev-parse", TARGET_BRANCH)
    coord_before = _git(repo_root, "rev-parse", coord_branch)
    files_before = _file_snapshot(repo_root)
    coord_index_before = _index_snapshot(coord_root)

    exit_code, emitted = _run_refresh(repo_root, feature_dir, mission_slug)

    assert exit_code != 0, f"pending coord history must refuse refresh; emitted={emitted!r}"
    assert any("refresh" in str(row.get("error", "")).lower() for row in emitted), f"refusal must identify the refresh guard; emitted={emitted!r}"
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == primary_before
    assert _git(repo_root, "rev-parse", coord_branch) == coord_before
    assert _file_snapshot(repo_root) == files_before, "refusal must preserve pending event history byte-for-byte"
    assert _git(repo_root, "diff", "--cached", "--binary") == ""
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert _index_snapshot(coord_root) == coord_index_before


def test_clean_coord_refresh_commits_only_primary_lanes_pin_and_reports_real_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    planning_tip = _git(repo_root, "rev-parse", TARGET_BRANCH)
    coord_before = _git(repo_root, "rev-parse", coord_branch)

    exit_code, emitted = _run_refresh(repo_root, feature_dir, mission_slug)

    assert exit_code == 0, f"a clean primary-only pin refresh must proceed; emitted={emitted!r}"
    success = next(row for row in emitted if row.get("result") == "success")
    lane_path = f"kitty-specs/{mission_slug}/lanes.json"
    assert success["files_committed"] == [lane_path]
    assert success["commit_created"] is True
    assert success["commit_hashes"] == [{"branch": TARGET_BRANCH, "hash": _git(repo_root, "rev-parse", TARGET_BRANCH)}]
    assert success["commit_hashes"][0]["hash"] != recorded_pin
    assert _git(repo_root, "show", "--pretty=format:", "--name-only", "HEAD").splitlines() == [lane_path]
    assert _git(repo_root, "rev-parse", coord_branch) == coord_before
    lanes_manifest = read_lanes_json(feature_dir)
    assert lanes_manifest is not None and lanes_manifest.planning_commit_sha == planning_tip
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert _git(coord_root, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_unchanged_commit_result_restores_pin_candidate_and_refuses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.coordination.commit_router import CommitRouterResult

    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    before_lanes = (feature_dir / "lanes.json").read_bytes()
    primary_before = _git(repo_root, "rev-parse", TARGET_BRANCH)
    coord_before = _git(repo_root, "rev-parse", coord_branch)
    primary_index_before = _index_snapshot(repo_root)
    coord_index_before = _index_snapshot(coord_root)
    before_events = (coord_root / "kitty-specs" / mission_slug / "status.events.jsonl").read_bytes()

    def unchanged_commit(**_kwargs: object) -> CommitRouterResult:
        return CommitRouterResult(status="unchanged", placement_ref=TARGET_BRANCH)

    exit_code, emitted = _run_refresh(
        repo_root,
        feature_dir,
        mission_slug,
        extra_patches={"specify_cli.coordination.commit_router.commit_for_mission": unchanged_commit},
    )

    assert exit_code != 0, f"changed lanes.json with an unchanged commit result must refuse; emitted={emitted!r}"
    assert not any(row.get("result") == "success" for row in emitted)
    assert any("reported unchanged" in str(row.get("error", "")) for row in emitted)
    assert (feature_dir / "lanes.json").read_bytes() == before_lanes
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == primary_before
    assert _git(repo_root, "rev-parse", coord_branch) == coord_before
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert _index_snapshot(repo_root) == primary_index_before
    assert _index_snapshot(coord_root) == coord_index_before
    assert (coord_root / "kitty-specs" / mission_slug / "status.events.jsonl").read_bytes() == before_events


def test_refresh_refuses_when_planning_tip_moves_before_pin_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    before_lanes = (feature_dir / "lanes.json").read_bytes()
    before_events = (coord_root / "kitty-specs" / mission_slug / "status.events.jsonl").read_bytes()
    coord_index_before = _index_snapshot(coord_root)
    moved_tip: list[str] = []

    from specify_cli.cli.commands.agent import mission_finalize

    run_bootstrap = mission_finalize._run_bootstrap_loop

    def advance_after_pin_capture(*args: object, **kwargs: object) -> object:
        state = run_bootstrap(*args, **kwargs)
        moved_tip.append(_commit_marker(repo_root, "RACE-AMENDMENT.txt"))
        return state

    exit_code, emitted = _run_refresh(
        repo_root,
        feature_dir,
        mission_slug,
        extra_patches={f"{SEAM}._run_bootstrap_loop": advance_after_pin_capture},
    )

    assert moved_tip, "the real-Git race injector must advance the target after pin capture"
    assert exit_code != 0, f"refresh must refuse a moved planning tip; emitted={emitted!r}"
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == moved_tip[0]
    assert (feature_dir / "lanes.json").read_bytes() == before_lanes
    assert (coord_root / "kitty-specs" / mission_slug / "status.events.jsonl").read_bytes() == before_events
    assert _git(repo_root, "rev-parse", coord_branch) == _git(coord_root, "rev-parse", "HEAD")
    assert _git(repo_root, "diff", "--cached", "--binary") == ""
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert _index_snapshot(coord_root) == coord_index_before


def test_refresh_refuses_if_target_advances_after_preflight_tip_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    original_lanes = (feature_dir / "lanes.json").read_bytes()
    initial_tip = _git(repo_root, "rev-parse", TARGET_BRANCH)
    coord_before = _git(repo_root, "rev-parse", coord_branch)
    from specify_cli.cli.commands.agent import mission_finalize

    prepare = mission_finalize._prepare_primary_pin_refresh_commit
    advanced_tip: list[str] = []

    def advance_after_tip_check(*args: object, **kwargs: object) -> object:
        plan = prepare(*args, **kwargs)
        advanced_tip.append(_commit_marker(repo_root, "RACE-AFTER-PREFLIGHT.txt"))
        return plan

    exit_code, emitted = _run_refresh(
        repo_root,
        feature_dir,
        mission_slug,
        extra_patches={f"{SEAM}._prepare_primary_pin_refresh_commit": advance_after_tip_check},
    )

    assert advanced_tip and advanced_tip[0] != initial_tip
    assert exit_code != 0, f"a pin refresh must not commit against a parent newer than its captured planning SHA; emitted={emitted!r}"
    assert not any(row.get("result") == "success" for row in emitted)
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == advanced_tip[0]
    head_parents = _git(repo_root, "rev-list", "--parents", "-n", "1", "HEAD").split()
    assert len(head_parents) == 2 and head_parents[1] == initial_tip
    assert (feature_dir / "lanes.json").read_bytes() == original_lanes
    assert _git(repo_root, "rev-parse", coord_branch) == coord_before
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_expected_parent_ref_update_cas_rejects_tip_advance_at_commit_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    original_lanes = (feature_dir / "lanes.json").read_bytes()
    initial_tip = _git(repo_root, "rev-parse", TARGET_BRANCH)
    coord_before = _git(repo_root, "rev-parse", coord_branch)
    from specify_cli.git import ref_advance

    run_git = ref_advance._run_git
    advanced_tip: list[str] = []

    def advance_before_ref_update(repo: Path, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        if args and args[0] == "update-ref" and not advanced_tip:
            advanced_tip.append(_commit_marker(repo, "RACE-AT-CAS.txt"))
        return run_git(repo, args, env=env)

    exit_code, emitted = _run_refresh(
        repo_root,
        feature_dir,
        mission_slug,
        extra_patches={"specify_cli.git.ref_advance._run_git": advance_before_ref_update},
    )

    assert advanced_tip and advanced_tip[0] != initial_tip, "the race must occur immediately before Git's conditional ref update"
    assert exit_code != 0 and not any(row.get("result") == "success" for row in emitted)
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == advanced_tip[0]
    head_parents = _git(repo_root, "rev-list", "--parents", "-n", "1", "HEAD").split()
    assert len(head_parents) == 2 and head_parents[1] == initial_tip
    assert (feature_dir / "lanes.json").read_bytes() == original_lanes
    assert _git(repo_root, "rev-parse", coord_branch) == coord_before
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert _git(coord_root, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_landed_pin_commit_is_reported_when_index_refresh_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    initial_tip = _git(repo_root, "rev-parse", TARGET_BRANCH)
    lane_path = f"kitty-specs/{mission_slug}/lanes.json"
    from specify_cli.git import commit_helpers
    from specify_cli.git import ref_advance

    run_git = commit_helpers._run_git_for_commit
    run_ref_git = ref_advance._run_git
    landed_ref_update = False
    injected_reset = False

    def fail_index_refresh_after_ref_update(
        worktree_root: Path,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal injected_reset
        if args and args[0] == "reset" and landed_ref_update and not injected_reset:
            injected_reset = True
            return subprocess.CompletedProcess(["git", *args], 1, "", "injected index refresh failure")
        result = run_git(worktree_root, args, env=env)
        return result

    def observe_successful_ref_update(
        repo: Path,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal landed_ref_update
        result = run_ref_git(repo, args, env=env)
        if args and args[0] == "update-ref" and result.returncode == 0:
            landed_ref_update = True
        return result

    exit_code, emitted = _run_refresh(
        repo_root,
        feature_dir,
        mission_slug,
        extra_patches={
            "specify_cli.git.commit_helpers._run_git_for_commit": fail_index_refresh_after_ref_update,
            "specify_cli.git.ref_advance._run_git": observe_successful_ref_update,
        },
    )

    assert landed_ref_update and injected_reset, "the injected failure must follow a successful compare-and-swap"
    assert exit_code == 0, f"the landed commit must remain a success; emitted={emitted!r}"
    success = next(row for row in emitted if row.get("result") == "success")
    landed_sha = _git(repo_root, "rev-parse", TARGET_BRANCH)
    assert landed_sha != initial_tip
    assert success["commit_created"] is True
    assert success["commit_hash"] == landed_sha
    assert success["commit_hashes"] == [{"branch": TARGET_BRANCH, "hash": landed_sha}]
    diagnostic = str(success.get("commit_diagnostic", ""))
    assert "landed" in diagnostic and "index" in diagnostic and landed_sha in diagnostic
    lanes_path = feature_dir / "lanes.json"
    assert (
        lanes_path.read_bytes()
        == subprocess.run(
            ["git", "show", f"{landed_sha}:{lane_path}"],
            cwd=repo_root,
            capture_output=True,
            check=True,
        ).stdout
    )
    lanes_manifest = read_lanes_json(feature_dir)
    assert lanes_manifest is not None and lanes_manifest.planning_commit_sha == initial_tip
    assert _git(repo_root, "rev-parse", coord_branch) == _git(coord_root, "rev-parse", "HEAD")


def test_landed_pin_commit_is_reported_when_index_refresh_raises_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    initial_tip = _git(repo_root, "rev-parse", TARGET_BRANCH)
    lane_path = f"kitty-specs/{mission_slug}/lanes.json"
    from specify_cli.git import commit_helpers
    from specify_cli.git import ref_advance

    run_git = commit_helpers._run_git_for_commit
    run_ref_git = ref_advance._run_git
    landed_ref_update = False
    injected_reset = False

    def raise_index_refresh_after_ref_update(
        worktree_root: Path,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal injected_reset
        if args and args[0] == "reset" and landed_ref_update and not injected_reset:
            injected_reset = True
            raise OSError("injected index refresh OSError")
        result = run_git(worktree_root, args, env=env)
        return result

    def observe_successful_ref_update(
        repo: Path,
        args: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal landed_ref_update
        result = run_ref_git(repo, args, env=env)
        if args and args[0] == "update-ref" and result.returncode == 0:
            landed_ref_update = True
        return result

    exit_code, emitted = _run_refresh(
        repo_root,
        feature_dir,
        mission_slug,
        extra_patches={
            "specify_cli.git.commit_helpers._run_git_for_commit": raise_index_refresh_after_ref_update,
            "specify_cli.git.ref_advance._run_git": observe_successful_ref_update,
        },
    )

    assert landed_ref_update and injected_reset, "the OSError must follow a successful compare-and-swap"
    assert exit_code == 0, f"the landed commit must remain a success; emitted={emitted!r}"
    success = next(row for row in emitted if row.get("result") == "success")
    landed_sha = _git(repo_root, "rev-parse", TARGET_BRANCH)
    assert landed_sha != initial_tip
    assert success["commit_created"] is True
    assert success["commit_hash"] == landed_sha
    assert success["commit_hashes"] == [{"branch": TARGET_BRANCH, "hash": landed_sha}]
    diagnostic = str(success.get("commit_diagnostic", ""))
    assert "landed" in diagnostic and "index" in diagnostic and landed_sha in diagnostic
    assert "injected index refresh OSError" in diagnostic
    lanes_path = feature_dir / "lanes.json"
    committed_lanes = subprocess.run(
        ["git", "show", f"{landed_sha}:{lane_path}"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    ).stdout
    assert lanes_path.read_bytes() == committed_lanes, "a landed candidate must not be rolled back after the index refresh OSError"
    lanes_manifest = read_lanes_json(feature_dir)
    assert lanes_manifest is not None and lanes_manifest.planning_commit_sha == initial_tip
    assert _git(repo_root, "rev-parse", coord_branch) == _git(coord_root, "rev-parse", "HEAD")


def test_refresh_rejects_pre_commit_hook_rewriting_the_planning_pin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    lane_path = f"kitty-specs/{mission_slug}/lanes.json"
    initial_tip = _git(repo_root, "rev-parse", TARGET_BRANCH)
    primary_index_before = _index_snapshot(repo_root)
    coord_index_before = _index_snapshot(coord_root)
    committed_lanes_before = subprocess.run(
        ["git", "show", f"{initial_tip}:{lane_path}"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    ).stdout
    hook = repo_root / ".git" / "hooks" / "pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        "#!/bin/sh\n"
        "python - <<'PY'\n"
        "import json\n"
        "from pathlib import Path\n"
        f"path = Path({lane_path!r})\n"
        "lanes = json.loads(path.read_text(encoding='utf-8'))\n"
        "lanes['planning_commit_sha'] = 'hook-mutated-pin'\n"
        "path.write_text(json.dumps(lanes, indent=2) + '\\n', encoding='utf-8')\n"
        "PY\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)

    exit_code, emitted = _run_refresh(repo_root, feature_dir, mission_slug)

    assert exit_code != 0, f"a successful pre-commit hook that rewrites lanes.json must not land a wrong pin; emitted={emitted!r}"
    assert not any(row.get("result") == "success" for row in emitted)
    assert any("hook" in str(row.get("error", "")).lower() and "changed" in str(row.get("error", "")).lower() for row in emitted)
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == initial_tip
    committed_lanes_after = subprocess.run(
        ["git", "show", f"{initial_tip}:{lane_path}"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    ).stdout
    assert committed_lanes_after == committed_lanes_before
    assert b"hook-mutated-pin" in (feature_dir / "lanes.json").read_bytes(), "failed hook edits remain visible for operator inspection"
    assert _index_snapshot(repo_root) == primary_index_before
    assert _index_snapshot(coord_root) == coord_index_before
    assert _git(repo_root, "rev-parse", coord_branch) == _git(coord_root, "rev-parse", "HEAD")


def test_refresh_rejects_clean_filter_rewriting_the_planning_pin_before_ref_update(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    lane_path = f"kitty-specs/{mission_slug}/lanes.json"
    attributes = repo_root / ".gitattributes"
    attributes.write_text(f"{lane_path} filter=pin\n", encoding="utf-8")
    _git(repo_root, "add", "--", ".gitattributes")
    _git(repo_root, "commit", "-q", "-m", "test: configure lanes clean filter")

    initial_tip = _git(repo_root, "rev-parse", TARGET_BRANCH)
    wrong_pin = "0" * len(initial_tip)
    _git(repo_root, "config", "filter.pin.clean", f"sed s/{initial_tip}/{wrong_pin}/g")
    _git(repo_root, "config", "filter.pin.required", "true")

    lanes_path = feature_dir / "lanes.json"
    original_lanes = lanes_path.read_bytes()
    committed_lanes_before = subprocess.run(
        ["git", "show", f"{initial_tip}:{lane_path}"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    ).stdout
    coord_before = _git(repo_root, "rev-parse", coord_branch)
    primary_index_before = _index_snapshot(repo_root)
    coord_index_before = _index_snapshot(coord_root)

    exit_code, emitted = _run_refresh(repo_root, feature_dir, mission_slug)

    assert exit_code != 0, f"a clean filter that rewrites the planning pin must refuse before the ref update; emitted={emitted!r}"
    assert not any(row.get("result") == "success" for row in emitted)
    assert any("staged blob" in str(row.get("error", "")).lower() for row in emitted)
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == initial_tip
    assert lanes_path.read_bytes() == original_lanes, "refusal must restore the original lanes.json bytes"
    committed_lanes_after = subprocess.run(
        ["git", "show", f"{initial_tip}:{lane_path}"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    ).stdout
    assert committed_lanes_after == committed_lanes_before
    assert _git(repo_root, "rev-parse", coord_branch) == coord_before
    assert _index_snapshot(repo_root) == primary_index_before
    assert _index_snapshot(coord_root) == coord_index_before
    assert _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all") == ""
    assert _git(coord_root, "status", "--porcelain=v1", "--untracked-files=all") == ""


def test_refresh_refuses_concurrent_lanes_edit_after_preparation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root, feature_dir, _coord_root, mission_slug, _coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    lanes_path = feature_dir / "lanes.json"
    concurrent_lanes = lanes_path.read_bytes() + b" \n"
    tip_before = _git(repo_root, "rev-parse", TARGET_BRANCH)
    from specify_cli.cli.commands.agent import mission_finalize

    prepare = mission_finalize._prepare_primary_pin_refresh_commit

    def edit_after_preparation(*args: object, **kwargs: object) -> object:
        plan = prepare(*args, **kwargs)
        lanes_path.write_bytes(concurrent_lanes)
        return plan

    exit_code, emitted = _run_refresh(
        repo_root,
        feature_dir,
        mission_slug,
        extra_patches={f"{SEAM}._prepare_primary_pin_refresh_commit": edit_after_preparation},
    )

    assert exit_code != 0, f"refresh must not overwrite lanes.json bytes changed after preparation; emitted={emitted!r}"
    assert not any(row.get("result") == "success" for row in emitted)
    assert lanes_path.read_bytes() == concurrent_lanes, "the concurrent manifest bytes must remain untouched"
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == tip_before


def test_refresh_rollback_serializes_a_concurrent_manifest_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from specify_cli.lanes import persistence as persistence_module
    from specify_cli.lanes.persistence import write_lanes_json

    repo_root, feature_dir, coord_root, mission_slug, coord_branch, _recorded_pin = _prepare_coord_mission(tmp_path, monkeypatch)
    lanes_path = feature_dir / "lanes.json"
    original_conditional_write = persistence_module.write_lanes_json_if_bytes_match
    writer_attempting = threading.Event()
    writer_done = threading.Event()
    worker_error: list[BaseException] = []
    worker: threading.Thread | None = None
    expected_concurrent_bytes: list[bytes] = []
    primary_before = _git(repo_root, "rev-parse", TARGET_BRANCH)
    coord_before = _git(coord_root, "rev-parse", "HEAD")

    def concurrent_writer() -> None:
        try:
            concurrent = read_lanes_json(feature_dir)
            assert concurrent is not None
            concurrent.planning_commit_sha = "concurrent-writer-pin"
            expected_concurrent_bytes.append((json.dumps(concurrent.to_dict(), indent=2) + "\n").encode("utf-8"))
            writer_attempting.set()
            write_lanes_json(feature_dir, concurrent)
        except BaseException as exc:  # surfaced in the test thread below
            worker_error.append(exc)
        finally:
            writer_done.set()

    def race_at_rollback_write(feature_dir: Path, expected: bytes, replacement: bytes) -> bool:
        nonlocal worker
        if feature_dir / "lanes.json" == lanes_path and worker is None:
            worker = threading.Thread(target=concurrent_writer)
            worker.start()
            assert writer_attempting.wait(timeout=2), "concurrent writer did not reach the lanes write"
            # Give an unlocked writer time to replace the candidate before the
            # rollback atomic write. A locked writer stays blocked until after
            # this transaction releases its manifest lock.
            writer_done.wait(timeout=0.1)
        return original_conditional_write(feature_dir, expected, replacement)

    hook = repo_root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho refresh-commit-refused >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    monkeypatch.setattr(persistence_module, "write_lanes_json_if_bytes_match", race_at_rollback_write)

    exit_code, emitted = _run_refresh(repo_root, feature_dir, mission_slug)

    if worker is not None:
        worker.join(timeout=5)
    assert worker is not None and writer_done.is_set(), "concurrent writer must finish after refresh releases its lock"
    assert not worker_error, worker_error
    assert expected_concurrent_bytes
    assert exit_code != 0 and not any(row.get("result") == "success" for row in emitted)
    assert lanes_path.read_bytes() == expected_concurrent_bytes[0], "rollback must not erase the serialized concurrent lanes.json write"
    assert _git(repo_root, "rev-parse", TARGET_BRANCH) == primary_before
    assert _git(coord_root, "rev-parse", coord_branch) == coord_before


def test_refresh_status_probe_does_not_refresh_the_git_index(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent.mission_finalize import _read_refresh_worktree_status

    repo_root = tmp_path / "status-probe"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "config", "user.email", "test@example.invalid")
    tracked = repo_root / "tracked.txt"
    tracked.write_text("same content\n", encoding="utf-8")
    _git(repo_root, "add", "tracked.txt")
    _git(repo_root, "commit", "-qm", "seed")

    stat = tracked.stat()
    os.utime(tracked, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
    raw_index_path = Path(_git(repo_root, "rev-parse", "--git-path", "index"))
    index_path = raw_index_path if raw_index_path.is_absolute() else repo_root / raw_index_path
    index_before = index_path.read_bytes()

    status, error = _read_refresh_worktree_status(repo_root)

    assert error is None and status == ()
    assert index_path.read_bytes() == index_before, "status-only refresh preflight must not write Git's stat cache into .git/index"
