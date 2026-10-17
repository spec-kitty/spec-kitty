"""Migration 3.1.1: install the status.events.jsonl git merge driver."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

_ATTRIBUTES_ENTRY = "kitty-specs/**/status.events.jsonl merge=spec-kitty-event-log"
_DRIVER_NAME = "Spec Kitty event log union merge"
_DRIVER_COMMAND = "spec-kitty merge-driver-event-log %O %A %B"


def _ensure_line(path: Path, line: str) -> bool:
    """Append ``line`` to ``path`` if it is not already present."""
    existing = []
    if path.exists():
        existing = path.read_text(encoding="utf-8").splitlines()
        if line in existing:
            return False

    existing.append(line)
    path.write_text("\n".join(existing).rstrip() + "\n", encoding="utf-8")
    return True


def _git_config(project_path: Path, *args: str) -> str | None:
    """Run ``git config`` in the project and return stdout on success."""
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


@MigrationRegistry.register
class EventLogMergeDriverMigration(BaseMigration):
    """Install the git merge driver for append-only status event logs."""

    migration_id = "3.1.1_event_log_merge_driver"
    description = "Install a semantic git merge driver for status.events.jsonl"
    target_version = "3.1.1"
    # Split effect: tracked ``.gitattributes`` + clone-local ``git config --local``;
    # detect() returns True while the local half is missing, so reselection
    # settles per-clone (#6233).
    clone_local_effect = True

    def detect(self, project_path: Path) -> bool:
        attributes_path = project_path / ".gitattributes"
        attributes_missing = True
        if attributes_path.exists():
            attributes_missing = _ATTRIBUTES_ENTRY not in attributes_path.read_text(
                encoding="utf-8"
            )

        if not (project_path / ".git").exists():
            return attributes_missing

        driver = _git_config(project_path, "--get", "merge.spec-kitty-event-log.driver")
        name = _git_config(project_path, "--get", "merge.spec-kitty-event-log.name")
        return attributes_missing or driver != _DRIVER_COMMAND or name != _DRIVER_NAME

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        changes: list[str] = []
        warnings: list[str] = []

        if dry_run:
            if self.detect(project_path):
                changes.append("Would install status.events.jsonl merge driver and .gitattributes entry")
            return MigrationResult(success=True, changes_made=changes, warnings=warnings)

        attributes_path = project_path / ".gitattributes"
        if _ensure_line(attributes_path, _ATTRIBUTES_ENTRY):
            changes.append(f"Added .gitattributes entry: {_ATTRIBUTES_ENTRY}")

        if (project_path / ".git").exists():
            current_name = _git_config(project_path, "--get", "merge.spec-kitty-event-log.name")
            if current_name != _DRIVER_NAME:
                subprocess.run(
                    ["git", "config", "--local", "merge.spec-kitty-event-log.name", _DRIVER_NAME],
                    cwd=project_path,
                    check=True,
                )
                changes.append("Configured git merge.spec-kitty-event-log.name")

            current_driver = _git_config(project_path, "--get", "merge.spec-kitty-event-log.driver")
            if current_driver != _DRIVER_COMMAND:
                subprocess.run(
                    ["git", "config", "--local", "merge.spec-kitty-event-log.driver", _DRIVER_COMMAND],
                    cwd=project_path,
                    check=True,
                )
                changes.append("Configured git merge.spec-kitty-event-log.driver")
        else:
            warnings.append("Skipped local git merge-driver config because this project is not a git repository")

        return MigrationResult(success=True, changes_made=changes, warnings=warnings)
