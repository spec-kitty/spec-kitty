"""T006 (mission ``drg-read-path-bridge-01M0CHVZ``, #3573): the
``drg_root_graph_missing`` finding is reconciled with the DRG read-path bridge.

Once the runtime reads a pack's ``drg/fragment.yaml`` (via
``charter.activation._drg_helpers.load_validated_graph``'s ``org_fragments`` fold), the
validator must NOT tell the operator that pack's DRG "will not be read" — that
would contradict the runtime (C-001 / NFR-003). This suite pins:

* a ``drg/fragment.yaml``-**only** pack yields **no** ``drg_root_graph_missing``
  finding (a fragment-only pack ships no ``drg/*.graph.yaml`` and so never
  matches the glob — SC-003 / US3 AC1);
* a pack shipping BOTH ``drg/fragment.yaml`` AND a ``drg/*.graph.yaml`` still
  yields the finding — the fragment's edges cascade, but the ``drg/*.graph.yaml``
  graph document is a distinct shape no runtime path reads, so the author still
  needs the signal (the fragment does not suppress it);
* a genuinely-unread ``drg/*.graph.yaml``-only pack still yields the finding
  (dead-content protection);
* the finding message states the real runtime read-set and drops the false
  "not drg/ fragments" blanket claim.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from charter.offering.packs.pack_validator import validate_pack

pytestmark = [pytest.mark.unit, pytest.mark.fast]


_GRAPH_YAML = textwrap.dedent(
    """\
    schema_version: "1.0"
    generated_at: STATIC
    generated_by: test
    nodes: []
    edges: []
    """
)

_FRAGMENT_YAML = textwrap.dedent(
    """\
    pack_name: fixture-pack
    source_kind: local_path
    source_ref: /nonexistent/fixture-pack
    layer_index: 1
    provenance_marker: org
    nodes:
      - id: fixture-node
        kind: directives
        title: "Fixture directive"
    edges: []
    """
)


def _findings(pack_dir: Path) -> list[str]:
    result = validate_pack(pack_dir)
    return [i.category for i in result.errors]


class TestFragmentPackNoLongerFlagged:
    def test_fragment_only_pack_yields_no_finding(self, tmp_path: Path) -> None:
        """A pack shipping only ``drg/fragment.yaml`` is read at runtime via the
        bridge, so no ``drg_root_graph_missing`` finding fires (SC-003 / US3 AC1)."""
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "fragment.yaml").write_text(_FRAGMENT_YAML, encoding="utf-8")
        assert not sorted(tmp_path.glob("*.graph.yaml"))

        assert "drg_root_graph_missing" not in _findings(tmp_path)

    def test_fragment_plus_drg_graph_yaml_still_flags_the_graph_shape(self, tmp_path: Path) -> None:
        """A pack shipping ``drg/fragment.yaml`` AND ``drg/*.graph.yaml`` STILL
        fires ``drg_root_graph_missing``: the fragment's edges cascade, but the
        ``drg/*.graph.yaml`` graph document is a distinct shape no runtime path
        reads, so the operator still needs the signal. The fragment's presence
        does not suppress the finding (it answers a different question than the
        runtime graphless-warning). Guards the pre-existing
        ``test_doctrine_org_commands`` AC-7b fixture, which scaffolds a pack
        (always carrying a ``drg/fragment.yaml``) then adds a
        ``drg/*.graph.yaml`` and expects the finding."""
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "fragment.yaml").write_text(_FRAGMENT_YAML, encoding="utf-8")
        (drg / "010-security.graph.yaml").write_text(_GRAPH_YAML, encoding="utf-8")
        assert not sorted(tmp_path.glob("*.graph.yaml"))

        assert "drg_root_graph_missing" in _findings(tmp_path)


class TestDeadContentStillFlagged:
    def test_drg_graph_yaml_only_still_fires(self, tmp_path: Path) -> None:
        """A ``drg/*.graph.yaml``-only pack (no pack-root graph, no
        ``drg/fragment.yaml``) is genuinely unread by every runtime path, so the
        finding is retained (dead-content protection — D5 rationale)."""
        drg = tmp_path / "drg"
        drg.mkdir()
        (drg / "010-security.graph.yaml").write_text(_GRAPH_YAML, encoding="utf-8")
        assert not sorted(tmp_path.glob("*.graph.yaml"))
        assert not (drg / "fragment.yaml").exists()

        result = validate_pack(tmp_path)
        root_missing = [i for i in result.errors if i.category == "drg_root_graph_missing"]
        assert root_missing, result.errors
        message = root_missing[0].message
        # The message must state the real read-set and drop the false blanket.
        assert "not drg/ fragments" not in message
        assert "drg/fragment.yaml" in message
        assert "drg/*.graph.yaml" in message
