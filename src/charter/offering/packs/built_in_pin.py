"""Transitional alias module for the built-in pin (#3504, #6451).

The pin model now lives in :mod:`charter.offering.packs.pack_pin` and serves
every pack. This module keeps the old ``BuiltInPin`` names importable.

Removal target: delete this module once its callers (``pack_vendor.py``, the
WP06/WP07 fetch-based resolver work, and ``test_built_in_release_parity.py``)
move to ``pack_pin``.
"""

from __future__ import annotations

from pathlib import Path

from charter.offering.packs.pack_pin import (
    PackPin,
    PackPinError,
    load_pack_pin,
    verify_pack_pin,
    write_pack_pin,
)

__all__ = [
    "BuiltInPin",
    "BuiltInPinError",
    "load_built_in_pin",
    "verify_built_in_pin",
    "write_built_in_pin",
]

BuiltInPin = PackPin
BuiltInPinError = PackPinError


def load_built_in_pin(path: Path) -> PackPin:
    """Load a pin leniently: legacy callers' lockfiles may predate ``subtree``."""
    return load_pack_pin(path, require_subtree=False)


def verify_built_in_pin(pin: PackPin, pack_root: Path) -> bool:
    """Alias of :func:`verify_pack_pin`."""
    verified: bool = verify_pack_pin(pin, pack_root)
    return verified


def write_built_in_pin(pin: PackPin, path: Path) -> None:
    """Alias of :func:`write_pack_pin`."""
    write_pack_pin(pin, path)
