"""Named gate-handler registry (WP04, mission
``doctrine-controlled-transition-gates-01KY51Z7``, epic #2535 half A).

Delivers FR-004: transitions no longer reach a hardcoded call to
``evaluate_pre_review_gate`` — they look up a named handler in
``GATE_REGISTRY`` instead. This mirrors the shape of the ``GUARD_REGISTRY``
that lived in the retired ``mission_v1/guards.py`` (see git history before
mission ``dead-port-disposition-01M1TZVN``): a module-level
``dict[str, ...]`` plus a lookup helper that raises a clear error naming the
missing key and the known keys.

This module is **pure indirection** for half A: exactly one handler is
registered (the incumbent Spec-Kitty pre-review engine), and dispatching it
reproduces the current :class:`~specify_cli.review.pre_review_gate.GateVerdict`
byte-for-byte. It introduces no aggregation, precedence, or block/terminal
logic — that is owned by WP08's ``aggregate_verdicts`` and WP09's inverted
hook. Wiring this registry into the live transition path (replacing the
hardcoded call in ``tasks_move_task_gates.py``) is WP09's responsibility, not
this module's.

``TransitionGateContext`` (data-model.md §8) has its **single home** here —
WP06 (binding resolution) and WP09 (the inverted hook) import it from this
module; they must never redeclare it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from specify_cli.review.pre_review_gate import _DEFAULT_HEAD_RUN_TIMEOUT, evaluate_pre_review_gate

if TYPE_CHECKING:
    from specify_cli.review.baseline import BaselineTestResult
    from specify_cli.review.pre_review_gate import GateStatusObserver, GateVerdict
    from specify_cli.review.scope_source import ScopeSource
    from specify_cli.status.models import Lane

# ``GATE_REGISTRY`` is the module-internal registry table; cross-module callers
# reach handlers through ``get_gate_handler`` (the lookup facade), so the dict
# itself is not exported. Its contents are still exercised directly by tests.
__all__ = [
    "GateHandler",
    "TransitionGateContext",
    "get_gate_handler",
]

# Hoisted per Sonar S1192 (repeated literal, referenced by both the handler
# registration below and the review contract's ``gates`` binding, WP05).
_SPEC_KITTY_PRE_REVIEW_HANDLER_NAME = "spec-kitty-pre-review"
_IN_PROGRESS_TO_FOR_REVIEW_EDGE = "in_progress->for_review"


@dataclass(frozen=True)
class TransitionGateContext:
    """The shared, per-transition payload passed to every ``GateHandler.run``.

    Single home (WP04-owned, data-model.md §8): WP06/WP09 import this type,
    they never redeclare it. Carries the shared inputs a handler needs so it
    resolves nothing itself (NFR-005) — the changed-files SSOT, the
    activation-selected :class:`~specify_cli.review.scope_source.ScopeSource`,
    the captured baseline, the repo root, the ``--force`` flag, and the lane
    edge being gated.
    """

    changed_files: tuple[str, ...]
    scope_source: ScopeSource
    baseline: BaselineTestResult | None
    repo_root: Path
    force: bool
    from_lane: Lane
    to_lane: Lane
    status_observer: GateStatusObserver | None = None
    timeout: float = _DEFAULT_HEAD_RUN_TIMEOUT


@dataclass(frozen=True)
class GateHandler:
    """A named, edge-scoped gate handler.

    ``name`` is the ``GATE_REGISTRY`` key; ``edge`` is the ``"<from>-><to>"``
    lane-edge key the handler is bound to (data-model.md §3/§6); ``run`` is
    the callable the handler dispatches through — the canonical form is
    ``get_gate_handler(name).run(ctx)``, never a bare
    ``GATE_REGISTRY[name](ctx)``.

    A handler's ``run`` MUST be pure-ish and self-contained: it never calls
    ``Exit()`` and never aggregates multiple verdicts — exit and aggregation
    belong to the hook (WP09) and ``aggregate_verdicts`` (WP08). It always
    returns a :class:`~specify_cli.review.pre_review_gate.GateVerdict`, even
    for a blocking-shaped outcome; deciding whether that outcome blocks the
    transition is the hook's job, not the handler's.
    """

    name: str
    edge: str
    run: Callable[[TransitionGateContext], GateVerdict]


def _spec_kitty_pre_review_handler(ctx: TransitionGateContext) -> GateVerdict:
    """Wrap the post-WP03 ``evaluate_pre_review_gate`` as a named handler.

    A strangler adapter, not a re-implementation: it unpacks
    ``TransitionGateContext`` and delegates straight to
    ``evaluate_pre_review_gate`` with the WP03 injected-``ScopeSource``
    surface, returning its verdict unchanged. It does not catch-and-swallow
    exceptions and does not call ``Exit()`` — fail-open handling and
    exit/aggregation are the hook's concern (WP09/WP08).
    """
    return evaluate_pre_review_gate(
        ctx.changed_files,
        repo_root=ctx.repo_root,
        baseline=ctx.baseline,
        scope_source=ctx.scope_source,
        status_observer=ctx.status_observer,
        timeout=ctx.timeout,
    )


GATE_REGISTRY: dict[str, GateHandler] = {
    _SPEC_KITTY_PRE_REVIEW_HANDLER_NAME: GateHandler(
        name=_SPEC_KITTY_PRE_REVIEW_HANDLER_NAME,
        edge=_IN_PROGRESS_TO_FOR_REVIEW_EDGE,
        run=_spec_kitty_pre_review_handler,
    ),
}


def get_gate_handler(name: str) -> GateHandler:
    """Look up a registered handler by name.

    Mirrors the unknown-guard error of ``compile_guards`` in the retired
    ``mission_v1/guards.py`` (git history before mission
    ``dead-port-disposition-01M1TZVN``; it named the missing key AND the
    known keys): an unknown ``name`` is a misconfiguration, and
    the resulting ``KeyError`` names both the missing key and the registered
    ones so the cause is immediately diagnosable.
    """
    try:
        return GATE_REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(sorted(GATE_REGISTRY)) or "(none registered)"
        raise KeyError(f"Unknown gate handler: {name!r}. Registered handlers: {known}") from exc
