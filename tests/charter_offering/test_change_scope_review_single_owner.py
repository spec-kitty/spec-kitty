"""Change-scope reconciler, review tactics, boring-code-review kind and in-house moves.

Covers:
- ``RECONCILE_CHANGE_SCOPE_TENSIONS`` names DIRECTIVE_052, states the
    tidy-first carve-out, and states the tie-break between Boy Scout Rule's
    naming licence and smallest-viable-diff's file-set discipline.
- The evidence gate of the retired ``locality-of-change`` tactic (3+ real
    failures, the 5-of-7 checklist) lives in ``avoid-gold-plating`` as the
    single owned threshold.
- ``DIRECTIVE_025`` names ``DIRECTIVE_030`` for pre-existing-failure
    classification and does not call proving pre-existing-ness "the waste".
- ``boring-code-review`` resolves as a styleguide, not a tactic.
- ``iterative-deepening-review`` / ``tracker-organisation-workflow`` live in
    the internal pack (renamed / moved), with schema-valid artifacts.
- ``code-review-incremental`` references ``review-intent-and-risk-first``
    rather than restating its steps.

Absence of the retired built-in artifacts and of references to the internal-only
ids is guarded in ``test_retired_ids_absent.py``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from tests.charter_offering.conftest import OFFERING_SOURCE_ROOT, REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

_BUILT_IN = REPO_ROOT / "packs" / "built-in"
_INTERNAL = REPO_ROOT / "packs" / "internal"
_SCHEMAS = OFFERING_SOURCE_ROOT / "schemas"

_RECONCILER = _BUILT_IN / "directives" / "reconcile-change-scope-tensions.directive.yaml"
_DIRECTIVE_025 = _BUILT_IN / "directives" / "025-boy-scout-rule.directive.yaml"
_AVOID_GOLD_PLATING = _BUILT_IN / "tactics" / "avoid-gold-plating.tactic.yaml"
_SMALLEST_VIABLE_DIFF = _BUILT_IN / "tactics" / "change-apply-smallest-viable-diff.tactic.yaml"
_BORING_STYLEGUIDE = _BUILT_IN / "styleguides" / "boring-code-review.styleguide.yaml"
_CODE_REVIEW_INCREMENTAL = _BUILT_IN / "tactics" / "code-review-incremental.tactic.yaml"
_REVIEW_INTENT_FIRST = _BUILT_IN / "tactics" / "review-intent-and-risk-first.tactic.yaml"

_INTERNAL_ITERATIVE_DEEPENING = _INTERNAL / "tactics" / "tracker-backlog-iterative-deepening.tactic.yaml"
_INTERNAL_TRACKER_WORKFLOW = _INTERNAL / "procedures" / "tracker-organisation-workflow.procedure.yaml"

_DIRECTIVE_SCHEMA = _SCHEMAS / "directive.schema.yaml"
_TACTIC_SCHEMA = _SCHEMAS / "tactic.schema.yaml"
_STYLEGUIDE_SCHEMA = _SCHEMAS / "styleguide.schema.yaml"
_PROCEDURE_SCHEMA = _SCHEMAS / "procedure.schema.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _raw_text(path: Path) -> str:
    """Raw file text for substring checks -- avoids ``yaml.safe_dump`` re-wrapping
    long strings across a line break and breaking a substring match."""
    return path.read_text(encoding="utf-8")


def _validate(data: dict[str, Any], schema_path: Path) -> None:
    schema = _load_yaml(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: e.path)
    assert not errors, f"Schema validation failed: {[e.message for e in errors]}"


class TestReconcilerNamesDirective052AndCarveOuts:
    """The reconciler names DIRECTIVE_052, the tidy-first carve-out, and the tie-break."""

    def test_reconciler_names_directive_052(self) -> None:
        text = _raw_text(_RECONCILER)
        assert "DIRECTIVE_052" in text, "RECONCILE_CHANGE_SCOPE_TENSIONS must name DIRECTIVE_052"

    def test_reconciler_states_tidy_first_carve_out(self) -> None:
        text = _raw_text(_RECONCILER).lower()
        assert "tidy-first" in text, "the reconciler must state the tidy-first carve-out"
        assert "precedes the functional change" in " ".join(text.split())

    def test_reconciler_states_the_tie_break(self) -> None:
        text = _raw_text(_RECONCILER).lower()
        assert "tie-break" in text, "the reconciler must state the tie-break between naming and file-set discipline"
        assert "file set" in text
        assert "naming" in text

    def test_reconciler_validates_against_schema(self) -> None:
        data = _load_yaml(_RECONCILER)
        _validate(data, _DIRECTIVE_SCHEMA)


class TestSmallestViableDiffPointsAtTheTieBreak:
    """The tactic's absolute "do not rename" wording must point at the owner of the tie-break."""

    def test_tactic_names_the_reconciler_tie_break(self) -> None:
        text = _raw_text(_SMALLEST_VIABLE_DIFF)
        assert "RECONCILE_CHANGE_SCOPE_TENSIONS" in text, "change-apply-smallest-viable-diff must point at the reconciler's naming tie-break"
        assert "tie-break" in text


