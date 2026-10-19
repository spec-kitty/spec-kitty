"""Identity + org-pack-load contract for ``packs/internal/pack.yaml`` (WP04, T020; WP07).

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

import sys
from pathlib import Path

import pytest

from charter.offering.drg.org_pack_loader import OrgDRGFragment, load_org_pack
from charter.offering.packs.pack_descriptor import PackDescriptor, load_pack_descriptor
from charter.offering.packs.pack_fetch import PackTreeStatus, check_pack
from charter.offering.packs.pack_pin import PackPin, load_pack_pin
from kernel.pack_tiers import ORG

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INTERNAL_ROOT = _REPO_ROOT / "packs" / "internal"
_INTERNAL_PIN = _REPO_ROOT / "packs" / "internal.source.yaml"
_PLACEHOLDER_SHA = "0" * 40

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


def _synced_internal_descriptor(pin: PackPin) -> PackDescriptor:
    """Return the descriptor of the synced internal tree, proven to be the pinned one without network.

    ``check_pack`` re-hashes ``packs/internal`` against the pin's clean-tree digest, so a
    passing check means the tree on disk is byte-for-byte the pinned open-packs tree.
    Absence or staleness fails loudly (no skip): the fast tier never contacts the network.
    """
    if pin.commit == _PLACEHOLDER_SHA:
        pytest.fail(
            "packs/internal.source.yaml still pins the placeholder commit: the open-packs PR carrying "
            "pack_version and pack_level: org for packs/internal is pending (#6451, WP01); "
            "set the merged SHA and digest, then run `make sync-packs`."
        )
    status = check_pack(pin, _INTERNAL_ROOT)
    if status is not PackTreeStatus.OK:
        pytest.fail(f"packs/internal is {status.value} against packs/internal.source.yaml (tree absent or not the pinned digest); run `make sync-packs`")
    return load_pack_descriptor(_INTERNAL_ROOT / "pack.yaml")


def test_internal_pack_version_equals_open_packs_pinned_value() -> None:
    """The synced internal pack is the digest-verified pinned tree and declares ``pack_version`` and ``org`` level.

    Never None-tolerant and never networked: a missing version fails, an unsynced tree fails.
    """
    descriptor = _synced_internal_descriptor(load_pack_pin(_INTERNAL_PIN))

    assert descriptor.pack_version is not None, "open-packs pinned internal pack.yaml must declare pack_version"
    assert descriptor.pack_level == ORG, "open-packs pinned internal pack must stay pack_level: org"


def test_unsynced_internal_tree_fails_loudly_naming_make_sync_packs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys.modules[__name__], "_INTERNAL_ROOT", tmp_path / "absent")
    with pytest.raises(pytest.fail.Exception, match="make sync-packs"):
        _synced_internal_descriptor(load_pack_pin(_INTERNAL_PIN))
