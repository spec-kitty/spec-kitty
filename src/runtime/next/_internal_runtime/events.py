"""Mission runtime event emission interface and persistence.

Uses canonical event constants and payload models from spec-kitty-events v2.3.1.
"""

# Internalized from spec-kitty-runtime 0.4.3 as part of
# `shared-package-boundary-cutover-01KQ22DS` (mission). See
# `runtime-standalone-package-retirement-01KQ20Z8` for the upstream
# public-API inventory.
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from spec_kitty_events.mission_next import (
    DECISION_INPUT_ANSWERED,
    DECISION_INPUT_REQUESTED,
    MISSION_RUN_COMPLETED,
    MISSION_RUN_STARTED,
    NEXT_STEP_AUTO_COMPLETED,
    NEXT_STEP_ISSUED,
    DecisionInputAnsweredPayload,
    DecisionInputRequestedPayload,
    MissionRunCompletedPayload,
    MissionRunStartedPayload,
    NextStepAutoCompletedPayload,
    NextStepIssuedPayload,
)
# WP04 (org-doctrine-profile-integrity-closeout, T014): these two payloads
# are imported for use as annotations on the emitter Protocol/impl below
# (``emit_significance_evaluated`` / ``emit_decision_timeout_expired``).
# They are intentionally NOT re-exported in ``__all__`` — consumers resolve
# the canonical payloads from ``significance.py`` directly. Keeping these
# imports (annotation-only) while dropping them from ``__all__`` clears the
# dead-symbol gate without breaking any annotation.
from runtime.next._internal_runtime.significance import (
    SignificanceEvaluatedPayload,
    TimeoutExpiredPayload,
)
# Layer note (dead-port-disposition-01M1VRA2, research R-5): ``runtime`` may import
# ``specify_cli.*`` except ``specify_cli.cli`` / ``specify_cli.next``; both ``core``
# and ``mission_metadata`` are already on the runtime outbound ledger
# (``tests/architectural/test_layer_rules.py``), so these add no ledger entry.
from specify_cli.core.env import moment_handlers_disabled_reason
from specify_cli.mission_metadata import resolve_mission_identity

# Explicit re-exports so `from runtime.next._internal_runtime.events import X`
# resolves under `mypy --strict` (otherwise `attr-defined` flags the indirected names).
__all__ = [
    "DECISION_INPUT_ANSWERED",
    "DECISION_INPUT_REQUESTED",
    "MISSION_RUN_COMPLETED",
    "MISSION_RUN_STARTED",
    "NEXT_STEP_AUTO_COMPLETED",
    "NEXT_STEP_ISSUED",
    "DecisionInputAnsweredPayload",
    "DecisionInputRequestedPayload",
    "MissionRunCompletedPayload",
    "MissionRunStartedPayload",
    "NextStepAutoCompletedPayload",
    "NextStepIssuedPayload",
    "RuntimeEventEmitter",
    "NullEmitter",
    "JsonlEventLog",
    "seed_runtime_emitter",
    "runtime_emitter_for_mission",
    "register_runtime_emitter_factory",
    "reset_runtime_emitter_factory",
]


# ---------------------------------------------------------------------------
# RuntimeEventEmitter protocol
# ---------------------------------------------------------------------------

class RuntimeEventEmitter(Protocol):
    """Interface for mission runtime event emission.

    All emit methods accept a single canonical payload model from
    spec-kitty-events.mission_next.
    """

    def emit_mission_run_started(self, payload: MissionRunStartedPayload) -> None: ...

    def emit_next_step_issued(self, payload: NextStepIssuedPayload) -> None: ...

    def emit_next_step_auto_completed(self, payload: NextStepAutoCompletedPayload) -> None: ...

    def emit_decision_input_requested(self, payload: DecisionInputRequestedPayload) -> None: ...

    def emit_decision_input_answered(self, payload: DecisionInputAnsweredPayload) -> None: ...

    def emit_mission_run_completed(self, payload: MissionRunCompletedPayload) -> None: ...

    def emit_significance_evaluated(self, payload: SignificanceEvaluatedPayload) -> None: ...

    def emit_decision_timeout_expired(self, payload: TimeoutExpiredPayload) -> None: ...


def seed_runtime_emitter(emitter: RuntimeEventEmitter, snapshot: Any) -> None:
    """Seed optional producer state without affecting mission control flow.

    Protocol-only products need no hook. Lookup and invocation failures are
    logged and ignored, including when a decision-log wrapper delegates inward.
    """
    try:
        seed = getattr(emitter, "seed_from_snapshot", None)
        if seed is not None:
            seed(snapshot)
    except Exception as exc:  # noqa: BLE001 — optional instrumentation must not alter mission state
        logging.getLogger(__name__).warning("Failed to seed runtime emitter from snapshot: %s", exc)


# ---------------------------------------------------------------------------
# NullEmitter (no-op default)
# ---------------------------------------------------------------------------

