"""Migration ``verdict_provenance_backfill``: wire the FR-012 / SC-008 backfill.

Realises the operational half of ``verdict-seam-write-unification-01KZ9Q35``:
the mission collapsed every verdict reader onto the event authority
(``status.events.jsonl``) and deleted the ``review-cycle-N.md`` frontmatter
readers -- the *irreversible* half of single-authority. The protective
backfill (:func:`~specify_cli.migration.verdict_provenance_backfill.
backfill_verdict_provenance`, SC-008) that reduces a pre-schema-change
terminal ``.md`` verdict into a hand-constructed ``review_result`` event
already existed but had **zero production callers**: an existing deployment
upgrading across the reader collapse could strand a historical rejection
(a WP with a terminal ``.md`` verdict and no event ``review_result`` slot),
so a consumer reading the retired authority mid-upgrade would miss it.

This module is that caller. It is an *auto-discovered* upgrade migration
(``@MigrationRegistry.register`` + ``pkgutil.iter_modules`` -- no static
importer) that runs the backfill over **every** mission under
``kitty-specs/`` on ``spec-kitty upgrade``.

Reuse, not re-implementation
----------------------------
The one and only backfill spine lives in
:func:`specify_cli.migration.verdict_provenance_backfill.backfill_verdict_provenance`.
This module adds only the corpus walk; it never touches the write path itself.
The backfill refreshes an already-existing ``status.json`` after an append
(#5869); a refresh failure is surfaced here as a ``MigrationResult`` warning
(the append is committed, so ``success`` stays ``True``).
The provenance predicate
(:func:`~specify_cli.migration.verdict_provenance_backfill.stranded_verdict_findings`)
drives :meth:`detect` / the dry-run preview so the migration is a true no-op
on a corpus with nothing to recover.

Idempotency (NFR-002)
---------------------
``backfill_verdict_provenance`` is idempotent by construction: it keys each
seeded event on a deterministic ULID over ``(mission_id, wp_id, verdict,
cycle)`` and skips any WP that already carries a ``review_result`` event
slot. A second ``apply()`` over an unchanged corpus therefore appends
nothing (``appended_count == 0`` for every mission) -- ``detect()`` returns
``False`` once the corpus is converged, and even a forced re-run is a no-op.

Version-key ordering
--------------------
``target_version = "3.2.6rc1"`` -- tied to the installed package version
(``pyproject.toml``), the same still-unreleased cycle as the sibling
``m_zz_runtime_state_backfill.py``. The ``m_zz_`` filename prefix keeps this
module importing (and registering) after the ``m_unify_charter_activation*``
charter folds at the same tied version, exactly as its runtime-state sibling
documents -- ordering between the two ``m_zz_*`` backfills is immaterial (they
touch disjoint on-disk state). The semantic identifier stays on
``migration_id`` below.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.migration.verdict_provenance_backfill import (
    backfill_verdict_provenance,
    stranded_verdict_findings,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

#: Corpus root, relative to the project root -- the canonical enumeration
#: mirrors ``m_zz_runtime_state_backfill``'s ``_iter_mission_dirs``: no
#: divergent glob.
_KITTY_SPECS_DIRNAME = "kitty-specs"


def _iter_mission_dirs(project_path: Path) -> list[Path]:
    """Return every mission directory under ``kitty-specs/``, sorted by name.

    Mirrors :func:`specify_cli.upgrade.migrations.m_zz_runtime_state_backfill._iter_mission_dirs`
    exactly. Returns ``[]`` when ``kitty-specs/`` is absent (fresh install).
    """
    kitty_specs = project_path / _KITTY_SPECS_DIRNAME
    if not kitty_specs.is_dir():
        return []
    return sorted(entry for entry in kitty_specs.iterdir() if entry.is_dir())


@MigrationRegistry.register
class VerdictProvenanceBackfillMigration(BaseMigration):
    """Auto-discovered corpus backfill of verdict provenance (FR-012, SC-008).

    Runs :func:`~specify_cli.migration.verdict_provenance_backfill.
    backfill_verdict_provenance` over every mission under ``kitty-specs/``, in
    sorted order, reducing any stranded terminal ``.md`` verdict into a
    ``review_result`` event so the event authority is complete before a
    consumer reads it. No-ops on a fresh install (no ``kitty-specs/``) and on
    an already-converged corpus (idempotent, NFR-002).
    """

    migration_id = "verdict_provenance_backfill"
    description = (
        "Backfill each kitty-specs/ mission's stranded terminal review-cycle "
        ".md verdict into status.events.jsonl as a hand-constructed "
        "review_result event, so the event authority is complete after the "
        "verdict-reader collapse (FR-012, SC-008). Idempotent."
    )
    target_version = "3.2.6rc1"
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        """True while at least one mission still carries a stranded verdict."""
        return any(
            stranded_verdict_findings(mission)
            for mission in _iter_mission_dirs(project_path)
        )

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "no stranded verdict provenance found under kitty-specs/"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        missions = _iter_mission_dirs(project_path)
        if not missions:
            return MigrationResult(success=True, changes_made=[])
        if dry_run:
            return MigrationResult(
                success=True,
                changes_made=self._dry_run_summary(missions),
            )
        changes, warnings = self._apply_backfill(missions)
        return MigrationResult(success=True, changes_made=changes, warnings=warnings)

    @staticmethod
    def _dry_run_summary(missions: list[Path]) -> list[str]:
        """Count would-seed events via the read-only provenance predicate."""
        would_seed = sum(len(stranded_verdict_findings(mission)) for mission in missions)
        if would_seed == 0:
            return []
        return [
            f"dry-run: would backfill {would_seed} stranded verdict event(s) "
            f"across {len(missions)} mission(s) scanned"
        ]

    @staticmethod
    def _apply_backfill(missions: list[Path]) -> tuple[list[str], list[str]]:
        """Run the idempotent backfill; return ``(change lines, warnings)``.

        A snapshot-refresh failure (#5869) becomes one warning per mission.
        """
        seeded = 0
        warnings: list[str] = []
        for mission in missions:
            outcome = backfill_verdict_provenance(mission)
            seeded += outcome.appended_count
            if outcome.refresh_error is not None:
                warnings.append(
                    f"{mission.name}: {outcome.refresh_error}; "
                    f"heal with `spec-kitty agent status materialize --mission {mission.name}`"
                )
        if seeded == 0:
            return [], warnings
        return [
            f"Backfilled {seeded} stranded verdict event(s) across "
            f"{len(missions)} mission(s) scanned"
        ], warnings


__all__ = ["VerdictProvenanceBackfillMigration"]
