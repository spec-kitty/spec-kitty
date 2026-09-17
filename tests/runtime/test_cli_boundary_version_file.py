"""FR-004: an unreadable version lock remains a diagnostic, never a crash."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.runtime import doctor

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize("as_directory", [False, True])
def test_unreadable_version_lock_is_actionable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, as_directory: bool) -> None:
    monkeypatch.setattr(doctor, "get_kittify_home", lambda: tmp_path)
    lock = tmp_path / "cache" / "version.lock"
    lock.parent.mkdir()
    if as_directory:
        lock.mkdir()
    else:
        lock.write_bytes(b"\xffinvalid")
    result = doctor.check_version_lock()
    assert not result.passed
    assert result.name == "version_lock"
    assert result.severity == "warning"
    assert str(lock) in result.message
    assert "read" in result.message.lower()


def test_global_checks_keep_running_after_bad_version_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "get_kittify_home", lambda: tmp_path)
    lock = tmp_path / "cache" / "version.lock"
    lock.parent.mkdir()
    lock.write_bytes(b"\xffbad")
    checks = doctor.run_global_checks()
    assert [check.name for check in checks] == ["global_runtime_exists", "version_lock", "mission_integrity"]
    assert not checks[1].passed
    assert str(lock) in checks[1].message
