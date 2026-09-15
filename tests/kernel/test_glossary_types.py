"""Unit tests for kernel.glossary_types — shared glossary primitive types.

Tests cover the validation logic embedded in __post_init__ methods.
Construction/existence tests are intentionally excluded per project policy.
"""

from __future__ import annotations

import pytest

from kernel.glossary_types import (
    ConflictType,
    SemanticConflict,
    SenseRef,
    Severity,
    TermSurface,
)

pytestmark = pytest.mark.fast


class TestTermSurfaceNormalization:
    """TermSurface enforces lowercase, stripped text."""

    def test_accepts_normalized_text(self) -> None:
        ts = TermSurface("workspace")
        assert ts.surface_text == "workspace"

    def test_accepts_multi_word_normalized(self) -> None:
        ts = TermSurface("work package")
        assert ts.surface_text == "work package"

    def test_rejects_uppercase(self) -> None:
        with pytest.raises(ValueError, match="must be normalized"):
            TermSurface("Workspace")

    def test_rejects_leading_whitespace(self) -> None:
        with pytest.raises(ValueError, match="must be normalized"):
            TermSurface(" workspace")

    def test_rejects_trailing_whitespace(self) -> None:
        with pytest.raises(ValueError, match="must be normalized"):
            TermSurface("workspace ")

    def test_rejects_mixed_case(self) -> None:
        with pytest.raises(ValueError, match="must be normalized"):
            TermSurface("WorkPackage")


class TestSemanticConflictAmbiguousGuard:
    """SemanticConflict requires candidate_senses when type is AMBIGUOUS."""

    def _make_term(self) -> TermSurface:
        return TermSurface("mission")

    def _make_sense(self) -> SenseRef:
        return SenseRef(
            surface="mission",
            scope="team_domain",
            definition="A concrete unit of product work",
            confidence=0.9,
        )

    def test_ambiguous_with_candidates_is_valid(self) -> None:
        conflict = SemanticConflict(
            term=self._make_term(),
            conflict_type=ConflictType.AMBIGUOUS,
            severity=Severity.MEDIUM,
            confidence=0.8,
            candidate_senses=[self._make_sense()],
        )
        assert conflict.conflict_type == ConflictType.AMBIGUOUS
        assert len(conflict.candidate_senses) == 1

    def test_ambiguous_without_candidates_raises(self) -> None:
        with pytest.raises(ValueError, match="AMBIGUOUS conflict must have candidate_senses"):
            SemanticConflict(
                term=self._make_term(),
                conflict_type=ConflictType.AMBIGUOUS,
                severity=Severity.HIGH,
                confidence=0.9,
                candidate_senses=[],
            )

    def test_non_ambiguous_without_candidates_is_valid(self) -> None:
        """UNKNOWN, INCONSISTENT, UNRESOLVED_CRITICAL do not require candidates."""
        for conflict_type in (
            ConflictType.UNKNOWN,
            ConflictType.INCONSISTENT,
            ConflictType.UNRESOLVED_CRITICAL,
        ):
            conflict = SemanticConflict(
                term=self._make_term(),
                conflict_type=conflict_type,
                severity=Severity.LOW,
                confidence=0.5,
            )
            assert conflict.conflict_type == conflict_type
