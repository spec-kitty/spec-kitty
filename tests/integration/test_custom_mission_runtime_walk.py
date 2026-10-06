"""Integration tests for the ERP custom-mission runtime walk (WP06 / T032-T034).

Three levels of pressure:

* :func:`test_erp_full_walk` — drives the runtime engine through the ERP
  fixture's seven steps, proving the loader → registry → engine handoff
  pauses at the ``ask-user`` decision-required gate (FR-007) and resumes
  through the rest of the composed steps + the retrospective marker
  (FR-006, FR-009).
* :func:`test_paired_invocation_records_carry_contract_action` — patches
  ``StepContractExecutor.execute`` and asserts the bridge dispatches a
  composed ERP step with ``context.action == step.id`` (FR-006).
* :func:`test_software_dev_specify_dispatch_unchanged` — re-asserts
  FR-010 at the integration layer: built-in ``software-dev`` keeps
  ``profile_hint=None`` so the executor's
  ``_ACTION_PROFILE_DEFAULTS`` fallback path is unchanged.

Mocking strategy mirrors ``tests/specify_cli/next/test_runtime_bridge_composition.py``:
the executor and the advancement helper are patched out so no DRG load
or live invocation writer is exercised. NFR-004: this module targets
sub-second per-test wall clock.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.mission_loader.command import run_custom_mission
from specify_cli.mission_loader.registry import get_runtime_contract_registry
from specify_cli.mission_step_contracts.executor import (
    StepContractExecutionContext,
)
from runtime.next._internal_runtime.discovery import DiscoveryContext
from runtime.next._internal_runtime.engine import (
    MissionRunRef,
    _read_snapshot,
    next_step as engine_next_step,
    provide_decision_answer,
    start_mission_run,
)
from runtime.next._internal_runtime.events import NullEmitter
from runtime.next._internal_runtime.schema import (
    ActorIdentity,
    MissionPolicySnapshot,
)
from runtime.next.decision import Decision, DecisionKind
from runtime.next.runtime_bridge_composition import _dispatch_via_composition
from tests._factories import provision_test_charter


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "missions"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Clear the singleton runtime-contract registry between tests."""
    get_runtime_contract_registry().clear()
    yield
    get_runtime_contract_registry().clear()


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip discovery env vars so tests cannot pull in side-channel paths."""
    monkeypatch.delenv("SPEC_KITTY_MISSION_PATHS", raising=False)


def _setup_project(tmp_path: Path, fixture: str) -> Path:
    """Copy ``tests/fixtures/missions/<fixture>/`` into the tmp project tier."""
    src = _FIXTURES_ROOT / fixture / "mission.yaml"
    if not src.is_file():
        raise FileNotFoundError(f"Test fixture not found: {src}")
    project_missions_dir = tmp_path / ".kittify" / "missions" / fixture
    project_missions_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, project_missions_dir / "mission.yaml")
    return tmp_path


def _isolated_context(repo_root: Path) -> DiscoveryContext:
    """Build a DiscoveryContext that ignores the user's real ``~/.kittify``."""
    fake_home = repo_root / ".fake-home"
    fake_home.mkdir(exist_ok=True)
    return DiscoveryContext(
        project_dir=repo_root,
        user_home=fake_home,
        builtin_roots=[],
    )


# ---------------------------------------------------------------------------
# T032 — Full ERP runtime walk
# ---------------------------------------------------------------------------


