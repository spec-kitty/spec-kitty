"""Transactional status-transition emission helpers.

Production workflow callers must append status events through
``BookkeepingTransaction`` so SaaS/dossier fanout runs only after the
bookkeeping commit succeeds.

This module is the **transactional composition shell** of the status write
path (mission ``fsm-write-path-integrity-01M1TZV6``, contract
``contracts/emit-pipeline.md`` §2, data-model §5). Validation and event
construction live in the status-owned pipeline
:func:`specify_cli.status.transition_pipeline.prepare_transition` -- the
single validation/build authority (decision Q4,
``01M1V80R6F6RTMR7Y3C2WBKR32``). The three doors here (single, batch,
inner-state) own only what a shell owns: the transaction acquire (L1), the
in-lock from-lane derivation, the append, and the fan-out timing (deferred
behind the commit). ``MissionStatus`` (``status/aggregate.py``) composes the
single door and is the intended domain facade for callers; it is not the
write chokepoint (the eight direct transactional callers remain until a
caller-migration mission).

Fan-out timing (FR-008): every coord arm -- the ``BookkeepingTransaction``
doors AND the non-transactional coord fallback arms -- announces an event
only after its durable commit succeeded. A truncated event is never
announced (SC-002; ``tests/specify_cli/coordination/test_phantom_fanout.py``).
"""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, replace
from kernel.clock import now_utc, now_utc_iso, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from specify_cli.coordination.outbound import queue_saas_emission
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.core.errors import StructuredError
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    read_event_log,
    read_event_stream_log,
    wp_lane_actor_from_events,
)
from specify_cli.coordination.transaction import (
    BookkeepingTransaction,
    BookkeepingWorktreeMissing,
)
from specify_cli.lanes._git import branch_exists as _branch_exists
from specify_cli.lanes.branch_naming import (
    coord_mission_dir_name as _seam_coord_mission_dir_name,
    resolve_transaction_mid8,
    worktree_dir_name,
)
from specify_cli.status import emit as _emit
from specify_cli.status.locking import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    feature_status_lock,
)
from specify_cli.status.models import (
    CurrentWpState,
    EventStream,
    InnerStateChanged,
    Lane,
    StatusEvent,
    TransitionRequest,
    WPInnerStateDelta,
)
from specify_cli.status.reducer import reduce as _reduce_events
from specify_cli.status.store import EVENTS_FILENAME as _EVENTS_FILENAME
from specify_cli.status.store import read_event_stream_from_text as _read_event_stream_from_text
from specify_cli.status.store import read_events as _read_raw_events
from specify_cli.status.transition_pipeline import PreparedTransition, prepare_transition
from specify_cli.status.views import DERIVED_STATUS_FILENAME as _DERIVED_STATUS_FILENAME
from specify_cli.status.transitions import is_terminal, resolve_lane_alias
from specify_cli.status.wp_state import annotate as _annotate
from specify_cli.workspace import canonicalize_feature_dir, delete_context

if TYPE_CHECKING:
    from specify_cli.core.dependency_graph import DependencyReadiness

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TransactionIdentity:
    repo_root: Path
    feature_dir: Path
    mission_id: str | None  # WP04/FR-004: ULID or None; never a slug-derived fallback
    mid8: str
    destination_ref: str
    meta_exists: bool
    coordination_branch: str | None
    transaction_meta_exists: bool
    primary_root: Path | None = None


def _repo_root_for_feature(feature_dir: Path, repo_root: Path | None) -> Path:
    """Resolve the canonical primary repo root for a status-transition feature dir.

    R5 adoption (FR-001 / D-12): the prior ``feature_dir.parent.parent`` walk
    keyed on ``kitty-specs`` resolved the *enclosing worktree* root (the coord
    worktree under coord topology — the #2004/#2007 flatten hazard). It is now
    routed to the single canonical worktree-pointer resolver
    (``workspace.primary_root`` semantics), so a coord/lane worktree feature dir
    follows its ``.git`` pointer back to the canonical MAIN checkout and a
    submodule stops at the submodule root (#2011). The explicit ``repo_root``
    short-circuit is preserved for callers that already carry one. When no
    enclosing git repo can be resolved (ad-hoc test fixtures built outside a
    worktree) we degrade to ``feature_dir`` — byte-identical to the prior
    non-``kitty-specs`` fallback — so those callers keep working.
    """
    if repo_root is not None:
        return repo_root
    from specify_cli.workspace.root_resolver import (  # noqa: PLC0415
        WorkspaceRootNotFound,
        resolve_canonical_root,
    )

    try:
        canonical: Path = resolve_canonical_root(feature_dir)
    except WorkspaceRootNotFound:
        return feature_dir
    return canonical


