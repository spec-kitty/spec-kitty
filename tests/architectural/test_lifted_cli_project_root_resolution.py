"""Always-on gate: ``get_project_root_or_exit`` resolves worktrees and fails closed on git errors.

Source: ``tests/specify_cli/cli/test_helpers.py`` (T007, #4123), which lives
under ``tests/specify_cli/cli`` — recorded ``out_of_matrix`` in
``.github/ci-module-registry.yml`` (#4374, decide-out-of-matrix-test-dirs
ledger, lift-invariant disposition; PC1 nested-family bulk-lift).

Ledger assertion shape: "Fixture worktree + a git-unavailable fixture;
assert message/exit/JSON shape." Lifts the worktree-resolution invariant plus
one representative message/exit/JSON assertion per rendering path (human
exit-1 render, machine JSON envelope) rather than the source suite's full
message-content permutations.
"""

from __future__ import annotations

import pytest

# The tests live once, in the shared home this gate and its source import
# (#5015); importing them is what makes pytest collect them in this module.
from tests.architectural._lifted_cli_project_root_resolution import (
    test_get_project_root_or_exit_succeeds_in_worktree as test_get_project_root_or_exit_succeeds_in_worktree,
)
from tests.architectural._lifted_cli_project_root_resolution import test_exit_git_resolution_failure_exits_1 as test_exit_git_resolution_failure_exits_1
from tests.architectural._lifted_cli_project_root_resolution import test_exit_git_resolution_failure_json_envelope as test_exit_git_resolution_failure_json_envelope

pytestmark = [pytest.mark.architectural]
