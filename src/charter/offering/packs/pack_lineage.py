"""Pack lineage resolution: a data-only adapter over ``extends`` (FR-006, FR-007).

This module resolves the `id`-keyed pack-lineage edge introduced by the
pack-metadata manifest unification: ``parent_pack`` — a pack's parent, by
``pack_id`` (see ``data-model.md``'s ``PackDescriptor.parent_pack``). The
former ``accompanies_doctrine_pack`` binding was retired with no replacement
concept (#3732): a pack that still declares it is rejected with
``RETIRED_PACK_FIELD``.

C-002 / NFR-001 (no parallel resolver)
---------------------------------------
``charter.offering.packs.extends.resolve_extends_order`` is the **single** canonical
resolver for lineage-chain topology (cycle detection, missing-base
detection, base-first ordering). The live ``extends:`` field feeds it a
**name-keyed** edge map today (``org_charter.py:517,525``). This module does
**not** introduce a second walker: :func:`resolve_pack_lineage_order` is a
data-only ``pack_id -> resolvable key`` adapter that builds a name-keyed
edge map and delegates the entire walk — including cycle and missing-base
detection — to :func:`charter.offering.packs.extends.resolve_extends_order`. No
traversal, recursion, or graph algorithm of its own lives in this module.

Lineage authority (two-key period, IC-05/PP-M1): the live ``extends:``
(name-keyed) map remains the single *live* resolution authority. This
adapter lets ``parent_pack`` (id-keyed) be resolved through the same
canonical resolver without retiring ``extends:`` — full migration to
``parent_pack`` as the sole edge source is deferred until ``pack_id``
backfill is universal.

Decoupling note (lane independence)
------------------------------------
This module operates purely on plain edge data handed in by the caller
(``Mapping[str, str | None]`` and friends) — it does **not** import
``pack_descriptor`` or ``pack_manifest`` types from sibling work packages.
Real callers (a future integration WP) will project a ``PackDescriptor``
collection down to these plain mappings before calling in.
"""

from __future__ import annotations

from collections.abc import Mapping

from charter.offering.packs.extends import (
    ExtendsBaseNotFoundError,
    ExtendsCycleError,
    resolve_extends_order,
)

__all__ = [
    "PackLineageCycleError",
    "UnresolvedPackParentError",
    "resolve_pack_lineage_order",
]

# Sentinel prefix for a pack_id that has no known resolvable key (name).
# It is chosen so it can never collide with a real pack name (a NUL byte is
# not a legal character in an authored `name:` value), which lets the
# fallback key flow straight into `extends.resolve_extends_order` and
# be rejected there as a missing base -- no duplicate validation here.
_UNRESOLVED_KEY_PREFIX = "\x00unresolved-pack-id:"


class UnresolvedPackParentError(ValueError):
    """Raised when a ``parent_pack`` edge cannot be resolved (fail-closed).

    Mirrors :class:`charter.offering.packs.extends.ExtendsBaseNotFoundError`: a
    ``parent_pack`` pointing at a ``pack_id`` with no known resolvable key
    (e.g. a pre-``pack_id``-backfill pack, per IC-05/Q2) is reported here
    rather than silently dropped or treated as a root pack.
    """

    def __init__(self, missing_pack_id: str, chain: list[str]) -> None:
        self.missing_pack_id = missing_pack_id
        self.chain = list(chain)
        super().__init__(
            f"parent_pack {missing_pack_id!r} could not be resolved: no "
            "known name for this pack_id (fail-closed, not a silent "
            f"no-op). Chain so far: {' → '.join(chain)}"
        )


class PackLineageCycleError(ValueError):
    """Raised when a ``parent_pack`` chain contains a cycle (fail-closed).

    Mirrors :class:`charter.offering.packs.extends.ExtendsCycleError`, reported in
    terms of ``pack_id`` rather than the internal resolvable key.
    """

    def __init__(self, cycle_path: list[str]) -> None:
        self.cycle_path = list(cycle_path)
        super().__init__("Cycle detected in parent_pack chain: " + " → ".join(cycle_path))


def _resolvable_key(pack_id: str, pack_names: Mapping[str, str]) -> str:
    """Map a ``pack_id`` to the key ``extends`` can walk (its name).

    Falls back to a sentinel-prefixed marker for a ``pack_id`` absent from
    *pack_names*, so ``extends``' own missing-base detection catches it
    when the walk reaches that key -- this adapter performs no traversal or
    validation of its own.
    """
    name = pack_names.get(pack_id)
    if name is not None:
        return name
    return f"{_UNRESOLVED_KEY_PREFIX}{pack_id}"


def _original_pack_id(key: str, pack_id_by_name: Mapping[str, str]) -> str:
    """Invert :func:`_resolvable_key`: recover the ``pack_id`` for a walked key."""
    if key in pack_id_by_name:
        return pack_id_by_name[key]
    if key.startswith(_UNRESOLVED_KEY_PREFIX):
        return key[len(_UNRESOLVED_KEY_PREFIX) :]
    return key


def resolve_pack_lineage_order(
    start_pack_id: str,
    parent_edges: Mapping[str, str | None],
    pack_names: Mapping[str, str],
) -> list[str]:
    """Resolve the ``parent_pack`` chain from *start_pack_id*, base-first.

    This is a data-only adapter: it builds a name-keyed edge map from
    *parent_edges* (``pack_id -> parent pack_id | None``) and *pack_names*
    (``pack_id -> resolvable key``, i.e. the pack's ``name``), then
    delegates the entire walk to
    :func:`charter.offering.packs.extends.resolve_extends_order` -- the single
    canonical lineage resolver (C-002/NFR-001). No new traversal is
    performed here.

    Parameters
    ----------
    start_pack_id:
        ``pack_id`` of the overlay pack whose chain to resolve. Must be a
        key in *parent_edges*.
    parent_edges:
        Mapping of ``pack_id`` -> its declared ``parent_pack`` (or ``None``
        for a root pack). Mirrors ``PackDescriptor.parent_pack``.
    pack_names:
        Mapping of ``pack_id`` -> resolvable key (``name``) -- the
        ``pack_id -> resolvable-key`` adapter data described by IC-05.

    Returns
    -------
    list[str]
        ``pack_id`` values in resolution order, base first.

    Raises
    ------
    UnresolvedPackParentError
        When *start_pack_id* or any ``parent_pack`` target has no entry in
        *pack_names* (fail-closed; never a silent no-op).
    PackLineageCycleError
        When the ``parent_pack`` chain contains a cycle.
    """
    pack_id_by_name = {name: pack_id for pack_id, name in pack_names.items()}
    name_edges: dict[str, str | None] = {}
    for pack_id, parent_id in parent_edges.items():
        key = _resolvable_key(pack_id, pack_names)
        parent_key = _resolvable_key(parent_id, pack_names) if parent_id is not None else None
        name_edges[key] = parent_key

    start_key = _resolvable_key(start_pack_id, pack_names)
    try:
        order_keys = resolve_extends_order(start_key, name_edges)
    except ExtendsCycleError as exc:
        cycle = [_original_pack_id(key, pack_id_by_name) for key in exc.cycle_path]
        raise PackLineageCycleError(cycle) from exc
    except ExtendsBaseNotFoundError as exc:
        missing = _original_pack_id(exc.missing_base, pack_id_by_name)
        chain = [_original_pack_id(key, pack_id_by_name) for key in exc.chain]
        raise UnresolvedPackParentError(missing, chain) from exc

    return [_original_pack_id(key, pack_id_by_name) for key in order_keys]
