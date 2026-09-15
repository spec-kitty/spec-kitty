"""Tests for spec-kitty doctor ops orphan detection and stale sweep."""

from __future__ import annotations

import json
import subprocess
import time
from kernel.clock import datetime, timedelta, UTC
from pathlib import Path
from typing import Literal

import pytest
from typer.testing import CliRunner

from tests._perf_helpers import assert_timing_budget

from specify_cli import app as cli_app
from specify_cli.doctor import ops as ops_module
from specify_cli.doctor.ops import close_stale_ops, list_orphan_ops
from specify_cli.invocation import writer as writer_module
from specify_cli.invocation.executor import ProfileInvocationExecutor
from specify_cli.invocation.record import OpCompletedEvent
from specify_cli.invocation.writer import (
    EVENTS_DIR,
    OP_CLOSURES_FILENAME,
    OP_CLOSURES_RELATIVE_PATH,
    append_op_closure,
    op_closures_path,
    read_op_closures,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

_NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)


def _write_op(
    path: Path,
    *,
    completed: bool,
    started_at: str = "2026-06-05T00:00:00+00:00",
) -> None:
    events = [
        {
            "event": "started",
            "invocation_id": path.stem,
            "profile_id": "implementer-fixture",
            "action": "implement",
            "started_at": started_at,
        }
    ]
    if completed:
        events.append(
            {
                "event": "completed",
                "invocation_id": path.stem,
                "profile_id": "implementer-fixture",
                "action": "",
                "completed_at": "2026-06-05T00:01:00+00:00",
            }
        )
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def test_list_orphan_ops_ignores_missing_dir(tmp_path: Path) -> None:
    assert list_orphan_ops(tmp_path) == []


def test_list_orphan_ops_returns_started_only_files(tmp_path: Path) -> None:
    ops_dir = tmp_path / EVENTS_DIR
    ops_dir.mkdir()
    orphan = ops_dir / "01KTBE0RQY9XKTV0PE49PJDMRM.jsonl"
    closed = ops_dir / "01KTBE0RQY9XKTV0PE49PJDMRN.jsonl"
    swept = ops_dir / "01KTBE0RQY9XKTV0PE49PJDMP0.jsonl"
    _write_op(orphan, completed=False)
    _write_op(closed, completed=True)
    _write_op(swept, completed=False)
    for name in ("ops-index.jsonl", "lifecycle.jsonl", "propagation-errors.jsonl", OP_CLOSURES_FILENAME):
        (ops_dir / name).write_text("{}\n", encoding="utf-8")
    # A prior sweep closed `swept` on the closure spine — it is not an orphan.
    append_op_closure(
        tmp_path,
        OpCompletedEvent(
            invocation_id=swept.stem,
            completed_at="2026-06-05T00:01:00+00:00",
            outcome="abandoned",
            closed_by="doctor_sweep",
        ),
    )

    assert list_orphan_ops(tmp_path) == [orphan]


def test_doctor_ops_json_reports_orphan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".kittify").mkdir()
    ops_dir = tmp_path / EVENTS_DIR
    ops_dir.mkdir()
    orphan = ops_dir / "01KTBE0RQY9XKTV0PE49PJDMRM.jsonl"
    _write_op(orphan, completed=False)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(cli_app, ["doctor", "ops", "--json"])

    assert result.exit_code == 1
    assert json.loads(result.output) == [{"path": f"{EVENTS_DIR}/{orphan.name}"}]


# ---------------------------------------------------------------------------
# close_stale_ops (WP04 — T015/T017/T018)
# ---------------------------------------------------------------------------


