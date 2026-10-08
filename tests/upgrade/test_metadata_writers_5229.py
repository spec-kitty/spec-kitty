"""#5229 -- every ``.kittify/metadata.yaml`` writer keeps the keys it does not own.

Unit level (``tmp_path`` only, no subprocess). Each case names the mutant it kills.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from specify_cli.migration import backfill_identity
from specify_cli.migration import schema_version as schema_version_module
from specify_cli.migration.schema_version import CURRENT_SCHEMA_CAPABILITIES, CURRENT_SCHEMA_VERSION
from specify_cli.upgrade.metadata import ProjectMetadata, VersionStamp
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_UUID = "01HZZZZZZZZZZZZZZZZZZZZZZZ"


def _write(kdir: Path, data: dict[str, object]) -> Path:
    kdir.mkdir(parents=True, exist_ok=True)
    path = kdir / "metadata.yaml"
    path.write_text(yaml.dump(data, sort_keys=False), encoding="utf-8")
    return path


def _read(kdir: Path) -> dict[str, object]:
    data = yaml.safe_load((kdir / "metadata.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _base_block(**extra: object) -> dict[str, object]:
    return {"version": "2.1.0", "initialized_at": "2026-01-01T00:00:00", **extra}


def _loaded(kdir: Path) -> ProjectMetadata:
    metadata = ProjectMetadata.load(kdir)
    assert metadata is not None
    return metadata


# --------------------------------------------------------------------------- save()


def test_save_keeps_keys_the_model_does_not_own(tmp_path: Path) -> None:
    """Kills: save() rebuilds the whole file from the fixed dict."""
    kdir = tmp_path / ".kittify"
    caps = {**CURRENT_SCHEMA_CAPABILITIES, "my_cap": False}
    _write(
        kdir,
        {
            "spec_kitty": _base_block(project_uuid=_UUID, custom_flag=True, schema_capabilities=caps),
            "operator_note": "keep-me",
            "environment": {"python_version": "3.12", "platform": "linux", "platform_version": "x", "editor": "vim"},
            "migrations": {"applied": [], "operator_extra": 1},
        },
    )
    metadata = _loaded(kdir)
    assert metadata.record_migration("some_migration", "success") is True

    assert metadata.save(kdir) is True

    data = _read(kdir)
    block = data["spec_kitty"]
    assert isinstance(block, dict)
    assert data["operator_note"] == "keep-me"
    assert block["project_uuid"] == _UUID
    assert block["custom_flag"] is True
    assert block["schema_capabilities"] == caps
    assert data["environment"]["editor"] == "vim"  # type: ignore[index]
    assert data["migrations"]["operator_extra"] == 1  # type: ignore[index]
    assert [m["id"] for m in data["migrations"]["applied"]] == ["some_migration"]  # type: ignore[index]


def test_save_with_stale_none_model_keeps_the_schema_version_on_disk(tmp_path: Path) -> None:
    """Kills: a merge that pops schema_version whenever the model says None (re-creates 'the upgrade erased the stamp')."""
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block()})
    metadata = _loaded(kdir)
    assert metadata.schema_version is None
    _write(kdir, {"spec_kitty": _base_block(schema_version=CURRENT_SCHEMA_VERSION)})
    metadata.version = "9.9.9"

    metadata.save(kdir)

    assert _read(kdir)["spec_kitty"]["schema_version"] == CURRENT_SCHEMA_VERSION  # type: ignore[index]


def test_save_with_none_model_and_no_key_on_disk_writes_no_schema_version(tmp_path: Path) -> None:
    """Over-correction guard (green on the base too). Kills: a merge that forges a schema stamp."""
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block(custom_flag=True)})
    metadata = _loaded(kdir)
    metadata.version = "9.9.9"

    metadata.save(kdir)

    assert "schema_version" not in _read(kdir)["spec_kitty"]  # type: ignore[operator]


def test_save_lets_the_model_win_for_the_fields_it_owns(tmp_path: Path) -> None:
    """Kills: a 'disk wins' merge; a removed migration record resurrecting from disk."""
    kdir = tmp_path / ".kittify"
    record = {"id": "old_one", "applied_at": "2026-01-01T00:00:00+00:00", "result": "success", "notes": None}
    _write(
        kdir,
        {
            "spec_kitty": _base_block(),
            "migrations": {"applied": [record, {**record, "id": "gone_from_model"}]},
        },
    )
    metadata = _loaded(kdir)
    metadata.applied_migrations = [m for m in metadata.applied_migrations if m.id == "old_one"]
    metadata.version = "new"
    metadata.platform = "plan9"

    metadata.save(kdir)

    data = _read(kdir)
    assert data["spec_kitty"]["version"] == "new"  # type: ignore[index]
    assert data["environment"]["platform"] == "plan9"  # type: ignore[index]
    assert [m["id"] for m in data["migrations"]["applied"]] == ["old_one"]  # type: ignore[index]


@pytest.mark.parametrize("garbage", ["just a string\n", "- a\n- list\n", ""])
def test_save_over_an_unusable_existing_file_writes_the_model(tmp_path: Path, garbage: str) -> None:
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block()})
    metadata = _loaded(kdir)
    (kdir / "metadata.yaml").write_text(garbage, encoding="utf-8")
    metadata.version = "9.9.9"

    assert metadata.save(kdir) is True

    assert _read(kdir)["spec_kitty"]["version"] == "9.9.9"  # type: ignore[index]


def test_save_refuses_to_replace_unparseable_yaml_and_leaves_it_untouched(tmp_path: Path) -> None:
    """Replacing a file that is not valid YAML would erase project_uuid and operator keys only the disk holds."""
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block()})
    metadata = _loaded(kdir)
    broken = "project_uuid: keep-me\nkey: [unclosed\n"
    (kdir / "metadata.yaml").write_text(broken, encoding="utf-8")

    with pytest.raises(ValueError, match="refusing to rewrite"):
        metadata.save(kdir)

    assert (kdir / "metadata.yaml").read_text(encoding="utf-8") == broken


@pytest.mark.parametrize("bad_block", ["a string", ["a", "list"]])
def test_save_replaces_a_non_mapping_spec_kitty_block(tmp_path: Path, bad_block: object) -> None:
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block(), "operator_note": "keep-me"})
    metadata = _loaded(kdir)
    _write(kdir, {"spec_kitty": bad_block, "operator_note": "keep-me", "migrations": "nope"})
    metadata.version = "9.9.9"

    metadata.save(kdir)

    data = _read(kdir)
    assert data["spec_kitty"]["version"] == "9.9.9"  # type: ignore[index]
    assert data["operator_note"] == "keep-me"
    assert data["migrations"] == {"applied": []}


def test_save_skips_a_timestamp_only_change(tmp_path: Path) -> None:
    """Over-correction guard (green on the base too). Kills: a merge that always rewrites (#1871 churn)."""
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block(custom_flag=True), "operator_note": "keep-me"})
    metadata = _loaded(kdir)
    metadata.version = "3.0.0"
    metadata.last_upgraded_at = schema_clock("2026-02-01T00:00:00+00:00")
    assert metadata.save(kdir) is True
    first = (kdir / "metadata.yaml").read_bytes()

    metadata.last_upgraded_at = schema_clock("2026-03-01T00:00:00+00:00")

    assert metadata.save(kdir) is False
    assert (kdir / "metadata.yaml").read_bytes() == first


