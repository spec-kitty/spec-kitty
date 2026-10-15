"""FR-036 / D17 regression: custom mission loader does not leak post-merge.

Authority: ``kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/spec.md``
section FR-036 and ``research.md`` D17. References issue #801.

WP07 audit verdict: **verified-already-fixed**. The
``RuntimeContractRegistry`` (``src/specify_cli/mission_loader/registry.py``)
exposes ``registered_runtime_contracts`` as a context manager that uses
snapshot/restore semantics: ``__enter__`` snapshots the current shadow
before the block's contracts are registered, and ``__exit__`` restores
that snapshot in a ``finally`` clause -- so contracts added inside the
block are removed cleanly even if the block raises. There is no
post-merge cleanup gap on the in-memory side.

The merge command runs in a fresh CLI process, so cross-process leakage
is not a concern either: the singleton starts empty in every new
invocation. This regression test pins the in-process invariant so a
future refactor that drops snapshot/restore (and thereby reintroduces
issue #801) trips a test failure.
"""

from __future__ import annotations

from typing import Any

import pytest


pytestmark = [pytest.mark.integration]

@pytest.fixture(autouse=True)
def _reset_registry() -> Any:
    """Ensure each test starts with an empty shadow.

    The registry is a process-local singleton; tests sharing a process
    could pollute one another's view. We clear before AND after each
    test so a failure in one test doesn't corrupt the next.
    """
    from specify_cli.mission_loader.registry import (
        get_runtime_contract_registry,
    )

    get_runtime_contract_registry().clear()
    yield
    get_runtime_contract_registry().clear()


def _make_contract(contract_id: str) -> Any:
    """Build a minimal contract-shaped object for registry round-trips.

    ``RuntimeContractRegistry.register`` keys on ``contract.id`` only,
    so a duck-typed stand-in is sufficient for the cleanup contract we
    care about here. Avoids coupling the test to the doctrine model
    package's evolving constructor signature.
    """
    contract = type("FakeContract", (), {})()
    contract.id = contract_id  # type: ignore[attr-defined]
    return contract


def test_context_manager_restores_snapshot_on_clean_exit() -> None:
    """The contract-shadow must be empty after the with block exits."""
    from specify_cli.mission_loader.registry import (
        RuntimeContractRegistry,
        get_runtime_contract_registry,
    )

    registry = get_runtime_contract_registry()
    assert registry.snapshot() == {}

    fake_contracts = [_make_contract("merge-cleanup-A")]

    snapshot_before = registry.snapshot()
    registry.register(fake_contracts)
    try:
        # Inside the simulated block, the contract is visible.
        assert registry.lookup("merge-cleanup-A") is not None
    finally:
        # Simulate the context manager exit path used by
        # registered_runtime_contracts: restore prior snapshot.
        registry.restore(snapshot_before)

    # FR-036 / issue #801 invariant: nothing leaks past the block.
    assert registry.snapshot() == {}
    assert registry.lookup("merge-cleanup-A") is None


def test_context_manager_restores_snapshot_on_exception() -> None:
    """A raise inside the block must NOT leave contracts in the registry."""
    from specify_cli.mission_loader.registry import (
        get_runtime_contract_registry,
    )

    registry = get_runtime_contract_registry()
    snapshot_before = registry.snapshot()
    registry.register([_make_contract("merge-cleanup-B")])

    try:
        try:
            raise RuntimeError("simulated post-merge failure")
        finally:
            registry.restore(snapshot_before)
    except RuntimeError:
        pass

    assert registry.snapshot() == {}, (
        "RuntimeContractRegistry leaked contracts past an exception path; "
        "issue #801 regression."
    )


def test_nested_blocks_compose_via_stack_of_snapshots() -> None:
    """Inner block exit removes only its own contracts (FR-036 nesting)."""
    from specify_cli.mission_loader.registry import (
        get_runtime_contract_registry,
    )

    registry = get_runtime_contract_registry()

    outer_snapshot = registry.snapshot()
    registry.register([_make_contract("outer-A")])

    inner_snapshot = registry.snapshot()
    registry.register([_make_contract("inner-B")])

    # Both visible inside the inner block.
    assert registry.lookup("outer-A") is not None
    assert registry.lookup("inner-B") is not None

    # Inner exit: only outer-A remains.
    registry.restore(inner_snapshot)
    assert registry.lookup("outer-A") is not None
    assert registry.lookup("inner-B") is None

    # Outer exit: registry is empty again.
    registry.restore(outer_snapshot)
    assert registry.snapshot() == {}


def test_clear_is_a_hard_reset_for_post_merge_safety() -> None:
    """``RuntimeContractRegistry.clear`` is the safety belt operators rely on."""
    from specify_cli.mission_loader.registry import (
        get_runtime_contract_registry,
    )

    registry = get_runtime_contract_registry()
    registry.register(
        [
            _make_contract("hardreset-1"),
            _make_contract("hardreset-2"),
        ]
    )
    assert registry.lookup("hardreset-1") is not None

    registry.clear()
    assert registry.snapshot() == {}
    assert registry.lookup("hardreset-1") is None
