"""Execution-state resolution entry point (canonical surface, internal module).

This is an **internal** submodule of the :mod:`mission_runtime` umbrella. It is
import-forbidden from outside the package — consumers use the symbols re-exported
from :mod:`mission_runtime` only (see ADR 2026-06-07-1 and
``tests/architectural/test_mission_runtime_surface.py``).

WP03 relocates the hardened ``resolve_action_context`` (and its helpers) from
``specify_cli.core.execution_context`` here under the Strangler migration. The
implementation is moved verbatim — this is the single sanctioned resolver
(FR-003/FR-005); behaviour is preserved (NFR-001) and no parallel resolver
survives (NFR-002). The old ``core/execution_context.py`` is removed entirely —
no importers remained after the caller migration, so it is deleted, not shimmed.

Prompts should not discover context on their own. They call into this
command-owned resolver, which determines the active mission, target branch,
work package, workspace path, and any action-specific commands to run.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast, get_args

from mission_runtime.artifacts import (
    MissionArtifactKind,
    TopologySurface,
    _PRIMARY_ARTIFACT_KINDS,
    artifact_home_for,
    assert_partition_invariant,
    assert_surface_totality,
    is_primary_artifact_kind,
)
from mission_runtime.context import (
    ArtifactPlacementFragment,
    BranchRefFragment,
    CommitTarget,
    IdentityFragment,
    MissionArtifactContext,
    MissionContext,
    MissionExecutionContext,
    MissionTopology,
    StatusSurfaceFragment,
    WorkspaceFragment,
    is_single_branch,
    routes_through_coordination,
)
from mission_runtime.identity import mid8_from_slug, resolve_mid8
from mission_runtime.lifecycle_phase import (
    LifecyclePhase,
    content_present_at_primary_tip,
    resolve_lifecycle_phase,
)
from mission_runtime.mission_resolver_port import MissionResolver

# Seam-B checkout-identity refusal (WP03, #3128 / FR-005) lives in
# ``mission_runtime.checkout_identity`` and is surfaced on the package root via
# ``mission_runtime/__init__.py``; consumers import it from there (see
# ``workspace.context.resolve_workspace_for_wp``). It is intentionally NOT
# re-exported from this module — a second unimported surface here is dead public
# API (test_no_dead_symbols).


ActionName = Literal[
    "specify",
    "plan",
    "analyze",
    "tasks",
    "tasks_outline",
    "tasks_packages",
    "tasks_finalize",
    "implement",
    "review",
    "accept",
    "status",
]
ACTION_NAMES: tuple[str, ...] = cast(tuple[str, ...], get_args(ActionName))

__all__ = [
    "ACTION_NAMES",
    "ActionContextError",
    "ActionName",
    "PlacementSeam",
    # ResolvedSurface / SurfaceLocations / translate_surface: demoted -- the
    # stamped output, the input bundle, and the member->path translation of
    # ``resolve_artifact_surface`` are consumed as *instances* by src/ callers,
    # never imported by name outside this module (dead-port-disposition-01M1TZVN
    # WP03, FR-014; same disposition as resolve_context_for_mission below).
    "TopologySurface",
    "coord_read_dir_for",
    "declared_read_surface",
    "mission_context_for",
    "placement_seam",
    "resolve_action_context",
    "resolve_artifact_surface",
    "resolve_create_time_write_target",
    # resolve_context_for_mission: demoted — no cross-module src/ from-import
    # callers (WP01 harden-dead-symbol-gate-01KW0RJR).
    "resolve_placement_only",
]


class ActionContextError(RuntimeError):
    """Raised when canonical action context cannot be resolved.

    The single error type consumers catch. The resolver raises this on
    unresolvable context — there is never a silent fallback (see the contract).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# Placement-seam campsite (coord-primary-partition-lock WP01, S1192): the
# ``ActionContextError`` code raised whenever a mission handle/slug fails to
# resolve at ALL four sites in this module (``_resolve_mission_slug``,
# ``mission_context_for``, ``resolve_placement_only``) restated the literal
# string. Hoisted to one module constant.
_FEATURE_CONTEXT_UNRESOLVED_CODE = "FEATURE_CONTEXT_UNRESOLVED"

# #3033 WP03 (ADR 2026-07-30-1 Decision 1 §6, operator HiC): the E2
# (PUBLISHED) CONSOLIDATED-surface write routing is SCOPED, not blanket. It
# applies to every PRIMARY-partition kind PLUS exactly the four coord
# write kinds named by the ADR (ISSUE_MATRIX / TRACER_FILE /
# ACCEPTANCE_MATRIX -- #3033 -- and REVIEW_CYCLE, ruled in below --
# review-cycle-verdict-seam-rebuild-01KZ2W7W WP04, T016, ADR 2026-08-03-1).
# ``STATUS_STATE`` and ``DECISION_LOG`` are DELIBERATELY excluded -- their
# post-consolidation resolution stays unchanged (SC-005 / C-005
# non-regression). This is resolver-INTERNAL kind selection (the resolver
# already keys on ``MissionArtifactKind`` for the existing
# ``_PRIMARY_ARTIFACT_KINDS`` split), never call-site kind-conditioning
# (C-006 preserved).
#
# REVIEW_CYCLE ruling (T016, INCLUDED): review-cycle artifacts share the
# EXACT "coordination branch is gone post-merge" reality the ADR's own text
# names for the other three coord kinds already in this set (measured: 45 of
# 102 review-cycle-carrying missions declare a coordination_branch, and 0 of
# those 45 branches still exist -- ADR 2026-08-03-1's "Migration" section).
# Leaving REVIEW_CYCLE unruled would make a PUBLISHED mission's review-cycle
# write fall through to the unconditional coordination-surface probe below,
# raising ``CoordinationBranchDeleted`` for every one of those 45 missions --
# exactly the defect this scoped E2 short-circuit exists to avoid for
# ISSUE_MATRIX/TRACER_FILE/ACCEPTANCE_MATRIX. This does NOT apply to
# ``DECISION_LOG``'s exclusion rationale ("in-mission and not an E2 write
# target by design", ADR 2026-07-30-1 Decision 1 §6): a review-cycle verdict
# is accept/retrospective-relevant bookkeeping like ISSUE_MATRIX /
# ACCEPTANCE_MATRIX / TRACER_FILE (the latter is explicitly read by the
# retrospective generator post-merge, per its own PARTITION_RATIONALE row),
# not an in-mission-only decision log entry that is never consulted again
# once a mission is done.
_E2_CONSOLIDATED_ELIGIBLE_KINDS: frozenset[MissionArtifactKind] = frozenset(
    _PRIMARY_ARTIFACT_KINDS
    | {
        MissionArtifactKind.ISSUE_MATRIX,
        MissionArtifactKind.TRACER_FILE,
        MissionArtifactKind.ACCEPTANCE_MATRIX,
        MissionArtifactKind.REVIEW_CYCLE,
    }
)

# The ``ActionContextError`` code raised when a PUBLISHED (E2) mission's
# CONSOLIDATED content is not present on the current checkout (FR-006
# refuse-with-recovery; the actual write-seam refusal UX is WP04's — this
# module only raises the structured signal WP04 catches).
_CONSOLIDATED_CONTENT_ABSENT_CODE = "CONSOLIDATED_CONTENT_ABSENT"


def _resolve_consolidated_e2_target(
    repo_root: Path,
    mission_slug: str,
    *,
    resolver: MissionResolver | None,
) -> CommitTarget:
    """Resolve the E2 (published) CONSOLIDATED write target (D1/D2/D3, FR-003).

    The repository-root checkout on the resolved Primary Branch, gated by the
    squash-robust content-presence predicate (D1 —
    :func:`~mission_runtime.lifecycle_phase.content_present_at_primary_tip`).
    The returned ref is ALWAYS the resolved Primary-Branch NAME — an existing
    branch — never a SHA and never literal ``HEAD`` (paula MINOR-2): this
    keeps ``commit_router.use_coord`` ``False`` and skips coord-worktree
    materialisation, matching how a genuine PRIMARY-kind write already
    resolves today.

    Raises:
        ActionContextError: When the current checkout does not carry the
            mission's consolidated content — FR-006 refuse-with-recovery,
            naming the checkout to use. The write-seam-level refusal UX
            (zero-residue, structured diagnostic) is WP04's; this is the
            signal WP04's catch clause consumes.
    """
    from specify_cli.core.git_ops import resolve_primary_branch
    from specify_cli.core.paths import get_main_repo_root

    main_root = get_main_repo_root(repo_root)
    primary_branch = resolve_primary_branch(main_root, bias=False)
    if not content_present_at_primary_tip(mission_slug, repo_root, resolver=resolver):
        raise ActionContextError(
            _CONSOLIDATED_CONTENT_ABSENT_CODE,
            f"mission {mission_slug!r} is published (its Target Ref has been "
            f"deleted) but this checkout does not carry its consolidated "
            f"content; check out {primary_branch!r} (the resolved Primary "
            "Branch) and retry.",
        )
    return CommitTarget(ref=primary_branch)


# Mission-level lifecycle actions resolve the mission context without a work
# package (FR-011 full-lifecycle parity).
_MISSION_LEVEL_ACTIONS: frozenset[str] = frozenset(
    {
        "specify",
        "plan",
        "analyze",
        "tasks",
        "tasks_outline",
        "tasks_packages",
        "tasks_finalize",
        "accept",
        "status",
    }
)


def read_dir_for(
    effective_root: Path | None,
    primary_root: Path,
    mission_slug: str,
    *,
    kind: MissionArtifactKind,
    resolver: MissionResolver | None = None,
) -> Path:
    """Resolve the primary meta-bearing read dir for a mission (single fork authority).

    Collapses the ``effective_root is None ? <legacy primary compose> :
    compose_meta_json_path(effective_root, …).parent`` fork that recurred across
    the coord/topology resolvers in this module (mission
    write-path-integrity-01KZZD69 WP01, #3373, T004). One helper now owns the
    derivation so no site re-inlines it and the read stays drift-free.

    * The default (``effective_root is None``) arm delegates to
      :func:`resolve_planning_read_dir` for the PRIMARY-partition ``kind`` these
      sites read (``PRIMARY_METADATA``). That is byte-identical to the prior
      inline ``_compose_primary_feature_dir(_canonicalize_primary_read_handle(
      primary_root, mission_slug, resolver=resolver))`` — because
      :func:`resolve_planning_read_dir`'s PRIMARY leg IS exactly that composition
      (the ``resolver`` is threaded to the same single injected walk, no bypass).
    * The opted-in (owned-checkout) arm composes the ``meta.json`` dir directly
      against the already-validated ``effective_root`` — never re-folding it
      through ``get_main_repo_root`` (#3328 / C-002) — matching the prior inline
      ``compose_meta_json_path(effective_root, mission_slug).parent``.

    ``kind`` MUST be a PRIMARY-partition kind (``meta.json`` lives only on the
    primary checkout); passing a STATUS-partition kind would route the default
    arm through the topology-aware seam instead and is a caller error.
    """
    from specify_cli.missions._read_path_resolver import (
        compose_meta_json_path,
        resolve_planning_read_dir,
    )

    # Explicit ``Path`` binds absorb the ``Any`` the ``specify_cli.*`` package
    # boundary erases these returns to (follow_imports=skip) — mirroring the
    # existing typed-local pattern elsewhere in this module.
    if effective_root is None:
        planning_dir: Path = resolve_planning_read_dir(primary_root, mission_slug, kind=kind, resolver=resolver)
        return planning_dir
    meta_dir: Path = compose_meta_json_path(effective_root, mission_slug).parent
    return meta_dir


def build_execution_context(
    **fields: Any,
) -> MissionExecutionContext:
    """Construct the ONE :class:`MissionExecutionContext` — the sole construction door.

    This is the **package-private** single factory for the canonical context
    composite (D-6 / IC-01 / C-001 — no new public symbol; it is not exported
    from :mod:`mission_runtime`). :func:`resolve_action_context` delegates every
    construction here; there is exactly one ``MissionExecutionContext(`` call in
    production code (this body). The composite is frozen, so callers assemble all
    fields up front and never patch a built context.

    Build-time invariant (C-IC01 / FR-009 / D-2): when a ``branch_ref`` fragment
    is supplied, ``target_branch`` MUST equal ``branch_ref.target_branch``; on
    mismatch this raises ``ActionContextError("CONTEXT_INVARIANT_VIOLATION", …)``
    naming both values. The invariant is **never** asserted against
    ``branch_name`` — the WP lane branch legitimately differs from the mission
    target branch (D-2 supersedes the spec's original FR-009 wording).

    Write-projection boundary contract (D-6): write surfaces compose
    names/paths/identity from the factory-projected :class:`IdentityFragment` +
    :class:`BranchRefFragment` (+ workspace/surface); they **MUST NOT** re-derive
    ``mission_id`` / ``mid8`` / ``primary_root`` independently. ``branch_naming``
    is the grammar collaborator the resolver *calls*; the factory is the
    identity/topology authority that feeds it. The deferred write-side
    (#1716 / #1878, Mission B) adopts against this frozen seam — not a rewrite.
    """
    context = MissionExecutionContext(**fields)
    branch_ref = context.branch_ref
    if branch_ref is not None and context.target_branch != branch_ref.target_branch:
        raise ActionContextError(
            "CONTEXT_INVARIANT_VIOLATION",
            "MissionExecutionContext.target_branch "
            f"({context.target_branch!r}) must equal branch_ref.target_branch "
            f"({branch_ref.target_branch!r}); the composite is internally "
            "inconsistent (FR-009 / C-IC01).",
        )
    return context


