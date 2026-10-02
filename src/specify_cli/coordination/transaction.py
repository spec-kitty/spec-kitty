"""BookkeepingTransaction — atomic emit + commit on the coordination branch.

This module implements the contract in
``contracts/bookkeeping_transaction.md``.

It is the single owner of writes that target the coordination branch:

    acquire → policy gate → append → materialize → commit → outbound → release

On exception, performs **surgical truncate** rollback of the event log
(FR-010) and byte-snapshot rollback of any other artifact written via
:meth:`BookkeepingTransaction.write_artifact`. It NEVER uses
``git checkout --`` (C-009 prohibits it for any rollback path).

Spec source: FR-019, FR-020, FR-021, FR-023, FR-026, FR-033, C-009,
C-013, NFR-001, NFR-008, NFR-010.
"""

from __future__ import annotations

from specify_cli.core.constants import WORKTREES_DIR
import logging
import subprocess
from collections.abc import Callable
from contextlib import AbstractContextManager
from kernel.clock import now_utc
from kernel.git import GitCommandError, status_entries
from pathlib import Path
from types import TracebackType
from typing import NamedTuple

from specify_cli.coordination.policy import (
    WorkflowMutationPolicy,
    _normalize_ref,
)
from specify_cli.coordination.status_service import (
    EventLogWriteContract,
    append_event_stream_log,
)
from specify_cli.coordination.types import (
    Allowed,
    CommitReceipt,
    PolicyVerdict,
    DESTINATION_REF_NOT_FOUND,
    GitChangeSet,
    PendingEventHandle,
    PROTECTED_BRANCH_REFUSED,
    Refused,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from mission_runtime import CommitTarget, MissionArtifactKind, OwnedCheckout, placement_seam
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.coordination.coord_seed import CoordSeedForkRefused
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
)
from specify_cli.git.commit_helpers import (
    SafeCommitPathPolicyError,
    SafeCommitRecoveryFailed,
    safe_commit,
)
from specify_cli.lanes.branch_naming import coord_mission_dir_name
from specify_cli.status import reducer as _reducer
from specify_cli.status.locking import (
    FeatureStatusLockTimeoutError,
    feature_status_lock,
)
from specify_cli.status.models import InnerStateChanged, StatusEvent

# WP08 campsite split (behaviour-free): the error hierarchy, the legacy-mission
# resolution helpers, and the confined-atomic-write leaf primitives now live in
# sibling modules. They are re-exported here so existing
# ``from specify_cli.coordination.transaction import <name>`` imports (and the
# ``transaction_module.<name>`` monkeypatch surfaces used by the oracle) keep
# resolving to the same objects.
from specify_cli.coordination.transaction_errors import (
    BookkeepingCommitFailed,
    BookkeepingDoubleEventId,
    BookkeepingError,
    BookkeepingLegacyResolutionFailed,
    BookkeepingLockTimeout,
    BookkeepingPolicyRefused,
    BookkeepingWorktreeMissing,
)
from specify_cli.coordination.legacy_resolution import (
    _checkout_mission_dir,
    _coordination_branch_from_meta,
    _emit_legacy_warning_once,
    _is_legacy_mission,
    _mission_specs_dir_name,
    _resolve_legacy_lane_destination,
    _validate_safe_segment,
    _warrants_legacy_warning,
)
from specify_cli.coordination.legacy_resolution import (
    _legacy_warning_marker_path as _legacy_warning_marker_path,
)

