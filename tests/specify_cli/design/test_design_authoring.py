"""API-only authoring acceptance; the first commit runs red on the existing API."""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api.commands import app
from specify_cli.orchestrator_api.design_authoring import artifact_read, artifact_submit, design_validate
from specify_cli.design import authoring, receipts, validation
from specify_cli.design.context import build_design_context, record_interview_answers
from specify_cli.design.errors import DesignError
from mission_runtime import MissionArtifactKind
from specify_cli.coordination.commit_router import CommitRouterResult
from tests.specify_cli.orchestrator_api.test_specify_plan_tasks_verbs import _POLICY, _SUBSTANTIVE_SPEC, _git, _init_repo, _specify
from tests.specify_cli.missions.test_substantive_gate_formats import _BULLETED_REAL

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# The registry is another package's scope. This harness binds the real adapter
# functions until that package integrates them into the production app.
for name, callback in (("artifact-read", artifact_read), ("artifact-submit", artifact_submit), ("design-validate", design_validate)):
    if name not in {command.name for command in app.registered_commands}:
        app.command(name)(callback)


@pytest.fixture
def mission(tmp_path: Path) -> tuple[Path, str]:
    repo = _init_repo(tmp_path)
    slug = _specify(repo, "authoring")["data"]["mission_slug"]
    return repo, slug


def _answers(repo: Path, slug: str, stage: str) -> str:
    context = build_design_context(repo, slug, stage)
    if stage != "tasks":
        answers = {question["id"]: f"Concrete answer for {question['id']}" for question in context["questions"]}
        record_interview_answers(repo, slug, stage, answers, "author")
    return str(context["context_sha256"])


def _request(repo: Path, slug: str, kind: str, content: str, *, parents: dict[str, str] | None = None, artifact_id: str | None = None) -> str:
    stage = authoring.artifact_action(kind)
    return json.dumps(
        {
            "artifacts": [
                {"kind": kind, "artifact_id": artifact_id, "content": content, "expected_sha256": authoring.read_artifact(repo, slug, kind, artifact_id)["sha256"]}
            ],
            "parents": parents or {},
            "context_sha256": _answers(repo, slug, stage),
        }
    )


def _submit_spec(repo: Path, slug: str) -> str:
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "specification", _SUBSTANTIVE_SPEC), "author")
    return str(authoring.read_artifact(repo, slug, "specification")["sha256"])


def _invoke(repo: Path, args: list[str], *, stdin: str | bytes | None = None) -> dict[str, Any]:
    with contextlib.chdir(repo):
        result = CliRunner().invoke(app, args, input=stdin, catch_exceptions=False)
    return json.loads(result.output)


