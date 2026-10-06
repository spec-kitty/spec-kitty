"""WP08 (design-phase-orchestrator-api-01M1HE6M) -- ``answer-decision``
orchestrator-api verb (FR-013, Mechanism B, full event/lifecycle parity via
WP02's extracted seam, operator ruling SPEC-FRESH2-001).

Acceptance scenarios (see
``kitty-specs/design-phase-orchestrator-api-01M1HE6M/tasks/WP08-answer-decision-verb.md``,
spec User Story 5):

1. A single pending ``decision_required`` (blocking ``AuditStep``) is
   auto-resolved when ``--decision-id`` is omitted -> ``success: true``,
   ``data.answered_decision_id`` names it, the run-snapshot's
   ``pending_decisions`` no longer contains it, AND ``data`` carries the
   full ``Decision.to_dict()`` shape for whatever follows.
2. More than one pending decision without ``--decision-id`` ->
   ``AMBIGUOUS_PENDING_DECISION``, listing the pending ids.
3. An explicit ``--decision-id "input:<key>"`` (``PromptStep`` with an unmet
   ``requires_inputs`` entry) -> ``success: true``, next-step parity fields
   PLUS ``answered_decision_id``.
4. A ``--decision-id`` not in the current run's ``pending_decisions`` ->
   ``DECISION_NOT_PENDING``.
5. No decision currently pending -> ``NO_PENDING_DECISION``.
6. Independent of ``OriginFlow``/FR-012's scope guard: no ``--origin``
   concept at all, ``INVALID_ORIGIN_FLOW`` never applies to this verb.
7. ``--answer`` without ``--result`` -> ``RESULT_REQUIRED``.

Plus (T040 / SC-007): a field-for-field diff assertion against a real
``spec-kitty next --answer ... --json`` invocation for the identical
scenario -- byte-identical on every ``Decision.to_dict()``-derived key
except the fields that are legitimately non-deterministic PER CALL/PER RUN
(``timestamp``, ``run_id``, ``prompt_file`` -- see
``runtime_bridge.py``'s own module comment: "threads the caller-computed
non-deterministic fields (timestamp/run_id/decision_id) -- the core itself
never stamps them"; ``prompt_file`` is an absolute, run-instance-scoped
filesystem path so two independent runs never share one even for the
identical logical step).

This is the RED-then-GREEN ATDD anchor (charter C-011): pre-implementation,
``answer-decision`` does not exist as an ``@app.command`` on
``orchestrator_api.commands.app``, so every scenario below fails at the
Typer "no such command" / non-zero-exit level.

Real mission scaffolding (real git repo, real ``mission-runtime.yaml``/
``state.json`` run-snapshot disk I/O -- the SAME fixture-builder pattern
``tests/specify_cli/next/test_next_invocation_lifecycle_seam.py`` (WP02)
uses, duplicated here per this repo's own established convention for this
fixture shape: attribute the origin in a comment rather than import across
test-suite boundaries) -- hence ``integration``/``git_repo`` (NOT ``fast``),
matching ``test_transition_subtask_gate.py``'s precedent (real fixture-
mission run-snapshot I/O).
"""

from __future__ import annotations

import contextlib
import inspect
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.orchestrator_api import decision_verbs
from specify_cli.orchestrator_api.commands import app as orchestrator_app
from tests._factories import provision_test_charter

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_POLICY = json.dumps(
    {
        "orchestrator_id": "test-orch",
        "orchestrator_version": "0.0.1",
        "agent_family": "claude",
        "approval_mode": "full_auto",
        "sandbox_mode": "workspace_write",
        "network_mode": "none",
        "dangerous_flags": [],
    }
)


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verbatim pattern from ``test_next_invocation_lifecycle_seam.py``
    (WP02): the fixture-mission builders below stage minimal mission state
    without running ``spec-kitty charter sync``, so the real preflight gate
    would otherwise block every ``next`` CLI call this file's setup/parity
    helpers make before ever reaching the code under test. Only the direct
    ``next`` CLI invocations go through this gate -- none of the
    ``orchestrator_api`` verbs (including ``answer-decision``) call it.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_warn_only",
        lambda *_args, **_kwargs: result,
    )


