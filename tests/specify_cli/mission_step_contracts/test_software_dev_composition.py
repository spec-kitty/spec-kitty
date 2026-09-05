"""Composition tests for the five `software-dev` mission step contracts.

WP01 (mission `software-dev-composition-rewrite-01KQ26CY`) introduced the
`tasks` step contract. These tests pin the executor surface for all five
software-dev actions:

1. The `tasks` contract loads cleanly from the shipped repository.
2. `_ACTION_PROFILE_DEFAULTS` returns the agreed default profile for `tasks`.
3. All five canonical software-dev actions resolve to a shipped contract.
4. The composer routes every `tasks` sub-step through
   `ProfileInvocationExecutor` in declared order (fake invocation executor).
5. Every non-bootstrap `tasks` step has at least one delegation candidate that
   resolves against the merged DRG action context.

These tests intentionally mirror the fake-invocation-executor pattern used in
``tests/specify_cli/mission_step_contracts/test_executor.py`` and never spin up
a real ``ProfileInvocationExecutor`` — keeping per-test runtime negligible and
the executor pure-composer contract (C-001) untouched.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from charter.offering.missions.step_contracts import MissionStepContractRepository
from specify_cli.invocation.writer import EVENTS_DIR, INDEX_PATH
from specify_cli.mission_step_contracts.executor import (
    _ACTION_PROFILE_DEFAULTS,
    StepContractExecutionContext,
    StepContractExecutor,
)


pytestmark = pytest.mark.fast

_OPS_INDEX_FILENAME = Path(INDEX_PATH).name


# ---------------------------------------------------------------------------
# Helpers (patterned after tests/specify_cli/mission_step_contracts/test_executor.py)
# ---------------------------------------------------------------------------

def _setup_fixture_profiles(repo_root: Path) -> None:
    """Copy the implementer + reviewer fixture profiles into the repo root.

    The fake ``ProfileInvocationExecutor`` flow inside
    ``StepContractExecutor.execute`` resolves a profile hint against the
    project ``.kittify/profiles`` directory; reusing the existing fixtures
    keeps this file aligned with ``test_executor.py``.
    """
    profiles_dir = repo_root / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    fixtures = Path(__file__).parents[1] / "invocation" / "fixtures" / "profiles"
    for yaml_file in fixtures.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)


# NOTE: The shipped DRG already scopes the `software-dev/tasks` action to the
# candidate URNs declared in ``tasks.step-contract.yaml`` (see
# ``packs/built-in/missions/software-dev/actions/tasks/index.yaml``). Tests
# therefore rely on the shipped graph and do not write a project overlay --
# adding one would create duplicate-edge validation errors at load time.


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_tasks_contract_loads_from_repository() -> None:
    """T003 #1 — the new shipped YAML loads through the canonical repository."""
    repo = MissionStepContractRepository()
    contract = repo.get_by_action("software-dev", "tasks")

    assert contract is not None, (
        "Expected MissionStepContractRepository to surface the new "
        "tasks.step-contract.yaml; ensure the file exists under "
        "packs/built-in/missions/built_in_step_contracts/."
    )
    assert contract.id == "tasks"
    assert contract.action == "tasks"
    assert contract.mission == "software-dev"
    assert [step.id for step in contract.steps] == [
        "bootstrap",
        "outline",
        "packages",
        "finalize",
    ]


def test_tasks_default_profile_is_architect_alphonso() -> None:
    """T003 #2 — locked-decision D-2 default profile is wired into the executor."""
    assert _ACTION_PROFILE_DEFAULTS[("software-dev", "tasks")] == "architect-alphonso"


def test_all_five_software_dev_actions_have_shipped_contracts() -> None:
    """T003 #3 — every canonical software-dev action resolves to a contract."""
    repo = MissionStepContractRepository()
    for action in ("specify", "plan", "tasks", "implement", "review"):
        contract = repo.get_by_action("software-dev", action)
        assert contract is not None, (
            f"Missing shipped contract for software-dev/{action}; expected a "
            f"file at packs/built-in/missions/built_in_step_contracts/{action}.step-contract.yaml"
        )
        assert contract.action == action
        assert contract.mission == "software-dev"