def test_external_client_can_read_specification_without_repository_access(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    mission = _specify(repo, "authoring-read")["data"]["mission_slug"]
    with contextlib.chdir(repo):
        result = CliRunner().invoke(app, ["artifact-read", "--mission", mission, "--kind", "specification"])
    envelope: dict[str, Any] = json.loads(result.output)
    assert envelope["success"] is True, envelope
    assert envelope["data"]["kind"] == "specification"
    assert "#" in envelope["data"]["content"]
    assert len(envelope["data"]["sha256"]) == 64


def test_absent_outline_has_explicit_creation_revision(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    data = _invoke(repo, ["artifact-read", "--mission", slug, "--kind", "outline"])["data"]
    assert data["sha256"] == "absent"
    assert data["content"] is None


def test_submit_commits_content_and_validate_is_read_only(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    request = _request(repo, slug, "specification", _SUBSTANTIVE_SPEC)
    envelope = _invoke(repo, ["artifact-submit", "--mission", slug, "--request-json", request, "--actor", "author", "--policy", _POLICY])
    assert envelope["success"] is True, envelope
    assert envelope["data"]["commit_status"] == "committed"
    assert receipts.api_authoring_enabled(repo, slug)
    accepted = receipts.read_receipts(repo, slug)
    assert accepted is not None and "specification" in accepted.artifacts
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    assert validation.validate_stage(repo, slug, "specify")["prerequisites_satisfied"] is True
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == before


@pytest.mark.parametrize("failure", ["target", "context", "unknown_field", "too_big"])
def test_invalid_submission_has_no_content_or_commit_effect(mission: tuple[Path, str], failure: str) -> None:
    repo, slug = mission
    request = json.loads(_request(repo, slug, "specification", _SUBSTANTIVE_SPEC))
    expected = {
        "target": "DESIGN_REVISION_CONFLICT",
        "context": "DESIGN_CONTEXT_STALE",
        "unknown_field": "DESIGN_REQUEST_INVALID",
        "too_big": "DESIGN_BOUNDS_EXCEEDED",
    }
    if failure == "target":
        request["artifacts"][0]["expected_sha256"] = "0" * 64
    elif failure == "context":
        request["context_sha256"] = "0" * 64
    elif failure == "unknown_field":
        request["artifacts"][0]["path"] = "meta.json"
    else:
        request["artifacts"][0]["content"] = "x" * (256 * 1024 + 1)
    before = authoring.read_artifact(repo, slug, "specification")
    head = _git(repo, "rev-parse", "HEAD").stdout
    with pytest.raises(DesignError) as caught:
        authoring.submit_artifacts(repo, slug, json.dumps(request), "author")
    assert caught.value.code == expected[failure]
    assert authoring.read_artifact(repo, slug, "specification") == before
    assert _git(repo, "rev-parse", "HEAD").stdout == head
    assert not receipts.api_authoring_enabled(repo, slug)


@pytest.mark.parametrize("kind", ["metadata", "tasks.md", "status", "decision", "../specification"])
def test_unregistered_authority_is_not_an_artifact(mission: tuple[Path, str], kind: str) -> None:
    repo, slug = mission
    with pytest.raises(DesignError) as caught:
        authoring.read_artifact(repo, slug, kind)
    assert caught.value.code == "DESIGN_ARTIFACT_UNSUPPORTED"


def test_plan_accepted_parent_receipt_detects_later_spec_revision(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    spec_sha = _submit_spec(repo, slug)
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "plan", _BULLETED_REAL, parents={"specification": spec_sha}), "author")
    validation.validate_stage(repo, slug, "plan")
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "specification", _SUBSTANTIVE_SPEC + "\nA changed requirement interpretation.\n"), "author")
    validation.validate_stage(repo, slug, "specify")
    with pytest.raises(DesignError) as caught:
        validation.validate_stage(repo, slug, "plan")
    assert caught.value.code == "DESIGN_PARENT_STALE"


def test_commit_failure_is_materialized_but_never_accepted(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    request = _request(repo, slug, "specification", _SUBSTANTIVE_SPEC)
    with (
        patch.object(authoring, "commit_for_mission", return_value=CommitRouterResult(status="error", placement_ref="primary")),
        pytest.raises(DesignError) as caught,
    ):
        authoring.submit_artifacts(repo, slug, request, "author")
    assert caught.value.code == "DESIGN_COMMIT_FAILED"
    assert caught.value.details["effect_state"] == "reconciliation_required"
    assert authoring.read_artifact(repo, slug, "specification")["content"] == _SUBSTANTIVE_SPEC
    accepted = receipts.read_receipts(repo, slug)
    assert accepted is not None and not accepted.artifacts
    with pytest.raises(DesignError):
        validation.validate_stage(repo, slug, "specify")


def test_missing_receipt_does_not_fall_back_to_manual_compatibility(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    _submit_spec(repo, slug)
    marker, receipt_file = receipts._paths(repo, slug)
    receipt_file.unlink()
    assert marker.exists() and receipts.api_authoring_enabled(repo, slug)
    with pytest.raises(DesignError) as caught:
        validation.validate_stage(repo, slug, "specify")
    assert caught.value.code == "DESIGN_RECEIPT_UNREADABLE"


def test_existing_symlink_target_is_refused(mission: tuple[Path, str], tmp_path: Path) -> None:
    repo, slug = mission
    target = authoring.artifact_path(repo, slug, "specification")
    target.unlink()
    outside = tmp_path / "outside"
    outside.write_text("Private content")
    target.symlink_to(outside)
    with pytest.raises(DesignError) as caught:
        authoring.read_artifact(repo, slug, "specification")
    assert caught.value.code == "DESIGN_PATH_REFUSED"


_OUTLINE = """work_packages:
  - id: WP01
    title: Change the readme
    dependencies: []
    owned_files: [README.md]
    requirement_refs: [FR-001]
    subtasks: []
    prompt_file: tasks/WP01.md
"""
_PROMPT = """---
work_package_id: WP01
title: Change the readme
dependencies: []
owned_files: [README.md]
requirement_refs: [FR-001]
subtasks: []
authoritative_surface: README.md
execution_mode: code_change
---
# WP01
Implement FR-001 by updating the readme.

## Activity Log
"""


def _planning_parents(repo: Path, slug: str) -> dict[str, str]:
    spec = _submit_spec(repo, slug)
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "plan", _BULLETED_REAL, parents={"specification": spec}), "author")
    return {"specification": spec, "plan": str(authoring.read_artifact(repo, slug, "plan")["sha256"])}


