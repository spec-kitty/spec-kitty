"""Unit tests for the shared org/project recursion authority (WP01 / T003).

The authority (:mod:`doctrine.discovery_recursion`) is the single seam both the
loader and the charter-activation resolver read so recursion cannot diverge per
kind (C-001, FR-002). Recursion is unconditional — every kind recurses — and the
authority never lists a non-recursive exclusion.
"""

from __future__ import annotations

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.discovery_recursion import (
    RECURSIVE_OVERLAY_KINDS,
    overlay_scan_is_recursive,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


def test_every_kind_is_recursive() -> None:
    """C-001: org/project overlay discovery recurses for every kind."""
    for kind in ArtifactKind:
        assert overlay_scan_is_recursive(kind) is True, kind


def test_recursive_overlay_kinds_is_the_whole_universe() -> None:
    """The recursive set is derived as the full ArtifactKind universe."""
    assert frozenset(ArtifactKind) == RECURSIVE_OVERLAY_KINDS


def test_no_kind_is_configured_non_recursive() -> None:
    """C-001 is a policy, not a per-kind toggle: no exclusions exist."""
    assert set(ArtifactKind) - RECURSIVE_OVERLAY_KINDS == set()


def test_unmapped_kind_none_still_recurses() -> None:
    """A scan that maps to no canonical kind (test stub) still recurses (C-001).

    The uniform policy has no silent non-recursive fallback, so a repository
    whose glob is not a canonical ``ArtifactKind.glob_pattern`` gets the same
    recursion rather than being quietly dropped.
    """
    assert overlay_scan_is_recursive(None) is True
