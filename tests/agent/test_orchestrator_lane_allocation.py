"""Regression: orchestrator-api start-implementation allocates a real lane worktree.

Before the fix, ``start-implementation`` returned a bare legacy path and never
created a lane branch, so a WP could reach ``done`` with nothing for
``merge-mission`` to integrate. These tests drive the real CLI command against a
real coordination-topology git repo with a lanes manifest and assert:

* S1/S2 — the response carries ``lane_id`` / ``lane_branch`` / ``lane_base_ref``
  and ``workspace_path`` is a real worktree checked out on the lane branch.
* S3 — moving the WP to ``for_review`` is rejected until a commit exists on the
  lane branch beyond its base.

Uses git (unlike test_orchestrator_commands_integration.py, which is git-free).

WP01 / #2570.1 note: the sequential-N-lane / zero-inter-allocation-commits
assertion belongs conceptually here, but this file's ``start-implementation``
path (``orchestrator_api.commands`` -> ``allocate_lane_worktree``) never
touches ``tasks/WP##.md`` frontmatter or the ``implement.py`` dirty-tree
guard (``_ensure_planning_artifacts_committed_git`` /
``resolve_planning_artifact_staging``) that #2570.1 fixes -- the bug and its
regression coverage live entirely on the ``spec-kitty implement`` claim
surface. Per the WP01 task guidance, that assertion was added instead to
``tests/specify_cli/cli/commands/test_implement_runtime_frontmatter_claim.py``
(``test_sequential_n_lane_allocation_needs_zero_inter_allocation_commits``),
which drives the real ``implement()`` claim path.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.worktree_allocator import DirtyWorktreeError
from specify_cli.orchestrator_api.wp_lifecycle import _enforce_for_review_commit_gate, _lane_base_ref
from specify_cli.orchestrator_api.commands import app
from specify_cli.status.models import Lane, StatusEvent

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

MISSION_SLUG = "lane-alloc"
MID8 = "01KLANE00"
MISSION_ID = "01KLANE00000000000000000000"
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"

_WP_FILE = (
    "---\n"
    "work_package_id: WP01\n"
    "title: Test WP01\n"
    "dependencies: []\n"
    "subtasks: []\n"
    "---\n\n"
    "# WP01\n"
)


def _valid_policy_json() -> str:
    return json.dumps(
        {
            "orchestrator_id": "test-orch",
            "orchestrator_version": "0.1.0",
            "agent_family": "claude",
            "approval_mode": "supervised",
            "sandbox_mode": "sandbox",
            "network_mode": "restricted",
            "dangerous_flags": [],
        }
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=MISSION_DIRNAME,
        mission_id=MISSION_ID,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01",),
                write_scope=("src/**",),
                predicted_surfaces=(),
                depends_on_lanes=(),
                parallel_group=0,
            ),
        ],
        computed_at="2026-06-20T00:00:00+00:00",
        computed_from="test",
    )


def _seed_planned_on_coord(repo: Path) -> None:
    """Record WP01 as planned on the coordination branch (genesis->planned)."""
    from specify_cli.coordination.status_service import (
        EventLogWriteContract,
        append_event_log,
    )

    seed = StatusEvent(
        event_id="01SEEDGENESIS0000000000001",
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-06-19T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-coord"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    append_event_log(
        EventLogWriteContract.coordination_transaction_append(
            worktree / "kitty-specs" / MISSION_DIRNAME
        ),
        seed,
    )
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _git(repo, "worktree", "remove", "-f", str(worktree))


@pytest.fixture
def coord_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A coord-topology mission with a lanes manifest and a seeded coord branch."""
    # Keep status emits from touching the network / dossier sync.
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "coordination_branch": COORD_BRANCH,
                "target_branch": "main",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01.md").write_text(_WP_FILE, encoding="utf-8")
    # Top-level tasks.md index carrying the canonical checked subtask rows the
    # in_progress -> for_review subtask-completeness gate (#2574) reads. Complete
    # ([x]) so the gate turns on the commit requirement (S3), not on subtasks.
    (feature_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01 Test WP01\n\n- [x] T001 subtask for WP01\n- [x] T002 subtask for WP01\n",
        encoding="utf-8",
    )
    write_lanes_json(feature_dir, _manifest())
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _git(repo, "branch", COORD_BRANCH)
    _seed_planned_on_coord(repo)
    return repo


def _start_implementation(repo: Path) -> Any:
    with patch(
        "specify_cli.orchestrator_api._common._get_main_repo_root",
        return_value=repo,
    ):
        return runner.invoke(
            app,
            [
                "start-implementation",
                "--mission",
                MISSION_DIRNAME,
                "--wp",
                "WP01",
                "--actor",
                "claude",
                "--policy",
                _valid_policy_json(),
            ],
        )


