"""Tests for fresh-init fail-closed default-charter provisioning (WP03).

Mission ``resolution-activation-foundation-01KZ9FKG``, FR-009/010/011 and
NFR-004; contracts C-A3/C-A4/C-A5; data-model Seam 2 (I-8/I-9/I-10).

Covers:

* T014(a) — C-A3: a brand-new ``spec-kitty init`` writes an explicit,
  non-empty ``mission_type_activations`` copied from the built-in pack's
  ``default`` preset (FR-003).
* T014(b) — C-A4: a broken install whose ``default`` preset is missing fails
  closed with ``DEFAULT_PRESET_MISSING``, both at the helper level and through
  the ``init`` CLI command.
* T014(c) — C-A5/NFR-004/I-8: re-running provisioning on an already-
  provisioned config is byte-identical and preserves a custom (non-built-in)
  entry; an authored empty list is never overwritten (C-008/C-A2).
* **Copy-vs-rescan discriminator (REQUIRED)** — a fixture ``default`` preset
  whose ``mission_type_activations`` differs from the disk-scanned built-in
  roster; the provisioned config must match the *fixture*, not
  ``builtin_mission_type_id_set()``. This is what pins D-07/I-10 (copy, not
  re-derive) and fails a re-scan implementation.
* T017 — migration-parity regression: the rc35
  ``m_3_2_0rc35_activate_builtin_mission_types`` migration is unchanged in
  identity and remains idempotent (operator decision D-05).

Fixture presets live in a tmp copy of ``packs/built-in`` that
``SPEC_KITTY_PACKS_ROOT`` points at.
"""

from __future__ import annotations

import io
import shutil
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from ruamel.yaml import YAML
from typer import Typer
from typer.testing import CliRunner

from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult
from charter.activation.compiler import DefaultPresetMissingError
from specify_cli.provisioning.default_charter import provision_default_mission_type_activations

pytestmark = pytest.mark.integration

_SAFE_YAML = YAML(typ="safe")


_BUILT_IN = Path(__file__).resolve().parents[4] / "packs" / "built-in"


def _copied_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tmp copy of ``packs/built-in`` the code resolves through ``SPEC_KITTY_PACKS_ROOT``."""
    packs_root = tmp_path / "packs-root"
    shutil.copytree(_BUILT_IN, packs_root / "built-in")
    monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
    return packs_root / "built-in"


def _write_preset_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]) -> Path:
    """Copy the built-in pack and replace its ``default`` preset with *body*."""
    preset = _copied_pack(tmp_path, monkeypatch) / "presets" / "default.yaml"
    dump_yaml = YAML()
    with preset.open("w", encoding="utf-8") as fh:
        dump_yaml.dump({"name": "default", "description": "fixture", **body}, fh)
    return preset


def _load_config(config_file: Path) -> dict[str, Any]:
    return _SAFE_YAML.load(config_file) or {}


# ---------------------------------------------------------------------------
# Shared CLI fixture (mirrors test_init_integration.py)
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli_app(monkeypatch: pytest.MonkeyPatch) -> tuple[Typer, Console]:
    """Return a minimal Typer app with init registered and heavy I/O mocked."""
    console = Console(file=io.StringIO(), force_terminal=False)
    app = Typer()

    register_init_command(
        app,
        console=console,
        show_banner=lambda: None,
        activate_mission=lambda proj, mtype, mdisplay, _con: mdisplay,
        ensure_executable_scripts=lambda path, tracker=None: None,
    )

    return app, console


def _run(app: Typer, args: list[str]) -> object:
    runner = CliRunner()
    return runner.invoke(app, args, catch_exceptions=True)


def _fake_copy_package(project_path: Path) -> TemplateCopyResult:
    kittify = project_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    return TemplateCopyResult(kittify / "templates" / "command-templates", templates_created=True)


def _patch_common_init_seams(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(init_module, "get_local_repo_root", lambda override_path=None: None)
    monkeypatch.setattr(init_module, "copy_specify_base_from_package", _fake_copy_package)


# ---------------------------------------------------------------------------
# T014(a) — C-A3: fresh init copies the real default preset roster verbatim
# ---------------------------------------------------------------------------


def test_fresh_init_writes_mission_type_activations_from_default_preset(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """C-A3/SC-003: a brand-new init writes a non-empty, copied activation set."""
    app, _console = cli_app
    monkeypatch.chdir(tmp_path)
    _patch_common_init_seams(monkeypatch)

    result = _run(app, ["init", "fresh-provision", "--ai", "claude", "--non-interactive"])
    assert result.exit_code == 0, result.output

    config_file = tmp_path / "fresh-provision" / ".kittify" / "config.yaml"
    assert config_file.exists()
    config_data = _load_config(config_file)

    expected = _SAFE_YAML.load(_BUILT_IN / "presets" / "default.yaml")["mission_type_activations"]

    assert config_data.get("mission_type_activations") == expected
    assert config_data["mission_type_activations"] != []


# ---------------------------------------------------------------------------
# T014(b) — C-A4: fail closed on a broken install missing the default preset
# ---------------------------------------------------------------------------


def test_provision_raises_when_default_preset_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C-A4/FR-003: a missing default preset raises, never an empty/implicit set."""
    (_copied_pack(tmp_path, monkeypatch) / "presets" / "default.yaml").unlink()

    with pytest.raises(DefaultPresetMissingError) as caught:
        provision_default_mission_type_activations(tmp_path / "project")

    assert caught.value.code == "DEFAULT_PRESET_MISSING"
    assert not (tmp_path / "project" / ".kittify" / "config.yaml").exists()


