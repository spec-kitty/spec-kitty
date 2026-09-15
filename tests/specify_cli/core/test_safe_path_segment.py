"""Tests for the canonical safe-path-segment validator.

T001 (NFR-006): union-of-real-format-slugs accepts + traversal rejects.

Dot-policy decision:
  The canonical grammar adopts the interior-dot-allowed form (so transaction.py's
  real accepts survive) but rejects leading-dot and any ``..`` substring (traversal
  guard). This WIDENS merge.py's slug acceptance to allow interior dots — that is
  intentional. No caller relies on merge.py rejecting a dotted slug (verified:
  merge.py's _validate_mission_slug_path_segment is WP02's target; its callers
  only see valid mission slugs produced by the CLI creation flow, which never
  emits interior dots; the widening is safe).
"""

from __future__ import annotations

import pytest

from specify_cli.core.paths import UnsafePathSegmentError, assert_safe_path_segment

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Union of real-format values — every currently-valid format MUST pass
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [
        # Full 26-char ULID (used as mission_id)
        "01KVBBT6FEQ01NHNSQD7X8JTPE",
        # <slug>-<mid8> directory name (post-083 naming)
        "canonical-seams-path-trust-guard-capability-01KVBBT6",
        # Numeric-prefix slug (legacy missions)
        "034-feature-status-state-model",
        # Bare mid8 (handle disambiguation)
        "01KVBBT6",
        # Simple kebab slug
        "my-feature",
        # Slug with interior dot — transaction.py allows this; the reconciled
        # grammar keeps it to avoid breaking existing mission directories
        # that contain a dot character.
        "my.feature",
        # Slug with underscore (aggregate.py pattern allows underscores)
        "my_feature",
        # Alphanumeric only
        "abc123",
    ],
    ids=[
        "full-ulid",
        "slug-mid8",
        "numeric-prefix-slug",
        "bare-mid8",
        "simple-kebab",
        "interior-dot",
        "underscore",
        "alphanumeric",
    ],
)
def test_accept_real_format_values(value: str) -> None:
    """Every currently-valid real-format mission slug/segment MUST pass."""
    result = assert_safe_path_segment(value)
    assert result == value, (
        f"assert_safe_path_segment({value!r}) must return the value unchanged, "
        f"got {result!r}"
    )


# ---------------------------------------------------------------------------
# Traversal guard — MUST raise UnsafePathSegmentError for all of these
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [
        # Empty and whitespace
        "",
        "   ",
        # Literal traversal tokens
        ".",
        "..",
        # Path separators
        "a/b",
        "a\\b",
        # Classic traversal sequence
        "../escape",
        # Non-ASCII character
        "naïve",
        # Leading slash
        "/absolute",
        # Trailing slash
        "trailing/",
        # ---------------------------------------------------------------
        # Dotted-traversal forms: these are NOT in the literal {".", ".."}
        # set but must be rejected because their stripped form begins with
        # "." or contains ".." as a substring.  A grammar that only
        # special-cases the two literal tokens would wrongly ACCEPT these —
        # this is the squad-flagged gaming path (T001 binding constraint).
        # ---------------------------------------------------------------
        # Begins with "." (hidden-file style — leading-dot rejected)
        ".hidden",
        # ".." as a substring with trailing chars
        "..foo",
        # ".." as a substring with leading chars
        "foo..",
        # ".." as an interior substring
        "a..b",
    ],
    ids=[
        "empty",
        "whitespace",
        "dot",
        "dotdot",
        "forward-slash",
        "backslash",
        "classic-traversal",
        "non-ascii",
        "leading-slash",
        "trailing-slash",
        "hidden-file",
        "dotdot-prefix",
        "dotdot-suffix",
        "dotdot-interior",
    ],
)
def test_reject_traversal_values(value: str) -> None:
    """Traversal-unsafe values raise the dedicated, ValueError-compatible subtype."""
    with pytest.raises(UnsafePathSegmentError, match="safe path segment"):
        assert_safe_path_segment(value)


def test_returns_validated_value() -> None:
    """assert_safe_path_segment returns the input value unchanged on success."""
    result = assert_safe_path_segment("01KVBBT6FEQ01NHNSQD7X8JTPE")
    assert result == "01KVBBT6FEQ01NHNSQD7X8JTPE"
