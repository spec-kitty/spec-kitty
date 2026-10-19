"""Fetch a pinned pack subtree from spec-kitty-open-packs, cache it, verify it, place it (#6451).

The one core behind ``scripts/sync_packs.py``, the hatch build hook and the
pin-bump helper. Pipeline: :func:`fetch_to_cache` (cached, digest-verified tree
for the pinned commit) then :func:`place_pack` (re-hash a staged copy, swap it
in). :func:`check_pack` answers ``OK`` / ``STALE`` / ``MISSING`` without network.

Remote contact belongs to ``kernel.git.remote``; this module spawns no git. The
repository URL comes only from the pin. Trees containing symlinks are refused
(NFR-004), and every cache read and every placement re-hashes the tree, so a
poisoned cache is never trusted.
"""

from __future__ import annotations

import os
import shutil
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from charter.offering.packs.pack_pin import PackPin, verify_pack_pin
from kernel.tree_removal import remove_tool_owned_tree
from kernel.git.remote import CommitUnresolvable, RemoteUnreachable, fetch_commit_subtree

__all__ = [
    "PACK_COMMIT_UNRESOLVABLE",
    "PACK_DIGEST_MISMATCH",
    "PACK_PIN_INVALID",
    "PACK_SYNC_UNAVAILABLE",
    "PACK_TREE_STALE",
    "PackSyncError",
    "PackTreeStatus",
    "check_pack",
    "fetch_to_cache",
    "place_pack",
]

PACK_DIGEST_MISMATCH = "PACK_DIGEST_MISMATCH"
PACK_COMMIT_UNRESOLVABLE = "PACK_COMMIT_UNRESOLVABLE"
PACK_SYNC_UNAVAILABLE = "PACK_SYNC_UNAVAILABLE"
PACK_TREE_STALE = "PACK_TREE_STALE"
PACK_PIN_INVALID = "PACK_PIN_INVALID"

_REMEDY = "run `make sync-packs` with network access"
_ASIDE_FMT = ".{name}.aside"
_STAGING_FMT = ".{name}.staging-{pid}"
_WORK_FMT = ".fetch-{sha}-{pid}"
_DEFAULT_RETRIES = 5
_DEFAULT_RETRY_DELAY = 0.2


class PackSyncError(RuntimeError):
    """A pack sync failed; ``code`` is one of the stable ``PACK_*`` codes."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


class PackTreeStatus(Enum):
    """State of a placed pack tree relative to its pin."""

    OK = "ok"
    STALE = "stale"
    MISSING = "missing"


def default_cache_root() -> Path:
    """``${XDG_CACHE_HOME:-~/.cache}/spec-kitty/open-packs``."""
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "spec-kitty" / "open-packs"


def _require_subtree(pin: PackPin) -> str:
    if pin.subtree is None:
        raise PackSyncError(PACK_PIN_INVALID, f"pin for {pin.repository} has no 'subtree'; add it to the pin file")
    subtree: str = pin.subtree
    return subtree


def _find_symlink(root: Path) -> Path | None:
    for current, dirnames, filenames in os.walk(root):
        for name in (*dirnames, *filenames):
            candidate = Path(current) / name
            if candidate.is_symlink():
                return candidate
    return None


def _refuse_symlinks(root: Path) -> None:
    link = _find_symlink(root)
    if link is not None:
        raise PackSyncError(PACK_DIGEST_MISMATCH, f"refusing pack tree containing a symlink: {link.relative_to(root)}")


def _digest_ok(pin: PackPin, root: Path) -> bool:
    """``True`` iff *root* is a symlink-free pack tree whose clean digest equals the pin's."""
    if not root.is_dir() or _find_symlink(root) is not None:
        return False
    try:
        verified: bool = verify_pack_pin(pin, root)
    except (OSError, ValueError):
        # No/invalid pack.yaml or unreadable file: not the pinned tree.
        return False
    return verified


def _remove_tree(path: Path) -> None:
    """Delete a cache, staging or aside entry this module created beside its owning parent."""
    remove_tool_owned_tree(path, tool_root=path.parent, reason="pack sync scratch, staging or aside tree")


def _remove_scratch_repo(work: Path) -> None:
    """Delete the scratch fetch repository: its own ``.git`` first (a tree this module ``git init``-ed), then the rest."""
    git_dir = work / ".git"
    if git_dir.is_dir() and not git_dir.is_symlink():
        remove_tool_owned_tree(git_dir, tool_root=git_dir, reason="git dir of the pack fetch scratch repository")
    _remove_tree(work)


