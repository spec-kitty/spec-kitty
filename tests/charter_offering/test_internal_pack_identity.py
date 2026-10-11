"""Identity + org-pack-load contract for ``packs/internal/pack.yaml`` (WP04, T020).

FR-012: the in-house maintainer pack (``packs/internal/``) is an ORG-tier
Charter Pack that now carries an authored ``pack.yaml`` descriptor. This module
pins two facts:

* **Identity drift guard** -- internal's ``pack_id`` is a stable, minted ULID,
  pinned here exactly as it is authored on disk (mirrors the built-in
  ``pack_id`` pin in
  :mod:`tests.charter.test_retired_accompanies_doctrine_pack`). A regenerated or
  accidentally-remitted id fails loudly instead of silently re-identifying the
  pack.
* **Loads as an org pack** -- the descriptor validates as an ORG-level
  :class:`~charter.offering.packs.pack_descriptor.PackDescriptor` with the
  declared active-charter / DRG pointers, and its ``drg/fragment.yaml`` loads
  through the real org-pack loader
  (:func:`~charter.offering.drg.org_pack_loader.load_org_pack`).

``packs/internal/`` is NEVER wheel-shipped (C-004); this test reads it from the
repository source tree (``<repo>/packs/internal``), so it deliberately does not
carry :data:`pytest.mark.corpus` (that marker is for the wheel-shipped built-in
corpus only -- see
``tests/architectural/test_ci_corpus_trigger_completeness.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.drg.org_pack_loader import OrgDRGFragment, load_org_pack
from charter.offering.packs.pack_descriptor import load_pack_descriptor
from kernel.pack_tiers import ORG

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INTERNAL_ROOT = _REPO_ROOT / "packs" / "internal"

# The pinned, minted ULID identity of the internal org pack. Immutable: changing
# it re-identifies the pack. If this ever needs to change, it is a deliberate,
# reviewed act -- update packs/internal/pack.yaml and this constant together.
_INTERNAL_PACK_ID = "01M4P01D5TWB5FKZGNNQG3943R"


def test_internal_pack_id_is_the_pinned_minted_ulid() -> None:
    descriptor = load_pack_descriptor(_INTERNAL_ROOT / "pack.yaml")

    assert descriptor.pack_id == _INTERNAL_PACK_ID, (
        "packs/internal/pack.yaml pack_id drifted from the pinned minted ULID; the id is immutable -- a regenerated id silently re-identifies the pack"
    )
    assert isinstance(descriptor.pack_id, str) and len(descriptor.pack_id) == 26, "internal pack_id must be a 26-char ULID"


def test_internal_pack_loads_as_an_org_pack_with_declared_pointers() -> None:
    descriptor = load_pack_descriptor(_INTERNAL_ROOT / "pack.yaml")

    assert descriptor.pack_level == ORG, "packs/internal is an org-tier pack (FR-012)"
    assert descriptor.name == "spec-kitty-internal"
    assert descriptor.parent_pack is None, "the internal pack is a lineage root"
    # Internal is UNSHARDED -- it declares its active-charter + DRG pointers
    # explicitly rather than relying on the built-in sharded convention.
    assert descriptor.active_charter == "org-charter.yaml"
    assert descriptor.pack_drg == "drg/fragment.yaml"

    # The declared DRG pointer resolves: the fragment loads through the real
    # org-pack loader as a valid org fragment.
    fragment = load_org_pack("spec-kitty-internal", _INTERNAL_ROOT, layer_index=1)
    assert isinstance(fragment, OrgDRGFragment)
    assert fragment.pack_name == "spec-kitty-internal"


def test_internal_pack_declares_no_pack_version() -> None:
    """An org pack need not author ``pack_version`` (FR-005); internal omits it."""
    descriptor = load_pack_descriptor(_INTERNAL_ROOT / "pack.yaml")
    assert descriptor.pack_version is None