def test_erp_full_walk(tmp_path: Path) -> None:
    """FR-006 / FR-007 / FR-009: walk the ERP template end-to-end.

    Drives the runtime engine directly (rather than through the bridge's
    composition path) so the test does not depend on a real DRG. The
    bridge-level guarantees are covered by
    :func:`test_paired_invocation_records_carry_contract_action`. What
    this test proves:

    1. The ERP fixture loads + freezes through the runtime template
       discovery chain (no validator rejection at the engine layer).
    2. ``query-erp`` issues, then ``lookup-provider`` issues — the DAG
       respects ``depends_on``.
    3. ``ask-user`` surfaces as a ``decision_required`` decision keyed
       ``input:export_shape`` (FR-007).
    4. ``provide_decision_answer(..., answer="per-record")`` writes the
       value into ``inputs`` so the step's ``requires_inputs`` clears.
    5. The remaining composed steps (``create-js``, ``refactor-function``,
       ``write-report``) issue in order.
    6. The ``retrospective`` marker is the final step before terminal.
    """
    repo_root = _setup_project(tmp_path, fixture="erp-integration")
    ctx = _isolated_context(repo_root)

    # The runtime engine resolves the template by mission key against the
    # discovery context. Because we placed the YAML under .kittify/missions,
    # the project legacy tier finds it.
    run_ref = start_mission_run(
        template_key="erp-integration",
        inputs={"mission_slug": "erp-walk"},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=tmp_path / "runs",
        emitter=NullEmitter(),
    )

    # Drive the engine until issued_step_id reaches each expected step.
    seen_steps: list[str] = []

    def _advance() -> None:
        engine_next_step(run_ref, agent_id="test", result="success", emitter=NullEmitter())

    # First call issues the first step.
    _advance()
    snapshot = _read_snapshot(Path(run_ref.run_dir))
    assert snapshot.issued_step_id == "query-erp", (
        f"Expected first issued step to be 'query-erp'; got {snapshot.issued_step_id!r}"
    )
    seen_steps.append(snapshot.issued_step_id)

    # Advance through query-erp and into lookup-provider.
    _advance()
    snapshot = _read_snapshot(Path(run_ref.run_dir))
    assert snapshot.issued_step_id == "lookup-provider", (
        f"Expected 'lookup-provider' after query-erp; got {snapshot.issued_step_id!r}"
    )
    seen_steps.append(snapshot.issued_step_id)

    # Advance: ask-user has requires_inputs:[export_shape] so the engine
    # surfaces a decision_required NextDecision instead of issuing the step.
    decision = engine_next_step(
        run_ref, agent_id="test", result="success", emitter=NullEmitter()
    )
    assert decision.kind == "decision_required", (
        f"Expected ask-user to surface decision_required; got {decision!r}"
    )
    assert decision.decision_id == "input:export_shape"
    assert decision.input_key == "export_shape"
    assert decision.step_id == "ask-user"

    # Resolve the decision via the engine's API and verify the input lands
    # in snapshot.inputs so the next plan_next() can clear requires_inputs.
    actor = ActorIdentity(actor_id="operator", actor_type="human")
    provide_decision_answer(
        run_ref,
        decision_id="input:export_shape",
        answer="per-record",
        actor=actor,
        emitter=NullEmitter(),
    )
    snapshot = _read_snapshot(Path(run_ref.run_dir))
    assert snapshot.inputs.get("export_shape") == "per-record"
    assert "input:export_shape" not in snapshot.pending_decisions

    # Re-advance: ask-user's requires_inputs is now satisfied, so it
    # issues normally.
    _advance()
    snapshot = _read_snapshot(Path(run_ref.run_dir))
    assert snapshot.issued_step_id == "ask-user", (
        f"Expected ask-user to issue after answer; got {snapshot.issued_step_id!r}"
    )

    # Walk the remaining composed steps + the retrospective marker.
    for expected in ("create-js", "refactor-function", "write-report", "retrospective"):
        _advance()
        snapshot = _read_snapshot(Path(run_ref.run_dir))
        assert snapshot.issued_step_id == expected, (
            f"Expected step {expected!r}; got {snapshot.issued_step_id!r} "
            f"(completed_steps={snapshot.completed_steps!r})"
        )
        seen_steps.append(expected)

    # One more advance after retrospective lands us at terminal.
    final = engine_next_step(
        run_ref, agent_id="test", result="success", emitter=NullEmitter()
    )
    assert final.kind == "terminal", (
        f"Expected terminal after retrospective; got {final!r}"
    )

    # Sanity: the seen_steps cover the full ordered ERP DAG.
    assert seen_steps == [
        "query-erp",
        "lookup-provider",
        "create-js",
        "refactor-function",
        "write-report",
        "retrospective",
    ]


# ---------------------------------------------------------------------------
# T033 — Paired invocation record carries contract action
# ---------------------------------------------------------------------------


