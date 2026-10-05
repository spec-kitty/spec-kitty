"""Unit tests for ``specify_cli.feedback.preferences`` (hardened ``feedback.json``)."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

import pytest

from kernel.clock import UTC, datetime, parse_iso, timedelta
from kernel.locks import LockAcquireTimeout
from specify_cli.feedback import preferences as prefs_module
from specify_cli.feedback.preferences import (
    LOCK_FILENAME,
    MAX_PREFERENCES_BYTES,
    PREFERENCES_FILENAME,
    SurveyPreferences,
    Unreadable,
    load_preferences,
    lock_path_for,
    preferences_path,
    save_preferences,
    set_automatic_prompts,
)
from specify_cli.feedback.preferences import resolve_config_dir as real_resolve_config_dir

pytestmark = [pytest.mark.unit, pytest.mark.fast]

POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX ownership and mode checks")
SHOWN_AT = datetime(2026, 9, 1, 8, 30, tzinfo=UTC)


@pytest.fixture
def prefs_file(feedback_config_dir: Path) -> Path:
    return feedback_config_dir / PREFERENCES_FILENAME


def _write_raw(path: Path, content: str | bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    path.chmod(mode)


def _write_json(path: Path, data: Any) -> None:
    _write_raw(path, json.dumps(data))


# --- paths -------------------------------------------------------------------


def test_preferences_path_is_under_the_config_dir(feedback_config_dir: Path) -> None:
    assert preferences_path() == feedback_config_dir / PREFERENCES_FILENAME


def test_preferences_path_accepts_an_injected_resolver(tmp_path: Path) -> None:
    assert preferences_path(lambda: tmp_path / "elsewhere") == tmp_path / "elsewhere" / PREFERENCES_FILENAME


def test_resolve_config_dir_reuses_the_shared_config_dir_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.compat.config._resolve_config_dir", lambda: str(tmp_path / "shared"))

    assert real_resolve_config_dir() == tmp_path / "shared"


def test_lock_path_sits_beside_the_preferences_file(prefs_file: Path) -> None:
    assert lock_path_for(prefs_file) == prefs_file.parent / LOCK_FILENAME


# --- load --------------------------------------------------------------------


def test_missing_file_yields_defaults(prefs_file: Path) -> None:
    assert load_preferences(prefs_file) == SurveyPreferences()


def test_missing_config_dir_yields_defaults(tmp_path: Path) -> None:
    assert load_preferences(tmp_path / "absent" / PREFERENCES_FILENAME) == SurveyPreferences()


def test_default_path_is_used_when_none_given(prefs_file: Path) -> None:
    assert save_preferences(prefs_file, SurveyPreferences(automatic_prompts=False)) is True

    assert load_preferences() == SurveyPreferences(automatic_prompts=False)


def test_round_trip(prefs_file: Path) -> None:
    stored = SurveyPreferences(automatic_prompts=False, last_shown_at=SHOWN_AT, endpoint_override="https://example.invalid/fb")

    assert save_preferences(prefs_file, stored) is True
    assert load_preferences(prefs_file) == stored


def test_to_dict_serialises_last_shown_at_as_utc() -> None:
    offset_time = parse_iso("2026-09-01T10:30:00+02:00")

    data = SurveyPreferences(last_shown_at=offset_time).to_dict()

    assert data["last_shown_at"] == "2026-09-01T08:30:00+00:00"


def test_naive_timestamp_is_read_as_utc(prefs_file: Path) -> None:
    _write_json(prefs_file, {"schema_version": 1, "last_shown_at": "2026-09-01T08:30:00"})

    loaded = load_preferences(prefs_file)

    assert isinstance(loaded, SurveyPreferences)
    assert loaded.last_shown_at == SHOWN_AT


def test_offset_timestamp_is_normalised_to_utc(prefs_file: Path) -> None:
    _write_json(prefs_file, {"last_shown_at": "2026-09-01T10:30:00+02:00"})

    loaded = load_preferences(prefs_file)

    assert isinstance(loaded, SurveyPreferences)
    assert loaded.last_shown_at == SHOWN_AT
    assert loaded.last_shown_at.utcoffset() == timedelta(0)


def test_absent_keys_take_defaults(prefs_file: Path) -> None:
    _write_json(prefs_file, {})

    assert load_preferences(prefs_file) == SurveyPreferences()


@pytest.mark.requires_symlinks
def test_symlinked_file_is_unreadable(prefs_file: Path, tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    _write_json(real, {"automatic_prompts": True})
    prefs_file.parent.mkdir(parents=True, exist_ok=True)
    prefs_file.symlink_to(real)

    loaded = load_preferences(prefs_file)

    assert isinstance(loaded, Unreadable)
    assert "symlink" in loaded.reason


@pytest.mark.requires_symlinks
def test_symlinked_parent_is_unreadable(feedback_config_dir: Path, tmp_path: Path) -> None:
    real_dir = tmp_path / "real-dir"
    _write_json(real_dir / PREFERENCES_FILENAME, {"automatic_prompts": True})
    feedback_config_dir.parent.mkdir(parents=True, exist_ok=True)
    feedback_config_dir.symlink_to(real_dir, target_is_directory=True)

    loaded = load_preferences(feedback_config_dir / PREFERENCES_FILENAME)

    assert isinstance(loaded, Unreadable)
    assert "directory is a symlink" in loaded.reason


def test_oversize_file_is_unreadable(prefs_file: Path) -> None:
    _write_raw(prefs_file, json.dumps({"endpoint_override": "x" * MAX_PREFERENCES_BYTES}))

    loaded = load_preferences(prefs_file)

    assert loaded == Unreadable("file too large")


def test_oversize_read_is_caught_even_if_stat_under_reports(prefs_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_raw(prefs_file, b"{" + b" " * MAX_PREFERENCES_BYTES + b"}")
    monkeypatch.setattr(prefs_module, "_stat_problem", lambda _st: None)

    assert load_preferences(prefs_file) == Unreadable("file too large")


def test_directory_at_the_file_path_is_unreadable(prefs_file: Path) -> None:
    prefs_file.mkdir(parents=True)

    loaded = load_preferences(prefs_file)

    assert isinstance(loaded, Unreadable)


@POSIX_ONLY
def test_directory_is_reported_as_not_a_regular_file(prefs_file: Path) -> None:
    prefs_file.mkdir(parents=True)

    assert load_preferences(prefs_file) == Unreadable("not a regular file")


@pytest.mark.parametrize(
    "content",
    [b"{not json", b"[1, 2]", b'"text"', b"\xff\xfe\x00"],
    ids=["bad-json", "array", "string", "not-utf8"],
)
def test_invalid_content_is_unreadable(prefs_file: Path, content: bytes) -> None:
    _write_raw(prefs_file, content)

    loaded = load_preferences(prefs_file)

    assert isinstance(loaded, Unreadable)
    assert loaded.reason.startswith("invalid preferences file")


@pytest.mark.parametrize(
    "data",
    [
        {"schema_version": "1"},
        {"schema_version": True},
        {"schema_version": 0},
        {"automatic_prompts": "yes"},
        {"automatic_prompts": 1},
        {"last_shown_at": 5},
        {"last_shown_at": "not-a-date"},
        {"endpoint_override": 3},
    ],
    ids=lambda d: next(iter(d.items())).__repr__(),
)
def test_wrong_types_are_unreadable(prefs_file: Path, data: dict[str, object]) -> None:
    _write_json(prefs_file, data)

    assert isinstance(load_preferences(prefs_file), Unreadable)


def test_future_schema_version_is_unreadable(prefs_file: Path) -> None:
    _write_json(prefs_file, {"schema_version": 2, "automatic_prompts": True})

    loaded = load_preferences(prefs_file)

    assert isinstance(loaded, Unreadable)
    assert "unsupported schema_version 2" in loaded.reason


@POSIX_ONLY
def test_foreign_owner_is_unreadable(prefs_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_json(prefs_file, {"automatic_prompts": True})
    foreign_uid = prefs_file.stat().st_uid + 1
    monkeypatch.setattr(os, "geteuid", lambda: foreign_uid)

    assert load_preferences(prefs_file) == Unreadable("not owned by the current user")


@POSIX_ONLY
def test_wrong_mode_is_unreadable(prefs_file: Path) -> None:
    _write_raw(prefs_file, json.dumps({"automatic_prompts": True}), mode=0o644)

    assert load_preferences(prefs_file) == Unreadable("permissions are 644, expected 600")


def test_windows_skips_owner_and_mode_checks(prefs_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_raw(prefs_file, json.dumps({"automatic_prompts": False}), mode=0o644)
    monkeypatch.setattr(prefs_module, "is_windows", lambda: True)

    assert load_preferences(prefs_file) == SurveyPreferences(automatic_prompts=False)


@POSIX_ONLY
def test_unopenable_file_is_unreadable(prefs_file: Path) -> None:
    _write_raw(prefs_file, json.dumps({}), mode=0o000)
    try:
        loaded = load_preferences(prefs_file)
    finally:
        prefs_file.chmod(0o600)

    assert isinstance(loaded, Unreadable)
    assert loaded.reason.startswith("cannot open preferences file")


def test_read_error_after_open_is_unreadable(prefs_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_json(prefs_file, {})

    def _fail(_fd: int) -> bytes:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(prefs_module, "_read_bounded", _fail)

    loaded = load_preferences(prefs_file)

    assert isinstance(loaded, Unreadable)
    assert loaded.reason.startswith("cannot read preferences file")


# --- save --------------------------------------------------------------------


@POSIX_ONLY
def test_save_sets_owner_only_modes(prefs_file: Path) -> None:
    assert save_preferences(prefs_file, SurveyPreferences()) is True

    assert stat.S_IMODE(prefs_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(prefs_file.parent.stat().st_mode) == 0o700


@POSIX_ONLY
def test_save_does_not_narrow_an_existing_shared_config_dir(prefs_file: Path) -> None:
    prefs_file.parent.mkdir(parents=True)
    prefs_file.parent.chmod(0o755)

    assert save_preferences(prefs_file, SurveyPreferences()) is True
    assert stat.S_IMODE(prefs_file.parent.stat().st_mode) == 0o755


def test_save_writes_sorted_json(prefs_file: Path) -> None:
    assert save_preferences(prefs_file, SurveyPreferences(last_shown_at=SHOWN_AT)) is True

    data = json.loads(prefs_file.read_text(encoding="utf-8"))
    assert list(data) == sorted(data)
    assert data == {
        "automatic_prompts": True,
        "endpoint_override": None,
        "last_shown_at": "2026-09-01T08:30:00+00:00",
        "schema_version": 1,
    }


@pytest.mark.requires_symlinks
def test_save_refuses_a_symlinked_target(prefs_file: Path, tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text("{}", encoding="utf-8")
    prefs_file.parent.mkdir(parents=True, exist_ok=True)
    prefs_file.symlink_to(real)

    assert save_preferences(prefs_file, SurveyPreferences(automatic_prompts=False)) is False
    assert real.read_text(encoding="utf-8") == "{}"


@pytest.mark.requires_symlinks
def test_save_refuses_a_symlinked_parent(feedback_config_dir: Path, tmp_path: Path) -> None:
    real_dir = tmp_path / "real-dir"
    real_dir.mkdir()
    feedback_config_dir.parent.mkdir(parents=True, exist_ok=True)
    feedback_config_dir.symlink_to(real_dir, target_is_directory=True)

    assert save_preferences(feedback_config_dir / PREFERENCES_FILENAME, SurveyPreferences()) is False
    assert not (real_dir / PREFERENCES_FILENAME).exists()


def test_save_returns_false_on_filesystem_error(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("", encoding="utf-8")

    assert save_preferences(blocker / PREFERENCES_FILENAME, SurveyPreferences()) is False


# --- set_automatic_prompts ---------------------------------------------------


def test_set_automatic_prompts_toggles_and_preserves_other_fields(prefs_file: Path) -> None:
    assert save_preferences(prefs_file, SurveyPreferences(last_shown_at=SHOWN_AT, endpoint_override="https://example.invalid/fb")) is True

    assert set_automatic_prompts(False) is True
    assert load_preferences(prefs_file) == SurveyPreferences(
        automatic_prompts=False,
        last_shown_at=SHOWN_AT,
        endpoint_override="https://example.invalid/fb",
    )

    assert set_automatic_prompts(True, path=prefs_file) is True
    loaded = load_preferences(prefs_file)
    assert isinstance(loaded, SurveyPreferences)
    assert loaded.automatic_prompts is True


def test_set_automatic_prompts_creates_the_file(prefs_file: Path) -> None:
    assert set_automatic_prompts(False) is True

    assert load_preferences(prefs_file) == SurveyPreferences(automatic_prompts=False)


def test_set_automatic_prompts_repairs_an_unreadable_file(prefs_file: Path) -> None:
    _write_raw(prefs_file, b"{corrupt")
    assert isinstance(load_preferences(prefs_file), Unreadable)

    assert set_automatic_prompts(False) is True

    assert load_preferences(prefs_file) == SurveyPreferences(automatic_prompts=False)


def test_set_automatic_prompts_returns_false_when_the_lock_times_out(prefs_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _timeout(*_args: object, **_kwargs: object) -> None:
        raise LockAcquireTimeout(path=str(lock_path_for(prefs_file)))

    monkeypatch.setattr(prefs_module, "machine_file_lock", _timeout)

    assert set_automatic_prompts(False) is False
    assert not prefs_file.exists()


def test_set_automatic_prompts_returns_false_on_filesystem_error(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("", encoding="utf-8")

    assert set_automatic_prompts(True, path=blocker / PREFERENCES_FILENAME) is False
