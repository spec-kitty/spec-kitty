"""What a completed ``spec-kitty upgrade`` prints, pinned through the real command.

Every test drives the real ``upgrade`` command in-process with ``CliRunner`` on a
real git-backed project; only the inputs the run depends on (the applicable
migrations, the repair inventory) are stubbed. The outcome object is never built
by hand here: the closing line, the JSON ``status`` and the exit code are all
read from what the command emitted.

The first group are golden characterisation tests: the full captured text of a
successful run, pinned before the single-outcome change and unchanged after it
(FR-006, FR-007, NFR-003).
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import upgrade as upgrade_module
from specify_cli.cli.console import console
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.runner import UpgradeResult

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_PROJECT_VERSION = "1.0.0a1"
_MIGRATED_VERSION = "3.2.0a4"
_MIGRATION_ID = "3.2.0a4_fake_migration"
_SKIPPED_ID = "3.1.0_old_migration"
_GOLDEN_WIDTH = 80
_GOLDEN_HEIGHT = 24

_METADATA_YAML = (
    "spec_kitty:\n"
    "  version: '{version}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)

_test_app = typer.Typer(add_completion=False)
_test_app.command()(upgrade_module.upgrade)
_runner = CliRunner()


def _init_project(root: Path, *, version: str = _PROJECT_VERSION) -> None:
    """A minimal, real git-backed Spec Kitty project at *version*."""
    root.mkdir(parents=True, exist_ok=True)
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(_METADATA_YAML.format(version=version), encoding="utf-8")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)


def _invoke(project: Path, args: list[str]) -> Any:
    with contextlib.chdir(project):
        return _runner.invoke(_test_app, args, catch_exceptions=False)


def _stub_applied_migration(monkeypatch: pytest.MonkeyPatch) -> None:
    """One applicable migration that the (stubbed) runner applies successfully."""
    migration = MagicMock(migration_id=_MIGRATION_ID, description="fake migration", target_version=_MIGRATED_VERSION)
    monkeypatch.setattr("specify_cli.upgrade.registry.MigrationRegistry.get_applicable", lambda *_a, **_kw: [migration])

    def _upgrade(_self: object, target_version: str, **kwargs: Any) -> UpgradeResult:
        return UpgradeResult(
            success=True,
            from_version=_PROJECT_VERSION,
            to_version=target_version,
            dry_run=bool(kwargs.get("dry_run")),
            migrations_applied=[_MIGRATION_ID],
            migrations_skipped=[_SKIPPED_ID],
            migration_results={_MIGRATION_ID: MigrationResult(success=True)},
        )

    monkeypatch.setattr("specify_cli.upgrade.runner.MigrationRunner.upgrade", _upgrade)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A real project, with the banner silenced and a fixed render width."""
    monkeypatch.setattr(upgrade_module, "show_banner", lambda: None)
    console.size = (_GOLDEN_WIDTH, _GOLDEN_HEIGHT)  # the autouse render pin restores it after the test
    root = tmp_path / "project"
    _init_project(root)
    return root


_GOLDEN_NO_OP_WITH_WARNING = (
    "Current version: 1.0.0a1\nTarget version:  1.0.0a1\n\nProject is already up to date!\nWarning: one warning\n→ Auto-committed upgrade changes (2 files)\n"
)

_GOLDEN_APPLIED = (
    "Current version: 1.0.0a1\n"
    "Target version:  3.2.0a4\n"
    "\n"
    "                   Migration Plan                    \n"
    "┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┓\n"
    "┃ Migration              ┃ Description    ┃ Target  ┃\n"
    "┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━┩\n"
    "│ 3.2.0a4_fake_migration │ fake migration │ 3.2.0a4 │\n"
    "└────────────────────────┴────────────────┴─────────┘\n"
    "\n"
    "\n"
    "Migrations applied:\n"
    "  ✓ 3.2.0a4_fake_migration\n"
    "Migrations skipped (already applied or not needed):\n"
    "  ○ 3.1.0_old_migration\n"
    "\n"
    "Upgrade complete! 1.0.0a1 -> 3.2.0a4\n"
    "→ Auto-committed upgrade changes (1 files)\n"
)

_GOLDEN_APPLIED_DRY_RUN = (
    "Current version: 1.0.0a1\n"
    "Target version:  3.2.0a4\n"
    "\n"
    "                   Migration Plan                    \n"
    "┏━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━┓\n"
    "┃ Migration              ┃ Description    ┃ Target  ┃\n"
    "┡━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━┩\n"
    "│ 3.2.0a4_fake_migration │ fake migration │ 3.2.0a4 │\n"
    "└────────────────────────┴────────────────┴─────────┘\n"
    "\n"
    "Would provision missing mission_type_activations (seeded on a real upgrade).\n"
    "Would repair 1 supporting surface paths (including 0 manifests). Use --plan-json\n"
    "for full repair details.\n"
    "\n"
    "╭──────────────────────────────────────────────────────────────────────────────╮\n"
    "│ DRY RUN - No changes were made                                               │\n"
    "╰──────────────────────────────────────────────────────────────────────────────╯\n"
    "Migrations applied:\n"
    "  ✓ 3.2.0a4_fake_migration\n"
    "Migrations skipped (already applied or not needed):\n"
    "  ○ 3.1.0_old_migration\n"
    "\n"
    "Dry run complete — no changes applied. (1.0.0a1 -> 3.2.0a4 previewed)\n"
)


def test_golden_no_op_with_one_warning(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A no-op run prints its closing line first, then each warning, then the commit line."""
    monkeypatch.setattr(upgrade_module, "_run_no_migrations_worktree_stamp", lambda *_a, **_kw: (["one warning"], []))

    result = _invoke(project, ["--target", _PROJECT_VERSION, "--yes", "--no-worktrees"])

    assert result.exit_code == 0, result.output
    assert result.output == _GOLDEN_NO_OP_WITH_WARNING


def test_golden_applied_run(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An applied run prints its sections, then the closing line, then the commit line."""
    _stub_applied_migration(monkeypatch)

    result = _invoke(project, ["--target", _MIGRATED_VERSION, "--yes", "--no-worktrees"])

    assert result.exit_code == 0, result.output
    assert result.output == _GOLDEN_APPLIED


def test_golden_applied_dry_run(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A completed dry run says nothing was applied and never prints the commit line."""
    _stub_applied_migration(monkeypatch)

    result = _invoke(project, ["--target", _MIGRATED_VERSION, "--yes", "--no-worktrees", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert result.output == _GOLDEN_APPLIED_DRY_RUN