def _init_min_repo(repo_root: Path) -> None:
    """Initialize a minimal git repo and project layout for bridge dispatch."""
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )
    (repo_root / "README.md").write_text("# test", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"], cwd=repo_root, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=repo_root,
        capture_output=True,
        check=True,
    )


def test_paired_invocation_records_carry_contract_action(tmp_path: Path) -> None:
    """FR-006: the bridge dispatches a composed ERP step with ``action == step.id``.

    Synthesizes the ERP contracts via the loader's public surface, then
    drives ``_dispatch_via_composition`` for the ``query-erp`` step with
    a mocked ``StepContractExecutor.execute`` that returns a fake result
    carrying a single ``invocation_ids`` entry. We then assert:

    * The executor was called exactly once.
    * The ``StepContractExecutionContext`` it received carries
      ``mission == "erp-integration"`` and ``action == "query-erp"`` —
      the contract under R-004's synthesis convention is ``custom:<key>:
      <step.id>`` whose ``action`` IS the step.id.
    * The returned ``failures`` list is empty (composition succeeded;
      the ERP step has no built-in CLI guard so no post-action check
      runs against ``feature_dir``).
    """
    repo_root = tmp_path / "repo"
    _init_min_repo(repo_root)

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)

    feature_dir = repo_root / "kitty-specs" / "erp-walk"
    feature_dir.mkdir(parents=True)

    with patch(
        "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
        return_value=fake_result,
    ) as mock_execute:
        failures = _dispatch_via_composition(
            repo_root=repo_root,
            mission="erp-integration",
            action="query-erp",
            actor="researcher-robbie",
            profile_hint="researcher-robbie",
            request_text=None,
            mode_of_work=None,
            feature_dir=feature_dir,
        )

    assert mock_execute.call_count == 1
    call = mock_execute.call_args
    context = call.args[0] if call.args else call.kwargs["context"]
    assert isinstance(context, StepContractExecutionContext)
    # FR-006: paired invocation records carry action == step.id.
    assert context.mission == "erp-integration"
    assert context.action == "query-erp"
    # And the resolved profile_hint flows through (covered separately by
    # WP04 unit tests; included here for the cross-check).
    assert context.profile_hint == "researcher-robbie"
    # An ERP custom-mission step is not in the built-in composed-action
    # set, so no post-action guard runs and the dispatch surfaces no
    # blocking failures.
    assert failures is None


# ---------------------------------------------------------------------------
# T034 — Built-in software-dev dispatch unchanged
# ---------------------------------------------------------------------------


def _scaffold_software_dev_project(tmp_path: Path) -> tuple[Path, Path, str]:
    """Scaffold a minimal software-dev project with a feature dir.

    Mirrors the helper in
    ``tests/specify_cli/next/test_runtime_bridge_composition.py`` so the
    integration test exercises the same composition gate path WP04
    unit-tested.
    """
    mission_slug = "042-test-feature"
    repo_root = tmp_path / "project"
    _init_min_repo(repo_root)

    (repo_root / ".kittify").mkdir(exist_ok=True)
    # WP04 fail-closed follow-up: the software-dev dispatch path routes
    # through resolve_mission_type_context(), which validates against the
    # project's activated mission types. A bare git-init fixture never ran
    # `spec-kitty init`, so provision the same default charter surface here.
    provision_test_charter(repo_root)

    feature_dir = repo_root / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_type": "software-dev"}),
        encoding="utf-8",
    )
    return repo_root, feature_dir, mission_slug


def _write_wp_file(tasks_dir: Path, wp_id: str) -> Path:
    """Write a minimal WP*.md with 'dependencies:' frontmatter."""
    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Test\ndependencies: []\n---\nbody\n",
        encoding="utf-8",
    )
    return wp_file


