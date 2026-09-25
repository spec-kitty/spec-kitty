from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from runtime.next.decision import DecisionKind
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = pytest.mark.git_repo


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)


def _scaffold(
    repo: Path,
    wps: dict[str, Lane],
    *,
    canceled_reason_source: str | None = None,
) -> tuple[Path, str]:
    _init_repo(repo)
    (repo / ".kittify").mkdir()
    mission_slug = "001-finalized-routing"
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "software-dev"}), encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    write_single_lane_manifest(feature_dir, wp_ids=tuple(wps.keys()))
    for wp_id, lane in wps.items():
        (tasks_dir / f"{wp_id}.md").write_text(
            f"---\nwork_package_id: {wp_id}\ndependencies: []\ntitle: {wp_id}\n---\n# {wp_id}\n",
            encoding="utf-8",
        )
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{wp_id}-{lane}",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=lane,
                at="2026-01-01T00:00:00+00:00",
                actor="fixture",
                force=True,
                execution_mode="worktree",
                reason=("Operator chose to drop this work package" if lane is Lane.CANCELED else None),
                reason_source=canceled_reason_source if lane is Lane.CANCELED else None,
            ),
        )
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed finalized routing"], cwd=repo, check=True, capture_output=True)
    return feature_dir, mission_slug


def test_query_prefers_finalized_planned_wps_over_discovery(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.PLANNED})

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "implement"
    assert decision.preview_step == "implement"


def test_query_routes_finalized_for_review_wps_to_review(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.FOR_REVIEW})

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "review"
    assert decision.preview_step == "review"


def test_query_blocks_finalized_in_review_wps_without_discovery(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.IN_REVIEW})

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "blocked"
    assert decision.preview_step is None
    assert decision.reason == "review in progress"


def test_query_marks_all_done_finalized_wps_terminal_without_discovery(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.DONE, "WP02": Lane.DONE})

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "done"
    assert decision.preview_step is None
    assert decision.reason == "All work packages are done"


def test_finalized_for_review_routes_to_review(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.FOR_REVIEW})

    from runtime.next.runtime_bridge import _finalized_task_board_override_step
    from runtime.next.decision import _compute_wp_progress

    assert _finalized_task_board_override_step(feature_dir, _compute_wp_progress(feature_dir)) == "review"


def test_finalized_done_is_terminal(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.DONE, "WP02": Lane.DONE})

    from runtime.next.runtime_bridge import _finalized_task_board_override_step
    from runtime.next.decision import _compute_wp_progress

    assert _finalized_task_board_override_step(feature_dir, _compute_wp_progress(feature_dir)) == "done"


def test_finalized_in_review_is_blocked_not_discovery(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.IN_REVIEW})

    from runtime.next.runtime_bridge import _finalized_task_board_override_step
    from runtime.next.decision import _compute_wp_progress

    assert _finalized_task_board_override_step(feature_dir, _compute_wp_progress(feature_dir)) == "blocked:review_in_progress"


def test_finalized_override_ignores_missing_progress(tmp_path: Path) -> None:
    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()

    from runtime.next.runtime_bridge import _finalized_task_board_override_step

    assert _finalized_task_board_override_step(feature_dir, None) is None
    assert _finalized_task_board_override_step(feature_dir, {"total_wps": 0}) is None


def test_finalized_override_requires_finalized_task_artifacts(tmp_path: Path) -> None:
    feature_dir = tmp_path / "feature"
    feature_dir.mkdir()

    from runtime.next.runtime_bridge import _finalized_task_board_override_step

    assert _finalized_task_board_override_step(feature_dir, {"total_wps": 1}) is None


@pytest.mark.parametrize("lane", [Lane.CLAIMED, Lane.IN_PROGRESS])
def test_finalized_active_implementation_lanes_route_to_implement(tmp_path: Path, lane: Lane) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": lane})

    from runtime.next.runtime_bridge import _finalized_task_board_override_step
    from runtime.next.decision import _compute_wp_progress

    assert _finalized_task_board_override_step(feature_dir, _compute_wp_progress(feature_dir)) == "implement"


