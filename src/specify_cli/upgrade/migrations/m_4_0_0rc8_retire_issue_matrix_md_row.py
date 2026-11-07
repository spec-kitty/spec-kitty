"""Migration 4.0.0rc8: retire the stale ``issue-matrix.md`` merge-driver row (#7217).

``3.2.6_gate_artifact_merge_drivers`` seeds two gate-artifact rows, one of them
``kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix``. WP05
(``write-side-seam-matrix-tracer-01KYP3MH``, C-008) then moved the canonical artifact to
``issue-matrix.json``, and ``3.2.6_issue_matrix_driver_repoint`` added the ``.json`` row
**without** removing the old one.

The row is the wrong half, not the driver:

* no canonical path writes ``issue-matrix.md`` any more
  (``tests/architectural/test_issue_matrix_json_migration_completeness.py``), and
  ``_MERGE_DRIVERS`` declares only ``kitty-specs/**/issue-matrix.json`` for
  ``spec-kitty-issue-matrix``, so the row is an orphan drift the architectural guard rejects;
* ``spec-kitty merge-driver-issue-matrix`` merges the JSON ``rows`` array, so mapping a
  Markdown table onto it was never the fix.

The historical migration is ``clone_local_effect``: a fresh clone never carries its
``git config --local`` half, so ``detect()`` is True, it is re-selected and re-applied, and it
re-appends the retired row -- leaving a committed ``.gitattributes`` dirty on every clone
(#7174, #7217). A shipped migration is never edited (DIRECTIVE_044: its bytes are its
``content_hash``), so ``supersession.SUPERSEDED_MIGRATIONS`` replaces it with this migration,
which:

1. seeds the two gate-artifact rows that still route real artifacts
   (``acceptance-matrix.json``, ``issue-matrix.json``) with their canonical driver names -- the
   half of the superseded migration that is the #2804 fix and must survive the retirement;
2. removes the retired ``.md`` row wherever an earlier run already wrote it, line-exactly and
   idempotently.

A project whose ``.gitattributes`` is already correct is left byte-identical: that is what makes
the first upgrade on a fresh clone a no-op for the tracked file.

Scope limit: the superseded migration is now a recorded no-op at any target, while this
successor targets ``4.0.0rc8``. An upgrade capped below that (``spec-kitty upgrade --target
3.2.6rc1``) therefore seeds neither gate-artifact driver; the next upgrade to the installed
version does.
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from ._merge_driver_seeding import DriverSpec, MergeDriverSeedingMigration
from .base import MigrationResult

#: The retired mapping: no canonical writer, no declared driver pattern, JSON-only driver.
RETIRED_ENTRY = "kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix"

_DRIVERS: tuple[DriverSpec, ...] = (
    DriverSpec(
        config_key="spec-kitty-acceptance-matrix",
        name="Spec Kitty acceptance matrix filled-side merge",
        command="spec-kitty merge-driver-acceptance-matrix %O %A %B",
        pattern="kitty-specs/**/acceptance-matrix.json",
    ),
    DriverSpec(
        config_key="spec-kitty-issue-matrix",
        name="Spec Kitty issue matrix row-aware merge",
        command="spec-kitty merge-driver-issue-matrix %O %A %B",
        pattern="kitty-specs/**/issue-matrix.json",
    ),
)


def _retired_row_present(project_path: Path) -> bool:
    attributes_path = project_path / ".gitattributes"
    if not attributes_path.exists():
        return False
    return any(line.strip() == RETIRED_ENTRY for line in attributes_path.read_text(encoding="utf-8").splitlines())


def _without_retired_row(project_path: Path) -> int:
    """Drop every line whose stripped text is the retired mapping; return how many went.

    Only that one mapping is removed. Every other line keeps its bytes, line ending included
    (a CRLF file stays CRLF), and a file without the row is not rewritten at all.
    """
    attributes_path = project_path / ".gitattributes"
    lines = attributes_path.read_bytes().decode("utf-8").splitlines(keepends=True)
    kept = [line for line in lines if line.strip() != RETIRED_ENTRY]
    if len(kept) == len(lines):
        return 0
    attributes_path.write_bytes("".join(kept).encode("utf-8"))
    return len(lines) - len(kept)


@MigrationRegistry.register
class RetireIssueMatrixMdRowMigration(MergeDriverSeedingMigration):
    """Keep both ``.json`` gate-artifact drivers and retire the stale ``issue-matrix.md`` row."""

    migration_id = "4.0.0rc8_retire_issue_matrix_md_row"
    description = "Retire the stale issue-matrix.md merge-driver row and keep the .json gate-artifact drivers"
    target_version = "4.0.0rc8"
    drivers = _DRIVERS
    dry_run_summary = "Would install the gate-artifact merge drivers and remove the retired issue-matrix.md row"

    def detect(self, project_path: Path) -> bool:
        return super().detect(project_path) or _retired_row_present(project_path)

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        if dry_run:
            changes: list[str] = []
            if super().detect(project_path):
                changes.append(self.dry_run_summary)
            if _retired_row_present(project_path):
                changes.append(f"Would remove .gitattributes entry: {RETIRED_ENTRY}")
            return MigrationResult(success=True, changes_made=changes)

        seeded = super().apply(project_path, dry_run=False)
        if not seeded.success:
            return seeded
        changes = list(seeded.changes_made)
        removed = _without_retired_row(project_path)
        if removed:
            changes.append(f"Removed .gitattributes entry: {RETIRED_ENTRY}")
        return MigrationResult(success=True, changes_made=changes, warnings=list(seeded.warnings))
