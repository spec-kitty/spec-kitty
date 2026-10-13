"""ATDD tests for the auto-discovered verdict-provenance backfill migration.

verdict-seam-write-unification-01KZ9Q35 pre-merge remediation (FR-012/SC-008,
#3236). Proves ``spec-kitty upgrade`` runs the previously caller-less
``migration.verdict_provenance_backfill`` over every ``kitty-specs/`` mission:
a stranded pre-event ``.md`` rejection is reduced into a ``review_result``
event so the event authority is complete after the verdict-reader collapse.

RED-first: before the wrapper existed the module
``upgrade.migrations.m_zz_verdict_provenance_backfill`` did not exist, so the
import at the top of this file failed at collection and every test errored.
GREEN once the wrapper is wired.

All tests call ``detect()``/``can_apply()``/``apply()`` directly on a
``VerdictProvenanceBackfillMigration`` instance -- the established pattern in
``test_runtime_state_backfill_migration.py`` -- so the ``target_version`` guard
never interferes. Fixtures are synthetic ``tmp_path/kitty-specs/`` corpora
reusing the WP02 SC-008 hermetic shape (a review-cycle ``.md`` carrying a
LEGACY ``verdict`` frontmatter key); the live repository is never mutated.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.migration.verdict_provenance_backfill import (
    stranded_verdict_findings,
)
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import (
    event_sourced_review_result,
    materialize,
    materialize_snapshot,
    materialize_to_json,
)
from specify_cli.status.store import append_events_atomic_verified
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.migrations.m_zz_verdict_provenance_backfill import (
    VerdictProvenanceBackfillMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_THIS_MIGRATION_ID = "verdict_provenance_backfill"


def _write_stranded_mission(
    project_path: Path,
    *,
    slug: str = "042-verdict-provenance-demo",
    mission_id: str = "01JRDVERDICTPROV000000000",
    wp_id: str = "WP01",
    verdict: str = "rejected",
) -> Path:
    """Create a mission whose only rejection record is a pre-event ``.md``.

    Mirrors WP02's SC-008 hermetic fixture (``test_verdict_seam_reader_collapse``):
    a ``review-cycle-N.md`` written through the live schema, then spliced with
    the LEGACY ``verdict:`` frontmatter key those historical files carry forever
    (``ReviewCycleArtifact`` no longer has a ``verdict`` field). No
    ``status.events.jsonl`` ``review_result`` slot exists yet -- exactly the
    stranded shape the backfill exists to recover.
    """
    feature_dir = project_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": slug,
                "mission_id": mission_id,
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )
    sub_dir = feature_dir / "tasks" / f"{wp_id}-demo"
    artifact = ReviewCycleArtifact(
        cycle_number=1,
        wp_id=wp_id,
        mission_slug=slug,
        reviewer_agent="reviewer-renata",
        reviewed_at="2026-01-01T00:00:00+00:00",
        body="# Review\n",
    )
    path = sub_dir / "review-cycle-1.md"
    artifact.write(path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"expected frontmatter delimiter in {path}"
    path.write_text(f"---\nverdict: {verdict}\n{text[4:]}", encoding="utf-8")
    return feature_dir


def test_apply_backfills_stranded_md_verdict_into_event_log(tmp_path: Path) -> None:
    """The load-bearing wiring proof: ``apply()`` reduces a stranded ``.md``
    rejection into a ``review_result`` event on the real event log."""
    feature_dir = _write_stranded_mission(tmp_path)

    # Precondition: stranded, and the event authority has no opinion yet.
    assert len(stranded_verdict_findings(feature_dir)) == 1
    assert event_sourced_review_result(feature_dir, "WP01").slot_present is False

    migration = VerdictProvenanceBackfillMigration()
    assert migration.detect(tmp_path) is True

    result = migration.apply(tmp_path)

    assert result.success is True
    assert result.changes_made, "a backfill that seeded an event must report it"
    # The rejection is now resolvable from the event log alone (SC-008).
    lookup = event_sourced_review_result(feature_dir, "WP01")
    assert lookup.slot_present is True
    assert lookup.result is not None
    assert lookup.result.verdict == "changes_requested"
    # And the interlock is clear.
    assert stranded_verdict_findings(feature_dir) == []


def test_detect_false_and_apply_noop_once_converged(tmp_path: Path) -> None:
    """Idempotency (NFR-002): a second ``apply()`` seeds nothing and
    ``detect()`` reports the converged corpus as needing no work."""
    feature_dir = _write_stranded_mission(tmp_path)
    migration = VerdictProvenanceBackfillMigration()

    first = migration.apply(tmp_path)
    assert first.changes_made

    assert migration.detect(tmp_path) is False
    can_apply, reason = migration.can_apply(tmp_path)
    assert can_apply is False
    assert "no stranded verdict provenance" in reason

    second = migration.apply(tmp_path)
    assert second.success is True
    assert second.changes_made == [], "converged re-run must seed nothing"
    # The single backfilled event is unchanged (no duplicate append).
    assert event_sourced_review_result(feature_dir, "WP01").result is not None


def test_dry_run_previews_without_writing(tmp_path: Path) -> None:
    """A dry-run reports the would-seed count and writes NO event log."""
    feature_dir = _write_stranded_mission(tmp_path)
    migration = VerdictProvenanceBackfillMigration()

    result = migration.apply(tmp_path, dry_run=True)

    assert result.success is True
    assert any("dry-run" in line for line in result.changes_made)
    # Nothing was written -- still stranded, still no event slot.
    assert not (feature_dir / "status.events.jsonl").exists()
    assert len(stranded_verdict_findings(feature_dir)) == 1


def test_noop_on_fresh_install_without_kitty_specs(tmp_path: Path) -> None:
    """No ``kitty-specs/`` (fresh install) is a clean no-op, not a crash."""
    migration = VerdictProvenanceBackfillMigration()

    assert migration.detect(tmp_path) is False
    result = migration.apply(tmp_path)

    assert result.success is True
    assert result.changes_made == []


def test_migration_is_auto_discovered_and_registered() -> None:
    """The wiring is real: the migration self-registers via auto-discovery
    (``pkgutil.iter_modules`` + ``@MigrationRegistry.register``), at the tied
    package ``target_version``."""
    auto_discover_migrations()

    migration = MigrationRegistry.get_by_id(_THIS_MIGRATION_ID)
    assert migration is not None, (
        "verdict_provenance_backfill must be auto-discovered and registered"
    )
    assert migration.target_version == "3.2.6rc1"
    assert migration.runs_on_worktrees is False


_LIFECYCLE = (
    (Lane.PLANNED, Lane.CLAIMED, "01ARZ3NDEKTSV4RRFFQ69G5FC0", "2026-01-01T00:00:01+00:00"),
    (Lane.CLAIMED, Lane.IN_PROGRESS, "01ARZ3NDEKTSV4RRFFQ69G5FC1", "2026-01-01T00:00:02+00:00"),
    (Lane.IN_PROGRESS, Lane.FOR_REVIEW, "01ARZ3NDEKTSV4RRFFQ69G5FC2", "2026-01-01T00:00:03+00:00"),
    (Lane.FOR_REVIEW, Lane.IN_REVIEW, "01ARZ3NDEKTSV4RRFFQ69G5FC4", "2026-01-01T00:00:04+00:00"),
)


def _stranded_mission_with_snapshot(project_path: Path, *, snapshot: bool = True) -> Path:
    """A stranded-verdict mission with a real lifecycle and (optionally) a
    ``status.json`` materialized before the backfill runs."""
    feature_dir = _write_stranded_mission(project_path)
    append_events_atomic_verified(
        feature_dir,
        [
            StatusEvent(
                event_id=event_id,
                mission_slug=feature_dir.name,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                at=at,
                actor="claude",
                force=False,
                execution_mode="worktree",
            )
            for from_lane, to_lane, event_id, at in _LIFECYCLE
        ],
    )
    if snapshot:
        materialize(feature_dir)
    return feature_dir


def _fresh_json(feature_dir: Path) -> str:
    return materialize_to_json(materialize_snapshot(feature_dir))


@pytest.mark.regression
class TestSnapshotRefreshViaMigration:
    """Regression guard for #5869 through ``VerdictProvenanceBackfillMigration.apply``."""

    def test_apply_refreshes_existing_snapshot(self, tmp_path: Path) -> None:
        feature_dir = _stranded_mission_with_snapshot(tmp_path)
        stale = (feature_dir / "status.json").read_text(encoding="utf-8")

        result = VerdictProvenanceBackfillMigration().apply(tmp_path)

        assert result.success is True and result.changes_made
        assert result.warnings == []
        persisted = (feature_dir / "status.json").read_text(encoding="utf-8")
        assert json.loads(persisted) == json.loads(_fresh_json(feature_dir))
        assert persisted != stale

    def test_apply_creates_no_snapshot_where_none_existed(self, tmp_path: Path) -> None:
        feature_dir = _stranded_mission_with_snapshot(tmp_path, snapshot=False)

        result = VerdictProvenanceBackfillMigration().apply(tmp_path)

        assert result.changes_made
        assert not (feature_dir / "status.json").exists()

    def test_dry_run_leaves_log_and_perturbed_snapshot_byte_identical(self, tmp_path: Path) -> None:
        feature_dir = _stranded_mission_with_snapshot(tmp_path)
        snapshot_path = feature_dir / "status.json"
        snapshot_path.write_text(
            json.dumps(json.loads(snapshot_path.read_text(encoding="utf-8")), indent=4), encoding="utf-8"
        )
        log_before = (feature_dir / "status.events.jsonl").read_bytes()
        snapshot_before = snapshot_path.read_bytes()
        assert snapshot_before != _fresh_json(feature_dir).encode("utf-8")

        result = VerdictProvenanceBackfillMigration().apply(tmp_path, dry_run=True)

        assert any("dry-run" in line for line in result.changes_made)
        assert (feature_dir / "status.events.jsonl").read_bytes() == log_before
        assert snapshot_path.read_bytes() == snapshot_before

    def test_refresh_failure_surfaces_as_warning_and_stays_successful(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        feature_dir = _stranded_mission_with_snapshot(tmp_path)

        def _broken(_dir: Path) -> None:
            raise OSError("disk full")

        monkeypatch.setattr("specify_cli.migration.snapshot_refresh.materialize", _broken)

        result = VerdictProvenanceBackfillMigration().apply(tmp_path)

        assert result.success is True
        assert result.changes_made, "the append is committed and must still be reported"
        assert len(result.warnings) == 1
        assert feature_dir.name in result.warnings[0] and "disk full" in result.warnings[0]
        assert event_sourced_review_result(feature_dir, "WP01").slot_present is True
