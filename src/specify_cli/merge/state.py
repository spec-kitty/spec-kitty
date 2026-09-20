"""Merge state persistence for resume capability.

Implements FR-013: per-mission merge state at the canonical runtime location
.kittify/runtime/merge/<mission_id>/state.json with lock support to prevent
concurrent merge operations.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from kernel.clock import now_utc_iso
from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded
from specify_cli.merge.workspace import get_merge_runtime_dir

__all__ = [
    "MergeAmbiguousStateError",
    "MergeLockError",
    "MergeStateReadError",
    "MergeState",
    "save_state",
    "load_state",
    "clear_state",
    "has_active_merge",
    "iter_pending_coord_reconcile_markers",
    "get_state_path",
    "acquire_merge_lock",
    "release_merge_lock",
    "is_merge_locked",
    "detect_git_merge_state",
    "abort_git_merge",
    "needs_number_assignment",
]

_STATE_FILE = "state.json"
_LOCK_FILE = "lock"


class MergeAmbiguousStateError(Exception):
    """Raised when multiple active merge states exist and no mission_id was given.

    Pass ``--mission <slug>`` (or ``--mission-id <id>``) to disambiguate.
    """

    def __init__(self, mission_ids: list[str]) -> None:
        self.mission_ids = mission_ids
        ids_formatted = "\n  ".join(mission_ids)
        super().__init__(
            f"Multiple active merge states found — pass --mission to disambiguate:\n  {ids_formatted}"
        )


class MergeStateReadError(GuardedReadError, RuntimeError):
    """Raised when a persisted merge ``state.json`` exists but cannot be decoded.

    Mission cli-error-surface-seam WP07/#4746: pre-fix, ``_load_state_file``
    silently collapsed ``(json.JSONDecodeError, TypeError, KeyError)`` into a
    ``None`` return — indistinguishable from "no merge in progress". That is
    a fail-open bug, not a benign presentation gap: a corrupt resumable-merge
    state silently masquerading as "nothing to resume" can lose in-progress
    merge bookkeeping. Never raised for a genuinely absent state file (D5) —
    that branch stays outside the guard.
    """


class MergeLockError(Exception):
    """Raised when a merge lock is already held for a mission."""

    def __init__(self, mission_id: str, lock_path: Path) -> None:
        self.mission_id = mission_id
        self.lock_path = lock_path
        super().__init__(
            f"Merge lock already held for '{mission_id}' (lock file: {lock_path}). "
            "Another merge operation may be running. "
            "If not, remove the lock file manually: spec-kitty merge --abort"
        )


@dataclass
class MergeState:
    """Persisted state for resumable merge operations."""

    mission_id: str  # Per-mission scoping (e.g. "057-feature-name")
    mission_slug: str  # Display alias for the feature
    target_branch: str
    wp_order: list[str]
    # #2711 FR-007: ADVISORY HINT ONLY. The authority for resume progress is the
    # durable event log (the committed coordination ref); this list is confirmed
    # against it in ``done_bookkeeping._reconcile_completed_wps_for_resume`` and a
    # stale entry (no durable ``done``) is dropped so the resume re-emits.
    completed_wps: list[str] = field(default_factory=list)
    current_wp: str | None = None
    has_pending_conflicts: bool = False
    strategy: str = "merge"  # "merge", "squash", or "rebase"
    workspace_path: str | None = None  # Absolute path to merge workspace
    started_at: str = field(default_factory=now_utc_iso)
    updated_at: str = field(default_factory=now_utc_iso)
    mission_number_baked: bool = False  # WP04 — set True once mission_number is committed
    push_requested: bool = False  # WP02 — True when --push was passed at merge start
    # #2786 / #2367-B FR-004: durable coord-strand reconcile marker. A plain dict
    # (NOT a nested dataclass) because ``from_dict`` rehydrates JSON objects as
    # dicts and drops unknown keys — so pre-existing state files that predate this
    # field simply rehydrate to ``None`` with no migration. Keys (see data-model):
    # ``coord_ref``, ``captured_sha``, ``coord_worktree``, ``stranded_wp_ids``,
    # ``revert_error``, ``detected_at``.
    pending_coord_reconcile: dict[str, Any] | None = None
    # terminus-safety-invariant-01M2XFT7 FOLD-F2 (T021, FR-012): mirrors the
    # executor's transient ``_MergeRunState.skip_lanes`` (merge/executor.py)
    # so a genuinely-lanes.json-absent direct-on-target mission's
    # ``--skip-lanes``/``--no-lanes`` choice survives a ``merge --resume``.
    # Pre-fix a resume re-derives ``skip_lanes=False`` from CLI defaults and
    # ``require_lanes_json`` raises ``MissingLanesError`` mid-resume, which
    # reads as a regression on a mission that was never going to have a lanes
    # manifest. Round-trips through ``from_dict``'s known-fields filter
    # exactly like ``mission_number_baked`` — back-compat for state files
    # written before this field existed (absent key -> default ``False``).
    skip_lanes: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MergeState:
        """Create from dict (loaded JSON).

        Backward-compatible: older state files that predate the
        ``mission_number_baked`` field (added in WP04) load with the safe
        default of ``False`` so that resume correctly re-enters the
        idempotency check rather than blindly skipping it.
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

    @property
    def remaining_wps(self) -> list[str]:
        """WPs not yet merged."""
        completed_set = set(self.completed_wps)
        return [wp for wp in self.wp_order if wp not in completed_set]

    @property
    def progress_percent(self) -> float:
        """Completion percentage."""
        if not self.wp_order:
            return 0.0
        return len(self.completed_wps) / len(self.wp_order) * 100

    def mark_wp_complete(self, wp_id: str) -> None:
        """Mark a WP as successfully merged."""
        if wp_id not in self.completed_wps:
            self.completed_wps.append(wp_id)
        self.current_wp = None
        self.has_pending_conflicts = False
        self.updated_at = now_utc_iso()

    def set_current_wp(self, wp_id: str) -> None:
        """Set the currently-merging WP."""
        self.current_wp = wp_id
        self.updated_at = now_utc_iso()

    def set_pending_conflicts(self, has_conflicts: bool = True) -> None:
        """Mark that there are pending conflicts to resolve."""
        self.has_pending_conflicts = has_conflicts
        self.updated_at = now_utc_iso()


