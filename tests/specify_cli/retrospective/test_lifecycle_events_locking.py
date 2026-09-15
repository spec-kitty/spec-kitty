"""Locking + atomicity pins for ``retrospective/lifecycle_events.py`` (WP01 T002).

Family 5 of the writer census (data-model.md section 2): the live post-merge
retrospective appender. After WP01 every append is (a) performed while the
mission status lock keyed on ``feature_dir.name`` is held, (b) written through
the atomic store primitive, and (c) preceded by a Lamport read under the SAME
acquisition (no TOCTOU between read and append).
"""

from __future__ import annotations

import ast
import json
import threading
from pathlib import Path
from typing import Any

import pytest

import specify_cli.retrospective.lifecycle_events as retro_lifecycle
import specify_cli.status.store as status_store
from specify_cli.retrospective.lifecycle_events import (
    Actor,
    _append_retro_lifecycle_event,
    _resolve_lock_timeout,
    bounded_lock_timeout,
    emit_capture_failed,
    emit_skipped,
    retro_status_lock,
)
from specify_cli.status import FeatureStatusLockTimeoutError, feature_status_lock
from specify_cli.status.locking import _get_thread_locks, feature_status_lock_path
from specify_cli.workspace.root_resolver import resolve_status_lock_root

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01KS049J4V9CSWBKJHTY2FB69H"
MISSION_SLUG = "retro-locking-01KS049J"
_ACTOR = Actor(kind="runtime", id="spec-kitty-test")


@pytest.fixture
def feature_dir(tmp_path: Path) -> Path:
    fd = tmp_path / "kitty-specs" / MISSION_SLUG
    fd.mkdir(parents=True)
    return fd


def _expected_lock_path(feature_dir: Path) -> Path:
    return feature_status_lock_path(resolve_status_lock_root(feature_dir), feature_dir.name)


