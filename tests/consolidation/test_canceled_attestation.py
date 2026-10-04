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


@pytest.mark.git_repo
def test_dry_run_cli_prints_the_attestation_notice_and_still_forecasts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The ONE CLI smoke for the FR-012 dry-run notice (#5653).

    Drives the real ``consolidate`` Typer command in a real git repository with
    one real Mission directory. Only the true downstream boundary is stubbed: the
    dry-run forecast, captured so the test can see it still runs after the
    notice. The notice's decision table lives in the unit tests below.
    """
    import json
    import subprocess

    import typer
    from typer.testing import CliRunner

    from specify_cli.cli.commands import consolidate as consolidate_module

    slug = "attest-smoke-01M43DRV"
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (repo / ".kittify").mkdir()
    mission_dir = repo / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    meta = {
        "mission_id": "01M43DRVZZZZZZZZZZZZZZZZZZ",
        "mid8": "01M43DRV",
        "mission_slug": slug,
        "slug": slug,
        "friendly_name": "Attestation smoke",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-10-04T00:00:00Z",
        "topology": "single_branch",
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "init")
    monkeypatch.chdir(repo)
    forecasts: list[dict[str, object]] = []
    monkeypatch.setattr(consolidate_module, "run_dry_run_forecast", lambda **kwargs: forecasts.append(kwargs))
    app = typer.Typer()
    app.command()(consolidate_module.consolidate)

    result = CliRunner().invoke(app, ["--dry-run", "--mission", slug, ca.ATTEST_FLAG, "WP02", ca.ATTEST_REASON_FLAG, "checked"])

    assert result.exit_code == 0, result.output
    assert ca.dry_run_attestation_notice(("WP02",), dry_run=True, json_output=False) in " ".join(result.output.split())
    assert len(forecasts) == 1  # the notice does not replace the forecast


# #5653: the ``consolidate --dry-run`` "attestation not applied" notice is a pure
# decision, unit-tested here instead of through the CLI's call graph. One CLI
# smoke (``test_dry_run_cli_prints_the_attestation_notice_and_still_forecasts``,
# directly above) keeps the wiring honest.
_DRY_RUN_NOTICE = "--attest-canceled-superseded is not applied with --dry-run: nothing is recorded, and the forecast does not evaluate mixed-lane attribution."


def test_dry_run_notice_names_the_flag_for_a_human_dry_run() -> None:
    notice = ca.dry_run_attestation_notice(("WP02",), dry_run=True, json_output=False)

    # Byte-identical to the pre-extraction inline text, built from ATTEST_FLAG.
    assert notice == _DRY_RUN_NOTICE


@pytest.mark.parametrize(
    ("attested_wps", "dry_run", "json_output"),
    [
        pytest.param((), True, False, id="no-attestation"),
        pytest.param(("WP02",), False, False, id="real-run-records-it"),
        pytest.param(("WP02",), True, True, id="json-output-stays-clean"),
    ],
)
def test_dry_run_notice_is_silent_otherwise(attested_wps: tuple[str, ...], dry_run: bool, json_output: bool) -> None:
    assert ca.dry_run_attestation_notice(attested_wps, dry_run=dry_run, json_output=json_output) is None
