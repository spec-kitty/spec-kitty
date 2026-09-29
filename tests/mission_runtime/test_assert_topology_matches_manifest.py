"""Unit tests for ``_assert_topology_matches_manifest`` (#5100 IC-02, WP03 T012).

The pure writer-chokepoint guard: refuses a ``SINGLE_BRANCH`` mission whose
lane manifest has a code lane (Invariant T-1, ``data-model.md``). It is
module-private (``_assert_topology_matches_manifest``) for this work package
-- it has zero ``src/`` callers until a later work package of this mission
wires it into the two writer chokepoints (post-tasks fold B-2), mirroring
this mission's own WP02 precedent (``lanes/claim_base.py``'s
``_claim_base_ref``/``_clear_claim_base``, privatized for exactly the same
symbol-level dead-code-gate reason). Tests reach it via the defining
submodule directly, same precedent as ``tests/mission_runtime/test_context_fragments.py``.

Fast, hermetic, no git / no filesystem.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.fast]

from mission_runtime.context import (
    MissionTopology,
    TopologyManifestMismatch,
    _assert_topology_matches_manifest,
)

_SLUG = "single-branch-topology-honesty-01M3M22V"


# ---------------------------------------------------------------------------
# The violation: SINGLE_BRANCH + has_code_lanes=True
# ---------------------------------------------------------------------------


def test_raises_when_single_branch_and_has_code_lanes() -> None:
    with pytest.raises(TopologyManifestMismatch) as excinfo:
        _assert_topology_matches_manifest(
            MissionTopology.SINGLE_BRANCH,
            has_code_lanes=True,
            mission_slug=_SLUG,
        )
    assert excinfo.value.error_code == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"


def test_error_message_names_the_mission_and_both_remedies() -> None:
    with pytest.raises(TopologyManifestMismatch) as excinfo:
        _assert_topology_matches_manifest(
            MissionTopology.SINGLE_BRANCH,
            has_code_lanes=True,
            mission_slug=_SLUG,
        )
    message = str(excinfo.value)
    assert _SLUG in message
    assert "spec-kitty upgrade" in message
    assert "spec-kitty migrate backfill-topology --restamp-single-branch" in message


def test_to_dict_carries_the_stable_error_code() -> None:
    with pytest.raises(TopologyManifestMismatch) as excinfo:
        _assert_topology_matches_manifest(
            MissionTopology.SINGLE_BRANCH,
            has_code_lanes=True,
            mission_slug=_SLUG,
        )
    payload = excinfo.value.to_dict()
    assert payload["error_code"] == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"
    assert payload["message"] == str(excinfo.value)


# ---------------------------------------------------------------------------
# Every non-violation combination proceeds (returns None, no raise)
# ---------------------------------------------------------------------------


def test_single_branch_without_code_lanes_proceeds() -> None:
    assert (
        _assert_topology_matches_manifest(
            MissionTopology.SINGLE_BRANCH,
            has_code_lanes=False,
            mission_slug=_SLUG,
        )
        is None
    )


@pytest.mark.parametrize(
    "topology",
    [MissionTopology.LANES, MissionTopology.COORD, MissionTopology.LANES_WITH_COORD],
)
def test_non_single_branch_topology_proceeds_even_with_code_lanes(topology: MissionTopology) -> None:
    """Only SINGLE_BRANCH is the guarded cell; the other three never refuse here."""
    assert (
        _assert_topology_matches_manifest(
            topology,
            has_code_lanes=True,
            mission_slug=_SLUG,
        )
        is None
    )


@pytest.mark.parametrize(
    "topology",
    [MissionTopology.LANES, MissionTopology.COORD, MissionTopology.LANES_WITH_COORD],
)
def test_non_single_branch_topology_proceeds_without_code_lanes(topology: MissionTopology) -> None:
    assert (
        _assert_topology_matches_manifest(
            topology,
            has_code_lanes=False,
            mission_slug=_SLUG,
        )
        is None
    )
