"""Coordination-transaction value types (WP05).

These dataclasses are the small, frozen, side-effect-free types used by
:mod:`specify_cli.coordination.policy` and
:mod:`specify_cli.coordination.transaction`. Keeping them in a separate
module avoids any cycle between the policy gate and the transaction
service (the transaction depends on the policy, both depend on these
types).

See contracts:
- ``contracts/bookkeeping_transaction.md``
- ``contracts/workflow_mutation_policy.md``

Spec source: FR-019, FR-020, FR-021, FR-026, FR-033, C-013, C-016.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kernel.clock import datetime
from specify_cli.core.commit_guard import GuardCapability


@dataclass(frozen=True, kw_only=True)
class GitChangeSet:
    """The minimal description of a would-be commit.

    Inputs to :class:`~specify_cli.coordination.policy.WorkflowMutationPolicy`.

    ``destination_ref`` MUST be the SHORT branch name (C-016). Callers
    that hand in ``refs/heads/...`` are routed to a ``Refused`` verdict
    with stable error code ``DESTINATION_REF_INVALID_SHAPE`` so the
    pre-flight gate stays simple and side-effect free.

    Attributes:
        destination_ref: Short branch name (e.g. ``"kitty/mission-foo-01ABCDEF"``).
        repo_root: Path to the primary git repository.
        worktree_root: Path to the worktree the commit would land in.
        paths: Paths the would-be commit would touch (diagnostic only;
            the policy gate does not inspect them).
        message: The would-be commit message (diagnostic only).
        operation: A short diagnostic label naming the caller's intent
            (e.g. ``"emit_status_transition"``).
        capability: Asserted-at-the-surface authorization (FR-008). Defaults to
            ``GuardCapability.STANDARD`` because the coordination bookkeeping
            commit lands on the per-mission coordination branch (or, in legacy
            mode, the lane branch) — neither is protected, so the
            placement-matched STANDARD commit is correct and a protected
            destination (e.g. ``main``) is refused. Test fixtures that
            deliberately land bookkeeping on a protected branch pass
            ``GuardCapability.TEST_MODE``. The protected-branch decision in the
            policy gate is delegated to ``commit_guard.evaluate`` over this
            capability — never derived from message text, file content, or env.
        mission_slug: The mission this write belongs to, when it is a
            mission-scoped write. Lets the protection decision honour that
            mission's persisted ``commit_to_target`` (#5100 FR-008) for its own
            target branch only; ``None`` for non-mission commits.
    """

    destination_ref: str
    repo_root: Path
    worktree_root: Path
    paths: tuple[Path, ...]
    message: str
    operation: str
    capability: GuardCapability = field(default=GuardCapability.STANDARD)
    mission_slug: str | None = None


@dataclass(frozen=True)
class Allowed:
    """The policy permits the would-be commit. No side effects required."""

    pass


# ---------------------------------------------------------------------------
# Stable ``Refused.error_code`` constants (NFR-007)
#
# These values are the machine-readable codes emitted by WorkflowMutationPolicy
# and matched by callers. Declare here so every comparison site imports the
# constant rather than embedding inline literals.  The string VALUES are part
# of the public API contract and MUST NOT change.
# ---------------------------------------------------------------------------

#: Destination ref exists but is on the project's protected-branch list.
PROTECTED_BRANCH_REFUSED = "PROTECTED_BRANCH_REFUSED"

#: Destination ref does not exist locally.
DESTINATION_REF_NOT_FOUND = "DESTINATION_REF_NOT_FOUND"


@dataclass(frozen=True, kw_only=True)
class Refused:
    """The policy refused the would-be commit.

    ``error_code`` is stable across releases for scripted detection
    (NFR-007). See ``contracts/workflow_mutation_policy.md`` for the
    canonical list of codes.

    Attributes:
        error_code: Stable, machine-readable code (e.g.
            ``PROTECTED_BRANCH_REFUSED``).
        message: Operator-facing description of what was rejected and
            why. Names the rejected commit's intent and the destination ref.
        destination_ref: The destination ref that was rejected.
        next_step: A short, concrete recovery instruction.
    """

    error_code: str
    message: str
    destination_ref: str
    next_step: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation (FR-014)."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "destination_ref": self.destination_ref,
            "next_step": self.next_step,
        }


# Discriminated-union alias. Python's structural type system has no
# native sum type, so we use a typing.Union and route on isinstance.
PolicyVerdict = Allowed | Refused


@dataclass(frozen=True, kw_only=True)
class PendingEventHandle:
    """The receipt returned by ``BookkeepingTransaction.append_event``.

    Carries ONLY the new event_id. The commit SHA does not exist yet
    when this is returned (FR-033 cross-review correction).

    Attributes:
        event_id: The ULID assigned to the appended status event.
    """

    event_id: str


@dataclass(frozen=True, kw_only=True)
class CommitReceipt:
    """The receipt returned by ``BookkeepingTransaction.commit``.

    Returned only after ``safe_commit()`` succeeds.

    Attributes:
        commit_sha: The new commit SHA on the coordination branch.
        committed_at: UTC timestamp at which the commit landed.
        destination_ref: The short branch name the commit landed on.
        worktree_root: The worktree the commit was made from.
        event_ids: The ULIDs of every status event appended in this
            transaction, in order of appending.
    """

    commit_sha: str
    committed_at: datetime
    destination_ref: str
    worktree_root: Path
    event_ids: tuple[str, ...]
    #: WP04/T015 (FR-004, #2861): ``True`` when this receipt is the idempotent
    #: no-op of :meth:`BookkeepingTransaction.commit_idempotent` — the staged
    #: paths already matched HEAD, so THIS transaction created no new commit and
    #: ``commit_sha`` merely pins the pre-existing HEAD (the commit a prior
    #: transaction created). A rollback of "this transaction's commit" must skip
    #: a no-op receipt: there is nothing this transaction added to revert.
    is_noop: bool = False
