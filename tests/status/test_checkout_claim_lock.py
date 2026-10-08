"""``write_checkout_claim_lock`` (concurrent-mission-writers WP01, #5819, plan D4/A9)."""

from __future__ import annotations

import hashlib
import os
import subprocess
import threading
from pathlib import Path

import pytest

from specify_cli.status import mission_write_lock, write_checkout_claim_lock
from specify_cli.status.locking import (
    CHECKOUT_CLAIM_LOCK_TIMEOUT_SECONDS,
    FeatureStatusLockTimeoutError,
    _get_thread_locks,
    feature_status_lock,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True, capture_output=True)
    return root


def test_default_timeout_is_two_minutes() -> None:
    assert CHECKOUT_CLAIM_LOCK_TIMEOUT_SECONDS == 120.0


def test_key_is_the_normcased_resolved_checkout_digest(checkout: Path) -> None:
    digest = hashlib.sha1(os.path.normcase(str(checkout.resolve())).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    with write_checkout_claim_lock(checkout) as lock_path:
        assert lock_path == checkout / ".git" / "spec-kitty-locks" / f"__checkout-{digest}__.status.lock"
        assert str(lock_path) in _get_thread_locks()
    assert str(lock_path) not in _get_thread_locks()


def test_reentrant_on_one_thread(checkout: Path) -> None:
    with write_checkout_claim_lock(checkout) as outer, write_checkout_claim_lock(checkout) as inner:
        assert outer == inner


def test_a_second_thread_blocks_until_the_first_releases(checkout: Path) -> None:
    holding = threading.Event()
    release = threading.Event()
    order: list[str] = []

    def _first() -> None:
        with write_checkout_claim_lock(checkout):
            order.append("first-in")
            holding.set()
            assert release.wait(10)
            order.append("first-out")

    def _second() -> None:
        with write_checkout_claim_lock(checkout, timeout=10):
            order.append("second-in")

    t1 = threading.Thread(target=_first)
    t1.start()
    assert holding.wait(10)
    t2 = threading.Thread(target=_second)
    t2.start()
    t2.join(0.3)
    assert t2.is_alive(), "second claimant entered while the first held the lock"
    release.set()
    t1.join(10)
    t2.join(10)
    assert order == ["first-in", "first-out", "second-in"]


def test_timeout_names_the_holder(checkout: Path) -> None:
    holding = threading.Event()
    release = threading.Event()

    def _hold() -> None:
        with write_checkout_claim_lock(checkout):
            holding.set()
            release.wait(10)

    thread = threading.Thread(target=_hold, name="claim-holder")
    thread.start()
    try:
        assert holding.wait(10)
        with pytest.raises(FeatureStatusLockTimeoutError) as raised, write_checkout_claim_lock(checkout, timeout=0.2):
            pass
        assert "claim-holder" in str(raised.value)
        assert raised.value.holder is not None and raised.value.holder["pid"] == os.getpid()
    finally:
        release.set()
        thread.join(10)


def test_lock_order_guard_refuses_a_checkout_lock_under_a_mission_lock(checkout: Path) -> None:
    with (
        mission_write_lock(checkout / "kitty-specs" / "m-01ABCDEF", repo_root=checkout),
        pytest.raises(RuntimeError, match=r"checkout claim lock must be taken before any Mission lock \(this thread already holds: .*m-01ABCDEF"),
        write_checkout_claim_lock(checkout),
    ):
        pass


def test_checkout_then_mission_is_the_allowed_order(checkout: Path) -> None:
    with write_checkout_claim_lock(checkout), feature_status_lock(checkout, "m-01ABCDEF"), write_checkout_claim_lock(checkout):
        pass


def test_two_checkouts_do_not_exclude_each_other(checkout: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=other, check=True, capture_output=True)
    with write_checkout_claim_lock(checkout) as first, write_checkout_claim_lock(other, timeout=0.2) as second:
        assert first != second
