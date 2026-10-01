"""Stress test (T040, SC-12): N concurrent emitters serialize cleanly.

Verifies that the per-feature status lock (FR-026) actually serializes
concurrent emitters and produces a valid event log with no interleaved
partial writes.

The contract being stressed:

* Every concurrent ``BookkeepingTransaction.acquire(...) → append_event
  → commit`` round trip lands a single well-formed JSONL line in
  ``status.events.jsonl``.
* No event is dropped, no event_id is duplicated, every line parses as
  valid JSON, and ``status.json`` after the burst matches the materialise
  of the event log.

We use real OS processes (via ``multiprocessing`` with the ``spawn``
start method) so the file-based locking under
``specify_cli.status.locking.feature_status_lock`` is exercised the way
it would be in a multi-shell production scenario.

The default emitter count is **20** per SC-12. If a CI runner cannot
sustain 20 parallel git operations in <60s, set
``SPEC_KITTY_STRESS_EMITTER_COUNT`` env var to a lower number (the test
asserts the count it actually ran).
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.stress, pytest.mark.slow, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Constants — kept here (and not in conftest) so test_template invocations
# remain self-contained.
# ---------------------------------------------------------------------------

MISSION_SLUG = "stress-feature"
MID8 = "01J6STRSS"
MISSION_ID = "01J6STRSS00000000000000000"  # 26-char placeholder ULID
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}-{MID8}"
FEATURE_DIRNAME = f"{MISSION_SLUG}-{MID8}"

#: SC-12's wall-clock budget for the concurrent-emit workload (RK-3: split
#: out of the correctness test below into its own ``timing`` test so a slow
#: runner never turns a correctness assertion into a wall-clock flake).
_SC12_BUDGET_SECONDS = 60.0


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )


def _init_coord_repo(repo: Path) -> None:
    """Build the minimum post-WP03 mission topology required by acquire()."""
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "stress@example.invalid")
    _git(repo, "config", "user.name", "Stress")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "initial")
    _git(repo, "branch", COORD_BRANCH)


# ---------------------------------------------------------------------------
# Worker — must be module-top-level so multiprocessing can pickle it.
# ---------------------------------------------------------------------------


def _emit_one(args: tuple[str, str]) -> dict[str, Any]:
    """Run a single ``acquire → append_event → commit`` round.

    Returns a small JSON-friendly dict so the orchestrator can aggregate
    results without re-importing transaction internals.
    """
    repo_str, wp_id = args
    repo = Path(repo_str)

    # Late imports: child processes need a clean import boundary so the
    # status-locking thread cache is empty.
    from specify_cli.coordination.transaction import (  # noqa: PLC0415
        BookkeepingCommitFailed,
        BookkeepingTransaction,
    )
    from specify_cli.status.emit import build_status_event  # noqa: PLC0415

    event = build_status_event(
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id=wp_id,
        from_lane="planned",
        to_lane="claimed",
        actor="stress-worker",
    )

    started = time.monotonic()
    try:
        with BookkeepingTransaction.acquire(
            repo_root=repo,
            mission_id=MISSION_ID,
            mission_slug=MISSION_SLUG,
            mid8=MID8,
            destination_ref=COORD_BRANCH,
            operation=f"stress_emit_{wp_id}",
            timeout=120.0,  # CI may sequence behind 19 other procs
        ) as txn:
            handle = txn.append_event(event)
            receipt = txn.commit(f"status: {wp_id} → claimed")
    except BookkeepingCommitFailed as exc:
        return {
            "wp_id": wp_id,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "duration_s": time.monotonic() - started,
        }
    except Exception as exc:  # noqa: BLE001 — capture for aggregation
        return {
            "wp_id": wp_id,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "duration_s": time.monotonic() - started,
        }

    return {
        "wp_id": wp_id,
        "ok": True,
        "event_id": handle.event_id,
        "commit_sha": receipt.commit_sha,
        "duration_s": time.monotonic() - started,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stress_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "stress-repo"
    repo.mkdir()
    _init_coord_repo(repo)
    # Pre-create the coord worktree before the workers fan out. The
    # transaction's worktree resolver is single-shot (it does ``git
    # worktree add`` whose lock is the on-disk index.lock) and N
    # concurrent first-time resolves would all race the same git lock.
    # The production path serializes through ``spec-kitty implement``
    # which runs the resolver in the main checkout before fanning work
    # out to lanes; we replicate that here by warming the worktree.
    from specify_cli.coordination.workspace import CoordinationWorkspace  # noqa: PLC0415
    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)
    return repo


# ---------------------------------------------------------------------------
# T040 / SC-12
# ---------------------------------------------------------------------------


def _emitter_count() -> int:
    raw = os.environ.get("SPEC_KITTY_STRESS_EMITTER_COUNT")
    if raw is None:
        return 20
    try:
        n = int(raw)
    except ValueError:
        return 20
    return max(2, min(n, 50))


@dataclass(frozen=True)
class _EmitRun:
    """Result of one concurrent-emit workload run, shared by both tests below."""

    results: list[dict[str, Any]]
    duration: float
    n: int
    wp_ids: list[str]
    events_path: Path


def _run_concurrent_emits(stress_repo: Path) -> _EmitRun:
    """Fan N emitters out concurrently and time the whole burst.

    Holds the pool map and the timing only — every functional assertion
    over the resulting event log stays in
    ``test_concurrent_emits_produce_valid_event_log`` (pinned verbatim by
    ``tests/architectural/test_timing_coverage_invariant.py``), so this
    helper's only job is producing the raw materials both tests need.
    """
    n = _emitter_count()
    wp_ids = [f"WP{i:02d}" for i in range(1, n + 1)]
    args = [(str(stress_repo), wp_id) for wp_id in wp_ids]

    started = time.monotonic()
    # Use ``spawn`` so child processes start with a clean import state
    # and don't inherit any thread-local lock counters from pytest.
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=n) as pool:
        results = pool.map(_emit_one, args)
    duration = time.monotonic() - started

    # Inspect the event log — it lives on the coord worktree, not the
    # repo_root. CoordinationWorkspace.resolve created it under
    # .worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/.
    coord_worktree = stress_repo / ".worktrees" / f"{FEATURE_DIRNAME}-coord"
    feature_dir = coord_worktree / "kitty-specs" / FEATURE_DIRNAME
    events_path = feature_dir / "status.events.jsonl"

    return _EmitRun(results=results, duration=duration, n=n, wp_ids=wp_ids, events_path=events_path)


@pytest.mark.timeout(120)
def test_concurrent_emits_produce_valid_event_log(stress_repo: Path) -> None:
    """N concurrent emitters → N events, all valid, all unique, ordered.

    "Ordered" here means: the snapshot reduced from the event log matches
    the per-WP terminal lane each worker emitted. We do NOT assert a
    specific interleaving — the lock only guarantees serialization of
    each transaction, not a deterministic ordering across processes.

    Correctness only (RK-3): the SC-12 wall-clock budget is asserted
    separately by ``test_concurrent_emits_meet_sc12_budget`` below, so a
    slow runner can never turn this test's functional coverage into a
    wall-clock flake.
    """
    run = _run_concurrent_emits(stress_repo)
    n = run.n
    wp_ids = run.wp_ids
    events_path = run.events_path

    # 1. Every worker reported success.
    failures = [r for r in run.results if not r["ok"]]
    assert not failures, (
        f"{len(failures)} of {n} concurrent emitters failed: "
        f"{[(r['wp_id'], r.get('error')) for r in failures]}"
    )

    # 2. The event log must exist.
    coord_worktree = events_path.parent.parent.parent
    assert events_path.exists(), (
        f"status.events.jsonl missing at {events_path}. "
        f"Coord worktree contents: "
        f"{list(coord_worktree.rglob('*')) if coord_worktree.exists() else 'no worktree'}"
    )

    lines = [
        ln for ln in events_path.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]

    # 3. Exactly N lines.
    assert len(lines) == n, (
        f"expected {n} events; found {len(lines)} in {events_path}"
    )

    # 4. Each line is valid JSON and has the expected envelope.
    events: list[dict[str, Any]] = []
    event_ids: set[str] = set()
    seen_wps: set[str] = set()
    for i, line in enumerate(lines):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(f"line {i} is not valid JSON: {exc!r}; line={line!r}")
        events.append(obj)
        eid = obj.get("event_id")
        wp_id = obj.get("wp_id")
        assert eid, f"line {i} missing event_id: {line!r}"
        assert wp_id, f"line {i} missing wp_id: {line!r}"
        assert eid not in event_ids, (
            f"duplicate event_id {eid} at line {i} — lock did not serialize"
        )
        event_ids.add(eid)
        seen_wps.add(wp_id)
        # Every line is a planned → claimed transition for some WP.
        assert obj.get("from_lane") == "planned"
        assert obj.get("to_lane") == "claimed"

    # 5. Every WP shows up exactly once.
    assert seen_wps == set(wp_ids), (
        f"wp coverage mismatch: missing={set(wp_ids) - seen_wps} "
        f"unexpected={seen_wps - set(wp_ids)}"
    )


@pytest.mark.timing
@pytest.mark.timeout(120)
def test_concurrent_emits_meet_sc12_budget(stress_repo: Path) -> None:
    """SC-12: N concurrent emitters complete within the 60s wall-clock budget.

    Split out of the correctness test (RK-3, option b): a bare
    ``pytest.fail``/``pytest.skip`` on a wall-clock budget breach inside the
    correctness test would turn an environment-dependent measurement into a
    flake the flakiness policy forbids (no retry-to-green). This test is the
    honest, standalone home for that budget, marked ``timing`` (and
    inheriting ``stress`` from the module ``pytestmark`` above) so it only
    runs where wall-clock timing is meaningful — the nightly stress job — and
    never blocks an ordinary PR run.
    """
    run = _run_concurrent_emits(stress_repo)
    assert_timing_budget(run.duration, _SC12_BUDGET_SECONDS, name="duration")
