"""The owned-file matcher lives in ``specify_cli.ownership.matching`` (Mission review-context-wp-diff-01M774QF, WP01).

The evidence axis, ``move-task`` and the review range share one matcher; these tests pin
its rules and that ``consolidation.wp_evidence`` re-exports the same function objects.
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation import wp_evidence
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


def test_wp_evidence_re_exports_the_one_definition() -> None:
    assert wp_evidence.matches_owned is matching.matches_owned
    assert wp_evidence.owned_patterns is matching.owned_patterns
    assert matching.matches_owned.__module__ == "specify_cli.ownership.matching"
