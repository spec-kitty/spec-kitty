"""Shared utility helpers used across Spec Kitty modules."""

from __future__ import annotations

import contextlib
import errno
import os
import tempfile
import sys
from collections.abc import Sequence
from pathlib import Path
from stat import S_IMODE, S_ISDIR, S_ISREG

from kernel.tree_removal import remove_tool_owned_tree
from kernel.resolution import is_symlink_loop_error, resolve_rejecting_loops


#: Errnos that mean **absent** (or "not the kind of thing that could ever be a
#: directory/file", e.g. a dangling symlink or a non-directory in the middle of
#: a path) rather than **unreadable**. Reproduced from ``pathlib._ignore_error``
#: (private, and 3.13 moved it out of the top-level namespace) rather than
#: imported, for the same reason ``specify_cli.decisions.ownership`` reproduces
#: it: replacing ``is_dir()``/``is_file()``/``exists()`` with a guarded
#: ``stat()`` must not also change how genuinely absent-like failures are
#: classified — only make ``EACCES`` observable instead of silently swallowed.
_ABSENT_ERRNOS = frozenset({errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP})
_WRITE_BITS = 0o222

#: Shared prefix for the containment seams' symlink-loop refusal (#3189,
#: FR-002/FR-003): ``resolve_rejecting_loops`` reinstates the interpreter-
#: invariant loop probe, and both seams below translate its ``OSError`` into
#: this documented ``ValueError``.
_SYMLINK_LOOP_REFUSAL_PREFIX = "Refusing to access unresolvable path (symlink loop)"
_UNRESOLVABLE_REFUSAL_PREFIX = "Refusing to access unresolvable path"


def _unresolvable_path_refusal(path: Path, exc: OSError) -> ValueError:
    """Build the containment refusal for a path that could not be resolved.

    Only a genuine symlink loop is named as one; any other ``OSError`` (for
    example a relative path under a deleted working directory) gets the
    neutral wording so the message does not misreport the cause.
    """
    prefix = _SYMLINK_LOOP_REFUSAL_PREFIX if is_symlink_loop_error(exc) else _UNRESOLVABLE_REFUSAL_PREFIX
    return ValueError(f"{prefix}: {path}")


#: The write bit for owner/group/other. A managed tree (e.g. skills set
#: read-only by ``skills/installer._make_tree_read_only``) strips these, which
#: makes the atomic ``replace`` in :func:`write_text_within_directory` fail with
#: ``PermissionError`` (``[WinError 5]``) on Windows. Restoring the bit before
#: the replace is the #3771 fix; the value mirrors
#: ``runtime/generated_writer._WRITE_BITS``.
_WRITE_BITS = 0o222


def safe_is_dir(path: Path) -> bool:
    """``Path.is_dir()``, but with ONE behaviour across interpreters, not three.

    ``Path.is_dir()`` (and its siblings ``exists()``, ``is_file()``,
    ``is_symlink()``) call ``stat()`` and swallow ``OSError`` — but not
    identically everywhere: through Python 3.13 only the absent-like errnos
    above were swallowed and ``EACCES`` propagated, while 3.14 rewrote the
    predicates to swallow every ``OSError`` including ``EACCES``, so an
    unreadable ancestor silently answers ``False`` ("not a directory") on 3.14
    where every earlier interpreter raised. Measured (non-root euid, via a
    symlink into a ``0o000`` directory) in
    ``specify_cli.decisions.ownership``'s module docstring, which hit this
    exact divergence three times before the pattern was generalized here.

    This reproduces ``pathlib``'s own PRE-3.14 ``is_dir()`` — ``S_ISDIR(p.stat().st_mode)``
    under ``except OSError: if not _ignore_error(e): raise`` — so the answer
    is the same on every interpreter: ``False`` for absent-like failures
    (``ENOENT``/``ENOTDIR``/``EBADF``/``ELOOP``), and the ``OSError`` (typically
    ``EACCES``) is left to propagate for everything else, rather than being
    laundered into a bare ``False`` that a caller cannot tell apart from
    "not a directory".

    Callers that want to *tolerate* an unreadable candidate (skip it, warn
    about it, whatever the calling code's existing failure posture is) catch
    ``OSError`` around the call themselves, exactly as they already had to on
    3.11-3.13 before this helper existed — this only makes that requirement a
    property of ``stat()`` itself instead of an accident of interpreter version.
    """
    try:
        return S_ISDIR(path.stat().st_mode)
    except OSError as exc:
        if exc.errno in _ABSENT_ERRNOS:
            return False
        raise


def safe_is_file(path: Path) -> bool:
    """``Path.is_file()``, with the same one-behaviour-everywhere fix as :func:`safe_is_dir`.

    See :func:`safe_is_dir` for the full rationale; this is its ``S_ISREG``
    sibling for call sites asking "is this a regular file" rather than "is
    this a directory".
    """
    try:
        return S_ISREG(path.stat().st_mode)
    except OSError as exc:
        if exc.errno in _ABSENT_ERRNOS:
            return False
        raise


