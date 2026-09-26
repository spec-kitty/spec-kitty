"""MissionStatus aggregate root — Mission Management domain (WP04, FR-015–FR-023).

``MissionStatus`` is the authoritative read/write owner of mission WP lane state
within the Mission Management domain.  It encapsulates topology resolution,
the coord-aware read path, and lane transitions behind a single clean façade.

Usage::

    ms = MissionStatus.load(repo_root=Path("."), mission_slug="034-feature")
    wp_status = ms.claim("WP01")
    lane = wp_status.current_lane

Key constraints
---------------
* ``BookkeepingTransaction`` internals are NOT changed (C-004). ``MissionStatus``
  wraps it, does not replace it.
* When the coord worktree has been materialized but lacks the mission dir,
  ``CoordAuthorityUnavailable`` is raised. Before materialization, the primary
  checkout remains authoritative for the create→first-write window.
* All status reads go through the ``status/`` façade (never direct submodule
  imports from callers).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from specify_cli.core.paths import (
    MissionMetaReadError,
    assert_safe_path_segment,
    load_meta_fail_closed,
)

if TYPE_CHECKING:
    from specify_cli.coordination.types import CommitReceipt
    from specify_cli.status import TransitionRequest
    from specify_cli.status.models import Lane, StatusEvent

_logger = logging.getLogger(__name__)

# The mission ``meta.json`` filename (Sonar S1192 — the literal appears in several
# path joins across the meta-resolution helpers; hoisted to a single constant).
_META_JSON_FILENAME = "meta.json"


def _enrich_transition_request(
    request: TransitionRequest,  # noqa: F821
    *,
    read_dir: Path,
    mission_slug: str,
    current_actor: str | None = None,
) -> TransitionRequest:  # noqa: F821
    """Inject aggregate-owned path/slug (and the WP's current actor) into a request.

    ``current_actor`` is the guard input the aggregate resolves from the
    transactional read surface; a caller-supplied value is never overwritten.
    """
    import dataclasses

    return dataclasses.replace(
        request,
        feature_dir=read_dir,
        current_actor=request.current_actor if request.current_actor is not None else current_actor,
        mission_slug=mission_slug,
    )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CoordAuthorityUnavailable(RuntimeError):
    """Raised when coord-topology is declared but the coord worktree is missing.

    Carry the relevant paths so callers can surface a useful diagnostic.
    """

    def __init__(
        self,
        *,
        mission_slug: str,
        coord_candidate: Path,
        primary_candidate: Path,
    ) -> None:
        self.mission_slug = mission_slug
        self.coord_candidate = coord_candidate
        self.primary_candidate = primary_candidate
        super().__init__(
            f"Coordination worktree unavailable for mission {mission_slug!r}. "
            f"Expected coord path: {coord_candidate}. "
            f"Primary checkout (stale, not used): {primary_candidate}. "
            "Either materialise the coordination worktree or investigate why it is missing."
        )


class MissionMetadataUnavailable(RuntimeError):
    """Raised when an existing mission ``meta.json`` cannot be trusted."""

    def __init__(
        self,
        *,
        mission_slug: str,
        meta_path: Path,
        primary_candidate: Path,
        reason: str,
    ) -> None:
        self.mission_slug = mission_slug
        self.meta_path = meta_path
        self.primary_candidate = primary_candidate
        super().__init__(
            f"Mission metadata unavailable for mission {mission_slug!r}. "
            f"meta.json path: {meta_path}. "
            f"Primary checkout (not used): {primary_candidate}. "
            f"Reason: {reason}. "
            "Fix meta.json before reading mission status."
        )


class InvalidMissionSlug(ValueError):
    """Raised when a ``mission_slug`` is not a safe path segment.

    Mission slugs feed filesystem paths, git refs, and worktree names, so they
    must be a single safe path segment per the canonical
    :func:`specify_cli.core.paths.assert_safe_path_segment` grammar — pure ASCII,
    no path separators, no ``..`` traversal, no leading dot (FR-007,
    DIRECTIVE_010). The offending slug is carried so callers can surface a
    precise diagnostic.
    """

    def __init__(self, mission_slug: str) -> None:
        self.mission_slug = mission_slug
        super().__init__(
            f"Invalid mission slug {mission_slug!r}: mission slugs must be a "
            "single safe path segment (ASCII, no path separators, no '..', no "
            "leading dot)."
        )


# ---------------------------------------------------------------------------
# ActiveWPStatus — read projection for a single WP
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActiveWPStatus:
    """Current lane state for a single WorkPackage within a Mission (read projection).

    Attributes:
        wp_id: Work package identifier (e.g. ``"WP01"``).
        current_lane: The WP's current lane from the event log.
        last_event: The most recent ``StatusEvent`` for this WP, or ``None``
            if no events have been recorded yet.
    """

    wp_id: str
    current_lane: Lane | str
    last_event: StatusEvent | None


# ---------------------------------------------------------------------------
# MissionStatus — aggregate root
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MissionStatus:
    """Aggregate root for mission WP lane state in the Mission Management domain.

    Attributes:
        mission_slug: Human-readable mission slug (e.g. ``"034-feature-name"``).
        mission_id: ULID mission identity from ``meta.json``, or ``None`` for
            legacy missions that predate identity minting.
        mid8: First 8 characters of ``mission_id``, or ``""`` for legacy missions.
        topology: ``"legacy"`` when no coord worktree exists; ``"coordination"``
            when the mission carries a ``coordination_branch`` declaration.
        read_dir: Authoritative directory containing ``status.events.jsonl``.
    """

    mission_slug: str
    mission_id: str | None
    mid8: str
    topology: Literal["legacy", "coordination"]
    read_dir: Path
    repo_root: Path
    coordination_branch: str | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls,
        repo_root: Path,
        mission_slug: str,
    ) -> MissionStatus:
        """Resolve topology once and return the authoritative status aggregate.

        Resolution logic
        ----------------
        1. Read ``meta.json`` to learn ``mission_id`` (and derive ``mid8``).
        2. Resolve the authoritative status directory **once** through the
           canonical :func:`resolve_status_surface` helper — the single
           coord-aware surface authority that ``status_transition`` is also
           built on.
        3. If the coord worktree root exists but lacks the mission dir, the
           canonical helper fails closed; ``load`` surfaces this as
           ``CoordAuthorityUnavailable`` (preserving the historical contract).
        4. Otherwise return the aggregate with the resolved ``read_dir``.

        Args:
            repo_root: Absolute repository root (primary checkout).
            mission_slug: Mission slug; may be bare human form or
                ``<human>-<mid8>`` (post-WP03).

        Returns:
            Populated :class:`MissionStatus` aggregate.

        Raises:
            CoordAuthorityUnavailable: When the coord worktree exists but
                lacks the mission directory.
            MissionMetadataUnavailable: When ``meta.json`` exists but cannot
                be parsed as a trusted object.
            InvalidMissionSlug: When ``mission_slug`` is not a safe path segment
                per ``assert_safe_path_segment`` (empty, non-ASCII, separators,
                ``..`` traversal, or leading dot) (FR-007).
        """
        # 0. Guard the slug at the boundary (FR-007 / DIRECTIVE_010) before it
        #    is used to compose paths, git refs, or worktree names.
        cls._validate_mission_slug(mission_slug)

        # 1. Load meta.json (best-effort; legacy missions may not have one) so
        #    the aggregate carries identity + coord-branch declaration. The
        #    read_dir itself comes from the canonical surface, not from any
        #    hand-rolled composition here (FR-005 / #1821).
        mission_id, coordination_branch, primary_candidate = cls._read_meta(repo_root, mission_slug)
        # Route the mid8 through the authoritative failover resolver instead of
        # an inline ``[:8]`` slice (WP03 / FR-009). ``resolve_mid8`` declines to
        # ``""`` when no declared identity is available, preserving the legacy
        # empty-string contract for missions without a mission_id.
        from specify_cli.lanes.branch_naming import resolve_mid8

        mid8 = resolve_mid8(mission_slug, mission_id=mission_id)

        # 2. Resolve the authoritative status directory through the single
        #    canonical surface. Consume a carried fragment when present; never
        #    re-derive the coord candidate by hand (the second-composition seam
        #    Debby flagged at 01KTPKST closeout).
        read_dir = cls._resolve_read_dir(
            repo_root=repo_root,
            mission_slug=mission_slug,
            primary_candidate=primary_candidate,
        )

        topology: Literal["legacy", "coordination"] = (
            "coordination"
            if cls._is_coord_dir(read_dir, repo_root=repo_root)
            else "legacy"
        )
        return cls(
            mission_slug=mission_slug,
            mission_id=mission_id,
            mid8=mid8,
            topology=topology,
            read_dir=read_dir,
            repo_root=repo_root,
            coordination_branch=coordination_branch,
        )

    @staticmethod
    def _is_coord_dir(read_dir: Path, *, repo_root: Path) -> bool:
        """Return True when the resolved read dir lives in a coord worktree.

        Delegates to the WP03 topology authority
        (:func:`is_registered_coord_worktree`): the git worktree registry
        *disposes* coord-ness, not the path shape. A husk (under ``.worktrees``
        but unregistered) or a lane worktree therefore classifies as ``legacy``,
        killing the split-brain where a lane/husk path silently received coord
        routing (#1589/#1821, F-005). Fails closed via
        :class:`WorktreeRegistryUnavailable` if the registry cannot be read.
        """
        from specify_cli.coordination.surface_resolver import (
            is_registered_coord_worktree,
        )

        # ``bool(...)`` re-narrows the value mypy widens to ``Any`` across the
        # function-local import chain (the predicate is annotated ``-> bool`` at
        # its source; the late import loses the annotation) — Boy Scout fix, no
        # behaviour change.
        return bool(is_registered_coord_worktree(read_dir, repo_root=repo_root))

    @classmethod
    def _resolve_read_dir(
        cls,
        *,
        repo_root: Path,
        mission_slug: str,
        primary_candidate: Path,
    ) -> Path:
        """Resolve the authoritative read dir as a thin adapter over the delegator.

        Delegates the resolve-dir-or-typed-error body to the single WP03
        delegator :func:`resolve_surface_dir_or_typed_error` (FR-009/T4): there
        is now exactly ONE resolution body shared with
        ``mission_runtime.resolution`` rather than a duplicate re-implementation
        of the ``resolve_status_surface`` happy/error tail here. This call site
        keeps only the two aggregate-specific concerns the delegator cannot own:

        * **on_missing_meta = primary_candidate** — the delegator catches
          ``FileNotFoundError`` / ``ValueError`` (no ``meta.json`` yet: the
          create→first-write window) and returns the caller-supplied primary
          directory, so the primary checkout stays authoritative until first
          write (mutation-guarded by ``test_create_first_write_window_*``).
        * **StatusReadPathNotFound → CoordAuthorityUnavailable** — the delegator
          propagates the surface's fail-closed signal unchanged (typed-error
          convergence is WP06's job); the aggregate translates it to its own
          historical boundary type here.
        * **Unmaterialised-coord create-window gate** — when the canonical
          :func:`resolve_status_surface` composes a coord path whose worktree is
          declared but **not yet materialised** (coord branch in meta, pre-first
          write), it returns that composed coord path *as-is* and explicitly
          defers the authority decision to this call site (see the WP03
          delegator docstring: this gate "stays at the aggregate call site"). The
          aggregate keeps the primary checkout authoritative until the coord
          worktree exists, matching the historical ``coord_candidate.exists()``
          semantics — a shape-only check on a not-yet-materialised path, so it
          consumes the blessed ``is_under_worktrees_segment`` shape predicate
          rather than the (git-touching) registry authority.

        The body that re-implemented ``resolve_status_surface``'s happy/error
        tail inline (the ``FileNotFoundError`` → primary and the
        ``StatusReadPathNotFound`` translation) is **consolidated** onto the one
        WP03 delegator (FR-009/T4); only the two genuinely aggregate-specific
        concerns above remain at this seam. C-004: the consolidation is gated on
        WP02's equivalence matrix staying green/xfail-tracked for aggregate's
        input classes.
        """
        from specify_cli.coordination.surface_resolver import (
            CoordinationBranchDeleted,
            is_under_worktrees_segment,
        )
        from specify_cli.missions._read_path_resolver import (
            StatusReadPathNotFound,
            resolve_surface_dir_or_typed_error,
        )

        try:
            resolved_dir: Path = resolve_surface_dir_or_typed_error(
                repo_root,
                mission_slug,
                on_missing_meta=primary_candidate,
            )
        except CoordinationBranchDeleted:
            # ORDERING (WP05 / T023, FR-005): ``CoordinationBranchDeleted`` SUBCLASSES
            # ``StatusReadPathNotFound``, so this more-specific handler MUST sit
            # AHEAD of the re-wrap below — otherwise the subclass is swallowed and
            # re-spelled ``CoordAuthorityUnavailable``, masking the data-loss
            # verdict. A deleted coord branch carrying unmerged status is data loss,
            # not a degraded read: propagate the loud, distinct error VERBATIM so
            # every leg converges on ``COORDINATION_BRANCH_DELETED`` (#1848).
            raise
        except StatusReadPathNotFound as exc:
            raise CoordAuthorityUnavailable(
                mission_slug=mission_slug,
                coord_candidate=exc.coord_candidate,
                primary_candidate=exc.primary_candidate,
            ) from exc
        # Aggregate-specific create-window authority (see docstring): a composed
        # coord dir whose worktree is not yet materialised is not authoritative;
        # the primary checkout owns the create→first-write window until the coord
        # worktree exists. The canonical surface deliberately defers this to the
        # call site (WP03 delegator docstring), so it stays here, not in the
        # shared delegator.
        if is_under_worktrees_segment(resolved_dir) and not resolved_dir.exists():
            return primary_candidate
        return resolved_dir

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_mission_slug(mission_slug: str) -> None:
        """Reject mission slugs outside the ASCII identifier allowlist (FR-007).

        Delegates to the canonical ``assert_safe_path_segment`` (FR-001 / WP01) and
        re-raises any ``ValueError`` as ``InvalidMissionSlug`` to preserve the
        call-site contract (C-001: migrate, don't wrap — no parallel mechanism).

        Raises:
            InvalidMissionSlug: When the slug is empty, non-ASCII, or contains
                characters outside the safe-segment grammar.
        """
        try:
            assert_safe_path_segment(mission_slug)
        except ValueError as exc:
            raise InvalidMissionSlug(mission_slug) from exc

    @staticmethod
    def _read_meta(
        repo_root: Path, mission_slug: str
    ) -> tuple[str | None, str | None, Path]:
        """Read ``meta.json`` and extract identity fields.

        Returns:
            ``(mission_id, coordination_branch, primary_dir)`` — identity
            values may be ``None`` for legacy missions.
        """
        meta_path, primary_dir = MissionStatus._find_meta_path(repo_root, mission_slug)
        if not meta_path.exists():
            return None, None, primary_dir
        try:
            # Canonical reader (FR-005/WP12): allow_missing=False because the
            # ``exists()`` precondition above already resolved the tolerant-missing
            # FR-007: fail-closed reader routing. Malformed meta surfaces typed
            # MissionMetaReadError instead of raw ValueError. Missing files still
            # raise FileNotFoundError (required by race-window handling).
            meta_result = load_meta_fail_closed(primary_dir)
            if meta_result is None:
                raise FileNotFoundError(meta_path)
            meta = meta_result or {}
        except (FileNotFoundError, MissionMetaReadError) as exc:
            _logger.warning(
                "_read_meta: failed to read/parse meta.json for mission %r at %s: %s",
                mission_slug,
                meta_path,
                exc,
            )
            raise MissionMetadataUnavailable(
                mission_slug=mission_slug,
                meta_path=meta_path,
                primary_candidate=primary_dir,
                reason=str(exc),
            ) from exc

        mission_id_value = meta.get("mission_id")
        if mission_id_value is not None and not isinstance(mission_id_value, str):
            raise MissionMetadataUnavailable(
                mission_slug=mission_slug,
                meta_path=meta_path,
                primary_candidate=primary_dir,
                reason=f"mission_id must be string or null, got {type(mission_id_value).__name__}",
            )

        mission_id = mission_id_value or None
        if isinstance(mission_id, str) and not mission_id.strip():
            mission_id = None

        coord_branch = meta.get("coordination_branch")
        if coord_branch is not None and not isinstance(coord_branch, str):
            raise MissionMetadataUnavailable(
                mission_slug=mission_slug,
                meta_path=meta_path,
                primary_candidate=primary_dir,
                reason=f"coordination_branch must be string or null, got {type(coord_branch).__name__}",
            )
        coordination_branch = coord_branch.strip() if isinstance(coord_branch, str) and coord_branch.strip() else None

        return mission_id, coordination_branch, primary_dir

    @staticmethod
    def _find_meta_path(repo_root: Path, mission_slug: str) -> tuple[Path, Path]:
        """Return ``(meta_path, primary_dir)`` via the canonical handle resolver.

        Routes EVERY handle form (full slug, bare mid8, full ULID, numeric
        prefix, ``<slug>-<mid8>`` dir name) so identity is derived exactly
        once — aggregate never self-composes the surface path or does its own
        ``glob`` selection (FR-008). :func:`candidate_feature_dir_for_mission`
        still disambiguates an ambiguous handle to a canonical mission-dir
        NAME, but the primary and canonical directory legs are now composed
        via ``placement_seam(...).read_dir(MissionArtifactKind.
        PRIMARY_METADATA)`` (read-side-seam-primary-primitive-closure-01KYKMMT
        WP07, T033) — the resolved candidate may land in a coord worktree
        (which carries no ``meta.json``), so only its canonical NAME
        re-anchors the meta read on the primary checkout, where ``meta.json``
        always lives.

        The historical silent-first-match glob
        (``sorted(specs_dir.glob(f"{slug}-*/meta.json"))``) is **removed**: an
        ambiguous handle now propagates :class:`MissionSelectorAmbiguous`
        (``error_code == MISSION_AMBIGUOUS_SELECTOR``) instead of silently
        picking the lexically-first candidate — the no-silent-fallback contract
        (C-CTX-4 / C-009 / FR-008). The fail-closed coordination window
        (``StatusReadPathNotFound``) is swallowed so the downstream
        ``_resolve_read_dir`` is the single place that translates it to
        ``CoordAuthorityUnavailable`` (one authority for the typed error).

        Raises:
            MissionSelectorAmbiguous: When ``mission_slug`` is a handle that
                matches more than one mission (FR-008 — never a silent pick).
        """
        from mission_runtime import MissionArtifactKind, placement_seam
        from specify_cli.missions._read_path_resolver import (
            StatusReadPathNotFound,
            _compose_primary_feature_dir,
            candidate_feature_dir_for_mission,
            resolve_bare_modern_mission_dir_name,
        )

        # Compose the primary candidate through the kind-aware placement seam
        # (a PRIMARY-partition kind never transits coord for any topology/coord
        # state), so aggregate never self-composes a raw
        # ``repo_root / KITTY_SPECS_DIR / <slug>`` surface path (WP01
        # raw-bypass; FR-008). The slug is also grammar-checked one level up at
        # the ``load`` boundary. read-side-seam-primary-primitive-closure-
        # 01KYKMMT WP07 (T033): routed through
        # ``placement_seam(...).read_dir(PRIMARY_METADATA)`` -- the seam folds
        # every handle form (bare mid8 / ULID / numeric prefix / bare human
        # slug) to the correct composed primary dir internally, so the caller
        # no longer pre-canonicalizes with ``_canonicalize_primary_read_handle``.
        primary_dir = placement_seam(repo_root, mission_slug).read_dir(
            MissionArtifactKind.PRIMARY_METADATA
        )
        raw_meta = primary_dir / _META_JSON_FILENAME
        # Pure-path happy path: when the literal slug already names an existing
        # primary mission dir with ``meta.json``, it IS the canonical directory
        # — no handle disambiguation (and no git-registry read) is needed. This
        # mirrors ``resolve_mission_read_path``'s own literal-first short-circuit
        # and keeps the meta read off the heavier (git-touching) resolver on the
        # common case.
        if raw_meta.exists():
            return raw_meta, primary_dir
        # Bare modern slug → composed ``<slug>-<mid8>`` primary dir (#2050 read
        # mirror): the operator typed a bare human slug whose on-disk primary dir
        # carries the canonical ``<slug>-<mid8>`` name (e.g. before the coord
        # worktree is materialized, only the composed primary dir exists). The
        # identity resolver below keys on the dir NAME and so cannot map a bare
        # slug onto a composed dir name; the shared canonical primitive bridges
        # that gap (NFR-004 — same definition the ``agent status`` CLI consumes).
        # Re-anchor the meta read on the composed primary dir when it resolves.
        bare_dir_name = resolve_bare_modern_mission_dir_name(repo_root, mission_slug)
        if bare_dir_name is not None:
            # read-side-seam-primary-primitive-closure-01KYKMMT WP07 (T033) /
            # WP08 (T035): calls the module-private leaf directly, not the
            # seam. ``bare_dir_name`` is already the on-disk composed dir NAME
            # returned by ``resolve_bare_modern_mission_dir_name`` --
            # already-canonical by provenance, not a detectable intra-function
            # fold. This exact call carries the machine-checked sanction in
            # ``tests/architectural/test_no_read_side_bypass.py`` (qualname
            # ``MissionStatus._find_meta_path``). WP08 deleted the public wrapper
            # (``primary_feature_dir_for_mission``) this site used to call --
            # ``CANONICALIZER_PRIMITIVE_NAMES`` already recognises the leaf
            # ``_compose_primary_feature_dir`` by literal name, so the pinned
            # entry's token line is re-pointed to it in the same commit rather
            # than orphaned.
            composed_primary = _compose_primary_feature_dir(repo_root, bare_dir_name)
            composed_meta = composed_primary / _META_JSON_FILENAME
            if composed_meta.exists():
                return composed_meta, composed_primary
        try:
            candidate_dir = candidate_feature_dir_for_mission(repo_root, mission_slug)
        except StatusReadPathNotFound:
            # Fail-closed coordination window (coord worktree root materialized,
            # mission dir absent): defer to the literal primary candidate so the
            # downstream ``_resolve_read_dir`` surfaces the converged fail-closed
            # type for EVERY handle form — ``CoordinationBranchDeleted`` when the
            # declared coord branch is gone (#1848, propagated verbatim), else
            # ``CoordAuthorityUnavailable`` — instead of leaking the resolver's raw
            # ``StatusReadPathNotFound`` here.
            return raw_meta, primary_dir
        # ``candidate_feature_dir_for_mission`` resolved a canonical mission
        # directory NAME; re-anchor the meta read on the primary checkout under
        # that canonical name (the candidate itself may be a coord-worktree dir
        # with no ``meta.json``), again via the kind-aware seam. For a literal
        # slug that already matched on disk the name is unchanged and this
        # collapses to the same primary candidate. read-side-seam-primary-
        # primitive-closure-01KYKMMT WP07 (T033): ``candidate_dir.name`` is a
        # composed ``<slug>-<mid8>`` name for a BACKFILLED mission whose
        # on-disk PRIMARY dir still carries the bare ``<slug>``; routing
        # through the seam (rather than the deprecated wrapper's literal
        # compose) means the seam's ``_backfilled_primary_dir`` recovery leg
        # resolves the EXISTING bare-slug dir instead of silently returning a
        # non-existent composed path (NFR-001's one accepted divergence, US3
        # scenario 3) -- pinned by
        # ``tests/specify_cli/status/test_aggregate_read_seam_migration.py``.
        canonical_primary = placement_seam(repo_root, candidate_dir.name).read_dir(
            MissionArtifactKind.PRIMARY_METADATA
        )
        return canonical_primary / _META_JSON_FILENAME, canonical_primary

    # ------------------------------------------------------------------
    # Domain operations
    # ------------------------------------------------------------------

    def claim(self, wp_id: str) -> ActiveWPStatus:
        """Return the current lane state for a WP from the coord-aware read path.

        Args:
            wp_id: Work package identifier (e.g. ``"WP01"``).

        Returns:
            :class:`ActiveWPStatus` with the current lane and last event.
        """
        from specify_cli.status import get_wp_lane, read_events

        events = read_events(self.read_dir)
        current_lane = get_wp_lane(self.read_dir, wp_id)
        wp_events = [e for e in events if e.wp_id == wp_id]
        last_event = wp_events[-1] if wp_events else None
        return ActiveWPStatus(
            wp_id=wp_id,
            current_lane=current_lane,
            last_event=last_event,
        )

    def transition(self, request: TransitionRequest) -> StatusEvent:
        """Apply a lane transition by composing the transactional shell.

        Validation runs exactly once per emit, tree-wide: in the status-owned
        pipeline (``status.transition_pipeline.prepare_transition``), inside
        the transaction, against the in-lock ``from_lane`` the shell derives
        (decision Q4, ``01M1V80R6F6RTMR7Y3C2WBKR32``; spec FR-006 / US2-4).
        The aggregate no longer re-derives the lane, re-infers the review
        gates, or calls ``validate_transition`` itself; it contributes only
        what it owns -- the resolved read surface, the mission slug, and the
        WP's current actor (a guard input the shell cannot see) -- and
        delegates. ``BookkeepingTransaction`` is called by the shell, never
        exposed to callers (C-004).

        Args:
            request: Fully populated :class:`~specify_cli.status.TransitionRequest`.

        Returns:
            The persisted :class:`~specify_cli.status.StatusEvent` (or the
            shell's unpersisted synthetic event on the alias-collapse arm).

        Raises:
            :class:`~specify_cli.status.emit.TransitionError`: When the
                pipeline refuses the (from_lane, to_lane) edge or a guard.
        """
        # C-006 precedent violation, kept deliberately: ``status`` must never
        # import ``coordination``, and this lazy reach is the one existing
        # exception (decision Q4 rider). Removing it means migrating the
        # aggregate's callers onto a status-owned write door -- the future
        # caller-migration mission owns that; do NOT add a second reach.
        from specify_cli.coordination.status_transition import (
            emit_status_transition_transactional,
            read_current_wp_state_transactional,
        )
        from specify_cli.status.models import Lane

        _from_lane, current_actor = self._resolve_current_lane(
            request=request,
            read_current_wp_state_transactional=read_current_wp_state_transactional,
            lane_unseeded=Lane.GENESIS,
        )
        # Inject the resolved read_dir so the transactional path uses the
        # correct (possibly coord-worktree) directory.
        enriched = _enrich_transition_request(
            request,
            read_dir=self.read_dir,
            mission_slug=self.mission_slug,
            current_actor=current_actor,
        )
        return emit_status_transition_transactional(enriched)

    def _resolve_current_lane(
        self,
        *,
        request: TransitionRequest,
        read_current_wp_state_transactional: Any,
        lane_unseeded: Any,
    ) -> tuple[str, str | None]:
        """Resolve the lane/current actor from the transactional authority.

        An unseeded WP resolves to ``genesis`` (``lane_unseeded``), NOT ``planned``:
        a created-but-unfinalized WP cannot be claimed, and the FSM correctly
        rejects ``genesis -> claimed``. The transactional reader already returns
        ``Lane.GENESIS`` for unseeded WPs; the ``Lane.UNINITIALIZED`` read
        sentinel is handled here for any reader that still emits it (#1775
        review M4/Tier 3).

        Verified unreachable via the current production feeder (#2675
        harden): ``read_current_wp_state_transactional`` (the sole caller
        wires ``specify_cli.coordination.status_transition``'s
        implementation) converts ``UNINITIALIZED`` -> ``GENESIS`` itself on
        every path before returning, so ``from_lane_enum`` never actually
        equals ``UNINITIALIZED`` in production today. The branch is kept
        anyway: ``read_current_wp_state_transactional`` is an injected
        callable (typed ``Any`` precisely so tests can substitute readers),
        this method is the single place documented as handling the
        sentinel, and ``test_resolve_current_lane_maps_uninitialized_to_genesis``
        / ``test_transition_helper_maps_uninitialized_lane_to_genesis`` pin
        the mapping directly via an injected reader. Removing it would
        silently drop that documented contract for any future reader
        implementation that legitimately surfaces the sentinel.
        """
        from specify_cli.status.models import Lane as _Lane

        current = read_current_wp_state_transactional(
            feature_dir=self.read_dir,
            mission_slug=self.mission_slug,
            wp_id=request.wp_id or "",
            repo_root=self.repo_root,
        )
        from_lane_enum = current.lane
        if from_lane_enum == _Lane.UNINITIALIZED:
            from_lane_enum = lane_unseeded
        return str(from_lane_enum), current.actor

    def save(self, *, operation: str) -> CommitReceipt:
        """Persist staged transitions via ``BookkeepingTransaction``.

        This is a low-level escape hatch for callers that have already staged
        writes directly on the coord worktree.  Most callers should use
        :meth:`transition` instead.

        Args:
            operation: Human-readable operation label for the commit message.

        Returns:
            :class:`~specify_cli.coordination.types.CommitReceipt` from
            ``BookkeepingTransaction.commit()``.
        """
        from specify_cli.coordination.transaction import BookkeepingTransaction

        if self.mission_id is None or not self.mid8:
            # Compose the diagnostic paths through the kind-aware placement seam
            # so aggregate carries no raw
            # ``repo_root / KITTY_SPECS_DIR / <slug>`` self-composition for any
            # surface — even error-path diagnostics (WP01 raw-bypass).
            # read-side-seam-primary-primitive-closure-01KYKMMT WP07 (T033):
            # routed through ``placement_seam(...).read_dir(PRIMARY_METADATA)``
            # -- the seam folds every handle form internally, so the caller no
            # longer pre-canonicalizes with ``_canonicalize_primary_read_handle``.
            from mission_runtime import MissionArtifactKind, placement_seam

            diag_primary = placement_seam(
                self.repo_root, self.mission_slug
            ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
            raise MissionMetadataUnavailable(
                mission_slug=self.mission_slug,
                meta_path=diag_primary / _META_JSON_FILENAME,
                primary_candidate=diag_primary,
                reason="mission_id is required to persist via BookkeepingTransaction",
            )
        # FR-006 fold-in (cluster-B): compose the destination ref through the
        # canonical branch-identity authority instead of the legacy
        # ``f"kitty/mission-{slug}"`` f-string (which named a branch that never
        # existed for mid8-era missions). ``mission_id`` is guaranteed present
        # by the guard above, so this always resolves the mid8-era branch.
        from specify_cli.lanes.branch_naming import mission_branch_name_required
        from specify_cli.status.reducer import SNAPSHOT_FILENAME
        from specify_cli.status.store import EVENTS_FILENAME

        destination_ref = self.coordination_branch or mission_branch_name_required(
            self.mission_slug, self.mission_id
        )

        with BookkeepingTransaction.acquire(
            repo_root=self.repo_root,
            mission_id=self.mission_id,
            mission_slug=self.mission_slug,
            mid8=self.mid8,
            destination_ref=destination_ref,
            operation=operation,
        ) as txn:
            for artifact_name in (EVENTS_FILENAME, SNAPSHOT_FILENAME):
                artifact = txn.feature_dir / artifact_name
                if artifact.exists():
                    txn.stage_path(artifact)
            return txn.commit(operation)


__all__ = [
    "ActiveWPStatus",
    "CoordAuthorityUnavailable",
    "InvalidMissionSlug",
    "MissionMetadataUnavailable",
    "MissionStatus",
]
