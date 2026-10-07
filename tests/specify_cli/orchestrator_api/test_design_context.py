"""Governed authoring context and interview authority acceptance."""

from __future__ import annotations

import importlib
import contextlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner
from tests._factories import provision_test_charter
from tests.specify_cli.orchestrator_api.test_specify_plan_tasks_verbs import _POLICY, _SUBSTANTIVE_SPEC, _init_repo, _specify

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    provision_test_charter(tmp_path)
    mission = tmp_path / "kitty-specs" / "example"
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(json.dumps({"mission_id": "01KTEST_MISSION_ID_000001", "mission_slug": "example", "mission_type": "software-dev"}))
    return tmp_path


def context_module():
    return importlib.import_module("specify_cli.design.context")


def test_context_before_creation_discovers_activated_types_and_bounded_templates(project: Path) -> None:
    context = context_module().build_design_context(project, None, "specify", "software-dev")
    assert "software-dev" in context["mission_types"]
    assert context["templates"]["spec"]["content"].startswith("#")
    assert context["questions"][0]["question_id"] == "problem_statement"
    assert len(context["context_sha256"]) == 64
    assert context["limits"]["artifact_bytes"] == 262144


def test_digest_stable_and_template_change_invalidates_context(project: Path) -> None:
    module = context_module()
    before = module.planning_context_digest(project, "example", "specify")
    assert before == module.planning_context_digest(project, "example", "specify")
    bundle = module.resolve_mission_type_context(project, feature_dir=project / "kitty-specs" / "example")
    selected = module.resolve_configured_template("spec", project, bundle)
    with (
        patch.object(module, "resolve_configured_template", return_value=selected),
        patch.object(module, "_read_template", return_value="changed semantic template"),
    ):
        assert before != module.planning_context_digest(project, "example", "specify")


@pytest.mark.parametrize("stage", ["unknown", "../plan", ""])
def test_undeclared_stage_refuses(project: Path, stage: str) -> None:
    with pytest.raises(context_module().DesignContextError) as caught:
        context_module().build_design_context(project, "example", stage)
    assert caught.value.code == "DESIGN_CONTEXT_FAILED"


def test_absent_interviews_fail_instead_of_vacuous_completion(project: Path) -> None:
    with pytest.raises(context_module().DesignContextError) as caught:
        context_module().resolved_interview_answers(project, "example", "specify")
    assert caught.value.code == "DESIGN_INTERVIEW_INCOMPLETE"
    assert "problem_statement" in caught.value.details["incomplete"]


def test_record_answers_reuses_canonical_decisions_and_exact_retry(project: Path) -> None:
    module = context_module()
    answers = {"problem_statement": "Create governed clients", "success_criteria": "API only journey", "scope_boundaries": "No new execution engine"}
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1), patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        first = module.record_interview_answers(project, "example", "specify", answers, "alice")
        second = module.record_interview_answers(project, "example", "specify", answers, "alice")
    assert first["decision_ids"] == second["decision_ids"]
    assert module.resolved_interview_answers(project, "example", "specify") == answers
    from specify_cli.decisions.store import load_index

    index = load_index(project / "kitty-specs" / "example")
    assert len(index.entries) == 3
    assert index.entries[0].step_id == "specify.problem_statement"


@pytest.mark.parametrize("answers", [{"unknown": "x"}, {"problem_statement": " "}, {"problem_statement": 42}, []])
def test_invalid_whole_answer_batch_has_no_effect(project: Path, answers: object) -> None:
    with pytest.raises(context_module().DesignContextError) as caught:
        context_module().record_interview_answers(project, "example", "specify", answers, "alice")
    assert caught.value.code == "DESIGN_INTERVIEW_INVALID"
    assert not (project / "kitty-specs" / "example" / "decisions").exists()


@pytest.mark.parametrize("terminal", ["defer_decision", "cancel_decision"])
def test_terminal_unanswered_decision_is_incomplete(project: Path, terminal: str) -> None:
    from specify_cli.decisions import service
    from specify_cli.decisions.models import OriginFlow

    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1), patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        opened = service.open_decision(
            project,
            "example",
            origin_flow=OriginFlow.SPECIFY,
            input_key="problem_statement",
            step_id="specify.problem_statement",
            question="Problem?",
            options=(),
            actor="alice",
        )
        getattr(service, terminal)(project, "example", opened.decision_id, actor="alice", rationale="Later")
    with pytest.raises(context_module().DesignContextError):
        context_module().resolved_interview_answers(project, "example", "specify")


