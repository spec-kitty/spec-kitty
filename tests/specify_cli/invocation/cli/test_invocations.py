"""Integration tests for spec-kitty invocations list CLI surface.

Covers:
- Empty log → empty JSON array
- 3 records → 3 results
- --limit 2 with 5 files → at most 2 results
- --profile implementer-fixture filters by content, not filename
- Status: open vs closed shown correctly
- Performance gate: < 200 ms at 10 000 files (NFR-008)
"""

from __future__ import annotations

from kernel.clock import now_utc_iso
import json
import sys
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from tests._perf_helpers import assert_timing_budget

from specify_cli import app as cli_app
from specify_cli.cli.commands.invocations_cmd import (
    EVENTS_DIR,
    INDEX_PATH,
    _iter_records,
    _read_first_line,
    _read_last_line,
)
from specify_cli.invocation.record import OpStartedEvent
from specify_cli.invocation.writer import InvocationWriter

# Marked for mutmut sandbox skip — subprocess CLI invocation.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]
class ArgvCliRunner(CliRunner):
    def invoke(self, app, args=None, **kwargs):  # type: ignore[no-untyped-def]
        argv = ["spec-kitty", *(list(args) if args is not None and not isinstance(args, str) else [])]
        with patch.object(sys, "argv", argv):
            return super().invoke(app, args, **kwargs)


runner = ArgvCliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_events_dir(base: Path) -> Path:
    events_dir = base / EVENTS_DIR
    events_dir.mkdir(parents=True, exist_ok=True)
    return events_dir


def _write_started(
    events_dir: Path,
    *,
    invocation_id: str,
    profile_id: str = "implementer-fixture",
    action: str = "implement",
    started_at: str | None = None,
) -> Path:
    if started_at is None:
        started_at = now_utc_iso()
    record = {
        "event": "started",
        "invocation_id": invocation_id,
        "profile_id": profile_id,
        "action": action,
        "request_text": "test request",
        "actor": "claude",
        "mode_of_work": "task_execution",
        "governance_context_hash": "abcdef0123456789",
        "governance_context_available": True,
        "started_at": started_at,
    }
    path = events_dir / f"{invocation_id}.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    return path


def _seed_index_entry(repo_root: Path, record: Mapping[str, Any]) -> None:
    """Append one raw index line, bypassing ``InvocationWriter``.

    Needed where the writer cannot produce the fixture: bulk benchmark seeding
    over hand-written op files, and an index row with no matching op file
    (the dangling-entry shape the indexed reader must tolerate).
    """
    index_path = repo_root / INDEX_PATH
    index_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {key: record[key] for key in ("invocation_id", "profile_id", "started_at")}
    with index_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _write_started_via_writer(repo_root: Path, *, invocation_id: str) -> Path:
    """Write a real ``started`` event (op file plus index entry) through ``InvocationWriter``."""
    event = OpStartedEvent(
        invocation_id=invocation_id,
        profile_id="implementer-fixture",
        action="implement",
        request_text="test request",
        governance_context_hash="abcdef0123456789",
        governance_context_available=True,
        actor="claude",
        mode_of_work="task_execution",
        started_at=now_utc_iso(),
    )
    return InvocationWriter(repo_root).write_started(event)


