"""FR-014 provenance backfill migration.

A one-time migration that walks every on-disk acceptance matrix
(``kitty-specs/*/acceptance-matrix.json``) and, for each negative invariant
whose ``result`` is not ``pending`` and that does not already carry a
``provenance_origin`` key, writes the ``legacy_unrecorded`` sentinel
(data-model.md NI-1 / contract ``negative-invariant-provenance.md`` C1).
``verified_ref`` and ``verified_surface_kind`` are left null for those rows —
the sentinel means the surface a pre-schema judgement was established
against is genuinely unknowable, not that it is empty by omission.

``run_backfill_provenance_migration(..., mission_slug=<slug>)`` (#6347) walks
that ONE Mission's matrix instead of the corpus; the corpus-wide walk remains
the default when no scope is supplied.

Measured at implement time (2026-07-24, this lane's worktree; the ``153
matrices / 40 non-pending / 0 provenance`` figures quoted in the tasks
prompt were UNVERIFIED placeholders):

    files:              155
    negative invariants: 40 total, 40 non-pending (0 pending), 0 with
                          provenance (result split: 39 confirmed_absent,
                          1 still_present)

The whole-corpus write is a toolchain-generated write like any other
(mission thesis) and is enrolled in an explicit, one-off commit-or-revert
transaction (T028, :class:`_CorpusWriteTransaction`) that mirrors the
snapshot-and-restore rollback idiom
:class:`specify_cli.coordination.transaction.BookkeepingTransaction` uses
for a single mission's coordination worktree — re-implemented locally here
because this migration spans the WHOLE matrix corpus across many missions,
not one worktree, so the per-mission lock/coord-branch/git-commit machinery
does not apply. The generalized transactional-write owner (IC-06/WP09) is a
sibling in half 2 of this mission and is deliberately NOT depended upon here
(see WP05 task context) — this module owns its own explicit transaction.

AM-4 (T029): this module never calls, imports, or otherwise reaches an
archive operation. A matrix this migration cannot parse is reported as an
error in :class:`BackfillSummary` and skipped — never auto-archived.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from specify_cli.acceptance.matrix import (
    MATRIX_FILENAME,
    NegativeInvariant,
    PROVENANCE_LEGACY_UNRECORDED,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.utils import safe_is_dir, safe_is_file

_PENDING_RESULT = "pending"
_NEGATIVE_INVARIANTS_KEY = "negative_invariants"
_PROVENANCE_ORIGIN_KEY = "provenance_origin"


# ---------------------------------------------------------------------------
# Internal data model
# ---------------------------------------------------------------------------


@dataclass
class MatrixMigrationRecord:
    """One matrix file that was (or, in dry-run, would be) migrated."""

    path: Path
    invariants_stamped: int


@dataclass
class MatrixMigrationError:
    """A matrix file the migration could not bring onto the schema.

    AM-4: recording this here is the ENTIRE failure handling — there is no
    archive call reachable from this path or any other in this module.
    """

    path: Path
    message: str


@dataclass
class BackfillSummary:
    """Aggregated result of one migration run."""

    files_inspected: int = 0
    dry_run: bool = False
    #: #6347: the resolved Mission slug this run was scoped to, or ``None`` for
    #: the corpus-wide default. Reported so a scoped run is visible in its own
    #: output rather than only in the operator's command line.
    mission_slug: str | None = None
    migrated: list[MatrixMigrationRecord] = field(default_factory=list)
    unchanged: list[Path] = field(default_factory=list)
    errors: list[MatrixMigrationError] = field(default_factory=list)

    @property
    def stamped_total(self) -> int:
        return sum(record.invariants_stamped for record in self.migrated)

    @property
    def result(self) -> str:
        return "errors_present" if self.errors else "success"


# ---------------------------------------------------------------------------
# T028 — explicit one-off commit-or-revert transaction
# ---------------------------------------------------------------------------


class _CorpusWriteTransaction:
    """Whole-corpus commit-or-revert write.

    ``write()`` snapshots each target file's original bytes (once, before
    its first write in this transaction) and then atomically replaces it
    (temp file + ``Path.replace`` — same rename-based swap idiom used by
    ``matrix.write_acceptance_matrix`` and the coordination transaction's
    confined-artifact writer). ``commit()`` discards the rollback state on
    success; ``rollback()`` restores every file written so far to its
    pre-migration bytes. Never uses ``git checkout --`` (C-009 applies to
    any rollback path in this codebase, not only coordination-branch ones).
    """

    def __init__(self) -> None:
        self._snapshots: dict[Path, bytes] = {}
        self._written: list[Path] = []

    def write(self, path: Path, content: str) -> None:
        if path not in self._snapshots:
            self._snapshots[path] = path.read_bytes()
        tmp_path = path.with_name(f"{path.name}.tmp-{uuid4().hex}")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
        self._written.append(path)

    def commit(self) -> None:
        self._snapshots.clear()
        self._written.clear()

    def rollback(self) -> None:
        for path in self._written:
            original = self._snapshots.get(path)
            if original is not None:
                path.write_bytes(original)
        self._written.clear()
        self._snapshots.clear()


# ---------------------------------------------------------------------------
# T027 — per-file migration logic
# ---------------------------------------------------------------------------


def _stamped_invariant_dict(raw_invariant: dict[str, Any]) -> dict[str, Any] | None:
    """Return a copy of ``raw_invariant`` with the legacy sentinel stamped.

    Returns ``None`` when no stamp is needed: the result is still
    ``pending`` (nothing to attribute yet), or the invariant already
    carries a ``provenance_origin`` key (already migrated / freshly judged
    by the gate as ``recorded`` — NI-2 / C3 preservation means a terminal
    result's provenance is never touched again).

    Parses through :class:`NegativeInvariant` (the WP04 schema) to validate
    shape and compute the canonical stamped value via its ``to_dict()``,
    then applies ONLY the ``provenance_origin`` key back onto a COPY of the
    original raw dict — every other key, and its ordering, is left
    byte-identical. ``to_dict()`` itself omits ``provenance_origin`` when it
    equals the ``legacy_unrecorded`` default (matrix.py's byte-stability
    rule for matrices the migration has NOT touched); re-adding it here is
    exactly what makes THIS row's migration an explicit, readable on-disk
    fact rather than an implicit default.
    """
    invariant = NegativeInvariant.from_dict(raw_invariant)
    if invariant.result == _PENDING_RESULT:
        return None
    if _PROVENANCE_ORIGIN_KEY in raw_invariant:
        return None
    stamped = replace(invariant, provenance_origin=PROVENANCE_LEGACY_UNRECORDED)
    canonical = stamped.to_dict()
    updated = dict(raw_invariant)
    updated[_PROVENANCE_ORIGIN_KEY] = canonical.get(
        _PROVENANCE_ORIGIN_KEY, PROVENANCE_LEGACY_UNRECORDED
    )
    return updated


def _compute_migration(raw_text: str) -> tuple[str, int] | None:
    """Return ``(new_json_text, stamped_count)``, or ``None`` if unchanged.

    Operates on the raw parsed dict rather than round-tripping the whole
    file through :class:`~specify_cli.acceptance.matrix.AcceptanceMatrix`,
    so an untouched sibling invariant (or an untouched file) is never
    reformatted — only the rows actually gaining ``provenance_origin`` are
    modified.
    """
    data = json.loads(raw_text)
    invariants = data.get(_NEGATIVE_INVARIANTS_KEY) or []
    stamped_count = 0
    migrated_invariants: list[Any] = []
    changed = False
    for raw_invariant in invariants:
        updated = _stamped_invariant_dict(raw_invariant)
        if updated is None:
            migrated_invariants.append(raw_invariant)
            continue
        migrated_invariants.append(updated)
        stamped_count += 1
        changed = True

    if not changed:
        return None

    data[_NEGATIVE_INVARIANTS_KEY] = migrated_invariants
    return json.dumps(data, indent=2) + "\n", stamped_count


# ---------------------------------------------------------------------------
# T027/T028/T029 — corpus walk + transactional write
# ---------------------------------------------------------------------------


def _collect_matrix_paths(repo_root: Path, mission_slug: str | None = None) -> list[Path]:
    """Resolve the on-disk ``acceptance-matrix.json`` for every mission (T017).

    ``mission_slug`` (#6347) narrows the walk to that one Mission; ``None``
    keeps the whole-corpus walk. The narrowing happens on the MISSION LOOP, not
    on the resolved paths: each candidate's matrix is still located through the
    placement seam below, so a coordination-homed matrix stays reachable.

    WP04 (write-side-seam-matrix-tracer-01KYP3MH,
    ``contracts/write-seam-adoption.md``): the pre-fix glob
    (``specs_dir.glob("*/acceptance-matrix.json")``) only ever looked under the
    PRIMARY ``kitty-specs/`` tree — a hand-derived, coord-blind destination
    that silently skipped every COORD-topology mission's matrix (it lives
    under ``.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>/
    acceptance-matrix.json``, never copied back to primary). Each mission
    slug is now resolved through the single kind-aware read authority
    (``mission_runtime.placement_seam(...).read_dir(ACCEPTANCE_MATRIX)`` — the
    SAME authority ``acceptance/gates_core.py`` reads through) instead of a
    raw path join, so a coord-homed matrix is found too.

    This still returns file PATHS, not a write destination: the migration's
    own ``_CorpusWriteTransaction`` (module docstring) stays the sole writer —
    only discovery changes here. No git-commit machinery is introduced (module
    docstring: this migration deliberately does not depend on the generalized
    transactional-write owner, since it spans the whole matrix corpus across
    many missions, not one mission's coordination worktree).
    """
    specs_dir = repo_root / KITTY_SPECS_DIR
    if not safe_is_dir(specs_dir):
        return []

    from mission_runtime import ActionContextError, MissionArtifactKind, placement_seam
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    if mission_slug is None:
        mission_dirs = sorted(p for p in specs_dir.iterdir() if safe_is_dir(p))
    else:
        scoped_dir = specs_dir / mission_slug
        mission_dirs = [scoped_dir] if safe_is_dir(scoped_dir) else []

    paths: list[Path] = []
    for mission_dir in mission_dirs:
        try:
            matrix_dir = placement_seam(repo_root, mission_dir.name).read_dir(
                MissionArtifactKind.ACCEPTANCE_MATRIX
            )
        except (ActionContextError, StatusReadPathNotFound, FileNotFoundError):
            # An unroutable mission (e.g. a deleted coordination branch) has no
            # resolvable matrix home. AM-4 already treats a per-file parse
            # failure as "skip, never archive"; whole-corpus discovery mirrors
            # that posture by falling back to the pre-fix primary location
            # rather than aborting the run for the rest of the corpus.
            matrix_dir = mission_dir
        candidate = matrix_dir / MATRIX_FILENAME
        if safe_is_file(candidate):
            paths.append(candidate)
    return paths


def _plan_migration(
    matrix_paths: list[Path], summary: BackfillSummary
) -> list[tuple[Path, str, int]]:
    """Read + compute every file's migration in memory (no writes yet).

    A parse failure here is recorded as an error and the file is skipped —
    it never aborts the run for the rest of the corpus, and it is never
    auto-archived (AM-4 / T029).
    """
    plan: list[tuple[Path, str, int]] = []
    for path in matrix_paths:
        try:
            raw_text = path.read_text(encoding="utf-8")
            outcome = _compute_migration(raw_text)
        except (OSError, json.JSONDecodeError) as exc:
            summary.errors.append(MatrixMigrationError(path=path, message=str(exc)))
            continue
        if outcome is None:
            summary.unchanged.append(path)
            continue
        new_text, stamped_count = outcome
        plan.append((path, new_text, stamped_count))
    return plan


def run_backfill_provenance_migration(
    repo_root: Path,
    *,
    dry_run: bool = False,
    mission_slug: str | None = None,
) -> BackfillSummary:
    """Execute the FR-014 provenance backfill across the on-disk matrix corpus.

    ``mission_slug`` (#6347) scopes the run to one Mission's matrix; ``None``
    keeps the corpus-wide default unchanged.

    Two phases:

    1. **Plan** (:func:`_plan_migration`) — read and parse every matrix,
       computing the migrated JSON text for those needing it. No file is
       written during this phase; a parse failure here is reported and the
       file is skipped, never aborting the whole run and never reaching an
       archive operation (AM-4 / T029).
    2. **Write** (T028) — every planned write is enrolled in
       :class:`_CorpusWriteTransaction`. If every write succeeds, the
       transaction commits. If any write raises ``OSError`` partway through,
       every file already written in this run is restored to its
       pre-migration bytes before the error propagates — no partial
       migration state is left on disk.

    ``dry_run=True`` runs the plan phase only and reports what WOULD be
    written; nothing is touched on disk.
    """
    matrix_paths = _collect_matrix_paths(repo_root, mission_slug)
    summary = BackfillSummary(files_inspected=len(matrix_paths), dry_run=dry_run, mission_slug=mission_slug)
    plan = _plan_migration(matrix_paths, summary)

    if dry_run:
        summary.migrated = [
            MatrixMigrationRecord(path=path, invariants_stamped=stamped_count)
            for path, _new_text, stamped_count in plan
        ]
        return summary

    txn = _CorpusWriteTransaction()
    try:
        for path, new_text, _stamped_count in plan:
            txn.write(path, new_text)
    except OSError:
        txn.rollback()
        raise
    txn.commit()

    summary.migrated = [
        MatrixMigrationRecord(path=path, invariants_stamped=stamped_count)
        for path, _new_text, stamped_count in plan
    ]
    return summary
