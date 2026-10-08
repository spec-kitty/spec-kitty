"""``next`` issues a guarded ``analyze`` step between tasks and implement (WP07, FR-016, FR-017, US7).

Red-first (T030): before WP07 the runtime walked ``tasks`` straight to
``implement`` while ``agent action implement`` refused on the missing analysis
report, and the finalized-board override handed out ``implement`` without
looking at the report at all (B3).

The analysis-currency check is injected into the runtime as a callable (C-001:
the runtime imports nothing from ``specify_cli``). The bridge-level tests pass
hand-written callables; ``TestCliEntry`` drives the real ``spec-kitty next``
wiring (B4, T060, SC-005).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import pytest
from typer.testing import CliRunner

from runtime.next.decision import AnalysisVerdict, Decision, DecisionKind
from specify_cli import app as cli_app
from specify_cli.status.models import Lane
from tests.next.test_finalized_task_routing import _scaffold
from tests.runtime._next_mission_scaffold import advance_to_step, provision_mission_type_activations, scaffold_software_dev

pytestmark = [pytest.mark.git_repo]

_STEP = DecisionKind.step
_QUERY = DecisionKind.query
_BLOCKED = DecisionKind.blocked
_STALE_SPEC = "Analysis report is stale: spec.md"
_STALE_CHARTER = "Analysis report is stale: charter"
_MISSING_MESSAGE = "Analysis report missing: analysis-report.md has not been recorded"
_UNAVAILABLE_MESSAGE = "Analysis currency could not be evaluated: no analysis-currency check is available"
_WALKED_SLUG = "042-walked-run"

Status = Literal["current", "missing", "stale"]


def _verdict(status: Status, *stale_inputs: str) -> Callable[[], AnalysisVerdict]:
    """An injected currency check that reports ``status`` (what the CLI wraps)."""

    def _check() -> AnalysisVerdict:
        return AnalysisVerdict(status, tuple(stale_inputs))

    return _check


def _raising_check() -> AnalysisVerdict:
    raise OSError("analysis inputs are unreadable")


def _finalized_board(repo: Path) -> str:
    """A hand-run specify, plan and tasks with a finalized board; returns the slug."""
    repo.mkdir()
    _, mission_slug = _scaffold(repo, {"WP01": Lane.PLANNED})
    provision_mission_type_activations(repo, "software-dev")
    return mission_slug


def _walked_to(repo: Path, step: str) -> str:
    """A software-dev run the real engine walked to ``step``; returns the slug."""
    scaffold_software_dev(repo, _WALKED_SLUG, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})
    advance_to_step(repo, _WALKED_SLUG, "software-dev", step)
    return _WALKED_SLUG


def _issued_step(repo: Path, slug: str) -> str | None:
    from runtime.next._internal_runtime.engine import _read_snapshot
    from runtime.next.runtime_bridge import get_or_start_run

    run_ref = get_or_start_run(slug, repo, "software-dev")
    return _read_snapshot(Path(run_ref.run_dir)).issued_step_id


def _advance(repo: Path, slug: str, check: Callable[[], AnalysisVerdict] | None = None) -> Decision:
    from runtime.next.runtime_bridge import decide_next_via_runtime

    return decide_next_via_runtime("codex", slug, "success", repo, analysis_currency=check)


def _query(repo: Path, slug: str, check: Callable[[], AnalysisVerdict] | None = None) -> Decision:
    from runtime.next.runtime_bridge import query_current_state

    return query_current_state("codex", slug, repo, analysis_currency=check)


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

    def test_decide_mode_missing_report_issues_analyze(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = _advance(repo, slug, _verdict("missing"))

        assert decision.kind == _STEP, decision.reason
        assert (decision.action, decision.step_id, decision.mission_state) == ("analyze", "analyze", "analyze")
        assert decision.error_code == "ANALYSIS_REPORT_MISSING"
        assert decision.guard_failures == [_MISSING_MESSAGE]
        assert decision.wp_id is None

    def test_decide_mode_stale_report_names_each_stale_input(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = _advance(repo, slug, _verdict("stale", "spec.md", "charter"))

        assert decision.kind == _STEP, decision.reason
        assert decision.action == "analyze"
        assert decision.error_code == "ANALYSIS_REPORT_STALE"
        assert decision.guard_failures == [_STALE_SPEC, _STALE_CHARTER]

    def test_decide_mode_current_report_hands_out_implement(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = _advance(repo, slug, _verdict("current"))

        assert decision.kind == _STEP, decision.reason
        assert (decision.action, decision.wp_id) == ("implement", "WP01")
        assert decision.error_code is None
        assert decision.guard_failures == []

    def test_decide_mode_a_check_that_raises_fails_closed(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = _advance(repo, slug, _raising_check)

        assert decision.action == "analyze"
        assert decision.error_code == "ANALYSIS_CURRENCY_UNAVAILABLE"
        assert decision.guard_failures == [_UNAVAILABLE_MESSAGE]

    def test_decide_mode_refusal_leaves_the_run_untouched(self, tmp_path: Path) -> None:
        """The override issues analyze without moving the run, so the next call re-checks."""
        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        refused = _advance(repo, slug, _verdict("missing"))
        retried = _advance(repo, slug, _verdict("current"))

        assert refused.action == "analyze"
        assert (retried.action, retried.wp_id) == ("implement", "WP01")

    def test_query_mode_without_a_currency_check_fails_closed(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import query_current_state

        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = query_current_state("codex", slug, repo)

        assert decision.kind == _QUERY
        assert decision.preview_step == "analyze"
        assert decision.error_code == "ANALYSIS_CURRENCY_UNAVAILABLE"

    def test_query_mode_missing_report_previews_analyze(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = _query(repo, slug, _verdict("missing"))

        assert decision.kind == _QUERY
        assert (decision.mission_state, decision.preview_step) == ("analyze", "analyze")
        assert decision.error_code == "ANALYSIS_REPORT_MISSING"
        assert decision.guard_failures == [_MISSING_MESSAGE]

    def test_query_mode_stale_report_names_each_stale_input(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = _query(repo, slug, _verdict("stale", "spec.md", "charter"))

        assert decision.preview_step == "analyze"
        assert decision.error_code == "ANALYSIS_REPORT_STALE"
        assert decision.guard_failures == [_STALE_SPEC, _STALE_CHARTER]

    def test_query_mode_current_report_previews_implement(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        slug = _finalized_board(repo)

        decision = _query(repo, slug, _verdict("current"))

        assert (decision.mission_state, decision.preview_step) == ("implement", "implement")
        assert decision.wp_id == "WP01"
        assert decision.error_code is None


class TestAnalyzeStepGuard:
    """The walked run's ``analyze`` step completes only while the report is current."""

    def test_tasks_success_advances_to_analyze_not_implement(self, tmp_path: Path) -> None:
        repo = tmp_path / "walked"
        slug = _walked_to(repo, "tasks")

        decision = _advance(repo, slug)

        assert decision.kind == _STEP, decision.reason
        assert decision.action == "analyze"
        assert decision.mission_state == "analyze"
        assert _issued_step(repo, slug) == "analyze"

    def test_composed_tasks_advance_cannot_skip_analyze(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """T056: ``tasks`` is a composed action; its advance is planned from the template DAG, so it lands on analyze.

        The spy proves the composition path ran for this call (not the legacy DAG dispatch),
        so the tasks to implement edge cannot be hiding in ``runtime_bridge_composition``.
        """
        from runtime.next import runtime_bridge_composition as composition

        repo = tmp_path / "walked"
        slug = _walked_to(repo, "tasks")
        dispatched: list[str] = []
        real = composition._dispatch_via_composition

        def _spy(**kwargs: Any) -> Any:
            dispatched.append(kwargs["action"])
            return real(**kwargs)

        monkeypatch.setattr(composition, "_dispatch_via_composition", _spy)

        decision = _advance(repo, slug)

        assert dispatched == ["tasks"], "the tasks step must have been completed through composition"
        assert (decision.kind, decision.action) == (_STEP, "analyze"), decision.reason

    @pytest.mark.parametrize(
        ("check", "code", "failures"),
        [
            (_verdict("missing"), "ANALYSIS_REPORT_MISSING", [_MISSING_MESSAGE]),
            (_verdict("stale", "spec.md", "plan.md"), "ANALYSIS_REPORT_STALE", [_STALE_SPEC, "Analysis report is stale: plan.md"]),
            (None, "ANALYSIS_CURRENCY_UNAVAILABLE", [_UNAVAILABLE_MESSAGE]),
            (_raising_check, "ANALYSIS_CURRENCY_UNAVAILABLE", [_UNAVAILABLE_MESSAGE]),
        ],
        ids=["missing", "stale", "no-callable", "raising-callable"],
    )
    def test_refusal_reissues_analyze_with_the_typed_code(
        self,
        tmp_path: Path,
        check: Callable[[], AnalysisVerdict] | None,
        code: str,
        failures: list[str],
    ) -> None:
        repo = tmp_path / "walked"
        slug = _walked_to(repo, "analyze")

        decision = _advance(repo, slug, check)

        assert decision.kind == _STEP, decision.reason
        assert (decision.action, decision.step_id) == ("analyze", "analyze")
        assert decision.error_code == code
        assert decision.guard_failures == failures
        assert _issued_step(repo, slug) == "analyze", "a refused analyze must not advance the run"

    def test_current_report_advances_to_implement(self, tmp_path: Path) -> None:
        repo = tmp_path / "walked"
        slug = _walked_to(repo, "analyze")

        decision = _advance(repo, slug, _verdict("current"))

        assert decision.kind == _STEP, decision.reason
        assert (decision.action, decision.wp_id) == ("implement", "WP01")
        assert decision.error_code is None
        assert _issued_step(repo, slug) == "implement"

    def test_prompt_resolution_error_code_wins_over_the_analysis_code(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from runtime.next import runtime_bridge

        repo = tmp_path / "walked"
        slug = _walked_to(repo, "analyze")
        monkeypatch.setattr(runtime_bridge, "_build_prompt_or_error", lambda *a, **k: (None, "prompt exploded", "PROMPT_FAILED"))

        decision = _advance(repo, slug, _verdict("missing"))

        assert decision.kind == _BLOCKED
        assert decision.error_code == "PROMPT_FAILED"
        assert decision.reason == "prompt exploded"
        assert decision.guard_failures == [_MISSING_MESSAGE]

    def test_only_the_analyze_step_reads_the_check(self, tmp_path: Path) -> None:
        """B5: another step never calls the injected check, so it costs nothing there."""
        repo = tmp_path / "walked"
        slug = _walked_to(repo, "tasks")
        calls: list[str] = []

        def _spy() -> AnalysisVerdict:
            calls.append("called")
            return AnalysisVerdict("current")

        _advance(repo, slug, _spy)

        assert calls == []


class TestAnalyzeStepResolves:
    """B5: the new step has an action and a prompt, and its refusal renders its stale inputs."""

    def test_state_to_action_maps_analyze(self, tmp_path: Path) -> None:
        from runtime.next.decision import _state_to_action

        repo = tmp_path / "walked"
        slug = _walked_to(repo, "tasks")

        action = _state_to_action("analyze", slug, repo / "kitty-specs" / slug, repo, "software-dev")

        assert action == ("analyze", None, None)

    def test_build_prompt_or_error_resolves_analyze(self, tmp_path: Path) -> None:
        from runtime.next.decision import _build_prompt_or_error

        repo = tmp_path / "walked"
        slug = _walked_to(repo, "tasks")

        path, error, code = _build_prompt_or_error("analyze", repo / "kitty-specs" / slug, slug, None, "codex", repo, "software-dev")

        assert error is None and code is None
        assert path is not None and Path(path).is_file()

    def test_guard_failure_paths_render_the_stale_inputs(self, tmp_path: Path) -> None:
        from runtime.next.decision import _with_guard_failure_paths

        repo = tmp_path / "walked"
        slug = _walked_to(repo, "analyze")
        decision = _advance(repo, slug, _verdict("stale", "spec.md", "charter"))

        rendered = _with_guard_failure_paths(decision, repo)

        assert rendered.guard_failure_paths == {"spec.md": f"kitty-specs/{slug}/spec.md"}, "charter is not a mission artifact, so it has no path"

    def test_guard_failure_paths_are_empty_for_a_missing_report(self, tmp_path: Path) -> None:
        from runtime.next.decision import _with_guard_failure_paths

        repo = tmp_path / "walked"
        slug = _walked_to(repo, "analyze")
        decision = _advance(repo, slug, _verdict("missing"))

        assert _with_guard_failure_paths(decision, repo).guard_failure_paths == {}


class TestRunOrderIsFrozen:
    """FR-017: a run frozen before this Mission keeps its recorded order."""

    def test_frozen_run_without_analyze_still_walks_tasks_to_implement(self, tmp_path: Path) -> None:
        from runtime.next.runtime_bridge import get_or_start_run

        repo = tmp_path / "frozen"
        scaffold_software_dev(repo, _WALKED_SLUG, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "planned"})
        run_ref = get_or_start_run(_WALKED_SLUG, repo, "software-dev")
        frozen = Path(run_ref.run_dir) / "mission_template_frozen.yaml"
        old_order = frozen.read_text(encoding="utf-8")
        old_order = old_order.replace(
            "  - id: analyze\n    title: Analysis\n    depends_on: [tasks]\n    prompt_template: analyze.md\n"
            "    description: Cross-artifact consistency analysis, recorded as a current analysis report\n\n",
            "",
        ).replace("depends_on: [analyze]", "depends_on: [tasks]")
        assert "id: analyze" not in old_order, "the fixture must reproduce a pre-WP07 frozen template"
        frozen.write_text(old_order, encoding="utf-8")
        advance_to_step(repo, _WALKED_SLUG, "software-dev", "tasks")

        decision = _advance(repo, _WALKED_SLUG)

        assert decision.kind == _STEP, decision.reason
        assert decision.action == "implement"
        assert _issued_step(repo, _WALKED_SLUG) == "implement"


def test_software_dev_runtime_template_orders_analyze_between_tasks_and_implement() -> None:
    from runtime.next._internal_runtime.schema import load_mission_template_file

    root = Path(__file__).resolve().parents[2] / "packs" / "built-in" / "missions"
    template = load_mission_template_file(root / "software-dev" / "mission-runtime.yaml")

    ids = [step.id for step in template.steps]
    assert ids == ["discovery", "specify", "plan", "tasks", "analyze", "implement", "review", "accept"]
    depends = {step.id: list(step.depends_on or []) for step in template.steps}
    assert depends["analyze"] == ["tasks"]
    assert depends["implement"] == ["analyze"]


def test_analyze_stays_off_the_action_sequence() -> None:
    """C6: no action index and no graph edge are added for the new step."""
    root = Path(__file__).resolve().parents[2] / "packs" / "built-in" / "missions"
    step_yaml = (root / "mission-steps" / "software-dev" / "analyze" / "step.yaml").read_text(encoding="utf-8")

    assert "in_action_sequence: false" in step_yaml
    assert not (root / "software-dev" / "actions" / "analyze").exists()


# ---------------------------------------------------------------------------
# The real wiring: spec-kitty next, and the orchestrator-api verb (B4, T060, SC-005)
# ---------------------------------------------------------------------------

runner = CliRunner()


@pytest.fixture
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr("specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort", lambda *_a, **_k: result)
    monkeypatch.setattr("specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only", lambda *_a, **_k: result)


def _cli_project(tmp_path: Path) -> tuple[Path, Path, str]:
    """A software-dev project whose specify, plan and tasks were run by hand and whose board is finalized."""
    from tests.next.test_next_command_integration import _add_wp_files, _scaffold_project

    slug = "042-test-feature"
    repo = _scaffold_project(tmp_path, slug)
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-001.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    _add_wp_files(feature_dir, {"WP01": "planned"})
    return repo, feature_dir, slug


def _record_analysis(feature_dir: Path, repo: Path) -> None:
    """Persist a current report through the renderer ``record-analysis`` uses."""
    from specify_cli.analysis_report import write_analysis_report

    write_analysis_report(
        feature_dir=feature_dir,
        repo_root=repo,
        body="# Analysis\n\nCritical Issues Count: 0\nHigh Issues Count: 0\nPASS\n",
        analyzer_agent="test",
    )


def _next_json(repo: Path, slug: str, *extra: str) -> dict[str, Any]:
    with contextlib.chdir(repo):
        result = runner.invoke(cli_app, ["next", "--agent", "codex", "--mission", slug, "--json", *extra])
    assert result.exit_code == 0, result.output
    payload: dict[str, Any] = json.loads(result.stdout)
    return payload


@pytest.mark.usefixtures("_bypass_charter_preflight")
class TestCliEntry:
    """T060: ``spec-kitty next --json`` after tasks issues analyze; after a recorded report it advances."""

    def test_finalized_board_issues_analyze_then_implement_once_recorded(self, tmp_path: Path) -> None:
        repo, feature_dir, slug = _cli_project(tmp_path)

        first = _next_json(repo, slug, "--result", "success")
        assert first["kind"] == "step", first
        assert first["action"] == "analyze"
        assert first["error_code"] == "ANALYSIS_REPORT_MISSING"
        assert first["guard_failures"] == [_MISSING_MESSAGE]

        _record_analysis(feature_dir, repo)
        second = _next_json(repo, slug, "--result", "success")

        assert second["kind"] == "step", second
        assert (second["action"], second["wp_id"]) == ("implement", "WP01")
        assert "error_code" not in second

    def test_query_mode_previews_analyze_until_the_report_is_current(self, tmp_path: Path) -> None:
        repo, feature_dir, slug = _cli_project(tmp_path)

        before = _next_json(repo, slug)
        assert (before["kind"], before["preview_step"]) == ("query", "analyze")
        assert before["error_code"] == "ANALYSIS_REPORT_MISSING"

        _record_analysis(feature_dir, repo)
        after = _next_json(repo, slug)

        assert after["preview_step"] == "implement"

    def test_a_stale_report_names_the_changed_input(self, tmp_path: Path) -> None:
        repo, feature_dir, slug = _cli_project(tmp_path)
        _record_analysis(feature_dir, repo)
        (feature_dir / "spec.md").write_text("# Spec\n\nFR-001 changed after the analysis.\n", encoding="utf-8")

        stale = _next_json(repo, slug, "--result", "success")

        assert stale["action"] == "analyze"
        assert stale["error_code"] == "ANALYSIS_REPORT_STALE"
        assert stale["guard_failures"] == [_STALE_SPEC]
        assert stale["guard_failure_paths"] == {"spec.md": f"kitty-specs/{slug}/spec.md"}

    def test_walked_run_reissues_analyze_until_recorded_then_advances(self, tmp_path: Path) -> None:
        repo, feature_dir, slug = _cli_project(tmp_path)
        advance_to_step(repo, slug, "software-dev", "analyze")

        refused = _next_json(repo, slug, "--result", "success")
        assert refused["action"] == "analyze"
        assert refused["error_code"] == "ANALYSIS_REPORT_MISSING"

        _record_analysis(feature_dir, repo)
        advanced = _next_json(repo, slug, "--result", "success")

        assert advanced["kind"] == "step", advanced
        assert (advanced["action"], advanced["wp_id"]) == ("implement", "WP01")


class TestWrapperInjection:
    """B4: the shared ``next_cmd.decide_next`` wrapper injects the check; callers go through it."""

    def test_wrapper_passes_a_currency_callable_to_the_runtime(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from specify_cli.cli.commands import next_cmd

        seen: dict[str, Any] = {}
        monkeypatch.setattr("runtime.next.decision.decide_next", lambda *a, **k: seen.update(k))

        next_cmd.decide_next("codex", "042-x", "success", tmp_path)

        assert callable(seen["analysis_currency"])

    def test_the_injected_check_reports_missing_stale_and_current(self, tmp_path: Path) -> None:
        from specify_cli.cli.commands import next_cmd

        repo, feature_dir, slug = _cli_project(tmp_path)
        check = next_cmd.analysis_currency_for(slug, repo)

        assert check() == AnalysisVerdict("missing")
        _record_analysis(feature_dir, repo)
        assert check() == AnalysisVerdict("current")
        (feature_dir / "plan.md").write_text("# Plan\n\nchanged\n", encoding="utf-8")
        assert check() == AnalysisVerdict("stale", ("plan.md",))

    def test_a_stale_report_without_a_named_input_carries_its_reason(self) -> None:
        from specify_cli.analysis_report import AnalysisFreshness
        from specify_cli.cli.commands import next_cmd

        freshness = AnalysisFreshness(
            ok=False, path=Path("analysis-report.md"), stale=True, missing=False, reason="invalid_analysis_report_artifact_type", mismatches={}
        )

        assert next_cmd._analysis_verdict(freshness) == AnalysisVerdict("stale", ("invalid_analysis_report_artifact_type",))

    def test_orchestrator_answer_decision_injects_the_check(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """B4: ``answer-decision`` advances the run through the same wrapper, so it cannot skip the check."""
        from runtime.next import decision as runtime_decision
        from tests.specify_cli.orchestrator_api import test_answer_decision as scenario

        mission_slug, mission_type, agent = "wp07-audit", "wp07-audit-mission", "wp07-agent"
        repo = scenario._scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP07AUDITULID000000001")
        scenario._write_audit_gate_mission(repo, mission_type)
        assert scenario._next(repo, agent, mission_slug)["kind"] == "decision_required"
        scenario._set_mission_owner_id(repo, mission_slug, agent)
        seen: dict[str, Any] = {}
        real = runtime_decision.decide_next

        def _spy(*args: Any, **kwargs: Any) -> Decision:
            seen.update(kwargs)
            return real(*args, **kwargs)

        monkeypatch.setattr("runtime.next.decision.decide_next", _spy)

        outcome = scenario._run_answer_decision(
            repo,
            ["--mission", mission_slug, "--agent", agent, "--result", "success", "--answer", "approve", "--policy", scenario._POLICY],
        )

        assert scenario._envelope(outcome)["success"] is True, outcome.output
        assert callable(seen.get("analysis_currency"))
