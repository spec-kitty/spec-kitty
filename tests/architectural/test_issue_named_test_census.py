"""Shrink-only census of issue-named test files.

A test file named after an issue (``test_issue_NNNN*`` or ``test_repro_NNNN*``)
records the slice that produced it, not the contract it guards. The
``development-assist-test-cleanup`` procedure requires a fold-or-keep verdict
for each one at mission wrap-up: fold its cases into the purpose-named suite
that owns the contract, or keep it renamed after that contract.

This guard holds the count shrink-only, so a new issue-named file cannot land
without either being judged away or a visible, reviewed bump of
``_HIGH_WATER``. Lower the mark when you fold or rename one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_TESTS_ROOT = Path(__file__).resolve().parents[1]
_ISSUE_NAMED = re.compile(r"^test_(?:issue|repro)_\d{3,}")

# Shrink-only high-water mark of issue-named test files under tests/, as of
# 2026-09-30 after the fold-or-keep pass on the 2026-09-29 slices.
_HIGH_WATER = 90


def _is_issue_named(filename: str) -> bool:
    return filename.endswith(".py") and _ISSUE_NAMED.match(filename) is not None


def _issue_named_test_files() -> list[str]:
    return sorted(str(path.relative_to(_TESTS_ROOT)) for path in _TESTS_ROOT.rglob("test_*.py") if _is_issue_named(path.name))


def test_issue_named_test_files_do_not_exceed_high_water_mark() -> None:
    """A new issue-named test file needs a fold-or-keep verdict, not a silent landing."""
    files = _issue_named_test_files()
    assert len(files) <= _HIGH_WATER, (
        f"{len(files)} issue-named test files under tests/, above {_HIGH_WATER}. "
        "Fold the new file into the suite that owns its contract, or rename it after that contract "
        "(development-assist-test-cleanup procedure)."
    )


def test_high_water_mark_is_tight() -> None:
    """A fold that is not reflected in the mark would let the next file in unjudged."""
    files = _issue_named_test_files()
    assert len(files) == _HIGH_WATER, f"{len(files)} issue-named test files but the mark says {_HIGH_WATER}; lower _HIGH_WATER to {len(files)}."


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("test_issue_5100_single_branch_topology.py", True),
        ("test_repro_5046.py", True),
        ("test_repro_5318_abort.py", True),
        ("test_repro_refuse_restores_all.py", False),
        ("test_issue_matrix_partition.py", False),
        ("test_rollback_5318.py", False),
        ("test_repro_5046.pyc", False),
    ],
)
def test_census_matcher(filename: str, expected: bool) -> None:
    """Non-vacuity for the matcher: issue-number prefixes count, purpose names do not."""
    assert _is_issue_named(filename) is expected
