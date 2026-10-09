"""Tests for loading DRG graphs from files and fragment directories."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.loader import DRGLoadError, load_graph, load_graph_or_dir


pytestmark = pytest.mark.fast


def _write_graph(
    path: Path,
    *,
    nodes: list[dict[str, str]],
    edges: list[dict[str, str]] | None = None,
    generated_by: str = "test",
) -> None:
    path.write_text(
        "\n".join(
            [
                'schema_version: "1.0"',
                'generated_at: "2026-05-15T00:00:00+00:00"',
                f'generated_by: "{generated_by}"',
                "nodes:",
                *[
                    "\n".join(
                        [
                            f'  - urn: "{node["urn"]}"',
                            f'    kind: "{node["kind"]}"',
                            *(
                                [f'    label: "{node["label"]}"']
                                if "label" in node
                                else []
                            ),
                        ]
                    )
                    for node in nodes
                ],
                *(
                    [
                        "edges:",
                        *[
                            "\n".join(
                                [
                                    f'  - source: "{edge["source"]}"',
                                    f'    target: "{edge["target"]}"',
                                    f'    relation: "{edge["relation"]}"',
                                ]
                            )
                            for edge in edges
                        ],
                    ]
                    if edges
                    else ["edges: []"]
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_single_file_path(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.yaml"
    _write_graph(
        graph_path,
        nodes=[{"urn": "directive:DIRECTIVE_001", "kind": "directive"}],
    )

    assert load_graph_or_dir(graph_path) == load_graph(graph_path)


def test_directory_legacy_graph_yaml(tmp_path: Path) -> None:
    graph_path = tmp_path / "graph.yaml"
    _write_graph(
        graph_path,
        nodes=[{"urn": "directive:DIRECTIVE_001", "kind": "directive"}],
    )

    assert load_graph_or_dir(tmp_path) == load_graph(graph_path)


def test_directory_single_fragment(tmp_path: Path) -> None:
    fragment_path = tmp_path / "010.graph.yaml"
    _write_graph(
        fragment_path,
        nodes=[{"urn": "directive:DIRECTIVE_001", "kind": "directive"}],
    )

    assert load_graph_or_dir(tmp_path) == load_graph(fragment_path)


def test_directory_multiple_fragments(tmp_path: Path) -> None:
    _write_graph(
        tmp_path / "010.graph.yaml",
        nodes=[{"urn": "directive:DIRECTIVE_001", "kind": "directive"}],
    )
    _write_graph(
        tmp_path / "020.graph.yaml",
        nodes=[{"urn": "tactic:tactic-001", "kind": "tactic"}],
        edges=[
            {
                "source": "tactic:tactic-001",
                "target": "directive:DIRECTIVE_001",
                "relation": "requires",
            }
        ],
    )

    graph = load_graph_or_dir(tmp_path)

    assert {node.urn for node in graph.nodes} == {
        "directive:DIRECTIVE_001",
        "tactic:tactic-001",
    }
    assert {e.source for e in graph.edges} == {"tactic:tactic-001"}
    assert graph.edges[0].source == "tactic:tactic-001"


def test_directory_alphabetical_order(tmp_path: Path) -> None:
    _write_graph(
        tmp_path / "zzz.graph.yaml",
        nodes=[
            {
                "urn": "directive:DIRECTIVE_001",
                "kind": "directive",
                "label": "late",
            }
        ],
    )
    _write_graph(
        tmp_path / "aaa.graph.yaml",
        nodes=[
            {
                "urn": "directive:DIRECTIVE_001",
                "kind": "directive",
                "label": "early",
            }
        ],
    )

    graph = load_graph_or_dir(tmp_path)

    assert graph.nodes[0].label == "late"


def test_directory_empty(tmp_path: Path) -> None:
    with pytest.raises(DRGLoadError, match="No DRG graph files found"):
        load_graph_or_dir(tmp_path)


def test_path_not_exists(tmp_path: Path) -> None:
    with pytest.raises(DRGLoadError, match="Path not found"):
        load_graph_or_dir(tmp_path / "missing")


def test_directory_one_invalid_fragment(tmp_path: Path) -> None:
    _write_graph(
        tmp_path / "010.graph.yaml",
        nodes=[{"urn": "directive:DIRECTIVE_001", "kind": "directive"}],
    )
    (tmp_path / "020.graph.yaml").write_text("nodes: [\n", encoding="utf-8")

    with pytest.raises(DRGLoadError):
        load_graph_or_dir(tmp_path)
