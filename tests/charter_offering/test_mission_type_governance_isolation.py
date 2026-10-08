"""Enduring enforcement: mission-type governance isolation (contract C5).

WP12 — the join. These are **behavioural** assertions on the *resolved URN set*
that a real mission of each type surfaces through the single charter-mediated
seam (:func:`charter.activation.mission_type_profiles.resolve_mission_type_context`).
They deliberately do **not** ratchet on code shape — they assert on the doctrine a
mission would actually be governed by.

The four contract obligations (C5 / resolution-and-enforcement.md):

* **Non-leakage** — for each non-software type (documentation / research / plan)
  the resolved *(type ⊕ action)* URN set is **disjoint** from a curated,
  URN-normalized software-dev-only denylist.
* **Non-vacuity twin** — the SAME denylist **is** resolved by ``software-dev``,
  exercised through the shared ``bundle.governance`` union, so the non-leakage
  pass cannot succeed vacuously (i.e. by never resolving anything). If
  ``software-dev`` stops resolving the denylist,
  :func:`test_non_vacuity_twin_software_dev_resolves_denylist` fails loud.
* **Determinism (NFR-007)** — two resolutions of identical inputs are
  byte-identical.
* **Hard-fail / degrade** — an unknown *typed* mission raises; a known type with
  an empty grain resolves empty (no error); a typeless caller degrades neutrally
  (never software-dev).

The denylist is the software-dev *implement*-action doctrine — TDD/git-flow
governance that is meaningless for a documentation, research, or plan mission.
It is homed **only** in ``src/charter/offering/missions/software-dev/actions/implement/index.yaml``;
this test pins that it never leaks into the other three domains.

WP03 wired the live action-grain union into ``bundle.governance`` itself (lazily,
behind a ``cached_property`` thunk — accessing ``.governance`` now triggers the
real ``charter.activation.action_grain.aggregate_action_grain`` union, covering EVERY
action the mission type ships, not just a probe subset). WP05 reconciled this
test onto that single source (C-002 / FR-006): ``_resolve_union`` used to
independently re-union ``load_action_index`` over a probe action list — a
second, competing implementation of the exact union ``bundle.governance``
already performs. That loop is deleted; ``_resolve_union`` now reads
``bundle.governance`` directly. ``test_probe_action_implement_is_shared_and_load_bearing``
below still calls ``load_action_index`` directly (not via ``_resolve_union``) to
probe the *raw* action index in isolation from the resolver — that is a
deliberate, independent check, not a union loop.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.mission_type_profiles import (
    ResolvedGovernance,
    UnknownMissionTypeError,
    resolve_mission_type_context,
)
from charter.offering.missions.action_index import ActionIndex, load_action_index
from charter.offering.missions.repository import MissionTemplateRepository

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


@pytest.fixture(autouse=True)
def _provision_all_builtin_mission_types(tmp_path: Path) -> None:
    """Provision the per-test ``tmp_path`` with the four built-in mission types.

    These tests resolve ``software-dev`` / ``documentation`` / ``research`` /
    ``plan`` through ``resolve_mission_type_context`` against ``tmp_path``. The
    WP04 construction-total pivot made ``PackContext`` construction total (an
    absent ``mission_type_activations`` key reads as ``frozenset()``), so an
    unprovisioned ``tmp_path`` resolves an EMPTY activation set and the resolver
    hard-fails at the use boundary with ``UnknownMissionTypeError`` for any
    typed request. A usable project is provisioned; declaring the four
    built-ins here is exactly that. The negative-path tests (unknown/typeless)
    are unaffected — an unregistered id and a typeless caller behave the same
    with or without this activation set.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n  - documentation\n"
        "  - research\n  - plan\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Doctrine source roots + canonical URN normalization
# ---------------------------------------------------------------------------

#: On-disk root of the shipped mission doctrine (``packs/built-in/missions``,
#: relocated from ``src/charter/offering/missions`` by mission
#: doctrine-consumer-surface-missions-extraction-01KZ6G6H, FR-005). The
#: retired ``Path(charter.offering.missions.__file__).resolve().parent`` construction
#: would resolve to the now data-less ``.py``-only package directory instead.
MISSIONS_ROOT: Path = MissionTemplateRepository.default_missions_root()

#: The non-software mission types whose resolved governance MUST be free of
#: software-dev-only doctrine (FR-005 / SC-001).
NON_SOFTWARE_TYPES: tuple[str, ...] = ("documentation", "research", "plan")

#: Plural governance-kind → singular URN prefix (the form the shipped DRG uses,
#: e.g. ``paradigm:git-flow``). Load-bearing for the disjointness comparison key.
_KIND_SINGULAR: dict[str, str] = {
    "directives": "directive",
    "tactics": "tactic",
    "paradigms": "paradigm",
    "styleguides": "styleguide",
    "toolguides": "toolguide",
    "procedures": "procedure",
    "agent_profiles": "agent_profile",
}

