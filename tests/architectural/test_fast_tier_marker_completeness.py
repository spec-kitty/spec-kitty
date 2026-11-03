"""Every test under a FAST_TIER_DIRS root carries an explicit tier marker.

``make test-fast`` selects ``FAST_TIER_DIRS`` by the Makefile's
``FAST_TIER_MARKERS`` -- ``(fast or unit) and not slow and not e2e and ...`` --
a positive selection on ``{fast, unit}``. A test placed under one of those
roots with NONE of the vocabulary markers that expression names is silently
deselected: it never runs in the fast-tier baseline, and nothing says so
(controller-qa audit of PR #15; spec-kitty#21 -- at audit time 257 of 456
deselected tests in those dirs were unmarked). This guard makes the invariant
"a new fast-tier test runs in ``make test-fast`` without anyone remembering a
marker" hold by construction: it fails loudly, at architectural-gate time,
the moment such a test is collected.
"""

from __future__ import annotations

import pytest

from tests.architectural import _fast_tier_gate as ftg
from tests.architectural import _gate_coverage as gc
from tests.architectural.test_same_tier_uniqueness import _UNIVERSE_TIMEOUT_S

pytestmark = pytest.mark.architectural


@pytest.fixture(scope="module")
def universe() -> list[gc.TestRecord]:
    return gc.collect_universe()


# #7052: the module-scoped ``universe`` fixture may run the real collection inside its own
# setup when the store is bypassed (dirty checkout, unsupported platform, no record), so the
# test below must not inherit the suite's 240 s runaway-hang backstop. The budget is the
# sibling consumer's derived one (the collector's ceiling plus its allowance), so pytest-timeout
# can never under-cut the collector; the guard in the sibling module scans this file through the
# pinned consumer registry and fails if this marker is dropped.
_COLLECTS_UNIVERSE = pytest.mark.timeout(_UNIVERSE_TIMEOUT_S)


@_COLLECTS_UNIVERSE
def test_every_fast_tier_dir_test_carries_a_vocabulary_marker(
    universe: list[gc.TestRecord],
) -> None:
    roots = ftg.fast_tier_dirs()
    vocabulary = ftg.fast_tier_marker_vocabulary()
    records = [record for record in universe if any(record["relpath"] == root or record["relpath"].startswith(f"{root}/") for root in roots)]
    assert records, f"FAST_TIER_DIRS roots {roots!r} collect no tests"

    unmarked = sorted(record["nodeid"] for record in records if not (set(record["markers"]) & vocabulary))
    assert not unmarked, (
        "tests under FAST_TIER_DIRS must carry an explicit tier marker "
        f"({sorted(vocabulary)}) or `make test-fast` silently drops them "
        f"(spec-kitty#21): {unmarked[:20]}"
    )
