"""The one claim-sidecar builder and the one planned-release authority (#5781, #7644)."""

from __future__ import annotations

import pytest

from specify_cli.status import claim_policy_metadata
from specify_cli.status.claim_release import planned_claim_release_delta, planned_claim_release_fields
from specify_cli.status.models import ReviewOverride, WPInnerStateDelta

pytestmark = pytest.mark.fast


def test_claim_sidecar_without_a_shell_records_only_the_agent() -> None:
    assert claim_policy_metadata(None, "claude") == {"agent": "claude"}


def test_claim_sidecar_merges_extra_under_the_claim_keys() -> None:
    sidecar = claim_policy_metadata(None, "claude", extra={"orchestrator_id": "orch", "agent": "spoof", "shell_pid": 1})

    assert sidecar == {"orchestrator_id": "orch", "agent": "claude"}


def test_claim_sidecar_with_a_shell_keeps_the_host_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.core.process_liveness as liveness

    monkeypatch.setattr(liveness, "capture_creation_time_baseline", lambda pid: "2026-11-20T00:00:00+00:00")

    assert claim_policy_metadata(42, "claude") == {"shell_pid": 42, "shell_pid_created_at": "2026-11-20T00:00:00+00:00", "agent": "claude"}


def test_planned_release_delta_releases_the_claim_and_clears_the_review_override() -> None:
    delta = planned_claim_release_delta()

    assert isinstance(delta, WPInnerStateDelta)
    assert delta.release_runtime_claim is True
    assert delta.review == ReviewOverride(at="", actor="", wp_id="", reason="")
    # Nothing else is touched: no slot is planted by the release itself.
    assert delta.agent is None
    assert delta.shell_pid is None


def test_planned_release_fields_are_the_delta_in_dict_form() -> None:
    assert planned_claim_release_fields() == {
        "release_runtime_claim": True,
        "review": ReviewOverride(at="", actor="", wp_id="", reason=""),
    }
    assert WPInnerStateDelta(**planned_claim_release_fields()) == planned_claim_release_delta()


def test_move_task_planned_additions_come_from_the_shared_release() -> None:
    from specify_cli.cli.commands.agent import tasks_move_task_hops

    source = tasks_move_task_hops.__dict__["_build_claim_review_override"].__code__.co_names
    assert "planned_claim_release_fields" in source
