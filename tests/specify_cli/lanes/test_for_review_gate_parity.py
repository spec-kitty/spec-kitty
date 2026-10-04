"""Both-direction parity for the shared, topology-aware ``for_review`` gate (#3547).

FR-011 / contract C-7. The ``for_review`` commit gate is hoisted to a
surface-neutral ``lanes``-side leaf (:func:`evaluate_for_review_gate`) returning a
:class:`GateDecision` (never raising the orchestrator envelope). This test proves
the ONE gate yields the SAME verdict via the hoisted leaf AND via the real
``orchestrator-api transition`` surface, across ``{primary, worktree, clone}``
checkouts, in BOTH directions:

* satisfied commits -> PASS (leaf ``passed`` True; transition exit 0)
* unsatisfied commits -> FAIL (leaf ``passed`` False; transition rejected)

Honesty note (per WP08): this leg is internal-API (the leaf) + one real
orchestrator surface (the ``transition`` CLI). There is no separate CLI verdict
door for the gate today (WP09 adds ``agent status emit``), so "both surfaces"
here means the leaf and the orchestrator-api transition path.

Permanent guard (#3547, fixed): the hoisted leaf ``specify_cli.lanes.for_review_gate``
now exists and this matrix keeps both surfaces in verdict parity.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.lanes.for_review_gate import GateDecision, evaluate_for_review_gate
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.orchestrator_api.commands import app
from specify_cli.status.models import Lane, StatusEvent

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

MISSION_SLUG = "gate-parity"
MID8 = "01KGATE00"
MISSION_ID = "01KGATE00000000000000000000"
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"

_WP_FILE = "---\nwork_package_id: WP01\ntitle: Test WP01\ndependencies: []\nsubtasks: []\n---\n\n# WP01\n"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep status emits off the network / dossier sync."""
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_saas_fan_out", lambda *a, **k: None)


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
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


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
        EventLogWriteContract.coordination_transaction_append(worktree / "kitty-specs" / MISSION_DIRNAME),
        seed,
    )
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", "seed genesis->planned")
    _git(repo, "worktree", "remove", "-f", str(worktree))


def _build_mission(repo: Path) -> Path:
    """Materialize a coord-topology mission with a lanes manifest at ``repo``."""
    repo.mkdir(parents=True)
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


def _start_implementation(repo: Path) -> Path:
    """Allocate the lane worktree (planned->in_progress) and return its path."""
    with patch(
        "specify_cli.orchestrator_api.commands._get_main_repo_root",
        return_value=repo,
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
    assert result.exit_code == 0, result.output
    return Path(json.loads(result.output)["data"]["workspace_path"])


def _transition_for_review(repo: Path) -> Any:
    with patch(
        "specify_cli.orchestrator_api.commands._get_main_repo_root",
        return_value=repo,
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


def _resolve_gate_root(topology: str, repo: Path, lane_worktree: Path) -> Path:
    """The ``main_repo_root`` the gate resolves for a given invocation topology.

    * ``primary``  -- invoked from the primary checkout: root is the repo itself.
    * ``worktree`` -- invoked from a linked lane worktree: the canonical resolver
      re-anchors to the primary, so the gate still sees the primary root.
    * ``clone``    -- an independent full checkout of the mission: its own root.
    """
    if topology == "worktree":
        from specify_cli.core.paths import get_main_repo_root

        return get_main_repo_root(lane_worktree)
    return repo


@pytest.mark.parametrize("topology", ["primary", "worktree", "clone"])
@pytest.mark.parametrize("satisfied", [True, False])
def test_for_review_gate_parity_both_directions(tmp_path: Path, topology: str, satisfied: bool) -> None:
    """One gate, one verdict: leaf and orchestrator agree per topology & direction."""
    repo = _build_mission(tmp_path / topology)
    lane_worktree = _start_implementation(repo)

    if satisfied:
        (lane_worktree / "src").mkdir(exist_ok=True)
        (lane_worktree / "src" / "impl.py").write_text("x = 1\n", encoding="utf-8")
        _git(lane_worktree, "add", "-A")
        _git(lane_worktree, "commit", "-q", "-m", "feat(WP01): implement")

    gate_root = _resolve_gate_root(topology, repo, lane_worktree)

    # Surface 1 -- the hoisted, surface-neutral leaf: returns a decision, no raise.
    decision = evaluate_for_review_gate(gate_root, MISSION_DIRNAME, "WP01", force=False)
    assert isinstance(decision, GateDecision)
    assert decision.passed is satisfied, decision.reason
    if not satisfied:
        # Fail-closed decision must name the lane for the caller to render.
        assert decision.lane_id == "lane-a"
        assert decision.reason  # non-empty guidance

    # Surface 2 -- the real orchestrator-api transition path (delegates to the leaf).
    result = _transition_for_review(repo)
    orchestrator_passed = result.exit_code == 0
    assert orchestrator_passed is satisfied, result.output
    if not satisfied:
        assert json.loads(result.output)["error_code"] == "TRANSITION_REJECTED"

    # Parity: identical repo state -> identical verdict on both surfaces.
    assert decision.passed is orchestrator_passed


def test_for_review_gate_force_bypasses_without_lanes(tmp_path: Path) -> None:
    """Surface-neutral no-ops: ``force`` and a missing manifest both PASS."""
    assert evaluate_for_review_gate(tmp_path, "any-mission", "WP01", force=True).passed
    assert evaluate_for_review_gate(tmp_path, "any-mission", "WP01", force=False).passed