def _ops_dir(tmp_path: Path) -> Path:
    ops_dir = tmp_path / EVENTS_DIR
    ops_dir.mkdir(exist_ok=True)
    return ops_dir


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _read_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_sweep_closes_only_stale_ops(tmp_path: Path) -> None:
    ops_dir = _ops_dir(tmp_path)
    stale = ops_dir / "01KTBE0RQY9XKTV0PE49PJD001.jsonl"
    fresh = ops_dir / "01KTBE0RQY9XKTV0PE49PJD002.jsonl"
    _write_op(stale, completed=False, started_at=_iso(_NOW - timedelta(hours=48)))
    _write_op(fresh, completed=False, started_at=_iso(_NOW - timedelta(hours=1)))

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 1
    assert report.skipped_fresh == 1
    assert report.threshold_hours == 24.0
    by_id = {entry.invocation_id: entry for entry in report.open_ops}
    assert by_id[stale.stem].action_taken == "closed_abandoned"
    assert by_id[stale.stem].age_hours == pytest.approx(48.0)
    assert by_id[fresh.stem].action_taken == "none"
    # The fresh op was not touched on disk.
    assert all(event["event"] == "started" for event in _read_events(fresh))


def test_sweep_writes_closed_by_and_outcome_verbatim(tmp_path: Path) -> None:
    ops_dir = _ops_dir(tmp_path)
    stale = ops_dir / "01KTBE0RQY9XKTV0PE49PJD003.jsonl"
    _write_op(stale, completed=False, started_at=_iso(_NOW - timedelta(hours=100)))
    # Capture the pre-sweep bytes for the byte-freeze check below.
    record_before = stale.read_bytes()

    close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    # #4397: the closure is recorded on the append-only spine, never by
    # mutating the pre-existing per-record archive file.
    assert stale.read_bytes() == record_before
    closures = read_op_closures(tmp_path)
    assert len(closures) == 1
    completed = closures[0]
    assert completed.invocation_id == stale.stem
    assert completed.outcome == "abandoned"
    assert completed.closed_by == "doctor_sweep"


def test_sweep_propagates_completed_event_when_sync_enabled(tmp_path: Path) -> None:
    """D1/R1 fix: sweep closes go through the shared SaaS propagator (FR-008 parity)."""
    from unittest.mock import patch

    from specify_cli.invocation.propagator import InvocationSaaSPropagator

    ops_dir = _ops_dir(tmp_path)
    stale = ops_dir / "01KTBE0RQY9XKTV0PE49PJD030.jsonl"
    _write_op(stale, completed=False, started_at=_iso(_NOW - timedelta(hours=48)))
    submitted: list[object] = []

    def _spy_submit(self: object, record: object) -> None:
        submitted.append(record)

    with patch.object(InvocationSaaSPropagator, "submit", _spy_submit):
        report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 1
    assert len(submitted) == 1, "exactly one (completed) event must be submitted"
    record = submitted[0]
    assert isinstance(record, OpCompletedEvent)
    assert record.invocation_id == stale.stem
    assert record.outcome == "abandoned"
    assert record.closed_by == "doctor_sweep"


def test_sweep_without_a_transport_closes_locally_without_propagation(tmp_path: Path) -> None:
    """LOCAL-FIRST invariant: with no transport registered, nothing is sent but
    the swept Op is still closed locally."""
    from unittest.mock import MagicMock, patch

    from specify_cli.invocation import propagator as propagator_mod

    ops_dir = _ops_dir(tmp_path)
    stale = ops_dir / "01KTBE0RQY9XKTV0PE49PJD031.jsonl"
    _write_op(stale, completed=False, started_at=_iso(_NOW - timedelta(hours=48)))

    # Run propagation synchronously so the no-transport path is exercised in-test.
    def _sync_submit(
        self: propagator_mod.InvocationSaaSPropagator, record: object
    ) -> None:
        propagator_mod._propagate_one(record, tmp_path)  # type: ignore[arg-type]

    client_spy = MagicMock(return_value=None)
    with (
        patch.object(propagator_mod.InvocationSaaSPropagator, "submit", _sync_submit),
        patch.object(propagator_mod, "_get_saas_client", client_spy),
    ):
        report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 1
    client_spy.assert_called_once()  # consulted, answered "no transport"
    # #4397: the local closure is the spine append — the per-record file is
    # never touched — and it is written even with nothing to send through.
    closures = read_op_closures(tmp_path)
    assert [event.invocation_id for event in closures] == [stale.stem]
    assert [event["event"] for event in _read_events(stale)] == ["started"]
    assert not (tmp_path / propagator_mod.PROPAGATION_ERRORS_PATH).exists(), (
        "a transport-less close is not an error and must not be logged as one"
    )


