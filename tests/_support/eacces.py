"""Shared helpers for denied-access (EACCES) tests.

**Prefer seam injection.** ``deny_open_in`` and ``deny_path_method`` make ONE
named path raise ``PermissionError`` at the filesystem seam the code under test
reads through, and delegate to the original for every other path. They behave
the same for every uid (root bypasses mode bits, so a ``chmod(0)`` setup gave a
different verdict per uid, #5622), so they need no skip.

Reach for the chmod-and-skip technique (``mode_bits_enforced``) only when the
test must exercise the real kernel permission check itself. It is the pattern
``tests/specify_cli/decisions/test_ownership_3111.py`` established for
`#3111`/`#3177` and `#3194` found at several call sites carrying the same
``Path.is_dir()`` / ``Path.exists()`` / ``Path.is_file()`` EACCES divergence.

Paths are compared RESOLVED (``Path(p).resolve() == Path(target).resolve()``),
so a symlinked or relative spelling of the target is still denied. Arguments
that are not path-like fall through to the original.
"""

from __future__ import annotations

import builtins
import os
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _is_target(candidate: object, resolved_target: Path) -> bool:
    """Whether *candidate* names *resolved_target*; non-path arguments are never a match."""
    if not isinstance(candidate, (str, os.PathLike)):
        return False
    try:
        return Path(candidate).resolve() == resolved_target
    except (OSError, RuntimeError, ValueError):
        return False


def _denied(candidate: object) -> PermissionError:
    return PermissionError(13, "Permission denied", str(candidate))


def deny_open_in(monkeypatch: pytest.MonkeyPatch, module: ModuleType, target: Path) -> None:
    """Make ``open(target)`` inside *module* raise ``PermissionError``; every other path delegates.

    Patches the module-level name ``open`` (shadowing the builtin for that
    module only), so code in other modules is unaffected.
    """
    resolved_target = Path(target).resolve()
    real_open = builtins.open

    def guarded_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_target(file, resolved_target):
            raise _denied(file)
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(module, "open", guarded_open, raising=False)


def deny_path_method(monkeypatch: pytest.MonkeyPatch, attr: str, target: Path) -> None:
    """Make ``Path.<attr>`` raise ``PermissionError`` when called on *target*; every other path delegates.

    *attr* is a ``Path`` method name such as ``"read_text"``, ``"exists"`` or
    ``"iterdir"``. Call it once per method to deny several.
    """
    resolved_target = Path(target).resolve()
    original: Callable[..., Any] = getattr(Path, attr)

    def guarded(self: Path, *args: Any, **kwargs: Any) -> Any:
        if _is_target(self, resolved_target):
            raise _denied(self)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, attr, guarded)


def mode_bits_enforced(probe: Path) -> bool:
    """Return ``True`` when the process is actually denied by *probe*'s mode bits.

    **Skip honestly.** Running as root, or on a filesystem that ignores mode
    bits, makes a ``0o000`` test pass while exercising nothing — the vacuous
    case. *probe* must be a **file** read *after* the directory containing it
    has been ``chmod``'d to ``0o000``: on a directory, opening it always raises
    ``IsADirectoryError`` (itself an ``OSError``), which would make this helper
    constant ``True`` and silently defeat the skip it exists to perform.
    """
    try:
        with probe.open("rb"):
            pass
    except OSError:
        return True
    return False