# ---------------------------------------------------------------------------
# Fixture-mission builders. Duplicated from
# ``tests/specify_cli/next/test_next_invocation_lifecycle_seam.py``'s
# (WP02's) own proven, real (unmocked) builders -- this repo's established
# convention for this fixture shape (see that module's own header comment
# for the same rationale) -- extended here with a SECOND mission shape (a
# blocking ``AuditStep``) this WP's own Acceptance Scenarios 1/6/parity need.
# ---------------------------------------------------------------------------


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    (path / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def _scaffold_project(tmp_path: Path, *, mission_slug: str, mission_type: str, mission_id: str) -> Path:
    """Scaffold a minimal spec-kitty project with a mission carrying a real
    ``mission_id`` -- the lifecycle seam's PRIMARY-anchoring reads
    (``resolve_mission_identity(...).mission_id``) are a fail-closed no-op
    without one (FR-004/#2278).
    """
    repo_root = tmp_path / "project"
    repo_root.mkdir(parents=True)
    _init_git_repo(repo_root)

    kittify = repo_root / ".kittify"
    kittify.mkdir()
    provision_test_charter(repo_root)

    from specify_cli.identity.project import ensure_identity

    ensure_identity(repo_root)

    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": mission_type, "mission_id": mission_id}),
        encoding="utf-8",
    )
    return repo_root


def _write_audit_gate_mission(repo_root: Path, mission_type: str) -> None:
    """A runtime-only mission: a blocking ``AuditStep`` with NO dependencies
    (so it is the very first eligible step -- ``decision_required`` is
    surfaced on the mission's FIRST ``next`` call, no setup/reveal call
    needed), then a plain step after it.
    """
    mission_dir = repo_root / ".kittify" / "overrides" / "missions" / mission_type
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "mission-runtime.yaml").write_text(
        (
            "mission:\n"
            f"  key: {mission_type}\n"
            f"  name: {mission_type}\n"
            "  version: '1.0.0'\n"
            "audit_steps:\n"
            "  - id: audit_gate\n"
            "    title: Audit Gate\n"
            "    description: Blocking audit checkpoint\n"
            "    audit:\n"
            "      trigger_mode: manual\n"
            "      enforcement: blocking\n"
            "steps:\n"
            "  - id: after_audit\n"
            "    title: After Audit\n"
            "    depends_on: [audit_gate]\n"
            "    description: Proceed after the audit gate is resolved\n"
        ),
        encoding="utf-8",
    )
    template_dir = repo_root / ".kittify" / "overrides" / "command-templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "after_audit.md").write_text(
        "# after_audit\n\nRun the synthetic after_audit step for the WP08 fixture.\n",
        encoding="utf-8",
    )


def _write_input_requiring_mission(repo_root: Path, mission_type: str) -> None:
    """A runtime-only mission: a plain first step, an input-requiring second
    step, then a plain third step -- verbatim shape (and rationale) as
    ``test_next_invocation_lifecycle_seam.py``'s
    ``_write_three_step_input_mission``.
    """
    mission_dir = repo_root / ".kittify" / "overrides" / "missions" / mission_type
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "mission-runtime.yaml").write_text(
        (
            "mission:\n"
            f"  key: {mission_type}\n"
            f"  name: {mission_type}\n"
            "  version: '1.0.0'\n"
            "steps:\n"
            "  - id: step_one\n"
            "    title: Step One\n"
            "    description: Plain first step, no input required\n"
            "  - id: collect_input\n"
            "    title: Collect Input\n"
            "    description: Gather required answer\n"
            "    depends_on: [step_one]\n"
            "    requires_inputs: [approval]\n"
            "  - id: execute\n"
            "    title: Execute\n"
            "    depends_on: [collect_input]\n"
            "    description: Proceed with mission\n"
        ),
        encoding="utf-8",
    )
    template_dir = repo_root / ".kittify" / "overrides" / "command-templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    for action in ("step_one", "collect_input", "execute"):
        (template_dir / f"{action}.md").write_text(
            f"# {action}\n\nRun the synthetic {action} step for the WP08 fixture.\n",
            encoding="utf-8",
        )


