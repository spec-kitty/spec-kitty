"""Charter kind-vocabulary collapse onto the derived authority (WP03 / #2981).

Red-first: on `main` the two `_activation_render` copies had drifted two kinds
behind the authoritative 10-kind set, so `_singular_kind("glossary_packs")`
failed open (returned the plural verbatim) and `_infer_kind` was blind to
`glossary_packs`. After WP03 both derive from the single
`doctrine.artifact_kinds` authority, and no charter module re-declares a local
plural↔singular kind dict (FR-004).
"""

from __future__ import annotations

import pytest

from charter.activation import _activation_render
from charter.activation._activation_render import _infer_kind, _singular_kind
from charter.activation.activations import _PLURAL_TO_SINGULAR_KIND, _SINGULAR_TO_PLURAL_KIND
from charter.offering.artifact_kinds import (
    CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR,
    CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL,
)

pytestmark = [pytest.mark.fast, pytest.mark.unit]


# ── T014: _singular_kind drift (fails open pre-fix) ───────────────────────────


def test_singular_kind_resolves_glossary_pack() -> None:
    """`glossary_packs` -> `glossary_pack` (drifted map returned it verbatim)."""
    assert _singular_kind("glossary_packs") == "glossary_pack"


def test_singular_kind_resolves_anti_pattern() -> None:
    assert _singular_kind("anti_patterns") == "anti_pattern"


def test_singular_kind_unknown_plural_passes_through() -> None:
    assert _singular_kind("not_a_kind") == "not_a_kind"


# ── T015: _infer_kind blind to glossary_packs pre-fix ─────────────────────────


class _Repo:
    def __init__(self, ids: set[str]) -> None:
        self._ids = ids

    def get(self, artifact_id: str) -> object | None:
        return object() if artifact_id in self._ids else None


class _Service:
    """Minimal ActiveCharterService double exposing only a glossary_packs repo."""

    def __init__(self) -> None:
        self.glossary_packs = _Repo({"spec-kitty-core"})


def test_infer_kind_finds_glossary_pack() -> None:
    """`_infer_kind` now scans `service.glossary_packs` (was skipped pre-fix)."""
    assert _infer_kind("spec-kitty-core", _Service()) == "glossary_packs"


def test_infer_kind_unknown_id_returns_none() -> None:
    assert _infer_kind("nonexistent", _Service()) is None


# ── T019: derived, no local dict; anti_patterns inert in property map ─────────


def test_activations_maps_are_the_derived_authority() -> None:
    """FR-004: activations imports the authority — no re-declared local dict."""
    assert _SINGULAR_TO_PLURAL_KIND is CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL
    assert _PLURAL_TO_SINGULAR_KIND is CHARTER_ACTIVATABLE_PLURAL_TO_SINGULAR


def test_kind_to_property_covers_all_activatable_plurals() -> None:
    assert set(_activation_render._KIND_TO_PROPERTY) == set(CHARTER_ACTIVATABLE_SINGULAR_TO_PLURAL.values())
    # property name == plural for every kind
    assert all(k == v for k, v in _activation_render._KIND_TO_PROPERTY.items())


def test_anti_patterns_property_is_inert_no_crash() -> None:
    """`anti_patterns` is in the property map but has no service repo (getattr None).

    A service lacking `anti_patterns` must not crash `_infer_kind`.
    """
    assert "anti_patterns" in _activation_render._KIND_TO_PROPERTY
    assert _infer_kind("whatever", _Service()) is None  # no anti_patterns attr → skipped
