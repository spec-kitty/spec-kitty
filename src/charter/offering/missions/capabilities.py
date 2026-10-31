"""The built-in mission-type capability defaults — one table, one authority (#6327).

A mission type's capabilities answer the questions governance gates ask without
testing the family name: does it produce committed code (``code_producing``, so
the review-time implementation-commit prerequisite applies), and must its spec be
substantive (``requires_substantive_spec``). ``#6315`` shipped the second as
:data:`~charter.activation.mission_type_profiles.BUILTIN_REQUIRES_SUBSTANTIVE_SPEC`;
``#6328`` needs the first, so both now derive from this one table rather than
each growing its own enumeration.

**Precedence (the whole rule).** A mission type's own *declared* value wins. When
a type declares nothing, its value here applies. When it is not in this table at
all — every custom, charter-pack, org and project type that does not declare the
capability — the answer is the conservative ``False``, so no existing custom type
silently gains code-rigour or substantive-spec gates.

The table lives in the offering layer because that is where the mission-type
*descriptor* lives: the same doctrine tree holds
``models.MissionType`` (the field declarations) and the shipped built-in
descriptors under ``packs/built-in/missions/mission_types/*.yaml``, which carry
the same two keys for the built-in types. A table kept on the runtime side would
be a second authority for doctrine data that the descriptor layer already owns.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

__all__ = ["BUILTIN_TYPE_CAPABILITIES"]

#: Built-in capability defaults, keyed by mission-type id then capability name.
#: ``software-dev`` is the only built-in family whose work packages are committed
#: code, so it is the only one that answers ``code_producing`` true; ``research``
#: and ``documentation`` still require a substantive spec, ``plan`` does not.
BUILTIN_TYPE_CAPABILITIES: Mapping[str, Mapping[str, bool]] = MappingProxyType(
    {
        "software-dev": MappingProxyType({"code_producing": True, "requires_substantive_spec": True}),
        "research": MappingProxyType({"code_producing": False, "requires_substantive_spec": True}),
        "documentation": MappingProxyType({"code_producing": False, "requires_substantive_spec": False}),
        "plan": MappingProxyType({"code_producing": False, "requires_substantive_spec": False}),
    }
)
