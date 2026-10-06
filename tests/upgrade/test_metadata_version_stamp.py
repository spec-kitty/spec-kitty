"""``VersionStamp``: the one restore authority for ``.kittify/metadata.yaml``'s version trio (#3334 / #4275)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.upgrade.metadata import ProjectMetadata, VersionStamp

_BASE = (
    "spec_kitty:\n  version: '1.0.0'\n  initialized_at: '2026-01-01T00:00:00+00:00'\n"
    "  last_upgraded_at: '2026-01-02T00:00:00+00:00'\n  schema_version: 3\n"
    "environment:\n  python_version: '3.12'\nmigrations:\n  applied: []\n"
)


def _kittify(tmp_path: Path, text: str | None) -> Path:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    if text is not None:
        (kittify / "metadata.yaml").write_text(text, encoding="utf-8")
    return kittify


def test_stamp_restore_is_a_noop_when_nothing_changed(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    stamp = VersionStamp.capture(kittify)
    assert stamp.restore(kittify) is False
    assert (kittify / "metadata.yaml").read_text(encoding="utf-8") == _BASE


def test_stamp_restore_returns_original_bytes_when_only_the_trio_moved(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    stamp = VersionStamp.capture(kittify)
    (kittify / "metadata.yaml").write_text(
        _BASE.replace("1.0.0", "2.0.0").replace("2026-01-02", "2026-10-06").replace("schema_version: 3", "schema_version: 4"),
        encoding="utf-8",
    )
    assert stamp.restore(kittify) is True
    assert (kittify / "metadata.yaml").read_text(encoding="utf-8") == _BASE


def test_stamp_restore_keeps_recorded_migrations_and_patches_only_the_trio(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    stamp = VersionStamp.capture(kittify)
    moved = _BASE.replace("1.0.0", "2.0.0").replace(
        "applied: []", "applied:\n  - id: m1\n    applied_at: '2026-10-06T00:00:00+00:00'\n    result: success\n    notes: null"
    )
    (kittify / "metadata.yaml").write_text(moved, encoding="utf-8")

    assert stamp.restore(kittify) is True

    loaded = ProjectMetadata.load(kittify)
    assert loaded is not None
    assert loaded.version == "1.0.0"
    assert loaded.schema_version == 3
    assert [m.id for m in loaded.applied_migrations] == ["m1"]


def test_stamp_restore_pops_a_trio_key_that_was_absent_before(tmp_path: Path) -> None:
    legacy = _BASE.replace("  schema_version: 3\n", "")
    kittify = _kittify(tmp_path, legacy)
    stamp = VersionStamp.capture(kittify)
    (kittify / "metadata.yaml").write_text(
        _BASE.replace("applied: []", "applied:\n  - id: m1\n    applied_at: '2026-10-06T00:00:00+00:00'\n    result: success"), encoding="utf-8"
    )

    assert stamp.restore(kittify) is True

    loaded = ProjectMetadata.load(kittify)
    assert loaded is not None
    assert loaded.schema_version is None


def test_stamp_restore_reports_false_when_the_patched_trio_already_matches(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    stamp = VersionStamp.capture(kittify)
    migrated = _BASE.replace("applied: []", "applied:\n  - id: m1\n    applied_at: '2026-10-06T00:00:00+00:00'\n    result: success")
    (kittify / "metadata.yaml").write_text(migrated, encoding="utf-8")
    assert stamp.restore(kittify) is False
    assert (kittify / "metadata.yaml").read_text(encoding="utf-8") == migrated


def test_stamp_restore_recreates_a_missing_spec_kitty_block(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    stamp = VersionStamp.capture(kittify)
    (kittify / "metadata.yaml").write_text("migrations:\n  applied:\n    - id: m1\n", encoding="utf-8")
    assert stamp.restore(kittify) is True
    loaded = ProjectMetadata.load(kittify)
    assert loaded is not None
    assert loaded.version == "1.0.0"


def test_stamp_of_an_absent_file_restores_nothing(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, None)
    stamp = VersionStamp.capture(kittify)
    assert stamp.raw is None
    assert stamp.restore(kittify) is False
    (kittify / "metadata.yaml").write_text(_BASE, encoding="utf-8")
    assert stamp.restore(kittify) is False
    assert (kittify / "metadata.yaml").read_text(encoding="utf-8") == _BASE


@pytest.mark.parametrize("captured", ["- just\n- a list\n", ": : not yaml ["])
def test_stamp_restore_leaves_an_unparseable_capture_alone(tmp_path: Path, captured: str) -> None:
    kittify = _kittify(tmp_path, captured)
    stamp = VersionStamp.capture(kittify)
    (kittify / "metadata.yaml").write_text(_BASE, encoding="utf-8")
    assert stamp.restore(kittify) is False
    assert (kittify / "metadata.yaml").read_text(encoding="utf-8") == _BASE


def test_stamp_restore_leaves_an_unparseable_current_file_alone(tmp_path: Path) -> None:
    kittify = _kittify(tmp_path, _BASE)
    stamp = VersionStamp.capture(kittify)
    (kittify / "metadata.yaml").write_bytes(b"\xff\xfe not utf8")
    assert stamp.restore(kittify) is False


def test_stamp_capture_of_an_unreadable_path_is_absent(tmp_path: Path) -> None:
    kittify = tmp_path / ".kittify"
    (kittify).mkdir()
    (kittify / "metadata.yaml").mkdir()  # a directory: read_bytes raises OSError
    assert VersionStamp.capture(kittify).raw is None
