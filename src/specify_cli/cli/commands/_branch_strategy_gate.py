"""Branch-strategy gate for PR-bound missions (FR-033, WP07/T040).

When a mission is declared PR-bound (``meta.json`` carries ``pr_bound:
true``) and the operator invokes ``mission create`` while the cwd is
already on the mission's ``merge_target_branch``, we must not silently
let the mission start on the merge target. Instead we prompt the
operator to confirm or to switch to a topic branch.

The prompt is suppressed entirely when the operator passes
``--branch-strategy already-confirmed``. Non-PR-bound missions and
missions on a topic branch hit the no-op path so the legacy flow is
preserved verbatim.

The gate is intentionally side-effect-free apart from emitting the
prompt: it returns a :class:`GateOutcome` describing what should happen
next (proceed / abort) and the resolved
``branch_strategy`` decision. The caller decides how to honour that
outcome (typer.Exit on abort, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

__all__ = [
    "ALREADY_CONFIRMED",
    "BranchStrategyGateError",
    "GateDecision",
    "GateOutcome",
    "evaluate_branch_strategy",
]

ALREADY_CONFIRMED = "already-confirmed"


class BranchStrategyGateError(Exception):
    """Raised when the gate refuses to let the operator proceed."""


@dataclass(frozen=True)
class GateDecision:
    """The operator-facing answer to the prompt."""

    proceed: bool
    reason: str


@dataclass(frozen=True)
class GateOutcome:
    """Result of evaluating the branch-strategy gate.

    Attributes:
        prompted: Whether the gate actually prompted the operator. False
            when the gate was a no-op (non-PR-bound mission, feature
            branch, or ``--branch-strategy already-confirmed``).
        decision: The :class:`GateDecision` produced by the prompt or by
            an implicit auto-proceed (no prompt fired).
    """

    prompted: bool
    decision: GateDecision


def evaluate_branch_strategy(
    *,
    pr_bound: bool,
    current_branch: Optional[str],
    merge_target_branch: Optional[str],
    branch_strategy: Optional[str] = None,
    prompt: Callable[[str], bool] | None = None,
) -> GateOutcome:
    """Decide whether mission creation may proceed given the branch context.

    Args:
        pr_bound: ``meta.json``'s ``pr_bound`` value (default false).
        current_branch: The branch the operator is currently on. ``None``
            for detached HEAD or when the gate cannot determine it; the
            gate treats that as "not on the merge target" and is a no-op.
        merge_target_branch: The branch into which completed work must
            land. When ``None`` or empty the gate is a no-op.
        branch_strategy: Optional value of ``--branch-strategy``. The
            sentinel :data:`ALREADY_CONFIRMED` suppresses the prompt and
            auto-proceeds (FR-033 escape hatch for scripted runs).
        prompt: Callable used to ask the operator. Returns ``True`` to
            proceed, ``False`` to abort. Required when the gate fires;
            ignored when the gate is a no-op. Tests inject a stub.

    Returns:
        :class:`GateOutcome` describing what the caller should do.

    Raises:
        BranchStrategyGateError: When the gate must fire but no prompt
            callable was supplied (programmer error).
    """
    auto_decision = GateDecision(proceed=True, reason="gate-not-applicable")

    # Gate only fires for PR-bound missions; non-PR-bound is the legacy flow.
    if not pr_bound:
        return GateOutcome(prompted=False, decision=auto_decision)

    if not merge_target_branch or not current_branch:
        return GateOutcome(prompted=False, decision=auto_decision)

    if current_branch != merge_target_branch:
        return GateOutcome(prompted=False, decision=auto_decision)

    # On the merge target with a PR-bound mission. Honour the suppression flag.
    if branch_strategy == ALREADY_CONFIRMED:
        return GateOutcome(
            prompted=False,
            decision=GateDecision(proceed=True, reason="already-confirmed"),
        )

    if prompt is None:
        raise BranchStrategyGateError(
            "Branch-strategy gate must prompt but no prompt callable was supplied. "
            "Pass `--branch-strategy already-confirmed` to bypass."
        )

    message = (
        f"You are on '{current_branch}', which is the mission's merge target. "
        "PR-bound missions usually live on a topic branch. Proceed anyway?"
    )
    answer = prompt(message)
    decision_reason = "operator-confirmed" if answer else "operator-aborted"
    return GateOutcome(
        prompted=True,
        decision=GateDecision(proceed=bool(answer), reason=decision_reason),
    )
