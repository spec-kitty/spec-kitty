"""The org-pack RUNTIME loader honors a declared ``pack_drg`` pointer (#6059).

``resolve_pack_layout`` is the single pack-layout seam: an authored
``pack_drg`` pointer wins, and the per-level convention (``drg/fragment.yaml``
for an org pack) is only the fallback when the pointer is absent. ``load_org_pack``
used to resolve its DRG through the convention default alone, so an org pack
pointing ``pack_drg`` somewhere else was silently loaded from the wrong file.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.org_pack_loader import load_org_pack

pytestmark = [pytest.mark.fast]

_BASE = "pack_id: 01ARWG13C000000000000000FG\nname: acme\npack_level: org\n"


def test_pack_drg_pointer_selects_a_non_default_fragment(tmp_path: Path) -> None:
    pack_root = tmp_path / "p"
    (pack_root / "graph").mkdir(parents=True)
    (pack_root / "graph" / "custom.yaml").write_text(
        "nodes:\n  - id: ACME-001-POINTED\n    kind: directives\nedges: []\n",
        encoding="utf-8",
    )
    # The convention default also exists and carries different content, so a
    # loader that ignores the pointer loads the wrong fragment (and fails).
    (pack_root / "drg").mkdir(parents=True)
    (pack_root / "drg" / "fragment.yaml").write_text("nodes: []\nedges: []\n", encoding="utf-8")
    (pack_root / "pack.yaml").write_text(f"{_BASE}pack_drg: graph/custom.yaml\n", encoding="utf-8")

    fragment = load_org_pack("acme", pack_root, 1)

    assert [(node.id, node.kind) for node in fragment.nodes] == [("ACME-001-POINTED", "directives")]


def test_absent_pack_drg_pointer_falls_back_to_the_convention_path(tmp_path: Path) -> None:
    pack_root = tmp_path / "p"
    (pack_root / "drg").mkdir(parents=True)
    (pack_root / "drg" / "fragment.yaml").write_text(
        "nodes:\n  - id: ACME-001-CONVENTION\n    kind: directives\nedges: []\n",
        encoding="utf-8",
    )
    (pack_root / "pack.yaml").write_text(_BASE, encoding="utf-8")

    fragment = load_org_pack("acme", pack_root, 1)

    assert [(node.id, node.kind) for node in fragment.nodes] == [("ACME-001-CONVENTION", "directives")]


def test_pointer_to_a_missing_fragment_names_the_pointed_path(tmp_path: Path) -> None:
    pack_root = tmp_path / "p"
    (pack_root / "drg").mkdir(parents=True)
    (pack_root / "drg" / "fragment.yaml").write_text("nodes: []\nedges: []\n", encoding="utf-8")
    (pack_root / "pack.yaml").write_text(f"{_BASE}pack_drg: graph/absent.yaml\n", encoding="utf-8")

    from charter.offering.drg.org_pack_loader import OrgPackMissingError

    with pytest.raises(OrgPackMissingError) as caught:
        load_org_pack("acme", pack_root, 1)
    assert caught.value.configured_path.endswith("graph/absent.yaml")
