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

from specify_cli.template.manager import _allocate_backup_dir

__all__ = ["archive_into", "write_file_verbatim"]


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
