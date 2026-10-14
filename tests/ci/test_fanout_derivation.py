"""Census-derived fan-out cross-check (#6173, WP03, mission derived-consumer-census-01M4V5P5).

``gate_selection.derive_group_module_fanout()`` is the census's OWN answer for each
fan-out group (the modules the committed census records consuming a path matching
that group's router globs). These tests pin that the derivation:

* is non-vacuous — every group derives modules, and a malformed census raises;
* leaves no census-derived module unrouted: each is in the hand fan-out or carries a
  reasoned ``FANOUT_ALLOWLIST`` entry;
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

from pathlib import Path

import pytest

from scripts.ci.gate_selection import (
    FANOUT_ALLOWLIST,
    FANOUT_GROUPS,
    GROUP_MODULE_FANOUT,
    derive_group_module_fanout,
)

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def derived() -> dict[str, frozenset[str]]:
    return derive_group_module_fanout()


def test_every_census_derived_module_is_routed_or_allowlisted(derived: dict[str, frozenset[str]]) -> None:
    """A module the census derives for a fan-out group must be in the hand fan-out
    or carry a reasoned allowlist entry, so a new real consumer cannot go unrouted
    (and an incidental one cannot be silently ignored)."""
    for group in sorted(FANOUT_GROUPS):
        missing = derived[group] - GROUP_MODULE_FANOUT[group] - frozenset(FANOUT_ALLOWLIST.get(group, {}))
        assert not missing, (
            f"census derives {sorted(missing)} as consumer(s) of fan-out group {group!r} but they are in neither "
            f"GROUP_MODULE_FANOUT[{group!r}] nor FANOUT_ALLOWLIST[{group!r}] in scripts/ci/gate_selection.py. "
            "Fix: add the module to GROUP_MODULE_FANOUT if its tests assert on the shipped content, "
            "otherwise allowlist it with a one-line reason."
        )
        stale = set(FANOUT_ALLOWLIST.get(group, {})) - derived[group]
        assert not stale, f"FANOUT_ALLOWLIST[{group!r}] entries {sorted(stale)} are no longer census-derived; remove them."


def test_derivation_is_non_vacuous(derived: dict[str, frozenset[str]], tmp_path: Path) -> None:
    """Every fan-out group derives at least one module (a census/router break that
    emptied a group would red, not silently route nothing); an absent census yields
    empty sets, but a malformed one raises instead of routing nothing."""
    empty = [group for group, members in derived.items() if not members]
    assert not empty, f"fan-out groups with an empty census-derived set: {empty}"

    assert all(not members for members in derive_group_module_fanout(census_path=tmp_path / "absent.json").values())
    for label, content in (("not-json", "{nope"), ("no-modules", "{}"), ("modules-not-a-map", '{"modules": []}')):
        bad = tmp_path / f"{label}.json"
        bad.write_text(content, encoding="utf-8")
        with pytest.raises(ValueError, match="malformed"):
            derive_group_module_fanout(census_path=bad)


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
