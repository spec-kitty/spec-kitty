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

from specify_cli.core.constants import KITTY_SPECS_DIR, WORKTREES_DIR
import logging
import subprocess
from collections.abc import Callable
from contextlib import AbstractContextManager
from kernel.clock import now_utc
from pathlib import Path
from types import TracebackType

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
    DESTINATION_REF_NOT_FOUND,
    GitChangeSet,
    PendingEventHandle,
    PROTECTED_BRANCH_REFUSED,
    Refused,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from mission_runtime import CommitTarget
from specify_cli.core.commit_guard import GuardCapability
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


def _write_confined_artifact_bytes(
    worktree_root: Path,
    path: Path,
    content: bytes,
) -> Path:
    """Write bytes, injecting this module's resolver (oracle-patchable)."""
    return _aw_write_confined_artifact_bytes(
        worktree_root, path, content, resolve=_resolve_confined_artifact_path
    )


def _unlink_confined_artifact_path(worktree_root: Path, path: Path) -> None:
    """Unlink an artifact, injecting this module's resolver (oracle-patchable)."""
    _aw_unlink_confined_artifact_path(
        worktree_root, path, resolve=_resolve_confined_artifact_path
    )


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
    ) -> None:
        # Note: most attributes are public-but-immutable-by-convention.
        # ``mypy --strict`` is satisfied because we do not annotate them
        # as ``Final`` and we never re-bind them after construction.
        self.repo_root = repo_root
        self._primary_root: Path | None = None
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
        effective_root: Path | None = None,
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
        lock_cm = feature_status_lock(
            effective_root or repo_root, _mission_specs_dir_name(mission_slug, mid8), timeout=timeout,
        )
        try:
            lock_cm.__enter__()
        except FeatureStatusLockTimeoutError as exc:
            raise BookkeepingLockTimeout(str(exc)) from exc

        try:
            return cls._acquire_locked(
                repo_root=effective_root or repo_root,
                mission_id=mission_id,
                mission_slug=mission_slug,
                mid8=mid8,
                destination_ref=destination_ref,
                normalised_ref=normalised_ref,
                operation=operation,
                lock_cm=lock_cm,
                capability=capability,
                commit_to_primary_target=commit_to_primary_target,
                primary_root=repo_root if effective_root is not None else None,
            )
        except Exception:
            lock_cm.__exit__(None, None, None)
            raise

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
        primary_root: Path | None = None,
    ) -> BookkeepingTransaction:
        safe_mission_slug = _validate_safe_segment("mission_slug", mission_slug)
        safe_mid8 = _validate_safe_segment("mid8", mid8)
        effective_destination_ref = destination_ref
        effective_normalized_ref = normalised_ref

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
                repo_root, safe_mission_slug, safe_mid8,
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
            caller_change_set = GitChangeSet(
                destination_ref=effective_destination_ref,
                repo_root=repo_root,
                worktree_root=repo_root,
                paths=(),
                message=f"<pending: {operation}>",
                operation=operation,
                capability=capability,
            )
            caller_verdict = WorkflowMutationPolicy.assert_allowed(
                caller_change_set,
                coord_available=True,
            )
            if isinstance(caller_verdict, Refused):
                explicit_coord_branch = _coordination_branch_from_meta(
                    repo_root, safe_mission_slug, safe_mid8,
                )
                can_recover_to_coord_branch = (
                    caller_verdict.error_code == PROTECTED_BRANCH_REFUSED
                    and explicit_coord_branch == coord_branch
                )
                allow_coord_resolution_to_report_missing_branch = (
                    caller_verdict.error_code == DESTINATION_REF_NOT_FOUND
                    and effective_destination_ref == coord_branch
                )
                if not (
                    can_recover_to_coord_branch
                    or allow_coord_resolution_to_report_missing_branch
                ):
                    raise BookkeepingPolicyRefused(caller_verdict)
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
                # New topology — create coord worktree on first call.
                try:
                    worktree_root = CoordinationWorkspace.resolve(
                        repo_root, safe_mission_slug, safe_mid8,
                    )
                except Exception as exc:  # noqa: BLE001 — domain error surface
                    identity = coord_mission_dir_name(
                        safe_mission_slug, mid8=safe_mid8
                    )
                    raise BookkeepingWorktreeMissing(
                        f"Failed to resolve coordination worktree for "
                        f"{identity}: {exc}"
                    ) from exc
                # Status events must be committed to the coordination branch,
                # not the caller-supplied destination (which may be "main").
                # Mirror the legacy path's destination_ref override (lines above).
                effective_normalized_ref = _normalize_ref(coord_branch)
                effective_destination_ref = effective_normalized_ref

        # 3. Compute the feature_dir + status files INSIDE the resolved
        # worktree.  Both paths (coord and legacy lane) host the
        # ``kitty-specs/<slug>-<mid8>/`` tree containing
        # ``status.events.jsonl`` + ``status.json``.  In legacy mode
        # there is no sparse-checkout policy on the lane, so the files
        # are physically present and the surgical truncate rollback
        # works against the lane worktree without modification.
        kitty_dir_name = _mission_specs_dir_name(safe_mission_slug, safe_mid8)
        feature_dir = worktree_root / KITTY_SPECS_DIR / kitty_dir_name
        events_path = feature_dir / _EVENTS_FILENAME
        snapshot_path = feature_dir / _SNAPSHOT_FILENAME

        # 4. Build the change set and run the pre-flight policy gate.
        # This still happens before any bookkeeping write; the lock is
        # already held only to serialize first-time coord worktree setup.
        change_set = GitChangeSet(
            destination_ref=effective_destination_ref,
            repo_root=primary_root or repo_root,
            worktree_root=worktree_root,
            paths=(events_path, snapshot_path),
            message=f"<pending: {operation}>",
            operation=operation,
            capability=capability,
        )
        from specify_cli.coordination.commit_router import (
            mission_has_coordination_branch,
        )

        coord_available = mission_has_coordination_branch(
            repo_root,
            safe_mission_slug,
        )
        verdict = WorkflowMutationPolicy.assert_allowed(
            change_set,
            coord_available=coord_available,
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
            lock_cm=lock_cm,
        )
        txn._capability = capability
        txn._primary_root = primary_root
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
                    msg = self._explicit_commit_message or (
                        f"chore(spec-kitty): {self.operation}"
                    )
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
                    isinstance(exc, BookkeepingCommitFailed)
                    and isinstance(exc.__cause__, SafeCommitRecoveryFailed)
                    and exc.__cause__.commit_sha is not None
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
        duplicate_ids = {
            event_id
            for event_id in unit_ids
            if unit_ids.count(event_id) > 1 or event_id in self._seen_event_ids
        }
        if duplicate_ids:
            duplicate = sorted(duplicate_ids)[0]
            raise BookkeepingDoubleEventId(
                f"event_id {duplicate!r} appended twice in one transaction"
            )

        # Capture the pre-emit status.json on first event so rollback
        # restores exact bytes (not "approximately re-materialised").
        if self._pre_emit_snapshot_existed is None:
            self._pre_emit_snapshot_existed = self._snapshot_path.exists()
            self._pre_emit_snapshot_bytes = (
                self._snapshot_path.read_bytes()
                if self._pre_emit_snapshot_existed
                else None
            )

        # Ensure parent directories exist (the feature_dir may be new
        # if this is the first emission for this mission).
        self.feature_dir.mkdir(parents=True, exist_ok=True)

        # Append + verify readback (matches existing emit pipeline).
        if self._legacy_mode and ".worktrees" not in self.feature_dir.parts:
            write_contract = EventLogWriteContract.primary_checkout_append(
                self.feature_dir
            )
        else:
            write_contract = EventLogWriteContract.coordination_transaction_append(
                self.feature_dir
            )
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
        resolved_candidate = (path if path.is_absolute() else self.worktree_root / path).resolve(
            strict=False
        )
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
            raise ValueError(
                "Refusing to write artifact outside coordination worktree "
                "(outside worktree): "
                f"{path}"
            ) from exc
        # Capture snapshot ONLY if we have not seen this path yet.
        # Re-writing the same path repeatedly in one transaction still
        # rolls back to the *original* pre-transaction state.
        if resolved_path not in self._snapshots:
            self._snapshots[resolved_path] = (
                resolved_path.read_bytes() if resolved_path.exists() else None
            )

        resolved_path = _write_confined_artifact_bytes(
            self.worktree_root,
            resolved_path,
            content,
        )

        if resolved_path not in self._staged_paths:
            self._staged_paths.append(resolved_path)

    def enroll_subprocess_byproducts(
        self, *paths: Path, stage: bool = True
    ) -> None:
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
            resolved_path = _resolve_confined_artifact_path(
                self.worktree_root, confined
            )
            if resolved_path not in self._byproduct_snapshots:
                self._byproduct_snapshots[resolved_path] = (
                    resolved_path.read_bytes() if resolved_path.exists() else None
                )
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
        """
        if self._committed:
            if self._explicit_commit_receipt is None:
                raise BookkeepingCommitFailed(
                    "commit_idempotent(): transaction marked committed but no "
                    "commit receipt was recorded"
                )
            return self._explicit_commit_receipt
        if self._staged_paths and not self._worktree_has_pending_changes():
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
            raise BookkeepingCommitFailed(
                "commit() cannot be retried: safe_commit already created a commit "
                "but failed to restore caller staging"
            )

        if not self._staged_paths:
            raise BookkeepingCommitFailed(
                "commit() called with no events or artifacts to commit"
            )

        try:
            result = safe_commit(
                repo_root=self._primary_root or self.repo_root,
                worktree_root=self.worktree_root,
                target=CommitTarget(ref=self.destination_ref),
                message=message,
                paths=tuple(self._staged_paths),
                capability=self._capability,
                effective_root=self.worktree_root if self._primary_root is not None else None,
            )
        except SafeCommitRecoveryFailed as exc:
            if exc.commit_sha is None:
                self._rollback()
            else:
                self._commit_recovery_failed_after_commit = True
            raise BookkeepingCommitFailed(
                f"safe_commit recovery failed on {self.destination_ref!r}: {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 — wrap as domain error
            # Rollback before re-raising. ``_rollback`` is intentionally
            # tolerant: it logs but does not raise so the caller sees
            # the original commit failure, not a rollback failure.
            self._rollback()
            raise BookkeepingCommitFailed(
                f"safe_commit failed on {self.destination_ref!r}: {exc}"
            ) from exc

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
        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.worktree_root),
                "status",
                "--porcelain",
                "--",
                *[str(path) for path in self._staged_paths],
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return True
        return bool(result.stdout.strip())

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
            raise BookkeepingCommitFailed(
                "commit() no-op: could not resolve HEAD in "
                f"{self.worktree_root} to pin the already-committed transition"
            )
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
                "BookkeepingTransaction rollback: truncate of %s "
                "failed: %s",
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
                        parents=True, exist_ok=True,
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
                    "BookkeepingTransaction rollback: restore of %s "
                    "failed: %s",
                    self._snapshot_path,
                    exc,
                )

        # 3. Snapshot-restore each tracked write_artifact path AND every enrolled
        # subprocess byproduct (C3), through the single compensator (TAO-3). The
        # confined fd-relative write/unlink is injected so restore stays inside the
        # worktree (C-009: no ``git checkout --``).
        restore_generated_artifact_snapshots(
            {**self._snapshots, **self._byproduct_snapshots},
            write=lambda path, prev: _write_confined_artifact_bytes(
                self.worktree_root, path, prev
            ),
            unlink=lambda path: _unlink_confined_artifact_path(
                self.worktree_root, path
            ),
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
