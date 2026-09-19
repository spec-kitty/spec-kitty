"""Tests for concurrent review isolation via ReviewLock.

Covers all 12 required test cases for T029 with 90%+ target coverage of
src/specify_cli/review/lock.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.review.lock import (
    LOCK_DIR,
    LOCK_FILE,
    ReviewLock,
    ReviewLockError,
    ReviewLockReadError,
    _apply_env_var_isolation,
    _get_isolation_config,
)

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lock(worktree: Path, pid: int = os.getpid(), agent: str = "claude", wp_id: str = "WP01") -> ReviewLock:
    """Create and save a ReviewLock to the given worktree directory."""
    lock = ReviewLock(
        worktree_path=str(worktree),
        wp_id=wp_id,
        agent=agent,
        started_at="2026-04-06T12:00:00+00:00",
        pid=pid,
    )
    lock.save(worktree)
    return lock


def _lock_path(worktree: Path) -> Path:
    return worktree / LOCK_DIR / LOCK_FILE


# ---------------------------------------------------------------------------
# T1: test_acquire_creates_lock_file
# ---------------------------------------------------------------------------


def test_acquire_creates_lock_file(tmp_path: Path) -> None:
    """Lock file exists after acquire()."""
    lock = ReviewLock.acquire(tmp_path, wp_id="WP01", agent="claude")

    assert _lock_path(tmp_path).exists(), "Lock file should be created"
    data = json.loads(_lock_path(tmp_path).read_text())
    assert data["wp_id"] == "WP01"
    assert data["agent"] == "claude"
    assert data["pid"] == os.getpid()


# ---------------------------------------------------------------------------
# T2: test_release_removes_lock_file
# ---------------------------------------------------------------------------


def test_release_removes_lock_file(tmp_path: Path) -> None:
    """Lock file is removed after release()."""
    ReviewLock.acquire(tmp_path, wp_id="WP01", agent="claude")
    assert _lock_path(tmp_path).exists()

    ReviewLock.release(tmp_path)
    assert not _lock_path(tmp_path).exists(), "Lock file should be removed after release"


# ---------------------------------------------------------------------------
# T3: test_acquire_blocks_on_active_lock
# ---------------------------------------------------------------------------


def test_acquire_blocks_on_active_lock(tmp_path: Path) -> None:
    """Raises ReviewLockError when an active lock exists (PID alive)."""
    # Place a lock with the CURRENT process PID (guaranteed alive).
    _make_lock(tmp_path, pid=os.getpid(), agent="codex", wp_id="WP02")

    with pytest.raises(ReviewLockError) as exc_info:
        ReviewLock.acquire(tmp_path, wp_id="WP03", agent="claude")

    msg = str(exc_info.value)
    assert "codex" in msg
    assert "WP02" in msg
    assert str(os.getpid()) in msg


# ---------------------------------------------------------------------------
# T4: test_acquire_overwrites_stale_lock
# ---------------------------------------------------------------------------


def test_acquire_overwrites_stale_lock(tmp_path: Path) -> None:
    """Stale lock (dead PID) is overwritten without raising an error."""
    # Simulate a dead PID via the canonical is_process_alive seam.
    dead_pid = 999999999  # Very unlikely to exist
    _make_lock(tmp_path, pid=dead_pid, agent="old-agent", wp_id="WP01")

    with patch("specify_cli.review.lock.is_process_alive", return_value=False):
        new_lock = ReviewLock.acquire(tmp_path, wp_id="WP01", agent="new-agent")

    assert new_lock.agent == "new-agent"
    data = json.loads(_lock_path(tmp_path).read_text())
    assert data["agent"] == "new-agent"


# ---------------------------------------------------------------------------
# T5: test_is_stale_with_dead_pid
# ---------------------------------------------------------------------------


def test_is_stale_with_dead_pid(tmp_path: Path) -> None:
    """is_stale() returns True when is_process_alive reports the PID is dead."""
    lock = ReviewLock(
        worktree_path=str(tmp_path),
        wp_id="WP01",
        agent="claude",
        started_at="2026-04-06T12:00:00+00:00",
        pid=999999999,
    )

    with patch("specify_cli.review.lock.is_process_alive", return_value=False):
        assert lock.is_stale() is True


# ---------------------------------------------------------------------------
# T6: test_is_stale_with_alive_pid
# ---------------------------------------------------------------------------


def test_is_stale_with_alive_pid(tmp_path: Path) -> None:
    """is_stale() returns False when is_process_alive reports the PID is live."""
    lock = ReviewLock(
        worktree_path=str(tmp_path),
        wp_id="WP01",
        agent="claude",
        started_at="2026-04-06T12:00:00+00:00",
        pid=os.getpid(),
    )

    with patch("specify_cli.review.lock.is_process_alive", return_value=True):
        assert lock.is_stale() is False


# ---------------------------------------------------------------------------
# T7: test_load_missing_file
# ---------------------------------------------------------------------------


def test_load_missing_file(tmp_path: Path) -> None:
    """load() returns None when lock file does not exist."""
    result = ReviewLock.load(tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# T8: test_load_malformed_json
# ---------------------------------------------------------------------------


def test_load_malformed_json(tmp_path: Path) -> None:
    """load() fails closed with ReviewLockReadError on invalid JSON.

    WP07/#4746 (cli-error-surface-seam): pre-fix, this silently returned
    None -- indistinguishable from "no active lock" -- which is a
    stale-lock safety gap (a corrupt lock must not be treated as absent).
    """
    lock_dir = tmp_path / LOCK_DIR
    lock_dir.mkdir(parents=True)
    (lock_dir / LOCK_FILE).write_text("{not valid json")

    with pytest.raises(ReviewLockReadError):
        ReviewLock.load(tmp_path)


def test_load_non_utf8_bytes(tmp_path: Path) -> None:
    """load() fails closed with ReviewLockReadError on non-UTF-8 bytes.

    WP07/#4746: pre-fix, this guard gap was fully unguarded (a raw
    UnicodeDecodeError traceback), not even the pre-fix None-on-malformed
    behavior of test_load_malformed_json.
    """
    lock_dir = tmp_path / LOCK_DIR
    lock_dir.mkdir(parents=True)
    (lock_dir / LOCK_FILE).write_bytes(b"\xff\xfe\x00not utf-8")

    with pytest.raises(ReviewLockReadError):
        ReviewLock.load(tmp_path)


# ---------------------------------------------------------------------------
# T9: test_isolation_config_env_var
# ---------------------------------------------------------------------------


def test_isolation_config_env_var(tmp_path: Path) -> None:
    """Config with env_var strategy is parsed correctly."""
    config_dir = tmp_path / ".kittify"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text(
        "review:\n  concurrent_isolation:\n    strategy: env_var\n    env_var: TEST_DB_SUFFIX\n    template: '{agent}_{wp_id}'\n"
    )

    result = _get_isolation_config(tmp_path)
    assert result is not None
    assert result["strategy"] == "env_var"
    assert result["env_var"] == "TEST_DB_SUFFIX"
    assert result["template"] == "{agent}_{wp_id}"


# ---------------------------------------------------------------------------
# T10: test_isolation_config_missing
# ---------------------------------------------------------------------------


def test_isolation_config_missing(tmp_path: Path) -> None:
    """_get_isolation_config returns None when config.yaml doesn't exist."""
    result = _get_isolation_config(tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# T11: test_apply_env_var_isolation
# ---------------------------------------------------------------------------


def test_apply_env_var_isolation(tmp_path: Path) -> None:
    """_apply_env_var_isolation sets env var with correctly formatted value."""
    config = {
        "strategy": "env_var",
        "env_var": "TEST_DB_SUFFIX",
        "template": "{agent}_{wp_id}",
    }

    try:
        _apply_env_var_isolation(config, agent="claude", wp_id="WP05")
        assert os.environ.get("TEST_DB_SUFFIX") == "claude_WP05"
    finally:
        os.environ.pop("TEST_DB_SUFFIX", None)


# ---------------------------------------------------------------------------
# T12: test_default_serialization_no_config
# ---------------------------------------------------------------------------


def test_default_serialization_no_config(tmp_path: Path) -> None:
    """Without config, default behavior is lock serialization (not env-var)."""
    # No .kittify/config.yaml present → _get_isolation_config returns None.
    isolation = _get_isolation_config(tmp_path)
    assert isolation is None, "Should return None when no config exists"

    # Verify that acquire/release work correctly (serialization path).
    lock = ReviewLock.acquire(tmp_path, wp_id="WP01", agent="claude")
    assert _lock_path(tmp_path).exists()

    ReviewLock.release(tmp_path)
    assert not _lock_path(tmp_path).exists()


# ---------------------------------------------------------------------------
# Additional edge-case tests for coverage
# ---------------------------------------------------------------------------


def test_release_no_lock_file_is_safe(tmp_path: Path) -> None:
    """release() is a no-op when no lock file exists."""
    # Should not raise.
    ReviewLock.release(tmp_path)


def test_is_stale_permission_error(tmp_path: Path) -> None:
    """is_stale() returns False when the process exists but cannot be inspected.

    Mirrors is_process_alive's conservative AccessDenied -> True (alive) posture:
    the process exists but permissions block inspection (e.g. different user).
    """
    lock = ReviewLock(
        worktree_path=str(tmp_path),
        wp_id="WP01",
        agent="claude",
        started_at="2026-04-06T12:00:00+00:00",
        pid=1234,
    )

    with patch("specify_cli.review.lock.is_process_alive", return_value=True):
        assert lock.is_stale() is False


def test_is_stale_os_error(tmp_path: Path) -> None:
    """is_stale() returns True when is_process_alive cannot confirm liveness."""
    lock = ReviewLock(
        worktree_path=str(tmp_path),
        wp_id="WP01",
        agent="claude",
        started_at="2026-04-06T12:00:00+00:00",
        pid=1234,
    )

    with patch("specify_cli.review.lock.is_process_alive", return_value=False):
        assert lock.is_stale() is True


def test_load_missing_fields_returns_none(tmp_path: Path) -> None:
    """load() fails closed with ReviewLockReadError when JSON is valid but
    fields are missing (WP07/#4746 -- see test_load_malformed_json)."""
    lock_dir = tmp_path / LOCK_DIR
    lock_dir.mkdir(parents=True)
    (lock_dir / LOCK_FILE).write_text('{"wp_id": "WP01"}')  # Missing required fields

    with pytest.raises(ReviewLockReadError):
        ReviewLock.load(tmp_path)


def test_isolation_config_no_review_section(tmp_path: Path) -> None:
    """_get_isolation_config returns None when config.yaml has no review section."""
    config_dir = tmp_path / ".kittify"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("vcs:\n  type: git\n")

    result = _get_isolation_config(tmp_path)
    assert result is None


def test_isolation_config_wrong_strategy(tmp_path: Path) -> None:
    """_get_isolation_config returns None when strategy is not env_var."""
    config_dir = tmp_path / ".kittify"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("review:\n  concurrent_isolation:\n    strategy: other\n")

    result = _get_isolation_config(tmp_path)
    assert result is None


def test_lock_roundtrip(tmp_path: Path) -> None:
    """ReviewLock saves and loads correctly (round-trip)."""
    original = ReviewLock(
        worktree_path=str(tmp_path),
        wp_id="WP07",
        agent="gemini",
        started_at="2026-04-06T15:00:00+00:00",
        pid=42,
    )
    original.save(tmp_path)

    loaded = ReviewLock.load(tmp_path)
    assert loaded is not None
    assert loaded.wp_id == "WP07"
    assert loaded.agent == "gemini"
    assert loaded.pid == 42
    assert loaded.started_at == "2026-04-06T15:00:00+00:00"
