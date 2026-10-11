"""The org load path reads ``pack.yaml`` and runs the level checks (FR-006/FR-007, WP02 T012).

Bounded regression anchor: ``load_org_pack`` is taught to read a pack's
``pack.yaml`` and refuse a declared level that disagrees with the org position
(``PACK_LEVEL_MISMATCH`` -> :class:`OrgPackSchemaError`) and warn on an absent
level (``PACK_LEVEL_MISSING``) — whether the ``pack.yaml`` omits ``pack_level``
or there is no ``pack.yaml`` at all (the legacy org pack the window targets).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.org_pack_loader import OrgPackSchemaError, load_org_pack
from kernel.pack_tiers import BUILT_IN, ORG

pytestmark = [pytest.mark.fast]

_BASE = "pack_id: 01ARWG13C000000000000000FG\nname: acme\n"


def _org_pack(root: Path, *, pack_yaml: str | None) -> Path:
    (root / "drg").mkdir(parents=True, exist_ok=True)
    (root / "drg" / "fragment.yaml").write_text("nodes: []\nedges: []\n", encoding="utf-8")
    if pack_yaml is not None:
        (root / "pack.yaml").write_text(pack_yaml, encoding="utf-8")
    return root


def test_matching_org_level_loads(tmp_path: Path) -> None:
    pack_root = _org_pack(tmp_path / "p", pack_yaml=f"{_BASE}pack_level: {ORG}\n")
    fragment = load_org_pack("acme", pack_root, 1)
    assert fragment.pack_name == "acme"


def test_no_pack_yaml_warns_and_proceeds(tmp_path: Path) -> None:
    # The legacy org pack the deprecation window targets: no pack.yaml at all
    # warns (PACK_LEVEL_MISSING, naming the file to add) and still loads (FR-007).
    pack_root = _org_pack(tmp_path / "p", pack_yaml=None)
    with pytest.warns(UserWarning, match="PACK_LEVEL_MISSING"):
        fragment = load_org_pack("acme", pack_root, 1)
    assert fragment.pack_name == "acme"


def test_built_in_level_in_org_position_refuses(tmp_path: Path) -> None:
    pack_root = _org_pack(tmp_path / "p", pack_yaml=f"{_BASE}pack_level: {BUILT_IN}\npack_version: 1.0.0\n")
    with pytest.raises(OrgPackSchemaError) as caught:
        load_org_pack("acme", pack_root, 1)
    message = str(caught.value)
    assert BUILT_IN in message and ORG in message
    assert caught.value.source_file == str(pack_root / "pack.yaml")


def test_missing_level_warns_and_proceeds(tmp_path: Path) -> None:
    pack_root = _org_pack(tmp_path / "p", pack_yaml=_BASE)  # no pack_level
    with pytest.warns(UserWarning, match="PACK_LEVEL_MISSING"):
        fragment = load_org_pack("acme", pack_root, 1)
    assert fragment.pack_name == "acme"