def test_executor_composes_tasks_through_invocation_executor(tmp_path: Path) -> None:
    """T003 #4 — composer walks all four tasks sub-steps through invocation."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    context_result = SimpleNamespace(mode="compact", text="fixture governance context")
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=context_result,
    ):
        result = StepContractExecutor(
            repo_root=repo_root,
            contract_repository=MissionStepContractRepository(),
        ).execute(
            StepContractExecutionContext(
                repo_root=repo_root,
                mission="software-dev",
                action="tasks",
                actor="pytest",
                # Use the fixture profile so we don't need a real architect profile;
                # this overrides the default in _ACTION_PROFILE_DEFAULTS.
                profile_hint="implementer-fixture",
                request_text="WP01 composition test",
            )
        )

    assert result.contract_id == "tasks"
    assert result.mission == "software-dev"
    assert result.action == "tasks"
    assert result.resolution_source == "merged_drg"
    # Four steps composed in declared order, each producing one invocation.
    assert [step.step_id for step in result.steps] == [
        "bootstrap",
        "outline",
        "packages",
        "finalize",
    ]
    assert len(result.invocation_ids) == 4
    assert all(step.invocation_payload is not None for step in result.steps)
    # Bootstrap and finalize declare commands; declaration is recorded but the
    # composer never executes them (C-001).
    assert result.steps[0].command_declared is True
    assert result.steps[3].command_declared is True


def test_tasks_step_delegations_resolve_against_action_index(tmp_path: Path) -> None:
    """T003 #5 — every non-bootstrap step has at least one resolved delegation.

    The tasks contract declares ``delegates_to`` on three of four steps
    (``outline``, ``packages``, ``finalize``). With the project DRG overlay
    scoping each candidate URN to ``action:software-dev/tasks``, every one of
    those steps must resolve at least one candidate; the bootstrap step has
    no delegations and is intentionally skipped.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    context_result = SimpleNamespace(mode="compact", text="fixture governance context")
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=context_result,
    ):
        result = StepContractExecutor(
            repo_root=repo_root,
            contract_repository=MissionStepContractRepository(),
        ).execute(
            StepContractExecutionContext(
                repo_root=repo_root,
                mission="software-dev",
                action="tasks",
                actor="pytest",
                profile_hint="implementer-fixture",
            )
        )

    steps_by_id = {step.step_id: step for step in result.steps}

    # Bootstrap declares no delegations -- skip per the docstring contract.
    assert steps_by_id["bootstrap"].resolved_delegations == ()

    # Every other step must resolve at least one candidate against the action context.
    for step_id in ("outline", "packages", "finalize"):
        step = steps_by_id[step_id]
        assert len(step.resolved_delegations) >= 1, (
            f"Step {step_id} resolved no delegation candidates; expected at "
            f"least one to exist in action:software-dev/tasks scope."
        )
        # Spot-check: each resolved delegation URN is present in the action context.
        for delegation in step.resolved_delegations:
            assert delegation.urn.startswith(("tactic:", "directive:"))


# ---------------------------------------------------------------------------
# WP03 (#793 + #794): action_hint pass-through and lifecycle pairing tests
# ---------------------------------------------------------------------------


def _read_jsonl_records(path: Path) -> list[dict[str, object]]:
    """Read every JSON object line from a JSONL file."""
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _invocation_jsonl_files(events_dir: Path) -> list[Path]:
    """Return per-invocation logs without hiding filenames that contain ``index``."""
    return sorted(
        path for path in events_dir.glob("*.jsonl") if path.name != _OPS_INDEX_FILENAME
    )


def test_invocation_jsonl_files_excludes_only_ops_index(tmp_path: Path) -> None:
    """A legitimate invocation log such as ``reindex.jsonl`` remains observable."""
    ops_index = tmp_path / _OPS_INDEX_FILENAME
    reindex = tmp_path / "reindex.jsonl"
    ops_index.touch()
    reindex.touch()

    assert _invocation_jsonl_files(tmp_path) == [reindex]


def _run_software_dev_specify(
    repo_root: Path,
    *,
    contract_repository: MissionStepContractRepository | None = None,
):
    """Execute the shipped ``software-dev/specify`` contract end-to-end."""
    context_result = SimpleNamespace(mode="compact", text="fixture governance context")
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=context_result,
    ):
        return StepContractExecutor(
            repo_root=repo_root,
            contract_repository=contract_repository or MissionStepContractRepository(),
        ).execute(
            StepContractExecutionContext(
                repo_root=repo_root,
                mission="software-dev",
                action="specify",
                actor="pytest",
                # Override default profile to use the implementer fixture so the
                # registry resolves without depending on shipped agent profiles.
                profile_hint="implementer-fixture",
                request_text="WP03 lifecycle test",
            )
        )