def _next(repo_root: Path, agent: str, mission_slug: str, **extra: str) -> dict[str, Any]:
    """Real ``spec-kitty next --json`` CLI invocation, cwd pinned to *repo_root*."""
    args = ["next", "--agent", agent, "--mission", mission_slug, "--result", "success", "--json"]
    for key, value in extra.items():
        args.extend([f"--{key.replace('_', '-')}", value])
    with contextlib.chdir(repo_root):
        result = runner.invoke(cli_app, args)
    assert result.exit_code == 0, result.output
    return cast("dict[str, Any]", json.loads(result.stdout))


def _run_answer_decision(repo_root: Path, args: list[str]) -> Result:
    with contextlib.chdir(repo_root):
        return runner.invoke(orchestrator_app, ["answer-decision", *args])


def _envelope(result: Result) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(result.output.strip().split("\n")[0]))


def _run_dir_for(repo_root: Path, mission_slug: str) -> Path:
    from runtime.next.runtime_bridge_io import _resolve_run_dir_for_mission

    run_dir = _resolve_run_dir_for_mission(repo_root, mission_slug)
    assert run_dir is not None, f"no run directory resolved for {mission_slug!r}"
    return run_dir


def _read_pending_decisions(repo_root: Path, mission_slug: str) -> dict[str, Any]:
    from runtime.next._internal_runtime.engine import _read_snapshot

    snapshot = _read_snapshot(_run_dir_for(repo_root, mission_slug))
    return dict(snapshot.pending_decisions)


def _set_mission_owner_id(repo_root: Path, mission_slug: str, owner_id: str) -> None:
    """Audit decisions (``decision_id`` starting ``audit:``) are gated by the
    engine's own RACI/authority check (``engine.py:_provide_decision_answer``,
    T014): the answering actor must be ``actor_type == "human"`` (the
    default ``answer_decision_via_runtime`` uses) AND ``actor_id`` must equal
    ``inputs["mission_owner_id"]``. Production runs set this via mission
    bootstrap inputs this fixture does not otherwise populate
    (``get_or_start_run`` seeds only ``{"mission_slug": ...}``) -- inject it
    directly into the run snapshot's ``inputs`` (real on-disk state.json
    I/O, this file's own established technique) so the audit-gate fixture's
    answer calls pass the SAME authority check a real audit-answering human
    operator would.
    """
    from runtime.next._internal_runtime.engine import _read_snapshot, _write_snapshot

    run_dir = _run_dir_for(repo_root, mission_slug)
    snapshot = _read_snapshot(run_dir)
    snapshot.inputs["mission_owner_id"] = owner_id
    _write_snapshot(run_dir, snapshot)


# ---------------------------------------------------------------------------
# Acceptance Scenario 1 -- single pending decision, auto-resolved.
# ---------------------------------------------------------------------------


