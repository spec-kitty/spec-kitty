"""Residue-aware successor of the 3.1.1 ``status.json`` normalisation (#6669).

``3.1.1_normalize_status_json`` is a shipped, byte-frozen migration
(DIRECTIVE_044). It rewrites the ``status.json`` of every ``kitty-specs/``
child, including a residue folder that is not a Mission. It is listed in
``SUPERSEDED_MIGRATIONS``; this successor re-walks the project over the frozen
``_needs_normalisation`` check and leaves residue untouched.

Only the module-level helper is imported from the shipped module, never its
migration class (see ``m_2_0_6_residue_safe_consistency_sweep`` for why).
"""

from __future__ import annotations

import json
from pathlib import Path

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.status import SNAPSHOT_FILENAME, read_events, reduce

from ..registry import MigrationRegistry
from ._residue_successor import partition_kitty_specs, predecessor_settled, residue_warnings
from .base import BaseMigration, MigrationResult
from .m_3_1_1_normalize_status_json import _needs_normalisation

PREDECESSOR_ID = "3.1.1_normalize_status_json"


def _normalise_one(mission_dir: Path, dry_run: bool) -> str | None:
    """Normalise one Mission's ``status.json``; return the change line, or ``None`` when it needs none."""
    status_path = mission_dir / SNAPSHOT_FILENAME
    if not status_path.exists() or not _needs_normalisation(mission_dir):
        return None
    if dry_run:
        return f"{mission_dir.name}: would normalise status.json"
    current = json.loads(status_path.read_text(encoding="utf-8"))
    snapshot = reduce(read_events(mission_dir))
    current["materialized_at"] = snapshot.materialized_at
    # Residue-safe successor of the frozen 3.1.1 writer: same bytes.
    status_path.write_text(
        json.dumps(current, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return f"{mission_dir.name}: normalised status.json"


@MigrationRegistry.register
class ResidueSafeNormalizeStatusJsonMigration(BaseMigration):
    """Normalise status.json files to a deterministic materialized_at, leaving residue folders alone."""

    migration_id = "3.1.1_residue_safe_normalize_status_json"
    description = (
        "Residue-safe status.json normalisation: replace wall-clock materialized_at with a deterministic value (issue #524), never in a kitty-specs/ residue folder"
    )
    target_version = "3.1.1"

    def detect(self, project_path: Path) -> bool:
        """True when any Mission's status.json is out of date."""
        if predecessor_settled(project_path, PREDECESSOR_ID):
            return False
        kitty_specs = project_path / KITTY_SPECS_DIR
        missions, _residue = partition_kitty_specs(kitty_specs, project_path)
        return any(_needs_normalisation(mission_dir) for mission_dir in missions)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if (project_path / KITTY_SPECS_DIR).exists() or (project_path / ".kittify").exists():
            return True, ""
        return False, "No kitty-specs/ directory found"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        changes: list[str] = []
        errors: list[str] = []

        kitty_specs = project_path / KITTY_SPECS_DIR
        missions, residue = partition_kitty_specs(kitty_specs, project_path)
        for mission_dir in missions:
            try:
                change = _normalise_one(mission_dir, dry_run)
            except Exception as exc:
                errors.append(f"{mission_dir.name}: {exc}")
                continue
            if change is not None:
                changes.append(change)

        return MigrationResult(
            success=not errors,
            changes_made=changes,
            warnings=residue_warnings(residue, project_path),
            errors=errors,
        )
