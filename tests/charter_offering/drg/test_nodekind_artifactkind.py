"""Regression coverage for the DRG node-kind artifact-kind contract."""

from __future__ import annotations

import pytest

from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.models import DRGNode, NodeKind


pytestmark = [pytest.mark.fast]


def test_node_kind_remains_superset_of_artifact_kind() -> None:
    artifact_values = {kind.value for kind in ArtifactKind}
    node_values = {kind.value for kind in NodeKind}

    assert artifact_values <= node_values


def test_mission_step_contract_is_valid_drg_node_kind() -> None:
    node = DRGNode(
        urn="mission_step_contract:implement-step",
        kind=NodeKind.MISSION_STEP_CONTRACT,
    )

    assert node.kind is NodeKind.MISSION_STEP_CONTRACT


def test_asset_is_valid_drg_node_kind() -> None:
    """T002: NodeKind.ASSET exists and accepts a bare `asset:<id>` URN."""
    node = DRGNode(
        urn="asset:example-asset",
        kind=NodeKind.ASSET,
    )

    assert node.kind is NodeKind.ASSET


def test_template_urn_stays_bare() -> None:
    """Companion pin: `template:<id>` URNs stay bare (no `<pack>/` qualifier)."""
    node = DRGNode(
        urn="template:example-template",
        kind=NodeKind.TEMPLATE,
    )

    assert node.kind is NodeKind.TEMPLATE


def test_anti_pattern_is_valid_drg_node_kind() -> None:
    """WP01 (T003): NodeKind.ANTI_PATTERN exists and accepts an
    `anti_pattern:<id>` URN, and the corresponding ArtifactKind member exists
    with the same string value (D2)."""
    node = DRGNode(
        urn="anti_pattern:example-anti-pattern",
        kind=NodeKind.ANTI_PATTERN,
    )

    assert node.kind is NodeKind.ANTI_PATTERN
    assert ArtifactKind.ANTI_PATTERN.value == NodeKind.ANTI_PATTERN.value
