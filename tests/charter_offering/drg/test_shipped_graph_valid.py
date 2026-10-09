"""Regression test: shipped graph.yaml + project overlay is always cycle-free
and otherwise structurally valid.

Replaces the coverage that previously lived in the deleted
``test_cycle_detection.py`` and ``test_shipped_doctrine_cycle_free.py``
modules, which both imported
from the deleted charter transitive-reference module.

:func:`charter.offering.drg.validator.assert_valid` rejects:

- dangling edges (target URN not in nodes)
- duplicate edges
- cycles in the ``requires`` subgraph
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from charter.offering.drg.validator import assert_valid

if TYPE_CHECKING:
    from charter.offering.drg.models import DRGGraph

pytestmark = [pytest.mark.fast, pytest.mark.corpus]


def test_shipped_graph_loads_and_validates(built_in_graph: DRGGraph) -> None:
    assert_valid(built_in_graph)


def test_shipped_graph_has_at_least_one_edge(built_in_graph: DRGGraph) -> None:
    """Smoke check that the graph file is non-degenerate."""
    assert len(built_in_graph.edges) > 0, "shipped graph must contain edges"
