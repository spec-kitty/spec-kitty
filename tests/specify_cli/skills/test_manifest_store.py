"""Tests for specify_cli.skills.manifest_store.

Covers:
- Round-trip identity (save → load produces identical sorted manifest)
- Absent file returns empty manifest
- Schema version mismatch raises ManifestError("unsupported_schema_version")
- Schema validation failure raises ManifestError("schema_validation_failed")
- Duplicate path raises ManifestError("duplicate_path")
- Atomic save durability (pre-existing file unmodified on os.replace failure)
- Fingerprint stability
- Forward-compatibility with unknown top-level fields (load succeeds, save drops them)
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from specify_cli.skills.manifest_errors import ManifestError
from specify_cli.skills.manifest_store import (
    SCHEMA_VERSION,
    ManifestEntry,
    SkillsManifest,
    fingerprint,
    fingerprint_file,
    load,
    save,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_VALID_PATH_1 = ".agents/skills/spec-kitty.specify/SKILL.md"
_VALID_PATH_2 = ".agents/skills/spec-kitty.plan/SKILL.md"
_VALID_PATH_3 = ".agents/skills/spec-kitty.tasks/SKILL.md"
_VALID_HASH = "a" * 64  # 64 lowercase hex chars
_VALID_TS = "2026-01-01T00:00:00+00:00"
_VALID_VERSION = "3.2.0"


def _make_entry(
    path: str = _VALID_PATH_1,
    content_hash: str = _VALID_HASH,
    agents: tuple[str, ...] = ("codex",),
    installed_at: str = _VALID_TS,
    spec_kitty_version: str = _VALID_VERSION,
) -> ManifestEntry:
    return ManifestEntry(
        path=path,
        content_hash=content_hash,
        agents=agents,
        installed_at=installed_at,
        spec_kitty_version=spec_kitty_version,
    )


def _write_raw(repo_root: Path, data: dict[str, Any]) -> None:
    """Write arbitrary JSON to the manifest file without going through save()."""
    kittify = repo_root / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    (kittify / "command-skills-manifest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _read_raw(repo_root: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((repo_root / ".kittify" / "command-skills-manifest.json").read_text())
    return data


# ---------------------------------------------------------------------------
# T001 – ManifestEntry helpers
# ---------------------------------------------------------------------------


class TestManifestEntry:
    def test_with_agent_added(self) -> None:
        entry = _make_entry(agents=("codex",))
        updated = entry.with_agent_added("vibe")
        assert updated.agents == ("codex", "vibe")
        # Original is unchanged (frozen)
        assert entry.agents == ("codex",)

    def test_with_agent_added_deduplicates(self) -> None:
        entry = _make_entry(agents=("codex",))
        updated = entry.with_agent_added("codex")
        assert updated.agents == ("codex",)

    def test_with_agent_removed(self) -> None:
        entry = _make_entry(agents=("codex", "vibe"))
        updated = entry.with_agent_removed("codex")
        assert updated.agents == ("vibe",)

    def test_with_agent_removed_absent_is_noop(self) -> None:
        entry = _make_entry(agents=("vibe",))
        updated = entry.with_agent_removed("codex")
        assert updated.agents == ("vibe",)

    def test_frozen(self) -> None:
        entry = _make_entry()
        with pytest.raises(Exception):  # FrozenInstanceError
            entry.path = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# T002 – SkillsManifest helpers
# ---------------------------------------------------------------------------


class TestSkillsManifest:
    def test_find_existing(self) -> None:
        m = SkillsManifest()
        e = _make_entry()
        m.upsert(e)
        assert m.find(_VALID_PATH_1) is e

    def test_find_missing(self) -> None:
        m = SkillsManifest()
        assert m.find("nonexistent") is None

    def test_upsert_appends_new(self) -> None:
        m = SkillsManifest()
        m.upsert(_make_entry(_VALID_PATH_1))
        m.upsert(_make_entry(_VALID_PATH_2))
        assert len(m.entries) == 2

    def test_upsert_replaces_existing(self) -> None:
        m = SkillsManifest()
        e1 = _make_entry(_VALID_PATH_1, agents=("codex",))
        e2 = _make_entry(_VALID_PATH_1, agents=("vibe",))
        m.upsert(e1)
        m.upsert(e2)
        assert len(m.entries) == 1
        assert m.entries[0].agents == ("vibe",)

    def test_remove_path(self) -> None:
        m = SkillsManifest()
        m.upsert(_make_entry(_VALID_PATH_1))
        m.upsert(_make_entry(_VALID_PATH_2))
        m.remove_path(_VALID_PATH_1)
        assert m.find(_VALID_PATH_1) is None
        assert m.find(_VALID_PATH_2) is not None

    def test_remove_path_noop_if_absent(self) -> None:
        m = SkillsManifest()
        m.remove_path("ghost")  # should not raise


# ---------------------------------------------------------------------------
# T005a – Absent file returns empty manifest
# ---------------------------------------------------------------------------


def test_wp04_serialization_is_read_only_and_prepared_save_exact(tmp_path: Path) -> None:
    from specify_cli.skills import manifest_store
    from tests.upgrade.preview_support.snapshot import snapshot, assert_unchanged

    manifest = SkillsManifest(entries=[_make_entry(_VALID_PATH_1)])
    before = snapshot({"project": tmp_path})
    encoded = manifest_store.serialize(manifest)
    assert_unchanged(before, snapshot({"project": tmp_path}))
    (tmp_path / ".kittify").mkdir()
    manifest_store.save_prepared(tmp_path, encoded, mode=0o400)
    path = tmp_path / ".kittify/command-skills-manifest.json"
    assert path.read_bytes() == encoded
    assert path.stat().st_mode & 0o777 == 0o400


def test_wp04_prepared_save_preserves_existing_temp_occupant(tmp_path: Path) -> None:
    from specify_cli.skills import manifest_store

    (tmp_path / ".kittify").mkdir()
    temporary = tmp_path / ".kittify/command-skills-manifest.tmp"
    temporary.write_bytes(b"custom temporary occupant")
    with pytest.raises(FileExistsError):
        manifest_store.save_prepared(tmp_path, manifest_store.serialize(SkillsManifest()))
    assert temporary.read_bytes() == b"custom temporary occupant"


def test_absent_file_returns_empty(tmp_path: Path) -> None:
    """load() on a repo with no .kittify/ returns an empty manifest."""
    manifest = load(tmp_path)
    assert manifest.schema_version == SCHEMA_VERSION
    assert manifest.entries == []


def test_absent_kittify_dir_returns_empty(tmp_path: Path) -> None:
    # No .kittify directory at all
    assert not (tmp_path / ".kittify").exists()
    manifest = load(tmp_path)
    assert manifest.entries == []


# ---------------------------------------------------------------------------
# T005b – Round-trip identity
# ---------------------------------------------------------------------------


def test_round_trip_identity(tmp_path: Path) -> None:
    """Build a manifest with three entries in arbitrary order, save, reload; verify equality and sorting."""
    # Entries inserted in reverse-alphabetical path order
    e1 = _make_entry(_VALID_PATH_3, agents=("codex", "vibe"))
    e2 = _make_entry(_VALID_PATH_2, agents=("vibe",))
    e3 = _make_entry(_VALID_PATH_1, agents=("codex",))

    m = SkillsManifest()
    for e in (e1, e2, e3):
        m.upsert(e)

    save(tmp_path, m)
    loaded = load(tmp_path)

    # Entries must be sorted by path
    assert [e.path for e in loaded.entries] == sorted([_VALID_PATH_1, _VALID_PATH_2, _VALID_PATH_3])

    # Content equality (compare as sets to ignore order differences from in-memory state)
    original_by_path = {e.path: e for e in m.entries}
    loaded_by_path = {e.path: e for e in loaded.entries}
    assert original_by_path == loaded_by_path


def test_save_windows_fchmod_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulated Windows (no ``os.fchmod``): ``save()`` still writes and applies mode.

    Before the fix, ``_save_bytes`` raised ``AttributeError: module 'os' has
    no attribute 'fchmod'`` on a platform without the syscall.
    """
    import stat

    monkeypatch.delattr(os, "fchmod", raising=False)
    m = SkillsManifest()
    m.upsert(_make_entry(_VALID_PATH_1))

    save(tmp_path, m)

    manifest_path = tmp_path / ".kittify" / "command-skills-manifest.json"
    assert manifest_path.is_file()
    assert stat.S_IMODE(manifest_path.stat().st_mode) == 0o644
    loaded = load(tmp_path)
    assert {e.path for e in loaded.entries} == {_VALID_PATH_1}


