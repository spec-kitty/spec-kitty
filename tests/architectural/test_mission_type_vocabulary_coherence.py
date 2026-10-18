"""Vocabulary coherence of built-in mission types (#6388).

A built-in mission type names its steps in two places that must agree: the
``required_by_step`` keys of its ``expected-artifacts.yaml`` manifest, and the
action ids of its runtime step contracts (the vocabulary the guard tables and
``gather_artifact_presence`` dispatch on). When the manifest is keyed on a
different vocabulary the presence gatherer silently reads a committed artifact
as absent -- the plan mission's ``goals``/``draft`` keys against the
``specify``/``plan`` action ids blocked every plan mission.

Both sides are read from their canonical loaders, never from hardcoded lists.
"""

from __future__ import annotations

import pytest

from charter.activation.manifest_loader import load_manifest
from charter.offering.missions.step_contracts import MissionStepContractRepository

pytestmark = [pytest.mark.architectural]

BUILT_IN_MISSION_TYPES = ("software-dev", "research", "documentation", "plan")

#: Manifest keys that are NOT runtime action ids, per built-in type. This is a
#: shrink-only ledger of pre-existing, non-plan vocabulary (CLI-guard step ids
#: and a terminal marker) that the non-plan families' byte-compat
#: characterization pins (NFR-001). Never add an entry for a new divergence:
#: reconcile the manifest to the action ids instead. ``plan`` must stay empty.
_KNOWN_NON_ACTION_KEYS: dict[str, frozenset[str]] = {
    "software-dev": frozenset({"discovery", "tasks_outline", "tasks_packages", "tasks_finalize", "done"}),
    "research": frozenset({"done"}),
    "documentation": frozenset(),
    "plan": frozenset(),
}


def _action_ids(mission_type: str) -> set[str]:
    return {contract.action for contract in MissionStepContractRepository().get_by_mission(mission_type)}


@pytest.mark.parametrize("mission_type", BUILT_IN_MISSION_TYPES)
def test_built_in_type_has_step_contracts(mission_type: str) -> None:
    assert _action_ids(mission_type), f"{mission_type} declares no runtime step contracts"


@pytest.mark.parametrize("mission_type", BUILT_IN_MISSION_TYPES)
def test_manifest_step_keys_are_runtime_action_ids(mission_type: str) -> None:
    manifest = load_manifest(mission_type)
    assert manifest is not None, f"{mission_type} has no expected-artifacts manifest"

    divergent = set(manifest.required_by_step) - _action_ids(mission_type) - _KNOWN_NON_ACTION_KEYS[mission_type]

    assert not divergent, (
        f"{mission_type}: expected-artifacts.yaml required_by_step keys {sorted(divergent)} are not runtime "
        f"step-contract action ids {sorted(_action_ids(mission_type))}; the presence gatherer would read the "
        "artifacts they gate as absent. Re-key the manifest to the action ids (#6388)."
    )


@pytest.mark.parametrize("mission_type", BUILT_IN_MISSION_TYPES)
def test_known_non_action_ledger_has_no_stale_entries(mission_type: str) -> None:
    """The ledger may only shrink: every entry must still be a live manifest key."""
    manifest = load_manifest(mission_type)
    assert manifest is not None

    stale = _KNOWN_NON_ACTION_KEYS[mission_type] - set(manifest.required_by_step)

    assert not stale, f"{mission_type}: ledger entries {sorted(stale)} are no longer manifest keys; remove them"
