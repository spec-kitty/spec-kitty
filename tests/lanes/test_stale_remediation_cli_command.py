"""FR-091 / A-10: the stale-lane remedy is a ``spec-kitty`` command (WP17, #7285).

The remedy for a stale code lane names the re-entry path
``spec-kitty agent action implement <WP> --mission <handle>``, never a manual
``cd .worktrees/...`` and ``git merge`` recipe. A-10 verifies that the path it
names works: re-entry runs the lifecycle sync point, which refreshes the stale
lane through auto-rebase.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.lifecycle_sync import sync_lane_after_coordination_commit
from specify_cli.lanes.models import ExecutionLane
from specify_cli.lanes.stale_check import check_lane_staleness
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.git_repo]

MISSION_SLUG = "stale-remedy"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
LANE_BRANCH = f"kitty/mission-{MISSION_SLUG}-lane-a"
REENTRY_COMMAND = f"spec-kitty agent action implement WP01 --mission {MISSION_SLUG}"
WORKFLOW_EXECUTOR = Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "cli" / "commands" / "agent" / "workflow_executor.py"


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)


def _lane() -> ExecutionLane:
    return ExecutionLane(
        lane_id="lane-a",
        wp_ids=("WP01",),
        write_scope=("src/**", "kitty-specs/**"),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


def _stale_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A repository whose lane-a changed the same file the Mission branch changed (non-conflicting)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main", str(repo)], tmp_path)
    for key, value in (("user.email", "test@spec-kitty"), ("user.name", "test"), ("commit.gpgsign", "false")):
        _run(["git", "config", key, value], repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",), lane_id="lane-a", write_scope=("src/**", "kitty-specs/**"))
    (feature_dir / "tasks" / "WP01-test.md").write_text("---\nwork_package_id: WP01\n---\n# WP01\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "shared.txt").write_text("one\ntwo\nthree\nfour\nfive\nsix\n", encoding="utf-8")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "seed mission"], repo)
    _run(["git", "branch", COORD_BRANCH, "main"], repo)
    worktree = repo / ".worktrees" / f"{MISSION_SLUG}-lane-a"
    worktree.parent.mkdir()
    _run(["git", "worktree", "add", "-b", LANE_BRANCH, str(worktree), "main"], repo)

    (worktree / "src" / "shared.txt").write_text("one-lane\ntwo\nthree\nfour\nfive\nsix\n", encoding="utf-8")
    _run(["git", "commit", "-am", "lane work"], worktree)
    _run(["git", "switch", COORD_BRANCH], repo)
    (repo / "src" / "shared.txt").write_text("one\ntwo\nthree\nfour\nfive\nsix-mission\n", encoding="utf-8")
    _run(["git", "commit", "-am", "mission work"], repo)
    _run(["git", "switch", "main"], repo)
    return repo, worktree


def test_stale_remediation_has_no_git_merge_or_worktrees_cd(tmp_path: Path) -> None:
    repo, _worktree = _stale_repo(tmp_path)

    result = check_lane_staleness(_lane(), LANE_BRANCH, COORD_BRANCH, repo, mission_slug=MISSION_SLUG)

    assert result.is_stale is True
    assert result.remediation is not None
    assert REENTRY_COMMAND in result.remediation
    assert "spec-kitty consolidate" in result.remediation
    assert "cd .worktrees" not in result.remediation
    assert "git merge" not in result.remediation


def test_stale_remediation_reopens_the_approved_wp_before_reentry(tmp_path: Path) -> None:
    """#7754: at consolidate the WP is approved and ``implement`` refuses it, so the remedy reopens it first."""
    repo, _worktree = _stale_repo(tmp_path)

    result = check_lane_staleness(_lane(), LANE_BRANCH, COORD_BRANCH, repo, mission_slug=MISSION_SLUG)

    assert result.remediation is not None
    reopen = f"spec-kitty agent tasks move-task WP01 --to planned --review-feedback-file <file> --mission {MISSION_SLUG}"
    assert reopen in result.remediation
    assert "re-review" in result.remediation
    assert result.remediation.index(reopen) < result.remediation.index(REENTRY_COMMAND)


def test_stale_remediation_without_handle_names_placeholder(tmp_path: Path) -> None:
    repo, _worktree = _stale_repo(tmp_path)

    result = check_lane_staleness(_lane(), LANE_BRANCH, COORD_BRANCH, repo)

    assert result.remediation is not None
    assert "spec-kitty agent action implement WP01 --mission <mission>" in result.remediation
    assert "git merge" not in result.remediation


