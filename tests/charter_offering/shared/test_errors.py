"""Tests for charter.offering.shared.errors — inline-reference rejection helpers.

Targets mutation-prone areas:
- reject_inline_refs: artifact_id fallback ("?"), forbidden_field assignment,
  field presence check across all FORBIDDEN_TOP_LEVEL_FIELDS
- reject_inline_refs_in_procedure_steps: same artifact_id fallback,
  continue vs. break (multiple steps), forbidden_field assignment

Patterns: Boundary Pair (id present/absent, field present/absent),
Non-Identity Inputs (distinct field names), Bi-Directional Logic
(raise vs. no-raise).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.shared.errors import (
    build_migration_hint,
    reject_inline_refs,
    reject_inline_refs_in_procedure_steps,
)
from charter.offering.shared.exceptions import InlineReferenceRejectedError

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ── build_migration_hint ───────────────────────────────────────────────────────


class TestBuildMigrationHint:
    """Hint string contains all required components."""

    def test_hint_contains_forbidden_field(self):
        hint = build_migration_hint(
            forbidden_field="tactic_refs",
            source_kind="directive",
            source_id="dir-001",
        )
        assert "tactic_refs" in hint

    def test_hint_contains_source_kind_and_id(self):
        hint = build_migration_hint(
            forbidden_field="tactic_refs",
            source_kind="directive",
            source_id="dir-001",
        )
        assert "directive:dir-001" in hint

    def test_hint_contains_relation_requires(self):
        hint = build_migration_hint(
            forbidden_field="tactic_refs",
            source_kind="directive",
            source_id="dir-001",
        )
        assert "relation: requires" in hint

    def test_hint_names_the_fragment_for_the_source_kind(self):
        hint = build_migration_hint(
            forbidden_field="applies_to",
            source_kind="tactic",
            source_id="tac-001",
        )
        assert "packs/built-in/tactic.graph.yaml" in hint

    def test_hint_names_a_fragment_that_is_on_disk(self):
        """FR-008: a hint that names a missing file is not followable."""
        repo_root = Path(__file__).resolve().parents[3]
        for kind in (
            "directive",
            "tactic",
            "procedure",
            "paradigm",
            "styleguide",
            "toolguide",
            "agent_profile",
        ):
            hint = build_migration_hint(forbidden_field="applies_to", source_kind=kind, source_id="x")
            named = hint.rsplit(" to ", 1)[1]
            assert (repo_root / named).is_file(), f"{kind}: {named} is not on disk"

    def test_hint_with_target_kind_and_id(self):
        hint = build_migration_hint(
            forbidden_field="tactic_refs",
            source_kind="procedure",
            source_id="proc-001",
            target_kind="tactic",
            target_id="tac-specific",
        )
        assert "tactic:tac-specific" in hint


# ── reject_inline_refs (top-level) ────────────────────────────────────────────


class TestRejectInlineRefs:
    """Top-level rejection with artifact_id fallback and field assignment."""

    def test_raises_for_tactic_refs(self):
        with pytest.raises(InlineReferenceRejectedError):
            reject_inline_refs(
                {"id": "d-001", "tactic_refs": ["t-1"]},
                file_path="/some/d-001.yaml",
                artifact_kind="directive",
            )

    def test_raises_for_paradigm_refs(self):
        with pytest.raises(InlineReferenceRejectedError):
            reject_inline_refs(
                {"id": "d-001", "paradigm_refs": ["p-1"]},
                file_path="/some/d-001.yaml",
                artifact_kind="directive",
            )

    def test_raises_for_applies_to(self):
        with pytest.raises(InlineReferenceRejectedError):
            reject_inline_refs(
                {"id": "d-001", "applies_to": ["a-1"]},
                file_path="/some/d-001.yaml",
                artifact_kind="directive",
            )

    def test_no_raise_when_no_forbidden_field(self):
        reject_inline_refs(
            {"id": "d-001", "title": "safe"},
            file_path="/some/d-001.yaml",
            artifact_kind="directive",
        )

    def test_forbidden_field_attribute_matches_rejected_field(self):
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs(
                {"id": "d-001", "tactic_refs": ["t-1"]},
                file_path="/some/d-001.yaml",
                artifact_kind="directive",
            )
        assert excinfo.value.forbidden_field == "tactic_refs"
        assert excinfo.value.forbidden_field is not None

    def test_forbidden_field_attribute_for_applies_to(self):
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs(
                {"id": "d-001", "applies_to": ["a-1"]},
                file_path="/some/d-001.yaml",
                artifact_kind="tactic",
            )
        assert excinfo.value.forbidden_field == "applies_to"

    def test_artifact_id_from_data_appears_in_hint(self):
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs(
                {"id": "specific-id-123", "tactic_refs": ["t-1"]},
                file_path="/some/file.yaml",
                artifact_kind="directive",
            )
        assert "specific-id-123" in excinfo.value.migration_hint

    def test_artifact_id_fallback_when_absent(self):
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs(
                {"tactic_refs": ["t-1"]},
                file_path="/some/file.yaml",
                artifact_kind="directive",
            )
        assert "?" in excinfo.value.migration_hint

    def test_artifact_kind_attribute_set_correctly(self):
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs(
                {"id": "d-001", "tactic_refs": ["t-1"]},
                file_path="/some/d-001.yaml",
                artifact_kind="tactic",
            )
        assert excinfo.value.artifact_kind == "tactic"

    def test_file_path_attribute_set_correctly(self):
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs(
                {"id": "d-001", "tactic_refs": ["t-1"]},
                file_path="/specific/path/d-001.yaml",
                artifact_kind="directive",
            )
        assert excinfo.value.file_path == "/specific/path/d-001.yaml"


# ── reject_inline_refs_in_procedure_steps ────────────────────────────────────


class TestRejectInlineRefsInProcedureSteps:
    """Step-level rejection: continue vs. break, artifact_id fallback, field assignment."""

    def test_raises_for_tactic_refs_in_step(self):
        data = {
            "id": "proc-001",
            "steps": [{"id": "step-1", "tactic_refs": ["t-1"]}],
        }
        with pytest.raises(InlineReferenceRejectedError):
            reject_inline_refs_in_procedure_steps(data, file_path="/proc.yaml")

    def test_raises_for_paradigm_refs_in_step(self):
        data = {
            "id": "proc-001",
            "steps": [{"id": "step-1", "paradigm_refs": ["p-1"]}],
        }
        with pytest.raises(InlineReferenceRejectedError):
            reject_inline_refs_in_procedure_steps(data, file_path="/proc.yaml")

    def test_no_raise_when_steps_are_clean(self):
        data = {
            "id": "proc-001",
            "steps": [{"id": "step-1", "title": "Do something"}],
        }
        reject_inline_refs_in_procedure_steps(data, file_path="/proc.yaml")

    def test_no_raise_when_no_steps_key(self):
        reject_inline_refs_in_procedure_steps({"id": "proc-001"}, file_path="/proc.yaml")

    def test_second_step_forbidden_field_is_detected(self):
        """continue vs. break: second step must also be checked."""
        data = {
            "id": "proc-001",
            "steps": [
                {"id": "step-1", "title": "clean step"},
                {"id": "step-2", "tactic_refs": ["t-1"]},
            ],
        }
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs_in_procedure_steps(data, file_path="/proc.yaml")
        assert excinfo.value.forbidden_field is not None

    def test_forbidden_field_attribute_is_set_in_step_error(self):
        data = {
            "id": "proc-001",
            "steps": [{"id": "step-1", "tactic_refs": ["t-1"]}],
        }
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs_in_procedure_steps(data, file_path="/proc.yaml")
        assert excinfo.value.forbidden_field == "tactic_refs"
        assert excinfo.value.forbidden_field is not None

    def test_artifact_id_in_hint_when_id_present(self):
        data = {
            "id": "my-procedure-id",
            "steps": [{"tactic_refs": ["t-1"]}],
        }
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs_in_procedure_steps(data, file_path="/proc.yaml")
        assert "my-procedure-id" in excinfo.value.migration_hint

    def test_artifact_id_fallback_when_id_absent_from_data(self):
        data = {"steps": [{"tactic_refs": ["t-1"]}]}
        with pytest.raises(InlineReferenceRejectedError) as excinfo:
            reject_inline_refs_in_procedure_steps(data, file_path="/proc.yaml")
        assert "?" in excinfo.value.migration_hint

    def test_non_list_steps_does_not_raise(self):
        reject_inline_refs_in_procedure_steps(
            {"id": "proc-001", "steps": "not-a-list"},
            file_path="/proc.yaml",
        )

    def test_non_dict_step_skipped(self):
        data = {"id": "proc-001", "steps": ["string-step", None]}
        reject_inline_refs_in_procedure_steps(data, file_path="/proc.yaml")
