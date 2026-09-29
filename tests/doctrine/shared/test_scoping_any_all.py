"""T021 — applies_to_languages_match behavior for ``any``/``all`` sentinel tokens.

FR-012 defense-in-depth: when ``applies_to_languages`` contains a sentinel
token (``any`` / ``all``), the artifact is treated as **unscoped** (always
loads) rather than silently disappearing.

The validate-time guard (T020) rejects these tokens at authoring time so
reaching this function with them in production means the artifact bypassed
validation.  The correct runtime fallback is to load it (fail-open) rather
than silently filter it out — a missing-content bug is harder to debug than
a "why did this load?" question.

T021 decision: **normalize ``any``/``all`` → unscoped/always-load** (not
"treat as unreachable with an assertion error").  This is tested below as
the observable contract.
"""

from __future__ import annotations

import pytest

from charter.offering.shared.scoping import _SENTINEL_TOKENS, applies_to_languages_match

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]


# ---------------------------------------------------------------------------
# Sentinel token set
# ---------------------------------------------------------------------------


class TestSentinelTokenSet:
    """The _SENTINEL_TOKENS constant must cover the canonical sentinels."""

    def test_any_is_a_sentinel(self) -> None:
        assert "any" in _SENTINEL_TOKENS

    def test_all_is_a_sentinel(self) -> None:
        assert "all" in _SENTINEL_TOKENS


# ---------------------------------------------------------------------------
# T021: sentinel tokens → always-load (defense-in-depth behavior)
# ---------------------------------------------------------------------------


class TestSentinelTokensAlwaysLoad:
    """Sentinel tokens in applies_to_languages are treated as unscoped."""

    def test_any_alone_returns_true_for_specific_active_lang(self) -> None:
        """``[any]`` with a concrete active language → True (always-load)."""
        assert applies_to_languages_match(["any"], ["python"]) is True

    def test_all_alone_returns_true_for_specific_active_lang(self) -> None:
        """``[all]`` with a concrete active language → True (always-load)."""
        assert applies_to_languages_match(["all"], ["python"]) is True

    def test_any_alone_returns_true_for_empty_active_scope(self) -> None:
        """``[any]`` with empty active scope → True.

        Normal scoped artifacts return False for an empty active scope; sentinel
        tokens bypass that and return True (defense-in-depth: prefer loading
        over silently filtering).
        """
        assert applies_to_languages_match(["any"], []) is True

    def test_all_alone_returns_true_for_empty_active_scope(self) -> None:
        """``[all]`` with empty active scope → True (same reasoning)."""
        assert applies_to_languages_match(["all"], []) is True

    def test_any_case_insensitive(self) -> None:
        """Guard normalizes to lowercase; ``ANY`` behaves like ``any``."""
        assert applies_to_languages_match(["ANY"], ["python"]) is True

    def test_all_case_insensitive(self) -> None:
        """``ALL`` normalizes to ``all`` → sentinel → always-load."""
        assert applies_to_languages_match(["ALL"], ["python"]) is True

    def test_any_only_sentinel_set_with_no_active_filter(self) -> None:
        """``[any]`` with active_languages=None → True (same as unscoped)."""
        assert applies_to_languages_match(["any"], None) is True

    def test_all_only_sentinel_set_with_no_active_filter(self) -> None:
        """``[all]`` with active_languages=None → True."""
        assert applies_to_languages_match(["all"], None) is True


# ---------------------------------------------------------------------------
# Non-sentinel scoped artifacts are NOT affected (regression guard)
# ---------------------------------------------------------------------------


class TestNonSentinelScopingUnchanged:
    """The sentinel guard must not alter behavior for non-sentinel tokens."""

    def test_mixed_sentinel_and_real_lang_returns_true(self) -> None:
        """``[any, python]`` — mixed list containing a sentinel.

        The sentinel check fires only when the artifact scope is a *subset*
        of sentinels.  A mixed list that includes real language tokens is NOT
        treated as a sentinel-only scope and falls through to normal matching.
        Since ``python`` overlaps ``python`` the result is still True, but via
        the normal overlap path.
        """
        assert applies_to_languages_match(["any", "python"], ["python"]) is True


# ---------------------------------------------------------------------------
# WP02 (#5284): reserved ``unknown`` language vocabulary
# ---------------------------------------------------------------------------

_MATCH_TABLE = [
    # (artifact, active, expected)
    (["python"], ["unknown"], False),  # GREEN control
    ([], ["unknown"], True),  # GREEN control
    (None, ["unknown"], True),  # GREEN control
    (["unknown"], ["unknown"], False),  # RED
    (["unknown"], ["python"], False),  # GREEN control
    (["unknown"], None, False),  # RED
    (["python"], ["python", "unknown"], True),  # GREEN control
    (["any"], ["unknown"], True),  # GREEN control
    (["python"], None, True),  # GREEN control
    (["python"], [], False),  # GREEN control
]


@pytest.mark.parametrize(("artifact", "active", "expected"), _MATCH_TABLE)
def test_reserved_unknown_truth_table(artifact: list[str] | None, active: list[str] | None, expected: bool) -> None:
    """RED (pins the fix) for ([unknown],[unknown]) and ([unknown],None); GREEN control otherwise.

    The reserved token ``unknown`` is stripped from both sides; an artifact
    scoped only to ``unknown`` never loads (invalid scope).
    """
    assert applies_to_languages_match(artifact, active) is expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (None, False),
        ([], False),
        (["unknown"], True),
        (["UNKNOWN "], True),
        (["python", "unknown"], False),
    ],
)
def test_is_unknown_language(values: list[str] | None, expected: bool) -> None:
    """RED (pins the fix): only a set equal to {"unknown"} is an unknown-language project."""
    from charter.offering.shared import scoping

    # getattr keeps the base failing on an assertion, not an ImportError.
    is_unknown_language = getattr(scoping, "is_unknown_language", None)
    assert is_unknown_language is not None, "is_unknown_language missing from scoping"
    assert is_unknown_language(values) is expected


def test_reserved_tokens_constants() -> None:
    """RED (pins the fix): reserved vocabulary lives in scoping; unknown is NOT a sentinel."""
    from charter.offering.shared import scoping

    assert getattr(scoping, "UNKNOWN_LANGUAGE", None) == "unknown"
    assert getattr(scoping, "RESERVED_LANGUAGE_TOKENS", None) == frozenset({"unknown"})
    assert "unknown" not in _SENTINEL_TOKENS