def test_reentry_refreshes_stale_lane(tmp_path: Path) -> None:
    """A-10: the sync point re-entry runs refreshes the stale lane (auto-rebase), so it is no longer stale."""
    repo, _worktree = _stale_repo(tmp_path)
    assert check_lane_staleness(_lane(), LANE_BRANCH, COORD_BRANCH, repo).is_stale is True

    report = sync_lane_after_coordination_commit(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        coordination_branch=COORD_BRANCH,
    )

    assert report is not None
    assert report.succeeded is True
    assert check_lane_staleness(_lane(), LANE_BRANCH, COORD_BRANCH, repo).is_stale is False


def _commit_workflow_change_calls(func: ast.FunctionDef) -> list[ast.Call]:
    return [node for node in ast.walk(func) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_commit_workflow_change"]


def test_implement_resume_path_runs_the_lane_sync_point() -> None:
    """A-10: re-running ``implement`` on an in_progress WP commits with ``auto_rebase_lane_after_commit=True``."""
    tree = ast.parse(WORKFLOW_EXECUTOR.read_text(encoding="utf-8"))
    body = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_implement_claim_transition_body")
    calls = _commit_workflow_change_calls(body)
    assert calls, "the resume path no longer commits through _commit_workflow_change"
    flags = [kw.value for call in calls for kw in call.keywords if kw.arg == "auto_rebase_lane_after_commit"]
    assert any(isinstance(flag, ast.Constant) and flag.value is True for flag in flags)


# --- WP07 ratchet (US1 AS3): without a sibling lane, the remedy text is unchanged byte for byte ----

#: The no-sibling code-lane remedy as of the #7754/#7755 fix, before WP07 (the reopen step, then auto-rebase re-entry).
_NO_SIBLING_TEXT = (
    f"Lane lane-a must incorporate changes from {COORD_BRANCH} before it is consolidated. "
    "The lane's work package is approved and `spec-kitty agent action implement` refuses an approved work package, "
    f"so reopen it first (this costs a re-review): spec-kitty agent tasks move-task WP01 --to planned --review-feedback-file <file> --mission {MISSION_SLUG}. "
    f"Then re-enter it with {REENTRY_COMMAND}, which refreshes the lane through auto-rebase; if the auto-rebase stops on a conflict, "
    "resolve it in the lane checkout the command names and commit there. "
    f"Then hand the lane's work back for review; once it is approved again, re-run: spec-kitty consolidate --mission {MISSION_SLUG}"
)


def test_non_sibling_callers_keep_the_a10_text(tmp_path: Path) -> None:
    """Ratchet: the stale check, and a refinement that names no sibling (with or without a halt), keep today's text."""
    from specify_cli.lanes.stale_check import refine_stale_result

    repo, _worktree = _stale_repo(tmp_path)

    result = check_lane_staleness(_lane(), LANE_BRANCH, COORD_BRANCH, repo, mission_slug=MISSION_SLUG)
    assert result.remediation == _NO_SIBLING_TEXT

    refined = refine_stale_result(result, _lane(), LANE_BRANCH, COORD_BRANCH, mission_slug=MISSION_SLUG, sibling_lanes=())
    assert refined.remediation == _NO_SIBLING_TEXT
    halted = refine_stale_result(result, _lane(), LANE_BRANCH, COORD_BRANCH, mission_slug=MISSION_SLUG, auto_rebase_halt="stop")
    assert halted.remediation == f"The in-run auto-rebase of lane lane-a onto {COORD_BRANCH} stopped: stop. {_NO_SIBLING_TEXT}"


def test_planning_lane_text_is_unchanged_by_a_sibling(tmp_path: Path) -> None:
    """Ratchet: the planning lane keeps its manual steps whatever siblings are named."""
    from specify_cli.lanes.stale_check import SiblingLane, _stale_remediation

    planning = ExecutionLane(lane_id="lane-planning", wp_ids=("WP01",), write_scope=("**",), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    expected = (
        "Lane lane-planning must incorporate mission changes before merging. "
        "This lane runs in the repository-root checkout (no worktree) on branch 'main'. From the repository root: "
        f"git checkout main && git merge {COORD_BRANCH}. "
        "If that merge reports a conflict on status.json (a derived projection of status.events.jsonl that git cannot text-merge), "
        "do not hand-edit it -- rebuild it from the event log instead: "
        "spec-kitty agent status materialize --mission <id> && git add kitty-specs/<id>/status.json"
    )
    sibling = (SiblingLane("lane-a", LANE_BRANCH),)
    assert _stale_remediation(planning, "main", COORD_BRANCH, mission_slug=MISSION_SLUG, sibling_lanes=sibling) == expected
