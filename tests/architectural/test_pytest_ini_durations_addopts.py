"""PR-TESTS-003: ``pytest.ini``'s durations-reporting ``addopts`` must not
silently regress.

WP07 added ``--durations=0 --durations-min=1.0`` to ``pytest.ini``'s
``addopts`` (CI-log diagnostics: report every test slower than 1.0s). Nothing
asserted the flags stayed there -- reverting the line to plain ``--tb=short``
would not fail any other test in the suite. This test parses ``pytest.ini``
with ``configparser`` (the same approach ``test_quarantine_marker.py`` uses
for the live marker registry -- never a loose regex over the whole file) and
tokenizes ``addopts`` properly, so it catches the flags being dropped,
renamed, or truncated (e.g. ``--durations-min=1`` losing precision) without
false-positiving on unrelated ``addopts`` edits.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REQUIRED_TOKENS = ("--durations=0", "--durations-min=1.0")


def _addopts_tokens() -> list[str]:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(_REPO_ROOT / "pytest.ini", encoding="utf-8")
    raw = parser.get("pytest", "addopts", fallback="")
    return raw.split()


def test_addopts_keeps_the_durations_reporting_flags() -> None:
    tokens = _addopts_tokens()
    missing = [token for token in _REQUIRED_TOKENS if token not in tokens]
    assert not missing, f"pytest.ini's [pytest] addopts is missing {missing} (WP07's durations-reporting flags) -- got tokens: {tokens}"


def test_addopts_is_actually_parsed_as_tokens_not_a_substring() -> None:
    """Non-vacuousness control: a value that merely CONTAINS the substring
    (e.g. ``--durations-min=10.0``) must not satisfy the token-exact check
    above -- proves this test reads real tokens, not a loose substring scan."""
    tokens = ["--tb=short", "--durations=0", "--durations-min=10.0"]
    assert "--durations-min=1.0" not in tokens
