"""Tests for charter.offering.shared.exceptions — exception class behaviors.

Targets InlineReferenceRejectedError, ArtifactResolutionCycleError attribute
and string representation contracts.

Patterns: Non-Identity Inputs (distinct argument values), Boundary Pair
(required-only vs. all fields).
"""

from __future__ import annotations

import pytest

from charter.offering.shared.exceptions import (
    ArtifactLoadError,
    ArtifactResolutionCycleError,
    InlineReferenceRejectedError,
)

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ── InlineReferenceRejectedError ───────────────────────────────────────────────


class TestInlineReferenceRejectedError:
    """Attribute access and str() representation."""

    def _make_err(self, **overrides) -> InlineReferenceRejectedError:
        kwargs = {
            "file_path": "/path/to/file.yaml",
            "forbidden_field": "tactic_refs",
            "artifact_kind": "directive",
            "migration_hint": "Remove tactic_refs from YAML; add edge {source: x, target: y, relation: requires} to src/charter/offering/directive.graph.yaml",
        }
        kwargs.update(overrides)
        return InlineReferenceRejectedError(**kwargs)

    def test_file_path_attribute(self):
        err = self._make_err(file_path="/specific/path.yaml")
        assert err.file_path == "/specific/path.yaml"

    def test_forbidden_field_attribute(self):
        err = self._make_err(forbidden_field="paradigm_refs")
        assert err.forbidden_field == "paradigm_refs"

    def test_artifact_kind_attribute(self):
        err = self._make_err(artifact_kind="tactic")
        assert err.artifact_kind == "tactic"

    def test_migration_hint_attribute(self):
        hint = "Remove applies_to from YAML; add edge {source: s:id, target: t:id, relation: requires} to src/charter/offering/styleguide.graph.yaml"
        err = self._make_err(migration_hint=hint)
        assert err.migration_hint == hint

    def test_str_contains_file_path(self):
        err = self._make_err(file_path="/my/artifact.yaml")
        assert "/my/artifact.yaml" in str(err)

    def test_str_contains_artifact_kind(self):
        err = self._make_err(artifact_kind="paradigm")
        assert "paradigm" in str(err)

    def test_str_contains_forbidden_field(self):
        err = self._make_err(forbidden_field="applies_to")
        assert "applies_to" in str(err)

    def test_is_value_error_subclass(self):
        err = self._make_err()
        assert isinstance(err, ValueError)

    def test_different_fields_produce_different_attributes(self):
        err_a = self._make_err(forbidden_field="tactic_refs")
        err_b = self._make_err(forbidden_field="paradigm_refs")
        assert err_a.forbidden_field != err_b.forbidden_field


# ── ArtifactResolutionCycleError ───────────────────────────────────────────────


class TestArtifactResolutionCycleError:
    """cycle attribute and str() representation."""

    def test_cycle_attribute_preserved(self):
        cycle = [("tactic", "t-a"), ("tactic", "t-b")]
        err = ArtifactResolutionCycleError(cycle)
        assert err.cycle == cycle

    def test_str_contains_artifact_types(self):
        cycle = [("directive", "d-001"), ("tactic", "t-001")]
        err = ArtifactResolutionCycleError(cycle)
        assert "directive" in str(err)
        assert "tactic" in str(err)

    def test_str_contains_artifact_ids(self):
        cycle = [("directive", "specific-id"), ("tactic", "other-id")]
        err = ArtifactResolutionCycleError(cycle)
        assert "specific-id" in str(err)
        assert "other-id" in str(err)

    def test_empty_cycle_does_not_raise(self):
        err = ArtifactResolutionCycleError([])
        assert err.cycle == []


# ── ArtifactLoadError ──────────────────────────────────────────────────


class TestArtifactLoadError:
    """ArtifactLoadError is an Exception subclass."""

    def test_is_exception_subclass(self):
        assert issubclass(ArtifactLoadError, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(ArtifactLoadError):
            raise ArtifactLoadError("load failed")
