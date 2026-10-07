"""``safe_confirm`` + consent/exit honesty (#4775, re-pinned by #5811).

``--yes``/``--force`` is fully non-interactive, and since ADR 2026-10-07-1
``upgrade`` never runs the mission-state repair at all: the finalizer step is
report-only and takes no consent parameter. The only remaining prompt is the
``Apply N migration(s)?`` confirmation, routed through ``safe_confirm``.

A green exit code alone proves nothing here, so every test that claims "no
prompt" or "prompt still appears" asserts the actual ``safe_confirm`` call
(or its absence) through a mock.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer

import specify_cli.cli.commands.upgrade as upgrade_cmd
from specify_cli.cli.commands._confirm import safe_confirm
from specify_cli.upgrade.outcome import RepairOutcome, UpgradeOutcome
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# T019 — safe_confirm: declines safely on Abort/EOFError, never a bare except
# ---------------------------------------------------------------------------


def test_safe_confirm_returns_true_when_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(typer, "confirm", lambda *_a, **_kw: True)
    assert safe_confirm("Proceed?", default=False) is True


def test_safe_confirm_declines_on_typer_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    """``typer.Abort`` is the exception ``typer.confirm`` raises on Ctrl-C or
    when reading hits EOF."""

    def _raise_abort(*_a: object, **_kw: object) -> bool:
        raise typer.Abort

    monkeypatch.setattr(typer, "confirm", _raise_abort)
    # Even with default=True, an aborted prompt must decline, not "succeed
    # via the default" — a caller could not answer at all.
    assert safe_confirm("Proceed?", default=True) is False


def test_safe_confirm_declines_on_eof_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_eof(*_a: object, **_kw: object) -> bool:
        raise EOFError

    monkeypatch.setattr(typer, "confirm", _raise_eof)
    assert safe_confirm("Proceed?", default=True) is False


def test_safe_confirm_does_not_swallow_other_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not a bare ``except Exception`` (C-002/NFR-005): an unrelated bug
    raised while prompting must propagate, not be misreported as a decline."""

    def _raise_value_error(*_a: object, **_kw: object) -> bool:
        raise ValueError("boom")

    monkeypatch.setattr(typer, "confirm", _raise_value_error)
    with pytest.raises(ValueError, match="boom"):
        safe_confirm("Proceed?", default=False)


def test_safe_confirm_passes_prompt_and_default_through(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_confirm(prompt: str, **kwargs: object) -> bool:
        captured["prompt"] = prompt
        captured.update(kwargs)
        return True

    monkeypatch.setattr(typer, "confirm", _fake_confirm)
    safe_confirm("Run the thing?", default=True)
    assert captured == {"prompt": "Run the thing?", "default": True}


# ---------------------------------------------------------------------------
# The finalizer step is report-only: it never passes consent to the gate
# ---------------------------------------------------------------------------


def _up_to_date_outcome() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version="1.0.0", to_version="1.0.0"))


def test_finalizer_step_reports_without_any_consent_parameter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The step hands the gate only the project and a console: no --yes,
    no opt-in, no dry-run flag can reach a repair because none exists."""
    spy = MagicMock(name="report_teamspace_mission_state_blockers", return_value=RepairOutcome(reported=True))
    monkeypatch.setattr(upgrade_cmd, "report_teamspace_mission_state_blockers", spy)

    upgrade_cmd._finalizer_step_report_mission_state(_up_to_date_outcome(), project_path=tmp_path, json_output=False)

    spy.assert_called_once()
    assert set(spy.call_args.kwargs) == {"console"}


def test_finalizer_step_report_skipped_under_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unchanged pre-existing gating: never invoked under --json."""
    spy = MagicMock(name="report_teamspace_mission_state_blockers")
    monkeypatch.setattr(upgrade_cmd, "report_teamspace_mission_state_blockers", spy)

    result = upgrade_cmd._finalizer_step_report_mission_state(_up_to_date_outcome(), project_path=tmp_path, json_output=True)

    spy.assert_not_called()
    assert result.pending is True


# ---------------------------------------------------------------------------
# T018/T019/T020 — the "Apply N migration(s)?" bare-confirm site
# (upgrade.py:768-770): --yes never prompts; without --yes the prompt still
# appears (mock-call assertion, not inferred from exit code); EOF cancels
# cleanly instead of crashing.
# ---------------------------------------------------------------------------


def test_show_migration_plan_confirm_not_invoked_with_yes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--yes (confirm=True): the ``Apply N migration(s)?`` prompt must never
    fire at all — a real ``</dev/null`` run must not even attempt to read."""
    spy = MagicMock(name="safe_confirm")
    monkeypatch.setattr(upgrade_cmd, "safe_confirm", spy)

    upgrade_cmd._show_migration_plan_and_confirm(
        [],
        project_path=tmp_path,
        json_output=True,
        dry_run=False,
        verbose=False,
        confirm=True,
    )

    spy.assert_not_called()


def test_show_migration_plan_prompt_still_appears_without_yes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NEGATIVE test (T018): WITHOUT --yes and with (simulated) pending
    migrations, the prompt STILL appears. Proven by a mock-call assertion on
    the actual confirm call, never by exit code alone (both a correct and a
    broken wiring can yield exit 0)."""
    spy = MagicMock(name="safe_confirm", return_value=True)
    monkeypatch.setattr(upgrade_cmd, "safe_confirm", spy)

    upgrade_cmd._show_migration_plan_and_confirm(
        [],
        project_path=tmp_path,
        json_output=True,
        dry_run=False,
        verbose=False,
        confirm=False,
    )

    spy.assert_called_once_with("Apply 0 migration(s)?", default=True)


def test_show_migration_plan_confirm_declined_cancels_with_exit_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spy = MagicMock(name="safe_confirm", return_value=False)
    monkeypatch.setattr(upgrade_cmd, "safe_confirm", spy)

    with pytest.raises(typer.Exit) as exc_info:
        upgrade_cmd._show_migration_plan_and_confirm(
            [],
            project_path=tmp_path,
            json_output=True,
            dry_run=False,
            verbose=False,
            confirm=False,
        )
    assert exc_info.value.exit_code == 0


def test_show_migration_plan_confirm_eof_cancels_cleanly_not_uncaught_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """RED-on-main proof: simulated-TTY-EOF at this exact prompt used to
    raise ``typer.Abort`` straight out of this function (uncaught) — now it
    is routed through ``safe_confirm``, which declines, and the function's
    own existing decline path takes over: ``typer.Exit(0)``, no crash."""

    def _raise_abort(*_a: object, **_kw: object) -> bool:
        raise typer.Abort

    monkeypatch.setattr(typer, "confirm", _raise_abort)

    with pytest.raises(typer.Exit) as exc_info:
        upgrade_cmd._show_migration_plan_and_confirm(
            [],
            project_path=tmp_path,
            json_output=True,
            dry_run=False,
            verbose=False,
            confirm=False,
        )
    assert exc_info.value.exit_code == 0


# ---------------------------------------------------------------------------
# T024 — FR-014 preserved: repair failure/decline never feeds exit_code
# ---------------------------------------------------------------------------


def test_repair_reported_or_failed_never_flips_effective_success() -> None:
    outcome = _up_to_date_outcome()
    outcome.repair = RepairOutcome(reported=True)
    assert outcome.effective_success is True
    assert outcome.exit_code == 0

    outcome2 = _up_to_date_outcome()
    outcome2.repair = RepairOutcome(failed=True, message="boom")
    assert outcome2.effective_success is True
    assert outcome2.exit_code == 0
