"""Unit tests for doc_state.py — iteration mode and Divio type validation.

Covers set_iteration_mode() and set_divio_types_selected() with valid inputs,
invalid inputs, and missing-key initialisation of documentation_state.
All tests use tmp_path (no real project required).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.doc_analysis.doc_state import (
    ITERATION_MODES,
    canonical_iteration_mode,
    initialize_documentation_state,
    read_documentation_state,
    set_divio_types_selected,
    set_iteration_mode,
    update_documentation_state,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_VALID_META_BASE: dict = {
    "feature_number": "001",
    "slug": "001-test",
    "mission_slug": "001-test",
    "friendly_name": "Test Feature",
    "mission": "documentation",
    "target_branch": "main",
    "created_at": "2026-01-01T00:00:00+00:00",
}


def _make_meta(path: Path, extra: dict | None = None) -> Path:
    """Write a valid meta.json to *path* and return the Path."""
    data: dict = {**_VALID_META_BASE}
    if extra:
        data.update(extra)
    meta = path / "meta.json"
    meta.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return meta


# ---------------------------------------------------------------------------
# set_iteration_mode
# ---------------------------------------------------------------------------


class TestSetIterationMode:
    """set_iteration_mode() stores valid modes and rejects invalid ones."""

    def test_sets_initial_mode(self, tmp_path: Path) -> None:
        """'initial' is written into documentation_state.iteration_mode."""
        # Arrange
        meta = _make_meta(tmp_path)

        # Assumption check
        assert "documentation_state" not in json.loads(meta.read_text())

        # Act
        set_iteration_mode(meta, "initial")

        # Assert
        stored = json.loads(meta.read_text())
        assert stored["documentation_state"]["iteration_mode"] == "initial"

    def test_sets_gap_filling_mode(self, tmp_path: Path) -> None:
        """'gap_filling' is accepted and stored correctly."""
        # Arrange
        meta = _make_meta(tmp_path)

        # Assumption check
        assert meta.exists()

        # Act
        set_iteration_mode(meta, "gap_filling")

        # Assert
        stored = json.loads(meta.read_text())
        assert stored["documentation_state"]["iteration_mode"] == "gap_filling"

    def test_sets_mission_specific_mode(self, tmp_path: Path) -> None:
        """'mission_specific' is accepted and stored correctly."""
        # Arrange
        meta = _make_meta(tmp_path)

        # Assumption check
        assert meta.exists()

        # Act
        set_iteration_mode(meta, "mission_specific")

        # Assert
        stored = json.loads(meta.read_text())
        assert stored["documentation_state"]["iteration_mode"] == "mission_specific"

    def test_legacy_feature_specific_alias_is_stored_canonically(self, tmp_path: Path) -> None:
        """The legacy 'feature_specific' input is accepted but written as 'mission_specific' (#5205)."""
        # Arrange
        meta = _make_meta(tmp_path)

        # Act
        set_iteration_mode(meta, "feature_specific")

        # Assert
        stored = json.loads(meta.read_text())
        assert stored["documentation_state"]["iteration_mode"] == "mission_specific"

    def test_overwrites_existing_mode(self, tmp_path: Path) -> None:
        """A second call overwrites the previously stored mode."""
        # Arrange
        meta = _make_meta(tmp_path)
        set_iteration_mode(meta, "initial")

        # Assumption check
        assert json.loads(meta.read_text())["documentation_state"]["iteration_mode"] == "initial"

        # Act
        set_iteration_mode(meta, "gap_filling")

        # Assert
        stored = json.loads(meta.read_text())
        assert stored["documentation_state"]["iteration_mode"] == "gap_filling"

    def test_initialises_documentation_state_key(self, tmp_path: Path) -> None:
        """documentation_state is auto-created when absent from meta.json."""
        # Arrange
        meta = _make_meta(tmp_path)

        # Assumption check
        assert "documentation_state" not in json.loads(meta.read_text())

        # Act
        set_iteration_mode(meta, "initial")

        # Assert
        stored = json.loads(meta.read_text())
        assert "documentation_state" in stored

    def test_rejects_invalid_mode(self, tmp_path: Path) -> None:
        """An invalid iteration_mode string raises ValueError."""
        # Arrange
        meta = _make_meta(tmp_path)

        # Assumption check
        assert meta.exists()

        # Act / Assert
        with pytest.raises(ValueError, match="Invalid iteration_mode"):
            set_iteration_mode(meta, "bogus")

    def test_missing_meta_file_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError is raised when meta.json does not exist."""
        # Arrange
        meta = tmp_path / "meta.json"

        # Assumption check
        assert not meta.exists()

        # Act / Assert
        with pytest.raises(FileNotFoundError):
            set_iteration_mode(meta, "initial")


# ---------------------------------------------------------------------------
# Iteration-mode canon and the legacy feature_specific alias (#5205)
# ---------------------------------------------------------------------------


class TestIterationModeCanon:
    """Canonical tokens round-trip; the legacy alias is read-only."""

    @pytest.mark.parametrize("mode", sorted(ITERATION_MODES))
    def test_canonical_tokens_are_identity(self, mode: str) -> None:
        assert canonical_iteration_mode(mode) == mode

    def test_legacy_alias_maps_to_mission_specific(self) -> None:
        assert canonical_iteration_mode("feature_specific") == "mission_specific"

    @pytest.mark.parametrize("value", ["mission-specific", "gap-filling", "bogus", None, 3])
    def test_unknown_values_are_rejected(self, value: object) -> None:
        assert canonical_iteration_mode(value) is None

    def test_read_surfaces_legacy_value_canonically_without_rewriting(self, tmp_path: Path) -> None:
        meta = _make_meta(
            tmp_path,
            {"mission_type": "documentation", "documentation_state": {"iteration_mode": "feature_specific"}},
        )

        state = read_documentation_state(meta)

        assert state is not None
        assert state["iteration_mode"] == "mission_specific"
        # read-only alias: the file on disk is untouched
        assert json.loads(meta.read_text())["documentation_state"]["iteration_mode"] == "feature_specific"

    def test_initialize_normalizes_and_rejects(self, tmp_path: Path) -> None:
        meta = _make_meta(tmp_path, {"mission_type": "documentation"})

        state = initialize_documentation_state(meta, "feature_specific", ["tutorial"], [], "developers")

        assert state["iteration_mode"] == "mission_specific"
        with pytest.raises(ValueError, match="Invalid iteration_mode"):
            initialize_documentation_state(meta, "mission-specific", ["tutorial"], [], "developers")

    def test_update_writes_canonical_token(self, tmp_path: Path) -> None:
        meta = _make_meta(tmp_path, {"mission_type": "documentation"})
        initialize_documentation_state(meta, "initial", ["tutorial"], [], "developers")

        update_documentation_state(meta, iteration_mode="feature_specific")

        stored = json.loads(meta.read_text())
        assert stored["documentation_state"]["iteration_mode"] == "mission_specific"


# ---------------------------------------------------------------------------
# set_divio_types_selected
# ---------------------------------------------------------------------------


class TestSetDivioTypesSelected:
    """set_divio_types_selected() stores valid Divio types and rejects invalid ones."""

    def test_sets_all_four_types(self, tmp_path: Path) -> None:
        """All four Divio types are stored as a list."""
        # Arrange
        meta = _make_meta(tmp_path)
        all_types = ["tutorial", "how-to", "reference", "explanation"]

        # Assumption check
        assert meta.exists()

        # Act
        set_divio_types_selected(meta, all_types)

        # Assert
        stored = json.loads(meta.read_text())
        assert stored["documentation_state"]["divio_types_selected"] == all_types

    def test_sets_single_type(self, tmp_path: Path) -> None:
        """A list with one Divio type is stored correctly."""
        # Arrange
        meta = _make_meta(tmp_path)

        # Assumption check
        assert meta.exists()

        # Act
        set_divio_types_selected(meta, ["reference"])

        # Assert
        stored = json.loads(meta.read_text())
        assert stored["documentation_state"]["divio_types_selected"] == ["reference"]

    def test_rejects_invalid_type(self, tmp_path: Path) -> None:
        """An unrecognised Divio type raises ValueError."""
        # Arrange
        meta = _make_meta(tmp_path)

        # Assumption check
        assert meta.exists()

        # Act / Assert
        with pytest.raises(ValueError, match="Invalid Divio types"):
            set_divio_types_selected(meta, ["tutorial", "unknown-type"])

    def test_preserves_existing_meta_fields(self, tmp_path: Path) -> None:
        """Other meta.json fields are not clobbered when writing Divio types."""
        # Arrange
        meta = _make_meta(tmp_path, extra={"custom_field": "preserve-me"})

        # Assumption check
        assert json.loads(meta.read_text())["custom_field"] == "preserve-me"

        # Act
        set_divio_types_selected(meta, ["how-to"])

        # Assert
        stored = json.loads(meta.read_text())
        assert stored["custom_field"] == "preserve-me"
        assert stored["documentation_state"]["divio_types_selected"] == ["how-to"]
