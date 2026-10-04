"""Unit tests for the FR-012 operator attestation record (#5046 landing).

``specify_cli.consolidation.canceled_attestation`` — the record reader
(:func:`attestation_stamps`), the request validation, and the shape of
the forced ``canceled -> canceled`` transition written through the canonical
transactional seam (seam call captured; its own persistence is covered by the
coordination suite and end to end by
``tests/terminus/test_mixed_lane_fail_recovery_and_attestation.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import Result

from specify_cli.consolidation import canceled_attestation as ca
from specify_cli.status import Lane, StatusEvent, TransitionRequest
from specify_cli.status.transitions import validate_transition
from specify_cli.status.models import GuardContext

pytestmark = [pytest.mark.unit]

_OPERATOR = "operator"


def _event(
    seq: int,
    wp_id: str,
    from_lane: Lane,
    to_lane: Lane,
    *,
    actor: str = "claude",
    reason_source: str | None = None,
    marker: str | None = None,
) -> StatusEvent:
    return StatusEvent(
        event_id=f"01HXYZ{seq:020d}",
        mission_slug="m",
        wp_id=wp_id,
        from_lane=from_lane,
        to_lane=to_lane,
        at=f"2026-09-29T00:00:{seq:02d}+00:00",
        actor=actor,
        force=from_lane == to_lane,
        execution_mode="worktree",
        reason="r",
        reason_source=reason_source,
        policy_metadata={ca.ATTESTATION_KEY: marker} if marker else None,
    )


def _attestation(seq: int, wp_id: str = "WP02") -> StatusEvent:
    return _event(seq, wp_id, Lane.CANCELED, Lane.CANCELED, reason_source=_OPERATOR, marker=ca.CANCELED_SUPERSEDED)


def test_forced_self_transition_is_a_legal_fsm_edge_only_under_force() -> None:
    """The record rides the FSM's own force rule: actor AND reason are required."""
    assert validate_transition("canceled", "canceled", GuardContext(force=True, actor="op", reason="checked")) == (True, None)
    assert validate_transition("canceled", "canceled", GuardContext(force=False, actor="op", reason="checked"))[0] is False
    assert validate_transition("canceled", "canceled", GuardContext(force=True, actor="op", reason=""))[0] is False


def test_valid_attestation_is_recognised() -> None:
    events = [_event(1, "WP02", Lane.IN_PROGRESS, Lane.CANCELED, reason_source=_OPERATOR), _attestation(2)]
    assert set(ca.attestation_stamps(events)) == {"WP02"}


@pytest.mark.parametrize(
    "event",
    [
        _event(2, "WP02", Lane.CANCELED, Lane.CANCELED, reason_source=_OPERATOR),  # no marker
        _event(2, "WP02", Lane.CANCELED, Lane.CANCELED, marker=ca.CANCELED_SUPERSEDED),  # no operator provenance
        _event(2, "WP02", Lane.CANCELED, Lane.CANCELED, reason_source=_OPERATOR, marker="something_else"),
        _event(2, "WP02", Lane.IN_PROGRESS, Lane.CANCELED, reason_source=_OPERATOR, marker=ca.CANCELED_SUPERSEDED),
        _event(2, "WP02", Lane.CANCELED, Lane.CANCELED, reason_source=_OPERATOR, marker=ca.CANCELED_SUPERSEDED, actor="migration:x"),
    ],
)
def test_non_attestation_shapes_are_not_recognised(event: StatusEvent) -> None:
    assert ca.is_canceled_superseded_attestation(event) is False
    assert ca.attestation_stamps([event]) == {}


def test_later_governed_transition_voids_the_attestation() -> None:
    events = [_attestation(1), _event(2, "WP02", Lane.CANCELED, Lane.IN_PROGRESS)]
    assert ca.attestation_stamps(events) == {}


def test_migration_seed_after_attestation_does_not_void_it() -> None:
    events = [_attestation(1), _event(2, "WP02", Lane.PLANNED, Lane.CLAIMED, actor="migration:backfill_runtime_state")]
    assert set(ca.attestation_stamps(events)) == {"WP02"}