def test_sweep_fires_auto_commit_per_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops_dir = _ops_dir(tmp_path)
    for suffix in ("004", "005"):
        _write_op(
            ops_dir / f"01KTBE0RQY9XKTV0PE49PJD{suffix}.jsonl",
            completed=False,
            started_at=_iso(_NOW - timedelta(hours=48)),
        )
    commits: list[dict[str, object]] = []
    monkeypatch.setattr(
        ProfileInvocationExecutor, "_current_branch", lambda self: "main"
    )
    monkeypatch.setattr(
        "specify_cli.invocation.executor.safe_commit",
        lambda **kwargs: commits.append(kwargs),
    )

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 2
    assert len(commits) == 2  # one auto-commit per close
    # #4397: the sweep commits ONLY the append-only closure spine — never a
    # modified pre-existing per-record archive file.
    assert all(commit["paths"] == (OP_CLOSURES_RELATIVE_PATH,) for commit in commits)
    assert all(entry.commit == "committed" for entry in report.open_ops)


def test_sweep_threshold_zero_sweeps_all(tmp_path: Path) -> None:
    ops_dir = _ops_dir(tmp_path)
    for hours, suffix in ((48, "006"), (0.01, "007")):
        _write_op(
            ops_dir / f"01KTBE0RQY9XKTV0PE49PJD{suffix}.jsonl",
            completed=False,
            started_at=_iso(_NOW - timedelta(hours=hours)),
        )

    report = close_stale_ops(tmp_path, threshold_hours=0, now=_NOW)

    assert report.swept == 2
    assert report.skipped_fresh == 0
    assert all(entry.action_taken == "closed_abandoned" for entry in report.open_ops)


def test_sweep_fresh_only_sweeps_nothing(tmp_path: Path) -> None:
    ops_dir = _ops_dir(tmp_path)
    fresh = ops_dir / "01KTBE0RQY9XKTV0PE49PJD008.jsonl"
    _write_op(fresh, completed=False, started_at=_iso(_NOW - timedelta(hours=2)))

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 0
    assert report.skipped_fresh == 1
    assert not report.has_errors


def test_sweep_unparseable_started_at_treated_stale_with_warning(tmp_path: Path) -> None:
    ops_dir = _ops_dir(tmp_path)
    broken = ops_dir / "01KTBE0RQY9XKTV0PE49PJD009.jsonl"
    _write_op(broken, completed=False, started_at="not-a-timestamp")

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 1
    entry = report.open_ops[0]
    assert entry.action_taken == "closed_abandoned"
    assert entry.age_hours is None
    assert entry.parse_warning is not None


def test_sweep_handles_naive_started_at_without_crash(tmp_path: Path) -> None:
    ops_dir = _ops_dir(tmp_path)
    naive = ops_dir / "01KTBE0RQY9XKTV0PE49PJD010.jsonl"
    _write_op(
        naive,
        completed=False,
        started_at=(_NOW - timedelta(hours=48)).replace(tzinfo=None).isoformat(),
    )

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.open_ops[0].age_hours == pytest.approx(48.0)
    assert report.swept == 1


