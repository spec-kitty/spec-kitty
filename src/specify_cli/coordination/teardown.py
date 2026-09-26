"""Shared coordination-topology teardown seam (FR-004 / FR-005, #2119).

The single place the **persist-before-destroy** invariant lives. Three
production call sites previously each open-coded a
``CoordinationWorkspace.teardown(...)`` inside a best-effort
``except Exception`` swallow:

* merge cleanup  — ``cli/commands/merge.py`` (``_run_lane_based_merge_locked``)
* merge ``--abort`` — ``cli/commands/merge.py`` (the ``--abort`` branch)
* mission close / ``--discard`` — ``cli/commands/mission_type.py``
  (``_teardown_coordination_worktree``)

That duplication is exactly why the ordering bug existed in one path (merge:
the coordination worktree was destroyed inside ``_run_lane_based_merge_locked``
*before* ``run_retrospective_postcondition`` fired in the outer ``merge()``) and
was absent in another (close/abort: no persist step at all). Consolidating the
three sites onto this one seam makes the invariant attachable once and provable
by destroy-step fault injection.

Ordering reconciliation (DIR-003 / ADR Binding B)
-------------------------------------------------
ADR Binding B states **persist → flatten → destroy**. This base does NOT carry
a separate ``_flatten_discarded_mission`` / ``_verify_discard_complete`` discard
sub-pipeline (that topology — and the ``merge/executor.py`` split the WP prompt
referenced — does not exist here; the merge cleanup lives in
``cli/commands/merge.py`` and the discard path's branch/lane-worktree deletion
lives in ``mission_type._discard_mission``). On THIS base both the merge path
and the discard path reduce to **persist → destroy**:

* **merge path**: ``persist → destroy`` (this seam persists the retrospective to
  its durable PRIMARY home, then destroys the coordination worktree).
* **discard path**: the close command keeps its existing branch + lane-worktree
  deletion (``_discard_mission``) ahead of this seam; the seam itself is invoked
  for the coordination-worktree leg and runs ``persist → destroy``. No flatten
  step exists to reorder, so verify-before-flatten is vacuously preserved.

The shipped seam therefore matches ADR Binding B's load-bearing invariant
(persist precedes destroy) for both paths on this base. The "flatten" middle
term in Binding B's wording has no anchor in this tree; if a future base
re-introduces a flatten sub-pipeline, the seam — not the call sites — is where
the persist→flatten→destroy ordering must be reasserted.

Acyclic-import discipline (alphonso)
------------------------------------
The retrospective-persist import is **function-local / lazy** (mirroring the
convention at ``retrospective/gate.py``), so importing ``coordination`` never
drags in ``retrospective`` at module-import time. The seam symbol is
deliberately **NOT** added to ``coordination/__init__.__all__`` — it is reachable
only via this module path, keeping ``coordination/__init__`` free of the
retrospective dependency and the ``coordination → retrospective`` import edge out
of the package's public surface.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specify_cli.retrospective.schema import ProvenanceKind

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProjectionTeardownGate:
    """S-B / FR-004 precondition the teardown must honor before destroying anything.

    Built by the merge integration hook (WP09) from the WP06 reconciliation seam:

    * ``coord_ref`` — the coordination ref whose tip is compare-and-swapped.
    * ``expected_coord_sha`` — the coord tip observed while the projection captured
      its ``checkpoint..tip`` window (``ProjectionResult.coord_tip_sha``). Teardown
      re-reads the ref and refuses unless it is still exactly this value, so a
      concurrent status-emit / verdict that landed AFTER projection (and was
      therefore never projected) can never be silently destroyed (#4981).
    * ``reachability_ok`` — whether the WP06 ``MergeOutcomeVerifier`` PASSed (every
      approved WP commit reachable from the target, no excluded commit reachable).
    * ``projected_commits`` — the projected window's SHAs, carried for diagnostics.
    """

    coord_ref: str
    expected_coord_sha: str
    reachability_ok: bool
    projected_commits: tuple[str, ...] = ()


class ProjectionTeardownAbort(RuntimeError):
    """Fail-closed refusal: the projection + CAS precondition for teardown did not hold.

    Raised BEFORE persist and BEFORE any destroy, so nothing is torn down — the
    coordination branch, marker, and worktree survive as one coupled triple
    (CLAUDE.md merge-retention invariant). Propagates as a non-zero terminus exit.
    """

    error_code = "PROJECTION_TEARDOWN_ABORTED"

    def __init__(
        self,
        *,
        reason: str,
        coord_ref: str,
        expected_sha: str,
        actual_sha: str | None = None,
    ) -> None:
        self.reason = reason
        self.coord_ref = coord_ref
        self.expected_sha = expected_sha
        self.actual_sha = actual_sha
        moved = f" (expected {expected_sha[:12]}, found {actual_sha[:12]})" if actual_sha is not None else ""
        super().__init__(
            f"Refusing coordination teardown for {coord_ref!r}: {reason}{moved}. "
            "Nothing was torn down and no refs/worktrees were mutated. Resolve the "
            "coordination-surface issue, then re-run the merge (`spec-kitty merge "
            "--resume`)."
        )


def _current_coord_ref_sha(repo_root: Path, coord_ref: str) -> str:
    """Resolve ``coord_ref``'s current tip SHA (``""`` when it does not resolve).

    The git read is function-local so importing ``coordination`` never drags the
    git-ops module in at module-import time (module docstring: acyclic discipline).
    """
    from specify_cli.core.git_ops import run_command  # noqa: PLC0415

    ret, out, _err = run_command(
        ["git", "rev-parse", coord_ref],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return out.strip() if ret == 0 and out.strip() else ""


def _enforce_projection_teardown_gate(repo_root: Path, gate: ProjectionTeardownGate) -> None:
    """Refuse teardown unless reachability passed AND the coord tip is unchanged (CAS).

    Fail-closed: any failing leg raises :class:`ProjectionTeardownAbort` before
    persist/destroy, so a moved coord tip or an unprojected/unreachable outcome
    never tears down the coupled triple partially (T034).
    """
    if not gate.reachability_ok:
        raise ProjectionTeardownAbort(
            reason="the reconciliation reachability check did not pass",
            coord_ref=gate.coord_ref,
            expected_sha=gate.expected_coord_sha,
        )
    current = _current_coord_ref_sha(repo_root, gate.coord_ref)
    if current != gate.expected_coord_sha:
        raise ProjectionTeardownAbort(
            reason="the coordination tip moved since projection captured its window "
            "(compare-and-swap failed); a concurrent commit may not have been "
            "projected onto the target",
            coord_ref=gate.coord_ref,
            expected_sha=gate.expected_coord_sha,
            actual_sha=current,
        )


def _persist_retrospective(
    repo_root: Path,
    mission_slug: str,
    provenance_kind: ProvenanceKind = "runtime_post_completion",
) -> None:
    """Persist any pending retrospective to its durable PRIMARY home.

    Routes through the post-merge terminus, which resolves the durable home via
    the WP03 ``resolve_retrospective_home`` authority and writes
    ``kitty-specs/<slug>/retrospective.yaml`` (idempotent: a no-op when the
    record already exists). The import is function-local to keep ``coordination``
    acyclic (see module docstring).

    This runs OUTSIDE the destroy best-effort swallow: the retrospective MUST be
    durable before the coordination worktree is destroyed. ``run_retrospective_
    postcondition`` is itself fail-open for *capture* failures (it records a
    ``capture_failed`` event rather than aborting), so the persist step does not
    block teardown on a genuine generator/IO failure — but an unexpected error in
    the persist machinery surfaces here instead of being masked by the destroy
    handler.
    """
    from specify_cli.post_merge.retrospective_terminus import (  # noqa: PLC0415
        run_retrospective_postcondition,
    )

    run_retrospective_postcondition(
        mission_slug=mission_slug,
        repo_root=repo_root,
        provenance_kind=provenance_kind,
    )


def _destroy_coordination_worktree(
    repo_root: Path, mission_slug: str, mid8: str
) -> bool:
    """Destroy the coordination worktree (best-effort). Returns ``True`` on success.

    Wraps ``CoordinationWorkspace.teardown`` in the best-effort ``except
    Exception`` swallow that the three former call sites each carried: a teardown
    failure is non-fatal and never blocks a successful merge / close / abort. The
    import is function-local for symmetry with the persist leg.
    """
    try:
        from specify_cli.coordination.workspace import (  # noqa: PLC0415
            CoordinationWorkspace,
        )

        CoordinationWorkspace.teardown(repo_root, mission_slug, mid8)
        return True
    except Exception as exc:  # noqa: BLE001 — destroy is best-effort cleanup
        logger.warning(
            "Coordination worktree teardown failed (non-fatal) for %s-%s: %s",
            mission_slug,
            mid8,
            exc,
        )
        return False


def teardown_coordination_topology(
    repo_root: Path,
    mission_slug: str,
    mid8: str,
    *,
    persist: bool = True,
    provenance_kind: ProvenanceKind = "runtime_post_completion",
    projection_gate: ProjectionTeardownGate | None = None,
) -> bool:
    """Persist the retrospective, then destroy the coordination worktree.

    The single shared teardown seam (FR-004). Ordered steps:

    0. **gate** (``projection_gate`` supplied, S-B / FR-004 / T034) — refuse
       fail-closed unless the reconciliation reachability check passed AND the
       coordination tip is unchanged since the projection captured its window
       (compare-and-swap). This runs BEFORE persist so an aborted gate tears down
       NOTHING — the coord branch/marker/worktree survive as one coupled triple
       (#4981/#4970/#4973). Omitted (``None``) ⇒ the pre-existing behavior, so the
       mission-close / ``--abort`` / not-yet-wired merge call sites are unchanged.
    1. **persist** (``persist=True``, OUTSIDE the swallow) — write any pending
       retrospective to its durable PRIMARY home
       (``kitty-specs/<slug>/retrospective.yaml``) via the WP03 authority, so the
       learning record survives the worktree destruction (FR-005).
    2. **destroy** (best-effort, swallowed) — remove the coordination worktree;
       its failure is non-fatal.

    Args:
        repo_root: Primary repo root (NOT a lane / coordination worktree).
        mission_slug: Canonical mission directory name (already re-keyed by the
            caller to ``feature_dir.name`` — the seam composes no handles).
        mid8: The mid8 disambiguator from ``meta.json``. An empty value means the
            mission never had a coordination worktree (legacy); the destroy leg is
            then a documented no-op and persist still runs.
        persist: When ``False``, skip the persist leg (e.g. callers that have
            already persisted, or paths with no retrospective semantics).
        provenance_kind: Provenance to stamp on a freshly captured retrospective
            (#3716). The ``mission close --discard`` leg passes
            ``"runtime_abandoned"`` so an abandoned mission is not tagged with
            completion provenance; the default (``runtime_post_completion``)
            preserves the merge/close-completion behaviour.
        projection_gate: When supplied, the S-B projection + coord-ref CAS
            precondition (:class:`ProjectionTeardownGate`) is enforced before any
            persist/destroy; a failing gate raises :class:`ProjectionTeardownAbort`
            and mutates nothing. ``None`` (the default) preserves the ungated
            behavior for callers that do not run the reconciliation seam.

    Returns:
        ``True`` when the destroy leg succeeded (or no-op'd cleanly), ``False``
        when destroy raised and was swallowed.

    Raises:
        ProjectionTeardownAbort: ``projection_gate`` was supplied and its
            reachability or compare-and-swap precondition failed; nothing was
            mutated (fail-closed, non-zero terminus exit).

    Note:
        Persist is intentionally NOT wrapped in the destroy swallow: an
        unexpected persist-machinery error surfaces to the caller rather than
        being silently absorbed as "teardown was best-effort".
    """
    if projection_gate is not None:
        # Fail-closed BEFORE persist/destroy — an aborted gate mutates nothing.
        _enforce_projection_teardown_gate(repo_root, projection_gate)

    if persist:
        # OUTSIDE the destroy swallow — persist-before-destroy (FR-005).
        _persist_retrospective(repo_root, mission_slug, provenance_kind)

    if not mid8:
        # Legacy / never-coordinated mission: nothing to destroy. Persist (above)
        # still ran. Mirror CoordinationWorkspace.teardown's idempotent no-op.
        return True

    return _destroy_coordination_worktree(repo_root, mission_slug, mid8)