def test_other_wp_transitions_do_not_void_it() -> None:
    events = [_attestation(1), _event(2, "WP01", Lane.APPROVED, Lane.DONE)]
    assert set(ca.attestation_stamps(events)) == {"WP02"}


def test_validate_dedupes_and_allows_empty() -> None:
    assert ca.validate_attestation_request(["WP02", "WP02"], "checked", acceptably_canceled=frozenset({"WP02"})) == ("WP02",)
    assert ca.validate_attestation_request([], None, acceptably_canceled=frozenset()) == ()


def test_record_goes_through_the_transactional_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[TransitionRequest] = []

    def _fake_emit(request: TransitionRequest) -> None:
        captured.append(request)

    monkeypatch.setattr("specify_cli.coordination.status_transition.emit_status_transition_transactional", _fake_emit)
    ca.record_canceled_superseded_attestation(
        repo_root=tmp_path,
        feature_dir=tmp_path / "kitty-specs" / "m",
        mission_slug="m",
        wp_id="WP02",
        reason="  verified by hand: file removed on the lane  ",
        actor="stijn",
    )
    (request,) = captured
    assert request.wp_id == "WP02"
    assert request.to_lane == Lane.CANCELED
    assert request.force is True
    assert request.actor == "stijn"
    assert request.reason_source == _OPERATOR
    assert request.reason is not None and request.reason.endswith("verified by hand: file removed on the lane")
    assert request.policy_metadata == {ca.ATTESTATION_KEY: ca.CANCELED_SUPERSEDED}


def test_cli_boundary_requires_reason_with_the_flag() -> None:
    import typer

    from specify_cli.cli.commands.consolidate import _validated_attestation_flags

    with pytest.raises(typer.Exit) as excinfo:
        _validated_attestation_flags(["WP02"], "   ")
    assert excinfo.value.exit_code == 2


def test_cli_boundary_dedupes_and_tolerates_a_lone_reason() -> None:
    from specify_cli.cli.commands.consolidate import _validated_attestation_flags

    assert _validated_attestation_flags(["WP02", " WP02 ", "WP03"], "checked") == ("WP02", "WP03")
    assert _validated_attestation_flags(None, "inert reason") == ()
    assert _validated_attestation_flags(None, None) == ()


def test_cli_boundary_treats_unresolved_typer_defaults_as_absent() -> None:
    """A direct ``consolidate()`` call that omits the flags passes ``OptionInfo`` sentinels."""
    import typer

    from specify_cli.cli.commands.consolidate import _validated_attestation_flags

    assert _validated_attestation_flags(typer.Option(None), typer.Option(None)) == ()


def test_attestation_stamps_carry_the_lane_head_or_none() -> None:
    stamped = StatusEvent(
        event_id="01HXYZ00000000000000000009",
        mission_slug="m",
        wp_id="WP02",
        from_lane=Lane.CANCELED,
        to_lane=Lane.CANCELED,
        at="2026-09-29T00:00:09+00:00",
        actor="op",
        force=True,
        execution_mode="worktree",
        reason="r",
        reason_source=_OPERATOR,
        policy_metadata={ca.ATTESTATION_KEY: ca.CANCELED_SUPERSEDED, "lane_head": "abc123"},
    )
    assert ca.attestation_stamps([stamped]) == {"WP02": "abc123"}
    assert ca.attestation_stamps([_attestation(1)]) == {"WP02": None}


def test_latest_attestation_stamp_wins() -> None:
    """A re-attestation advances the stamp (each explicit attestation is a new operator act)."""

    def stamped(seq: int, head: str) -> StatusEvent:
        return StatusEvent(
            event_id=f"01HXYZ{seq:020d}",
            mission_slug="m",
            wp_id="WP02",
            from_lane=Lane.CANCELED,
            to_lane=Lane.CANCELED,
            at=f"2026-09-29T00:00:{seq:02d}+00:00",
            actor="op",
            force=True,
            execution_mode="worktree",
            reason="r",
            reason_source=_OPERATOR,
            policy_metadata={ca.ATTESTATION_KEY: ca.CANCELED_SUPERSEDED, "lane_head": head},
        )

    assert ca.attestation_stamps([stamped(1, "old"), stamped(2, "new")]) == {"WP02": "new"}


