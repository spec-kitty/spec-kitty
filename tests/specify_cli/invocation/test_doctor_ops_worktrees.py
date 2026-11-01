"""`spec-kitty doctor ops` across every checkout of the repository (#6661).

Op records are owned by the checkout that invoked the command (#6564, #6664), so a
record can live in a linked worktree's ``kitty-ops/``. These tests pin the
repository-wide sweep: the listing must show a worktree Op, and ``--close-stale``
must close each Op through the checkout that owns it, so the closure spine lands
where the record lives.

Every fixture is a real git repository, because the checkout set comes from
``git worktree list``.
"""

from __future__ import annotations

import json
from kernel.clock import datetime, UTC
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.specify_cli.invocation._op_git import (
    checkout_issue_branch,
    run_git,
    track_op_record_on_current_branch,
)

from specify_cli import app as cli_app
from specify_cli.invocation import op_custody
from specify_cli.invocation.writer import EVENTS_DIR, read_op_closures
from specify_cli.doctor import ops as ops_module
from specify_cli.doctor.ops import close_stale_ops, list_orphan_ops, scan_op_records

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)

_ROOT_OP = "01KTBE0RQY9XKTV0PE49PJDMRM"
_LANE_OP = "01KTBE0RQY9XKTV0PE49PJDMRN"
_OTHER_LANE_OP = "01KTBE0RQY9XKTV0PE49PJDMRP"
_STALE_STARTED_AT = "2026-06-05T00:00:00+00:00"


def _repo(tmp_path: Path) -> Path:
    """A real repository with a ``.kittify`` marker, on ``main``."""
    root = tmp_path / "primary"
    root.mkdir()
    run_git(root, "init", "-b", "main")
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("project: fixture\n", encoding="utf-8")
    run_git(root, "add", "-A")
    run_git(root, "commit", "-m", "init")
    return root


def _add_worktree(root: Path, name: str, branch: str) -> Path:
    lane = root.parent / name
    run_git(root, "worktree", "add", "-b", branch, str(lane))
    return lane


