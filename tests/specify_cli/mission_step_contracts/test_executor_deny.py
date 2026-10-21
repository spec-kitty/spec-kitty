"""The mission-step executor never picks a denied contract (WP06: FR-016, research D-21, P6).

``StepContractExecutor.execute`` gates the contract ``get_by_action`` picks
through ``PackContext.admits``. A denied contract is reported not runnable,
naming ``charter activate mission-step-contract <id>``, before any step is
invoked. The deny matches either spelling: the contract id (the resolver's
key) and the ``<mission>/<action>`` DRG id.

Ledger-seeded.
Positive control (F15): the same fixture runs the contract before the deny.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.mission_step_contracts.executor import (
    StepContractExecutionContext,
    StepContractExecutionError,
    StepContractExecutor,
)
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_MISSION = "software-dev"
_ACTION = "implement"


class _RecordingInvocationExecutor:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, _request_text: str, **_kwargs: object) -> object:
        self.calls += 1
        return SimpleNamespace(invocation_id=f"inv-{self.calls}")

    def complete_invocation(self, _invocation_id: str, *, outcome: str, closed_by: str) -> None:
        assert (outcome, closed_by) == ("done", "agent")


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=[_MISSION])
    return tmp_path


def _execute(root: Path, invoker: Any) -> object:
    executor = StepContractExecutor(repo_root=root, invocation_executor=invoker)
    return executor.execute(StepContractExecutionContext(repo_root=root, mission=_MISSION, action=_ACTION, actor="pytest"))


@pytest.mark.parametrize("spelling", ["implement", f"{_MISSION}/{_ACTION}"])
def test_a_denied_contract_is_not_runnable_and_never_picked(tmp_path: Path, spelling: str) -> None:
    root = _project(tmp_path)
    ran = _RecordingInvocationExecutor()
    _execute(root, ran)
    assert ran.calls > 0  # positive control: the contract runs before the deny

    seed_activation_ledger(root, deactivated_mission_step_contracts=[spelling])
    blocked = _RecordingInvocationExecutor()
    with pytest.raises(StepContractExecutionError, match="charter activate mission-step-contract implement"):
        _execute(root, blocked)
    assert blocked.calls == 0


def test_an_allow_list_without_the_contract_is_not_runnable(tmp_path: Path) -> None:
    root = _project(tmp_path)
    seed_activation_ledger(root, activated_mission_step_contracts=["implement"])
    ran = _RecordingInvocationExecutor()
    _execute(root, ran)
    assert ran.calls > 0

    seed_activation_ledger(root, activated_mission_step_contracts=["plan"])
    with pytest.raises(StepContractExecutionError, match="not runnable"):
        _execute(root, _RecordingInvocationExecutor())