def test_round_trip_empty(tmp_path: Path) -> None:
    """An empty manifest round-trips cleanly."""
    m = SkillsManifest()
    save(tmp_path, m)
    loaded = load(tmp_path)
    assert loaded.entries == []
    assert loaded.schema_version == SCHEMA_VERSION


def test_on_disk_format(tmp_path: Path) -> None:
    """Verify the on-disk file has 2-space indent, sorted keys, and trailing newline."""
    m = SkillsManifest()
    m.upsert(_make_entry())
    save(tmp_path, m)

    raw = (tmp_path / ".kittify" / "command-skills-manifest.json").read_text(encoding="utf-8")
    assert raw.endswith("\n")

    # Round-trip the JSON and re-dump with expected settings; they must match
    # (modulo the trailing newline we add).
    data = json.loads(raw)
    expected = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert raw == expected


# ---------------------------------------------------------------------------
# T005c – Schema version mismatch
# ---------------------------------------------------------------------------


def test_schema_version_mismatch(tmp_path: Path) -> None:
    """schema_version != 1 raises ManifestError("unsupported_schema_version")."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 2,
            "entries": [],
        },
    )
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "unsupported_schema_version"
    assert exc_info.value.context["found"] == 2


def test_schema_version_zero(tmp_path: Path) -> None:
    _write_raw(tmp_path, {"schema_version": 0, "entries": []})
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "unsupported_schema_version"


def test_schema_version_string(tmp_path: Path) -> None:
    """A string schema_version fails with unsupported_schema_version (not schema_validation_failed)."""
    _write_raw(tmp_path, {"schema_version": "1", "entries": []})
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    # The version check fires before jsonschema because the != 1 comparison catches it first
    assert exc_info.value.code == "unsupported_schema_version"


# ---------------------------------------------------------------------------
# T005d – Schema validation failure
# ---------------------------------------------------------------------------


def test_schema_validation_missing_content_hash(tmp_path: Path) -> None:
    """An entry missing content_hash fails with schema_validation_failed."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": _VALID_PATH_1,
                    # content_hash intentionally missing
                    "agents": ["codex"],
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                }
            ],
        },
    )
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "schema_validation_failed"
    errors = exc_info.value.context["errors"]
    assert isinstance(errors, list)
    assert len(errors) >= 1
    # At least one error should mention content_hash
    assert any("content_hash" in msg for msg in errors)