class TestDirective025NamesDirective030:
    """DIRECTIVE_025 names DIRECTIVE_030 for pre-existing-failure classification."""

    def test_does_not_call_the_proof_the_waste(self) -> None:
        text = " ".join(_raw_text(_DIRECTIVE_025).split())
        assert "is the waste this directive exists to prevent" not in text

    def test_names_directive_030_for_classification(self) -> None:
        text = _raw_text(_DIRECTIVE_025)
        assert "DIRECTIVE_030" in text, "DIRECTIVE_025 must name DIRECTIVE_030 for pre-existing-failure classification"

    def test_validates_against_schema(self) -> None:
        data = _load_yaml(_DIRECTIVE_025)
        _validate(data, _DIRECTIVE_SCHEMA)


class TestAvoidGoldPlatingOwnsTheEvidenceGate:
    """The locality-of-change evidence gate lives in avoid-gold-plating."""

    def test_avoid_gold_plating_carries_the_evidence_gate(self) -> None:
        raw = _raw_text(_AVOID_GOLD_PLATING)
        text = raw.lower()
        assert "3+" in raw, "the evidence gate's 3+ real-failures threshold must be present"
        assert "5+" in raw or "5/7" in raw, "the 5-of-7 checklist threshold must be present"
        assert "do nothing" in text

    def test_avoid_gold_plating_validates_against_schema(self) -> None:
        data = _load_yaml(_AVOID_GOLD_PLATING)
        _validate(data, _TACTIC_SCHEMA)

    def test_deepening_opportunity_assessment_repoints_to_avoid_gold_plating(self) -> None:
        path = _BUILT_IN / "tactics" / "architecture" / "deepening-opportunity-assessment.tactic.yaml"
        data = _load_yaml(path)
        ids = {ref.get("id") for step in data.get("steps", []) for ref in step.get("references", []) or []}
        ids |= {ref.get("id") for ref in data.get("references", []) or []}
        assert "avoid-gold-plating" in ids, "deepening-opportunity-assessment must repoint to avoid-gold-plating"

    def test_avoid_gold_plating_references_the_deleted_tactics_directive_edges(self) -> None:
        """The locality-of-change tactic's only DRG edges were its references to
        DIRECTIVE_024, DIRECTIVE_001 and DIRECTIVE_003. The fold must carry
        them over so avoid-gold-plating still applies those directives."""
        data = _load_yaml(_AVOID_GOLD_PLATING)
        directive_refs = {ref.get("id") for ref in data.get("references", []) or [] if ref.get("type") == "directive"}
        assert "DIRECTIVE_024" in directive_refs, "avoid-gold-plating must reference DIRECTIVE_024 (locality of change)"
        assert "DIRECTIVE_001" in directive_refs, "avoid-gold-plating must reference DIRECTIVE_001 (architectural integrity)"
        # DIRECTIVE_003 is cited by id in the evidence-gate step, NOT as a typed
        # reference: a typed reference mints a ``suggests`` edge, and
        # avoid-gold-plating sits two ``suggests`` hops from the implement
        # action (via the boring-code-review styleguide), so the edge would
        # deliver the required decision-documentation directive to implement
        # and break the decision-documentation scoping gate
        # (``scan_decision_documentation_scoped_on_implement``). Decision
        # documentation is delivered at review.
        assert "DIRECTIVE_003" not in directive_refs, "a typed DIRECTIVE_003 reference would deliver it to implement (decision-documentation scoping gate)"
        assert "DIRECTIVE_003" in _raw_text(_AVOID_GOLD_PLATING), "avoid-gold-plating must still cite DIRECTIVE_003 (decision documentation) by id"

    def test_avoid_gold_plating_carries_the_accept_reject_rationale_rule(self) -> None:
        text = _raw_text(_AVOID_GOLD_PLATING).lower()
        assert "do-nothing baseline" in text or "do nothing baseline" in text, (
            "the accept/reject rationale must record the do-nothing baseline and alternatives considered"
        )

    def test_avoid_gold_plating_carries_the_adr_supersede_or_reject_rule(self) -> None:
        text = _raw_text(_AVOID_GOLD_PLATING).lower()
        assert "supersede" in text and "adr" in text, "a change that conflicts with an ADR must propose to supersede it or be rejected"

    def test_avoid_gold_plating_carries_the_complexity_creep_failure_mode(self) -> None:
        data = _load_yaml(_AVOID_GOLD_PLATING)
        failure_modes = " ".join(data.get("failure_modes", []) or []).lower()
        assert "complexity creep" in failure_modes, "the complexity-creep failure mode must survive the fold"


