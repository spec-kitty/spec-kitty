"""Always-on gate: the ``.gitignore`` contract stays intact.

Source: ``tests/specify_cli/test_gitignore_contract.py``, which lives
directly under ``tests/specify_cli`` — recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` (#4374, decide-out-of-matrix-test-dirs
ledger, lift-invariant disposition).

The source suite carries many individual historical-regression pins (dossier
snapshot rooting, worktrees root, skill projection, ops index, ...); this
lift narrows to the TWO structural invariants that make the phrase "the
gitignore contract stays intact" literally true — every drift-prone case a
future ``STATE_SURFACES`` addition could silently violate:

1. Every ``LOCAL_RUNTIME``/``IGNORED`` PROJECT-rooted state surface has a
   matching entry in the repo's own ``.gitignore``.
2. ``GitignoreManager``'s protected-entry set matches
   ``get_runtime_gitignore_entries()`` exactly (no drift between the
   generator and its consumer).

The remaining source tests are individual historical-bugfix regression pins
(one surface / one fix each), not this single contract-consistency
invariant, and are left out-of-matrix pending a future promote/deferred-
promotion decision.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_root_gitignore_contract import test_repo_gitignore_covers_local_runtime as test_repo_gitignore_covers_local_runtime
from tests.architectural._lifted_root_gitignore_contract import test_runtime_entries_match_contract as test_runtime_entries_match_contract

pytestmark = [pytest.mark.architectural]
