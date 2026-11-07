"""Coordination workspace package.

Manages per-mission coordination worktrees and lane sparse-checkout policy.

Public surface:

- :class:`CoordinationWorkspace` — resolve / teardown coordination worktree
- :class:`CoordinationWorkspaceBranchMismatch` — structured error
  (``error_code = "COORDINATION_WORKTREE_BRANCH_MISMATCH"``)
- :func:`lane_sparse_checkout_patterns` — pure helper returning the pattern
  lines that lane worktrees use
  (``specify_cli.lanes.lane_checkout.exclude_lane_status_files`` applies
  them; it is the one way to do so)

The coordination worktree is the single writer of ``status.events.jsonl`` /
``status.json``. Lane worktrees use git ``sparse-checkout`` (non-cone mode)
to make those two files invisible inside the lane, eliminating any chance
that a lane process accidentally writes them.

See ``contracts/coordination_workspace.md`` and FR-024 / FR-025 / FR-029.
"""

from __future__ import annotations

from specify_cli.coordination.policy import WorkflowMutationPolicy
from specify_cli.coordination.transaction import (
    BookkeepingCommitFailed,
    BookkeepingDoubleEventId,
    BookkeepingError,
    BookkeepingLockTimeout,
    BookkeepingPolicyRefused,
    BookkeepingTransaction,
    BookkeepingWorktreeMissing,
    build_status_event,
)
from specify_cli.coordination.types import (
    Allowed,
    CommitReceipt,
    GitChangeSet,
    PendingEventHandle,
    PolicyVerdict,
    Refused,
)
from specify_cli.coordination.surface_resolver import resolve_status_surface
from specify_cli.coordination.workspace import (
    CoordinationWorkspace,
    CoordinationWorkspaceBranchMismatch,
    lane_sparse_checkout_patterns,
)

__all__ = [
    # Surface resolver (WP01 — merge-done-surface-resolver)
    "resolve_status_surface",
    # Workspace (WP04)
    "CoordinationWorkspace",
    "CoordinationWorkspaceBranchMismatch",
    "lane_sparse_checkout_patterns",
    # Policy (WP05)
    "WorkflowMutationPolicy",
    # Transaction (WP05)
    "BookkeepingTransaction",
    "BookkeepingError",
    "BookkeepingPolicyRefused",
    "BookkeepingLockTimeout",
    "BookkeepingWorktreeMissing",
    "BookkeepingCommitFailed",
    "BookkeepingDoubleEventId",
    "build_status_event",
    # Types (WP05)
    "Allowed",
    "Refused",
    "PolicyVerdict",
    "GitChangeSet",
    "PendingEventHandle",
    "CommitReceipt",
]
