"""The EventBridge port: the one interface the domain records its facts through.

ADR 2026-10-14-1 D-2, as amended by ADR 2026-10-22-1: the run loop and the
lane state machine depend on a port, not on the writer. The port grows
:class:`~runtime.next._internal_runtime.events.RuntimeEventEmitter` rather
than duplicating it. ``EventBridgePort``, defined beside that emitter, is the
emitter's Mission state advance entry points plus the work package transition
entry point that this module defines (:class:`WorkPackageTransitionPort`).

This module imports only the standard library, and must keep doing so. The
transition doors in ``specify_cli.status.emit`` import it, and importing
``runtime.next._internal_runtime`` loads the engine, which loads
``specify_cli.status.emit``: a cycle.

The adapter is bound at the composition root. Open-core binds none: the
transition doors fall back to the local file adapter in
``specify_cli.events.event_bridge``, which writes through today's store
primitives. The client of the Java write service (#6675, #6193) is a later
adapter behind this same port; nothing here has a transport.

During the strangler, the CLI still resolves where a transition lands
(ADR 2026-10-22-1 D-3), so a :class:`WorkPackageTransition` carries the
resolved write location and the CLI's write contract beside its rows. The
domain treats the contract as opaque; the adapter verifies it.

The unit is the append only. The coordination shell still materializes,
commits and, on failure, cuts the log in process around the port call, and
``emit_inner_state_changed`` still appends standalone annotations without it.
ADR 2026-10-22-1 makes append, status commit and cut one unit of work in the
write service, so #6675 widens this port to that unit and routes that door.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "TransitionRow",
    "WorkPackageTransition",
    "WorkPackageTransitionPort",
    "bind_work_package_transition_port",
    "bound_work_package_transition_port",
    "reset_work_package_transition_port",
]

logger = logging.getLogger(__name__)


class TransitionRow(Protocol):
    """One row of a work package transition's durability unit."""

    @property
    def event_id(self) -> str: ...

    def to_dict(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class WorkPackageTransition:
    """One work package transition, as the domain hands it to the port.

    Attributes:
        write_location: The resolved Mission directory the unit lands in.
        rows: One durability unit, in order: the transition, then its
            annotations. It lands whole or not at all.
        write_contract: The CLI's resolved write contract for
            ``write_location`` (opaque to the domain); ``None`` for a direct
            append by the flat shell.
    """

    write_location: Path
    rows: tuple[TransitionRow, ...]
    write_contract: object | None = None

    def __post_init__(self) -> None:
        if not self.rows:
            raise ValueError("a work package transition needs at least one row")


class WorkPackageTransitionPort(Protocol):
    """Entry point for a work package transition (ADR 2026-10-14-1 D-2, open question 6)."""

    def record_work_package_transition(self, transition: WorkPackageTransition) -> None:
        """Persist *transition* as one unit, or raise; never swallow a failure."""
        ...


_bound_port: WorkPackageTransitionPort | None = None


def _port_key(port: WorkPackageTransitionPort) -> str:
    kind = type(port)
    return f"{kind.__module__}.{kind.__qualname__}"


def bind_work_package_transition_port(port: WorkPackageTransitionPort) -> None:
    """Bind the adapter the transition doors hand their units to.

    This is the binding of the port's second half, not a second emitter
    registry: ``register_runtime_emitter_factory`` binds the Mission state
    advance half per Mission, and this binds the work package transition half
    once. It follows the same reject-on-conflict policy: rebinding an instance
    of the same class replaces it, and binding a different class while one is
    bound raises ``RuntimeError``. Open-core binds none outside tests; the
    write-service client (#6675) is the planned binder.
    """
    global _bound_port
    if _bound_port is not None and _port_key(_bound_port) != _port_key(port):
        raise RuntimeError(f"A different work package transition port is already bound: {_bound_port!r}. Cannot bind {port!r}.")
    logger.debug("bind_work_package_transition_port: %s", _port_key(port))
    _bound_port = port


def bound_work_package_transition_port() -> WorkPackageTransitionPort | None:
    """Return the bound adapter, or ``None`` when the default applies."""
    return _bound_port


def reset_work_package_transition_port() -> None:
    """Unbind the adapter (test-only, mirrors ``reset_runtime_emitter_factory``)."""
    global _bound_port
    _bound_port = None