def schema_clock(iso: str):  # noqa: ANN201 - tiny helper
    from kernel.clock import parse_iso

    return parse_iso(iso)


def test_save_is_byte_stable_across_two_identical_saves(tmp_path: Path) -> None:
    """Kills: a merge that reorders keys between saves (byte churn)."""
    kdir = tmp_path / ".kittify"
    _write(kdir, {"zeta": 1, "spec_kitty": _base_block(project_uuid=_UUID, aaa=2), "operator_note": "x"})
    metadata = _loaded(kdir)
    metadata.version = "3.0.0"
    metadata.save(kdir)
    first = (kdir / "metadata.yaml").read_bytes()

    metadata.applied_migrations = list(metadata.applied_migrations)
    assert metadata.save(kdir) is False
    assert (kdir / "metadata.yaml").read_bytes() == first
    assert list(_read(kdir))[:2] == ["zeta", "spec_kitty"]


# --------------------------------------------------------------------------- _stamp_schema_version


def _stamp(kdir: Path) -> None:
    MigrationRunner._stamp_schema_version(kdir, CURRENT_SCHEMA_VERSION)


def _caps(kdir: Path) -> object:
    return _read(kdir)["spec_kitty"]["schema_capabilities"]  # type: ignore[index]


def test_stamp_adds_the_canonical_map_when_absent(tmp_path: Path) -> None:
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block(), "operator_note": "keep-me"})

    _stamp(kdir)

    assert _caps(kdir) == CURRENT_SCHEMA_CAPABILITIES
    assert _read(kdir)["operator_note"] == "keep-me"
    assert _read(kdir)["spec_kitty"]["schema_version"] == CURRENT_SCHEMA_VERSION  # type: ignore[index]


def test_stamp_converts_a_legacy_list_keeping_unknown_names(tmp_path: Path) -> None:
    """Kills: a converter that filters to known names, or leaves the list."""
    kdir = tmp_path / ".kittify"
    legacy = [*CURRENT_SCHEMA_CAPABILITIES, "custom_cap"]
    _write(kdir, {"spec_kitty": _base_block(schema_capabilities=legacy)})

    _stamp(kdir)

    assert _caps(kdir) == {**CURRENT_SCHEMA_CAPABILITIES, "custom_cap": True}


def test_stamp_completes_a_partial_legacy_list_with_the_canonical_names(tmp_path: Path) -> None:
    kdir = tmp_path / ".kittify"
    only = next(iter(CURRENT_SCHEMA_CAPABILITIES))
    _write(kdir, {"spec_kitty": _base_block(schema_capabilities=[only])})

    _stamp(kdir)

    assert _caps(kdir) == CURRENT_SCHEMA_CAPABILITIES


