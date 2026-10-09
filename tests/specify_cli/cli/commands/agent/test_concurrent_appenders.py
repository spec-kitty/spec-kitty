"""Overlapping appenders keep every entry (concurrent-mission-writers WP04, #5820 / #5467).

Red-first reproductions. Each test pauses writer A at the seam between its read
of the current text and its write, lets writer B run, then releases A:

* ``add-history`` (#5820 / #2334): each call records its note as an append-only
  event-log annotation under the per-Mission status lock, so two overlapping
  writers both keep their notes (no shared markdown buffer to clobber).
* ``tracer-append`` (#5467): A reads ``traces/<category>.md``, B appends and
  commits, A writes its merged copy and commits. Before the fix B's finding was
  absent from the committed file, on a coord and on a lanes Mission.

The pause is a ``threading.Event`` hook (never a ``sleep``) and every wait is
bounded, so a regression fails instead of hanging.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import specify_cli.cli.commands.agent.tasks as tasks_module
import specify_cli.retrospective.tracer_writer as tracer_module
from mission_runtime import MissionTopology
from specify_cli.retrospective.tracer_writer import append_tracer_finding
from tests.integration.coord_topology_fixture import _build_coord_topology
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
    _write_wp_and_lanes,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

#: Bound for every cross-thread wait; a regression fails after this, never hangs.
WAIT_SECONDS = 20.0
#: How long writer B gets to reach its read while A is paused. Post-fix B is blocked
#: on the Mission lock and never reaches it, so this is the only timed wait.
B_PROGRESS_SECONDS = 1.0

CATEGORY = "approach"
NOTE_A = "NOTE-FROM-WRITER-A"
NOTE_B = "NOTE-FROM-WRITER-B"
FINDING_A = "FINDING-FROM-WRITER-A"
FINDING_B = "FINDING-FROM-WRITER-B"


class _OpenPolicy:
    def is_protected(self, ref: str) -> bool:
        return False


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


class _Pause:
    """Pause the first caller of a wrapped function after the real call returned."""

    def __init__(self) -> None:
        self.reached = threading.Event()
        self.release = threading.Event()
        self.other_reached = threading.Event()
        self._first = threading.Event()
        self._guard = threading.Lock()

    def wrap(self, real: Callable[..., Any]) -> Callable[..., Any]:
        def hooked(*args: Any, **kwargs: Any) -> Any:
            value = real(*args, **kwargs)
            with self._guard:
                is_first = not self._first.is_set()
                self._first.set()
            if is_first:
                self.reached.set()
                assert self.release.wait(WAIT_SECONDS), "writer A was never released"
            else:
                self.other_reached.set()
            return value

        return hooked


def _run_in_thread(target: Callable[[], None], errors: list[BaseException]) -> threading.Thread:
    def runner() -> None:
        try:
            target()
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


def _join(thread: threading.Thread) -> None:
    thread.join(WAIT_SECONDS)
    assert not thread.is_alive(), "writer thread did not finish"


# ---------------------------------------------------------------------------
# #5820 add-history
# ---------------------------------------------------------------------------


def _lanes_mission(tmp_path: Path) -> tuple[Path, str, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    result = _create_mission(repo, "append-demo", MissionTopology.LANES)
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    _write_wp_and_lanes(result.feature_dir, result.mission_slug, str(meta["mission_id"]), "main")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed WP01")
    return repo, result.mission_slug, result.feature_dir / "tasks" / "WP01.md"


def test_overlapping_add_history_keeps_both_notes(tmp_path: Path) -> None:
    """#5820 / #2334: concurrent add-history calls both land in the event log.

    add-history records each note as an append-only ``InnerStateChanged`` note
    annotation under the per-Mission status lock (``emit_runtime_annotation``,
    #2334 end state (ii)), not a read-modify-write of a shared ``## Activity
    Log`` markdown section. Two overlapping writers therefore cannot lose each
    other's note: there is no stale shared buffer to clobber.
    """
    from specify_cli.status import read_event_stream

    repo, slug, wp_file = _lanes_mission(tmp_path)
    feature_dir = wp_file.parent.parent
    errors: list[BaseException] = []

    def add(note: str) -> Callable[[], None]:
        return lambda: tasks_module.add_history(task_id="WP01", note=note, mission=slug, agent="a", shell_pid=None, json_output=True)

    with patch.object(tasks_module, "locate_project_root", return_value=repo):
        thread_a = _run_in_thread(add(NOTE_A), errors)
        thread_b = _run_in_thread(add(NOTE_B), errors)
        _join(thread_a)
        _join(thread_b)

    assert not errors, errors
    notes = [annotation.delta.note or "" for annotation in read_event_stream(feature_dir).annotations if annotation.wp_id == "WP01"]
    assert any(NOTE_A in note for note in notes), f"writer A's note was lost; notes={notes!r}"
    assert any(NOTE_B in note for note in notes), f"writer B's note was lost; notes={notes!r}"


# ---------------------------------------------------------------------------
# #5467 tracer-append
# ---------------------------------------------------------------------------


def _overlap_tracer_appends(repo: Path, slug: str, monkeypatch: pytest.MonkeyPatch) -> None:
    pause = _Pause()
    monkeypatch.setattr(
        tracer_module,
        "_read_current_coord_content",
        pause.wrap(tracer_module._read_current_coord_content),
    )
    errors: list[BaseException] = []

    def append(entry: str, actor: str) -> Callable[[], None]:
        def run() -> None:
            result = append_tracer_finding(repo_root=repo, mission_slug=slug, category=CATEGORY, entry=entry, actor=actor, policy=_OpenPolicy())
            assert result.status == "committed", result.diagnostic

        return run

    thread_a = _run_in_thread(append(FINDING_A, "alice"), errors)
    assert pause.reached.wait(WAIT_SECONDS), "writer A never read the traces file"
    thread_b = _run_in_thread(append(FINDING_B, "bob"), errors)
    # Pre-fix B reads and commits while A is paused. Post-fix B waits on the
    # Mission lock A holds, so it never reaches its read inside this window.
    pause.other_reached.wait(B_PROGRESS_SECONDS)
    if pause.other_reached.is_set():
        _join(thread_b)
    pause.release.set()
    _join(thread_a)
    _join(thread_b)
    assert not errors, errors


def _committed_traces(repo: Path, ref: str, slug: str) -> str:
    return _git(repo, "show", f"{ref}:kitty-specs/{slug}/traces/{CATEGORY}.md")


def test_overlapping_tracer_appends_keep_both_findings_on_coord(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)

    _overlap_tracer_appends(ctx.repo, ctx.slug, monkeypatch)

    committed = _committed_traces(ctx.repo, ctx.coord_branch, ctx.slug)
    assert FINDING_A in committed
    assert FINDING_B in committed, "writer B's finding is missing from the committed coord traces file"


def test_overlapping_tracer_appends_keep_both_findings_on_lanes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")  # a lanes Mission commits on main here
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    result = _create_mission(repo, "tracer-lanes", MissionTopology.LANES)
    _git(repo, "add", ".")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed mission", "--allow-empty")

    _overlap_tracer_appends(repo, result.mission_slug, monkeypatch)

    committed = _committed_traces(repo, "HEAD", result.mission_slug)
    assert FINDING_A in committed
    assert FINDING_B in committed, "writer B's finding is missing from the committed lanes traces file"
