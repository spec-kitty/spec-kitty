"""CI-cost tool guards (#6173, WP04, mission derived-consumer-census-01M4V5P5).

``scripts/ci/consumer_census_cost.py`` measures the per-PR selected-shard count
under the live hand fan-out vs the census-derived one (FR-009). These pin the pure
library: a diff selects its module's shard cost, the derived fan-out is dearer than the hand
one on a built-in pin bump (the recorded trade-off), and a non-consumed pack file costs zero
under both.
"""

from __future__ import annotations

import pytest

from scripts.ci import consumer_census_cost as cost
from scripts.ci.gate_selection import GROUP_MODULE_FANOUT, PACK_PIN_GLOB, load_router

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def router():
    return load_router()


def test_a_src_group_diff_costs_its_module_shards(router) -> None:
    counts = cost.shard_counts()
    c = cost.shard_count_for(["src/specify_cli/consolidation/executor.py"], GROUP_MODULE_FANOUT, router=router, counts=counts)
    assert c == counts["consolidation"]


def test_pin_bump_shows_a_positive_derivation_delta(router) -> None:
    """A built-in pin bump (the only in-repo pack content change since #6451) is
    strictly more expensive under the derived fan-out (the census finds more real
    consumers) — a non-vacuous cost signal."""
    rows = cost.compare_fanouts([[PACK_PIN_GLOB]], router=router)
    assert rows[0]["hand_shards"] > 0 and rows[0]["delta"] > 0


def test_non_consumed_pack_file_costs_zero_under_both(router) -> None:
    rows = cost.compare_fanouts([["packs/built-in/missions/README.md"]], router=router)
    assert rows[0]["hand_shards"] == 0 and rows[0]["derived_shards"] == 0
