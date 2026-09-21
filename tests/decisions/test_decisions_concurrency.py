"""T010/T011 — service-level RMW lock + barrier-synchronized concurrency
proof for the decisions index (mission local-write-safety-01M2ZPZD WP03, D4,
FR-004, SC-002).

RED-FIRST (see the PR's "Tests run" section for the captured failing-without-
-lock output): before T010, ``decisions/service.py`` did lock-free
``load_index -> mutate -> save_index`` at the SERVICE level (the
check-then-act window spans ``open_decision``'s dedup lookup through
``store.append_entry``'s write, not just ``store.save_index``'s own atomic
rename). ``test_concurrent_distinct_key_opens_preserve_all_entries`` proves
this with 8 real OS threads, each opening a decision under a DISTINCT
logical key, released simultaneously via a ``threading.Barrier`` so they
contend on the SAME initial index snapshot -- the shape that drops entries
under last-writer-wins. The assertion is SET-EQUALITY of the 8 distinct
``input_key`` values between the index and the ``DecisionPointOpened``
events (not a bare ``len(...) == 8``, which a drop+duplicate could still
pass), repeated across several iterations so a narrow race window is not
missed by chance.

``machine_file_lock`` uses ``fcntl.flock``, which is enforced per OPEN FILE
DESCRIPTION (not per-process), so genuine contention between threads in the
same process is real, not a no-op -- each worker thread opens its own file
descriptor via ``kernel.locks``' factory.

HOME isolation: the repo-wide autouse ``_isolated_worker_home`` fixture
(``tests/conftest.py``) already redirects HOME/XDG env vars into a
per-xdist-worker temp dir before every test, so the sidecar lock file and
the mission status lock this exercises never touch the real
``~/.spec-kitty`` (WP04 policy) -- no additional isolation needed here.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from specify_cli.decisions import store as _store
from specify_cli.decisions.models import OriginFlow
from specify_cli.decisions.service import open_decision
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED

#: Real thread + barrier concurrency, corrupted by co-scheduled xdist workers
#: racing coverage's per-thread trace installation -- run in the dedicated
#: `-m stress` lane (see pytest.ini's `stress` marker docstring), not the
#: fast tier. Run directly via `pytest tests/decisions/test_decisions_concurrency.py`.
pytestmark = [pytest.mark.stress]

N_WORKERS = 8
N_ITERATIONS = 5


def _setup_meta(mission_dir: Path, *, mission_id: str, mission_slug: str) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": mission_id, "mission_slug": mission_slug}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _open_one(
    repo_root: Path,
    mission_slug: str,
    worker_index: int,
    barrier: threading.Barrier,
    errors: list[BaseException],
) -> None:
    try:
        barrier.wait(timeout=10)
        open_decision(
            repo_root,
            mission_slug,
            origin_flow=OriginFlow.CHARTER,
            step_id=f"step-{worker_index}",
            input_key=f"key-{worker_index}",
            question=f"Question {worker_index}?",
            actor="concurrency-test",
        )
    except BaseException as exc:  # noqa: BLE001 - surfaced via `errors`, never swallowed
        errors.append(exc)


def _run_one_iteration(repo_root: Path, mission_slug: str) -> tuple[set[str], set[str]]:
    """Open N_WORKERS decisions with distinct keys, barrier-released together.

    Returns ``(index_keys, event_keys)`` -- the distinct ``input_key``
    values found in ``decisions/index.json`` and in the
    ``DecisionPointOpened`` events respectively.
    """
    mission_dir = repo_root / "kitty-specs" / mission_slug
    _setup_meta(mission_dir, mission_id=f"01KTEST_{mission_slug}", mission_slug=mission_slug)

    barrier = threading.Barrier(N_WORKERS)
    errors: list[BaseException] = []
    threads = [threading.Thread(target=_open_one, args=(repo_root, mission_slug, i, barrier, errors)) for i in range(N_WORKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not errors, f"worker thread(s) raised: {errors}"
    assert all(not t.is_alive() for t in threads), "worker thread(s) did not finish within the timeout"

    index = _store.load_index(mission_dir)
    index_keys = {e.input_key for e in index.entries}

    events_path = mission_dir / "status.events.jsonl"
    event_keys: set[str] = set()
    if events_path.exists():
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("event_type") == DECISION_POINT_OPENED:
                event_keys.add(event["payload"]["input_key"])

    return index_keys, event_keys


def test_concurrent_distinct_key_opens_preserve_all_entries(tmp_path_factory: pytest.TempPathFactory) -> None:
    """T011: N=8 distinct-key opens, barrier-released together, repeated
    across iterations -- the index and the event log must agree on the
    SET of 8 distinct keys every time (per-key 1:1, not a bare count)."""
    expected_keys = {f"key-{i}" for i in range(N_WORKERS)}

    for iteration in range(N_ITERATIONS):
        repo_root = tmp_path_factory.mktemp(f"decisions-concurrency-{iteration}")
        mission_slug = f"concurrency-mission-{iteration}"

        index_keys, event_keys = _run_one_iteration(repo_root, mission_slug)

        # The event log is written one line per `open_decision` call under
        # its own (already-serialized) status lock, so it is always
        # complete -- the index is what a missing/short lock would corrupt.
        assert event_keys == expected_keys, (
            f"iteration {iteration}: event log itself is incomplete ({sorted(event_keys)} != {sorted(expected_keys)}) -- broken test setup, not the lock under test"
        )
        assert index_keys == expected_keys, (
            f"iteration {iteration}: decisions/index.json lost entries under concurrent "
            f"distinct-key opens ({sorted(index_keys)} != {sorted(expected_keys)}); "
            "the service-level RMW lock (T010) did not serialize the load->mutate->save span"
        )
        assert index_keys == event_keys