def test_context_discovery_does_not_change_project_bytes(project: Path) -> None:
    before = {str(path.relative_to(project)): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    context_module().build_design_context(project, "example", "plan")
    after = {str(path.relative_to(project)): path.read_bytes() for path in project.rglob("*") if path.is_file()}
    assert after == before


def test_tasks_interview_requires_specification_and_plan(project: Path) -> None:
    module = context_module()
    with pytest.raises(module.DesignContextError) as caught:
        module.resolved_interview_answers(project, "example", "tasks")
    assert "specify.problem_statement" in caught.value.details["incomplete"]
    assert "plan.approach" in caught.value.details["incomplete"]


def test_exact_byte_content_digest_and_bound(project: Path) -> None:
    module = context_module()
    path = project / "input.md"
    path.write_bytes(b"body\r\n")
    first = module.bounded_content(path, 6)
    path.write_bytes(b"body\n")
    assert first["sha256"] != module.bounded_content(path, 6)["sha256"]
    with pytest.raises(module.DesignContextError):
        module.bounded_content(path, 4)


def test_corrupt_interview_ledger_is_typed_failure(project: Path) -> None:
    module = context_module()
    ledger = project / "kitty-specs" / "example" / "decisions"
    ledger.mkdir()
    (ledger / "index.json").write_bytes(b"broken")
    with pytest.raises(module.DesignContextError) as caught:
        module.resolved_interview_answers(project, "example", "specify")
    assert caught.value.code == "DESIGN_INTERVIEW_FAILED"


def test_conflicting_answer_stays_native_terminal_conflict(project: Path) -> None:
    module = context_module()
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1), patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        module.record_interview_answers(project, "example", "specify", {"problem_statement": "First"}, "alice")
        with pytest.raises(module.DesignContextError) as caught:
            module.record_interview_answers(project, "example", "specify", {"problem_statement": "Conflicting"}, "alice")
    assert caught.value.details["reason"] == "DECISION_TERMINAL_CONFLICT"


def test_existing_mission_type_cannot_be_overridden(project: Path) -> None:
    module = context_module()
    with pytest.raises(module.DesignContextError) as caught:
        module.build_design_context(project, "example", "specify", "research")
    assert caught.value.code == "DESIGN_CONTEXT_FAILED"


def test_final_context_bound_includes_interview_content(project: Path) -> None:
    module = context_module()
    with patch.object(module, "interview_status", return_value={"answers": {"huge": "x" * 1048576}}), pytest.raises(module.DesignContextError) as caught:
        module.build_design_context(project, "example", "tasks")
    assert caught.value.code == "DESIGN_CONTEXT_FAILED"


def test_later_native_conflict_reports_already_applied_answers(project: Path) -> None:
    module = context_module()
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1), patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        module.record_interview_answers(project, "example", "specify", {"success_criteria": "Original"}, "alice")
        with pytest.raises(module.DesignContextError) as caught:
            module.record_interview_answers(
                project, "example", "specify", {"problem_statement": "Accepted first", "success_criteria": "Conflicting second"}, "alice"
            )
    assert "problem_statement" in caught.value.details["decision_ids"]
    assert caught.value.details["effect_state"] == "reconciliation_required"


def test_lifecycle_and_application_share_one_question_set() -> None:
    from specify_cli.cli.commands import lifecycle
    from specify_cli.missions.plan import interview_questions

    assert lifecycle.SPECIFY_WIDEN_QUESTIONS is interview_questions.SPECIFY_WIDEN_QUESTIONS
    assert lifecycle.PLAN_WIDEN_QUESTIONS is interview_questions.PLAN_WIDEN_QUESTIONS


def _invoke_boundary(repo: Path, args: list[str]):
    from specify_cli.orchestrator_api.design_context import design_context, interview_record
    from specify_cli.orchestrator_api.design_authoring import artifact_read, artifact_submit
    from specify_cli.orchestrator_api.runtime_next import runtime_next

    app = typer.Typer()
    for name, callback in (
        ("design-context", design_context),
        ("interview-record", interview_record),
        ("artifact-read", artifact_read),
        ("artifact-submit", artifact_submit),
        ("next", runtime_next),
    ):
        app.command(name)(callback)
    with contextlib.chdir(repo):
        result = CliRunner().invoke(app, args, catch_exceptions=False)
    return result, json.loads(result.stdout)