class NullEmitter:
    """No-op emitter — default when no concrete emitter is provided.

    Also the null object the runtime emitter seam returns (see
    :func:`runtime_emitter_for_mission`). Nothing here may raise: emission is
    fire-and-forget instrumentation, never control flow.
    """

    def __init__(
        self,
        correlation_id: str = "",
        *,
        mission_slug: str = "",
        mission_type: str = "",
        mission_id: str | None = None,
    ) -> None:
        self.correlation_id = correlation_id
        self.mission_slug = mission_slug
        self.mission_type = mission_type
        self.mission_id = mission_id

    @classmethod
    def for_mission(
        cls,
        *,
        feature_dir: Path,
        mission_slug: str,
        mission_type: str,
    ) -> NullEmitter:
        """Build the null seam for one mission, resolving its ULID when possible."""
        try:
            mission_id: str | None = resolve_mission_identity(feature_dir).mission_id
        except Exception:  # noqa: BLE001 — identity is informational; the seam must never raise
            mission_id = None
        return cls(mission_slug=mission_slug, mission_type=mission_type, mission_id=mission_id)

    def seed_from_snapshot(self, snapshot: Any) -> None:
        """No-op: the null seam carries no phase state to seed."""
        del snapshot

    def emit_mission_run_started(self, payload: MissionRunStartedPayload) -> None:
        pass

    def emit_next_step_issued(self, payload: NextStepIssuedPayload) -> None:
        pass

    def emit_next_step_auto_completed(self, payload: NextStepAutoCompletedPayload) -> None:
        pass

    def emit_decision_input_requested(self, payload: DecisionInputRequestedPayload) -> None:
        pass

    def emit_decision_input_answered(self, payload: DecisionInputAnsweredPayload) -> None:
        pass

    def emit_mission_run_completed(self, payload: MissionRunCompletedPayload) -> None:
        pass

    def emit_significance_evaluated(self, payload: SignificanceEvaluatedPayload) -> None:
        pass

    def emit_decision_timeout_expired(self, payload: TimeoutExpiredPayload) -> None:
        pass


# ---------------------------------------------------------------------------
# Runtime emitter seam (factory + registry)
# ---------------------------------------------------------------------------
#
# This is the E3 *producer* seam for the six ``mission_next`` runtime moments
# (mission run started/completed, next step issued/auto-completed, decision
# input requested/answered). With no producer registered the seam returns
# :class:`NullEmitter`, so the bridge's instrumentation points survive intact.
#
# The live producer (#3929) is
# ``specify_cli.events.runtime_moments.RuntimeMomentProducer``. It is
# registered by ``specify_cli.status.adapters.ensure_zeitgeist_moment_handlers``
# under the moment-handler gate (#3980: ``SPEC_KITTY_NO_MOMENT_HANDLERS``, the
# kill switch, or the deprecated ``SPEC_KITTY_SYNC_MINIMAL_IMPORT`` alias) and
# publishes each moment through that module's lifecycle fan-out slot. The
# status package loads before the bridge first calls
# :func:`runtime_emitter_for_mission`, so a normal CLI process always has it.
#
# Governing ADR: ``docs/adr/3.x/2026-09-06-2-runtime-event-emitter-disposition.md``.

class RuntimeEmitterFactory(Protocol):
    """A producer factory: keyword-only mission identity in, a conforming emitter out.

    Typed as a keyword ``Protocol`` rather than ``Callable[..., ...]`` so a
    factory whose product does not satisfy :class:`RuntimeEventEmitter` is a
    static type error at the registration call, while the seam itself still
    passes the product through unmodified (S3).
    """

    def __call__(self, *, feature_dir: Path, mission_slug: str, mission_type: str) -> RuntimeEventEmitter: ...

_registered_factory: RuntimeEmitterFactory | None = None


def _callable_key(fn: Callable[..., Any]) -> str:
    """Return a stable identity key for a registered callable.

    Mirrors ``specify_cli.invocation.adapters._callable_key`` (this module
    may not import from ``specify_cli.invocation`` -- see the enforced layer
    chain in ``tests/architectural/test_layer_rules.py`` -- so the helper is
    duplicated locally rather than imported). Uses ``__module__`` +
    ``__qualname__`` (falling back to ``__name__``) so that the same logical
    callable compares equal across module reloads *and* across repeated
    attribute access on a classmethod, which mints a fresh bound-method
    object every time (``Producer.for_mission is Producer.for_mission`` is
    ``False``).
    """
    module = getattr(fn, "__module__", None)
    qualname = getattr(fn, "__qualname__", None)
    name = qualname if isinstance(qualname, str) else getattr(fn, "__name__", None)
    if isinstance(module, str) and isinstance(name, str):
        return f"{module}.{name}"
    if isinstance(name, str):
        return name
    return repr(fn)


