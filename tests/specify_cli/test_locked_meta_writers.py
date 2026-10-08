"""Every ``meta.json`` read-modify-write runs under the Mission write lock (mission-writer-followups WP02, US1).

Each overlap test pauses writer A right after it read ``meta.json`` (an injected pause point on the fail-closed
reader, not a sleep), lets writer B run its whole setter on another thread, then lets A finish. Without the lock
A writes its stale copy over B's field; with it, B queues behind A and both fields survive.
"""

from __future__ import annotations

import json
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

import specify_cli.mission_metadata as mm
from specify_cli.core.atomic import atomic_write
from specify_cli.lanes.implement_support import ensure_vcs_locked
from specify_cli.mission_metadata import (
    clear_merge_metadata,
    flatten_coordination_metadata,
    locked_update_meta,
    record_acceptance,
    record_discard,
    restore_meta_text,
    set_documentation_state,
    set_origin_ticket,
    set_target_branch,
    set_vcs_lock,
)
from specify_cli.status import FeatureStatusLockTimeoutError, mission_write_lock

pytestmark = [pytest.mark.unit]

SLUG = "060-test"
MID8 = "01COORD0"
# How long writer A stays paused waiting for writer B to finish. Unlocked, B finishes at once and the wait ends
# early; locked, B is queued behind A, so the wait runs out and A proceeds.
PAUSE_SECONDS = 0.5
JOIN_SECONDS = 20.0
WRITER_A = "writer-a"

