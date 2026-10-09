"""Tests for NodeKind.GLOSSARY addition (T006).

Verifies:
- NodeKind.GLOSSARY.value == "glossary"
- DRGNode with a "glossary:<id>" URN validates successfully
- Existing shipped DRG graph.yaml still loads without error (backward compat)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from charter.offering.drg.models import DRGNode, NodeKind
from charter.offering.drg.validator import assert_valid

if TYPE_CHECKING:
    from charter.offering.drg.models import DRGGraph

pytestmark = [pytest.mark.fast, pytest.mark.corpus]


def test_node_kind_glossary_value() -> None:
    """NodeKind.GLOSSARY must have the string value "glossary"."""
    assert NodeKind.GLOSSARY.value == "glossary"


def test_node_kind_glossary_is_str_enum() -> None:
    """NodeKind.GLOSSARY must behave as a str (StrEnum)."""
    assert str(NodeKind.GLOSSARY) == "glossary"
    assert NodeKind.GLOSSARY == "glossary"


def test_drg_node_glossary_urn_validates() -> None:
    """DRGNode with a valid glossary:<id> URN must pass model validation."""
    node = DRGNode(urn="glossary:abc12345", kind=NodeKind.GLOSSARY)
    assert node.urn == "glossary:abc12345"
    assert node.kind is NodeKind.GLOSSARY


def test_drg_node_glossary_urn_with_label() -> None:
    """DRGNode with a label field also validates correctly."""
    node = DRGNode(urn="glossary:d93244e7", kind=NodeKind.GLOSSARY, label="lane")
    assert node.label == "lane"


def test_drg_node_glossary_wrong_prefix_rejected() -> None:
    """A glossary node with mismatched URN prefix is rejected by the validator."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        DRGNode(urn="action:abc12345", kind=NodeKind.GLOSSARY)


def test_shipped_graph_still_loads_after_glossary_addition(built_in_graph: DRGGraph) -> None:
    """Backward-compat: adding NodeKind.GLOSSARY must not break existing graph."""
    assert_valid(built_in_graph)
    # The shipped graph must not yet contain glossary nodes
    # (the layer is built dynamically, not baked into the shipped graph)
    glossary_nodes = [n for n in built_in_graph.nodes if n.kind == NodeKind.GLOSSARY]
    assert glossary_nodes == [], (
        "Shipped graph should not contain NodeKind.GLOSSARY nodes; "
        "the glossary layer is built dynamically by build_glossary_drg_layer()"
    )