def test_stamp_leaves_an_operator_owned_map_alone(tmp_path: Path) -> None:
    """Kills: a converter that overwrites or completes an existing map (init's rule: the operator owns it)."""
    kdir = tmp_path / ".kittify"
    first = next(iter(CURRENT_SCHEMA_CAPABILITIES))
    owned = {first: False, "my_cap": True}
    _write(kdir, {"spec_kitty": _base_block(schema_capabilities=owned)})

    _stamp(kdir)

    assert _caps(kdir) == owned


@pytest.mark.parametrize("malformed", ["on", 7])
def test_stamp_replaces_a_malformed_capability_value_with_the_canonical_map(tmp_path: Path, malformed: object) -> None:
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block(schema_capabilities=malformed)})

    _stamp(kdir)

    assert _caps(kdir) == CURRENT_SCHEMA_CAPABILITIES


def test_stamp_is_idempotent_and_does_not_touch_the_file(tmp_path: Path) -> None:
    """Kills: an always-write stamp."""
    kdir = tmp_path / ".kittify"
    path = _write(kdir, {"spec_kitty": _base_block()})
    _stamp(kdir)
    before = path.read_bytes()
    os.utime(path, ns=(1_000_000_000, 1_000_000_000))

    _stamp(kdir)

    assert path.read_bytes() == before
    assert path.stat().st_mtime_ns == 1_000_000_000


def test_stamp_derives_the_map_from_the_schema_module_at_call_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kills: a hard-coded or import-time copy of the capability set (the #840 drift)."""
    monkeypatch.setattr(schema_version_module, "CURRENT_SCHEMA_CAPABILITIES", {**CURRENT_SCHEMA_CAPABILITIES, "probe_cap": True})
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block()})

    _stamp(kdir)

    assert _caps(kdir)["probe_cap"] is True  # type: ignore[index]


def test_stamp_and_init_produce_the_same_capability_map(tmp_path: Path) -> None:
    """Kills: divergence between the upgrade stamp rule and ``init``'s."""
    from specify_cli.cli.commands.init import _stamp_schema_metadata

    for name in ("by_upgrade", "by_init"):
        _write(tmp_path / name / ".kittify", {"spec_kitty": _base_block()})

    _stamp(tmp_path / "by_upgrade" / ".kittify")
    _stamp_schema_metadata(tmp_path / "by_init" / ".kittify")

    assert _caps(tmp_path / "by_upgrade" / ".kittify") == _caps(tmp_path / "by_init" / ".kittify")


def test_failed_run_restores_the_capability_map_with_the_version_trio(tmp_path: Path) -> None:
    """Kills: a restore that keeps the map a failed run's stamp added (byte-identical-on-failure contract)."""
    kdir = tmp_path / ".kittify"
    path = _write(kdir, {"spec_kitty": _base_block(custom_flag=True)})
    before = path.read_bytes()
    stamp = VersionStamp.capture(kdir)
    _stamp(kdir)
    assert "schema_capabilities" in _read(kdir)["spec_kitty"]  # type: ignore[operator]

    assert stamp.restore(kdir) is True

    assert path.read_bytes() == before


def test_failed_run_after_recorded_migrations_still_drops_the_added_map(tmp_path: Path) -> None:
    kdir = tmp_path / ".kittify"
    _write(kdir, {"spec_kitty": _base_block(custom_flag=True), "operator_note": "keep-me"})
    stamp = VersionStamp.capture(kdir)
    metadata = _loaded(kdir)
    metadata.record_migration("ran_before_the_failure", "success")
    metadata.save(kdir)
    _stamp(kdir)

    stamp.restore(kdir)

    data = _read(kdir)
    assert "schema_capabilities" not in data["spec_kitty"]  # type: ignore[operator]
    assert "schema_version" not in data["spec_kitty"]  # type: ignore[operator]
    assert data["operator_note"] == "keep-me"
    assert [m["id"] for m in data["migrations"]["applied"]] == ["ran_before_the_failure"]  # type: ignore[index]


# --------------------------------------------------------------------------- backfill_project_uuid


def test_backfill_project_uuid_writes_through_the_atomic_seam(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kills: the plain ``open(..., 'w')`` write that truncates the file on a crash."""
    kdir = tmp_path / ".kittify"
    path = _write(kdir, {"spec_kitty": _base_block(custom_flag=True), "operator_note": "keep-me"})
    calls: list[Path] = []
    real = backfill_identity.atomic_write

    def spy(target: Path, content: str, **kwargs: object) -> None:
        calls.append(Path(target))
        real(target, content, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(backfill_identity, "atomic_write", spy)

    new_uuid = backfill_identity.backfill_project_uuid(tmp_path)

    assert calls == [path]
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["spec_kitty"]["project_uuid"] == new_uuid
    assert data["spec_kitty"]["custom_flag"] is True
    assert data["operator_note"] == "keep-me"