def test_provision_raises_when_preset_lacks_mission_type_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C-A4/FR-003: a default preset without the activation key also fails closed."""
    _write_preset_fixture(tmp_path, monkeypatch, {"activated_kinds": []})

    with pytest.raises(DefaultPresetMissingError, match="DEFAULT_PRESET_MISSING"):
        provision_default_mission_type_activations(tmp_path / "project")


def test_fresh_init_fails_closed_when_default_preset_missing(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """C-A4/FR-011: init itself fails closed (exit 1, actionable message)."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    _patch_common_init_seams(monkeypatch)

    (_copied_pack(tmp_path, monkeypatch) / "presets" / "default.yaml").unlink()

    result = _run(app, ["init", "broken-install", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 1
    # The injected `console` (not CliRunner's captured stdout) is where init.py
    # prints its actionable error -- see register_init_command's `console` kwarg.
    assert isinstance(console.file, io.StringIO)
    printed = console.file.getvalue()
    assert "Error (DEFAULT_PRESET_MISSING):" in printed
    assert "reinstall spec-kitty" in printed


# ---------------------------------------------------------------------------
# Copy-vs-rescan discriminator (REQUIRED, post-tasks squad) — D-07/I-10
# ---------------------------------------------------------------------------


def test_provision_copies_fixture_pack_verbatim_not_disk_roster(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The provisioned config matches the FIXTURE preset, not the disk-scanned roster.

    The ``default`` preset currently authors exactly the disk roster
    ``[software-dev, documentation, research, plan]``, so a naive test would
    pass whether the implementation copies or re-scans. This fixture's list
    deliberately differs from the disk roster (a subset plus a custom,
    non-built-in id) — a re-scan implementation (via
    ``builtin_mission_type_id_set()``) would resolve the disk roster instead
    of the fixture and fail this assertion.
    """
    fixture_types = ["software-dev", "totally-custom-fixture-type"]
    _write_preset_fixture(tmp_path, monkeypatch, {"mission_type_activations": fixture_types})

    project = tmp_path / "project"
    project.mkdir()

    changed = provision_default_mission_type_activations(project)
    assert changed is True

    config_file = project / ".kittify" / "config.yaml"
    data = _load_config(config_file)
    assert data["mission_type_activations"] == fixture_types

    from charter.offering.missions.mission_type_repository import (
        builtin_mission_type_id_set,
    )

    disk_roster = sorted(builtin_mission_type_id_set())
    # The fixture must genuinely differ from the disk roster, or this test
    # would not discriminate copy-vs-rescan at all.
    assert sorted(fixture_types) != disk_roster
    assert data["mission_type_activations"] != disk_roster


# ---------------------------------------------------------------------------
# T014(c) — C-A5/NFR-004/I-8/I-9: idempotence + customization-safety
# ---------------------------------------------------------------------------


def test_provision_is_idempotent_and_preserves_custom_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Re-running provisioning is byte-identical and keeps a custom entry."""
    _write_preset_fixture(tmp_path, monkeypatch, {"mission_type_activations": ["software-dev", "documentation"]})

    project = tmp_path / "project"
    project.mkdir()

    first = provision_default_mission_type_activations(project)
    assert first is True

    config_file = project / ".kittify" / "config.yaml"

    # Simulate a hand-added custom mission type alongside the built-ins.
    round_trip_yaml = YAML()
    round_trip_yaml.preserve_quotes = True
    with config_file.open("r", encoding="utf-8") as fh:
        data = round_trip_yaml.load(fh)
    data["mission_type_activations"].append("my-custom-type")
    with config_file.open("w", encoding="utf-8") as fh:
        round_trip_yaml.dump(data, fh)

    before = config_file.read_text(encoding="utf-8")

    second = provision_default_mission_type_activations(project)
    assert second is False  # no-op: key already present (I-9)

    after = config_file.read_text(encoding="utf-8")
    assert after == before  # byte-identical (NFR-004)

    final_data = _load_config(config_file)
    assert "my-custom-type" in final_data["mission_type_activations"]
    assert "software-dev" in final_data["mission_type_activations"]


def test_authored_empty_activations_not_overwritten(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C-008/C-A2: an authored empty list must not trigger provisioning."""
    _write_preset_fixture(tmp_path, monkeypatch, {"mission_type_activations": ["software-dev"]})

    project = tmp_path / "project"
    kittify = project / ".kittify"
    kittify.mkdir(parents=True)
    config_file = kittify / "config.yaml"
    config_file.write_text("mission_type_activations: []\n", encoding="utf-8")
    before = config_file.read_text(encoding="utf-8")

    changed = provision_default_mission_type_activations(project)
    assert changed is False

    after = config_file.read_text(encoding="utf-8")
    assert after == before
    data = _load_config(config_file)
    assert data["mission_type_activations"] == []


# ---------------------------------------------------------------------------
# T017 — migration-parity regression (operator decision: keep BOTH rc35
# migrations unchanged; no consolidation, D-05). Reads/imports only — no
# migration file is edited by this WP.
# ---------------------------------------------------------------------------


def test_rc35_activate_builtin_mission_types_migration_identity_and_idempotence_unchanged(
    tmp_path: Path,
) -> None:
    """m_3_2_0rc35_activate_builtin_mission_types: identity + idempotence pinned."""
    from specify_cli.upgrade.migrations.m_3_2_0rc35_activate_builtin_mission_types import (
        ActivateBuiltinMissionTypesMigration,
    )

    migration = ActivateBuiltinMissionTypesMigration()
    assert migration.migration_id == "3.2.0rc35_activate_builtin_mission_types"
    assert migration.target_version == "3.2.0rc35"

    # Fail-open on absent config.yaml is an unchanged, deliberate operator
    # decision (D-05): absent config = not yet a spec-kitty project.
    assert migration.detect(tmp_path) is False

    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("agents:\n  available: []\n", encoding="utf-8")

    first = migration.apply(tmp_path)
    assert first.success is True
    assert first.changes_made

    second = migration.apply(tmp_path)
    assert second.success is True
    assert second.changes_made == [
        "mission_type_activations already present; no changes needed"
    ]
