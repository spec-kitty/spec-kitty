"""Public-client acceptance: no file or git writes after project initialization."""

from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner
from runtime.next.run_index import feature_runs_path

from specify_cli.orchestrator_api.commands import app
from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION
from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]
runner = CliRunner()


def _content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()  # noqa: TID251 - Independent file-integrity oracle, not a charter hash.


POLICY = json.dumps(
    {
        "orchestrator_id": "planning-client",
        "orchestrator_version": "1.0",
        "agent_family": "codex",
        "approval_mode": "full_auto",
        "sandbox_mode": "workspace_write",
        "network_mode": "none",
        "dangerous_flags": [],
    }
)
SPEC = """# Specification: API planning client

## User Scenarios
An external client authors and finalizes a mission through the governed API.

## Functional Requirements
| ID | Title | Description | Priority | Status |
|----|-------|-------------|----------|--------|
| FR-001 | Complete API planning | Client reaches ready work without editing repository files. | High | Open |

## Acceptance
Given an initialized project, API submission and finalization produce one ready package.
"""
PLAN = """# Implementation Plan: API planning client

## Summary
Implement the specified README behavior with one focused work package.

## Technical Context
**Language/Version**: Markdown documentation.
**Storage**: Git using the existing canonical mission workflow.

## Architecture
One package owns README.md. No parallel state or custom tracker authority.

## Validation
Review the README content and the governed client proof against FR-001.

## Risks
Dependency, ownership and requirement validation remain with the host finalizer.
"""
OUTLINE = """work_packages:
  - id: WP01
    title: Update the README
    dependencies: []
    owned_files: [README.md]
    requirement_refs: [FR-001]
    subtasks: []
    prompt_file: tasks/WP01.md
"""
PROMPT = """---
work_package_id: WP01
title: Update the README
dependencies: []
requirement_refs: [FR-001]
subtasks: []
owned_files: [README.md]
authoritative_surface: README.md
execution_mode: code_change
---

# WP01: Update the README

## Objective
Describe the API planning client behavior required by FR-001.

## Validation
Review the README content against the requirement.

## Activity Log
"""


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for args in [("init", "-b", "client-work"), ("config", "user.email", "client@example.com"), ("config", "user.name", "API Client")]:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    (root / ".kittify").mkdir()
    (root / "README.md").write_text("Planning client fixture\n", encoding="utf-8")
    provision_test_charter(root)
    for args in [("add", "."), ("commit", "-m", "initialize client project")]:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    return root


def _call(root: Path, *args: str, success: bool = True, input_text: str | None = None) -> dict[str, Any]:
    with contextlib.chdir(root):
        result = runner.invoke(app, list(args), input=input_text, catch_exceptions=False)
    envelope = json.loads(result.stdout)
    assert envelope["success"] is success, (result.exit_code, envelope)
    assert (result.exit_code == 0) is success, envelope
    return envelope


def _context(root: Path, mission: str, stage: str) -> dict[str, Any]:
    return _call(root, "design-context", "--mission", mission, "--stage", stage)["data"]


def _interview(root: Path, mission: str, stage: str) -> None:
    context = _context(root, mission, stage)
    answers = {q["id"]: f"Bounded README planning client: {q['question']}" for q in context["questions"]}
    data = _call(
        root, "interview-record", "--mission", mission, "--stage", stage, "--answers", json.dumps(answers), "--actor", "planning-client", "--policy", POLICY
    )["data"]
    assert data["interview"]["complete"] is True


def _read(root: Path, mission: str, kind: str, artifact_id: str | None = None) -> dict[str, Any]:
    args = ["artifact-read", "--mission", mission, "--kind", kind]
    if artifact_id:
        args += ["--artifact-id", artifact_id]
    return _call(root, *args)["data"]


def _submit(root: Path, mission: str, stage: str, kind: str, content: str, parents: dict[str, str], artifact_id: str | None = None) -> dict[str, Any]:
    current = _read(root, mission, kind, artifact_id)
    artifact: dict[str, Any] = {"kind": kind, "content": content, "expected_sha256": current["sha256"]}
    if artifact_id:
        artifact["artifact_id"] = artifact_id
    request = {"artifacts": [artifact], "parents": parents, "context_sha256": _context(root, mission, stage)["context_sha256"]}
    data = _call(
        root, "artifact-submit", "--mission", mission, "--request-json", "-", "--actor", "planning-client", "--policy", POLICY, input_text=json.dumps(request)
    )["data"]
    assert data["artifacts"][0]["sha256"] == _content_sha256(content)
    observed = _read(root, mission, kind, artifact_id)
    assert observed["content"] == content
    return observed