def _receipt_digests(repo: Path, slug: str) -> dict[str, str]:
    stored = receipts.read_receipts(repo, slug)
    assert stored is not None
    return {key: item.sha256 for key, item in stored.artifacts.items()}


def test_outline_package_native_finalization_and_frozen_content(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    parents = _planning_parents(repo, slug)
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "outline", _OUTLINE, parents=parents), "author")
    parents["outline"] = str(authoring.read_artifact(repo, slug, "outline")["sha256"])
    absent = authoring.read_artifact(repo, slug, "work_package", "WP01")
    assert absent["sha256"] == "absent" and absent["content"] is None
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "work_package", _PROMPT, parents=parents, artifact_id="WP01"), "author")
    validation.validate_stage(repo, slug, "tasks")
    digest = _receipt_digests(repo, slug)
    prompt = authoring.artifact_path(repo, slug, "work_package", "WP01")
    original = prompt.read_text()

    def failed_delegate(**_: Any) -> None:
        prompt.write_text(original + "\nPartial native write.\n")
        print(json.dumps({"result": "error", "error": "finalize failed"}))

    with patch("specify_cli.cli.commands.agent.mission.finalize_tasks", failed_delegate):
        _invoke(repo, ["tasks", "--mission", slug, "--policy", _POLICY])
    assert _receipt_digests(repo, slug) == digest
    prompt.write_text(original)
    outcome = _invoke(repo, ["tasks", "--mission", slug, "--policy", _POLICY])
    assert outcome["success"] is True, outcome
    validation.validate_stage(repo, slug, "tasks")
    request = _request(repo, slug, "specification", _SUBSTANTIVE_SPEC + "\nA revised draft.")
    with pytest.raises(DesignError) as caught:
        authoring.submit_artifacts(repo, slug, request, "author")
    assert caught.value.code == "DESIGN_FINALIZED"
    scaffold = _invoke(repo, ["plan", "--mission", slug, "--policy", _POLICY])
    assert scaffold["error_code"] == "DESIGN_FINALIZED"


def test_batch_spanning_artifact_placements_is_refused_before_effects(mission: tuple[Path, str], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, slug = mission
    parents = _planning_parents(repo, slug)
    request = json.loads(_request(repo, slug, "outline", _OUTLINE, parents=parents))
    request["artifacts"].append({"kind": "work_package", "artifact_id": "WP01", "content": _PROMPT, "expected_sha256": "absent"})
    real = authoring.placement_seam(repo, slug)

    class Split:
        def read_dir(self, kind: MissionArtifactKind) -> Path:
            base = real.read_dir(kind)
            return base / "elsewhere" if kind is authoring._KINDS["work_package"] else base

    monkeypatch.setattr(authoring, "placement_seam", lambda *_: Split())
    with pytest.raises(DesignError) as caught:
        authoring.submit_artifacts(repo, slug, json.dumps(request), "author")
    assert caught.value.code == "DESIGN_REQUEST_INVALID"
    assert authoring.read_artifact(repo, slug, "outline")["sha256"] == "absent"


@pytest.mark.parametrize("failure", ["cycle", "unknown_requirement", "outside_prompt", "duplicate"])
def test_outline_invalid_graph_has_no_content_effect(mission: tuple[Path, str], failure: str) -> None:
    repo, slug = mission
    parents = _planning_parents(repo, slug)
    content = _OUTLINE
    if failure == "cycle":
        content = content.replace("dependencies: []", "dependencies: [WP01]")
    elif failure == "unknown_requirement":
        content = content.replace("FR-001", "FR-999")
    elif failure == "outside_prompt":
        content = content.replace("tasks/WP01.md", "../WP01.md")
    else:
        content += _OUTLINE.removeprefix("work_packages:\n")
    with pytest.raises(DesignError):
        authoring.submit_artifacts(repo, slug, _request(repo, slug, "outline", content, parents=parents), "author")
    assert authoring.read_artifact(repo, slug, "outline")["sha256"] == "absent"


def test_research_is_independent_early_discovery_evidence(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "research", "# Research\nCanonical services support bounded clients."), "author")
    _submit_spec(repo, slug)
    validation.validate_stage(repo, slug, "specify")