def resolve_context_for_mission(
    mission_id: str,
    topology: MissionTopology,
    *,
    action: ActionName,
    mission_slug: str,
    feature_dir: str,
    target_branch: str,
    identity: IdentityFragment,
    branch_ref: BranchRefFragment,
    status_surface: StatusSurfaceFragment | None = None,
    workspace: WorkspaceFragment | None = None,
    coordination_branch_signal: str | None = None,
    has_lanes_signal: bool | None = None,
    **extra_fields: Any,
) -> MissionExecutionContext:
    """PURE projection of an :class:`MissionExecutionContext` from stored topology (FR-004).

    The **functional core** of the single planning-surface authority. Given a
    mission identity + the WP02 **stored** :class:`MissionTopology` (read from
    ``meta.json`` by the imperative shell) and the shell-assembled fragments, it
    projects exactly one :class:`MissionExecutionContext` through the PURE construction
    door :func:`build_execution_context` (``resolution.py`` factory). It performs
    **zero** filesystem or git I/O (NFR-005): there is no ``open`` / ``read_text``
    / ``load_meta`` / ``subprocess`` / ``git`` / ``*.exists()`` / ``*.stat()`` /
    ``_assemble_core_fragments`` call in this body — every such read happens in the
    shell BEFORE the resolver and arrives as an argument.

    Placement (C-001 / FR-004 / FR-001b): the destination/placement ref is a
    ref-only :class:`CommitTarget` (C-007) — the coord-routing decision is read
    from the stored ``topology`` via :func:`routes_through_coordination`, never
    from a retired per-ref enum. The supplied ``branch_ref.destination_ref`` is
    carried through unchanged, and the matching
    :class:`ArtifactPlacementFragment` shares that one ``CommitTarget`` (C-PLACE-1).

    C-003 (binding): this is a **thin projection over the PURE door**, sharing
    :func:`resolve_placement_only`'s narrow-projection *discipline* while sitting
    one layer UP. ``resolve_placement_only`` is the imperative SHELL — it itself
    calls :func:`_assemble_core_fragments` (FS/git) and projects the
    ``destination_ref`` out of those fragments. This resolver does NOT call
    ``_assemble_core_fragments`` or any reader: the shell assembles the fragments
    + reads the stored ``topology`` and threads them in; the resolver projects
    only :func:`build_execution_context`. That separation is what makes the
    zero-fixture purity test possible (T018 / SC-002).

    Optional input-assertion (T016 / C-003 spirit, fail-closed): when the shell
    ALSO supplies the structured ``coordination_branch_signal`` /
    ``has_lanes_signal`` it already read, and the **supplied** ``topology``
    disagrees with what those signals would classify, this raises
    ``ActionContextError("TOPOLOGY_INPUT_MISMATCH", …)`` naming BOTH topologies. It
    is an assertion over shell-provided inputs, NOT a disk re-derivation — the
    resolver stays pure. When the corroborating signals are not supplied the guard
    is skipped cleanly, so pure callers passing only the topology are unaffected.

    Args:
        mission_id: The canonical mission identity (already resolved by the shell).
        topology: The WP02 stored mission topology (authoritative input).
        action: The action name the context is resolved for.
        mission_slug: The mission directory name / slug.
        feature_dir: The resolved mission feature directory (string substrate).
        target_branch: The mission target branch (resolved once by the shell).
        identity: Shell-assembled identity fragment.
        branch_ref: Shell-assembled branch-ref fragment; its ref-only
            ``destination_ref`` is carried through unchanged (C-007).
        status_surface: Shell-assembled status-surface fragment (optional).
        workspace: Shell-assembled workspace fragment (optional).
        coordination_branch_signal: Raw coordination-branch value the shell read,
            supplied ONLY to corroborate the topology (optional T016 guard).
        has_lanes_signal: Whether the mission has lanes, supplied ONLY to
            corroborate the topology (optional T016 guard).
        **extra_fields: Additional flat-substrate fields forwarded to the factory.

    Returns:
        The single projected :class:`MissionExecutionContext`.

    Raises:
        ActionContextError: ``TOPOLOGY_INPUT_MISMATCH`` when the optional
            corroborating signals contradict the supplied topology, or
            ``CONTEXT_INVARIANT_VIOLATION`` from the door.
    """
    if mission_id != identity.mission_id:
        raise ActionContextError(
            "TOPOLOGY_INPUT_MISMATCH",
            f"mission_id {mission_id!r} does not match identity fragment mission_id {identity.mission_id!r}; the shell threaded inconsistent identity inputs.",
        )
    _assert_topology_corroborated(
        topology,
        coordination_branch_signal=coordination_branch_signal,
        has_lanes_signal=has_lanes_signal,
    )

    # ``CommitTarget`` is a ref-only carrier (C-007 / FR-001b): the coord-routing
    # decision is read from the stored ``topology`` via
    # :func:`routes_through_coordination`, never from a ref-local enum, so the
    # destination ref the shell already resolved is carried through unchanged and
    # the artifact placement shares that one ``CommitTarget`` (C-PLACE-1).
    destination_ref = branch_ref.destination_ref
    projected_branch_ref = branch_ref
    artifact_placement = ArtifactPlacementFragment(placement_ref=destination_ref)

    return build_execution_context(
        action=action,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
        target_branch=target_branch,
        detection_method="explicit",
        identity=identity,
        branch_ref=projected_branch_ref,
        status_surface=status_surface,
        workspace=workspace,
        artifact_placement=artifact_placement,
        **extra_fields,
    )


def _assert_topology_corroborated(
    topology: MissionTopology,
    *,
    coordination_branch_signal: str | None,
    has_lanes_signal: bool | None,
) -> None:
    """Fail closed when supplied topology disagrees with corroborating signals.

    The T016 optional input-assertion. Skipped cleanly when ``has_lanes_signal``
    is ``None`` (the shell did not supply corroborating structured signals), so a
    pure caller passing only ``(mission_id, topology)`` is unaffected. This is an
    assertion over shell-provided inputs — it does NOT read disk (the resolver
    stays pure); it imports the WP01 :func:`classify_topology` authority to
    compute the signal-implied topology rather than re-implementing the 2×2 grid.
    """
    if has_lanes_signal is None:
        return
    from mission_runtime.context import classify_topology

    implied = classify_topology(coordination_branch_signal, has_lanes_signal)
    if implied is not topology:
        raise ActionContextError(
            "TOPOLOGY_INPUT_MISMATCH",
            f"supplied topology {topology.value!r} disagrees with the topology "
            f"{implied.value!r} implied by the corroborating signals "
            f"(coordination_branch={coordination_branch_signal!r}, "
            f"has_lanes={has_lanes_signal!r}); refusing to silently prefer one "
            "(C-003 fail-closed).",
        )


def _resolve_mission_slug(
    repo_root: Path,
    *,
    feature: str | None,
    cwd: Path | None,  # noqa: ARG001 -- kept for signature compatibility
    env: Mapping[str, str] | None,  # noqa: ARG001 -- kept for signature compatibility
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> tuple[str, Path]:
    """Resolve the CANONICAL mission slug and read-side directory.

    Mission directory resolution is CWD-independent and topology-aware
    (WP08 T037, FR-030): for missions on the coord-branch topology the
    returned ``feature_dir`` points into the coordination worktree;
    for legacy missions it points into the primary checkout.  The
    caller never has to guess which view the operator is sitting in.

    The returned slug is the canonical mission-dir name (the resolved
    directory's name), NOT the raw operator handle: a bare ``mid8`` or
    numeric-prefix handle must yield the SAME identity, status surface,
    and placement as the full slug (F-001), so the raw handle never
    flows into downstream compositions.

    Raises ActionContextError if feature is not provided or the mission
    directory cannot be located in either view.

    ``resolver`` (mission-resolver-port-01KX1C05 WP03, FR-002): optional
    :class:`MissionResolver` threaded down to :func:`resolve_handle_to_read_path`
    and, through it, to the canonicalizer chain's single walk. This is the
    trunk seam — every caller of :func:`resolve_action_context` that injects a
    ``resolver`` (e.g. a ``FakeMissionResolver`` in a test) reaches the walk with
    no bypass. ``None`` preserves historical behaviour (a fresh
    ``FsMissionResolver`` is constructed at the free ``resolve_mission`` call
    site in ``specify_cli.context.mission_resolver``).
    """
    from specify_cli.core.paths import require_explicit_feature

    try:
        slug = require_explicit_feature(feature, command_hint="--mission <slug>")
    except ValueError as exc:
        raise ActionContextError(_FEATURE_CONTEXT_UNRESOLVED_CODE, str(exc)) from exc

    # Route through the SINGLE guarded read-side seam (WP01 reroute, IC-01 /
    # FR-001): ``resolve_handle_to_read_path`` owns the primary-meta probe AND
    # the ONE sanctioned mid8 cascade internally, so this caller no longer
    # pre-derives the mid8 (``mid8_from_slug`` → ``_mid8_from_primary_meta``).
    # Byte-identical: the seam runs the same cascade and forwards the result to
    # the existence-gated topology resolver. Handle forms (bare mid8, numeric
    # prefix, ULID) are canonicalized inside the seam itself.
    #
    # Late import to avoid a hard module-load dependency for legacy consumers of
    # the resolver that pre-date its introduction.
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
        resolve_handle_to_read_path,
    )

    try:
        feature_dir = resolve_handle_to_read_path(
            effective_root or repo_root,
            slug,
            resolver=resolver,
        )
    except StatusReadPathNotFound as exc:
        # Boundary translation (PR #1850 M6): the read resolver's fail-closed
        # refusal (coord worktree root materialized without the mission dir)
        # must surface as the single consumer-facing error type, preserving
        # the refusal message — never a raw specify_cli exception.
        raise ActionContextError(exc.error_code, str(exc)) from exc
    except MissionSelectorAmbiguous as exc:
        # Boundary translation (WP05 / FR-005 / #2010 bug #15): an ambiguous
        # handle propagates as a raw specify_cli exception if uncaught here.
        # Translate to the single consumer-facing type preserving the stable
        # error code (MISSION_AMBIGUOUS_SELECTOR) — never a silent fallback.
        raise ActionContextError(exc.error_code, str(exc)) from exc
    if not feature_dir.exists():
        raise ActionContextError(
            _FEATURE_CONTEXT_UNRESOLVED_CODE,
            f"Mission directory not found: {feature_dir}. Check that '{slug}' is the correct mission slug.",
        )
    # Parse, don't re-derive: the resolved directory's name IS the canonical
    # mission slug (identical in the coord-worktree and primary views).
    return feature_dir.name, feature_dir


def _mid8_from_primary_meta(repo_root: Path, mission_slug: str) -> str:
    """Canonical mid8 for a slug whose name carries no parseable suffix.

    Reads the primary-checkout ``meta.json`` and runs the ONE sanctioned mid8
    cascade (:func:`resolve_declared_mid8`, NFR-005/#1868) instead of a
    hand-rolled ``meta.mid8`` → ``mission_id[:8]`` parallel impl (FR-002, C-007).
    Returns ``""`` when no identity-bearing meta exists (raw handles, scaffolds,
    pre-identity legacy missions), preserving the literal-slug behaviour.

    Subsumption note (T013): the retired body derived ``meta.mid8`` first, then
    ``resolve_mid8(slug, mission_id)`` under a ``len >= 8`` guard, returning
    ``""`` otherwise — exactly the first two tiers of ``resolve_declared_mid8``.

    WP01 reroute note: ``_resolve_mission_slug`` now routes through
    ``resolve_handle_to_read_path`` (which runs the same cascade internally), so
    this helper is no longer on that call path. It is retained as a directly
    tested primitive (``test_mid8_direct_routing.py``,
    ``test_read_path_resolver_validation.py``); collapsing it is a separate tidy.

    FR-007 / #3162: the meta read is routed through the ONE fail-closed reader
    (:func:`specify_cli.core.paths.load_meta_fail_closed`), so a corrupt
    ``meta.json`` degrades to ``""`` via the typed
    :class:`MissionMetaReadError` arm instead of a raw ``ValueError`` — the same
    phase-probe carve-out ``lifecycle_phase._read_baseline_merge_commit`` uses.
    """
    from specify_cli.coordination.surface_resolver import resolve_declared_mid8
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
    from specify_cli.missions._read_path_resolver import (
        _canonicalize_primary_read_handle,
        _compose_primary_feature_dir,
    )

    # FR-006: canonical reader contract (a) — None on a missing file, typed
    # MissionMetaReadError on malformed (routed, #3162); the malformed arm below
    # reproduces the historical malformed→"" degrade. The compose-step guard is
    # kept SEPARATE from the read: its ``except ValueError`` also swallows the
    # path-traversal-guard ``ValueError`` (``assert_safe_path_segment``) raised
    # inside ``_compose_primary_feature_dir`` above, degrading an unsafe segment
    # to ``""`` the same way a malformed meta.json does.
    # ``MissionSelectorAmbiguous`` (raised by ``_canonicalize_primary_read_handle``)
    # is NOT a ``ValueError`` and correctly still propagates uncaught.
    # WP05/FR-005: extract to local so the canonicalized handle feeds the reader.
    # WP03 T016 (read-side-seam-primary-primitive-closure-01KYKMMT): calls the
    # module-private leaf directly, not the public wrapper — the wrapper now
    # (T019) delegates to the seam, which reaches this module's callers again
    # (Ledger M16 recursion guard).
    try:
        primary_dir = _compose_primary_feature_dir(
            repo_root,
            _canonicalize_primary_read_handle(repo_root, mission_slug),
        )
    except ValueError:
        return ""
    try:
        meta = load_meta_fail_closed(primary_dir)
    except MissionMetaReadError:
        return ""
    if not meta:
        return ""
    # ``follow_imports=skip`` on ``specify_cli.*`` erases the str return across
    # the package boundary, so bind explicitly.
    resolved: str = resolve_declared_mid8(meta, mission_slug)
    return resolved


