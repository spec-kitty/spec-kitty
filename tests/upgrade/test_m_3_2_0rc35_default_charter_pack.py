"""Tests for migration m_3_2_0rc35_default_charter_pack.

All tests call ``detect()`` and ``apply()`` directly on a
``DefaultCharterPackMigration`` instance.  They do NOT invoke the upgrade
pipeline so that the ``target_version = "3.2.0rc35"`` guard (which prevents the
migration from firing against rc builds) does not interfere with the test
suite.
"""

from __future__ import annotations

import glob
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.upgrade
from ruamel.yaml import YAML

from charter.drg import (
    DRGGraph,
    DRGNode,
    NodeKind,
)
from charter.activation.drg_activation import filter_graph_by_activation
from charter.activation.pack_context import PackContext
from specify_cli.upgrade.migrations import m_3_2_0rc35_default_charter_pack
from specify_cli.upgrade.migrations.m_3_2_0rc35_default_charter_pack import (
    DefaultCharterPackMigration,
    _DEFAULT_YAML_PATH,
    _PER_KIND_KEYS,
)


@pytest.mark.fast
def test_detect_returns_false_without_kittify(tmp_path: Path) -> None:
    """detect() returns False when no .kittify directory exists."""
    m = DefaultCharterPackMigration()
    assert m.detect(tmp_path) is False


@pytest.mark.fast
def test_detect_returns_true_when_any_per_kind_key_absent(tmp_path: Path) -> None:
    """detect() returns True when per-kind keys are absent from config.yaml."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config = kittify / "config.yaml"
    config.write_text("activated_kinds: []\n", encoding="utf-8")

    m = DefaultCharterPackMigration()
    assert m.detect(tmp_path) is True


@pytest.mark.fast
def test_detect_returns_false_when_all_keys_present(tmp_path: Path) -> None:
    """detect() returns False when all activation keys are present."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config = kittify / "config.yaml"

    all_keys = _PER_KIND_KEYS + ["activated_kinds", "mission_type_activations"]
    lines = [f"{key}: []\n" for key in all_keys]
    config.write_text("".join(lines), encoding="utf-8")

    m = DefaultCharterPackMigration()
    assert m.detect(tmp_path) is False


@pytest.mark.fast
def test_apply_writes_absent_keys_from_default_pack(tmp_path: Path) -> None:
    """apply() writes all missing per-kind keys from default.yaml.

    This test uses the real ``_DEFAULT_YAML_PATH`` shipped by WP04 when it is
    available.  When WP04 has not yet been merged into this lane, the test
    creates a minimal fixture ``default.yaml`` in a temp directory and patches
    ``_DEFAULT_YAML_PATH`` so the migration can still be exercised end-to-end.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config = kittify / "config.yaml"
    config.write_text("agents:\n  available: []\n", encoding="utf-8")

    yaml = YAML(typ="safe")

    if _DEFAULT_YAML_PATH.exists():
        # WP04 is merged — use the real file as the source of truth.
        m = DefaultCharterPackMigration()
        result = m.apply(tmp_path)

        assert result.success is True

        data = yaml.load(config) or {}
        expected = yaml.load(_DEFAULT_YAML_PATH) or {}

        for key in _PER_KIND_KEYS:
            assert key in data, f"Missing key: {key}"
            assert data[key] == expected.get(key, []), (
                f"Key {key!r} does not match default.yaml"
            )
        assert data["activated_kinds"] == expected["activated_kinds"]
        assert data["activated_kinds"] != []
    else:
        # WP04 is not yet merged into this lane.  Create a minimal fixture
        # that exercises the same code path so the migration logic is verified
        # independently of the dependency lane.
        fixture_pack = tmp_path / "default.yaml"
        fixture_content = {key: [f"default-{key}-entry"] for key in _PER_KIND_KEYS}
        fixture_content["activated_kinds"] = []
        fixture_content["mission_type_activations"] = ["software-dev"]
        dump_yaml = YAML()
        with fixture_pack.open("w", encoding="utf-8") as fh:
            dump_yaml.dump(fixture_content, fh)

        m = DefaultCharterPackMigration()
        with patch.object(
            m_3_2_0rc35_default_charter_pack, "_DEFAULT_YAML_PATH", fixture_pack
        ):
            result = m.apply(tmp_path)

        assert result.success is True

        data = yaml.load(config) or {}
        expected = yaml.load(fixture_pack) or {}

        for key in _PER_KIND_KEYS:
            assert key in data, f"Missing key: {key}"
            assert data[key] == expected.get(key, []), (
                f"Key {key!r} does not match fixture default.yaml"
            )


@pytest.mark.fast
def test_apply_writes_activation_kinds_that_keep_builtin_nodes_visible(
    tmp_path: Path,
) -> None:
    """Migrated default config must not filter out every built-in DRG artifact."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config = kittify / "config.yaml"
    config.write_text("agents:\n  available: []\n", encoding="utf-8")

    result = DefaultCharterPackMigration().apply(tmp_path)
    assert result.success is True

    ctx = PackContext.from_config(tmp_path)
    graph = DRGGraph.model_construct(
        schema_version="1.0",
        generated_at="2026-06-01T00:00:00Z",
        generated_by="test",
        nodes=[
            DRGNode(
                # Canonical directive URN form is ``directive:DIRECTIVE_NNN`` —
                # config stems (``001-architectural-integrity-standard``) resolve
                # to it via ``resolve_artifact_urn``. The activation filter
                # compares on the canonical node URN, never the config slug.
                urn="directive:DIRECTIVE_001",
                kind=NodeKind.DIRECTIVE,
            )
        ],
        edges=[],
    )

    filtered = filter_graph_by_activation(graph, ctx)
    assert [node.urn for node in filtered.nodes] == ["directive:DIRECTIVE_001"]


