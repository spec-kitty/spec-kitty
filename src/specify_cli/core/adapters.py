"""Pending-origin consumer registry for core mission creation.

Provides a result-bearing callable registry so that
``core/mission_creation.py`` can invoke the tracker's pending-origin
consumer without importing the INTEGRATION set (``tracker.*``,
``sync.*``, ``saas.*``).

The registry uses the same idiom as ``status/adapters.py``:

* Idempotent by qualified name — re-registering a handler with the
  same ``__module__.__qualname__`` replaces the existing entry.
* Non-raising — exceptions from the registered consumer are caught;
  the error message is returned in the third tuple element.
* No INTEGRATION imports in this module.
* No third-party imports.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Relative location of the staged pending-origin file (".kittify/pending-origin.yaml").
# A path literal — NOT an import — so CORE can detect a *cold-miss* (a staged
# binding present on disk while no consumer is registered) without importing any
# INTEGRATION package. The hosted ticket-origin staging helper that once owned
# this filename (``tracker.ticket_context``) was removed from open-core with the
# frozen hosted surfaces (#6164) and relocated out of tree; the consume seam
# below stays, and any future producer that writes this file must keep the name
# in lockstep with this constant.
_PENDING_ORIGIN_RELPATH = (".kittify", "pending-origin.yaml")


class PendingOriginConsumerNotRegisteredError(RuntimeError):
    """Raised when a staged pending origin exists but no consumer is registered.

    This is a *cold-miss*: a ``.kittify/pending-origin.yaml`` file is present on
    disk (a ticket binding was staged) but ``consume_pending_origin`` was called
    before any consumer registered itself with the registry — typically because
    a caller invoked ``create_mission_core`` without first importing
    ``specify_cli.tracker`` (whose startup hook performs registration).

    Silently returning the no-pending-origin default in this case would *drop*
    the staged binding without trace. We fail loud instead (fail-closed-loud),
    so the missing ``import specify_cli.tracker`` side-effect surfaces as an
    error at the call site rather than as a vanished ticket link.
    """


# Callable signature:
#   (repo_root, feature_dir, meta) -> (attempted, succeeded, error_msg, updated_meta)
#
# Returns a 4-tuple:
#   attempted  (bool)       — True if a pending origin was found and consumed
#   succeeded  (bool)       — True if the binding completed without error
#   error_msg  (str | None) — error description on failure, None on success
#   updated_meta (dict)     — meta dict, possibly updated with binding data
PendingOriginConsumer = Callable[
    [Path, Path, dict[str, Any]],
    tuple[bool, bool, str | None, dict[str, Any]],
]

_origin_consumer: PendingOriginConsumer | None = None


def _consumer_key(fn: PendingOriginConsumer) -> str:
    """Return a stable identity key for a consumer function."""
    module = getattr(fn, "__module__", None)
    qualname = getattr(fn, "__qualname__", None)
    name = qualname if isinstance(qualname, str) else getattr(fn, "__name__", None)
    if isinstance(module, str) and isinstance(name, str):
        return f"{module}.{name}"
    if isinstance(name, str):
        return name
    return repr(fn)


def register_pending_origin_consumer(fn: PendingOriginConsumer) -> None:
    """Register the pending-origin consumer implementation.

    Idempotent: re-registering the same qualified name replaces the
    existing entry so that re-importing ``tracker/`` (e.g. in test
    processes) does not stack duplicate entries.

    Called once at tracker package startup (``tracker/__init__.py`` or
    ``tracker/origin_consumer.py`` startup hook).
    """
    global _origin_consumer  # noqa: PLW0603
    _origin_consumer = fn
    logger.debug("Registered pending-origin consumer: %s", _consumer_key(fn))


def _pending_origin_present(repo_root: Path) -> bool:
    """Return True if a staged pending-origin file exists under *repo_root*.

    Pure path probe — no INTEGRATION import. Used only to distinguish a benign
    cold-miss (nothing staged) from a correctness-relevant one (a binding is
    staged but no consumer is registered).
    """
    try:
        return repo_root.joinpath(*_PENDING_ORIGIN_RELPATH).is_file()
    except OSError:
        return False


def consume_pending_origin(
    repo_root: Path,
    feature_dir: Path,
    meta: dict[str, Any],
) -> tuple[bool, bool, str | None, dict[str, Any]]:
    """Dispatch to the registered pending-origin consumer.

    When no consumer is registered the behaviour splits on whether a binding
    is actually staged:

    * **No staged file** → returns the safe default ``(False, False, None,
      meta)`` ("no pending origin was found or processed"). This preserves the
      pre-binding behaviour on installations where the tracker package is
      absent or not yet imported.
    * **A ``.kittify/pending-origin.yaml`` file exists** → raises
      :class:`PendingOriginConsumerNotRegisteredError`. Returning the no-op
      default here would silently drop the staged ticket binding; the gate
      guards imports, not registration *timing*, so we fail loud (fail-closed)
      instead of dropping correctness-bearing state.

    Consumer exceptions are caught and returned as
    ``(True, False, str(exc), meta)`` — preserving the non-raising
    contract for the caller.
    """
    if _origin_consumer is None:
        if _pending_origin_present(repo_root):
            raise PendingOriginConsumerNotRegisteredError(
                "A staged pending origin "
                f"({repo_root.joinpath(*_PENDING_ORIGIN_RELPATH)}) exists but no "
                "pending-origin consumer is registered. Ensure "
                "'import specify_cli.tracker' runs before create_mission_core so "
                "the tracker startup hook registers its consumer — otherwise the "
                "staged ticket binding would be silently dropped."
            )
        return False, False, None, meta
    try:
        return _origin_consumer(repo_root, feature_dir, meta)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Pending-origin consumer raised unexpectedly (repo_root=%s): %s",
            repo_root,
            exc,
        )
        return True, False, str(exc), meta


def reset_origin_consumer() -> None:
    """Reset the registry to its initial (empty) state.

    Test-only utility.  Call in test teardown to avoid state bleed
    between test cases.
    """
    global _origin_consumer  # noqa: PLW0603
    _origin_consumer = None
