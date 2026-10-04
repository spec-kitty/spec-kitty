"""Permutation sweep: no started work package ever silently changes lane (#5573 T009).

SC-002 / NFR-002 / FR-010, stdlib only. For every realistic prior manifest over
WP01-WP04 (2 or 3 lanes), every amendment (merge, merge-all, split, add, remove,
retire, kind change) and every started subset, ``compute_lanes`` either keeps
each started work package on its recorded lane or raises
``LaneMembershipFrozenError``.

The expected outcome is computed **independently** with a tiny union-find over
the amended ownership, so "always refuse" cannot satisfy the sweep:
``raised == expected`` for every case.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import pytest

from specify_cli.lanes.compute import LaneMembershipFrozenError, compute_lanes
from specify_cli.lanes.frozen_membership import FrozenLaneMembership, build_frozen_membership
from specify_cli.lanes.models import LanesManifest
from specify_cli.ownership.models import OwnershipManifest, WorkProductKind

pytestmark = pytest.mark.fast

_SLUG = "frozen-sweep"
_UNIVERSE = ("WP01", "WP02", "WP03", "WP04")


# ---------------------------------------------------------------------------
# Universe and amendments
# ---------------------------------------------------------------------------


@dataclass
class _Plan:
    """A mission's lane inputs: WP -> owned files, plus kind and retirement facts."""

    owned: dict[str, set[str]]
    planning: set[str] = field(default_factory=set)
    retired: set[str] = field(default_factory=set)

    def copy(self) -> _Plan:
        return _Plan({wp: set(files) for wp, files in self.owned.items()}, set(self.planning), set(self.retired))


def _partitions(items: tuple[str, ...]) -> Iterable[list[list[str]]]:
    """Yield every set partition of *items* (blocks keep item order)."""
    if not items:
        yield []
        return
    head, rest = items[0], items[1:]
    for partial in _partitions(rest):
        yield [[head], *partial]
        for index in range(len(partial)):
            yield [*partial[:index], [head, *partial[index]], *partial[index + 1 :]]


def _prior_blocks() -> list[list[list[str]]]:
    blocks = [sorted(sorted(block) for block in part) for part in _partitions(_UNIVERSE)]
    return [part for part in blocks if len(part) in (2, 3)]


def _plan_for(blocks: list[list[str]]) -> _Plan:
    """Each WP owns its own file; lane-mates also share their block's file."""
    owned: dict[str, set[str]] = {}
    for index, block in enumerate(blocks):
        for wp in block:
            owned[wp] = {f"{wp.lower()}.py"}
            if len(block) > 1:
                owned[wp].add(f"block{index}.py")
    return _Plan(owned)


def _merge_first_two(plan: _Plan, blocks: list[list[str]]) -> _Plan:
    amended = plan.copy()
    amended.owned[blocks[0][0]].add(f"{blocks[1][0].lower()}.py")
    return amended


def _merge_all(plan: _Plan, blocks: list[list[str]]) -> _Plan:
    amended = plan.copy()
    for block in blocks[1:]:
        amended.owned[blocks[0][0]].add(f"{block[0].lower()}.py")
    return amended


def _split(plan: _Plan, blocks: list[list[str]]) -> _Plan:
    """Remove the shared file of the first multi-member lane (its members separate)."""
    amended = plan.copy()
    for index, block in enumerate(blocks):
        if len(block) > 1:
            for wp in block:
                amended.owned[wp].discard(f"block{index}.py")
            break
    return amended


def _add_wp05(plan: _Plan, _blocks: list[list[str]]) -> _Plan:
    amended = plan.copy()
    amended.owned["WP05"] = {"wp05.py"}
    return amended


def _remove_last(plan: _Plan, _blocks: list[list[str]]) -> _Plan:
    amended = plan.copy()
    amended.owned.pop("WP04")
    return amended


def _retire_last(plan: _Plan, _blocks: list[list[str]]) -> _Plan:
    """WP04 is canceled: excluded from lane inputs by the cancellation projection."""
    amended = plan.copy()
    amended.owned.pop("WP04")
    amended.retired.add("WP04")
    return amended


def _kind_change(plan: _Plan, _blocks: list[list[str]]) -> _Plan:
    amended = plan.copy()
    amended.planning.add("WP01")
    amended.owned["WP01"] = {"kitty-specs/notes.md"}
    return amended


_AMENDMENTS: dict[str, Callable[[_Plan, list[list[str]]], _Plan]] = {
    "merge-two": _merge_first_two,
    "merge-all": _merge_all,
    "split": _split,
    "add": _add_wp05,
    "remove": _remove_last,
    "retire": _retire_last,
    "kind-change": _kind_change,
}


def _inputs(plan: _Plan, *, reverse: bool = False) -> tuple[dict[str, list[str]], dict[str, OwnershipManifest]]:
    wps = sorted(plan.owned, reverse=reverse)
    graph: dict[str, list[str]] = {wp: [] for wp in wps}
    manifests = {
        wp: OwnershipManifest(
            execution_mode=WorkProductKind.PLANNING_ARTIFACT if wp in plan.planning else WorkProductKind.CODE_CHANGE,
            owned_files=tuple(sorted(plan.owned[wp], reverse=reverse)),
            authoritative_surface=sorted(plan.owned[wp])[0],
        )
        for wp in wps
    }
    return graph, manifests


