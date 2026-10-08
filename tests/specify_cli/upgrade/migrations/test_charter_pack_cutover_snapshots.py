"""Frozen released ``default`` / ``minimal`` snapshots of the charter-pack cutover (#3732, T061).

The expected counts and sizes come from the research table
(``research/default-yaml-snapshots.md``), not from the module itself.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from specify_cli.upgrade.migrations._charter_pack_cutover_snapshots import (
    DEFAULT_KIND_GATE,
    DEFAULT_SNAPSHOTS,
    DIRECTIVE_ID_TO_STEM,
    MINIMAL_KIND_GATE,
    MINIMAL_SNAPSHOTS,
    normalise_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: Research table: per key, the sizes of every distinct released list (original and post-rewrite).
EXPECTED_SIZES = {
    "activated_directives": [19],
    "activated_paradigms": [8],
    "activated_procedures": [13],
    "activated_mission_step_contracts": [17],
    "activated_agent_profiles": [15, 16, 18],
    "activated_styleguides": [8, 9],
    "activated_toolguides": [9, 10, 12],
    "activated_tactics": [94, 95, 97],
}


def test_default_snapshot_keys_are_the_eight_per_artifact_keys() -> None:
    assert set(DEFAULT_SNAPSHOTS) == set(EXPECTED_SIZES)
    assert "mission_type_activations" not in DEFAULT_SNAPSHOTS


@pytest.mark.parametrize("key", sorted(EXPECTED_SIZES))
def test_distinct_counts_and_sizes_per_key(key: str) -> None:
    snapshots = DEFAULT_SNAPSHOTS[key]
    assert len(set(snapshots)) == len(snapshots) == len(EXPECTED_SIZES[key])
    assert sorted(len(s) for s in snapshots) == EXPECTED_SIZES[key]


def test_unshipped_94_tactics_list_is_the_95_list_minus_supply_chain_install_safety() -> None:
    by_size = {len(s): s for s in DEFAULT_SNAPSHOTS["activated_tactics"]}
    assert by_size[94] == by_size[95] - {"supply-chain-install-safety"}
    assert "supply-chain-install-safety" in by_size[95]


def test_rtk_rewrite_of_the_10_toolguides_list_is_the_9_list() -> None:
    by_size = {len(s): s for s in DEFAULT_SNAPSHOTS["activated_toolguides"]}
    assert by_size[9] == by_size[10] - {"rtk-search-tooling"}


def test_kind_gates() -> None:
    assert {
        "directives",
        "tactics",
        "styleguides",
        "toolguides",
        "paradigms",
        "procedures",
        "agent_profiles",
        "mission_step_contracts",
    } == DEFAULT_KIND_GATE
    assert {"directives", "tactics"} == MINIMAL_KIND_GATE


def test_minimal_snapshots() -> None:
    assert set(MINIMAL_SNAPSHOTS) == {"activated_directives", "activated_tactics"}
    assert [len(s) for s in MINIMAL_SNAPSHOTS["activated_directives"]] == [5]
    assert sorted(MINIMAL_SNAPSHOTS["activated_tactics"], key=len) == [
        frozenset({"acceptance-test-first"}),
        frozenset({"acceptance-test-first", "boring-code-review"}),
    ]


@pytest.mark.parametrize("key", sorted(MINIMAL_SNAPSHOTS))
def test_no_minimal_list_equals_a_default_list(key: str) -> None:
    assert not set(MINIMAL_SNAPSHOTS[key]) & set(DEFAULT_SNAPSHOTS[key])


def test_directive_table_covers_every_snapshot_directive() -> None:
    stems = {stem for snapshot in DEFAULT_SNAPSHOTS["activated_directives"] for stem in snapshot}
    stems |= {stem for snapshot in MINIMAL_SNAPSHOTS["activated_directives"] for stem in snapshot}
    assert set(DIRECTIVE_ID_TO_STEM.values()) == stems
    assert len(DIRECTIVE_ID_TO_STEM) == 19
    assert all(stem.startswith(directive_id.removeprefix("DIRECTIVE_") + "-") for directive_id, stem in DIRECTIVE_ID_TO_STEM.items())


@pytest.mark.parametrize(
    ("kind_key", "raw", "expected"),
    [
        ("activated_directives", "DIRECTIVE_001", "001-architectural-integrity-standard"),
        ("activated_directives", "001-architectural-integrity-standard", "001-architectural-integrity-standard"),
        ("activated_directives", "USE_C4_MODEL_TECHNIQUES", "use-c4-model-techniques"),
        ("activated_directives", "DIRECTIVE_999", "DIRECTIVE_999"),
        ("activated_directives", "my-custom-directive", "my-custom-directive"),
        ("activated_tactics", "DIRECTIVE_001", "DIRECTIVE_001"),
        ("activated_tactics", "UPPER_CASE", "UPPER_CASE"),
    ],
)
def test_normalise_id(kind_key: str, raw: str, expected: str) -> None:
    assert normalise_id(kind_key, raw) == expected


def test_normalise_id_round_trips_every_table_entry() -> None:
    for directive_id, stem in DIRECTIVE_ID_TO_STEM.items():
        assert normalise_id("activated_directives", directive_id) == stem
        assert normalise_id("activated_directives", stem) == stem


def test_snapshots_are_immutable() -> None:
    with pytest.raises(TypeError):
        cast(Any, DEFAULT_SNAPSHOTS)["activated_tactics"] = ()
