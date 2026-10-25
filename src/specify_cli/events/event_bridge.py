"""Local file adapter behind the EventBridge port (#6603, ADR 2026-10-14-1 D-1, D-2).

The three work package transition doors (``status.emit._persist_prepared``,
``status.emit.emit_status_transition_batch`` and
``coordination.transaction.BookkeepingTransaction.append_events``) build a
:class:`~runtime.next.event_bridge.WorkPackageTransition` and hand it to
:func:`work_package_transition_port`. With no adapter bound, which is the
open-core default, that is :class:`LocalFileEventBridge`. It writes the unit
through the same store primitives the doors used before, so the bytes,
ordering and readback verification are unchanged.

This adapter is where the store's raw append primitives become private to the
bridge (ADR 2026-10-14-1 D-1). At the handover it is replaced by the client of
the Java write service (#6675, #6193), behind the same port. It holds no
transport and validates nothing beyond the row types it can persist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from runtime.next.event_bridge import (
    WorkPackageTransition,
    WorkPackageTransitionPort,
    bound_work_package_transition_port,
)

if TYPE_CHECKING:
    from specify_cli.status import InnerStateChanged, StatusEvent

# The status facade is imported inside the functions: ``specify_cli.status``
# loads ``status.emit``, which calls this adapter, so a module-level import
# would be a cycle.

# Only names another src/ module imports are exported; the rest stay importable (tests use them).
__all__ = [
    "work_package_transition_port",
]


class LocalFileEventBridge:
    """Write a work package transition to the Mission's ``status.events.jsonl``.

    A coordination write contract (``EventLogWriteContract``) goes through the
    coordination wrapper, which first verifies the contract against the write
    location. Without a contract, the flat shells' direct append is used.
    Either way the unit lands in one atomic, read-back-verified append, or the
    store's error propagates.
    """

    def record_work_package_transition(self, transition: WorkPackageTransition) -> None:
        rows = _persistable_rows(transition)
        contract = transition.write_contract
        if contract is None:
            # Looked up on the module at call time, so a test that observes the
            # durability append (``tests/status/test_emit_durability.py``) sees it.
            from specify_cli.status import _unsafe

            _unsafe.append_event_stream_atomic_verified(transition.write_location, rows)
            return
        from specify_cli.coordination.status_service import EventLogWriteContract, append_event_stream_log

        if not isinstance(contract, EventLogWriteContract):
            raise TypeError(f"unsupported write contract {type(contract).__name__}; expected EventLogWriteContract or None")
        if contract.feature_dir != transition.write_location:
            raise ValueError(f"write contract targets {contract.feature_dir}, but the transition's write location is {transition.write_location}")
        append_event_stream_log(contract, rows)


def _persistable_rows(transition: WorkPackageTransition) -> list[StatusEvent | InnerStateChanged]:
    from specify_cli.status import InnerStateChanged, StatusEvent

    rows: list[StatusEvent | InnerStateChanged] = []
    for row in transition.rows:
        if not isinstance(row, StatusEvent | InnerStateChanged):
            raise TypeError(f"the local file adapter persists StatusEvent and InnerStateChanged rows, not {type(row).__name__}")
        rows.append(row)
    return rows


_DEFAULT_PORT = LocalFileEventBridge()


def work_package_transition_port() -> WorkPackageTransitionPort:
    """Return the bound EventBridge adapter, or the local file adapter when none is bound."""
    return bound_work_package_transition_port() or _DEFAULT_PORT
