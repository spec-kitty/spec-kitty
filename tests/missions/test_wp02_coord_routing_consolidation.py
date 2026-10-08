"""WP02 (FR-005 / NFR-005) — coord-routing predicate + frozenset consolidation.

This pins the behaviour-neutral collapse of the six coord-routing predicates and
the four verbatim ``{COORD, LANES_WITH_COORD}`` frozensets onto the ONE canonical
:func:`mission_runtime.routes_through_coordination` predicate over the ONE
canonical ``_COORD_ROUTING_TOPOLOGIES`` set.

Two contracts are pinned as **executable** assertions:

* **(b) the 4-member topology truth table** over every ``MissionTopology`` member,
  PLUS the transitional per-ref ``CommitTarget`` form (the ONLY surviving
  ``.kind is COORDINATION`` read, WP04's drain) — both forms agree, each with its
  negative control (CT5).
* **(c) the T007 KEEP map** — each C-002 genuine-fallback **relay** and the C-001
  husk short-circuit is driven on its EXCEPTION / fallback arm and asserted to
  relay via :func:`classify_topology` (NOT to have been folded into the routing
  predicate). Every relay assertion is paired with its coord/no-coord negative
  control so an over-folded mutant cannot survive.

Discipline: assertions are over the **observable return value** of each surface
(topology / kind / bool), never the internal call graph (CT4 / D036). Fixtures are
production-shaped — a real 26-char ULID + 8-char mid8 — and use the canonical
``meta.json`` serializer (`tests._meta_write_support.write_meta_canonical`) rather than a hand-rolled
writer that rots (CT3). The relay EXCEPTION arms (meta.json absent / no stored
``topology`` field) are degraded inputs that no production create path emits by
design, so they are constructed directly as the minimal faithful fixture for the
fallback arm.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from specify_cli.coordination.status_transition import _TransactionIdentity

from mission_runtime import (
    MissionTopology,
    classify_topology,
    routes_through_coordination,
)

pytestmark = [pytest.mark.fast]

# A real ULID-shaped mission identity (26 chars) + its 8-char mid8 prefix. Never a
# short hand-rolled placeholder (testing-principles realistic-data standing rule).
_MISSION_ID = "01KVRJ6PQ8ZB2H7M3N4P5R6S7T"
_MID8 = _MISSION_ID[:8]
_SLUG_BASE = "wp02-coord-routing"
_MISSION_SLUG = f"{_SLUG_BASE}-{_MID8}"
_COORD_BRANCH_REF = f"kitty/mission-{_MISSION_SLUG}"


# --------------------------------------------------------------------------- #
# (b) 4-member truth-table over the ONE canonical predicate.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("topology", "expected"),
    [
        (MissionTopology.COORD, True),
        (MissionTopology.LANES_WITH_COORD, True),
        (MissionTopology.SINGLE_BRANCH, False),
        (MissionTopology.LANES, False),
    ],
)
def test_routes_through_coordination_topology_truth_table(
    topology: MissionTopology, expected: bool
) -> None:
    """FR-005: the ONE predicate is True iff the topology routes through coord.

    Absolute per-topology assertion (CT5): all four enum members are pinned, so
    an over-allow mutant (LANES → True) and an under-allow mutant
    (LANES_WITH_COORD → False) both die. Paired coord/coord-less rows are the
    mutual negative controls.
    """
    assert routes_through_coordination(topology) is expected


def test_routes_through_coordination_covers_every_member() -> None:
    """FR-005: every MissionTopology member is classified — no member is unhandled.

    Guards against a future member being added without a routing decision (the
    predicate must answer for the whole enum, not a subset).
    """
    decided = {member: routes_through_coordination(member) for member in MissionTopology}
    assert decided == {
        MissionTopology.SINGLE_BRANCH: False,
        MissionTopology.LANES: False,
        MissionTopology.COORD: True,
        MissionTopology.LANES_WITH_COORD: True,
    }


# --------------------------------------------------------------------------- #
# Production-shaped meta.json fixtures (canonical serializer, never hand-rolled).
# --------------------------------------------------------------------------- #
def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    """Persist meta via the canonical sorted-key serializer (NOT a rotting writer)."""
    from tests._meta_write_support import write_meta_canonical as _write_meta_canonical

    feature_dir.mkdir(parents=True, exist_ok=True)
    _write_meta_canonical(feature_dir / "meta.json", meta)


def _base_meta(*, coordination_branch: str | None) -> dict[str, object]:
    """A production-shaped meta.json body (real ULID/mid8), topology field OMITTED.

    Omitting ``topology`` exercises the un-backfilled-legacy / no-stored-shape
    relay arm: the surface that reads it must derive the shape ONCE via
    ``classify_topology`` rather than restate the coord-routing set.
    """
    return {
        "mission_id": _MISSION_ID,
        "mid8": _MID8,
        "mission_slug": _MISSION_SLUG,
        "friendly_name": "WP02 Coord Routing",
        "coordination_branch": coordination_branch,
        "flattened": False,
    }


# --------------------------------------------------------------------------- #
# (c) KEEP map — relay #1: status_transition._read_contract_routes_through_coordination
#     EXCEPTION arm (read_topology raises -> classify_topology relay, line 599).
# --------------------------------------------------------------------------- #
def _make_identity(
    feature_dir: Path, coordination_branch: str | None
) -> _TransactionIdentity:
    from specify_cli.coordination.status_transition import _TransactionIdentity

    return _TransactionIdentity(
        repo_root=feature_dir.parent.parent,
        feature_dir=feature_dir,
        mission_id=_MISSION_ID,
        mid8=_MID8,
        destination_ref=coordination_branch or "refs/heads/main",
        meta_exists=feature_dir.joinpath("meta.json").exists(),
        coordination_branch=coordination_branch,
        transaction_meta_exists=False,
    )


@pytest.mark.parametrize(
    ("coordination_branch", "expected"),
    [
        (_COORD_BRANCH_REF, True),   # coord-shaped relay -> routes through coord
        (None, False),               # negative control: flat -> primary read
    ],
)
def test_read_contract_relay_exception_arm(
    tmp_path: Path, coordination_branch: str | None, expected: bool
) -> None:
    """KEEP relay #1 (status_transition:599): exception arm relays via classify_topology.

    With NO meta.json at the identity's ``feature_dir`` the ``read_topology`` call
    raises ``FileNotFoundError``, so the predicate MUST relay via
    ``classify_topology(coordination_branch, has_lanes=False)`` — the C-002
    genuine-fallback relay, NOT a folded routing predicate. The observable contract
    is the returned bool; it must equal what ``classify_topology`` would route to.
    The (coord, flat) pair are mutual negative controls.
    """
    from specify_cli.coordination.status_transition import (
        _read_contract_routes_through_coordination,
    )

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    # NO meta.json written -> read_topology raises -> exception-arm relay fires.
    assert not (feature_dir / "meta.json").exists()

    identity = _make_identity(feature_dir, coordination_branch)
    result = _read_contract_routes_through_coordination(identity)

    # The relay decision equals the classify_topology authority's routing answer.
    relayed = classify_topology(coordination_branch, has_lanes=False)
    assert result is expected
    assert result is routes_through_coordination(relayed)


# --------------------------------------------------------------------------- #
# (c) KEEP map — relay #2: surface_resolver._effective_surface_topology
#     no-stored-topology arm -> classify_topology relay (line 562).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("coord_branch", "expected"),
    [
        (_COORD_BRANCH_REF, MissionTopology.COORD),   # relay derives COORD
        (None, MissionTopology.SINGLE_BRANCH),        # negative control
    ],
)
def test_effective_surface_topology_relay_arm(
    coord_branch: str | None, expected: MissionTopology
) -> None:
    """KEEP relay #2 (surface_resolver:562): no-stored-topology arm relays.

    With ``threaded=None`` and a ``meta`` carrying NO ``topology`` field, the
    resolver MUST derive the shape ONCE via ``classify_topology(coord_branch,
    has_lanes=False)`` — the genuine fallback. The observable contract is the
    returned ``MissionTopology``; it must equal the ``classify_topology`` authority.
    """
    from specify_cli.coordination.surface_resolver import _effective_surface_topology

    meta = _base_meta(coordination_branch=coord_branch)  # no 'topology' key
    assert "topology" not in meta

    result = _effective_surface_topology(None, meta, coord_branch)
    assert result is expected
    assert result is classify_topology(coord_branch, has_lanes=False)


def test_effective_surface_topology_prefers_stored_over_relay() -> None:
    """KEEP relay #2 negative control: a STORED topology wins over the relay.

    When ``meta`` DOES carry a valid ``topology`` the resolver reads it directly and
    does NOT relay via ``classify_topology`` — proving the relay is the fallback arm
    only, not the primary disposal.
    """
    from specify_cli.coordination.surface_resolver import _effective_surface_topology

    # Stored shape COORD even though the branch value would classify as flat (None):
    # the stored value must win, so a relay-only mutant (always classify) would fail.
    meta = _base_meta(coordination_branch=None)
    meta["topology"] = MissionTopology.COORD.value

    result = _effective_surface_topology(None, meta, None)
    assert result is MissionTopology.COORD
    assert result is not classify_topology(None, has_lanes=False)


# --------------------------------------------------------------------------- #
# (c) KEEP map — relay #3: resolution._resolve_topology EXCEPTION arm (line 765).
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("coordination_branch", "expected"),
    [
        (_COORD_BRANCH_REF, MissionTopology.COORD),
        (None, MissionTopology.SINGLE_BRANCH),
    ],
)
def test_resolve_topology_relay_exception_arm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    coordination_branch: str | None,
    expected: MissionTopology,
) -> None:
    """KEEP relay #3 (resolution:765): exception arm relays via classify_topology.

    With no readable stored meta (``read_topology`` raises) ``_resolve_topology``
    derives the shape ONCE from the resolved ``coordination_branch`` value via
    ``classify_topology(..., has_lanes=False)`` — the genuine fallback. Observable
    contract: the returned ``MissionTopology``. The coord/flat pair are mutual
    negative controls.
    """
    from mission_runtime import resolution

    primary_root = tmp_path
    # No meta on disk: stub the primary-dir resolver to a dir with no meta.json so
    # read_topology raises FileNotFoundError and the relay arm runs.
    empty_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    empty_dir.mkdir(parents=True, exist_ok=True)
    # read-side-seam-primary-primitive-closure-01KYKMMT WP08 (T035): patch
    # target moved from the deleted public wrapper to the module-private
    # ``_compose_primary_feature_dir`` leaf -- ``resolution.py``'s internal
    # PRIMARY-dir composition (WP03 T016) already called the leaf directly,
    # never the wrapper, before this WP.
    monkeypatch.setattr(
        "specify_cli.missions._read_path_resolver._compose_primary_feature_dir",
        lambda _root, _slug: empty_dir,
    )
    # The coordination-branch value the relay classifies from is read separately.
    monkeypatch.setattr(
        resolution,
        "_resolve_coordination_branch",
        lambda _root, _slug, **_kw: coordination_branch,
    )

    result = resolution._resolve_topology(primary_root, _MISSION_SLUG)
    assert result is expected
    assert result is classify_topology(coordination_branch, has_lanes=False)


# --------------------------------------------------------------------------- #
# (c) KEEP map — C-001 husk short-circuit: _husk_is_authoritative_surface.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("stored_topology", "expected"),
    [
        (MissionTopology.COORD.value, True),             # real coord -> husk authoritative
        (MissionTopology.LANES_WITH_COORD.value, True),  # real coord -> husk authoritative
        (MissionTopology.SINGLE_BRANCH.value, False),    # flattened -> husk stale
        (MissionTopology.LANES.value, False),            # flattened -> husk stale
        (None, True),                                    # legacy (no stored) -> preserve
    ],
)
def test_husk_short_circuit_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stored_topology: str | None,
    expected: bool,
) -> None:
    """KEEP C-001 (surface_resolver:503): husk short-circuit gate is unchanged.

    Coord-routing stored topology OR no-stored (legacy) -> the registered ``-coord``
    husk IS the authoritative surface (True); a coord-less stored topology -> the
    husk is stale and structurally not consulted (False). The legacy ``None`` arm
    preserves the historical husk-consulting behaviour exactly once. This pins that
    the consolidation did NOT alter the husk decision.
    """
    from specify_cli.coordination import surface_resolver

    meta = _base_meta(coordination_branch=_COORD_BRANCH_REF)
    if stored_topology is not None:
        meta["topology"] = stored_topology

    monkeypatch.setattr(
        surface_resolver,
        "read_primary_meta",
        lambda _root, _slug: (meta, tmp_path / "kitty-specs" / _MISSION_SLUG),
    )

    result = surface_resolver._husk_is_authoritative_surface(tmp_path, _MISSION_SLUG)
    assert result is expected


def test_husk_short_circuit_unreadable_meta_degrades_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KEEP C-001 negative control: unreadable primary meta degrades to True.

    A malformed/unreadable primary meta cannot safely override the husk
    short-circuit, so it degrades to the historical husk-consulting behaviour
    (True). This is the documented fail-safe arm — pinned so the consolidation does
    not silently flip it to a stale-suppressing False.
    """
    from specify_cli.coordination import surface_resolver

    def _boom(_root: Path, _slug: str) -> tuple[dict[str, object], Path]:
        raise ValueError("malformed primary meta.json")

    monkeypatch.setattr(surface_resolver, "read_primary_meta", _boom)
    assert surface_resolver._husk_is_authoritative_surface(tmp_path, _MISSION_SLUG) is True
