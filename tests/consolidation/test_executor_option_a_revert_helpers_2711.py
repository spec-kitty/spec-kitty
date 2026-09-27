"""Focused unit coverage for the #2711 Option-A coord-revert helpers (executor.py).

The coord-topology full-merge regression tests
(``test_issue_2711_merge_rollback_resume_coherence`` — success revert;
``test_issue_2786_revert_failure_split_brain`` — swallowed revert failure) drive
these helpers end-to-end, but only along the coord-present happy/failure paths.
This module pins the fast no-op / early-return branches that a coord-topology
merge never reaches: unresolvable placement, no captured ref, no coordination
worktree, and the ``HEAD == captured`` nothing-committed guard — plus the
success/abort subprocess branches of ``_revert_coord_done_commit`` in isolation.

The ``run`` argument is a light ``SimpleNamespace`` stand-in: each helper reads
only a handful of ``_MergeRunState`` attributes, so a full state object (and a
real merge) is unnecessary to exercise the branch logic (test-scaffolding-as-
design-smell — the pure seams take their inputs off a plain object). mypy checks
this test with ``follow_imports = skip`` for ``specify_cli.*`` (pyproject test
override), so the helpers collapse to ``Any`` and accept the stand-in.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

import specify_cli.status  # noqa: F401  # import-order guard (see #2711 harness)

from specify_cli.consolidation import executor
from specify_cli.consolidation.executor import (
    _capture_pre_target_coord_ref_sha,
    _coord_worktree_root,
    _revert_coord_done_commit,
)

pytestmark = pytest.mark.fast

_CAPTURED_SHA = "f76bd91297db0000000000000000000000000000"
_HEAD_SHA = "aaaa1111bbbb2222cccc3333dddd4444eeee5555"

_RunFn = Callable[..., "subprocess.CompletedProcess[str]"]


def _completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        ["git"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _recording_run(calls: list[list[str]]) -> _RunFn:
    """A ``subprocess.run`` double that records commands and always succeeds."""

    def _run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return _completed(0)

    return _run


def _staged_run(calls: list[list[str]], head_sha: str, revert_rc: int) -> _RunFn:
    """A ``subprocess.run`` double: ``rev-parse`` -> *head_sha*, ``revert`` -> *revert_rc*."""

    def _run(cmd: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        if "rev-parse" in cmd:
            return _completed(0, stdout=head_sha + "\n")
        if "revert" in cmd and "--abort" not in cmd:
            return _completed(revert_rc, stderr="conflict" if revert_rc else "")
        return _completed(0)  # the --abort follow-up

    return _run


# ---------------------------------------------------------------------------
# _coord_worktree_root (lines 448-455)
# ---------------------------------------------------------------------------


def test_coord_worktree_root_none_when_no_events_path() -> None:
    run = SimpleNamespace(canonical_events_path=None)
    assert _coord_worktree_root(run) is None


def test_coord_worktree_root_none_when_not_under_worktrees(tmp_path: Path) -> None:
    events = tmp_path / "kitty-specs" / "slug-01ab" / "status.events.jsonl"
    run = SimpleNamespace(canonical_events_path=events)
    assert _coord_worktree_root(run) is None


def test_coord_worktree_root_strips_to_worktree_root(tmp_path: Path) -> None:
    worktree = tmp_path / ".worktrees" / "slug-01ab"
    events = worktree / "kitty-specs" / "slug-01ab" / "status.events.jsonl"
    run = SimpleNamespace(canonical_events_path=events)
    assert _coord_worktree_root(run) == worktree


# ---------------------------------------------------------------------------
# _revert_coord_done_commit (lines 476-514)
# ---------------------------------------------------------------------------


def test_revert_noop_without_captured_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    """No coordination ref/sha captured (non-coord topology) — proven no-op."""
    calls: list[list[str]] = []
    monkeypatch.setattr(executor.subprocess, "run", _recording_run(calls))
    run = SimpleNamespace(pre_target_coord_ref=None, pre_target_coord_sha=None)
    _revert_coord_done_commit(run)
    assert calls == []  # never touched git


def test_revert_noop_without_coord_worktree(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ref/sha captured but no coordination worktree resolves — no-op."""
    calls: list[list[str]] = []
    monkeypatch.setattr(executor.subprocess, "run", _recording_run(calls))
    run = SimpleNamespace(
        pre_target_coord_ref="kitty/mission-x",
        pre_target_coord_sha=_CAPTURED_SHA,
        canonical_events_path=None,  # -> _coord_worktree_root None
    )
    _revert_coord_done_commit(run)
    assert calls == []


