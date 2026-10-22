"""Always-on round-trip gate: ``scripts/lint_canonical_producers.py`` stays wired.

Lifted from ``tests/lint/test_canonical_producers.py`` (mission
canonical-producer-lint-01KS4XX4), a ``tests/lint`` tree recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` — no per-PR lane
selects it (#4374 disposition ledger, disposition 2 — lift-invariant).

The source suite is a broad, ~34-test unit suite covering every CP00x
finding code and CLI exit path — genuinely more than one enumerable
invariant, so it is NOT lifted wholesale here (per the WP02 Definition of
Done: "a lift is ONE invariant"; the full edge-case matrix stays
make-test-full-only pending a future promotion decision). What IS lifted is
the single round-trip invariant the tree's disposition depends on: the lint
script still distinguishes canonical construction (zero findings) from the
classic hand-rolled event-dict violation (CP001) — i.e. the linter has not
silently gone inert.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_lint import _lint_module as _lint_module
from tests.architectural._lifted_lint import test_lint_clean_canonical_construction_zero_findings as test_lint_clean_canonical_construction_zero_findings
from tests.architectural._lifted_lint import test_lint_hand_rolled_event_dict_fires_cp001 as test_lint_hand_rolled_event_dict_fires_cp001

pytestmark = [pytest.mark.architectural]
