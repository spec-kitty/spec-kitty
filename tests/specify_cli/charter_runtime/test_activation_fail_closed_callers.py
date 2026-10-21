"""Former fail-open ``PackContext`` callers now fail closed (WP06: FR-016, FR-017, research D-20, P2).

A malformed activation ledger must not turn into an unfiltered graph (which
would serve denied artifacts). The review gate binding, the mission-step
executor and the charter preflight advisory let ``ActiveCharterConfigError``
propagate, as they already do for ``OrgPackEnvVarUnsetError``. The
CLI-side readers WP06 moves onto the accessors fail closed the same way.

Two malformed ledgers: a non-list allow value, and a valid one plus an unknown
key. Positive control (F15): every case first runs the same caller on the same
fixture with a valid ledger and asserts success.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from charter.activation.pack_context import ActiveCharterConfigError, PackContext
from charter.drg import DRGGraph
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.charter_runtime.preflight import run_charter_preflight
from specify_cli.cli.commands.agent.workflow_executor import implement_check_wp_charter_precondition
from specify_cli.invocation.empty_charter import is_charter_empty
from specify_cli.mission_step_contracts.executor import StepContractExecutor
from specify_cli.review import gate_bindings
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_MALFORMED = {
    "non_list_value": "activated_directives: notalist\n",
    "unknown_key": "activated_tactics:\n  - x\nunknown_key: 1\n",
}


def _project(tmp_path: Path) -> Path:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], activated_agent_profiles=["python-pedro"])
    return tmp_path


def _break_ledger(root: Path, text: str) -> None:
    activation_ledger_path(root).write_text(text, encoding="utf-8")


def _empty_graph(_root: Path) -> DRGGraph:
    return DRGGraph(schema_version="1.0", generated_at="2026-10-20T00:00:00Z", generated_by="test", nodes=[], edges=[])


def _gate_binding_urns(root: Path) -> object:
    return gate_bindings._activated_msc_urns(root, graph_loader=_empty_graph, pack_resolver=None)


def _executor_pack_context(root: Path) -> object:
    executor: Any = StepContractExecutor(repo_root=root, invocation_executor=SimpleNamespace())
    return executor._resolve_pack_context(root)


def _preflight(root: Path) -> object:
    return run_charter_preflight(root)


def _implement_precondition(root: Path) -> object:
    wp: Any = SimpleNamespace(frontmatter="---\nagent_profile: python-pedro\n---\n")
    implement_check_wp_charter_precondition(root, wp, "01")
    return True


CALLERS: dict[str, Callable[[Path], object]] = {
    "review_gate_bindings": _gate_binding_urns,
    "mission_step_executor": _executor_pack_context,
    "charter_preflight": _preflight,
    "implement_precondition": _implement_precondition,
    "empty_charter": is_charter_empty,
}


@pytest.mark.parametrize("malformed", sorted(_MALFORMED))
@pytest.mark.parametrize("caller", sorted(CALLERS))
def test_a_malformed_ledger_fails_closed(tmp_path: Path, caller: str, malformed: str) -> None:
    root = _project(tmp_path)
    call = CALLERS[caller]
    assert call(root) is not None  # positive control: a valid ledger serves

    _break_ledger(root, _MALFORMED[malformed])
    with pytest.raises(ActiveCharterConfigError):
        call(root)


def test_the_executor_positive_control_returns_a_real_pack_context(tmp_path: Path) -> None:
    """Pins that the executor's positive control is a PackContext, not the old ``None`` fallback."""
    assert isinstance(_executor_pack_context(_project(tmp_path)), PackContext)


def test_preflight_keeps_swallowing_a_non_activation_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only activation-store errors propagate; other read faults keep the advisory's never-raise contract."""
    root = _project(tmp_path)

    def boom(_root: Path) -> PackContext:
        raise RuntimeError("boom")

    monkeypatch.setattr(PackContext, "from_config", staticmethod(boom))
    assert not [warning for warning in run_charter_preflight(root).warnings if "built-in default profile" in warning]


_PACK_RESOLVERS: dict[str, Callable[[Path], object]] = {
    "review_gate_bindings": gate_bindings._resolve_pack_context,
    "mission_step_executor": _executor_pack_context,
}


@pytest.mark.parametrize("resolver", sorted(_PACK_RESOLVERS))
def test_a_non_activation_error_still_leaves_the_filter_optional(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resolver: str) -> None:
    """WP06 closeout LOW: only activation-store (and org-pack) errors propagate; any other fault returns ``None``."""
    resolve = _PACK_RESOLVERS[resolver]
    root = _project(tmp_path)
    assert isinstance(resolve(root), PackContext)  # positive control

    def boom(_root: Path) -> PackContext:
        raise RuntimeError("boom")

    monkeypatch.setattr(PackContext, "from_config", staticmethod(boom))
    assert resolve(root) is None