def test_revert_noop_when_head_at_captured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HEAD unchanged since capture — nothing to revert, no revert issued."""
    worktree = tmp_path / ".worktrees" / "slug-01ab"
    events = worktree / "kitty-specs" / "slug-01ab" / "status.events.jsonl"
    calls: list[list[str]] = []
    monkeypatch.setattr(
        executor.subprocess, "run", _staged_run(calls, head_sha=_CAPTURED_SHA, revert_rc=0)
    )
    run = SimpleNamespace(
        pre_target_coord_ref="kitty/mission-x",
        pre_target_coord_sha=_CAPTURED_SHA,
        canonical_events_path=events,
    )
    _revert_coord_done_commit(run)
    assert all("revert" not in cmd for cmd in calls)  # only rev-parse ran


def test_revert_success_issues_forward_revert(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HEAD advanced past capture and the revert succeeds — forward revert issued,
    no abort, no warning."""
    worktree = tmp_path / ".worktrees" / "slug-01ab"
    events = worktree / "kitty-specs" / "slug-01ab" / "status.events.jsonl"
    calls: list[list[str]] = []
    monkeypatch.setattr(
        executor.subprocess, "run", _staged_run(calls, head_sha=_HEAD_SHA, revert_rc=0)
    )
    run = SimpleNamespace(
        pre_target_coord_ref="kitty/mission-x",
        pre_target_coord_sha=_CAPTURED_SHA,
        canonical_events_path=events,
    )
    _revert_coord_done_commit(run)
    reverts = [cmd for cmd in calls if "revert" in cmd]
    assert reverts and all("--abort" not in cmd for cmd in reverts)  # forward revert, no abort


def test_revert_failure_aborts_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing forward revert triggers ``git revert --abort`` + a warning (#2786
    proves this same swallowed path re-opens the split-brain end-to-end)."""
    worktree = tmp_path / ".worktrees" / "slug-01ab"
    events = worktree / "kitty-specs" / "slug-01ab" / "status.events.jsonl"
    calls: list[list[str]] = []
    monkeypatch.setattr(
        executor.subprocess, "run", _staged_run(calls, head_sha=_HEAD_SHA, revert_rc=1)
    )
    run = SimpleNamespace(
        pre_target_coord_ref="kitty/mission-x",
        pre_target_coord_sha=_CAPTURED_SHA,
        canonical_events_path=events,
    )
    with caplog.at_level("WARNING"):
        _revert_coord_done_commit(run)
    assert any("--abort" in cmd for cmd in calls)  # abort issued
    assert any("could not revert" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# _capture_pre_target_coord_ref_sha (lines 423-437)
# ---------------------------------------------------------------------------


def test_capture_skips_on_unresolvable_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    """A placement that cannot resolve (non-coord / legacy) leaves both fields None."""

    def _raise(*_a: object, **_k: object) -> object:
        raise RuntimeError("no placement")

    monkeypatch.setattr(executor, "resolve_placement_only", _raise)
    run = SimpleNamespace(
        main_repo=Path("/repo"),
        mission_slug="slug-01ab",
        pre_target_coord_ref=None,
        pre_target_coord_sha=None,
    )
    _capture_pre_target_coord_ref_sha(run)
    assert run.pre_target_coord_ref is None
    assert run.pre_target_coord_sha is None


def test_capture_records_ref_and_sha(monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolvable coord ref whose tip resolves records both fields."""
    monkeypatch.setattr(
        executor,
        "resolve_placement_only",
        lambda *_a, **_k: SimpleNamespace(ref="kitty/mission-x"),
    )
    monkeypatch.setattr(
        executor, "run_command", lambda *_a, **_k: (0, _CAPTURED_SHA + "\n", "")
    )
    run = SimpleNamespace(
        main_repo=Path("/repo"),
        mission_slug="slug-01ab",
        pre_target_coord_ref=None,
        pre_target_coord_sha=None,
    )
    _capture_pre_target_coord_ref_sha(run)
    assert run.pre_target_coord_ref == "kitty/mission-x"
    assert run.pre_target_coord_sha == _CAPTURED_SHA
