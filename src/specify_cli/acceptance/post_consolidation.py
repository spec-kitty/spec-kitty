"""Post-consolidation verification of ``deferred_to_consolidation`` invariants.

The acceptance gate (``gates_core.py``, the matrix's single pre-consolidation
reader) cannot judge an invariant whose subject only comes into existence once a
mission's lane branches are integrated: pre-consolidation those changes live on
lane branches, so the tree being checked cannot contain them. Such an invariant is
recorded ``deferred_to_consolidation`` (FR-003 / C4) rather than reported as a
false ``still_present``.

This module is the seam that honours that deferral **after** consolidation
(FR-004 / C6). It reads the consolidated mission tree and the acceptance matrix,
re-judges every ``deferred_to_consolidation`` invariant against that consolidated
tree, and writes the outcome back with ``verified_surface_kind = CONSOLIDATED`` and
the consolidation commit as ``verified_ref``. A deferred invariant that proves
``still_present`` fails **this op** and names the invariant (FR-005 / C7).

Design constraints (deliberate, load-bearing — see contract C7 and WP06):

* **Dispatched as a governed Op, not a merge call-in.** This runs as an ordinary
  governed Op through the canonical surface (``spec-kitty dispatch``, closed with
  ``profile-invocation complete``). It is a plain library function that returns a
  :class:`PostConsolidationResult`; the dispatched Op maps ``result.passed`` onto
  its ``done`` / ``failed`` outcome. There is **no new CLI verb** and **no call-in
  from** ``merge/executor.py``.
* **Zero ``merge/`` coupling.** Nothing here imports ``specify_cli.consolidation`` or the
  consolidation rollback machinery. The judging logic is reused wholesale from the
  matrix's own public :func:`enforce_negative_invariants`, so this module stays
  file-disjoint from the consolidation transaction (WP06 review guidance).
* **Runs AFTER consolidation; never rolls it back.** The op fails the *verification*
  when an invariant is violated — the consolidation itself has already completed
  cleanly and is left untouched (C7). No abort path is added inside the
  consolidation transaction, and no rollback is attempted. The blast radius is the
  mission/PR branch, not ``origin/main``: a violation blocks the pull request,
  which is where it should block.

Enforcement that a mission does not *reach done* with a dangling deferral is the
external CI check (FR-016 / WP18), not a guardrail in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from mission_runtime import TopologySurface

from specify_cli.acceptance.execution_context import (
    GateExecutionContext,
    LifecyclePhase,
)
from specify_cli.acceptance.matrix import (
    DEFERRED_TO_CONSOLIDATION,
    PROVENANCE_LEGACY_UNRECORDED,
    TERMINAL_INVARIANT_RESULTS,
    NegativeInvariant,
    enforce_negative_invariants,
    read_acceptance_matrix,
    write_acceptance_matrix,
)

# The re-judged results that fail the post-consolidation op (C7 / FR-005 /
# NI-5-parity): ``still_present`` is the violation the contract names, and
# ``verification_error`` means the op could not confirm absence — neither is a
# clean pass, so both close the Op as failed.
_OP_FAILING_RESULTS = frozenset({"still_present", "verification_error"})


@dataclass(frozen=True)
class InvariantViolation:
    """A deferred invariant that did not clear on the consolidated tree.

    Carries the specific invariant id (so the failed op *names* it, FR-005) and the
    re-judged ``result`` + ``evidence`` gathered from the consolidated surface.
    """

    invariant_id: str
    result: str
    evidence: str


class PostConsolidationViolation(RuntimeError):
    """Raised to fail the op when a deferred invariant is violated (C7 / FR-005).

    The message names every violated invariant. Carries a stable ``error_code`` so a
    dispatching op routes on the code rather than string-parsing the message. This
    fails **the verification op** — it never triggers a rollback of the already
    completed consolidation (C7).
    """

    error_code: str = "POST_CONSOLIDATION_INVARIANT_VIOLATED"

    def __init__(self, message: str, violations: list[InvariantViolation]) -> None:
        self.violations = violations
        super().__init__(message)


@dataclass
class PostConsolidationResult:
    """The outcome of one post-consolidation verification op.

    ``passed`` is the op's disposition: ``True`` closes the dispatched Op as
    ``done``, ``False`` as ``failed`` (naming the violated invariants). The
    consolidation is untouched either way — this is a verification result, not a
    consolidation result.
    """

    mission_slug: str
    consolidation_ref: str
    verified: list[str] = field(default_factory=list)
    violations: list[InvariantViolation] = field(default_factory=list)
    matrix_path: Path | None = None

    @property
    def passed(self) -> bool:
        """True when no deferred invariant was violated on the consolidated tree."""
        return not self.violations

    def failure_message(self) -> str:
        """A human-readable message naming every violated invariant (FR-005)."""
        if not self.violations:
            return (
                f"Post-consolidation verification passed for {self.mission_slug!r} "
                f"on the consolidated tree at {self.consolidation_ref!r}: "
                f"{len(self.verified)} deferred invariant(s) cleared."
            )
        named = "; ".join(
            f"{v.invariant_id} ({v.result}): {v.evidence}" for v in self.violations
        )
        return (
            f"Post-consolidation verification FAILED for {self.mission_slug!r} on "
            f"the consolidated tree at {self.consolidation_ref!r}: "
            f"{len(self.violations)} deferred invariant(s) violated — {named}. "
            "The completed consolidation is untouched (C7); resolve the violation on "
            "the mission branch before merging."
        )

    def raise_for_violations(self) -> None:
        """Fail the op (raise) when any deferred invariant was violated (C7).

        A no-op when the op passed. Raising :class:`PostConsolidationViolation` is
        the fail-loud path a dispatched op uses to close as ``failed``; it never
        interacts with consolidation rollback.
        """
        if self.violations:
            raise PostConsolidationViolation(self.failure_message(), self.violations)


def _post_consolidation_context(
    consolidated_tree: Path, consolidation_ref: str, mission_slug: str
) -> GateExecutionContext:
    """The gate context a deferred invariant is re-judged against (C6).

    Surface is the consolidated tree, stamped :attr:`TopologySurface.CONSOLIDATED`,
    at the consolidation commit, in :attr:`LifecyclePhase.POST_CONSOLIDATION` — so a
    freshly judged result is stamped with exactly that provenance by the matrix's own
    stamping logic.
    """
    return GateExecutionContext(
        surface=consolidated_tree,
        surface_kind=TopologySurface.CONSOLIDATED,
        ref=consolidation_ref,
        phase=LifecyclePhase.POST_CONSOLIDATION,
        mission_slug=mission_slug,
    )


def _reset_to_pending(invariant: NegativeInvariant) -> NegativeInvariant:
    """Clear a deferral back to ``pending`` so the tree can be re-judged.

    Only the scheduling fields are cleared; the *what to check* (id, method,
    command, scope) is preserved so the same subject is judged against the
    consolidated surface. The provenance stamped by the deferral is dropped — the
    re-judgement establishes fresh provenance against the consolidated surface.
    """
    return replace(
        invariant,
        result="pending",
        evidence=None,
        deferred_reason=None,
        deferred_to_phase=None,
        verified_ref=None,
        verified_surface_kind=None,
        provenance_origin=PROVENANCE_LEGACY_UNRECORDED,
    )


def _rejudge(
    consolidated_tree: Path,
    invariant: NegativeInvariant,
    context: GateExecutionContext,
) -> NegativeInvariant:
    """Re-judge one deferred invariant against the consolidated tree (C6).

    Reuses the matrix's public :func:`enforce_negative_invariants` at the
    ``POST_CONSOLIDATION`` phase, where deferral no longer applies, so the invariant
    is judged normally and the terminal result is stamped
    ``verified_surface_kind = CONSOLIDATED`` + the consolidation ref. When the
    subject remains unjudgeable (an unknown method / missing command yields
    ``pending``), the original deferral is returned unchanged rather than silently
    demoted — a later run can still resolve it.
    """
    pending = _reset_to_pending(invariant)
    judged = enforce_negative_invariants(
        consolidated_tree, [pending], context=context
    )[0]
    if judged.result not in TERMINAL_INVARIANT_RESULTS:
        return invariant
    return judged


def verify_deferred_invariants(
    consolidated_tree: Path,
    feature_dir: Path,
    *,
    consolidation_ref: str,
    mission_slug: str,
) -> PostConsolidationResult:
    """Judge every deferred invariant against the consolidated tree (C6 / C7).

    This is the module's single entry point and the body of the dispatched Op.

    Args:
        consolidated_tree: The repo-root checkout of the consolidated mission
            branch. Deferred invariants are judged against this surface and stamped
            :attr:`TopologySurface.CONSOLIDATED`.
        feature_dir: The directory holding ``acceptance-matrix.json`` on the
            consolidated tree. The matrix is read, re-judged, and written back.
        consolidation_ref: The consolidation commit sha, recorded as ``verified_ref``
            on every re-judged outcome (C6).
        mission_slug: The owning mission slug.

    Returns:
        A :class:`PostConsolidationResult`. ``passed`` is ``True`` when no deferred
        invariant was violated; ``violations`` names any that proved
        ``still_present`` / ``verification_error`` on the consolidated tree (C7).
        Terminal and ``pending`` invariants are preserved verbatim — only
        ``deferred_to_consolidation`` rows are re-judged (C3 preservation).

    The consolidation itself is never touched: on a violation the op fails
    (``passed is False`` / :meth:`PostConsolidationResult.raise_for_violations`),
    but no rollback of the completed consolidation is attempted (C7).
    """
    matrix = read_acceptance_matrix(feature_dir)
    if matrix is None:
        return PostConsolidationResult(mission_slug, consolidation_ref)

    context = _post_consolidation_context(
        consolidated_tree, consolidation_ref, mission_slug
    )
    verified: list[str] = []
    violations: list[InvariantViolation] = []
    rejudged: list[NegativeInvariant] = []
    for invariant in matrix.negative_invariants:
        if invariant.result != DEFERRED_TO_CONSOLIDATION:
            # C3 / NI-2: terminal and pending rows are preserved verbatim — the op
            # only judges what was explicitly deferred to this phase.
            rejudged.append(invariant)
            continue
        judged = _rejudge(consolidated_tree, invariant, context)
        rejudged.append(judged)
        if judged is invariant:
            # Still unjudgeable on the consolidated tree — deferral left intact.
            continue
        verified.append(judged.invariant_id)
        if judged.result in _OP_FAILING_RESULTS:
            violations.append(
                InvariantViolation(
                    invariant_id=judged.invariant_id,
                    result=judged.result,
                    evidence=judged.evidence or "",
                )
            )

    matrix.negative_invariants = rejudged
    # WP04 / T017 (write-side-seam-matrix-tracer-01KYP3MH,
    # contracts/write-seam-adoption.md) names this call site as a
    # caller-resolved-``feature_dir`` matrix writer to route through the WP03
    # seam (``write_and_commit_acceptance_matrix`` /
    # ``coordination.write_seam.write_artifact``). Deliberately NOT done: that
    # seam's ``commit_for_mission`` machinery resolves mission topology and
    # coordination worktrees relative to the INTERACTIVE primary checkout
    # (``.worktrees/`` siblings, ``meta.json``-declared ``coordination_branch``,
    # ``CoordinationWorkspace.resolve``) -- but ``consolidated_tree`` here is
    # "the repo-root checkout of the consolidated mission branch" (module
    # docstring), which in the real dispatched-Op / CI usage this module is
    # built for (see the "Zero merge/ coupling" design constraint above) is not
    # guaranteed to be that interactive checkout at all (e.g. a bare
    # CI checkout of the merged PR branch with no ``.worktrees/`` sibling).
    # Forcing this through ``commit_for_mission`` would reintroduce exactly the
    # ``merge``/consolidation-machinery coupling this module explicitly stays
    # free of. The write stays the plain raw writer; the caller (the dispatched
    # Op / CI job) commits or pushes the result as part of its own workflow,
    # matching "a plain library function that returns a PostConsolidationResult"
    # from the module docstring.
    matrix_path = write_acceptance_matrix(feature_dir, matrix)
    return PostConsolidationResult(
        mission_slug=mission_slug,
        consolidation_ref=consolidation_ref,
        verified=verified,
        violations=violations,
        matrix_path=matrix_path,
    )


__all__ = [
    "InvariantViolation",
    "PostConsolidationResult",
    "PostConsolidationViolation",
    "verify_deferred_invariants",
]
