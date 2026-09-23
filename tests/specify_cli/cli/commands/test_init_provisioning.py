"""Tests for fresh-init fail-closed default-charter provisioning (WP03).

Mission ``resolution-activation-foundation-01KZ9FKG``, FR-009/010/011 and
NFR-004; contracts C-A3/C-A4/C-A5; data-model Seam 2 (I-8/I-9/I-10).

Covers:

* T014(a) — C-A3: a brand-new ``spec-kitty init`` writes an explicit,
  non-empty ``mission_type_activations`` copied from
  ``src/charter/activation/packs/default.yaml``.
* T014(b) — C-A4: a broken install missing ``default.yaml`` fails closed
  with an actionable error, both at the helper level and through the ``init``
  CLI command.
* T014(c) — C-A5/NFR-004/I-8: re-running provisioning on an already-
  provisioned config is byte-identical and preserves a custom (non-built-in)
  entry; an authored empty list is never overwritten (C-008/C-A2).
* **Copy-vs-rescan discriminator (REQUIRED)** — a fixture ``default.yaml``
  whose ``mission_type_activations`` differs from the disk-scanned built-in
  roster; the provisioned config must match the *fixture*, not
  ``builtin_mission_type_id_set()``. This is what pins D-07/I-10 (copy, not
  re-derive) and fails a re-scan implementation.
* T017 — migration-parity regression: both rc35 migrations
  (``m_3_2_0rc35_default_charter_pack``, ``m_3_2_0rc35_activate_builtin_mission_types``)
  are unchanged in identity and remain idempotent (operator decision: keep
  both, no consolidation, D-05). No migration file is edited by this WP.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from ruamel.yaml import YAML
from typer import Typer
from typer.testing import CliRunner

from specify_cli.charter_pack_registry import load_pack_yaml, resolve_builtin_pack_path
from specify_cli.cli.commands import init as init_module
from specify_cli.cli.commands.init import register_init_command
from specify_cli.template.manager import TemplateCopyResult
from specify_cli.provisioning import default_charter
from specify_cli.provisioning.default_charter import (
    DefaultCharterPackMissingError,
    provision_default_mission_type_activations,
)

pytestmark = pytest.mark.integration

_SAFE_YAML = YAML(typ="safe")


def _write_pack_fixture(path: Path, mission_types: list[str]) -> None:
    """Write a minimal charter-pack fixture declaring only the activation key."""
    dump_yaml = YAML()
    with path.open("w", encoding="utf-8") as fh:
        dump_yaml.dump({"mission_type_activations": mission_types}, fh)


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
# T014(a) — C-A3: fresh init copies the real default.yaml roster verbatim
# ---------------------------------------------------------------------------


def test_fresh_init_writes_mission_type_activations_from_default_pack(
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

    default_pack_path = resolve_builtin_pack_path("default")
    expected = load_pack_yaml(default_pack_path)["mission_type_activations"]

    assert config_data.get("mission_type_activations") == expected
    assert config_data["mission_type_activations"] != []


# ---------------------------------------------------------------------------
# T014(b) — C-A4: fail closed on a broken install missing default.yaml
# ---------------------------------------------------------------------------


def test_provision_raises_when_default_pack_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C-A4/FR-011: a missing default.yaml raises, never an empty/implicit set."""

    def _raise_missing(name: str) -> Path:
        raise FileNotFoundError(f"missing pack {name!r}")

    monkeypatch.setattr(default_charter, "resolve_builtin_pack_path", _raise_missing)

    with pytest.raises(DefaultCharterPackMissingError):
        provision_default_mission_type_activations(tmp_path / "project")


def test_provision_raises_when_pack_lacks_mission_type_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C-A4/FR-011: a malformed default.yaml (no activation key) also fails closed."""
    fixture_pack = tmp_path / "fixture-default.yaml"
    dump_yaml = YAML()
    with fixture_pack.open("w", encoding="utf-8") as fh:
        dump_yaml.dump({"activated_kinds": []}, fh)

    monkeypatch.setattr(
        default_charter, "resolve_builtin_pack_path", lambda name: fixture_pack
    )

    with pytest.raises(DefaultCharterPackMissingError):
        provision_default_mission_type_activations(tmp_path / "project")


def test_fresh_init_fails_closed_when_default_pack_missing(
    cli_app: tuple[Typer, Console],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """C-A4/FR-011: init itself fails closed (exit 1, actionable message)."""
    app, console = cli_app
    monkeypatch.chdir(tmp_path)
    _patch_common_init_seams(monkeypatch)

    def _raise_missing(name: str) -> Path:
        raise FileNotFoundError(f"missing pack {name!r}")

    monkeypatch.setattr(default_charter, "resolve_builtin_pack_path", _raise_missing)

    result = _run(app, ["init", "broken-install", "--ai", "claude", "--non-interactive"])

    assert result.exit_code == 1
    # The injected `console` (not CliRunner's captured stdout) is where init.py
    # prints its actionable error -- see register_init_command's `console` kwarg.
    assert isinstance(console.file, io.StringIO)
    printed = console.file.getvalue().lower()
    assert "default" in printed
    assert "broken" in printed or "reinstall" in printed


# ---------------------------------------------------------------------------
# Copy-vs-rescan discriminator (REQUIRED, post-tasks squad) — D-07/I-10
# ---------------------------------------------------------------------------


def test_provision_copies_fixture_pack_verbatim_not_disk_roster(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The provisioned config matches the FIXTURE pack, not the disk-scanned roster.

    ``default.yaml`` currently authors exactly the disk roster
    ``[software-dev, documentation, research, plan]``, so a naive test would
    pass whether the implementation copies or re-scans. This fixture's list
    deliberately differs from the disk roster (a subset plus a custom,
    non-built-in id) — a re-scan implementation (via
    ``builtin_mission_type_id_set()``) would resolve the disk roster instead
    of the fixture and fail this assertion.
    """
    fixture_pack = tmp_path / "fixture-default.yaml"
    fixture_types = ["software-dev", "totally-custom-fixture-type"]
    _write_pack_fixture(fixture_pack, fixture_types)

    monkeypatch.setattr(
        default_charter, "resolve_builtin_pack_path", lambda name: fixture_pack
    )

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
    fixture_pack = tmp_path / "fixture-default.yaml"
    _write_pack_fixture(fixture_pack, ["software-dev", "documentation"])
    monkeypatch.setattr(
        default_charter, "resolve_builtin_pack_path", lambda name: fixture_pack
    )

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
    fixture_pack = tmp_path / "fixture-default.yaml"
    _write_pack_fixture(fixture_pack, ["software-dev"])
    monkeypatch.setattr(
        default_charter, "resolve_builtin_pack_path", lambda name: fixture_pack
    )

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


def test_rc35_default_charter_pack_migration_identity_and_idempotence_unchanged(
    tmp_path: Path,
) -> None:
    """m_3_2_0rc35_default_charter_pack: identity + idempotence pinned."""
    from specify_cli.upgrade.migrations.m_3_2_0rc35_default_charter_pack import (
        DefaultCharterPackMigration,
    )

    migration = DefaultCharterPackMigration()
    assert migration.migration_id == "3.2.0rc35_default_charter_pack"
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
        "All activation keys already present; no changes needed"
    ]


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
