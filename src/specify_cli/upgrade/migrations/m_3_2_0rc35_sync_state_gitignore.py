"""Migration: repair local runtime ``.kittify`` git hygiene."""

from __future__ import annotations

import subprocess
from pathlib import Path

from kernel.git import GitCommandError, is_tracked
from specify_cli.gitignore_manager import GitignoreManager, read_ignore_file_text

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

_SYNC_STATE_ENTRY = ".kittify/sync-state.json"
_PROVENANCE_GITIGNORE_ENTRY = ".kittify/encoding-provenance/"
_PROVENANCE_TRACKED_PATH = ".kittify/encoding-provenance/global.jsonl"
# Machine-local Op-index performance cache (durable Op records live in
# kitty-ops/<op_id>.jsonl and stay tracked -- only the index is ignored).
_OPS_INDEX_ENTRY = "kitty-ops/ops-index.jsonl"
_GITIGNORE_ENTRIES = (_SYNC_STATE_ENTRY, _PROVENANCE_GITIGNORE_ENTRY, _OPS_INDEX_ENTRY)
_LOCAL_RUNTIME_TRACKED_PATHS = (
    ".kittify/charter/context-state.json",
    _PROVENANCE_TRACKED_PATH,
    _OPS_INDEX_ENTRY,
)


def _is_git_repo(project_path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(project_path), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _is_tracked(project_path: Path, relative_path: str) -> bool:
    if not _is_git_repo(project_path):
        return False
    try:
        return is_tracked(project_path, relative_path)
    except GitCommandError:
        # Advisory (detect/apply hygiene): a probe that could not run reads as
        # "not tracked", as before.
        return False


def _untrack(project_path: Path, relative_path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(project_path), "rm", "--cached", "--", relative_path],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _read_gitignore_entries(project_path: Path) -> set[str]:
    content = read_ignore_file_text(project_path / ".gitignore")
    return {
        line.strip()
        for line in content.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


@MigrationRegistry.register
class KittifyRuntimeGitHygieneMigration(BaseMigration):
    """Ignore sync state and untrack known local-runtime files."""

    migration_id = "3.2.0rc35_kittify_runtime_git_hygiene"
    description = "Repair local-runtime .kittify gitignore and tracked-file state"
    target_version = "3.2.0rc35"

    def detect(self, project_path: Path) -> bool:
        gitignore_entries = _read_gitignore_entries(project_path)
        entry_missing = any(entry not in gitignore_entries for entry in _GITIGNORE_ENTRIES)
        tracked_runtime = any(
            _is_tracked(project_path, path)
            for path in _LOCAL_RUNTIME_TRACKED_PATHS
        )
        return entry_missing or tracked_runtime

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        if dry_run:
            gitignore_entries = _read_gitignore_entries(project_path)
            missing_entries = [
                entry for entry in _GITIGNORE_ENTRIES if entry not in gitignore_entries
            ]
            tracked = [
                path
                for path in _LOCAL_RUNTIME_TRACKED_PATHS
                if _is_tracked(project_path, path)
            ]
            return MigrationResult(
                success=True,
                changes_made=[f"Would add {entry} to .gitignore" for entry in missing_entries]
                + [f"Would untrack local runtime file: {path}" for path in tracked],
            )

        changes: list[str] = []
        errors: list[str] = []

        gitignore_entries = _read_gitignore_entries(project_path)
        missing_entries = [
            entry for entry in _GITIGNORE_ENTRIES if entry not in gitignore_entries
        ]
        manager = GitignoreManager(project_path)
        modified = manager.ensure_entries(list(_GITIGNORE_ENTRIES))
        if modified and missing_entries:
            changes.append(f"Added gitignore entries: {', '.join(missing_entries)}")
        elif modified:
            changes.append("Updated .gitignore")
        else:
            changes.append("gitignore entries already present")

        for path in _LOCAL_RUNTIME_TRACKED_PATHS:
            if not _is_tracked(project_path, path):
                continue
            if _untrack(project_path, path):
                changes.append(f"Untracked local runtime file: {path}")
            else:
                errors.append(f"Failed to untrack local runtime file: {path}")

        return MigrationResult(
            success=not errors,
            changes_made=changes,
            errors=errors,
        )
