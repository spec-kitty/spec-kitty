"""Atomic file write utility.

Guarantees: file is either complete old content or complete new content,
never partial. Uses write-to-temp-then-rename on the same filesystem.

Also exposes the canonical *no-op-stable* comparison core (umbrella #1914):
a pure, I/O-free :func:`substantively_equal` that decides whether a freshly
rendered payload differs from existing content *modulo* a caller-supplied
volatile-field projection. Surfaces that re-render tracked files on every run
(charter synthesis, status snapshots, upgrade metadata, ...) share this
comparison so a no-op run leaves the committed bytes untouched and the working
tree clean.

It lives in ``kernel`` (the dependency-free root) rather than
``specify_cli.core`` so the ``charter`` layer can adopt it without crossing the
``charter ↛ specify_cli`` boundary (see
``tests/architectural/test_layer_rules.py`` Invariant 3). specify_cli-level
callers import it directly from ``kernel.atomic``.

Phase 1 (#1914) ships :func:`substantively_equal` with charter synthesis as its
first adopter (via ``src/charter/activation/synthesizer/write_pipeline.py``). A
``write_if_changed`` convenience that gates :func:`atomic_write` on this core —
for byte-comparable writers like status.json (#524) — is deferred to the
Phase-2 convergence so it lands with its first real consumer (the symbol-level
dead-code ratchet forbids shipping it as unwired public surface).
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import Callable
from contextvars import ContextVar, Token
from pathlib import Path

__all__ = [
    "atomic_write",
    "notify_written",
    "observe_writes",
    "stop_observing_writes",
    "substantively_equal",
]

#: The observer the current context installed with :func:`observe_writes`, told about each file written.
_WRITE_OBSERVER: ContextVar[Callable[[Path, bytes], None] | None] = ContextVar("kernel_atomic_write_observer", default=None)


def observe_writes(observer: Callable[[Path, bytes], None]) -> Token[Callable[[Path, bytes], None] | None]:
    """Tell *observer* ``(path, bytes)`` after every :func:`atomic_write` (and :func:`notify_written`) in this context.

    For a caller that must know exactly which files, and which bytes, one operation wrote (the finalize
    write ledger). An observer already installed keeps hearing about every write too. Returns the token :func:`stop_observing_writes` takes.
    """
    outer = _WRITE_OBSERVER.get()

    def both(path: Path, content: bytes) -> None:
        if outer is not None:
            outer(path, content)
        observer(path, content)

    return _WRITE_OBSERVER.set(both)


def stop_observing_writes(token: Token[Callable[[Path, bytes], None] | None]) -> None:
    """Remove the observer :func:`observe_writes` installed."""
    _WRITE_OBSERVER.reset(token)


def notify_written(path: Path, content: bytes) -> None:
    """Tell the installed observer, if any, that *path* now holds *content* (for writers that do not use :func:`atomic_write`)."""
    observer = _WRITE_OBSERVER.get()
    if observer is not None:
        observer(path, content)


# A volatile-field projection: given decoded text and a set of volatile keys,
# return the "substantive content" form that two semantically-identical renders
# produce identically. Pluggable so the core makes NO assumptions about the
# serialization format (the charter YAML-canonical-line stripper is one such
# projection, passed in by the caller — see ``src/charter/synthesizer``).
StripFn = Callable[[str, frozenset[str]], str]


def atomic_write(path: Path, content: str | bytes, *, mkdir: bool = False) -> None:
    """Write *content* atomically to *path*.

    Parameters
    ----------
    path : Path
        Target file path.
    content : str | bytes
        File content. ``str`` is encoded to UTF-8; ``bytes`` is written raw.
    mkdir : bool
        If True, create parent directories before writing.
    """
    if mkdir:
        path.parent.mkdir(parents=True, exist_ok=True)

    raw = content.encode("utf-8") if isinstance(content, str) else content

    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=".atomic-",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        # fd is now closed by the context manager
        Path(tmp_path).replace(path)
        notify_written(path, raw)
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        with contextlib.suppress(OSError):
            Path(tmp_path).unlink()
        raise


def substantively_equal(
    existing: str | bytes,
    candidate: str | bytes,
    *,
    volatile_keys: frozenset[str] = frozenset(),
    strip: StripFn | None = None,
) -> bool:
    """Return True if *candidate* equals *existing* for no-op-stability purposes.

    Pure and I/O-free — the canonical comparison core for umbrella #1914. The
    caller is responsible for reading existing content from disk (and for
    deciding what an *absent* file means); this function only compares two
    in-memory payloads.

    Default behaviour (``strip is None``) is a plain byte/text comparison —
    correct for surfaces whose rendered payload carries no volatile fields
    (e.g. status.json snapshots, #524).

    When a ``strip`` projection is supplied, both sides are decoded to text and
    run through ``strip(text, volatile_keys)`` before comparison; equality
    *modulo* the volatile fields then signals a no-op. The projection is
    pluggable precisely so this core bakes in NO format assumptions — charter
    passes its YAML-canonical-line stripper, a future JSON surface could pass a
    structural projection, etc.

    Parameters
    ----------
    existing, candidate:
        The two payloads to compare. ``str`` is compared as text; ``bytes`` is
        compared raw on the default path and decoded as UTF-8 when a ``strip``
        projection is in play.
    volatile_keys:
        Keys handed to the ``strip`` projection. Ignored on the default path.
    strip:
        Optional volatile-field projection. ``None`` ⇒ pure byte/text compare.
    """
    if strip is None:
        return _as_bytes(existing) == _as_bytes(candidate)
    existing_text = _as_text(existing)
    candidate_text = _as_text(candidate)
    return strip(existing_text, volatile_keys) == strip(candidate_text, volatile_keys)


def _as_bytes(value: str | bytes) -> bytes:
    return value.encode("utf-8") if isinstance(value, str) else value


def _as_text(value: str | bytes) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else value
