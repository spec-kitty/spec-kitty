"""Unit tests for ``tool_surface.profiles.manifest``."""

from __future__ import annotations

import json
from pathlib import Path

from specify_cli.skills.manifest_store import fingerprint
from specify_cli.tool_surface.model import NativeAgentProfile
from specify_cli.tool_surface.profiles.manifest import (
    MANIFEST_FILENAME,
    PROJECTION_VERSION,
    ProfileManifest,
    hash_content,
    hash_file,
    manifest_path_for,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _entry(slug: str, file_hash: str | None = "deadbeef") -> NativeAgentProfile:
    return NativeAgentProfile(
        profile_urn=f"agent_profile:{slug}",
        source_layer="built-in",
        tool_key="claude",
        output_path=Path(f"/project/.claude/agents/{slug}.md"),
        format="claude-agent",
        file_hash=file_hash,
    )


def _provenance_entry(
    slug: str,
    *,
    file_hash: str | None = "deadbeef",
    source_path: str | None = "src/charter/offering/agent_profiles/built-in/x.agent.yaml",
    source_hash: str | None = "sha256:source",
) -> NativeAgentProfile:
    return NativeAgentProfile(
        profile_urn=f"agent_profile:{slug}",
        source_layer="built-in",
        tool_key="claude",
        output_path=Path(f"/project/.claude/agents/{slug}.md"),
        format="claude-agent",
        file_hash=file_hash,
        source_path=source_path,
        source_hash=source_hash,
        projection_version=PROJECTION_VERSION,
    )


def test_manifest_filename_is_agent_profiles_manifest() -> None:
    assert MANIFEST_FILENAME == "agent_profiles_manifest.json"


def test_manifest_path_is_under_kittify(tmp_path: Path) -> None:
    path = manifest_path_for(tmp_path)
    assert path == tmp_path / ".kittify" / "agent_profiles_manifest.json"


def test_hash_content_matches_canonical_fingerprint() -> None:
    # The manifest must use the project's canonical SHA-256 routine, not a
    # reimplementation, so its digests interoperate with the installer/renderer.
    assert hash_content("hello") == fingerprint(b"hello")


def test_hash_file_matches_canonical_fingerprint(tmp_path: Path) -> None:
    f = tmp_path / "x.md"
    f.write_text("hello", encoding="utf-8")
    assert hash_file(f) == fingerprint(b"hello")


def test_record_and_get_hash(tmp_path: Path) -> None:
    manifest = ProfileManifest(manifest_path_for(tmp_path))
    entry = _entry("architect-alphonso", file_hash="abc123")
    manifest.record(entry)
    assert manifest.get_hash(entry.output_path) == "abc123"
    assert manifest.get_hash(Path("/nope.md")) is None


def test_remove_drops_entry(tmp_path: Path) -> None:
    manifest = ProfileManifest(manifest_path_for(tmp_path))
    entry = _entry("planner-priti")
    manifest.record(entry)
    manifest.remove(entry.output_path)
    assert manifest.get_hash(entry.output_path) is None
    # Removing an absent path is a no-op.
    manifest.remove(Path("/missing.md"))


def test_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = ProfileManifest.load(tmp_path)
    manifest.record(_entry("architect-alphonso", file_hash="h1"))
    manifest.record(_entry("planner-priti", file_hash=None))
    manifest.save()

    reloaded = ProfileManifest.load(tmp_path)
    entries = reloaded.all_entries()
    assert [e.profile_urn for e in entries] == [
        "agent_profile:architect-alphonso",
        "agent_profile:planner-priti",
    ]
    assert reloaded.get_hash(Path("/project/.claude/agents/architect-alphonso.md")) == "h1"
    assert reloaded.get_hash(Path("/project/.claude/agents/planner-priti.md")) is None
    assert entries[0].format == "claude-agent"
    assert entries[0].tool_key == "claude"


def test_load_absent_manifest_is_empty(tmp_path: Path) -> None:
    manifest = ProfileManifest.load(tmp_path)
    assert manifest.all_entries() == []


# --- #1940 provenance (source_path / source_hash / projection_version) --------


def test_provenance_roundtrip_preserves_all_eight_fields(tmp_path: Path) -> None:
    """load(save(8-field entry)) == entry (lossless 8-field round-trip)."""
    manifest = ProfileManifest.load(tmp_path)
    entry = _provenance_entry("architect-alphonso")
    manifest.record(entry)
    manifest.save()

    reloaded = ProfileManifest.load(tmp_path).all_entries()
    assert reloaded == [entry]
    got = reloaded[0]
    assert got.source_path == entry.source_path
    assert got.source_hash == entry.source_hash
    assert got.projection_version == PROJECTION_VERSION


def _write_legacy_six_field_manifest(tmp_path: Path) -> Path:
    """Write a real pre-#1940 6-field manifest (no provenance keys)."""
    path: Path = manifest_path_for(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "entries": [
            {
                "profile_urn": "agent_profile:legacy-larry",
                "source_layer": "built-in",
                "tool_key": "claude",
                "output_path": "/project/.claude/agents/legacy-larry.md",
                "format": "claude-agent",
                "file_hash": "sha256:legacy",
            }
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_load_legacy_six_field_entry_populates_with_none_provenance(
    tmp_path: Path,
) -> None:
    """A real 6-field legacy manifest loads to a populated entry, not a crash.

    The 3 new provenance keys are absent-tolerant on read: ``source_path`` and
    ``source_hash`` default to ``None`` and ``projection_version`` to ``None``;
    the legacy 6 fields are preserved verbatim (no swallowed/None entry).
    """
    _write_legacy_six_field_manifest(tmp_path)

    entries = ProfileManifest.load(tmp_path).all_entries()

    assert len(entries) == 1, "legacy entry must load, not be dropped"
    entry = entries[0]
    assert entry.profile_urn == "agent_profile:legacy-larry"
    assert entry.file_hash == "sha256:legacy"
    assert entry.source_path is None
    assert entry.source_hash is None
    assert entry.projection_version is None


def test_source_hash_change_is_independent_of_file_hash(tmp_path: Path) -> None:
    """Source YAML changed but rendered output unchanged -> only source drifts."""
    manifest = ProfileManifest.load(tmp_path)
    manifest.record(
        _provenance_entry(
            "drift-dan", file_hash="sha256:out", source_hash="sha256:src-v1"
        )
    )
    manifest.save()

    recorded = ProfileManifest.load(tmp_path).all_entries()[0]
    # Output unchanged...
    assert recorded.file_hash == "sha256:out"
    # ...but the source moved: detectable purely via source_hash.
    assert recorded.source_hash == "sha256:src-v1"
    assert recorded.source_hash != recorded.file_hash


def test_file_hash_change_is_independent_of_source_hash(tmp_path: Path) -> None:
    """Rendered output edited but source unchanged -> only file drifts."""
    manifest = ProfileManifest.load(tmp_path)
    manifest.record(
        _provenance_entry(
            "drift-dora", file_hash="sha256:out-edited", source_hash="sha256:src"
        )
    )
    manifest.save()

    recorded = ProfileManifest.load(tmp_path).all_entries()[0]
    assert recorded.source_hash == "sha256:src"
    assert recorded.file_hash == "sha256:out-edited"
    assert recorded.file_hash != recorded.source_hash


# --- #2589 output_path repo-relative storage -----------------------------


def test_in_tree_output_path_serializes_relative(tmp_path: Path) -> None:
    """An in-tree entry is written to disk as a repo-relative POSIX string."""
    output_path = tmp_path / ".claude" / "agents" / "architect-alphonso.md"
    manifest = ProfileManifest.load(tmp_path)
    manifest.record(
        NativeAgentProfile(
            profile_urn="agent_profile:architect-alphonso",
            source_layer="built-in",
            tool_key="claude",
            output_path=output_path,
            format="claude-agent",
            file_hash="h1",
        )
    )
    manifest.save()

    raw = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    stored = raw["entries"][0]["output_path"]
    assert stored == ".claude/agents/architect-alphonso.md"
    assert not stored.startswith("/")
    assert str(tmp_path) not in stored


def test_legacy_absolute_manifest_under_different_project_root_still_resolves(
    tmp_path: Path,
) -> None:
    """A pre-#2589 manifest with an absolute output_path still resolves.

    The manifest is loaded under a *different* project_root than the one the
    absolute path was originally written under -- the legacy value must be
    passed through unchanged (no migration) and continue to ``.exists()``.
    """
    real_target_dir = tmp_path / "elsewhere"
    real_target_dir.mkdir()
    real_target = real_target_dir / "legacy-larry.md"
    real_target.write_text("legacy content", encoding="utf-8")

    different_project_root = tmp_path / "different-project"
    manifest_path = manifest_path_for(different_project_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "entries": [
            {
                "profile_urn": "agent_profile:legacy-larry",
                "source_layer": "built-in",
                "tool_key": "claude",
                "output_path": str(real_target),
                "format": "claude-agent",
                "file_hash": "sha256:legacy",
            }
        ],
    }
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    entries = ProfileManifest.load(different_project_root).all_entries()

    assert len(entries) == 1
    assert entries[0].output_path == real_target
    assert entries[0].output_path.exists()


def test_get_hash_finds_entry_by_absolute_path_after_relative_roundtrip(
    tmp_path: Path,
) -> None:
    """The manifest KEY stays absolute even though disk storage is relative.

    This pins the #2589 fix boundary: relativizing the *serialized* copy must
    not leak into the in-memory key, or get_hash/prune break.
    """
    output_path = tmp_path / ".claude" / "agents" / "planner-priti.md"
    manifest = ProfileManifest.load(tmp_path)
    manifest.record(
        NativeAgentProfile(
            profile_urn="agent_profile:planner-priti",
            source_layer="built-in",
            tool_key="claude",
            output_path=output_path,
            format="claude-agent",
            file_hash="abc123",
        )
    )
    manifest.save()

    reloaded = ProfileManifest.load(tmp_path)
    assert reloaded.get_hash(output_path) == "abc123"
    assert reloaded.get_hash(output_path.resolve()) == "abc123"


def test_out_of_tree_output_path_serializes_absolute_and_roundtrips(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """A genuinely out-of-tree output_path falls back to absolute storage.

    Mirrors the existing ``source_path`` fallback (the ``ValueError`` branch
    in ``relativize_under_root``) -- otherwise this branch is untested.
    """
    project_root = tmp_path_factory.mktemp("project")
    outside_root = tmp_path_factory.mktemp("outside")
    output_path = outside_root / "agents" / "out-of-tree-otto.md"

    manifest = ProfileManifest.load(project_root)
    manifest.record(
        NativeAgentProfile(
            profile_urn="agent_profile:out-of-tree-otto",
            source_layer="built-in",
            tool_key="claude",
            output_path=output_path,
            format="claude-agent",
            file_hash="deadbeef",
        )
    )
    manifest.save()

    raw = json.loads(manifest.manifest_path.read_text(encoding="utf-8"))
    stored = raw["entries"][0]["output_path"]
    assert stored.startswith("/")
    assert stored == str(output_path.resolve())

    reloaded = ProfileManifest.load(project_root)
    assert reloaded.get_hash(output_path) == "deadbeef"
    assert reloaded.all_entries()[0].output_path == output_path.resolve()
