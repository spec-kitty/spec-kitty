"""Scope: models unit tests — no real git or subprocesses."""

import pytest
from kernel.clock import now_utc
from glossary.models import (
    TermSurface, TermSense, SemanticConflict, Provenance,
    ConflictType, Severity, SenseRef,
    term_surface_to_dict, semantic_conflict_to_dict,
)

pytestmark = pytest.mark.fast

def test_term_surface_normalized():
    """TermSurface must be lowercase and trimmed."""
    ts = TermSurface("workspace")
    assert ts.surface_text == "workspace"

    with pytest.raises(ValueError, match="must be normalized"):
        TermSurface("Workspace")  # Not lowercase

    with pytest.raises(ValueError, match="must be normalized"):
        TermSurface(" workspace ")  # Not trimmed

def test_term_sense_validation():
    """TermSense validates confidence range and definition."""
    prov = Provenance("user:alice", now_utc(), "user_clarification")

    # Valid
    ts = TermSense(
        surface=TermSurface("workspace"),
        scope="team_domain",
        definition="Git worktree directory",
        provenance=prov,
        confidence=0.9,
    )
    assert ts.confidence == 0.9

    # Invalid confidence
    with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
        TermSense(
            surface=TermSurface("workspace"),
            scope="team_domain",
            definition="Git worktree directory",
            provenance=prov,
            confidence=1.5,  # Out of range
        )

    # Empty definition
    with pytest.raises(ValueError, match="Definition cannot be empty"):
        TermSense(
            surface=TermSurface("workspace"),
            scope="team_domain",
            definition="",  # Empty
            provenance=prov,
            confidence=0.9,
        )

def test_semantic_conflict_validation():
    """SemanticConflict validates AMBIGUOUS must have candidates."""
    ts = TermSurface("workspace")

    # Valid AMBIGUOUS with candidates
    sc = SemanticConflict(
        term=ts,
        conflict_type=ConflictType.AMBIGUOUS,
        severity=Severity.HIGH,
        confidence=0.9,
        candidate_senses=[
            SenseRef("workspace", "team_domain", "Git worktree", 0.9),
            SenseRef("workspace", "team_domain", "VS Code workspace", 0.7),
        ],
    )
    assert len(sc.candidate_senses) == 2

    # Invalid: AMBIGUOUS without candidates
    with pytest.raises(ValueError, match="AMBIGUOUS conflict must have candidate_senses"):
        SemanticConflict(
            term=ts,
            conflict_type=ConflictType.AMBIGUOUS,
            severity=Severity.HIGH,
            confidence=0.9,
            candidate_senses=[],  # Empty
        )

    # UNKNOWN without candidates is OK
    sc2 = SemanticConflict(
        term=ts,
        conflict_type=ConflictType.UNKNOWN,
        severity=Severity.MEDIUM,
        confidence=0.7,
        candidate_senses=[],
    )
    assert len(sc2.candidate_senses) == 0


def test_term_surface_to_dict():
    """term_surface_to_dict serializes TermSurface correctly."""
    ts = TermSurface("workspace")
    result = term_surface_to_dict(ts)

    assert result == {"surface_text": "workspace"}
    assert isinstance(result, dict)


def test_semantic_conflict_to_dict():
    """semantic_conflict_to_dict serializes SemanticConflict with enum values."""
    ts = TermSurface("workspace")
    sc = SemanticConflict(
        term=ts,
        conflict_type=ConflictType.AMBIGUOUS,
        severity=Severity.HIGH,
        confidence=0.9,
        candidate_senses=[
            SenseRef("workspace", "team_domain", "Git worktree", 0.9),
            SenseRef("workspace", "team_domain", "VS Code workspace", 0.7),
        ],
        context="step input: description field",
    )

    result = semantic_conflict_to_dict(sc)

    # Check structure
    assert "term" in result
    assert "conflict_type" in result
    assert "severity" in result
    assert "confidence" in result
    assert "candidate_senses" in result
    assert "context" in result

    # Check values
    assert result["term"] == {"surface_text": "workspace"}
    assert result["conflict_type"] == "ambiguous"  # Enum value
    assert result["severity"] == "high"  # Enum value
    assert result["confidence"] == 0.9
    assert result["context"] == "step input: description field"

    # Check candidate_senses structure
    assert len(result["candidate_senses"]) == 2
    assert result["candidate_senses"][0] == {
        "surface": "workspace",
        "scope": "team_domain",
        "definition": "Git worktree",
        "confidence": 0.9,
    }
