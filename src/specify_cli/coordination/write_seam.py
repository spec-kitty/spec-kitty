"""Write-seam adoption helper (FR-007 core; FR-011 zero-write refusal; FR-012).

Not a new write resolver (ADR ``2026-06-24-1`` C-006 forbids a second one) --
this module composes the existing write authority
(:func:`mission_runtime.placement_seam` -> :meth:`~mission_runtime.PlacementSeam
.write_target`) with the existing commit materialiser
(:func:`~specify_cli.coordination.commit_router.commit_for_mission`) into ONE
reusable helper that the TRUE write-side bypasses
(``kitty-specs/write-side-seam-matrix-tracer-01KYP3MH/contracts/write-seam-
adoption.md``) converge onto. It never routes the seam's own engine
(``commit_router`` internals, ``write_target_degrade``, the
``status_transition:300`` FR-006 mirror, merge infra) -- doing so would be
circular.

FR-011 (zero-write refusal): when the seam cannot resolve a routable
destination for ``kind`` (missing coord surface, a deleted ``target_branch``,
or any other unroutable-mission condition), :func:`write_artifact` refuses --
it NEVER falls back to a hand-picked ref (e.g. ``main``), and it NEVER writes
anything. This mirrors -- but deliberately does NOT repeat -- the defect
latent in ``mission_runtime.write_target_degrade.resolve_write_target_or_
degrade``: that helper's ``degrade_ref`` fallback exists to serve callers
that explicitly opt into a fail-open policy (writing straight to a caller-
supplied ref on an unresolvable mission); THIS helper's callers never opt
into that -- an unroutable target is always a structured, recoverable
REFUSAL that discloses the deferred #3033 ``CONSOLIDATED``-surface decision,
never a silent (or loud) write to the wrong place, and never a consolidation
abort (``2026-07-23-2``).

FR-012 (idempotent, structured result): re-invoking with identical inputs is
a no-op. This is inherited directly from ``commit_for_mission``'s own
idempotence contract (a byte-identical artifact already committed at the
resolved placement returns ``"unchanged"``, never a duplicate empty commit)
-- this helper does not re-implement that logic, it only projects the
outcome into :class:`WriteSeamResult`.

post-merge-write-authoring-finish-01KYRRM5 WP04 (#3033 T014/T016/T017)
------------------------------------------------------------------------

**Staging thunk (FR-005 / #3073).** :func:`write_artifact` accepts EXACTLY
ONE of ``files=`` (the historical pre-staged-paths contract) or ``stage=``
(a zero-arg callable that MATERIALIZES the artifact on disk and returns the
paths, invoked ONLY after :func:`_probe_write_target` returns a routable
target). This is the single locus of the probe-before-stage invariant: a
refused write never calls ``stage()``, so it leaves zero untracked residue.
No per-writer reordering is needed or permitted; the single call site here
IS the contract.

**Caller census (priti B1 / paula M2, T014/T018).** Of :func:`write_artifact`'s
callers, exactly THREE pre-stage a LOCAL file before calling in (candidates
for the ``stage=`` migration): ``retrospective/tracer_writer.py`` (migrated
here, T015), ``acceptance/matrix.py`` (WP05 T024), and
``tasks/issue_matrix.py`` (WP06 T029). Every other caller passes
PRE-EXISTING, already-dirty paths it did not just materialize (a
commit-existing-dirty sweep, not a stage-then-probe hazard) --
``cli/commands/accept.py``'s ``_commit_coord_residuals`` is the canonical
example and is intentionally NOT migrated to ``stage=``: it commits
whatever the working tree already holds, so there is no residue to guard
against (a refused commit there leaves exactly the pre-existing dirty state,
not NEW untracked files this seam created). This claim is explicit, not
assumed -- it was checked against every caller of this function at WP04
authorship time.

**Off-checkout refuse-with-recovery (FR-006).** WP03's resolver
(``mission_runtime.resolve_placement_only``) raises a structured
``ActionContextError`` (code ``"CONSOLIDATED_CONTENT_ABSENT"``, documented on
its own ``Raises:`` clause as "the signal WP04's catch clause consumes")
when a PUBLISHED (E2) mission's consolidated content is not present on the
current checkout. :func:`_probe_write_target` already catches
``ActionContextError`` as part of ``_UNROUTABLE_EXCEPTIONS``; this module
recognises that ONE code and formats a refusal diagnostic that carries the
resolver's OWN branch-derived recovery text verbatim (the resolver derives
it via ``resolve_primary_branch(..., bias=False)``, whose Method 1 is
``git symbolic-ref refs/remotes/origin/HEAD`` -- never a hard-coded
``"main"``, never a bare SHA). This module never re-derives the branch name
and never performs a checkout (C-004).

**E2 CONSOLIDATED write authorization (FR-003/FR-004, #3033 T017).** The
resolved CONSOLIDATED target for a PUBLISHED (E2) mission is the
repository-root checkout on a (commonly protected) Primary Branch --
:func:`~specify_cli.coordination.commit_router.commit_for_mission` (frozen,
downstream of the single resolver -- WP03 hardening) refuses a protected
destination under its own default ``GuardCapability.STANDARD``, with no
capability parameter exposed for a caller to override. Rather than editing
that frozen module, this seam recognises the E2 CONSOLIDATED destination
from PUBLIC signals ONLY (:func:`is_post_consolidation_write_target` --
never re-deriving ``LifecyclePhase``, which is internal to
``mission_runtime`` and import-forbidden from outside the package, ADR
2026-06-07-1) and, for exactly that recognised destination, commits through
:func:`~specify_cli.git.commit_helpers.safe_commit` directly with the
asserted ``GuardCapability.POST_CONSOLIDATION_WRITE`` -- mirroring the
established single-sanctioned-protected-flow pattern
(``git/bookkeeping_commit.py`` / ``MERGE_BOOKKEEPING``), registered in the
same architectural allowlist
(``tests/architectural/test_guard_capability_call_sites.py``). Every other
destination (pre-consolidation, E1, or a coordination branch) is completely
unaffected -- it still routes through ``commit_for_mission`` exactly as
before (regression floor, #3076).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from mission_runtime import ActionContextError, CommitTarget, MissionArtifactKind, placement_seam

# Imported from the submodule (not re-exported by ``mission_runtime.__init__``,
# which is outside this WP's owned surface) — the same convention as the
# ``specify_cli.missions._read_path_resolver`` import below. It IS a public name
# (in ``write_target_degrade.__all__``); this is the ONE fail-closed WRITE
# decision the seam consults (RN-F1), never a second resolver.
from mission_runtime.write_target_degrade import assert_coord_write_materialized
from specify_cli.coordination.commit_router import CommitRouterResult, commit_for_mission
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.core.owned_mission import effective_root_kwargs
from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

# The exact caught set mission_runtime.write_target_degrade.resolve_write_target_or_degrade
# already established as "a genuine mission-resolution failure" (never a bare
# ``except Exception`` -- an unrelated bug surfacing inside the seam must still
# raise loudly, not be swallowed into a refusal). ``StatusReadPathNotFound``
# covers its subclass ``CoordinationBranchDeleted`` (a deleted coord branch),
# the literal FR-011 scenario named in the WP context.
_UNROUTABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    ActionContextError,
    StatusReadPathNotFound,
    FileNotFoundError,
)

_REFUSAL_DIAGNOSTIC_TEMPLATE = (
    "write_seam: refusing a zero-write on an unroutable target for mission "
    "{mission_slug!r} (kind={kind_value!r}); this is the deferred #3033 "
    "CONSOLIDATED-surface decision -- no fallback write, no consolidation "
    "abort. Original resolution failure: {cause}"
)

# FR-006 (T016): a DISTINCT diagnostic for WP03's structured off-checkout
# signal -- distinguishable from the generic FR-011 unroutable-target refusal
# above so a caller/log reader can tell "genuinely no route exists" apart from
# "a route exists, but not from THIS checkout". ``{cause}`` is the resolver's
# own exception text, which already names the branch-derived recovery
# instruction (see module docstring) -- never recomputed here.
_OFF_CHECKOUT_REFUSAL_DIAGNOSTIC_TEMPLATE = (
    "write_seam: refusing a zero-write for mission {mission_slug!r} (kind={kind_value!r}) -- FR-006 off-checkout refusal (#3033): {cause}"
)

# FR-006 (S-C / #4970): a DISTINCT diagnostic for the fail-closed WRITE gate —
# a coord-routing write whose coordination surface is unresolved/unmaterialized
# on this checkout. Distinguishable from the generic FR-011 unroutable-target
# refusal so a log reader can tell "no route exists" apart from "the coordination
# surface exists but is not materialized here". ``{cause}`` is the gate's own
# exception text, which already names the branch-derived recovery instruction.
_UNMATERIALIZED_COORD_REFUSAL_TEMPLATE = (
    "write_seam: refusing a zero-write for mission {mission_slug!r} (kind={kind_value!r}) -- FR-006 unmaterialized coordination surface (#4970): {cause}"
)

# Mirrors ``mission_runtime.write_target_degrade._COORD_WRITE_UNMATERIALIZED_CODE``
# (mirrored, not imported -- the code string itself IS the public "structured
# signal" contract, exactly as ``_CONSOLIDATED_CONTENT_ABSENT_CODE`` below mirrors
# resolution.py's private value).
_COORD_WRITE_UNMATERIALIZED_CODE = "COORD_WRITE_SURFACE_UNMATERIALIZED"

# Mirrors resolution.py's private ``_CONSOLIDATED_CONTENT_ABSENT_CODE`` value
# (mirrored, not imported -- ``resolution.py`` is an internal ``mission_runtime``
# submodule, import-forbidden from outside the package, ADR 2026-06-07-1; the
# code string itself IS the public "structured signal" contract, documented on
# ``resolve_placement_only``'s ``Raises:`` clause as "the signal WP04's catch
# clause consumes"). Matches this module's existing convention for
# resolution-internal signals (see ``tracer_writer.py``'s
# ``_NO_EXISTING_CONTENT_EXCEPTIONS`` comment for the sibling pattern).
_CONSOLIDATED_CONTENT_ABSENT_CODE = "CONSOLIDATED_CONTENT_ABSENT"

_STATUS_REFUSED: Literal["refused"] = "refused"
_STATUS_COMMITTED: Literal["committed"] = "committed"
_STATUS_UNCHANGED: Literal["unchanged"] = "unchanged"

# T014 (renata m4): write_artifact accepts EXACTLY ONE of files=/stage=.
_MATERIALIZATION_USAGE_ERROR_NEITHER = "write_artifact requires exactly one of files= or stage= (materialization source); neither was supplied."
_MATERIALIZATION_USAGE_ERROR_BOTH = "write_artifact requires exactly one of files= or stage= (materialization source); both were supplied."

# T017: git-level "nothing to commit" signal, shared verbatim with
# ``coordination.commit_router._is_empty_changeset_error`` -- ``safe_commit``
# raises this exact ``RuntimeError`` prefix when ``git commit`` finds no
# staged delta (e.g. a byte-identical artifact already committed at the
# resolved placement), so the E2 CONSOLIDATED bypass path (which cannot reuse
# the frozen router's own idempotence handling) recognises the SAME signal
# rather than inventing a second one.
_EMPTY_CHANGESET_PREFIX = "safe_commit: git commit failed"


class WriteSeamUsageError(ValueError):
    """T014 (renata m4): ``write_artifact`` was called with neither/both of
    ``files=``/``stage=``. A caller-programming-error, raised immediately at
    entry -- before the probe, before any I/O -- never silently defaulting to
    one or the other.
    """


@runtime_checkable
class ProtectionPolicyLike(Protocol):
    """Structural protocol for the ``ProtectionPolicy`` duck-type this helper
    threads straight through to ``commit_for_mission``.

    Mirrors ``commit_router._ProtectionPolicyProtocol`` locally (rather than
    importing that private name across the module boundary) for the same
    reason it exists there: avoiding a hard import cycle while matching on
    structure, not on the concrete class.
    """

    def is_protected(self, ref: str) -> bool: ...


@dataclass(frozen=True)
class WriteSeamResult:
    """Structured, typed outcome of :func:`write_artifact` (FR-012).

    ``status`` mirrors :class:`~specify_cli.coordination.commit_router.
    CommitRouterResult` for the routed outcomes (``"committed"`` /
    ``"unchanged"`` / ``"no_op_wrong_surface"`` / ``"error"``), plus the
    FR-011 zero-write ``"refused"`` outcome this helper adds on top -- the
    ONE outcome ``commit_for_mission`` itself can never produce, because
    reaching ``"refused"`` means resolution never got far enough to call it.

    ``entry_id`` names the logical row/entry this write represents (e.g. an
    issue number, a WP id) so a caller can log/report which write an outcome
    belongs to without re-threading its own bookkeeping. ``destination_surface``
    is the resolved placement ref on every non-refused outcome, and ``None``
    on ``"refused"`` (there is no destination -- nothing was resolved).
    """

    status: Literal["committed", "unchanged", "no_op_wrong_surface", "error", "refused"]
    entry_id: str
    destination_surface: str | None
    commit_hash: str | None = None
    diagnostic: str | None = None


def _probe_write_target(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    *,
    effective_root: Path | None = None,
) -> CommitTarget | Exception:
    """Probe routability via the seam; return the resolved target, or the
    caught exception on an unroutable target.

    A THIN probe -- it resolves via :meth:`~mission_runtime.PlacementSeam.
    write_target` (the same authority ``commit_for_mission`` itself calls
    internally) purely to detect an unroutable target BEFORE any write is
    attempted. The caller does not treat the returned :class:`CommitTarget`
    as authoritative for materialisation -- ``commit_for_mission`` (or the
    T017 E2 CONSOLIDATED bypass) resolves again internally (C-006 -- this is
    the one seam, consulted twice for two different purposes: refusal
    detection / mechanism selection, and materialisation). Surfacing the
    resolved value (rather than discarding it, pre-WP04) lets
    :func:`write_artifact` recognise the E2 CONSOLIDATED destination without
    a THIRD resolution call.
    """
    try:
        return placement_seam(
            repo_root,
            mission_slug,
            **effective_root_kwargs(effective_root),
        ).write_target(kind)
    except _UNROUTABLE_EXCEPTIONS as exc:
        return exc


def _is_off_checkout_refusal(exc: Exception) -> bool:
    """T016: does ``exc`` carry WP03's structured FR-006 off-checkout signal?"""
    return isinstance(exc, ActionContextError) and exc.code == _CONSOLIDATED_CONTENT_ABSENT_CODE


