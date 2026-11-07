"""Project-stamped successor of the 3.1.2 command-globalization migration (#6954).

``3.1.2_globalize_commands`` is shipped and byte-frozen (DIRECTIVE_044). Its
registry entry is superseded by this migration, which keeps the shipped safety
rules while classifying a stamped project without consulting the operator's
home. The shipped module is imported as an alias so auto-discovery can reload
this successor after ``MigrationRegistry.clear()``.
"""

from __future__ import annotations

from pathlib import Path

from packaging.version import InvalidVersion, Version

from specify_cli.asset_preservation import CanonicalContentProver, guard_destructive_removal
from specify_cli.tool_surface.operations import OwnershipProof

from ..metadata import ProjectMetadata
from ..registry import MigrationRegistry
from . import m_3_1_2_globalize_commands as _shipped
from .base import MigrationResult

PREDECESSOR_ID = "3.1.2_globalize_commands"


def _agent_key_for_root(agent_root: str) -> str | None:
    """Return the agent key for a command-dir root, or ``None`` when it has none."""
    try:
        from specify_cli.agent_utils.directories import AGENT_DIR_TO_KEY  # noqa: PLC0415
    except Exception:
        return None
    key = AGENT_DIR_TO_KEY.get(agent_root)
    return key if isinstance(key, str) else None


class _EmptyDirectoryProver:
    """Prove that an agent command directory is empty and has no symlink identity."""

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:
        if path.is_symlink() or not path.is_dir() or any(path.iterdir()):
            return None
        return OwnershipProof("managed_path", f"empty-command-dir:{path.relative_to(project_path).as_posix()}")


@MigrationRegistry.register
class StampGlobalizeCommandsMigration(_shipped.GlobalizeCommandsMigration):
    """Remove generated project-local commands based on the project's own stamp."""

    migration_id = "4.0.0rc8_stamp_globalize_commands"
    description = "Remove generated project-local command files using the project stamp, not the operator home"
    target_version = "4.0.0rc8"
    predecessor_id = PREDECESSOR_ID

    @staticmethod
    def _global_command_file_present(agent_root: str, subdir: str, filename: str) -> bool:
        """Ask the canonical owner for the exact global replacement file."""
        agent_key = _agent_key_for_root(agent_root)
        if agent_key is not None:
            try:
                from specify_cli.runtime.agent_commands import (  # noqa: PLC0415
                    get_global_command_dir,
                )

                return bool((get_global_command_dir(agent_key) / filename).is_file())
            except Exception:
                return False
        try:
            global_agent_dir = Path.home() / agent_root / subdir
        except Exception:
            return False
        return (global_agent_dir / filename).is_file()

    def _is_past_globalization_boundary(self, project_path: Path) -> bool:
        """Return whether the project stamp is past the shipped globalization boundary."""
        metadata = ProjectMetadata.load(project_path / ".kittify")
        if metadata is None:
            return False
        try:
            boundary = _shipped.GlobalizeCommandsMigration.target_version
            return Version(metadata.version) >= Version(boundary)
        except (InvalidVersion, TypeError):
            return False

    def _classify(
        self,
        *,
        target: Path,
        agent_root: str,
        subdir: str,
        runtime_present: bool,
        globalized: bool = False,
    ) -> tuple[str, str]:
        """Classify one command file, bypassing machine evidence for a stamped project."""
        if globalized and self._is_generated_file(target):
            return _shipped._REMOVE, ""
        return super()._classify(
            target=target,
            agent_root=agent_root,
            subdir=subdir,
            runtime_present=runtime_present,
        )

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        changes: list[str] = []
        warnings: list[str] = []
        preserved_paths: list[str] = []
        globalized = self._is_past_globalization_boundary(project_path)
        runtime_present = True if globalized else self._global_runtime_present()
        verb_keep = "Would keep" if dry_run else "Kept"

        for agent_root, subdir in self._iter_agent_command_dirs(project_path):
            agent_dir = project_path / agent_root / subdir
            if not agent_dir.is_dir():
                continue

            targets = sorted(candidate for candidate in agent_dir.iterdir() if candidate.name.startswith("spec-kitty."))
            for target in targets:
                rel = self._rel(target, project_path)
                action, reason = self._classify(
                    target=target,
                    agent_root=agent_root,
                    subdir=subdir,
                    runtime_present=runtime_present,
                    globalized=globalized,
                )
                if action == _shipped._HOLD:
                    self._preserve(
                        changes=changes,
                        preserved_paths=preserved_paths,
                        rel=rel,
                        reason=reason,
                        dry_run=dry_run,
                    )
                    continue
                if action == _shipped._KEEP:
                    changes.append(f"{verb_keep}: {rel} (generated; {reason})")
                    continue

                if dry_run:
                    changes.append(f"Would remove: {rel}")
                    continue

                try:
                    verdict = guard_destructive_removal(target, project_path, prover=CanonicalContentProver())
                except OSError as exc:
                    changes.append(f"Kept: {rel} (generated; unlink failed: {exc})")
                    warnings.append(f"Could not remove {rel}: {exc}")
                else:
                    if verdict.owned:
                        changes.append(f"Removed: {rel}")
                    else:
                        changes.append(f"Kept: {rel} (generated; {verdict.reason})")
                        warnings.append(verdict.diagnostic)

            if not dry_run and agent_dir.is_dir():
                try:
                    verdict = guard_destructive_removal(agent_dir, project_path, prover=_EmptyDirectoryProver())
                except OSError as exc:
                    warnings.append(f"Could not remove empty directory {self._rel(agent_dir, project_path)}: {exc}")
                else:
                    if verdict.owned:
                        changes.append(f"Removed empty directory: {self._rel(agent_dir, project_path)}")

        return MigrationResult(
            success=True,
            changes_made=changes,
            warnings=warnings,
            manual_review_required=bool(preserved_paths),
            preserved_paths=preserved_paths,
        )
