"""Self-heal for stale ``.pyc`` bytecode caches left by interrupted installs.

An interrupted ``pip install`` / ``uv tool install`` upgrade — common on
Windows, where file locking and antivirus scans can truncate the write —
leaves a partially-written ``__pycache__/*.pyc`` behind. The 16-byte header
survives, so the import machinery trusts the file and dies unmarshalling the
body: ``ValueError: bad marshal data``, ``EOFError: marshal data too short``,
``ImportError: Non-code object in '...pyc'``, or the ``AttributeError:
'bytes' object has no attribute 'co_filename'`` signature observed in the
field (#4124). Because ``cli/commands/upgrade.py`` imports
``specify_cli.upgrade.runner`` -> ``upgrade.migrations.base`` at module
level, one corrupt cache file kills app assembly — every command, not just
``upgrade`` — with a raw traceback that names no actionable fix.

Deleting a ``.pyc`` is always safe: ``.pyc`` files are derived caches and
Python recompiles from the ``.py`` source on the next import. This module
recognizes import failures plausibly caused by a stale cache, purges the
installed package's bytecode, and retries the failed operation exactly once.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import TypeVar

from kernel.paths import is_windows

__all__ = ["invoke_with_bytecode_heal"]

T = TypeVar("T")

# The import machinery executes in frozen ``importlib._bootstrap*`` frames;
# their presence in a failure's traceback is the signal that the failure
# happened *inside an import*, not in ordinary package code.
_FROZEN_IMPORTLIB_MARKER = "<frozen importlib."

# Field signature of a partially-unmarshalled code object (#4124): something
# read ``.co_filename`` off what the corrupt cache actually unmarshalled to.
_CORRUPT_CODE_ATTRIBUTE_MARKER = "co_filename"


def package_root() -> Path | None:
    """Directory of the running ``specify_cli`` package, if resolvable."""
    with suppress(Exception):
        import specify_cli

        if specify_cli.__file__:
            return Path(specify_cli.__file__).resolve().parent
    return None


def failure_during_package_import(exc: BaseException) -> bool:
    """Return True when *exc* was plausibly raised loading this package's bytecode.

    Three shapes qualify directly:

    * a marshal-flavored failure (``ValueError``/``EOFError``) raised from a
      frozen ``importlib`` frame — the truncated-cache signature;
    * an ``ImportError`` whose message or ``.path`` names a file under the
      package root (``ImportError: Non-code object in '...pyc'`` — the import
      machinery strips its own frames from that traceback, so the frame scan
      below cannot see it);
    * the ``AttributeError ... no attribute 'co_filename'`` signature observed
      in the field on a partially-unmarshalled code object.

    A *laundered* failure also qualifies when the exception it wraps does:
    ``upgrade.migrations.auto_discover_migrations`` collects per-module import
    failures and raises one fresh ``MigrationDiscoveryError`` chained to the
    first original (``raise ... from``), so the corrupt-cache signature lives
    on the wrapped exception in the ``__cause__``/``__context__`` chain, not on
    the wrapper. Only the marshal/non-code/``co_filename`` signatures qualify
    when wrapped — a genuinely broken migration module (``SyntaxError``,
    ``ModuleNotFoundError``) fails inside an import too, and healing it would
    just purge every cache and fail again.

    An ordinary bug in package code matches none of these: it propagates
    untouched.
    """
    root = package_root()
    if root is None:
        return False
    if _directly_plausibly_stale(exc, root):
        return True
    return _wrapped_plausibly_stale(exc, root)


def _directly_plausibly_stale(exc: BaseException, root: Path) -> bool:
    """The three direct shapes described in ``failure_during_package_import``."""
    if isinstance(exc, AttributeError) and _CORRUPT_CODE_ATTRIBUTE_MARKER in str(exc):
        return True
    if isinstance(exc, ImportError) and _names_package_path(exc, root):
        return True
    saw_frozen_import_frame = False
    saw_package_frame = False
    tb = exc.__traceback__
    while tb is not None:
        filename = tb.tb_frame.f_code.co_filename
        if _FROZEN_IMPORTLIB_MARKER in filename:
            saw_frozen_import_frame = True
        elif _is_under_root(filename, root):
            saw_package_frame = True
        tb = tb.tb_next
    if not saw_frozen_import_frame:
        return False
    return saw_package_frame or isinstance(exc, (ValueError, EOFError))


def _wrapped_plausibly_stale(exc: BaseException, root: Path) -> bool:
    """True when a failure wrapped in *exc*'s cause/context chain is stale-cache-shaped."""
    pending: list[BaseException | None] = [exc.__cause__, exc.__context__]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if _corrupt_cache_signature(current, root):
            return True
        pending.append(current.__cause__)
        pending.append(current.__context__)
    return False