def test_capability_profile_is_honest() -> None:
    result = runner.invoke(app, ["contract-version"], catch_exceptions=False)
    data = json.loads(result.stdout)["data"]
    profile = data["delivery_profile"]
    assert profile["semantic_contract"] == "spec-kitty.orchestrator/2"
    assert profile["full_go_conformance"] is False
    assert {"GapDB", "leases", "fences", "native_async", "watch", "durable_operation_replay"} <= set(profile["unavailable"])
    assert profile["limits"]["artifact_bytes"] == 262144


@pytest.mark.parametrize("capability", ["watch", "durable_operation_replay", "invented-capability"])
def test_unavailable_capability_is_refused_before_work(capability: str) -> None:
    result = runner.invoke(app, ["contract-version", "--require-capability", capability], catch_exceptions=False)
    envelope = json.loads(result.stdout)
    assert result.exit_code != 0
    assert envelope["success"] is False
    assert envelope["error_code"] == "UNSUPPORTED_CAPABILITY"
    assert envelope["data"]["capability"] == capability


def test_supported_capability_keeps_version_handshake() -> None:
    result = runner.invoke(app, ["contract-version", "--require-capability", "artifact-submit", "--provider-version", "0.0.1"], catch_exceptions=False)
    envelope = json.loads(result.stdout)
    assert result.exit_code != 0
    assert envelope["error_code"] == "CONTRACT_VERSION_MISMATCH"
    accepted = runner.invoke(app, ["contract-version", "--require-capability", "artifact-submit"], catch_exceptions=False)
    assert accepted.exit_code == 0
    assert json.loads(accepted.stdout)["data"]["api_version"] == CONTRACT_VERSION


def _runtime_bytes(root: Path) -> dict[str, bytes]:
    runtime = root / ".kittify" / "runtime"
    return {str(path.relative_to(runtime)): path.read_bytes() for path in runtime.rglob("*") if path.is_file()}


@pytest.mark.parametrize(("mission", "code"), [("../escape", "INVALID_MISSION"), ("missing-mission", "MISSION_NOT_FOUND")])
def test_next_uses_the_canonical_api_mission_guard(tmp_path: Path, mission: str, code: str) -> None:
    root = _project(tmp_path)
    before = _runtime_bytes(root)
    assert not feature_runs_path(root).exists()
    result = _call(root, "next", "--mission", mission, success=False)
    assert result["error_code"] == code
    assert _runtime_bytes(root) == before
    assert not feature_runs_path(root).exists()


@pytest.mark.parametrize("topology", ["single_branch", "coord"])
def test_public_client_finalizes_without_manual_artifact_bridge(tmp_path: Path, topology: str) -> None:
    root = _project(tmp_path)
    discovery = _call(root, "design-context", "--mission-type", "software-dev", "--stage", "specify")["data"]
    assert discovery["templates"]["spec"]["content"]
    created = _call(root, "specify", "--mission", "public-client", "--mission-type", "software-dev", "--topology", topology, "--policy", POLICY)["data"]
    mission = created["mission_slug"]
    _interview(root, mission, "specify")
    spec = _submit(root, mission, "specify", "specification", SPEC, {})
    _call(root, "design-validate", "--mission", mission, "--stage", "specify")
    scaffold = _call(root, "plan", "--mission", mission, "--policy", POLICY)["data"]
    assert scaffold["scaffold_only"] is True
    assert scaffold["phase_complete"] is False
    _interview(root, mission, "plan")
    plan = _submit(root, mission, "plan", "plan", PLAN, {"specification": spec["sha256"]})
    _call(root, "design-validate", "--mission", mission, "--stage", "plan")
    parents = {"specification": spec["sha256"], "plan": plan["sha256"]}
    outline = _submit(root, mission, "tasks", "outline", OUTLINE, parents)
    _submit(root, mission, "tasks", "work_package", PROMPT, {**parents, "outline": outline["sha256"]}, "WP01")
    _call(root, "design-validate", "--mission", mission, "--stage", "tasks")
    finalized = _call(root, "tasks", "--mission", mission, "--policy", POLICY)["data"]
    assert finalized["wp_count"] == 1
    assert finalized["bootstrap"]["newly_seeded"] == 1
    ready = _call(root, "list-ready", "--mission", mission)["data"]
    assert [wp["wp_id"] for wp in ready["ready_work_packages"]] == ["WP01"]
    frozen_request = {
        "artifacts": [{"kind": "specification", "content": SPEC + "\nAmended\n", "expected_sha256": spec["sha256"]}],
        "parents": {},
        "context_sha256": _context(root, mission, "specify")["context_sha256"],
    }
    frozen = _call(
        root, "artifact-submit", "--mission", mission, "--request-json", json.dumps(frozen_request), "--actor", "planning-client", "--policy", POLICY, success=False
    )
    assert frozen["error_code"] == "DESIGN_FINALIZED"
    assert _read(root, mission, "specification")["content"] == SPEC


