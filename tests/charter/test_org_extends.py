"""Tests for the canonical ``extends:`` chain resolver (FR-008, WP08).

Covers the topology contract of :func:`charter.offering.packs.extends.resolve_extends_order`:
base-first ordering, fail-closed cycle rejection, missing-base rejection, and
the non-destructive single-layer (no-``extends:``) path. The additive merge and
precedence-on-conflict are exercised at the consumer layer
(``tests/charter/activation/test_org_charter.py``), which now delegates its
chain walk to this resolver.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.fast]

from charter.offering.packs.extends import (
    ExtendsBaseNotFoundError,
    ExtendsCycleError,
    resolve_extends_order,
)


class TestResolveOrder:
    def test_single_layer_no_extends(self) -> None:
        order = resolve_extends_order("A", {"A": None})
        assert order == ["A"]

    def test_simple_pair_base_first(self) -> None:
        order = resolve_extends_order("B", {"A": None, "B": "A"})
        # Base-first: A then B (the overlay).
        assert order == ["A", "B"]

    def test_depth_two_chain_base_first(self) -> None:
        order = resolve_extends_order("C", {"A": None, "B": "A", "C": "B"})
        assert order == ["A", "B", "C"]

    def test_unrelated_layers_do_not_pollute_chain(self) -> None:
        # An extra layer not on the resolved chain is ignored.
        order = resolve_extends_order("B", {"A": None, "B": "A", "Z": None})
        assert order == ["A", "B"]


class TestCycleDetection:
    def test_two_layer_cycle_rejected(self) -> None:
        with pytest.raises(ExtendsCycleError) as exc:
            resolve_extends_order("A", {"A": "B", "B": "A"})
        assert "A" in exc.value.cycle_path
        assert "B" in exc.value.cycle_path
        # The loop closes on the repeated node.
        assert exc.value.cycle_path[-1] == exc.value.cycle_path[0]

    def test_self_reference_rejected(self) -> None:
        with pytest.raises(ExtendsCycleError) as exc:
            resolve_extends_order("A", {"A": "A"})
        assert exc.value.cycle_path == ["A", "A"]

    def test_three_layer_cycle_path_preserved(self) -> None:
        with pytest.raises(ExtendsCycleError) as exc:
            resolve_extends_order("A", {"A": "B", "B": "C", "C": "A"})
        # Walk order A→B→C then back to A closing the loop.
        assert exc.value.cycle_path == ["A", "B", "C", "A"]


class TestMissingBase:
    def test_missing_base_rejected(self) -> None:
        with pytest.raises(ExtendsBaseNotFoundError) as exc:
            resolve_extends_order("B", {"B": "nonexistent"})
        assert exc.value.missing_base == "nonexistent"
        assert exc.value.chain == ["B"]

    def test_missing_start_rejected(self) -> None:
        with pytest.raises(ExtendsBaseNotFoundError) as exc:
            resolve_extends_order("X", {"A": None})
        assert exc.value.missing_base == "X"
        assert exc.value.chain == []


class TestFailClosedBeforeOrder:
    def test_cycle_raises_no_partial_order(self) -> None:
        # The whole chain is validated before any order is returned: a cycle
        # deep in the chain raises rather than yielding a partial prefix.
        edges = {"A": "B", "B": "C", "C": "B"}
        with pytest.raises(ExtendsCycleError):
            resolve_extends_order("A", edges)
