"""Tests for the data-only pack-lineage adapter (FR-006, FR-007, WP03).

Covers :mod:`charter.offering.packs.pack_lineage`: the ``pack_id -> resolvable
key`` adapter that feeds ``extends.resolve_extends_order`` (no second
walker, C-002/NFR-001) and fail-closed rejection of an unresolvable
``parent_pack`` edge. (The ``accompanies_doctrine_pack`` binding was retired,
#3732; its rejection is covered by
``tests/charter/test_retired_accompanies_doctrine_pack.py``.)

All fixtures are plain in-memory dicts (``pack_id -> name`` / ``pack_id ->
parent pack_id``) -- this lane is decoupled from sibling work packages'
``PackDescriptor``/``PackManifest`` types (lane independence; see module
docstring in ``pack_lineage.py``).
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

from charter.offering.packs.extends import resolve_extends_order
from charter.offering.packs.pack_lineage import (
    PackLineageCycleError,
    UnresolvedPackParentError,
    resolve_pack_lineage_order,
)


class TestResolvePackLineageOrder:
    """T011: id -> name adapter delegates to extends.resolve_extends_order."""

    def test_single_pack_no_parent(self) -> None:
        order = resolve_pack_lineage_order(
            "id-root",
            parent_edges={"id-root": None},
            pack_names={"id-root": "root"},
        )
        assert order == ["id-root"]

    def test_parent_chain_matches_name_keyed_path(self) -> None:
        """A parent chain resolves in the same order the name-keyed path would."""
        parent_edges = {
            "id-root": None,
            "id-mid": "id-root",
            "id-leaf": "id-mid",
        }
        pack_names = {"id-root": "root", "id-mid": "mid", "id-leaf": "leaf"}

        order = resolve_pack_lineage_order("id-leaf", parent_edges, pack_names)
        assert order == ["id-root", "id-mid", "id-leaf"]

        # The equivalent name-keyed call through extends directly, which
        # is the live resolution path today (org_charter.py:517,525).
        name_edges = {"root": None, "mid": "root", "leaf": "mid"}
        name_order = resolve_extends_order("leaf", name_edges)
        assert [pack_names[pid] for pid in order] == name_order

    def test_unrelated_packs_do_not_pollute_chain(self) -> None:
        parent_edges = {
            "id-root": None,
            "id-mid": "id-root",
            "id-other": None,
        }
        pack_names = {"id-root": "root", "id-mid": "mid", "id-other": "other"}

        order = resolve_pack_lineage_order("id-mid", parent_edges, pack_names)
        assert order == ["id-root", "id-mid"]


class TestFailClosedParentPack:
    """T012a: an unresolvable parent_pack fails closed (never a silent no-op)."""

    def test_unbackfilled_parent_raises(self) -> None:
        # id-mid's parent_pack points at id-root, but id-root has no known
        # name (e.g. a pre-pack_id-backfill pack, per IC-05/Q2).
        parent_edges = {"id-mid": "id-root"}
        pack_names = {"id-mid": "mid"}

        with pytest.raises(UnresolvedPackParentError) as exc:
            resolve_pack_lineage_order("id-mid", parent_edges, pack_names)
        assert exc.value.missing_pack_id == "id-root"

    def test_unresolvable_edge_does_not_silently_return_empty_order(self) -> None:
        # A no-op / inert-field bug would silently return `[]` (or a partial
        # prefix) instead of raising. Assert the raise happens *before* any
        # return value is produced, by checking the exception type is not a
        # falsy/empty sentinel masquerading as success.
        parent_edges = {"id-mid": "id-root"}
        pack_names = {"id-mid": "mid"}

        try:
            resolve_pack_lineage_order("id-mid", parent_edges, pack_names)
            pytest.fail("expected UnresolvedPackParentError, got a return value")
        except UnresolvedPackParentError:
            pass

    def test_unknown_start_pack_raises(self) -> None:
        with pytest.raises(UnresolvedPackParentError) as exc:
            resolve_pack_lineage_order(
                "id-ghost",
                parent_edges={"id-root": None},
                pack_names={"id-root": "root"},
            )
        assert exc.value.missing_pack_id == "id-ghost"

    def test_cycle_raises_pack_lineage_cycle_error(self) -> None:
        parent_edges = {"id-a": "id-b", "id-b": "id-a"}
        pack_names = {"id-a": "a", "id-b": "b"}

        with pytest.raises(PackLineageCycleError) as exc:
            resolve_pack_lineage_order("id-a", parent_edges, pack_names)
        assert exc.value.cycle_path[0] == exc.value.cycle_path[-1]
        assert set(exc.value.cycle_path) == {"id-a", "id-b"}
