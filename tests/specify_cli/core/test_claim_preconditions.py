"""Seam tests for ``core.dependency_graph.ensure_wp_claim_preconditions`` (FR-003, SC-005).

The claim-precondition decision is pure over the reduced status snapshot's
``work_packages`` mapping, so every case here feeds plain dicts: no event log,
no git, no CLI, and nothing patched.
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.core.dependency_graph import ensure_wp_claim_preconditions
from specify_cli.status import WorkPackageStartRejected
from specify_cli.status_lanes import OPERATOR_REASON_SOURCE

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_UNMET = "dependencies_not_satisfied: WP02 depends on {blocked}; all dependencies must be approved or done before implementation can start"


def _wps(**lanes: Any) -> dict[str, dict[str, Any]]:
    """Reduced-snapshot ``work_packages`` mapping from ``WPnn=<lane or state dict>`` pairs."""
    return {wp: (state if isinstance(state, dict) else {"lane": state}) for wp, state in lanes.items()}


def test_genesis_wp_is_rejected_with_the_finalize_tasks_hint() -> None:
    with pytest.raises(WorkPackageStartRejected) as excinfo:
        ensure_wp_claim_preconditions("WP02", [], _wps(WP02="genesis"))

    assert str(excinfo.value) == "WP WP02 is not finalized; run `spec-kitty agent mission finalize-tasks`"


def test_wp_absent_from_the_snapshot_counts_as_genesis() -> None:
    with pytest.raises(WorkPackageStartRejected, match="WP WP09 is not finalized"):
        ensure_wp_claim_preconditions("WP09", [], _wps(WP01="planned"))


def test_unmet_dependency_raises_value_error_with_the_exact_text() -> None:
    with pytest.raises(ValueError, match="dependencies_not_satisfied") as excinfo:
        ensure_wp_claim_preconditions("WP02", ["WP01"], _wps(WP01="in_progress", WP02="planned"))

    assert str(excinfo.value) == _UNMET.format(blocked="WP01")


def test_every_unmet_dependency_is_named_in_declaration_order() -> None:
    wps = _wps(WP01="for_review", WP02="planned", WP03="approved", WP04="blocked")

    with pytest.raises(ValueError, match="dependencies_not_satisfied") as excinfo:
        ensure_wp_claim_preconditions("WP02", ["WP01", "WP03", "WP04"], wps)

    assert str(excinfo.value) == _UNMET.format(blocked="WP01, WP04")


@pytest.mark.parametrize("dep_lane", ["approved", "done"])
def test_approved_or_done_dependencies_pass(dep_lane: str) -> None:
    ensure_wp_claim_preconditions("WP02", ["WP01"], _wps(WP01=dep_lane, WP02="planned"))


def test_no_declared_dependencies_passes_for_a_finalized_wp() -> None:
    ensure_wp_claim_preconditions("WP02", [], _wps(WP02="planned"))


def test_operator_canceled_dependency_counts_as_satisfied() -> None:
    wps = _wps(WP01={"lane": "canceled", "reason_source": OPERATOR_REASON_SOURCE}, WP02="planned")

    ensure_wp_claim_preconditions("WP02", ["WP01"], wps)


def test_synthetic_canceled_dependency_blocks() -> None:
    wps = _wps(WP01={"lane": "canceled", "reason_source": "auto"}, WP02="planned")

    with pytest.raises(ValueError, match="dependencies_not_satisfied: WP02 depends on WP01"):
        ensure_wp_claim_preconditions("WP02", ["WP01"], wps)


def test_state_without_a_lane_key_reads_as_genesis() -> None:
    """Pin: ``state.get("lane", Lane.GENESIS)`` -- an absent key is genesis."""
    with pytest.raises(WorkPackageStartRejected):
        ensure_wp_claim_preconditions("WP02", [], {"WP02": {}})


def test_present_but_falsy_lane_is_not_genesis() -> None:
    """Pin (do not dedupe with ``wp_lanes_from_snapshot``): ``.get("lane", GENESIS)`` keeps a
    present-but-falsy lane (``None`` / ``""``) as-is, where ``str(state.get("lane") or GENESIS)``
    would coerce it to genesis. So the unseeded check passes for the WP itself, and a dependency in
    such a state is simply an unresolvable lane (blocked), never an unseeded rejection.
    """
    ensure_wp_claim_preconditions("WP02", [], {"WP02": {"lane": None}})
    ensure_wp_claim_preconditions("WP02", [], {"WP02": {"lane": ""}})

    with pytest.raises(ValueError, match="dependencies_not_satisfied: WP02 depends on WP01"):
        ensure_wp_claim_preconditions("WP02", ["WP01"], {"WP01": {"lane": None}, "WP02": {"lane": "planned"}})
