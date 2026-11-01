"""Migration ``runtime_state_backfill``: corpus-wide cutover for existing deployments.

Realises **IC-02** (plan.md) / **FR-010** / **US3**: an *auto-discovered* upgrade
migration that runs ``backfill -> fail-closed verify -> status_phase flip`` over
**every** mission in an existing deployment's ``kitty-specs/`` corpus, so a
big-bang production-default flip of the snapshot-authority reader never strands
an un-migrated on-disk WP.

This migration is **fail-closed and stricter than the operator CLI** (research
D-03): ``spec-kitty migrate backfill-runtime-state`` treats each mission as an
independent best-effort unit (one mission's failure does not block the rest).
This migration instead aborts the **whole step** on the first mission whose
verify fails, with an operator-actionable message naming the mission and the
specific mismatch. Missions that already passed earlier in the same run stay
flipped -- each one was independently verified before it flipped, so nothing is
ever half-flipped (per-mission atomicity, *not* a corpus-wide rollback -- there
is no cross-mission transaction primitive to roll back with, D-03).

Reuse, not re-implementation (D-01)
------------------------------------
The one and only verify-then-flip spine lives in
:func:`specify_cli.migration.runtime_state_cutover.cutover_mission` (WP01). This
module calls it once per mission and adds nothing to the write path itself --
only the corpus walk and the fail-closed abort-on-first-failure control flow are
new here. The write target is canonicalized *inside* that reused helper, so this
migration never touches ``Path.cwd()`` and never writes at the repository root
(INV-5 / C-003 / #2815).

THE VERSION-KEY ORDERING TRAP (load-bearing -- read before editing the filename)
----------------------------------------------------------------------------------
``MigrationRegistry.get_all()`` sorts registered migrations by
``Version(target_version)``; same-version ties keep **registry insertion
order**, which is **alphabetical module-discovery order**
(``pkgutil.iter_modules`` sorts filenames before ``auto_discover_migrations()``
imports them -- verified empirically). FR-010 requires this migration to run
strictly **after** the charter-fold migrations
(``m_unify_charter_activation.py`` / ``m_unify_charter_activation_finalize.py``,
both ``target_version = "3.2.6rc1"``). Two ways to get this wrong:

1. **A ``target_version`` above ``"3.2.6rc1"``** (e.g. ``"3.3.1"``, matching the
   pre-flight brief's original filename): the installed/unreleased package
   version is ``3.2.6`` (see ``pyproject.toml``), and
   ``MigrationRegistry.get_applicable()`` only includes a migration when
   ``target <= to_version`` -- a higher ``target_version`` is **silently
   skipped** by real upgrades, and separately HARD-FAILs
   ``tests/architectural/test_migration_chain_integrity.py`` (chain end ahead of
   ``pyproject.toml``). Fix: tie the version at ``"3.2.6rc1"``, shipping within the
   same, still-unreleased cycle as the charter folds and
   ``m_3_2_6_meta_traces_merge_drivers.py``.
2. **A numeric-prefix filename at the tied version** (e.g.
   ``m_3_3_1_runtime_state_backfill.py``): digit ``'3'`` (0x33) sorts *before*
   letter ``'u'`` (0x75), so such a module would import -- and register --
   *before* ``m_unify_charter_activation*.py``, running this migration BEFORE
   the charter folds it must follow. No ``m_<digits>_*`` filename can win that
   alphabetical tie against ``m_unify_*``. This module is therefore named
   ``m_zz_runtime_state_backfill.py`` -- ``'z'`` (0x7a) sorts after ``'u'``, so
   it is guaranteed, not incidental, to import after both charter-fold modules
   at the same ``target_version``. The ``zz_`` prefix is a deliberate ordering
   marker (mirroring how ``m_unify_charter_activation_finalize.py`` encodes its
   own ordering constraint in its filename); the semantic, stable identifier
   stays on ``migration_id`` below. The auto-discovery/ordering test locks this
   property in as a regression guard.

No-op / idempotency (NFR-002, C-003)
--------------------------------------
``detect()`` is a **fast skip-hint**, not the idempotency source of truth
(research D-02): it short-circuits per mission on an already snapshot-authority
``status_phase`` (cheap, no I/O beyond ``meta.json``), and otherwise falls back
to a read-only legacy-state scan. ``apply()`` never trusts this hint for
correctness -- it always re-derives the true idempotent outcome through
:func:`cutover_mission` itself (whose backfill mints deterministic seed ids and
whose flip short-circuits once already at authority), so a second ``apply()``
over an unchanged corpus seeds nothing and re-flips nothing.

Dry-run and the fail-closed check (WP01 contract, not new here)
-------------------------------------------------------------------
``cutover_mission``'s dry-run seed phase computes the would-seed count
*without writing*, so on a never-yet-seeded mission the fail-closed verify --
which always reads the REAL on-disk event log -- legitimately cannot confirm
parity yet; that is "nothing written yet," not corruption. This migration's
abort check therefore only treats a non-``ok`` verify as fatal on a **live**
run; a dry-run preview reports the would-seed count and never aborts on that
expected pre-write mismatch (a structural error still aborts a dry-run, same
as live).
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.mission_metadata import load_meta
from specify_cli.migration.backfill_runtime_state import read_legacy_runtime
from specify_cli.migration.runtime_state_cutover import (
    CutoverResult,
    PlacementMismatchError,
    cutover_mission,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult, PartialWrite

#: Corpus root, relative to the project root -- the canonical enumeration
#: mirrors ``backfill_runtime_state_repo``/``cutover_repo``: no divergent glob.
_KITTY_SPECS_DIRNAME = "kitty-specs"

#: The two per-mission files :func:`cutover_mission` can persist: the seed
#: event log (written by the backfill/seed phase) and ``meta.json`` (written by
#: the ``status_phase`` flip). Named constants so the report-on-abort derivation
#: (:func:`_partial_writes`) and any reader agree on the exact basenames (S1192).
_STATUS_EVENTS_FILENAME = "status.events.jsonl"
_META_FILENAME = "meta.json"

#: ``meta.json`` key read by the cheap ``detect()`` skip-hint. Kept as a
#: constant (not re-imported from the reused helper's private module symbol)
#: because this is a read-only heuristic, not the shared write authority --
#: the shared helper stays the sole production *writer* of this key.
_STATUS_PHASE_KEY = "status_phase"

#: Remediation hint appended to every fail-closed abort message (T007) --
#: hoisted so it is defined exactly once (Sonar S1192).
_REMEDIATION_TEMPLATE = (
    "run `spec-kitty migrate backfill-runtime-state --mission {slug} --dry-run` to inspect"
)


def _iter_mission_dirs(project_path: Path) -> list[Path]:
    """Return every mission directory under ``kitty-specs/``, sorted by name.

    Mirrors :func:`~specify_cli.migration.backfill_runtime_state.backfill_runtime_state_repo`
    and :func:`~specify_cli.migration.runtime_state_cutover.cutover_repo` exactly
    -- no divergent glob. Returns ``[]`` when ``kitty-specs/`` is absent (fresh
    install).
    """
    kitty_specs = project_path / _KITTY_SPECS_DIRNAME
    if not kitty_specs.is_dir():
        return []
    return sorted(entry for entry in kitty_specs.iterdir() if entry.is_dir())


def _is_snapshot_authority_phase(meta: dict[str, object]) -> bool:
    """Return True iff *meta* already declares a snapshot-authority phase (>= 1)."""
    try:
        return int(str(meta.get(_STATUS_PHASE_KEY)).strip()) >= 1
    except (TypeError, ValueError):
        return False


def _mission_needs_cutover(feature_dir: Path) -> bool:
    """True when *feature_dir* still carries un-migrated legacy runtime state.

    Fast skip-hint first (a mission already at snapshot authority is never
    re-scanned); otherwise falls back to the real, read-only
    :func:`read_legacy_runtime` scan so a mission that has genuinely nothing to
    backfill (e.g. no evictable WP state at all) is correctly reported as
    needing nothing, rather than always saying "yes" just because
    ``status_phase`` happens to be absent (research D-02: status_phase alone is
    never the sole authority).
    """
    meta = load_meta(feature_dir, allow_missing=True, on_malformed="none") or {}
    if _is_snapshot_authority_phase(meta):
        return False
    legacy = read_legacy_runtime(feature_dir)
    return any(runtime.has_evictable_state() for runtime in legacy.values())


def _mission_failed(result: CutoverResult, *, dry_run: bool) -> bool:
    """True when *result* represents a fail-closed abort condition for this mission.

    A structural error (``MigrationOrderingError`` / a per-mission backfill
    error) is always fatal. A non-``ok`` verify is fatal only on a LIVE run:
    ``cutover_mission``'s dry-run seed phase computes the would-seed count
    without writing, so on a never-yet-seeded mission the fail-closed verify
    -- which always reads the REAL on-disk event log -- legitimately cannot
    confirm parity yet (this is not corruption; it is "nothing written yet").
    Only a REAL write that still fails verify (a live run) is the genuine
    fail-closed signal NFR-005 guards against.
    """
    if result.error is not None:
        return True
    if dry_run:
        return False
    return result.verify is not None and not result.verify.ok


def _failure_detail(result: CutoverResult) -> str:
    """The specific, operator-actionable count/value mismatch for *result*."""
    if result.verify is not None and not result.verify.ok:
        return "; ".join(result.verify.mismatches) or "verify reported a failure with no detail"
    if result.error:
        return result.error
    return "unknown cutover failure"  # defensive -- _mission_failed guards every caller


def _abort_message(result: CutoverResult) -> str:
    """Operator-actionable abort message naming the mission and the mismatch (NFR-005)."""
    remediation = _REMEDIATION_TEMPLATE.format(slug=result.slug)
    return (
        f"Runtime-state cutover aborted: mission {result.slug!r} failed fail-closed "
        f"verify ({_failure_detail(result)}); {remediation}"
    )


def _cutover_corpus(
    missions: list[Path], *, dry_run: bool
) -> tuple[list[CutoverResult], str | None]:
    """Walk *missions* calling :func:`cutover_mission`, aborting on the first failure.

    Returns ``(results, abort_message)``. ``abort_message`` is ``None`` on a
    clean walk; when set, the walk stopped immediately after appending the
    failing mission's result -- no mission after it was visited (NFR-005: no
    partial flip beyond the boundary of the failure).

    A :class:`PlacementMismatchError` out of ``cutover_mission`` (FR-001's
    per-mission fail-close, WP01) is caught HERE and folded into a
    ``CutoverResult(error=...)`` for that one mission, exactly like the
    pre-existing ``MigrationOrderingError`` / backfill-error paths
    ``cutover_mission`` already returns as a result rather than raising. Left
    uncaught it would escape ``apply()`` as a bare traceback instead of this
    migration's documented abort-with-actionable-message contract
    (placement-port-residuals-closure-01KYDEF0 finding 1) -- this migration is
    already stricter than the operator CLI (module docstring, research D-03),
    so folding it into the SAME abort-on-first-failure path this function
    already runs is the correct, not a laxer, containment.
    """
    results: list[CutoverResult] = []
    for feature_dir in missions:
        try:
            result = cutover_mission(feature_dir, dry_run=dry_run)
        except PlacementMismatchError as exc:
            # FR-015 (#3390): a live abort here happens AFTER the seed phase
            # already wrote real events to disk -- preserve that true count
            # (carried on the exception) so _partial_writes below reports the
            # genuine on-disk residue instead of silently under-reporting it
            # via a fresh CutoverResult defaulting seeded_count back to 0.
            result = CutoverResult(
                slug=feature_dir.name, flipped=False, error=str(exc), seeded_count=exc.seeded_count
            )
        results.append(result)
        if _mission_failed(result, dry_run=dry_run):
            return results, _abort_message(result)
    return results, None


def _partial_writes(results: list[CutoverResult], project_path: Path) -> list[PartialWrite]:
    """Enumerate every file the aborted walk already persisted (FR-005, US2-AC1).

    report-on-abort — NOT a corpus rollback (the "already-flipped missions stay
    flipped" per-mission design is intentional, research D-03). ``_cutover_corpus``
    stops right after appending the failing mission's result, so *results* holds
    exactly the missions visited up to and including the failure; anything sorted
    after it was never touched and correctly never appears here.

    The two per-mission paths are DERIVED from the mission slug and *project_path*
    (``<project>/kitty-specs/<slug>/<file>``) rather than re-read off
    :class:`CutoverResult` (which carries no path) — matching how the corpus walk
    enumerates missions in the first place (:func:`_iter_mission_dirs`). A mission
    is recorded per file it actually wrote THIS run: the event log iff it seeded
    (``seeded_count > 0``) and ``meta.json`` iff it flipped (``flipped``). A
    mission that failed verify before writing either (the common live-run abort
    case: the divergent rows pre-existed, so the idempotent re-seed adds nothing
    and the flip is unreachable) contributes no phantom path.
    """
    kitty_specs = project_path / _KITTY_SPECS_DIRNAME
    writes: list[PartialWrite] = []
    for result in results:
        mission_dir = kitty_specs / result.slug
        if result.seeded_count > 0:
            writes.append(
                PartialWrite(mission=result.slug, path=str(mission_dir / _STATUS_EVENTS_FILENAME))
            )
        if result.flipped:
            writes.append(
                PartialWrite(mission=result.slug, path=str(mission_dir / _META_FILENAME))
            )
    return writes


def _summarize_changes(results: list[CutoverResult], *, dry_run: bool) -> list[str]:
    """Build the ``changes_made`` summary. Empty means a clean no-op (INV-4).

    Gated on ``seeded_count`` alone (not ``flipped``/``would_flip``): the flip
    phase is itself a no-write short-circuit once a mission is already at
    snapshot authority, so "seeded nothing" is the one signal that is
    meaningful identically in both live and dry-run mode -- an
    already-migrated mission reports no changes either way.
    """
    seeded = sum(r.seeded_count for r in results)
    if seeded == 0:
        return []

    total = len(results)
    if dry_run:
        return [f"dry-run: would seed {seeded} event(s) across {total} mission(s) scanned"]
    flipped = sum(1 for r in results if r.flipped)
    return [f"Seeded {seeded} event(s) and flipped {flipped} of {total} mission(s) scanned"]


@MigrationRegistry.register
class RuntimeStateBackfillMigration(BaseMigration):
    """Auto-discovered corpus cutover for existing deployments (FR-010, US3).

    Runs :func:`cutover_mission` (seed -> fail-closed verify -> flip) over every
    mission under ``kitty-specs/``, in sorted order, aborting the whole step on
    the first mission whose verify fails. No-ops on a fresh install (no
    ``kitty-specs/``) and on an already-migrated corpus (idempotent, NFR-002).
    """

    migration_id = "runtime_state_backfill"
    description = (
        "Cutover every kitty-specs/ mission's runtime state to the WP01 "
        "event-log snapshot (backfill -> fail-closed verify -> status_phase "
        "flip), aborting the whole step on the first mission whose verify "
        "fails (FR-010, NFR-005)."
    )
    target_version = "3.2.6rc1"
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        """True while at least one mission still carries un-migrated legacy state."""
        return any(_mission_needs_cutover(m) for m in _iter_mission_dirs(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "no un-migrated mission runtime state found under kitty-specs/"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        missions = _iter_mission_dirs(project_path)
        if not missions:
            return MigrationResult(success=True, changes_made=[])

        results, abort_message = _cutover_corpus(missions, dry_run=dry_run)
        if abort_message is not None:
            return MigrationResult(
                success=False,
                errors=[abort_message],
                partial_writes=_partial_writes(results, project_path),
            )

        return MigrationResult(
            success=True, changes_made=_summarize_changes(results, dry_run=dry_run)
        )


__all__ = ["RuntimeStateBackfillMigration"]
