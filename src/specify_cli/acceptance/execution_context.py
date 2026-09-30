"""The value a gate is *handed* — surface, ref, phase — and cannot derive.

This module introduces the :class:`GateExecutionContext` value object (the
``(surface, ref, phase)`` bundle a gate judges from), the ordered
:class:`LifecyclePhase` enum, and the distinguishable *cannot-evaluate* outcome.
Together they convert #1834 from a per-site fix into a **property of every gate**:
a gate judges the surface it is handed, names that surface on its verdict, and
refuses — rather than passing or failing — when the surface cannot hold the fact.

Design (data-model.md ``GateExecutionContext`` GEC-1..GEC-5, ``LifecyclePhase``
PH-1; contract ``gate-execution-context.md`` C1..C7):

* **GEC-1 — Not derivable.** A gate *receives* a :class:`GateExecutionContext`; it
  may not construct one from ``repo_root`` / ``os.getcwd()`` / a bare dir. The ONE
  construction door is :func:`build_gate_execution_context`, which resolves the
  surface through the WP02 seam (:func:`mission_runtime.resolve_artifact_surface`)
  rather than any ambient location.
* **GEC-2 / C5 — Ref agreement.** :meth:`GateExecutionContext.assert_at_ref`
  verifies the surface is actually at :attr:`GateExecutionContext.ref` before a
  gate judges it, and raises :class:`GateSurfaceRefMismatch` otherwise (mirroring
  the ``safe_commit`` HEAD-vs-destination assert). It is an explicit, injectable
  gate step — construction stays pure, so a gate that runs against a non-checkout
  surface is never forced through a HEAD read it does not need.
* **GEC-3 / C3 — Total resolution.** The four ``CoordState`` answers are supplied by
  the consumed WP02 resolver: ``DELETED`` raises ``CoordinationBranchDeleted``;
  ``UNMATERIALIZED`` raises ``CoordinationWorktreeUnmaterialized`` (#4959);
  ``EMPTY`` resolves primary and **stamps** ``PRIMARY``;
  ``MATERIALIZED`` resolves coord. This module never re-derives that classifier.
* **GEC-5 / C2 — A stamp is not permission.** :meth:`GateExecutionContext.surface_cannot_hold`
  refuses (cannot-evaluate) when a kind whose declared home is ``COORD`` is judged
  against a surface stamped ``PRIMARY`` — the create-window substitution — so the
  #2885 "empty surface → pass by default" failure is reported honestly.
* **PH-1 — Phase floor.** :meth:`GateExecutionContext.not_applicable_below` returns
  the cannot-evaluate outcome (never a pass/fail) when the context's phase is below
  the gate's declared minimum.

Topology neutrality (GEC-4 / C-004 / C7): no field, name, or branch of
:class:`GateExecutionContext` is conditioned on coordination topology, and nothing
here reads the ``flattened`` flag. :func:`declared_home_surface` consults the ONE
canonical partition + :func:`mission_runtime.routes_through_coordination` predicate
over the *stored* topology — the same authority the resolver itself uses — to answer
"where does this kind authoritatively live", which is a per-kind home fact, not a
coord-topology branch.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mission_runtime import (
    MissionArtifactKind,
    MissionResolver,
    OwnedCheckout,
    TopologySurface,
    declared_read_surface,
    resolve_artifact_surface,
)


class LifecyclePhase(enum.IntEnum):
    """Where in the mission lifecycle a judgement happens (data-model PH-1).

    Ordered ``REVIEW < ACCEPT < POST_CONSOLIDATION``: a gate declares the minimum
    phase at which its subject *can* exist, and a gate invoked below that floor
    returns :class:`CannotEvaluate` (PH-1) rather than a pass or a fail. Ordering
    is the load-bearing property, so this is an :class:`enum.IntEnum` — comparisons
    (``phase < minimum``) are the contract, not an incidental convenience.

    ``IMPLEMENT`` is intentionally **not** a member: IC-01's finding (WP01
    tracers/design-decisions.md, #2795) placed the implement-phase fix on the
    consolidation side, so no gate declares an IMPLEMENT floor and adding the
    member would be a phantom (data-model, deferred-to-IC-01 note).
    """

    REVIEW = 1
    ACCEPT = 2
    POST_CONSOLIDATION = 3


class CannotEvaluateReason(enum.StrEnum):
    """The named reason a gate returns *cannot-evaluate* (contract C2).

    A distinguishable reason is what separates this outcome from a pass or a fail:
    the caller routes on the reason, never on string-parsing a diagnostic.
    """

    BELOW_MINIMUM_PHASE = "NOT_APPLICABLE_IN_PHASE"
    SURFACE_CANNOT_HOLD_FACT = "SURFACE_CANNOT_HOLD_FACT"


@dataclass(frozen=True)
class CannotEvaluate:
    """The distinguishable cannot-evaluate outcome (contract C2 / GEC-5 / PH-1).

    It is neither a pass nor a fail. It **names the reason** (:attr:`reason`) and,
    per C6/NFR-003, the surface + ref the refusal was reached against, so a
    recorded judgement is always attributable to a resolvable surface.
    """

    reason: CannotEvaluateReason
    detail: str
    surface_kind: TopologySurface
    ref: str


class GateSurfaceRefMismatch(RuntimeError):
    """Raised when a gate's surface is not at the expected ``ref`` (GEC-2 / C5).

    The gate refuses to judge a surface that has drifted from the reference point
    it was expected to be at, mirroring the ``safe_commit`` HEAD-vs-destination
    assert. Carries a stable ``error_code`` so callers route without string
    parsing.
    """

    error_code: str = "GATE_SURFACE_REF_MISMATCH"

    def __init__(
        self,
        *,
        surface_kind: TopologySurface,
        expected_ref: str,
        actual_ref: str,
    ) -> None:
        self.surface_kind = surface_kind
        self.expected_ref = expected_ref
        self.actual_ref = actual_ref
        super().__init__(
            f"Gate surface (stamped {surface_kind.value!r}) is at {actual_ref!r} "
            f"but the gate expected it at {expected_ref!r}; refusing to judge a "
            "surface that has drifted from its reference point (GEC-2 / C5)."
        )


@dataclass(frozen=True)
class GateExecutionContext:
    """The ``(surface, ref, phase)`` bundle a gate is handed and cannot derive.

    Immutable for the duration of one gate invocation. GEC-1: a gate *receives*
    this — it may not build one from ``repo_root`` / ``os.getcwd()`` / a bare dir.
    The single construction door is :func:`build_gate_execution_context`.

    A gate judges its subject strictly from :attr:`surface` (C1) and names
    :attr:`surface_kind` + :attr:`ref` on every verdict it emits (C6 / NFR-003).
    """

    surface: Path
    surface_kind: TopologySurface
    ref: str
    phase: LifecyclePhase
    mission_slug: str

    def assert_at_ref(self, head_of: SurfaceHeadResolver | None = None) -> None:
        """GEC-2 / C5: refuse to judge a surface that has drifted from its ref.

        Reads the surface's actual HEAD (via ``head_of``, defaulting to the git
        resolver) and raises :class:`GateSurfaceRefMismatch` when it differs from
        :attr:`ref`. An explicit gate step — a gate calls it before judging when it
        needs ref agreement — so :func:`build_gate_execution_context` stays a pure,
        HEAD-read-free construction door (GEC-1) and a non-checkout surface is never
        forced through a git read it does not need.
        """
        resolve = _git_head_of if head_of is None else head_of
        actual_ref = resolve(self.surface)
        if actual_ref != self.ref:
            raise GateSurfaceRefMismatch(
                surface_kind=self.surface_kind,
                expected_ref=self.ref,
                actual_ref=actual_ref,
            )

    def not_applicable_below(
        self, minimum_phase: LifecyclePhase
    ) -> CannotEvaluate | None:
        """PH-1: refuse (not pass/fail) when below the gate's declared floor.

        Returns a :class:`CannotEvaluate` naming ``NOT_APPLICABLE_IN_PHASE`` when
        this context's :attr:`phase` is earlier than ``minimum_phase`` — the single
        rule that turns "a gate ran too early" into a distinguishable outcome
        instead of a spurious verdict. Returns ``None`` when the phase is in range.
        """
        if self.phase < minimum_phase:
            return CannotEvaluate(
                reason=CannotEvaluateReason.BELOW_MINIMUM_PHASE,
                detail=(
                    f"Gate is not applicable at phase {self.phase.name}: its subject "
                    f"cannot exist before {minimum_phase.name}."
                ),
                surface_kind=self.surface_kind,
                ref=self.ref,
            )
        return None

    def surface_cannot_hold(
        self, declared_home: TopologySurface
    ) -> CannotEvaluate | None:
        """GEC-5 / C2: a stamp is not permission.

        When the kind's ``declared_home`` is ``COORD`` but this context's surface
        was stamped ``PRIMARY`` (the ``EMPTY`` create-window
        substitution), the surface is *visible* but not *authoritative*: it cannot
        hold the coord-homed fact. Returns cannot-evaluate rather than letting the
        gate read an empty primary and pass by default (#2885). Returns ``None``
        when the surface can legitimately hold the fact — i.e. the declared home is
        ``PRIMARY`` (flat / ``SINGLE_BRANCH`` / ``LANES``, where primary IS the
        home, AH-2), or the surface is stamped the coord home it was resolved to.

        The comparison is ``COORD`` vs ``PRIMARY`` *stamps* — never a coord-topology
        branch on this type (GEC-4). ``declared_home`` is computed once, upstream,
        by :func:`declared_home_surface` from the canonical partition authority.
        """
        if (
            declared_home is TopologySurface.COORD
            and self.surface_kind is TopologySurface.PRIMARY
        ):
            return CannotEvaluate(
                reason=CannotEvaluateReason.SURFACE_CANNOT_HOLD_FACT,
                detail=(
                    "Kind's declared home is COORD but the resolved surface is "
                    "stamped PRIMARY (the coordination surface is not materialised "
                    "yet); a substituted surface cannot hold this fact — refusing "
                    "rather than judging an empty surface (GEC-5 / C2)."
                ),
                surface_kind=self.surface_kind,
                ref=self.ref,
            )
        return None


def declared_home_surface(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    *,
    resolver: MissionResolver | None = None,
    owned: OwnedCheckout | None = None,
) -> TopologySurface:
    """The surface a ``kind`` authoritatively belongs to under the STORED topology.

    Answers "where does this kind's fact live" (GEC-5's input). A THIN wrapper
    over :func:`mission_runtime.declared_read_surface` — the ONE shared
    partition (:func:`mission_runtime.is_primary_artifact_kind`) + topology
    (:func:`mission_runtime.routes_through_coordination`) predicate — so it
    never re-derives coord-state or ``EMPTY`` loud/quiet behaviour:

    * a PRIMARY-partition kind is ``PRIMARY`` for every topology (AH-1/AH-3);
    * a coord-partition kind is ``COORD`` only when the mission's stored topology
      routes through coordination; on flat / ``SINGLE_BRANCH`` / ``LANES`` its
      declared home is ``PRIMARY`` (AH-2 — primary is the home, not a fallback).

    This is a per-kind *home* fact, not a coord-topology branch on the gate context
    (GEC-4): the flat and coord-materialised cases both answer with the surface the
    fact genuinely lives on, and only the coord create-window diverges from its
    stamp — which is exactly what :meth:`GateExecutionContext.surface_cannot_hold`
    keys on.

    coord-write-placement-closure-01KYCF83 WP07 (T034 fold — the #2906
    convergence): this function used to reimplement the partition+topology
    check inline; it now DELEGATES to :func:`mission_runtime.
    declared_read_surface` — the same predicate the new fail-loud read
    authority (:meth:`mission_runtime.PlacementSeam.read_dir`'s
    ``resolve_artifact_surface`` projection) is built from. One shared
    predicate, two consumers — never a second competing guard.
    """
    return declared_read_surface(
        repo_root, mission_slug, kind, resolver=resolver,
        owned=owned,
    )


# Default HEAD resolver for GEC-2 ref agreement. Injected in tests so the seam is
# exercisable without a real repository; the production default reads the surface
# checkout's HEAD via git.
SurfaceHeadResolver = Callable[[Path], str]


_DETACHED_HEAD_SENTINEL = "HEAD"


def _git_head_of(surface: Path) -> str:
    """Resolve the short branch name checked out at ``surface`` (GEC-2 / C5).

    Mirrors ``safe_commit``'s own HEAD-vs-destination assert
    (``specify_cli.git.commit_helpers._read_worktree_head``): a short branch name
    via ``git symbolic-ref``, never a raw commit sha. A ``ref`` supplied to
    :meth:`GateExecutionContext.assert_at_ref` is always a branch-shaped
    identifier (the caller-observed checked-out branch, or the mission's target
    branch, or the literal ``"HEAD"`` fallback — see
    ``gates_core._acceptance_gate_context``), so the actual-side of the
    comparison must be branch-shaped too; a sha would never agree with a branch
    name and the assertion would refuse on every real invocation, not merely a
    drifted one. A detached checkout (``symbolic-ref`` fails) resolves to the
    same ``"HEAD"`` sentinel the caller falls back to when it has no branch to
    assert against, so "no expectation" on either side compares equal.
    """
    from specify_cli.task_utils import run_git

    result = run_git(
        ["symbolic-ref", "--short", "HEAD"], cwd=surface, check=False
    )
    if result.returncode != 0:
        return _DETACHED_HEAD_SENTINEL
    # ``result.stdout`` widens to ``Any`` across the subprocess boundary; bind
    # explicitly so the declared ``-> str`` return narrows back.
    branch: str = result.stdout.strip()
    return branch


def build_gate_execution_context(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    *,
    phase: LifecyclePhase,
    ref: str,
    resolver: MissionResolver | None = None,
    owned: OwnedCheckout | None = None,
) -> GateExecutionContext:
    """The ONE construction door for a :class:`GateExecutionContext` (GEC-1).

    Resolves the surface through the WP02 seam
    (:func:`mission_runtime.resolve_artifact_surface`) — never an ambient
    ``repo_root`` / cwd — so the four ``CoordState`` answers are total by
    construction (C3): ``DELETED`` propagates ``CoordinationBranchDeleted``,
    ``UNMATERIALIZED`` propagates ``CoordinationWorktreeUnmaterialized`` (#4959),
    ``EMPTY`` resolves primary stamped ``PRIMARY``, and
    ``MATERIALIZED`` resolves coord. The caller-asserted ``ref`` is the reference
    point the surface is expected to be at; GEC-2 agreement is verified separately
    and lazily by :meth:`GateExecutionContext.assert_at_ref` (C5), keeping this door
    pure so it never forces a HEAD read a non-checkout surface does not need.

    Raises:
        CoordinationBranchDeleted: when the declared coordination branch has been
            deleted from git (propagated from the resolver, C3 fail-loud).
    """
    resolved = resolve_artifact_surface(
        repo_root, mission_slug, kind, resolver=resolver,
        owned=owned,
    )
    return GateExecutionContext(
        surface=resolved.path,
        surface_kind=resolved.surface_kind,
        ref=ref,
        phase=phase,
        mission_slug=mission_slug,
    )


__all__ = [
    "CannotEvaluate",
    "CannotEvaluateReason",
    "GateExecutionContext",
    "GateSurfaceRefMismatch",
    "LifecyclePhase",
    "SurfaceHeadResolver",
    "build_gate_execution_context",
    "declared_home_surface",
]