def test_finalized_snapshot_with_truncated_log_refuses_all_design_writes(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    parents = _planning_parents(repo, slug)
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "outline", _OUTLINE, parents=parents), "author")
    parents["outline"] = str(authoring.read_artifact(repo, slug, "outline")["sha256"])
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "work_package", _PROMPT, parents=parents, artifact_id="WP01"), "author")
    assert _invoke(repo, ["tasks", "--mission", slug, "--policy", _POLICY])["success"] is True
    status_dir = authoring.placement_seam(repo, slug).read_dir(authoring.MissionArtifactKind.STATUS_STATE)
    (status_dir / "status.events.jsonl").write_text("")
    before = authoring.read_artifact(repo, slug, "specification")
    request = _request(repo, slug, "specification", _SUBSTANTIVE_SPEC + "\nRevised after finalization.")
    outcome = _invoke(repo, ["artifact-submit", "--mission", slug, "--request-json", request, "--actor", "author", "--policy", _POLICY])
    assert outcome["success"] is False, outcome
    assert outcome["error_code"] == "DESIGN_STATUS_EVENT_LOG_UNREADABLE"
    assert authoring.read_artifact(repo, slug, "specification") == before
    setup = _invoke(repo, ["plan", "--mission", slug, "--policy", _POLICY])
    assert setup["success"] is False and setup["error_code"] == "DESIGN_STATUS_EVENT_LOG_UNREADABLE"