def _refused_result(*, mission_slug: str, kind: MissionArtifactKind, entry_id: str, cause: Exception) -> WriteSeamResult:
    """Build the FR-011/FR-006 zero-write refusal (T016 -- ONE locus, two templates)."""
    template = _OFF_CHECKOUT_REFUSAL_DIAGNOSTIC_TEMPLATE if _is_off_checkout_refusal(cause) else _REFUSAL_DIAGNOSTIC_TEMPLATE
    return WriteSeamResult(
        status=_STATUS_REFUSED,
        entry_id=entry_id,
        destination_surface=None,
        diagnostic=template.format(mission_slug=mission_slug, kind_value=kind.value, cause=cause),
    )


def _coord_surface_write_refusal(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    resolved: CommitTarget,
    *,
    entry_id: str,
) -> WriteSeamResult | None:
    """Consult the S-C fail-closed WRITE gate; return a refusal or ``None`` (proceed).

    FR-006 / #4970: ``_probe_write_target`` already refuses an *unroutable* target
    (a resolution exception), but a coord-routing mission whose coordination branch
    RESOLVES cleanly while its worktree is absent-and-not-a-local-head (the
    fresh-clone / CI shape) slips past it and would degrade to the primary
    directory, overwriting committed coordination state. This gate closes that hole
    by consulting the ONE decision locus
    (:func:`mission_runtime.assert_coord_write_materialized`) on the
    already-probed ``resolved`` target — no second resolution (C-006). It runs
    BEFORE any staging so a refused write leaves zero residue (FR-005).

    Returns a ``"refused"`` :class:`WriteSeamResult` when the gate raises, else
    ``None``. A non-coord / E2 / materialized target is a no-op inside the gate,
    so this returns ``None`` and the ordinary write path proceeds unchanged.
    """
    try:
        assert_coord_write_materialized(repo_root, mission_slug, kind, resolved)
    except ActionContextError as exc:
        template = _UNMATERIALIZED_COORD_REFUSAL_TEMPLATE if exc.code == _COORD_WRITE_UNMATERIALIZED_CODE else _REFUSAL_DIAGNOSTIC_TEMPLATE
        return WriteSeamResult(
            status=_STATUS_REFUSED,
            entry_id=entry_id,
            destination_surface=None,
            diagnostic=template.format(mission_slug=mission_slug, kind_value=kind.value, cause=exc),
        )
    return None


