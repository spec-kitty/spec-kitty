"""Consumer contract for spec-kitty-events.

Pins the subset of the events public surface that CLI uses. Upstream
contract changes (renaming or removing pinned symbols, or shifting their
shape) MUST break this test, per FR-005 / FR-009 / C-003 of mission
``shared-package-boundary-cutover-01KQ22DS``.

The pinned surface is documented in
``kitty-specs/shared-package-boundary-cutover-01KQ22DS/contracts/events_consumer_surface.md``.

Each pinned symbol corresponds to a real CLI usage in production code; the
list was derived by grep over ``src/`` on the post-WP04 tree:

* ``src/specify_cli/decisions/emit.py``
* ``src/specify_cli/glossary/events.py``
* ``src/specify_cli/sync/diagnose.py``
* ``src/specify_cli/sync/emitter.py``
* ``src/specify_cli/status/validate.py``
* ``src/specify_cli/events/adapter.py``
* ``src/specify_cli/next/_internal_runtime/events.py``
* ``src/specify_cli/next/_internal_runtime/engine.py``
* ``src/specify_cli/next/_internal_runtime/schema.py``

If WP02 / WP04 / future work changes which events symbols CLI uses, update
both the contract doc and this test in the same PR.
"""
from __future__ import annotations

import importlib
import inspect

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast]


# ---------------------------------------------------------------------------
# Top-level package surface (``import spec_kitty_events as X``)
# ---------------------------------------------------------------------------

_TOP_LEVEL_SYMBOLS = (
    # Core data model
    "Event",
    "ErrorEntry",
    "ConflictResolution",
    # Helpers
    "normalize_event_id",
    # Clock surface (adapter.py no longer wraps it; still part of the pinned contract)
    "LamportClock",
    "InMemoryClockStorage",
    # Event-store surface
    "EventStore",
    "InMemoryEventStore",
)


@pytest.mark.parametrize("symbol_name", _TOP_LEVEL_SYMBOLS)
def test_top_level_symbol_exists(symbol_name: str) -> None:
    """FR-009: Each pinned top-level symbol must resolve at the documented path."""
    module = importlib.import_module("spec_kitty_events")
    assert hasattr(module, symbol_name), (
        f"spec_kitty_events.{symbol_name} is missing. "
        f"This breaks CLI imports in mission "
        f"shared-package-boundary-cutover-01KQ22DS. "
        f"Either upstream events removed the symbol (file an upstream issue) "
        f"or CLI no longer needs it (remove from this contract and update "
        f"contracts/events_consumer_surface.md)."
    )


# ---------------------------------------------------------------------------
# Sub-module surface
# ---------------------------------------------------------------------------

_SUBMODULE_SYMBOLS = (
    # (module, symbol_name) — derived from real CLI imports
    # decisionpoint (decisions/emit.py)
    ("spec_kitty_events.decisionpoint", "DECISION_POINT_OPENED"),
    ("spec_kitty_events.decisionpoint", "DECISION_POINT_RESOLVED"),
    ("spec_kitty_events.decisionpoint", "DecisionPointOpenedInterviewPayload"),
    # decision_moment (decisions/emit.py)
    ("spec_kitty_events.decision_moment", "OriginFlow"),
    ("spec_kitty_events.decision_moment", "OriginSurface"),
    ("spec_kitty_events.decision_moment", "TerminalOutcome"),
    # mission_next (next/_internal_runtime/*)
    ("spec_kitty_events.mission_next", "DECISION_INPUT_ANSWERED"),
    ("spec_kitty_events.mission_next", "DECISION_INPUT_REQUESTED"),
    ("spec_kitty_events.mission_next", "MISSION_RUN_COMPLETED"),
    ("spec_kitty_events.mission_next", "DecisionInputAnsweredPayload"),
    ("spec_kitty_events.mission_next", "DecisionInputRequestedPayload"),
    ("spec_kitty_events.mission_next", "MissionRunCompletedPayload"),
    ("spec_kitty_events.mission_next", "RuntimeActorIdentity"),
)


@pytest.mark.parametrize("module_name,symbol_name", _SUBMODULE_SYMBOLS)
def test_submodule_symbol_exists(module_name: str, symbol_name: str) -> None:
    """FR-009: Each pinned sub-module symbol must resolve at the documented path."""
    module = importlib.import_module(module_name)
    assert hasattr(module, symbol_name), (
        f"{module_name}.{symbol_name} is missing in spec-kitty-events. "
        "Update the consumer contract (and "
        "contracts/events_consumer_surface.md) or fix the upstream surface."
    )


# ---------------------------------------------------------------------------
# Callable / structural shape (matches CLI's actual usage shape)
# ---------------------------------------------------------------------------


def test_normalize_event_id_signature() -> None:
    """``normalize_event_id`` must accept at least one positional argument.

    CLI calls (sync/emitter.py, status/validate.py): ``normalize_event_id(value)``.
    """
    from spec_kitty_events import normalize_event_id

    sig = inspect.signature(normalize_event_id)
    params = list(sig.parameters)
    assert len(params) >= 1, (
        f"spec_kitty_events.normalize_event_id signature changed: {sig}. "
        "CLI passes a single positional argument."
    )


def test_event_class_pydantic_shape() -> None:
    """``Event`` must expose ``model_dump`` (Pydantic v2 surface).

    CLI's sync emitter (``sync/emitter.py``) relies on this for envelope
    serialization.
    """
    from spec_kitty_events import Event

    assert hasattr(Event, "model_dump"), (
        "spec_kitty_events.Event no longer exposes Pydantic model_dump(). "
        "CLI's sync emitter relies on this surface — adapt CLI or restore "
        "the upstream method."
    )


def test_validate_strict_envelope_is_callable() -> None:
    """``strict.validate_strict_envelope`` must be callable.

    The envelope-level cutover gate (``CUTOVER_ARTIFACT``,
    ``assert_canonical_cutover_signal``) was deleted in spec-kitty-events
    8.0.0; fail-closed envelope gating was re-homed onto the strict profile
    (upstream COMPATIBILITY.md, ``8.0.0``). CLI's FR-018-style verification
    follows it there.
    """
    from spec_kitty_events.strict import validate_strict_envelope

    assert callable(validate_strict_envelope), (
        "spec_kitty_events.strict.validate_strict_envelope is no longer "
        "callable. CLI's fail-closed envelope verification relies on this "
        "surface."
    )


def test_forbidden_keys_walk_is_callable() -> None:
    """``forbidden_keys.find_forbidden_keys`` must be callable.

    The recursive forbidden-key walk moved with the cutover gate's removal;
    the strict profile composes it, and audit classifiers call it directly.
    """
    from spec_kitty_events.forbidden_keys import find_forbidden_keys

    assert callable(find_forbidden_keys), (
        "spec_kitty_events.forbidden_keys.find_forbidden_keys is no longer "
        "callable. CLI's fail-closed envelope verification relies on this "
        "surface."
    )
