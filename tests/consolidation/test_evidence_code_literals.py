"""The evidence refusal codes, the attestation value and its flag, pinned by their literal strings (#6715, #5939).

Operators, the ``--json`` envelopes and orchestrator-api ``data.preflight_error_codes`` key on
these strings, so renaming a Python name must never change one. Every assertion compares
against a literal, never against the module constant itself.
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation import wp_evidence

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: Each single_branch alias code (#5939, still emitted) and the neutral code it maps onto.
_ALIASES = {
    "SINGLE_BRANCH_IMPLEMENTATION_MISSING": "IMPLEMENTATION_MISSING",
    "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT": "REVIEW_NOT_INDEPENDENT",
    "SINGLE_BRANCH_EVIDENCE_UNREADABLE": "IMPLEMENTATION_UNREADABLE",
    "SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE": "IMPLEMENTATION_UNREADABLE",
    "SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE": "EVIDENCE_WINDOW_UNCOMPUTABLE",
}


def test_the_neutral_codes_keep_their_literal_values() -> None:
    assert wp_evidence.IMPLEMENTATION_MISSING == "IMPLEMENTATION_MISSING"
    assert wp_evidence.REVIEW_NOT_INDEPENDENT == "REVIEW_NOT_INDEPENDENT"
    assert wp_evidence.IMPLEMENTATION_UNREADABLE == "IMPLEMENTATION_UNREADABLE"
    assert wp_evidence.EVIDENCE_WINDOW_UNCOMPUTABLE == "EVIDENCE_WINDOW_UNCOMPUTABLE"
    assert wp_evidence._NEUTRAL_CODES == ("IMPLEMENTATION_MISSING", "REVIEW_NOT_INDEPENDENT", "IMPLEMENTATION_UNREADABLE", "EVIDENCE_WINDOW_UNCOMPUTABLE")


def test_the_single_branch_alias_codes_keep_their_literal_values() -> None:
    assert wp_evidence.SINGLE_BRANCH_IMPLEMENTATION_MISSING == "SINGLE_BRANCH_IMPLEMENTATION_MISSING"
    assert wp_evidence.SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT == "SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT"
    assert wp_evidence._SINGLE_BRANCH_EVIDENCE_UNREADABLE == "SINGLE_BRANCH_EVIDENCE_UNREADABLE"
    assert wp_evidence.SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE == "SINGLE_BRANCH_IMPLEMENTATION_UNREADABLE"
    assert wp_evidence.SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE == "SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE"
    assert dict(wp_evidence._SINGLE_BRANCH_ALIASES) == _ALIASES


@pytest.mark.parametrize(("alias", "neutral"), sorted(_ALIASES.items()))
def test_every_literal_code_leads_a_refusal_line_and_maps_to_its_neutral_code(alias: str, neutral: str) -> None:
    assert wp_evidence._refusal_codes(f"header\n{alias}: WP01 detail\n{neutral}: WP02 detail") == [alias, neutral]
    assert wp_evidence._canonical_code(alias) == neutral
    assert wp_evidence._canonical_code(neutral) == neutral


def test_the_attestation_value_and_flag_keep_their_literal_values() -> None:
    assert wp_evidence.NO_IMPLEMENTATION == "no_implementation"
    assert wp_evidence.ATTEST_NO_IMPLEMENTATION_FLAG == "--attest-no-implementation"