def _current_branch(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    branch = result.stdout.strip()
    return branch if result.returncode == 0 and branch else "HEAD"


def _repo_supports_transactions(repo_root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _transaction_dir_name(mission_slug: str, mid8: str) -> str:
    """Return the on-disk transaction (kitty-specs) dir name for this mission.

    Delegates to the seam's VERBATIM coordination primitive
    (``lanes.branch_naming.coord_mission_dir_name``, FR-010): exactly ONE
    algorithm for the coordination ``<slug>-<mid8>`` grammar, reconstructed
    byte-identical to the prior hand-rolled body. The ``mission_slug`` arrives
    VERBATIM from ``meta.json`` (including any legacy ``NNN-`` prefix); the seam
    primitive does NOT strip it, so the transaction dir matches the on-disk coord
    target (#1589). ``mid8`` may be ``""`` for the legacy/flattened routing path —
    the verbatim primitive preserves the prior ``f"{slug}-"`` form there, so
    routing stays byte-identical. The canonical, NNN-stripping ``mission_dir_name``
    is NOT used here.
    """
    return _seam_coord_mission_dir_name(mission_slug, mid8=mid8)


def _transaction_topology_available(identity: _TransactionIdentity, mission_slug: str) -> bool:
    if not _repo_supports_transactions(identity.repo_root):
        return False
    if identity.coordination_branch is not None:
        return True
    if identity.meta_exists:
        # Legacy missions with meta but no coordination_branch are handled by
        # BookkeepingTransaction's legacy lane fallback when its derived
        # kitty-specs/<slug>-<mid8>/meta.json path can see that meta.
        return identity.transaction_meta_exists

    if not identity.mid8:
        # #154: resolve_transaction_mid8 returned "" -- its documented
        # bare-slug surface for meta-less / legacy missions with no
        # coordination topology in play ("there is no coord target to
        # mis-route"). Composing the branch handle from that empty mid8 is
        # exactly the malformed 'kitty/mission-<slug>-' ref the workspace seam
        # refuses (#2091, M-1), so probing it here raised
        # CoordinationWorkspaceIdentityUnresolved out of every read/write on
        # any host where this feature dir sits inside a git work tree instead
        # of taking the primary-checkout contract the clean-host run takes.
        return False

    from specify_cli.coordination.workspace import CoordinationWorkspace  # noqa: PLC0415

    return _branch_exists(
        identity.repo_root,
        CoordinationWorkspace.branch_name(mission_slug, identity.mid8),
    )


_NonTxnEmitResult = TypeVar("_NonTxnEmitResult")


class FallbackCoordWorktreeUnresolved(StructuredError):
    """A stored-COORD mission's coord worktree could not be materialized for a write.

    US1 Edge Case / SC-001: a coord-routed (``COORD`` / ``LANES_WITH_COORD``)
    mission whose coordination worktree cannot be materialized MUST NOT silently
    degrade to a primary-uncommitted write (which strands the coord event log on
    the wrong surface). This mirrors the sibling misroute guard
    (``workflow_executor`` FR-002(a), which fails loud for the same
    corrupt/unresolvable-identity class rather than routing coord artifacts to the
    repository root) — reconciling the two coord-write authorities to ONE failure
    policy. The legitimate primary path is preserved ONLY for coord-less
    topologies (``SINGLE_BRANCH`` / ``LANES`` / flat), decided by the stored
    topology SSOT — never by a surface existence test.
    """

    error_code: str = "FALLBACK_COORD_WORKTREE_UNRESOLVED"

    def __init__(self, *, mission_slug: str, mid8: str, cause: BaseException) -> None:
        self.mission_slug = mission_slug
        self.mid8 = mid8
        super().__init__(
            f"coord-routed mission {mission_slug!r} (mid8 {mid8!r}) requires its "
            "coordination worktree for a status write, but it could not be "
            f"materialized: {cause}. Refusing to degrade to a primary-uncommitted "
            "write that would strand the coordination event log. Repair the "
            "coordination worktree/branch (meta.mid8 / coordination_branch) and retry."
        )


def _resolve_fallback_coord_worktree(
    identity: _TransactionIdentity, mission_slug: str
) -> Path | None:
    """Resolve the coord worktree for the non-transactional coord fallback.

    Two layers, mirroring the read contract's shape-vs-existence split
    (:func:`_read_contract_routes_through_coordination` plus its transient probe
    arms — the same two-layer structure the read side already uses):

    * **SHAPE — stored-topology SSOT.** The coord-vs-primary decision is disposed
      by the WP02 topology SSOT via
      :func:`_read_contract_routes_through_coordination`
      (``routes_through_coordination(read_topology(...))``), NOT a
      ``coordination_branch is not None`` / branch-exists SURFACE test — the exact
      re-derivation SC-001 forbids the read contract from doing. A coord-less
      topology (``SINGLE_BRANCH`` / ``LANES`` / flat) returns ``None`` so the
      caller PRESERVES the legitimate primary-uncommitted write (contract row 8);
      no coord path is forced and no error is raised.
    * **TRANSIENT MATERIALIZATION.** For a stored-``COORD`` / ``LANES_WITH_COORD``
      mission the write MUST land on the coord worktree — materialize/target it
      through the ONE ``CoordinationWorkspace.resolve`` authority (never a forked
      resolver). If it genuinely cannot be resolved, FAIL LOUD
      (:class:`FallbackCoordWorktreeUnresolved`) rather than silently degrade to a
      primary-uncommitted write (US1 Edge Case; the same fail-loud policy the
      ``workflow_executor`` misroute guard applies). Only the concrete
      materialization failures are caught-and-re-raised; an unexpected error
      (programming bug — ``AttributeError`` etc.) propagates raw rather than being
      masked as a silent primary write (#3 narrowing).
    """
    if not _read_contract_routes_through_coordination(identity):
        return None
    from specify_cli.coordination.workspace import (  # noqa: PLC0415
        CoordinationWorkspace,
        CoordinationWorkspaceBranchMismatch,
        CoordinationWorkspaceIdentityUnresolved,
    )

    try:
        # Local annotation re-narrows the cross-module (``Any``) resolve result.
        coord_worktree: Path = CoordinationWorkspace.resolve(
            identity.repo_root, mission_slug, identity.mid8
        )
    except (
        OSError,
        subprocess.SubprocessError,
        CoordinationWorkspaceBranchMismatch,
        CoordinationWorkspaceIdentityUnresolved,
    ) as exc:
        raise FallbackCoordWorktreeUnresolved(
            mission_slug=mission_slug, mid8=identity.mid8, cause=exc
        ) from exc
    return coord_worktree


def _emit_via_non_transactional_fallback(
    identity: _TransactionIdentity,
    mission_slug: str,
    *,
    primary_emit: Callable[[], _NonTxnEmitResult],
    coord_emit: Callable[[Path], _NonTxnEmitResult],
) -> _NonTxnEmitResult:
    """The ``_transaction_topology_available`` False-arm write (FR-004, rows 7-8).

    The ONE place the False arm decides coord-vs-primary — both the single and the
    batch site route through here, so neither branches in place.

    * **Coord topology** (stored ``COORD`` / ``LANES_WITH_COORD``): materialize/
      target the coord worktree via ``CoordinationWorkspace.resolve`` and commit
      the event THERE (via *coord_emit*), so a reader of the coord event log never
      sees a stale primary-only-uncommitted write (contract row 7). If the coord
      worktree genuinely cannot be materialized,
      :func:`_resolve_fallback_coord_worktree` FAILS LOUD
      (:class:`FallbackCoordWorktreeUnresolved`) — a stored-COORD write is never
      silently degraded to a primary-uncommitted write (US1 Edge Case).
    * **Coord-less topology** (``SINGLE_BRANCH``/``LANES``/flat): PRESERVE the
      primary-uncommitted write path (via *primary_emit*, contract row 8). No coord
      path is forced and no error is raised — a blanket delete of this arm would
      regress flat missions.
    """
    coord_worktree = _resolve_fallback_coord_worktree(identity, mission_slug)
    if coord_worktree is not None:
        return coord_emit(coord_worktree)
    return primary_emit()


def _commit_status_artifacts_to_coord(
    *, repo_root: Path, mission_slug: str, coord_worktree: Path, coord_feature_dir: Path
) -> None:
    """Commit the just-emitted status artifacts to the coord branch (FR-004 row 7).

    Composes canonical primitives only: ``CoordinationWorkspace.resolve`` already
    chose the destination worktree; the write target is resolved through the
    single placement seam (``resolve_placement_only`` for the ``STATUS_STATE``
    kind — the SAME seam ``_resolve_write_target`` uses), never a checkout-derived
    ref; ``safe_commit`` is the single low-level commit primitive (the one
    ``BookkeepingTransaction`` uses) whose HEAD==destination guard keeps the write
    representable on the coord branch.
    """
    from mission_runtime import MissionArtifactKind, resolve_placement_only  # noqa: PLC0415
    from specify_cli.git.commit_helpers import safe_commit  # noqa: PLC0415

    paths = tuple(
        candidate
        for candidate in (
            coord_feature_dir / _EVENTS_FILENAME,
            coord_feature_dir / _DERIVED_STATUS_FILENAME,
        )
        if candidate.exists()
    )
    if not paths:
        return
    write_target = resolve_placement_only(
        repo_root, mission_slug, kind=MissionArtifactKind.STATUS_STATE
    )
    safe_commit(
        repo_root=repo_root,
        worktree_root=coord_worktree,
        target=write_target,
        message=f"chore(spec-kitty): status transition {coord_feature_dir.name}",
        paths=paths,
        capability=GuardCapability.STANDARD,
    )


def _snapshot_coord_status_artifacts(coord_feature_dir: Path) -> tuple[int, bytes | None]:
    """Capture the coord event-log size + derived-snapshot bytes BEFORE emit.

    Paired with :func:`_restore_coord_status_artifacts` so the FR-004 coord
    fallback arm can roll an emitted-but-uncommitted event back if the subsequent
    coord commit fails (rollback-symmetry with the transactional True-arm).
    """
    events_path = coord_feature_dir / _EVENTS_FILENAME
    status_path = coord_feature_dir / _DERIVED_STATUS_FILENAME
    pre_event_size = events_path.stat().st_size if events_path.exists() else 0
    pre_status = status_path.read_bytes() if status_path.exists() else None
    return pre_event_size, pre_status


def _restore_coord_status_artifacts(
    coord_feature_dir: Path,
    *,
    pre_emit_event_size: int,
    pre_emit_status_bytes: bytes | None,
) -> None:
    """Truncate/restore the coord status artifacts after a failed coord commit.

    Mirrors ``workflow._restore_status_artifacts`` so the FR-004 coord fallback
    arm is transactional-symmetric with the ``BookkeepingTransaction`` True-arm: a
    commit failure truncates the just-appended event (and restores the derived
    snapshot) rather than stranding an emitted-but-uncommitted event on the coord
    worktree working copy.
    """
    events_path = coord_feature_dir / _EVENTS_FILENAME
    status_path = coord_feature_dir / _DERIVED_STATUS_FILENAME
    try:
        if events_path.exists():
            with events_path.open("ab") as fh:
                fh.truncate(pre_emit_event_size)
    except OSError:
        _logger.exception("Could not truncate %s on coord commit failure", events_path)
    try:
        if pre_emit_status_bytes is None:
            status_path.unlink(missing_ok=True)
        else:
            status_path.write_bytes(pre_emit_status_bytes)
    except OSError:
        _logger.exception("Could not restore %s on coord commit failure", status_path)


def _coord_feature_dir(coord_worktree: Path, mission_slug: str, mid8: str) -> Path:
    """The coord worktree's on-disk feature dir for this mission (single grammar)."""
    # Explicit local annotation re-narrows the cross-module ``KITTY_SPECS_DIR``
    # (``Any`` under ``follow_imports = "skip"``) back to ``Path``.
    feature_dir: Path = coord_worktree / KITTY_SPECS_DIR / _transaction_dir_name(mission_slug, mid8)
    return feature_dir


def _capture_coord_tail(coord_feature_dir: Path, pre_emit_event_size: int) -> EventStream:
    """Read this operation's appended rows while its status lock is held."""
    events_path = coord_feature_dir / _EVENTS_FILENAME
    if not events_path.exists():
        return EventStream()
    with events_path.open("rb") as fh:
        fh.seek(pre_emit_event_size)
        tail = fh.read().decode("utf-8")
    return _read_event_stream_from_text(coord_feature_dir, tail)


def _fan_out_committed_coord_tail(
    stream: EventStream,
    *,
    mission_slug: str,
    repo_root: Path | None,
    ensure_sync_daemon: bool,
) -> None:
    """Announce only the rows captured for the successful coord commit.

    The stream is captured under L1 before the commit. Fan-out happens after
    commit and lock release, so another writer cannot enter this operation's
    announcements and outbound I/O cannot hold the status lock.
    """
    for event in stream.transitions:
        _emit._saas_fan_out(
            event,
            mission_slug,
            repo_root,
            policy_metadata=event.policy_metadata,
            ensure_sync_daemon=ensure_sync_daemon,
        )
    for annotation in stream.annotations:
        _emit._resolved_binding_fan_out(annotation, mission_slug)


_CoordEmitResult = TypeVar("_CoordEmitResult")


def _emit_on_coord_then_commit(
    identity: _TransactionIdentity,
    mission_slug: str,
    coord_worktree: Path,
    *,
    emit: Callable[[Path], _CoordEmitResult],
    repo_root: Path | None,
    ensure_sync_daemon: bool,
) -> tuple[_CoordEmitResult, Path]:
    """The coord fallback arm shared by the single and batch doors (FR-004 row 7).

    Order is load-bearing: *emit* (the flat shell, fan-out suppressed) ->
    ``safe_commit`` -> fan out the committed tail. A commit failure truncates
    the just-emitted rows back (rollback-symmetry with the transactional
    True-arm) and NO fan-out fires for them (SC-002) -- the ``finally`` only
    restores; the deferred step 7 is reached only on the success path.
    Returns the emit result and the coord feature dir the write landed on.
    """
    coord_fd = _coord_feature_dir(coord_worktree, mission_slug, identity.mid8)
    # The flat shell re-enters the same L1. Keep it through commit/rollback:
    # otherwise rollback may erase another writer's successful append. This
    # take spans safe_commit (~9 git subprocesses), so -- unlike the plain
    # single-writer L1 takes elsewhere -- it is deliberately bounded rather
    # than left at the lock's unbounded (-1) default: a stalled sibling
    # writer (blocked pre-commit hook, held .git/index.lock, credential
    # prompt) must surface as a structured FeatureStatusLockTimeoutError,
    # not wedge every status writer for this mission forever. See
    # NFR-001's dated amendment in
    # kitty-specs/fsm-write-path-integrity-01M1TZV6/spec.md and
    # design-notes/WP01-lock-rules.md for why this L1-across-git take is
    # accepted (rollback-safety) and bounded instead of eliminated.
    with feature_status_lock(
        identity.repo_root,
        coord_fd.name,
        timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    ):
        pre_size, pre_status = _snapshot_coord_status_artifacts(coord_fd)
        committed = False
        try:
            result = emit(coord_fd)
            stream = _capture_coord_tail(coord_fd, pre_size)
            _commit_status_artifacts_to_coord(
                repo_root=identity.repo_root,
                mission_slug=mission_slug,
                coord_worktree=coord_worktree,
                coord_feature_dir=coord_fd,
            )
            committed = True
        except SafeCommitRecoveryFailed as exc:
            # A landed commit remains authoritative even when restoring the
            # caller's staging failed. Match BookkeepingTransaction: retain
            # its artifacts and propagate the recovery error without fan-out.
            committed = exc.commit_sha is not None
            raise
        finally:
            if not committed:
                _restore_coord_status_artifacts(
                    coord_fd,
                    pre_emit_event_size=pre_size,
                    pre_emit_status_bytes=pre_status,
                )
    _fan_out_committed_coord_tail(
        stream,
        mission_slug=mission_slug,
        repo_root=repo_root,
        ensure_sync_daemon=ensure_sync_daemon,
    )
    return result, coord_fd


def _fallback_emit_single(
    identity: _TransactionIdentity,
    request: TransitionRequest,
    mission_slug: str,
    *,
    ensure_sync_daemon: bool,
) -> StatusEvent:
    """Single-event non-transactional fallback (FR-004 rows 7-8).

    ``_primary`` (coord-less: ``SINGLE_BRANCH`` / ``LANES`` / flat) is the
    plain-door call with its uncommitted-write semantics (C-008; pinned by
    ``tests/specify_cli/coordination/test_plain_door_semantics.py``) and, as
    no commit exists there, immediate fan-out is correct. ``_coord`` defers
    fan-out behind the coord commit (FR-008).
    """

    def _primary() -> StatusEvent:
        event = _emit.emit_status_transition(request, ensure_sync_daemon=ensure_sync_daemon)
        _tombstone_lane_workspace_context_on_cancel(
            repo_root=identity.repo_root,
            mission_slug=mission_slug,
            read_feature_dir=identity.feature_dir,
            event=event,
        )
        return event

    def _coord(coord_worktree: Path) -> StatusEvent:
        def _flat_shell(coord_fd: Path) -> StatusEvent:
            event: StatusEvent = _emit.emit_status_transition(
                replace(request, feature_dir=coord_fd, mission_dir=None),
                ensure_sync_daemon=ensure_sync_daemon,
                fan_out=False,
            )
            return event

        event, coord_fd = _emit_on_coord_then_commit(
            identity,
            mission_slug,
            coord_worktree,
            emit=_flat_shell,
            repo_root=request.repo_root,
            ensure_sync_daemon=ensure_sync_daemon,
        )
        _tombstone_lane_workspace_context_on_cancel(
            repo_root=identity.repo_root,
            mission_slug=mission_slug,
            read_feature_dir=coord_fd,
            event=event,
        )
        return event

    return _emit_via_non_transactional_fallback(
        identity, mission_slug, primary_emit=_primary, coord_emit=_coord
    )


def _fallback_emit_batch(
    identity: _TransactionIdentity,
    requests: list[TransitionRequest],
    mission_slug: str,
    *,
    ensure_sync_daemon: bool,
) -> list[StatusEvent]:
    """Same-WP batch non-transactional fallback (FR-004 rows 7-8).

    Same two arms as :func:`_fallback_emit_single`; the coord arm fans the
    committed tail out with the batch's emitting checkout root (the batch is
    ONE lifecycle operation on one mission/WP, so ``requests[0].repo_root``
    is the checkout every member emits from).
    """

    def _primary() -> list[StatusEvent]:
        # Local annotation re-narrows the cross-module (``Any``) emit result.
        events: list[StatusEvent] = _emit.emit_status_transition_batch(
            requests, ensure_sync_daemon=ensure_sync_daemon
        )
        return events

    def _coord(coord_worktree: Path) -> list[StatusEvent]:
        def _flat_shell(coord_fd: Path) -> list[StatusEvent]:
            events: list[StatusEvent] = _emit.emit_status_transition_batch(
                [replace(req, feature_dir=coord_fd, mission_dir=None) for req in requests],
                ensure_sync_daemon=ensure_sync_daemon,
                fan_out=False,
            )
            return events

        events, _coord_fd = _emit_on_coord_then_commit(
            identity,
            mission_slug,
            coord_worktree,
            emit=_flat_shell,
            repo_root=requests[0].repo_root,
            ensure_sync_daemon=ensure_sync_daemon,
        )
        return events

    return _emit_via_non_transactional_fallback(
        identity, mission_slug, primary_emit=_primary, coord_emit=_coord
    )


def _is_under_worktree(feature_dir: Path) -> bool:
    """Return whether *feature_dir* lives under a ``.worktrees`` segment.

    #1900 / FR-001: the raw ``".worktrees" in parts`` path-shape proposal is no
    longer spelled here — it routes through the blessed seam authority
    :func:`is_under_worktrees_segment` (``coordination/surface_resolver.py``), the
    single home of that shape idiom (C-SEAM-1). This is a *shape* read (generic
    worktree-context detection / re-anchor gate), NOT a coord-vs-lane routing
    decision; coord routing uses :func:`_is_coord_worktree_status_surface` below,
    which consults the git registry.
    """
    from specify_cli.coordination.surface_resolver import (  # noqa: PLC0415
        is_under_worktrees_segment,
    )

    return bool(is_under_worktrees_segment(feature_dir))


def _is_coord_worktree_status_surface(feature_dir: Path) -> bool:
    """Return True only when *feature_dir* is a *registered* coord worktree.

    #1900 / FR-001 / FR-007: the former hand-rolled ``-coord`` suffix + parts
    predicate (a 5th parallel topology-selection site) is migrated to the single
    canonical authority :func:`is_registered_coord_worktree`
    (``coordination/surface_resolver.py``) — name proposes, the git worktree
    registry disposes (C-SEAM-1). A lane worktree, the primary checkout, or an
    unregistered husk therefore returns ``False``, killing the split-brain where
    a lane/husk path silently received coord write-contract routing
    (#1589/#1821).

    Fails *open to non-coord* when the registry cannot be read
    (:class:`WorktreeRegistryUnavailable`) — e.g. ad-hoc test fixtures or paths
    outside a git repo. The historical predicate was pure-path and never raised;
    treating an unreadable registry as "not a coord surface" preserves that
    no-raise contract here while keeping the authoritative answer whenever git
    *can* be consulted. (The genuine fail-closed posture for status reads lives
    in the resolver itself, not in this routing convenience.)
    """
    from specify_cli.coordination.surface_resolver import (  # noqa: PLC0415
        WorktreeRegistryUnavailable,
        is_registered_coord_worktree,
    )

    try:
        return bool(is_registered_coord_worktree(feature_dir))
    except WorktreeRegistryUnavailable:
        return False


def _canonical_repo_root(feature_dir: Path, repo_root: Path) -> Path:
    """Return the canonical (main-checkout) repo root for the status anchor.

    The CWD-invariant primary feature-dir anchor must be composed from the
    *main-checkout* repo root; deriving it from a lane-worktree root would
    anchor status on a lane-local (sparse-excluded) surface. We therefore
    canonicalize the root via the single worktree-pointer resolver. Worktree
    roots (coordination or lane) are returned as-is here — the lane re-anchor to
    the canonical primary surface happens one level up in
    :func:`_canonical_primary_feature_dir`'s ``_fallback`` (which DOES split coord
    from lane via the registry authority). Falls back to the supplied root when
    no enclosing git repo is found (ad-hoc test fixtures built outside a
    worktree).

    #1900 / FR-001: the worktree-context read is the blessed seam shape predicate
    (:func:`_is_under_worktree` → ``is_under_worktrees_segment``), not a raw
    ``".worktrees" in parts`` test (C-SEAM-1). Byte-identical to the prior
    ``_is_coordination_feature_dir`` membership it replaces.
    """
    if _is_under_worktree(feature_dir):
        return repo_root

    from specify_cli.workspace.root_resolver import (  # noqa: PLC0415
        WorkspaceRootNotFound,
        resolve_canonical_root,
    )

    try:
        canonical: Path = resolve_canonical_root(feature_dir)
    except WorkspaceRootNotFound:
        return repo_root
    return canonical


def _canonical_primary_feature_dir(
    repo_root: Path, mission_slug: str, fallback: Path
) -> Path:
    """Resolve the CWD-invariant primary feature-dir anchor via the facade.

    Consumes the single canonical authority
    (``placement_seam(...).read_dir(PRIMARY_METADATA)``) so the primary anchor
    is identical whether the request originates from a sparse lane worktree or
    the primary checkout. This is the #1737 / F-007 root fix: the
    transaction-identity anchor no longer re-derives where status lives from a
    CWD-dependent path, so an in-progress WP can no longer be misread as
    ``genesis`` from a lane worktree.

    Coordination topology resolution downstream
    (``_read_contract_from_transaction_target``) still derives the coord path
    from this anchor + ``meta.json``; we keep the anchor on the canonical primary
    dir so that meta loading and coord-ref derivation remain intact (C-004).

    Returns ``fallback`` (the canonicalized request dir) when no canonical
    surface can be resolved — e.g. ad-hoc test fixtures or bootstrap windows
    where ``meta.json`` is not yet present.
    """
    from mission_runtime import MissionArtifactKind, placement_seam  # noqa: PLC0415
    from specify_cli.coordination.surface_resolver import (  # noqa: PLC0415
        resolve_status_surface_with_anchor,
    )
    from specify_cli.missions._read_path_resolver import (  # noqa: PLC0415
        StatusReadPathNotFound,
    )

    def _primary_anchor() -> Path:
        anchor: Path = placement_seam(repo_root, mission_slug).read_dir(
            MissionArtifactKind.PRIMARY_METADATA
        )
        return anchor

    def _fallback() -> Path:
        # The request-derived fallback is only safe when it is the canonical
        # coord surface or a non-worktree primary path. A *lane* ``.worktrees``
        # path is a sparse-excluded surface that would both misread status and
        # trip the primary-checkout read contract, so anchor on the canonical
        # primary candidate instead (fail to the authority, never to the lane).
        # #1900 / FR-001: coord-vs-lane is the git-registry authority's call
        # (_is_coord_worktree_status_surface → is_registered_coord_worktree), and
        # the generic "am I under a worktree" gate is the blessed shape predicate
        # (_is_under_worktree → is_under_worktrees_segment) — neither spells a raw
        # ``-coord``/``.worktrees`` path test here (C-SEAM-1).
        if _is_coord_worktree_status_surface(fallback):
            return fallback
        if _is_under_worktree(fallback):
            return _primary_anchor()
        return fallback

    # FR-005 / #1821: resolve the canonical surface ONCE and consume the carried
    # primary anchor. The previous code resolved the surface for validation,
    # discarded it, then re-invoked the primary resolver — a second composition
    # of the same path. Now both halves come from one resolution.
    try:
        resolved = resolve_status_surface_with_anchor(repo_root, mission_slug)
    except FileNotFoundError:
        # No meta.json at the canonical location: degrade to the request dir so
        # ad-hoc fixtures and the create→first-write window keep working.
        return _fallback()
    except ValueError:
        # Malformed meta — surface the canonical anchor anyway; downstream meta
        # loading will report the same condition consistently.
        return _primary_anchor()
    except StatusReadPathNotFound as exc:
        # Fail-closed surface refusal (PR #1850 M6): the coord worktree root is
        # materialized without the mission dir (#1589/#1821). The refusal
        # protects status READERS from a stale primary surface; the transaction
        # identity needs only the canonical primary anchor — which the
        # structured error already carries (re-resolving via the primary seam
        # would just re-raise). Coordination topology is still honoured
        # downstream by ``_read_contract_from_transaction_target``.
        refusal_anchor: Path = exc.primary_candidate
        return refusal_anchor
    return resolved.primary_anchor


def _resolve_write_target(
    repo_root: Path, mission_slug: str, coord_branch: str | None
) -> str:
    """Resolve the status write-target ref via the canonical placement resolver.

    FR-004 / D-2 adoption (the latent-bug fix): the prior inline selector was
    ``coord_branch or _current_branch(repo_root)``. The flat arm
    (``_current_branch`` = ``git rev-parse --abbrev-ref HEAD``) was **CWD-dependent**
    — it routed status events to whatever branch happened to be checked out,
    diverging from the CWD-invariant ``target_branch`` the read/placement path
    resolves to (reduction-census §6). This routes the write-target through the
    single public placement resolver
    (:func:`mission_runtime.resolve_placement_only`), whose
    ``CommitTarget`` is BYTE-IDENTICAL to the value the full execution context
    builder computes:

    * **Coord topology** (``meta.coordination_branch`` declared) →
      ``CommitTarget(ref=coordination_branch)`` — identical to the prior
      ``coord_branch`` short-circuit (idempotency-preserving, NFR-004).
    * **Flat/base topology** (no coord branch) → ``CommitTarget(ref=target_branch)``
      — the CWD-invariant fix that supersedes ``_current_branch``.

    FR-003 / #1716 closure (WP04/T017): when the placement resolver cannot
    resolve the mission (a blank/whitespace slug, or the coord-worktree-
    materialized-without-mission-dir refusal reached in the pre-``meta.json``
    create window), the fallback no longer reads the ambient checkout HEAD.
    It instead resolves the SAME CWD-invariant ``target_branch`` the port
    itself consults internally
    (:func:`specify_cli.core.paths.get_feature_target_branch` — reads the
    mission's ``target_branch`` from the primary ``meta.json`` when present,
    else the repo's configured primary branch), so a status write in the
    create window still resolves without deadlock and without guessing off
    whatever branch happens to be checked out. ``coord_branch`` still
    short-circuits first when the caller already has one in hand.

    WP05 / IC-06b / FR-005 / C-004 (pre-gate adoption, real behavior change):
    this now routes through the shared
    :func:`mission_runtime.resolve_write_target_or_degrade` helper (WP04),
    which ADDS the ``_mission_meta_exists`` pre-gate this selector lacked.
    Before this adoption, the inline ``try`` arm always called
    ``resolve_placement_only`` even in the no-``meta.json`` bootstrap window;
    that function never raises for a merely-absent mission (documented
    contract) — it silently degrades INTERNALLY to
    ``get_feature_target_branch``, with no awareness of ``coord_branch`` at
    all, so the ``except`` arm computing ``coord_branch or
    get_feature_target_branch(...)`` was unreachable there — a caller-
    supplied ``coord_branch`` was silently discarded in that window. The
    pre-gate closes this: when ``meta.json`` is absent, resolution is skipped
    entirely and ``degrade_ref = coord_branch or
    get_feature_target_branch(...)`` is returned directly, honoring a
    supplied ``coord_branch`` instead of dropping it (T021). ``STATUS_STATE``
    stays a coordination kind — for a bootstrapped mission (``meta.json``
    present) the helper's pre-gate passes through and still consults
    ``resolve_placement_only``, keeping the coordination-branch routing under
    coord topology; it is never flattened to the primary target branch
    (C-004, T023).

    Landing-fold (PR #2963, P2): ``get_feature_target_branch`` is now only
    ever CALLED from the ``except ActionContextError`` arm below, i.e. lazily
    — once the helper has genuinely failed to resolve the mission and has no
    ``degrade_ref`` to fall back on. It is never invoked eagerly on the happy
    path (a resolvable mission with no ``coord_branch`` in hand), which is
    every SINGLE_BRANCH/LANES status transition.
    """
    from mission_runtime import (  # noqa: PLC0415
        ActionContextError,
        MissionArtifactKind,
        resolve_write_target_or_degrade,
    )
    from specify_cli.core.paths import get_feature_target_branch  # noqa: PLC0415

    # Landing-fold (PR #2963 finding): ``get_feature_target_branch`` is NOT
    # computed eagerly here. It shells out to
    # ``resolve_primary_branch``/``git symbolic-ref`` (and, on the ambient-HEAD
    # fallback path, a further ``get_current_branch`` read) — real cost that
    # was previously paid on EVERY status transition without a coord branch in
    # hand (all SINGLE_BRANCH/LANES missions), even on the happy path where the
    # port resolves and the eager value is discarded. ``degrade_ref`` is now
    # passed through as-is (``coord_branch`` or ``None``) and
    # ``get_feature_target_branch`` is only invoked in the ``except`` arm,
    # i.e. once the port has genuinely failed to resolve — preserving T021's
    # behaviour that a caller-supplied ``coord_branch`` is still honored
    # directly in the bootstrap window (the pre-gate returns it before ever
    # needing the fallback).
    #
    # The STATUS write target MUST keep resolving the coordination branch
    # under coord topology (write-surface-coherence WP02 / T031 / C-001 /
    # G-2). STATUS_STATE is a coordination kind, so the kind-aware placement
    # keeps the topology-routed ref — it MUST NOT be flipped to a primary
    # kind.
    try:
        return resolve_write_target_or_degrade(
            repo_root,
            mission_slug,
            MissionArtifactKind.STATUS_STATE,
            degrade_ref=coord_branch or None,
        ).ref
    except ActionContextError:
        fallback_ref: str = get_feature_target_branch(repo_root, mission_slug)
        return fallback_ref


def _identity_for_request(request: TransitionRequest) -> _TransactionIdentity:
    raw_feature_dir = request.feature_dir or request.mission_dir
    if raw_feature_dir is None:
        raise TypeError("transactional status emit requires feature_dir/mission_dir")

    mission_slug = request.mission_slug or request._legacy_mission_slug
    if mission_slug is None:
        raise TypeError("transactional status emit requires mission_slug")

    # #1737 / F-007: anchor the transaction identity on the CWD-invariant
    # canonical primary feature dir resolved through the facade, instead of
    # trusting the (CWD-dependent, existence-gated) canonicalize redirect alone.
    primary_root = None
    if request.effective_root is not None:
        from specify_cli.core.owned_mission import resolve_owned_mission

        primary_root = _repo_root_for_feature(raw_feature_dir, request.repo_root)
        owned = resolve_owned_mission(primary_root, request.effective_root, mission_slug)
        feature_dir, repo_root = owned.directory, owned.root
    else:
        canonical_feature_dir = canonicalize_feature_dir(raw_feature_dir)
        interim_repo_root = _repo_root_for_feature(canonical_feature_dir, request.repo_root)
        canonical_repo_root = _canonical_repo_root(canonical_feature_dir, interim_repo_root)
        feature_dir = _canonical_primary_feature_dir(
            canonical_repo_root, mission_slug, fallback=canonical_feature_dir
        )
        repo_root = request.repo_root or canonical_repo_root

    # FR-007: fail-closed reader routing. Malformed meta surfaces typed
    # MissionMetaReadError instead of raw ValueError.
    from specify_cli.core.paths import load_meta_fail_closed
    meta = load_meta_fail_closed(feature_dir)

    coord_branch: str | None = None
    mission_id: str | None = None
    mid8: str | None = None
    meta_exists = isinstance(meta, dict)
    if isinstance(meta, dict):
        raw_coord = meta.get("coordination_branch")
        raw_mission_id = meta.get("mission_id")
        raw_mid8 = meta.get("mid8")
        coord_branch = str(raw_coord) if raw_coord else None
        mission_id = str(raw_mission_id) if raw_mission_id else None
        mid8 = str(raw_mid8) if raw_mid8 else None
        # Single grammar (FR-010): when meta carries no explicit ``mid8`` we leave
        # it ``None`` and let the canonical ``resolve_transaction_mid8`` derive it
        # from the declared ``mission_id`` (its cascade does ``mission_id[:8]``).
        # Pre-deriving here via the bare slicer was redundant (proven byte-equal)
        # and is the last external caller of the demoted ``mid8`` primitive
        # (mission 01KV7SFD / WP01).

    # WP04/FR-004: mission_id is the canonical ULID or None — never a slug-derived
    # fallback. The f"legacy-{slug}" sentinel is removed from the stored field;
    # BookkeepingTransaction.acquire receives it ONLY as an explicit worktree-lock
    # identifier for legacy missions (not persisted to any mission_id event field).
    effective_mission_id = mission_id
    # FR-007: the mid8 names the ON-DISK transaction dir. Route through the
    # canonical fail-closed authority instead of fabricating a zero-padded mid8
    # from the slug — that idiom invented a wrong-but-plausible dir name and
    # mis-routed the transaction/lock target.
    effective_mid8 = resolve_transaction_mid8(
        mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        coordination_branch=coord_branch,
    )
    transaction_dir_name = _transaction_dir_name(mission_slug, effective_mid8)
    if request.effective_root is not None:
        from mission_runtime import MissionArtifactKind, resolve_placement_only

        assert primary_root is not None
        destination_ref = resolve_placement_only(
            primary_root, mission_slug, kind=MissionArtifactKind.STATUS_STATE,
            effective_root=request.effective_root,
        ).ref
    else:
        destination_ref = _resolve_write_target(repo_root, mission_slug, coord_branch)
    return _TransactionIdentity(
        repo_root=repo_root,
        feature_dir=feature_dir,
        mission_id=effective_mission_id,
        mid8=effective_mid8,
        destination_ref=destination_ref,
        meta_exists=meta_exists,
        coordination_branch=coord_branch,
        transaction_meta_exists=(feature_dir.parent / transaction_dir_name / "meta.json").exists(),
        primary_root=primary_root,
    )


def _resolve_transaction_entry(
    request: TransitionRequest, mission_slug: str
) -> tuple[_TransactionIdentity, bool]:
    """Shared preamble of the single and batch doors: identity + topology + owned check.

    ONE place decides whether a request may take the ``BookkeepingTransaction``
    path (FR-007 / decision Q5 parity, data-model §5 S-2): the batch door used
    to skip the owned-mission refusal the single door applied, so an
    ``effective_root`` request could silently degrade to the non-transactional
    fallback. An owned mission (#1737) requires the transaction; refusing it
    here makes the divergence structurally impossible.
    """
    identity = _identity_for_request(request)
    topology_available = _transaction_topology_available(identity, mission_slug)
    if request.effective_root is not None and not topology_available:
        from mission_runtime import ActionContextError  # noqa: PLC0415

        raise ActionContextError(
            "OWNED_TRANSACTION_UNAVAILABLE", "Owned mission requires transactional status metadata."
        )
    return identity, topology_available


def _acquire_status_transaction(
    identity: _TransactionIdentity,
    mission_slug: str,
    *,
    operation: str,
    capability: GuardCapability,
) -> BookkeepingTransaction:
    """The ONE ``BookkeepingTransaction.acquire`` shape for every door (contract §2 step 1).

    * ``repo_root`` anchors the lock/worktree on the PRIMARY root for an owned
      mission (``identity.primary_root``) and on the mission's own root
      otherwise; ``effective_root`` is the owned checkout in the former case
      and omitted (``None``) in the latter.
    * WP04/FR-004: ``acquire`` requires ``str`` for its lock/path management.
      For a legacy mission (``identity.mission_id is None``) the explicit
      ``f"legacy-{slug}"`` string is the transaction-lock identifier ONLY --
      it is never written into any ``mission_id`` event field.
    """
    return BookkeepingTransaction.acquire(
        repo_root=identity.primary_root or identity.repo_root,
        mission_id=identity.mission_id or f"legacy-{mission_slug}",
        mission_slug=mission_slug,
        mid8=identity.mid8,
        destination_ref=identity.destination_ref,
        operation=operation,
        capability=capability,
        effective_root=identity.repo_root if identity.primary_root is not None else None,
    )


def _durability_unit(prepared: PreparedTransition, event: StatusEvent) -> list[StatusEvent | InnerStateChanged]:
    """A transition and its claim annotation are appended as one unit.

    A resolved binding must never lag behind the claim it describes: one
    ``txn.append_events`` call carries both rows.
    """
    annotation = prepared.annotation
    return [event, *([annotation] if annotation is not None else [])]


def _defer_fan_out(
    txn: BookkeepingTransaction,
    prepared: PreparedTransition,
    event: StatusEvent,
    *,
    mission_slug: str,
    repo_root: Path | None,
    ensure_sync_daemon: bool,
) -> None:
    """Step 7 of the transactional shell: fan-out fires only after commit success."""
    if prepared.annotation is not None:
        txn.defer_outbound(_deferred_resolved_binding_fan_out(prepared.annotation, mission_slug))
    queue_saas_emission(
        txn,
        event,
        mission_slug=mission_slug,
        repo_root=repo_root,
        ensure_sync_daemon=ensure_sync_daemon,
    )


def _collapse_alias_in_transaction(
    feature_dir: Path,
    request: TransitionRequest,
    *,
    mission_slug: str,
    mission_id: str | None,
    from_lane: str,
    prepared: PreparedTransition,
) -> StatusEvent:
    """Alias-collapse no-op arm of the single door (C-007): mirror only, nothing appended.

    The pipeline only *requests* the phase-gated frontmatter mirror
    (``mirror_frontmatter_lane``); the shell performs it here -- the same
    ``_mirror_phase1_frontmatter_lane`` write the arm always did, still the
    tree's only ``write_frontmatter`` of ``lane`` (the 2093 invariant). The
    persisted arm of this shell never mirrored (a frontmatter write on the
    coord worktree would dirty the coord tree, #2939), and still does not.
    Returns the same unpersisted synthetic same-lane event as before.
    """
    if request.wp_id is None:  # guarded by the pipeline; keeps the type invariant explicit
        raise TypeError("transactional status emit requires wp_id")
    if prepared.mirror_frontmatter_lane:
        _emit._mirror_phase1_frontmatter_lane(feature_dir, request.wp_id, prepared.resolved_lane)
    # #4327: normalize the inline moment fields exactly as the persisted arm
    # does (``prepare_transition`` already refused invalid values at the
    # shared boundary before choosing this arm); the synthetic event a
    # caller inspects must never carry an un-normalized gist/pointer shape a
    # persisted event would not.
    from specify_cli.status.moment_fields import validate_review_ref, validate_summary

    summary = validate_summary(request.summary) if request.summary is not None else None
    review_ref = validate_review_ref(request.review_ref, repo_root=request.repo_root) if request.review_ref is not None else None
    synthetic: StatusEvent = _emit.build_status_event(
        mission_slug=mission_slug,
        wp_id=request.wp_id,
        from_lane=from_lane,
        to_lane=from_lane,
        actor=request.actor or "unknown",
        mission_id=mission_id,
        force=request.force,
        execution_mode=request.execution_mode,
        reason=request.reason,
        review_ref=review_ref,
        summary=summary,
        review_result=request.review_result,
        policy_metadata=request.policy_metadata,
    )
    return synthetic


def _deferred_resolved_binding_fan_out(
    annotation: InnerStateChanged,
    mission_slug: str,
) -> Callable[[], None]:
    """Return a typed post-commit resolved-binding fan-out callback."""

    def emit() -> None:
        _emit._resolved_binding_fan_out(annotation, mission_slug)

    return emit


def _read_events_from_transaction_target(
    identity: _TransactionIdentity,
    mission_slug: str,
) -> list[StatusEvent]:
    """Read target status events without creating worktrees or commits."""
    # Local annotation re-narrows the cross-module (``Any``) read result.
    events: list[StatusEvent] = read_event_log(
        _read_contract_from_transaction_target(identity, mission_slug)
    )
    return events


def _read_event_stream_from_transaction_target(
    identity: _TransactionIdentity,
    mission_slug: str,
) -> EventStream:
    """Read transitions and annotations without creating a worktree."""
    return read_event_stream_log(
        _read_contract_from_transaction_target(identity, mission_slug)
    )


def read_current_wp_state_transactional(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    repo_root: Path | None = None,
) -> CurrentWpState:
    """Read the current WP lane/actor/role from the transaction's write target.

    Reads the full event STREAM (transitions + annotations) so the reduced
    ``role`` slot is available on the returned :class:`CurrentWpState` from the
    single in-transaction reduction (C-002). The role rides this value object
    only to the in-lock re-claim collision site; it is never threaded onto the
    guard input contract.
    """
    identity = _identity_for_request(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane=Lane.PLANNED,
            actor="status-read",
            repo_root=repo_root,
        )
    )
    contract = _read_contract_from_transaction_target(identity, mission_slug)
    stream = read_event_stream_log(contract)
    events = stream.transitions
    if not events and not _transaction_topology_available(identity, mission_slug):
        from specify_cli.status.lane_reader import (  # noqa: PLC0415
            CanonicalStatusNotFoundError,
            get_wp_lane,
        )

        try:
            resolved_lane = Lane(resolve_lane_alias(get_wp_lane(identity.feature_dir, wp_id)))
        except (ValueError, FileNotFoundError, CanonicalStatusNotFoundError):
            # GENESIS-fallback contract (FR-008d / R7): exactly two expected
            # failure shapes mean "unseeded WP" and fall back to GENESIS
            # (matching _derive_from_lane on the write side — Contract 3,
            # FR-009): a pre-schema/unknown lane value (ValueError from
            # Lane()/resolve_lane_alias) and an absent log/WP file.
            # ``CanonicalStatusNotFoundError`` is the codebase's concrete
            # "absent log" signal (``get_wp_lane`` raises it instead of
            # FileNotFoundError; the contract names the shape, this names the
            # type). Every other exception (PermissionError, corruption
            # signals, ...) is a real error and MUST propagate — the former
            # broad ``except Exception`` silently converted genesis-corruption
            # signals into "unseeded WP" (#1736 dormant mask 1).
            return CurrentWpState(Lane.GENESIS, None, None)
        if resolved_lane == Lane.UNINITIALIZED:
            # #2675/WP05: ``Lane.UNINITIALIZED`` is now a real ``Lane`` member,
            # so ``Lane("uninitialized")`` no longer raises here and the
            # ``except`` above goes dead for the unseeded-sentinel case. This
            # equality check preserves the same GENESIS-fallback contract
            # explicitly instead of relying on the now-dead ``ValueError``
            # branch: an absent-from-snapshot WP still means "unseeded" ->
            # GENESIS, per FR-008d/R7.
            return CurrentWpState(Lane.GENESIS, None, None)
        return CurrentWpState(resolved_lane, None, None)
    # Single in-transaction reduction (transitions + annotations) surfaces the
    # reduced role slot alongside lane/actor on the value object (C-002).
    return wp_lane_actor_from_events(events, wp_id, stream.annotations)


def _read_contract_routes_through_coordination(
    identity: _TransactionIdentity,
) -> bool:
    """Decide the coord-vs-primary read-contract SHAPE from the STORED topology.

    FR-009 / SC-001: the read-contract coord-vs-primary SHAPE is decided by the
    WP02 topology SSOT, never re-inferred from a bare ``coordination_branch is
    None`` SURFACE test — the exact forbidden re-derivation SC-001 gates against.

    This answers ONLY "is this a coord-SHAPED mission?". The transient on-disk
    arms in the caller (worktree-exists / branch-deleted) keep PROBING the
    materialized-yet/deleted-now state (C-006: #1718 create-window / #1848
    coord-deleted) — the stored topology must NOT answer that transient question.

    Mirrors the canonical WP03 surface-resolver pattern
    (``surface_resolver._topology_uses_coord_surface``): the binary
    coord-vs-primary SHAPE is disposed by the WP02 topology SSOT
    (:func:`mission_runtime.classify_topology`) over the stored
    ``coordination_branch`` VALUE, NOT by a bare ``coordination_branch is None``
    re-inference. ``has_lanes`` is irrelevant to the binary coord-routing SHAPE
    (both ``COORD`` and ``LANES_WITH_COORD`` route through coordination), so the
    coord-less default arm is used — identical to the surface resolver's
    historical two-arg call sites.

    The shape is READ from the WP02 stored ``topology`` (the relocated read site
    now READS the stored value rather than relaying a parallel
    ``classify_topology(coord_branch, …)`` inference — randy #2 / SC-001): the
    PURE :func:`read_topology` reader is anchored on the canonical primary
    ``feature_dir`` the identity carries (where ``meta.json`` lives). An
    un-backfilled legacy mission (or absent/malformed meta) degrades to deriving
    the shape ONCE from the ``coordination_branch`` value via WP01's
    :func:`classify_topology` SSOT — the same single authority, no parallel grid.

    The derivation is **pure** (no ``meta.json`` write), so a status READ never
    persists a ``topology`` back-fill (the read-must-not-write contract, #1814).
    ``mid8`` materialization / branch-deletion stay the transient probe arms below
    (C-006).
    """
    from mission_runtime import (  # noqa: PLC0415
        classify_topology,
        routes_through_coordination,
    )
    from specify_cli.core.paths import MissionMetaReadError  # noqa: PLC0415
    from specify_cli.migration.backfill_topology import (  # noqa: PLC0415
        read_topology,
    )

    try:
        topology = read_topology(identity.feature_dir)
    except (FileNotFoundError, ValueError, OSError, MissionMetaReadError):
        # Un-backfilled legacy mission / absent / malformed primary meta: derive
        # the shape ONCE from the coordination-branch value-read (the historical
        # two-arg arm). Same single ``classify_topology`` authority, no re-inference.
        # This is the C-002 genuine-fallback RELAY — the exception arm reads the
        # stored topology first and only relays via ``classify_topology`` here; it
        # is NOT a routing predicate and stays distinct from the coord-routing
        # disposal below (NFR-005).
        topology = classify_topology(identity.coordination_branch, has_lanes=False)
    # The coord-routing membership is disposed by the ONE canonical predicate over
    # the ONE canonical set — no inline ``{COORD, LANES_WITH_COORD}`` frozenset is
    # restated here (FR-005 / S1192).
    return routes_through_coordination(topology)


def _read_contract_from_transaction_target(
    identity: _TransactionIdentity,
    mission_slug: str,
) -> EventLogReadContract:
    """Resolve the read-only contract for the transaction write target."""
    if not _transaction_topology_available(identity, mission_slug):
        # #1900 / FR-001: the worktree-context read is the blessed seam shape
        # predicate (_is_under_worktree → is_under_worktrees_segment), not a raw
        # ``.worktrees`` membership test (C-SEAM-1). Byte-identical to the prior
        # ``_is_coordination_feature_dir`` membership it replaces — a feature dir
        # already inside a worktree carries the coordination read contract.
        if _is_under_worktree(identity.feature_dir):
            return EventLogReadContract.coordination_worktree(identity.feature_dir)
        return EventLogReadContract.primary_checkout(identity.feature_dir)
    # FR-009 / SC-001: the coord-vs-primary SHAPE is read from the STORED topology
    # (the WP03 seam), retiring the prior ``coordination_branch is None`` SURFACE
    # re-inference. The transient on-disk arms below stay probe-discriminated.
    if not _read_contract_routes_through_coordination(identity):
        return EventLogReadContract.primary_checkout(identity.feature_dir)

    from specify_cli.coordination.workspace import CoordinationWorkspace  # noqa: PLC0415

    worktree_root = CoordinationWorkspace.worktree_path(
        identity.repo_root,
        mission_slug,
        identity.mid8,
    )
    transaction_feature_dir = worktree_root / KITTY_SPECS_DIR / _transaction_dir_name(
        mission_slug,
        identity.mid8,
    )
    if worktree_root.exists():
        return EventLogReadContract.coordination_worktree(transaction_feature_dir)
    if not _branch_exists(identity.repo_root, identity.destination_ref):
        # The coordination branch was deleted (e.g. post-merge cleanup).
        # FR-018 recreates it from the destination ref at write time, so the
        # primary checkout is the authoritative read source until then;
        # reading the dangling ref would report every WP as genesis (#1847).
        return EventLogReadContract.primary_checkout(identity.feature_dir)
    return EventLogReadContract.coordination_branch_ref(
        repo_root=identity.repo_root,
        destination_ref=identity.destination_ref,
        feature_dir=transaction_feature_dir,
        parser_feature_dir=identity.feature_dir,
    )


def read_events_transactional(
    *,
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path | None = None,
    effective_root: Path | None = None,
) -> list[StatusEvent]:
    """Read status events from the same target transactional writes use."""
    identity = _identity_for_request(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP00",
            to_lane=Lane.PLANNED,
            actor="status-read",
            repo_root=repo_root,
            effective_root=effective_root,
        )
    )
    return _read_events_from_transaction_target(identity, mission_slug)


