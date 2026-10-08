"""Tests for ASSET registration in the migration extractor + doctrine CLI (WP05).

Covers:
- T019: ``_discover_built_in_artifact_nodes`` scans ``assets/built-in`` and
  registers discovered ``*.asset.yaml`` files as ``NodeKind.ASSET`` nodes.
- T019: ``_kind_for_type`` stays ``.get``-based (never a raising subscript), so
  an unknown/new reference type is skipped cleanly instead of raising
  ``KeyError``. (WP04 of ``doctrine-silence-guards-01KYFV7Q`` made ``_KIND_MAP``
  itself total over ``NodeKind``; the ``.get`` contract at this read site is
  unchanged and still guards typo'd reference types.)
- T020: ``doctrine.py::_SUFFIX_TO_KIND`` resolves ``*.asset.yaml`` to the
  ``("assets", "asset")`` kind pair.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.migration.extractor import (
    _KIND_MAP,
    _discover_built_in_artifact_nodes,
    _kind_for_type,
)
from charter.offering.drg.models import DRGNode, NodeKind
from specify_cli.cli.commands.charter.authoring import _detect_artifact_kind

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]


def test_discover_built_in_artifact_nodes_registers_assets(tmp_path: Path) -> None:
    """A ``*.asset.yaml`` file under ``assets/built-in`` becomes an ASSET node."""
    assets_dir = tmp_path / "assets" / "built-in"
    assets_dir.mkdir(parents=True)
    (assets_dir / "brand-logo.asset.yaml").write_text(
        "id: brand-logo\nname: Brand Logo\n", encoding="utf-8"
    )

    nodes_by_urn: dict[str, DRGNode] = {}
    _discover_built_in_artifact_nodes(tmp_path, nodes_by_urn)

    node = nodes_by_urn.get("asset:brand-logo")
    assert node is not None
    assert node.kind == NodeKind.ASSET
    assert node.label == "Brand Logo"


def test_discover_built_in_artifact_nodes_skips_missing_assets_dir(
    tmp_path: Path,
) -> None:
    """No ``assets/built-in`` directory is a no-op, not an error."""
    nodes_by_urn: dict[str, DRGNode] = {}
    _discover_built_in_artifact_nodes(tmp_path, nodes_by_urn)

    assert nodes_by_urn == {}


def test_kind_map_get_is_none_safe_for_unknown_type() -> None:
    """``_kind_for_type`` is ``.get``-based -- an unrecognised type returns ``None``.

    This is the regression guard: a raising subscript (``_KIND_MAP[ref_type]``)
    at *this* read site would crash on any reference ``type`` an author typos.

    Re-pinned by WP04 (FR-004). The probe used to be ``asset``, on the reasoning
    that built-in reference fields never target assets by type. But ``asset`` is
    a ``NodeKind``, and using a real kind as the "unknown type" specimen is what
    let ``_KIND_MAP`` sit at 11 of 16 members with a test apparently vouching for
    it. ``_KIND_MAP`` is now derived from ``NodeKind`` and total; the probe moved
    to a string that is genuinely not a kind, which is what the contract was ever
    about.
    """
    assert _kind_for_type("asset") is NodeKind.ASSET
    assert _KIND_MAP.get("some-future-kind-not-yet-registered") is None
    assert _kind_for_type("some-future-kind-not-yet-registered") is None


def test_suffix_to_kind_resolves_asset_yaml() -> None:
    """``doctrine.py::_SUFFIX_TO_KIND`` maps ``*.asset.yaml`` to ``("assets", "asset")``."""
    result = _detect_artifact_kind(Path("brand-logo.asset.yaml"))
    assert result == ("assets", "asset")