def _write_stale_op(checkout: Path, invocation_id: str) -> Path:
    """Write a started-only (orphan) Op record in *checkout*."""
    ops_dir = checkout / EVENTS_DIR
    ops_dir.mkdir(parents=True, exist_ok=True)
    path = ops_dir / f"{invocation_id}.jsonl"
    path.write_text(
        json.dumps(
            {
                "event": "started",
                "invocation_id": invocation_id,
                "profile_id": "implementer-fixture",
                "action": "implement",
                "started_at": _STALE_STARTED_AT,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _doctor_ops(cwd: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> object:
    monkeypatch.chdir(cwd)
    return runner.invoke(cli_app, ["doctor", "ops", *args])


# ---------------------------------------------------------------------------
# Listing: an Op opened in a linked worktree is visible
# ---------------------------------------------------------------------------


def test_doctor_ops_lists_an_op_held_by_a_linked_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    lane = _add_worktree(root, "lane", "topic")
    _write_stale_op(lane, _LANE_OP)

    result = _doctor_ops(root, monkeypatch, "--json")

    assert result.exit_code == 1, result.output
    assert json.loads(result.output) == [{"path": f"../lane/{EVENTS_DIR}/{_LANE_OP}.jsonl"}]


def test_doctor_ops_lists_a_worktree_op_from_inside_the_worktree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    lane = _add_worktree(root, "lane", "topic")
    _write_stale_op(lane, _LANE_OP)

    result = _doctor_ops(lane, monkeypatch, "--json")

    assert result.exit_code == 1, result.output
    assert json.loads(result.output) == [{"path": f"../lane/{EVENTS_DIR}/{_LANE_OP}.jsonl"}]


def test_doctor_ops_lists_every_checkout_root_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    lane = _add_worktree(root, "lane", "topic")
    other = _add_worktree(root, "other", "other-topic")
    _write_stale_op(root, _ROOT_OP)
    _write_stale_op(lane, _LANE_OP)
    _write_stale_op(other, _OTHER_LANE_OP)

    result = _doctor_ops(root, monkeypatch, "--json")

    assert result.exit_code == 1, result.output
    assert json.loads(result.output) == [
        {"path": f"{EVENTS_DIR}/{_ROOT_OP}.jsonl"},
        {"path": f"../lane/{EVENTS_DIR}/{_LANE_OP}.jsonl"},
        {"path": f"../other/{EVENTS_DIR}/{_OTHER_LANE_OP}.jsonl"},
    ]


# ---------------------------------------------------------------------------
# Sweep: each Op closes in the checkout that owns it
# ---------------------------------------------------------------------------


def test_sweep_closes_a_worktree_op_on_the_worktree_spine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    # #6410: the auto-commit only fires where the primary branch tracks an Op
    # record, so seed one (closed, never an orphan) on `main` first.
    track_op_record_on_current_branch(root)
    lane = _add_worktree(root, "lane", "topic")
    checkout_issue_branch(root, "issue-fixture-topic")
    _write_stale_op(lane, _LANE_OP)
    record = lane / EVENTS_DIR / f"{_LANE_OP}.jsonl"
    record_before = record.read_bytes()

    result = _doctor_ops(root, monkeypatch, "--close-stale", "--threshold", "0", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [entry["invocation_id"] for entry in payload["open_ops"]] == [_LANE_OP]
    assert payload["open_ops"][0]["action_taken"] == "closed_abandoned"
    assert payload["open_ops"][0]["commit"] == "committed"
    assert payload["swept"] == 1
    # The closure landed on the worktree's spine, not the root checkout's.
    assert [event.invocation_id for event in read_op_closures(lane)] == [_LANE_OP]
    assert read_op_closures(root) == []
    # And the record itself is byte-frozen: only the spine changed.
    assert record.read_bytes() == record_before


def test_sweep_closes_ops_in_every_checkout_in_one_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path)
    track_op_record_on_current_branch(root)
    lane = _add_worktree(root, "lane", "topic")
    other = _add_worktree(root, "other", "other-topic")
    checkout_issue_branch(root, "issue-fixture-topic")
    _write_stale_op(root, _ROOT_OP)
    _write_stale_op(lane, _LANE_OP)
    _write_stale_op(other, _OTHER_LANE_OP)

    swept = close_stale_ops(root, threshold_hours=0, now=_NOW)

    assert swept.swept == 3
    assert {entry.action_taken for entry in swept.open_ops} == {"closed_abandoned"}
    # Each checkout's spine holds exactly its own closure.
    assert [event.invocation_id for event in read_op_closures(root)] == [_ROOT_OP]
    assert [event.invocation_id for event in read_op_closures(lane)] == [_LANE_OP]
    assert [event.invocation_id for event in read_op_closures(other)] == [_OTHER_LANE_OP]
    # And each closure was committed on the branch of the checkout that owns it:
    # the worktree's own history gains the sweep commit, not only the root's.
    assert {entry.commit for entry in swept.open_ops} == {"committed"}
    for checkout in (root, lane, other):
        assert "(doctor sweep)" in run_git(checkout, "log", "-1", "--format=%s")

    # A second run has nothing left to close, from any checkout.
    again = close_stale_ops(root, threshold_hours=0, now=_NOW)
    assert again.swept == 0
    assert again.open_ops == []
    listed = _doctor_ops(root, monkeypatch, "--json")
    assert listed.exit_code == 0, listed.output
    assert json.loads(listed.output) == []


# ---------------------------------------------------------------------------
# Cost and degraded paths
# ---------------------------------------------------------------------------


def test_doctor_ops_enumerates_checkouts_once_per_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001: one `git worktree list` per run, never one per record or checkout."""
    root = _repo(tmp_path)
    lane = _add_worktree(root, "lane", "topic")
    other = _add_worktree(root, "other", "other-topic")
    for checkout, invocation_id in ((root, _ROOT_OP), (lane, _LANE_OP), (other, _OTHER_LANE_OP)):
        _write_stale_op(checkout, invocation_id)
    calls: list[tuple[str, ...]] = []
    real_git_lines = op_custody._git_lines

    def counting(cwd: Path, *args: str) -> list[str] | None:
        calls.append(args)
        return real_git_lines(cwd, *args)

    monkeypatch.setattr(op_custody, "_git_lines", counting)

    result = _doctor_ops(root, monkeypatch, "--json")

    assert result.exit_code == 1, result.output
    assert len(json.loads(result.output)) == 3
    assert calls.count(("worktree", "list", "--porcelain")) == 1
    assert all(args == ("worktree", "list", "--porcelain") for args in calls)


def test_sweep_enumerates_checkouts_once_for_many_ops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A sweep over several checkouts still runs one `git worktree list`."""
    root = _repo(tmp_path)
    lane = _add_worktree(root, "lane", "topic")
    for invocation_id in (_ROOT_OP, _OTHER_LANE_OP):
        _write_stale_op(root, invocation_id)
    _write_stale_op(lane, _LANE_OP)
    calls: list[tuple[str, ...]] = []
    real_git_lines = op_custody._git_lines

    def counting(cwd: Path, *args: str) -> list[str] | None:
        calls.append(args)
        return real_git_lines(cwd, *args)

    monkeypatch.setattr(op_custody, "_git_lines", counting)

    report = close_stale_ops(root, threshold_hours=0, now=_NOW)

    assert report.swept == 3
    assert calls.count(("worktree", "list", "--porcelain")) == 1


def test_checkout_enumeration_degrades_to_the_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No usable git: the sweep behaves exactly as it did before #6661."""
    root = _repo(tmp_path)
    lane = _add_worktree(root, "lane", "topic")
    _write_stale_op(root, _ROOT_OP)
    _write_stale_op(lane, _LANE_OP)
    monkeypatch.setattr(op_custody, "_git_lines", lambda cwd, *args: None)

    assert list(op_custody.repository_checkouts(root)) == []
    pairs, unreadable = scan_op_records(root)
    assert [record for _checkout, record in pairs] == list_orphan_ops(root)
    assert [record for _checkout, record in pairs] == [root / EVENTS_DIR / f"{_ROOT_OP}.jsonl"]
    assert unreadable == []


def test_unreadable_checkout_does_not_hide_the_others(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """NFR-002: one broken worktree must not fail the whole repository-wide sweep."""
    root = _repo(tmp_path)
    lane = _add_worktree(root, "lane", "topic")
    _write_stale_op(root, _ROOT_OP)
    _write_stale_op(lane, _LANE_OP)
    real_closed_ids = ops_module.closed_invocation_ids

    def broken_spine(checkout: Path) -> set[str]:
        if Path(checkout).resolve() == lane.resolve():
            raise PermissionError(f"cannot read {checkout}")
        return real_closed_ids(checkout)

    monkeypatch.setattr(ops_module, "closed_invocation_ids", broken_spine)

    with caplog.at_level("WARNING", logger="specify_cli.doctor.ops"):
        pairs, unreadable = scan_op_records(root)

    assert [record for _checkout, record in pairs] == [root / EVENTS_DIR / f"{_ROOT_OP}.jsonl"]
    assert unreadable == [lane]
    assert any(str(lane) in record.getMessage() for record in caplog.records)

    # The operator is told, on stderr, that a checkout was skipped: `--json` stdout
    # stays the frozen payload, and the exit code is unchanged.
    listed = _doctor_ops(root, monkeypatch, "--json")
    assert listed.exit_code == 1, listed.output
    assert json.loads(listed.stdout) == [{"path": f"{EVENTS_DIR}/{_ROOT_OP}.jsonl"}]
    assert "could not read Op records in ../lane" in listed.stderr
