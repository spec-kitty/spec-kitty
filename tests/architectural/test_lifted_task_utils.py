"""Always-on gate: ``set_scalar``'s append-on-miss retirement stays fail-closed.

Lifted from ``tests/task_utils/test_set_scalar_retired.py`` (FR-006, WP08,
mission upgrade-atomicity-recovery), a ``tests/task_utils`` tree recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` — no per-PR lane
selects it (#4374 disposition ledger, disposition 2 — lift-invariant).

``set_scalar`` still updates an existing scalar key (the symbol is retained
for re-exports), but must refuse — never silently append an inline
``key: value`` line — when the key is absent. This is the guard that closes
the #3372 dual-``review_feedback``-key regression: no code path may
reintroduce an inline-appended frontmatter key via this writer.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_task_utils import test_set_scalar_updates_existing_key as test_set_scalar_updates_existing_key
from tests.architectural._lifted_task_utils import test_set_scalar_refuses_append_on_miss as test_set_scalar_refuses_append_on_miss
from tests.architectural._lifted_task_utils import (
    test_set_scalar_never_appends_inline_review_feedback_key as test_set_scalar_never_appends_inline_review_feedback_key,
)

pytestmark = [pytest.mark.architectural]
