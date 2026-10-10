"""``kernel.pack_tiers``: the single authority for the Charter Pack tier token.

Closes the tier-spelling half of #5825 / #5961. The tier token historically
carried two spellings -- ``"built-in"`` (the tier-token sense and the on-disk
``packs/built-in/`` directory) and ``"builtin"`` (a parallel, frozen
provenance/layer/rank vocabulary). The operator decision (WP04) is to unify the
**tier token** on the single hyphenated spelling ``"built-in"`` in one
kernel-owned authority, importable by ``kernel``, ``charter`` and
``specify_cli``.

These tests are the single-spelling invariant (FR-012): exactly one spelling,
``built-in``; the ordered tuple is the precedence rank (built-in < org <
project); and the ``PackTier`` type alias names the same three tokens. Written
RED-first (C-003) -- they fail with ``ModuleNotFoundError`` until
``src/kernel/pack_tiers.py`` exists.
"""

from __future__ import annotations

import typing

import pytest

from kernel import pack_tiers

pytestmark = [pytest.mark.fast]


def test_pack_tiers_tuple_is_ordered_built_in_first() -> None:
    """``PACK_TIERS`` is the ordered authority: index == precedence rank."""
    rank = pack_tiers.PACK_TIERS.index
    assert rank(pack_tiers.BUILT_IN) < rank(pack_tiers.ORG) < rank(pack_tiers.PROJECT)


def test_pack_tier_literal_names_exactly_the_three_tokens() -> None:
    """``PackTier`` is a ``Literal`` of the same three single-spelled tokens."""
    members = set(typing.get_args(pack_tiers.PackTier))
    assert members == {"built-in", "org", "project"}
    assert members == set(pack_tiers.PACK_TIERS)