def get_state_path(repo_root: Path, mission_id: str | None = None) -> Path:
    """Return the path to the merge state file.

    When mission_id is provided (new canonical location):
        .kittify/runtime/merge/<mission_id>/state.json

    When mission_id is None (legacy compatibility, deprecated):
        .kittify/merge-state.json
    """
    if mission_id is not None:
        return get_merge_runtime_dir(mission_id, repo_root) / _STATE_FILE
    # Legacy path — only used by the CLI's --abort/--resume handlers
    return repo_root / ".kittify" / "merge-state.json"


def save_state(state: MergeState, repo_root: Path) -> None:
    """Persist merge state to .kittify/runtime/merge/<mission_id>/state.json.

    Args:
        state: MergeState to persist (must have mission_id set)
        repo_root: Repository root path
    """
    state_path = get_state_path(repo_root, state.mission_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = now_utc_iso()

    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)


def load_state(repo_root: Path, mission_id: str | None = None) -> MergeState | None:
    """Load merge state from the canonical runtime location.

    Args:
        repo_root: Repository root path
        mission_id: If given, load from the per-mission path; otherwise scan
                    for active state files under .kittify/runtime/merge/.
                    When exactly one active state is found it is returned.
                    When multiple active states are found,
                    :class:`MergeAmbiguousStateError` is raised — callers must
                    pass ``mission_id`` to disambiguate.

    Returns:
        MergeState if found and valid, None otherwise

    Raises:
        MergeAmbiguousStateError: When multiple active merge states exist and
            no ``mission_id`` was provided.
        MergeStateReadError: When ``mission_id`` is given and that mission's
            ``state.json`` exists but cannot be decoded (fail-closed; never
            raised for a missing file). The no-``mission_id`` scan below
            deliberately does NOT raise this — see its own note.
    """
    if mission_id is not None:
        return _load_state_file(get_state_path(repo_root, mission_id))

    # Scan for all active state files
    runtime_merge_dir = repo_root / ".kittify" / "runtime" / "merge"
    if not runtime_merge_dir.exists():
        return None

    active_states: list[MergeState] = []
    for candidate in sorted(runtime_merge_dir.iterdir()):
        state_file = candidate / _STATE_FILE
        # A corrupt state file for ONE mission must not block resolving an
        # active merge for another (this scan enumerates every mission's
        # runtime dir, unlike the single-mission path above) -- skip it
        # rather than propagating MergeStateReadError. The caller passing an
        # explicit mission_id (the fail-closed path) still sees the error.
        try:
            state = _load_state_file(state_file)
        except MergeStateReadError:
            continue
        if state is not None:
            active_states.append(state)

    if len(active_states) == 0:
        return None
    if len(active_states) == 1:
        return active_states[0]

    # Multiple active merge states: require caller to disambiguate
    raise MergeAmbiguousStateError([s.mission_id for s in active_states])


