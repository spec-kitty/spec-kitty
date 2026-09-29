"""Unit tests for ``assert_topology_matches_manifest`` (#5100 IC-02, WP03 T012 / WP04 T020b).

The pure writer-chokepoint guard: refuses a ``SINGLE_BRANCH`` mission whose
lane manifest has a code lane (Invariant T-1, ``data-model.md``). WP04
promoted it off module-private status (``_assert_topology_matches_manifest``)
once the review path (``agent/workflow.py``) became its first real ``src/``
caller (mirrors this mission's own WP02 precedent: ``lanes/claim_base.py``'s
``_claim_base_ref``/``_clear_claim_base``, privatized for the identical
symbol-level dead-code-gate reason, before later widening). Imported from the
package root (not ``mission_runtime.context`` directly) now that it is public
-- the internal submodule is import-forbidden from outside the package
(``tests/architectural/test_mission_runtime_surface.py``).

Fast, hermetic, no git / no filesystem.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.fast]

from mission_runtime import (
    MissionTopology,
    TopologyManifestMismatch,
    assert_topology_matches_manifest,
)

_SLUG = "single-branch-topology-honesty-01M3M22V"


# ---------------------------------------------------------------------------
# The violation: SINGLE_BRANCH + has_code_lanes=True
# ---------------------------------------------------------------------------


def test_raises_when_single_branch_and_has_code_lanes() -> None:
    with pytest.raises(TopologyManifestMismatch) as excinfo:
        assert_topology_matches_manifest(
            MissionTopology.SINGLE_BRANCH,
            has_code_lanes=True,
            mission_slug=_SLUG,
        )
    assert excinfo.value.error_code == "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"


def test_error_message_names_the_mission_and_both_remedies() -> None:
    with pytest.raises(TopologyManifestMismatch) as excinfo:
        assert_topology_matches_manifest(
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
        assert_topology_matches_manifest(
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
        assert_topology_matches_manifest(
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
        assert_topology_matches_manifest(
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
        assert_topology_matches_manifest(
            topology,
            has_code_lanes=False,
            mission_slug=_SLUG,
        )
        is None
    )
