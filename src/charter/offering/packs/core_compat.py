"""FR-014 — reusable ``requires_core`` compatibility predicate.

A pack may declare ``requires_core`` (a PEP 440 version specifier, validated at
descriptor-load time) naming the Spec Kitty core versions it supports. This
module exposes the single pure predicate #3504 vendor tooling calls to decide
whether a given core version satisfies that constraint.

Kept separate from the descriptor model (and from ``snapshot_sha256`` /
``builtin_manifest``) so it stays a thin, side-effect-free check with no I/O.
"""

from __future__ import annotations

from packaging.specifiers import SpecifierSet

from charter.offering.packs.pack_descriptor import PackDescriptor

__all__ = ["check_requires_core"]


def check_requires_core(descriptor: PackDescriptor, core_version: str) -> bool:
    """Return whether *core_version* satisfies ``descriptor.requires_core``.

    An absent ``requires_core`` means no constraint, so the check passes. When
    present, the constraint is the descriptor's already-validated PEP 440
    version specifier and the result is ``core_version in SpecifierSet(...)``.

    Pure predicate: reads only the descriptor's declared specifier and the
    candidate version, performs no I/O, and raises nothing for a well-formed
    descriptor (``requires_core`` is validated as a specifier at load time).
    """
    specifier = descriptor.requires_core
    if specifier is None:
        return True
    return core_version in SpecifierSet(specifier)