#: The shared probe action list applied to **every** mission type. It is exactly
#: the software-dev action set, so ``implement`` — the sole home of the denylist
#: doctrine — is exercised uniformly across all four types. This is what makes
#: the non-leakage assertion non-vacuous: documentation/research/plan are probed
#: with the *same* ``implement`` action that surfaces the denylist for
#: software-dev; they simply have no such action index, so it contributes
#: nothing (an empty fallback), which is precisely the property under test.
_SHARED_PROBE_ACTIONS: tuple[str, ...] = (
    "implement",
    "plan",
    "specify",
    "tasks",
    "review",
    "retrospect",
)

#: The software-dev-only governance denylist, expressed as canonical URNs. Every
#: entry is authored **only** in
#: ``src/charter/offering/missions/software-dev/actions/implement/index.yaml`` and is
#: nonsensical for a docs/research/plan mission (TDD, git-flow branching,
#: refactoring/bug-fix procedures).
SOFTWARE_DEV_ONLY_DENYLIST: frozenset[str] = frozenset(
    {
        "paradigm:git-flow",
        "paradigm:trunk-based",
        "paradigm:shared-branch-ci",
        "directive:034-test-first-development",
        "tactic:tdd-red-green-refactor",
        "tactic:acceptance-test-first",
        "procedure:refactoring",
        "procedure:test-first-bug-fixing",
    }
)


def _canonical_urn(kind_plural: str, raw: str) -> str:
    """Normalize an artifact reference to a ``<kind>:<slug>`` canonical URN.

    Both sides of the disjointness comparison are normalized through this one
    function so ``git-flow`` (raw slug) and ``urn:paradigm:git-flow`` (URN form)
    collapse to the same ``paradigm:git-flow`` key. Including the kind prefix
    keeps distinct kinds that share a slug (or numeric code) from colliding.
    """
    text = raw.strip().lower()
    if text.startswith("urn:"):
        segments = text.split(":")
        return f"{segments[1]}:{segments[-1]}"
    return f"{_KIND_SINGULAR[kind_plural]}:{text}"


def _governance_urns(governance: ResolvedGovernance | None) -> set[str]:
    """Canonical URNs carried by a resolved type-grain governance bundle."""
    if governance is None:
        return set()
    urns: set[str] = set()
    for kind_plural in _KIND_SINGULAR:
        for raw in getattr(governance, f"selected_{kind_plural}"):
            urns.add(_canonical_urn(kind_plural, raw))
    return urns


def _action_urns(index: ActionIndex) -> set[str]:
    """Canonical URNs carried by a resolved doctrine action index (action grain)."""
    urns: set[str] = set()
    for kind_plural in _KIND_SINGULAR:
        for raw in getattr(index, kind_plural):
            urns.add(_canonical_urn(kind_plural, raw))
    return urns


def _resolve_union(mission_type: str, *, repo_root: Path) -> set[str]:
    """Resolve the *(type-grain ⊕ action-grain)* URN set for a type.

    Reads ``resolve_mission_type_context(...).governance`` directly — post-WP03
    that property already carries the FR-013 union of the type grain
    (``governance-profile.yaml``) with the FULL action grain (every action the
    mission type ships, via :func:`charter.activation.action_grain.aggregate_action_grain`),
    not a probe subset. This is the single production union (C-002); no second,
    independent ``load_action_index`` loop is performed here.
    """
    bundle = resolve_mission_type_context(repo_root, mission_type=mission_type)
    return _governance_urns(bundle.governance)


# ---------------------------------------------------------------------------
# Non-leakage (SC-001 / FR-005) — the core enduring guarantee
# ---------------------------------------------------------------------------


class TestNonLeakage:
    """No software-dev-only doctrine leaks into a non-software mission type."""

    @pytest.mark.parametrize("mission_type", NON_SOFTWARE_TYPES)
    def test_resolved_governance_is_disjoint_from_software_dev_denylist(
        self, mission_type: str, tmp_path: Path
    ) -> None:
        union = _resolve_union(mission_type, repo_root=tmp_path)
        leaked = union & SOFTWARE_DEV_ONLY_DENYLIST
        assert not leaked, (
            f"SC-001 regression: mission type {mission_type!r} resolved "
            f"software-dev-only doctrine {sorted(leaked)}. This doctrine is homed "
            "in software-dev/actions/implement/index.yaml and is meaningless for a "
            f"{mission_type} mission — it must not leak across the type boundary."
        )

    @pytest.mark.parametrize("mission_type", NON_SOFTWARE_TYPES)
    def test_governance_text_has_no_software_dev_default(
        self, mission_type: str, tmp_path: Path
    ) -> None:
        bundle = resolve_mission_type_context(tmp_path, mission_type=mission_type)
        assert "software-dev-default" not in bundle.governance_text.lower(), (
            f"FR-011 regression: {mission_type!r} governance text leaked the "
            "software-dev-default template set."
        )


