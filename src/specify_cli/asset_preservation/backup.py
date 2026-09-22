"""Copy-only verbatim archiving for the asset-preservation guard.

When ownership is unprovable and the path's parent is about to be removed, the
guard preserves the content by copying it verbatim into a fresh, collision-safe
timestamped backup directory (reusing ``template.manager._allocate_backup_dir``
so backup-directory naming has one authority). This module is *copy-only*
(contract C1.5): it never unlinks the source — the guard performs any removal
separately, so an in-place preserve never deletes and a parent-removal archive
keeps a byte-identical copy before the guard tears the original down.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

from kernel.clock import now_utc_compact_stamp
from specify_cli.template.manager import _allocate_backup_dir

__all__ = ["archive_into", "backup_before_overwrite", "write_file_verbatim"]


def write_file_verbatim(src: Path, dest: Path) -> None:
    """Copy a regular file byte-exact, preserving mode + mtime, refusing to clobber.

    Uses ``O_EXCL`` so an unexpected pre-existing backup member is an error, not a
    silent overwrite. Never follows or removes the source.
    """
    info = src.lstat()
    mode = stat.S_IMODE(info.st_mode)
    content = src.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
    os.chmod(dest, mode)
    os.utime(dest, ns=(info.st_mtime_ns, info.st_mtime_ns))


def _copy_node(src: Path, dest: Path) -> None:
    if src.is_symlink():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(os.readlink(src))
    elif src.is_dir():
        dest.mkdir(parents=True, exist_ok=False)
        for child in sorted(src.iterdir()):
            _copy_node(child, dest / child.name)
        shutil.copystat(src, dest)
    else:
        write_file_verbatim(src, dest)


def _backup_symlink(path: Path, sidecar: Path) -> None:
    """Recreate ``path``'s link (never its target) at ``sidecar``.

    Uses ``os.readlink`` so a broken link's missing target never triggers a
    raise, and ``os.symlink`` so an existing ``sidecar`` refuses (``FileExistsError``)
    rather than being clobbered -- the same no-silent-overwrite guarantee
    ``write_file_verbatim`` gives the regular-file case via ``O_EXCL``.
    """
    link_target = os.readlink(path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(link_target, sidecar)


def backup_before_overwrite(path: Path) -> Path:
    """Create a byte-exact, symlink-aware sidecar backup before ``path`` is overwritten.

    Returns the sidecar path ``<path>.<timestamp>`` (timestamp from the
    canonical ``kernel.clock`` door, the same seam :func:`archive_into` uses
    transitively via ``_allocate_backup_dir``). The sidecar is created with
    ``O_EXCL`` semantics -- a pre-existing sidecar for the same path+timestamp
    raises rather than being clobbered. A symlink ``path`` is captured via
    ``os.readlink`` and recreated at the sidecar (never dereferenced), so a
    broken link backs up cleanly. ``path`` itself is never removed or modified;
    the caller replaces it afterward.
    """
    timestamp = now_utc_compact_stamp()
    sidecar = path.with_name(f"{path.name}.{timestamp}")
    if path.is_symlink():
        _backup_symlink(path, sidecar)
    else:
        write_file_verbatim(path, sidecar)
    return sidecar


def archive_into(path: Path, project_path: Path, backup_parent: Path) -> Path:
    """Copy ``path`` verbatim into a fresh timestamped dir under ``backup_parent``.

    Returns the archived path. The original is left untouched (the guard removes
    it afterward when the parent is being torn down).
    """
    backup_dir: Path = _allocate_backup_dir(backup_parent)
    try:
        rel = path.relative_to(project_path)
    except ValueError:
        rel = Path(path.name)
    dest: Path = backup_dir / rel
    _copy_node(path, dest)
    return dest
