"""Tests for the ``4.0.0rc8_repair_historical_sweep_overrides`` migration (#6548).

An older build's ``2.0.6_consistency_sweep`` moved every file under
``.kittify/missions/<mission>/`` into ``.kittify/overrides/missions/<mission>/``,
including files the package ships byte-for-byte. The new-sweep classifier is
fixed, and ``4.0.0rc8_retire_stale_mission_template_forks`` repairs 15 named
documentation/research fork copies, but a *historical* override for another
mission is still read at resolution tier 1, and ``2.0.7_fix_stale_overrides``
cannot see it (its matcher joins a second ``missions/`` segment onto a root that
already ends in ``missions/``; it is a frozen shipped body, DIRECTIVE_044).

The reproduction at the bottom drives the real ``spec-kitty upgrade`` command:
it fails on the baseline and passes only once the repair step is registered.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.runtime.home import get_package_asset_root
from specify_cli.runtime.resolver import ResolutionTier, resolve_template
from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.migrations import m_4_0_0rc8_repair_historical_sweep_overrides as module
from specify_cli.upgrade.migrations.m_4_0_0rc8_repair_historical_sweep_overrides import (
    MIGRATION_ID,
    TARGET_VERSION,
    RepairHistoricalSweepOverridesMigration,
    kept_warning,
    skipped_symlink_warning,
    skipped_tree_warning,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = pytest.mark.fast

MISSION = "software-dev"
IDENTICAL = "spec-template.md"
DIFFERING = "plan-template.md"
_OUTDATED_SUFFIX = b"\n<!-- outdated copy left by the 2.0.6 sweep -->\n"


def _shipped(name: str, mission: str = MISSION) -> bytes:
    return (get_package_asset_root() / mission / "templates" / name).read_bytes()


def _plant_override(project: Path, name: str, content: bytes, mission: str = MISSION) -> Path:
    path = project / ".kittify" / "overrides" / "missions" / mission / "templates" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '4.0.0rc8'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)


def _init_project(root: Path) -> None:
    """A bare project at 4.0.0rc8 — the shape an older sweep left behind."""
    kittify = root / ".kittify"
    kittify.mkdir(parents=True)
    (kittify / "metadata.yaml").write_text(_METADATA_YAML, encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade)
_cli_runner = CliRunner()


def _run_upgrade(cwd: Path) -> str:
    with contextlib.chdir(cwd):
        result = _cli_runner.invoke(_test_app, ["--yes", "--no-worktrees"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    return result.output


class TestUpgradeRepairsAHistoricalSweepOverride:
    """The reproduction: the real ``spec-kitty upgrade`` command (red on the baseline)."""

    @pytest.mark.integration
    @pytest.mark.git_repo
    @pytest.mark.usefixtures("canonical_home")
    def test_identical_override_is_removed_and_differing_one_is_named(self, tmp_path: Path) -> None:
        project = tmp_path / "proj"
        _init_project(project)
        identical = _plant_override(project, IDENTICAL, _shipped(IDENTICAL))
        differing = _plant_override(project, DIFFERING, _shipped(DIFFERING) + _OUTDATED_SUFFIX)
        # Before: both shadow the shipped templates at the override tier.
        for name in (IDENTICAL, DIFFERING):
            assert resolve_template(name, project, MISSION).tier is ResolutionTier.OVERRIDE

        output = _run_upgrade(project)

        assert not identical.exists(), "a proven byte-identical override must be removed"
        assert differing.read_bytes() == _shipped(DIFFERING) + _OUTDATED_SUFFIX
        assert f"overrides/missions/{MISSION}/templates/{DIFFERING}" in output, "the kept override must be named for the operator"
        assert resolve_template(IDENTICAL, project, MISSION).tier is not ResolutionTier.OVERRIDE
        # The kept file is the positive control: the scan did not blanket-delete.
        assert resolve_template(DIFFERING, project, MISSION).tier is ResolutionTier.OVERRIDE


# ---------------------------------------------------------------------------
# Unit tests: the migration seam
# ---------------------------------------------------------------------------


def _migration() -> RepairHistoricalSweepOverridesMigration:
    return RepairHistoricalSweepOverridesMigration()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A project whose global runtime home is empty, so resolution falls through to the pack."""
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path / "empty-global-home"))
    monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
    root = tmp_path / "project"
    (root / ".kittify").mkdir(parents=True)
    return root


def test_identical_override_is_removed_and_the_pack_copy_resolves(project: Path) -> None:
    override = _plant_override(project, IDENTICAL, _shipped(IDENTICAL))
    assert resolve_template(IDENTICAL, project, MISSION).tier is ResolutionTier.OVERRIDE

    result = _migration().apply(project)

    assert result.success, result.errors
    assert not override.exists()
    assert override.parent.is_dir(), "directories are never removed"
    assert result.changes_made == [f"Removed package-owned .kittify/overrides/missions/{MISSION}/templates/{IDENTICAL} (proof: canonical_content)"]
    resolved = resolve_template(IDENTICAL, project, MISSION)
    assert resolved.tier is not ResolutionTier.OVERRIDE
    assert resolved.path.read_bytes() == _shipped(IDENTICAL)