def _corrupt_cache_signature(exc: BaseException, root: Path) -> bool:
    """The truncated-``.pyc`` signature, independent of where it surfaced.

    Used on *wrapped* failures, where the looser direct frame heuristic would
    also match a genuine import-time bug in a migration module (any exception
    raised while a package module imports carries frozen ``importlib`` and
    package frames): only the marshal-flavored failure from the import
    machinery itself, the non-code ``ImportError`` naming a package ``.pyc``,
    or the ``co_filename`` ``AttributeError`` prove a stale cache.
    """
    if isinstance(exc, AttributeError) and _CORRUPT_CODE_ATTRIBUTE_MARKER in str(exc):
        return True
    if isinstance(exc, ImportError) and _names_package_path(exc, root):
        return True
    return isinstance(exc, (ValueError, EOFError)) and _saw_frozen_import_frame(exc)


def _saw_frozen_import_frame(exc: BaseException) -> bool:
    """True when *exc*'s traceback passes through frozen ``importlib`` frames."""
    tb = exc.__traceback__
    while tb is not None:
        if _FROZEN_IMPORTLIB_MARKER in tb.tb_frame.f_code.co_filename:
            return True
        tb = tb.tb_next
    return False


def purge_package_bytecode() -> int:
    """Delete every ``*.pyc`` under the running package; return the count removed.

    Always safe: ``.pyc`` files are derived caches and are recompiled from
    source on the next import. Cache files that cannot be removed (e.g.
    briefly locked by antivirus on Windows) are skipped — a partial purge
    still lets the retry recompile what it needs.
    """
    root = package_root()
    if root is None or not root.is_dir():
        return 0
    removed = 0
    for cache_file in root.rglob("*.pyc"):
        with suppress(OSError):
            cache_file.unlink()
            removed += 1
    importlib.invalidate_caches()
    return removed


def invoke_with_bytecode_heal(
    operation: Callable[[], T],
    *,
    on_healed: Callable[[int], None] | None = None,
) -> T:
    """Run *operation*, healing a stale bytecode cache once if its import fails.

    A failure not plausibly caused by the import machinery, and a retry that
    fails again, propagate unchanged — this heals interrupted-install
    corruption, not bugs. When the retry succeeds, ``on_healed`` (if given)
    receives the number of purged cache files so the caller can tell the
    operator what happened.
    """
    try:
        return operation()
    except Exception as exc:
        if not failure_during_package_import(exc):
            raise
        removed = purge_package_bytecode()
        if removed == 0:
            # Nothing was purgeable, so a retry would hit the identical
            # failure — surface the original exception instead.
            raise
        result = operation()
        if on_healed is not None:
            with suppress(Exception):
                on_healed(removed)
        return result


def _names_package_path(exc: ImportError, root: Path) -> bool:
    """Return True when *exc* carries a file path under *root*.

    Windows paths compare case-insensitively, matching the filesystem.
    """
    candidates = [str(exc)]
    path = getattr(exc, "path", None)
    if isinstance(path, (str, Path)):
        candidates.append(str(path))
    if is_windows():
        root_text = str(root).casefold()
        return any(root_text in candidate.casefold() for candidate in candidates)
    root_text = str(root)
    return any(root_text in candidate for candidate in candidates)


def _is_under_root(filename: str, root: Path) -> bool:
    """Return True when *filename* resolves to a path inside *root*."""
    try:
        return Path(filename).resolve().is_relative_to(root)
    except (OSError, ValueError):
        return False