def test_schema_validation_invalid_agent_enum(tmp_path: Path) -> None:
    """An unsupported agent key fails validation."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": _VALID_PATH_1,
                    "content_hash": _VALID_HASH,
                    "agents": ["claude"],  # not in enum
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                }
            ],
        },
    )
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "schema_validation_failed"


def test_schema_validation_bad_content_hash_pattern(tmp_path: Path) -> None:
    """content_hash not matching ^[0-9a-f]{64}$ fails validation."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": _VALID_PATH_1,
                    "content_hash": "UPPERCASE" + "a" * 55,  # uppercase not allowed
                    "agents": ["codex"],
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                }
            ],
        },
    )
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "schema_validation_failed"


def test_schema_validation_bad_path_pattern(tmp_path: Path) -> None:
    """path not matching the required pattern fails validation."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": "wrong/path/SKILL.md",  # doesn't match pattern
                    "content_hash": _VALID_HASH,
                    "agents": ["codex"],
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                }
            ],
        },
    )
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "schema_validation_failed"


def test_schema_validation_empty_agents(tmp_path: Path) -> None:
    """agents: [] (minItems=1) fails validation."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": _VALID_PATH_1,
                    "content_hash": _VALID_HASH,
                    "agents": [],  # minItems: 1
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                }
            ],
        },
    )
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "schema_validation_failed"