def test_finalized_approved_wps_route_to_accept(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.APPROVED, "WP02": Lane.DONE})

    from runtime.next.runtime_bridge import _finalized_task_board_override_step
    from runtime.next.decision import _compute_wp_progress

    assert _finalized_task_board_override_step(feature_dir, _compute_wp_progress(feature_dir)) == "accept"


def test_finalized_without_actionable_wp_blocks(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.BLOCKED})

    from runtime.next.runtime_bridge import _finalized_task_board_override_step
    from runtime.next.decision import _compute_wp_progress

    assert _finalized_task_board_override_step(feature_dir, _compute_wp_progress(feature_dir)) == "blocked:no_actionable_wp"


def test_query_routes_operator_canceled_wp_to_accept(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(
        repo,
        {"WP01": Lane.DONE, "WP02": Lane.CANCELED},
        canceled_reason_source="operator",
    )

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "accept"
    assert decision.preview_step == "accept"


def test_finalized_done_tally_cannot_promote_canceled_wp_to_done(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(
        repo,
        {"WP01": Lane.DONE, "WP02": Lane.CANCELED},
        canceled_reason_source="operator",
    )

    from runtime.next.runtime_bridge import _finalized_task_board_override_step

    progress = {"total_wps": 2, "done_wps": 2}

    assert _finalized_task_board_override_step(feature_dir, progress) == "accept"


def test_query_blocks_synthetic_canceled_wp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(
        repo,
        {"WP01": Lane.DONE, "WP02": Lane.CANCELED},
        canceled_reason_source="synthetic",
    )

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "blocked"
    assert decision.preview_step is None
    assert decision.reason == "no actionable wp"


# ===========================================================================
# advancing-next-board-unification-01M3BGQ0 T006 -- mapping pin (CT-7):
# the advancing board-authority selector (_resolve_wp_board_action) MUST
# derive the SAME lane->step->action mapping as
# _finalized_task_board_override_step / query mode, over the identical lane
# fixtures already pinned above. Distinct from the NFR-002 negative
# single-authority test in tests/runtime/test_bridge_parity.py::
# test_no_advancing_path_emits_unauthorized_step -- both are required.
# ===========================================================================


def test_advance_authority_matches_finalized_step_for_planned_wp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.PLANNED})

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    result = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)

    assert result.board_step == "implement"
    assert result.action == "implement"
    assert result.wp_id == "WP01"
    assert result.blocked_reason is None


def test_advance_authority_matches_finalized_step_for_review_wp(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.FOR_REVIEW})

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    result = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)

    assert result.board_step == "review"
    assert result.action == "review"
    assert result.wp_id == "WP01"
    assert result.blocked_reason is None


@pytest.mark.parametrize("lane", [Lane.CLAIMED, Lane.IN_PROGRESS])
def test_advance_authority_matches_finalized_step_for_active_implementation_lanes(tmp_path: Path, lane: Lane) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": lane})

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    result = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)

    assert result.board_step == "implement"


def test_advance_authority_blocks_on_in_review_with_named_recovery(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.IN_REVIEW})

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    result = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)

    assert result.board_step == "blocked:review_in_progress"
    assert result.action is None
    assert result.wp_id is None
    assert result.blocked_reason is not None
    assert f"spec-kitty agent tasks status --mission {mission_slug}" in result.blocked_reason


def test_advance_authority_blocks_on_no_actionable_wp_with_named_recovery(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.BLOCKED})

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    result = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)

    assert result.board_step == "blocked:no_actionable_wp"
    assert result.action is None
    assert result.blocked_reason is not None
    assert f"spec-kitty agent tasks status --mission {mission_slug}" in result.blocked_reason


def test_advance_authority_declines_on_accept_board_step(tmp_path: Path) -> None:
    """The selector DECLINES (returns a fully-None result with
    ``board_step=None``) when the board says ``accept``/``done`` -- that
    transition is owned by the leave-step boolean
    (``_should_advance_wp_step``), not the WP-iteration action selector
    (FR-006 preservation of the pre-existing DAG-advance shape)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.APPROVED, "WP02": Lane.DONE})

    from runtime.next.runtime_bridge import _resolve_wp_board_action

    result = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)

    assert result.board_step is None
    assert result.action is None
    assert result.blocked_reason is None