def read_event_stream_transactional(
    *,
    feature_dir: Path,
    mission_slug: str,
    repo_root: Path | None = None,
) -> EventStream:
    """Read the complete event stream from the transactional write target."""
    identity = _identity_for_request(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id="WP00",
            to_lane=Lane.PLANNED,
            actor="status-read",
            repo_root=repo_root,
        )
    )
    return _read_event_stream_from_transaction_target(identity, mission_slug)


def has_transition_to_transactional(
    *,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    to_lane: str,
    repo_root: Path | None = None,
) -> bool:
    """Return whether the transaction write target already has a lane event."""
    identity = _identity_for_request(
        TransitionRequest(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=wp_id,
            to_lane=Lane.PLANNED,
            actor="status-read",
            repo_root=repo_root,
        )
    )
    return any(
        event.wp_id == wp_id and str(event.to_lane) == str(to_lane)
        for event in _read_events_from_transaction_target(identity, mission_slug)
    )


# ---------------------------------------------------------------------------
# Workspace-context tombstone on cancel (FR-005 / LC-6, #1842 WP03)
# ---------------------------------------------------------------------------


def _lane_wp_ids_all_terminal(
    work_packages: dict[str, dict[str, Any]], wp_ids: tuple[str, ...]
) -> bool:
    """Return whether every WP in *wp_ids* has reached a terminal lane.

    Mirrors ``status/doctor.py``'s ``check_orphan_workspaces`` all-terminal
    gate (``all(wp.lane in {done, canceled})``), scoped to one lane's WPs
    instead of every WP in the mission: the workspace-context JSON is
    per-lane, while a ``canceled`` transition is emitted per-WP, so a lane's
    shared context may only be tombstoned once every WP sharing that
    worktree is done or canceled. A WP absent from *work_packages* (never
    transitioned) is treated as non-terminal.
    """
    for wp_id in wp_ids:
        wp_state = work_packages.get(wp_id)
        lane_value = wp_state.get("lane") if wp_state else None
        if lane_value is None or not is_terminal(lane_value):
            return False
    return True