def test_differing_override_is_kept_verbatim_and_named(project: Path) -> None:
    content = _shipped(DIFFERING) + _OUTDATED_SUFFIX
    override = _plant_override(project, DIFFERING, content)

    result = _migration().apply(project)

    assert result.success, result.errors
    assert override.read_bytes() == content
    assert result.warnings == [kept_warning(f".kittify/overrides/missions/{MISSION}/templates/{DIFFERING}")]
    assert result.changes_made == ["No historical sweep-created override matched a shipped file — nothing removed"]
    assert resolve_template(DIFFERING, project, MISSION).tier is ResolutionTier.OVERRIDE


def test_identical_and_differing_in_one_project_are_one_step(project: Path) -> None:
    identical = _plant_override(project, IDENTICAL, _shipped(IDENTICAL))
    differing = _plant_override(project, DIFFERING, _shipped(DIFFERING) + _OUTDATED_SUFFIX)

    result = _migration().apply(project)

    assert not identical.exists()
    assert differing.read_bytes().endswith(_OUTDATED_SUFFIX)
    assert len(result.changes_made) == 1
    assert len(result.warnings) == 1


def test_override_without_a_shipped_counterpart_is_untouched(project: Path) -> None:
    """A custom mission, and an extra file in a shipped mission, are genuine customisations."""
    erp = _plant_override(project, "mission.yaml", b"name: erp\n", mission="erp")
    extra = _plant_override(project, "our-own-template.md", b"hand written\n")

    result = _migration().apply(project)

    assert erp.read_bytes() == b"name: erp\n"
    assert extra.read_bytes() == b"hand written\n"
    assert result.warnings == []
    assert result.changes_made == ["No historical sweep-created override matched a shipped file — nothing removed"]


def test_crlf_copy_of_the_shipped_file_is_preserved_and_named(project: Path) -> None:
    """Exact bytes: a CRLF working-tree copy is not proven identical, so it is never deleted."""
    crlf = _shipped(IDENTICAL).replace(b"\n", b"\r\n")
    override = _plant_override(project, IDENTICAL, crlf)

    result = _migration().apply(project)

    assert override.read_bytes() == crlf
    assert result.warnings == [kept_warning(f".kittify/overrides/missions/{MISSION}/templates/{IDENTICAL}")]


def test_second_apply_changes_nothing(project: Path) -> None:
    _plant_override(project, IDENTICAL, _shipped(IDENTICAL))
    _migration().apply(project)

    second = _migration().apply(project)

    assert second.changes_made == ["No historical sweep-created override matched a shipped file — nothing removed"]
    assert second.warnings == []


def test_dry_run_reports_the_removal_without_performing_it(project: Path) -> None:
    override = _plant_override(project, IDENTICAL, _shipped(IDENTICAL))

    result = _migration().apply(project, dry_run=True)

    assert override.exists()
    assert result.changes_made == [f"Would remove package-owned .kittify/overrides/missions/{MISSION}/templates/{IDENTICAL} (proof: canonical_content)"]


def test_detect_is_false_without_an_overrides_tree(project: Path) -> None:
    assert _migration().detect(project) is False


def test_detect_is_true_for_a_kept_override_so_it_is_named(project: Path) -> None:
    _plant_override(project, DIFFERING, _shipped(DIFFERING) + _OUTDATED_SUFFIX)

    assert _migration().detect(project) is True


def test_can_apply_refuses_when_the_shipped_files_cannot_be_located(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def _missing() -> Path:
        raise FileNotFoundError("no pack tree here")

    monkeypatch.setattr(module, "get_package_asset_root", _missing)

    ok, reason = _migration().can_apply(project)

    assert ok is False
    assert "no pack tree here" in reason
    assert _migration().detect(project) is False


def test_apply_fails_closed_when_the_shipped_files_cannot_be_located(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = _plant_override(project, IDENTICAL, _shipped(IDENTICAL))

    def _missing() -> Path:
        raise FileNotFoundError("no pack tree here")

    monkeypatch.setattr(module, "get_package_asset_root", _missing)
    result = _migration().apply(project)

    assert result.success is False
    assert override.exists()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_symlinked_override_tree_is_refused_and_left_untouched(project: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    target = outside / MISSION / "templates" / IDENTICAL
    target.parent.mkdir(parents=True)
    target.write_bytes(_shipped(IDENTICAL))
    (project / ".kittify" / "overrides").symlink_to(outside, target_is_directory=True)

    assert _migration().detect(project) is True
    result = _migration().apply(project)

    assert result.success, result.errors
    assert target.read_bytes() == _shipped(IDENTICAL)
    assert result.warnings == [skipped_tree_warning(".kittify/overrides")]


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_symlinked_override_file_is_skipped_and_named(project: Path, tmp_path: Path) -> None:
    real = tmp_path / "real-template.md"
    real.write_bytes(_shipped(IDENTICAL))
    link = project / ".kittify" / "overrides" / "missions" / MISSION / "templates" / IDENTICAL
    link.parent.mkdir(parents=True)
    link.symlink_to(real)

    result = _migration().apply(project)

    assert link.is_symlink()
    assert real.read_bytes() == _shipped(IDENTICAL)
    assert result.warnings == [skipped_symlink_warning(f".kittify/overrides/missions/{MISSION}/templates/{IDENTICAL}")]


def test_migration_is_registered_and_ordered() -> None:
    registered = MigrationRegistry.get_by_id(MIGRATION_ID)

    assert registered is not None
    assert registered.target_version == TARGET_VERSION
    manifest = load_order_manifest()
    assert manifest.count(MIGRATION_ID) == 1
    assert manifest.index(MIGRATION_ID) > manifest.index("4.0.0rc8_retire_stale_mission_template_forks")