def test_sweep_race_concurrent_close_reports_already_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops_dir = _ops_dir(tmp_path)
    stale = ops_dir / "01KTBE0RQY9XKTV0PE49PJD011.jsonl"
    _write_op(stale, completed=False, started_at=_iso(_NOW - timedelta(hours=48)))

    # Simulate the race: enumeration sees the op, then a manual close lands
    # between enumeration and the sweep's close attempt.
    enumerated = list_orphan_ops(tmp_path)
    ProfileInvocationExecutor(tmp_path).complete_invocation(
        stale.stem, outcome="done", closed_by="agent"
    )
    monkeypatch.setattr(ops_module, "list_orphan_ops", lambda repo_root: enumerated)

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 0
    assert not report.has_errors
    assert report.open_ops[0].action_taken == "already_closed"
    # The manual close is untouched — no misattribution.
    events = _read_events(stale)
    assert len(events) == 2
    assert events[1]["closed_by"] == "agent"


def test_sweep_per_op_error_recorded_and_sweep_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ops_dir = _ops_dir(tmp_path)
    bad = ops_dir / "01KTBE0RQY9XKTV0PE49PJD012.jsonl"
    good = ops_dir / "01KTBE0RQY9XKTV0PE49PJD013.jsonl"
    for path in (bad, good):
        _write_op(path, completed=False, started_at=_iso(_NOW - timedelta(hours=48)))

    real_complete = ProfileInvocationExecutor.complete_invocation

    def flaky(
        self: ProfileInvocationExecutor,
        invocation_id: str,
        outcome: Literal["done", "failed", "abandoned"],
        evidence_ref: str | None = None,
        artifact_refs: list[str] | None = None,
        commit_sha: str | None = None,
        *,
        closed_by: Literal["agent", "doctor_sweep"],
    ) -> OpCompletedEvent:
        if invocation_id == bad.stem:
            raise OSError("disk full")
        return real_complete(
            self,
            invocation_id,
            outcome,
            evidence_ref,
            artifact_refs,
            commit_sha,
            closed_by=closed_by,
        )

    monkeypatch.setattr(ProfileInvocationExecutor, "complete_invocation", flaky)

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 1
    assert report.has_errors
    by_id = {entry.invocation_id: entry for entry in report.open_ops}
    assert by_id[bad.stem].error is not None
    assert by_id[good.stem].action_taken == "closed_abandoned"


# ---------------------------------------------------------------------------
# #4397: sweep closures vs the byte-frozen kitty-ops archive
# ---------------------------------------------------------------------------


def test_sweep_double_run_does_not_reopen_spine_closed_op(tmp_path: Path) -> None:
    """A spine-closed Op is no longer open: a second sweep has nothing to do."""
    ops_dir = _ops_dir(tmp_path)
    stale = ops_dir / "01KTBE0RQY9XKTV0PE49PJD014.jsonl"
    _write_op(stale, completed=False, started_at=_iso(_NOW - timedelta(hours=48)))

    first = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)
    second = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert first.swept == 1
    assert second.swept == 0
    assert second.open_ops == []
    assert list_orphan_ops(tmp_path) == []