def _tombstone_lane_workspace_context_on_cancel(
    *,
    repo_root: Path,
    mission_slug: str,
    read_feature_dir: Path,
    event: StatusEvent | None,
) -> None:
    """Delete a lane's ``.kittify/workspaces/<slug>-<lane>.json`` once a
    ``canceled`` transition leaves every WP sharing that lane terminal.

    FR-005 / C-004: additive only — this changes no validation, persistence,
    or fan-out behavior for any other transition. No-ops when: *event* is
    ``None`` (the legacy alias-collapse no-op arm — nothing actually
    transitioned); the transition is not into ``canceled``; the mission has
    no ``lanes.json`` (flat/legacy execution has no lane-scoped context to
    tombstone); the WP is not lane-owned; or the lane still has a
    non-terminal WP. ``delete_context`` is a pure, order-independent unlink
    (no worktree gate) — safe to call even when the context file was never
    created (planning-artifact WPs) or was already removed.
    """
    if event is None or event.to_lane != Lane.CANCELED:
        return

    from mission_runtime import MissionArtifactKind, placement_seam  # noqa: PLC0415
    from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json  # noqa: PLC0415

    lanes_read_dir: Path = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.LANE_STATE
    )
    try:
        lanes_manifest = read_lanes_json(lanes_read_dir)
    except CorruptLanesError:
        return  # Malformed lanes.json is not this hook's problem to repair.
    if lanes_manifest is None:
        return

    lane = lanes_manifest.lane_for_wp(event.wp_id)
    if lane is None or not lane.wp_ids:
        return

    snapshot = _reduce_events(_read_raw_events(read_feature_dir))
    if not _lane_wp_ids_all_terminal(snapshot.work_packages, lane.wp_ids):
        return

    workspace_name = worktree_dir_name(mission_slug, mission_id=None, lane_id=lane.lane_id)
    delete_context(repo_root, workspace_name)


