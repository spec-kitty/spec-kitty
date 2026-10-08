"""The Mission write primitive: one lock, one verified rollback (#5819).

A Mission's status files (``status.events.jsonl``, ``status.json``) and the
shared planning files beside them are written by several actors in parallel.
This module is the **only** module in ``src/specify_cli`` that truncates or
unlinks a Mission's ``status.events.jsonl`` (pinned by the Mission write
discipline gate), and the single way a non-status writer takes the lock that
serialises those writes.

* :func:`mission_lock_key` is the ONE key every per-Mission lock door takes: the
  Mission directory name, or the coordination directory name ``<slug>-<mid8>`` for a
  coordination-routed Mission, so the primary and coordination directories of one
  Mission lock one file (mission-writer-followups plan D1, A1-A4).
* :func:`mission_write_lock` is :func:`~specify_cli.status.locking.feature_status_lock`
  keyed on :func:`mission_lock_key`, re-entrant per thread.
* :func:`locked_rewrite_text` is a locked read-modify-write whose transform
  never sees a stale read.
* :func:`capture_rollback_point` records the log size and ``status.json`` bytes
  and **refuses unless the calling thread holds the lock**, so a capture made
  outside the hold can never be written back.
* :func:`rollback_events_log` / :func:`rollback_status_artifacts` cut the rows a
  failed operation appended. They verify before they cut and **never extend**
  the file: the log is opened once, the same descriptor is measured and
  truncated, and a log that is shorter than at capture, vanished, holds a tail
  that is not whole JSON rows, holds rows the caller did not append, or whose
  tail is already committed at ``HEAD`` is left byte-identical and reported as
  :data:`STATUS_ROLLBACK_REFUSED`.

Design: ``kitty-specs/concurrent-mission-writers-01M4BT23/plan.md`` (D1 and
amendments A1-A3).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import BinaryIO

from kernel.atomic import atomic_write
from kernel.git import GitCommandError, blob_at, run_git
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.lanes.branch_naming import MissionLockKeyUnresolved, coordination_lock_dir_name, mission_lock_dir_name
from specify_cli.mission_metadata import load_meta_or_empty
from specify_cli.missions._read_path_resolver import literal_primary_meta
from specify_cli.status.locking import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    feature_status_lock,
    feature_status_lock_path,
    holds_status_lock,
)
from specify_cli.status.reducer import SNAPSHOT_FILENAME as _STATUS_FILENAME
from specify_cli.status.store import EVENTS_FILENAME as _EVENTS_FILENAME
from specify_cli.workspace.root_resolver import resolve_status_lock_root

__all__ = [
    "MISSION_WRITE_LOCK_TIMEOUT_SECONDS",
    "STATUS_ROLLBACK_REFUSED",
    "RollbackOutcome",
    "RollbackPoint",
    "RollbackRefusal",
    "append_refusal_to_error",
    "appended_event_ids",
    "capture_rollback_point",
    "locked_rewrite_text",
    "mission_lock_key",
    "registered_hold",
    "transaction_lock_key",
    "mission_write_lock",
    "rollback_io_failure",
    "rollback_events_log",
    "rollback_status_artifacts",
]

logger = logging.getLogger(__name__)

#: Default bound for a Mission write lock take (reuses the shared 10 s bound; plan A1).
MISSION_WRITE_LOCK_TIMEOUT_SECONDS: float = BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS

#: Error code printed with every refused rollback.
STATUS_ROLLBACK_REFUSED = "STATUS_ROLLBACK_REFUSED"

_EVENT_ID_KEY = "event_id"
_HEAD = "HEAD"
_NOT_A_REPOSITORY = b"not a git repository"


_held_state = threading.local()


def _held_keys() -> dict[tuple[str, str], str]:
    """Per-thread map ``(lock root, directory name) -> lock key`` of the Mission locks this thread holds."""
    held: dict[tuple[str, str], str] | None = getattr(_held_state, "keys", None)
    if held is None:
        held = {}
        _held_state.keys = held
    return held


def _is_coordination_routed(meta: Mapping[str, object]) -> bool:
    branch = meta.get("coordination_branch")
    return isinstance(branch, str) and bool(branch.strip())


def _optional_text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _lock_name_from_meta(meta: Mapping[str, object], primary_name: str) -> str | None:
    """The coordination lock key *meta* records, or ``None`` when the Mission is not coordination-routed."""
    if not _is_coordination_routed(meta):
        return None
    return coordination_lock_dir_name(
        _optional_text(meta.get("mission_slug")) or primary_name,
        mission_id=_optional_text(meta.get("mission_id")),
        mid8=_optional_text(meta.get("mid8")),
        coordination_branch=str(meta["coordination_branch"]).strip(),
    )


def _lock_name_for_ad_hoc_dir(feature_dir: Path) -> str:
    """A directory outside ``kitty-specs/``: its own ``meta.json`` is the only record there is."""
    return _lock_name_from_meta(load_meta_or_empty(feature_dir), feature_dir.name) or feature_dir.name


def _primary_meta(root: Path, name: str) -> Mapping[str, object]:
    """The canonical primary ``meta.json`` of *name* under *root*.

    A *root* whose ``.git`` is a directory (a repository root checkout, e.g. the ``repository_root`` an
    owned-checkout caller passes) is read directly: it cannot be a lane worktree, and that caller must not
    resolve a main repo root. Any other root goes through the read-path resolver's primary-directory leaf,
    which follows a worktree's ``.git`` pointer to the main checkout (plan A4). When the main checkout records
    nothing for *name* (an owned linked worktree whose Mission exists only in its own checkout), the
    checkout's own copy is the only record there is, so the transaction and every door read the same one.
    """
    if not _is_single_segment(name):
        return {}
    # ``load_meta_or_empty`` / ``literal_primary_meta`` widen to ``Any`` (``follow_imports=skip``); bind them.
    own: Mapping[str, object] = load_meta_or_empty(root / KITTY_SPECS_DIR / name)
    if (root / ".git").is_dir():
        return own
    canonical: Mapping[str, object] = literal_primary_meta(root, name)
    return canonical or own


def _is_single_segment(name: str) -> bool:
    return name not in {"", ".", ".."} and Path(name).name == name


def _lock_name_for_dir(feature_dir: Path, root: Path) -> str:
    """The lock key of the Mission whose primary or coordination directory is *feature_dir*.

    The primary ``meta.json`` is read through the read-path resolver's primary-directory leaf, which resolves a
    worktree's ``.git`` pointer to the main checkout, so a lane worktree's copy never decides (plan A4). A coordination
    directory is named by the key itself, so a directory whose canonical
    primary ``meta.json`` does not route through coordination is keyed on its own name.
    """
    name = feature_dir.name
    if feature_dir.parent.name != KITTY_SPECS_DIR:
        return _lock_name_for_ad_hoc_dir(feature_dir)
    return _lock_name_from_meta(_primary_meta(root, name), name) or name


def transaction_lock_key(repo_root: Path, mission_slug: str, mid8: str) -> str:
    """The Mission write-lock key ``BookkeepingTransaction`` takes: the door's routing decision, not its own.

    When the canonical primary ``meta.json`` of ``kitty-specs/<mission_slug>/`` exists the key is
    the one :func:`mission_lock_key` returns for that directory (the coordination name only for a
    coordination-routed Mission, the directory name otherwise), so the transaction and every
    door can never diverge (plan A1). When the slug names no recorded Mission, *mid8* composes the
    coordination directory name (the bare slug without one, never ``<slug>-``).
    """
    meta = _primary_meta(repo_root, mission_slug)
    if not meta:
        return mission_lock_dir_name(mission_slug, mid8=mid8)
    return _lock_name_from_meta(meta, mission_slug) or mission_slug


def mission_lock_key(feature_dir: Path, *, repo_root: Path | None = None) -> str:
    """The lock key of the Mission that owns *feature_dir*: one key for every directory of one Mission.

    Pure and Git-free. A coordination-routed Mission (``coordination_branch`` recorded in
    its canonical primary ``meta.json``, never a lane worktree's copy) is keyed on its
    coordination directory name ``<slug>-<mid8>``, whichever of its directories is passed:
    the primary directory (``060-test``) and the coordination directory
    (``060-test-01COORD0``) resolve one key, the one ``BookkeepingTransaction`` takes. Every
    other Mission is keyed on ``feature_dir.name``.

    While the calling thread holds a Mission lock, a nested call for the same Mission returns
    the held key, so a writer that changes ``coordination_branch`` or ``mid8`` inside the hold
    never takes a second lock.

    Raises:
        MissionLockKeyUnresolved: the Mission is coordination-routed but no mid8 resolves.
    """
    root = resolve_status_lock_root(feature_dir, repo_root)
    held = _held_keys().get((os.path.realpath(root), feature_dir.name))
    if held is not None:
        return held
    return _lock_name_for_dir(feature_dir, root)


@contextmanager
def registered_hold(root: Path, directory_name: str, key: str) -> Iterator[None]:
    """Record that this thread holds *key* for *directory_name* (and for a directory named *key*) until exit."""
    held = _held_keys()
    slots = [(os.path.realpath(root), directory_name), (os.path.realpath(root), key)]
    previous = {slot: held.get(slot) for slot in slots}
    for slot in slots:
        held.setdefault(slot, key)
    try:
        yield
    finally:
        for slot, before in previous.items():
            if before is None:
                held.pop(slot, None)
            else:
                held[slot] = before


_MID8_SUFFIX_LENGTH = 9  # "-" plus the eight-character mid8


def _primary_alias(root: Path, key: str) -> str | None:
    """The primary directory name whose Mission is keyed *key*, when *key* is a coordination name (plan A4).

    A hold taken through the coordination-named directory (``mission_write_lock_dir``) must also be found by a
    nested lock taken through the primary directory after the Mission's meta changed inside the hold.
    """
    if len(key) <= _MID8_SUFFIX_LENGTH or key[-_MID8_SUFFIX_LENGTH] != "-":
        return None
    candidate = key[:-_MID8_SUFFIX_LENGTH]
    return candidate if _lock_name_from_meta(_primary_meta(root, candidate), candidate) == key else None


@contextmanager
def mission_write_lock(
    feature_dir: Path,
    *,
    repo_root: Path | None = None,
    timeout: float = MISSION_WRITE_LOCK_TIMEOUT_SECONDS,
    fallback_to_dir_name: bool = False,
) -> Iterator[Path]:
    """Hold the Mission write lock for *feature_dir*; re-entrant per thread.

    The lock is keyed on :func:`mission_lock_key` under the git common dir of the
    canonical repo root, so every writer of the same Mission converges on one lock file,
    whichever of the Mission's directories it holds. The key is resolved before the lock
    is entered. A timeout raises
    :class:`~specify_cli.status.locking.FeatureStatusLockTimeoutError`.

    *fallback_to_dir_name* is for the migration/upgrade writers that repair legacy metadata a key
    cannot be read from: a coordination-routed Mission that records no resolvable mid8 is locked
    on ``feature_dir.name`` instead of raising
    :class:`~specify_cli.lanes.branch_naming.MissionLockKeyUnresolved`. Every other caller keeps
    the fail-closed default. The complete list of callers that set it:

    * ``migration/backfill_identity.py``: ``backfill_mission`` and ``backfill_mission_ids``
    * ``migration/backfill_topology.py``: ``_stamp_topology`` writer, ``restamp_single_branch_with_code_lanes``
    * ``migration/backfill_mission_type.py``: ``backfill_mission_mission_type``
    * ``migration/mission_state.py``: ``_repair_meta_phase``
    * ``migration/runtime_state_cutover.py``: ``_flip_phase``
    * ``upgrade/feature_meta.py``: ``write_feature_meta``
    * ``upgrade/migrations/m_0_13_8_target_branch.py``: ``TargetBranchMigration.apply``
    """
    root = resolve_status_lock_root(feature_dir, repo_root)
    try:
        key = mission_lock_key(feature_dir, repo_root=root)
    except MissionLockKeyUnresolved:
        if not fallback_to_dir_name:
            raise
        key = feature_dir.name
    alias = _primary_alias(root, key) if feature_dir.name == key else None
    with (
        feature_status_lock(root, key, timeout=timeout) as held,
        registered_hold(root, feature_dir.name, key),
        registered_hold(root, alias or feature_dir.name, key),
    ):
        yield held


def locked_rewrite_text(
    path: Path,
    transform: Callable[[str | None], str],
    *,
    feature_dir: Path,
    repo_root: Path | None = None,
    timeout: float = MISSION_WRITE_LOCK_TIMEOUT_SECONDS,
    encoding: str = "utf-8",
) -> str:
    """Rewrite *path* as ``transform(current_text)`` under the Mission write lock.

    ``current_text`` is ``None`` when the file is missing. The file is replaced
    atomically and only when the text changed. Returns the resulting text.
    """
    with mission_write_lock(feature_dir, repo_root=repo_root, timeout=timeout):
        current = path.read_text(encoding=encoding) if path.exists() else None
        updated = transform(current)
        if updated != current:
            atomic_write(path, updated.encode(encoding))
        return updated


@dataclass(frozen=True)
class RollbackPoint:
    """Pre-operation state of a Mission's status files, captured under the write lock."""

    events_path: Path
    status_path: Path
    pre_event_size: int
    pre_status_bytes: bytes | None
    events_existed: bool

    @classmethod
    def measured_under_held_lock(cls, *, events_path: Path, status_path: Path, pre_event_size: int, events_existed: bool) -> RollbackPoint:
        """A point from measurements the caller already took while holding the Mission write lock.

        For a caller that measured the log before this call (``BookkeepingTransaction``
        measures inside its own lock hold): it does not re-read the files and does not
        check the lock, so the CALLER must hold it, and must also hold it for the
        rollback. ``status.json`` bytes are not captured (``None``): the caller restores
        ``status.json`` from its own snapshot. Prefer :func:`capture_rollback_point`.
        """
        return cls(events_path=events_path, status_path=status_path, pre_event_size=pre_event_size, pre_status_bytes=None, events_existed=events_existed)


def _holds_mission_lock(feature_dir: Path, repo_root: Path | None) -> bool:
    root = resolve_status_lock_root(feature_dir, repo_root)
    return holds_status_lock(feature_status_lock_path(root, mission_lock_key(feature_dir, repo_root=root)))


def capture_rollback_point(feature_dir: Path, *, repo_root: Path | None = None) -> RollbackPoint:
    """Capture the Mission's log size and ``status.json`` bytes.

    Raises:
        RuntimeError: the calling thread does not hold the Mission write lock for
            *feature_dir*. A capture taken outside the hold could be written back
            over another writer's rows.
    """
    if not _holds_mission_lock(feature_dir, repo_root):
        raise RuntimeError(
            f"capture_rollback_point({feature_dir.name}) requires the Mission write lock; wrap the capture, the write and the rollback in mission_write_lock()"
        )
    events_path = feature_dir / _EVENTS_FILENAME
    status_path = feature_dir / _STATUS_FILENAME
    events_existed = events_path.exists()
    return RollbackPoint(
        events_path=events_path,
        status_path=status_path,
        pre_event_size=events_path.stat().st_size if events_existed else 0,
        pre_status_bytes=status_path.read_bytes() if status_path.exists() else None,
        events_existed=events_existed,
    )


def appended_event_ids(point: RollbackPoint) -> list[str] | None:
    """Event ids of the rows appended after *point*, or ``None`` when the tail is not whole JSON rows.

    Read it while the Mission write lock is held to learn which rows are this
    operation's own, then hand it to the rollback as ``expected_event_ids`` so a
    rollback made later, under a re-acquired lock, still refuses a foreign row.
    """
    try:
        with point.events_path.open("rb") as fh:
            fh.seek(point.pre_event_size)
            return _parse_tail_event_ids(fh.read())
    except FileNotFoundError:
        return []


class RollbackRefusal(StrEnum):
    """Why a rollback left the Mission files untouched."""

    LOG_VANISHED = "the event log existed at capture and is gone"
    LOG_SHRANK = "the event log is shorter than at capture"
    TAIL_UNPARSEABLE = "the rows after the capture point are not whole JSON event rows"
    TAIL_NOT_OWNED = "the rows after the capture point are not the rows this operation appended"
    TAIL_ALREADY_COMMITTED = "the rows after the capture point are already committed at HEAD"
    HEAD_UNREADABLE = "HEAD could not be read to prove the rows are uncommitted"
    IO_ERROR = "the rollback hit an I/O error before it could finish"


@dataclass(frozen=True)
class RollbackOutcome:
    """Result of a rollback attempt; a refusal left every file byte-identical."""

    rolled_back: bool
    refusal: RollbackRefusal | None
    events_path: Path

    def message(self) -> str:
        """Operator text for a refusal (empty when the rollback succeeded)."""
        if self.refusal is None:
            return ""
        state = "may be partly rewritten" if self.refusal is RollbackRefusal.IO_ERROR else "left unchanged"
        return f"{STATUS_ROLLBACK_REFUSED}: {self.refusal.value}; {self.events_path} {state}. Inspect with: git diff HEAD -- {self.events_path}"


def _refuse(events_path: Path, refusal: RollbackRefusal) -> RollbackOutcome:
    outcome = RollbackOutcome(rolled_back=False, refusal=refusal, events_path=events_path)
    logger.warning("%s", outcome.message())
    return outcome


def append_refusal_to_error(exc: BaseException, refusal: str) -> None:
    """Append the refused-rollback text *refusal* to *exc* so callers that print the error show it (once).

    Rewrites the first string argument as ``"<message> [<refusal>]"``; an exception
    without one carries the text as a note instead.
    """
    if not refusal or refusal in str(exc):
        return
    if exc.args and isinstance(exc.args[0], str):
        exc.args = (f"{exc.args[0]} [{refusal}]", *exc.args[1:])
    else:
        exc.add_note(refusal)


def rollback_io_failure(point: RollbackPoint, exc: OSError) -> RollbackOutcome:
    """The refusal outcome for a rollback that raised *exc*, so the caller prints a coded message instead of a traceback.

    The files may be partly rewritten (the failure came from the filesystem), so the
    message tells the operator to inspect them.
    """
    logger.warning("rollback of %s failed: %s", point.events_path, exc)
    return _refuse(point.events_path, RollbackRefusal.IO_ERROR)


def _done(events_path: Path) -> RollbackOutcome:
    return RollbackOutcome(rolled_back=True, refusal=None, events_path=events_path)


def _parse_tail_event_ids(tail: bytes) -> list[str] | None:
    """Event ids of the whole JSON rows in *tail*, or ``None`` when it is not whole rows.

    Blank lines are legal (``append_raw_rows_atomic`` inserts a leading newline when
    the log lacked a trailing one); a last row without its newline is torn.
    """
    if tail and not tail.endswith(b"\n"):
        return None
    ids: list[str] = []
    for raw in tail.split(b"\n"):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except ValueError:
            return None
        event_id = row.get(_EVENT_ID_KEY) if isinstance(row, dict) else None
        if not isinstance(event_id, str):
            return None
        ids.append(event_id)
    return ids


def _head_is_unborn(root: Path) -> bool:
    """Whether HEAD names a branch that has no commit yet (a corrupt ref is not unborn: it stays unreadable)."""
    branch = run_git(root, "symbolic-ref", "--quiet", _HEAD, check=False)
    if branch.returncode != 0:
        return False  # detached HEAD (or an error): let the blob read decide, fail closed
    ref = branch.stdout.decode("utf-8", "replace").strip()
    return run_git(root, "show-ref", "--verify", "--quiet", ref, check=False).returncode == 1


def _committed_event_ids(events_path: Path) -> frozenset[str]:
    """Event ids of the log committed at ``HEAD`` of the checkout holding *events_path*.

    Empty when the path is not in a git checkout, HEAD is unborn, or HEAD does not
    track the log.

    Raises:
        GitCommandError: git failed in a way that leaves the committed log unknown.
        ValueError: the committed log holds a line that is not JSON (the committed ids are unknown).
    """
    cwd = events_path.parent
    # LC_ALL=C pins git's diagnostics to English so the non-repository probe below is locale-independent.
    top = run_git(cwd, "rev-parse", "--show-toplevel", env={**os.environ, "LC_ALL": "C"}, check=False)
    if top.returncode != 0:
        if _NOT_A_REPOSITORY in top.stderr:
            return frozenset()
        raise GitCommandError(argv=("rev-parse", "--show-toplevel"), cwd=cwd, returncode=top.returncode, stderr=top.stderr.decode("utf-8", "replace"))
    root = Path(top.stdout.decode("utf-8", "replace").strip())
    if _head_is_unborn(root):
        return frozenset()
    relative = events_path.resolve().relative_to(root.resolve()).as_posix()
    committed = blob_at(root, _HEAD, relative)
    if committed is None:
        return frozenset()
    ids: set[str] = set()
    for raw in committed.split(b"\n"):
        row = json.loads(raw) if raw.strip() else None  # a malformed committed line raises ValueError: the caller fails closed
        if isinstance(row, dict) and isinstance(row.get(_EVENT_ID_KEY), str):
            ids.add(row[_EVENT_ID_KEY])
    return frozenset(ids)


def _verify_tail(
    point: RollbackPoint,
    fh: BinaryIO,
    expected_event_ids: Sequence[str] | None,
) -> RollbackRefusal | None:
    """Return why the tail after ``point.pre_event_size`` may not be cut, or ``None`` when it may.

    Reads from *fh*, the descriptor that is truncated afterwards.
    """
    size = os.fstat(fh.fileno()).st_size
    if size < point.pre_event_size:
        return RollbackRefusal.LOG_SHRANK
    fh.seek(point.pre_event_size)
    tail_ids = _parse_tail_event_ids(fh.read(size - point.pre_event_size))
    if tail_ids is None:
        return RollbackRefusal.TAIL_UNPARSEABLE
    if expected_event_ids is not None and Counter(tail_ids) != Counter(expected_event_ids):
        return RollbackRefusal.TAIL_NOT_OWNED
    if not tail_ids:
        return None
    try:
        committed = _committed_event_ids(point.events_path)
    except (GitCommandError, ValueError, OSError):
        return RollbackRefusal.HEAD_UNREADABLE
    if committed.intersection(tail_ids):
        return RollbackRefusal.TAIL_ALREADY_COMMITTED
    return None


def _cut_tail(point: RollbackPoint, fh: BinaryIO) -> None:
    """Cut the log back to the capture point (never extends); unlink a log that did not exist at capture."""
    if not point.events_existed:
        fh.close()
        point.events_path.unlink(missing_ok=True)
        return
    if os.fstat(fh.fileno()).st_size > point.pre_event_size:
        os.ftruncate(fh.fileno(), point.pre_event_size)
        os.fsync(fh.fileno())


def _rollback_events_locked(
    point: RollbackPoint,
    expected_event_ids: Sequence[str] | None,
) -> RollbackOutcome:
    try:
        fh = point.events_path.open("r+b")
    except FileNotFoundError:
        if point.events_existed:
            return _refuse(point.events_path, RollbackRefusal.LOG_VANISHED)
        return _done(point.events_path)
    with fh:
        refusal = _verify_tail(point, fh, expected_event_ids)
        if refusal is not None:
            return _refuse(point.events_path, refusal)
        _cut_tail(point, fh)
    return _done(point.events_path)


def rollback_events_log(
    point: RollbackPoint,
    *,
    expected_event_ids: Sequence[str] | None = None,
    repo_root: Path | None = None,
) -> RollbackOutcome:
    """Cut the rows appended after *point*, or refuse and leave the log byte-identical.

    Runs inside the Mission write lock (re-entrant). *expected_event_ids*, when the
    caller knows the ids it appended, must equal the tail's ids as a multiset.
    """
    with mission_write_lock(point.events_path.parent, repo_root=repo_root):
        return _rollback_events_locked(point, expected_event_ids)


def _restore_status_bytes(point: RollbackPoint) -> None:
    if point.pre_status_bytes is None:
        point.status_path.unlink(missing_ok=True)
    else:
        atomic_write(point.status_path, point.pre_status_bytes, mkdir=True)


def rollback_status_artifacts(
    point: RollbackPoint,
    *,
    expected_event_ids: Sequence[str] | None = None,
    repo_root: Path | None = None,
) -> RollbackOutcome:
    """Roll the log back, then restore ``status.json``, only when the log half succeeded."""
    with mission_write_lock(point.events_path.parent, repo_root=repo_root):
        outcome = _rollback_events_locked(point, expected_event_ids)
        if outcome.rolled_back:
            _restore_status_bytes(point)
        return outcome
