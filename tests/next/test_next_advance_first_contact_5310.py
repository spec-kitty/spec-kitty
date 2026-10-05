"""Issue-pinned regression for #5310: advance first-contact parity.

An advancing ``next --result success`` with no persisted run against a
*finalized* board used to boot a fresh ``discovery`` run and walk the DAG from
its first step, while query mode (which applies the finalized-board override)
selected the board WP. Advance must consult the same board authority and agree
with query; a mission with no finalized board still starts at discovery, and a
board the authority declines (all approved/done) keeps its pre-existing path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next.decision import Decision, DecisionKind
from specify_cli.status.models import Lane
from tests.next.test_finalized_task_routing import _scaffold
from tests.runtime._next_mission_scaffold import provision_mission_type_activations

pytestmark = [pytest.mark.git_repo, pytest.mark.regression]

_WALLED_BOARD_DEPS = {"WP02": ["WP01"]}
_BOARD_DISPATCH_STEPS = ("implement", "review")


def _finalized_board(
    repo: Path,
    wps: dict[str, Lane],
    *,
    dependencies: dict[str, list[str]] | None = None,
) -> tuple[Path, str]:
    """Finalized board with the mission type activated (prompt resolution is real)."""
    repo.mkdir()
    feature_dir, mission_slug = _scaffold(repo, wps, dependencies=dependencies)
    provision_mission_type_activations(repo, "software-dev")
    return feature_dir, mission_slug


def _advance_and_query(repo: Path, mission_slug: str) -> tuple[Decision, Decision]:
    from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state

    advance = decide_next_via_runtime("codex", mission_slug, "success", repo)
    query = query_current_state("codex", mission_slug, repo)
    return advance, query


def test_advance_agrees_with_query_on_all_planned_finalized_board_5310(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _, mission_slug = _finalized_board(repo, {"WP01": Lane.PLANNED})

    advance, query = _advance_and_query(repo, mission_slug)

    assert query.preview_step == "implement"
    assert advance.kind == DecisionKind.step, advance.reason
    assert advance.action == query.preview_step
    assert advance.mission_state == query.mission_state
    assert advance.wp_id == "WP01"


def test_advance_agrees_with_query_on_dependency_walled_board_5310(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _, mission_slug = _finalized_board(
        repo,
        {"WP01": Lane.FOR_REVIEW, "WP02": Lane.PLANNED},
        dependencies=_WALLED_BOARD_DEPS,
    )

    advance, query = _advance_and_query(repo, mission_slug)

    assert query.preview_step == "review"
    assert advance.kind == DecisionKind.step
    assert advance.action == query.preview_step
    assert advance.mission_state == query.mission_state
    assert advance.wp_id == "WP01"


def test_advance_agrees_with_query_on_blocked_finalized_board_5310(tmp_path: Path) -> None:
    """A named ``blocked:*`` board verdict is surfaced by advance too, not
    swallowed by a fresh discovery run."""
    repo = tmp_path / "repo"
    _, mission_slug = _finalized_board(repo, {"WP01": Lane.IN_REVIEW})

    advance, query = _advance_and_query(repo, mission_slug)

    assert query.mission_state == "blocked"
    assert advance.kind == DecisionKind.blocked
    assert advance.mission_state == query.mission_state
    assert f"spec-kitty agent tasks status --mission {mission_slug}" in (advance.reason or "")


def test_advance_without_finalized_board_still_starts_at_discovery(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    feature_dir, mission_slug = _finalized_board(repo, {"WP01": Lane.PLANNED})
    (feature_dir / "tasks.md").unlink()

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance = decide_next_via_runtime("codex", mission_slug, "success", repo)

    assert advance.mission_state == "discovery"
    assert advance.action not in _BOARD_DISPATCH_STEPS


def test_advance_declines_front_phase_on_all_approved_board(tmp_path: Path) -> None:
    """Accept/done stay owned by the pre-existing path: the board authority
    declines, so the new front phase must not dispatch implement/review."""
    repo = tmp_path / "repo"
    _, mission_slug = _finalized_board(repo, {"WP01": Lane.APPROVED, "WP02": Lane.DONE})

    from runtime.next.runtime_bridge import decide_next_via_runtime

    advance = decide_next_via_runtime("codex", mission_slug, "success", repo)

    assert advance.action not in _BOARD_DISPATCH_STEPS
    assert advance.wp_id is None


def test_advance_of_an_already_walked_run_keeps_dag_progression(tmp_path: Path) -> None:
    """The front phase is first-contact only: a run that already completed DAG
    steps owns its progression, so the issued decision and the persisted run
    state advance together (never a decision with the run left behind)."""
    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next.runtime_bridge import decide_next_via_runtime, get_or_start_run
    from tests.runtime._next_mission_scaffold import advance_to_step, scaffold_software_dev

    repo = tmp_path / "walked"
    slug = "042-walked-run"
    scaffold_software_dev(repo, slug, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})
    advance_to_step(repo, slug, "software-dev", "tasks")

    advance = decide_next_via_runtime("codex", slug, "success", repo)

    assert advance.kind == DecisionKind.step, advance.reason
    assert advance.action == "implement"
    run_ref = get_or_start_run(slug, repo, "software-dev")
    assert _read_snapshot(Path(run_ref.run_dir)).issued_step_id == "implement"


def test_run_is_untouched_treats_an_unreadable_snapshot_as_touched(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import _run_is_untouched

    assert _run_is_untouched(tmp_path / "no-such-run") is False