def _fetch_into_cache(pin: PackPin, subtree: str, target: Path, cache_root: Path) -> None:
    work = cache_root / _WORK_FMT.format(sha=pin.commit, pid=os.getpid())
    cache_root.mkdir(parents=True, exist_ok=True)
    _remove_scratch_repo(work)
    try:
        try:
            fetched = fetch_commit_subtree(pin.repository, pin.commit, subtree, work)
        except (CommitUnresolvable, RemoteUnreachable):
            raise
        except ValueError as exc:
            raise PackSyncError(PACK_PIN_INVALID, f"pin for {pin.repository} is unsafe: {exc}") from exc
        if not fetched.is_dir():
            raise PackSyncError(PACK_COMMIT_UNRESOLVABLE, f"commit {pin.commit} has no '{subtree}' tree in {pin.repository}")
        _refuse_symlinks(fetched)
        if not _digest_ok(pin, fetched):
            raise PackSyncError(
                PACK_DIGEST_MISMATCH,
                f"'{subtree}' at {pin.commit} does not match the pinned tree_digest {pin.tree_digest.value}; the pin file and the repository disagree",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        _remove_tree(target)
        shutil.copytree(fetched, target, symlinks=False, ignore=shutil.ignore_patterns(".git"))
    except CommitUnresolvable as exc:
        raise PackSyncError(PACK_COMMIT_UNRESOLVABLE, f"commit {pin.commit} is not served by {pin.repository}: {exc}") from exc
    except RemoteUnreachable as exc:
        raise PackSyncError(PACK_SYNC_UNAVAILABLE, f"cannot reach {pin.repository} and no valid cache exists ({exc}); {_REMEDY}") from exc
    finally:
        _remove_scratch_repo(work)


def fetch_to_cache(pin: PackPin, *, offline: bool = False, cache_root: Path | None = None) -> Path:
    """Return the digest-verified cached tree for *pin*, fetching it unless *offline*.

    A cached tree is trusted only after its digest is re-checked; a failing one
    is deleted and refetched. Nothing that fails its digest stays in the cache.
    """
    subtree = _require_subtree(pin)
    root = default_cache_root() if cache_root is None else Path(cache_root)
    commit: str = pin.commit
    target: Path = root / commit / subtree
    if target.exists():
        if _digest_ok(pin, target):
            return target
        _remove_tree(target)
    if offline:
        raise PackSyncError(PACK_SYNC_UNAVAILABLE, f"offline and no valid cache for {pin.commit}; {_REMEDY}")
    _fetch_into_cache(pin, subtree, target, root)
    return target


def _rename(src: Path, dst: Path) -> None:
    src.rename(dst)


def _retrying(rename: Callable[[Path, Path], None], retries: int, delay: float) -> Callable[[Path, Path], None]:
    """Wrap *rename* with bounded retries for the transient ``PermissionError`` Windows raises."""

    def run(src: Path, dst: Path) -> None:
        for attempt in range(1, retries + 1):
            try:
                rename(src, dst)
            except PermissionError:
                if attempt == retries:
                    raise
                time.sleep(delay)
            else:
                return

    return run


def recover_interrupted_swap(dest: Path) -> None:
    """Undo a swap that died between moving the old tree aside and installing the new one."""
    aside = dest.parent / _ASIDE_FMT.format(name=dest.name)
    if not aside.exists():
        return
    if dest.exists():
        _remove_tree(aside)  # the swap finished; only the cleanup was interrupted
    else:
        aside.rename(dest)


def _stage(cached: Path, pin: PackPin, staging: Path) -> None:
    _refuse_symlinks(cached)
    shutil.copytree(cached, staging, symlinks=False)
    if not _digest_ok(pin, staging):
        raise PackSyncError(
            PACK_DIGEST_MISMATCH,
            f"staged copy of {cached} does not match the pinned tree_digest {pin.tree_digest.value}; the cache was altered",
        )


def place_pack(
    cached: Path,
    dest: Path,
    pin: PackPin,
    *,
    rename: Callable[[Path, Path], None] = _rename,
    retries: int = _DEFAULT_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> None:
    """Install *cached* at *dest* atomically-enough: stage, re-hash, swap with aside-restore.

    The staged copy is re-hashed against *pin* before anything at *dest* is
    touched; a mismatch leaves *dest* as it was. The old tree is renamed aside
    (never ``os.replace`` onto a directory: that fails on Windows), the staged
    tree renamed in, then the aside copy removed. Any failure in between puts
    the old tree back; a hard kill is repaired by :func:`recover_interrupted_swap`
    at the start of the next run.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    recover_interrupted_swap(dest)
    staging = dest.parent / _STAGING_FMT.format(name=dest.name, pid=os.getpid())
    aside = dest.parent / _ASIDE_FMT.format(name=dest.name)
    move = _retrying(rename, retries, retry_delay)
    restore = _retrying(_rename, retries, retry_delay)
    _remove_tree(staging)
    swapped = False
    try:
        _stage(Path(cached), pin, staging)
        if dest.exists():
            move(dest, aside)
        move(staging, dest)
        swapped = True
    finally:
        if not swapped and aside.exists() and not dest.exists():
            restore(aside, dest)
        _remove_tree(staging)
        if swapped:
            _remove_tree(aside)


def check_pack(pin: PackPin, dest: Path) -> PackTreeStatus:
    """Compare the tree at *dest* with the pin, offline; re-hashes on every call, trusts no marker."""
    dest = Path(dest)
    recover_interrupted_swap(dest)
    if not dest.is_dir():
        return PackTreeStatus.MISSING
    return PackTreeStatus.OK if _digest_ok(pin, dest) else PackTreeStatus.STALE
