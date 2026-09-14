"""CLI tests for spec-kitty doctor ops --close-stale (WP04 — T016/T018)."""

from __future__ import annotations

import json
from kernel.clock import timedelta, now_utc
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.invocation.writer import EVENTS_DIR, OP_CLOSURES_RELATIVE_PATH, read_op_closures

from tests._support.ansi import strip_ansi

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()


def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".kittify").mkdir()
    ops_dir = tmp_path / EVENTS_DIR
    ops_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    return ops_dir


def _write_open_op(ops_dir: Path, invocation_id: str, started_at: str) -> Path:
    path = ops_dir / f"{invocation_id}.jsonl"
    event = {
        "event": "started",
        "invocation_id": invocation_id,
        "profile_id": "implementer-fixture",
        "action": "implement",
        "started_at": started_at,
    }
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    return path


def _stale_ts(hours: float = 100.0) -> str:
    return (now_utc() - timedelta(hours=hours)).isoformat()


def _fresh_ts() -> str:
    return (now_utc() - timedelta(minutes=5)).isoformat()


def test_threshold_without_close_stale_is_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _project(tmp_path, monkeypatch)

    result = runner.invoke(cli_app, ["doctor", "ops", "--threshold", "12"])

    assert result.exit_code == 2
    # Strip ANSI: under CI, Rich force-enables terminal styling so the captured
    # usage-error text carries colour codes that break a raw substring check.
    assert "--close-stale" in strip_ansi(result.output)


def test_close_stale_sweeps_stale_op_json_and_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops_dir = _project(tmp_path, monkeypatch)
    path = _write_open_op(ops_dir, "01KTBE0RQY9XKTV0PE49PJDC01", _stale_ts())

    result = runner.invoke(cli_app, ["doctor", "ops", "--close-stale", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload) == {"open_ops", "swept", "skipped_fresh", "threshold_hours", "closure_spine"}
    assert payload["swept"] == 1
    assert payload["skipped_fresh"] == 0
    assert payload["threshold_hours"] == 24.0
    assert payload["closure_spine"] == OP_CLOSURES_RELATIVE_PATH.as_posix()
    (op,) = payload["open_ops"]
    assert op["invocation_id"] == "01KTBE0RQY9XKTV0PE49PJDC01"
    assert op["profile_id"] == "implementer-fixture"
    assert op["action_taken"] == "closed_abandoned"
    assert op["age_hours"] == pytest.approx(100.0, abs=0.5)
    # #4397: closed_by / outcome written verbatim through the canonical close
    # path — onto the append-only closure spine, never the byte-frozen
    # per-record archive file.
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    (closure,) = read_op_closures(tmp_path)
    assert closure.invocation_id == "01KTBE0RQY9XKTV0PE49PJDC01"
    assert closure.outcome == "abandoned"
    assert closure.closed_by == "doctor_sweep"


def test_close_stale_fresh_only_sweeps_nothing_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops_dir = _project(tmp_path, monkeypatch)
    _write_open_op(ops_dir, "01KTBE0RQY9XKTV0PE49PJDC02", _fresh_ts())

    result = runner.invoke(cli_app, ["doctor", "ops", "--close-stale", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["swept"] == 0
    assert payload["skipped_fresh"] == 1
    assert payload["open_ops"][0]["action_taken"] == "none"


def test_close_stale_threshold_zero_sweeps_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops_dir = _project(tmp_path, monkeypatch)
    _write_open_op(ops_dir, "01KTBE0RQY9XKTV0PE49PJDC03", _fresh_ts())
    _write_open_op(ops_dir, "01KTBE0RQY9XKTV0PE49PJDC04", _stale_ts())

    result = runner.invoke(
        cli_app, ["doctor", "ops", "--close-stale", "--threshold", "0", "--json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["swept"] == 2
    assert payload["skipped_fresh"] == 0
    assert payload["threshold_hours"] == 0.0


def test_close_stale_human_output_mentions_sweep_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops_dir = _project(tmp_path, monkeypatch)
    _write_open_op(ops_dir, "01KTBE0RQY9XKTV0PE49PJDC05", _stale_ts())

    result = runner.invoke(cli_app, ["doctor", "ops", "--close-stale"])

    assert result.exit_code == 0
    assert "Ops sweep" in result.output
    assert "1 closed as abandoned" in result.output


def test_report_mode_unchanged_without_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops_dir = _project(tmp_path, monkeypatch)
    path = _write_open_op(ops_dir, "01KTBE0RQY9XKTV0PE49PJDC06", _stale_ts())

    result = runner.invoke(cli_app, ["doctor", "ops", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output) == [{"path": f"{EVENTS_DIR}/{path.name}"}]
    # Report-only mode never closes anything.
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
