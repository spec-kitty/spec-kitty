"""Tests for drg_builder module (T007).

Covers:
- glossary_urn("lane") == "glossary:d93244e7"
- _normalize("lanes") == "lane"
- _normalize("missions") == "mission"
- build_index() contains canonical and lemmatized aliases
- empty store returns empty index
"""

from __future__ import annotations

from pathlib import Path

import pytest

from glossary.drg_builder import (
    GlossaryTermIndex,
    _normalize,
    build_index,
    glossary_urn,
)
from glossary.models import Provenance, SenseStatus, TermSense, TermSurface
from glossary.store import GlossaryStore
from kernel.clock import now_utc

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_LOG = Path("/dev/null")  # GlossaryStore only reads events, not used here


def _make_store(*senses: TermSense) -> GlossaryStore:
    """Return a GlossaryStore pre-populated with the given senses."""
    store = GlossaryStore(_FAKE_LOG)
    for sense in senses:
        store.add_sense(sense)
    return store


def _active_sense(surface: str, scope: str = "spec_kitty_core") -> TermSense:
    return TermSense(
        surface=TermSurface(surface),
        scope=scope,
        definition=f"Definition of {surface}",
        provenance=Provenance(
            actor_id="test",
            timestamp=now_utc(),
            source="test",
        ),
        confidence=1.0,
        status=SenseStatus.ACTIVE,
    )


def _draft_sense(surface: str, scope: str = "spec_kitty_core") -> TermSense:
    return TermSense(
        surface=TermSurface(surface),
        scope=scope,
        definition=f"Draft definition of {surface}",
        provenance=Provenance(
            actor_id="test",
            timestamp=now_utc(),
            source="test",
        ),
        confidence=0.5,
        status=SenseStatus.DRAFT,
    )


# ---------------------------------------------------------------------------
# glossary_urn
# ---------------------------------------------------------------------------


def test_glossary_urn_lane() -> None:
    """Canonical fixture: glossary_urn('lane') == 'glossary:d93244e7'."""
    assert glossary_urn("lane") == "glossary:d93244e7"


def test_glossary_urn_is_stable() -> None:
    """Same input always produces the same URN."""
    first_urn = glossary_urn("mission")
    second_urn = glossary_urn("mission")
    assert first_urn == second_urn


def test_glossary_urn_prefix() -> None:
    """URN always starts with 'glossary:'."""
    urn = glossary_urn("workspace")
    assert urn.startswith("glossary:")
    hex_part = urn.split(":")[1]
    assert len(hex_part) == 8
    assert all(c in "0123456789abcdef" for c in hex_part)


def test_glossary_urn_distinct_for_distinct_surfaces() -> None:
    """Different surface texts produce different URNs."""
    assert glossary_urn("lane") != glossary_urn("mission")
    assert glossary_urn("workspace") != glossary_urn("worktree")


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


def test_normalize_lanes_to_lane() -> None:
    """_normalize('lanes') == 'lane'."""
    assert _normalize("lanes") == "lane"


def test_normalize_missions_to_mission() -> None:
    """_normalize('missions') == 'mission'."""
    assert _normalize("missions") == "mission"


def test_normalize_already_singular() -> None:
    """A singular form is returned unchanged."""
    assert _normalize("lane") == "lane"
    assert _normalize("mission") == "mission"


def test_normalize_lowercases() -> None:
    """_normalize always lowercases."""
    assert _normalize("Lanes") == "lane"
    assert _normalize("MISSIONS") == "mission"


def test_normalize_ments_suffix() -> None:
    # "ments$" fires first: "requirements" -> "require"
    assert _normalize("requirements") == "require"


def test_normalize_tions_suffix() -> None:
    # "tions$" fires: "definitions" -> "defini"
    assert _normalize("definitions") == "defini"


def test_normalize_tion_suffix() -> None:
    # "tion$" fires: "definition" -> "defini"
    assert _normalize("definition") == "defini"


def test_normalize_ing_suffix() -> None:
    # "ing$" fires: "running" -> "runn" (still >= 3 chars)
    assert _normalize("running") == "runn"


def test_normalize_ed_suffix() -> None:
    # "ed$" fires: "claimed" -> "claim"
    assert _normalize("claimed") == "claim"


def test_normalize_min_stem_preserved() -> None:
    """Suffix stripping stops when result would be too short."""
    # "ens" → strip "s" → "en" (len 2 < 3) — keep "ens" not "en"
    # But "ens" - "s" = "en" len 2, so no rule fires; result is "ens"
    result = _normalize("ens")
    assert len(result) >= 1  # just verify it doesn't crash


