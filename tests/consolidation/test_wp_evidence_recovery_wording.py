"""Every evidence refusal names a recovery an operator can actually run (#6715, #6871 investigation).

The single-agent shape reported in #6871's fleet evidence — one actor implementing and approving, so
the lane window holds no owned content and the approval is not independent — reaches an operator as
`IMPLEMENTATION_MISSING` and/or `REVIEW_NOT_INDEPENDENT`. Nothing in the machinery pretends a second
actor exists, so the honest answer is the one the refusal carries: the attestation flag for a work
package that owes no implementation, and a genuinely different reviewer for the other. This pins
that contract so a later wording change cannot leave an operator with a code and no next step.
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation import wp_evidence

pytestmark = [pytest.mark.unit]

_NEUTRAL_CODES = (wp_evidence.IMPLEMENTATION_MISSING, wp_evidence.REVIEW_NOT_INDEPENDENT)


@pytest.mark.parametrize("code", _NEUTRAL_CODES)
def test_each_single_agent_code_has_its_own_recovery_line(code: str) -> None:
    recovery = wp_evidence._RECOVERY[code]

    assert recovery.startswith(f"Recovery for {code}:"), recovery
    assert "then re-run" in recovery or "`spec-kitty " in recovery, "a recovery must name the step (or command) that clears the refusal"


def test_implementation_missing_names_the_attestation_flag() -> None:
    recovery = wp_evidence._RECOVERY[wp_evidence.IMPLEMENTATION_MISSING]

    assert wp_evidence.ATTEST_NO_IMPLEMENTATION_FLAG in recovery
    assert "--attest-reason" in recovery, "the flag alone is refused; the reason is required"


def test_review_not_independent_says_no_attestation_lifts_it() -> None:
    """A single actor cannot clear the independence axis by attesting: only another reviewer can."""
    recovery = wp_evidence._RECOVERY[wp_evidence.REVIEW_NOT_INDEPENDENT]

    assert "reviewer who is not the implementer" in recovery
    assert "No attestation lifts this" in recovery


def test_the_lanes_refusal_carries_exactly_the_recoveries_for_the_codes_it_emitted() -> None:
    text = wp_evidence._lanes_refusal_text("single-agent-mission", [f"{wp_evidence.REVIEW_NOT_INDEPENDENT}: WP01 was approved by its implementer."])

    assert "Recovery for REVIEW_NOT_INDEPENDENT:" in text
    assert "Recovery for IMPLEMENTATION_MISSING:" not in text, "a refusal must not name a recovery for a code it did not emit"


def test_an_empty_lane_window_refusal_offers_both_next_steps() -> None:
    """The #7082 shape emits both codes; the text must then carry both recoveries, in code order."""
    text = wp_evidence._lanes_refusal_text(
        "single-agent-mission",
        [
            f"{wp_evidence.IMPLEMENTATION_MISSING}: WP01 was approved with no implementation commit touching its owned_files.",
            f"{wp_evidence.REVIEW_NOT_INDEPENDENT}: WP01 was approved by its implementer.",
        ],
    )

    assert text.index("Recovery for IMPLEMENTATION_MISSING:") < text.index("Recovery for REVIEW_NOT_INDEPENDENT:")
