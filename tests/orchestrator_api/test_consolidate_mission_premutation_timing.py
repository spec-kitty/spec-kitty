"""#4796 red-first: ``orchestrator-api consolidate-mission`` must refuse a dirty lane worktree
BEFORE it mutates anything.

The CLI consolidation hoists a pre-mutation safety preflight, so a dirty lane worktree refuses
before any ref moves. The orchestrator-api code-lane path received only the refusal-envelope
half of that fix (#4753 finding B): ``_execute_lane_merge`` still consolidates the lane into the
mission branch, integrates the mission into the target, stamps every WP ``done`` and pushes
BEFORE ``_apply_lane_merge_cleanup`` reaches ``guarded_worktree_remove`` and refuses the dirty
lane worktree with ``MERGE_UNSAFE_WORKTREE_DIRTY``. The refusal is truthful about the reason but
a lie about the timing: by the time it fires, the target has already advanced, the WP is already
``done``, and (with ``--push``) origin already moved.

This drives the REAL ``consolidate_mission`` against a genuine repo with a real approved code
lane (merge-gates run in their default ``warn`` mode, the approved-bound check and the origin
gate pass), a real lane worktree carrying ONE untracked operator file, and a bare ``origin``.
Only the repo-root / mission-dir environment resolvers are patched (the established real-repo
pattern in this package); the merge body and the cleanup run for real so the timing is
falsifiable. The refusal (assertion 1) is the invariant both before and after the fix; the
timing pins (assertions 2-4) are RED at HEAD. WP04 hoists the preflight and turns them green.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer

from kernel.clock import now_utc_iso
from specify_cli.git.destructive_guard import MERGE_UNSAFE_WORKTREE_DIRTY
from specify_cli.lanes.branch_naming import code_lane_branch_name, worktree_path
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.orchestrator_api import _common
from specify_cli.orchestrator_api.consolidation import consolidate_mission
from specify_cli.status import read_events, reduce
from tests.consolidation.approval_stamps import restamp_log_at_lane_tips
from tests.integration.test_merge_lane_planning_data_loss import _seed_wp_approved, _write_wp_file

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_SLUG = "premutation-timing-4796"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"


def _git(repo: Path, *args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_slug": _SLUG,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "purpose_tldr": "pre-mutation timing regression pin",
        "purpose_context": "real-merge #4796 orchestrator-api preflight timing",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(feature_dir: Path) -> LanesManifest:
    manifest = LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id=None,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/foo.py",),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


@pytest.fixture
def approved_mission(tmp_path: Path) -> tuple[Path, Path, Path, str, str]:
    """``(repo, feature_dir, lane_worktree, target_sha, origin_target_sha)`` for a mergeable mission.

    A real approved code lane (WP01 on ``src/foo.py``) whose lane worktree carries one untracked
    operator file, and a bare ``origin`` whose ``main`` sits at the pre-merge tip.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")

    feature_dir = repo / "kitty-specs" / _SLUG
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    _write_wp_file(feature_dir, "WP01")
    _seed_wp_approved(feature_dir, _SLUG, "WP01")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "bootstrap approved mission fixture")

    # Mission + lane branches; the lane carries the approved code commit.
    _git(repo, "branch", _MISSION_BRANCH, "main")
    lane_branch = code_lane_branch_name(_SLUG, "lane-a")
    _git(repo, "branch", lane_branch, "main")
    _git(repo, "checkout", "-q", lane_branch)
    (repo / "src").mkdir(exist_ok=True)
    (repo / "src" / "foo.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", "src/foo.py")
    _git(repo, "commit", "-q", "-m", "feat: add foo (WP01)")
    _git(repo, "checkout", "-q", "main")

    # Stamp the approval at the lane tip so the approved-bound check passes (#5668).
    restamp_log_at_lane_tips(repo, feature_dir)

    # Bare origin whose main sits at the current (pre-merge) tip; sets refs/remotes/origin/main.
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    _git(repo, "remote", "add", "origin", str(bare))
    _git(repo, "push", "-q", "-u", "origin", "main")

    # A real lane worktree checked out on the lane branch, carrying ONE untracked operator file.
    wt_path = worktree_path(repo, _SLUG, lane_id="lane-a")
    wt_path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", str(wt_path), lane_branch)
    (wt_path / "scratch.txt").write_text("implementer's in-progress notes\n", encoding="utf-8")

    target_sha = _git(repo, "rev-parse", "refs/heads/main")
    origin_target_sha = _git(bare, "rev-parse", "refs/heads/main")
    return repo, feature_dir, wt_path, target_sha, origin_target_sha


def _run_consolidate_mission(repo: Path, feature_dir: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    with (
        patch.object(_common, "_get_main_repo_root", return_value=repo),
        patch.object(_common, "_resolve_mission_dir_or_fail", return_value=feature_dir),
        pytest.raises(typer.Exit) as excinfo,
    ):
        consolidate_mission(mission=_SLUG, target=None, strategy="merge", push=True, origin_check="off")
    assert excinfo.value.exit_code == 1, "a refused consolidation exits 1"
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one JSON envelope line, got: {lines!r}"
    envelope: dict[str, Any] = json.loads(lines[0])
    return envelope


def _wp_lane(feature_dir: Path, wp_id: str) -> str:
    snapshot = reduce(read_events(feature_dir))
    wp = snapshot.work_packages.get(wp_id, {})
    return str(wp.get("lane", "")) if isinstance(wp, dict) else ""


def test_dirty_lane_worktree_refuses_before_target_advance(
    approved_mission: tuple[Path, Path, Path, str, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, feature_dir, wt_path, target_sha, origin_target_sha = approved_mission
    bare = repo.parent / "origin.git"

    envelope = _run_consolidate_mission(repo, feature_dir, capsys)

    # (1) INVARIANT (before and after the fix): the refusal is the dirty-lane-worktree one.
    assert envelope["success"] is False
    assert envelope["data"]["destructive_op_error_code"] == MERGE_UNSAFE_WORKTREE_DIRTY
    assert MERGE_UNSAFE_WORKTREE_DIRTY in " ".join(str(e) for e in envelope["data"]["errors"])

    # (2) RED at HEAD: the merge integrated into the target before the cleanup refused.
    assert _git(repo, "rev-parse", "refs/heads/main") == target_sha, "the target branch must not advance when the lane worktree is dirty (#4796 timing)"

    # (3) RED at HEAD: WP01 was stamped done before the cleanup refused.
    assert _wp_lane(feature_dir, "WP01") != "done", "WP01 must not be stamped done when the consolidation refuses (#4796 timing)"

    # (4) RED at HEAD: the push to origin happened before the cleanup refused.
    assert _git(bare, "rev-parse", "refs/heads/main") == origin_target_sha, "origin's target branch must not move when the lane worktree is dirty (#4796 timing)"

    # The operator's untracked file is never touched by the refusal.
    assert (wt_path / "scratch.txt").read_text(encoding="utf-8") == "implementer's in-progress notes\n"