def _tasks_commands(mission_slug: str) -> dict[str, str]:
    return {
        "check_prerequisites": (f"spec-kitty agent mission check-prerequisites --json --paths-only --include-tasks --mission {mission_slug}"),
        "finalize_tasks": (f"spec-kitty agent mission finalize-tasks --mission {mission_slug} --json"),
    }


def _wp_workflow_commands(
    *,
    action: ActionName,
    wp_id: str,
    mission_slug: str,
    agent: str | None,
) -> dict[str, str]:
    """Compute the action-specific ``commands`` for a WP-bearing context.

    Built up-front (not patched onto a built context) so the single
    construction door (``build_execution_context``) is fed the complete
    ``commands`` mapping — the frozen composite forbids the historical
    ``context.commands["workflow"] = …`` post-build dict-write (T005).
    """
    verb = "implement" if action == "implement" else "review"
    workflow = f"spec-kitty agent action {verb} {wp_id}"
    if agent:
        workflow += f" --agent {agent}"
    commands = {"workflow": workflow}
    if action != "implement":
        commands["approve"] = f'spec-kitty agent tasks move-task {wp_id} --to approved --mission {mission_slug} --note "Review passed: <summary>"'
        commands["reject"] = f"spec-kitty agent tasks move-task {wp_id} --to planned --review-feedback-file <feedback-file> --mission {mission_slug}"
    return commands


def _resolve_wp_lane(
    feature_dir: Path,
    wp_id: str,
    *,
    resolve_lane_alias: Callable[[str], str],
    planned_lane: str,
) -> str:
    """Resolve a WP's lane from the canonical event log (FR-011).

    WPs without a canonical event yet (or with the ``uninitialized`` sentinel)
    are treated as ``planned`` so legacy missions that have not emitted events
    for every WP still resolve.
    """
    from specify_cli.status import CanonicalStatusNotFoundError
    from specify_cli.status import get_wp_lane as _ec_get_wp_lane

    try:
        raw_lane = str(_ec_get_wp_lane(feature_dir, wp_id))
    except CanonicalStatusNotFoundError:
        raw_lane = planned_lane
    except Exception as exc:
        raise ActionContextError("CANONICAL_STATUS_UNREADABLE", str(exc)) from exc
    if raw_lane == "uninitialized":
        raw_lane = planned_lane
    return resolve_lane_alias(raw_lane)


def _resolve_wp_bearing_fields(
    repo_root: Path,
    *,
    action: ActionName,
    mission_slug: str,
    feature_dir: Path,
    wp_id: str | None,
    agent: str | None,
    locate_work_package: Callable[..., Any],
    parse_wp_dependencies: Callable[[Path], list[str]],
    resolve_workspace_for_wp: Callable[..., Any],
    resolve_lane_alias: Callable[[str], str],
    planned_lane: str,
) -> dict[str, Any]:
    """Assemble the WP-bearing fields (incl. ``commands``) for one build call.

    Returns the field mapping the factory consumes; performs NO construction or
    post-build mutation (T005 — verification-by-deletion of the ``:800-808``
    mutator and the ``commands["workflow"] =`` dict-write).
    """
    normalized_wp_id = _resolve_wp_id(action, feature_dir, wp_id)
    if normalized_wp_id is None:
        raise ActionContextError(
            "WORK_PACKAGE_UNRESOLVED",
            f"No work package available for action '{action}' in feature {mission_slug}.",
        )

    try:
        wp = locate_work_package(repo_root, mission_slug, normalized_wp_id)
    except Exception as exc:
        raise ActionContextError("WORK_PACKAGE_UNRESOLVED", str(exc)) from exc

    dependencies = parse_wp_dependencies(wp.path)
    lane = _resolve_wp_lane(
        feature_dir,
        normalized_wp_id,
        resolve_lane_alias=resolve_lane_alias,
        planned_lane=planned_lane,
    )
    wp_workspace = resolve_workspace_for_wp(repo_root, mission_slug, normalized_wp_id)

    return {
        "wp_id": normalized_wp_id,
        "wp_file": str(wp.path),
        "lane": lane,
        "lane_id": wp_workspace.lane_id,
        "branch_name": wp_workspace.branch_name,
        "execution_mode": wp_workspace.execution_mode,
        "resolution_kind": wp_workspace.resolution_kind,
        "dependencies": dependencies,
        "workspace_path": str(wp_workspace.worktree_path),
        "commands": _wp_workflow_commands(
            action=action,
            wp_id=normalized_wp_id,
            mission_slug=mission_slug,
            agent=agent,
        ),
    }


def _find_first_wp(feature_dir: Path, lane: str) -> str | None:
    """Find the first WP with the given lane from the canonical event log."""
    import re as _re
    from specify_cli.status import CanonicalStatusNotFoundError
    from specify_cli.status import Lane
    from specify_cli.status import get_wp_lane
    from specify_cli.status import resolve_lane_alias

    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return None

    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        wp_match = _re.match(r"(WP\d+)", wp_file.stem)
        if wp_match is None:
            continue
        wp_id = wp_match.group(1)
        try:
            wp_lane_raw = str(get_wp_lane(feature_dir, wp_id))
        except CanonicalStatusNotFoundError:
            wp_lane_raw = Lane.PLANNED
        # WPs with no canonical event yet (or an "uninitialized" sentinel) are
        # treated as planned for the purposes of "find the first WP in this
        # lane". This matches the legacy ``event_log_lanes.get(wp_id, "planned")``
        # fallback that previous iterations used and keeps zero-migration
        # support (FR-019) intact for missions that have not emitted events for
        # every WP.
        if wp_lane_raw == "uninitialized":
            wp_lane_raw = Lane.PLANNED
        wp_lane = resolve_lane_alias(wp_lane_raw)
        if wp_lane == lane:
            return wp_id
    return None


def _resolve_review_wp_id(feature_dir: Path) -> str | None:
    """Find the WP to review: first ``for_review``, else a review-claimed WP."""
    from specify_cli.status import CanonicalStatusNotFoundError
    from specify_cli.status import Lane
    from specify_cli.status import get_wp_lane
    from specify_cli.status import read_events
    from specify_cli.task_utils import extract_scalar, split_frontmatter

    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return None

    try:
        events = read_events(feature_dir)

        candidate_wp_ids = _review_candidate_wp_ids(
            tasks_dir,
            extract_scalar=extract_scalar,
            split_frontmatter=split_frontmatter,
        )

        review_ready_wp_id = _first_wp_in_lane(
            feature_dir,
            candidate_wp_ids,
            target_lane=Lane.FOR_REVIEW,
            get_wp_lane=get_wp_lane,
        )
        if review_ready_wp_id is not None:
            return review_ready_wp_id

        for candidate_wp_id in candidate_wp_ids:
            candidate_lane = get_wp_lane(feature_dir, candidate_wp_id)
            if candidate_lane not in (Lane.IN_PROGRESS, Lane.IN_REVIEW):
                continue
            if _is_review_claimed(events, candidate_wp_id, Lane=Lane):
                return candidate_wp_id
    except CanonicalStatusNotFoundError as exc:
        raise ActionContextError("CANONICAL_STATUS_NOT_FOUND", str(exc)) from exc
    except ActionContextError:
        raise
    except Exception:
        return None
    return None


def _review_candidate_wp_ids(
    tasks_dir: Path,
    *,
    extract_scalar: Callable[[str, str], str | None],
    split_frontmatter: Callable[[str], tuple[str, str, str]],
) -> list[str]:
    candidate_wp_ids: list[str] = []
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        frontmatter = split_frontmatter(wp_file.read_text(encoding="utf-8-sig"))[0]
        candidate_wp_id = extract_scalar(frontmatter, "work_package_id")
        if candidate_wp_id:
            candidate_wp_ids.append(str(candidate_wp_id))
    return candidate_wp_ids


def _first_wp_in_lane(
    feature_dir: Path,
    candidate_wp_ids: list[str],
    *,
    target_lane: object,
    get_wp_lane: Callable[[Path, str], object],
) -> str | None:
    for candidate_wp_id in candidate_wp_ids:
        if get_wp_lane(feature_dir, candidate_wp_id) == target_lane:
            return candidate_wp_id
    return None


def _is_review_claimed(events: Sequence[Any], candidate_wp_id: str, *, Lane: Any) -> bool:
    latest_event = next(
        (event for event in reversed(events) if getattr(event, "wp_id", None) == candidate_wp_id),
        None,
    )
    if latest_event is None:
        return False
    return bool(latest_event.to_lane == Lane.IN_REVIEW or (latest_event.to_lane == Lane.IN_PROGRESS and latest_event.review_ref == "action-review-claim"))


def _resolve_wp_id(
    action: ActionName,
    feature_dir: Path,
    explicit_wp_id: str | None,
) -> str | None:
    from specify_cli.status import Lane

    if explicit_wp_id:
        return explicit_wp_id.upper().split("-", 1)[0]

    if action == "implement":
        for lane in (Lane.PLANNED, Lane.IN_PROGRESS):
            wp_id = _find_first_wp(feature_dir, lane)
            if wp_id:
                return wp_id
        return None

    if action == "review":
        return _resolve_review_wp_id(feature_dir)

    return None