def test_schema_validation_additional_properties_in_entry(tmp_path: Path) -> None:
    """An extra field in an entry is rejected (additionalProperties: false)."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": _VALID_PATH_1,
                    "content_hash": _VALID_HASH,
                    "agents": ["codex"],
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                    "extra_field": "should be rejected",
                }
            ],
        },
    )
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "schema_validation_failed"


# ---------------------------------------------------------------------------
# T005e – Duplicate path
# ---------------------------------------------------------------------------


def test_duplicate_path(tmp_path: Path) -> None:
    """Two entries with the same path raise ManifestError("duplicate_path")."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": _VALID_PATH_1,
                    "content_hash": _VALID_HASH,
                    "agents": ["codex"],
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                },
                {
                    "path": _VALID_PATH_1,  # duplicate
                    "content_hash": _VALID_HASH,
                    "agents": ["vibe"],
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                },
            ],
        },
    )
    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "duplicate_path"
    assert exc_info.value.context["path"] == _VALID_PATH_1


# ---------------------------------------------------------------------------
# T005f – Corrupt JSON
# ---------------------------------------------------------------------------


def test_corrupt_json(tmp_path: Path) -> None:
    """A file with invalid JSON raises ManifestError("corrupt_json")."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "command-skills-manifest.json").write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(ManifestError) as exc_info:
        load(tmp_path)
    assert exc_info.value.code == "corrupt_json"
    assert "path" in exc_info.value.context
    assert "detail" in exc_info.value.context


# ---------------------------------------------------------------------------
# T005g – Atomic save durability
# ---------------------------------------------------------------------------


def test_atomic_save_failure_leaves_original_intact(tmp_path: Path) -> None:
    """If os.replace raises, the pre-existing manifest file is unchanged."""
    # Write a known-good manifest first
    m_original = SkillsManifest()
    m_original.upsert(_make_entry(_VALID_PATH_1, agents=("codex",)))
    save(tmp_path, m_original)

    original_content = (tmp_path / ".kittify" / "command-skills-manifest.json").read_text()

    # Now attempt a second save that will fail at os.replace
    m_new = SkillsManifest()
    m_new.upsert(_make_entry(_VALID_PATH_2, agents=("vibe",)))

    with patch("os.replace", side_effect=OSError("simulated failure")):
        with pytest.raises(OSError, match="simulated failure"):
            save(tmp_path, m_new)

    # The original file must be unmodified
    assert (tmp_path / ".kittify" / "command-skills-manifest.json").read_text() == original_content

    # The .tmp file should have been cleaned up
    tmp_file = tmp_path / ".kittify" / "command-skills-manifest.tmp"
    assert not tmp_file.exists()


def test_atomic_save_creates_kittify_dir(tmp_path: Path) -> None:
    """save() creates .kittify/ if it does not exist."""
    assert not (tmp_path / ".kittify").exists()
    m = SkillsManifest()
    save(tmp_path, m)
    assert (tmp_path / ".kittify" / "command-skills-manifest.json").exists()


# ---------------------------------------------------------------------------
# T005h – Fingerprint stability
# ---------------------------------------------------------------------------


def test_fingerprint_known_value() -> None:
    """fingerprint(b"hello") equals the known SHA-256 digest."""
    expected = hashlib.sha256(b"hello").hexdigest()  # noqa: TID251 — skills manifest fingerprint() is defined as raw SHA-256; the test verifies that definition, not charter freshness
    assert fingerprint(b"hello") == expected
    assert len(fingerprint(b"hello")) == 64
    first_digest = fingerprint(b"hello")
    second_digest = fingerprint(b"hello")
    assert first_digest == second_digest  # idempotent


def test_fingerprint_empty_bytes() -> None:
    expected = hashlib.sha256(b"").hexdigest()  # noqa: TID251 — skills manifest fingerprint() is defined as raw SHA-256; the test verifies that definition, not charter freshness
    assert fingerprint(b"") == expected


def test_fingerprint_file(tmp_path: Path) -> None:
    content = b"spec-kitty fingerprint test"
    f = tmp_path / "test.bin"
    f.write_bytes(content)
    assert fingerprint_file(f) == fingerprint(content)


def test_fingerprint_returns_lowercase_hex() -> None:
    digest = fingerprint(b"test")
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


# ---------------------------------------------------------------------------
# T005i – Forward compatibility: unknown top-level fields
# ---------------------------------------------------------------------------


def test_forward_compat_unknown_top_level_field(tmp_path: Path) -> None:
    """A JSON file with an unknown top-level field loads successfully."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": _VALID_PATH_1,
                    "content_hash": _VALID_HASH,
                    "agents": ["codex"],
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                }
            ],
            "comment": "hi",  # unknown field
        },
    )
    # load must succeed (with a warning)
    with pytest.warns(UserWarning, match="comment"):
        manifest = load(tmp_path)

    assert len(manifest.entries) == 1
    assert manifest.entries[0].path == _VALID_PATH_1


