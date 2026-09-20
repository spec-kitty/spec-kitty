"""WP03 (#4775) — ``safe_confirm`` + consent/exit honesty.

Two live defects on ``main`` at ``6b4015c4d1``:

1. ``--yes``/``--force`` (``confirm``) was wired to the migration-apply
   decision (``assume_yes``) but never to the mission-state repair sub-gate's
   OWN opt-in (``repair_opt_in``, defaulted ``False``) — so ``--yes`` at an
   interactive TTY still prompted ``Run 'spec-kitty doctor mission-state
   --fix' now?`` (``_teamspace_mission_state_gate.py``/``upgrade.py:1208``).
2. Both bare ``typer.confirm`` sites (the repair sub-gate prompt, and the
   separate ``Apply N migration(s)?`` prompt at ``upgrade.py:768-770``) let
   ``typer.confirm`` raise ``typer.Abort`` uncaught on EOF (a closed/
   non-interactive stdin), crashing an otherwise-successful upgrade instead
   of cancelling cleanly.

Operator ruling: ``--yes``/``--force`` is fully non-interactive — it
auto-skips the mission-state repair sub-gate's own prompt too, exit 0.

Load-bearing distinction (T018): a green exit code alone proves nothing here
— both the correct wiring (``repair_opt_in=confirm``) and the forbidden one
(``repair_opt_in=True`` unconditionally) can yield exit 0. Every test that
claims to prove "no prompt" or "prompt still appears" asserts the actual
``typer.confirm``/``safe_confirm`` call (or its absence) directly, via a
mock, never via exit code alone.
"""

from __future__ import annotations

import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer
from rich.console import Console

import specify_cli.cli.commands.upgrade as upgrade_cmd
from specify_cli.cli.commands import _teamspace_mission_state_gate as gate
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
# T020 — the mission-state repair prompt is EOF-safe and produces an honest
# ``declined`` outcome (not a swallowed-by-a-different-layer ``failed``)
# ---------------------------------------------------------------------------


def _blocked_readiness(repo_root: Path) -> gate.TeamspaceMissionStateReadiness:
    return gate.TeamspaceMissionStateReadiness(
        repo_root=repo_root,
        total_missions=1,
        blocker_count=2,
        missions_with_blockers=1,
        blocker_codes=("teamspace-blocker",),
        audit_error=None,
    )


def test_interactive_repair_prompt_eof_declines_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An interactive TTY whose stdin hits EOF while answering the repair
    prompt declines the repair instead of raising ``Abort`` uncaught."""
    monkeypatch.setattr(gate, "check_teamspace_mission_state_readiness", lambda _r: _blocked_readiness(tmp_path))
    spy = MagicMock(name="repair_repo")
    monkeypatch.setattr("specify_cli.migration.mission_state.repair_repo", spy)
    monkeypatch.setattr(gate, "sys", types.SimpleNamespace(stdin=types.SimpleNamespace(isatty=lambda: True)))

    def _raise_abort(*_a: object, **_kw: object) -> bool:
        raise typer.Abort

    monkeypatch.setattr(typer, "confirm", _raise_abort)

    outcome = gate.offer_teamspace_mission_state_migration(
        tmp_path,
        console=Console(),
        dry_run=False,
        repair_opt_in=False,
    )

    spy.assert_not_called()
    assert outcome.declined is True
    assert outcome.failed is False


# ---------------------------------------------------------------------------
# T021 — ``_finalizer_step_offer_repair`` wires repair_opt_in=confirm, not
# a hardcoded True (the distinguishing NEW test named in the WP)
# ---------------------------------------------------------------------------


def _up_to_date_outcome() -> UpgradeOutcome:
    return UpgradeOutcome(result=UpgradeResult(success=True, from_version="1.0.0", to_version="1.0.0"))


def test_finalizer_step_offer_repair_passes_yes_as_repair_opt_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """--yes (confirm=True) must reach the sub-gate as its OWN opt-in, not
    merely as the unrelated assume_yes flag the gate ignores."""
    spy = MagicMock(name="offer_teamspace_mission_state_migration", return_value=RepairOutcome(ran=True))
    monkeypatch.setattr(upgrade_cmd, "offer_teamspace_mission_state_migration", spy)

    upgrade_cmd._finalizer_step_offer_repair(
        _up_to_date_outcome(),
        project_path=tmp_path,
        confirm=True,
        dry_run=False,
        json_output=False,
    )

    spy.assert_called_once()
    _, kwargs = spy.call_args
    assert kwargs["repair_opt_in"] is True
    assert kwargs["assume_yes"] is True


def test_finalizer_step_offer_repair_passes_no_yes_as_repair_opt_in_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without --yes, repair_opt_in must be False (proves the wiring is
    ``repair_opt_in=confirm``, NOT a hardcoded ``repair_opt_in=True`` that
    would defeat NFR-003 by always granting repair consent)."""
    spy = MagicMock(name="offer_teamspace_mission_state_migration", return_value=RepairOutcome(ran=True))
    monkeypatch.setattr(upgrade_cmd, "offer_teamspace_mission_state_migration", spy)

    upgrade_cmd._finalizer_step_offer_repair(
        _up_to_date_outcome(),
        project_path=tmp_path,
        confirm=False,
        dry_run=False,
        json_output=False,
    )

    spy.assert_called_once()
    _, kwargs = spy.call_args
    assert kwargs["repair_opt_in"] is False
    assert kwargs["assume_yes"] is False


def test_finalizer_step_offer_repair_skipped_under_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unchanged pre-existing gating: never invoked under --json."""
    spy = MagicMock(name="offer_teamspace_mission_state_migration")
    monkeypatch.setattr(upgrade_cmd, "offer_teamspace_mission_state_migration", spy)

    result = upgrade_cmd._finalizer_step_offer_repair(
        _up_to_date_outcome(),
        project_path=tmp_path,
        confirm=True,
        dry_run=False,
        json_output=True,
    )

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


def test_repair_declined_or_failed_never_flips_effective_success() -> None:
    outcome = _up_to_date_outcome()
    outcome.repair = RepairOutcome(declined=True)
    assert outcome.effective_success is True
    assert outcome.derive_exit_code() == 0

    outcome2 = _up_to_date_outcome()
    outcome2.repair = RepairOutcome(failed=True, message="boom")
    assert outcome2.effective_success is True
    assert outcome2.derive_exit_code() == 0
