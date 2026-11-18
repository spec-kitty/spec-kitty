"""#7692: the run and ``--dry-run`` judge a retarget through ONE owner (``preflight.retarget_mode``).

The entry preflight and the forecast each carried their own copy of the persisted-record read and
the retarget-mode rule, and the copies had already drifted: the forecast's
``RETARGET_RESUME_MISMATCH`` next step omitted the bare ``--resume`` remedy. Both now call
:func:`specify_cli.consolidation.preflight.retarget_mode`, a module the forecast may import (it
never imports the executor family). This file pins the single owner and the parity of the two
surfaces over the same on-disk merge record.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from specify_cli.consolidation import entry_preflight, forecast, preflight
from specify_cli.consolidation.state import ConsolidationState, save_state

pytestmark = pytest.mark.fast

_MISSION_ID = "01M7M5JA00000000000000000P"
_SLUG = "m"
_CONSOLIDATION_DIR = Path(preflight.__file__).parent


def _persist(repo: Path, pair: tuple[str, str] | None) -> None:
    if pair is None:
        return
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug=_SLUG, target_branch=pair[1], wp_order=["WP01"])
    state.retarget = {"from": pair[0], "to": pair[1], "actor": "op", "at": "2026-11-17T09:00:00+00:00", "reason": "r", "committed": False}
    save_state(state, repo)


def _entry(repo: Path, *, retarget: bool, effective: str) -> tuple[str, str] | None:
    is_retarget = entry_preflight._retarget_mode(repo, _MISSION_ID, retarget=retarget, recorded="main", effective=effective)
    return ("main", effective) if is_retarget else None


def _forecast(repo: Path, *, retarget: bool, effective: str) -> tuple[str, str] | None:
    manifest = SimpleNamespace(mission_id=_MISSION_ID, mission_branch="kitty/mission-m", target_branch="main", lanes=[])
    pair: tuple[str, str] | None = forecast._forecast_retarget_pair(
        repo, _SLUG, manifest, retarget=retarget, recorded_target="main", effective_target=effective, json_output=True
    )
    return pair


def test_both_surfaces_bind_the_one_owner() -> None:
    # Read through ``vars``: the binding is an import, not a re-export of either module.
    assert vars(entry_preflight)["retarget_mode"] is preflight.retarget_mode
    assert vars(forecast)["retarget_mode"] is preflight.retarget_mode


@pytest.mark.parametrize("module", ["entry_preflight.py", "forecast.py"])
def test_no_surface_keeps_its_own_copy_of_the_rule(module: str) -> None:
    tree = ast.parse((_CONSOLIDATION_DIR / module).read_text(encoding="utf-8"))
    defined = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "_persisted_retarget_pair" not in defined, f"{module} re-grew a private persisted-record read"
    loads = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == "RETARGET_RESUME_MISMATCH"]
    assert loads == [], f"{module} renders RETARGET_RESUME_MISMATCH text of its own instead of the owner's Refused"


def test_the_forecast_never_imports_the_executor_family() -> None:
    tree = ast.parse((_CONSOLIDATION_DIR / "forecast.py").read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not imported & {"specify_cli.consolidation.entry_preflight", "specify_cli.consolidation.executor"}


@pytest.mark.parametrize(
    ("persisted", "retarget", "effective"),
    [
        (None, True, "develop"),
        (None, False, "develop"),
        (None, True, "main"),
        (("main", "develop"), False, "develop"),
        (("main", "develop"), True, "develop"),
        (("release", "develop"), False, "develop"),
    ],
)
def test_the_two_surfaces_judge_the_same_record_identically(
    tmp_path: Path, persisted: tuple[str, str] | None, retarget: bool, effective: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _persist(tmp_path, persisted)
    expected = preflight.retarget_mode(tmp_path, _MISSION_ID, retarget=retarget, recorded="main", effective=effective)
    assert expected.mismatch is None
    assert _entry(tmp_path, retarget=retarget, effective=effective) == expected.pair
    assert _forecast(tmp_path, retarget=retarget, effective=effective) == expected.pair
    assert "Retargeting" not in capsys.readouterr().out


def test_the_mismatch_carries_one_message_and_next_step_on_both_surfaces(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _persist(tmp_path, ("main", "develop"))
    verdict = preflight.retarget_mode(tmp_path, _MISSION_ID, retarget=True, recorded="main", effective="release").mismatch
    assert verdict is not None and verdict.error_code == preflight.RETARGET_RESUME_MISMATCH
    assert "(or a bare `spec-kitty consolidate --resume`)" in verdict.next_step

    with pytest.raises(typer.Exit) as entry_exit:
        _entry(tmp_path, retarget=True, effective="release")
    entry_out = " ".join(capsys.readouterr().out.split())
    with pytest.raises(typer.Exit) as forecast_exit:
        _forecast(tmp_path, retarget=True, effective="release")
    payload: dict[str, Any] = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert entry_exit.value.exit_code == forecast_exit.value.exit_code == 1
    assert f"Error: {verdict.error_code}: {verdict.message}" in entry_out
    assert f"Next step: {verdict.next_step}" in entry_out
    assert payload["error_code"] == verdict.error_code
    assert payload["error"] == f"{verdict.error_code}: {verdict.message} Next step: {verdict.next_step}"


@pytest.mark.parametrize(("retarget", "effective"), [(False, "main"), (False, "release"), (True, "main")])
def test_a_target_other_than_the_persisted_retarget_is_a_mismatch_with_or_without_the_flag(
    tmp_path: Path, retarget: bool, effective: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """RISK-1: a persisted retarget binds every run; ``--target <recorded>`` must not silently re-land it."""
    _persist(tmp_path, ("main", "develop"))
    verdict = preflight.retarget_mode(tmp_path, _MISSION_ID, retarget=retarget, recorded="main", effective=effective).mismatch
    assert verdict is not None and verdict.error_code == preflight.RETARGET_RESUME_MISMATCH
    asked = f"'--target {effective} --retarget'" if retarget else f"'--target {effective}'"
    assert asked in verdict.message, verdict.message
    assert "'--target develop --retarget'" in verdict.next_step and "--abort" in verdict.next_step

    with pytest.raises(typer.Exit):
        _entry(tmp_path, retarget=retarget, effective=effective)
    capsys.readouterr()
    with pytest.raises(typer.Exit):
        _forecast(tmp_path, retarget=retarget, effective=effective)
    payload: dict[str, Any] = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["error_code"] == preflight.RETARGET_RESUME_MISMATCH


def test_no_persisted_retarget_never_mismatches(tmp_path: Path) -> None:
    for retarget, effective in ((False, "main"), (True, "develop"), (False, "develop")):
        assert preflight.retarget_mode(tmp_path, _MISSION_ID, retarget=retarget, recorded="main", effective=effective).mismatch is None


def test_an_unreadable_record_contributes_no_persisted_retarget(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation.state import ConsolidationStateReadError

    def _raise(*_a: object, **_k: object) -> None:
        raise ConsolidationStateReadError("unreadable")

    monkeypatch.setattr(preflight, "load_state", _raise)
    assert preflight.persisted_retarget_pair(tmp_path, _MISSION_ID) is None
    assert preflight.retarget_mode(tmp_path, _MISSION_ID, retarget=False, recorded="main", effective="develop").pair is None
