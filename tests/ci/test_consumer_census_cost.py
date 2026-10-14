"""CI-cost tool guards (#6173, WP04, mission derived-consumer-census-01M4V5P5).

``scripts/ci/consumer_census_cost.py`` measures the per-PR selected-shard count
under the live hand fan-out vs the census-derived one (FR-009). These pin the pure
library: shard counts come from the registry's measured values, a diff selects a
positive cost, and the derived fan-out is >= the hand fan-out on a pack-content
edit (full derivation widens, never narrows, those edits — the recorded trade-off)
while a non-consumed pack file costs zero under both.
"""

from __future__ import annotations

import pytest

from scripts.ci import consumer_census_cost as cost
from scripts.ci.gate_selection import GROUP_MODULE_FANOUT, load_router

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def router():
    return load_router()


def test_shard_counts_are_positive_registry_values() -> None:
    counts = cost.shard_counts()
    assert counts["charter"] == 7, "charter's measured shard_count drifted (the 7-shard long pole)"
    assert all(v >= 1 for v in counts.values())


def test_a_src_group_diff_costs_its_module_shards(router) -> None:
    counts = cost.shard_counts()
    c = cost.shard_count_for(["src/specify_cli/consolidation/executor.py"], GROUP_MODULE_FANOUT, router=router, counts=counts)
    assert c == counts["consolidation"]


def test_derived_fanout_never_cheaper_than_hand_on_pack_edits(router) -> None:
    """Full derivation WIDENS pack-content routing (the recorded trade-off): for
    every representative pack-edit type the derived shard count is >= the hand one."""
    rows = cost.compare_fanouts([paths for _label, paths in cost.REPRESENTATIVE_EDITS], router=router)
    for (label, _paths), row in zip(cost.REPRESENTATIVE_EDITS, rows, strict=True):
        assert row["delta"] >= 0, f"{label}: derived fan-out is cheaper than hand ({row})"


def test_prompt_edit_shows_a_positive_derivation_delta(router) -> None:
    """The mission-step prompt edit is strictly more expensive under the derived
    fan-out (the census finds more real consumers) — a non-vacuous cost signal."""
    rows = cost.compare_fanouts([["packs/built-in/missions/mission-steps/software-dev/research/prompt.md"]], router=router)
    assert rows[0]["hand_shards"] > 0 and rows[0]["delta"] > 0


def test_non_consumed_pack_file_costs_zero_under_both(router) -> None:
    rows = cost.compare_fanouts([["packs/built-in/missions/README.md"]], router=router)
    assert rows[0]["hand_shards"] == 0 and rows[0]["derived_shards"] == 0
