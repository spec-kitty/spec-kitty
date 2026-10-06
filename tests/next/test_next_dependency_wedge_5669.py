"""Issue-pinned regression for #5669: the finalized-board override wedge.

A finalized board whose only ``planned`` WP is dependency-walled behind a
``for_review`` WP must route to ``review`` -- on the override verdict, on the
advancing board authority and on the query preview alike -- never wedge on
``implement`` (a hard blocked floor) while a review is pending. A walled
``planned`` WP is still never dispatched for ``implement`` (#4860).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next.decision import DecisionKind, _compute_wp_progress
from specify_cli.status.models import Lane
from tests.next.test_finalized_task_routing import _scaffold

pytestmark = [pytest.mark.git_repo, pytest.mark.regression]

_WALLED_BOARD_DEPS = {"WP02": ["WP01"]}


def _walled_board(repo: Path) -> tuple[Path, str]:
    repo.mkdir()
    return _scaffold(
        repo,
        {"WP01": Lane.FOR_REVIEW, "WP02": Lane.PLANNED},
        dependencies=_WALLED_BOARD_DEPS,
    )


def test_override_reports_review_for_walled_planned_wp_5669(tmp_path: Path) -> None:
    feature_dir, _ = _walled_board(tmp_path / "repo")

    from runtime.next.runtime_bridge_decision_mapping import _finalized_task_board_override_step

    assert _finalized_task_board_override_step(feature_dir, _compute_wp_progress(feature_dir)) == "review"


def test_dispatch_authority_resolves_review_for_walled_planned_wp_5669(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _, mission_slug = _walled_board(repo)

    from runtime.next.runtime_bridge_decision_mapping import _resolve_wp_board_action

    result = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)

    assert result.board_step == "review"
    assert result.action == "review"
    assert result.wp_id == "WP01"
    assert result.blocked_reason is None


def test_query_previews_review_for_walled_planned_wp_5669(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _, mission_slug = _walled_board(repo)

    from runtime.next.runtime_bridge import query_current_state

    decision = query_current_state("codex", mission_slug, repo)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "review"
    assert decision.preview_step == "review"
    assert decision.reason != "dependencies_not_satisfied"


def test_walled_planned_wp_alone_is_never_dispatched_for_implement_4860(tmp_path: Path) -> None:
    """#4860 guard: with no review pending, a walled ``planned`` WP (its
    dependency is ``blocked``) is never dispatched for ``implement``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _, mission_slug = _scaffold(
        repo,
        {"WP01": Lane.BLOCKED, "WP02": Lane.PLANNED},
        dependencies=_WALLED_BOARD_DEPS,
    )

    from runtime.next.runtime_bridge_decision_mapping import _resolve_wp_board_action

    result = _resolve_wp_board_action(mission_slug=mission_slug, repo_root=repo)

    assert result.action != "implement"
    assert result.wp_id != "WP02"


def test_claimable_planned_wp_still_routes_to_implement(tmp_path: Path) -> None:
    """NFR-002: a dependency-satisfied planned WP keeps routing to ``implement``
    even while another WP sits in ``for_review``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, _ = _scaffold(repo, {"WP01": Lane.FOR_REVIEW, "WP02": Lane.PLANNED})

    from runtime.next.runtime_bridge_decision_mapping import _finalized_task_board_override_step

    assert _finalized_task_board_override_step(feature_dir, _compute_wp_progress(feature_dir)) == "implement"


def test_board_authority_preempts_state_to_action_fallback_for_walled_board(tmp_path: Path) -> None:
    """``decision.py::_implement_state_action`` keeps a live ``for_review``
    fallback, but the board authority owns the walled verdict: its named
    ``blocked_reason`` short-circuits ``_wp_iteration_action_and_state`` so the
    fallback is never consulted for a finalized board."""
    repo = tmp_path / "repo"
    repo.mkdir()
    feature_dir, mission_slug = _scaffold(
        repo,
        {"WP01": Lane.BLOCKED, "WP02": Lane.PLANNED},
        dependencies=_WALLED_BOARD_DEPS,
    )

    from runtime.next.runtime_bridge_decision_mapping import _wp_iteration_action_and_state

    action, wp_id, _workspace, blocked_reason, _state = _wp_iteration_action_and_state("implement", mission_slug, "software-dev", feature_dir, repo)

    assert action is None
    assert wp_id is None
    assert blocked_reason is not None
    assert f"spec-kitty agent tasks status --mission {mission_slug}" in blocked_reason