def _resolve_coordination_branch(
    primary_root: Path,
    mission_slug: str,
    *,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> str | None:
    """Read the mission ``coordination_branch`` from meta (canonical anchor).

    Returns ``None`` under flattened topology (no separate coordination branch,
    C-001). Anchored on the canonical *primary* dir so the value is identical
    from any CWD (never trust a lane-supplied surface — WP02 carry-forward).

    FR-003 / C-GUARD-3a (coord-topology placement regression fix): ``meta.json``
    is written by ``mission create`` and only ever lives on the PRIMARY checkout.
    Reading it through the topology-aware ``candidate_feature_dir_for_mission``
    selected the coordination worktree once one was materialized — and that
    worktree's ``kitty-specs/<slug>/`` dir carries no ``meta.json`` — so the
    coordination branch read back as ``None`` and the placement *kind* flipped
    from COORDINATION to FLATTENED depending on whether a coord worktree existed.
    That made the single placement authority CWD/topology-DEPENDENT (e.g.
    ``setup-plan`` resolved COORDINATION and committed plan.md to the coord
    worktree, while ``finalize-tasks`` later resolved FLATTENED and committed to
    the target branch — a split-brain). The fix is to anchor the ``meta.json``
    read on the topology-BLIND primary constructor (the SAME anchoring
    ``finalize-tasks`` uses for its merge-target read), restoring a CWD-invariant
    placement with NO second destination authority.
    """
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    # WP01 (#3373, T004): the effective-root read fork is consolidated into the
    # single ``read_dir_for`` authority. PRIMARY_METADATA is a PRIMARY-partition
    # kind, so the default arm stays byte-identical to the prior
    # ``_compose_primary_feature_dir(_canonicalize_primary_read_handle(...))``
    # (resolver threaded to the same single injected walk — WP03/FR-002), and the
    # opted-in arm to ``compose_meta_json_path(effective_root, …).parent``. This
    # read feeds the seam's classification decision (it produces the raw
    # ``coordination_branch`` routing signal) rather than recursing through it, so
    # there is no cycle.
    primary_dir = read_dir_for(
        effective_root,
        primary_root,
        mission_slug,
        kind=MissionArtifactKind.PRIMARY_METADATA,
        resolver=resolver,
    )
    # FR-006: canonical reader contract (a) — None on missing, typed
    # MissionMetaReadError on malformed (routed through the ONE fail-closed
    # reader, FR-007 / #3162); the malformed arm below keeps the historical
    # degrade-to-undeclared answer.
    try:
        meta = load_meta_fail_closed(primary_dir)
    except MissionMetaReadError:
        # Malformed meta: treat coordination topology as undeclared. Downstream
        # surface resolution reports the same condition consistently.
        return None
    if not meta:
        return None
    raw = meta.get("coordination_branch")
    return str(raw) if raw else None


def _resolve_topology(
    primary_root: Path,
    mission_slug: str,
    *,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> MissionTopology:
    """Read the WP02 **stored** :class:`MissionTopology` from meta (PURE shell read).

    The imperative-shell topology read: anchored on the canonical PRIMARY dir
    (where ``meta.json`` lives, mirroring :func:`_resolve_coordination_branch`)
    and delegated to WP02's :func:`read_topology` — the **pure** stored-topology
    reader. It returns the stored value when present and derives the shape ONCE
    (via WP01's :func:`classify_topology`) for a pre-WP02 mission, **without ever
    writing** — so a READ path (``resolve_action_context`` for finalize
    ``--validate-only`` / accept-readiness / a transactional read) never mutates
    ``meta.json`` (the read-only contract, #1814). Persisting the back-fill is the
    job of the explicit ``ensure_topology`` mint / ``migrate backfill-topology``
    command, never an incidental read side effect. Falls back to the
    ``(coordination_branch, has_lanes=False)`` classification when ``meta.json`` is
    absent/malformed so bootstrap windows still resolve a stable shape.
    """
    from mission_runtime.context import classify_topology
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.migration.backfill_topology import read_topology

    # WP01 (#3373, T004): consolidated through the single ``read_dir_for`` fork
    # authority (byte-identical arms; resolver threaded to the same single
    # injected walk — WP03/FR-002). This IS the pure shell read
    # ``declared_read_surface`` calls (via the public ``resolve_topology``) to
    # produce the PRIMARY/COORD signal for a coord-partition kind — it precedes
    # and feeds that decision rather than routing through it, so there is no cycle.
    primary_dir = read_dir_for(
        effective_root,
        primary_root,
        mission_slug,
        kind=MissionArtifactKind.PRIMARY_METADATA,
        resolver=resolver,
    )
    try:
        stored: MissionTopology = read_topology(primary_dir)
        return stored
    except (FileNotFoundError, ValueError, MissionMetaReadError):
        # No persisted meta yet (bootstrap window) or malformed: classify from the
        # coordination-branch value-read with no lanes signal. This is the same
        # degraded-but-stable shape the surface resolver reports for the window.
        coordination_branch = _resolve_coordination_branch(
            primary_root,
            mission_slug,
            resolver=resolver,
            effective_root=effective_root,
        )
        return classify_topology(coordination_branch, has_lanes=False)


def resolve_topology(repo_root: Path, mission_handle: str, *, resolver: MissionResolver | None = None) -> MissionTopology:
    """Public seam: read the WP02 **stored** :class:`MissionTopology` for a mission.

    The single public entry point a caller uses to obtain the stored topology so
    it can route through the ONE canonical :func:`routes_through_coordination`
    predicate (FR-005 / FR-001b) — replacing the retired per-ref ``.kind`` arm
    that once let the predicate take a ``CommitTarget``.

    The operator ``mission_handle`` is canonicalized FIRST (bare mid8 / numeric
    prefix → the full ``<slug>-<mid8>`` dir name), EXACTLY as
    :func:`resolve_placement_only` does, so a coord-topology mission addressed by a
    bare handle is NOT mis-classified as a coord-less primary surface (the #1784
    flip class). After canonicalization it delegates to the same pure
    :func:`_resolve_topology` shell read the full resolver uses, so the value is
    byte-identical to what ``resolve_placement_only`` / ``_assemble_core_fragments``
    derive for the same mission (no second derivation). A pure READ — it never
    writes ``meta.json`` (#1814). When the handle does not resolve, the raw handle
    passes through and the topology degrades exactly as the full resolver does.
    """
    from specify_cli.core.paths import get_main_repo_root
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
        candidate_feature_dir_for_mission,
    )

    primary_root = get_main_repo_root(repo_root)
    mission_slug = mission_handle
    try:
        candidate_dir = candidate_feature_dir_for_mission(repo_root, mission_handle, resolver=resolver)
    except (StatusReadPathNotFound, MissionSelectorAmbiguous):
        # Unresolvable / ambiguous handle: pass the raw handle through so the
        # topology degrades exactly as the full resolver does for a missing mission
        # (the routing caller already tolerates a degraded shape).
        candidate_dir = None
    if candidate_dir is not None and candidate_dir.exists():
        mission_slug = candidate_dir.name
    return _resolve_topology(primary_root, mission_slug, resolver=resolver)


def mission_context_for(
    repo_root: Path,
    mission_handle: str,
    topology: MissionTopology | None = None,
    *,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> MissionContext:
    """Resolve mission artifact context by mission + topology.

    This is the mission-level SSOT facade for callers that need artifact
    placement but should not know whether that means primary checkout,
    coordination worktree, or a flattened single dir. Callers pass mission
    identity and, when already known, stored topology; they then ask the returned
    context for ``artifact(MissionArtifactKind.X)``.

    ``resolver`` (mission-resolver-port-01KX1C05 WP03, FR-002): optional
    :class:`MissionResolver` threaded to every downstream canonicalizer call in
    this function's body so no read path bypasses the injected walk. ``None``
    preserves historical behaviour.

    ``effective_root`` (owned mode): the already-validated owned checkout
    root. When set, ``repo_root`` is vestigial — it does not participate in
    the derivation (#3862 item B; see the pinned invariance note at the
    ``primary_root`` fold below).
    """
    from specify_cli.core.paths import get_feature_target_branch
    from specify_cli.core.paths import get_main_repo_root
    from specify_cli.mission import get_mission_type
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
        candidate_feature_dir_for_mission,
    )

    if not mission_handle or not mission_handle.strip():
        raise ActionContextError(
            _FEATURE_CONTEXT_UNRESOLVED_CODE,
            "mission_context_for requires an explicit mission handle.",
        )

    # The default path retains the historical primary-checkout fold exactly.
    # An owned-checkout caller instead threads the root already validated by
    # ``resolve_ownership_claim``. Folding it through ``get_main_repo_root``
    # would silently cross-read a sibling checkout (#3328 / C-002).
    #
    # #3862 item B: on the owned arm (``effective_root is not None``) the
    # ``repo_root`` parameter is VESTIGIAL — it does not participate in this
    # derivation at all, which is why callers may legitimately pass either
    # ``owned.primary`` or ``owned.root`` (or a CWD-derived root) without the
    # answer changing. That invariance is a pinned contract, not an accident:
    # ``tests/mission_runtime/test_owned_single_branch_ssot.py`` fails if a
    # future edit makes ``repo_root`` load-bearing here, forcing the
    # inconsistent caller pairings to be reconciled first.
    primary_root = get_main_repo_root(repo_root) if effective_root is None else effective_root.resolve()
    try:
        candidate_dir = candidate_feature_dir_for_mission(primary_root, mission_handle, resolver=resolver)
    except StatusReadPathNotFound as exc:
        raise ActionContextError(exc.error_code, str(exc)) from exc
    except MissionSelectorAmbiguous as exc:
        raise ActionContextError(exc.error_code, str(exc)) from exc

    mission_slug = candidate_dir.name if candidate_dir.exists() else mission_handle
    resolved_topology = topology or _resolve_topology(
        primary_root,
        mission_slug,
        resolver=resolver,
        effective_root=effective_root,
    )
    # WP01 (#3373, T004): consolidated through the single ``read_dir_for`` fork
    # authority. ``effective_root`` arrives already resolved (validated by
    # ``resolve_ownership_claim``), so composing meta against it is byte-identical
    # to the prior ``compose_meta_json_path(primary_root, …)`` (``primary_root ==
    # effective_root.resolve()`` on this arm).
    primary_read_dir = read_dir_for(
        effective_root,
        primary_root,
        mission_slug,
        kind=MissionArtifactKind.PRIMARY_METADATA,
        resolver=resolver,
    )
    if effective_root is None:
        target_branch = get_feature_target_branch(primary_root, mission_slug)
    else:
        # The legacy helper deliberately folds a generic worktree to the
        # ambient primary checkout. The opted-in path reads only the validated
        # checkout's meta and derives its fallback branch from that checkout.
        from specify_cli.core.git_ops import resolve_primary_branch
        from specify_cli.core.paths import read_target_branch_from_meta

        stored_target = read_target_branch_from_meta(primary_read_dir)
        target_branch = stored_target or str(resolve_primary_branch(primary_root))
    _identity, branch_ref, status_surface, _workspace = _assemble_core_fragments(
        primary_root,
        mission_slug=mission_slug,
        target_branch=target_branch,
        topology=resolved_topology,
        cwd=None,
        resolver=resolver,
        effective_root=effective_root,
    )
    artifacts: list[MissionArtifactContext] = []
    for kind in MissionArtifactKind:
        placement_ref = CommitTarget(ref=target_branch) if is_primary_artifact_kind(kind) else branch_ref.destination_ref
        home = artifact_home_for(kind, placement_ref)
        read_dir = primary_read_dir if home.read_surface == TopologySurface.PRIMARY else status_surface.status_read_dir
        write_dir = primary_read_dir if home.write_surface == TopologySurface.PRIMARY else status_surface.status_write_dir
        artifacts.append(
            MissionArtifactContext(
                kind=kind,
                read_dir=read_dir,
                write_dir=write_dir,
                commit_target=home.commit_target,
            )
        )
    return MissionContext(
        mission_slug=mission_slug,
        mission_type=get_mission_type(primary_read_dir),
        topology=resolved_topology,
        artifacts=tuple(artifacts),
    )


def _resolve_mission_id(
    primary_root: Path,
    mission_slug: str,
    *,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> str:
    """Resolve the canonical ``mission_id`` for the mission.

    Reads ``meta.json`` at the canonical primary dir. Falls back to a
    ``legacy-<slug>`` sentinel (mirroring ``status_transition`` identity
    resolution) so pre-identity missions still resolve a stable, CWD-invariant
    value — ``mid8`` is then derived once from that value (FR-012 / C-CTX-3).

    FR-003 / C-GUARD-3a: ``meta.json`` only ever lives on the PRIMARY checkout,
    so the read is anchored on the topology-blind primary constructor — the
    coord-aware resolver would return the (meta-less) coordination worktree once
    one exists and spuriously degrade to the ``legacy-`` sentinel (see
    :func:`_resolve_coordination_branch` for the full split-brain rationale).

    ``resolver`` (WP03, FR-002/D-07 — the sentinel carve-out): threaded to
    :func:`_canonicalize_primary_read_handle` ONLY, so an injected resolver
    still governs handle canonicalization here. The ``legacy-<slug>`` bootstrap
    branch below is a DELIBERATE, documented pre-identity carve-out and stays
    OUTSIDE the port: it is never rewritten to call ``resolver.resolve()``
    directly and let a fail-closed ``MissionNotFoundError`` propagate. A
    brand-new scaffold or a legacy mission with no ``mission_id`` yet MUST keep
    minting the stable sentinel — that is the load-bearing behaviour a
    regression test in ``tests/mission_runtime/test_builder_fs_free_identity.py``
    pins (T014).
    """
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    # WP01 (#3373, T004): consolidated through the single ``read_dir_for`` fork
    # authority (byte-identical arms; resolver threaded to the same single
    # injected walk). This feeds the ``mid8`` its coord-state probe needs after
    # ``declared_read_surface`` has already resolved COORD — the ``legacy-<slug>``
    # sentinel carve-out below is unaffected: it fires on a malformed/absent meta
    # read, before any classification decision is even in play.
    primary_dir = read_dir_for(
        effective_root,
        primary_root,
        mission_slug,
        kind=MissionArtifactKind.PRIMARY_METADATA,
        resolver=resolver,
    )
    # FR-006: canonical reader contract (a) — None on missing, typed
    # MissionMetaReadError on malformed (routed through the ONE fail-closed
    # reader, FR-007 / #3162); the malformed arm degrades to the ``legacy-``
    # sentinel below.
    try:
        meta = load_meta_fail_closed(primary_dir)
    except MissionMetaReadError:
        meta = None
    if meta:
        raw_mission_id = meta.get("mission_id")
        if raw_mission_id:
            return str(raw_mission_id)
    return f"legacy-{mission_slug}"


def _resolve_status_surface_dir(
    primary_root: Path,
    mission_slug: str,
    topology: MissionTopology,
    *,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
    for_write: bool = False,
) -> Path:
    """Resolve the canonical status-surface DIRECTORY via WP02's resolver.

    Consumes :func:`resolve_status_surface` (IC-01) — the single status-surface
    authority — and returns the containing directory (the resolver yields the
    ``status.events.jsonl`` path). Never re-derives the surface (FR-003/#1737).
    Falls back to the canonical primary dir when meta is absent/malformed so
    bootstrap windows and ad-hoc fixtures keep resolving. The fail-closed
    surface refusal is NOT a fallback case: it translates to
    :class:`ActionContextError` (PR #1850 M6).

    The stored ``topology`` is threaded through to
    :func:`resolve_status_surface` so the PRIMARY-vs-coordination surface SHAPE is
    decided from the WP02 stored value (FR-004 / SC-001), not from a parallel
    ``coordination_branch is None`` re-inference inside the surface resolver.

    ``resolver`` (WP03, FR-002): threaded ONLY to the ``candidate_feature_dir_
    for_mission`` fallback leg below — :func:`resolve_status_surface` itself
    lives in ``coordination.surface_resolver``, outside this WP's owned files,
    and is not adopted here (a separate, later port).
    """
    from specify_cli.coordination.surface_resolver import resolve_status_surface
    from specify_cli.missions._read_path_resolver import (
        StatusReadPathNotFound,
        candidate_feature_dir_for_mission,
    )

    if effective_root is not None:
        from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
        from specify_cli.core.paths import load_meta_fail_closed
        from specify_cli.missions._read_path_resolver import (
            CoordState,
            coord_feature_dir,
            probe_coord_state,
        )

        # WP01 (#3373, T004): the effective-root meta compose routes through the
        # single ``read_dir_for`` fork authority. ``effective_root`` is non-None
        # on this arm, so it is the opted-in owned-checkout compose —
        # byte-identical to the prior ``compose_meta_json_path(effective_root,
        # …).parent``.
        primary_dir: Path = read_dir_for(
            effective_root,
            effective_root,
            mission_slug,
            kind=MissionArtifactKind.PRIMARY_METADATA,
            resolver=resolver,
        )
        # FR-007 / #3162: routed through the ONE fail-closed reader — a corrupt
        # meta.json now surfaces the typed MissionMetaReadError (previously a raw
        # ValueError); a missing file still degrades to ``{}`` (the absent arm).
        meta = load_meta_fail_closed(primary_dir) or {}
        raw_coordination_branch = meta.get("coordination_branch")
        coordination_branch = str(raw_coordination_branch) if raw_coordination_branch else None
        if not routes_through_coordination(topology) or coordination_branch is None:
            return primary_dir
        mission_id = _resolve_mission_id(
            effective_root,
            mission_slug,
            resolver=resolver,
            effective_root=effective_root,
        )
        mid8 = resolve_mid8(mission_slug, mission_id=mission_id)
        coord_dir: Path = coord_feature_dir(effective_root, mission_slug, mid8)
        coord_state = probe_coord_state(
            effective_root,
            mission_slug,
            mid8,
            coordination_branch=coordination_branch,
        )
        if coord_state is CoordState.DELETED:
            # #4403: the DELETED → build-and-raise policy routes through the ONE
            # ``CoordinationBranchDeleted.for_mission`` factory (single payload
            # authority — it composes the coord candidate itself); only this
            # site's seam-resolved ``primary_dir`` is threaded.
            raise CoordinationBranchDeleted.for_mission(
                repo_root=effective_root,
                mission_slug=mission_slug,
                mid8=mid8,
                coordination_branch=coordination_branch,
                primary_candidate=primary_dir,
            )
        if coord_state in {CoordState.EMPTY, CoordState.NONE}:
            return primary_dir
        return coord_dir

    try:
        surface = resolve_status_surface(primary_root, mission_slug, topology, for_write=for_write)
    except StatusReadPathNotFound as exc:
        # Fail closed (FR-005 / #1589 / #1821): the coord worktree root is
        # materialized but its mission dir is absent. Degrading to the primary
        # dir here would hand back the stale split-brain surface the refusal
        # exists to kill — translate to the boundary's single error type
        # instead, preserving the refusal message (PR #1850 M6).
        raise ActionContextError(exc.error_code, str(exc)) from exc
    except (FileNotFoundError, ValueError):
        fallback_dir: Path = candidate_feature_dir_for_mission(primary_root, mission_slug, resolver=resolver)
        return fallback_dir
    surface_parent: Path = surface.parent
    return surface_parent


def _assemble_workspace_fragment(
    primary_root: Path,
    *,
    mission_slug: str,
    mid8: str,
    coordination_branch: str | None,
    cwd: Path | None,
) -> WorkspaceFragment:
    """Assemble the WP05-owned WorkspaceFragment (IC-04 / C-005).

    ``primary_root`` is the canonical main-checkout root produced by the
    **single** worktree-pointer parser
    (:func:`specify_cli.core.paths.resolve_canonical_root`, which
    :func:`get_main_repo_root` feeds — IC-04). It is never the lane-supplied
    root, so it is CWD-invariant (C-CTX-2 / WP02 carry-forward): the parity
    ratchet asserts that both the primary-CWD and lane-CWD arms resolve the
    same ``primary_root``.

    ``coord_worktree`` is the per-mission coordination worktree path when the
    mission declares a coordination branch, else ``None`` under flattened
    topology (C-001). It is derived from the canonical primary root, not the
    current CWD, so it too is CWD-invariant. ``current_cwd`` records where the
    command actually runs; ``allowed_command_cwd`` is the primary-resolving
    guard CWD for surfaces that must run git ops against the main checkout.
    ``execution_workspace`` (the lane worktree for implement/review) is attached
    later by the action-specific branch when a WP is resolved.
    """
    from specify_cli.coordination.workspace import CoordinationWorkspace

    current_cwd = (cwd or primary_root).resolve()
    coord_worktree: Path | None = None
    if coordination_branch is not None:
        coord_worktree = CoordinationWorkspace.worktree_path(primary_root, mission_slug, mid8)

    return WorkspaceFragment(
        primary_root=primary_root,
        current_cwd=current_cwd,
        coord_worktree=coord_worktree,
        execution_workspace=None,
        allowed_command_cwd=primary_root,
    )


def _assemble_core_fragments(
    repo_root: Path,
    *,
    mission_slug: str,
    target_branch: str,
    topology: MissionTopology,
    cwd: Path | None,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
    for_write: bool = False,
) -> tuple[IdentityFragment, BranchRefFragment, StatusSurfaceFragment, WorkspaceFragment]:
    """Assemble the WP02/WP03/WP05-owned fragments of the op-composite (IC-02).

    This is the single fragment-assembly path (C-CTX-1): the builder derives
    each fragment's domain values exactly once and never lets a call site
    recompute them.

    * ``IdentityFragment`` — ``mid8`` single-derived as ``mission_id[:8]``.
    * ``BranchRefFragment`` — ``target_branch`` carried (already resolved once by
      the caller, FR-012); ``coordination_branch`` from meta (the value-read,
      ``None`` when flattened, C-001); ``destination_ref`` a ref-only
      :class:`CommitTarget` (C-007) whose ref is the coord branch when the
      **stored** ``topology`` routes through coordination
      (:func:`routes_through_coordination`, WP03 / FR-004) — NOT inferred from
      ``coordination_branch is None``. The shape is READ, not guessed.
    * ``StatusSurfaceFragment`` — read/write dirs from WP02's
      :func:`resolve_status_surface` (IC-01), classified by the same stored
      ``topology``; collapse to one dir absent a coord worktree.
    * ``WorkspaceFragment`` — ``primary_root`` via the single worktree-pointer
      parser (WP05 / IC-04 / C-005); CWD-invariant by construction.

    The canonical *primary* root is resolved here (never the lane-supplied root)
    so every fragment value is CWD-invariant (C-CTX-2 / WP02 carry-forward).
    ArtifactPlacement / PromptSource fragments are intentionally NOT assembled
    here — they land in WP04/06/07 (C-004 strangler ordering).

    ``topology`` (WP02 stored field) is supplied by the caller — the shell reads
    it once from ``meta.json`` (via :func:`_resolve_topology`) alongside the
    existing ``target_branch`` read and threads it in. It is the SSOT for the
    placement/surface coord-routing classification.

    ``resolver`` (WP03, FR-002): optional :class:`MissionResolver` threaded to
    every fragment-assembly helper below that canonicalizes a handle
    (:func:`_resolve_mission_id`, :func:`_resolve_coordination_branch`,
    :func:`_resolve_status_surface_dir`'s fallback leg) — the assembler itself
    performs NO construction of a resolver (it is injected at the callers, per
    the WP03 design ruling); it only forwards the one it was given. ``None``
    preserves historical behaviour end-to-end.
    """
    from specify_cli.core.paths import get_main_repo_root

    primary_root = get_main_repo_root(repo_root) if effective_root is None else effective_root.resolve()

    mission_id = _resolve_mission_id(
        primary_root,
        mission_slug,
        resolver=resolver,
        effective_root=effective_root,
    )
    identity = IdentityFragment.derive(mission_id=mission_id, mission_slug=mission_slug)

    # ``_resolve_coordination_branch`` stays as the VALUE reader for the ref
    # string the BranchRefFragment carries (the shell still needs the ref). The
    # retired ``is None ⇒ FLATTENED`` *decision* is replaced by reading the stored
    # topology: the placement ``kind`` is now classified from ``topology`` (FR-004
    # / SC-001), never inferred from the branch value's presence.
    coordination_branch = _resolve_coordination_branch(
        primary_root,
        mission_slug,
        resolver=resolver,
        effective_root=effective_root,
    )
    # The coord-routing DECISION reads the STORED topology via the SINGLE predicate
    # (FR-005 / WP04 drain) — never a re-derived per-ref enum. ``CommitTarget`` is a
    # ref-only carrier (C-007 / FR-001b): the destination ref is the coord branch
    # when the stored topology routes through coordination, else the target branch.
    coord_ref = coordination_branch if routes_through_coordination(topology) and coordination_branch is not None else target_branch
    destination_ref = CommitTarget(ref=coord_ref)
    branch_ref = BranchRefFragment(
        target_branch=target_branch,
        coordination_branch=coordination_branch,
        destination_ref=destination_ref,
    )

    surface_dir = _resolve_status_surface_dir(
        primary_root,
        mission_slug,
        topology,
        resolver=resolver,
        effective_root=effective_root,
        for_write=for_write,
    )
    status_surface = StatusSurfaceFragment(
        status_read_dir=surface_dir,
        status_write_dir=surface_dir,
    )

    workspace = _assemble_workspace_fragment(
        primary_root,
        mission_slug=mission_slug,
        mid8=identity.mid8,
        coordination_branch=coordination_branch,
        cwd=cwd,
    )

    return identity, branch_ref, status_surface, workspace


def _assemble_artifact_placement_fragment(
    branch_ref: BranchRefFragment,
) -> ArtifactPlacementFragment:
    """Assemble the WP06-owned ArtifactPlacementFragment (IC-05 / C-PLACE-1).

    The placement ref is the **same** :class:`CommitTarget` carried on
    :class:`BranchRefFragment.destination_ref` — it is not re-derived from
    meta.json or git here (C-005: no parallel placement logic). This makes the
    FR-004 invariant a *structural* identity: planning artifacts
    (spec/plan/tasks/analysis-report) and status events resolve to literally the
    same value object, so implement-claim (#1816) and record-analysis (#1814)
    can never reconcile a primary↔coord split — under flattened topology the
    shared ``destination_ref`` already collapses (``kind == FLATTENED``, WP08).

    The fragment is CWD-invariant by construction because ``destination_ref`` is
    assembled from the canonical primary root (C-CTX-2 / WP02 carry-forward).
    """
    return ArtifactPlacementFragment(placement_ref=branch_ref.destination_ref)


def _require_owned_single_branch(context: MissionContext) -> None:
    """The ONE owned-placement topology refusal (#3862 item A).

    Both owned arms (``resolve_placement_only`` / ``resolve_artifact_surface``)
    refused a non-``single_branch`` stored topology with a byte-identical
    duplicated ``ActionContextError`` tuple; this guard is the single hoisted
    refusal, disposing against the ONE enum-based
    :func:`~mission_runtime.context.is_single_branch` predicate — the same
    predicate the owned checkout preflight
    (:func:`specify_cli.core.owned_mission.resolve_owned_mission`) applies to
    the raw meta read — so the invariant is expressed once, enum-based, and
    the historical string/enum representations cannot drift apart.
    """
    if not is_single_branch(context.topology):
        raise ActionContextError("OWNED_TOPOLOGY_UNSUPPORTED", "Explicit placement requires single_branch.")


def resolve_placement_only(
    repo_root: Path,
    mission_slug: str,
    *,
    kind: MissionArtifactKind,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> CommitTarget:
    """Resolve the placement :class:`CommitTarget` for a mission artifact ``kind``.

    The **WP-less placement projection** (IC-04 / C-GUARD-3a): the planning
    phase (specify / plan / tasks / finalize-tasks) has no ``wp_id`` — no work
    packages exist yet — so the full :func:`resolve_action_context` cannot be
    driven to obtain an :class:`ArtifactPlacementFragment`. This function is a
    narrower entry point over the **same** resolution authority, NOT a parallel
    resolver (C-CTX-1): it resolves ``target_branch`` once via
    :func:`get_feature_target_branch` and runs the single
    :func:`_assemble_core_fragments` builder, then projects out the one
    ``destination_ref`` :class:`CommitTarget` that builder already computes. The
    topology classification (primary / coordination / flattened) is therefore
    BYTE-IDENTICAL to what the full resolver assembles for the same mission —
    there is no second derivation from ``meta.json`` or git on the planning
    commit path (the #1784 catch-22 root: ``_resolve_planning_branch`` reading
    one authority while the placement fragment reads another).

    This is the literal #1784 fix: on a protected-target repo ``mission create``
    materializes a coordination branch, so the resolved placement is the
    NON-protected coordination ref — a ``GuardCapability.STANDARD`` commit lands
    there cleanly, with no "switch to the lane branch before lanes exist"
    refusal-to-nowhere.

    The projection is now kind-aware (write-surface-coherence WP01, FR-002 /
    FR-004): the READ side (:func:`artifact_home_for`) has routed by kind since
    #2090; this WRITE-side projection now agrees. A ``_PRIMARY_ARTIFACT_KINDS``
    member (spec / data-model / research / checklist / finalized plan /
    tasks-index / WP task / lanes / metadata) resolves to the primary
    ``target_branch`` for EVERY topology shape; every other kind keeps the
    topology-routed ``destination_ref`` (the coordination branch under
    coordination topology, else the target branch). ``kind`` is a REQUIRED
    keyword (DECISION 1): there is no default, so an un-threaded call site fails
    at the type/import level rather than silently flipping coord→primary.

    Args:
        repo_root: Repository root (resolved to the canonical primary root by
            the shared builder, so the result is CWD-invariant).
        mission_slug: The mission directory name / slug.
        kind: The mission artifact kind being placed. REQUIRED — no default;
            its partition membership selects the primary vs topology-routed ref.
        resolver: Optional :class:`MissionResolver` threaded through entry
            canonicalization and the shared builder (WP03, FR-002). ``None``
            preserves historical behaviour.

    Returns:
        The single :class:`CommitTarget` the artifact commits to — the primary
        ``target_branch`` ref for a primary kind, else the topology-routed
        ``destination_ref`` (the value object status events resolve to). For a
        PUBLISHED (E2) mission and an E2-in-scope ``kind`` (every PRIMARY kind
        plus ``ISSUE_MATRIX`` / ``TRACER_FILE`` / ``ACCEPTANCE_MATRIX`` — ADR
        2026-07-30-1 Decision 1 §6 — and ``REVIEW_CYCLE`` — ADR 2026-08-03-1,
        review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 T016), this is instead
        the resolved Primary Branch NAME (#3033, T009) — the lifecycle phase
        is derived internally
        from durable ``meta.json`` + git state (D2), never threaded as a
        parameter.

    Raises:
        ActionContextError: when the mission slug cannot be resolved (no silent
            fallback — mirrors :func:`resolve_action_context`), OR when a
            PUBLISHED (E2) mission's consolidated content is not present on
            the current checkout (FR-006 refuse-with-recovery; code
            ``CONSOLIDATED_CONTENT_ABSENT``).
    """
    if effective_root is not None:
        context = mission_context_for(repo_root, mission_slug, resolver=resolver, effective_root=effective_root)
        _require_owned_single_branch(context)
        target = context.artifact(kind).commit_target
        if target is None:
            raise ActionContextError("OWNED_ARTIFACT_UNSUPPORTED", f"Artifact {kind.value} has no commit target.")
        return target

    from specify_cli.core.paths import get_feature_target_branch
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
        candidate_feature_dir_for_mission,
    )

    if not mission_slug or not mission_slug.strip():
        raise ActionContextError(
            _FEATURE_CONTEXT_UNRESOLVED_CODE,
            "resolve_placement_only requires an explicit mission_slug.",
        )

    # F-001: canonicalize the operator handle at entry. A bare mid8 / numeric
    # prefix must compose the SAME placement (ref AND kind) as the full slug —
    # composing from the raw handle reads no meta.json, flips a coord-topology
    # mission to FLATTENED, and targets the (possibly protected) target branch
    # (the #1784 class). When nothing resolves, the raw slug passes through and
    # the builder degrades exactly as before (no behaviour change for missing
    # missions).
    try:
        candidate_dir = candidate_feature_dir_for_mission(repo_root, mission_slug, resolver=resolver)
    except StatusReadPathNotFound as exc:
        # Fail-closed surface refusal at entry canonicalization: translate to
        # the boundary's single error type, preserving the refusal message
        # (PR #1850 M6) — mirrors :func:`_resolve_mission_slug`.
        raise ActionContextError(exc.error_code, str(exc)) from exc
    except MissionSelectorAmbiguous as exc:
        # Boundary translation (WP05 / FR-005 / #2010 bug #15): mirrors the
        # _resolve_mission_slug arm — the ambiguous handle must not escape as a
        # raw specify_cli exception from this entry point either.
        raise ActionContextError(exc.error_code, str(exc)) from exc
    if candidate_dir.exists():
        mission_slug = candidate_dir.name

    # T009 (D2/D3, NFR-001): derive lifecycle phase INTERNALLY — no phase
    # parameter is threaded through this function's callers
    # (``PlacementSeam.write_target`` / ``commit_for_mission``), both of which
    # re-derive the identical phase from this SAME durable signal on their own
    # call into this function, so they can never disagree (no split-brain).
    # A PUBLISHED (E2) mission short-circuits straight to the CONSOLIDATED
    # target for the in-scope kinds (PRIMARY + the 3 coord write kinds — ADR
    # Decision 1 §6) BEFORE the unconditional coordination-surface probe
    # below, which would otherwise raise ``CoordinationBranchDeleted`` on a
    # fully-retired E2 mission whose coordination branch has ALSO been
    # cleaned up (#3033 T007). PRE_CONSOLIDATION and CONSOLIDATED (E1) fall
    # through completely UNCHANGED (#3076 regression floor, T012) — including
    # for ``STATUS_STATE`` / ``DECISION_LOG``, which are never in the E2
    # in-scope set (SC-005 non-regression).
    phase = resolve_lifecycle_phase(mission_slug, repo_root, resolver=resolver)
    if phase is LifecyclePhase.PUBLISHED and kind in _E2_CONSOLIDATED_ELIGIBLE_KINDS:
        return _resolve_consolidated_e2_target(repo_root, mission_slug, resolver=resolver)

    # FR-012 / C-CTX-3: ``target_branch`` is resolved exactly once here, exactly
    # as ``resolve_action_context`` does, and threaded into the shared builder.
    # The WP02 stored ``topology`` is read once alongside it (the shell read) and
    # threaded in so the placement ``kind`` is classified from the stored shape,
    # never re-inferred from ``coordination_branch`` (FR-004).
    from specify_cli.core.paths import get_main_repo_root

    target_branch = get_feature_target_branch(repo_root, mission_slug)
    topology = _resolve_topology(get_main_repo_root(repo_root), mission_slug, resolver=resolver)
    _identity, branch_ref, _status_surface, _workspace = _assemble_core_fragments(
        repo_root,
        mission_slug=mission_slug,
        target_branch=target_branch,
        topology=topology,
        cwd=None,
        resolver=resolver,
        for_write=True,
    )
    # FR-002 / FR-004 (write-surface-coherence WP01): the projection is
    # kind-aware. A ``_PRIMARY_ARTIFACT_KINDS`` member routes to the primary
    # ``target_branch`` already resolved above (via ``get_feature_target_branch``)
    # for EVERY topology shape, so planning + identity artifacts live with their
    # mission on the primary surface. Every other kind keeps the topology-routed
    # ``destination_ref`` — the SAME CommitTarget the full resolver projects via
    # ``_assemble_artifact_placement_fragment`` (C-PLACE-1): one authority, two
    # projections. We return a bare CommitTarget rather than an
    # ArtifactPlacementFragment because planning callers hand it straight to
    # ``safe_commit(target=...)``.
    if kind in _PRIMARY_ARTIFACT_KINDS:
        return CommitTarget(ref=target_branch)
    return branch_ref.destination_ref


@dataclass(frozen=True)
class PlacementSeam:
    """The single kind-aware placement authority for one mission operation (T001).

    The public face of the :func:`resolve_action_context` derivation root
    (contracts/seam-api.md): "one authority object per mission operation,
    exposing two kind-aware projections." Both projections are THIN — they
    delegate to the pre-existing leaf resolvers rather than re-deriving
    placement (C-001 / Directive-044):

    - :meth:`write_target` projects :func:`resolve_placement_only` (the
      existing write projection, `resolution.py`).
    - :meth:`read_dir` projects :func:`~specify_cli.missions._read_path_resolver
      .resolve_planning_read_dir` (the existing read projection) for every kind
      EXCEPT ``RETROSPECTIVE``, which routes to the dedicated single authority
      :func:`~specify_cli.retrospective.writer.resolve_retrospective_home`
      (squad finding H-1) — computing a second RETROSPECTIVE home here would
      duplicate that authority and fail its own single-authority guard test
      (``tests/retrospective/test_home_resolution_single_authority.py``).

    Both projections are CWD-invariant: they derive from ``repo_root`` +
    ``mission_slug`` (the stored topology, read via ``meta.json``), never from
    the current checkout (T-2). Coord-routing decisions inside the delegated
    resolvers consult ONLY :func:`~mission_runtime.context.
    routes_through_coordination` over the stored topology — this seam never
    inlines its own coord-topology equality check (T-1).

    Constructed via :func:`placement_seam`, which also asserts the P-1
    partition invariant (T002) so a future kind added to
    :class:`~mission_runtime.artifacts.MissionArtifactKind` without a
    partition entry fails loudly at the seam boundary.
    """

    repo_root: Path
    mission_slug: str
    effective_root: Path | None = None

    def write_target(self, kind: MissionArtifactKind) -> CommitTarget:
        """Return the :class:`CommitTarget` a write of ``kind`` must commit to.

        Thin projection over :func:`resolve_placement_only` — see class
        docstring. Never constructs ``CommitTarget(ref=<current_checkout>)``
        (the forbidden-for-callers grammar, contracts/seam-api.md).
        """
        return resolve_placement_only(
            self.repo_root,
            self.mission_slug,
            kind=kind,
            effective_root=self.effective_root,
        )

    def read_dir(self, kind: MissionArtifactKind) -> Path:
        """Return the directory a read of ``kind`` resolves to.

        ``RETROSPECTIVE`` routes to :func:`resolve_retrospective_home` (the
        dedicated single authority, H-1); every other kind routes through
        :func:`resolve_artifact_surface` (coord-write-placement-closure-01KYCF83
        WP07, T032 — FR-004/NFR-002 fail-loud read authority).

        Before WP07 this projected the LENIENT
        :func:`~specify_cli.missions._read_path_resolver.resolve_planning_read_dir`
        (via ``candidate_feature_dir_for_mission``), which never supplies a
        ``coordination_branch`` to its fail-closed tail — so a coord-partition
        kind whose declared coordination branch had been DELETED from git
        silently substituted the primary checkout instead of raising. Routing
        through :func:`resolve_artifact_surface` instead — the SAME
        materialization-aware authority :func:`build_gate_execution_context`
        already consumes — closes that silent substitution: ``DELETED`` now
        raises :class:`~specify_cli.coordination.surface_resolver.
        CoordinationBranchDeleted` (the existing typed partition-mismatch
        signal; no new exception type needed). Every other cell — a
        PRIMARY-partition kind, a coord-less topology (AH-2), or a coord
        topology whose worktree is genuinely ``EMPTY``/``UNMATERIALIZED``
        (the create-window) — resolves identically to before **with respect to
        raising**: these are the T031-enumerated SANCTIONED degrades, preserved
        verbatim (NFR-002 forbids only *undeclared* fallbacks, not these
        declared ones).

        Identical *raising* is NOT identical *anchoring*.
        :func:`resolve_artifact_surface` applies
        :func:`~specify_cli.core.paths.get_main_repo_root` to ``repo_root``
        first; ``candidate_feature_dir_for_mission`` consumed ``repo_root``
        VERBATIM. A caller migrating off that primitive can therefore see a
        different resolved ROOT even in a cell that can never raise — the live
        ``verify.py::_existing_feature_dir`` regression, which began returning a
        main-repo path where it previously returned ``None``. Reason on BOTH
        axes when auditing a migrated call site.
        """
        if kind is MissionArtifactKind.RETROSPECTIVE:
            from specify_cli.retrospective.writer import resolve_retrospective_home

            # Explicit ``Path`` annotation: under the project's
            # ``follow_imports = "skip"`` mypy config the cross-module
            # ``resolve_retrospective_home`` return is seen as ``Any``; the
            # annotation re-narrows it (the function IS typed ``-> Path``) —
            # matching the sibling ``_planning_read_dir`` chokepoint pattern.
            retrospective_dir: Path = resolve_retrospective_home(self.repo_root, self.mission_slug)
            return retrospective_dir

        return resolve_artifact_surface(
            self.repo_root,
            self.mission_slug,
            kind,
            effective_root=self.effective_root,
        ).path


@dataclass(frozen=True)
class SurfaceLocations:
    """The candidate filesystem locations a mission's surfaces map to.

    The input bundle to :func:`translate_surface`: one optional path per
    :class:`TopologySurface` member. ``primary`` is always known (its declared
    home exists for every topology); the others are populated only when the caller
    has resolved that surface (``coord`` once the coordination worktree is
    materialised; ``lane`` / ``consolidated`` / ``temp`` by their respective
    flows). A member whose location is ``None`` has no resolved home for this call,
    and :func:`translate_surface` refuses it rather than guessing.
    """

    primary: Path
    coord: Path | None = None
    lane: Path | None = None
    consolidated: Path | None = None
    temp: Path | None = None


# The ONE surface→field translation map (data-model.md "TopologySurface", IC-11).
# Keyed by EVERY :class:`TopologySurface` member so :func:`assert_surface_totality`
# proves no member is a phantom: a member added to the enum without an entry here
# fails LOUD inside :func:`translate_surface`.
_SURFACE_LOCATION_FIELD: dict[TopologySurface, str] = {
    TopologySurface.PRIMARY: "primary",
    TopologySurface.COORD: "coord",
    TopologySurface.LANE: "lane",
    TopologySurface.CONSOLIDATED: "consolidated",
    TopologySurface.TEMP: "temp",
}


def translate_surface(surface: TopologySurface, locations: SurfaceLocations) -> Path:
    """Translate a :class:`TopologySurface` member to its filesystem location.

    The ONE **total** surface→filesystem translation (data-model.md
    "TopologySurface", IC-11 — the true schema root). It is total over the enum:
    every member has a translation entry, asserted by
    :func:`~mission_runtime.artifacts.assert_surface_totality` on every call (the
    anti-phantom guard — a member added to :class:`TopologySurface` without an
    entry fails LOUD here rather than resolving to nothing). ``locations`` supplies
    the concrete path for the requested member; a member with no resolved location
    for this call raises rather than fabricating one.

    Raises:
        AssertionError: When the enum has a member with no translation entry.
        ValueError: When ``locations`` carries no path for ``surface``.
    """
    assert_surface_totality(frozenset(_SURFACE_LOCATION_FIELD))
    location: Path | None = getattr(locations, _SURFACE_LOCATION_FIELD[surface])
    if location is None:
        raise ValueError(f"No resolved location for surface {surface.value!r}; the caller must supply it in SurfaceLocations before translating.")
    return location


@dataclass(frozen=True)
class ResolvedSurface:
    """A resolved surface plus the stamp naming which physical tree it is (C6).

    The output of :func:`resolve_artifact_surface`: ``path`` is where the artifact
    is read/written; ``surface_kind`` is the :class:`TopologySurface` stamp a
    recorded judgement names (NFR-003 / contract GEC-3). Per GEC-5 a ``PRIMARY``
    stamp on a *substituted* surface (the ``EMPTY`` / ``UNMATERIALIZED`` create
    window) is visible, not authoritative — the consuming gate decides whether the
    stamped surface can hold the fact.
    """

    path: Path
    surface_kind: TopologySurface


def declared_read_surface(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    *,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> TopologySurface:
    """The intrinsic, materialization-BLIND declared home for a read of ``kind``.

    AH-1/AH-3: a PRIMARY-partition kind's declared home is ``PRIMARY`` for
    every topology (it never transits coordination). AH-2: a coord-partition
    kind's declared home is ``COORD`` only when the mission's STORED topology
    routes through coordination (:func:`routes_through_coordination`); a
    coord-less topology (``SINGLE_BRANCH`` / ``LANES``) declares ``PRIMARY`` —
    its actual home, not a fallback.

    This answers "where does this kind's fact architecturally live", never
    "where does a read resolve RIGHT NOW" — that materialization-aware
    question belongs to :func:`resolve_artifact_surface`. The distinction is
    load-bearing: :meth:`~specify_cli.acceptance.execution_context.
    GateExecutionContext.surface_cannot_hold` (GEC-5 / #2906) compares THIS
    declared answer against an ALREADY-RESOLVED (possibly create-window
    -substituted) surface stamp to detect exactly the divergence a
    stamp-is-not-permission refusal exists for. If this function consulted
    materialization too, the two would always agree and the #2906 guard
    could never fire.

    coord-write-placement-closure-01KYCF83 WP07 (T034 fold): the ONE shared
    partition+topology predicate. :func:`_classify_artifact_surface` (this
    module) and :func:`~specify_cli.acceptance.execution_context.
    declared_home_surface` both call this instead of each independently
    reimplementing ``is_primary_artifact_kind`` + ``routes_through_coordination``
    inline — convergence, not a second competing guard (D-06 / contract
    "Read" reconciliation).
    """
    if is_primary_artifact_kind(kind):
        return TopologySurface.PRIMARY
    topology = (
        resolve_topology(repo_root, mission_slug, resolver=resolver)
        if effective_root is None
        else mission_context_for(repo_root, mission_slug, resolver=resolver, effective_root=effective_root).topology
    )
    if routes_through_coordination(topology):
        return TopologySurface.COORD
    return TopologySurface.PRIMARY


def _classify_artifact_surface(
    primary_root: Path,
    canonical_slug: str,
    kind: MissionArtifactKind,
    *,
    primary_dir: Path,
    resolver: MissionResolver | None,
) -> tuple[TopologySurface, Path | None]:
    """Classify the affirmative surface for ``kind`` (the four-CoordState answer).

    Returns the :class:`TopologySurface` stamp and — for a ``COORD`` stamp — the
    coordination mission dir. Consumes the EXISTING
    :func:`~specify_cli.missions._read_path_resolver.probe_coord_state` /
    :class:`CoordState` classifier; it writes no classifier beside it (GEC-3).

    The declared (materialization-blind) partition+topology question is
    answered by :func:`declared_read_surface` (T034 fold, WP07) — a
    ``PRIMARY`` declared answer covers BOTH AH-1/AH-3 (a PRIMARY-partition
    kind never transits coordination — no probe, no raise even under a
    deleted coord branch) and AH-2 (a coord-less topology's declared home IS
    primary, not a fallback); only a ``COORD`` declared answer proceeds to
    the materialization-aware four-state classifier below.
    """
    declared = declared_read_surface(primary_root, canonical_slug, kind, resolver=resolver)
    if declared is TopologySurface.PRIMARY:
        return TopologySurface.PRIMARY, None

    # Coord-routing topology + coord-partition kind: consume the four-state
    # classifier (GEC-3 / contract C3). ``coordination_branch`` (read from the
    # primary ``meta.json``) is what splits UNMATERIALIZED from DELETED inside the
    # probe's single ``git rev-parse`` arm.
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.missions._read_path_resolver import (
        CoordState,
        coord_feature_dir,
        probe_coord_state,
    )

    coordination_branch = _resolve_coordination_branch(primary_root, canonical_slug, resolver=resolver)
    mission_id = _resolve_mission_id(primary_root, canonical_slug, resolver=resolver)
    mid8 = resolve_mid8(canonical_slug, mission_id=mission_id)
    coord_state = probe_coord_state(primary_root, canonical_slug, mid8, coordination_branch=coordination_branch)

    if coord_state is CoordState.DELETED:
        # C3 "fail loud" (#1848 data-loss): a declared coord branch deleted from
        # git carries unmerged status — raise the SAME canonical exception the read
        # path raises, never a silent primary fallback. #4403: the payload is
        # built by the ONE ``CoordinationBranchDeleted.for_mission`` factory
        # (the ``or ""`` None-guard it owns replaces this site's hand-rolled
        # one); only this site's backfill-aware ``primary_dir`` is threaded.
        raise CoordinationBranchDeleted.for_mission(
            repo_root=primary_root,
            mission_slug=canonical_slug,
            mid8=mid8,
            coordination_branch=coordination_branch,
            primary_candidate=primary_dir,
        )
    if coord_state is CoordState.MATERIALIZED:
        return TopologySurface.COORD, coord_feature_dir(primary_root, canonical_slug, mid8)
    # EMPTY / UNMATERIALIZED / NONE → primary + PRIMARY stamp (GEC-3): a DECLARED
    # answer the returned stamp names, NOT an undeclared fallback (NFR-001). GEC-5
    # governs whether the consuming gate may treat the stamped surface as
    # authoritative.
    return TopologySurface.PRIMARY, None


def _backfilled_primary_dir(
    primary_root: Path,
    mission_slug: str,
    primary_dir: Path,
    *,
    resolver: MissionResolver | None,
) -> Path | None:
    """Recover the BARE on-disk primary dir when ``mission_slug`` is ALREADY composed.

    The existence-aware leg that keeps :func:`resolve_artifact_surface` IDEMPOTENT
    under its own canonical output. ``resolve_planning_read_dir(...,
    PRIMARY_METADATA)`` literal-composes ``<slug>-<mid8>``; for a **backfilled**
    mission — whose primary dir on disk carries the BARE ``<slug>`` while its coord
    worktree carries the composed ``<slug>-<mid8>`` — feeding the seam the composed
    name it just emitted yields a ``primary_dir`` that does not exist. The
    downstream ``declared_read_surface`` then finds no ``meta.json``, reads no
    topology, and short-circuits to ``PRIMARY`` before ``probe_coord_state`` is ever
    consulted — a silently wrong path that is not on disk.

    This restores the branch the retired ``candidate_feature_dir_for_mission`` leg
    carried explicitly ("backfilled mission: the directory name lacks the
    ``-<mid8>`` suffix — trust it"), but on the PRIMARY side and *identity-confirmed*
    rather than name-guessed: the recovered dir must DECLARE the very mid8 that was
    stripped, via the ONE sanctioned mid8 cascade
    (:func:`_mid8_from_primary_meta` → ``resolve_declared_mid8``, C-006/NFR-005).
    A coincidental 8-char Crockford tail on an unrelated sibling dir therefore
    cannot be mistaken for a mid8 (the documented hazard of the heuristic
    :func:`~mission_runtime.identity.mid8_from_slug`).

    Returns the recovered primary dir, or ``None`` to leave the caller's
    literal-composed answer untouched — so a genuinely absent mission keeps its
    existing fail-loud diagnostics unchanged (NFR-001).
    """
    if primary_dir.exists():
        return None
    tail = mid8_from_slug(mission_slug)
    if not tail:
        return None
    bare = mission_slug[: -(len(tail) + 1)]
    if not bare:
        return None

    from specify_cli.missions._read_path_resolver import resolve_planning_read_dir

    # ``resolve_planning_read_dir`` is typed ``-> Path`` but the
    # ``follow_imports=skip`` boundary on ``specify_cli.*`` widens it to ``Any``;
    # bind explicitly so the declared return narrows back.
    candidate: Path = resolve_planning_read_dir(
        primary_root,
        bare,
        kind=MissionArtifactKind.PRIMARY_METADATA,
        resolver=resolver,
    )
    if candidate == primary_dir or not candidate.is_dir():
        return None
    if _mid8_from_primary_meta(primary_root, bare).upper() != tail.upper():
        return None
    return candidate


def resolve_artifact_surface(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
    *,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> ResolvedSurface:
    """Resolve the affirmative read/write surface for a mission artifact ``kind``.

    The stamped face of the surface→filesystem seam (data-model.md "ArtifactHome"
    AH-1/AH-2, contract GEC-3 / C3 — the four-``CoordState`` answer set). Consumes
    the EXISTING
    :func:`~specify_cli.missions._read_path_resolver.probe_coord_state` /
    :class:`CoordState` classifier — never a new one beside it. It is TOTAL: every
    topology and coord state has a DECLARED answer named by the returned
    ``surface_kind`` stamp (NFR-001 forbids only *undeclared* fallbacks):

    * a PRIMARY-partition kind resolves the primary mission dir, stamped PRIMARY,
      for EVERY topology and coord state (AH-1/AH-3 — it never transits coord);
    * a coord-partition kind on flat / ``SINGLE_BRANCH`` / ``LANES`` resolves the
      primary dir AFFIRMATIVELY (AH-2 — its declared home, not a fallback), stamped
      PRIMARY;
    * a coord-partition kind on coord-routing topology consumes the four-state
      classifier: ``DELETED`` raises :class:`CoordinationBranchDeleted` (C3 "fail
      loud"); ``MATERIALIZED`` resolves the coord dir, stamped COORD; ``EMPTY`` /
      ``UNMATERIALIZED`` resolve the primary dir, stamped PRIMARY.

    The final path goes through :func:`translate_surface` so the ONE total
    translation is the production path, not merely a tested one. CWD-invariant: the
    canonical primary root is resolved first, so the answer is identical from any
    checkout (C-CTX-2).

    Raises:
        CoordinationBranchDeleted: When the declared coordination branch has been
            deleted from git (C3 fail-loud).
        MissionSelectorAmbiguous: When ``mission_slug`` is an ambiguous handle
            (propagated from handle canonicalization — no silent pick).
    """
    if effective_root is not None:
        context = mission_context_for(repo_root, mission_slug, resolver=resolver, effective_root=effective_root)
        _require_owned_single_branch(context)
        return ResolvedSurface(path=context.artifact(kind).read_dir, surface_kind=TopologySurface.PRIMARY)

    from specify_cli.core.paths import get_main_repo_root
    from specify_cli.missions._read_path_resolver import resolve_planning_read_dir

    primary_root = get_main_repo_root(repo_root)
    # The affirmative PRIMARY home (canonicalized handle → ``<slug>-<mid8>`` dir).
    # ``resolve_planning_read_dir`` is typed ``-> Path`` but the
    # ``follow_imports=skip`` boundary on ``specify_cli.*`` widens it to ``Any``;
    # bind explicitly so the declared return narrows back.
    primary_dir: Path = resolve_planning_read_dir(
        primary_root,
        mission_slug,
        kind=MissionArtifactKind.PRIMARY_METADATA,
        resolver=resolver,
    )
    # Idempotence under our own output (the #3012 backfilled-mission regression):
    # when the literal-composed ``<slug>-<mid8>`` primary dir does NOT exist but the
    # BARE ``<slug>`` dir does, adopt the bare dir BEFORE classifying. Every
    # downstream consumer keys off ``canonical_slug`` and recomposes the coord name
    # through the double-suffix-safe ``_compose_mission_dir``, so correcting the
    # slug here is sufficient — and ``declared_read_surface`` can then actually read
    # the mission's ``meta.json`` and reach ``probe_coord_state``.
    recovered = _backfilled_primary_dir(primary_root, mission_slug, primary_dir, resolver=resolver)
    if recovered is not None:
        primary_dir = recovered
    canonical_slug = primary_dir.name
    surface_kind, coord_dir = _classify_artifact_surface(
        primary_root,
        canonical_slug,
        kind,
        primary_dir=primary_dir,
        resolver=resolver,
    )
    # T010 / renata M1: populate the previously-always-``None``
    # ``SurfaceLocations.consolidated`` field. This is the SAME phase
    # derivation ``resolve_placement_only`` calls (no second derivation,
    # NFR-001 no-split-brain) — it does NOT alter ``surface_kind`` /
    # ``translate_surface``'s selection above, so every existing caller's
    # returned ``.path`` is byte-identical (SC-005: ``STATUS_STATE`` /
    # ``DECISION_LOG`` resolution is unaffected, exactly like every other
    # kind not explicitly wired into the E2 write-routing short-circuit in
    # ``resolve_placement_only``). E1 and E2 both resolve the integrated tree
    # to the same ``primary_dir`` this function already anchors on the
    # canonical primary root (C-CTX-2): in E1 that root is (by construction)
    # the Target Ref tree while checked out there; in E2 it is the
    # repository-root checkout on the Primary Branch. PRE_CONSOLIDATION
    # leaves ``consolidated`` ``None`` — "n/a" per data-model.md — so
    # ``translate_surface(CONSOLIDATED, …)`` keeps refusing with its
    # existing "no resolved location" guard before any consolidation exists.
    phase = resolve_lifecycle_phase(canonical_slug, primary_root, resolver=resolver)
    consolidated_dir = None if phase is LifecyclePhase.PRE_CONSOLIDATION else primary_dir
    locations = SurfaceLocations(primary=primary_dir, coord=coord_dir, consolidated=consolidated_dir)
    return ResolvedSurface(
        path=translate_surface(surface_kind, locations),
        surface_kind=surface_kind,
    )


def coord_read_dir_for(
    repo_root: Path,
    mission_slug: str,
    kind: MissionArtifactKind,
) -> Path | None:
    """Resolve the COORDINATION read dir for a coord-classified ``kind``, or ``None``.

    The ONE shared coord-read guard (coord-commit-integrity SURFACE A #5): returns
    the coordination-surface read dir for ``kind`` when — and only when — the
    mission's STORED topology routes through coordination
    (:func:`routes_through_coordination` over ``COORD`` / ``LANES_WITH_COORD``) AND
    that coordination surface is materialised on disk. Returns ``None`` in every
    coord-less case (``SINGLE_BRANCH`` / ``LANES``) and whenever the coord worktree
    has not been materialised yet — there is no coord surface to read from, so the
    caller falls back to its own primary ``feature_dir`` (or reports "nothing to
    reconcile"). Never materialises the worktree (a read/scan must not have side
    effects).

    Now a THIN ``Path | None`` projection of the affirmative seam
    :func:`resolve_artifact_surface` (WP02 — the surface→filesystem schema root):
    it keeps the ``None``-signal contract its remaining consumers rely on
    (``status.doctor`` / ``cli.commands.review`` — "nothing to reconcile") by
    projecting the stamp: a ``COORD`` stamp yields the coord dir, every other stamp
    yields ``None``. The affirmative-vs-``None`` split lives in the ONE seam; this
    is only its narrowing projection (Directive-044).

    Fail-soft (post-merge safety): a mission whose stored topology still declares
    coordination but whose coordination worktree has already been consolidated away
    (a post-merge review read), an ambiguous handle, or a DELETED coordination
    branch all mean "there is no coordination surface to read from" for a
    ``None``-returning guard — so :class:`CoordinationBranchDeleted` (a
    :class:`StatusReadPathNotFound` subclass), the fail-closed refusals, and
    ambiguity are absorbed to ``None`` here. Callers that need the loud C3
    fail-closed behaviour on ``DELETED`` (the accept-path gates) consume
    :func:`resolve_artifact_surface` directly.
    """
    from specify_cli.missions._read_path_resolver import (
        MissionSelectorAmbiguous,
        StatusReadPathNotFound,
    )

    try:
        resolved = resolve_artifact_surface(repo_root, mission_slug, kind)
    except (StatusReadPathNotFound, MissionSelectorAmbiguous, ActionContextError):
        # ``CoordinationBranchDeleted`` subclasses ``StatusReadPathNotFound``, so it
        # is absorbed here too — preserving this guard's historical ``None``-for-
        # deleted behaviour for its non-accept consumers.
        return None
    if resolved.surface_kind is not TopologySurface.COORD:
        return None
    return resolved.path


def resolve_create_time_write_target(planning_branch: str) -> CommitTarget:
    """Return the explicit target used before mission identity is readable.

    Mission creation derives ``planning_branch`` only after exact-checkout
    ownership validation.  During that narrow bootstrap interval no mission
    metadata exists for :func:`placement_seam` to inspect, so this pure seam
    carries the already-authoritative short branch into commit routing without
    consulting CWD, environment, topology, or a fallback repository root.
    """
    if not planning_branch or planning_branch != planning_branch.strip() or planning_branch.startswith("refs/heads/"):
        raise ActionContextError(
            "CREATE_TIME_TARGET_INVALID",
            "Create-time planning branch must be a non-empty short branch name without the 'refs/heads/' prefix.",
        )
    return CommitTarget(ref=planning_branch)


def placement_seam(repo_root: Path, mission_slug: str, *, effective_root: Path | None = None) -> PlacementSeam:
    """Construct the placement seam for one mission operation (T001 entry point).

    Asserts the P-1 partition invariant (T002) before returning the seam: the
    two :mod:`mission_runtime.artifacts` partition frozensets must stay
    disjoint and jointly exhaustive over every
    :class:`~mission_runtime.artifacts.MissionArtifactKind` member. The check
    is pure in-memory set arithmetic — cheap enough to run on every
    construction — so a future kind added without a partition entry fails
    loudly here rather than as a deep ``ValueError`` inside
    :func:`~mission_runtime.artifacts.artifact_home_for`.
    """
    assert_partition_invariant()
    return PlacementSeam(repo_root=repo_root, mission_slug=mission_slug, effective_root=effective_root)


def resolve_action_context(
    repo_root: Path,
    *,
    action: ActionName,
    feature: str | None = None,
    wp_id: str | None = None,
    agent: str | None = None,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    resolver: MissionResolver | None = None,
    effective_root: Path | None = None,
) -> MissionExecutionContext:
    """Resolve canonical mission/work-package context for an agent action.

    CWD-invariant, topology-aware, mode-correct. Raises
    :class:`ActionContextError` on unresolvable context (no silent fallback).

    ``resolver`` (mission-resolver-port-01KX1C05 WP03, FR-002 — the trunk):
    optional :class:`MissionResolver` threaded through :func:`_resolve_mission_slug`,
    :func:`_resolve_topology`, and :func:`_assemble_core_fragments`, so every
    handle→mission walk this call performs (including the ones nested inside
    the canonicalizer chain in ``specify_cli.missions._read_path_resolver``)
    goes through the ONE injected resolver — never a second, uninjected
    ``FsMissionResolver``. ``None`` (the default) is byte-identical to the
    pre-WP03 behaviour: each walk constructs its own ``FsMissionResolver``.
    """
    if action not in ACTION_NAMES:
        raise ActionContextError(
            "INVALID_ACTION",
            f"Invalid action '{action}'. Expected one of: {', '.join(ACTION_NAMES)}.",
        )

    from specify_cli.core.dependency_graph import parse_wp_dependencies
    from specify_cli.core.paths import get_feature_target_branch
    from specify_cli.status import Lane
    from specify_cli.status import resolve_lane_alias
    from specify_cli.task_utils import locate_work_package
    from specify_cli.workspace.context import resolve_workspace_for_wp

    from specify_cli.core.paths import get_main_repo_root

    mission_slug, feature_dir = _resolve_mission_slug(
        repo_root,
        feature=feature,
        cwd=cwd,
        env=env,
        resolver=resolver,
        effective_root=effective_root,
    )
    # FR-012 / C-CTX-3: ``target_branch`` is resolved exactly once here and
    # threaded onto both the flat substrate field and the BranchRefFragment; no
    # downstream surface re-derives it. The WP02 stored ``topology`` is read once
    # alongside it (shell read) and threaded in so the placement/surface ``kind``
    # is classified from the stored shape, never re-inferred (FR-004 / SC-001).
    if effective_root is None:
        target_branch = get_feature_target_branch(repo_root, mission_slug)
    else:
        # Prefer the caller-owned surface's stored value, but fall back through
        # the SINGLE canonical adapter (FR-005 thin-reader doctrine): under coord
        # topology ``feature_dir`` may be the coordination worktree, whose mission
        # dir carries no meta.json — falling back to the bare repo default there
        # would silently drop the stored ``target_branch`` (the WP00/FR-004 bug
        # class). ``get_feature_target_branch`` reads the PRIMARY surface's meta
        # and only then degrades to the primary branch.
        from specify_cli.core.paths import read_target_branch_from_meta

        stored_target = read_target_branch_from_meta(feature_dir)
        target_branch = stored_target if stored_target is not None else get_feature_target_branch(repo_root, mission_slug)
    topology = _resolve_topology(
        get_main_repo_root(repo_root),
        mission_slug,
        resolver=resolver,
        effective_root=effective_root,
    )

    identity, branch_ref, status_surface, workspace = _assemble_core_fragments(
        repo_root,
        mission_slug=mission_slug,
        target_branch=target_branch,
        topology=topology,
        cwd=cwd,
        resolver=resolver,
        effective_root=effective_root,
    )
    # IC-05 (WP06 / T019): the artifact-placement ref is the SAME CommitTarget
    # status events resolve to (C-PLACE-1) — assembled from ``branch_ref`` so no
    # surface re-derives a parallel primary/coord placement (C-005).
    artifact_placement = _assemble_artifact_placement_fragment(branch_ref)

    if action in _MISSION_LEVEL_ACTIONS:
        # Mission-level lifecycle actions (planning/analysis/status) resolve the
        # mission context without a work package — FR-011 full-lifecycle parity.
        #
        # FR-004 SSOT adoption (#2070): route the mission-level door through the
        # PURE :func:`resolve_context_for_mission` projection so the "single
        # planning-surface authority" is actually INVOKED, not dead-exported. It
        # carries ``branch_ref.destination_ref`` (a ref-only ``CommitTarget``, C-007)
        # + the artifact placement through unchanged — the SAME ref
        # ``_assemble_core_fragments`` already resolved for the same mission from the
        # stored ``topology``, so this is behaviour-preserving (NFR-003): the
        # destination ref value is byte-identical to the prior direct-factory build. The
        # WP-bearing path still composes its WP fields into the single factory door
        # below; wiring those 13 call sites through the projection is the remaining
        # #2070 increment (carved conservatively — they assemble WP-only fragments
        # the projection does not yet accept).
        return resolve_context_for_mission(
            identity.mission_id,
            topology,
            action=action,
            mission_slug=mission_slug,
            feature_dir=str(feature_dir),
            target_branch=target_branch,
            identity=identity,
            branch_ref=branch_ref,
            status_surface=status_surface,
            workspace=workspace,
            commands=_tasks_commands(mission_slug),
        )

    # The factory (``build_execution_context``) is the SOLE construction door for
    # ``MissionExecutionContext`` (D-6 / IC-01). The WP-bearing actions assemble their
    # fields BEFORE the single build call (no post-build mutation — the composite
    # is frozen).
    base_fields: dict[str, Any] = {
        "action": action,
        "mission_slug": mission_slug,
        "feature_dir": str(feature_dir),
        "target_branch": target_branch,
        "detection_method": "explicit",
        "identity": identity,
        "branch_ref": branch_ref,
        "status_surface": status_surface,
        "workspace": workspace,
        "artifact_placement": artifact_placement,
    }

    wp_fields = _resolve_wp_bearing_fields(
        repo_root,
        action=action,
        mission_slug=mission_slug,
        feature_dir=feature_dir,
        wp_id=wp_id,
        agent=agent,
        locate_work_package=locate_work_package,
        parse_wp_dependencies=parse_wp_dependencies,
        resolve_workspace_for_wp=resolve_workspace_for_wp,
        resolve_lane_alias=resolve_lane_alias,
        planned_lane=Lane.PLANNED,
    )
    return build_execution_context(**base_fields, **wp_fields)
