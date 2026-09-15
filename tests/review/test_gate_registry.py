"""Tests for ``specify_cli.review.gate_registry`` — WP04 of mission
``doctrine-controlled-transition-gates-01KY51Z7`` (epic #2535 half A).

Covers T019: registration (exactly one handler, half-A single-handler
guard), lookup (hit + unknown-name error naming the missing/known keys),
single-handler dispatch parity against a direct ``evaluate_pre_review_gate``
call, and the no-``Exit`` guarantee for a blocking-shaped verdict. ATDD
red-first: authored against the not-yet-written ``gate_registry`` module.

No real git, no real subprocess: the fabricated ``ScopeSource`` below always
reports ``test_command() -> None``, which routes ``evaluate_pre_review_gate``
straight to a deterministic ``NO_COVERAGE`` verdict with no process launch —
fast and hermetic, per the WP04 task notes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from specify_cli.review import gate_registry
from specify_cli.review.gate_registry import (
    GATE_REGISTRY,
    GateHandler,
    TransitionGateContext,
    get_gate_handler,
)
from specify_cli.review.pre_review_gate import GateOutcome, GateVerdict, ScopeResult, evaluate_pre_review_gate
from specify_cli.status.models import Lane

if TYPE_CHECKING:
    from specify_cli.review.baseline import BaselineFailure
    from specify_cli.review.scope_source import RawRunResult

pytestmark = [pytest.mark.fast]

_HANDLER_NAME = "spec-kitty-pre-review"
_EDGE = "in_progress->for_review"


@dataclass(frozen=True)
class _NoCommandScopeSource:
    """A fabricated ``ScopeSource`` that never runs a subprocess.

    ``test_command() -> None`` is the port's own no-config signal
    (FR-012): ``evaluate_pre_review_gate`` routes it straight to a
    deterministic ``NO_COVERAGE`` verdict without launching anything,
    making it ideal for a fast, hermetic dispatch-parity fixture.
    """

    def test_command(self) -> list[str] | None:
        return None

    def file_to_scope(self, path: str) -> tuple[str, ...]:  # noqa: ARG002 - port shape
        return ()

    def parse_results(self, raw: RawRunResult) -> tuple[BaselineFailure, ...]:  # noqa: ARG002 - port shape
        return ()


def _build_context(**overrides: object) -> TransitionGateContext:
    defaults: dict[str, object] = {
        "changed_files": ("src/specify_cli/review/gate_registry.py",),
        "scope_source": _NoCommandScopeSource(),
        "baseline": None,
        "repo_root": Path("."),
        "force": False,
        "from_lane": Lane.IN_PROGRESS,
        "to_lane": Lane.FOR_REVIEW,
    }
    defaults.update(overrides)
    return TransitionGateContext(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Registration (half-A single-handler guard)
# ---------------------------------------------------------------------------


def test_registry_has_exactly_one_handler() -> None:
    """The half-A guard: a second production handler leaking in must fail loudly."""
    assert len(GATE_REGISTRY) == 1


def test_registry_registers_spec_kitty_pre_review_on_the_for_review_edge() -> None:
    handler = GATE_REGISTRY[_HANDLER_NAME]
    assert isinstance(handler, GateHandler)
    assert handler.name == _HANDLER_NAME
    assert handler.edge == _EDGE


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def test_get_gate_handler_returns_the_registered_handler() -> None:
    assert get_gate_handler(_HANDLER_NAME) is GATE_REGISTRY[_HANDLER_NAME]


def test_get_gate_handler_raises_on_unknown_name_naming_missing_and_known_keys() -> None:
    with pytest.raises(KeyError) as exc_info:
        get_gate_handler("not-a-real-handler")

    message = str(exc_info.value)
    assert "not-a-real-handler" in message
    assert _HANDLER_NAME in message


# ---------------------------------------------------------------------------
# Single-handler dispatch parity (T019.3)
# ---------------------------------------------------------------------------


def test_dispatch_reproduces_direct_evaluate_pre_review_gate_call() -> None:
    ctx = _build_context()

    dispatched = GATE_REGISTRY[_HANDLER_NAME].run(ctx)
    direct = evaluate_pre_review_gate(
        ctx.changed_files,
        repo_root=ctx.repo_root,
        baseline=ctx.baseline,
        scope_source=ctx.scope_source,
    )

    assert dispatched == direct
    assert dispatched.outcome is GateOutcome.NO_COVERAGE


def test_dispatch_via_get_gate_handler_matches_direct_registry_access() -> None:
    ctx = _build_context()

    assert get_gate_handler(_HANDLER_NAME).run(ctx) == GATE_REGISTRY[_HANDLER_NAME].run(ctx)


def test_handler_delegates_status_observer_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Registry indirection carries the public renderer seam by identity."""
    canned_verdict = GateVerdict(
        outcome=GateOutcome.NO_COVERAGE,
        scope=ScopeResult.from_override(()),
    )
    observed: list[object] = []

    def observer(event: object) -> None:
        observed.append(event)

    def fake_evaluate(*args: object, **kwargs: object) -> GateVerdict:
        del args
        assert kwargs["status_observer"] is observer
        return canned_verdict

    monkeypatch.setattr(gate_registry, "evaluate_pre_review_gate", fake_evaluate)

    result = get_gate_handler(_HANDLER_NAME).run(_build_context(status_observer=observer))

    assert result is canned_verdict
    assert observed == []


# ---------------------------------------------------------------------------
# No-Exit guarantee (T019.4)
# ---------------------------------------------------------------------------


def test_handler_returns_normally_for_a_new_failures_shaped_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blocking is the hook's job, not the handler's: even a ``NEW_FAILURES``
    verdict must come back as a plain return value, never a ``SystemExit``."""
    canned_verdict = GateVerdict(
        outcome=GateOutcome.NEW_FAILURES,
        scope=ScopeResult(
            test_targets=("tests/review/test_gate_registry.py",),
            matched_shard_groups=(),
            matched_composite_dirs=(),
            empty_cone_composite_dirs=(),
            excluded_scope_files=(),
        ),
        new_failures=(),
    )

    def _fake_evaluate_pre_review_gate(*args: object, **kwargs: object) -> GateVerdict:
        return canned_verdict

    monkeypatch.setattr(gate_registry, "evaluate_pre_review_gate", _fake_evaluate_pre_review_gate)

    ctx = _build_context()
    result = GATE_REGISTRY[_HANDLER_NAME].run(ctx)

    assert result is canned_verdict
    assert result.outcome is GateOutcome.NEW_FAILURES