def register_runtime_emitter_factory(factory: RuntimeEmitterFactory) -> None:
    """Register the runtime producer factory (the E3 producer is registered by the status seam).

    The callable must accept ``feature_dir``, ``mission_slug`` and
    ``mission_type`` as keywords and return an object satisfying
    :class:`RuntimeEventEmitter`.

    Policy: reject-on-conflict. Two producers racing to register here would
    otherwise resolve silently by import order -- whichever registers first
    (or last, under a last-writer-wins policy) wins with no diagnosis of the
    other -- so this fails closed with ``RuntimeError`` instead, forcing the
    conflict to surface at the point it happens. That policy is the in-repo
    precedent set by ``kernel.glossary_runner.register``. The *comparison*
    it runs, however, is keyed on ``__module__`` + ``__qualname__`` (see
    :func:`_callable_key`, mirroring ``specify_cli.invocation.adapters.
    _callable_key``) rather than object identity: ``glossary_runner``
    registers a *class*, whose identity is stable across accesses, but this
    seam's own documented registration form (``MyProducer.for_mission``, a
    classmethod) is not -- every attribute access mints a fresh bound-method
    object, so an identity check would treat a benign re-import as a
    conflicting registrant. Re-registering the same logical callable (by
    key) rebinds the slot to the newest object and returns; registering a
    genuinely different callable while one is already registered raises
    ``RuntimeError``; a non-callable argument raises ``TypeError``.
    """
    global _registered_factory
    if not callable(factory):
        raise TypeError(f"factory must be callable, got {type(factory)!r}")
    new_key = _callable_key(factory)
    if _registered_factory is not None:
        existing_key = _callable_key(_registered_factory)
        if existing_key == new_key:
            # Idempotent: same logical callable re-registered (e.g. a
            # classmethod re-accessed, or a module re-import) rebinds the
            # slot to the newest object rather than raising.
            logging.getLogger(__name__).debug("register_runtime_emitter_factory: rebinding %s", new_key)
            _registered_factory = factory
            return
        raise RuntimeError(f"A different runtime emitter factory is already registered: {_registered_factory!r}. Cannot register {factory!r}.")
    _registered_factory = factory


def reset_runtime_emitter_factory() -> None:
    """Restore the default (null) seam; test-only utility, mirrors ``reset_handlers()``."""
    global _registered_factory
    _registered_factory = None


def runtime_emitter_for_mission(
    *,
    feature_dir: Path,
    mission_slug: str,
    mission_type: str,
) -> RuntimeEventEmitter:
    """Return the mission's runtime emitter seam.

    Under the moment-handler gate (#3980: ``SPEC_KITTY_NO_MOMENT_HANDLERS``,
    the ``SPEC_KITTY_SYNC_DISABLE`` kill switch, or the deprecated
    ``SPEC_KITTY_SYNC_MINIMAL_IMPORT`` alias, resolved by
    :func:`specify_cli.core.env.moment_handlers_disabled_reason`) the null
    seam is returned
    unconditionally and the registered factory is not called (S2). Otherwise
    the registered factory wins (S3); with none registered the null seam is
    returned (S1). The env gate is read at call time so tests can toggle it
    without reloading this module.

    A registered factory that raises degrades to the null seam rather than
    propagating: ``NullEmitter``'s own docstring rule -- "Nothing here may
    raise: emission is fire-and-forget instrumentation, never control flow"
    -- applies to the seam as a whole, and an uncaught factory-constructor
    exception would otherwise kill the caller (e.g. ``spec-kitty next``)
    instead of degrading gracefully. The failure is logged at WARNING, not
    silent.
    """
    if moment_handlers_disabled_reason() is not None:
        return NullEmitter.for_mission(
            feature_dir=feature_dir, mission_slug=mission_slug, mission_type=mission_type
        )
    if _registered_factory is not None:
        try:
            return _registered_factory(
                feature_dir=feature_dir, mission_slug=mission_slug, mission_type=mission_type
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "runtime_emitter_for_mission: registered factory %r raised; degrading to NullEmitter",
                _registered_factory,
                exc_info=True,
            )
            return NullEmitter.for_mission(
                feature_dir=feature_dir, mission_slug=mission_slug, mission_type=mission_type
            )
    return NullEmitter.for_mission(
        feature_dir=feature_dir, mission_slug=mission_slug, mission_type=mission_type
    )


# ---------------------------------------------------------------------------
# JsonlEventLog (append-only JSONL persistence)
# ---------------------------------------------------------------------------

class JsonlEventLog:
    """Append-only JSONL log. Writes dicts with sort_keys for determinism.

    Runtime-local debug/audit log. Payload dicts match canonical payload
    model shapes but do not use the full Event envelope (event_id,
    lamport_clock, etc.) — that is a cross-repo concern for a later version.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def append(self, record: dict[str, Any]) -> None:
        """Append a single record as a JSON line."""
        line = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str)
        with open(self._path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        """Read all records from the log file."""
        if not self._path.exists():
            return []
        records: list[dict[str, Any]] = []
        with open(self._path, encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    records.append(json.loads(stripped))
        return records