def test_sweep_race_with_prior_spine_closure_reports_already_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Concurrent-sweep race: enumeration saw the op, another sweep closed it on
    the spine first — reported as ``already_closed``, never double-appended."""
    ops_dir = _ops_dir(tmp_path)
    stale = ops_dir / "01KTBE0RQY9XKTV0PE49PJD015.jsonl"
    _write_op(stale, completed=False, started_at=_iso(_NOW - timedelta(hours=48)))

    enumerated = list_orphan_ops(tmp_path)
    close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)
    monkeypatch.setattr(ops_module, "list_orphan_ops", lambda repo_root: enumerated)

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 0
    assert not report.has_errors
    assert report.open_ops[0].action_taken == "already_closed"
    assert len(read_op_closures(tmp_path)) == 1  # no duplicate closure line


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )
    return result.stdout


def test_sweep_on_committed_records_leaves_archive_history_intact(
    tmp_path: Path,
) -> None:
    """Acceptance (#4397): sweeping already-committed Op records must leave the
    archive gate green — per-record ``kitty-ops/`` files byte-frozen, the only
    mutation an append-only prefix-preserving addition to the closure spine.

    This is the sweep-on-committed-record case the fresh-record path could
    never evidence: the stale record and an earlier spine closure are both in
    the git baseline before the sweep runs, exactly like real stale Ops.
    """
    _git(tmp_path, "init", "-b", "issue-fixture-topic")
    _git(tmp_path, "config", "user.email", "fixture@example.com")
    _git(tmp_path, "config", "user.name", "Fixture")
    ops_dir = _ops_dir(tmp_path)
    stale = ops_dir / "01KTBE0RQY9XKTV0PE49PJD016.jsonl"
    _write_op(stale, completed=False, started_at=_iso(_NOW - timedelta(hours=175)))
    earlier = ops_dir / "01KTBE0RQY9XKTV0PE49PJD017.jsonl"
    _write_op(earlier, completed=False, started_at=_iso(_NOW - timedelta(hours=190)))
    append_op_closure(
        tmp_path,
        OpCompletedEvent(
            invocation_id=earlier.stem,
            completed_at="2026-06-05T00:01:00+00:00",
            outcome="abandoned",
            closed_by="doctor_sweep",
        ),
    )
    _git(tmp_path, "add", "kitty-ops")
    _git(tmp_path, "commit", "-m", "fixture base: committed op records and spine")
    base = _git(tmp_path, "rev-parse", "HEAD").strip()
    record_before = stale.read_bytes()
    spine_before = op_closures_path(tmp_path).read_bytes()

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 1
    by_id = {entry.invocation_id: entry for entry in report.open_ops}
    assert by_id[stale.stem].action_taken == "closed_abandoned"
    assert by_id[stale.stem].commit == "committed"
    # The per-record archive file is byte-frozen: the sweep never touches it.
    assert stale.read_bytes() == record_before
    # The only mutation under kitty-ops/ is the append-only closure spine —
    # the exact predicate the architectural archive gate enforces.
    diff = _git(tmp_path, "diff", "--name-status", base, "--", EVENTS_DIR).splitlines()
    assert diff == [f"M\t{OP_CLOSURES_RELATIVE_PATH.as_posix()}"], diff
    # The spine mutation is a prefix-preserving append of valid v2 events.
    spine_after = op_closures_path(tmp_path).read_bytes()
    assert spine_after.startswith(spine_before)
    assert spine_after.endswith(b"\n")
    assert [event.invocation_id for event in read_op_closures(tmp_path)] == [
        earlier.stem,
        stale.stem,
    ]
    # And the closure is durable + observed: the op stays closed.
    assert list_orphan_ops(tmp_path) == []


def _generate_synthetic_ops(ops_dir: Path, count: int, started_at: str) -> None:
    for i in range(count):
        invocation_id = f"01KTPERF{i:018d}"
        line = json.dumps(
            {
                "event": "started",
                "invocation_id": invocation_id,
                "profile_id": "perf-fixture",
                "action": "implement",
                "started_at": started_at,
            }
        )
        (ops_dir / f"{invocation_id}.jsonl").write_text(line + "\n", encoding="utf-8")


def test_sweep_enumeration_sweeps_1k_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 1k-file sweep sweeps every synthetic stale Op."""
    ops_dir = _ops_dir(tmp_path)
    _generate_synthetic_ops(ops_dir, 1000, _iso(_NOW - timedelta(hours=48)))
    monkeypatch.setattr(
        ProfileInvocationExecutor,
        "complete_invocation",
        lambda self, invocation_id, *a, **k: None,
    )

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 1000


def test_sweep_reads_closure_spine_once_while_performing_real_closes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One executor reads the spine once; each real close updates its snapshot."""
    ops_dir = _ops_dir(tmp_path)
    _generate_synthetic_ops(ops_dir, 3, _iso(_NOW - timedelta(hours=48)))
    real_closed_invocation_ids = writer_module.closed_invocation_ids
    reads = 0

    def counted_closed_invocation_ids(repo_root: Path) -> set[str]:
        nonlocal reads
        reads += 1
        return real_closed_invocation_ids(repo_root)

    monkeypatch.setattr(
        "specify_cli.invocation.executor.closed_invocation_ids",
        counted_closed_invocation_ids,
    )
    monkeypatch.setattr(ProfileInvocationExecutor, "_commit_op_record", lambda *a, **k: None)

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 3
    assert reads == 1
    assert len(read_op_closures(tmp_path)) == 3


@pytest.mark.performance
def test_sweep_real_closes_against_large_spine_under_2s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real spine closes stay linear when substantial closure history exists."""
    ops_dir = _ops_dir(tmp_path)
    _generate_synthetic_ops(ops_dir, 100, _iso(_NOW - timedelta(hours=48)))
    history = [
        OpCompletedEvent(
            invocation_id=f"01KTC{i:021d}",
            completed_at="2026-06-05T00:01:00+00:00",
            outcome="abandoned",
            closed_by="doctor_sweep",
        )
        for i in range(10_000)
    ]
    op_closures_path(tmp_path).write_text(
        "".join(event.to_jsonl_line() + "\n" for event in history),
        encoding="utf-8",
    )
    monkeypatch.setattr(ProfileInvocationExecutor, "_commit_op_record", lambda *a, **k: None)

    start = time.perf_counter()
    close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)
    elapsed = time.perf_counter() - start

    assert_timing_budget(elapsed, 2.0, name="100 real closes against 10k-row spine")


