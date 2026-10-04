"""Focused tests for the extracted ``tasks_move_task_hops`` seam (#5629)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from specify_cli.cli.commands.agent import tasks_move_task_hops
from specify_cli.status import Lane

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    ("lane", "expected"),
    [
        (Lane.CLAIMED, "implementer"),
        (Lane.IN_REVIEW, "reviewer"),
        (Lane.APPROVED, "reviewer"),
        (Lane.DONE, "reviewer"),
        (Lane.PLANNED, None),
        (Lane.IN_PROGRESS, None),
        (Lane.FOR_REVIEW, None),
        ("claimed", "implementer"),
        ("in_review", "reviewer"),
        ("blocked", None),
    ],
)
def test_binding_role_for_lane(lane: Lane | str, expected: str | None) -> None:
    assert tasks_move_task_hops._binding_role_for_lane(lane) == expected


@pytest.mark.parametrize(
    ("emit_ref", "target", "result", "expected"),
    [
        ("plan-ref", Lane.APPROVED, SimpleNamespace(reference="r1"), "plan-ref"),
        (None, Lane.APPROVED, SimpleNamespace(reference="r1"), "r1"),
        (None, Lane.DONE, SimpleNamespace(reference="r2"), "r2"),
        (None, Lane.APPROVED, None, None),
        (None, Lane.PLANNED, SimpleNamespace(reference="r1"), None),
        (None, Lane.APPROVED, SimpleNamespace(reference="   "), None),
        (None, Lane.APPROVED, SimpleNamespace(reference=7), None),
    ],
)
def test_hop_review_ref(emit_ref: str | None, target: str, result: object, expected: str | None) -> None:
    assert tasks_move_task_hops._mt_hop_review_ref(emit_ref, target, result) == expected  # type: ignore[arg-type]