def _seed_wp_event_for_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Seed a status event so ``get_wp_lane`` returns ``lane``."""
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    event = StatusEvent(
        event_id=f"test-{wp_id}-{lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def _advance_runtime_to_step(
    repo_root: Path, mission_slug: str, target_step: str
) -> None:
    """Drive the runtime engine until ``issued_step_id == target_step``."""
    from runtime.next.runtime_bridge import get_or_start_run

    run_ref = get_or_start_run(mission_slug, repo_root, "software-dev")
    for _ in range(20):
        snapshot = _read_snapshot(Path(run_ref.run_dir))
        if snapshot.issued_step_id == target_step:
            return
        engine_next_step(
            run_ref, agent_id="test", result="success", emitter=NullEmitter()
        )
    raise RuntimeError(
        f"Could not drive runtime to {target_step!r}; snapshot ="
        f"{_read_snapshot(Path(run_ref.run_dir))!r}"
    )


def test_software_dev_specify_dispatch_unchanged(tmp_path: Path) -> None:
    """FR-010: built-in software-dev dispatch keeps ``profile_hint=None``.

    Re-asserts the WP04 invariant at the integration layer using the same
    composition-fixture pattern as
    ``test_runtime_bridge_composition.py::test_builtin_software_dev_dispatches_with_none_profile_hint``.
    Reuses the identical scaffolding because the existing unit test does
    not run as part of the integration suite. If both are kept in sync,
    a future widening of the gate that accidentally consults the frozen
    template's empty ``agent_profile`` would fail in two places — that is
    by design (FR-010 is a regression trap).
    """
    repo_root, feature_dir, mission_slug = _scaffold_software_dev_project(tmp_path)
    # Lay down the artifacts every composed action's guard wants present so
    # the post-action check passes.
    (feature_dir / "spec.md").write_text("# spec", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# plan", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# tasks", encoding="utf-8")
    tasks = feature_dir / "tasks"
    tasks.mkdir()
    _write_wp_file(tasks, "WP01")
    _seed_wp_event_for_lane(feature_dir, "WP01", "done")

    _advance_runtime_to_step(repo_root, mission_slug, "specify")

    from runtime.next.runtime_bridge import decide_next_via_runtime

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)

    # WP02 / #844: kind=step requires a real prompt_file at construction
    # time (C1/C2). Stage one under tmp_path so the validator passes.
    sentinel_prompt = tmp_path / "sentinel-next.md"
    sentinel_prompt.write_text("# next", encoding="utf-8")
    sentinel_decision = Decision(
        kind=DecisionKind.step,
        agent="test",
        mission_slug=mission_slug,
        mission="software-dev",
        mission_state="next",
        timestamp="2026-04-25T00:00:00+00:00",
        action="next",
        run_id="run-x",
        step_id="next",
        prompt_file=str(sentinel_prompt),
    )

    with (
        patch(
            "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
            return_value=fake_result,
        ) as mock_execute,
        patch(
            "runtime.next.runtime_bridge_engine.advance_run_state_after_composition",
            return_value=sentinel_decision,
        ),
    ):
        decide_next_via_runtime("test", mission_slug, "success", repo_root)

    assert mock_execute.call_count == 1
    call = mock_execute.call_args
    context = call.args[0] if call.args else call.kwargs["context"]
    assert isinstance(context, StepContractExecutionContext)
    # FR-010: built-in software-dev keeps profile_hint=None so the
    # executor's _ACTION_PROFILE_DEFAULTS fallback path is unchanged.
    assert context.profile_hint is None, (
        f"Built-in software-dev dispatch must keep profile_hint=None; "
        f"got {context.profile_hint!r}"
    )
    assert context.mission == "software-dev"
    assert context.action == "specify"


# ---------------------------------------------------------------------------
# Bonus coverage: run_custom_mission start path
# ---------------------------------------------------------------------------


def test_run_custom_mission_starts_runtime_for_erp_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-001 / FR-009: the public surface starts the runtime for ERP.

    Lighter-weight companion to ``test_erp_full_walk`` that proves the
    public ``run_custom_mission`` API itself wires through to the
    runtime bridge for the ERP fixture (the bridge is stubbed so no
    real run state is created). Pinning this here at the integration
    layer guards against a future regression that breaks the bridge
    handoff while leaving the unit-level command happy path green.
    """
    repo_root = _setup_project(tmp_path, fixture="erp-integration")

    fake_run_dir = tmp_path / "runs" / "fake-run-id"
    fake_run_dir.mkdir(parents=True)

    captured: dict[str, object] = {}

    def _fake_get_or_start_run(
        *, mission_slug: str, repo_root: Path, mission_type: str
    ) -> MissionRunRef:
        captured["mission_slug"] = mission_slug
        captured["repo_root"] = repo_root
        captured["mission_type"] = mission_type
        return MissionRunRef(
            run_id="fake-run-id",
            run_dir=str(fake_run_dir),
            mission_key=mission_type,
        )

    from runtime.next import runtime_bridge

    monkeypatch.setattr(runtime_bridge, "get_or_start_run", _fake_get_or_start_run)

    result = run_custom_mission(
        "erp-integration",
        "erp-walk",
        repo_root,
        discovery_context=_isolated_context(repo_root),
    )
    assert result.exit_code == 0, result.envelope
    assert captured["mission_type"] == "erp-integration"
    assert captured["mission_slug"] == "erp-walk"

    # Synthesized contracts registered in the shadow per FR-009.
    registry = get_runtime_contract_registry()
    assert registry.lookup("custom:erp-integration:query-erp") is not None
    assert registry.lookup("custom:erp-integration:create-js") is not None
    # The retrospective marker must NOT have a synthesized contract.
    assert registry.lookup("custom:erp-integration:retrospective") is None
    # The ask-user decision-required gate must NOT have a synthesized contract.
    assert registry.lookup("custom:erp-integration:ask-user") is None