def emit_status_transition_transactional(
    request: TransitionRequest,
    *,
    ensure_sync_daemon: bool = True,
    operation: str | None = None,
    capability: GuardCapability = GuardCapability.STANDARD,
) -> StatusEvent:
    """The single transactional door (contract §2, transactional column).

    acquire (L1) -> derive ``from_lane`` once in-lock -> the status-owned
    :func:`prepare_transition` (the tree's only validation) -> one atomic
    append of the event and its claim annotation -> deferred fan-out -> commit
    on exit. Failure policy (C-007): fail-closed on an unresolvable coord
    worktree -- ``BookkeepingWorktreeMissing`` propagates (#1848 / SC-001,
    pinned by ``test_transactional_emit_fails_closed_when_coordination_branch_
    missing``); a pipeline refusal (``TransitionError``) raises before any
    append; the alias-collapse no-op arm appends nothing.
    """
    feature_dir = request.feature_dir or request.mission_dir
    mission_slug = request.mission_slug or request._legacy_mission_slug
    if feature_dir is None or mission_slug is None or request.wp_id is None:
        raise TypeError("transactional status emit requires feature_dir, mission_slug, and wp_id")

    identity, topology_available = _resolve_transaction_entry(request, mission_slug)
    if not topology_available:
        # WP04/FR-004 (rows 7-8): coord topology commits to the coord worktree;
        # coord-less topologies keep the primary-uncommitted write path. The
        # coord-vs-primary decision lives in _emit_via_non_transactional_fallback.
        return _fallback_emit_single(
            identity,
            request,
            mission_slug,
            ensure_sync_daemon=ensure_sync_daemon,
        )

    with _acquire_status_transaction(
        identity,
        mission_slug,
        operation=operation or f"status transition {request.wp_id}",
        capability=capability,
    ) as txn:
        # WP04: identity.mission_id is str | None; None means no ULID (legacy).
        # One reduce of the transaction's write surface (NFR-004) feeds both
        # ``from_lane`` and the dependency verdict, which is resolved INSIDE the
        # transaction against ``txn.feature_dir`` (FR-013) -- the declared deps
        # come from the WP file on the primary planning surface.
        snapshot = _emit._reduce_write_surface(txn.feature_dir)
        from_lane = str(_emit._derive_from_lane(txn.feature_dir, request.wp_id, snapshot=snapshot))
        readiness = _emit._resolve_dependency_readiness(identity.feature_dir, request.wp_id, snapshot)
        prepared = prepare_transition(
            request=request,
            feature_dir=txn.feature_dir,
            mission_slug=mission_slug,
            mission_id=identity.mission_id,
            from_lane=from_lane,
            readiness=readiness,
        )
        if prepared.event is None:
            return _collapse_alias_in_transaction(
                txn.feature_dir,
                request,
                mission_slug=mission_slug,
                mission_id=identity.mission_id,
                from_lane=from_lane,
                prepared=prepared,
            )
        event = prepared.event
        txn.append_events(_durability_unit(prepared, event))
        _defer_fan_out(
            txn,
            prepared,
            event,
            mission_slug=mission_slug,
            repo_root=request.repo_root,
            ensure_sync_daemon=ensure_sync_daemon,
        )
        _tombstone_lane_workspace_context_on_cancel(
            repo_root=identity.repo_root,
            mission_slug=mission_slug,
            read_feature_dir=txn.feature_dir,
            event=event,
        )
        return event


