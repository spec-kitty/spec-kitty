"""The owned-file matcher lives in ``specify_cli.ownership.matching`` (Mission review-context-wp-diff-01M774QF, WP01).

The evidence axis, ``move-task`` and the review range share one matcher; these tests pin
its rules.
"""

from __future__ import annotations

import pytest

from specify_cli.ownership import matching

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    ("path", "patterns", "expected"),
    [
        ("src/m1/x.py", ("src/m1/*",), True),
        ("src/m1/deep/x.py", ("src/m1/**",), True),
        ("src/m1/deep/x.py", ("src/m1/*",), True),
        ("src/m2/x.py", ("src/m1/**",), False),
        ("src/m10/x.py", ("src/m1/**",), False),
        ("./src/m1/x.py", ("src/m1/**",), True),
        ("src\\m1\\x.py", ("src/m1/**",), True),
        ("src/m1/x.py", (), False),
    ],
)
def test_matches_owned(path: str, patterns: tuple[str, ...], expected: bool) -> None:
    assert matching.matches_owned(path, patterns) is expected


def test_owned_patterns_normalizes_and_drops_blanks() -> None:
    assert matching.owned_patterns(["./src/m1/**", "  ", "a\\b/*"]) == ("src/m1/**", "a/b/*")