def _materialize_files(
    files: tuple[Path, ...] | None,
    stage: Callable[[], tuple[Path, ...]] | None,
) -> tuple[Path, ...]:
    """T014: the SINGLE locus where ``stage()`` is invoked -- called ONLY after
    the routability probe has already returned OK (FR-005 probe-before-stage).

    Exactly one of ``files``/``stage`` is guaranteed non-``None`` here (the
    entry guard in :func:`write_artifact` already raised on neither/both).
    """
    if stage is not None:
        return stage()
    if files is not None:
        return files
    raise WriteSeamUsageError(  # pragma: no cover -- unreachable; guarded at entry
        _MATERIALIZATION_USAGE_ERROR_NEITHER
    )


# C-005 / SC-005 defense in depth: resolution.py's own E2-eligible-kind set
# already excludes these two (they must never re-route in E2), so this arm
# should be unreachable via a legitimate ``resolved`` value. Kept as a second,
# independent guard so a future accidental widening in resolution.py cannot
# silently authorize an elevated capability here too (belt-and-braces, not a
# second resolver -- it never CHANGES where the write routes, only whether
# THIS module may assert an elevated capability for it).
_NEVER_POST_CONSOLIDATION_KINDS: frozenset[MissionArtifactKind] = frozenset({MissionArtifactKind.STATUS_STATE, MissionArtifactKind.DECISION_LOG})


