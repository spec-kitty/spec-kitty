"""Coord-fallback L1 take is bounded (NFR-001 amendment, PR #3922 landing fold).

Mission ``fsm-write-path-integrity-01M1TZV6`` (design-notes/WP01-lock-rules.md
Section 3 amendment).

``_emit_on_coord_then_commit`` (``coordination/status_transition.py``) holds
``feature_status_lock`` across ``_commit_status_artifacts_to_coord``'s
``safe_commit`` git subprocesses -- a genuine, deliberately-accepted
L1-across-git take (kept for rollback-safety: releasing L1 before the
commit/rollback would let a rollback erase a concurrent writer's successful
append). Before this fix the take used the lock's unbounded (``-1``)
default: a stalled sibling holding the lock (a blocked pre-commit hook, a
held ``.git/index.lock``, a credential prompt inside ``safe_commit``) would
wedge every status writer for the mission forever, with no timeout error and
no holder message.

This test proves the take is now bounded: an external holder plus a
monkeypatched (small, fast) timeout constant makes the coord-fallback path
raise a structured ``FeatureStatusLockTimeoutError`` -- naming the lock file
and the holder -- instead of hanging indefinitely.
"""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

import pytest

from specify_cli.coordination import status_transition as st
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.status.locking import (
    FeatureStatusLockTimeoutError,
    feature_status_lock,
    feature_status_lock_path,
)
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "coord-fallback-lock-bound"
MID8 = "01M1LKBD"
MISSION_ID = "01M1LKBD000000000000000000"
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=check, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    feature_dir = r / "kitty-specs" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "coordination_branch": COORD_BRANCH,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    _git(r, "add", "kitty-specs")
    _git(r, "commit", "-q", "-m", "seed mission")
    _git(r, "branch", COORD_BRANCH)
    return r


def _request(repo: Path) -> TransitionRequest:
    return TransitionRequest(
        feature_dir=repo / "kitty-specs" / MISSION_DIRNAME,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        to_lane="claimed",
        actor="coord-fallback-lock-bound-test",
        repo_root=repo,
    )


def _seed_planned_on_coord(repo: Path) -> None:
    """Seed WP01 out of 'genesis' into 'planned' directly on the coord branch."""
    seed_event = StatusEvent(
        event_id="01SEEDGENESIS0000000000002",
        mission_slug=MISSION_SLUG,
        mission_id=MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-05-31T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )
    worktree = repo / ".worktrees" / "seed-genesis"
    _git(repo, "worktree", "add", "-q", str(worktree), COORD_BRANCH)
    events_path = worktree / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(seed_event.to_dict()) + "\n")
    _git(worktree, "add", "kitty-specs")
    _git(worktree, "commit", "-q", "-m", "seed WP01 planned")
    # Committing inside the worktree already advances COORD_BRANCH (shared ref
    # store) -- no fetch back into `repo` needed. Just drop the worktree.
    _git(repo, "worktree", "remove", "-f", str(worktree))


def _force_fallback_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the ``_transaction_topology_available`` False arm (FR-004 row 7)."""
    monkeypatch.setattr(st, "_transaction_topology_available", lambda *_args, **_kwargs: False)


def test_coord_fallback_lock_take_is_bounded(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A contended lock times out with a structured error instead of hanging."""
    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)
    # Fast bound so the test does not actually wait the real production
    # duration: the call site imports the constant by name into its own
    # module namespace, so it must be patched there, not on `status.locking`.
    monkeypatch.setattr(st, "BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS", 0.2)

    lock_path = feature_status_lock_path(repo, MISSION_DIRNAME)
    ready = threading.Event()
    release = threading.Event()

    def _hold() -> None:
        with feature_status_lock(repo, MISSION_DIRNAME, timeout=5):
            ready.set()
            release.wait(timeout=10)

    holder = threading.Thread(target=_hold, name="coord-fallback-lock-holder")
    holder.start()
    try:
        assert ready.wait(timeout=5), "holder thread never acquired the lock"
        with pytest.raises(FeatureStatusLockTimeoutError) as excinfo:
            st.emit_status_transition_transactional(_request(repo))
    finally:
        release.set()
        holder.join(timeout=10)

    assert not holder.is_alive()
    message = str(excinfo.value)
    assert str(lock_path) in message
    assert "coord-fallback-lock-holder" in message or "held by pid" in message
    # Nothing landed on the coord worktree while the holder owned the lock.
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    events_path = coord_worktree / "kitty-specs" / MISSION_DIRNAME / "status.events.jsonl"
    if events_path.exists():
        assert "claimed" not in events_path.read_text(encoding="utf-8")


def test_coord_fallback_lock_take_still_succeeds_uncontended(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: the bound does not break the ordinary, uncontended write path.

    Stubs ``_commit_status_artifacts_to_coord`` the same way the sibling
    phantom-fan-out tests do (``test_phantom_fanout.py``) -- the real
    ``safe_commit``/placement-resolution path needs full mission topology
    plumbing this fixture does not set up, which is orthogonal to what this
    test is proving: that a *finite* timeout does not turn an ordinary,
    uncontended acquisition into a failure.
    """
    _seed_planned_on_coord(repo)
    _force_fallback_path(monkeypatch)
    monkeypatch.setattr(st, "BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr(st, "_commit_status_artifacts_to_coord", lambda **_kwargs: None)

    event = st.emit_status_transition_transactional(_request(repo))
    assert event.to_lane == Lane.CLAIMED
