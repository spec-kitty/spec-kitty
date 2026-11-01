"""The mission-type capability contract on the charter offering seam (#6331).

A resolved mission type answers two capability questions: whether it iterates work packages
(``wp_driven``) and whether it demands a substantive spec (``requires_substantive_spec``).
Those answers were only reachable from ``charter.activation.mission_type_profiles``, which is
an activation-tier module — so any consumer that may import the offering seam had to reach
*up* into activation to read them.

This module carries the **contract** across the seam: a frozen value object, a structural
protocol, and one read function. It deliberately does **not** carry the resolver.
``resolve_mission_type_context`` and ``ResolvedMissionType`` stay in ``charter.activation``
because ``charter.offering`` sits *below* activation — ADR
``2026-10-16-1`` (Amendment 2026-10-19) records the verified zero-edge dependency direction
(offering → activation imports = 0, the reverse edge is heavy). A re-export of the resolver
would invert that edge; exposing its *contract* does not.

The resolved mission type remains the single producer of the values (single canonical
authority, C-004): :func:`capabilities_of` derives from the object's own attributes and never
copies or re-decides a capability. ``wp_driven`` is advisory here — the runtime WP-advance
guard reads the frozen DAG, which is authoritative (#6330). A third capability
(``code_producing``, #6327) joins additively: the protocol is the stable part, the value
object grows a field.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "MissionTypeCapabilities",
    "MissionTypeCapabilitySource",
    "capabilities_of",
]


@dataclass(frozen=True)
class MissionTypeCapabilities:
    """An immutable snapshot of a mission type's capabilities.

    Both fields default to ``False``: an undeclared capability is never assumed, so an empty
    snapshot is the conservative answer rather than the optimistic one.
    """

    #: The mission type iterates work packages: its action sequence declares an ``implement``
    #: step (kernel rule, single authority). Advisory where the frozen DAG is authoritative.
    wp_driven: bool = False
    #: The mission type's authored rigour requirement: a stub spec may not satisfy it. A type
    #: that declares nothing is conservatively ``False``.
    requires_substantive_spec: bool = False


@runtime_checkable
class MissionTypeCapabilitySource(Protocol):
    """Anything that answers the two capability questions.

    Structural on purpose: a resolved mission type satisfies it without inheriting from an
    offering base class, so the seam never names the resolver's type and the resolver never
    depends on the seam's implementation. ``runtime_checkable`` checks attribute *presence*
    only — the annotated types are the caller's static-checker concern.
    """

    @property
    def wp_driven(self) -> bool: ...

    @property
    def requires_substantive_spec(self) -> bool: ...


def capabilities_of(source: MissionTypeCapabilitySource) -> MissionTypeCapabilities:
    """Read ``source``'s capabilities into the seam's value object.

    The single read through the seam. Coerces to ``bool`` so a truthy ``0``/``1`` from a
    YAML-backed resolver arrives as a real boolean.

    Raises :class:`AttributeError` for a source that does not answer both capabilities: a
    non-conforming object is a programming error, and defaulting it to ``False`` would be a
    silent fail-open.
    """
    return MissionTypeCapabilities(
        wp_driven=bool(source.wp_driven),
        requires_substantive_spec=bool(source.requires_substantive_spec),
    )
