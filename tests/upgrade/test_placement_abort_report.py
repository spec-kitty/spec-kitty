"""WP05 T027 — placement-mismatch abort must be fully reported (#3390, FR-015).

Contract ``contracts/seam-contracts.md`` C8: a ``PlacementMismatchError`` abort
(``runtime_state_cutover.py:228`` -> ``m_zz_runtime_state_backfill.py:229``) is
fully reported (names the mismatch -- no under-report); a ``--dry-run`` abort
writes 0 files.

Green-on-arrival note: ``test_apply_folds_placement_mismatch_into_abort_without_a_bare_traceback``
(``tests/specify_cli/upgrade/test_runtime_state_backfill_migration.py``) already
pins that the human-readable abort *message* contains the raw
``PlacementMismatchError`` text (a fully-mocked ``cutover_mission``, so no real
seed ever runs there). This file does NOT re-assert that tautology. It instead
drives the REAL ``cutover_mission`` seed -> verify -> flip spine end to end (no
mock of ``cutover_mission`` itself, only of the placement port's resolved
home), so the seed phase genuinely writes ``status.events.jsonl`` to disk
*before* the flip fails -- exposing the narrow residual: the corpus walker's
``except PlacementMismatchError`` handler rebuilt a *fresh* ``CutoverResult``
with ``seeded_count`` defaulted back to 0, so ``_partial_writes`` silently
dropped the genuinely-written event log from the abort report (an
under-report of real on-disk residue, not a message-text problem). Confirmed
RED against the pre-fix ``runtime_state_cutover.py`` (the exception carried no
``seeded_count`` at all) before writing the fix.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.migration import runtime_state_cutover as cutover_module
from specify_cli.migration.runtime_state_cutover import PlacementMismatchError, cutover_mission
from specify_cli.upgrade.migrations.m_zz_runtime_state_backfill import (
    RuntimeStateBackfillMigration,
)
from tests.unit.migration._backfill_fixture import build_mission

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _force_mismatch(monkeypatch: pytest.MonkeyPatch, elsewhere: Path) -> None:
    """Make the placement port resolve every mission's PRIMARY home to
    *elsewhere* -- guaranteed to disagree with the real write target, so
    ``_flip_phase`` raises ``PlacementMismatchError`` for real (not mocked)."""
    monkeypatch.setattr(
        cutover_module,
        "_resolve_primary_home_or_degrade",
        lambda _feature_dir, **_owned: elsewhere,
    )


def test_placement_mismatch_error_carries_the_real_seeded_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Driving the real spine: the seed phase writes real events before the
    flip aborts, and the raised exception must carry that true count so a
    catching caller can build an honest CutoverResult."""
    alpha = build_mission(tmp_path, slug="alpha")
    _force_mismatch(monkeypatch, tmp_path / "elsewhere")

    events_path = alpha / "status.events.jsonl"
    events_before = events_path.stat().st_size

    with pytest.raises(PlacementMismatchError) as excinfo:
        cutover_mission(alpha)

    # The seed phase really did write to disk before the flip failed.
    assert events_path.stat().st_size > events_before

    assert excinfo.value.seeded_count > 0, "PlacementMismatchError must carry the real on-disk seeded_count so callers do not under-report already-written residue"


def test_migration_apply_reports_the_genuinely_written_event_log_on_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The upgrade migration's abort report (``MigrationResult.partial_writes``)
    must name the ``status.events.jsonl`` file it actually wrote for the
    mismatched mission before aborting -- not silently omit it."""
    alpha = build_mission(tmp_path, slug="alpha")
    _force_mismatch(monkeypatch, tmp_path / "elsewhere")

    events_path = alpha / "status.events.jsonl"

    migration = RuntimeStateBackfillMigration()
    result = migration.apply(tmp_path)

    assert result.success is False
    assert events_path.exists()
    assert events_path.stat().st_size > 0, "sanity: the seed phase really wrote this file"

    written_paths = {pw.path for pw in result.partial_writes}
    assert str(events_path) in written_paths, (
        "the migration wrote status.events.jsonl for alpha before the flip "
        "aborted; the abort report's partial_writes must name it, not "
        f"under-report it (got: {sorted(written_paths)})"
    )

    # And the human-readable message still names the mismatch (unchanged
    # guarantee, distinct from the partial_writes check above).
    (error,) = result.errors
    assert "alpha" in error
    assert "placement" in error.lower()


def test_dry_run_over_the_placement_mismatch_path_writes_zero_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A --dry-run run must never reach the flip phase at all, so a placement
    mismatch cannot cause a phantom write even when the walk aborts.

    ``cutover_mission`` returns *before* calling ``_flip_phase`` whenever
    ``dry_run=True`` (the seed phase itself also only computes the would-seed
    count without writing) -- so forcing a mismatched placement home has no
    write-path effect on a dry run at all. This pins that structural
    invariant directly: no file under the mission directory changes.
    """
    alpha = build_mission(tmp_path, slug="clean-mission", with_claim=False, with_history=False, with_transitions=False)
    _force_mismatch(monkeypatch, tmp_path / "elsewhere")

    before = {p: p.read_bytes() for p in alpha.rglob("*") if p.is_file()}

    migration = RuntimeStateBackfillMigration()
    result = migration.apply(tmp_path, dry_run=True)

    after = {p: p.read_bytes() for p in alpha.rglob("*") if p.is_file()}
    assert after == before, "dry-run must write zero bytes to any existing file"
    assert {p for p in alpha.rglob("*") if p.is_file()} == set(before), "dry-run must not create any new file either"
    # The migration result itself must not claim any partial write occurred.
    assert result.partial_writes == []
