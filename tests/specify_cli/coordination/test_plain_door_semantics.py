"""C-008 / SC-007: plain-door semantics for stored-``LANES`` missions.

Mission ``fsm-write-path-integrity-01M1TZV6`` (WP06, T033 -> T039).

Rationale: the pin exists because ``_fallback_emit_single._primary``
(``coordination/status_transition.py``, the ``_transaction_topology_available``
False arm for a coord-LESS topology) really does route a stored ``LANES`` /
``SINGLE_BRANCH`` / flat mission through the plain ``emit_status_transition``
door with the legitimate primary-UNCOMMITTED write semantics (C-001 row 8).
The four "plain-door callers" named in spec C-008 are docstring mentions, not
callers (``research.md`` §3 D-1) -- the fallback arm is the live caller.

The rejected shim-over-coordination mechanism (research §1 option 5) would
have made this door resolve identity through git subprocesses and commit the
write; converging the shells on the status-owned pipeline must not resurface
it. So: no new commits, no coordination worktree materialised, no mutating git
subprocess, and -- for the plain door itself -- no git subprocess beyond the
lock-path probe (``status/locking.py`` resolves the lock file under the git
common dir with ``rev-parse --git-common-dir``; that is lock placement, not
mission-identity resolution). Outbound fan-out is patched out: the zeitgeist
bridge's own origin lookup is the outbound side, not the write path.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from specify_cli.coordination import status_transition as st
from specify_cli.coordination.status_service import EventLogWriteContract, append_event_log
from specify_cli.status.emit import emit_status_transition
from specify_cli.status.models import Lane, StatusEvent, TransitionRequest

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "lanes-plain-door"
MISSION_ID = "01LANES00000000000000000001"
_MUTATING_GIT_VERBS = frozenset({"commit", "checkout", "merge", "rebase", "reset", "push", "tag"})
_LOCK_PATH_PROBE = ["rev-parse", "--git-common-dir"]
_FAN_OUT_BOUNDARIES = (
    "specify_cli.status.adapters.fire_saas_fanout",
    "specify_cli.status.fire_saas_fanout",
    "specify_cli.status.emit.fire_saas_fanout",
)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def lanes_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A one-commit git repo holding a stored-``LANES`` mission seeded to ``planned``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": MISSION_SLUG, "mission_id": MISSION_ID, "topology": "lanes", "target_branch": "main"}) + "\n",
        encoding="utf-8",
    )
    append_event_log(
        EventLogWriteContract.primary_checkout_append(feature_dir),
        StatusEvent(
            event_id="01SEEDLANES000000000000001",
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
        ),
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed lanes mission")
    return repo, feature_dir


@pytest.fixture
def git_argv(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[list[str]]]:
    """Record every ``git`` argv spawned through ``subprocess.Popen`` (run/check_output included)."""
    recorded: list[list[str]] = []
    real_popen = subprocess.Popen

    class _RecordingPopen(real_popen):  # type: ignore[misc,valid-type]
        def __init__(self, args: Any, *popen_args: Any, **popen_kwargs: Any) -> None:
            argv = [str(part) for part in args] if isinstance(args, (list, tuple)) else [str(args)]
            if argv and Path(argv[0]).name == "git":
                recorded.append(argv)
            super().__init__(args, *popen_args, **popen_kwargs)

    monkeypatch.setattr(subprocess, "Popen", _RecordingPopen)
    yield recorded


def _claim(feature_dir: Path, repo: Path) -> TransitionRequest:
    return TransitionRequest(
        feature_dir=feature_dir,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        to_lane="claimed",
        actor="plain-door-test",
        repo_root=repo,
    )


def _mutating(argv: list[str]) -> bool:
    """True for a git invocation that could commit, create a worktree/branch, or move HEAD."""
    verbs = [part for part in argv[1:] if not part.startswith("-")]
    if not verbs:
        return False
    verb = verbs[0] if verbs[0] != "-C" else verbs[2]
    if verb == "worktree":
        return "add" in verbs
    if verb == "branch":
        return "--show-current" not in argv and "--list" not in argv
    return verb in _MUTATING_GIT_VERBS


def test_plain_door_lanes_mission_gains_no_commits(lanes_repo: tuple[Path, Path], git_argv: list[list[str]], monkeypatch: pytest.MonkeyPatch) -> None:
    """The transactional door's ``_primary`` fallback arm keeps the uncommitted write.

    A stored-``LANES`` mission with a bare-slug directory has no transaction
    metadata dir, so ``_transaction_topology_available`` is False and the
    single door takes ``_fallback_emit_single._primary`` -> the plain door.
    """
    repo, feature_dir = lanes_repo
    head_before = _git(repo, "rev-list", "--count", "HEAD")
    resolved: list[Path | None] = []
    real_resolve = st._resolve_fallback_coord_worktree

    def _recording_resolve(*args: Any, **kwargs: Any) -> Path | None:
        result = real_resolve(*args, **kwargs)
        resolved.append(result)
        return result

    monkeypatch.setattr(st, "_resolve_fallback_coord_worktree", _recording_resolve)

    event = st.emit_status_transition_transactional(_claim(feature_dir, repo))

    assert event.to_lane == Lane.CLAIMED
    assert resolved == [None], "a coord-less topology must take the primary arm"
    assert _git(repo, "rev-list", "--count", "HEAD") == head_before, "the plain door never commits"
    assert "kitty-specs/lanes-plain-door/status.events.jsonl" in _git(repo, "status", "--short")
    assert not (repo / ".worktrees").exists(), "no coordination worktree is materialised"
    assert not [argv for argv in git_argv if _mutating(argv)], git_argv


def test_plain_door_itself_resolves_no_identity_through_git(lanes_repo: tuple[Path, Path], git_argv: list[list[str]], monkeypatch: pytest.MonkeyPatch) -> None:
    """The flat shell's write path spawns git only for the lock-path probe.

    Lock, derive, pipeline, append, mirror: none resolve a mission identity
    (no ``worktree list``, no ``symbolic-ref``, no branch probe, no
    ``CoordinationWorkspace.resolve``). Identity resolution through git on this
    door is the rejected shim mechanism (C-008).
    """
    repo, feature_dir = lanes_repo
    for boundary in _FAN_OUT_BOUNDARIES:
        monkeypatch.setattr(boundary, lambda **_kwargs: None)
    head_before = _git(repo, "rev-list", "--count", "HEAD")
    del git_argv[:]  # drop the fixture's own rev-list call

    event = emit_status_transition(_claim(feature_dir, repo))

    assert event.to_lane == Lane.CLAIMED
    assert [argv[-2:] for argv in git_argv] == [_LOCK_PATH_PROBE], git_argv
    assert _git(repo, "rev-list", "--count", "HEAD") == head_before