def test_answer_decision_auto_resolves_single_pending_audit_decision(tmp_path: Path) -> None:
    mission_slug = "wp08-audit-auto-resolve"
    mission_type = "wp08-audit-mission-1"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08AUDITULID000000001")
    _write_audit_gate_mission(repo_root, mission_type)
    agent = "wp08-agent"

    reveal = _next(repo_root, agent, mission_slug)
    assert reveal["kind"] == "decision_required"
    assert reveal["decision_id"] == "audit:audit_gate"
    assert reveal["options"] == ["approve", "reject"]
    assert "audit:audit_gate" in _read_pending_decisions(repo_root, mission_slug)
    _set_mission_owner_id(repo_root, mission_slug, agent)

    result = _run_answer_decision(
        repo_root,
        [
            "--mission",
            mission_slug,
            "--agent",
            agent,
            "--result",
            "success",
            "--answer",
            "approve",
            "--policy",
            _POLICY,
        ],
    )
    envelope = _envelope(result)
    assert envelope["success"] is True, envelope
    data = envelope["data"]

    assert data["answered_decision_id"] == "audit:audit_gate"
    assert "answer" not in data
    assert data["kind"] == "step"
    assert data["step_id"] == "after_audit"

    assert "audit:audit_gate" not in _read_pending_decisions(repo_root, mission_slug)


# ---------------------------------------------------------------------------
# Acceptance Scenario 3 -- explicit --decision-id "input:<key>".
# ---------------------------------------------------------------------------


def test_answer_decision_explicit_decision_id_input_key(tmp_path: Path) -> None:
    mission_slug = "wp08-input-explicit"
    mission_type = "wp08-input-mission-1"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08INPUTULID0000000002")
    _write_input_requiring_mission(repo_root, mission_type)
    agent = "wp08-agent"

    _next(repo_root, agent, mission_slug)  # issue step_one
    reveal = _next(repo_root, agent, mission_slug)  # reveal collect_input's requirement
    assert reveal["kind"] == "decision_required"
    assert reveal["decision_id"] == "input:approval"

    result = _run_answer_decision(
        repo_root,
        [
            "--mission",
            mission_slug,
            "--agent",
            agent,
            "--result",
            "success",
            "--answer",
            "yes",
            "--decision-id",
            "input:approval",
            "--policy",
            _POLICY,
        ],
    )
    envelope = _envelope(result)
    assert envelope["success"] is True, envelope
    data = envelope["data"]

    assert data["answered_decision_id"] == "input:approval"
    assert "answer" not in data
    assert data["kind"] == "step"
    assert data["step_id"] == "collect_input"


# ---------------------------------------------------------------------------
# Acceptance Scenario 2 -- ambiguous pending decisions.
# ---------------------------------------------------------------------------


def test_answer_decision_ambiguous_pending_decision_without_decision_id(tmp_path: Path) -> None:
    mission_slug = "wp08-ambiguous"
    mission_type = "wp08-input-mission-2"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08AMBIGULID000000003")
    _write_input_requiring_mission(repo_root, mission_type)
    agent = "wp08-agent"

    _next(repo_root, agent, mission_slug)
    reveal = _next(repo_root, agent, mission_slug)
    assert reveal["kind"] == "decision_required"
    real_decision_id = reveal["decision_id"]

    # Inject a SECOND synthetic pending decision directly into the run
    # snapshot's on-disk state -- real fixture-mission run-snapshot I/O
    # (this file's own precedent, mirroring test_transition_subtask_gate.py),
    # the only practical way to make TWO decisions genuinely pending at once
    # without inventing a second concurrent DAG branch.
    from runtime.next._internal_runtime.engine import _read_snapshot, _write_snapshot

    run_dir = _run_dir_for(repo_root, mission_slug)
    snapshot = _read_snapshot(run_dir)
    real_entry = dict(snapshot.pending_decisions[real_decision_id])
    fake_decision_id = "audit:synthetic-extra-decision"
    fake_entry = {**real_entry, "decision_id": fake_decision_id, "step_id": "synthetic-extra-decision"}
    snapshot.pending_decisions[fake_decision_id] = fake_entry
    _write_snapshot(run_dir, snapshot)
    assert set(_read_pending_decisions(repo_root, mission_slug)) == {real_decision_id, fake_decision_id}

    result = _run_answer_decision(
        repo_root,
        [
            "--mission",
            mission_slug,
            "--agent",
            agent,
            "--result",
            "success",
            "--answer",
            "yes",
            "--policy",
            _POLICY,
        ],
    )
    envelope = _envelope(result)
    assert envelope["success"] is False
    assert envelope["error_code"] == "AMBIGUOUS_PENDING_DECISION"
    assert sorted(envelope["data"]["pending_decision_ids"]) == sorted([real_decision_id, fake_decision_id])

    # Rejected BEFORE the service layer -- neither decision was answered.
    assert set(_read_pending_decisions(repo_root, mission_slug)) == {real_decision_id, fake_decision_id}