def format_path(path: Path, relative_to: Path | None = None) -> str:
    """Return a string path, optionally relative to another directory."""
    target = path
    if relative_to is not None:
        try:
            target = path.relative_to(relative_to)
        except ValueError:
            target = path
    return str(target)


def ensure_directory(path: Path) -> Path:
    """Create a directory (and parents) if it does not exist and return the Path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_within_directory(path: Path, root: Path) -> Path:
    """Resolve ``path`` and assert it remains under ``root``.

    Raises:
        ValueError: When ``path`` resolves outside ``root``, or when
            resolving ``path`` encounters a symlink loop anywhere in its
            components (interpreter-invariant on 3.11-3.14; see
            ``kernel.resolution.resolve_rejecting_loops``).
    """
    resolved_root = root.resolve()
    try:
        resolved_path = resolve_rejecting_loops(path)
    except OSError as exc:
        raise _unresolvable_path_refusal(path, exc) from exc
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Refusing to access path outside {resolved_root}: {resolved_path}") from exc
    return resolved_path


def ensure_within_any(path: Path, *, roots: Sequence[Path], files: Sequence[Path] = ()) -> Path:
    """Return ``path.resolve(strict=False)`` if it is under any of ``roots`` OR equals
    an allowed exact file in ``files``; else raise ``ValueError``.

    Multi-root sibling of ``ensure_within_directory``. Uses ``resolve(strict=False)``
    intentionally so that non-existent snapshot/rollback paths (which may not yet
    exist on disk) are accepted when they fall under a trusted root.

    Args:
        path: The candidate path to validate.
        roots: Trusted root directories. A resolved ``path`` is accepted when
            it is relative to any of these roots.
        files: Optional allowlist of exact file paths. A resolved ``path`` is
            accepted when it equals the resolved form of any entry here, even if
            it falls under no root.

    Returns:
        The resolved (strict=False) form of ``path``.

    Raises:
        ValueError: When ``path`` is neither under any root nor equal to any
            allowed file, or when resolving ``path`` encounters a symlink
            loop anywhere in its components (interpreter-invariant on
            3.11-3.14; see ``kernel.resolution.resolve_rejecting_loops``).
    """
    try:
        resolved = resolve_rejecting_loops(path)
    except OSError as exc:
        raise _unresolvable_path_refusal(path, exc) from exc
    resolved_roots = [r.resolve(strict=False) for r in roots]
    resolved_files = [f.resolve(strict=False) for f in files]

    if any(resolved == allowed for allowed in resolved_files):
        return resolved

    if any(_is_relative_to(resolved, root) for root in resolved_roots):
        return resolved

    raise ValueError(f"Refusing to access path outside trusted roots: {resolved}")


def _is_relative_to(path: Path, root: Path) -> bool:
    """Return True when ``path`` is relative to ``root`` (Python 3.9+ compatible helper)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def write_text_within_directory(path: Path, content: str, *, root: Path, encoding: str = "utf-8") -> Path:
    """Atomically write text to a file only when the resolved path stays under ``root``."""
    safe_path = ensure_within_directory(path, root)
    safe_path.parent.mkdir(parents=True, exist_ok=True)

    existing_mode: int | None = None
    if safe_is_file(safe_path):
        existing_mode = S_IMODE(safe_path.stat().st_mode)
        # Best effort: Windows needs the target write bit cleared before an
        # atomic replace, while POSIX can still replace it when chmod itself
        # is denied but the parent directory is writable.
        with contextlib.suppress(OSError):
            safe_path.chmod(existing_mode | _WRITE_BITS)

    fd, temp_path = tempfile.mkstemp(dir=safe_path.parent, prefix=f".{safe_path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(content)
        Path(temp_path).replace(safe_path)
        if existing_mode is not None:
            with contextlib.suppress(OSError):
                safe_path.chmod(existing_mode)
    except Exception:
        if existing_mode is not None:
            with contextlib.suppress(OSError):
                safe_path.chmod(existing_mode)
        Path(temp_path).unlink(missing_ok=True)
        raise
    return safe_path


def safe_remove(path: Path, *, tool_root: Path | None = None) -> bool:
    """Remove a file or directory tree if it exists, returning True when something was removed.

    ``tool_root`` is the root the caller owns (default: ``path`` itself); the removal is
    refused (``ToolOwnedPathUnproven``) when ``path`` is outside it or is a git checkout.
    """
    return remove_tool_owned_tree(path, tool_root=tool_root or path, reason="core.utils.safe_remove")


def get_platform() -> str:
    """Return the current platform identifier (linux/darwin/win32)."""
    return sys.platform


__all__ = [
    "format_path",
    "ensure_directory",
    "ensure_within_any",
    "ensure_within_directory",
    "write_text_within_directory",
    "safe_remove",
    "safe_is_dir",
    "safe_is_file",
    "get_platform",
]
