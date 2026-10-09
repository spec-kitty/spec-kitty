"""Resolution of agent-profile ``operating-procedures`` against real procedure nodes.

An agent profile's ``collaboration.operating-procedures`` is a schema-validated
``list[str]`` (see :class:`charter.offering.agent_profiles.profile.CollaborationContract`),
but its *values* were historically never checked against real doctrine nodes: an
entry naming no procedure (fictional) or naming a node of the wrong kind (e.g. a
tactic) loaded clean and then reached no consumer. This module is the single
authority for the question "does an ``operating-procedures`` entry resolve to a
real *procedure* node?" — read by the DRG extractor (build-time gate + guarded
edge emission) and by ``doctor charter-packs`` (diagnostic). It stays in-layer
(``doctrine``) and never imports upward into ``charter`` or ``specify_cli`` (C-004).

The contract is *procedure-kind*: an entry must resolve to a ``procedure:`` node.
An entry that resolves to a node of another kind is reported as ``wrong_kind``
(not silently accepted), and one that resolves to nothing as ``no_node`` — so a
misfiled or fictional reference fails loud rather than being dropped downstream.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ruamel.yaml import YAML

from charter.offering.drg.migration.id_normalizer import artifact_to_urn
from charter.offering.drg.models import DRGNode, NodeKind

__all__ = [
    "collect_operating_procedure_entries",
    "node_universe",
    "resolve_operating_procedure_entries",
]

#: A single ``ruamel.yaml`` reader reused for every profile parse. ``typ="safe"``
#: mirrors the DRG extractor / doctor collectors so the harvest is byte-identical
#: across all three consumers.
_YAML = YAML(typ="safe")

#: The DRG kind an ``operating-procedures`` entry must resolve to.
_PROCEDURE_KIND = NodeKind.PROCEDURE

UnresolvedReason = Literal["no_node", "wrong_kind"]


@dataclass(frozen=True)
class UnresolvedOpProc:
    """One ``operating-procedures`` entry that does not resolve to a procedure node.

    Attributes:
        profile_id: The owning agent profile's ``profile-id``.
        entry: The ``operating-procedures`` value as authored.
        reason: ``"no_node"`` (resolves to nothing) or ``"wrong_kind"`` (resolves
            to a real node of a non-procedure kind).
        resolved_kind: For ``"wrong_kind"``, the kind the entry actually resolved
            to (e.g. ``"tactic"``); ``None`` for ``"no_node"``.
    """

    profile_id: str
    entry: str
    reason: UnresolvedReason
    resolved_kind: str | None


def collect_operating_procedure_entries(profiles_dir: Path) -> dict[str, list[str]]:
    """Harvest ``{profile_id: [operating-procedures entry, ...]}`` from *profiles_dir*.

    THE single authority for reading the ``collaboration.operating-procedures``
    field off built-in agent-profile YAML. The DRG extractor (edge emission +
    fail-closed raise), ``doctor charter-packs`` (diagnostic collector) and the
    architectural gate all delegate here so the walk — glob order, dict-shape
    guard, ``profile-id`` keying and the falsy-entry policy — can never diverge
    between them (C-004 single-authority).

    Globs ``*.agent.yaml`` under *profiles_dir* in sorted order and parses each
    with ``ruamel.yaml.YAML(typ="safe")``. A file whose top-level data is not a
    mapping, or that carries no ``profile-id``, is skipped. The single
    falsy-filter policy is applied here and nowhere else: empty/falsy entries
    (e.g. an authored ``""``) are dropped, so a caller never has to re-decide
    whether a blank entry is a real reference. A profile with no
    ``operating-procedures`` field maps to an empty list.

    Returns an empty mapping when *profiles_dir* is not a directory.
    """
    entries_by_profile: dict[str, list[str]] = {}
    if not profiles_dir.is_dir():
        return entries_by_profile
    for path in sorted(profiles_dir.glob("*.agent.yaml")):
        data = _YAML.load(path)
        if not isinstance(data, dict):
            continue
        profile_id = data.get("profile-id")
        if not profile_id:
            continue
        collaboration = data.get("collaboration") or {}
        raw = collaboration.get("operating-procedures") or []
        entries_by_profile[profile_id] = [entry for entry in raw if entry]
    return entries_by_profile


def node_universe(
    nodes: Iterable[DRGNode],
) -> tuple[frozenset[str], dict[NodeKind, frozenset[str]]]:
    """Derive ``(procedure_urns, urns_by_kind)`` from a node collection.

    Single-authority derivation so every caller (extractor build, gate test,
    doctor) computes the procedure universe the same way rather than restating a
    hand-listed id set. The procedure set is exactly the ``urns_by_kind`` entry
    for :attr:`NodeKind.PROCEDURE`, surfaced separately for the common case.
    """
    by_kind: dict[NodeKind, set[str]] = {}
    for node in nodes:
        by_kind.setdefault(node.kind, set()).add(node.urn)
    frozen_by_kind = {kind: frozenset(urns) for kind, urns in by_kind.items()}
    procedure_urns = frozen_by_kind.get(_PROCEDURE_KIND, frozenset())
    return procedure_urns, frozen_by_kind


def _classify(
    profile_id: str,
    entry: str,
    procedure_urns: AbstractSet[str],
    urns_by_kind: Mapping[NodeKind, AbstractSet[str]] | None,
) -> UnresolvedOpProc | None:
    """Classify a single entry; ``None`` when it resolves to a procedure node."""
    if artifact_to_urn(_PROCEDURE_KIND.value, entry) in procedure_urns:
        return None
    if urns_by_kind:
        # Deterministic kind order so ``resolved_kind`` is stable when an id
        # collides across kinds (does not happen in shipped built-in, but the
        # diagnostic must be reproducible regardless).
        for kind in sorted(urns_by_kind, key=lambda k: k.value):
            if kind is _PROCEDURE_KIND:
                continue
            if artifact_to_urn(kind.value, entry) in urns_by_kind[kind]:
                return UnresolvedOpProc(profile_id, entry, "wrong_kind", kind.value)
    return UnresolvedOpProc(profile_id, entry, "no_node", None)


def resolve_operating_procedure_entries(
    entries_by_profile: Mapping[str, Sequence[str]],
    procedure_urns: AbstractSet[str],
    urns_by_kind: Mapping[NodeKind, AbstractSet[str]] | None = None,
) -> list[UnresolvedOpProc]:
    """Resolve raw ``{profile_id: [entry, ...]}`` against the procedure universe.

    Returns one :class:`UnresolvedOpProc` per entry that does not resolve to a
    procedure node, deterministically ordered by ``(profile_id, entry)``. Pure —
    no I/O, no fuzzy matching (fail-closed, NFR-003). This is the raw seam the
    DRG extractor uses (it holds YAML dicts, not :class:`AgentProfile` objects).
    """
    unresolved: list[UnresolvedOpProc] = []
    for profile_id, entries in entries_by_profile.items():
        for entry in entries:
            record = _classify(profile_id, entry, procedure_urns, urns_by_kind)
            if record is not None:
                unresolved.append(record)
    unresolved.sort(key=lambda u: (u.profile_id, u.entry))
    return unresolved