# --------------------------------------------------------------------------- #
# Unit-level homes of the attestation rejection / dry-run notice contracts
# (formerly only reachable through the mixed-lane fail/attestation e2e)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_validate_refuses_a_missing_or_blank_reason_and_names_both_flags(reason: str | None) -> None:
    with pytest.raises(ca.AttestationError) as excinfo:
        ca.validate_attestation_request(["WP02"], reason, acceptably_canceled=frozenset({"WP02"}))
    assert ca.ATTEST_FLAG in str(excinfo.value)
    assert ca.ATTEST_REASON_FLAG in str(excinfo.value)


@pytest.mark.parametrize("wp_id", ["WP01", "WP99"], ids=["not-canceled", "unknown-wp"])
def test_validate_refuses_a_wp_that_is_not_acceptably_canceled_and_says_nothing_was_recorded(wp_id: str) -> None:
    """The request is all-or-nothing: one offender beside a valid WP refuses the whole request and names only the offender."""
    with pytest.raises(ca.AttestationError) as excinfo:
        ca.validate_attestation_request(["WP02", wp_id], "checked", acceptably_canceled=frozenset({"WP02"}))
    message = str(excinfo.value)
    assert f"not canceled: {wp_id}" in message
    assert "WP02" not in message
    assert "Nothing was recorded." in message


def _invoke_consolidate_dry_run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: list[str]) -> tuple[Result, list[dict[str, object]]]:
    """Drive the real ``consolidate`` Typer command up to the dry-run forecast seam.

    Everything between argument parsing and the forecast (repo/branch/mission
    resolution, retention cleanup) is stubbed; the forecast itself is captured so
    the test sees the notice the command prints before delegating to it.
    """
    import typer
    from typer.testing import CliRunner

    from specify_cli.cli.commands import consolidate as consolidate_module
    from specify_cli.core.context_validation import ExecutionContext

    forecasts: list[dict[str, object]] = []
    stubs: dict[str, object] = {
        "find_repo_root": lambda: tmp_path,
        "_enforce_git_preflight": lambda *_a, **_k: None,
        "load_merge_config": lambda _root: type("Cfg", (), {"strategy": None})(),
        "_resolve_slug_or_exit": lambda _root, _mission: "m-01TESTMISSION",
        "_resolved_mission_dir_exists": lambda *_a, **_k: True,
        "load_state": lambda *_a, **_k: None,
        "_resolve_target_branch": lambda *_a, **_k: ("main", "explicit"),
        "_validate_target_branch": lambda *_a, **_k: None,
        "_enforce_retention_cleanup": lambda *_a, **_k: None,
        "show_banner": lambda: None,
        "run_dry_run_forecast": lambda **kwargs: forecasts.append(kwargs),
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(consolidate_module, name, stub)
    monkeypatch.setattr(
        "specify_cli.core.context_validation.get_current_context",
        lambda: type("Ctx", (), {"location": ExecutionContext.MAIN_REPO})(),
    )
    app = typer.Typer()
    app.command()(consolidate_module.consolidate)
    return CliRunner().invoke(app, args), forecasts


def test_dry_run_says_the_attestation_flags_are_not_applied(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--dry-run`` must not silently drop the attestation flags (FR-012)."""
    result, forecasts = _invoke_consolidate_dry_run(
        monkeypatch, tmp_path, ["--dry-run", "--mission", "m-01TESTMISSION", ca.ATTEST_FLAG, "WP02", ca.ATTEST_REASON_FLAG, "checked"]
    )

    assert result.exit_code == 0, result.output
    flat = " ".join(result.output.split())
    assert f"{ca.ATTEST_FLAG} is not applied with --dry-run" in flat
    assert len(forecasts) == 1  # the notice does not replace the forecast


def test_dry_run_without_attestation_flags_prints_no_attestation_notice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result, forecasts = _invoke_consolidate_dry_run(monkeypatch, tmp_path, ["--dry-run", "--mission", "m-01TESTMISSION"])

    assert result.exit_code == 0, result.output
    assert "not applied with --dry-run" not in result.output
    assert len(forecasts) == 1
