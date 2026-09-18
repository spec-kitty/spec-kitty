"""Tests for the ``spec-kitty auth doctor`` opt-in repair flag (WP06 / T028).

Covers ``--unstick-lock`` (force-release the refresh lock via WP01). The
``--reset`` orphan-sweep flag was removed together with the sync transport
(issue #5); ``--unstick-lock`` is now the only repair surface.

The age-guard inside :func:`force_release` (``only_if_age_s``) is the
WP01-enforced safety belt — :func:`doctor_impl` must pass the
``stuck_threshold`` through unchanged.
"""

from __future__ import annotations

import json
from kernel.clock import now_utc, timedelta
from pathlib import Path

import pytest

from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands import _auth_doctor
from specify_cli.cli.commands._auth_doctor import doctor_impl
from kernel.locks import read_lock_record


pytestmark = [pytest.mark.integration]

def _make_session() -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-abc",
        email="rob@example.com",
        name="Rob",
        teams=[Team(id="t1", name="Personal", role="owner", is_private_teamspace=True)],
        default_team_id="t1",
        access_token="access-xyz",
        refresh_token="refresh-xyz",
        session_id="session-xyz",
        issued_at=now,
        access_token_expires_at=now + timedelta(minutes=15),
        refresh_token_expires_at=now + timedelta(days=30),
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


class _FakeStorage:
    def __init__(self, session: StoredSession | None) -> None:
        self._session = session

    def read(self) -> StoredSession | None:
        return self._session

    def write(self, session: StoredSession) -> None:
        self._session = session


class _FakeTokenManager:
    def __init__(self, session: StoredSession | None) -> None:
        self._session = session
        self._storage = _FakeStorage(session)

    def get_current_session(self) -> StoredSession | None:
        return self._session


def _patch_state(
    monkeypatch: pytest.MonkeyPatch,
    *,
    session: StoredSession | None,
    lock_path: Path,
) -> None:
    """Wire ``_auth_doctor``'s upstream calls to deterministic fakes.

    Important: ``read_lock_record`` is NOT patched — the tests want
    ``--unstick-lock`` to read the *real* file at ``lock_path`` so the
    ``force_release`` age guard is exercised end-to-end.
    """
    monkeypatch.setattr(
        _auth_doctor,
        "get_token_manager",
        lambda: _FakeTokenManager(session),
    )
    monkeypatch.setattr(_auth_doctor, "_refresh_lock_path", lambda: lock_path)


def _write_lock_record(path: Path, *, age_s: float) -> None:
    """Write a JSON lock record at ``path`` with started_at = now - age_s."""
    started = now_utc() - timedelta(seconds=age_s)
    payload = {
        "schema_version": 1,
        "pid": 99999,
        "started_at": started.isoformat(),
        "host": "localhost",
        "version": "3.2.0a5",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# --unstick-lock
# ---------------------------------------------------------------------------


def test_unstick_drops_old_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """120-second-old lock + ``--unstick-lock`` ⇒ lock record cleared."""
    session = _make_session()
    lock_path = tmp_path / "auth" / "refresh.lock"
    _write_lock_record(lock_path, age_s=120.0)
    assert lock_path.exists()

    _patch_state(
        monkeypatch,
        session=session,
        lock_path=lock_path,
    )

    exit_code = doctor_impl(
        json_output=True, unstick_lock=True, stuck_threshold=60.0
    )

    assert read_lock_record(lock_path) is None
    # F-003 was the only critical finding; after the unstick repair the
    # second pass finds nothing critical so exit 0.
    assert exit_code == 0


def test_unstick_preserves_fresh_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """5-second-old lock + ``--unstick-lock`` ⇒ no-op; lock still present."""
    session = _make_session()
    lock_path = tmp_path / "auth" / "refresh.lock"
    _write_lock_record(lock_path, age_s=5.0)
    assert lock_path.exists()

    _patch_state(
        monkeypatch,
        session=session,
        lock_path=lock_path,
    )

    exit_code = doctor_impl(
        json_output=True, unstick_lock=True, stuck_threshold=60.0
    )

    assert lock_path.exists(), "Fresh lock must not be removed"
    # No F-003 (lock not stuck), no other critical findings, exit 0.
    assert exit_code == 0


def test_unstick_noop_without_stuck_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--unstick-lock`` without a stuck lock ⇒ no-op message, lock absent."""
    session = _make_session()
    lock_path = tmp_path / "auth" / "refresh.lock"
    _patch_state(monkeypatch, session=session, lock_path=lock_path)

    def _fail_force_release(*args: object, **kwargs: object) -> bool:
        raise AssertionError("force_release must not run when F-003 is absent")

    monkeypatch.setattr(_auth_doctor, "force_release", _fail_force_release)

    exit_code = doctor_impl(
        json_output=False, unstick_lock=True, stuck_threshold=60.0
    )

    # No critical findings before or after the no-op repair.
    assert exit_code == 0


def test_unstick_passes_stuck_threshold_to_force_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``doctor_impl`` forwards ``stuck_threshold`` unchanged to ``force_release``.

    A 400 s lock with a raised threshold (300 s) is still stuck, so the
    repair fires — and must receive the operator-supplied threshold, not a
    hardcoded default.
    """
    session = _make_session()
    lock_path = tmp_path / "auth" / "refresh.lock"
    _write_lock_record(lock_path, age_s=400.0)

    seen_thresholds: list[float] = []

    def fake_force_release(path: object, *, only_if_age_s: float) -> bool:
        seen_thresholds.append(only_if_age_s)
        return False

    monkeypatch.setattr(_auth_doctor, "force_release", fake_force_release)
    _patch_state(monkeypatch, session=session, lock_path=lock_path)

    exit_code = doctor_impl(
        json_output=True, unstick_lock=True, stuck_threshold=300.0
    )

    assert seen_thresholds == [300.0]
    # The fake declined to release, so the refreshed report still carries
    # the critical F-003 finding.
    assert exit_code == 1