def _lanes_annotation_transaction_available(
    identity: _TransactionIdentity, mission_slug: str
) -> bool:
    """Return whether a stored LANES mission can commit a primary annotation.

    Modern ``LANES`` missions have no distinct coordination branch, but their
    target branch still supports the same ``BookkeepingTransaction`` used by
    the preceding lane transition.  ``SINGLE_BRANCH`` and legacy/flat missions
    retain their historical uncommitted annotation behavior.
    """
    from mission_runtime import MissionTopology  # noqa: PLC0415
    from specify_cli.core.paths import (  # noqa: PLC0415
        MissionMetaReadError,
        load_meta_fail_closed,
    )

    try:
        meta = load_meta_fail_closed(identity.feature_dir)
    except (OSError, MissionMetaReadError):
        return False
    return (
        meta is not None
        and meta.get("topology") == MissionTopology.LANES.value
        and _transaction_topology_available(identity, mission_slug)
    )


def emit_inner_state_changed_transactional(
    feature_dir: Path,
    wp_id: str,
    delta: WPInnerStateDelta,
    *,
    actor: str,
    mission_slug: str,
    at: str | None = None,
    repo_root: Path | None = None,
    operation: str | None = None,
    capability: GuardCapability = GuardCapability.STANDARD,
    effective_root: Path | None = None,
) -> InnerStateChanged:
    """Persist AND commit one off-axis ``InnerStateChanged`` annotation (FR-007).

    The commit-durable sibling of
    :func:`specify_cli.status.emit.emit_inner_state_changed`. On a coordination
    topology the annotation rides a ``BookkeepingTransaction`` — the SAME atomic
    emit+commit seam :func:`emit_status_transition_transactional` uses for a lane
    hop — so the coord ``status.events.jsonl`` / ``status.json`` are committed on
    the coordination ref and a caller such as ``move-task`` returns a clean tree
    (#2939) rather than one dirtied by a written-but-uncommitted annotation.

    A modern stored ``LANES`` mission has no distinct coordination branch, but
    its primary target branch supports the same transaction as its preceding
    lane transition. Its annotation therefore commits there too. Stored
    ``SINGLE_BRANCH`` and genuinely flat/legacy missions still delegate to the
    uncommitted ``emit_inner_state_changed`` for byte-identical no-op parity.
    An explicitly owned checkout instead requires a transaction and never
    falls back to an uncommitted write or another checkout.
    The narrow :func:`_lanes_annotation_transaction_available` predicate reads
    the stored topology before consulting transaction availability, avoiding
    the over-broad legacy-meta arm that previously made a flat mission look
    transactional (``test_flat_topology_annotation_still_lands``).

    Regardless of which predicate decides "attempt a transaction", the coord
    worktree may still turn out to be unmaterializable (e.g. a
    ``coordination_branch`` declared in meta but deleted, or never created) —
    ``BookkeepingTransaction.acquire`` then raises ``BookkeepingWorktreeMissing``.
    Unlike the sibling lane-hop transition (an authoritative state change that
    is deliberately fail-closed on an unresolvable coord worktree, #1848/SC-001
    — see ``FallbackCoordWorktreeUnresolved``), an ``InnerStateChanged``
    annotation is auxiliary/best-effort metadata: a runtime annotation emit
    must never hard-fail ``move-task`` just because the coord worktree isn't
    materialized. So ``BookkeepingWorktreeMissing`` is caught here and degrades
    to the same uncommitted ``emit_inner_state_changed`` write, rather than
    propagating and hard-failing the caller (#3460). This catch is scoped to
    THIS function only — the lane-hop transition and its batch sibling keep
    raising ``BookkeepingWorktreeMissing`` unchanged (pinned by
    ``test_transactional_emit_fails_closed_when_coordination_branch_missing``
    and its batch counterpart).

    ``emit_inner_state_changed`` itself is UNCHANGED and stays partition-agnostic
    (#2939): the durability decision lives here, at the commit layer.
    """
    request = TransitionRequest(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        actor=actor,
        repo_root=repo_root,
        effective_root=effective_root,
    )
    identity = _identity_for_request(request)

    if effective_root is not None and not identity.transaction_meta_exists:
        from mission_runtime import ActionContextError

        raise ActionContextError("OWNED_TRANSACTION_UNAVAILABLE", "Owned annotation requires transactional status metadata.")

    def _uncommitted_emit() -> InnerStateChanged:
        return _emit.emit_inner_state_changed(
            feature_dir,
            wp_id,
            delta,
            actor=actor,
            mission_slug=mission_slug,
            at=at,
            repo_root=repo_root,
        )

    if (
        effective_root is None
        and identity.coordination_branch is None
        and not _lanes_annotation_transaction_available(identity, mission_slug)
    ):
        return _uncommitted_emit()

    annotation = _annotate(
        wp_id,
        delta,
        actor=actor,
        at=at or now_utc_iso(),
        event_id=_emit._generate_ulid(),
    )
    # The acquire shape is the shared one (``_acquire_status_transaction``):
    # ``identity.primary_root`` is set exactly when ``effective_root`` was
    # supplied, so the owned checkout threads through identically here.
    try:
        with _acquire_status_transaction(
            identity,
            mission_slug,
            operation=operation or f"inner-state annotation {wp_id}",
            capability=capability,
        ) as txn:
            txn.append_events([annotation])
            txn.defer_outbound(
                _deferred_resolved_binding_fan_out(annotation, mission_slug)
            )
    except BookkeepingWorktreeMissing:
        if effective_root is not None:
            raise
        # #3460: the coord worktree could not be materialized (e.g. a declared
        # ``coordination_branch`` that was deleted or never created). This
        # annotation is auxiliary — degrade to the uncommitted primary write
        # instead of hard-failing move-task (see docstring).
        return _uncommitted_emit()
    return annotation