# ---------------------------------------------------------------------------
# Acceptance Scenario 4 -- --decision-id not currently pending.
# ---------------------------------------------------------------------------


def test_answer_decision_decision_id_not_pending(tmp_path: Path) -> None:
    mission_slug = "wp08-not-pending"
    mission_type = "wp08-input-mission-3"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08NOTPENDULID00000004")
    _write_input_requiring_mission(repo_root, mission_type)
    agent = "wp08-agent"

    _next(repo_root, agent, mission_slug)
    reveal = _next(repo_root, agent, mission_slug)
    assert reveal["kind"] == "decision_required"

    result = _run_answer_decision(
        repo_root,
        [
            "--mission",
            mission_slug,
            "--agent",
            agent,
            "--result",
            "success",
            "--answer",
            "yes",
            "--decision-id",
            "input:does-not-exist",
            "--policy",
            _POLICY,
        ],
    )
    envelope = _envelope(result)
    assert envelope["success"] is False
    assert envelope["error_code"] == "DECISION_NOT_PENDING"

    # Never silently no-op'd or answered the wrong decision.
    assert "input:approval" in _read_pending_decisions(repo_root, mission_slug)


# ---------------------------------------------------------------------------
# Acceptance Scenario 5 -- no decision currently pending.
# ---------------------------------------------------------------------------


def test_answer_decision_no_pending_decision(tmp_path: Path) -> None:
    mission_slug = "wp08-no-pending"
    mission_type = "wp08-input-mission-4"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08NOPENDULID000000005")
    _write_input_requiring_mission(repo_root, mission_type)
    agent = "wp08-agent"

    issued = _next(repo_root, agent, mission_slug)
    assert issued["kind"] == "step"  # plain step_one, no decision pending yet

    result = _run_answer_decision(
        repo_root,
        [
            "--mission",
            mission_slug,
            "--agent",
            agent,
            "--result",
            "success",
            "--answer",
            "yes",
            "--policy",
            _POLICY,
        ],
    )
    envelope = _envelope(result)
    assert envelope["success"] is False
    assert envelope["error_code"] == "NO_PENDING_DECISION"


# ---------------------------------------------------------------------------
# RESULT_REQUIRED -- --answer without --result.
# ---------------------------------------------------------------------------


def test_answer_decision_result_required_without_result(tmp_path: Path) -> None:
    mission_slug = "wp08-result-required"
    mission_type = "wp08-input-mission-5"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08RESREQULID000000006")
    _write_input_requiring_mission(repo_root, mission_type)

    result = _run_answer_decision(
        repo_root,
        [
            "--mission",
            mission_slug,
            "--agent",
            "wp08-agent",
            "--answer",
            "yes",
            "--policy",
            _POLICY,
        ],
    )
    envelope = _envelope(result)
    assert envelope["success"] is False
    assert envelope["error_code"] == "RESULT_REQUIRED"


# ---------------------------------------------------------------------------
# Acceptance Scenario 6 -- FR-012's INVALID_ORIGIN_FLOW guard never applies.
# ---------------------------------------------------------------------------


def test_answer_decision_never_applies_origin_flow_guard() -> None:
    """Static regression check (Reviewer Guidance in the WP08 task file:
    "grep for INVALID_ORIGIN_FLOW in the WP08 diff; any hit is a violation")
    -- codified as an automated assertion rather than left to manual review.
    """
    source = inspect.getsource(decision_verbs.answer_decision)
    assert "INVALID_ORIGIN_FLOW" not in source
    assert "OriginFlow" not in source
    assert "--origin" not in source