def _rows(feature_dir: Path) -> list[dict[str, Any]]:
    path = feature_dir / "status.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class _WriteRecorder:
    """Record the lock paths held at the moment the store primitive writes."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.held_at_write: list[set[str]] = []
        original = status_store._fsync_directory

        def _record(directory: Path) -> None:
            self.held_at_write.append(set(_get_thread_locks()))
            original(directory)

        monkeypatch.setattr(status_store, "_fsync_directory", _record)


def _emit_failed(feature_dir: Path, **overrides: Any) -> Any:
    repo_root = feature_dir.parent.parent
    kwargs: dict[str, Any] = {
        "failure_category": "other",
        "failure_message": "test",
        "remediation_hint": None,
        "policy_source": {},
        "attempted_provenance_kind": "runtime_post_completion",
        "missing_artifacts": None,
        "actor": _ACTOR,
    }
    kwargs.update(overrides)
    return emit_capture_failed(MISSION_ID, MISSION_SLUG, repo_root, **kwargs)


# ---------------------------------------------------------------------------
# Lock held during the append; primitive is the atomic one
# ---------------------------------------------------------------------------


def test_public_appender_writes_while_mission_lock_is_held(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _WriteRecorder(monkeypatch)
    event = _emit_failed(feature_dir)
    assert len(recorder.held_at_write) == 1
    assert str(_expected_lock_path(feature_dir)) in recorder.held_at_write[0]
    assert [row["event_id"] for row in _rows(feature_dir)] == [event.event_id]


def test_raw_append_helper_writes_while_mission_lock_is_held(feature_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _WriteRecorder(monkeypatch)
    _append_retro_lifecycle_event(feature_dir, {"type": "X", "event_id": "E1", "lamport": 1})
    assert len(recorder.held_at_write) == 1
    assert str(_expected_lock_path(feature_dir)) in recorder.held_at_write[0]
    assert _rows(feature_dir) == [{"type": "X", "event_id": "E1", "lamport": 1}]


def test_lock_is_released_after_append(feature_dir: Path) -> None:
    _emit_failed(feature_dir)
    assert str(_expected_lock_path(feature_dir)) not in _get_thread_locks()


def test_module_has_no_raw_append_open() -> None:
    """The atomic primitive replaced the bare ``open(..., "a")`` (I-2)."""
    source = Path(retro_lifecycle.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
        if name != "open":
            continue
        modes = [arg.value for arg in node.args[1:2] if isinstance(arg, ast.Constant)]
        modes += [kw.value.value for kw in node.keywords if kw.arg == "mode" and isinstance(kw.value, ast.Constant)]
        assert not any("a" in str(mode) for mode in modes), f"raw append open at line {node.lineno}"
    assert "append_raw_rows_atomic" in source


def test_repo_backed_feature_dir_never_takes_the_null_path(feature_dir: Path) -> None:
    """The lock path resolves inside the sandbox for a kitty-specs-shaped dir."""
    with retro_status_lock(feature_dir) as lock_path:
        assert lock_path == _expected_lock_path(feature_dir)
        assert lock_path.name == f"{feature_dir.name}.status.lock"
        assert str(lock_path) in _get_thread_locks()


# ---------------------------------------------------------------------------
# Lamport read + append under one acquisition
# ---------------------------------------------------------------------------


def test_lamport_increments_monotonically_under_two_threads(feature_dir: Path) -> None:
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _worker() -> None:
        try:
            barrier.wait(timeout=5)
            for _ in range(5):
                _emit_failed(feature_dir, lock_timeout=10.0)
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads)
    assert not errors, errors
    lamports = [row["lamport"] for row in _rows(feature_dir)]
    assert lamports == list(range(1, 11)), lamports


def test_nested_inside_outer_mission_lock_does_not_deadlock(feature_dir: Path) -> None:
    """Re-entrancy: a caller already holding L1 (e.g. a transaction) can append."""
    lock_root = resolve_status_lock_root(feature_dir)
    with feature_status_lock(lock_root, feature_dir.name, timeout=2):
        event = _emit_failed(feature_dir, lock_timeout=2.0)
    assert [row["event_id"] for row in _rows(feature_dir)] == [event.event_id]


# ---------------------------------------------------------------------------
# Timeout resolution: explicit keyword > scoped default > unbounded
# ---------------------------------------------------------------------------


def test_resolve_lock_timeout_defaults_to_unbounded() -> None:
    assert _resolve_lock_timeout(None) == -1.0


def test_resolve_lock_timeout_prefers_explicit_keyword() -> None:
    with bounded_lock_timeout(3.0):
        assert _resolve_lock_timeout(0.25) == 0.25


def test_bounded_lock_timeout_scope_applies_and_resets() -> None:
    with bounded_lock_timeout(3.0):
        assert _resolve_lock_timeout(None) == 3.0
        with bounded_lock_timeout(1.0):
            assert _resolve_lock_timeout(None) == 1.0
        assert _resolve_lock_timeout(None) == 3.0
    assert _resolve_lock_timeout(None) == -1.0


def test_contended_lock_raises_structured_timeout_error(feature_dir: Path) -> None:
    """A FeatureStatusLockTimeoutError is an outage signal: it propagates."""
    lock_root = resolve_status_lock_root(feature_dir)
    holder_ready = threading.Event()
    release = threading.Event()

    def _hold() -> None:
        with feature_status_lock(lock_root, feature_dir.name, timeout=5):
            holder_ready.set()
            release.wait(timeout=10)

    holder = threading.Thread(target=_hold)
    holder.start()
    try:
        assert holder_ready.wait(timeout=5)
        with pytest.raises(FeatureStatusLockTimeoutError) as excinfo:
            _emit_failed(feature_dir, lock_timeout=0.2)
        assert str(_expected_lock_path(feature_dir)) in str(excinfo.value)
        with bounded_lock_timeout(0.2), pytest.raises(FeatureStatusLockTimeoutError):
            emit_skipped(
                MISSION_ID,
                MISSION_SLUG,
                feature_dir.parent.parent,
                skip_reason="contention test",
                skip_reason_source="cli_flag",
                policy_source={},
                actor=Actor(kind="human", id="tester"),
            )
    finally:
        release.set()
        holder.join(timeout=10)
    assert not holder.is_alive()
    assert _rows(feature_dir) == []
