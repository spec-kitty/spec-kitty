"""Unit tests for the additive ``selected_<kind>`` parity fields on
:class:`charter.activation.schemas.DoctrineSelectionConfig` and their byte-stable
emission via :func:`charter.activation.schemas.emit_yaml` (WP01 of mission
``charter-mediated-doctrine-selection-01KRTZCA``).

Coverage:
  * Defaulting: a freshly-constructed ``DoctrineSelectionConfig`` exposes
    all five new fields as empty lists.
  * Byte-stability (NFR-005): emitted YAML omits the empty new fields
    because they live in :data:`charter.activation.schemas._OPTIONAL_EMPTY_OMIT_KEYS`.
  * Round-trip: populating a new field survives ``emit_yaml`` →
    ``YAML().load(...)``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.schemas import (
    DoctrineSelectionConfig,
    GovernanceConfig,
    _OPTIONAL_EMPTY_OMIT_KEYS,
    _prune_optional_empties,
    emit_yaml,
)


pytestmark = [pytest.mark.unit]


_NEW_SELECTED_KEYS = (
    "selected_styleguides",
    "selected_toolguides",
    "selected_procedures",
    "selected_agent_profiles",
    "selected_mission_step_contracts",
)


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


def test_default_construction_exposes_all_new_selected_fields() -> None:
    cfg = DoctrineSelectionConfig()
    for key in _NEW_SELECTED_KEYS:
        assert hasattr(cfg, key), f"DoctrineSelectionConfig missing field {key}"
        assert getattr(cfg, key) == [], (
            f"Field {key} should default to empty list, got {getattr(cfg, key)!r}"
        )


def test_new_selected_keys_are_in_optional_omit_set() -> None:
    """All five new selected_<kind> field names must appear in
    ``_OPTIONAL_EMPTY_OMIT_KEYS`` so empty values stay out of emitted YAML.
    """
    missing = sorted(set(_NEW_SELECTED_KEYS) - _OPTIONAL_EMPTY_OMIT_KEYS)
    assert not missing, (
        "The following selected_<kind> fields are not in "
        f"_OPTIONAL_EMPTY_OMIT_KEYS: {missing}"
    )


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------


def test_prune_omits_empty_new_selected_fields() -> None:
    raw = DoctrineSelectionConfig().model_dump(mode="json")
    pruned = _prune_optional_empties(raw)
    for key in _NEW_SELECTED_KEYS:
        assert key not in pruned, (
            f"Empty {key!r} should have been pruned, but appears in: "
            f"{sorted(pruned)}"
        )


def test_prune_keeps_populated_new_selected_fields() -> None:
    cfg = DoctrineSelectionConfig(selected_styleguides=["caveman-comments"])
    raw = cfg.model_dump(mode="json")
    pruned = _prune_optional_empties(raw)
    assert pruned.get("selected_styleguides") == ["caveman-comments"]


# ---------------------------------------------------------------------------
# Round-trip via emit_yaml
# ---------------------------------------------------------------------------


def test_round_trip_through_emit_yaml(tmp_path: Path) -> None:
    governance = GovernanceConfig(
        charter=DoctrineSelectionConfig(
            selected_styleguides=["caveman-comments"],
            selected_toolguides=["ruff-strict"],
        )
    )
    out = tmp_path / "governance.yaml"
    emit_yaml(governance, out)

    text = out.read_text(encoding="utf-8")
    # Header preserved
    assert text.startswith("# Auto-generated from charter.md")
    # Populated fields land in the emitted YAML
    assert "selected_styleguides" in text
    assert "caveman-comments" in text
    # Empty new fields stay out
    assert "selected_procedures" not in text
    assert "selected_agent_profiles" not in text
    assert "selected_mission_step_contracts" not in text

    data = YAML(typ="safe").load(text)
    charter = data["charter"]
    assert charter["selected_styleguides"] == ["caveman-comments"]
    assert charter["selected_toolguides"] == ["ruff-strict"]


def test_governance_config_carries_activations_field(tmp_path: Path) -> None:
    """T008: ``GovernanceConfig.activations`` lives at the top level (not on
    ``DoctrineSelectionConfig``); defaults to empty; round-trips through
    ``emit_yaml`` with an entry; stays out of YAML when empty (NFR-005)."""
    from charter.activation.activations import ActivationEntry

    # Defaulting
    gov = GovernanceConfig()
    assert hasattr(gov, "activations")
    assert gov.activations == []
    assert "activations" in _OPTIONAL_EMPTY_OMIT_KEYS

    # Round-trip with an entry
    gov_with = GovernanceConfig(
        activations=[
            ActivationEntry(
                activation_context={"action": "implement"},
                charter_pack_id="project",
                artifact_id="caveman-comments",
                artifact_kind="styleguides",
            )
        ]
    )
    out = tmp_path / "governance.yaml"
    emit_yaml(gov_with, out)
    text = out.read_text(encoding="utf-8")
    assert "activations" in text
    assert "caveman-comments" in text

    # Empty-list governance omits the block
    out_empty = tmp_path / "governance_empty.yaml"
    emit_yaml(GovernanceConfig(), out_empty)
    assert "activations" not in out_empty.read_text(encoding="utf-8")


def test_default_governance_round_trip_stays_byte_stable(tmp_path: Path) -> None:
    """The new fields MUST NOT appear in the default-config YAML so existing
    fixtures stay byte-identical pre-/post-mission (NFR-005)."""
    out = tmp_path / "governance.yaml"
    emit_yaml(GovernanceConfig(), out)
    text = out.read_text(encoding="utf-8")
    for key in _NEW_SELECTED_KEYS:
        assert key not in text, (
            f"Default-config emission unexpectedly contains {key!r}: \n{text}"
        )
