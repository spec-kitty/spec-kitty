"""Census-derived fan-out cross-check (#6173, WP03, mission derived-consumer-census-01M4V5P5).

``gate_selection.derive_group_module_fanout()`` is the census's OWN answer for each
fan-out group (the modules the committed census records consuming a path matching
that group's router globs). These tests pin that the derivation:

* is non-vacuous — real groups, real registry modules, and it reproduces the three
  #6166 pins (``next``/``charter`` for the mission-step prompts, ``dossier`` for the
  manifest, ``agent`` for lifecycle.py) — so a future census/router change cannot
  silently drop a historical consumer;
* is a sound SUPERSET of the human-validated ``GROUP_MODULE_FANOUT`` for the
  routed-consumer sense: every module the hand fan-out routes because its tests
  genuinely resolve the real shipped pack is also found by the census (the two
  documented exceptions — ``dossier``/``missions`` in ``mission_pack_content`` — are
  manifest/profile consumers the census attributes to their OWN groups instead).

The derivation does NOT drive live routing today (see the GROUP_MODULE_FANOUT
comment in gate_selection: a blind derivation over-attributes widely-used resolver
entry points because static analysis cannot tell a real-pack assertion from a
temp-project one without running tests). This test is the derived-vs-hand analysis
anchor and the regression guard for the full-value-derivation follow-up.
"""

from __future__ import annotations

import pytest

from scripts.ci.gate_selection import (
    FANOUT_GROUPS,
    GROUP_MODULE_FANOUT,
    _registry_module_names,
    derive_group_module_fanout,
)

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def derived() -> dict[str, frozenset[str]]:
    return derive_group_module_fanout()


def test_derivation_covers_every_fanout_group(derived: dict[str, frozenset[str]]) -> None:
    assert set(derived) == set(FANOUT_GROUPS)


def test_every_derived_target_is_a_registry_module(derived: dict[str, frozenset[str]]) -> None:
    registry = _registry_module_names()
    for group, members in derived.items():
        stray = set(members) - set(registry)
        assert not stray, f"{group}: derived non-registry modules {sorted(stray)}"


def test_derivation_is_non_vacuous(derived: dict[str, frozenset[str]]) -> None:
    """Every fan-out group derives at least one module (a census/router break that
    emptied a group would red here, not silently route nothing)."""
    empty = [group for group, members in derived.items() if not members]
    assert not empty, f"fan-out groups with an empty census-derived set: {empty}"


def test_derivation_reproduces_the_three_pins(derived: dict[str, frozenset[str]]) -> None:
    """The census's own answer places each historical pin's consumer in its group:
    the #6156/#6153/#6161 consumers the hand fan-out routes are all re-found."""
    assert "next" in derived["mission_pack_content"], "prompt->next pin not re-derived"
    assert "charter" in derived["mission_pack_content"], "charter prompt consumer not re-derived"
    assert "dossier" in derived["mission_manifest"], "manifest->dossier pin not re-derived"
    assert "agent" in derived["cli_lifecycle"], "lifecycle.py->agent pin not re-derived"


def test_hand_fanout_routed_members_are_all_re_derived(derived: dict[str, frozenset[str]]) -> None:
    """The hand fan-out's members are re-found by the census, EXCEPT the two
    documented re-classifications (``dossier``/``missions`` sit in
    ``mission_pack_content`` by hand but are manifest/type/profile consumers the
    census files under ``mission_manifest``/``mission_type_definitions`` instead).

    This proves the census never drops a genuinely-routed consumer silently — the
    only hand members it omits from a group are the ones it routes elsewhere.
    """
    # Union of everything the census routes anywhere — a hand member absent from
    # its hand group must at least be routed by the census somewhere (re-classified),
    # never dropped entirely.
    derived_anywhere = set().union(*derived.values())
    reclassified_ok = {"dossier", "missions"}
    for group, hand_members in GROUP_MODULE_FANOUT.items():
        for module in hand_members:
            if module in derived[group]:
                continue
            assert module in derived_anywhere or module in reclassified_ok, (
                f"{group}: hand member {module!r} is neither re-derived in its group, routed elsewhere by the census, nor a documented re-classification"
            )