def test_forward_compat_save_drops_unknown_field(tmp_path: Path) -> None:
    """After loading a manifest with unknown fields, save() drops them."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [],
            "comment": "hi",
            "future_field": {"nested": True},
        },
    )
    with pytest.warns(UserWarning, match="unknown top-level fields"):
        manifest = load(tmp_path)

    save(tmp_path, manifest)

    on_disk = _read_raw(tmp_path)
    assert "comment" not in on_disk
    assert "future_field" not in on_disk
    assert set(on_disk.keys()) == {"schema_version", "entries"}


# ---------------------------------------------------------------------------
# T005j – agents coercion (tuple ↔ list boundary)
# ---------------------------------------------------------------------------


def test_agents_sorted_on_load(tmp_path: Path) -> None:
    """Agents stored in unsorted order in JSON are sorted on load."""
    _write_raw(
        tmp_path,
        {
            "schema_version": 1,
            "entries": [
                {
                    "path": _VALID_PATH_1,
                    "content_hash": _VALID_HASH,
                    "agents": ["vibe", "codex"],  # reversed order
                    "installed_at": _VALID_TS,
                    "spec_kitty_version": _VALID_VERSION,
                }
            ],
        },
    )
    manifest = load(tmp_path)
    assert manifest.entries[0].agents == ("codex", "vibe")


def test_agents_sorted_on_save(tmp_path: Path) -> None:
    """Agents are sorted in the on-disk JSON regardless of tuple order."""
    # Construct an entry with agents in "wrong" order by using object directly
    e = ManifestEntry(
        path=_VALID_PATH_1,
        content_hash=_VALID_HASH,
        agents=("vibe", "codex"),  # unsorted
        installed_at=_VALID_TS,
        spec_kitty_version=_VALID_VERSION,
    )
    m = SkillsManifest()
    m.upsert(e)
    save(tmp_path, m)

    on_disk = _read_raw(tmp_path)
    assert on_disk["entries"][0]["agents"] == ["codex", "vibe"]
