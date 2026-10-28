"""CLI tests for ``spec-kitty doctor event-logs`` (#6610, FR-006, FR-012).

The command wraps the retention engine (:mod:`specify_cli.state.retention`):
preview by default (changes nothing, exit 0), ``--apply`` deletes the candidates
(exit 1 when any deletion failed), and a config or usage error exits 2 with
nothing scanned or deleted. The ``--json`` payload follows
``kitty-specs/local-event-log-retention-01M5ZCJP/contracts/doctor-event-logs.md``.

The fixture project holds one completed Mission with two old runs. With
``keep_runs: 1`` and ``max_age_days: 30`` the newer run is kept (within
``keep_runs``) and the older one is the only candidate. Ages are set with
``os.utime`` relative to the real clock, the one the command reads.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from runtime.next import run_index
from runtime.next.run_lock import run_cursor_lock
from specify_cli.cli.commands import _event_logs_doctor
from specify_cli.cli.commands.doctor import app
from specify_cli.state import retention

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

DONE_SLUG = "001-done-mission"
DONE_ID = "01DONE0000000000000000000A"
CONTRACT_KEYS = {"applied", "limits", "candidates", "kept", "deleted", "failed", "removed_index_entries"}
ITEM_KEYS = {"surface", "kind", "path", "mission", "age_days", "reason"}
RETENTION_CONFIG = "ledger:\n  retention:\n    keep_runs: 1\n    max_age_days: 30\n"
EVENT_LOGS = "event-logs"
JSON_FLAG = "--json"
APPLY_FLAG = "--apply"


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _set_age(path: Path, age_days: float) -> None:
    stamp = time.time() - age_days * 86400
    for target in [p for p in path.rglob("*") if p.is_file()]:
        os.utime(target, (stamp, stamp))


def _run(repo: Path, name: str, age_days: float) -> Path:
    """A run as ``next`` leaves it: no Mission in ``state.json`` (the run index links it)."""
    run_dir = run_index.runs_root(repo) / name
    _write(run_dir / "state.json", json.dumps({"run_id": name, "mission_id": None, "mission_slug": None, "inputs": {"mission_slug": DONE_SLUG}}))
    _write(run_dir / "run.events.jsonl", '{"event_type": "MissionRunStarted"}\n')
    _set_age(run_dir, age_days)
    return run_dir


def _entry(run_dir: Path) -> dict[str, object]:
    return {"run_id": run_dir.name, "run_dir": str(run_dir), "mission_type": "software-dev", "mission_id": DONE_ID, "mission_slug": DONE_SLUG}


def _tree_digest(repo: Path) -> dict[str, bytes | None]:
    digest: dict[str, bytes | None] = {}
    for path in sorted(repo.rglob("*")):
        rel = path.relative_to(repo)
        if rel.parts[0] == ".git":
            continue
        digest[rel.as_posix()] = path.read_bytes() if path.is_file() else None
    return digest


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A git project with a completed Mission and no runs yet."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    meta = {"mission_id": DONE_ID, "mission_slug": DONE_SLUG, "slug": DONE_SLUG, "merged_at": "2026-09-01T00:00:00+00:00"}
    _write(tmp_path / "kitty-specs" / DONE_SLUG / "meta.json", json.dumps(meta, indent=2))
    _write(tmp_path / ".kittify" / "config.yaml", RETENTION_CONFIG)
    monkeypatch.setattr(_event_logs_doctor, "locate_project_root", lambda: tmp_path)
    return tmp_path


@pytest.fixture()
def runs(project: Path) -> dict[str, Path]:
    """Two old runs of the completed Mission: the newer is kept, the older is a candidate."""
    kept = _run(project, "run-newer", 40)
    candidate = _run(project, "run-older", 50)
    run_index.save_index(project, {DONE_ID: _entry(candidate), kept.name: _entry(kept)})
    return {"kept": kept, "candidate": candidate}


def _invoke(*args: str) -> Any:
    return runner.invoke(app, [EVENT_LOGS, *args])


def _rel(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


def test_preview_lists_candidates_and_kept_reasons_and_changes_nothing(project: Path, runs: dict[str, Path]) -> None:
    before = _tree_digest(project)

    result = _invoke()

    assert result.exit_code == 0, result.output
    assert "Preview" in result.output
    assert _rel(runs["candidate"], project) in result.output
    assert retention.REASON_COMPLETED in result.output
    assert retention.REASON_WITHIN_KEEP_RUNS in result.output
    assert "Run with --apply to delete these 1 item(s)." in result.output
    assert _tree_digest(project) == before


def test_json_preview_matches_the_contract_shape(project: Path, runs: dict[str, Path]) -> None:
    before = _tree_digest(project)

    result = _invoke(JSON_FLAG)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert set(payload) == CONTRACT_KEYS
    assert payload["applied"] is False
    assert payload["limits"] == {"keep_runs": 1, "max_age_days": 30, "source": ".kittify/config.yaml"}
    assert [item["path"] for item in payload["candidates"]] == [_rel(runs["candidate"], project)]
    assert [item["path"] for item in payload["kept"]] == [_rel(runs["kept"], project)]
    for item in payload["candidates"] + payload["kept"]:
        assert set(item) == ITEM_KEYS
        assert item["mission"] == DONE_SLUG
        assert item["kind"] == "run"
    assert payload["kept"][0]["reason"] == retention.REASON_WITHIN_KEEP_RUNS
    assert payload["deleted"] == payload["failed"] == payload["removed_index_entries"] == []
    assert _tree_digest(project) == before


def test_apply_json_deletes_the_candidates_and_their_index_entries(project: Path, runs: dict[str, Path]) -> None:
    result = _invoke(APPLY_FLAG, JSON_FLAG)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert set(payload) == CONTRACT_KEYS
    assert payload["applied"] is True
    assert [item["path"] for item in payload["deleted"]] == [_rel(runs["candidate"], project)]
    assert payload["failed"] == []
    assert payload["removed_index_entries"] == [DONE_ID]
    assert not runs["candidate"].exists()
    assert runs["kept"].is_dir()


def test_apply_human_output_reports_the_deletions(project: Path, runs: dict[str, Path]) -> None:
    result = _invoke(APPLY_FLAG)

    assert result.exit_code == 0, result.output
    assert "Deleted 1 item(s)" in result.output
    assert _rel(runs["candidate"], project) in result.output
    assert not runs["candidate"].exists()


def test_apply_human_output_says_nothing_was_deleted_when_every_candidate_was_kept(project: Path, runs: dict[str, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """A candidate locked between the scan and the apply is kept; the output still says what was deleted."""
    real_apply = _event_logs_doctor.apply_retention

    def _apply_while_locked(repo_root: Path, plan: retention.RetentionPlan) -> retention.RetentionResult:
        with run_cursor_lock(runs["candidate"]):
            return real_apply(repo_root, plan)

    monkeypatch.setattr(_event_logs_doctor, "apply_retention", _apply_while_locked)

    result = _invoke(APPLY_FLAG)

    assert result.exit_code == 0, result.output
    assert "Nothing was deleted" in result.output
    assert retention.REASON_LOCK_HELD in result.output
    assert runs["candidate"].is_dir()


@pytest.mark.parametrize("json_output", [False, True])
def test_invalid_config_exits_2_and_deletes_nothing(project: Path, runs: dict[str, Path], json_output: bool) -> None:
    _write(project / ".kittify" / "config.yaml", "ledger:\n  retention:\n    keep_runs: -1\n")
    before = _tree_digest(project)

    result = _invoke(APPLY_FLAG, *([JSON_FLAG] if json_output else []))

    assert result.exit_code == 2, result.output
    assert _tree_digest(project) == before
    if json_output:
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "config_error"
        assert "keep_runs" in payload["error"]["message"]
    else:
        assert "keep_runs" in result.output


@pytest.mark.parametrize("json_output", [False, True])
def test_registry_drift_is_an_internal_error_exit_2(project: Path, runs: dict[str, Path], monkeypatch: pytest.MonkeyPatch, json_output: bool) -> None:
    def _drift(*_args: object, **_kwargs: object) -> retention.RetentionPlan:
        raise retention.RetentionPolicyDriftError("surface x has no collector")

    monkeypatch.setattr(_event_logs_doctor, "scan_retention", _drift)
    before = _tree_digest(project)

    result = _invoke(APPLY_FLAG, *([JSON_FLAG] if json_output else []))

    assert result.exit_code == 2, result.output
    assert _tree_digest(project) == before
    if json_output:
        payload = json.loads(result.stdout)
        assert payload["error"]["code"] == "retention_policy_drift"
        assert "surface x has no collector" in payload["error"]["message"]
    else:
        assert "surface x has no collector" in result.output


@pytest.mark.parametrize("json_output", [False, True])
def test_a_failed_deletion_exits_1_and_is_reported(project: Path, runs: dict[str, Path], monkeypatch: pytest.MonkeyPatch, json_output: bool) -> None:
    def _refuse(_path: Path) -> None:
        raise OSError("disk says no")

    monkeypatch.setattr(retention, "_remove_tree", _refuse)

    result = _invoke(APPLY_FLAG, *([JSON_FLAG] if json_output else []))

    assert result.exit_code == 1, result.output
    assert runs["candidate"].is_dir()
    if json_output:
        payload = json.loads(result.stdout)
        assert [(f["path"], f["error"]) for f in payload["failed"]] == [(_rel(runs["candidate"], project), "disk says no")]
        assert payload["deleted"] == []
    else:
        assert "disk says no" in result.output
        assert "Failed" in result.output


@pytest.mark.parametrize("args", [(), (APPLY_FLAG,)])
def test_nothing_to_clean_exits_0_with_a_clear_line(project: Path, args: tuple[str, ...]) -> None:
    result = _invoke(*args)

    assert result.exit_code == 0, result.output
    assert "Nothing to remove" in result.output


def test_not_in_a_project_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_event_logs_doctor, "locate_project_root", lambda: None)

    result = _invoke(JSON_FLAG)

    assert result.exit_code == 2
    assert json.loads(result.stdout)["error"]["code"] == "not_in_project"


def test_doctor_help_lists_event_logs() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert EVENT_LOGS in result.output
