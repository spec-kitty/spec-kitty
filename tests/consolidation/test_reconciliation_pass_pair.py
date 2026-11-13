"""One door for the reconciliation PASS anchor and the coordination tip paired with it.

``ConsolidationState.reconciliation_passed_target_sha`` (#5021) and ``coord_tip_after_projection``
(#7491) are written only through pure field mutators on the record, so the pair is cleared, restored,
recorded and advanced in one place. The table pins each mutator's change report and its effect on the
pair; the AST pin fails when a writer outside ``state.py`` assigns either field again.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

import pytest

import specify_cli
from specify_cli.consolidation.state import ConsolidationState

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_PAIR = ("reconciliation_passed_target_sha", "coord_tip_after_projection")


def _state(anchor: str | None, tip: str | None = None) -> ConsolidationState:
    return ConsolidationState(
        mission_id="m",
        mission_slug="m",
        target_branch="main",
        wp_order=["WP01"],
        reconciliation_passed_target_sha=anchor,
        coord_tip_after_projection=tip,
    )


# (id, starting anchor, starting tip, mutation, reported change, resulting anchor, resulting tip)
_CASES: tuple[tuple[str, str | None, str | None, Callable[[ConsolidationState], bool], bool, str | None, str | None], ...] = (
    ("clear-drops-the-pair", "abc", "t1", lambda s: s.clear_reconciliation_pass(), True, None, None),
    ("clear-without-an-anchor", None, None, lambda s: s.clear_reconciliation_pass(), False, None, None),
    ("restore-a-different-anchor", "def", "t1", lambda s: s.restore_reconciliation_pass("abc", "t2"), True, "abc", "t2"),
    ("restore-the-same-pair", "abc", "t1", lambda s: s.restore_reconciliation_pass("abc", "t1"), False, "abc", "t1"),
    ("restore-a-tip-without-an-anchor-keeps-none", None, None, lambda s: s.restore_reconciliation_pass(None, "t1"), False, None, None),
    ("record-sets-both", None, None, lambda s: s.record_reconciliation_pass("abc", "t1"), True, "abc", "t1"),
    ("advance-the-anchor", "abc", "t1", lambda s: s.advance_pass_anchor("def"), True, "def", "t1"),
    ("advance-the-anchor-needs-one", None, None, lambda s: s.advance_pass_anchor("def"), False, None, None),
    ("advance-the-tip", "abc", "t1", lambda s: s.advance_proven_coordination_tip("t2"), True, "abc", "t2"),
    ("advance-the-tip-to-itself", "abc", "t1", lambda s: s.advance_proven_coordination_tip("t1"), False, "abc", "t1"),
    ("advance-the-tip-needs-an-anchor", None, None, lambda s: s.advance_proven_coordination_tip("t2"), False, None, None),
)


@pytest.mark.parametrize(("start_anchor", "start_tip", "mutate", "changed", "anchor", "tip"), [case[1:] for case in _CASES], ids=[case[0] for case in _CASES])
def test_each_mutator_moves_the_pair_and_nothing_else(
    start_anchor: str | None,
    start_tip: str | None,
    mutate: Callable[[ConsolidationState], bool],
    changed: bool,
    anchor: str | None,
    tip: str | None,
) -> None:
    state = _state(start_anchor, start_tip)
    before = state.to_dict()

    assert mutate(state) is changed
    assert (state.reconciliation_passed_target_sha, state.coord_tip_after_projection) == (anchor, tip)
    assert ConsolidationState.from_dict(state.to_dict()) == state
    assert {k: v for k, v in state.to_dict().items() if k not in _PAIR} == {k: v for k, v in before.items() if k not in _PAIR}


def test_record_refuses_an_empty_anchor() -> None:
    with pytest.raises(ValueError, match="must name a target tip"):
        _state(None).record_reconciliation_pass("", "t1")


def _assigns_the_pair(node: ast.AST) -> bool:
    """True for ``<state>.<field> = ...`` (also augmented/annotated) and ``setattr(<state>, "<field>", ...)``."""

    def is_state_receiver(value: ast.expr) -> bool:
        return (isinstance(value, ast.Name) and value.id in ("state", "self")) or (isinstance(value, ast.Attribute) and value.attr == "state")

    if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return any(isinstance(t, ast.Attribute) and t.attr in _PAIR and is_state_receiver(t.value) for t in targets)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "setattr" and len(node.args) >= 2:
        field = node.args[1]
        return is_state_receiver(node.args[0]) and isinstance(field, ast.Constant) and field.value in _PAIR
    return False


def test_nothing_outside_the_record_assigns_the_pair() -> None:
    package = Path(specify_cli.__file__).parent
    owner = package / "consolidation" / "state.py"
    offenders = [
        f"{path.relative_to(package)}:{node.lineno}"
        for path in sorted(package.rglob("*.py"))
        if path != owner
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.stmt | ast.expr) and _assigns_the_pair(node)
    ]

    assert offenders == [], f"write the PASS anchor / coordination tip through the ConsolidationState mutators: {offenders}"
