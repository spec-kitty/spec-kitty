"""Fan-out adapter registry for status events.

Provides a decoupled callback boundary so that status/emit.py does not
need to depend on any transport. Handlers are registered into the slots
below by whichever subsystem owns a transport. The default wiring (this
module's import tail) installs the Zeitgeist moment handler (#8), the
sole occupant of these registries since the sync package was deleted
(#5/#114); that tail honours the moment-handler gate
(:func:`specify_cli.core.env.moment_handlers_disabled_reason` —
``SPEC_KITTY_NO_MOMENT_HANDLERS``, the ``SPEC_KITTY_SYNC_DISABLE`` kill
switch, or the deprecated ``SPEC_KITTY_SYNC_MINIMAL_IMPORT`` alias, #3980).

All fire_* functions are non-raising: exceptions from individual
handlers are caught and logged, never re-raised to the caller. An empty
registry is a no-op.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from collections.abc import Callable
from typing import Any

from specify_cli.core.env import moment_handlers_disabled_reason

# The E3 Zeitgeist moment handler (#8): the default occupant of the three
# fan-out slots since the sync transport (which registered its own handlers)
# was deleted. Module-level import so registration below is a plain function
# call, never an import side effect hidden in another package's init.
from .zeitgeist_bridge import (
    lifecycle_moment_handler,
    resolved_binding_moment_handler,
    saas_moment_handler,
)

logger = logging.getLogger(__name__)

# Wall-time bound (seconds) for a single SaaS/lifecycle fan-out handler. The
# fan-out contract is "SaaS failures never block canonical persistence" — a
# guarantee that must cover a *hanging* handler (e.g. the sync daemon polling a
# stopped daemon with a large offline-queue backlog), not just a raising one.
# Handlers run in a short-lived daemon thread joined with this timeout; on
# timeout the caller (canonical persistence) proceeds and the worker is left to
# unwind on its own. Generous enough for a legitimate enqueue; a non-positive
# value runs handlers inline (legacy behaviour / opt-out).
_DEFAULT_SAAS_FANOUT_TIMEOUT_S = 10.0
_SAAS_FANOUT_TIMEOUT_ENV = "SPEC_KITTY_SAAS_FANOUT_TIMEOUT"


def _saas_fanout_timeout_s() -> float:
    """Resolve the per-handler fan-out timeout from the environment.

    Non-finite values (``nan``/``inf``) are rejected: ``Thread.join(nan)``
    raises immediately (defeating the bound) and ``join(inf)`` overflows
    platform time — both would silently disable the safety mechanism, so they
    fall back to the default.
    """
    raw = os.environ.get(_SAAS_FANOUT_TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return _DEFAULT_SAAS_FANOUT_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        return _DEFAULT_SAAS_FANOUT_TIMEOUT_S
    if math.isnan(value) or math.isinf(value):
        return _DEFAULT_SAAS_FANOUT_TIMEOUT_S
    return value


class _FanoutHandlerBusyError(RuntimeError):
    """A prior invocation of this handler is still running (orphaned past its timeout)."""


# Handler-identity keys whose bounded worker has not yet returned. A handler
# that hangs past its timeout stays here until its orphaned worker finally
# unwinds, so a later fan-out for the same handler is skipped rather than
# overlapped — this caps orphan threads at one per handler and prevents two
# live invocations from concurrently touching the handler's non-atomic writers
# (e.g. the Lamport clock / offline queue). Only relevant in a long-lived
# process (a daemon); one-shot CLI processes exit before it matters.
_inflight_fanout_handlers: set[str] = set()
_inflight_lock = threading.Lock()


def _run_fanout_handler_bounded(handler: Callable[..., None], kwargs: dict[str, Any], *, label: str) -> None:
    """Run one fan-out handler with a wall-time bound.

    Raises ``TimeoutError`` if the handler outlives the configured timeout, or
    ``_FanoutHandlerBusyError`` if a prior invocation of the same handler is
    still in flight, so the caller can log and move on; re-raises any handler
    exception so the existing per-handler ``except`` keeps catching it. A
    non-positive timeout runs the handler inline (no thread), preserving legacy
    behaviour.
    """
    timeout_s = _saas_fanout_timeout_s()
    if timeout_s <= 0:
        handler(**kwargs)
        return

    key = _handler_key(handler)
    with _inflight_lock:
        if key in _inflight_fanout_handlers:
            raise _FanoutHandlerBusyError(f"{label} handler still in flight")
        _inflight_fanout_handlers.add(key)

    error: list[Exception] = []

    def _target() -> None:
        try:
            handler(**kwargs)
        except Exception as exc:  # mirror the caller's per-handler catch
            error.append(exc)
        finally:
            with _inflight_lock:
                _inflight_fanout_handlers.discard(key)

    worker = threading.Thread(target=_target, name=f"{label}-handler", daemon=True)
    worker.start()
    worker.join(timeout_s)
    if worker.is_alive():
        # Leave `key` in-flight: the orphaned worker clears it on unwind, which
        # is what suppresses an overlapping invocation until then.
        raise TimeoutError(f"{label} handler exceeded {timeout_s:.1f}s")
    if error:
        raise error[0]


# Callback signature: keyword-only, mirrors emit_wp_status_changed
SaasFanOutHandler = Callable[..., None]

LifecycleSaasFanOutHandler = Callable[..., None]

# Callback signature: keyword-only, carries the resolved binding + WP identity
# for the first-class ``WPResolvedBindingChanged`` bridge (FR-015 / IC-09).
ResolvedBindingFanOutHandler = Callable[..., None]

_saas_handlers: list[SaasFanOutHandler] = []
_lifecycle_saas_handlers: list[LifecycleSaasFanOutHandler] = []
_resolved_binding_handlers: list[ResolvedBindingFanOutHandler] = []


def _handler_key(cb: Callable[..., Any]) -> str:
    """Return a stable identity key for a registered handler.

    Uses ``__module__`` + ``__qualname__`` (falling back to ``__name__``)
    so that the same logical handler is treated as identical across
    module reloads that produce fresh function objects.
    """
    module = getattr(cb, "__module__", None)
    qualname = getattr(cb, "__qualname__", None)
    name = qualname if isinstance(qualname, str) else getattr(cb, "__name__", None)
    if isinstance(module, str) and isinstance(name, str):
        return f"{module}.{name}"
    if isinstance(name, str):
        return name
    return repr(cb)


def register_saas_fanout_handler(cb: SaasFanOutHandler) -> None:
    """Register a SaaS fan-out callback (idempotent by qualified name).

    Re-registration of a handler with the same ``__qualname__`` replaces
    the existing entry rather than appending, so re-registering does not
    stack duplicate fan-out invocations.
    """
    key = _handler_key(cb)
    for idx, existing in enumerate(_saas_handlers):
        if _handler_key(existing) == key:
            _saas_handlers[idx] = cb
            return
    _saas_handlers.append(cb)


def register_lifecycle_saas_fanout_handler(cb: LifecycleSaasFanOutHandler) -> None:
    """Register a lifecycle SaaS fan-out callback (idempotent by qualified name)."""
    key = _handler_key(cb)
    for idx, existing in enumerate(_lifecycle_saas_handlers):
        if _handler_key(existing) == key:
            _lifecycle_saas_handlers[idx] = cb
            return
    _lifecycle_saas_handlers.append(cb)


def register_resolved_binding_fanout_handler(cb: ResolvedBindingFanOutHandler) -> None:
    """Register a ``WPResolvedBindingChanged`` fan-out callback (idempotent by name).

    Mirrors :func:`register_saas_fanout_handler`. The Zeitgeist moment handler
    builds the concrete ``spec_kitty_events.WPResolvedBindingChanged`` payload
    once the events package ships it; until then the status layer's version
    gate skips the fan-out (see ``emit._resolved_binding_fan_out``).
    """
    key = _handler_key(cb)
    for idx, existing in enumerate(_resolved_binding_handlers):
        if _handler_key(existing) == key:
            _resolved_binding_handlers[idx] = cb
            return
    _resolved_binding_handlers.append(cb)


def ensure_zeitgeist_moment_handlers() -> None:
    """Register the Zeitgeist moment handlers into all three fan-out slots.

    Idempotent: the ``register_*`` functions de-duplicate by qualified name,
    so calling this repeatedly is safe. This is the E3 (#8) default wiring of
    these slots — the sole default occupant since the sync package was
    deleted (#5/#114) — and, per the egress-consent precedent, it lives where
    the answer is needed rather than in some other package's init. The
    import tail calls it once; tests that wipe the registry via
    :func:`reset_handlers` call it again to restore production wiring.
    """
    register_saas_fanout_handler(saas_moment_handler)
    register_lifecycle_saas_fanout_handler(lifecycle_moment_handler)
    register_resolved_binding_fanout_handler(resolved_binding_moment_handler)
    # E3 (#3929): the runtime-moment producer publishes through the lifecycle
    # slot above, so it rides the same gate and the same restore hook. The
    # registry is idempotent by qualified name. Imported here, not at module
    # top, so the status package never imports the runtime seam while it is
    # still initialising.
    from runtime.next._internal_runtime.events import register_runtime_emitter_factory  # noqa: PLC0415
    from specify_cli.events.runtime_moments import RuntimeMomentProducer  # noqa: PLC0415

    register_runtime_emitter_factory(RuntimeMomentProducer.for_mission)


def reset_handlers() -> None:
    """Clear all registered handlers (test-only utility).

    Clears the Zeitgeist moment handlers too; a test that wipes the registry
    and wants the production wiring back calls
    :func:`ensure_zeitgeist_moment_handlers` (the status conftest does exactly
    that around every test, so one test's wipe cannot silence another's
    fan-out).
    """
    _saas_handlers.clear()
    _lifecycle_saas_handlers.clear()
    _resolved_binding_handlers.clear()


def _fanout_force(kwargs: dict[str, Any]) -> Any:
    """Resolve the force flag for the #1141 breadcrumb.

    Duck-typed and best-effort: lifecycle / other-event callers pass ``force``
    as a top-level kwarg, while WPStatusChanged producers bundle the optional
    tail (including ``force``) into a ``metadata`` params object. Read whichever
    is present so the diagnostic breadcrumb keeps surfacing the flag; never
    raise.
    """
    if "force" in kwargs:
        return kwargs["force"]
    return getattr(kwargs.get("metadata"), "force", None)


def fire_saas_fanout(**kwargs: Any) -> None:
    """Call all registered SaaS fan-out handlers with **kwargs.

    Guarantees:
    - Handlers called in registration order.
    - Exceptions are caught per handler, logged at WARNING level, and
      never propagate to the caller.
    - If no handlers are registered, this is a no-op.

    Logs an INFO-level entry breadcrumb (issue #1141) so silent fan-out
    failures on review-rejection / backward-rewind transitions are
    correlatable with the originating canonical event in operator logs.
    The breadcrumb identifies the WP, lane delta, and force flag; the
    full kwargs are NOT logged (PII / payload-size reasons).
    """
    # Diagnostic breadcrumb (issue #1141). Cheap dict.get() calls avoid
    # raising if the caller drops a key; the breadcrumb is best-effort and
    # never blocks fan-out. Log even with zero handlers; a missing handler
    # registration is one of the states this breadcrumb is meant to reveal.
    logger.info(
        "fire_saas_fanout: wp_id=%s from=%s to=%s force=%s handlers=%d",
        kwargs.get("wp_id"),
        kwargs.get("from_lane"),
        kwargs.get("to_lane"),
        _fanout_force(kwargs),
        len(_saas_handlers),
    )
    for handler in _saas_handlers:
        try:
            _run_fanout_handler_bounded(handler, kwargs, label="SaaS fan-out")
        except _FanoutHandlerBusyError:
            logger.warning(
                "SaaS fan-out handler still in flight from a prior transition; skipped to avoid overlap (wp_id=%s from=%s to=%s)",
                kwargs.get("wp_id"),
                kwargs.get("from_lane"),
                kwargs.get("to_lane"),
            )
        except TimeoutError:
            logger.warning(
                "SaaS fan-out handler timed out; canonical status log unaffected (wp_id=%s from=%s to=%s force=%s)",
                kwargs.get("wp_id"),
                kwargs.get("from_lane"),
                kwargs.get("to_lane"),
                _fanout_force(kwargs),
            )
        except Exception:
            logger.warning(
                "SaaS fan-out handler failed; canonical status log unaffected (wp_id=%s from=%s to=%s force=%s)",
                kwargs.get("wp_id"),
                kwargs.get("from_lane"),
                kwargs.get("to_lane"),
                _fanout_force(kwargs),
                exc_info=True,
            )


def fire_resolved_binding_fanout(**kwargs: Any) -> None:
    """Call all registered ``WPResolvedBindingChanged`` fan-out handlers with **kwargs.

    Same non-raising / bounded contract as :func:`fire_saas_fanout`: exceptions
    from a handler are caught and logged, never re-raised, so a resolved-binding
    fan-out can never block canonical local persistence. An empty registry is a
    no-op. The status layer only reaches here once its version gate confirms the
    installed ``spec_kitty_events`` supports the event (FR-015 / IC-09).
    """
    logger.info(
        "fire_resolved_binding_fanout: wp_id=%s mission_slug=%s handlers=%d",
        kwargs.get("wp_id"),
        kwargs.get("mission_slug"),
        len(_resolved_binding_handlers),
    )
    for handler in _resolved_binding_handlers:
        try:
            _run_fanout_handler_bounded(handler, kwargs, label="Resolved-binding fan-out")
        except _FanoutHandlerBusyError:
            logger.warning(
                "Resolved-binding fan-out handler still in flight from a prior emit; skipped to avoid overlap (wp_id=%s)",
                kwargs.get("wp_id"),
            )
        except TimeoutError:
            logger.warning(
                "Resolved-binding fan-out handler timed out; canonical status log unaffected (wp_id=%s)",
                kwargs.get("wp_id"),
            )
        except Exception:
            logger.warning(
                "Resolved-binding fan-out handler failed; canonical status log unaffected (wp_id=%s)",
                kwargs.get("wp_id"),
                exc_info=True,
            )


def fire_lifecycle_saas_fanout(**kwargs: Any) -> None:
    """Call all registered lifecycle SaaS fan-out handlers with **kwargs."""
    for handler in _lifecycle_saas_handlers:
        try:
            _run_fanout_handler_bounded(handler, kwargs, label="Lifecycle SaaS fan-out")
        except _FanoutHandlerBusyError:
            logger.warning(
                "Lifecycle SaaS fan-out handler still in flight from a prior transition; skipped to avoid overlap",
            )
        except TimeoutError:
            logger.warning(
                "Lifecycle SaaS fan-out handler timed out; canonical lifecycle log unaffected",
            )
        except Exception:
            logger.debug(
                "Lifecycle SaaS fan-out handler failed; canonical lifecycle log unaffected",
                exc_info=True,
            )


# Default wiring: every process that imports this seam carries the Zeitgeist
# moment handler (#3980 launch names). The gate has its own name —
# SPEC_KITTY_NO_MOMENT_HANDLERS means "register no transport at import time"
# — the kill switch SPEC_KITTY_SYNC_DISABLE folds in (a disarmed process
# registers no transport), and the former SPEC_KITTY_SYNC_MINIMAL_IMPORT name
# survives as a deprecated alias that warns once when honored. This is the
# only default registration into these slots. A caller needing an empty
# registry (tests) calls reset_handlers() and restores with
# ensure_zeitgeist_moment_handlers().
if moment_handlers_disabled_reason() is None:
    ensure_zeitgeist_moment_handlers()