def test_corrupt_manifest_read_returns_typed_refusal(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    outline = authoring.artifact_path(repo, slug, "outline")
    outline.write_text("work_packages: broken-schema\n")
    outcome = _invoke(repo, ["artifact-read", "--mission", slug, "--kind", "work_package", "--artifact-id", "WP01"])
    assert outcome["success"] is False
    assert outcome["error_code"] == "DESIGN_PREREQUISITES_FAILED"
    assert "ValidationError" not in json.dumps(outcome)
    assert str(repo) not in json.dumps(outcome)


@pytest.mark.parametrize(
    "kind,artifact_id,code",
    [
        ("contract", None, "DESIGN_REQUEST_INVALID"),
        ("contract", "../private.md", "DESIGN_PATH_REFUSED"),
        ("outline", "caller-selected", "DESIGN_REQUEST_INVALID"),
        ("specification", "caller-selected", "DESIGN_REQUEST_INVALID"),
        ("work_package", "WP01", "DESIGN_PREREQUISITES_FAILED"),
    ],
)
def test_artifact_identifiers_cannot_select_arbitrary_destinations(mission: tuple[Path, str], kind: str, artifact_id: str | None, code: str) -> None:
    repo, slug = mission
    with pytest.raises(DesignError) as caught:
        authoring.read_artifact(repo, slug, kind, artifact_id)
    assert caught.value.code == code


def test_contract_submission_uses_registered_contract_home(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    spec = _submit_spec(repo, slug)
    request = _request(repo, slug, "contract", "# Protocol\nExchange structured messages.", parents={"specification": spec}, artifact_id="protocol.md")
    authoring.submit_artifacts(repo, slug, request, "author")
    assert authoring.read_artifact(repo, slug, "contract", "protocol.md")["content"] == "# Protocol\nExchange structured messages."


@pytest.mark.parametrize("failure", ["identity", "definition", "runtime_authority", "malformed_frontmatter", "empty"])
def test_package_prompt_refusals_precede_materialization(mission: tuple[Path, str], failure: str) -> None:
    repo, slug = mission
    parents = _planning_parents(repo, slug)
    authoring.submit_artifacts(repo, slug, _request(repo, slug, "outline", _OUTLINE, parents=parents), "author")
    parents["outline"] = str(authoring.read_artifact(repo, slug, "outline")["sha256"])
    variants = {
        "identity": _PROMPT.replace("work_package_id: WP01", "work_package_id: WP02"),
        "definition": _PROMPT.replace("owned_files: [README.md]", "owned_files: [other.md]"),
        "runtime_authority": _PROMPT.replace("title:", "lane: done\ntitle:"),
        "malformed_frontmatter": "---\n: [\n---\nBody",
        "empty": " ",
    }
    request = _request(repo, slug, "work_package", variants[failure], parents=parents, artifact_id="WP01")
    with pytest.raises(DesignError) as caught:
        authoring.submit_artifacts(repo, slug, request, "author")
    assert caught.value.code in {"DESIGN_PREREQUISITES_FAILED", "DESIGN_REQUEST_INVALID"}
    assert authoring.read_artifact(repo, slug, "work_package", "WP01")["sha256"] == "absent"


def test_dirty_parent_cannot_be_accepted_using_its_current_digest(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    _submit_spec(repo, slug)
    path = authoring.artifact_path(repo, slug, "specification")
    path.write_text(_SUBSTANTIVE_SPEC + "\nUncommitted change.\n")
    spec = str(authoring.read_artifact(repo, slug, "specification")["sha256"])
    request = _request(repo, slug, "plan", _BULLETED_REAL, parents={"specification": spec})
    with pytest.raises(DesignError) as caught:
        authoring.submit_artifacts(repo, slug, request, "author")
    assert caught.value.code == "DESIGN_PREREQUISITES_FAILED"
    assert authoring.read_artifact(repo, slug, "plan")["sha256"] == "absent"


def test_adapter_validation_policy_and_invalid_utf8_refusals(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    _submit_spec(repo, slug)
    assert _invoke(repo, ["design-validate", "--mission", slug, "--stage", "specify"])["success"] is True
    stage = _invoke(repo, ["design-validate", "--mission", slug, "--stage", "undeclared"])
    assert stage["error_code"] == "DESIGN_REQUEST_INVALID"
    policy = _invoke(repo, ["artifact-submit", "--mission", slug, "--request-json", "{}", "--actor", "author"])
    assert policy["error_code"] == "POLICY_METADATA_REQUIRED"
    authoring.artifact_path(repo, slug, "specification").write_bytes(b"\xff")
    invalid = _invoke(repo, ["artifact-read", "--mission", slug, "--kind", "specification"])
    assert invalid["error_code"] == "DESIGN_IO_FAILED"
    assert str(repo) not in json.dumps(invalid)


def test_committed_content_with_receipt_io_failure_blocks_completion(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    _submit_spec(repo, slug)
    request = _request(repo, slug, "specification", _SUBSTANTIVE_SPEC + "\nNew accepted intent.\n")
    with patch.object(receipts, "atomic_write", side_effect=OSError("disk failure")), pytest.raises(DesignError) as caught:
        authoring.submit_artifacts(repo, slug, request, "author")
    assert caught.value.code == "DESIGN_RECEIPT_UNREADABLE"
    assert caught.value.details["effect_state"] == "reconciliation_required"
    assert receipts.api_authoring_enabled(repo, slug)
    with pytest.raises(DesignError) as stale:
        validation.validate_stage(repo, slug, "specify")
    assert stale.value.code == "DESIGN_PARENT_STALE"


def test_stdin_transports_content_above_os_argument_limit(mission: tuple[Path, str]) -> None:
    repo, slug = mission
    body = "# Research\n" + "Independent design evidence. " * 5500
    assert 128 * 1024 < len(body.encode("utf-8")) < 256 * 1024
    request = _request(repo, slug, "research", body)
    outcome = _invoke(repo, ["artifact-submit", "--mission", slug, "--request-json", "-", "--actor", "author", "--policy", _POLICY], stdin=request)
    assert outcome["success"] is True, outcome
    assert authoring.read_artifact(repo, slug, "research")["content"] == body


@pytest.mark.parametrize("failure", ["oversize", "invalid_utf8"])
def test_stdin_refuses_invalid_bytes_before_effects(mission: tuple[Path, str], failure: str) -> None:
    from specify_cli.design.models import MAX_REQUEST_BYTES

    repo, slug = mission
    content = b"x" * (MAX_REQUEST_BYTES + 1) if failure == "oversize" else b"\xff"
    before = authoring.read_artifact(repo, slug, "specification")
    outcome = _invoke(repo, ["artifact-submit", "--mission", slug, "--request-json", "-", "--actor", "author", "--policy", _POLICY], stdin=content)
    assert outcome["success"] is False
    assert outcome["error_code"] == ("DESIGN_BOUNDS_EXCEEDED" if failure == "oversize" else "DESIGN_REQUEST_INVALID")
    assert authoring.read_artifact(repo, slug, "specification") == before
    assert not receipts.api_authoring_enabled(repo, slug)


@pytest.mark.parametrize("glyphs,accepted", [(128, True), (129, False)])
def test_actor_budget_measures_utf8_bytes(mission: tuple[Path, str], glyphs: int, accepted: bool) -> None:
    repo, slug = mission
    request = _request(repo, slug, "specification", _SUBSTANTIVE_SPEC)
    outcome = _invoke(repo, ["artifact-submit", "--mission", slug, "--request-json", request, "--actor", "é" * glyphs, "--policy", _POLICY])
    assert outcome["success"] is accepted, outcome
    if not accepted:
        assert outcome["error_code"] == "DESIGN_REQUEST_INVALID"
        assert not receipts.api_authoring_enabled(repo, slug)
