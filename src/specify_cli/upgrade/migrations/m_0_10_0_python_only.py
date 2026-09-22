"""Migration: Remove bash scripts and update templates to use Python CLI."""

from __future__ import annotations

import re
from pathlib import Path

from specify_cli.asset_preservation import CanonicalContentProver, guard_destructive_removal
from specify_cli.runtime.generated_writer import write_generated_file

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


@MigrationRegistry.register
class PythonOnlyMigration(BaseMigration):
    """Migrate from bash scripts to Python-only CLI commands.

    As of v0.10.0, all spec-kitty commands are available through the
    `spec-kitty agent` CLI namespace. Bash wrapper scripts in
    `.kittify/scripts/bash/` are superseded by Python implementations.

    This migration:
    1. Routes every ``.kittify/scripts/{bash,powershell}`` sweep through the
       asset-preservation guard. Scripts carry no version marker and the package
       no longer ships a canonical to byte-match, so ``CanonicalContentProver``
       returns ``None`` for all of them ⇒ **preserve-all** (charter L472:
       unprovable ⇒ preserve + warn). "owned-delete" is N/A — scripts have no
       ownership signal — so the guard leaves every script in place and names it.
    2. Updates slash command templates to use `spec-kitty agent` commands
    3. Routes worktree bash sweeps through the same guard (preserve-all)
    4. Routes the obsolete ``.kittify/scripts/tasks/`` directory through the guard
    5. Is idempotent (safe to run multiple times)
    """

    migration_id = "0.10.0_python_only"
    description = "Remove bash scripts and update templates to use Python CLI"
    target_version = "0.10.0"

    # Bash scripts that should be removed (package scripts only)
    PACKAGE_SCRIPTS = (
        "common.sh",
        "create-new-feature.sh",
        "check-prerequisites.sh",
        "setup-plan.sh",
        "update-agent-context.sh",
        "accept-feature.sh",
        "merge-feature.sh",
        "tasks-move-to-lane.sh",
        "tasks-list-lanes.sh",
        "mark-task-status.sh",
        "tasks-add-history-entry.sh",
        "tasks-rollback-move.sh",
        "validate-task-workflow.sh",
        "move-task-to-doing.sh",
    )

    # Bash → Python command mappings for template updates
    COMMAND_REPLACEMENTS = {
        # Feature management
        r"\.kittify/scripts/bash/create-new-feature\.sh": "spec-kitty agent mission create-feature",
        r"scripts/bash/create-new-feature\.sh": "spec-kitty agent mission create-feature",
        r"\.kittify/scripts/bash/check-prerequisites\.sh": "spec-kitty agent mission check-prerequisites",
        r"scripts/bash/check-prerequisites\.sh": "spec-kitty agent mission check-prerequisites",
        r"\.kittify/scripts/bash/setup-plan\.sh": "spec-kitty agent setup-plan",
        r"scripts/bash/setup-plan\.sh": "spec-kitty agent setup-plan",
        r"\.kittify/scripts/bash/update-agent-context\.sh": "spec-kitty agent update-context",
        r"scripts/bash/update-agent-context\.sh": "spec-kitty agent update-context",
        r"\.kittify/scripts/bash/accept-feature\.sh": "spec-kitty agent mission accept",
        r"scripts/bash/accept-feature\.sh": "spec-kitty agent mission accept",
        r"\.kittify/scripts/bash/merge-feature\.sh": "spec-kitty agent mission merge",
        r"scripts/bash/merge-feature\.sh": "spec-kitty agent mission merge",
        # Task workflow
        r"\.kittify/scripts/bash/tasks-move-to-lane\.sh": "spec-kitty agent move-task",
        r"scripts/bash/tasks-move-to-lane\.sh": "spec-kitty agent move-task",
        r"\.kittify/scripts/bash/tasks-list-lanes\.sh": "spec-kitty agent list-tasks",
        r"scripts/bash/tasks-list-lanes\.sh": "spec-kitty agent list-tasks",
        r"\.kittify/scripts/bash/mark-task-status\.sh": "spec-kitty agent mark-status",
        r"scripts/bash/mark-task-status\.sh": "spec-kitty agent mark-status",
        r"\.kittify/scripts/bash/tasks-add-history-entry\.sh": "spec-kitty agent add-history",
        r"scripts/bash/tasks-add-history-entry\.sh": "spec-kitty agent add-history",
        r"\.kittify/scripts/bash/tasks-rollback-move\.sh": "spec-kitty agent rollback-move",
        r"scripts/bash/tasks-rollback-move\.sh": "spec-kitty agent rollback-move",
        r"\.kittify/scripts/bash/validate-task-workflow\.sh": "spec-kitty agent validate-workflow",
        r"scripts/bash/validate-task-workflow\.sh": "spec-kitty agent validate-workflow",
        r"\.kittify/scripts/bash/move-task-to-doing\.sh": "spec-kitty agent move-task",
        r"scripts/bash/move-task-to-doing\.sh": "spec-kitty agent move-task",
        # Legacy tasks_cli.py references
        r"tasks_cli\.py move": "spec-kitty agent move-task",
        r"tasks_cli\.py list": "spec-kitty agent list-tasks",
        r"tasks_cli\.py mark": "spec-kitty agent mark-status",
        r"tasks_cli\.py history": "spec-kitty agent add-history",
        r"tasks_cli\.py rollback": "spec-kitty agent rollback-move",
        r"tasks_cli\.py validate": "spec-kitty agent validate-workflow",
    }

    def detect(self, project_path: Path) -> bool:
        """Check if bash scripts still exist in user's .kittify directory."""
        kittify_bash = project_path / ".kittify" / "scripts" / "bash"

        if not kittify_bash.exists():
            return False

        # Check if ANY .sh files exist (not just known scripts)
        # This catches custom scripts and ensures complete cleanup
        bash_scripts = list(kittify_bash.glob("*.sh"))
        return len(bash_scripts) > 0

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        """Migration can always be applied if bash scripts are detected."""
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Remove bash scripts and update templates."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Step 1: Detect and remove bash scripts from .kittify
        bash_changes, bash_warnings = self._remove_bash_scripts(project_path, dry_run)
        changes.extend(bash_changes)
        warnings.extend(bash_warnings)

        # Step 2: Clean up bash scripts in worktrees
        worktree_changes, worktree_warnings = self._cleanup_worktree_bash_scripts(project_path, dry_run)
        changes.extend(worktree_changes)
        warnings.extend(worktree_warnings)

        # Step 2.5: Remove obsolete task helpers
        tasks_changes, tasks_warnings = self._remove_tasks_helpers(project_path, dry_run)
        changes.extend(tasks_changes)
        warnings.extend(tasks_warnings)

        # Step 3: Update slash command templates
        template_changes, template_errors = self._update_command_templates(project_path, dry_run)
        changes.extend(template_changes)
        errors.extend(template_errors)

        # Note: the guard preserves every script in place (no ownership signal)
        # and names it in a warning, so no user script is ever deleted.

        success = len(errors) == 0
        return MigrationResult(
            success=success,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )

    def _preserve_scripts(
        self,
        scripts: list[Path],
        project_path: Path,
        *,
        changes: list[str],
        warnings: list[str],
        dry_run: bool,
    ) -> int:
        """Route each script through the asset-preservation guard; return the
        number preserved.

        Scripts carry no version marker (the marker is a markdown/HTML comment for
        command files, never injected into scripts) and the package no longer
        ships a canonical to byte-match (this migration exists *because* commands
        went Python-only). With no content signal, ``CanonicalContentProver``
        proves ``None`` for every script ⇒ the guard preserves it in place and
        names it — charter L472 (unprovable ⇒ preserve + warn). "owned-delete" is
        N/A here: there is no ownership signal for a script, so allowlisting these
        deletes would be dishonest (the base code deleted *custom* scripts).
        """
        prover = CanonicalContentProver()
        preserved = 0
        for script in scripts:
            verdict = guard_destructive_removal(script, project_path, prover=prover, dry_run=dry_run)
            if verdict.owned:
                changes.append(verdict.diagnostic)
            else:
                preserved += 1
                warnings.append(verdict.diagnostic)
        return preserved

    def _remove_bash_scripts(self, project_path: Path, dry_run: bool) -> tuple[list[str], list[str]]:
        """Route the .kittify bash/powershell script sweeps through the guard.

        Preserve-all: no script proves package-owned, so the guard leaves every
        one in place (parent survives) and names it in a warning.
        """
        changes: list[str] = []
        warnings: list[str] = []

        kittify_bash = project_path / ".kittify" / "scripts" / "bash"

        if not kittify_bash.exists():
            warnings.append("No .kittify/scripts/bash/ directory found - already migrated?")
            return changes, warnings

        preserved = self._preserve_scripts(
            sorted(kittify_bash.glob("*.sh")),
            project_path,
            changes=changes,
            warnings=warnings,
            dry_run=dry_run,
        )

        kittify_ps = project_path / ".kittify" / "scripts" / "powershell"
        if kittify_ps.exists():
            preserved += self._preserve_scripts(
                sorted(kittify_ps.glob("*.ps1")),
                project_path,
                changes=changes,
                warnings=warnings,
                dry_run=dry_run,
            )

        # Empty-directory cleanup fires only when the guard proved AND removed
        # every member (rmdir is empty-only — it raises on a non-empty directory,
        # so it can never silently drop content; see the WP09 rmdir allowlist
        # class). Under preserve-all the user's scripts remain, so these no-op.
        if not dry_run:
            if kittify_bash.exists() and not any(kittify_bash.iterdir()):
                kittify_bash.rmdir()
                changes.append("Removed empty: .kittify/scripts/bash/")
            if kittify_ps.exists() and not any(kittify_ps.iterdir()):
                kittify_ps.rmdir()
                changes.append("Removed empty: .kittify/scripts/powershell/")

        if preserved > 0:
            warnings.append(f"Preserved {preserved} unprovable script(s); left in place (no ownership signal)")
        else:
            warnings.append("No bash scripts found to remove - already migrated?")

        return changes, warnings

    def _cleanup_worktree_bash_scripts(self, project_path: Path, dry_run: bool) -> tuple[list[str], list[str]]:
        """Route worktree bash sweeps through the guard.

        ``.worktrees/*/.kittify/scripts/bash/*.sh`` is user content in the same
        hazard class as the ``:175`` sweep — a REQUIRED-route preserve-all, NOT a
        package-teardown allowlist. Every worktree script proves ``None`` and is
        preserved in place; the worktree bash dir is never emptied under
        preserve-all, so the empty-only rmdir below no-ops.
        """
        changes: list[str] = []
        warnings: list[str] = []

        worktrees_dir = project_path / ".worktrees"
        if not worktrees_dir.exists():
            return changes, warnings

        for worktree in sorted(worktrees_dir.iterdir()):
            if not worktree.is_dir():
                continue

            wt_bash = worktree / ".kittify" / "scripts" / "bash"
            if not wt_bash.exists():
                continue

            preserved = self._preserve_scripts(
                sorted(wt_bash.glob("*.sh")),
                project_path,
                changes=changes,
                warnings=warnings,
                dry_run=dry_run,
            )
            if not dry_run and wt_bash.exists() and not any(wt_bash.iterdir()):
                wt_bash.rmdir()
            if preserved > 0:
                warnings.append(f"Preserved {preserved} unprovable script(s) in worktree: {worktree.name}")

        return changes, warnings

    def _remove_tasks_helpers(self, project_path: Path, dry_run: bool) -> tuple[list[str], list[str]]:
        """Route the obsolete .kittify/scripts/tasks/ directory through the guard.

        Borderline B2: the same preserve-all rule as the ``:175``/``:187`` script
        sweeps. The task helpers carry no version marker and no shipped canonical,
        so ``CanonicalContentProver`` proves ``None`` for the directory ⇒ the guard
        preserves it in place rather than ``rmtree``-ing it (charter L472). An
        operator may remove the inert helpers manually.
        """
        changes: list[str] = []
        warnings: list[str] = []

        tasks_dir = project_path / ".kittify" / "scripts" / "tasks"
        if not tasks_dir.exists():
            return changes, warnings

        verdict = guard_destructive_removal(
            tasks_dir,
            project_path,
            prover=CanonicalContentProver(),
            is_tree=True,
            dry_run=dry_run,
        )
        if verdict.owned:
            changes.append(verdict.diagnostic)
        else:
            warnings.append(verdict.diagnostic)

        return changes, warnings

    def _update_command_templates(self, project_path: Path, dry_run: bool) -> tuple[list[str], list[str]]:
        """Update slash command templates to use Python CLI."""
        changes: list[str] = []
        errors: list[str] = []

        # Templates in .kittify/templates/command-templates/
        templates_dir = project_path / ".kittify" / "templates" / "command-templates"

        if not templates_dir.exists():
            # Templates not in expected location - might be from old package install
            # This is expected for projects initialized with older package versions
            # Templates will be fixed when they upgrade to v0.10.9+ which has repair migration
            changes.append(
                "Templates directory not found at .kittify/templates/command-templates/. "
                "This is expected for projects initialized with older package versions. "
                "Run 'spec-kitty upgrade' after upgrading to v0.10.9+ to repair templates."
            )
            return changes, []  # No errors, defer to repair migration

        templates_updated = 0
        for template_path in sorted(templates_dir.glob("*.md")):
            try:
                updated, replacements = self._update_template_file(template_path, dry_run)
                if updated:
                    templates_updated += 1
                    if dry_run:
                        changes.append(f"Would update: {template_path.name} ({replacements} replacements)")
                    else:
                        changes.append(f"Updated: {template_path.name} ({replacements} replacements)")
            except Exception as e:
                errors.append(f"Error updating {template_path.name}: {e}")

        if templates_updated > 0:
            changes.append(f"Total templates updated: {templates_updated}")

        return changes, errors

    def _update_template_file(self, template_path: Path, dry_run: bool) -> tuple[bool, int]:
        """Update a single template file with bash → Python replacements."""
        content = template_path.read_text(encoding="utf-8")
        original_content = content
        replacements_made = 0

        # Apply all replacements
        for pattern, replacement in self.COMMAND_REPLACEMENTS.items():
            new_content, count = re.subn(pattern, replacement, content)
            if count > 0:
                content = new_content
                replacements_made += count

        # Write if changes were made
        if content != original_content:
            if not dry_run:
                write_generated_file(template_path, content)
            return True, replacements_made

        return False, 0

    def _detect_custom_modifications(self, project_path: Path) -> list[str]:
        """Detect custom modifications to bash scripts."""
        warnings: list[str] = []

        kittify_bash = project_path / ".kittify" / "scripts" / "bash"
        if not kittify_bash.exists():
            return warnings

        # Look for non-standard scripts (not in PACKAGE_SCRIPTS)
        custom_scripts = []
        for script_path in kittify_bash.glob("*.sh"):
            if script_path.name not in self.PACKAGE_SCRIPTS:
                custom_scripts.append(script_path.name)

        if custom_scripts:
            warnings.append(f"Custom bash scripts detected: {', '.join(custom_scripts)}")
            warnings.append("These scripts will NOT be removed automatically. Please migrate them manually or remove if no longer needed.")

        return warnings
