"""Migration 3.2.0rc35: normalize branch-intent terminology in generated command files.

Older generated slash-command files may still use:
- ``project root checkout``
- ``main repository root`` / ``main repository`` / ``main repo``
- mission-specific wording that teaches planning or task generation "in main"

The current canon distinguishes checkout location from branch choice:
- use ``repository root checkout`` for the non-worktree planning location
- use explicit branch terms (current/target/planning_base_branch/merge_target_branch)

This migration updates already-generated agent command files in-place so users do
not have to reinstall commands manually to get the corrected terminology.
"""

from __future__ import annotations

import logging
from pathlib import Path

from specify_cli.runtime.generated_writer import write_generated_file

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project

logger = logging.getLogger(__name__)

_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (
        "Planning happens in main for ALL missions.",
        "Planning happens in the repository root checkout for all missions. The mission target branch comes from branch-context.",
    ),
    (
        "Task generation happens in main for ALL missions.",
        "Task generation happens in the repository root checkout for all missions and commits to the mission's target branch.",
    ),
    ("project root checkout root", "repository root checkout"),
    ("Project root checkout root", "Repository root checkout"),
    ("main repository root", "repository root checkout"),
    ("Main repository root", "Repository root checkout"),
    ("project root checkout", "repository root checkout"),
    ("Project root checkout", "Repository root checkout"),
    ("main repository", "repository root checkout"),
    ("Main repository", "Repository root checkout"),
    ("main repo", "repository root checkout"),
    ("Main repo", "Repository root checkout"),
)

_DETECTION_MARKERS: tuple[str, ...] = (
    "project root checkout",
    "main repository root",
    "main repository",
    "main repo",
    "Planning happens in main for ALL missions.",
    "Task generation happens in main for ALL missions.",
)


def _agent_command_files(project_path: Path) -> list[Path]:
    files: list[Path] = []
    for agent_root, command_subdir in get_agent_dirs_for_project(project_path):
        cmd_dir = project_path / agent_root / command_subdir
        if not cmd_dir.is_dir():
            continue
        files.extend(sorted(cmd_dir.glob("spec-kitty.*.md")))
    return files


def _needs_fix(project_path: Path) -> list[Path]:
    hits: list[Path] = []
    for md_file in _agent_command_files(project_path):
        try:
            content = md_file.read_text(encoding="utf-8")
        except OSError:
            continue
        lowered = content.lower()
        if any(marker.lower() in lowered for marker in _DETECTION_MARKERS):
            hits.append(md_file)
    return hits


@MigrationRegistry.register
class RepositoryRootCheckoutTerminologyMigration(BaseMigration):
    """Normalize checkout-vs-branch terminology in generated command files."""

    migration_id = "3.2.0rc35_repository_root_checkout_terminology"
    description = (
        "Replace stale 'project root checkout' and generic 'main repository' "
        "phrasing in generated command files with the canonical "
        "'repository root checkout' terminology"
    )
    target_version = "3.2.0rc35"

    def detect(self, project_path: Path) -> bool:
        return len(_needs_fix(project_path)) > 0

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        hits = _needs_fix(project_path)
        if hits:
            return True, ""
        return False, "No generated command files need repository-root terminology updates"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        hits = _needs_fix(project_path)
        if not hits:
            return MigrationResult(success=True, changes_made=["No files needed updating"])

        from specify_cli.asset_preservation.guard import guard_destructive_overwrite
        from specify_cli.asset_preservation.provers import CanonicalContentProver

        prover = CanonicalContentProver()
        changed: list[str] = []
        preserved: list[str] = []
        warnings: list[str] = []
        for md_file in hits:
            try:
                content = md_file.read_text(encoding="utf-8")
                original = content
                for old, new in _REPLACEMENTS:
                    content = content.replace(old, new)
                if content == original:
                    continue

                rel = str(md_file.relative_to(project_path))
                # A matched phrase in a ``spec-kitty.*`` file is NOT proof of
                # package ownership: a user-authored custom command that merely
                # mentions e.g. "main repo" must not have its bytes rewritten
                # (charter "User Customization Preservation", #6247). Gate the
                # in-place overwrite on the canonical chokepoint: only a file
                # whose version marker proves it is package-generated is
                # rewritten; an unproven file is preserved and reported.
                verdict = guard_destructive_overwrite(
                    md_file,
                    project_path,
                    replacement_substantive=True,
                    authorized=False,
                    prover=prover,
                )
                if not verdict.proceed:
                    preserved.append(rel)
                    warnings.append(verdict.diagnostic)
                    logger.info("%s", verdict.diagnostic)
                    continue

                if not dry_run:
                    # Agent command files are left read-only by the
                    # generation layer; write_generated_file restores the
                    # write bit before writing so a previously-generated
                    # file does not raise PermissionError (#3651), and
                    # leaves it read-only again afterward.
                    write_generated_file(md_file, content, read_only=True)
                changed.append(rel)
                logger.info("Updated: %s", rel)
            except OSError as exc:
                logger.warning("Could not update %s: %s", md_file, exc)

        summary = "Updated generated command files to use 'repository root checkout' terminology"
        return MigrationResult(
            success=True,
            changes_made=changed or [summary],
            warnings=warnings,
            preserved_paths=preserved,
            manual_review_required=bool(preserved),
        )
