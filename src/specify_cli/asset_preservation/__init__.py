"""Prove-ownership-or-preserve guard for Spec Kitty mutating flows.

The single shared decision surface that ``init``, ``upgrade`` and migrations
route every destructive removal of a user-visible command/skill/template/
governance path through, so name/directory identity can never authorize
deleting user-authored content (charter L463-479). See
``kitty-specs/ownership-boundary-preservation-01M32KEN/contracts/ownership-guard-contract.md``.

This package is deliberately distinct from ``specify_cli.ownership`` (which is
work-package scope ownership) — its job is *preservation on unproven ownership*.
"""

from __future__ import annotations

from specify_cli.asset_preservation.guard import (
    OverwriteVerdict,
    OwnershipVerdict,
    guard_destructive_overwrite,
    guard_destructive_removal,
)
from specify_cli.asset_preservation.provers import (
    AnyProver,
    CanonicalContentProver,
    ManagedPathProver,
    ManifestProver,
    OwnershipProver,
)

__all__ = [
    "AnyProver",
    "CanonicalContentProver",
    "ManagedPathProver",
    "ManifestProver",
    "OverwriteVerdict",
    "OwnershipProver",
    "OwnershipVerdict",
    "guard_destructive_overwrite",
    "guard_destructive_removal",
]