def _parse_merge_state(content: bytes | str) -> MergeState:
    """Decode already-read *content* into a :class:`MergeState`."""
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    data = json.loads(text)
    return MergeState.from_dict(data)


def _load_state_file(state_path: Path) -> MergeState | None:
    """Load and parse a single state JSON file.

    Returns:
        ``None`` when *state_path* does not exist. Never ``None`` for a
        present-but-corrupt file (D5) — that raises :class:`MergeStateReadError`.

    Raises:
        MergeStateReadError: when *state_path* exists but cannot be decoded
            (non-UTF-8 bytes, malformed JSON, or a schema mismatch).
    """
    if not state_path.exists():
        return None
    return read_guarded(
        state_path,
        _parse_merge_state,
        errors=(json.JSONDecodeError, TypeError, KeyError),
        error_cls=MergeStateReadError,
    )


def clear_state(repo_root: Path, mission_id: str | None = None) -> bool:
    """Remove merge state file.

    Args:
        repo_root: Repository root path
        mission_id: If given, clear only that mission's state.

    Returns:
        True if a file was removed, False if it didn't exist
    """
    if mission_id is not None:
        state_path = get_state_path(repo_root, mission_id)
        if state_path.exists():
            state_path.unlink()
            return True
        return False

    # Clear the first active state found
    runtime_merge_dir = repo_root / ".kittify" / "runtime" / "merge"
    if runtime_merge_dir.exists():
        for candidate in sorted(runtime_merge_dir.iterdir()):
            state_file = candidate / _STATE_FILE
            if state_file.exists():
                state_file.unlink()
                return True

    return False


def has_active_merge(repo_root: Path, mission_id: str | None = None) -> bool:
    """Check if there is an active merge state with remaining WPs.

    Args:
        repo_root: Repository root path
        mission_id: If given, check only that mission's state.
    """
    state = load_state(repo_root, mission_id)
    if state is None:
        return False
    return len(state.remaining_wps) > 0


def iter_pending_coord_reconcile_markers(repo_root: Path) -> Iterable[MergeState]:
    """Yield every persisted merge state that carries a ``pending_coord_reconcile`` marker.

    The coordination doctor (#2786 / #2367-B WP04) must enumerate stranded-coord
    markers across ALL active missions, but :func:`load_state` with
    ``mission_id=None`` **raises** :class:`MergeAmbiguousStateError` as soon as two
    or more active states exist — so it cannot be used to enumerate. This iterator
    is the enumeration seam: ``state.py`` owns the runtime-path shape
    (``.kittify/runtime/merge/*/state.json``), so the doctor consumes this rather
    than re-implementing the scan (which would be a second path authority /
    DIR-044 breach).

    States whose ``pending_coord_reconcile`` is ``None`` (the common, coherent
    case) and unparseable state files are skipped. Yields in deterministic
    ``mission_id``-directory sort order.

    Args:
        repo_root: Repository root path.

    Yields:
        Each :class:`MergeState` carrying a non-``None`` ``pending_coord_reconcile``.
    """
    runtime_merge_dir = repo_root / ".kittify" / "runtime" / "merge"
    if not runtime_merge_dir.exists():
        return
    for candidate in sorted(runtime_merge_dir.iterdir()):
        try:
            state = _load_state_file(candidate / _STATE_FILE)
        except MergeStateReadError:
            # Documented "unparseable state files are skipped" contract
            # (docstring above) -- a corrupt state for one mission must not
            # abort the safety-net scan across every other mission.
            continue
        if state is not None and state.pending_coord_reconcile is not None:
            yield state


# ---------------------------------------------------------------------------
# Lock management
# ---------------------------------------------------------------------------