class TestBoringCodeReviewIsAStyleguide:
    """boring-code-review resolves as a styleguide."""

    def test_styleguide_file_present_with_same_id(self) -> None:
        assert _BORING_STYLEGUIDE.exists(), "boring-code-review styleguide must exist"
        data = _load_yaml(_BORING_STYLEGUIDE)
        assert data.get("id") == "boring-code-review"

    def test_styleguide_validates_against_schema(self) -> None:
        data = _load_yaml(_BORING_STYLEGUIDE)
        _validate(data, _STYLEGUIDE_SCHEMA)

    def test_directive_039_references_it_as_a_styleguide(self) -> None:
        path = _BUILT_IN / "directives" / "039-lynn-cole-engineering-culture.directive.yaml"
        data = _load_yaml(path)
        refs = {(ref.get("type"), ref.get("id")) for ref in data.get("references", []) or []}
        assert ("styleguide", "boring-code-review") in refs, "DIRECTIVE_039 must reference boring-code-review as a styleguide"


class TestInHouseMoves:
    """iterative-deepening-review / tracker-organisation-workflow live in the internal pack."""

    def test_present_in_internal_pack(self) -> None:
        assert _INTERNAL_ITERATIVE_DEEPENING.exists(), "tracker-backlog-iterative-deepening must exist in packs/internal/tactics/"
        assert _INTERNAL_TRACKER_WORKFLOW.exists(), "tracker-organisation-workflow must exist in packs/internal/procedures/"

    def test_renamed_tactic_id(self) -> None:
        data = _load_yaml(_INTERNAL_ITERATIVE_DEEPENING)
        assert data.get("id") == "tracker-backlog-iterative-deepening"

    def test_procedure_keeps_its_id(self) -> None:
        data = _load_yaml(_INTERNAL_TRACKER_WORKFLOW)
        assert data.get("id") == "tracker-organisation-workflow"

    def test_moved_artifacts_validate_against_schema(self) -> None:
        _validate(_load_yaml(_INTERNAL_ITERATIVE_DEEPENING), _TACTIC_SCHEMA)
        _validate(_load_yaml(_INTERNAL_TRACKER_WORKFLOW), _PROCEDURE_SCHEMA)

    def test_internal_pack_fragment_declares_both_nodes(self) -> None:
        fragment = _load_yaml(_INTERNAL / "drg" / "fragment.yaml")
        node_ids = {node.get("id") for node in fragment.get("nodes", [])}
        assert "tracker-backlog-iterative-deepening" in node_ids
        assert "tracker-organisation-workflow" in node_ids

    def test_internal_pack_fragment_carries_no_issue_numbers(self) -> None:
        text = (_INTERNAL / "drg" / "fragment.yaml").read_text(encoding="utf-8")
        assert not re.search(r"#\d{3,5}\b", text), "internal fragment comments must describe the move in words, not cite #NNNN issue numbers"


class TestReviewTacticLayering:
    """code-review-incremental references review-intent-and-risk-first by reference."""

    def test_review_intent_first_no_longer_asks_to_confirm_with_author(self) -> None:
        raw = " ".join(_raw_text(_REVIEW_INTENT_FIRST).split())
        assert "Confirm or correct this with the author" not in raw
        assert "open intent questions" in raw.lower()

    def test_incremental_references_intent_first(self) -> None:
        data = _load_yaml(_CODE_REVIEW_INCREMENTAL)
        ref_ids: set[str] = set()
        for ref in data.get("references", []) or []:
            ref_ids.add(ref.get("id", ""))
        for step in data.get("steps", []):
            for ref in step.get("references", []) or []:
                ref_ids.add(ref.get("id", ""))
        assert "review-intent-and-risk-first" in ref_ids

    def test_incremental_does_not_restate_its_own_competing_risk_taxonomy(self) -> None:
        text = " ".join(_raw_text(_CODE_REVIEW_INCREMENTAL).split())
        # The old, competing incremental-only taxonomy phrase must be gone --
        # ONE risk taxonomy (intent-first's) is now the single owner.
        assert "architectural boundaries, maintainability, unintended side effects" not in text

    def test_incremental_and_intent_first_validate_against_schema(self) -> None:
        _validate(_load_yaml(_CODE_REVIEW_INCREMENTAL), _TACTIC_SCHEMA)
        _validate(_load_yaml(_REVIEW_INTENT_FIRST), _TACTIC_SCHEMA)