# ---------------------------------------------------------------------------
# T040 / SC-007 -- field-for-field parity with a real `next --answer --json`
# invocation for the identical scenario.
# ---------------------------------------------------------------------------


def test_answer_decision_field_parity_with_host_cli_next_answer(tmp_path: Path) -> None:
    """Two independent, structurally IDENTICAL missions (same slug, same
    mission type, same audit-gate fixture) in separate repos: one resolved
    via the real host CLI's ``next --answer ... --json``, the other via
    orchestrator-api's ``answer-decision``. Every ``Decision.to_dict()``-
    derived key must match EXACTLY except the three fields that are
    genuinely non-deterministic per call/run (see module docstring).
    """
    mission_slug = "wp08-parity"
    mission_type = "wp08-parity-mission"
    agent = "parity-agent"

    cli_repo = _scaffold_project(
        tmp_path / "cli",
        mission_slug=mission_slug,
        mission_type=mission_type,
        mission_id="01HWP08PARITYULIDCLI00007",
    )
    _write_audit_gate_mission(cli_repo, mission_type)
    orch_repo = _scaffold_project(
        tmp_path / "orch",
        mission_slug=mission_slug,
        mission_type=mission_type,
        mission_id="01HWP08PARITYULIDORC00008",
    )
    _write_audit_gate_mission(orch_repo, mission_type)

    cli_reveal = _next(cli_repo, agent, mission_slug)
    orch_reveal = _next(orch_repo, agent, mission_slug)
    assert cli_reveal["decision_id"] == orch_reveal["decision_id"] == "audit:audit_gate"
    _set_mission_owner_id(cli_repo, mission_slug, agent)
    _set_mission_owner_id(orch_repo, mission_slug, agent)

    cli_payload = _next(cli_repo, agent, mission_slug, answer="approve", **{"decision-id": "audit:audit_gate"})
    assert cli_payload["kind"] == "step"
    assert cli_payload["answered"] == "audit:audit_gate"
    assert cli_payload["answer"] == "approve"

    orch_result = _run_answer_decision(
        orch_repo,
        [
            "--mission",
            mission_slug,
            "--agent",
            agent,
            "--result",
            "success",
            "--answer",
            "approve",
            "--decision-id",
            "audit:audit_gate",
            "--policy",
            _POLICY,
        ],
    )
    orch_envelope = _envelope(orch_result)
    assert orch_envelope["success"] is True, orch_envelope
    orch_data = orch_envelope["data"]

    # Non-deterministic per call/run -- see module docstring.
    _excluded = {"timestamp", "run_id", "prompt_file"}
    decision_keys = set(cli_payload) - {"answered", "answer"}
    assert decision_keys <= set(orch_data)
    for key in sorted(decision_keys - _excluded):
        assert orch_data[key] == cli_payload[key], f"field {key!r} diverges: cli={cli_payload[key]!r} orch={orch_data[key]!r}"
    assert orch_data.get("prompt_file"), "orchestrator-api response missing prompt_file"
    assert cli_payload.get("prompt_file"), "host-CLI response missing prompt_file"

    assert orch_data["answered_decision_id"] == "audit:audit_gate"
    assert "answer" not in orch_data


# ---------------------------------------------------------------------------
# WP08-001 (fold-in review finding, severity 3) -- ``--result`` enum
# validation, host-CLI parity. Pre-fix, ``answer-decision`` only checked
# ``result is None`` (``RESULT_REQUIRED``); any out-of-enum string (not in
# ``next_cmd.py``'s own ``_VALID_RESULTS = ("success", "failed", "blocked")``,
# ``next_cmd.py:53``) was silently accepted, the DAG still advanced, and
# ``pair_previous_lifecycle_record`` wrote the garbage value into the
# lifecycle record's ``reason`` field -- a live behavioural fork from the
# host CLI's own ``_validate_result_and_answer`` (``next_cmd.py:610-613``),
# which rejects it with exit 1 BEFORE ``_maybe_handle_answer``/
# ``_handle_answer`` ever runs (i.e. before decision auto-resolve, before
# any persistence).
# ---------------------------------------------------------------------------


