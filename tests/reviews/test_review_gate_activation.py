"""Tests for the SPDD/REASONS conditional review-gate block (WP05).

Covers FR-015, FR-016, FR-017, FR-018, NFR-001 and the seven contract cases
in ``contracts/review-gate.md``.

The renderer hook (``process_spdd_blocks``) is reused as-is from WP04. These
tests only verify that ``review.md`` carries the expected SPDD reasons-block
content and that inactive rendering remains byte-identical to the synthesized
pre-block baseline.
"""

from __future__ import annotations

import pytest

# The tests live once, in ``tests/architectural/_lifted_reviews.py``, which this suite's
# always-on lift also imports (#5015); importing them is what makes pytest collect them here.
from tests.architectural._lifted_reviews import TestReviewGateActivation as TestReviewGateActivation

pytestmark = [pytest.mark.unit, pytest.mark.fast]
