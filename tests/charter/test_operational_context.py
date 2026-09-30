"""Consumed behavior of the operational-context boundary."""

from __future__ import annotations

import pytest

from charter.activation.invocation_context import (
    build_operational_context,
)


pytestmark = pytest.mark.unit


def test_explicit_operational_context_round_trip() -> None:
    """Caller-owned context values survive assembly and guard access."""
    context = build_operational_context(
        active_model="opus",
        active_profile="python-pedro",
        active_role="implementer",
        current_activity="implement",
        tech_stack=frozenset({"python", "pytest"}),
    )

    assert context.active_model == "opus"
    assert context.active_profile == "python-pedro"
    assert context.require_active_role() == "implementer"
    assert context.current_activity == "implement"
    assert context.tech_stack == frozenset({"python", "pytest"})
