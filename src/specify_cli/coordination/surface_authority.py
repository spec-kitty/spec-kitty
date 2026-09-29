"""The single canonical authority for commit-surface decisions (mission ``coord-commit-surface-authority``).

Home for the ONE rule every commit-bearing locus consumes — create-time topology
selection, the ``spec-commit`` / task-command shell helpers, and
``commit_router._commit_partition_group``. It lives in ``coordination/`` (NOT
``cli/``) so both the ``cli.commands.agent.*`` callers AND ``coordination.*``
(``commit_router``) can import it without a cycle: ``coordination/`` never imports
``cli/`` (the layering guard in ``tests/coordination/test_surface_authority.py``
asserts this). Every dependency the rule needs — ``MissionTopology`` /
``routes_through_coordination`` (routing), ``is_primary_artifact_kind`` (the
PRIMARY vs COORD partition), the caller-resolved ``primary_protected`` bool — sits
at or below the coordination layer (all via ``mission_runtime`` public imports,
per the shared-package boundary).

This module is **pure**: no filesystem, git, or network I/O. Callers resolve the
inputs (topology, primary target branch, its protection, the current checkout, the
artifact kind) and consume the returned :class:`SurfaceVerdict`. Freezing the rule
here — with the behaviour tests in
``tests/specify_cli/cli/commands/agent/test_tasks_surface_authority.py`` and
``tests/coordination/test_surface_authority.py`` — is what lets the
consumer refactors (WP02/WP03/WP04) align to ONE authority without drifting the
observable per-command behavior (contract ``authoritative-surface.md``; NFR-001,
INV-1..INV-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from mission_runtime import (
    MissionArtifactKind,
    MissionTopology,
    is_primary_artifact_kind,
    routes_through_coordination,
)

# ``__all__`` names only what a runtime (``src/``) caller currently imports — the
# repo's dead-symbol gate (FR-303, ``tests/architectural/test_no_dead_symbols.py``)
# requires every exported name to have a src consumer. The module's fuller public
# vocabulary (``SurfaceVerdict``/``NoOp``/``NonCommittable``/``Surface``, the
# ``REMEDY_*`` constants, ``_classify_noncommit_outcome``, ``_exit_code_for``) stays
# defined at module scope and is imported directly by the tests; it rejoins
# ``__all__`` as the remaining commit-surface loci are wired onto this authority
# (epic #2160).
__all__ = [
    "RouteToCoord",
    "Refuse",
    "coord_topology_reachable",
    "resolve_surface_authority",
]

# ---------------------------------------------------------------------------
# Shared remedy constants (Sonar S1192 — one authoritative message per remedy)
# ---------------------------------------------------------------------------

#: The remedy offered when a primary/planning-kind commit is refused on a
#: protected primary target with no coordination route (rule 3; contract §2 rule 3;
#: #2739). The task-command refuse helpers (``tasks_shared``) cite this shared
#: constant directly. ``commit_router`` and ``spec-commit`` currently emit their own
#: semantically-aligned protected-primary guidance rather than this literal string;
#: folding those two loci (and the ``implement`` refuse twin) onto this constant so a
#: single remedy vocabulary is emitted everywhere is remaining scope under epic #2160.
#: ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`` is the operator hatch that folds
#: ``primary_protected`` to ``False`` at the caller boundary (rule 6), degrading rule
#: 3 to rule 4.
REMEDY_PROTECTED_PRIMARY: Final[str] = "--start-branch <feature-branch> or SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1"

#: The remedy offered when a commit-bearing operation targets the WRONG surface
#: (the artifact is absent at / never staged to the resolved placement). A
#: wrong-surface situation is a :class:`Refuse`, never a :class:`NoOp` (contract
#: §2 rule 5) — reporting exit 0 here would falsely claim a write landed.
REMEDY_WRONG_SURFACE: Final[str] = (
    "Commit the artifact to its own resolved surface; it was not present at the resolved placement, so the commit would no-op against the wrong surface."
)


# ---------------------------------------------------------------------------
# Verdict shape (contract §2 / data-model "Authoritative surface")
# ---------------------------------------------------------------------------

Surface = Literal["primary", "coordination"]


@dataclass(frozen=True)
class RouteToCoord:
    """Coordination-kind under a coord topology with a protected primary.

    The status/coordination commit on the coord branch is authoritative; the
    redundant direct-to-protected-primary commit is **suppressed** (the protection
    policy would refuse it anyway). Exit 0 — the write landed, on coordination.
    """


@dataclass(frozen=True)
class Refuse:
    """A commit that MUST NOT proceed and MUST signal failure (exit 1).

    Covers both a primary/planning-kind on a protected primary with no coord route
    (rule 3) and a wrong-surface commit (rule 5). Carries the operator-facing
    ``remedy`` to unblock.
    """

    remedy: str


@dataclass(frozen=True)
class NoOp:
    """A genuine no-op (nothing staged / already committed). Exit 0.

    The ONLY exit-0 "nothing committed" besides :class:`RouteToCoord`. ``reason``
    is the machine-readable disambiguator (``no_op_already_committed`` /
    ``no_op_no_changes``). NEVER used for a wrong-surface situation (that is a
    :class:`Refuse`).
    """

    reason: str


#: The non-committable outcomes a verdict may carry. ``None`` means the placement
#: is directly committable (a real commit is expected to land on ``surface``).
NonCommittable = RouteToCoord | Refuse | NoOp | None


@dataclass(frozen=True)
class SurfaceVerdict:
    """The authoritative decision: WHERE an artifact-kind's commit must land, and whether it may.

    ``surface`` / ``ref`` name the destination; ``non_committable`` is ``None`` for
    a directly committable placement, else the typed outcome (:class:`RouteToCoord`
    / :class:`Refuse` / :class:`NoOp`).
    """

    surface: Surface
    ref: str
    non_committable: NonCommittable = None


# ---------------------------------------------------------------------------
# Rule 5 (create-time topology reachability) — WP-A consumer: mission_create
# ---------------------------------------------------------------------------


def coord_topology_reachable(pr_bound: bool, primary_protected: bool, current_is_primary: bool) -> bool:
    """Coordination routing is reachable iff ``pr_bound and (primary_protected or current_is_primary)``.

    The create-time predicate (contract §1): a mission mints a coordination
    topology only when coordination routing is actually reachable (INV-2 topology
    honesty) — never as pure overhead on an unprotected feature branch.

    This is a pure boolean; the caller resolves the inputs. ``primary_protected``
    is the protection of the **primary target branch**
    (``ProtectionPolicy.resolve(repo_root).is_protected(primary_target)``), NOT the
    current checkout. It is the predicate WP02 inserts into the ``pr_bound`` arm of
    ``mission_create._resolve_default_topology_phase`` (the ``None``-guard and the
    non-pr-bound ``current == primary → COORD`` arms are preserved by the caller).

    Args:
        pr_bound: Whether the mission was created ``--pr-bound``.
        primary_protected: Protection of the primary TARGET branch.
        current_is_primary: Whether the current checkout IS the primary target.

    Returns:
        ``True`` iff coordination routing is reachable.
    """
    return pr_bound and (primary_protected or current_is_primary)


# ---------------------------------------------------------------------------
# Rules 1–4 (kind-aware surface decision) — WP-B/WP-C consumers
# ---------------------------------------------------------------------------


def resolve_surface_authority(
    topology: MissionTopology,
    primary_target: str,
    primary_protected: bool,
    current_branch: str,
    artifact_kind: MissionArtifactKind,
    *,
    coord_ref: str | None = None,
) -> SurfaceVerdict:
    """Resolve the authoritative commit surface for ``artifact_kind`` (contract §2 rules 1–4).

    The single kind-aware rule that ``move-task`` (lifecycle-kind), ``map-requirements``
    (planning-kind), ``spec-commit`` and ``commit_router`` all consume. Identical
    ``{artifact_kind, topology, primary_protected}`` ⇒ identical verdict (INV-4);
    exit codes legitimately differ *by kind*, never by hardcoded per-command logic.

    Routing mirrors ``commit_router``'s ``use_coord`` exactly: a coordination
    (non-PRIMARY-partition) kind under a coord-routing topology (``COORD`` /
    ``LANES_WITH_COORD``) routes to coordination; every PRIMARY-partition kind, and
    every kind under a non-coord topology, routes to the primary target.

    Rules:
        1. Coordination-kind + coord topology + protected primary →
           ``surface="coordination"``, :class:`RouteToCoord` (exit 0; the redundant
           primary commit is suppressed, the coord commit is authoritative).
        2. Coordination-kind + coord topology + UNPROTECTED primary → coord routing
           is inert → ``surface="primary"``, committable (``non_committable=None``).
        3. Primary-kind (or any kind with no coord route) on a PROTECTED primary →
           :class:`Refuse` (exit 1) with :data:`REMEDY_PROTECTED_PRIMARY`.
        4. Primary-kind (or any kind with no coord route) on an UNPROTECTED primary →
           ``surface="primary"``, committable.

    ``NoOp`` and wrong-surface :class:`Refuse` outcomes are runtime facts (staging
    state), NOT derivable from these static inputs — map a router outcome label to
    them via :func:`_classify_noncommit_outcome`.

    Rule 6: ``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`` folds into
    ``primary_protected=False`` at the CALLER boundary (this function takes the
    already-resolved bool), degrading rule 3 to rule 4.

    Args:
        topology: The mission's stored :class:`MissionTopology`.
        primary_target: The primary target branch name (the ref a primary-kind owns).
        primary_protected: Protection of ``primary_target`` (post operator-hatch fold).
        current_branch: The current checkout (informational; the decision keys on
            target protection, not the checkout — carried for consumer parity/logging).
        artifact_kind: The kind being committed (classified PRIMARY vs COORD).
        coord_ref: The concrete coordination branch that owns the commit, when the
            caller has resolved it (``commit_router`` passes ``placement.ref``). Used
            only to name ``ref`` for a coordination verdict; falls back to
            ``primary_target`` when omitted.

    Returns:
        The :class:`SurfaceVerdict`.
    """
    del current_branch  # keyed on target protection, not the checkout (contract §1 tripwire)

    routes_coord = routes_through_coordination(topology)
    use_coord = routes_coord and not is_primary_artifact_kind(artifact_kind)

    if use_coord:
        if primary_protected:
            # Rule 1: coord commit authoritative; redundant primary commit suppressed.
            return SurfaceVerdict(
                surface="coordination",
                ref=coord_ref or primary_target,
                non_committable=RouteToCoord(),
            )
        # Rule 2: coord routing inert on an unprotected primary → commit on primary.
        return SurfaceVerdict(surface="primary", ref=primary_target)

    # Primary surface (primary-kind, or a coord-kind with no coord route).
    if primary_protected:
        # Rule 3: refuse a commit to a protected primary with no coord route.
        return SurfaceVerdict(
            surface="primary",
            ref=primary_target,
            non_committable=Refuse(remedy=REMEDY_PROTECTED_PRIMARY),
        )
    # Rule 4: unprotected primary → committable.
    return SurfaceVerdict(surface="primary", ref=primary_target)


# ---------------------------------------------------------------------------
# Rule 5 (runtime no-op vs wrong-surface classification)
# ---------------------------------------------------------------------------

# The router status literals this classifier maps (``commit_router.py`` /
# ``write_seam.py``). Named once (S1192) so the mapping stays a single source.
_STATUS_COMMITTED: Final = "committed"
_STATUS_UNCHANGED: Final = "unchanged"
_STATUS_NO_OP_WRONG_SURFACE: Final = "no_op_wrong_surface"
_STATUS_ERROR: Final = "error"
_REASON_ALREADY_COMMITTED: Final = "no_op_already_committed"
_REASON_NO_CHANGES: Final = "no_op_no_changes"
_DEFAULT_NO_OP_REASON: Final = "no_op"


def _classify_noncommit_outcome(status: str, reason: str | None = None) -> NonCommittable:
    """Map a runtime commit-router outcome label to its :class:`NonCommittable` verdict (rule 5).

    The load-bearing case (contract §2 rule 5): the router labels a wrong-surface
    situation ``no_op_wrong_surface`` — the ``no_op_`` prefix must NOT be read as an
    exit-0 no-op. This helper maps it to :class:`Refuse`, while a GENUINE no-op
    (``unchanged`` / ``no_op_already_committed`` / ``no_op_no_changes``) maps to
    :class:`NoOp`.

    Args:
        status: The router status literal (``committed`` / ``unchanged`` /
            ``no_op_wrong_surface`` / ``error``), or one of the ``unchanged``
            ``reason`` flavours passed as a status.
        reason: The router's machine-readable ``reason`` for an ``unchanged`` status.

    Returns:
        :class:`NoOp` for a genuine no-op, :class:`Refuse` for a wrong-surface, or
        ``None`` when the commit landed (``committed``).

    Raises:
        ValueError: on an unrecognized status (fail-loud; INV-3 no silent misroute).
    """
    if status == _STATUS_COMMITTED:
        return None
    if status == _STATUS_NO_OP_WRONG_SURFACE:
        # Wrong-surface → Refuse, NEVER NoOp (the write did not land where asked).
        return Refuse(remedy=REMEDY_WRONG_SURFACE)
    if status == _STATUS_UNCHANGED:
        return NoOp(reason=reason or _DEFAULT_NO_OP_REASON)
    if status in (_REASON_ALREADY_COMMITTED, _REASON_NO_CHANGES):
        return NoOp(reason=status)
    if status == _STATUS_ERROR:
        # An error is a failure, not a surface verdict — the caller handles it
        # (exit 1) separately; there is no NonCommittable surface outcome for it.
        return None
    raise ValueError(f"Unrecognized commit outcome status: {status!r}")


# ---------------------------------------------------------------------------
# Canonical exit-code mapping (one source for JSON-mode exit codes)
# ---------------------------------------------------------------------------


def _exit_code_for(verdict: NonCommittable) -> int:
    """The canonical process exit code for a :class:`NonCommittable` outcome.

    ONE mapping shared by every consumer and the golden harness (DIR-044): a
    committable placement (``None``), a genuine :class:`NoOp`, or a
    :class:`RouteToCoord` all succeed (exit 0); a :class:`Refuse` fails (exit 1).
    Mirrors the CLI's status→exit mapping (``committed`` / ``unchanged`` → 0;
    ``no_op_wrong_surface`` / ``error`` → 1).
    """
    return 1 if isinstance(verdict, Refuse) else 0