def test_start_implementation_allocates_real_lane_worktree(coord_repo: Path) -> None:
    result = _start_implementation(coord_repo)

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]

    # S2: the contract now carries the lane identity the orchestrator needs.
    assert data["lane_id"] == "lane-a"
    assert data["lane_branch"] == f"{COORD_BRANCH}-lane-a"
    assert data["lane_base_ref"] == COORD_BRANCH

    # S1: workspace_path is a real worktree checked out on the lane branch.
    workspace_path = Path(data["workspace_path"])
    assert workspace_path.exists()
    head = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=workspace_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head == f"{COORD_BRANCH}-lane-a"


def test_for_review_transition_requires_a_commit(coord_repo: Path) -> None:
    start = _start_implementation(coord_repo)
    assert start.exit_code == 0, start.output
    workspace_path = Path(json.loads(start.output)["data"]["workspace_path"])

    def _transition_for_review() -> Any:
        with patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=coord_repo,
        ):
            return runner.invoke(
                app,
                [
                    "transition",
                    "--mission",
                    MISSION_DIRNAME,
                    "--wp",
                    "WP01",
                    "--to",
                    "for_review",
                    "--actor",
                    "claude",
                    "--policy",
                    _valid_policy_json(),
                ],
            )

    # S3: no commit on the lane branch beyond base -> rejected.
    rejected = _transition_for_review()
    assert rejected.exit_code == 1, rejected.output
    assert json.loads(rejected.output)["error_code"] == "TRANSITION_REJECTED"

    # Commit something on the lane, then the gate passes.
    (workspace_path / "src").mkdir(exist_ok=True)
    (workspace_path / "src" / "impl.py").write_text("x = 1\n", encoding="utf-8")
    _git(workspace_path, "add", "-A")
    _git(workspace_path, "commit", "-q", "-m", "feat(WP01): implement")

    accepted = _transition_for_review()
    assert accepted.exit_code == 0, accepted.output
    assert json.loads(accepted.output)["data"]["to_lane"] == "for_review"


def test_lane_allocation_failure_fails_closed(coord_repo: Path) -> None:
    """A genuine allocation failure surfaces as LANE_ALLOCATION_FAILED."""

    def _boom(**_: object) -> None:
        raise DirtyWorktreeError("lane worktree has uncommitted changes")

    with (
        patch(
            "specify_cli.orchestrator_api._common._get_main_repo_root",
            return_value=coord_repo,
        ),
        patch(
            "specify_cli.lanes.worktree_allocator.allocate_lane_worktree",
            _boom,
        ),
    ):
        result = runner.invoke(
            app,
            [
                "start-implementation",
                "--mission",
                MISSION_DIRNAME,
                "--wp",
                "WP01",
                "--actor",
                "claude",
                "--policy",
                _valid_policy_json(),
            ],
        )

    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["error_code"] == "LANE_ALLOCATION_FAILED"


def test_for_review_gate_is_noop_without_lanes(tmp_path: Path) -> None:
    """The gate does not apply (no raise) when force is set or no lanes manifest."""
    # --force bypass returns without touching git/lanes at all.
    _enforce_for_review_commit_gate(
        "transition", tmp_path, "any-mission", tmp_path, "WP01", force=True
    )
    # No lanes.json under the mission dir: the gate is not applicable, no raise.
    _enforce_for_review_commit_gate(
        "transition", tmp_path, "any-mission", tmp_path, "WP01", force=False
    )


def test_lane_base_ref_falls_back_to_mission_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When placement cannot be resolved, lane_base_ref uses manifest.mission_branch."""
    from types import SimpleNamespace

    import mission_runtime

    def _raise(*_: object, **__: object) -> None:
        raise mission_runtime.ActionContextError("UNRESOLVED", "no such mission")

    monkeypatch.setattr(mission_runtime, "resolve_placement_only", _raise)
    base = _lane_base_ref(
        tmp_path, "unresolvable", SimpleNamespace(mission_branch="kitty/mission-x")
    )
    assert base == "kitty/mission-x"


def test_lane_base_ref_uses_primary_when_no_mission_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unresolvable placement AND no mission_branch -> repo default, never empty.

    An empty base ref would degrade the commit gate's `git rev-list <base>..HEAD`.
    """
    from types import SimpleNamespace

    import mission_runtime

    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(tmp_path)],
        check=True,
        capture_output=True,
    )

    def _raise(*_: object, **__: object) -> None:
        raise mission_runtime.ActionContextError("UNRESOLVED", "no such mission")

    monkeypatch.setattr(mission_runtime, "resolve_placement_only", _raise)
    base = _lane_base_ref(tmp_path, "unresolvable", SimpleNamespace(mission_branch=""))
    assert base == "main"
    assert base != ""