@pytest.mark.fast
def test_apply_does_not_overwrite_existing_keys(tmp_path: Path) -> None:
    """apply() preserves existing key values (incremental write only)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config = kittify / "config.yaml"
    config.write_text(
        "activated_directives:\n  - my-custom-directive\n", encoding="utf-8"
    )

    # Provide a minimal default.yaml fixture so apply() can complete
    fixture_pack = tmp_path / "fixture_default.yaml"
    fixture_data = {key: [f"default-{key}"] for key in _PER_KIND_KEYS}
    fixture_data["activated_kinds"] = []
    fixture_data["mission_type_activations"] = ["software-dev"]
    dump_yaml = YAML()
    with fixture_pack.open("w", encoding="utf-8") as fh:
        dump_yaml.dump(fixture_data, fh)

    m = DefaultCharterPackMigration()
    with patch.object(m_3_2_0rc35_default_charter_pack, "_DEFAULT_YAML_PATH", fixture_pack):
        result = m.apply(tmp_path)

    assert result.success is True

    yaml = YAML(typ="safe")
    data = yaml.load(config) or {}
    assert data["activated_directives"] == ["my-custom-directive"], (
        "Existing activated_directives must not be overwritten"
    )


@pytest.mark.fast
def test_apply_creates_backup_when_charter_md_exists(tmp_path: Path) -> None:
    """apply() backs up charter.md before writing config.yaml."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config = kittify / "config.yaml"
    config.write_text("agents:\n  available: []\n", encoding="utf-8")

    charter_dir = kittify / "charter"
    charter_dir.mkdir()
    charter_md = charter_dir / "charter.md"
    charter_md.write_text("# My Charter", encoding="utf-8")

    # Provide a minimal default.yaml fixture so apply() can complete
    fixture_pack = tmp_path / "fixture_default.yaml"
    fixture_data = {key: [] for key in _PER_KIND_KEYS}
    fixture_data["activated_kinds"] = []
    fixture_data["mission_type_activations"] = ["software-dev"]
    dump_yaml = YAML()
    with fixture_pack.open("w", encoding="utf-8") as fh:
        dump_yaml.dump(fixture_data, fh)

    m = DefaultCharterPackMigration()
    with patch.object(m_3_2_0rc35_default_charter_pack, "_DEFAULT_YAML_PATH", fixture_pack):
        result = m.apply(tmp_path)

    assert result.success is True

    backup_dir = charter_dir / "backups"
    assert backup_dir.exists(), "Backup directory must be created"

    backup_files = glob.glob(str(backup_dir / "charter-*.md"))
    assert len(backup_files) == 1, (  # (timestamp-suffixed name)
        f"Expected exactly one backup file, found: {backup_files}"
    )
    assert Path(backup_files[0]).read_text(encoding="utf-8") == "# My Charter"


@pytest.mark.fast
def test_apply_backup_filename_timestamp_is_utc_not_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-011 (kernel-clock-single-door, WP13c): the backup filename's
    timestamp suffix is derived from the door's aware-UTC ``now_utc()``, not
    a naive local-time ``datetime.now()``.

    Byte-changing: the pre-migration site called naive ``datetime.now()``
    (interpreted in the host's local timezone); it now reads
    ``format_stamp(now_utc(), "%Y-%m-%dT%H-%M-%S")``. Under a frozen clock,
    this test pins the EXACT backup filename to the UTC-derived value.

    C-009 mutation verified: reverting the site to
    ``datetime.now().strftime(...)`` (local time) would produce a different
    filename whenever the test runner's local timezone differs from UTC --
    this assertion, pinned against a fixed frozen instant, fails under that
    reversion in any non-UTC timezone.
    """
    import kernel.clock as clock_module
    from kernel.clock import UTC, FrozenClock, datetime

    frozen_instant = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
    monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=frozen_instant))

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config = kittify / "config.yaml"
    config.write_text("agents:\n  available: []\n", encoding="utf-8")

    charter_dir = kittify / "charter"
    charter_dir.mkdir()
    charter_md = charter_dir / "charter.md"
    charter_md.write_text("# My Charter", encoding="utf-8")

    fixture_pack = tmp_path / "fixture_default.yaml"
    fixture_data = {key: [] for key in _PER_KIND_KEYS}
    fixture_data["activated_kinds"] = []
    fixture_data["mission_type_activations"] = ["software-dev"]
    dump_yaml = YAML()
    with fixture_pack.open("w", encoding="utf-8") as fh:
        dump_yaml.dump(fixture_data, fh)

    m = DefaultCharterPackMigration()
    with patch.object(m_3_2_0rc35_default_charter_pack, "_DEFAULT_YAML_PATH", fixture_pack):
        result = m.apply(tmp_path)

    assert result.success is True

    expected_backup = charter_dir / "backups" / "charter-2026-03-04T05-06-07.md"
    assert expected_backup.exists(), (
        f"Expected backup at {expected_backup}, found: "
        f"{glob.glob(str(charter_dir / 'backups' / 'charter-*.md'))}"
    )


@pytest.mark.fast
def test_apply_handles_missing_default_yaml_gracefully(tmp_path: Path) -> None:
    """apply() returns failure when default.yaml is missing (broken install)."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    config = kittify / "config.yaml"
    config.write_text("agents:\n  available: []\n", encoding="utf-8")

    nonexistent = tmp_path / "does-not-exist" / "default.yaml"

    m = DefaultCharterPackMigration()
    with patch.object(m_3_2_0rc35_default_charter_pack, "_DEFAULT_YAML_PATH", nonexistent):
        result = m.apply(tmp_path)

    assert result.success is False
    assert len(result.errors) >= 1
    assert "default.yaml not found" in result.errors[0]
