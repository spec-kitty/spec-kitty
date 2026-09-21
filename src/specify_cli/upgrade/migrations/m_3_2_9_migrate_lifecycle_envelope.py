"""Migration ``migrate_lifecycle_envelope``: wire the F2-T1 one-shot F1-strict rewrite.

:mod:`specify_cli.status.migrate_lifecycle_envelope` (F2-T1, M2 canonical
integration 2026-08-22) is a one-shot, idempotent, whole-file-atomic rewrite
of legacy 9-key lifecycle envelope rows (``schema_version: "5.0.0"``,
produced by :mod:`specify_cli.status.lifecycle_events`'s local appenders)
into F1's (``spec_kitty_events``, sibling repo) strict 14-key envelope
profile, wrapping the SAME ``event_type``/``payload`` pair. The rewrite
spine landed with a full red-first test suite (MIG1-5, COMPAT2, COMPAT6 --
``tests/status/test_migrate_lifecycle_envelope.py``) but **no CLI/upgrade
caller** -- an existing deployment upgrading across the F1-strict cutover
had no path that ever ran it, so its on-disk logs would stay legacy-shaped
forever. It was grandfathered as a Category-7 "library written but never
wired" orphan in ``tests/architectural/test_no_dead_modules.py`` pending
exactly this wiring (WIRE-M2-03).

This module is that caller. It is an *auto-discovered* upgrade migration
(``@MigrationRegistry.register`` + ``pkgutil.iter_modules`` -- no static
importer, same mechanism as every other ``m_*.py`` file in this package)
that runs the rewrite on ``spec-kitty upgrade`` over BOTH lifecycle event
log targets :mod:`specify_cli.status.lifecycle_events` defines:

* the one project-level log, ``<project_path>/.kittify/canonical-events.jsonl``
  (``ProjectInitialized`` rows), and
* every mission-level log, ``<project_path>/kitty-specs/<mission>/status.events.jsonl``
  (``MissionCreated``/``WPCreated``/... rows), for every mission directory
  under ``kitty-specs/``, in sorted order.

Reuse, not re-implementation
-----------------------------
The one and only rewrite spine is
:func:`specify_cli.status.migrate_lifecycle_envelope.migrate_lifecycle_envelope`.
``mission_event_log_path`` / ``project_event_log_path`` are imported as
``from specify_cli.status import ...`` -- this module is a ``src/``
consumer, so it goes through the curated ``specify_cli.status`` facade
rather than reaching into ``status.lifecycle_events`` directly, per the
repo-wide boundary (``tests/architectural/test_status_module_boundary.py``
SR-2). ``migrate_lifecycle_envelope`` itself is the one exception: its bare
name collides with its own home submodule's filename
(``status/migrate_lifecycle_envelope.py``), so promoting it onto the facade
under that name would silently break two pre-existing tests that already
resolve ``specify_cli.status.migrate_lifecycle_envelope`` to the MODULE
(``tests/status/test_migrate_lifecycle_envelope.py``, ``tests/status/
test_migrate_lifecycle_envelope_node_id_parity.py``) -- see the
``_WP10_DEFERRED_FILES`` entry for this file in
``test_status_module_boundary.py`` for the full rationale and the
follow-up-bead note. It is imported directly from its submodule instead,
as a documented, temporary boundary exception. This module adds only the
two-target corpus walk; it never re-implements the
per-row rewrite, the whole-file-atomic write, the ``.pre-migration.bak``
snapshot, or the symlink-safe read -- all of that stays exactly where F2-T1
put it. Mirrors the corpus-walk shape of the two sibling backfill migrations
(:mod:`m_zz_runtime_state_backfill`, :mod:`m_zz_verdict_provenance_backfill`)
-- same ``kitty-specs/`` enumeration, no divergent glob -- extended with the
one additional project-level target this migration's underlying function
also has to cover.

Idempotency (MIG2, already proven -- not re-derived here)
------------------------------------------------------------
``migrate_lifecycle_envelope`` is idempotent by construction:
``_is_already_strict_shaped`` short-circuits any row that already carries
every synthesized key and the strict ``schema_version`` to the ``"unchanged"``
action, and the live-write path skips the snapshot+replace round trip
entirely once a file's computed ``migrated_count`` is zero. This module adds
no additional idempotency layer on top -- a second ``apply()`` over an
unchanged corpus rewrites nothing and reports no changes, and ``detect()``
returns ``False`` once every log in the corpus is converged.

MIG4 (stale snapshot refusal) continues per-file but fails the aggregate
------------------------------------------------------------------------
``migrate_lifecycle_envelope`` itself refuses to re-migrate a single file
that already carries a ``.pre-migration.bak`` from an earlier run with
migrated rows still pending (an operator-recoverable situation: remove the
stale snapshot once satisfied with the prior run). That refusal is
file-scoped in the underlying function's own docstring, so this migration
continues rewriting every OTHER log in the corpus rather than aborting the
walk. The aggregate ``MigrationResult`` nevertheless fails, naming the exact
path and reason: the runner must not record the migration as successful or
advance project metadata while even one lifecycle log remains legacy-shaped.
After the operator removes the stale snapshot, the ordinary upgrade path can
retry the failed migration and converge the remaining log.

Version-key pin (``target_version = "3.2.6rc2"``, not a WP-shaped digit)
-------------------------------------------------------------------------
Installed/unreleased package version is ``"3.2.6rc2"`` (``pyproject.toml``)
at authoring time. ``MigrationRegistry.get_applicable()`` only includes a
migration when ``target <= to_version``, so a higher literal (e.g. a
filename-matching ``"3.2.9"``) would be silently skipped by every real
upgrade AND separately hard-fail
``tests/architectural/test_migration_chain_integrity.py`` (chain end ahead
of ``pyproject.toml``). Mirrors the same already-documented precedent in
``m_3_2_7_heal_provenance_paths.py`` / ``m_3_2_8_provision_kitty_env.py``:
the filename encodes a plausible next-in-sequence slug, the
``target_version`` is pinned to the actual installed package version. This
migration has no ordering dependency on any other migration in the same
tied-version group (it touches only lifecycle event logs, disjoint from the
charter/runtime-state/verdict-provenance/env-provisioning concerns of its
siblings), so no ``m_zz_``/``m_unify_`` ordering-marker filename trick is
needed here -- registration order among same-version siblings is immaterial
for this migration.
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.status import (
    mission_event_log_path,
    project_event_log_path,
)

# migrate_lifecycle_envelope is imported directly from its home submodule,
# not the facade: its bare name collides with the submodule's own filename
# (status/migrate_lifecycle_envelope.py), so promoting it onto
# specify_cli.status.__all__ would silently break two pre-existing tests
# that already resolve `specify_cli.status.migrate_lifecycle_envelope` to
# the MODULE. This is a documented, temporary boundary exception -- see
# this file's entry in test_status_module_boundary.py's
# _WP10_DEFERRED_FILES for the full rationale and the follow-up-bead note.
from specify_cli.status.migrate_lifecycle_envelope import (
    migrate_lifecycle_envelope,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

#: Corpus root, relative to the project root -- mirrors
#: ``m_zz_runtime_state_backfill``/``m_zz_verdict_provenance_backfill``
#: exactly: no divergent glob.
_KITTY_SPECS_DIRNAME = "kitty-specs"


def _iter_mission_dirs(project_path: Path) -> list[Path]:
    """Return every mission directory under ``kitty-specs/``, sorted by name.

    Mirrors :func:`~specify_cli.upgrade.migrations.m_zz_runtime_state_backfill._iter_mission_dirs`
    exactly. Returns ``[]`` when ``kitty-specs/`` is absent (fresh install).
    """
    kitty_specs = project_path / _KITTY_SPECS_DIRNAME
    if not kitty_specs.is_dir():
        return []
    return sorted(entry for entry in kitty_specs.iterdir() if entry.is_dir())


def _iter_existing_log_paths(project_path: Path) -> list[Path]:
    """Every lifecycle event log under *project_path* that currently exists.

    The project-level log first (if it was ever written), then each
    mission-level log in mission-directory-name order. A log that was never
    written (a fresh project with no ``ProjectInitialized`` yet, or a
    mission whose only rows so far are ``StatusEvent`` lane transitions) is
    skipped: ``migrate_lifecycle_envelope`` would report zero rows for a
    missing path anyway (its symlink-safe reader treats "file not found" as
    empty text), so skipping here only avoids acquiring that path's write
    lock for nothing.
    """
    project_log = project_event_log_path(project_path)
    log_paths = [project_log] if project_log.exists() else []
    for mission_dir in _iter_mission_dirs(project_path):
        mission_log = mission_event_log_path(mission_dir)
        if mission_log.exists():
            log_paths.append(mission_log)
    return log_paths


def _needs_migration(log_path: Path) -> bool:
    """True when *log_path* still carries at least one legacy-shaped row."""
    return migrate_lifecycle_envelope(log_path, dry_run=True).migrated_count > 0


def _migrate_corpus(log_paths: list[Path], *, dry_run: bool) -> tuple[list[str], list[str]]:
    """Run the F2-T1 rewrite over every path in *log_paths*.

    Returns ``(changes_made, refusals)``. A MIG4 refusal (a stale
    ``.pre-migration.bak`` left over from an earlier interrupted run) is
    returned as an aggregate-fatal error naming the exact path and the reused
    function's own operator-actionable reason. It does not abort the rest of
    the corpus walk, matching ``migrate_lifecycle_envelope``'s own per-file
    refusal scope (module docstring above).
    """
    migrated_total = 0
    refusals: list[str] = []
    for log_path in log_paths:
        manifest = migrate_lifecycle_envelope(log_path, dry_run=dry_run)
        if manifest.refused_reason is not None:
            refusals.append(f"{log_path}: {manifest.refused_reason}")
            continue
        migrated_total += manifest.migrated_count

    if migrated_total == 0:
        return [], refusals

    scanned = len(log_paths)
    if dry_run:
        return (
            [f"dry-run: would rewrite {migrated_total} legacy-shaped lifecycle envelope row(s) to F1's strict shape across {scanned} event log(s) scanned"],
            refusals,
        )
    return (
        [f"Rewrote {migrated_total} legacy-shaped lifecycle envelope row(s) to F1's strict shape across {scanned} event log(s) scanned"],
        refusals,
    )


@MigrationRegistry.register
class MigrateLifecycleEnvelopeMigration(BaseMigration):
    """Auto-discovered corpus rewrite of legacy lifecycle envelopes (F2-T1).

    Runs :func:`~specify_cli.status.migrate_lifecycle_envelope.migrate_lifecycle_envelope`
    over the project-level ``.kittify/canonical-events.jsonl`` log and every
    mission-level ``kitty-specs/<mission>/status.events.jsonl`` log,
    rewriting each legacy-shaped row into F1's strict 14-key envelope
    wrapping the identical ``event_type``/``payload`` pair. No-ops on a
    fresh install (no project log, no ``kitty-specs/``) and on an
    already-migrated corpus (idempotent, MIG2).
    """

    migration_id = "migrate_lifecycle_envelope"
    description = (
        "Rewrite legacy 9-key lifecycle envelope rows on disk into F1's strict 14-key envelope shape "
        "across the project-level and every mission-level event log, keeping each event_type/payload "
        "pair identical (F2-T1). Idempotent."
    )
    target_version = "3.2.6rc2"
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        """True while at least one event log still carries a legacy-shaped row."""
        return any(_needs_migration(p) for p in _iter_existing_log_paths(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "no legacy-shaped lifecycle envelope rows found in any event log"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        log_paths = _iter_existing_log_paths(project_path)
        if not log_paths:
            return MigrationResult(success=True, changes_made=[])
        changes, refusals = _migrate_corpus(log_paths, dry_run=dry_run)
        return MigrationResult(
            success=not refusals,
            changes_made=changes,
            errors=refusals,
        )


__all__ = ["MigrateLifecycleEnvelopeMigration"]