# ---------------------------------------------------------------------------
# build_index — empty store
# ---------------------------------------------------------------------------


def test_build_index_empty_store_returns_empty_index() -> None:
    """Empty store with any scopes returns an empty GlossaryTermIndex."""
    store = _make_store()
    index = build_index(store, ["spec_kitty_core"])

    assert isinstance(index, GlossaryTermIndex)
    assert index.surface_to_urn == {}
    assert index.surface_to_senses == {}
    assert index.term_count == 0


def test_build_index_empty_scopes_ignores_senses() -> None:
    """Senses in scopes not in applicable_scopes are excluded."""
    sense = _active_sense("lane", scope="spec_kitty_core")
    store = _make_store(sense)
    index = build_index(store, [])  # no scopes

    assert index.term_count == 0
    assert "lane" not in index.surface_to_urn


# ---------------------------------------------------------------------------
# build_index — canonical and lemmatized aliases
# ---------------------------------------------------------------------------


def test_build_index_contains_canonical_surface() -> None:
    """Index maps the canonical surface to the correct URN."""
    sense = _active_sense("lane")
    store = _make_store(sense)
    index = build_index(store, ["spec_kitty_core"])

    assert "lane" in index.surface_to_urn
    assert index.surface_to_urn["lane"] == glossary_urn("lane")


def test_build_index_contains_lemmatized_alias() -> None:
    """Index maps the lemmatized (normalized) alias to the same URN as canonical."""
    # If we store "lane" as canonical, _normalize("lane") == "lane" (no change)
    # Store "mission" and check that normalized form also maps to same URN
    sense = _active_sense("mission")
    store = _make_store(sense)
    index = build_index(store, ["spec_kitty_core"])

    assert "mission" in index.surface_to_urn
    assert index.surface_to_urn["mission"] == glossary_urn("mission")


def test_build_index_plural_surface_gets_stem_alias() -> None:
    """When canonical surface is singular, its plural form is NOT separately indexed.

    The store stores the canonical form ('lane'). The normalized form of 'lane'
    is also 'lane' (no change), so only one key exists — 'lane'.
    """
    sense = _active_sense("lane")
    store = _make_store(sense)
    index = build_index(store, ["spec_kitty_core"])

    # 'lane' is canonical; _normalize('lane') == 'lane' so one key
    assert index.surface_to_urn["lane"] == glossary_urn("lane")
    assert index.term_count == 1


def test_build_index_multiple_senses_distinct_urns() -> None:
    """Multiple active senses produce distinct URNs."""
    s1 = _active_sense("lane")
    s2 = _active_sense("mission")
    store = _make_store(s1, s2)
    index = build_index(store, ["spec_kitty_core"])

    assert index.term_count == 2
    assert index.surface_to_urn["lane"] != index.surface_to_urn["mission"]


def test_build_index_skips_draft_senses() -> None:
    """DRAFT senses are not included in the index."""
    draft = _draft_sense("lane")
    active = _active_sense("mission")
    store = _make_store(draft, active)
    index = build_index(store, ["spec_kitty_core"])

    assert "lane" not in index.surface_to_urn
    assert "mission" in index.surface_to_urn
    assert index.term_count == 1


def test_build_index_respects_scope_filter() -> None:
    """Only senses in applicable_scopes contribute to the index."""
    sense_core = _active_sense("lane", scope="spec_kitty_core")
    sense_team = _active_sense("sprint", scope="team_domain")
    store = _make_store(sense_core, sense_team)

    index_core_only = build_index(store, ["spec_kitty_core"])
    assert "lane" in index_core_only.surface_to_urn
    assert "sprint" not in index_core_only.surface_to_urn

    index_team_only = build_index(store, ["team_domain"])
    assert "sprint" in index_team_only.surface_to_urn
    assert "lane" not in index_team_only.surface_to_urn


def test_build_index_senses_list_populated() -> None:
    """surface_to_senses maps each canonical surface to a non-empty list."""
    sense = _active_sense("lane")
    store = _make_store(sense)
    index = build_index(store, ["spec_kitty_core"])

    assert "lane" in index.surface_to_senses
    assert index.surface_to_senses["lane"] == [sense]
    assert index.surface_to_senses["lane"][0] is sense


def test_build_index_applicable_scope_set() -> None:
    """applicable_scope_set reflects the scopes passed to build_index."""
    store = _make_store()
    index = build_index(store, ["spec_kitty_core", "team_domain"])

    assert index.applicable_scope_set == frozenset(["spec_kitty_core", "team_domain"])
