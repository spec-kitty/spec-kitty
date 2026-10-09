"""The pack manifest hashes presets; packs without presets stay byte-identical (FR-019, T038/T040)."""

from __future__ import annotations

from pathlib import Path

import pytest

from charter.offering.pack_paths import built_in_root
from charter.offering.packs.builtin_manifest import build_builtin_manifest, builtin_manifest_is_fresh
from charter.offering.packs.pack_manifest import (
    PackManifest,
    dump_pack_manifest_bytes,
    finalize_pack_manifest,
    load_pack_manifest,
    write_pack_manifest,
)
from charter.offering.packs.presets import enumerate_presets
from kernel.charter_pack_paths import pack_presets_dir

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _with_preset(pack: Path, name: str, text: str) -> Path:
    path = pack_presets_dir(pack) / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _manifest(pack: Path) -> PackManifest:
    return finalize_pack_manifest(PackManifest(source_type="assemble", presets=enumerate_presets(pack) or None))


def test_enumerate_presets_sorted_and_relative(tmp_path: Path) -> None:
    _with_preset(tmp_path, "zeta", "name: zeta\n")
    _with_preset(tmp_path, "alpha", "name: alpha\n")
    entries = enumerate_presets(tmp_path)
    assert [(entry.name, entry.path) for entry in entries] == [("alpha", "presets/alpha.yaml"), ("zeta", "presets/zeta.yaml")]
    assert enumerate_presets(tmp_path / "empty") == []


def test_pack_without_presets_has_no_key_and_unchanged_hash(tmp_path: Path) -> None:
    without = _manifest(tmp_path)
    assert without.presets is None
    assert b"presets" not in dump_pack_manifest_bytes(without)
    assert without.manifest_hash == finalize_pack_manifest(PackManifest(source_type="assemble")).manifest_hash


def test_presets_enter_the_manifest_and_its_hash(tmp_path: Path) -> None:
    base = _manifest(tmp_path)
    _with_preset(tmp_path, "team", "name: team\ndescription: x\n")
    with_preset = _manifest(tmp_path)
    assert with_preset.presets is not None and [entry.name for entry in with_preset.presets] == ["team"]
    assert b"presets/team.yaml" in dump_pack_manifest_bytes(with_preset)
    assert with_preset.manifest_hash != base.manifest_hash


def test_changing_a_preset_byte_changes_its_hash(tmp_path: Path) -> None:
    _with_preset(tmp_path, "team", "name: team\ndescription: x\n")
    first = enumerate_presets(tmp_path)[0].content_hash
    _with_preset(tmp_path, "team", "name: team\ndescription: y\n")
    assert enumerate_presets(tmp_path)[0].content_hash != first


def test_line_endings_do_not_change_the_hash(tmp_path: Path) -> None:
    _with_preset(tmp_path, "team", "name: team\ndescription: x\n")
    lf = enumerate_presets(tmp_path)[0].content_hash
    _with_preset(tmp_path, "team", "name: team\r\ndescription: x\r\n")
    assert enumerate_presets(tmp_path)[0].content_hash == lf


def test_fetched_pack_manifest_hashes_presets(tmp_path: Path) -> None:
    _with_preset(tmp_path, "team", "name: team\ndescription: x\n")
    write_pack_manifest(tmp_path, pack_version="1.0.0", etag=None, source_url="https://example.com/pack.git", source_type="git")
    manifest = load_pack_manifest(tmp_path / "pack-manifest.yaml")
    assert manifest.presets is not None and manifest.presets[0].path == "presets/team.yaml"


def test_fetched_pack_without_presets_has_no_key(tmp_path: Path) -> None:
    write_pack_manifest(tmp_path, pack_version="1.0.0", etag=None, source_url="https://example.com/pack.git", source_type="git")
    assert "presets" not in (tmp_path / "pack-manifest.yaml").read_text(encoding="utf-8")


def test_builtin_manifest_lists_both_presets_and_is_fresh() -> None:
    manifest = build_builtin_manifest(built_in_root())
    assert manifest.presets is not None
    assert {entry.path for entry in manifest.presets} >= {"presets/default.yaml", "presets/minimal.yaml"}
    assert builtin_manifest_is_fresh(built_in_root())