def emit_status_transition_batch_transactional(
    requests: list[TransitionRequest],
    *,
    ensure_sync_daemon: bool = True,
    operation: str | None = None,
    capability: GuardCapability = GuardCapability.STANDARD,
) -> list[StatusEvent]:
    """The batch transactional door: steps 2-5 per request under ONE acquisition (FR-018).

    Applies the owned-mission refusal and the ``effective_root`` acquisition
    exactly as the single door (FR-007 / Q5 parity) through the shared
    :func:`_resolve_transaction_entry` / :func:`_acquire_status_transaction`
    preamble. Failure policy (C-007, all-or-nothing): a member targeting
    another mission/WP (``TypeError``) or refused by the pipeline
    (``TransitionError``) raises before the single atomic append, so nothing
    is persisted; an unresolvable coord worktree propagates
    ``BookkeepingWorktreeMissing`` unchanged (fail-closed like the single
    door -- the #3460 degrade belongs to the inner-state door only).
    """
    if not requests:
        return []

    first = requests[0]
    mission_slug = first.mission_slug or first._legacy_mission_slug
    first_feature_dir_raw = first.feature_dir or first.mission_dir
    if mission_slug is None or first.wp_id is None or first_feature_dir_raw is None:
        raise TypeError(
            "transactional status batch requires feature_dir/mission_dir, mission_slug, and wp_id"
        )

    identity, topology_available = _resolve_transaction_entry(first, mission_slug)
    if not topology_available:
        # WP04/FR-004 (rows 7-8): same coord-vs-primary decision as the single
        # site, routed through the ONE _emit_via_non_transactional_fallback so
        # this batch function never branches coord-vs-primary in place.
        return _fallback_emit_batch(
            identity,
            requests,
            mission_slug,
            ensure_sync_daemon=ensure_sync_daemon,
        )

    with _acquire_status_transaction(
        identity,
        mission_slug,
        operation=operation or f"status transition batch {first.wp_id}",
        capability=capability,
    ) as txn:
        # One reduce of the coord write surface (NFR-004); the dependency
        # verdict is resolved in-transaction against ``txn.feature_dir``
        # (FR-013) with the declared deps from the primary WP file.
        snapshot = _emit._reduce_write_surface(txn.feature_dir)
        from_lane = str(_emit._derive_from_lane(txn.feature_dir, first.wp_id, snapshot=snapshot))
        readiness = _emit._resolve_dependency_readiness(identity.feature_dir, first.wp_id, snapshot)
        built = _prepare_batch_in_transaction(
            requests,
            first_feature_dir_raw=first_feature_dir_raw,
            feature_dir=txn.feature_dir,
            mission_slug=mission_slug,
            mission_id=identity.mission_id,
            from_lane=from_lane,
            readiness=readiness,
        )

        # The batch is one logical lifecycle operation. Persist every lane hop
        # and its annotations with one atomic file replacement so a hard crash
        # cannot strand an intermediate lane without the binding that belongs
        # to the completed start operation.
        txn.append_events([row for prepared, event, _request in built for row in _durability_unit(prepared, event)])

        for prepared, event, request in built:
            _defer_fan_out(
                txn,
                prepared,
                event,
                mission_slug=mission_slug,
                repo_root=request.repo_root,
                ensure_sync_daemon=ensure_sync_daemon,
            )

        return [event for _prepared, event, _request in built]


