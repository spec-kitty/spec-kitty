"""Caching invariants for the readiness coordinator.

Asserts FR-008 (get_readiness never raises, returns no-op default when no cache),
FR-009 (double-invocation returns cached result), and FR-007 (ctx.obj keying).

Mission: cli-startup-readiness-coordinator-skeleton-01KS7JRV
"""

from __future__ import annotations

import sys
from typing import Any

import pytest
import typer

from specify_cli.readiness import (
    AuthStatus,
    ReadinessResult,
    evaluate_readiness,
    get_readiness,
)
from specify_cli.readiness import coordinator as coord_module


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _make_ctx(obj: Any = None) -> typer.Context:
    """Build a minimal typer.Context with a settable ctx.obj."""
    app = typer.Typer()

    @app.callback()
    def _root_cb(ctx: typer.Context) -> None:  # pragma: no cover
        pass

    cmd = typer.main.get_command(app)
    ctx = typer.Context(cmd)
    ctx.obj = obj
    return ctx


# Removed: test_A_hosted_enabled_cached_after_first_call. The hosted-enabled
# coordinator path (SPEC_KITTY_ENABLE_SAAS_SYNC + the auth probe) was removed from
# open-core (#6164): the coordinator is always disabled now, so there is no
# enabled path to cache. The caching invariant itself is unchanged and is covered
# by test_B/test_C below on the (now sole) disabled path.


def test_B_disabled_path_caches_and_invokes_nag_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The (now sole) disabled path still caches and invokes the upgrade nag exactly once."""
    monkeypatch.setattr(sys, "argv", ["spec-kitty", "status"])

    call_count = {"n": 0}

    def _spy_invoke_nag(ctx: typer.Context) -> None:
        call_count["n"] += 1

    monkeypatch.setattr(coord_module, "_invoke_nag", _spy_invoke_nag)

    ctx = _make_ctx()
    first = evaluate_readiness(ctx)
    second = evaluate_readiness(ctx)

    assert call_count["n"] == 1, f"expected 1 nag call, got {call_count['n']}"
    assert first is second
    assert first.enabled is False


def test_C_get_readiness_returns_same_instance_after_evaluate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_readiness returns the cached ReadinessResult by identity."""
    monkeypatch.setattr(sys, "argv", ["spec-kitty"])
    monkeypatch.setattr(coord_module, "_invoke_nag", lambda ctx: None)

    ctx = _make_ctx()
    evaluated = evaluate_readiness(ctx)
    retrieved = get_readiness(ctx)

    assert retrieved is evaluated


def test_D_get_readiness_fresh_ctx_returns_noop_default() -> None:
    """get_readiness on a fresh ctx with no cache returns the no-op default, does not raise."""
    ctx = _make_ctx(obj=None)
    result = get_readiness(ctx)
    assert isinstance(result, ReadinessResult)
    assert result.enabled is False
    assert result.ran is False
    assert result.auth_status == AuthStatus.DISABLED
    assert result.nag_invoked is False


def test_E_get_readiness_non_dict_ctx_obj_returns_noop_default() -> None:
    """get_readiness with a non-dict, non-None ctx.obj returns the no-op default, does not raise."""

    class _Opaque:
        pass

    ctx = _make_ctx(obj=_Opaque())
    result = get_readiness(ctx)
    assert isinstance(result, ReadinessResult)
    assert result.enabled is False
    assert result.ran is False
    assert result.auth_status == AuthStatus.DISABLED
