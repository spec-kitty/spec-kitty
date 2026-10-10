"""Locking + atomicity pins for ``decisions/emit.py`` (WP07 T040).

Family 8 of the writer census (mission ``fsm-write-path-integrity-01M1TZV6``,
``design-notes/WP01-lock-rules.md`` section 1 addendum): ``_append_raw_event``
lands ``DecisionPointOpened`` / ``DecisionPointResolved`` rows in
``kitty-specs/<mission>/status.events.jsonl``. WP03's AST writes gate found it
as a raw, unlocked ``open("a")`` append the WP01 census had not enumerated.
After WP07 the row lands through ``append_raw_rows_atomic`` while the mission
status lock keyed on ``feature_dir.name`` is held.

Part 1 is the rollback-truncate race in WP01's shape (SC-001, permanent
functional pin per C-009 -- the red-first repro for this site): a
``BookkeepingTransaction`` whose commit is forced to fail rolls back by
truncating the log to its pre-emit size; an unlocked decision append landing
inside that window is truncated away with the transaction's own event.
"""

from __future__ import annotations

import ast
import json
import subprocess
import threading
from pathlib import Path
from typing import Any

import pytest

import specify_cli.coordination.transaction as transaction_module
import specify_cli.decisions.emit as decisions_emit
import specify_cli.status.store as status_store
from kernel.clock import UTC, datetime
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED, DECISION_POINT_RESOLVED
from specify_cli.coordination.transaction import BookkeepingCommitFailed, BookkeepingTransaction
from specify_cli.decisions.emit import emit_decision_opened, emit_decision_resolved
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.status.emit import build_status_event
from specify_cli.status.locking import _get_thread_locks, feature_status_lock_path
from specify_cli.status.models import StatusEvent
from specify_cli.workspace.root_resolver import resolve_status_lock_root

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MID8 = "01J7DECS"
MISSION_ID = "01J7DECS00000000000000000P"
# The slug embeds the mid8 so the transaction's specs dir name equals the slug
# (``_mission_specs_dir_name`` is idempotent on an embedded suffix); the lock
# key convention has its own pin in ``tests/status/test_locking_key.py``.
MISSION_SLUG = f"decision-emit-locking-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
DECISION_ID = "01AAAAAAAAAAAAAAAAAAAAAAAA"
ACTOR = "test-actor"


#: Where the stub placement seam sends ``STATUS_STATE`` for the current test:
#: ``None`` means ``repo_root/kitty-specs/<slug>`` (as in ``test_emit.py``); the
#: race test points it at the transaction's coord-partition mission dir, which
#: is where the real seam resolves the status log for a coordination topology.
_SEAM_TARGET: dict[str, Path | None] = {"dir": None}


class _FakeWriteLocation:
    """Minimal ``WriteLocation`` double exposing only the ``.path`` attribute
    ``_mission_dir`` consumes."""

    def __init__(self, path: Path) -> None:
        self.path = path


class _StubMissionDirSeam:
    def __init__(self, repo_root: Path, mission_slug: str, *, owned: object = None) -> None:
        self._repo_root = repo_root
        self._mission_slug = mission_slug

    def read_dir(self, kind: object) -> Path:
        return _SEAM_TARGET["dir"] or self._repo_root / "kitty-specs" / self._mission_slug

    def write_dir(self, kind: object) -> _FakeWriteLocation:
        # coord-artifact-single-home-01M3V4BE WP09 (T049): the write-side
        # writer now resolves through ``write_dir`` instead of ``read_dir`` --
        # same stubbed target either way.
        return _FakeWriteLocation(_SEAM_TARGET["dir"] or self._repo_root / "kitty-specs" / self._mission_slug)


