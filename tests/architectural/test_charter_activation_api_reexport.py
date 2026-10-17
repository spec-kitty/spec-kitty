"""The ``charter.activation.api`` seam is a pure, split, identity re-export surface.

Companion to :mod:`tests.architectural.test_charter_facades_reexport_offering` (the
offering seam's identity gate). It pins three invariants on the activation seam
(``src/charter/activation/api.py``, #6188 / #6099):

1. **Identity** — every exported symbol IS the exact object from its
   ``charter.activation`` source module (no wrapper/shim/alias copy), so consumers
   bind the real object and the seam can be swapped without semantic drift.
2. **``__all__`` completeness** — every tabled symbol is advertised in
   ``charter.activation.api.__all__`` (and vice-versa), so the public surface is
   exactly the enumerated contract.
3. **Split from offering** — the activation seam re-exports ONLY
   ``charter.activation`` symbols, never a ``charter.offering`` one. Offering and
   activation are separate extractable units (ADR ``2026-10-06-2`` §1); an offering
   symbol belongs on ``charter.offering.api`` / the ``charter.*`` offering facades,
   never here.

When the seam grows (a consumer is drained onto it), add the (symbol, source
module) row below.
"""

from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.architectural

#: (symbol, charter.activation source module). Keep in sync with charter.activation.api.__all__.
_SEAM_TABLE: list[tuple[str, str]] = [
    ("canonical_mission_type_key", "charter.activation.mission_type_key"),
    ("read_mission_type", "charter.activation.mission_type_key"),
    ("requires_substantive_spec_for", "charter.activation.mission_type_profiles"),
]


@pytest.mark.parametrize(
    ("symbol", "source_module"),
    _SEAM_TABLE,
    ids=[f"{s}" for s, _ in _SEAM_TABLE],
)
def test_seam_reexports_activation_symbol_by_identity(symbol: str, source_module: str) -> None:
    seam = importlib.import_module("charter.activation.api")
    source = importlib.import_module(source_module)
    seam_obj = getattr(seam, symbol)
    source_obj = getattr(source, symbol)
    assert seam_obj is source_obj, (
        f"charter.activation.api.{symbol} must be the same object as {source_module}.{symbol} — the seam is a pure identity re-export, no wrapper."
    )


def test_seam_all_matches_table() -> None:
    seam = importlib.import_module("charter.activation.api")
    all_ = getattr(seam, "__all__", None)
    assert all_ is not None, "charter.activation.api must define __all__"
    tabled = {symbol for symbol, _ in _SEAM_TABLE}
    assert set(all_) == tabled, (
        f"charter.activation.api.__all__ must equal the identity-contract table: missing={sorted(tabled - set(all_))}, extra={sorted(set(all_) - tabled)}"
    )


def test_seam_reexports_only_activation_never_offering() -> None:
    """The split invariant: the activation seam never fronts a charter.offering symbol."""
    seam = importlib.import_module("charter.activation.api")
    for name in seam.__all__:
        obj = getattr(seam, name)
        origin = getattr(obj, "__module__", "") or ""
        assert not origin.startswith("charter.offering"), (
            f"charter.activation.api.{name} originates from {origin}: an offering symbol must "
            "be exported from charter.offering.api / a charter.* offering facade, not the "
            "activation seam (offering/activation are separate extractable units)."
        )
        # A class/function carries a usable ``__module__`` (empty for a plain
        # constant/value, which is fine); when present it must stay inside charter.
        if origin:
            assert origin.startswith("charter."), f"charter.activation.api.{name} originates from {origin}, outside charter."