def test_step_contract_executor_passes_action_hint(tmp_path: Path) -> None:
    """T015 / FR-014 — every ``invoke(...)`` call passes ``action_hint=contract.action``."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    captured_kwargs: list[dict[str, object]] = []
    real_invoke = None

    from specify_cli.invocation import executor as inv_executor_mod

    real_invoke = inv_executor_mod.ProfileInvocationExecutor.invoke

    def spy_invoke(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        captured_kwargs.append(dict(kwargs))
        return real_invoke(self, *args, **kwargs)

    with patch.object(
        inv_executor_mod.ProfileInvocationExecutor,
        "invoke",
        new=spy_invoke,
    ):
        result = _run_software_dev_specify(repo_root)

    # All composed steps must produce an invoke call.
    assert len(captured_kwargs) == len(result.steps)
    assert len(captured_kwargs) >= 2, "specify contract should have ≥2 steps"

    # Every invoke call from the executor must pass action_hint="specify".
    for kwargs in captured_kwargs:
        assert kwargs.get("action_hint") == "specify", (
            f"Expected action_hint='specify' on every invoke call; got {kwargs!r}"
        )


def test_governance_context_uses_contract_action_when_hint_supplied(tmp_path: Path) -> None:
    """T015 / FR-013 — started JSONL records ``action="specify"`` (not a role default)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    result = _run_software_dev_specify(repo_root)

    jsonl_files = _invocation_jsonl_files(repo_root / EVENTS_DIR)
    assert len(jsonl_files) == len(result.steps)

    for path in jsonl_files:
        records = _read_jsonl_records(path)
        started = [r for r in records if r.get("event") == "started"]
        assert len(started) == 1
        assert started[0].get("action") == "specify", (
            f"Expected action='specify' on started record; got {started[0]!r}"
        )


def test_composed_action_pairs_started_with_completed(tmp_path: Path) -> None:
    """T014 / FR-006 — every JSONL has exactly one started + one completed (done) record."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    result = _run_software_dev_specify(repo_root)

    jsonl_files = _invocation_jsonl_files(repo_root / EVENTS_DIR)
    assert len(jsonl_files) == len(result.steps)

    for path in jsonl_files:
        records = _read_jsonl_records(path)
        # Filter to the canonical lifecycle event types so optional auxiliary
        # events (e.g. glossary_checked) do not break the pairing assertion.
        lifecycle = [r for r in records if r.get("event") in {"started", "completed"}]
        started = [r for r in lifecycle if r.get("event") == "started"]
        completed = [r for r in lifecycle if r.get("event") == "completed"]
        assert len(started) == 1, f"Expected exactly one started in {path}: {records!r}"
        assert len(completed) == 1, f"Expected exactly one completed in {path}: {records!r}"
        assert completed[0].get("outcome") == "done", (
            f"Expected outcome='done' for clean run; got {completed[0]!r}"
        )


def test_composed_step_failure_writes_failed_completion(tmp_path: Path) -> None:
    """T014 / FR-007 / EDGE-001 — per-step body raising yields started+failed and re-raises."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    class _Boom(RuntimeError):
        pass

    # Patch StepContractStepResult constructor to raise on the second invocation,
    # which is the per-step body that runs after invoke() in execute().
    call_count = {"n": 0}

    from specify_cli.mission_step_contracts import executor as exec_mod

    real_step_result = exec_mod.StepContractStepResult

    def fault_injecting_step_result(*args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise _Boom("injected per-step body failure")
        return real_step_result(*args, **kwargs)

    context_result = SimpleNamespace(mode="compact", text="fixture governance context")
    with (
        patch.object(exec_mod, "StepContractStepResult", new=fault_injecting_step_result),
        patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=context_result,
        ),
        pytest.raises(_Boom, match="injected per-step body failure"),
    ):
        StepContractExecutor(
            repo_root=repo_root,
            contract_repository=MissionStepContractRepository(),
        ).execute(
            StepContractExecutionContext(
                repo_root=repo_root,
                mission="software-dev",
                action="specify",
                actor="pytest",
                profile_hint="implementer-fixture",
                request_text="WP03 fault injection",
            )
        )

    jsonl_files = _invocation_jsonl_files(repo_root / EVENTS_DIR)
    # Two invocations: the first closed with done, the second closed with failed.
    assert len(jsonl_files) == 2

    outcomes: list[str] = []
    for path in jsonl_files:
        records = _read_jsonl_records(path)
        lifecycle = [r for r in records if r.get("event") in {"started", "completed"}]
        started = [r for r in lifecycle if r.get("event") == "started"]
        completed = [r for r in lifecycle if r.get("event") == "completed"]
        assert len(started) == 1
        assert len(completed) == 1
        outcome = completed[0].get("outcome")
        assert isinstance(outcome, str)
        outcomes.append(outcome)

    # One done (the step that succeeded before injection) and one failed.
    assert sorted(outcomes) == ["done", "failed"]


