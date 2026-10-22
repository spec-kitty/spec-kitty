"""Single home of the DRG mapping-writer node-field totality tests (#5015).

``tests/specify_cli/drg_writers/test_registry_completeness.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_drg_writers_registry_completeness.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

from pydantic import Field

from charter.offering.drg.migration import extractor
from charter.offering.drg.models import DRGNode, NodeKind
from specify_cli.drg_writers.registry import (
    MAPPING_WRITERS,
)


def _full_node() -> DRGNode:
    return DRGNode(
        urn="anti_pattern:big-ball-of-mud",
        kind=NodeKind.ANTI_PATTERN,
        label="Big Ball of Mud",
        provenance="org:acme",
        tags=["smell"],
    )


def _expected_node_keys() -> set[str]:
    keys: set[str] = set(DRGNode.model_fields) - extractor.FIELDS_WITHHELD_FROM_GRAPH_OUTPUT
    return keys


class _NodeWithNovelFields(DRGNode):
    novel_scalar: str | None = "planted-node-value"
    novel_empty: list[str] = Field(default_factory=list)


def _mutated_node() -> _NodeWithNovelFields:
    return _NodeWithNovelFields(urn="anti_pattern:x", kind=NodeKind.ANTI_PATTERN, label="L", tags=["t"])


def test_every_mapping_writer_emits_every_declared_node_field() -> None:
    assert MAPPING_WRITERS  # non-empty, so the scan is not vacuous
    node = _full_node()
    for writer in MAPPING_WRITERS:
        emitted = set(writer.node_to_mapping(node))
        missing = _expected_node_keys() - emitted
        assert not missing, f"{writer.name} dropped node field(s) {missing}"


def test_every_mapping_writer_preserves_a_novel_node_field() -> None:
    node = _mutated_node()
    for writer in MAPPING_WRITERS:
        emitted = set(writer.node_to_mapping(node))
        assert "novel_scalar" in emitted, f"{writer.name} dropped novel_scalar"
        assert "novel_empty" in emitted, f"{writer.name} dropped novel_empty (the empty-value hole, W-1a)"
