"""Every evidence refusal names a recovery an operator can actually run (#6715, from #6871's investigation).

The single-agent shape in #6871's fleet evidence — one actor implementing and approving, so the lane
window holds no owned content and the approval is not independent — reaches an operator as
`IMPLEMENTATION_MISSING` and/or `REVIEW_NOT_INDEPENDENT`. Nothing in the machinery pretends a second
actor exists, so the honest answer is the one the refusal carries: the attestation flag for a work
package that owes no implementation, and a genuinely different reviewer for the other. This pins the
two facts an operator depends on, through the ONE table the public refusal text is built from
(`wp_evidence._RECOVERY`, read 1:1 by `_lanes_refusal_text`) — not its wording or its ordering.
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation import wp_evidence

pytestmark = [pytest.mark.unit]

_NEUTRAL_CODES = (wp_evidence.IMPLEMENTATION_MISSING, wp_evidence.REVIEW_NOT_INDEPENDENT)


@pytest.mark.parametrize("code", _NEUTRAL_CODES)
def test_each_single_agent_code_has_its_own_recovery(code: str) -> None:
    recovery = wp_evidence._RECOVERY[code]

    assert code in recovery, "the recovery names the code it clears"
    assert "then re-run" in recovery or "`spec-kitty " in recovery, "a recovery must name the step (or command) that clears the refusal"


def test_implementation_missing_recovers_through_the_attestation_flag() -> None:
    """A work package that owes no implementation is recorded, not re-implemented: the flag plus its reason."""
    recovery = wp_evidence._RECOVERY[wp_evidence.IMPLEMENTATION_MISSING]

    assert wp_evidence.ATTEST_NO_IMPLEMENTATION_FLAG in recovery
    assert "--attest-reason" in recovery, "the flag alone is refused; the reason is required"


def test_review_not_independent_cannot_be_attested_away() -> None:
    """A single actor cannot clear the independence axis by attesting: only another reviewer can."""
    recovery = wp_evidence._RECOVERY[wp_evidence.REVIEW_NOT_INDEPENDENT]

    assert "reviewer who is not the implementer" in recovery
    assert "No attestation lifts this" in recovery
