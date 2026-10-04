"""Unit guard: ``next_cmd`` dispatch seams fail closed on a corrupt ``meta.json`` (#4642).

``MissionMetaReadError`` subclasses ``RuntimeError`` (not ``ValueError``), so it
escapes the slug-resolution guard in ``next_step`` and must be caught at both
dispatch seams: ``_dispatch_query_mode`` (no ``--result``) and
``_dispatch_advancing_mode`` (``--result <value>``).  The defect is fixed; these
tests are the permanent per-mode guard (the CLI smoke in
``test_next_meta_corruption.py`` covers the real entry point end to end).

Only the collaborator that raises is stubbed; each dispatch function is called
directly and the observable result (exit code plus rendered message) is asserted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands import next_cmd
from specify_cli.core.paths import MissionMetaReadError

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_META_PATH = Path("kitty-specs/042-corrupt-meta-mission/meta.json")
_SLUG = "042-corrupt-meta-mission"
_DOCTOR_HINT = "spec-kitty doctor"


def _raise_meta_error(*_args: object, **_kwargs: object) -> None:
    raise MissionMetaReadError(_META_PATH, ValueError("Expecting property name"))


def _call_query(json_output: bool) -> None:
    next_cmd._dispatch_query_mode("test-agent", _SLUG, Path("."), json_output, None, None, owned=None)


def _call_advancing(json_output: bool) -> None:
    next_cmd._dispatch_advancing_mode("test-agent", _SLUG, "success", Path("."), json_output, None, None, owned=None)


@pytest.fixture
def stub_query_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_cmd, "_run_query_mode", _raise_meta_error)


@pytest.fixture
def stub_advance_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_cmd, "_pair_previous_lifecycle_record", lambda *_a, **_k: None)
    monkeypatch.setattr(next_cmd, "decide_next", _raise_meta_error)


def _assert_json_error(out: str) -> None:
    payload = json.loads(out)
    assert payload["result"] == "error"
    assert payload["error_code"] == "MISSION_META_READ_ERROR"
    assert payload["meta_path"] == str(_META_PATH)
    assert _META_PATH.name in payload["error"]
    assert _DOCTOR_HINT in payload["next_step"]


def _assert_plain_error(err: str) -> None:
    assert _META_PATH.name in err
    assert _DOCTOR_HINT in err


@pytest.mark.usefixtures("stub_query_raises")
def test_query_mode_plain_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        _call_query(json_output=False)
    assert excinfo.value.exit_code == 1
    _assert_plain_error(capsys.readouterr().err)


@pytest.mark.usefixtures("stub_query_raises")
def test_query_mode_json_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        _call_query(json_output=True)
    assert excinfo.value.exit_code == 1
    _assert_json_error(capsys.readouterr().out)


@pytest.mark.usefixtures("stub_advance_raises")
def test_advancing_mode_plain_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        _call_advancing(json_output=False)
    assert excinfo.value.exit_code == 1
    _assert_plain_error(capsys.readouterr().err)


@pytest.mark.usefixtures("stub_advance_raises")
def test_advancing_mode_json_fails_closed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(typer.Exit) as excinfo:
        _call_advancing(json_output=True)
    assert excinfo.value.exit_code == 1
    _assert_json_error(capsys.readouterr().out)
