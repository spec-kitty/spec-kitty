"""NFR-004: the multi-log writes gate scans the full ``src/`` tree in under 5 s (#6603).

``pytestmark = pytest.mark.timing`` and nothing else, the house convention for a
wall-clock assertion: it runs only in ``make test-full``'s serial ``-m timing -n0``
pass, never in the parallel architectural battery, where a timed assertion flakes.
The parse is the shared ``src_source_tree`` fixture every architectural gate uses,
so only the gate's own scan is timed.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.architectural.conftest import SourceFile
from tests.architectural.test_event_log_writes_gate import scan_src_tree

pytestmark = pytest.mark.timing

#: NFR-004's budget, in seconds.
_BUDGET_S = 5.0


def test_the_scan_meets_its_time_budget(src_source_tree: Mapping[Path, SourceFile]) -> None:
    started = time.perf_counter()
    scan = scan_src_tree(src_source_tree)
    elapsed = time.perf_counter() - started
    assert scan.door_calls, "the scan found no door caller; the budget would be vacuous"
    assert elapsed < _BUDGET_S, f"the event-log writes gate scan took {elapsed:.2f} s (budget {_BUDGET_S} s)"
