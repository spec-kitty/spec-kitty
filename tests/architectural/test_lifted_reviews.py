"""Always-on gate: the SPDD/REASONS review-gate template contract holds.

Lifted from ``tests/reviews/test_review_gate_activation.py`` (WP05, contracts
FR-015/FR-017/FR-018/NFR-001), a ``tests/reviews`` tree recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` — no per-PR lane
selects it (#4374 disposition ledger, disposition 2 — lift-invariant).

The whole seven-case contract runs here, imported from the single home the
source also imports (#5015): inactive rendering of ``review.md`` stays
byte-identical to the synthesized pre-SPDD baseline (NFR-001, no residue
leaks when the doctrine pack is off), and active rendering surfaces the
Canvas Comparison headline, all eight drift outcomes and the charter,
canvas, divergence and outcome instructions (FR-015/FR-016/FR-017).
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_reviews import TestReviewGateActivation as TestReviewGateActivation

pytestmark = [pytest.mark.architectural]