ORIGIN_TICKET = {
    "provider": "github",
    "resource_type": "repo",
    "resource_id": "o/r",
    "external_issue_id": "1",
    "external_issue_key": "o/r#1",
    "external_issue_url": "https://example.invalid/1",
    "title": "t",
}


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def mission(tmp_path: Path) -> tuple[Path, Path]:
    """``(repo, feature_dir)`` for a coordination Mission carrying merge markers."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    feature_dir = repo / "kitty-specs" / SLUG
    feature_dir.mkdir(parents=True)
    meta = {
        "slug": SLUG,
        "mission_slug": SLUG,
        "friendly_name": "Test",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-04-13T00:00:00+00:00",
        "mission_id": f"{MID8}XXXXXXXXXXXXXXXXXX",
        "mid8": MID8,
        "coordination_branch": f"kitty/mission-{SLUG}-{MID8}",
        "topology": "coord",
        "merged_at": "2026-01-01T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return repo, feature_dir


def _meta(feature_dir: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return loaded


Setter = Callable[[Path], object]

# (name, setter, the meta key the setter leaves behind)
SETTERS: dict[str, tuple[Setter, str]] = {
    "record_acceptance": (lambda d: record_acceptance(d, accepted_by="a", mode="local"), "accepted_by"),
    "record_discard": (record_discard, "discarded_at"),
    "set_target_branch": (lambda d: set_target_branch(d, "develop"), "target_branch"),
    "set_origin_ticket": (lambda d: set_origin_ticket(d, dict(ORIGIN_TICKET)), "origin_ticket"),
    "set_documentation_state": (lambda d: set_documentation_state(d, {"iteration_mode": "initial"}), "documentation_state"),
    "set_vcs_lock": (lambda d: set_vcs_lock(d, vcs_type="git", locked_at="2026-01-01T00:00:00+00:00"), "vcs"),
    "clear_merge_metadata": (clear_merge_metadata, "merged_at"),
    "flatten_coordination_metadata": (flatten_coordination_metadata, "flattened"),
}

PAIRS = [
    ("record_acceptance", "set_target_branch"),
    ("set_origin_ticket", "record_discard"),
    ("set_documentation_state", "set_vcs_lock"),
    ("clear_merge_metadata", "set_origin_ticket"),
    ("flatten_coordination_metadata", "record_acceptance"),
    ("set_target_branch", "flatten_coordination_metadata"),
]


def _run_overlap(monkeypatch: pytest.MonkeyPatch, feature_dir: Path, first: Setter, second: Setter) -> list[Exception]:
    """Run *first* paused after its read while *second* runs on another thread; return their errors."""
    a_read = threading.Event()
    b_done = threading.Event()
    errors: list[Exception] = []
    real_read = mm._load_meta_fail_closed

    def paused_read(directory: Path) -> dict[str, Any] | None:
        result = real_read(directory)
        if threading.current_thread().name == WRITER_A and not a_read.is_set():
            a_read.set()
            b_done.wait(PAUSE_SECONDS)
        return result

    monkeypatch.setattr(mm, "_load_meta_fail_closed", paused_read)

    def run_a() -> None:
        try:
            first(feature_dir)
        except Exception as exc:
            errors.append(exc)

    def run_b() -> None:
        a_read.wait(JOIN_SECONDS)
        try:
            second(feature_dir)
        except Exception as exc:
            errors.append(exc)
        finally:
            b_done.set()

    threads = [threading.Thread(target=run_a, name=WRITER_A), threading.Thread(target=run_b)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(JOIN_SECONDS)
    return errors


@pytest.mark.parametrize(("first", "second"), PAIRS)
def test_overlapping_writers_keep_both_writes(mission: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, first: str, second: str) -> None:
    _repo, feature_dir = mission
    first_setter, first_key = SETTERS[first]
    second_setter, second_key = SETTERS[second]

    errors = _run_overlap(monkeypatch, feature_dir, first_setter, second_setter)

    assert errors == []
    final = _meta(feature_dir)
    for name, key in ((first, first_key), (second, second_key)):
        if name == "clear_merge_metadata":
            assert key not in final, f"{name} write lost"
        else:
            assert key in final, f"{name} write lost"
        if key == "target_branch":
            assert final[key] == "develop", f"{name} write lost"


def test_locked_update_meta_rereads_under_the_lock_and_writes_atomically(mission: tuple[Path, Path]) -> None:
    _repo, feature_dir = mission

    def mutate(meta: dict[str, Any]) -> None:
        meta["probe"] = meta["target_branch"] + "-seen"

    result = locked_update_meta(feature_dir, mutate)

    assert result["probe"] == "main-seen"
    assert _meta(feature_dir)["probe"] == "main-seen"
    assert not list(feature_dir.glob("*.tmp"))


def test_locked_update_meta_skips_the_write_when_mutate_reports_no_change(mission: tuple[Path, Path]) -> None:
    _repo, feature_dir = mission
    before = (feature_dir / "meta.json").read_text(encoding="utf-8")

    locked_update_meta(feature_dir, lambda meta: False)

    assert (feature_dir / "meta.json").read_text(encoding="utf-8") == before


def test_locked_update_meta_missing_meta_raises(mission: tuple[Path, Path]) -> None:
    _repo, feature_dir = mission
    (feature_dir / "meta.json").unlink()

    with pytest.raises(FileNotFoundError):
        locked_update_meta(feature_dir, lambda meta: None)


def test_locked_update_meta_waits_a_bounded_time_then_fails_with_status_lock_held(mission: tuple[Path, Path]) -> None:
    repo, feature_dir = mission
    holder_in = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with mission_write_lock(feature_dir, repo_root=repo):
            holder_in.set()
            release.wait(JOIN_SECONDS)

    thread = threading.Thread(target=hold)
    thread.start()
    try:
        assert holder_in.wait(JOIN_SECONDS)
        with pytest.raises(FeatureStatusLockTimeoutError) as caught:
            locked_update_meta(feature_dir, lambda meta: None, repo_root=repo, timeout=0.2)
        assert caught.value.error_code == "STATUS_LOCK_HELD"
    finally:
        release.set()
        thread.join(JOIN_SECONDS)


def test_setter_nests_under_a_held_mission_lock(mission: tuple[Path, Path]) -> None:
    repo, feature_dir = mission

    with mission_write_lock(feature_dir, repo_root=repo, timeout=0.2):
        set_target_branch(feature_dir, "develop")
        flatten_coordination_metadata(feature_dir)
        record_discard(feature_dir)

    final = _meta(feature_dir)
    assert final["target_branch"] == "develop"
    assert final["flattened"] is True
    assert "discarded_at" in final


def test_ensure_vcs_locked_writes_through_the_helper_without_a_second_acquisition(mission: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir = mission
    seen: list[float] = []
    import specify_cli.status.mission_write as mission_write

    real = mission_write.feature_status_lock

    def recording(root: Path, key: str, *, timeout: float) -> Any:
        seen.append(timeout)
        return real(root, key, timeout=timeout)

    monkeypatch.setattr(mission_write, "feature_status_lock", recording)

    assert ensure_vcs_locked(feature_dir, repo_root=repo) is True
    assert _meta(feature_dir)["vcs"] == "git"
    assert seen[0] < 0  # the outer claim hold is unbounded (NFR-002)


def test_uncontended_helper_adds_one_lock_acquisition_and_no_extra_subprocess(mission: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch) -> None:
    repo, feature_dir = mission
    import specify_cli.status.mission_write as mission_write

    acquisitions: list[str] = []
    commands: list[list[str]] = []
    real_lock = mission_write.feature_status_lock
    real_run = subprocess.run

    def recording_lock(root: Path, key: str, *, timeout: float) -> Any:
        acquisitions.append(key)
        return real_lock(root, key, timeout=timeout)

    def recording_run(command: Any, *args: Any, **kwargs: Any) -> Any:
        commands.append(list(command))
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(mission_write, "feature_status_lock", recording_lock)
    monkeypatch.setattr(subprocess, "run", recording_run)

    locked_update_meta(feature_dir, lambda meta: meta.update(probe=1), repo_root=repo)

    assert len(acquisitions) == 1
    # The only git call is the lock primitive's own common-dir lookup; the helper adds none.
    assert all("--git-common-dir" in command for command in commands), commands


def test_restore_meta_text_compare_and_swap(mission: tuple[Path, Path]) -> None:
    repo, feature_dir = mission
    meta_path = feature_dir / "meta.json"
    original = meta_path.read_text(encoding="utf-8")
    written = original.replace("main", "feature-x")
    atomic_write(meta_path, written)

    assert restore_meta_text(feature_dir, original, expected_current=written, repo_root=repo) is True
    assert meta_path.read_text(encoding="utf-8") == original

    atomic_write(meta_path, "someone else wrote this\n")
    assert restore_meta_text(feature_dir, original, expected_current=written, repo_root=repo) is False
    assert meta_path.read_text(encoding="utf-8") == "someone else wrote this\n"


def test_restore_meta_text_without_expectation_still_restores(mission: tuple[Path, Path]) -> None:
    _repo, feature_dir = mission
    meta_path = feature_dir / "meta.json"
    original = meta_path.read_text(encoding="utf-8")
    atomic_write(meta_path, "changed\n")

    assert restore_meta_text(feature_dir, original) is True
    assert meta_path.read_text(encoding="utf-8") == original
