"""The decisions lock is keyed on the event log, not the ledger directory (#6765).

The defect: ``open_decision`` holds the ledger-directory sidecar lock
(``kitty-specs/<mission>/decisions/index.json.lock``) across the dedup lookup and the
``DecisionPointOpened`` append, but the row it writes goes to the Mission *event log*
(``status.events.jsonl``), which resolves independently and, on a coordination topology,
on a different partition. Two checkouts that append to one log therefore take two
different lock files and do not serialize; two opens of one explicit ``decision_id`` can
interleave.

No supported topology splits the two legs today (issue #6765: "no caller does this
today"), so the split is injected at the two path-resolution helpers the service uses —
never inside ``placement_seam`` — which keeps the production entry point
(``open_decision``) and the real lock/emit machinery exercised.

Every test here pairs its assertion with a same-fixture control:

* the overlap probe is proven able to *see* an overlap (independent writers overlap), so
  "no overlap" cannot pass because the probe is blind;
* the "writers share a lock" probe is paired with the distinct-log case, on the same
  fixture, where the lock sets must stay disjoint (no global lock).
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

# Warm the lazily-imported status seam that ``decisions.emit`` imports on its first
# append. Resolving it here (module import, main thread) keeps the threaded tests about
# lock exclusion instead of about CPython's cross-thread import machinery.
import specify_cli.status  # noqa: F401
from kernel.event_log_append import event_log_lock_path
from kernel.locks import machine_file_lock as _real_machine_file_lock
from specify_cli.decisions import emit as _emit
from specify_cli.decisions import service as _service
from specify_cli.decisions.models import OriginFlow
from specify_cli.decisions.service import open_decision

pytestmark = [pytest.mark.unit]

MISSION_ID = "01KTEST_LOG_ANCHOR_000001"
MISSION_SLUG = "log-anchor-mission"
DECISION_ID = "01KTEST_LOG_ANCHOR_DECISION"
_WAIT_S = 20.0
#: How long a writer stays inside its critical section; wide enough that two unguarded
#: writers overlap deterministically, short enough to keep the module fast.
_HOLD_S = 0.25


def _mission_dir(root: Path) -> Path:
    return root / "kitty-specs" / MISSION_SLUG


def _checkout(tmp_path: Path, name: str) -> Path:
    """A checkout-shaped root carrying the Mission's meta.json (its ledger home)."""
    root = tmp_path / name
    mission_dir = _mission_dir(root)
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
        encoding="utf-8",
    )
    return root


def _shared_log(tmp_path: Path) -> Path:
    """The one event log two checkouts append to."""
    log_dir = tmp_path / "shared" / "kitty-specs" / MISSION_SLUG
    log_dir.mkdir(parents=True)
    return log_dir / "status.events.jsonl"


@contextmanager
def _resolved_as(monkeypatch: pytest.MonkeyPatch, ledger: dict[Path, Path], log: Path) -> Iterator[None]:
    """Pin the two legs: a ledger dir per checkout root, one event log for all of them."""
    with monkeypatch.context() as m:
        m.setattr(_service, "_ledger_dir", lambda repo_root, slug, owned=None, _l=ledger: _l[Path(repo_root)])
        m.setattr(_service, "_write_events_path", lambda repo_root, slug, owned=None, _p=log: _p)
        yield