def _run_next_raw(repo_root: Path, args: list[str]) -> Result:
    """Invoke the real host CLI's ``next`` command with raw args (no forced
    ``--result``, unlike ``_next`` above) -- ground truth for the host CLI's
    OWN literal validation behaviour.
    """
    with contextlib.chdir(repo_root):
        return runner.invoke(cli_app, ["next", *args])


def test_host_cli_rejects_invalid_result_before_no_pending_decision(tmp_path: Path) -> None:
    """Ground truth: the host CLI's own ordering for an invalid ``--result``
    COMBINED with a second, independently-true error condition (no pending
    decision to answer). ``_validate_result_and_answer`` (``next_cmd.py``
    line 610-613) runs before ``_maybe_handle_answer``'s decision
    auto-resolve (which would otherwise raise "No pending decisions..."),
    so the enum rejection wins -- this is the exact ordering
    ``answer-decision`` must reproduce.
    """
    mission_slug = "wp08-001-cli-ground-truth"
    mission_type = "wp08-input-mission-6"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08001CLIULID00000009")
    _write_input_requiring_mission(repo_root, mission_type)
    agent = "wp08-agent"

    issued = _next(repo_root, agent, mission_slug)
    assert issued["kind"] == "step"  # plain step_one, no decision pending yet

    result = _run_next_raw(
        repo_root,
        ["--agent", agent, "--mission", mission_slug, "--answer", "yes", "--result", "bogus", "--json"],
    )
    assert result.exit_code == 1
    assert "must be one of" in result.output
    assert "No pending decisions" not in result.output


def test_answer_decision_invalid_result_rejected(tmp_path: Path) -> None:
    """WP08-001: an out-of-enum ``--result`` must be rejected with a
    dedicated ``INVALID_RESULT`` error_code, never silently accepted.
    """
    mission_slug = "wp08-001-invalid-result"
    mission_type = "wp08-input-mission-7"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08001INVULID00000010")
    _write_input_requiring_mission(repo_root, mission_type)
    agent = "wp08-agent"

    issued = _next(repo_root, agent, mission_slug)
    assert issued["kind"] == "step"

    result = _run_answer_decision(
        repo_root,
        [
            "--mission",
            mission_slug,
            "--agent",
            agent,
            "--result",
            "bogus",
            "--answer",
            "yes",
            "--policy",
            _POLICY,
        ],
    )
    envelope = _envelope(result)
    assert envelope["success"] is False
    assert envelope["error_code"] == "INVALID_RESULT"


def test_answer_decision_invalid_result_fires_before_no_pending_decision(tmp_path: Path) -> None:
    """Interleaving/ordering proof (WP08-001): the SAME fixture shape as
    ``test_answer_decision_no_pending_decision`` (which raises
    ``NO_PENDING_DECISION`` for a VALID ``--result``) combined with an
    INVALID ``--result`` must still produce ``INVALID_RESULT`` -- mirroring
    the host CLI's own ordering (proven by
    ``test_host_cli_rejects_invalid_result_before_no_pending_decision``
    above): the enum check runs BEFORE decision-resolution/auto-resolve,
    never after it. A fix that validates the enum only after attempting
    decision resolution would surface ``NO_PENDING_DECISION`` here instead
    -- the wrong error from the wrong point in the call sequence.
    """
    mission_slug = "wp08-001-ordering"
    mission_type = "wp08-input-mission-8"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id="01HWP08001ORDULID00000011")
    _write_input_requiring_mission(repo_root, mission_type)
    agent = "wp08-agent"

    issued = _next(repo_root, agent, mission_slug)
    assert issued["kind"] == "step"

    result = _run_answer_decision(
        repo_root,
        [
            "--mission",
            mission_slug,
            "--agent",
            agent,
            "--result",
            "bogus",
            "--answer",
            "yes",
            "--policy",
            _POLICY,
        ],
    )
    envelope = _envelope(result)
    assert envelope["success"] is False
    assert envelope["error_code"] == "INVALID_RESULT"
    assert envelope["error_code"] != "NO_PENDING_DECISION"


