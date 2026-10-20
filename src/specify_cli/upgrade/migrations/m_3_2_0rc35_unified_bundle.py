"""Migration 3.2.0rc35_unified_bundle: advance project to unified bundle (v1.0.0).

Phase 2 migration. On apply:
    (a) Detect whether ``.kittify/charter/charter.md`` exists at the canonical root.
    (b) If yes, validate the bundle against ``CharterBundleManifest`` v1.0.0.
    (c) Invoke ``ensure_charter_bundle_fresh()`` to regenerate any missing or
        stale derivatives.
    (d) Emit a structured JSON report per
        ``contracts/migration-report.schema.json``.

Explicitly OUT OF SCOPE (per C-011 / C-012 and the design-review corrections):
    - Scanning or modifying worktrees.
    - Removing any symlinks (``.kittify/memory``, ``.kittify/AGENTS.md`` are
      documented-intentional per ``src/specify_cli/templates/AGENTS.md:168-179``).
    - Reconciling ``.gitignore`` (v1.0.0 manifest required entries already
      match current ``.gitignore`` verbatim).

The migration's public-facing contract is the JSON report returned by
``apply()``; ``BaseMigration.apply`` is specified to return a
``MigrationResult``. To honor both contracts, ``apply()`` composes the report
inside ``MigrationResult.changes_made[0]`` as a JSON string so the registry
framework's signature is preserved while the contract-shaped report is
available to callers that need it (and to ``tests/upgrade/test_unified_bundle_migration.py``
which parses the JSON payload directly).

Ref: FR-007, FR-008, FR-013, FR-015 / spec.md §Acceptance.
Ref: kitty-specs/unified-charter-bundle-chokepoint-01KP5Q2G/contracts/migration-report.schema.json
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "3.2.0rc35_unified_bundle"
TARGET_VERSION = "3.2.0rc35"


def _build_report(
    charter_present: bool,
    applied: bool,
    chokepoint_refreshed: bool,
    bundle_validation: dict[str, Any],
    errors: list[str],
    start_ns: int,
) -> dict[str, Any]:
    """Assemble the contract-shaped JSON report.

    Schema: ``contracts/migration-report.schema.json``.
    """
    duration_ms = max(0, int((time.monotonic_ns() - start_ns) / 1_000_000))
    return {
        "migration_id": MIGRATION_ID,
        "target_version": TARGET_VERSION,
        "applied": applied,
        "charter_present": charter_present,
        "bundle_validation": bundle_validation,
        "chokepoint_refreshed": chokepoint_refreshed,
        "errors": list(errors),
        "duration_ms": duration_ms,
    }


def _default_bundle_validation() -> dict[str, Any]:
    """Empty, passing bundle-validation block for no-charter projects."""
    return {
        "passed": True,
        "missing_tracked": [],
        "missing_derived": [],
        "unexpected": [],
    }


@MigrationRegistry.register
class UnifiedBundleMigration(BaseMigration):
    """Seal the project at 3.2.0rc35: ensure derivatives via the chokepoint, validate bundle.

    The migration is intentionally narrow. It performs NO worktree scanning,
    NO symlink operations, and NO ``.gitignore`` edits — v1.0.0 manifest
    scope only.
    """

    # Resolves the canonical repo root (charter.resolution), so it needs a git repository (#6539).
    requires_git_repository = True

    migration_id = MIGRATION_ID
    description = (
        "Advance 3.x project to the unified charter bundle (v1.0.0): validate "
        "bundle against CharterBundleManifest; invoke the chokepoint to refresh "
        "missing/stale derivatives; emit a structured JSON report. Idempotent; "
        "no worktree/symlink/.gitignore changes."
    )
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    # ------------------------------------------------------------------
    # Detection / gating
    # ------------------------------------------------------------------

    def detect(self, project_path: Path) -> bool:
        """Return True for the main checkout; False for linked worktrees.

        The migration's contract (see module docstring and §C-011/§C-012)
        says worktree scanning and mutation are out of scope. The upgrade
        runner now honors ``runs_on_worktrees = False`` and skips this
        migration entirely for `.worktrees/*` checkouts; this method keeps
        the same policy as a direct-call guardrail. Returning True on a
        linked worktree would wrongly treat that worktree as an upgrade
        target even though the chokepoint materializes derivatives only at
        the canonical main-checkout root.

        A linked worktree has ``.git`` as a regular file that points at the
        shared common dir (``gitdir: /path/to/main/.git/worktrees/<name>``);
        the main checkout has ``.git`` as a directory. We detect that
        distinction here and short-circuit to False for worktrees. The main-
        checkout pass is unchanged: always True, ``apply()`` handles all
        four fixture cases (no charter, charter+fresh, charter+stale,
        charter+missing-derivs) and sets ``applied`` accordingly.

        Args:
            project_path: Root of the project (.kittify parent).

        Returns:
            True iff ``project_path`` is the main checkout (``.git`` is a
            directory or absent). False for linked worktrees (``.git`` is
            a file).
        """
        git_marker = project_path / ".git"
        return not git_marker.is_file()

    def can_apply(self, _project_path: Path) -> tuple[bool, str]:
        """Always applicable; the migration itself is a no-op when nothing to do."""
        return True, ""

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Run the migration and return both the framework result + contract report.

        Returns:
            ``MigrationResult`` whose ``changes_made[0]`` is a JSON string
            carrying the contract-shaped migration report. Callers that need
            the typed report call ``json.loads(result.changes_made[0])``.
        """
        start_ns = time.monotonic_ns()
        errors: list[str] = []

        # Lazy imports keep registry-discovery fast (C-001 / C-008).
        from charter.bundle import CANONICAL_MANIFEST
        from charter.resolution import resolve_canonical_repo_root
        from charter.activation.sync import ensure_charter_bundle_fresh

        canonical_root = resolve_canonical_repo_root(project_path)
        charter_dir = canonical_root / ".kittify" / "charter"
        charter_md = charter_dir / "charter.md"
        charter_present = charter_md.exists()

        # ------------------------------------------------------------------
        # Case (e): no charter.md — clean no-op, trivially passing.
        # ------------------------------------------------------------------
        if not charter_present:
            report = _build_report(
                charter_present=False,
                applied=False,
                chokepoint_refreshed=False,
                bundle_validation=_default_bundle_validation(),
                errors=errors,
                start_ns=start_ns,
            )
            return MigrationResult(
                success=True,
                changes_made=[json.dumps(report, sort_keys=True)],
                errors=list(errors),
                warnings=[],
            )

        # ------------------------------------------------------------------
        # Pre-refresh snapshot against the v1.0.0 manifest.
        # ------------------------------------------------------------------
        tracked_before_missing = [
            str(rel) for rel in CANONICAL_MANIFEST.tracked_files
            if not (canonical_root / rel).exists()
        ]
        derived_before_missing = [
            str(rel) for rel in CANONICAL_MANIFEST.derived_files
            if not (canonical_root / rel).exists()
        ]

        # ------------------------------------------------------------------
        # Invoke the chokepoint. ``ensure_charter_bundle_fresh`` resolves
        # canonical-root internally and returns a SyncResult carrying
        # ``synced`` (True iff sync actually ran).
        #
        # C-001: if the chokepoint raises (filesystem failure, extraction
        # failure), propagate — do not swallow.
        # ------------------------------------------------------------------
        applied = False
        chokepoint_refreshed = False
        if not dry_run:
            sync_result = ensure_charter_bundle_fresh(canonical_root)
            if sync_result is not None:
                if sync_result.error:
                    errors.append(sync_result.error)
                if sync_result.synced:
                    chokepoint_refreshed = True
                    applied = True

        # ------------------------------------------------------------------
        # Post-refresh snapshot — what the migration report presents.
        # ------------------------------------------------------------------
        tracked_after_missing = [
            str(rel) for rel in CANONICAL_MANIFEST.tracked_files
            if not (canonical_root / rel).exists()
        ]
        derived_after_missing = [
            str(rel) for rel in CANONICAL_MANIFEST.derived_files
            if not (canonical_root / rel).exists()
        ]

        # Enumerate any files under ``.kittify/charter/`` that the v1.0.0
        # manifest does not declare (``references.yaml``, ``context-state.json``,
        # ``interview/answers.yaml``, ``library/*.md``). Operator visibility
        # only — the migration does NOT delete or modify these.
        declared_rel: set[str] = {
            str(p) for p in CANONICAL_MANIFEST.tracked_files
        } | {
            str(p) for p in CANONICAL_MANIFEST.derived_files
        }
        unexpected: list[str] = []
        if charter_dir.exists():
            for entry in charter_dir.rglob("*"):
                if not entry.is_file():
                    continue
                try:
                    rel = str(entry.relative_to(canonical_root))
                except ValueError:
                    continue
                if rel not in declared_rel:
                    unexpected.append(rel)
        unexpected.sort()

        bundle_validation = {
            "passed": not tracked_after_missing and not derived_after_missing,
            "missing_tracked": tracked_after_missing,
            "missing_derived": derived_after_missing,
            "unexpected": unexpected,
        }

        # Unused pre-refresh variables are kept for readability / debugging
        # at run-time; they are intentionally not surfaced in the report.
        del tracked_before_missing
        del derived_before_missing

        report = _build_report(
            charter_present=True,
            applied=applied,
            chokepoint_refreshed=chokepoint_refreshed,
            bundle_validation=bundle_validation,
            errors=errors,
            start_ns=start_ns,
        )

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=[json.dumps(report, sort_keys=True)],
            errors=list(errors),
            warnings=[],
        )


__all__ = [
    "MIGRATION_ID",
    "TARGET_VERSION",
    "UnifiedBundleMigration",
]