def is_post_consolidation_write_target(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    resolved: CommitTarget,
) -> bool:
    """Recognise WP03's E2 CONSOLIDATED short-circuit from PUBLIC signals ONLY.

    Used to select the commit MECHANISM for an ALREADY-RESOLVED destination
    (never to re-decide placement -- ``resolved`` came from
    :func:`mission_runtime.resolve_placement_only`, the single resolver,
    C-006). ``True`` iff ``resolved.ref`` equals the resolved Primary Branch
    (:func:`~specify_cli.core.git_ops.resolve_primary_branch`, ``bias=False``)
    AND diverges from the mission's OWN stored ``target_branch``
    (:func:`~specify_cli.core.paths.get_feature_target_branch`, which "stays
    unrouted" per D2/C-003 -- it always returns the raw stored field
    regardless of lifecycle phase). This exact divergence only occurs via
    WP03's E2 (published) CONSOLIDATED short-circuit: every other phase
    resolves a kind to either the coordination branch or the mission's own
    ``target_branch`` verbatim -- never to the repository's Primary Branch
    name while also differing from ``target_branch``.

    This mirrors -- without re-implementing -- the SAME
    ``placement.ref != primary_target`` comparison
    ``coordination.commit_router._commit_partition_group`` already makes
    internally for its own ``use_coord`` decision; it does NOT re-derive
    ``LifecyclePhase`` (internal to ``mission_runtime``, import-forbidden
    from outside the package, ADR 2026-06-07-1).
    """
    if kind in _NEVER_POST_CONSOLIDATION_KINDS:
        return False

    from specify_cli.core.git_ops import resolve_primary_branch
    from specify_cli.core.paths import get_feature_target_branch, get_main_repo_root

    main_root = get_main_repo_root(repo_root)
    # Explicit annotations: under the project's ``follow_imports = "skip"``
    # mypy config, these cross-module ``specify_cli.*`` calls are seen as
    # returning ``Any`` when this file is type-checked in isolation; the
    # annotations re-narrow them back to ``str`` (matching the sibling
    # ``tracer_writer.py`` / ``lifecycle_phase.py`` chokepoint pattern).
    primary_branch: str = resolve_primary_branch(main_root, bias=False)
    if resolved.ref != primary_branch:
        return False
    target_branch: str = get_feature_target_branch(repo_root, mission_slug)
    return resolved.ref != target_branch


