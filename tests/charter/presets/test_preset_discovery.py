"""Preset discovery and offering-pack enumeration (FR-004, T036/T040)."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.offering.pack_paths import built_in_root
from charter.offering.packs.presets import (
    OfferingPack,
    PresetNotFoundError,
    discover_presets,
    list_offering_packs,
    load_preset,
    preset_files,
)
from kernel.charter_pack_paths import pack_presets_dir, project_pack_root

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _preset(pack: Path, name: str) -> Path:
    path = pack_presets_dir(pack) / f"{name}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"name: {name}\ndescription: {name} preset\n", encoding="utf-8")
    return path


def test_pack_without_presets_dir_has_none(tmp_path: Path) -> None:
    assert preset_files(tmp_path) == ()
    assert discover_presets(tmp_path) == ()
    assert discover_presets(tmp_path / "not-fetched") == ()


def test_presets_sorted_by_name(tmp_path: Path) -> None:
    _preset(tmp_path, "zeta")
    _preset(tmp_path, "alpha")
    (pack_presets_dir(tmp_path) / "notes.txt").write_text("ignored", encoding="utf-8")
    assert [preset.name for preset in discover_presets(tmp_path)] == ["alpha", "zeta"]


def test_load_preset_by_name(tmp_path: Path) -> None:
    _preset(tmp_path, "alpha")
    assert load_preset(tmp_path, "alpha").name == "alpha"


@pytest.mark.parametrize("name", ["missing", "../alpha", "Alpha"])
def test_unknown_preset_lists_available_names(tmp_path: Path, name: str) -> None:
    _preset(tmp_path, "alpha")
    _preset(tmp_path, "beta")
    with pytest.raises(PresetNotFoundError) as excinfo:
        load_preset(tmp_path, name)
    assert excinfo.value.available == ("alpha", "beta")
    assert excinfo.value.name == name
    assert "alpha, beta" in str(excinfo.value)


def test_unknown_preset_in_pack_without_presets(tmp_path: Path) -> None:
    with pytest.raises(PresetNotFoundError, match="available: none"):
        load_preset(tmp_path, "default")


def test_builtin_pack_presets_discovered() -> None:
    assert {preset.name for preset in discover_presets(built_in_root())} >= {"default", "minimal"}


def test_list_offering_packs_orders_tiers(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    with_presets = repo / "packs" / "first"
    _preset(with_presets, "team")
    (repo / "packs" / "second").mkdir(parents=True)
    config = {
        "charter_packs": {
            "org": {
                "packs": [
                    {"name": "first", "local_path": "packs/first"},
                    {"name": "second", "local_path": "packs/second"},
                ]
            }
        }
    }
    (repo / ".kittify").mkdir(parents=True)
    with (repo / ".kittify" / "config.yaml").open("w", encoding="utf-8") as handle:
        YAML().dump(config, handle)

    packs = list_offering_packs(repo)

    assert [(pack.name, pack.tier) for pack in packs] == [
        ("built-in", "built-in"),
        ("first", "org"),
        ("second", "org"),
        ("project", "project"),
    ]
    assert packs[0].root == built_in_root()
    assert packs[1].root.resolve() == with_presets.resolve()
    assert packs[-1].root == project_pack_root(repo)
    assert [preset.name for preset in discover_presets(packs[1].root)] == ["team"]
    assert discover_presets(packs[2].root) == ()
    assert [pack.ships_presets for pack in packs] == [True, True, True, False]


def test_list_offering_packs_without_org_packs(tmp_path: Path) -> None:
    packs = list_offering_packs(tmp_path)
    assert [pack.tier for pack in packs] == ["built-in", "project"]
    assert isinstance(packs[0], OfferingPack)
