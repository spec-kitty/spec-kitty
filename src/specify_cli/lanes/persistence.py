"""Read and write lanes.json for a feature directory.

The lanes.json file lives at kitty-specs/{mission_slug}/lanes.json
and is the sole persistence location for lane assignments.

Read is fail-closed: a corrupt or malformed lanes.json raises
CorruptLanesError rather than silently falling back to no-lanes mode.
Write uses atomic rename to prevent truncated files.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path, PurePath, PureWindowsPath

from charter.hasher import hash_content
from kernel.errors import GuardedReadError
from kernel.git_topology import GitTopologyError, NotAGitRepositoryError, git_common_dir, git_toplevel
from kernel.locks import SyncMachineFileLock, machine_file_lock
from specify_cli.lanes.models import LanesManifest

LANES_FILENAME = "lanes.json"


def lanes_json_lock(feature_dir: Path) -> SyncMachineFileLock:
    """Return the cross-worktree lock shared by canonical lanes writers."""
    lanes_path = resolve_lanes_dir(feature_dir).resolve()
    try:
        common_dir = git_common_dir(feature_dir)
        worktree_root = git_toplevel(feature_dir)
    except NotAGitRepositoryError:
        lock_path = _non_git_lanes_lock_path(lanes_path)
    except GitTopologyError as exc:
        raise RuntimeError(f"Cannot safely lock lanes.json for {feature_dir}: {exc}") from exc
    else:
        try:
            relative_path = lanes_path.relative_to(worktree_root)
        except ValueError as exc:
            raise RuntimeError(f"lanes.json is outside its Git worktree: {lanes_path}") from exc
        lock_path = common_dir / "spec-kitty-lanes-locks" / relative_path.with_name(f"{relative_path.name}.lock")

    return machine_file_lock(lock_path, blocking=True, timeout_s=None, reentrant=True)


def _non_git_lanes_lock_path(lanes_path: PurePath) -> Path:
    """Map a canonical lanes path to a stable filename below the temp root."""
    path_key = lanes_path.as_posix()
    if isinstance(lanes_path, PureWindowsPath):
        path_key = path_key.casefold()
    path_identity = json.dumps(path_key, ensure_ascii=True, separators=(",", ":"))
    digest = hash_content(path_identity).removeprefix("sha256:")
    return Path(tempfile.gettempdir()) / "spec-kitty-lanes-locks" / f"{digest}.lock"


def resolve_lanes_dir(feature_dir: Path) -> Path:
    """Return the canonical ``lanes.json`` path for a feature directory.

    Single pure seam (#1993): the one place that knows how the lanes file
    path is composed from a feature dir. Pure path composition — no I/O, no
    topology semantics. Route every ``feature_dir / lanes.json`` derivation
    through here so the join is defined exactly once.
    """
    return feature_dir / LANES_FILENAME


class CorruptLanesError(GuardedReadError):
    """Raised when lanes.json exists but cannot be parsed.

    Re-parented together with :class:`MissingLanesError` (mission
    cli-error-surface-seam) — the caller census treats them as one coupled
    unit since many callers tuple-catch both.
    """


class MissingLanesError(GuardedReadError):
    """Raised when lanes.json is required but missing.

    Re-parented together with :class:`CorruptLanesError` (mission
    cli-error-surface-seam) — see that class's docstring.
    """


def write_lanes_json(feature_dir: Path, manifest: LanesManifest) -> Path:
    """Write lanes.json atomically to the feature directory.

    Uses write-to-temp + rename to prevent truncated files on crash.

    Args:
        feature_dir: Path to kitty-specs/{mission_slug}/.
        manifest: The LanesManifest to persist.

    Returns:
        Path to the written lanes.json file.
    """
    lanes_path = resolve_lanes_dir(feature_dir)
    content = json.dumps(manifest.to_dict(), indent=2, sort_keys=False) + "\n"

    with lanes_json_lock(feature_dir):
        fd, tmp_path = tempfile.mkstemp(dir=str(feature_dir), prefix=".lanes-", suffix=".tmp")
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            os.replace(tmp_path, str(lanes_path))
        except BaseException:
            os.close(fd) if not os.get_inheritable(fd) else None  # noqa: E501
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    return lanes_path


def write_lanes_json_if_bytes_match(feature_dir: Path, expected: bytes, replacement: bytes) -> bool:
    """Atomically replace lanes.json only while its complete bytes still match."""
    lanes_path = resolve_lanes_dir(feature_dir)
    with lanes_json_lock(feature_dir):
        if lanes_path.read_bytes() != expected:
            return False

        fd, tmp_path = tempfile.mkstemp(dir=str(feature_dir), prefix=".lanes-", suffix=".tmp")
        try:
            os.write(fd, replacement)
            os.close(fd)
            if lanes_path.read_bytes() != expected:
                os.unlink(tmp_path)
                return False
            os.replace(tmp_path, str(lanes_path))
        except BaseException:
            os.close(fd) if not os.get_inheritable(fd) else None  # noqa: E501
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    return True


def read_lanes_json(feature_dir: Path) -> LanesManifest | None:
    """Read lanes.json from the feature directory.

    Returns None only when the file does not exist (no lanes computed).
    Raises CorruptLanesError if the file exists but is malformed — this
    prevents silent fallback to legacy no-lanes mode.

    Args:
        feature_dir: Path to kitty-specs/{mission_slug}/.

    Returns:
        A LanesManifest if the file exists, None if absent.

    Raises:
        CorruptLanesError: If the file exists but cannot be parsed.
    """
    lanes_path = resolve_lanes_dir(feature_dir)
    if not lanes_path.exists():
        return None
    try:
        data = json.loads(lanes_path.read_text(encoding="utf-8"))
        return LanesManifest.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise CorruptLanesError(f"lanes.json at {lanes_path} is corrupt or malformed: {exc}") from exc


def require_lanes_json(feature_dir: Path) -> LanesManifest:
    """Read lanes.json or raise a deterministic missing-manifest error."""
    manifest = read_lanes_json(feature_dir)
    if manifest is None:
        raise MissingLanesError(
            f"lanes.json is required for {feature_dir}. "
            "Run 'spec-kitty agent mission finalize-tasks' to compute execution "
            "lanes, or if the mission has already begun executing, run "
            "'spec-kitty doctor mission-state --fix --mission <slug>' to rebuild "
            "lanes.json from the event log."
        )
    return manifest


def is_execution_wedged(*, execution_has_begun: bool, lanes_present: bool) -> bool:
    """The #4758 wedge predicate: execution has begun but lanes.json is absent.

    A mission in this state can neither safely re-finalize (there is no
    recorded ``planning_commit_sha`` to preserve, and blindly recapturing
    the branch tip would clobber the planning provenance an already-claimed
    lane worktree may carry a merge-base against, #3311) nor keep executing
    (``lanes.json`` resolves worktrees, and callers like ``move-task``
    refuse to advance a WP without it). It is only repairable by rebuilding
    ``lanes.json`` from the event log.

    Single named authority (DIRECTIVE_044 / C-001) shared by:

    - ``mission_finalize_planning_pin._preserve_or_capture_planning_commit_sha``'s
      re-finalize refusal (the historical ad hoc ``existing is None`` check
      once execution has begun).
    - WP03's ``doctor mission-state --fix`` recovery detector.

    Deliberately pure (no I/O, no ``Path``): both callers resolve
    ``execution_has_begun`` (a status-partition read) and ``lanes_present``
    (a ``read_lanes_json`` call) themselves, in whatever way their own
    layer allows, and combine them through this single predicate so the
    combination itself is never duplicated or drifted.
    """
    return execution_has_begun and not lanes_present