def _compute(plan: _Plan, prior: LanesManifest | None, frozen: FrozenLaneMembership | None, *, reverse: bool = False) -> LanesManifest:
    graph, manifests = _inputs(plan, reverse=reverse)
    return compute_lanes(graph, manifests, _SLUG, previous_lanes=prior, frozen=frozen)


# ---------------------------------------------------------------------------
# Independent oracle
# ---------------------------------------------------------------------------


def _oracle_groups(plan: _Plan, bindings: dict[str, str]) -> list[set[str]]:
    """Union code WPs sharing a file, then code WPs bound to the same lane."""
    code = sorted(wp for wp in plan.owned if wp not in plan.planning)
    parent = {wp: wp for wp in code}

    def find(wp: str) -> str:
        while parent[wp] != wp:
            wp = parent[wp]
        return wp

    def join(a: str, b: str) -> None:
        parent[find(a)] = find(b)

    for a, b in itertools.combinations(code, 2):
        if plan.owned[a] & plan.owned[b]:
            join(a, b)
    for a, b in itertools.combinations(code, 2):
        if a in bindings and bindings.get(a) == bindings.get(b):
            join(a, b)
    groups: dict[str, set[str]] = {}
    for wp in code:
        groups.setdefault(find(wp), set()).add(wp)
    return list(groups.values())


def _expected_refusal(plan: _Plan, bindings: dict[str, str]) -> bool:
    for wp, lane_id in bindings.items():
        if wp not in plan.owned and wp not in plan.retired:
            return True  # started WP removed
        if wp in plan.owned and (wp in plan.planning) != (lane_id == "lane-planning"):
            return True  # started WP changed kind
    return any(len({bindings[wp] for wp in group if wp in bindings}) > 1 for group in _oracle_groups(plan, bindings))


def _comparable(manifest: LanesManifest) -> dict[str, object]:
    data = manifest.to_dict()
    data.pop("computed_at", None)
    return data


# ---------------------------------------------------------------------------
# The sweep
# ---------------------------------------------------------------------------

_CASES = [
    pytest.param(blocks, name, id=f"{'|'.join('+'.join(b) for b in blocks)}-{name}")
    for blocks, name in itertools.product(_prior_blocks(), _AMENDMENTS)
]


@pytest.mark.parametrize(("blocks", "amendment"), _CASES)
def test_started_work_packages_keep_their_lane_or_refinalize_refuses(blocks: list[list[str]], amendment: str) -> None:
    base = _plan_for(blocks)
    prior = _compute(base, None, None)
    prior_lane = {wp: lane.lane_id for lane in prior.lanes for wp in lane.wp_ids}
    assert sorted(sorted(lane.wp_ids) for lane in prior.lanes) == blocks  # realistic prior
    amended = _AMENDMENTS[amendment](base, blocks)
    present = frozenset(amended.owned) | frozenset(amended.retired)
    eligible = frozenset(amended.owned)

    refusals = 0
    for size in range(len(_UNIVERSE) + 1):
        for started in itertools.combinations(_UNIVERSE, size):
            frozen = build_frozen_membership(
                prior,
                started=frozenset(started),
                tipped_branches=frozenset(),
                present_wp_ids=present,
                eligible_wp_ids=eligible,
            )
            bindings = dict(frozen.bindings)
            assert bindings == {wp: prior_lane[wp] for wp in started}
            expected = _expected_refusal(amended, bindings)
            try:
                result = _compute(amended, prior, frozen)
            except LaneMembershipFrozenError:
                raised = True
            else:
                raised = False
            assert raised == expected, f"started={started} bindings={bindings}"
            if raised:
                refusals += 1
                continue

            lane_of = {wp: lane.lane_id for lane in result.lanes for wp in lane.wp_ids}
            for wp, lane_id in bindings.items():
                if wp in amended.owned:
                    assert lane_of[wp] == lane_id, f"started {wp} moved: started={started}"
            prior_ids = {lane.lane_id for lane in prior.lanes}
            minted = {lane.lane_id for lane in result.lanes} - prior_ids
            assert not (minted & frozen.reserved_lane_ids), f"re-minted a reserved id: started={started}"
            # Determinism (NFR-002): shuffled dict insertion order, same manifest.
            assert _comparable(_compute(amended, prior, frozen, reverse=True)) == _comparable(result)
            if not started:
                # Same-fixture positive control: no started WPs == today's algorithm.
                assert _comparable(_compute(amended, prior, None)) == _comparable(result)
    # Non-vacuity: the empty started set never refuses, so every case has a
    # passing run; refusals are expected for some amendments, not all.
    assert refusals < 2 ** len(_UNIVERSE)


def test_sweep_exercises_both_outcomes() -> None:
    """Guard against an oracle that silently degenerates to one answer."""
    outcomes: set[bool] = set()
    for blocks, amendment in itertools.product(_prior_blocks(), _AMENDMENTS):
        base = _plan_for(blocks)
        prior = _compute(base, None, None)
        prior_lane = {wp: lane.lane_id for lane in prior.lanes for wp in lane.wp_ids}
        amended = _AMENDMENTS[amendment](base, blocks)
        outcomes.add(_expected_refusal(amended, dict(prior_lane)))
        outcomes.add(_expected_refusal(amended, {}))
    assert outcomes == {True, False}
    assert len(_CASES) <= 500