def _write_completed(path: Path, *, invocation_id: str, outcome: str = "done", closed_by: str = "agent") -> None:
    record = {
        "event": "completed",
        "invocation_id": invocation_id,
        "completed_at": now_utc_iso(),
        "outcome": outcome,
        "closed_by": closed_by,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def _new_ulid() -> str:
    """Generate a new ULID string using the codebase's available library."""
    import ulid as _ulid_mod  # python-ulid: ULID() generates a new one

    return str(_ulid_mod.ULID())


def create_fixture_invocations(
    events_dir: Path,
    count: int,
    profile_id: str = "implementer-fixture",
    *,
    write_index: bool = True,
) -> None:
    """Create *count* synthetic JSONL files for benchmarking.

    When *write_index* is True (the default) also appends entries to the
    invocation index so the benchmark tests the fast index-based path.
    """
    events_dir.mkdir(parents=True, exist_ok=True)
    # Derive repo_root from events_dir: events_dir = <root>/kitty-ops
    repo_root = events_dir.parent
    for _ in range(count):
        inv_id = _new_ulid()
        started_at = now_utc_iso()
        record = {
            "event": "started",
            "invocation_id": inv_id,
            "profile_id": profile_id,
            "action": "implement",
            "request_text": "test request",
            "actor": "claude",
            "mode_of_work": "task_execution",
            "governance_context_hash": "abcdef0123456789",
            "governance_context_available": True,
            "started_at": started_at,
        }
        path = events_dir / f"{inv_id}.jsonl"
        path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        if write_index:
            _seed_index_entry(repo_root, record)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


class TestReadFirstLine:
    def test_reads_first_line(self, tmp_path: Path) -> None:
        path = tmp_path / "test.jsonl"
        first = {"event": "started", "invocation_id": "A"}
        second = {"event": "completed", "invocation_id": "A"}
        path.write_text(
            json.dumps(first) + "\n" + json.dumps(second) + "\n",
            encoding="utf-8",
        )
        result = _read_first_line(path)
        assert result is not None
        assert result["event"] == "started"

    def test_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert _read_first_line(path) is None

    def test_returns_none_for_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "missing.jsonl"
        assert _read_first_line(path) is None


class TestReadLastLine:
    def test_reads_last_line_of_single_line_file(self, tmp_path: Path) -> None:
        path = tmp_path / "single.jsonl"
        record = {"event": "started", "invocation_id": "A"}
        path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        result = _read_last_line(path)
        assert result is not None
        assert result["event"] == "started"

    def test_reads_last_line_of_two_line_file(self, tmp_path: Path) -> None:
        path = tmp_path / "two.jsonl"
        first = {"event": "started", "invocation_id": "A"}
        last = {"event": "completed", "invocation_id": "A"}
        path.write_text(
            json.dumps(first) + "\n" + json.dumps(last) + "\n",
            encoding="utf-8",
        )
        result = _read_last_line(path)
        assert result is not None
        assert result["event"] == "completed"

    def test_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        assert _read_last_line(path) is None


# ---------------------------------------------------------------------------
# Integration tests via CLI (monkeypatched repo root)
# ---------------------------------------------------------------------------


class TestInvocationsListJSON:
    def test_empty_log_returns_empty_array(self, tmp_path: Path) -> None:
        """Empty log directory → empty JSON array."""
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(cli_app, ["invocations", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data == []

    def test_three_records_returns_three(self, tmp_path: Path) -> None:
        """After creating 3 records, list returns 3."""
        events_dir = _make_events_dir(tmp_path)
        for _ in range(3):
            _write_started(events_dir, invocation_id=_new_ulid())

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(cli_app, ["invocations", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 3

    def test_limit_caps_results(self, tmp_path: Path) -> None:
        """--limit 2 with 5 files returns at most 2 records."""
        events_dir = _make_events_dir(tmp_path)
        for _ in range(5):
            _write_started(events_dir, invocation_id=_new_ulid())

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(cli_app, ["invocations", "list", "--limit", "2", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) <= 2

    def test_profile_filter_reads_content_not_filename(self, tmp_path: Path) -> None:
        """--profile implementer-fixture filters out reviewer-fixture records.

        Filenames are ``<invocation_id>.jsonl`` with no profile prefix —
        filtering MUST read the ``profile_id`` field from file content.
        """
        events_dir = _make_events_dir(tmp_path)
        # 2 implementer records
        for _ in range(2):
            _write_started(
                events_dir,
                invocation_id=_new_ulid(),
                profile_id="implementer-fixture",
            )
        # 1 reviewer record — same filename pattern, different profile_id in content
        _write_started(
            events_dir,
            invocation_id=_new_ulid(),
            profile_id="reviewer-fixture",
        )

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(
                cli_app,
                ["invocations", "list", "--profile", "implementer-fixture", "--json"],
            )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert len(data) == 2
        assert all(r["profile_id"] == "implementer-fixture" for r in data)

    def test_status_open_vs_closed(self, tmp_path: Path) -> None:
        """Closed records carry status=closed; open records carry status=open."""
        events_dir = _make_events_dir(tmp_path)

        open_id = _new_ulid()
        _write_started(events_dir, invocation_id=open_id)

        closed_id = _new_ulid()
        closed_path = _write_started(events_dir, invocation_id=closed_id)
        _write_completed(closed_path, invocation_id=closed_id, outcome="done")

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(cli_app, ["invocations", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        statuses = {r["invocation_id"]: r["status"] for r in data}
        assert statuses[open_id] == "open"
        assert statuses[closed_id] == "closed"

    def test_status_closed_when_correlation_links_follow_completion(self, tmp_path: Path) -> None:
        """Closed status must not depend on completed being the final JSONL line."""
        events_dir = _make_events_dir(tmp_path)
        invocation_id = _new_ulid()
        path = _write_started(events_dir, invocation_id=invocation_id)
        _write_completed(path, invocation_id=invocation_id, outcome="done")
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "artifact_link", "invocation_id": invocation_id, "ref": "spec.md"}) + "\n")
            f.write(json.dumps({"event": "commit_link", "invocation_id": invocation_id, "sha": "abc123"}) + "\n")

        records = list(_iter_records(events_dir, None, 10, repo_root=tmp_path))
        record = next(r for r in records if r["invocation_id"] == invocation_id)
        assert record["status"] == "closed"
        assert record["outcome"] == "done"

    def test_indexed_status_closed_when_correlation_links_follow_completion(self, tmp_path: Path) -> None:
        """Index path must also scan for completed before post-terminal links."""
        events_dir = _make_events_dir(tmp_path)
        invocation_id = _new_ulid()
        path = _write_started_via_writer(tmp_path, invocation_id=invocation_id)
        _write_completed(path, invocation_id=invocation_id, outcome="done")
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "artifact_link", "invocation_id": invocation_id, "ref": "spec.md"}) + "\n")

        records = list(_iter_records(events_dir, None, 10, repo_root=tmp_path))
        record = next(r for r in records if r["invocation_id"] == invocation_id)
        assert record["status"] == "closed"
        assert record["outcome"] == "done"

    def test_indexed_reader_skips_dangling_index_entries_after_migration_delete(self, tmp_path: Path) -> None:
        """Deleted unsalvageable op files must not reappear as phantom open Ops."""
        events_dir = _make_events_dir(tmp_path)
        live_id = _new_ulid()
        deleted_id = _new_ulid()

        _write_started_via_writer(tmp_path, invocation_id=live_id)
        # An index row whose op file was deleted (migration): the public writer cannot produce it.
        _seed_index_entry(
            tmp_path,
            {
                "invocation_id": deleted_id,
                "profile_id": "implementer-fixture",
                "started_at": now_utc_iso(),
            },
        )

        records = list(_iter_records(events_dir, None, 10, repo_root=tmp_path))
        listed_ids = {record["invocation_id"] for record in records}
        assert live_id in listed_ids
        assert deleted_id not in listed_ids

# ---------------------------------------------------------------------------
# Performance gate (NFR-008)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_list_returns_100_records_from_10k_files(tmp_path: Path) -> None:
    """invocations list returns exactly 100 records from a 10 000-file audit log.

    Uses the index-based path (write_index=True) which is the production path
    when InvocationWriter.write_started() is used.
    """
    events_dir = tmp_path / EVENTS_DIR
    # write_index=True (default) — mimics production InvocationWriter behaviour.
    create_fixture_invocations(events_dir, 10_000, write_index=True)

    records = list(_iter_records(events_dir, None, 100, repo_root=tmp_path))

    assert len(records) == 100, f"Expected 100 records, got {len(records)}"


@pytest.mark.slow
@pytest.mark.performance
def test_list_performance_10k(tmp_path: Path) -> None:
    """invocations list for 100 records from 10 000 files must complete in < 200 ms.

    This validates NFR-008: the command must not become unusably slow even when
    the audit log has grown to 10 000 JSONL files.

    Uses the index-based path (write_index=True) which is the production path
    when InvocationWriter.write_started() is used.
    """
    events_dir = tmp_path / EVENTS_DIR
    # write_index=True (default) — mimics production InvocationWriter behaviour.
    create_fixture_invocations(events_dir, 10_000, write_index=True)

    start = time.monotonic()
    list(_iter_records(events_dir, None, 100, repo_root=tmp_path))
    elapsed = time.monotonic() - start

    assert_timing_budget(elapsed, 0.200, name="invocations list (10k files, index path)")


# ---------------------------------------------------------------------------
# Schema v2: closed-record display + legacy warn-and-skip (WP01)
# ---------------------------------------------------------------------------


class TestInvocationsListV2:
    def test_closed_record_exposes_outcome_and_closed_by(self, tmp_path: Path) -> None:
        """Closed v2 Ops expose outcome and closed_by in JSON output."""
        events_dir = _make_events_dir(tmp_path)
        open_id = "01KPQRX2EVGMRVB4Q1JQBAZJV1"
        closed_id = "01KPQRX2EVGMRVB4Q1JQBAZJV2"
        _write_started(events_dir, invocation_id=open_id)
        path = _write_started(events_dir, invocation_id=closed_id)
        _write_completed(path, invocation_id=closed_id, outcome="failed", closed_by="doctor_sweep")

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(cli_app, ["invocations", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = {r["invocation_id"]: r for r in json.loads(result.output)}
        assert data[open_id]["status"] == "open"
        assert "closed_by" not in data[open_id]
        assert data[closed_id]["status"] == "closed"
        assert data[closed_id]["outcome"] == "failed"
        assert data[closed_id]["closed_by"] == "doctor_sweep"

    def test_table_output_shows_outcome_and_closed_by_columns(self, tmp_path: Path) -> None:
        events_dir = _make_events_dir(tmp_path)
        closed_id = "01KPQRX2EVGMRVB4Q1JQBAZJV2"
        path = _write_started(events_dir, invocation_id=closed_id)
        _write_completed(path, invocation_id=closed_id, outcome="done", closed_by="agent")

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(cli_app, ["invocations", "list"])
        assert result.exit_code == 0, result.output
        assert "Outcome" in result.output
        assert "Closed By" in result.output
        assert "agent" in result.output

    def test_legacy_record_warns_and_skips(self, tmp_path: Path) -> None:
        """Legacy (pre-v2) lines produce one warning naming spec-kitty upgrade, never a traceback."""
        events_dir = _make_events_dir(tmp_path)
        v2_id = "01KPQRX2EVGMRVB4Q1JQBAZJV1"
        legacy_id = "01KPQRX2EVGMRVB4Q1JQBAZJV5"
        _write_started(events_dir, invocation_id=v2_id)
        # Legacy v1 started line: no actor / mode_of_work.
        legacy_record = {
            "event": "started",
            "invocation_id": legacy_id,
            "profile_id": "implementer-fixture",
            "action": "implement",
            "started_at": "2026-04-22T06:00:00+00:00",
        }
        (events_dir / f"{legacy_id}.jsonl").write_text(json.dumps(legacy_record) + "\n", encoding="utf-8")

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(cli_app, ["invocations", "list"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "spec-kitty upgrade" in result.output
        assert result.output.count("legacy Op record") == 1
        # The v2 record is still listed; the legacy one is skipped
        # (verified via the JSON surface, which is not column-truncated).
        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            json_result = runner.invoke(cli_app, ["invocations", "list", "--json"], catch_exceptions=False)
        listed_ids = {r["invocation_id"] for r in json.loads(json_result.output[json_result.output.index("[") :])}
        assert v2_id in listed_ids
        assert legacy_id not in listed_ids

    def test_legacy_completed_line_warns_and_skips(self, tmp_path: Path) -> None:
        """A v1 completed line (no closed_by) is skipped with the migration warning."""
        events_dir = _make_events_dir(tmp_path)
        legacy_id = "01KPQRX2EVGMRVB4Q1JQBAZJV6"
        path = _write_started(events_dir, invocation_id=legacy_id)
        legacy_completed = {
            "event": "completed",
            "invocation_id": legacy_id,
            "completed_at": "2026-04-22T07:00:00+00:00",
            "outcome": None,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(legacy_completed) + "\n")

        with pytest.MonkeyPatch().context() as mp:
            mp.setattr(
                "specify_cli.cli.commands.invocations_cmd.find_repo_root",
                lambda: tmp_path,
            )
            result = runner.invoke(cli_app, ["invocations", "list"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        assert "spec-kitty upgrade" in result.output
