"""Discard the per-user directories written by the pre-#6488 path rules.

Before #6488 each caller resolved its own directory, so on macOS the upgrade,
pack and service caches landed in ``~/.cache/spec-kitty`` while the upgrade-nag
cache landed in ``~/Library/Caches/spec-kitty``. Those old trees hold only
disposable caches and one one-time marker, so the operator's ruling is to
discard them rather than migrate anything (issue #6488, C-004).

Four invariants keep that safe. They are the whole contract of this module:

L1  **Never delete a live directory.** A candidate is skipped when it equals the
    current cache, state or config directory *or contains one*. This is not
    defensive padding: on Linux the pre-fix state root and the post-fix cache
    root are the same directory (``~/.cache/spec-kitty``), so without L1 the
    first command on a Linux machine would delete the live pack and service
    caches; on Windows the pre-fix cache root is the post-fix state directory.
L2  **Bounded.** A candidate is removed only through
    :func:`kernel.tree_removal.remove_tool_owned_tree`, with the per-user base it
    was derived from as the owned root: it must still resolve inside that base,
    it must not be a symlink (whose target may be anywhere), and no directory
    between it and the base may be a git checkout.
L3  **Silent.** A failure (permissions, a race, an unproven path) is logged at
    debug level and changes neither stdout, stderr nor the process's exit code:
    losing a cache is never worth failing a command.
L4  **Idempotent.** After the first run there is nothing left to stat-match, and
    the single caller (the CLI startup owners list) runs it once per process.

One file needs separate handling. On Linux the pre-fix state directory became the
post-fix **cache** directory, so it survives under L1; the one file inside it that
*was* state -- the runtime-cutover marker -- is discarded on its own, because
leaving it behind would show that one-time notice a second time.

No migration is performed: nothing is copied to the new location.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from kernel import paths as _paths
from kernel.tree_removal import ToolOwnedPathUnproven, remove_tool_owned_tree
from kernel.user_dirs import APP_NAME, user_cache_dir, user_config_dir, user_state_dir

__all__ = ["discard_legacy_locations"]

_LOG = logging.getLogger(__name__)

_XDG_CACHE_HOME = "XDG_CACHE_HOME"
_XDG_STATE_HOME = "XDG_STATE_HOME"
_LOCALAPPDATA = "LOCALAPPDATA"

_REASON = "pre-#6488 spec-kitty cache/state directory"

#: State files that moved with the state directory, discarded even when their old
#: directory is still live for another kind (the Linux case above).
_LEGACY_STATE_FILES = (".spec-kitty-runtime-cutover-notice-shown",)


@dataclass(frozen=True)
class _Candidate:
    """A legacy root and the per-user base it must stay inside."""

    root: Path
    base: Path
    written_by: str


def _xdg_base(variable: str, fallback: tuple[str, ...]) -> Path:
    """The pre-fix base for *variable*: its value if set, else ``~/<fallback>``."""
    value = os.environ.get(variable)
    if value:
        return Path(value)
    return Path.home().joinpath(*fallback)


def _local_app_data_base() -> Path:
    value = os.environ.get(_LOCALAPPDATA)
    return Path(value) if value else Path.home() / "AppData" / "Local"


def _candidates() -> tuple[_Candidate, ...]:
    """Every root a pre-#6488 rule could have written, with the base it belongs to."""
    cache_base = _xdg_base(_XDG_CACHE_HOME, (".cache",))
    state_base = _xdg_base(_XDG_STATE_HOME, (".cache",))
    candidates = [
        # upgrade_notifier, pack_fetch and service_artifacts all used the XDG rule
        # on every platform, so this is the legacy cache root everywhere.
        _Candidate(cache_base / APP_NAME, cache_base, "upgrade_notifier, pack_fetch, service_artifacts"),
        # runtime.next._runtime_pkg_notice used the state helper, whose fallback was
        # the literal ~/.cache rather than the XDG ~/.local/state.
        _Candidate(state_base / APP_NAME, state_base, "_runtime_pkg_notice"),
    ]
    if _paths.is_windows():
        local_app_data = _local_app_data_base()
        # upgrade_notifier's Windows branch: %LOCALAPPDATA%/<app> (now the live state dir).
        candidates.append(_Candidate(local_app_data / APP_NAME, local_app_data, "upgrade_notifier (Windows)"))
        # compat.cache and compat.config called platformdirs without appauthor=False,
        # which nests the app name twice; nothing reads that tree any more.
        candidates.append(_Candidate(local_app_data / APP_NAME / APP_NAME, local_app_data, "compat.cache, compat.config (platformdirs default author)"))
    return tuple(candidates)


def _is_live(root: Path, current: set[Path]) -> bool:
    """True when *root* is, or contains, a directory some caller writes to today (L1)."""
    return any(root == live or root in live.parents for live in current)


def _current_directories() -> set[Path]:
    return {user_cache_dir(), user_state_dir(), user_config_dir()}


def _discard_legacy_state_files() -> tuple[Path, ...]:
    """Remove the marker files that moved out of a still-live legacy directory (Linux).

    Only the note marker is handled here: it is one file the tool wrote itself, its
    name is unique to this product, and the copy in the legacy directory is stale by
    construction because the live one lives in the current state directory.
    """
    current_state = user_state_dir()
    removed: list[Path] = []
    for candidate in _candidates():
        if candidate.written_by != "_runtime_pkg_notice" or candidate.root == current_state:
            continue
        for name in _LEGACY_STATE_FILES:
            path = candidate.root / name
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                path.unlink()
                removed.append(path)
                _LOG.debug("discarded legacy state file %s", path)
            except OSError as exc:  # L3
                _LOG.debug("could not discard %s: %s", path, exc)
    return tuple(removed)


def discard_legacy_locations() -> tuple[Path, ...]:
    """Remove the pre-#6488 per-user directories that are no longer live (L1-L3).

    Returns:
        What was actually removed (legacy files first, then roots), in the order it
        was attempted. Empty when nothing was left behind, when every candidate is
        still live, or when a removal was refused -- an empty tuple is never an
        error.
    """
    current = _current_directories()
    removed: list[Path] = list(_discard_legacy_state_files())
    for candidate in _candidates():
        root = candidate.root
        if _is_live(root, current):
            continue
        if root.is_symlink():
            # ``remove_tool_owned_tree`` would refuse it after resolving; skip before
            # touching the filesystem so the intent is explicit.
            _LOG.debug("left legacy symlink %s in place (%s)", root, candidate.written_by)
            continue
        try:
            if remove_tool_owned_tree(root, tool_root=candidate.base, reason=_REASON, missing_ok=True, best_effort=True):
                removed.append(root)
                _LOG.debug("discarded legacy directory %s (%s)", root, candidate.written_by)
        except (ToolOwnedPathUnproven, OSError) as exc:  # L3: never fail a command over a cache
            _LOG.debug("could not discard %s (%s): %s", root, candidate.written_by, exc)
    return tuple(removed)