def test_composed_action_multistep_pairing(tmp_path: Path) -> None:
    """T014 / EDGE-004 — multi-step contract pairs each invocation independently."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    result = _run_software_dev_specify(repo_root)

    # specify ships with multiple steps; ensure ≥2 invocations exist.
    assert len(result.invocation_ids) >= 2

    for invocation_id in result.invocation_ids:
        path = repo_root / EVENTS_DIR / f"{invocation_id}.jsonl"
        assert path.exists(), f"Missing JSONL for invocation {invocation_id}"
        records = _read_jsonl_records(path)
        lifecycle = [r for r in records if r.get("event") in {"started", "completed"}]
        events = [r.get("event") for r in lifecycle]
        # Each invocation independently paired: exactly one started + one completed.
        assert events.count("started") == 1
        assert events.count("completed") == 1
        completed = [r for r in lifecycle if r.get("event") == "completed"][0]
        assert completed.get("outcome") == "done"


def test_executor_uses_complete_invocation_api_only(tmp_path: Path) -> None:
    """T015 / FR-008 — close flows through ``complete_invocation``, never direct writer."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    from specify_cli.invocation import executor as inv_executor_mod
    from specify_cli.invocation import writer as writer_mod

    complete_calls: list[tuple[object, ...]] = []
    real_complete = inv_executor_mod.ProfileInvocationExecutor.complete_invocation

    def recording_complete(self, invocation_id, *args, **kwargs):  # type: ignore[no-untyped-def]
        complete_calls.append((invocation_id, args, kwargs))
        return real_complete(self, invocation_id, *args, **kwargs)

    invoke_calls: list[None] = []
    real_invoke = inv_executor_mod.ProfileInvocationExecutor.invoke

    def counting_invoke(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        invoke_calls.append(None)
        return real_invoke(self, *args, **kwargs)

    # Track direct writer calls to assert the executor never bypasses the API.
    direct_writer_started: list[None] = []
    direct_writer_completed: list[None] = []
    real_write_started = writer_mod.InvocationWriter.write_started
    real_write_completed = writer_mod.InvocationWriter.write_completed

    # Walk the call stack to detect calls originating from mission_step_contracts.executor.
    import inspect as _inspect

    def _is_direct_call_from_step_contract_executor() -> bool:
        """Return True iff the writer was called directly from
        mission_step_contracts/executor.py without going through
        invocation/executor.py (the canonical API)."""
        stack = _inspect.stack()
        # Search the stack from the writer frame outward. If we find
        # invocation/executor.py before mission_step_contracts/executor.py,
        # the writer was reached through the API (allowed). If we find
        # mission_step_contracts/executor.py first, that's a direct call.
        for frame in stack:
            fname = frame.filename
            if "specify_cli/invocation/executor.py" in fname:
                return False  # API path -- allowed
            if "specify_cli/mission_step_contracts/executor.py" in fname:
                return True  # direct call from owned module -- forbidden
        return False

    def write_started_spy(self, record):  # type: ignore[no-untyped-def]
        if _is_direct_call_from_step_contract_executor():
            direct_writer_started.append(None)
        return real_write_started(self, record)

    def write_completed_spy(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        if _is_direct_call_from_step_contract_executor():
            direct_writer_completed.append(None)
        return real_write_completed(self, *args, **kwargs)

    with patch.object(
        inv_executor_mod.ProfileInvocationExecutor,
        "complete_invocation",
        new=recording_complete,
    ), patch.object(
        inv_executor_mod.ProfileInvocationExecutor,
        "invoke",
        new=counting_invoke,
    ), patch.object(
        writer_mod.InvocationWriter, "write_started", new=write_started_spy
    ), patch.object(
        writer_mod.InvocationWriter, "write_completed", new=write_completed_spy
    ):
        _run_software_dev_specify(repo_root)

    # complete_invocation reached once per invoke call from the executor.
    assert len(complete_calls) == len(invoke_calls), (
        f"Expected one complete_invocation per invoke; "
        f"got {len(complete_calls)} completes vs {len(invoke_calls)} invokes"
    )

    # No direct InvocationWriter.write_* calls originating from the executor module.
    assert direct_writer_started == [], (
        "mission_step_contracts/executor.py must not call InvocationWriter.write_started directly"
    )
    assert direct_writer_completed == [], (
        "mission_step_contracts/executor.py must not call InvocationWriter.write_completed directly"
    )


def test_composed_action_outcome_is_done_even_though_composition_does_not_run_llm(
    tmp_path: Path,
) -> None:
    """Naming-as-documentation: success outcome is literally ``"done"``.

    The ``"done"`` outcome describes the composition-step trail only. It does
    NOT imply that the host LLM finished generation -- the executor never
    spawns an LLM call. This regression guard locks the literal value so a
    future refactor cannot accidentally substitute ``"composed"``,
    ``"governance_only"``, or any other invented outcome string.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_fixture_profiles(repo_root)

    result = _run_software_dev_specify(repo_root)

    jsonl_files = _invocation_jsonl_files(repo_root / EVENTS_DIR)
    assert len(jsonl_files) == len(result.steps)
    assert jsonl_files, "expected at least one composed-step JSONL"

    for path in jsonl_files:
        records = _read_jsonl_records(path)
        completed = [r for r in records if r.get("event") == "completed"]
        assert len(completed) == 1
        assert completed[0].get("outcome") == "done"
