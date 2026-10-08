"""Unit tests for the canonical kind & ID vocabulary resolver (WP01, FR-027).

Covers:
- ``ArtifactKind.from_operator_token`` hyphen→underscore normalization for all
  8 artifact kinds, the ``mission-type`` sentinel behaviour, and unknown-token
  errors (R-009 / CL-1: no silent fallback).
- ``ArtifactKind.operator_token`` inverse property.
- ``CHARTER_KIND_TOKENS`` universe (8 artifact tokens + ``mission-type``).
- The artifact ID resolver round-trip (config-stem ↔ DRG URN) using real
  built-in artifacts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

from charter.activation.catalog import resolve_offering_root
from charter.activation.kind_vocabulary import (
    MissionTypeNotAnArtifactKind,
    UnknownArtifactIdError,
    resolve_artifact_urn,
    resolve_config_id,
)
from charter.offering.artifact_kinds import CHARTER_KIND_TOKENS, ArtifactKind


# --------------------------------------------------------------------------- #
# from_operator_token
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("directive", ArtifactKind.DIRECTIVE),
        ("tactic", ArtifactKind.TACTIC),
        ("styleguide", ArtifactKind.STYLEGUIDE),
        ("toolguide", ArtifactKind.TOOLGUIDE),
        ("paradigm", ArtifactKind.PARADIGM),
        ("procedure", ArtifactKind.PROCEDURE),
        ("agent-profile", ArtifactKind.AGENT_PROFILE),
        ("mission-step-contract", ArtifactKind.MISSION_STEP_CONTRACT),
        ("template", ArtifactKind.TEMPLATE),
    ],
)
def test_from_operator_token_maps_all_eight_artifact_kinds(
    token: str, expected: ArtifactKind
) -> None:
    assert ArtifactKind.from_operator_token(token) is expected


def test_from_operator_token_is_case_insensitive() -> None:
    assert ArtifactKind.from_operator_token("Agent-Profile") is ArtifactKind.AGENT_PROFILE


def test_from_operator_token_accepts_underscore_form() -> None:
    # Already-canonical underscore form must resolve too (total over documented tokens).
    assert ArtifactKind.from_operator_token("agent_profile") is ArtifactKind.AGENT_PROFILE


def test_from_operator_token_unknown_raises_value_error_listing_tokens() -> None:
    with pytest.raises(ValueError) as excinfo:
        ArtifactKind.from_operator_token("frobnicate")
    message = str(excinfo.value)
    # Lists valid operator tokens — no silent fallback (R-009 / CL-1).
    assert "frobnicate" in message
    assert "agent-profile" in message


def test_from_operator_token_mission_type_raises_distinct_error() -> None:
    with pytest.raises(MissionTypeNotAnArtifactKind):
        ArtifactKind.from_operator_token("mission-type")


def test_mission_type_error_is_not_plain_value_error_subclass_confusion() -> None:
    # mission-type is a *distinct* documented error, routed explicitly by callers.
    assert issubclass(MissionTypeNotAnArtifactKind, ValueError)


# --------------------------------------------------------------------------- #
# operator_token (inverse)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("kind", "token"),
    [
        (ArtifactKind.AGENT_PROFILE, "agent-profile"),
        (ArtifactKind.MISSION_STEP_CONTRACT, "mission-step-contract"),
        (ArtifactKind.DIRECTIVE, "directive"),
    ],
)
def test_operator_token_is_inverse_of_from_operator_token(
    kind: ArtifactKind, token: str
) -> None:
    assert kind.operator_token == token
    assert ArtifactKind.from_operator_token(kind.operator_token) is kind


# --------------------------------------------------------------------------- #
# CHARTER_KIND_TOKENS universe
# --------------------------------------------------------------------------- #

def test_charter_kind_tokens_is_eight_artifact_tokens_plus_mission_type() -> None:
    assert "mission-type" in CHARTER_KIND_TOKENS
    # 8 artifact-kind operator tokens + mission-type. (template is a member but
    # is also an artifact kind; the 8 tokens are the non-template artifact kinds.)
    artifact_tokens = {t for t in CHARTER_KIND_TOKENS if t != "mission-type"}
    assert "agent-profile" in artifact_tokens
    assert "directive" in artifact_tokens
    assert len(CHARTER_KIND_TOKENS) == len(set(CHARTER_KIND_TOKENS))  # no dupes


def test_charter_kind_tokens_artifact_entries_all_resolve() -> None:
    for token in CHARTER_KIND_TOKENS:
        if token == "mission-type":
            continue
        # Every non-mission-type token resolves to an ArtifactKind.
        assert isinstance(ArtifactKind.from_operator_token(token), ArtifactKind)


# --------------------------------------------------------------------------- #
# Artifact ID resolver round-trip
# --------------------------------------------------------------------------- #

@pytest.fixture()
def doctrine_root() -> Path:
    return resolve_offering_root()


@pytest.mark.parametrize(
    ("kind", "config_id", "expected_urn"),
    [
        (
            ArtifactKind.DIRECTIVE,
            "001-architectural-integrity-standard",
            "directive:DIRECTIVE_001",
        ),
        (
            ArtifactKind.TACTIC,
            "adversarial-qa-handoff",
            "tactic:adversarial-qa-handoff",
        ),
        (
            ArtifactKind.AGENT_PROFILE,
            "python-pedro",
            "agent_profile:python-pedro",
        ),
    ],
)
def test_resolve_artifact_urn_uses_id_field(
    kind: ArtifactKind, config_id: str, expected_urn: str, doctrine_root: Path
) -> None:
    urn = resolve_artifact_urn(kind, config_id, doctrine_root=doctrine_root)
    assert urn == expected_urn


@pytest.mark.parametrize(
    ("kind", "config_id"),
    [
        (ArtifactKind.DIRECTIVE, "001-architectural-integrity-standard"),
        (ArtifactKind.TACTIC, "adversarial-qa-handoff"),
        (ArtifactKind.AGENT_PROFILE, "python-pedro"),
    ],
)
def test_round_trip_config_id(
    kind: ArtifactKind, config_id: str, doctrine_root: Path
) -> None:
    urn = resolve_artifact_urn(kind, config_id, doctrine_root=doctrine_root)
    assert resolve_config_id(urn, doctrine_root=doctrine_root) == config_id


def test_project_layer_resolver_ignores_legacy_plural_directory(tmp_path: Path) -> None:
    """Project layer ID resolution scans singular runtime dirs only."""
    doctrine_root = tmp_path / "src-doctrine"
    project_root = tmp_path / ".kittify"
    singular_dir = project_root / "doctrine" / "directive"
    plural_dir = project_root / "doctrine" / "directives" / "project"
    singular_dir.mkdir(parents=True)
    plural_dir.mkdir(parents=True)
    (singular_dir / "950-project-rule.directive.yaml").write_text(
        "id: DIRECTIVE_950\ntype: directive\ntitle: Project\nintent: Project\n",
        encoding="utf-8",
    )
    (plural_dir / "951-legacy-project-rule.directive.yaml").write_text(
        "id: DIRECTIVE_951\ntype: directive\ntitle: Legacy\nintent: Legacy\n",
        encoding="utf-8",
    )

    assert (
        resolve_artifact_urn(
            ArtifactKind.DIRECTIVE,
            "950-project-rule",
            doctrine_root=doctrine_root,
            layer_roots={"project": project_root / "doctrine"},
        )
        == "directive:DIRECTIVE_950"
    )
    with pytest.raises(UnknownArtifactIdError):
        resolve_artifact_urn(
            ArtifactKind.DIRECTIVE,
            "951-legacy-project-rule",
            doctrine_root=doctrine_root,
            layer_roots={"project": project_root / "doctrine"},
        )
    with pytest.raises(UnknownArtifactIdError):
        resolve_config_id(
            "directive:DIRECTIVE_951",
            doctrine_root=doctrine_root,
            layer_roots={"project": project_root / "doctrine"},
        )


def test_resolve_artifact_urn_unknown_id_raises_structured_error(
    doctrine_root: Path,
) -> None:
    with pytest.raises(UnknownArtifactIdError) as excinfo:
        resolve_artifact_urn(
            ArtifactKind.DIRECTIVE, "999-nonexistent", doctrine_root=doctrine_root
        )
    message = str(excinfo.value)
    assert "directive" in message
    assert "999-nonexistent" in message


def test_resolve_config_id_unknown_urn_raises_structured_error(
    doctrine_root: Path,
) -> None:
    with pytest.raises(UnknownArtifactIdError) as excinfo:
        resolve_config_id("directive:DIRECTIVE_999", doctrine_root=doctrine_root)
    message = str(excinfo.value)
    assert "directive" in message
    assert "DIRECTIVE_999" in message


def test_resolve_config_id_malformed_urn_raises_value_error(
    doctrine_root: Path,
) -> None:
    with pytest.raises(ValueError):
        resolve_config_id("not-a-valid-urn", doctrine_root=doctrine_root)