def _commit_post_consolidation_write(
    *,
    repo_root: Path,
    resolved: CommitTarget,
    files: tuple[Path, ...],
    message: str,
    entry_id: str,
) -> WriteSeamResult:
    """T017: land the E2 CONSOLIDATED write via the ONE authorized direct path.

    Mirrors ``git/bookkeeping_commit.py``'s established shape -- a single
    guarded ``safe_commit`` call site asserting a dedicated non-STANDARD
    :class:`~specify_cli.core.commit_guard.GuardCapability`, registered in
    ``tests/architectural/test_guard_capability_call_sites.py`` -- rather
    than ``commit_for_mission``'s richer partition-aware machinery, which
    this narrow, already-resolved-destination case does not need: the
    resolved surface here is BY DEFINITION the repository-root checkout
    (never a coordination worktree -- the coordination branch is exactly
    what E2 publication retires), so there is no partition split to perform
    and no coordination ff-advance to attempt (it would target the
    mission's OWN now-deleted Target Ref, a no-op even in
    ``commit_for_mission``'s own best-effort path).
    """
    from specify_cli.git import safe_commit

    if not files:
        return WriteSeamResult(status=_STATUS_UNCHANGED, entry_id=entry_id, destination_surface=resolved.ref)
    if any(not path.exists() for path in files):
        return WriteSeamResult(
            status="no_op_wrong_surface",
            entry_id=entry_id,
            destination_surface=resolved.ref,
            diagnostic=(
                f"Artifact(s) not present at resolved CONSOLIDATED placement ({resolved.ref}); commit would no-op against the wrong surface and was not created."
            ),
        )

    try:
        commit_result = safe_commit(
            repo_root=repo_root,
            worktree_root=repo_root,
            target=resolved,
            message=message,
            paths=files,
            capability=GuardCapability.POST_CONSOLIDATION_WRITE,
        )
    except RuntimeError as exc:
        if str(exc).startswith(_EMPTY_CHANGESET_PREFIX):
            return WriteSeamResult(status=_STATUS_UNCHANGED, entry_id=entry_id, destination_surface=resolved.ref)
        return WriteSeamResult(status="error", entry_id=entry_id, destination_surface=resolved.ref, diagnostic=str(exc))

    return WriteSeamResult(
        status=_STATUS_COMMITTED,
        entry_id=entry_id,
        destination_surface=resolved.ref,
        commit_hash=commit_result.sha,
    )