def _record_lock_paths(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record every lock file the service actually acquires, then acquire it for real."""
    taken: list[Path] = []

    def _recording(lock_path: Path, *args: Any, **kwargs: Any) -> Any:
        taken.append(Path(lock_path))
        return _real_machine_file_lock(lock_path, *args, **kwargs)

    monkeypatch.setattr(_service, "machine_file_lock", _recording)
    return taken


def _record_intervals(monkeypatch: pytest.MonkeyPatch) -> list[tuple[float, float]]:
    """Record the interval each open spends inside its critical section.

    The real ``emit_decision_opened`` is still called (so the production append path runs
    under the real Mission status lock); the hold is widened so two unguarded writers
    overlap deterministically.
    """
    original_emit = _emit.emit_decision_opened
    intervals: list[tuple[float, float]] = []

    def _recording_emit(*args: Any, **kwargs: Any) -> int:
        start = time.monotonic()
        try:
            time.sleep(_HOLD_S)
            lamport = original_emit(*args, **kwargs)
            return int(lamport)
        finally:
            intervals.append((start, time.monotonic()))

    monkeypatch.setattr(_service._emit, "emit_decision_opened", _recording_emit)
    return intervals


def _overlaps(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return first[0] < second[1] and second[0] < first[1]


def _run_two_opens(roots: list[Path]) -> list[tuple[str, Any]]:
    """Open the same explicit decision_id from every root, all starting together."""
    barrier = threading.Barrier(len(roots), timeout=_WAIT_S)
    results: list[tuple[str, Any]] = []
    guard = threading.Lock()

    def _worker(root: Path) -> None:
        barrier.wait()
        try:
            response = open_decision(
                root,
                MISSION_SLUG,
                origin_flow=OriginFlow.CHARTER,
                step_id="step-team-size",
                input_key="team_size",
                question="How large is the team?",
                options=("1-5", "6-20"),
                actor="alice",
                decision_id=DECISION_ID,
            )
        except BaseException as exc:  # reported, never swallowed silently
            with guard:
                results.append((str(root), exc))
            return
        with guard:
            results.append((str(root), response))

    threads = [threading.Thread(target=_worker, args=(root,), daemon=True) for root in roots]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=_WAIT_S)
        assert not thread.is_alive(), "an open did not finish within the bounded wait"
    return results


def _assert_no_failures(results: list[tuple[str, Any]]) -> None:
    for root, outcome in results:
        assert not isinstance(outcome, BaseException), f"open from {root} failed: {outcome!r}"


# ---------------------------------------------------------------------------
# FR-001 / SC-002: one log means one lock, whatever ledger dir the writer sits in
# ---------------------------------------------------------------------------


def test_two_checkouts_writing_one_log_share_a_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared anchor decides the lock, not the per-checkout ledger directory."""
    first = _checkout(tmp_path, "repo-root")
    second = _checkout(tmp_path, "owned")
    log = _shared_log(tmp_path)
    ledger = {first: _mission_dir(first), second: _mission_dir(second)}
    assert ledger[first] != ledger[second], "fixture premise: the ledger dirs must differ"

    with _resolved_as(monkeypatch, ledger, log):
        taken = _record_lock_paths(monkeypatch)
        _assert_no_failures(_run_two_opens([first, second]))

    shared = set(taken)
    per_checkout = {lock for lock in shared if _is_under(lock, ledger[first]) or _is_under(lock, ledger[second])}
    assert len(shared) > len(per_checkout), (
        f"two writers of one event log must take at least one common lock that is not a per-checkout ledger lock; took {sorted(map(str, shared))}"
    )


def test_two_checkouts_writing_distinct_logs_share_no_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control for the test above: distinct logs must stay independent (no global lock)."""
    first = _checkout(tmp_path, "repo-root")
    second = _checkout(tmp_path, "owned")
    first_log = _mission_dir(first) / "status.events.jsonl"
    second_log = _mission_dir(second) / "status.events.jsonl"

    with monkeypatch.context() as m:
        logs = {first: first_log, second: second_log}
        m.setattr(
            _service,
            "_ledger_dir",
            lambda repo_root, slug, owned=None, _l={first: _mission_dir(first), second: _mission_dir(second)}: _l[Path(repo_root)],
        )
        m.setattr(_service, "_write_events_path", lambda repo_root, slug, owned=None, _p=logs: _p[Path(repo_root)])
        taken = _record_lock_paths(m)
        _assert_no_failures(_run_two_opens([first, second]))

    assert len(set(taken)) == len(taken), f"distinct logs must not share a lock; took {sorted(map(str, taken))}"


# ---------------------------------------------------------------------------
# FR-002 / FR-004 / C-004: the acquisition order, and exactly one added lock
# ---------------------------------------------------------------------------


def test_a_forward_write_takes_the_anchor_then_the_sidecar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One global lock order: the log anchor first, the ledger sidecar second.

    A single order is what keeps the pair deadlock-free (C-004), and the sidecar
    must still be held (FR-004 / US3-1) -- so the exact acquisition sequence is
    pinned, not just which files were touched. It also states NFR-002: a write
    takes exactly ONE lock beyond the sidecar it always took.
    """
    root = _checkout(tmp_path, "repo-root")
    log = _shared_log(tmp_path)

    with _resolved_as(monkeypatch, {root: _mission_dir(root)}, log):
        taken = _record_lock_paths(monkeypatch)
        response = open_decision(
            root,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-team-size",
            input_key="team_size",
            question="How large is the team?",
            options=("1-5", "6-20"),
            actor="alice",
            decision_id=DECISION_ID,
        )

    assert response.decision_id == DECISION_ID
    assert taken == [event_log_lock_path(log), _mission_dir(root) / "decisions" / "index.json.lock"], (
        f"expected anchor then sidecar and nothing else; took {sorted(map(str, taken))}"
    )


# ---------------------------------------------------------------------------
# FR-002 / SC-001: the open critical section does not overlap across checkouts
# ---------------------------------------------------------------------------


def test_two_checkouts_writing_one_log_do_not_interleave_an_open(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = _checkout(tmp_path, "repo-root")
    second = _checkout(tmp_path, "owned")
    log = _shared_log(tmp_path)
    ledger = {first: _mission_dir(first), second: _mission_dir(second)}

    with _resolved_as(monkeypatch, ledger, log):
        intervals = _record_intervals(monkeypatch)
        _assert_no_failures(_run_two_opens([first, second]))

    assert len(intervals) == 2, f"expected two critical sections, saw {len(intervals)}"
    assert not _overlaps(*intervals), f"the two opens interleaved: {intervals}"


def test_the_overlap_probe_sees_independent_writers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: the probe above must be able to observe an overlap at all."""
    first = _checkout(tmp_path, "repo-root")
    second = _checkout(tmp_path, "owned")

    with monkeypatch.context() as m:
        logs = {first: _mission_dir(first) / "status.events.jsonl", second: _mission_dir(second) / "status.events.jsonl"}
        ledger = {first: _mission_dir(first), second: _mission_dir(second)}
        m.setattr(_service, "_ledger_dir", lambda repo_root, slug, owned=None, _l=ledger: _l[Path(repo_root)])
        m.setattr(_service, "_write_events_path", lambda repo_root, slug, owned=None, _p=logs: _p[Path(repo_root)])
        intervals = _record_intervals(m)
        _assert_no_failures(_run_two_opens([first, second]))

    assert len(intervals) == 2, f"expected two critical sections, saw {len(intervals)}"
    assert _overlaps(*intervals), f"the probe cannot see an overlap, so the no-overlap test is vacuous: {intervals}"


# ---------------------------------------------------------------------------
# NFR-004 / SC-003: the anchor lock leaves no working-tree residue
# ---------------------------------------------------------------------------


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


@pytest.mark.integration
@pytest.mark.git_repo
def test_the_anchor_lock_lives_outside_the_working_tree(tmp_path: Path) -> None:
    """A decision write takes the anchor lock under the git common dir, nothing in the tree.

    A main checkout's ``.git`` is a directory *inside* the repository root, so
    "outside the checkout directory" is the wrong test of NFR-004. The invariant
    is that the anchor lock lives under the git COMMON dir -- the directory every
    worktree of the repository shares and git never tracks -- so it cannot reach
    a commit and needs no ``.gitignore`` rule. The ledger sidecar stays the only
    lock the working tree provisions for, exactly as before this change.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "user.email", "test@example.invalid")
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    mission_dir = _mission_dir(root)
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG, "topology": "single_branch"}),
        encoding="utf-8",
    )

    taken: list[Path] = []
    original = _service.machine_file_lock

    def _recording(lock_path: Path, *args: Any, **kwargs: Any) -> Any:
        taken.append(Path(lock_path))
        return original(lock_path, *args, **kwargs)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(_service, "machine_file_lock", _recording)
        open_decision(
            root,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-team-size",
            input_key="team_size",
            question="How large is the team?",
            options=("1-5", "6-20"),
            actor="alice",
        )

    common_dir = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    anchor_locks = [lock for lock in taken if lock == event_log_lock_path(mission_dir / "status.events.jsonl")]
    assert anchor_locks, f"the event-log anchor lock was never taken; took {sorted(map(str, taken))}"
    for lock in anchor_locks:
        assert _is_under(lock, common_dir / "spec-kitty-locks" / "event-logs"), (
            f"the anchor lock must live under the git common dir, outside every working tree: {lock}"
        )

    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    tracked_lock_paths = [line[3:] for line in status if line[3:].endswith(".lock")]
    sidecar = str((mission_dir / "decisions" / "index.json.lock").relative_to(root))
    assert set(tracked_lock_paths) <= {sidecar}, f"a lock other than the ledger sidecar appeared in the working tree: {tracked_lock_paths}"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


# ---------------------------------------------------------------------------
# The reused anchor contract: non-git fallback
# ---------------------------------------------------------------------------


def test_a_non_git_anchor_falls_back_to_a_sibling_lock(tmp_path: Path) -> None:
    """Computing the anchor lock path never creates a lock and never leaves the anchor's dir."""
    (tmp_path / "not-a-repo").mkdir()
    log = tmp_path / "not-a-repo" / "status.events.jsonl"
    lock = event_log_lock_path(log)
    assert lock == log.with_name(log.name + ".event-log.lock")
    assert not lock.exists(), "computing the lock path must not create the lock file"
    assert not log.exists()
