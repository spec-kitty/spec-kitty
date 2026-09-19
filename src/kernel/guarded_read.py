"""Format-agnostic guarded-read primitive — the kernel's read+collapse authority.

Lives in ``kernel`` (the zero-dependency root, D1): it takes a caller-supplied
``parse`` callable and a caller-declared exception tuple, and never imports a
schema/validation library (pydantic, tomllib's callers, a YAML decoder) — that
knowledge stays in the caller layer (``specify_cli``/``runtime``). See
``contracts/guarded-read-primitive.md`` for the full contract this module
implements.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal, TypeVar

from kernel.errors import GuardedReadError

__all__ = ["read_guarded"]

T = TypeVar("T")


def _read_content(path: Path, mode: Literal["bytes", "text"]) -> bytes | str:
    """Read *path* exactly once, in the requested *mode*."""
    if mode == "bytes":
        return path.read_bytes()
    return path.read_text(encoding="utf-8")


def _collapse(
    fn: Callable[[], T],
    declared: tuple[type[BaseException], ...],
    make_error: Callable[[BaseException], GuardedReadError],
) -> T:
    """Run *fn*; map any of *declared* it raises onto a chained typed error.

    Any exception outside *declared* propagates unchanged — a genuine bug in
    *fn* must still surface as a traceback (guarantee #4). Shared by
    :func:`read_guarded` and :func:`kernel.meta_decode.decode_meta`'s
    exception-collapsing branch: both "run untrusted work, map a declared
    failure set onto one typed error, chain the original cause" — the plan's
    ``MDEC --> PRIM`` dependency arrow, expressed as this small shared helper
    rather than a literal ``decode_meta`` call to :func:`read_guarded` (that
    would require ``decode_meta`` to take a filesystem path and break its
    documented pure-decode contract).
    """
    try:
        return fn()
    except declared as exc:
        raise make_error(exc) from exc


def read_guarded(
    path: Path,
    parse: Callable[[bytes | str], T],
    *,
    errors: tuple[type[BaseException], ...] = (),
    error_cls: type[GuardedReadError] = GuardedReadError,
    mode: Literal["bytes", "text"] = "text",
) -> T:
    """Read *path* once, apply *parse*, and collapse declared failures.

    Args:
        path: The file to read.
        parse: Applied to the read content; its result is returned unchanged
            on success.
        errors: Additional exception types (beyond the always-declared
            ``(OSError, UnicodeDecodeError)``) that *parse* may raise and that
            should collapse into *error_cls* — e.g. ``json.JSONDecodeError``,
            ``yaml.YAMLError``, ``pydantic.ValidationError``.
        error_cls: The :class:`GuardedReadError` subclass to raise on a
            declared failure. Defaults to the base itself.
        mode: ``"text"`` decodes the file as UTF-8 before calling *parse*;
            ``"bytes"`` passes the raw bytes.

    Returns:
        Whatever *parse* returns, unchanged.

    Raises:
        GuardedReadError: (or the *error_cls* subclass) when the read or
            *parse* raises one of ``(OSError, UnicodeDecodeError, *errors)``.
            The original exception is chained via ``raise ... from exc``.
        BaseException: Any exception *parse* raises that is not in the
            declared set propagates unchanged.
    """
    declared: tuple[type[BaseException], ...] = (OSError, UnicodeDecodeError, *errors)

    def _do() -> T:
        content = _read_content(path, mode)
        return parse(content)

    return _collapse(
        _do,
        declared,
        lambda exc: error_cls(path=str(path), reason=str(exc)),
    )
