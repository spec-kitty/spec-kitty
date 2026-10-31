"""``IdentityIndex.urn`` — the one forward map from an activation token to a DRG URN (#6741).

Before this seam existed, three activation surfaces each re-derived
``"<kind>:<declared id>"`` locally, and the DRG mints a *mission step contract* node from the
contract's ``mission``/``action`` pair instead (``mission_step_contract:documentation/accept`` for the
declared id ``documentation-accept``). Every activation token for that kind therefore resolved to a
URN no node carries. These tests pin the one authority that now answers the question for every kind.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.activation.identity_index import IdentityIndex
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.missions.step_contracts import step_contract_urn

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: A real built-in step contract: declared id ``documentation-accept``, shipped URN
#: ``mission_step_contract:documentation/accept``.
_STEP_CONTRACT_TOKEN = "documentation-accept"
_STEP_CONTRACT_URN = "mission_step_contract:documentation/accept"

#: A real directive whose declared id differs from its config stem (the ordinary-kind control).
_DIRECTIVE_STEM = "001-architectural-integrity-standard"
_DIRECTIVE_ID = "DIRECTIVE_001"


@pytest.fixture(scope="module")
def identity() -> IdentityIndex:
    return IdentityIndex.build(_REPO_ROOT)


def test_a_step_contract_urn_tail_is_the_owning_mission_and_action() -> None:
    assert step_contract_urn("documentation", "accept") == _STEP_CONTRACT_URN


def test_a_step_contract_stem_resolves_to_the_shipped_node_urn(identity: IdentityIndex) -> None:
    """RED before #6741: this returned ``mission_step_contract:documentation-accept`` (no such node)."""
    assert identity.urn(ArtifactKind.MISSION_STEP_CONTRACT, _STEP_CONTRACT_TOKEN) == _STEP_CONTRACT_URN


def test_a_step_contract_declared_id_resolves_like_its_stem(identity: IdentityIndex) -> None:
    declared = identity.declared_id(ArtifactKind.MISSION_STEP_CONTRACT, _STEP_CONTRACT_TOKEN)

    assert declared == _STEP_CONTRACT_TOKEN
    assert identity.urn(ArtifactKind.MISSION_STEP_CONTRACT, declared) == _STEP_CONTRACT_URN


def test_an_ordinary_kind_urn_tail_is_the_declared_id(identity: IdentityIndex) -> None:
    """Every other kind keeps ``"<kind>:<declared id>"`` — this mission changes no other kind."""
    assert identity.urn(ArtifactKind.DIRECTIVE, _DIRECTIVE_STEM) == f"directive:{_DIRECTIVE_ID}"
    assert identity.urn(ArtifactKind.DIRECTIVE, _DIRECTIVE_ID) == f"directive:{_DIRECTIVE_ID}"


def test_a_kind_prefixed_token_resolves_like_its_bare_id(identity: IdentityIndex) -> None:
    assert identity.urn(ArtifactKind.MISSION_STEP_CONTRACT, f"mission_step_contract:{_STEP_CONTRACT_TOKEN}") == _STEP_CONTRACT_URN
    assert identity.urn(ArtifactKind.DIRECTIVE, f"directive:{_DIRECTIVE_ID}") == f"directive:{_DIRECTIVE_ID}"


def test_an_unknown_token_has_no_urn_and_never_raises(identity: IdentityIndex) -> None:
    assert identity.urn(ArtifactKind.MISSION_STEP_CONTRACT, "no-such-step-contract") is None
    assert identity.urn(ArtifactKind.DIRECTIVE, "no-such-directive") is None


def test_a_project_overlay_contract_decides_its_own_mission_and_action(tmp_path: Path) -> None:
    """The URN comes from the resolved file, not from a table: a higher layer's contract wins.

    A project overlay reusing the built-in declared id must contribute *its* ``mission``/``action``
    to the URN, exactly as the runtime resolves it (first match across layers).
    """
    overlay_dir = tmp_path / ".kittify" / "charter-packs" / "mission_step_contracts"
    overlay_dir.mkdir(parents=True)
    (overlay_dir / f"{_STEP_CONTRACT_TOKEN}.step-contract.yaml").write_text(
        "schema_version: '1.0'\n"
        f"id: {_STEP_CONTRACT_TOKEN}\n"
        "action: review\n"
        "mission: software-dev\n"
        "steps:\n"
        "  - id: bootstrap\n"
        "    description: Load charter context\n"
        '    command: "spec-kitty charter context --action review --json"\n',
        encoding="utf-8",
    )

    overlay = IdentityIndex.build(tmp_path, org_roots=[])

    assert overlay.source_layer(ArtifactKind.MISSION_STEP_CONTRACT, _STEP_CONTRACT_TOKEN) == "project"
    assert overlay.urn(ArtifactKind.MISSION_STEP_CONTRACT, _STEP_CONTRACT_TOKEN) == "mission_step_contract:software-dev/review"