def _advance(root: Path, mission: str) -> dict[str, Any]:
    data = _call(root, "next", "--mission", mission, "--agent", "planning-client", "--result", "success", "--policy", POLICY)["data"]
    assert data["kind"] == "step", data
    prompt = data["prompt"]
    assert prompt["content"]
    assert prompt["bytes"] == len(prompt["content"].encode("utf-8")) <= 262144
    assert prompt["sha256"] == _content_sha256(prompt["content"])
    assert "prompt_file" not in data
    return data


def test_public_next_completes_real_design_actions(tmp_path: Path) -> None:
    root = _project(tmp_path)
    created = _call(root, "specify", "--mission", "native-cycle", "--mission-type", "software-dev", "--topology", "single_branch", "--policy", POLICY)["data"]
    mission = created["mission_slug"]
    before = _runtime_bytes(root)
    assert not feature_runs_path(root).exists()
    query = _call(root, "next", "--mission", mission)["data"]
    assert _runtime_bytes(root) == before
    assert not feature_runs_path(root).exists()
    assert query["kind"] == "query"
    assert query["mission_state"] == "not_started"
    issued = _advance(root, mission)
    assert issued["step_id"] == "discovery"
    assert feature_runs_path(root).exists()
    assert json.loads(feature_runs_path(root).read_text())
    active = _runtime_bytes(root)
    assert _call(root, "next", "--mission", mission, "--agent", "planning-client")["data"]["step_id"] == "discovery"
    assert _runtime_bytes(root) == active
    _interview(root, mission, "specify")
    _submit(root, mission, "specify", "research", "# Research\n\nThe README client uses the canonical local API.\n", {})
    assert _advance(root, mission)["step_id"] == "specify"
    refused = _call(root, "next", "--mission", mission, "--agent", "planning-client", "--result", "success", "--policy", POLICY, success=False)
    assert refused["error_code"] == "RUNTIME_NEXT_FAILED"
    assert refused["data"]["reason"] == "DESIGN_PREREQUISITES_FAILED"
    assert _call(root, "next", "--mission", mission)["data"]["step_id"] == "specify"
    spec = _submit(root, mission, "specify", "specification", SPEC, {})
    assert _advance(root, mission)["step_id"] == "plan"
    _call(root, "plan", "--mission", mission, "--policy", POLICY)
    _interview(root, mission, "plan")
    plan = _submit(root, mission, "plan", "plan", PLAN, {"specification": spec["sha256"]})
    assert _advance(root, mission)["step_id"] == "tasks"
    parents = {"specification": spec["sha256"], "plan": plan["sha256"]}
    outline = _submit(root, mission, "tasks", "outline", OUTLINE, parents)
    _submit(root, mission, "tasks", "work_package", PROMPT, {**parents, "outline": outline["sha256"]}, "WP01")
    _call(root, "tasks", "--mission", mission, "--policy", POLICY)
    next_action = _advance(root, mission)
    assert next_action["action"] == "implement"


def _configure_required_input(root: Path, step_id: str) -> None:
    import yaml
    from runtime.next.runtime_bridge_io import _runtime_template_key

    # Project initialization only: reuse the resolved native template and its
    # documented project-override tier. No run/status snapshot is manufactured.
    template = yaml.safe_load(Path(_runtime_template_key("software-dev", root)).read_text(encoding="utf-8"))
    selected = next(step for step in template["steps"] if step["id"] == step_id)
    selected["requires_inputs"] = ["approval"]
    override = root / ".kittify" / "overrides" / "missions" / "software-dev" / "mission-runtime.yaml"
    override.parent.mkdir(parents=True, exist_ok=True)
    override.write_text(yaml.safe_dump(template, sort_keys=False), encoding="utf-8")
    for args in [("add", "."), ("commit", "-m", "configure native input workflow before API calls")]:
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)
    assert Path(_runtime_template_key("software-dev", root)) == override.resolve()


