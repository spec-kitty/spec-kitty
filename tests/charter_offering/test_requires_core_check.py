"""FR-014 — reusable ``requires_core`` compatibility predicate (#3504 tooling).

A satisfied version-specifier range passes, an unsatisfied range fails, and an
absent ``requires_core`` imposes no constraint (passes). The predicate is pure:
it reads only the descriptor's ``requires_core`` and the candidate core version.
"""

from __future__ import annotations

from charter.offering.packs.core_compat import check_requires_core
from charter.offering.packs.pack_descriptor import PackDescriptor

_PACK_ID = "01ARWG13C000000000000000FG"


def _descriptor(requires_core: str | None) -> PackDescriptor:
    return PackDescriptor.model_validate(
        {
            "pack_id": _PACK_ID,
            "name": "sample",
            "pack_level": "org",
            "requires_core": requires_core,
        }
    )


def test_satisfied_range_passes() -> None:
    assert check_requires_core(_descriptor(">=4.0,<5.0"), "4.2") is True


def test_boundary_lower_inclusive_passes() -> None:
    assert check_requires_core(_descriptor(">=4.0,<5.0"), "4.0") is True


def test_unsatisfied_range_fails() -> None:
    assert check_requires_core(_descriptor(">=4.0,<5.0"), "5.1") is False


def test_absent_requires_core_passes() -> None:
    assert check_requires_core(_descriptor(None), "4.2") is True
    assert check_requires_core(_descriptor(None), "99.0") is True
