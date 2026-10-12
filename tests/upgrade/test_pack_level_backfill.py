"""ATDD coverage for the project-pack ``pack_level`` backfill migration (FR-010, WP03).

The migration writes ``pack.yaml`` (``pack_level: project`` + a minted ULID
``pack_id``) for an existing consumer PROJECT pack that lacks one, so a legacy
install becomes compliant with the ``pack_level`` descriptor schema (WP01).

Contract (``contracts/pack-descriptor.contract.md`` — Migration contract):

* config-aware discovery of the project pack (``.kittify/charter-packs/``);
* never ``mkdir`` a missing directory;
* skip ``packs/built-in`` and ``packs/internal``;
* never clobber an authored ``pack.yaml`` — add ``pack_level`` only if absent,
  never overwrite a differing ``pack_id``;
* idempotent on re-run.
"""

from __future__ import annotations

from pathlib import Path

from ruamel.yaml import YAML

from charter.offering.packs.pack_descriptor import load_pack_descriptor
from specify_cli.upgrade.migrations.m_4_0_0rc7_pack_level_backfill import (
    PackLevelBackfillMigration,
)

_YAML = YAML(typ="safe")


def _read_yaml(path: Path) -> dict:
    return _YAML.load(path.read_text(encoding="utf-8"))


def _make_project_pack(repo_root: Path) -> Path:
    """Create a project pack dir (``.kittify/charter-packs/``) without ``pack.yaml``."""
    pack_root = repo_root / ".kittify" / "charter-packs"
    (pack_root / "directive").mkdir(parents=True)
    (pack_root / "graph.yaml").write_text("nodes: []\n", encoding="utf-8")
    return pack_root


# ---------------------------------------------------------------------------
# T013 — ATDD anchor
# ---------------------------------------------------------------------------


def test_backfills_project_pack_missing_pack_yaml(tmp_path: Path) -> None:
    """A project pack lacking ``pack.yaml`` gains one (``pack_level: project`` + ULID)."""
    pack_root = _make_project_pack(tmp_path)

    result = PackLevelBackfillMigration().apply(tmp_path)

    assert result.success is True
    descriptor_path = pack_root / "pack.yaml"
    assert descriptor_path.is_file()
    # Loads cleanly under the WP01 schema (so a differing field set can't sneak in).
    descriptor = load_pack_descriptor(descriptor_path)
    assert descriptor.pack_level == "project"
    assert len(descriptor.pack_id) == 26
    assert descriptor.pack_version is None  # project packs need no version (FR-005)


def test_minted_pack_id_is_a_valid_ulid(tmp_path: Path) -> None:
    """The minted ``pack_id`` parses as a 26-char ULID."""
    from ulid import ULID

    pack_root = _make_project_pack(tmp_path)

    PackLevelBackfillMigration().apply(tmp_path)

    data = _read_yaml(pack_root / "pack.yaml")
    assert ULID.from_str(data["pack_id"])  # raises if malformed


def test_built_in_and_internal_are_untouched(tmp_path: Path) -> None:
    """``packs/built-in`` and ``packs/internal`` never receive a project ``pack.yaml``."""
    _make_project_pack(tmp_path)
    built_in = tmp_path / "packs" / "built-in"
    internal = tmp_path / "packs" / "internal"
    built_in.mkdir(parents=True)
    internal.mkdir(parents=True)

    PackLevelBackfillMigration().apply(tmp_path)

    assert not (built_in / "pack.yaml").exists()
    assert not (internal / "pack.yaml").exists()


def test_never_mkdir_when_project_pack_absent(tmp_path: Path) -> None:
    """A project with no ``charter-packs`` dir is a no-op — the dir is NOT created."""
    (tmp_path / ".kittify").mkdir()

    result = PackLevelBackfillMigration().apply(tmp_path)

    assert result.success is True
    assert not (tmp_path / ".kittify" / "charter-packs").exists()
    assert result.changes_made == []


# ---------------------------------------------------------------------------
# T015 — idempotency + non-clobber
# ---------------------------------------------------------------------------


def test_authored_pack_yaml_with_level_is_not_clobbered(tmp_path: Path) -> None:
    """An authored descriptor that already declares ``pack_level`` is left untouched."""
    pack_root = _make_project_pack(tmp_path)
    authored = pack_root / "pack.yaml"
    original = "pack_id: 01ARWG13C000000000000000AA\nname: authored-handle\npack_level: project\n"
    authored.write_text(original, encoding="utf-8")

    result = PackLevelBackfillMigration().apply(tmp_path)

    assert result.success is True
    assert authored.read_text(encoding="utf-8") == original
    assert result.changes_made == []


def test_adds_pack_level_only_if_absent_preserving_pack_id(tmp_path: Path) -> None:
    """An authored descriptor missing only ``pack_level`` gains it; its ``pack_id`` stays."""
    pack_root = _make_project_pack(tmp_path)
    authored = pack_root / "pack.yaml"
    authored.write_text(
        "pack_id: 01ARWG13C000000000000000BB\nname: authored-handle\n",
        encoding="utf-8",
    )

    result = PackLevelBackfillMigration().apply(tmp_path)

    assert result.success is True
    data = _read_yaml(authored)
    assert data["pack_id"] == "01ARWG13C000000000000000BB"  # differing id preserved
    assert data["pack_level"] == "project"
    assert data["name"] == "authored-handle"


def test_rerun_is_idempotent(tmp_path: Path) -> None:
    """Re-running the migration never changes a pack it already backfilled."""
    pack_root = _make_project_pack(tmp_path)

    first = PackLevelBackfillMigration().apply(tmp_path)
    minted_id = _read_yaml(pack_root / "pack.yaml")["pack_id"]
    second = PackLevelBackfillMigration().apply(tmp_path)

    assert first.success is True
    assert second.success is True
    assert second.changes_made == []
    assert _read_yaml(pack_root / "pack.yaml")["pack_id"] == minted_id


# ---------------------------------------------------------------------------
# detect / dry-run
# ---------------------------------------------------------------------------


def test_detect_true_when_backfill_needed_false_after(tmp_path: Path) -> None:
    """``detect`` is True while the project pack lacks ``pack_level``, False once set."""
    _make_project_pack(tmp_path)
    migration = PackLevelBackfillMigration()

    assert migration.detect(tmp_path) is True
    migration.apply(tmp_path)
    assert migration.detect(tmp_path) is False


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    """A dry-run reports the intended change but writes no file."""
    pack_root = _make_project_pack(tmp_path)

    result = PackLevelBackfillMigration().apply(tmp_path, dry_run=True)

    assert result.success is True
    assert result.changes_made  # describes the would-be write
    assert not (pack_root / "pack.yaml").exists()


def test_change_notes_use_project_relative_paths(tmp_path: Path) -> None:
    """Change notes land in the committed metadata.yaml: no absolute paths."""
    _make_project_pack(tmp_path)

    dry = PackLevelBackfillMigration().apply(tmp_path, dry_run=True)
    real = PackLevelBackfillMigration().apply(tmp_path)

    notes = dry.changes_made + real.changes_made
    assert notes
    assert all(str(tmp_path) not in note for note in notes)
    assert all(".kittify/charter-packs/pack.yaml" in note for note in notes)
