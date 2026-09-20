"""#4327 mint/classify drift guard.

The synthetic ``review_ref`` token grammar (``review:<WP>``,
``approval:<WP>``, ``auto-approval:<WP>:<date>``) used to be hardcoded as
f-strings at four mint sites AND re-listed as a prefix tuple in the
classifier (``is_synthetic_review_ref``). A prefix rename at a mint site
without a matching classifier update would silently reintroduce the bogus
"review feedback artifact is missing" bug #4327 fixed: the new token would
resolve as a pointer instead of being skipped as a marker.

This test pins the mint formatters (``synthetic_review_ref``,
``synthetic_approval_ref``, ``synthetic_auto_approval_ref``) — now the
single source of truth alongside ``SYNTHETIC_REVIEW_REF_PREFIXES`` — against
both their exact literal output and the classifier, so drift between mint
and classify shows up as a failing test instead of a silent divergence.
"""

from __future__ import annotations

import pytest

from specify_cli.review.cycle import (
    is_non_resolvable_review_ref,
    is_synthetic_review_ref,
    synthetic_approval_ref,
    synthetic_auto_approval_ref,
    synthetic_review_ref,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_synthetic_review_ref_literal_and_classified() -> None:
    token = synthetic_review_ref("WP03")
    assert token == "review:WP03"
    assert is_synthetic_review_ref(token) is True


def test_synthetic_approval_ref_literal_and_classified() -> None:
    token = synthetic_approval_ref("WP07")
    assert token == "approval:WP07"
    assert is_synthetic_review_ref(token) is True


def test_synthetic_auto_approval_ref_literal_and_classified() -> None:
    token = synthetic_auto_approval_ref("WP12", "20260920")
    assert token == "auto-approval:WP12:20260920"
    assert is_synthetic_review_ref(token) is True


@pytest.mark.parametrize(
    "pointer",
    [
        "review-cycle://WP01/1",
        "feedback://WP01/review-feedback-1.md",
    ],
)
def test_real_pointer_families_are_not_synthetic(pointer: str) -> None:
    assert is_synthetic_review_ref(pointer) is False


def test_is_non_resolvable_review_ref_folds_sentinels_and_synthetic_prefixes() -> None:
    # Exact-value operational sentinel.
    assert is_non_resolvable_review_ref("action-review-claim") is True
    assert is_non_resolvable_review_ref("force-override") is True
    # Synthetic mint-site tokens.
    assert is_non_resolvable_review_ref(synthetic_review_ref("WP01")) is True
    assert is_non_resolvable_review_ref(synthetic_approval_ref("WP01")) is True
    assert is_non_resolvable_review_ref(synthetic_auto_approval_ref("WP01", "20260101")) is True
    # A real pointer must NOT be treated as non-resolvable.
    assert is_non_resolvable_review_ref("review-cycle://WP01/1") is False


def test_auto_forward_deliberately_not_synthetic() -> None:
    """#4327 scope guard: ``auto-forward:`` is an approval-hop token, not a
    synthetic marker -- it must stay resolvable, so it is deliberately absent
    from ``SYNTHETIC_REVIEW_REF_PREFIXES``.
    """
    assert is_synthetic_review_ref("auto-forward:WP01") is False
