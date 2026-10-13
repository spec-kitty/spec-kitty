"""Migration 3.2.0: Move Codex from .codex/prompts/ to .agents/skills/.

Before 3.2.0 Spec Kitty wrote command prompt files for Codex into
``.codex/prompts/spec-kitty.<command>.md``.  Starting with 3.2.0, the Codex
integration is delivered as Agent Skills packages under
``.agents/skills/spec-kitty.<command>/SKILL.md`` — the same layout used by the
Vibe agent.

This migration:
1. No-ops when ``codex`` is absent from ``agents.available`` in
   ``.kittify/config.yaml``.
2. Installs the new ``.agents/skills/`` packages via
   :func:`specify_cli.skills.command_installer.install`.
3. Removes every ``.codex/prompts/spec-kitty.<command>.md`` file whose basename
   is in :data:`._legacy_codex_hashes.LEGACY_CODEX_FILENAMES` (owned files).
4. Leaves any other files in ``.codex/prompts/`` untouched (third-party).
5. Removes ``.codex/prompts/`` itself if it is empty after cleanup.  The
   ``.codex/`` directory is **never** touched.

Hash-comparison simplification
--------------------------------
This migration uses filename-only classification (Option A).  It does not
compare SHA-256 digests against pre-3.2 known hashes.  Any
``spec-kitty.<command>.md`` file — regardless of whether it has been edited —
is treated as owned and deleted after the new skills are installed.

Users who have hand-edited these files should stash them before running
``spec-kitty upgrade``.  See :mod:`._legacy_codex_hashes` for the full
rationale.

Non-recursive scope
-------------------
Only ``.md`` files directly inside ``.codex/prompts/`` are inspected.  The
pre-3.2 renderer never produced nested subdirectories, so recursive search is
unnecessary and is intentionally omitted.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from ._legacy_codex_hashes import LEGACY_CODEX_FILENAMES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classifier dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegacyCodexPrompt:
    """Represents a single ``.codex/prompts/*.md`` file and its classification.

    Attributes
    ----------
    path:
        Absolute path to the file.
    current_hash:
        SHA-256 hex digest of the file as it currently exists on disk.
        Empty string if the file could not be read.
    previous_version_hash:
        ``None`` — hash comparison is not performed in this migration
        (Option A simplification; see module docstring).
    status:
        ``"owned_unedited"`` if the filename is in
        :data:`LEGACY_CODEX_FILENAMES` (will be deleted after install).
        ``"third_party"`` otherwise (left untouched).
        ``"owned_edited"`` is unused in the Option-A implementation but
        retained in the type for forward-compatibility.
    """

    path: Path
    current_hash: str
    previous_version_hash: str | None
    status: Literal["owned_unedited", "owned_edited", "third_party"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _compute_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of *path*, or empty string on error."""
    import hashlib  # noqa: PLC0415

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()  # noqa: TID251 - production raw SHA-256 owner
    except OSError:
        return ""


def _classify(prompts_dir: Path) -> list[LegacyCodexPrompt]:
    """Enumerate direct ``.md`` children of *prompts_dir* and classify each.

    Only non-recursive, direct children are examined.  This matches the layout
    produced by the pre-3.2 renderer, which never nested files.
    """
    results: list[LegacyCodexPrompt] = []
    for child in prompts_dir.iterdir():
        if not child.is_file() or child.suffix != ".md":
            continue
        if child.name in LEGACY_CODEX_FILENAMES:
            status: Literal["owned_unedited", "owned_edited", "third_party"] = (
                "owned_unedited"
            )
        else:
            status = "third_party"
        results.append(
            LegacyCodexPrompt(
                path=child,
                current_hash=_compute_hash(child),
                previous_version_hash=None,
                status=status,
            )
        )
    return results


def _install_skills(project_path: Path) -> list[str]:
    """Install ``.agents/skills/`` packages for the ``codex`` agent.

    Returns one notice line per drifted command skill the installer regenerated (#6155).
    """
    from specify_cli.skills import command_installer  # noqa: PLC0415
    from specify_cli.tool_surface.repair import render_regenerated_surface_lines

    report = command_installer.install(project_path, "codex")
    return render_regenerated_surface_lines(report.regenerated)


def _print_preservation_notice(preserved: list[LegacyCodexPrompt]) -> None:
    """Emit a notice to stderr listing files that were left untouched.

    The message is intentionally plain text so that grep-based CI does not
    mistake it for an error.
    """
    lines = [
        "spec-kitty upgrade notice: the following .codex/prompts/ files were "
        "left untouched because they are not Spec Kitty-owned files:",
    ]
    for p in preserved:
        lines.append(f"  • {p.path}")
    lines.append(
        "Your Codex integration now reads from .agents/skills/; "
        "these files will not be invoked automatically."
    )
    print("\n".join(lines), file=sys.stderr)


def _print_superseded_notice(superseded: list[Path]) -> None:
    """Tell the user where their former ``.codex/prompts/spec-kitty.*.md`` files live.

    The migration deliberately does not delete these files because the spec's
    Edge Cases clause forbids silently discarding user edits. Instead it moves
    them out of Codex's active discovery path to ``.codex/prompts.superseded/``
    so the user can review and port any customizations.
    """
    lines = [
        "spec-kitty upgrade notice: Codex now reads slash commands from "
        ".agents/skills/ (Agent Skills).",
        "Your former Codex prompt files have been moved to ",
        ".codex/prompts.superseded/ — they are preserved so you can review and ",
        "port any hand edits into the new .agents/skills/spec-kitty.<command>/ ",
        "packages. Delete .codex/prompts.superseded/ when you are done.",
        "",
        "Preserved files:",
    ]
    for target in superseded:
        lines.append(f"  • {target}")
    print("\n".join(lines), file=sys.stderr)


def _move_owned_prompts(
    owned: list[LegacyCodexPrompt],
    superseded_dir: Path,
) -> tuple[list[Path], list[str]]:
    """Move owned ``.codex/prompts/`` files to the superseded directory.

    Creates *superseded_dir* if needed, moves each owned file atomically, and
    handles idempotency: if the target already exists (a previous run completed
    partially) the source copy is simply removed.

    Returns:
        A pair ``(moved, move_errors)`` where *moved* is the list of
        successfully relocated paths and *move_errors* collects per-file error
        messages for files that could not be moved.
    """
    moved: list[Path] = []
    move_errors: list[str] = []

    try:
        superseded_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        move_errors.append(f"Could not create .codex/prompts.superseded/: {exc}")
        return moved, move_errors

    for p in owned:
        target = superseded_dir / p.path.name
        # Idempotency: if a previous run already moved this file, the target
        # already exists — remove the stale active-path copy instead of
        # overwriting the preserved one.
        if target.exists():
            try:
                p.path.unlink()
            except OSError as exc:
                move_errors.append(f"{p.path.name}: {exc}")
            continue
        try:
            p.path.rename(target)
            moved.append(target)
        except OSError as exc:
            move_errors.append(f"{p.path.name}: {exc}")

    return moved, move_errors


def _try_remove_empty_prompts_dir(prompts_dir: Path) -> tuple[bool, str | None]:
    """Remove *prompts_dir* if it is empty after the migration.

    Returns:
        ``(removed, warning)`` — *removed* is ``True`` if the directory was
        deleted; *warning* is set to an error message on ``OSError``, else
        ``None``.
    """
    if not prompts_dir.exists():
        return False, None
    try:
        remaining = list(prompts_dir.iterdir())
        if not remaining:
            prompts_dir.rmdir()
            return True, None
    except OSError as exc:
        return False, f"Could not remove .codex/prompts/ directory: {exc}"
    return False, None


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


@MigrationRegistry.register
class CodexToSkillsMigration(BaseMigration):
    """Move Codex from .codex/prompts/ to .agents/skills/ (Agent Skills)."""

    migration_id = "3.2.0rc35_codex_to_skills"
    description = "Move Codex from .codex/prompts/ to .agents/skills/ (Agent Skills)"
    target_version = "3.2.0rc35"

    def detect(self, project_path: Path) -> bool:
        """Return True if legacy .codex/prompts/spec-kitty.*.md files exist."""
        prompts_dir = project_path / ".codex" / "prompts"
        if not prompts_dir.is_dir():
            return False
        return any(
            f.name in LEGACY_CODEX_FILENAMES
            for f in prompts_dir.iterdir()
            if f.is_file()
        )

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check that .kittify/ exists (project is initialized)."""
        kittify = project_path / ".kittify"
        if not kittify.is_dir():
            return False, ".kittify/ directory does not exist (not initialized)"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Apply the Codex → Agent Skills migration.

        Parameters
        ----------
        project_path:
            Root of the project (contains ``.kittify/``, ``.codex/``, etc.).
        dry_run:
            If ``True``, report what *would* happen without touching the
            filesystem or the manifest.
        """
        from specify_cli.core.agent_config import load_agent_config  # noqa: PLC0415

        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # --- No-op guard (T032) -----------------------------------------------
        try:
            agent_config = load_agent_config(project_path)
        except Exception as exc:
            errors.append(f"Could not load agent config: {exc}")
            return MigrationResult(success=False, errors=errors)

        if "codex" not in agent_config.available:
            logger.debug(
                "Skipping CodexToSkillsMigration: codex not in agents.available"
            )
            return MigrationResult(success=True, changes_made=[], warnings=[], errors=[])

        # --- Classify existing .codex/prompts/ files --------------------------
        prompts_dir = project_path / ".codex" / "prompts"
        classified: list[LegacyCodexPrompt] = []

        if prompts_dir.exists():
            classified = _classify(prompts_dir)

        owned = [p for p in classified if p.status == "owned_unedited"]
        third_party = [p for p in classified if p.status == "third_party"]

        # --- Install new .agents/skills/ packages ----------------------------
        if dry_run:
            return self._apply_dry_run(changes, warnings, errors, owned, third_party)

        try:
            regenerated_lines = _install_skills(project_path)
            changes.append(
                "Installed 11 Codex skill packages under .agents/skills/"
            )
            changes.extend(regenerated_lines)
        except Exception as exc:
            errors.append(f"Skill installation failed: {exc}")
            return MigrationResult(
                success=False, changes_made=changes, warnings=warnings, errors=errors
            )

        # --- Preserve owned files (do NOT silently delete) --------------------
        # Spec §Edge Cases: "Upgrade must not silently discard [user] edits
        # without either migrating them into the new skill or surfacing them
        # to the user; at minimum the old files must be preserved ... so a
        # user who edited them can recover."
        #
        # We move every spec-kitty-named file from .codex/prompts/ to
        # .codex/prompts.superseded/ so that:
        #   1. The file is removed from Codex's active discovery path
        #      (Codex no longer reads from there after this release).
        #   2. The original content is intact on disk for the user to review
        #      or port any customizations into .agents/skills/.
        #   3. A single notice lists every preserved file so the user knows
        #      where to look.
        if owned:
            superseded_dir = prompts_dir.parent / "prompts.superseded"
            moved, move_errors = _move_owned_prompts(owned, superseded_dir)
            if move_errors and not moved:
                # Could not even create the superseded dir — fatal.
                errors.extend(move_errors)
                return MigrationResult(
                    success=False, changes_made=changes, warnings=warnings, errors=errors
                )
            if moved:
                changes.append(
                    f"Moved {len(moved)} superseded Codex prompt(s) from .codex/prompts/ "
                    f"to .codex/prompts.superseded/ (new skill packages live in .agents/skills/)"
                )
                _print_superseded_notice(moved)
            if move_errors:
                warnings.append(
                    "Could not move some .codex/prompts/ files: " + "; ".join(move_errors)
                )

        # --- Notify about third-party files -----------------------------------
        if third_party:
            _print_preservation_notice(third_party)
            warnings.append(
                f"Preserved {len(third_party)} third-party file(s) in .codex/prompts/"
            )

        # --- Remove prompts dir if empty -------------------------------------
        removed, rm_warning = _try_remove_empty_prompts_dir(prompts_dir)
        if removed:
            changes.append("Removed empty .codex/prompts/ directory")
        if rm_warning:
            warnings.append(rm_warning)

        return MigrationResult(
            success=True, changes_made=changes, warnings=warnings, errors=errors
        )

    @staticmethod
    def _apply_dry_run(
        changes: list[str],
        warnings: list[str],
        errors: list[str],
        owned: list[LegacyCodexPrompt],
        third_party: list[LegacyCodexPrompt],
    ) -> MigrationResult:
        """Return a dry-run :class:`MigrationResult` without touching the filesystem."""
        changes.append(
            "Would install 11 Codex skill packages under .agents/skills/"
        )
        changes.append(
            f"Would delete {len(owned)} owned .codex/prompts/ file(s)"
        )
        if third_party:
            warnings.append(
                f"Would preserve {len(third_party)} third-party file(s): "
                + ", ".join(p.path.name for p in third_party)
            )
        return MigrationResult(
            success=True, changes_made=changes, warnings=warnings, errors=errors
        )
