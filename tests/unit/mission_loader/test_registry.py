"""Tests for ``mission_loader.registry`` (R-004, FR-006).

Locks the precedence and lifetime semantics of
:class:`RuntimeContractRegistry`,
:func:`registered_runtime_contracts`, and the
:func:`lookup_contract` repository façade.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import cast
from unittest.mock import MagicMock

import pytest

from charter.offering.missions.step_contracts import (
    MissionStepContract,
    MissionStepContractRepository,
    MissionStepContractStep as MissionStep,
)

from specify_cli.mission_loader.registry import (
    RuntimeContractRegistry,
    get_runtime_contract_registry,
    lookup_contract,
    registered_runtime_contracts,
)
from runtime.next._internal_runtime.schema import (
    MissionMeta,
    MissionTemplate,
    PromptStep,
)


pytestmark = [pytest.mark.unit]

@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Reset the singleton between tests so state never leaks."""
    get_runtime_contract_registry().clear()
    yield
    get_runtime_contract_registry().clear()


def _contract(contract_id: str, action: str = "act", mission: str = "m") -> MissionStepContract:
    return MissionStepContract(
        id=contract_id,
        schema_version="1.0",
        action=action,
        mission=mission,
        steps=[MissionStep(id=f"{action}.execute", description="desc")],
    )


def _template(key: str, step_ids: list[str]) -> MissionTemplate:
    steps = [
        PromptStep(id=sid, title=sid.title(), agent_profile=f"{sid}-profile")
        for sid in step_ids
    ]
    steps.append(PromptStep(id="retrospective", title="Retro"))
    return MissionTemplate(
        mission=MissionMeta(key=key, name="Demo", version="1.0.0"),
        steps=steps,
    )


# --------------------------------------------------------------------------- #
# RuntimeContractRegistry primitives
# --------------------------------------------------------------------------- #


def test_lookup_inside_registers_returns_shadow() -> None:
    registry = get_runtime_contract_registry()
    contract = _contract("custom:m:plan", action="plan")

    registry.register([contract])

    assert registry.lookup("custom:m:plan") is contract


def test_lookup_after_clear_returns_none() -> None:
    registry = get_runtime_contract_registry()
    registry.register([_contract("custom:m:plan", action="plan")])

    registry.clear()

    assert registry.lookup("custom:m:plan") is None


def test_lookup_unregistered_id_returns_none() -> None:
    registry = get_runtime_contract_registry()
    assert registry.lookup("custom:nope:nope") is None


def test_get_runtime_contract_registry_is_singleton() -> None:
    a = get_runtime_contract_registry()
    b = get_runtime_contract_registry()
    assert a is b


def test_register_overwrites_existing_id() -> None:
    registry = get_runtime_contract_registry()
    first = _contract("custom:m:plan", action="plan")
    second = _contract("custom:m:plan", action="plan", mission="other")

    registry.register([first])
    registry.register([second])

    assert registry.lookup("custom:m:plan") is second


# --------------------------------------------------------------------------- #
# registered_runtime_contracts() context manager
# --------------------------------------------------------------------------- #


def test_context_manager_registers_and_unregisters() -> None:
    template = _template("alpha", ["plan"])

    registry = get_runtime_contract_registry()
    assert registry.lookup("custom:alpha:plan") is None

    with registered_runtime_contracts(template):
        assert registry.lookup("custom:alpha:plan") is not None

    assert registry.lookup("custom:alpha:plan") is None


def test_nested_with_blocks() -> None:
    outer = _template("outer", ["plan"])
    inner = _template("inner", ["execute"])

    registry = get_runtime_contract_registry()

    with registered_runtime_contracts(outer):
        assert registry.lookup("custom:outer:plan") is not None
        with registered_runtime_contracts(inner):
            # Both visible inside the inner block.
            assert registry.lookup("custom:outer:plan") is not None
            assert registry.lookup("custom:inner:execute") is not None

        # On inner exit, only the inner contracts disappear.
        assert registry.lookup("custom:outer:plan") is not None
        assert registry.lookup("custom:inner:execute") is None

    # Outer exit clears everything that block added.
    assert registry.lookup("custom:outer:plan") is None
    assert registry.lookup("custom:inner:execute") is None


def test_context_manager_yields_registry() -> None:
    template = _template("alpha", ["plan"])
    with registered_runtime_contracts(template) as yielded:
        assert isinstance(yielded, RuntimeContractRegistry)
        assert yielded is get_runtime_contract_registry()


def test_context_manager_restores_on_exception() -> None:
    template = _template("alpha", ["plan"])
    registry = get_runtime_contract_registry()

    def _fail_inside_registration() -> None:
        with registered_runtime_contracts(template):
            assert registry.lookup("custom:alpha:plan") is not None
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        _fail_inside_registration()

    assert registry.lookup("custom:alpha:plan") is None


# --------------------------------------------------------------------------- #
# lookup_contract() façade
# --------------------------------------------------------------------------- #


def test_lookup_contract_facade_prefers_registry_over_repository() -> None:
    contract = _contract("custom:m:plan", action="plan")
    get_runtime_contract_registry().register([contract])

    repository = MagicMock(spec=MissionStepContractRepository)
    repository.get.return_value = _contract("repo-fallback", action="plan")

    result = lookup_contract("custom:m:plan", cast(MissionStepContractRepository, repository))

    assert result is contract
    repository.get.assert_not_called()


def test_lookup_contract_facade_falls_through_to_repository() -> None:
    repo_contract = _contract("repo:m:plan", action="plan")
    repository = MagicMock(spec=MissionStepContractRepository)
    repository.get.return_value = repo_contract

    result = lookup_contract("repo:m:plan", cast(MissionStepContractRepository, repository))

    assert result is repo_contract
    repository.get.assert_called_once_with("repo:m:plan")


def test_lookup_contract_facade_handles_repository_raise() -> None:
    repository = MagicMock(spec=MissionStepContractRepository)
    repository.get.side_effect = KeyError("unknown")

    result = lookup_contract("missing:id", cast(MissionStepContractRepository, repository))

    assert result is None


def test_lookup_contract_facade_returns_none_when_repository_returns_none() -> None:
    repository = MagicMock(spec=MissionStepContractRepository)
    repository.get.return_value = None

    result = lookup_contract("missing:id", cast(MissionStepContractRepository, repository))

    assert result is None
    repository.get.assert_called_once_with("missing:id")