# ---------------------------------------------------------------------------
# Non-vacuity twin (MANDATORY) — proves the non-leakage pass is real
# ---------------------------------------------------------------------------


class TestNonVacuityTwin:
    """The SAME denylist IS resolved by software-dev — so non-leakage is real."""

    def test_probe_action_implement_is_shared_and_load_bearing(self) -> None:
        """``implement`` (the denylist home) is applied to every type uniformly.

        The non-leakage pass probes each non-software type with the SAME
        ``implement`` action that surfaces the denylist for software-dev. The
        non-software types simply lack that action index, so it resolves empty —
        which is the exact disjointness under test, not a skipped comparison.
        """
        assert "implement" in _SHARED_PROBE_ACTIONS
        for mission_type in NON_SOFTWARE_TYPES:
            index = load_action_index(MISSIONS_ROOT, mission_type, "implement")
            assert not (_action_urns(index) & SOFTWARE_DEV_ONLY_DENYLIST)

    def test_non_vacuity_twin_software_dev_resolves_denylist(self, tmp_path: Path) -> None:
        """software-dev DOES resolve the whole denylist through the shared probe.

        This is the twin that keeps :class:`TestNonLeakage` honest: it runs the
        identical resolution machinery (``_resolve_union``) against
        ``software-dev``. If a regression made resolution return nothing (making
        non-leakage pass vacuously), this assertion fails loud because the
        denylist would no longer be a subset.
        """
        union = _resolve_union("software-dev", repo_root=tmp_path)
        missing = SOFTWARE_DEV_ONLY_DENYLIST - union
        assert not missing, (
            "Non-vacuity twin broke: software-dev no longer resolves the "
            f"software-dev-only denylist entries {sorted(missing)} via the shared "
            "'implement' action. Either the denylist drifted from "
            "software-dev/actions/implement/index.yaml or the resolution seam "
            "stopped surfacing action-grain doctrine — the non-leakage guarantee "
            "is now unverifiable and this test refuses to pass silently."
        )


# ---------------------------------------------------------------------------
# Determinism (NFR-007) — identical inputs render byte-identical
# ---------------------------------------------------------------------------


class TestDeterminism:
    @pytest.mark.parametrize("mission_type", ("software-dev", *NON_SOFTWARE_TYPES))
    def test_two_resolutions_are_byte_identical(
        self, mission_type: str, tmp_path: Path
    ) -> None:
        first = resolve_mission_type_context(tmp_path, mission_type=mission_type)
        second = resolve_mission_type_context(tmp_path, mission_type=mission_type)
        assert first == second
        assert first.governance_text == second.governance_text
        assert first.governance == second.governance

    @pytest.mark.parametrize("mission_type", NON_SOFTWARE_TYPES)
    def test_resolved_union_is_stable_across_resolutions(
        self, mission_type: str, tmp_path: Path
    ) -> None:
        first = _resolve_union(mission_type, repo_root=tmp_path)
        second = _resolve_union(mission_type, repo_root=tmp_path)
        assert first == second


# ---------------------------------------------------------------------------
# Hard-fail / degrade (FR-003 / FR-003a / FR-004)
# ---------------------------------------------------------------------------


class TestHardFailAndDegrade:
    def test_unknown_typed_mission_raises(self, tmp_path: Path) -> None:
        with pytest.raises(UnknownMissionTypeError):
            resolve_mission_type_context(tmp_path, mission_type="totally-made-up-type")

    def test_known_type_with_empty_type_grain_resolves_without_error(
        self, tmp_path: Path
    ) -> None:
        """software-dev ships an empty TYPE-grain — accessing governance never errors (FR-004).

        Post-WP03, ``bundle.governance`` is the type-grain UNION action-grain, so
        the resolved URN set is no longer empty — software-dev's action grain
        (every ``actions/*/index.yaml`` under the type) is substantial. Only the
        TYPE grain (``governance-profile.yaml``) is empty for software-dev. The
        FR-004 guarantee under test is "no error on an empty grain", not "empty
        result" — accessing ``.governance`` must resolve without raising even
        though the type-grain alone contributes nothing.
        """
        bundle = resolve_mission_type_context(tmp_path, mission_type="software-dev")
        assert bundle.mission_type == "software-dev"
        assert bundle.governance is not None

    def test_typeless_caller_degrades_neutrally_never_software_dev(
        self, tmp_path: Path
    ) -> None:
        bundle = resolve_mission_type_context(tmp_path)
        assert bundle.mission_type is None
        assert bundle.governance is None
        assert bundle.governance_text == ""