@pytest.fixture(autouse=True)
def _stub_mission_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(decisions_emit, "placement_seam", _StubMissionDirSeam)
    monkeypatch.setitem(_SEAM_TARGET, "dir", None)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Tmp repo with a coordination-topology mission seeded (WP01's fixture shape)."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    feature_dir = r / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    meta = {
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    _git(r, "add", "kitty-specs")
    _git(r, "commit", "-q", "-m", "seed mission")
    _git(r, "branch", COORD_BRANCH)
    return r


@pytest.fixture
def bare_feature_dir(tmp_path: Path) -> Path:
    """A non-git mission tree: the lock degrades to ``.kittify/spec-kitty-locks``."""
    fd = tmp_path / "kitty-specs" / MISSION_SLUG
    fd.mkdir(parents=True)
    return fd


def _make_entry(status: DecisionStatus = DecisionStatus.OPEN) -> IndexEntry:
    resolved = status is not DecisionStatus.OPEN
    return IndexEntry(
        decision_id=DECISION_ID,
        origin_flow=OriginFlow.CHARTER,
        step_id="charter.q1",
        slot_key=None,
        input_key="auth_strategy",
        question="Which auth strategy?",
        options=("session", "oauth2"),
        status=status,
        final_answer="oauth2" if status is DecisionStatus.RESOLVED else None,
        rationale="pin" if resolved else None,
        other_answer=False,
        created_at=datetime(2026, 4, 23, 10, 0, 0, tzinfo=UTC),
        resolved_at=datetime(2026, 4, 23, 11, 0, 0, tzinfo=UTC) if resolved else None,
        resolved_by=ACTOR if resolved else None,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
    )


def _make_event(wp_id: str) -> StatusEvent:
    return build_status_event(
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id=wp_id,
        from_lane="planned",
        to_lane="claimed",
        actor="implementer-ivan",
    )


def _acquire(repo: Path) -> Any:
    return BookkeepingTransaction.acquire(
        repo_root=repo,
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MID8,
        destination_ref=COORD_BRANCH,
        operation="decision-emit-locking",
    )


def _rows(events_path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _emit_opened(repo_root: Path) -> int:
    return emit_decision_opened(repo_root, MISSION_SLUG, decision_id=DECISION_ID, entry=_make_entry(), actor=ACTOR)


def _emit_resolved(repo_root: Path) -> int:
    entry = _make_entry(DecisionStatus.RESOLVED)
    return emit_decision_resolved(repo_root, MISSION_SLUG, decision_id=DECISION_ID, entry=entry, actor=ACTOR)


# ---------------------------------------------------------------------------
# Part 1 -- the rollback-truncate race (red-first repro, kept as the SC-001 pin)
# ---------------------------------------------------------------------------


def test_decision_append_waits_for_rollback_and_lands_after_truncate(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A DecisionPointOpened append never lands inside the rollback window.

    Ordering: the decision append runs in a second thread and blocks on the
    mission status lock the transaction holds; the forced commit failure rolls
    the transaction back (truncate) and releases the lock; only then does the
    append land -- after the truncate. Before WP07 the append was unlocked,
    landed inside the window immediately, and was truncated away.
    """
    with _acquire(repo) as txn:
        seed = _make_event("WP01")
        txn.append_event(seed)
        txn.commit("status: seed")
    events_path = txn.feature_dir / "status.events.jsonl"
    # The seam stub and the transaction must agree on ONE log file: the
    # coord-partition mission dir the transaction materialized.
    _SEAM_TARGET["dir"] = txn.feature_dir
    assert [row["event_id"] for row in _rows(events_path)] == [seed.event_id]

    def _forced_commit_failure(**_kwargs: Any) -> None:
        raise RuntimeError("forced commit failure (test)")

    monkeypatch.setattr(transaction_module, "safe_commit", _forced_commit_failure)
    thread_errors: list[BaseException] = []

    def _racing_open() -> None:
        try:
            _emit_opened(repo)
        except BaseException as exc:
            thread_errors.append(exc)

    with pytest.raises(BookkeepingCommitFailed), _acquire(repo) as txn:
        doomed = _make_event("WP02")
        txn.append_event(doomed)  # captures _pre_emit_size
        racer = threading.Thread(target=_racing_open)
        racer.start()
        # Unlocked: the append lands now. Locked: the racer blocks here on the
        # lock until the transaction releases it.
        racer.join(timeout=2.0)
        txn.commit("status: should fail")  # -> _rollback() -> truncate

    racer.join(timeout=15.0)
    assert not racer.is_alive(), "racing decision append never completed"
    assert not thread_errors, thread_errors

    rows = _rows(events_path)
    ids = [row["event_id"] for row in rows]
    assert doomed.event_id not in ids, "positive control: rollback removed the txn event"
    assert seed.event_id in ids
    opened = [row for row in rows if row.get("event_type") == DECISION_POINT_OPENED]
    assert opened, "SC-001: the DecisionPointOpened row was truncated away by the rollback"
    assert opened[0]["payload"]["decision_point_id"] == DECISION_ID


# ---------------------------------------------------------------------------
# Part 2 -- lock-held, atomic, git-free (SC-008, FR-002, NFR-001)
# ---------------------------------------------------------------------------


class _HeldLocksAtWrite:
    """Snapshot this thread's held locks at the store's durable-write choke point."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.snapshots: list[set[str]] = []
        original = status_store._fsync_directory

        def _record(directory: Path) -> None:
            self.snapshots.append(set(_get_thread_locks()))
            original(directory)

        monkeypatch.setattr(status_store, "_fsync_directory", _record)


@pytest.mark.parametrize(
    ("emit", "event_type"),
    [
        pytest.param(_emit_opened, DECISION_POINT_OPENED, id="opened"),
        pytest.param(_emit_resolved, DECISION_POINT_RESOLVED, id="resolved"),
    ],
)
def test_append_runs_while_mission_lock_is_held(
    bare_feature_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    emit: Any,
    event_type: str,
) -> None:
    recorder = _HeldLocksAtWrite(monkeypatch)
    repo_root = bare_feature_dir.parent.parent
    lamport = emit(repo_root)

    expected = feature_status_lock_path(resolve_status_lock_root(bare_feature_dir), bare_feature_dir.name)
    assert recorder.snapshots, "the atomic primitive never wrote"
    assert all(str(expected) in held for held in recorder.snapshots)
    rows = _rows(bare_feature_dir / "status.events.jsonl")
    assert [row["event_type"] for row in rows] == [event_type]
    assert lamport == 1
    # Lock released once the append is durable.
    assert str(expected) not in _get_thread_locks()
    # The lock never minted a fake repo root in the bare tree (WP01 section 6).
    assert not (repo_root / ".git").exists()


def test_lamport_proxy_counts_rows_as_of_this_append(bare_feature_dir: Path) -> None:
    """The readback runs under the same acquisition: the count is the row's line number."""
    repo_root = bare_feature_dir.parent.parent
    assert _emit_opened(repo_root) == 1
    assert _emit_resolved(repo_root) == 2
    assert len(_rows(bare_feature_dir / "status.events.jsonl")) == 2


def test_no_git_subprocess_while_holding_the_mission_lock(bare_feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001 / C-002: the critical section never spawns a subprocess."""
    held_at_spawn: list[set[str]] = []
    original_run = subprocess.run
    original_popen = subprocess.Popen

    def _record_run(*args: Any, **kwargs: Any) -> Any:
        held_at_spawn.append(set(_get_thread_locks()))
        return original_run(*args, **kwargs)

    def _record_popen(*args: Any, **kwargs: Any) -> Any:
        held_at_spawn.append(set(_get_thread_locks()))
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", _record_run)
    monkeypatch.setattr(subprocess, "Popen", _record_popen)
    _emit_opened(bare_feature_dir.parent.parent)
    expected = feature_status_lock_path(resolve_status_lock_root(bare_feature_dir), bare_feature_dir.name)
    assert not [held for held in held_at_spawn if str(expected) in held], "a subprocess was spawned while L1 was held"


def test_module_has_no_raw_append_open() -> None:
    """The raw ``open("a")`` is gone; the atomic primitive and the lock are named."""
    source = Path(decisions_emit.__file__).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != "open":
            continue
        modes = [arg.value for arg in node.args[1:2] if isinstance(arg, ast.Constant)]
        modes += [kw.value.value for kw in node.keywords if kw.arg == "mode" and isinstance(kw.value, ast.Constant)]
        assert not any("a" in str(mode) or "w" in str(mode) for mode in modes), f"raw write-mode open at line {node.lineno}"
    assert "append_raw_rows_atomic" in source
    assert "feature_status_lock(" in source
