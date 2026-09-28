"""Interpreter-invariant, loop-rejecting path resolution (issue #3189, WP01).

CPython 3.11 and 3.12's non-strict ``pathlib.Path.resolve()`` perform a
``stat()`` probe on the realpath result specifically to surface symlink
loops: if that probe fails with ``ELOOP`` (or, on Windows, the analogous
"cannot resolve filename" error), ``resolve()`` re-raises it as a
``RuntimeError`` wrapping the original ``OSError``. CPython 3.13 reworked
``pathlib``'s resolution internals and dropped that probe, so non-strict
``resolve()`` on 3.13+ silently returns an unresolved path for a symlink
loop instead of raising anything. ``resolve(strict=True)`` still raises
``OSError(ELOOP, ...)`` on 3.13+, but switching to strict mode everywhere
would also turn other non-loop failures (e.g. a merely-missing path) into
raises, which breaks the non-strict contract every existing call site
relies on (research.md R-1, alternatives considered).

``resolve_rejecting_loops`` re-instates exactly the 3.11/3.12 probe on
every interpreter: resolve non-strict, then ``stat()`` the result once
(the same call 3.11's own ``pathlib`` already performs internally, so the
added cost is one syscall — NFR-002) and treat a loop-shaped failure as a
loop. Any other ``OSError`` from that probe (missing path, dangling
symlink, permission denied) is swallowed, because non-strict semantics
must still hold for everything that is not a loop.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path


__all__ = ["resolve_rejecting_loops", "is_symlink_loop_error"]

# Windows' `FSCTL_GET_REPARSE_POINT`-based resolution reports a symlink loop
# as `winerror` 1921 ("The name of the file cannot be resolved by the
# system"), not as ELOOP — Python's `errno` module has no portable mapping
# for it, so it is checked as a named constant instead.
_WINERROR_CANT_RESOLVE_FILENAME = 1921


def is_symlink_loop_error(exc: BaseException) -> bool:
    """True if ``exc`` is an ``OSError`` shaped like a symlink-loop failure."""
    return isinstance(exc, OSError) and (exc.errno == errno.ELOOP or getattr(exc, "winerror", None) == _WINERROR_CANT_RESOLVE_FILENAME)


def _loop_error(path: Path) -> OSError:
    return OSError(errno.ELOOP, os.strerror(errno.ELOOP), str(path))


def resolve_rejecting_loops(path: Path) -> Path:
    """Behave like non-strict ``path.resolve()``, but always raise on a symlink loop.

    Equivalent to ``path.resolve()`` on every interpreter this project
    supports (3.11-3.14), except that a symlink loop anywhere in ``path``
    raises ``OSError(errno.ELOOP, ...)`` instead of either the 3.11/3.12
    ``RuntimeError`` wrapper or the 3.13+ silent, unresolved return.
    """
    try:
        resolved = path.resolve()
    except RuntimeError as exc:
        # 3.11/3.12 branch: pathlib's own check_eloop wraps the loop OSError
        # as a RuntimeError, reachable via __context__ or __cause__ depending
        # on how it was raised internally.
        context = exc.__context__
        cause = exc.__cause__
        if isinstance(context, OSError) and is_symlink_loop_error(context):
            raise _loop_error(path) from exc
        if isinstance(cause, OSError) and is_symlink_loop_error(cause):
            raise _loop_error(path) from exc
        # Not a loop: a genuine programmer-facing RuntimeError must not be
        # masked.
        raise

    # 3.13+ branch: resolve() no longer probes for loops itself, so probe
    # once here — the same stat() 3.11's pathlib already performed.
    try:
        os.stat(resolved)
    except OSError as probe_exc:
        if is_symlink_loop_error(probe_exc):
            raise _loop_error(path) from probe_exc
        # Anything else (missing, dangling, permission denied) is exactly
        # what non-strict resolve() semantics already tolerate.

    return resolved
