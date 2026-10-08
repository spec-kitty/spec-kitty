"""``next`` issues a guarded ``analyze`` step between tasks and implement (WP07, FR-016, FR-017, US7).

Red-first (T030): before WP07 the runtime walked ``tasks`` straight to
``implement`` while ``agent action implement`` refused on the missing analysis
report, and the finalized-board override handed out ``implement`` without
looking at the report at all (B3).

The analysis-currency check is injected into the runtime as a callable (C-001:
the runtime imports nothing from ``specify_cli``); the fixtures here pass
hand-written callables, and ``test_analyze_step_cli.py`` covers the real wiring.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from runtime.next.decision import Decision, DecisionKind
from specify_cli.status.models import Lane
from tests.next.test_finalized_task_routing import _scaffold
from tests.runtime._next_mission_scaffold import advance_to_step, provision_mission_type_activations, scaffold_software_dev

pytestmark = [pytest.mark.git_repo]

_STEP = DecisionKind.step
_QUERY = DecisionKind.query


def _finalized_board(repo: Path) -> str:
    """A hand-run specify, plan and tasks with a finalized board; returns the slug."""
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.PLANNED})
    provision_mission_type_activations(repo, "software-dev")
    return mission_slug


class TestBoardOverrideDoesNotSkipAnalyze:
    """B3: the finalized-board override must not hand out implement unchecked."""

    def test_decide_mode_without_a_currency_check_fails_closed(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import decide_next_via_runtime

        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = decide_next_via_runtime("codex", slug, "success", repo)

        assert decision.kind == _STEP, decision.reason
        assert decision.action == "analyze"
        assert decision.error_code == "ANALYSIS_CURRENCY_UNAVAILABLE"

    def test_query_mode_without_a_currency_check_fails_closed(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import query_current_state

        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = query_current_state("codex", slug, repo)

        assert decision.kind == _QUERY
        assert decision.preview_step == "analyze"
        assert decision.error_code == "ANALYSIS_CURRENCY_UNAVAILABLE"


class TestWalkedRunIssuesAnalyzeAfterTasks:
    def test_tasks_success_advances_to_analyze_not_implement(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import decide_next_via_runtime

        repo = tmp_path / "walked"
        slug = "042-walked-run"
        scaffold_software_dev(repo, slug, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})
        advance_to_step(repo, slug, "software-dev", "tasks")

        decision: Decision = decide_next_via_runtime("codex", slug, "success", repo)

        assert decision.kind == _STEP, decision.reason
        assert decision.action == "analyze"
        assert decision.mission_state == "analyze"


def test_software_dev_runtime_template_orders_analyze_between_tasks_and_implement() -> None:
    from runtime.next._internal_runtime.schema import load_mission_template_file

    root = Path(__file__).resolve().parents[2] / "packs" / "built-in" / "missions"
    template = load_mission_template_file(root / "software-dev" / "mission-runtime.yaml")

    ids = [step.id for step in template.steps]
    assert ids == ["discovery", "specify", "plan", "tasks", "analyze", "implement", "review", "accept"]
    depends = {step.id: list(step.depends_on or []) for step in template.steps}
    assert depends["analyze"] == ["tasks"]
    assert depends["implement"] == ["analyze"]