def _prepare_batch_in_transaction(
    requests: list[TransitionRequest],
    *,
    first_feature_dir_raw: Path,
    feature_dir: Path,
    mission_slug: str,
    mission_id: str | None,
    from_lane: str,
    readiness: DependencyReadiness,
) -> list[tuple[PreparedTransition, StatusEvent, TransitionRequest]]:
    """Run the pipeline per batch member in-lock, chaining ``from_lane`` in memory.

    ``readiness`` is the in-transaction verdict for the batch's single WP; a
    WP's verdict depends only on its dependencies' lanes, which a same-WP
    batch cannot change, so it holds for every member (see the flat
    ``emit._prepare_batch``).

    Every member must target the first member's mission folder and WP. We
    compare against the first request's folder, NOT ``identity.feature_dir``:
    in coordination mode a mission exists in two folders on disk (the normal
    checkout and the coordination worktree); the requests point at the
    coordination folder while the identity anchors on the normal one -- same
    work package, different folder. This runs INSIDE the transaction because
    the acquire just registered the coordination worktree with git, and
    ``canonicalize_feature_dir`` only keeps the coordination folder once that
    registration exists.

    Alias-collapse members persist nothing and are skipped without the
    frontmatter mirror (the batch's historical behaviour, D-4 in
    ``design-notes/WP06-convergence.md``). Any refusal raises before the
    caller appends anything.
    """
    first = requests[0]
    first_feature_dir = canonicalize_feature_dir(first_feature_dir_raw)
    built: list[tuple[PreparedTransition, StatusEvent, TransitionRequest]] = []
    started_at = now_utc()
    for request in requests:
        request_feature_dir = request.feature_dir or request.mission_dir
        request_mission_slug = request.mission_slug or request._legacy_mission_slug
        if (
            request_feature_dir is None
            or canonicalize_feature_dir(request_feature_dir) != first_feature_dir
            or request_mission_slug != mission_slug
            or request.wp_id != first.wp_id
        ):
            raise TypeError("transactional status batch only supports one feature/mission/wp")

        prepared = prepare_transition(
            request=request,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            mission_id=mission_id,
            from_lane=from_lane,
            readiness=readiness,
            at=(started_at + timedelta(microseconds=len(built))).isoformat(),
        )
        from_lane = prepared.resolved_lane
        if prepared.event is not None:
            built.append((prepared, prepared.event, request))
    return built