def write_artifact(
    *,
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    message: str,
    policy: ProtectionPolicyLike,
    entry_id: str,
    files: tuple[Path, ...] | None = None,
    stage: Callable[[], tuple[Path, ...]] | None = None,
    target_branch: str | None = None,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
    effective_root: Path | None = None,
) -> WriteSeamResult:
    """Write mission artifact ``kind`` through the ONE write seam.

    Resolves the destination via :meth:`~mission_runtime.PlacementSeam.
    write_target` and, when routable, materialises via
    :func:`~specify_cli.coordination.commit_router.commit_for_mission` --
    except for the recognised E2 CONSOLIDATED destination (T017), which
    lands via the authorized direct path (:func:`_commit_post_consolidation_
    write`; see the module docstring). An unroutable target (missing coord
    surface, deleted ``target_branch``, or any other mission-resolution
    failure) is refused with a zero-write, structured result (FR-011); a
    routable-but-off-checkout target (FR-006) is refused with a
    branch-named recovery instruction -- see the module docstring.

    Args:
        repo_root: Primary checkout root.
        mission_slug: Mission handle.
        kind: The :class:`~mission_runtime.MissionArtifactKind` being written.
        message: Commit message.
        policy: A duck-typed ``is_protected(ref) -> bool`` policy object.
        entry_id: Caller-supplied identifier for the row/entry being written.
        files: Absolute, ALREADY-MATERIALIZED paths of artifacts to commit
            (the historical contract). Mutually exclusive with ``stage``
            (T014) -- exactly one is required.
        stage: A zero-arg callable that materializes the artifact on disk
            and returns its paths, invoked ONLY after the routability probe
            succeeds (T014 / FR-005 -- no residue on a refused write).
            Mutually exclusive with ``files``.
        target_branch: Optional short primary-branch name for the post-commit
            ff-advance (threaded straight through to ``commit_for_mission``;
            unused by the E2 CONSOLIDATED bypass -- see its docstring).
        primary_paths_created_this_invocation: Threaded straight through to
            ``commit_for_mission`` (coord-residue cleanup eligibility, R6).

    Returns:
        A :class:`WriteSeamResult`.

    Raises:
        WriteSeamUsageError: neither or both of ``files``/``stage`` supplied.
    """
    if files is None and stage is None:
        raise WriteSeamUsageError(_MATERIALIZATION_USAGE_ERROR_NEITHER)
    if files is not None and stage is not None:
        raise WriteSeamUsageError(_MATERIALIZATION_USAGE_ERROR_BOTH)

    probed = _probe_write_target(
        repo_root,
        mission_slug,
        kind,
        **effective_root_kwargs(effective_root),
    )
    if isinstance(probed, Exception):
        return _refused_result(mission_slug=mission_slug, kind=kind, entry_id=entry_id, cause=probed)

    # S-C fail-closed WRITE gate (FR-006 / #4970): refuse a coord-routing write onto
    # an unresolved/unmaterialized coordination surface BEFORE staging, so a refused
    # write leaves no residue. Owned single-branch (``effective_root``) writes never
    # route through coordination, so the gate is skipped for them (it would have no
    # coordination_branch to gate on either). E2 CONSOLIDATED targets resolve to the
    # Primary Branch (not the coordination branch) and are a no-op inside the gate.
    if effective_root is None:
        refusal = _coord_surface_write_refusal(repo_root, mission_slug, kind, probed, entry_id=entry_id)
        if refusal is not None:
            return refusal

    materialized_files = _materialize_files(files, stage)

    if effective_root is None and is_post_consolidation_write_target(repo_root, mission_slug, kind, probed):
        return _commit_post_consolidation_write(
            repo_root=repo_root,
            resolved=probed,
            files=materialized_files,
            message=message,
            entry_id=entry_id,
        )

    result: CommitRouterResult = commit_for_mission(
        repo_root,
        mission_slug,
        materialized_files,
        message,
        policy,
        kind=kind,
        primary_paths_created_this_invocation=primary_paths_created_this_invocation,
        target_branch=target_branch,
        **effective_root_kwargs(effective_root),
    )
    return WriteSeamResult(
        status=result.status,
        entry_id=entry_id,
        destination_surface=result.placement_ref,
        commit_hash=result.commit_hash,
        diagnostic=result.diagnostic,
    )