def test_public_next_resolves_configured_native_input(tmp_path: Path) -> None:
    """Configure a supported workflow before any API call; native owns decisions."""
    root = _project(tmp_path)
    _configure_required_input(root, "discovery")

    # Every operation after this point is an external API call.
    created = _call(root, "specify", "--mission", "native-input", "--mission-type", "software-dev", "--topology", "single_branch", "--policy", POLICY)["data"]
    mission = created["mission_slug"]
    initial = _call(root, "next", "--mission", mission)["data"]
    assert initial["kind"] == "query"
    assert initial["mission_state"] == "not_started"
    assert initial.get("step_id") is None
    assert initial.get("run_id") is None
    required = _call(root, "next", "--mission", mission, "--agent", "planning-client", "--result", "success", "--policy", POLICY)["data"]
    assert required["kind"] == "decision_required"
    assert required["step_id"] == "discovery"
    assert required["decision_id"] == "input:approval"
    assert required["input_key"] == "approval"
    assert required["question"]
    pending = _call(root, "next", "--mission", mission, "--agent", "planning-client")["data"]
    assert pending["kind"] == "query"
    assert pending["decision_id"] == required["decision_id"]
    assert pending["question"] == required["question"]
    answer = "Approved bounded README investigation"
    resumed = _call(
        root,
        "next",
        "--mission",
        mission,
        "--agent",
        "planning-client",
        "--result",
        "success",
        "--decision-id",
        required["decision_id"],
        "--answer",
        answer,
        "--policy",
        POLICY,
    )["data"]
    assert resumed["kind"] == "step"
    assert resumed["step_id"] == "discovery"
    assert resumed["answered"] == required["decision_id"]
    assert resumed["answer"] == answer
    prompt = resumed["prompt"]
    assert prompt["content"]
    assert prompt["bytes"] == len(prompt["content"].encode("utf-8")) <= 262144
    assert prompt["sha256"] == _content_sha256(prompt["content"])
    assert "prompt_file" not in resumed
    resolved = _call(root, "next", "--mission", mission)["data"]
    assert resolved["kind"] == "query"
    assert resolved["step_id"] == "discovery"
    assert resolved.get("decision_id") is None
    assert resolved.get("input_key") is None
    assert resolved.get("question") is None


def test_design_input_answer_issues_step_before_completion_validation(tmp_path: Path) -> None:
    """A pending design input is not proof that its design prompt was issued."""
    root = _project(tmp_path)
    _configure_required_input(root, "specify")
    mission = _call(root, "specify", "--mission", "design-input", "--mission-type", "software-dev", "--topology", "single_branch", "--policy", POLICY)["data"][
        "mission_slug"
    ]
    _interview(root, mission, "specify")
    _submit(root, mission, "specify", "research", "# Research\n\nInvestigate the API planning client.\n", {})
    assert _advance(root, mission)["step_id"] == "discovery"
    pending = _call(root, "next", "--mission", mission, "--agent", "planning-client", "--result", "success", "--policy", POLICY)["data"]
    assert pending["kind"] == "decision_required"
    assert pending["step_id"] == "specify"
    assert pending["decision_id"] == "input:approval"
    issued = _call(
        root,
        "next",
        "--mission",
        mission,
        "--agent",
        "planning-client",
        "--result",
        "success",
        "--decision-id",
        pending["decision_id"],
        "--answer",
        "Approved bounded specification",
        "--policy",
        POLICY,
    )["data"]
    assert issued["kind"] == "step"
    assert issued["step_id"] == "specify"
    assert issued["prompt"]["content"]
    active = _runtime_bytes(root)
    refused = _call(root, "next", "--mission", mission, "--agent", "planning-client", "--result", "success", "--policy", POLICY, success=False)
    assert refused["data"]["reason"] == "DESIGN_PREREQUISITES_FAILED"
    assert _runtime_bytes(root) == active
    assert _call(root, "next", "--mission", mission)["data"]["step_id"] == "specify"
    _submit(root, mission, "specify", "specification", SPEC, {})
    assert _advance(root, mission)["step_id"] == "plan"