# WP09 (T052 / C-010): the confined-artifact orchestration helpers moved to
# ``coordination.atomic_write`` behind a dependency-injection ``resolve`` seam so
# ``transaction.py`` lands ≤ 1000 LOC even after the owner gains its new
# capabilities. ``_resolve_confined_artifact_path`` is re-imported under the same
# name so the campsite oracle's symlink-swap-on-resolve confinement attack stays
# exercisable through ``transaction._resolve_confined_artifact_path``; the thin
# write/unlink wrappers below inject that module-level resolver so a monkeypatch on
# THIS module's name governs the internal write-path resolves.
from specify_cli.coordination.atomic_write import (
    _confine_path_to_worktree,
    _resolve_confined_artifact_path,
    _unlink_confined_artifact_path as _aw_unlink_confined_artifact_path,
    _write_confined_artifact_bytes as _aw_write_confined_artifact_bytes,
    restore_generated_artifact_snapshots,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_EVENTS_FILENAME = "status.events.jsonl"
_SNAPSHOT_FILENAME = "status.json"


def _canonical_coord_mission_slug(
    seam_repo_root: Path,
    mission_slug: str,
    mid8: str,
    *,
    owned: OwnedCheckout | None,
) -> str:
    """Pick the mission_slug form whose ``meta.json`` actually declares coordination.

    coord-artifact-single-home-01M3V4BE WP07 (T039 step 4, campsite fix): a
    caller's ``mission_slug`` may be bare (not embedding ``mid8``) in TWO
    genuinely different on-disk shapes, and composing blindly breaks one of
    them:

    * A bare caller whose primary dir is itself the CANONICAL ``<slug>-<mid8>``
      name (e.g. ``test_transaction.py``'s ``MISSION_SLUG = "demo-feature"``,
      ``mid8 = "01J6XW9K"``, primary dir ``demo-feature-01J6XW9K``) -- the
      literal bare slug's ``meta.json`` does not exist, so it must be composed.
    * A mission whose primary dir is ITSELF bare (no ``-<mid8>`` suffix at
      all), even though its coordination branch is a canonical
      ``<slug>-<mid8>`` ref -- composing here invents a primary dir that does
      not exist, so ``establish_coord_write_location`` silently classifies
      PRIMARY (no meta found) instead of the real COORD mission.

    Checks the LITERAL ``mission_slug`` dir first -- genuinely literally, not
    through ``read_primary_meta``'s own canonicalization fallback (review
    cycle 2, coord-artifact-single-home-01M3V4BE WP09): that fallback now
    folds a bare human slug to its composed ``<slug>-<mid8>`` dir internally
    (the B1-residual same-family fix), so ``read_primary_meta(seam_repo_root,
    mission_slug)`` can report ``declares=True`` for a BARE slug whose
    on-disk dir is ITSELF the composed name -- exactly shape one below -- and
    this function would then wrongly keep the bare slug as "already
    canonical", handing the bare form to ``write_dir``/the seed mechanics
    (which use it verbatim in git operations, not just meta resolution).
    Only when the literal dir's OWN ``meta.json`` exists does this return
    ``mission_slug`` unchanged; otherwise it retries the mid8-composed
    canonical name exactly as before.
    """
    if owned is not None:
        # Zero I/O: the fact already carries its own canonical mission_slug.
        return owned.mission_slug
    from specify_cli.missions._read_path_resolver import literal_primary_dir_has_meta, read_primary_meta

    # Review cycle 3 (C3-B1): composed through ``literal_primary_dir_has_meta``
    # -- a PUBLIC sibling of ``read_primary_meta`` living in the read-
    # sanctioned module (never a raw ``KITTY_SPECS_DIR`` join here, which
    # regressed ``test_single_mission_surface_resolver.py``'s FR-004
    # raw-bypass gate; and never a direct call to the module-private
    # ``_compose_primary_feature_dir`` leaf from this non-sanctioned module,
    # which regresses ``test_no_read_side_bypass.py``'s FR-005/IC-06 gate).
    # Still genuinely LITERAL: it folds nothing, so the check below still
    # bypasses ``read_primary_meta``'s bare-slug fold exactly as before (M6
    # pins this is load-bearing).
    if literal_primary_dir_has_meta(seam_repo_root, mission_slug):
        return mission_slug
    composed = coord_mission_dir_name(mission_slug, mid8=mid8)
    if composed == mission_slug:
        return mission_slug
    _composed_meta, composed_declares = read_primary_meta(seam_repo_root, composed)
    return composed if composed_declares else mission_slug


class _CoordWriteTarget(NamedTuple):
    """What the coordination arm takes from ``write_dir``'s ``WriteLocation``."""

    worktree_root: Path
    feature_dir: Path
    seed_committed: bool


def _resolve_coord_worktree_root_for_transaction(
    *,
    repo_root: Path,
    mission_slug: str,
    mid8: str,
    owned: OwnedCheckout | None,
) -> _CoordWriteTarget:
    """Materialize/seed the coordination write location for the coordination arm.

    coord-artifact-single-home-01M3V4BE WP07 (T039): replaces the bare
    ``CoordinationWorkspace.resolve`` call, which only materializes an
    ``UNMATERIALIZED`` worktree and is blind to ``EMPTY`` -- the first
    transactional write on a pre-fix ``EMPTY`` coordination surface used to
    create the Mission dir itself and fork the log instead of carrying the
    root-checkout records over once. ``write_dir`` (WP03/WP04) materializes,
    seeds or restores as the state requires, or refuses loudly; its
    ``checkout_root`` AND ``path`` are returned (never ``.path.parent.parent``,
    never a re-composed ``checkout_root / KITTY_SPECS_DIR / name``): the
    caller uses ``WriteLocation.path`` verbatim as the transaction's
    ``feature_dir`` (FR-014 -- a COORD writer never re-derives its write
    location; coordination-write-gate cap 0).

    ``repo_root`` here is the REAL repository root (``owned.repository_root``
    when owned), never the inner lock root ``_acquire_locked`` itself resolves
    worktree-relative paths against -- the placement seam always anchors on
    the actual git repository, with ``owned`` threaded separately.

    ``mission_slug``/``mid8`` arrive as this call's own two-part addressing
    (a caller may pass a BARE slug that does not embed ``mid8``), but the
    placement seam resolves ``meta.json`` off the CANONICAL on-disk
    ``<slug>-<mid8>`` directory name -- so the seam is built from
    ``coord_mission_dir_name(mission_slug, mid8=mid8)`` (the same primitive
    :func:`_mission_specs_dir_name` / ``coord_seed._transaction_dir_name``
    already delegate to), never the raw ``mission_slug``, or a bare-slug
    caller's ``meta.json`` read silently finds nothing and the seam degrades
    to the PRIMARY checkout instead of the coordination worktree (T039 step 4
    dir-name agreement).

    The accessor's own typed refusals (``CoordinationWorktreeUnmaterialized``,
    ``CoordinationBranchDeleted``, ``CoordSeedForkRefused``, a
    ``STATUS_LOCK_HELD``-coded ``FeatureStatusLockTimeoutError``) propagate
    UNCHANGED -- callers that render coordination-specific recovery hints for
    these types must keep catching them. Only a genuinely unexpected
    materialization failure is wrapped into :class:`BookkeepingWorktreeMissing`,
    matching the exception this call site always raised for that case.

    coord-artifact-single-home-01M3V4BE WP07 (review cycle 2 R1), corrected by
    WP09 (review cycle 3 follow-up): also returns whether THIS call's own
    ``write_dir`` resolution just committed a genuine seed commit onto the
    coordination branch (``location.seed is not None and
    location.seed.coord_commit is not None``) -- the caller (``_acquire_locked``)
    threads this onto the transaction as ``seed_committed_this_txn`` so
    :meth:`BookkeepingTransaction.commit_idempotent` can tell "this
    transaction's OWN seed just committed content I never staged" apart from
    "this Mission merely has pre-existing history" (``events_path.exists()``
    alone cannot -- it is true for both). Gating on ``establishment`` alone
    (the WP07 shape) is WRONG: a ``RESTORED_FROM_BRANCH`` establishment can
    restore COORD-kind paths from the tip without producing a new commit (the
    restored content already matches the tip byte-for-byte, so the follow-up
    seed-commit attempt is a genuine git no-op, ``coord_commit=None``) --
    that acquire committed nothing, so the branch tip never moved and a
    caller that staged nothing must still see the empty-changeset
    :class:`BookkeepingCommitFailed`, not a silent no-op receipt.
    """
    seam_repo_root = owned.repository_root if owned is not None else repo_root
    canonical_mission_slug = _canonical_coord_mission_slug(seam_repo_root, mission_slug, mid8, owned=owned)
    try:
        location = placement_seam(seam_repo_root, canonical_mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE)
    except (
        CoordinationWorktreeUnmaterialized,
        CoordinationBranchDeleted,
        CoordSeedForkRefused,
        FeatureStatusLockTimeoutError,
    ):
        raise
    except Exception as exc:
        # Domain-error surface: any genuinely unexpected materialization failure
        # (programming bug, unforeseen git-plumbing error) becomes the typed
        # BookkeepingWorktreeMissing this call site has always raised for that
        # case, rather than propagating an unclassified exception to callers
        # that only expect this module's own error hierarchy.
        identity = coord_mission_dir_name(mission_slug, mid8=mid8)
        raise BookkeepingWorktreeMissing(f"Failed to resolve coordination worktree for {identity}: {exc}") from exc
    # coord-artifact-single-home-01M3V4BE WP09 (review-cycle-3 follow-up on
    # WP07): a RESTORED_FROM_BRANCH establishment does not, by itself, mean
    # THIS acquire committed anything -- ``_handle_empty_post_fix`` restores
    # the COORD-kind paths from the branch tip first (a worktree checkout,
    # no commit) and only THEN seeds any root-only records; when the root
    # checkout carries nothing new the resulting ``_commit_and_restore`` seed
    # commit is a genuine git no-op (``coord_commit=None``) because the
    # restored content already matches the coordination tip byte-for-byte.
    # Gating on ``establishment`` alone made ``commit_idempotent`` treat that
    # case as "this acquire's own seed already committed my content", so a
    # caller that staged nothing got a silent no-op receipt pinned at a HEAD
    # the branch tip never actually moved to, instead of the genuinely empty
    # changeset ``BookkeepingCommitFailed`` base behaviour. Gate on the
    # ``SeedReport`` itself: only a seed that actually produced a commit this
    # call (``location.seed.coord_commit is not None``) counts.
    seed_committed_this_txn = location.seed is not None and location.seed.coord_commit is not None
    return _CoordWriteTarget(
        worktree_root=location.checkout_root,
        feature_dir=location.path,
        seed_committed=seed_committed_this_txn,
    )


def _write_confined_artifact_bytes(
    worktree_root: Path,
    path: Path,
    content: bytes,
) -> Path:
    """Write bytes, injecting this module's resolver (oracle-patchable)."""
    return _aw_write_confined_artifact_bytes(worktree_root, path, content, resolve=_resolve_confined_artifact_path)


def _unlink_confined_artifact_path(worktree_root: Path, path: Path) -> None:
    """Unlink an artifact, injecting this module's resolver (oracle-patchable)."""
    _aw_unlink_confined_artifact_path(worktree_root, path, resolve=_resolve_confined_artifact_path)


# WP06 swap: the canonical builder now lives in ``status.emit`` so the
# status domain owns it (FR-032). Re-export under the original name to
# keep ``coordination.build_status_event`` import-compatible for any
# callers that imported it through this module.
from specify_cli.status.emit import build_status_event  # noqa: E402,F401

__all__ = [
    "BookkeepingCommitFailed",
    "BookkeepingDoubleEventId",
    "BookkeepingError",
    "BookkeepingLockTimeout",
    "BookkeepingPolicyRefused",
    "BookkeepingTransaction",
    "BookkeepingWorktreeMissing",
    "build_status_event",
]


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


def _caller_ref_refusal(
    *,
    repo_root: Path,
    mission_slug: str,
    mid8: str,
    destination_ref: str,
    operation: str,
    capability: GuardCapability,
    owned: OwnedCheckout | None = None,
) -> Refused | None:
    """The coordination arm's caller-ref verdict: the ``Refused`` acquire raises, else ``None``.

    ``None`` when the caller's ref is allowed OR the refusal is recoverable: a
    protected caller ref of a mission whose meta declares this coordination branch
    is redirected there, and a missing caller ref that IS the coordination branch
    is left for coordination-worktree resolution to report.
    """
    coord_branch = CoordinationWorkspace.branch_name(mission_slug, mid8)
    caller_change_set = GitChangeSet(
        destination_ref=destination_ref,
        repo_root=repo_root,
        worktree_root=repo_root,
        paths=(),
        message=f"<pending: {operation}>",
        operation=operation,
        capability=capability,
        mission_slug=mission_slug,
    )
    caller_verdict = WorkflowMutationPolicy.assert_allowed(
        caller_change_set,
        coord_available=True,
        owned=owned,
    )
    if not isinstance(caller_verdict, Refused):
        return None
    explicit_coord_branch = _coordination_branch_from_meta(repo_root, mission_slug, mid8)
    can_recover_to_coord_branch = caller_verdict.error_code == PROTECTED_BRANCH_REFUSED and explicit_coord_branch == coord_branch
    allow_coord_resolution_to_report_missing_branch = caller_verdict.error_code == DESTINATION_REF_NOT_FOUND and destination_ref == coord_branch
    if can_recover_to_coord_branch or allow_coord_resolution_to_report_missing_branch:
        return None
    return caller_verdict


def _preflight_policy_verdict(
    *,
    repo_root: Path,
    primary_root: Path | None,
    worktree_root: Path,
    mission_slug: str,
    destination_ref: str,
    status_paths: tuple[Path, Path],
    operation: str,
    capability: GuardCapability,
    owned: OwnedCheckout | None = None,
) -> PolicyVerdict:
    """Step 4 of acquire: the pre-flight policy gate over the would-be status commit.

    The ONE implementation shared by :meth:`BookkeepingTransaction._acquire_locked`
    and the lock-free :meth:`BookkeepingTransaction.preflight_refusal` (#5385, C-001).
    Pure apart from the policy's read-only git/config probes.
    """
    from specify_cli.coordination.commit_router import (
        mission_has_coordination_branch,
    )

    change_set = GitChangeSet(
        destination_ref=destination_ref,
        repo_root=owned.repository_root if owned is not None else (primary_root or repo_root),
        worktree_root=worktree_root,
        paths=status_paths,
        message=f"<pending: {operation}>",
        operation=operation,
        capability=capability,
        mission_slug=mission_slug,
    )
    coord_available = mission_has_coordination_branch(repo_root, mission_slug)
    return WorkflowMutationPolicy.assert_allowed(change_set, coord_available=coord_available, owned=owned)


class BookkeepingTransaction(AbstractContextManager["BookkeepingTransaction"]):
    """The single chokepoint for coordination-branch writes.

    Use :meth:`acquire` to construct; do NOT call ``__init__`` directly.
    Use as a context manager:

    .. code-block:: python

        with BookkeepingTransaction.acquire(...) as txn:
            handle = txn.append_event(event)
            receipt = txn.commit("status: WP01 → claimed")
    """

    # ---- construction is private; use acquire() ----

    def __init__(
        self,
        *,
        repo_root: Path,
        mission_id: str,
        mission_slug: str,
        mid8: str,
        destination_ref: str,
        operation: str,
        worktree_root: Path,
        feature_dir: Path,
        events_path: Path,
        snapshot_path: Path,
        pre_emit_size: int,
        pre_emit_events_existed: bool,
        lock_cm: AbstractContextManager[Path],
        seed_committed_this_txn: bool = False,
    ) -> None:
        # Note: most attributes are public-but-immutable-by-convention.
        # ``mypy --strict`` is satisfied because we do not annotate them
        # as ``Final`` and we never re-bind them after construction.
        self.repo_root = repo_root
        self._owned: OwnedCheckout | None = None
        self.mission_id = mission_id
        self.mission_slug = mission_slug
        self.mid8 = mid8
        self.destination_ref = destination_ref
        self.operation = operation
        self.worktree_root = worktree_root
        self.feature_dir = feature_dir
        self._events_path = events_path
        self._snapshot_path = snapshot_path
        self._pre_emit_size = pre_emit_size
        self._pre_emit_events_existed = pre_emit_events_existed
        self._seed_committed_this_txn = seed_committed_this_txn
        self._lock_cm = lock_cm

        # Per-transaction mutable state.
        self._event_ids: list[str] = []
        self._seen_event_ids: set[str] = set()
        # Snapshot of every artifact ever written via write_artifact().
        # None ⇒ file did not exist pre-write (rollback unlinks it).
        self._snapshots: dict[Path, bytes | None] = {}
        # Snapshot of every subprocess byproduct enrolled via
        # enroll_subprocess_byproducts() (C3). None ⇒ absent pre-transaction, so
        # rollback unlinks the child-created file instead of abandoning it.
        self._byproduct_snapshots: dict[Path, bytes | None] = {}
        # Snapshot of status.json pre-emit (used to restore exact bytes
        # on rollback, NOT re-materialise — keeps SHA-256 identical).
        self._pre_emit_snapshot_existed: bool | None = None
        self._pre_emit_snapshot_bytes: bytes | None = None
        # Paths we will pass to safe_commit() on commit().
        self._staged_paths: list[Path] = []
        # Outbound side-effects deferred until commit succeeds.
        self._deferred: list[Callable[[], None]] = []
        self._committed = False
        self._commit_recovery_failed_after_commit = False
        self._explicit_commit_message: str | None = None
        self._explicit_commit_receipt: CommitReceipt | None = None
        self._capability: GuardCapability = GuardCapability.STANDARD
        self._legacy_mode = False

    # ---- acquire ----

    @classmethod
    def acquire(
        cls,
        *,
        repo_root: Path,
        mission_id: str,
        mission_slug: str,
        mid8: str,
        destination_ref: str,
        operation: str,
        timeout: float = 30.0,
        capability: GuardCapability = GuardCapability.STANDARD,
        commit_to_primary_target: bool = False,
        owned: OwnedCheckout | None = None,
    ) -> BookkeepingTransaction:
        """Construct, lock, and run the pre-flight policy gate.

        The feature-status lock is acquired before worktree resolution so
        first-time coordination worktree creation is serialized across
        concurrent emitters. Policy refusal still happens before any
        bookkeeping write.

        ``commit_to_primary_target`` (write-path-integrity WP02 / FR-001):
        an OPT-IN routing signal for the partition-aware planning-artifact
        commit. By default (``False``) a coordination-topology mission
        redirects every write to the coordination branch + coord worktree
        (the historical behaviour every status caller relies on -- status
        events already resolve their ``destination_ref`` to the coord ref,
        so the redirect is a no-op for them). When ``True`` the caller is
        committing a PRIMARY-partition artifact (e.g. ``lanes.json`` /
        ``spec.md``) that MUST land on the mission's own ``destination_ref``
        (the primary target branch) from the primary checkout -- so the
        coord redirect is skipped and ``worktree_root`` is ``repo_root``.
        This is the fix for the #3371 P0 where a PRIMARY ``lanes.json`` was
        silently redirected onto the coordination branch and add/add-
        conflicted at lane allocation. Only the planning PRIMARY-partition
        caller (``implement.py::_run_planning_artifact_commit``) sets it;
        every other caller keeps the default, so no status/coord write path
        changes behaviour.

        On a lock-acquire timeout, raises :class:`BookkeepingLockTimeout`.

        On a missing coordination worktree, raises
        :class:`BookkeepingWorktreeMissing`.
        """
        # 1. Normalise + shape-check destination_ref FIRST. The policy
        # gate also checks shape, but normalising once here makes the
        # internal state consistent (HEAD assertion in safe_commit will
        # compare to short-form).
        normalised_ref = _normalize_ref(destination_ref)

        # 2. Acquire the feature status lock before worktree resolution. The
        # lock context manager is held open across the lifetime of the
        # transaction object; on any setup failure below, release it before
        # propagating the domain error.
        lock_root = owned.owned_root if owned is not None else repo_root
        lock_cm = feature_status_lock(lock_root, _mission_specs_dir_name(mission_slug, mid8), timeout=timeout)
        try:
            lock_cm.__enter__()
        except FeatureStatusLockTimeoutError as exc:
            raise BookkeepingLockTimeout(str(exc)) from exc

        try:
            return cls._acquire_locked(
                repo_root=lock_root,
                mission_id=mission_id,
                mission_slug=mission_slug,
                mid8=mid8,
                destination_ref=destination_ref,
                normalised_ref=normalised_ref,
                operation=operation,
                lock_cm=lock_cm,
                capability=capability,
                commit_to_primary_target=commit_to_primary_target,
                owned=owned,
            )
        except Exception:
            lock_cm.__exit__(None, None, None)
            raise

    @classmethod
    def preflight_refusal(
        cls,
        *,
        repo_root: Path,
        mission_slug: str,
        mid8: str,
        destination_ref: str,
        operation: str,
        capability: GuardCapability = GuardCapability.STANDARD,
        owned: OwnedCheckout | None = None,
    ) -> Refused | None:
        """The ``Refused`` :meth:`acquire` would raise as ``BookkeepingPolicyRefused``, else ``None``.

        A lock-free probe (#5385): no feature-status lock, no coordination worktree
        creation, no writes. It selects the write arm with the SAME classifiers
        ``_acquire_locked`` uses and runs the SAME policy gate
        (:func:`_preflight_policy_verdict`), so a caller can refuse up front
        exactly what the real write would refuse later (C-001: no second rule).
        ``repo_root`` is the primary checkout root; ``owned`` is the owned-checkout
        carrier (``None`` for a non-owned mission), threaded into the policy gate so
        an owned mission resolves protection through ``resolve_for_owned`` exactly as
        its real write does.

        * coordination arm: the caller-ref verdict (:func:`_caller_ref_refusal`),
          then the gate against the redirected coordination branch. A missing
          coordination branch is not a POLICY refusal: :meth:`acquire` does not
          create it, it fails closed with ``BookkeepingWorktreeMissing`` when
          resolving the coordination worktree, before its gate runs -- so the
          probe returns ``None`` and leaves that failure to the real write;
        * genuinely-legacy arm: ``None`` -- its destination is the operator's
          lane HEAD, which is not knowable before the run;
        * modern coordination-less arm: the gate against ``destination_ref`` on
          the primary checkout.

        C-001 (no second rule): the probe carries ``owned`` verbatim into
        :func:`_preflight_policy_verdict`, so it resolves protection the same way the
        real write does — ``owned=None`` (e.g. the consolidate ``done`` write,
        ``done_bookkeeping._mark_wp_merged_done``, which builds an owned-less request)
        resolves via ``resolve(repo_root).for_mission``; an owned mission resolves via
        ``resolve_for_owned``. Arm classification stays on the primary ``repo_root``.
        """
        arm_root = repo_root
        safe_mission_slug = _validate_safe_segment("mission_slug", mission_slug)
        safe_mid8 = _validate_safe_segment("mid8", mid8)
        effective_destination_ref = destination_ref
        coordination_arm = not _is_legacy_mission(arm_root, safe_mission_slug, safe_mid8)
        if not coordination_arm:
            if _warrants_legacy_warning(arm_root, safe_mission_slug, safe_mid8):
                return None
            worktree_root = arm_root
        else:
            caller_refusal = _caller_ref_refusal(
                repo_root=arm_root,
                mission_slug=safe_mission_slug,
                mid8=safe_mid8,
                destination_ref=destination_ref,
                operation=operation,
                capability=capability,
                owned=owned,
            )
            if caller_refusal is not None:
                return caller_refusal
            worktree_root = CoordinationWorkspace.worktree_path(arm_root, safe_mission_slug, safe_mid8)
            effective_destination_ref = CoordinationWorkspace.branch_name(safe_mission_slug, safe_mid8)
        feature_dir = _checkout_mission_dir(worktree_root, safe_mission_slug, safe_mid8)
        events_path = feature_dir / _EVENTS_FILENAME
        snapshot_path = feature_dir / _SNAPSHOT_FILENAME
        verdict = _preflight_policy_verdict(
            repo_root=arm_root,
            primary_root=None,
            worktree_root=worktree_root,
            mission_slug=safe_mission_slug,
            destination_ref=effective_destination_ref,
            status_paths=(events_path, snapshot_path),
            operation=operation,
            capability=capability,
            owned=owned,
        )
        if not isinstance(verdict, Refused):
            return None
        if coordination_arm and verdict.error_code == DESTINATION_REF_NOT_FOUND:
            # Coordination arm: ``acquire`` resolves the coordination worktree BEFORE
            # this gate runs and, when the coordination branch is missing, fails
            # closed there with ``BookkeepingWorktreeMissing`` (it never creates the
            # branch). The real write never reaches a policy refusal for it, so
            # this is not a ``Refused`` the probe may report.
            return None
        return verdict

    @classmethod
    def _acquire_locked(
        cls,
        *,
        repo_root: Path,
        mission_id: str,
        mission_slug: str,
        mid8: str,
        destination_ref: str,
        normalised_ref: str,
        operation: str,
        lock_cm: AbstractContextManager[Path],
        capability: GuardCapability = GuardCapability.STANDARD,
        commit_to_primary_target: bool = False,
        owned: OwnedCheckout | None = None,
    ) -> BookkeepingTransaction:
        safe_mission_slug = _validate_safe_segment("mission_slug", mission_slug)
        safe_mid8 = _validate_safe_segment("mid8", mid8)
        effective_destination_ref = destination_ref
        effective_normalized_ref = normalised_ref
        # Review cycle 2 R1: only the coordination arm below can ever set this
        # True (it is the one arm that calls write_dir); every other arm
        # (legacy, commit_to_primary_target) never seeds a coordination
        # surface, so it stays False for them.
        seed_committed_this_txn = False
        # Set ONLY by the coordination arm: ``WriteLocation.path`` as returned
        # by ``write_dir`` (never re-composed here). ``None`` for the
        # non-coordination checkouts (legacy lane worktree, primary checkout).
        coord_feature_dir: Path | None = None

        # Resolve the worktree.  Two paths exist (WP08 T035–T036, SC-11):
        #
        # (a) **New topology** (default): the mission's meta.json carries
        #     ``coordination_branch``.  We resolve the per-mission coord
        #     worktree at ``.worktrees/<slug>-<mid8>-coord/`` (created on
        #     first call by ``CoordinationWorkspace.resolve``).  The
        #     ``destination_ref`` passed in by the caller already names
        #     the coord branch.
        #
        # (b) **Legacy mission** (pre-WP03 / pre-PR2): the mission's
        #     ``meta.json`` lacks ``coordination_branch``.  Bookkeeping
        #     for this mission must run against the operator's current
        #     LANE worktree + its checked-out branch, exactly how it did
        #     before the coord topology landed.  We override the caller-
        #     supplied ``destination_ref`` with the actual lane branch
        #     name resolved from the worktree's ``HEAD`` so the pre-flight
        #     policy gate and the ``safe_commit`` HEAD assertion see a
        #     consistent ref.
        #
        # Crucial invariant: **every other step of acquire() below — the
        # pre-flight policy gate, the feature-status lock, the surgical
        # truncate rollback, and the outbound deferral — applies
        # uniformly to both paths.**  Only ``worktree_root`` and (in
        # legacy mode) ``destination_ref`` differ.
        legacy_mode = _is_legacy_mission(repo_root, safe_mission_slug, safe_mid8)
        if legacy_mode:
            # #2453: ``_is_legacy_mission`` alone conflates two shapes that
            # both merely lack ``coordination_branch`` — a genuinely-legacy
            # (pre-SSOT) mission AND a MODERN coordination-less mission
            # (``single_branch``/``lanes`` stored topology, or ``flattened``).
            # ``_warrants_legacy_warning`` already carries the SAME
            # stored-topology classification the sibling warning-fix (#2351)
            # introduced (C-005) — reuse it here as the routing split too,
            # rather than inventing a second classifier.
            genuinely_legacy = _warrants_legacy_warning(
                repo_root,
                safe_mission_slug,
                safe_mid8,
            )
            if genuinely_legacy:
                # Genuinely-legacy: unchanged pre-#2453 behaviour — resolve
                # the operator's current lane worktree + its checked-out
                # branch (there is no other reliable write target for a
                # mission that predates the coordination-branch topology).
                try:
                    worktree_root, lane_branch = _resolve_legacy_lane_destination(
                        repo_root,
                    )
                except BookkeepingLegacyResolutionFailed:
                    raise
                # Override caller-supplied destination_ref with the actual
                # lane branch so policy + HEAD assertion both see truth.
                effective_normalized_ref = _normalize_ref(lane_branch)
                effective_destination_ref = effective_normalized_ref
                _emit_legacy_warning_once(repo_root, mission_id, safe_mission_slug)
            else:
                # Modern coordination-less mission (#2453 / #2647): its
                # coordination-less shape was CHOSEN (stored topology) or is
                # ``flattened`` — it is not pre-SSOT debt. The write target is
                # the canonical mission surface: the primary checkout
                # (``repo_root``) on the caller-supplied ``destination_ref``,
                # which the caller already resolves CWD-invariantly (mirrors
                # ``status_transition._resolve_write_target``'s
                # ``resolve_placement_only(..., kind=STATUS_STATE).ref`` for
                # the flat/base arm). Do NOT re-derive from ``Path.cwd()`` —
                # that is the #2647 taint (a lane worktree's operator cwd can
                # carry a stale local ``status.events.jsonl`` snapshot).
                #
                # CALLER CONTRACT (PR #2662 squad, paula LOW-2): correctness of
                # this arm depends on EVERY caller passing a CWD-invariant
                # ``destination_ref`` (resolved from the mission's stored
                # topology / target branch, never from ``Path.cwd()``). This
                # module cannot inspect a ref's provenance, so a future caller
                # threading a cwd-derived ref would silently reopen #2647. The
                # guard is the caller contract + the routing tests
                # (``test_transaction_legacy_topology_routing`` asserts this arm
                # lands on ``repo_root`` from a stale lane cwd), NOT a runtime
                # provenance check here.
                worktree_root = repo_root
        else:
            coord_branch = CoordinationWorkspace.branch_name(safe_mission_slug, safe_mid8)
            caller_refusal = _caller_ref_refusal(
                repo_root=repo_root,
                mission_slug=safe_mission_slug,
                mid8=safe_mid8,
                destination_ref=effective_destination_ref,
                operation=operation,
                capability=capability,
                owned=owned,
            )
            if caller_refusal is not None:
                raise BookkeepingPolicyRefused(caller_refusal)
            if commit_to_primary_target:
                # write-path-integrity WP02 / FR-001: the caller is committing a
                # PRIMARY-partition planning artifact that MUST land on the
                # mission's own ``destination_ref`` (its primary target branch),
                # NOT the coordination branch. The primary target branch is
                # already checked out at ``repo_root`` when ``implement`` runs
                # the planning auto-commit, so we honour the caller-supplied ref
                # and commit from the primary checkout -- the SAME "worktree_root
                # = repo_root, keep the caller's destination_ref" shape the
                # modern coordination-less arm above uses. This is what stops a
                # PRIMARY ``lanes.json`` being silently redirected onto the
                # coordination branch (the #3371 add/add root cause). The coord
                # redirect below is skipped entirely.
                worktree_root = repo_root
            else:
                # New topology — materialize/seed the coordination write
                # location on first call (WP07 T039: the single write-location
                # accessor, not a bare ``CoordinationWorkspace.resolve`` blind
                # to ``EMPTY``).
                coord_target = _resolve_coord_worktree_root_for_transaction(
                    repo_root=repo_root,
                    mission_slug=safe_mission_slug,
                    mid8=safe_mid8,
                    owned=owned,
                )
                worktree_root = coord_target.worktree_root
                coord_feature_dir = coord_target.feature_dir
                seed_committed_this_txn = coord_target.seed_committed
                # Status events must be committed to the coordination branch,
                # not the caller-supplied destination (which may be "main").
                # Mirror the legacy path's destination_ref override (lines above).
                effective_normalized_ref = _normalize_ref(coord_branch)
                effective_destination_ref = effective_normalized_ref

        # 3. Compute the feature_dir + status files INSIDE the resolved
        # checkout.  Every arm hosts the ``kitty-specs/<slug>-<mid8>/`` tree
        # containing ``status.events.jsonl`` + ``status.json``.  The
        # coordination arm uses the ``WriteLocation.path`` ``write_dir``
        # returned; the non-coordination checkouts (legacy lane worktree --
        # no sparse-checkout policy, so the files are physically present and
        # the surgical truncate rollback works unchanged -- and the primary
        # checkout) locate their own Mission dir.
        feature_dir = coord_feature_dir if coord_feature_dir is not None else _checkout_mission_dir(worktree_root, safe_mission_slug, safe_mid8)
        events_path = feature_dir / _EVENTS_FILENAME
        snapshot_path = feature_dir / _SNAPSHOT_FILENAME

        # 4. Build the change set and run the pre-flight policy gate.
        # This still happens before any bookkeeping write; the lock is
        # already held only to serialize first-time coord worktree setup.
        verdict = _preflight_policy_verdict(
            repo_root=repo_root,
            primary_root=None,
            worktree_root=worktree_root,
            mission_slug=safe_mission_slug,
            destination_ref=effective_destination_ref,
            status_paths=(events_path, snapshot_path),
            operation=operation,
            capability=capability,
            owned=owned,
        )
        if isinstance(verdict, Refused):
            raise BookkeepingPolicyRefused(verdict)
        # ``Allowed`` — fall through.
        assert isinstance(verdict, Allowed)  # noqa: S101 — defensive

        # 5. Capture the pre-emit size of the event log (FR-010) and
        # snapshot of status.json (so rollback is byte-identical, not
        # "re-materialised approximately the same").
        pre_emit_events_existed = events_path.exists()
        pre_emit_size = events_path.stat().st_size if pre_emit_events_existed else 0

        # Construct + return. The pre-emit status.json snapshot is read
        # lazily on first append_event() — many transactions never
        # write events.
        txn = cls(
            repo_root=repo_root,
            mission_id=mission_id,
            mission_slug=mission_slug,
            mid8=mid8,
            destination_ref=effective_normalized_ref,
            operation=operation,
            worktree_root=worktree_root,
            feature_dir=feature_dir,
            events_path=events_path,
            snapshot_path=snapshot_path,
            pre_emit_size=pre_emit_size,
            pre_emit_events_existed=pre_emit_events_existed,
            seed_committed_this_txn=seed_committed_this_txn,
            lock_cm=lock_cm,
        )
        txn._capability = capability
        txn._owned = owned
        txn._legacy_mode = legacy_mode
        return txn

    # ---- context-manager protocol ----

    def __enter__(self) -> BookkeepingTransaction:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                if self._commit_recovery_failed_after_commit:
                    return
                # Happy path: implicit commit if the caller did not call
                # commit() explicitly. Then run deferred outbound.
                if not self._committed and (self._event_ids or self._staged_paths):
                    msg = self._explicit_commit_message or (f"chore(spec-kitty): {self.operation}")
                    try:
                        self.commit(msg)
                    except BookkeepingCommitFailed:
                        # commit() already performed rollback and
                        # raised; re-raise out of __exit__.
                        raise
                self._run_deferred_outbound()
            else:
                # Exception path: surgical rollback.
                recovery_after_commit = (
                    isinstance(exc, BookkeepingCommitFailed) and isinstance(exc.__cause__, SafeCommitRecoveryFailed) and exc.__cause__.commit_sha is not None
                )
                if not recovery_after_commit:
                    self._rollback()
        finally:
            self._release_lock()
        # Do not suppress exceptions (implicit None return).

    # ---- public API ----

    def append_event(
        self,
        event: StatusEvent | InnerStateChanged,
    ) -> PendingEventHandle:
        """Append one ``event`` to ``status.events.jsonl`` + re-materialise."""
        return self.append_events([event])[0]

    def append_events(
        self,
        events: list[StatusEvent | InnerStateChanged],
    ) -> list[PendingEventHandle]:
        """Atomically append a mixed event unit and re-materialise once.

        On first call within the transaction, also snapshots the
        pre-emit ``status.json`` bytes so rollback can restore them
        byte-identically.

        Raises:
            BookkeepingDoubleEventId: Any event id is duplicated within this
                unit or was already appended in this transaction.
        """
        if not events:
            return []
        unit_ids = [event.event_id for event in events]
        duplicate_ids = {event_id for event_id in unit_ids if unit_ids.count(event_id) > 1 or event_id in self._seen_event_ids}
        if duplicate_ids:
            duplicate = sorted(duplicate_ids)[0]
            raise BookkeepingDoubleEventId(f"event_id {duplicate!r} appended twice in one transaction")

        # Capture the pre-emit status.json on first event so rollback
        # restores exact bytes (not "approximately re-materialised").
        if self._pre_emit_snapshot_existed is None:
            self._pre_emit_snapshot_existed = self._snapshot_path.exists()
            self._pre_emit_snapshot_bytes = self._snapshot_path.read_bytes() if self._pre_emit_snapshot_existed else None

        # Ensure parent directories exist (the feature_dir may be new
        # if this is the first emission for this mission).
        self.feature_dir.mkdir(parents=True, exist_ok=True)

        # Append + verify readback (matches existing emit pipeline).
        # C-SEAM-1: the raw ".worktrees" in parts idiom is retired in favour of
        # the blessed shape primitive (WP06 T030), imported lazily to avoid a
        # module-level cycle back through mission_runtime (mirrors
        # status_service._is_coordination_worktree_path's prior lazy import).
        from specify_cli.coordination.surface_resolver import (  # noqa: PLC0415
            is_under_worktrees_segment,
        )

        if self._owned is not None:
            write_contract = EventLogWriteContract.primary_checkout_append(self.feature_dir, owned=self._owned)
        elif self._legacy_mode and not is_under_worktrees_segment(self.feature_dir):
            write_contract = EventLogWriteContract.primary_checkout_append(self.feature_dir)
        else:
            write_contract = EventLogWriteContract.coordination_transaction_append(self.feature_dir)
        append_event_stream_log(
            write_contract,
            events,
        )
        # Re-materialise status.json so an external observer sees
        # consistent state immediately after the event is durable.
        _reducer.materialize(self.feature_dir)

        self._event_ids.extend(unit_ids)
        self._seen_event_ids.update(unit_ids)
        # Both status files are now part of the changeset that commit()
        # will stage.
        for path in (self._events_path, self._snapshot_path):
            if path not in self._staged_paths:
                self._staged_paths.append(path)
        return [PendingEventHandle(event_id=event_id) for event_id in unit_ids]

    def write_artifact(self, path: Path, content: bytes) -> None:
        """Write ``content`` to ``path`` under snapshot-and-restore tracking.

        Captures ``pre_write_bytes`` BEFORE writing so rollback can
        restore the previous content (or unlink if the file did not
        previously exist). C-009: no ``git checkout --`` in the
        rollback path.
        """
        # FR-005 / Issue #1887: guard against callers that accidentally
        # resolve a path relative to the primary repo root (which would make
        # the output path land under .worktrees/) rather than relative to the
        # coordination worktree. This is the write-side backstop — if the
        # output path resolves under .worktrees/ from the primary repo's
        # perspective, reject it immediately before touching the filesystem.
        resolved_candidate = (path if path.is_absolute() else self.worktree_root / path).resolve(strict=False)
        try:
            rel_from_worktree = resolved_candidate.relative_to(self.worktree_root.resolve())
        except ValueError:
            rel_from_worktree = None
        if rel_from_worktree is not None and rel_from_worktree.parts and rel_from_worktree.parts[0] == WORKTREES_DIR:
            raise SafeCommitPathPolicyError(
                offending_path=rel_from_worktree.as_posix(),
                worktree_root=self.worktree_root,
            )
        try:
            resolved_path = _resolve_confined_artifact_path(self.worktree_root, path)
        except ValueError as exc:
            raise ValueError(f"Refusing to write artifact outside coordination worktree (outside worktree): {path}") from exc
        # Capture snapshot ONLY if we have not seen this path yet.
        # Re-writing the same path repeatedly in one transaction still
        # rolls back to the *original* pre-transaction state.
        if resolved_path not in self._snapshots:
            self._snapshots[resolved_path] = resolved_path.read_bytes() if resolved_path.exists() else None

        resolved_path = _write_confined_artifact_bytes(
            self.worktree_root,
            resolved_path,
            content,
        )

        if resolved_path not in self._staged_paths:
            self._staged_paths.append(resolved_path)

    def enroll_subprocess_byproducts(self, *paths: Path, stage: bool = True) -> None:
        """Enrol bytes a spec-kitty-spawned child process creates/modifies (C3/TAO-1).

        Call this **before** spawning the child (a gate's pytest run) with the
        paths it may create or modify. The pre-transaction bytes are snapshotted
        (``None`` when the path does not yet exist), so on a successful step the
        bytes are committed (``stage=True`` adds them to the changeset) and on an
        aborted step the single compensator restores them — a created byproduct is
        unlinked, a modified one is reverted. This replaces the "detected, warned,
        and abandoned" behaviour that manufactured the very orphan a later gate then
        had to be taught to ignore.

        Rollback restores these alongside :meth:`write_artifact` paths through the
        one compensator (TAO-3). Confinement matches :meth:`write_artifact`.
        """
        for path in paths:
            confined = _confine_path_to_worktree(self.worktree_root, path)
            resolved_path = _resolve_confined_artifact_path(self.worktree_root, confined)
            if resolved_path not in self._byproduct_snapshots:
                self._byproduct_snapshots[resolved_path] = resolved_path.read_bytes() if resolved_path.exists() else None
            if stage and resolved_path not in self._staged_paths:
                self._staged_paths.append(resolved_path)

    def stage_path(self, path: Path) -> None:
        """Add ``path`` to the commit changeset without snapshot tracking.

        Use this for paths the caller has already modified out-of-band.
        Rollback does NOT restore these (documented contract — only
        :meth:`write_artifact` paths get snapshot/restore semantics).
        """
        path = _confine_path_to_worktree(self.worktree_root, path)
        if path not in self._staged_paths:
            self._staged_paths.append(path)

    def defer_outbound(self, side_effect: Callable[[], None]) -> None:
        """Queue ``side_effect`` to run after a successful commit.

        Callables run in registration order. Individual callable
        failures are LOGGED but do not abort the rest (best-effort
        fanout per FR-022). Rollback skips deferred outbound entirely.
        """
        self._deferred.append(side_effect)

    def commit_idempotent(self, message: str) -> CommitReceipt:
        """Commit staged paths, or no-op when they already match HEAD.

        WP04/T015 (FR-004, #2861) — the single-write-authority follow-up
        commit. The transactional status emit already committed the lane
        transition to the coordination worktree; a follow-up workflow commit of
        the same paths therefore finds them byte-identical to HEAD. Routing that
        empty changeset through :meth:`commit` -> ``safe_commit`` would hit
        "nothing to commit, working tree clean" -> ``git commit failed`` -> the
        write is refused -> the manual review claim fails. THAT redundant second
        commit is the live #2861 block. When the staged paths carry no git diff,
        return an idempotent no-op receipt pinned at the current HEAD (the commit
        the emit already created) instead. When there IS a diff, delegate to the
        strict :meth:`commit` path unchanged.

        Distinct from :meth:`commit` (used by the transactional emit's implicit
        commit and by adversarial rollback callers), which must still surface an
        empty/failed changeset as :class:`BookkeepingCommitFailed`.

        coord-artifact-single-home-01M3V4BE WP07 (review cycle 2 R1,
        corrected again by WP09 review cycle 3): the no-op guard no longer
        requires ``self._staged_paths`` to be non-empty -- but ONLY when THIS
        transaction's OWN acquire just produced a genuine seed commit on the
        coordination branch (``self._seed_committed_this_txn``, set from
        ``location.seed.coord_commit is not None`` at acquire time -- NOT
        merely from the ``Establishment`` being ``SEEDED`` or
        ``RESTORED_FROM_BRANCH``, since a ``RESTORED_FROM_BRANCH`` establishment
        can restore COORD-kind paths from the tip without committing anything
        new, a genuine git no-op that must NOT be treated as "my content is
        already on the branch"). Cycle 1's first attempt used
        ``self._pre_emit_events_existed`` (``events_path.exists()`` at
        acquire) instead, which is true for ANY Mission with existing status
        history -- not only one whose SEED just committed content THIS
        transaction never staged -- so it kept masking a genuinely empty
        changeset against an existing-log Mission (review cycle 2 R1: the
        reviewer's own probe, pinned by
        ``test_commit_idempotent_still_raises_when_an_existing_log_mission_stages_nothing_new``).
        ``seed_committed_this_txn`` answers the narrower, correct question:
        did resolving WHERE to write, for THIS acquire, already commit the
        caller's intended content onto the coordination branch before the
        caller ever decided whether it still needed to ``write_artifact`` at
        all -- exactly as idempotent-safe as a caller whose staged paths
        already match HEAD.

        It does NOT cover a caller whose ``_staged_paths`` is empty because
        nothing was ever written AND this acquire's own write_dir resolution
        did not seed anything either (e.g. ``implement.py``'s planning-
        artifact commit skips every requested source that does not exist on
        disk, per its own ``continue``, against a Mission whose coordination
        surface was already ``MATERIALIZED`` with no pending seed -- or
        whose log already exists from an EARLIER, unrelated transaction) --
        that remains a genuine empty changeset and still falls through to
        :meth:`commit`, which raises :class:`BookkeepingCommitFailed` for it,
        unchanged from base.
        """
        if self._committed:
            if self._explicit_commit_receipt is None:
                raise BookkeepingCommitFailed("commit_idempotent(): transaction marked committed but no commit receipt was recorded")
            return self._explicit_commit_receipt
        if not self._staged_paths and not self._seed_committed_this_txn:
            # Genuinely nothing was ever written AND this transaction's own
            # acquire did not seed anything either -- delegate to the strict
            # path so an empty changeset still raises BookkeepingCommitFailed,
            # regardless of whether the Mission has UNRELATED prior history.
            return self.commit(message)
        if not self._worktree_has_pending_changes():
            receipt = self._noop_commit_receipt()
            self._committed = True
            self._explicit_commit_message = message
            self._explicit_commit_receipt = receipt
            return receipt
        return self.commit(message)

    def commit(self, message: str) -> CommitReceipt:
        """Commit all staged paths via :func:`safe_commit`.

        Returns a :class:`CommitReceipt` carrying the new commit SHA
        and the list of event_ids appended in this transaction.

        On commit failure: rolls back the event log + every
        :meth:`write_artifact` path, then raises
        :class:`BookkeepingCommitFailed` chaining the original error.
        """
        if self._committed:
            # Idempotent: return the receipt from the first call.
            assert self._explicit_commit_receipt is not None  # noqa: S101
            return self._explicit_commit_receipt
        if self._commit_recovery_failed_after_commit:
            raise BookkeepingCommitFailed("commit() cannot be retried: safe_commit already created a commit but failed to restore caller staging")

        if not self._staged_paths:
            raise BookkeepingCommitFailed("commit() called with no events or artifacts to commit")

        try:
            result = safe_commit(
                repo_root=self._owned.repository_root if self._owned is not None else self.repo_root,
                worktree_root=self.worktree_root,
                target=CommitTarget(ref=self.destination_ref),
                message=message,
                paths=tuple(self._staged_paths),
                capability=self._capability,
                owned=self._owned,
            )
        except SafeCommitRecoveryFailed as exc:
            if exc.commit_sha is None:
                self._rollback()
            else:
                self._commit_recovery_failed_after_commit = True
            raise BookkeepingCommitFailed(f"safe_commit recovery failed on {self.destination_ref!r}: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 — wrap as domain error
            # Rollback before re-raising. ``_rollback`` is intentionally
            # tolerant: it logs but does not raise so the caller sees
            # the original commit failure, not a rollback failure.
            self._rollback()
            raise BookkeepingCommitFailed(f"safe_commit failed on {self.destination_ref!r}: {exc}") from exc

        receipt = CommitReceipt(
            commit_sha=result.sha,
            committed_at=now_utc(),
            destination_ref=self.destination_ref,
            worktree_root=self.worktree_root,
            event_ids=tuple(self._event_ids),
        )
        self._committed = True
        self._explicit_commit_message = message
        self._explicit_commit_receipt = receipt
        return receipt

    def _worktree_has_pending_changes(self) -> bool:
        """Whether any staged path differs from HEAD in the coord worktree.

        WP04/T015: scopes ``git status --porcelain`` to exactly the paths this
        transaction staged. Empty output means those paths already match HEAD
        (a prior transaction committed identical content) — the follow-up
        commit would be the empty second commit behind #2861.

        Fails OPEN (returns ``True``) when git cannot be consulted, so an
        unreadable status never silently swallows a genuine commit — the
        normal ``safe_commit`` path then runs and surfaces the real error.
        """
        if not self._staged_paths:
            return False
        try:
            return bool(
                status_entries(
                    self.worktree_root,
                    pathspecs=[str(path) for path in self._staged_paths],
                    untracked=None,
                )
            )
        except GitCommandError:
            # Advisory (documented above): fail open so the real ``safe_commit``
            # path runs and surfaces the actual git error.
            return True

    def _noop_commit_receipt(self) -> CommitReceipt:
        """Receipt pinned at the current HEAD for an idempotent no-op commit.

        WP04/T015: when :meth:`_worktree_has_pending_changes` reports the staged
        paths already match HEAD, the transition is already durable at HEAD (the
        prior transaction committed it). The receipt therefore points at that
        existing commit so the caller's post-commit bookkeeping (lane sync /
        revert-on-failure) targets the real transition commit.
        """
        head = subprocess.run(
            ["git", "-C", str(self.worktree_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        sha = head.stdout.strip()
        if head.returncode != 0 or not sha:
            raise BookkeepingCommitFailed(f"commit() no-op: could not resolve HEAD in {self.worktree_root} to pin the already-committed transition")
        return CommitReceipt(
            commit_sha=sha,
            committed_at=now_utc(),
            destination_ref=self.destination_ref,
            worktree_root=self.worktree_root,
            event_ids=tuple(self._event_ids),
            is_noop=True,
        )

    # ---- private ----

    def _rollback(self) -> None:
        """Surgical rollback: truncate event log; restore artifacts.

        C-009: never uses ``git checkout --``. Every restore is from
        in-process byte snapshots.

        Idempotent and tolerant of partial failures: every step is
        guarded so a failing restore on one path still attempts the
        others.
        """
        # 1. Surgical truncate of status.events.jsonl (FR-010). This
        # restores the file byte-for-byte to the pre-emit state because
        # the file is append-only.
        try:
            if self._events_path.exists():
                if self._pre_emit_events_existed:
                    with self._events_path.open("ab") as fh:
                        fh.truncate(self._pre_emit_size)
                else:
                    self._events_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.error(
                "BookkeepingTransaction rollback: truncate of %s failed: %s",
                self._events_path,
                exc,
            )

        # 2. Restore status.json from the byte snapshot captured at
        # first append_event() (NOT a re-materialise — preserves SHA).
        # If no event was ever appended, _pre_emit_snapshot_existed is
        # None and we leave status.json alone.
        if self._pre_emit_snapshot_existed is not None:
            try:
                if self._pre_emit_snapshot_existed:
                    assert self._pre_emit_snapshot_bytes is not None  # noqa: S101
                    self._snapshot_path.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    self._snapshot_path.write_bytes(
                        self._pre_emit_snapshot_bytes,
                    )
                else:
                    # Pre-emit, the file did not exist. Remove the
                    # re-materialised one.
                    self._snapshot_path.unlink(missing_ok=True)
            except OSError as exc:
                logger.error(
                    "BookkeepingTransaction rollback: restore of %s failed: %s",
                    self._snapshot_path,
                    exc,
                )

        # 3. Snapshot-restore each tracked write_artifact path AND every enrolled
        # subprocess byproduct (C3), through the single compensator (TAO-3). The
        # confined fd-relative write/unlink is injected so restore stays inside the
        # worktree (C-009: no ``git checkout --``).
        restore_generated_artifact_snapshots(
            {**self._snapshots, **self._byproduct_snapshots},
            write=lambda path, prev: _write_confined_artifact_bytes(self.worktree_root, path, prev),
            unlink=lambda path: _unlink_confined_artifact_path(self.worktree_root, path),
            on_error=lambda path, exc: logger.error(
                "BookkeepingTransaction rollback: restore of %s failed: %s",
                path,
                exc,
            ),
        )

    def _run_deferred_outbound(self) -> None:
        """Run deferred outbound side effects. Individual failures log only."""
        for side_effect in self._deferred:
            try:
                side_effect()
            except Exception as exc:  # noqa: BLE001 — best-effort
                logger.warning(
                    "BookkeepingTransaction deferred outbound failed: %s",
                    exc,
                )

    def _release_lock(self) -> None:
        """Release the feature status lock. Idempotent within one __exit__."""
        try:
            self._lock_cm.__exit__(None, None, None)
        except Exception as exc:  # noqa: BLE001 — defensive
            logger.error(
                "BookkeepingTransaction: lock release failed: %s",
                exc,
            )
