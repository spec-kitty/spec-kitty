"""Shared machinery for migrations that seed git merge drivers (DIRECTIVE_044).

Every merge driver declared in ``specify_cli.lanes.consolidation._MERGE_DRIVERS`` needs
three seeding surfaces or an upgraded repo silently re-inherits the clobbering
behavior the driver exists to prevent (guarded by
``tests/architectural/test_merge_reconciliation_class_guard.py``):

1. the repo's committed ``.gitattributes`` (this project),
2. the ``init`` seed (fresh consumer repos),
3. an upgrade migration (already-initialized consumer repos) — this module.

Migrations parametrize :class:`MergeDriverSeedingMigration` with their own
``drivers`` tuple instead of cloning the seeding body.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .base import BaseMigration, MigrationResult


@dataclass(frozen=True)
class DriverSpec:
    """One merge driver's git-config identity and ``.gitattributes`` mapping."""

    config_key: str
    name: str
    command: str
    pattern: str

    @property
    def attributes_entry(self) -> str:
        return f"{self.pattern} merge={self.config_key}"


def ensure_line(path: Path, line: str) -> bool:
    """Append ``line`` to ``path`` if it is not already present."""
    existing: list[str] = []
    if path.exists():
        existing = path.read_text(encoding="utf-8").splitlines()
        if line in existing:
            return False
    existing.append(line)
    path.write_text("\n".join(existing).rstrip() + "\n", encoding="utf-8")
    return True


def git_config(project_path: Path, *args: str) -> str | None:
    """Run ``git config --local`` in the project and return stdout on success."""
    result = subprocess.run(
        ["git", "config", "--local", *args],
        cwd=project_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


class MergeDriverSeedingMigration(BaseMigration):
    """Base for migrations that install a set of git merge drivers.

    Subclasses declare ``migration_id``, ``description``, ``target_version``,
    ``drivers``, and ``dry_run_summary``. The detect/apply semantics — idempotent
    ``.gitattributes`` lines plus ``merge.<key>.name`` / ``.driver`` local config,
    with a warning (not a failure) on non-git projects — are defined once here.
    """

    drivers: tuple[DriverSpec, ...] = ()
    dry_run_summary: str = "Would install merge drivers and .gitattributes entries"

    def _attributes_missing(self, project_path: Path) -> bool:
        attributes_path = project_path / ".gitattributes"
        if not attributes_path.exists():
            return True
        text = attributes_path.read_text(encoding="utf-8")
        return any(driver.attributes_entry not in text for driver in self.drivers)

    def _config_missing(self, project_path: Path) -> bool:
        if not (project_path / ".git").exists():
            return False
        for driver in self.drivers:
            name = git_config(project_path, "--get", f"merge.{driver.config_key}.name")
            command = git_config(project_path, "--get", f"merge.{driver.config_key}.driver")
            if name != driver.name or command != driver.command:
                return True
        return False

    def detect(self, project_path: Path) -> bool:
        return self._attributes_missing(project_path) or self._config_missing(project_path)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        changes: list[str] = []
        warnings: list[str] = []

        if dry_run:
            if self.detect(project_path):
                changes.append(self.dry_run_summary)
            return MigrationResult(success=True, changes_made=changes, warnings=warnings)

        attributes_path = project_path / ".gitattributes"
        is_git_repo = (project_path / ".git").exists()
        for driver in self.drivers:
            if ensure_line(attributes_path, driver.attributes_entry):
                changes.append(f"Added .gitattributes entry: {driver.attributes_entry}")
            if not is_git_repo:
                continue
            if git_config(project_path, "--get", f"merge.{driver.config_key}.name") != driver.name:
                subprocess.run(
                    ["git", "config", "--local", f"merge.{driver.config_key}.name", driver.name],
                    cwd=project_path,
                    check=True,
                )
                changes.append(f"Configured git merge.{driver.config_key}.name")
            if git_config(project_path, "--get", f"merge.{driver.config_key}.driver") != driver.command:
                subprocess.run(
                    ["git", "config", "--local", f"merge.{driver.config_key}.driver", driver.command],
                    cwd=project_path,
                    check=True,
                )
                changes.append(f"Configured git merge.{driver.config_key}.driver")

        if not is_git_repo:
            warnings.append("Skipped local git merge-driver config because this project is not a git repository")

        return MigrationResult(success=True, changes_made=changes, warnings=warnings)