def test_context_and_interview_command_boundary_preserves_native_ids(project: Path) -> None:
    result, before = _invoke_boundary(project, ["design-context", "--mission-type", "software-dev"])
    assert result.exit_code == 0
    assert before["data"]["mission_slug"] is None
    assert "content" in before["data"]["templates"]["spec"]
    answers = {question["id"]: f"Concrete {question['id']}" for question in before["data"]["questions"]}
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1), patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        result, recorded = _invoke_boundary(
            project,
            [
                "interview-record",
                "--mission",
                "example",
                "--stage",
                "specify",
                "--answers",
                json.dumps(answers),
                "--actor",
                "alice",
                "--policy",
                _POLICY,
            ],
        )
    assert result.exit_code == 0
    result, after = _invoke_boundary(project, ["design-context", "--mission", "example", "--stage", "specify"])
    assert result.exit_code == 0
    assert after["data"]["interview"]["complete"] is True
    assert after["data"]["interview"]["decision_ids"] == recorded["data"]["decision_ids"]


@pytest.mark.parametrize("failure", ["missing_policy", "malformed_json", "oversize_json", "invalid_answers", "wrong_mission_type", "invalid_stage"])
def test_command_refusals_are_typed_and_have_no_decision_effect(project: Path, failure: str) -> None:
    args = ["interview-record", "--mission", "example", "--stage", "specify", "--answers", '{"problem_statement":"Concrete"}', "--actor", "alice"]
    code = "DESIGN_INTERVIEW_INVALID"
    if failure == "missing_policy":
        code = "POLICY_METADATA_REQUIRED"
    else:
        args += ["--policy", _POLICY]
    if failure == "malformed_json":
        args[args.index("--answers") + 1] = "{"
    elif failure == "oversize_json":
        args[args.index("--answers") + 1] = "x" * 262145
    elif failure == "invalid_answers":
        args[args.index("--answers") + 1] = '{"unrecognized":"answer"}'
    elif failure in {"wrong_mission_type", "invalid_stage"}:
        args = ["design-context", "--mission", "example", *(["--mission-type", "research"] if failure == "wrong_mission_type" else ["--stage", "unknown"])]
        code = "DESIGN_CONTEXT_FAILED"
    result, response = _invoke_boundary(project, args)
    assert result.exit_code == 1
    assert response["error_code"] == code
    assert not (project / "kitty-specs" / "example" / "decisions").exists()


def test_real_native_initial_issuance_and_completion_require_api_provenance(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    slug = _specify(repo, "native-context-proof")["data"]["mission_slug"]
    result, initial = _invoke_boundary(repo, ["next", "--mission", slug])
    assert result.exit_code == 0 and initial["data"]["mission_state"] == "not_started"
    result, context = _invoke_boundary(repo, ["design-context", "--mission", slug])
    assert result.exit_code == 0
    answers = {question["id"]: f"Concrete {question['id']}" for question in context["data"]["questions"]}
    result, recorded = _invoke_boundary(
        repo,
        [
            "interview-record",
            "--mission",
            slug,
            "--stage",
            "specify",
            "--answers",
            json.dumps(answers),
            "--actor",
            "alice",
            "--policy",
            _POLICY,
        ],
    )
    assert result.exit_code == 0, recorded

    def submit(kind: str, content: str) -> dict:
        result, read = _invoke_boundary(repo, ["artifact-read", "--mission", slug, "--kind", kind])
        assert result.exit_code == 0
        request = {
            "artifacts": [{"kind": kind, "content": content, "expected_sha256": read["data"]["sha256"]}],
            "context_sha256": context["data"]["context_sha256"],
            "parents": {},
        }
        result, accepted = _invoke_boundary(
            repo, ["artifact-submit", "--mission", slug, "--request-json", json.dumps(request), "--actor", "alice", "--policy", _POLICY]
        )
        assert result.exit_code == 0, accepted
        return accepted

    submit("research", "# Evidence\n\nThe external client requires native completion to validate accepted design content.\n")
    advance = ["next", "--mission", slug, "--agent", "codex", "--result", "success", "--policy", _POLICY]
    result, issued = _invoke_boundary(repo, advance)
    assert result.exit_code == 0 and issued["data"]["step_id"] == "discovery", issued
    assert "content" in issued["data"]["prompt"]
    result, specify = _invoke_boundary(repo, advance)
    assert result.exit_code == 0 and specify["data"]["step_id"] == "specify", specify
    result, rejected = _invoke_boundary(repo, advance)
    assert result.exit_code == 1 and rejected["error_code"] == "RUNTIME_NEXT_FAILED", rejected
    result, unchanged = _invoke_boundary(repo, ["next", "--mission", slug])
    assert result.exit_code == 0 and unchanged["data"]["step_id"] == "specify", unchanged
    submit("specification", _SUBSTANTIVE_SPEC)
    result, completed = _invoke_boundary(repo, advance)
    assert result.exit_code == 0 and completed["data"]["step_id"] == "plan", completed