@pytest.mark.performance
def test_sweep_enumeration_perf_1k_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default-suite smoke that the 1k-file sweep has no order-of-magnitude regression.

    Tier-1 budget gate (docs/development/testing/testing-flakiness.md): tune, never retry.
    The original 0.5 s budget was a tight single-machine extrapolation that
    tripped on shared CI runners with no code regression (observed 1.67 s on
    GitHub Actions, 2.96 s historically). Widened to 5.0 s so runner variance is
    absorbed while a genuine O(n^2)/order-of-magnitude regression still trips it.
    The *authoritative* NFR-002 latency check is the ``@pytest.mark.slow``
    ``test_sweep_nfr_002_10k_files_under_5s`` (10k files < 5 s) below.
    """
    ops_dir = _ops_dir(tmp_path)
    _generate_synthetic_ops(ops_dir, 1000, _iso(_NOW - timedelta(hours=48)))
    monkeypatch.setattr(
        ProfileInvocationExecutor,
        "complete_invocation",
        lambda self, invocation_id, *a, **k: None,
    )

    start = time.perf_counter()
    close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)
    elapsed = time.perf_counter() - start

    assert_timing_budget(elapsed, 5.0, name="1k-file sweep")


def test_sweep_10k_files_sweeps_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """10,000 Op files are all swept (close mocked)."""
    ops_dir = _ops_dir(tmp_path)
    _generate_synthetic_ops(ops_dir, 10_000, _iso(_NOW - timedelta(hours=48)))
    monkeypatch.setattr(
        ProfileInvocationExecutor,
        "complete_invocation",
        lambda self, invocation_id, *a, **k: None,
    )

    report = close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)

    assert report.swept == 10_000


@pytest.mark.slow
@pytest.mark.performance
def test_sweep_nfr_002_10k_files_under_5s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Authoritative NFR-002 check: 10,000 Op files swept in < 5 s (close mocked)."""
    ops_dir = _ops_dir(tmp_path)
    _generate_synthetic_ops(ops_dir, 10_000, _iso(_NOW - timedelta(hours=48)))
    monkeypatch.setattr(
        ProfileInvocationExecutor,
        "complete_invocation",
        lambda self, invocation_id, *a, **k: None,
    )

    start = time.perf_counter()
    close_stale_ops(tmp_path, threshold_hours=24.0, now=_NOW)
    elapsed = time.perf_counter() - start

    assert_timing_budget(elapsed, 5.0, name="10k-file sweep (NFR-002)")