def test_next_dispatch_synthesizes_contract_after_registry_clear(
    tmp_path: Path,
) -> None:
    """Regression: ``mission run`` and ``next`` are separate CLI processes.

    ``mission run`` registers synthesized contracts in a process-local
    registry, but the normal operator flow invokes ``spec-kitty next`` in a
    fresh process. Clearing the registry here simulates that boundary; the
    bridge must recover the custom step contract from the frozen template.
    """
    repo_root = _setup_project(tmp_path / "repo", fixture="erp-integration")
    _init_min_repo(repo_root)

    result = run_custom_mission(
        "erp-integration",
        "erp-walk",
        repo_root,
        discovery_context=_isolated_context(repo_root),
    )
    assert result.exit_code == 0, result.envelope

    # ``decide_next_via_runtime`` expects the tracked feature directory to
    # exist when it builds decisions/prompts.
    (repo_root / "kitty-specs" / "erp-walk").mkdir(parents=True, exist_ok=True)

    # First ``next`` call issues the first step; no composition dispatch yet.
    from runtime.next.runtime_bridge import decide_next_via_runtime

    first = decide_next_via_runtime("test", "erp-walk", "success", repo_root)
    assert first.step_id == "query-erp"

    # Simulate a new CLI process before completing the issued custom step.
    get_runtime_contract_registry().clear()

    fake_result = MagicMock()
    fake_result.invocation_ids = ("inv-001",)
    # WP02 / #844: kind=step requires a real prompt_file at construction
    # time (C1/C2). Stage one under tmp_path so the validator passes.
    sentinel_prompt = tmp_path / "sentinel-lookup-provider.md"
    sentinel_prompt.write_text("# lookup-provider", encoding="utf-8")
    sentinel_decision = Decision(
        kind=DecisionKind.step,
        agent="test",
        mission_slug="erp-walk",
        mission="erp-integration",
        mission_state="lookup-provider",
        timestamp="2026-04-25T00:00:00+00:00",
        action="lookup-provider",
        run_id="run-x",
        step_id="lookup-provider",
        prompt_file=str(sentinel_prompt),
    )

    with (
        patch(
            "specify_cli.mission_step_contracts.executor.StepContractExecutor.execute",
            return_value=fake_result,
        ) as mock_execute,
        patch(
            "runtime.next.runtime_bridge_engine.advance_run_state_after_composition",
            return_value=sentinel_decision,
        ),
    ):
        second = decide_next_via_runtime("test", "erp-walk", "success", repo_root)

    assert second is sentinel_decision
    assert mock_execute.call_count == 1
    call = mock_execute.call_args
    context = call.args[0] if call.args else call.kwargs["context"]
    contract = call.kwargs["contract"]
    assert isinstance(context, StepContractExecutionContext)
    assert context.mission == "erp-integration"
    assert context.action == "query-erp"
    assert context.profile_hint == "researcher-robbie"
    assert contract is not None
    assert contract.id == "custom:erp-integration:query-erp"