def acquire_merge_lock(mission_id: str, repo_root: Path) -> bool:
    """Create a lock file to prevent concurrent merge operations.

    Uses an atomic exclusive-create (``open(path, 'x')``) to avoid the
    TOCTOU race that exists() + write_text() is vulnerable to.

    Args:
        mission_id: Mission/feature slug identifier
        repo_root: Repository root path

    Returns:
        True if the lock was acquired, False if already locked

    Raises:
        MergeLockError: Never raised here (returns False instead), but callers
            that want a hard failure can raise it themselves on False return.
    """
    lock_path = get_merge_runtime_dir(mission_id, repo_root) / _LOCK_FILE
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Atomic exclusive create — fails immediately if lock already exists.
        with lock_path.open("x", encoding="utf-8") as fh:
            fh.write(now_utc_iso())
        return True
    except FileExistsError:
        return False


def release_merge_lock(mission_id: str, repo_root: Path) -> None:
    """Remove the merge lock file.

    Args:
        mission_id: Mission/feature slug identifier
        repo_root: Repository root path
    """
    lock_path = get_merge_runtime_dir(mission_id, repo_root) / _LOCK_FILE
    if lock_path.exists():
        lock_path.unlink()


def is_merge_locked(mission_id: str, repo_root: Path) -> bool:
    """Check whether a merge lock file exists for the given mission.

    Args:
        mission_id: Mission/feature slug identifier
        repo_root: Repository root path
    """
    lock_path = get_merge_runtime_dir(mission_id, repo_root) / _LOCK_FILE
    return lock_path.exists()


# ---------------------------------------------------------------------------
# Git merge state helpers (unchanged from original)
# ---------------------------------------------------------------------------

def needs_number_assignment(feature_dir: Path) -> bool:
    """Return True if the mission's ``meta.json`` lacks an integer ``mission_number``.

    The merge-time number-assignment gate (FR-044, WP10/T051): a mission needs
    a number assigned when its ``meta.json`` carries ``mission_number: null``.
    Any non-null value -- including legacy string forms like ``"042"`` -- is
    treated as already assigned because the mission_metadata loader coerces
    string forms to ``int`` at read time.

    Args:
        feature_dir: Path to the mission's ``kitty-specs/<slug>/`` directory.

    Returns:
        ``True`` if ``mission_number`` resolves to ``None``; ``False`` if it
        resolves to any integer (including ``0``).  Returns ``False`` if the
        ``meta.json`` file is missing -- there is nothing to assign into.
    """
    # Imported lazily to avoid a circular import (mission_metadata may import
    # nothing in this module today, but the merge package wires into many
    # higher-level subsystems and we want to keep the import surface tight).
    from specify_cli.mission_metadata import resolve_mission_identity

    if not (feature_dir / "meta.json").exists():
        return False

    identity = resolve_mission_identity(feature_dir)
    return identity.mission_number is None


def detect_git_merge_state(repo_root: Path) -> bool:
    """Check if git has an active merge in progress via MERGE_HEAD."""
    result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def abort_git_merge(repo_root: Path) -> bool:
    """Abort an in-progress git merge at *repo_root*.

    Despite the parameter name (kept for backward compatibility with existing
    call sites and test monkeypatches), this is a generic "abort whatever git
    merge is in progress at this working tree path" primitive -- it does NOT
    know or care whether the path is the caller's repository root or a
    scoped worktree.

    #4754: callers MUST NOT invoke this with the operator's own repository
    root unless they have already confirmed active spec-kitty merge state
    exists for that root. The merge pipeline runs ``git merge`` exclusively
    inside spec-kitty-owned worktrees (an ephemeral lane-consolidation tmp worktree
    and the persisted per-mission merge workspace at
    ``.kittify/runtime/merge/<mission_id>/workspace/``) -- never directly
    against a repository's primary checkout. A ``MERGE_HEAD`` found in an
    operator's primary checkout is always THEIR OWN in-progress merge and
    must never be touched. See ``cli.commands.merge._dispatch_abort`` for the
    gated, workspace-scoped call site.

    Returns:
        True if merge was aborted, False if no merge was in progress
    """
    if not detect_git_merge_state(repo_root):
        return False

    subprocess.run(
        ["git", "merge", "--abort"],
        cwd=str(repo_root),
        check=False,
    )
    return True