# ---------------------------------------------------------------------------
# Maintainer review fold-in (PR #3855): this module otherwise only asserts
# response-field parity (``test_answer_decision_field_parity_with_host_cli_
# next_answer``) and pending-decision clearing -- it never pins that
# ``answer-decision`` itself actually WROTE the three lifecycle-seam side
# effects (``pair_previous_lifecycle_record``, ``emit_mission_next_invoked``,
# ``write_issuance_lifecycle_record``). ``assert_lifecycle_seam_effects`` was
# purpose-built for exactly this (WP02's own deliverable, spec SC-008) --
# reused UNMODIFIED here rather than re-implemented, so this module has its
# own direct regression guard on the seam wiring alongside the rest of its
# ``answer-decision``-specific coverage.
# ---------------------------------------------------------------------------


def test_answer_decision_pins_lifecycle_seam_side_effects(tmp_path: Path) -> None:
    """RED if steps 2/4/5 in ``answer_decision`` (``pair_previous_lifecycle_
    record``, ``emit_mission_next_invoked``, ``write_issuance_lifecycle_
    record``, ``commands.py`` ~3494/3501/3506) are deleted; GREEN as-is.
    """
    from specify_cli.invocation.lifecycle import write_started
    from tests.specify_cli.next.test_next_invocation_lifecycle_seam import (
        assert_lifecycle_seam_effects,
    )

    mission_slug = "wp08-lifecycle-seam-pin"
    mission_type = "wp08-lifecycle-seam-pin-mission"
    mission_id = "01HWP08SEAMPINULID0000012"
    repo_root = _scaffold_project(tmp_path, mission_slug=mission_slug, mission_type=mission_type, mission_id=mission_id)
    _write_input_requiring_mission(repo_root, mission_type)
    feature_dir = repo_root / "kitty-specs" / mission_slug
    agent = "wp08-agent"

    _next(repo_root, agent, mission_slug)  # issue step_one
    reveal = _next(repo_root, agent, mission_slug)  # reveal collect_input's requirement
    assert reveal["kind"] == "decision_required"
    decision_id = reveal["decision_id"]
    assert decision_id == "input:approval"

    # Seed a PRIOR open `started` record directly (real on-disk I/O, not a
    # mock) so the single measured `answer-decision` call below is solely
    # responsible for pairing it -- `step_one`'s own started record was
    # already paired by the `reveal` call above (every `--result` call pairs
    # unconditionally, real production behaviour). Same technique as
    # ``TestAnswerDecisionLifecycleSeamEffects`` in the seam-test module.
    write_started(
        repo_root,
        canonical_action_id="synthetic::prior-open-issuance",
        agent=agent,
        mission_id=mission_id,
    )

    def run_action() -> None:
        result = _run_answer_decision(
            repo_root,
            [
                "--mission",
                mission_slug,
                "--agent",
                agent,
                "--result",
                "success",
                "--answer",
                "yes",
                "--decision-id",
                decision_id,
                "--policy",
                _POLICY,
            ],
        )
        envelope = _envelope(result)
        assert envelope["success"] is True, envelope
        assert envelope["data"]["kind"] == "step"
        assert envelope["data"]["answered_decision_id"] == decision_id

    assert_lifecycle_seam_effects(feature_dir, repo_root, mission_slug, run_action)
