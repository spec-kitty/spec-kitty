"""#7860 (WP03, FR-001/FR-011): the orchestrator API starts and resumes a planning WP where the CLI does.

Before a default Mission lands, its planning work package is worked in the checkout holding the
Mission branch (the coordination worktree once settled). ``start-implementation`` and the read-only
``resolve-workspace`` (the resume path) must report that checkout as ``workspace_path`` and the
Mission branch as ``lane_branch``, and the start must record the claim base from that checkout,
exactly as ``implement`` does. An explicit topology keeps the repository root checkout and the
target. A failure to resolve the planning lane is an envelope, never a traceback.

Real git; driven through the real ``orchestrator-api`` Typer app where the envelope is asserted.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.lanes.claim_base import read_claim_base
from specify_cli.orchestrator_api import wp_lifecycle
from specify_cli.orchestrator_api.commands import app
from specify_cli.workspace.context import clear_workspace_resolution_caches
from tests._support.git_cli import git_out
from tests.status.conftest import seed_wp_to_planned
from tests.lanes.test_planning_claim_base_7860 import (
    MISSION_BRANCH,
    PLANNING_WP,
    SLUG,
    TARGET,
    _init,
    commit_mission,
    meta,
    DefaultMission,
    settled_default_mission,
)

pytestmark = [pytest.mark.git_repo]

runner = CliRunner()

#: A valid ``--policy`` payload (the shape ``tests/agent/test_orchestrator_commands_integration.py`` uses).
_POLICY = json.dumps(
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


@pytest.fixture(autouse=True)
def _reset_caches() -> Iterator[None]:
    clear_workspace_resolution_caches()
    yield
    clear_workspace_resolution_caches()


def _invoke(repo: Path, *args: str) -> dict[str, Any]:
    with patch("specify_cli.orchestrator_api._common._get_main_repo_root", return_value=repo):
        result = runner.invoke(app, list(args))
    envelope: dict[str, Any] = json.loads(result.output)
    return envelope


def _finalized(mission: DefaultMission) -> DefaultMission:
    """Seed the planning WP to ``planned`` on the Mission branch, as ``finalize-tasks`` does."""
    seed_wp_to_planned(mission.mission_dir, PLANNING_WP, slug=SLUG)
    git_out(mission.holder, "add", "-A")
    git_out(mission.holder, "commit", "-q", "-m", "finalize: seed WP01 planned")
    return mission


def _start(repo: Path) -> dict[str, Any]:
    return _invoke(repo, "start-implementation", "--mission", SLUG, "--wp", PLANNING_WP, "--actor", "claude", "--policy", _POLICY)


def _resolve_workspace(repo: Path) -> dict[str, Any]:
    return _invoke(repo, "resolve-workspace", "--mission", SLUG, "--wp", PLANNING_WP)


# --- the default Mission: start and resume name the Mission-branch checkout --------------------


def test_start_and_resume_name_the_mission_branch_checkout(tmp_path: Path) -> None:
    mission = settled_default_mission(tmp_path)
    holder_head = git_out(mission.holder, "rev-parse", "HEAD")

    started = wp_lifecycle._resolve_start_workspace("start-implementation", mission.repo, SLUG, mission.mission_dir, PLANNING_WP)
    resumed = wp_lifecycle._resolve_existing_workspace(mission.repo, SLUG, PLANNING_WP)

    for workspace in (started, resumed):
        assert Path(workspace.workspace_path).resolve() == mission.holder.resolve()
        assert workspace.lane_branch == MISSION_BRANCH
    assert read_claim_base(mission.repo, SLUG, PLANNING_WP) == holder_head


def test_the_start_implementation_envelope_names_the_mission_branch_checkout(tmp_path: Path) -> None:
    mission = _finalized(settled_default_mission(tmp_path))
    holder_head = git_out(mission.holder, "rev-parse", "HEAD")

    started = _start(mission.repo)

    assert started["success"] is True, started
    assert Path(started["data"]["workspace_path"]).resolve() == mission.holder.resolve()
    assert started["data"]["lane_branch"] == MISSION_BRANCH
    assert read_claim_base(mission.repo, SLUG, PLANNING_WP) == holder_head

    resumed = _resolve_workspace(mission.repo)

    assert resumed["success"] is True, resumed
    assert Path(resumed["data"]["workspace_path"]).resolve() == mission.holder.resolve()
    assert resumed["data"]["lane_branch"] == MISSION_BRANCH


# --- an explicit topology: the repository root checkout and the target ------------------------


def test_an_explicit_topology_keeps_the_repository_root_checkout(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init(repo)
    commit_mission(repo, meta(topology_source=None))

    started = wp_lifecycle._resolve_start_workspace("start-implementation", repo, SLUG, repo / "kitty-specs" / SLUG, PLANNING_WP)
    resumed = wp_lifecycle._resolve_existing_workspace(repo, SLUG, PLANNING_WP)

    for workspace in (started, resumed):
        assert workspace.workspace_path == str(repo)
        assert workspace.lane_branch == TARGET
    assert read_claim_base(repo, SLUG, PLANNING_WP) == git_out(repo, "rev-parse", "HEAD")


# --- failures are envelopes -------------------------------------------------------------------


def test_a_removed_coordination_worktree_is_a_named_envelope(tmp_path: Path) -> None:
    """The Mission lives only on its Mission branch: the lookup refuses by name before any claim."""
    mission = settled_default_mission(tmp_path)
    git_out(mission.repo, "worktree", "remove", "--force", str(mission.holder))

    started = _start(mission.repo)

    assert started["success"] is False
    assert started["error_code"] == "MISSION_NOT_FOUND", started
    assert read_claim_base(mission.repo, SLUG, PLANNING_WP) is None


def test_a_mission_branch_no_checkout_holds_is_planning_checkout_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Past the lookup, the start and resume seams keep the resolver's own code (NFR-002), never the root."""
    import mission_runtime
    from specify_cli.coordination import planning_commit

    mission = _finalized(settled_default_mission(tmp_path))

    def _missing(*_a: object, **_k: object) -> object:
        raise mission_runtime.PlanningCheckoutMissing(SLUG, MISSION_BRANCH)

    monkeypatch.setattr(planning_commit, "planning_lane_target", _missing)

    for envelope in (_start(mission.repo), _resolve_workspace(mission.repo)):
        assert envelope["success"] is False
        assert envelope["error_code"] == "PLANNING_CHECKOUT_MISSING", envelope
        assert envelope["data"]["mission_branch"] == MISSION_BRANCH
    assert read_claim_base(mission.repo, SLUG, PLANNING_WP) is None


def test_an_unreadable_planning_write_ref_is_reported_by_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``PlanningWriteRefUnavailable`` carries no code: it reuses ``LANE_ALLOCATION_FAILED``, named in ``error_type``."""
    import mission_runtime

    mission = _finalized(settled_default_mission(tmp_path))

    def _unavailable(*_a: object, **_k: object) -> object:
        raise mission_runtime.PlanningWriteRefUnavailable(SLUG, "meta.json is unreadable (test)")

    monkeypatch.setattr(mission_runtime, "planning_write_ref", _unavailable)

    for envelope in (_start(mission.repo), _resolve_workspace(mission.repo)):
        assert envelope["success"] is False
        assert envelope["error_code"] == "LANE_ALLOCATION_FAILED", envelope
        assert envelope["data"]["error_type"] == "PlanningWriteRefUnavailable"
        assert "meta.json is unreadable (test)" in envelope["data"]["message"]
