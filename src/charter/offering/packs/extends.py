"""Canonical ``extends:`` chain resolution for org-charter composition (FR-008).

This module is the **single source of truth** for resolving an ``extends:``
chain over org-charter layers: cycle detection, missing-base detection, and the
base-first resolution order. It is the topology counterpart to the additive
merge performed by the higher layer, and it follows the same validate-before-
mutate discipline as :mod:`charter.activation.activation_engine` — the chain is fully
validated (cycles and missing bases rejected fail-closed) **before** any
resolved order is returned, so a caller never folds a half-resolved chain.

C-005 / R-10 (no parallel resolver)
-----------------------------------
Prior to FR-008 the ``extends:`` topology was walked by a private depth-first
resolver inside ``specify_cli.doctrine.org_charter`` (``_resolve_chain``). That
was a second, hand-rolled resolution path living above the charter layer. This
module hoists that logic into the canonical ``charter.*`` layer so there is a
single resolution mechanism; ``specify_cli.doctrine.org_charter`` delegates to
:func:`resolve_extends_order` rather than maintaining its own walk.

Layering (C-001 / C-008)
------------------------
Charter layer: this module performs **no I/O** and imports nothing from
``specify_cli``. It operates purely on data handed in by the caller — a mapping
from layer name to its declared ``extends:`` target (or ``None``). This mirrors
the activation-engine contract of receiving the loaded config *as data*.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = [
    "ExtendsBaseNotFoundError",
    "ExtendsCycleError",
    "resolve_extends_order",
]


class ExtendsCycleError(ValueError):
    """Raised when an ``extends:`` chain contains a cycle (fail-closed, C-004).

    A cycle has no well-defined base, so resolution is rejected rather than
    producing a partial/ambiguous merge. The full cycle path — including the
    repeated node that closes the loop — is preserved on :attr:`cycle_path` so
    callers can render an operator-friendly diagnostic without re-walking.
    """

    def __init__(self, cycle_path: list[str]) -> None:
        self.cycle_path = list(cycle_path)
        super().__init__("Cycle detected in extends: chain: " + " → ".join(self.cycle_path))


class ExtendsBaseNotFoundError(ValueError):
    """Raised when an ``extends:`` target names a layer absent from the set.

    The missing base name and the chain walked so far (overlay-first) are
    preserved so the caller can surface both the unresolved reference and the
    path that reached it.
    """

    def __init__(self, missing_base: str, chain: list[str]) -> None:
        self.missing_base = missing_base
        self.chain = list(chain)
        super().__init__(f"Base layer {missing_base!r} not found. Chain: {' → '.join(self.chain)}")


def resolve_extends_order(
    start: str,
    extends_edges: Mapping[str, str | None],
) -> list[str]:
    """Resolve the ``extends:`` chain from *start*, base-first.

    Walks the ``extends:`` pointers depth-first from the overlay (*start*) down
    to the root base, validating the topology fail-closed, then reverses the
    walk so the returned order is base-first (``[root_base, ..., overlay]``).

    The whole chain is validated before any order is returned: a cycle raises
    :class:`ExtendsCycleError` and a dangling ``extends:`` target raises
    :class:`ExtendsBaseNotFoundError`. Neither leaves a partially-resolved
    result for the caller to fold (the activation-engine NFR-003 discipline).

    Parameters
    ----------
    start:
        Name of the overlay layer whose chain to resolve. Must be a key in
        *extends_edges*.
    extends_edges:
        Mapping of layer name → its declared ``extends:`` target (or ``None``
        for a root layer). Every name reachable through the chain — including
        *start* — must be present as a key, otherwise the missing name is
        reported via :class:`ExtendsBaseNotFoundError`.

    Returns
    -------
    list[str]
        The chain in resolution order, base first.

    Raises
    ------
    ExtendsBaseNotFoundError
        When *start* or any ``extends:`` target is absent from *extends_edges*.
    ExtendsCycleError
        When a layer already in the chain re-appears (including a self-edge).
    """
    chain: list[str] = []
    visited: set[str] = set()

    current: str | None = start
    while current is not None:
        if current in visited:
            # Reveal the full cycle, appending the repeat for clarity so the
            # diagnostic shows the loop closing on itself.
            raise ExtendsCycleError([*chain, current])
        if current not in extends_edges:
            raise ExtendsBaseNotFoundError(current, chain)
        visited.add(current)
        chain.append(current)
        current = extends_edges[current]

    # chain is [overlay, ..., root_base]; reverse for base-first resolution.
    chain.reverse()
    return chain
