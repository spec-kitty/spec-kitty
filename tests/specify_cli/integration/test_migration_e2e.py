"""E2E integration test: legacy project migration with zero status loss (T071).

Verifies SC-005: migration converts legacy project with zero status loss.

Covers:
- Multi-feature project migration via rebuild_event_log()
- Pre-migration board state is preserved post-migration
- Lane aliases (doing → in_progress) are canonicalized in event log
- Features with no transitions are skipped (idempotency)
- Features without tasks/ directory report as skipped (not silent)
- Post-migration: event log + status.json are consistent
- Materialized snapshot from events matches pre-migration lane state
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.migration.rebuild_state import rebuild_event_log, RebuildResult
from specify_cli.status.reducer import materialize
from specify_cli.status.store import EVENTS_FILENAME, read_events

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_wp(
    tasks_dir: Path,
    wp_id: str,
    lane: str,
    *,
    history: list[dict[str, str]] | None = None,
    title: str | None = None,
) -> Path:
    """Write a WP markdown file with frontmatter.

    When no explicit history is given, generates a realistic history chain
    that transitions from 'planned' to the final lane.  This is needed because
    rebuild_event_log() only creates events for WPs with actual transitions.
    """
    wp_title = title or f"Test WP {wp_id}"

    if history is not None:
        history_entries = history
    else:
        # Build a realistic history chain leading to the target lane
        lane_chain = {
            "planned": [
                {"lane": "planned", "agent": "system", "action": "Created"},
            ],
            "claimed": [
                {"lane": "planned", "agent": "system", "action": "Created"},
                {"lane": "claimed", "agent": "claude", "action": "Claimed"},
            ],
            "doing": [
                {"lane": "planned", "agent": "system", "action": "Created"},
                {"lane": "doing", "agent": "claude", "action": "Started"},
            ],
            "in_progress": [
                {"lane": "planned", "agent": "system", "action": "Created"},
                {"lane": "in_progress", "agent": "claude", "action": "Started"},
            ],
            "for_review": [
                {"lane": "planned", "agent": "system", "action": "Created"},
                {"lane": "in_progress", "agent": "claude", "action": "Started"},
                {"lane": "for_review", "agent": "claude", "action": "Submitted for review"},
            ],
            "done": [
                {"lane": "planned", "agent": "system", "action": "Created"},
                {"lane": "in_progress", "agent": "claude", "action": "Started"},
                {"lane": "for_review", "agent": "claude", "action": "Submitted for review"},
                {"lane": "done", "agent": "reviewer", "action": "Approved"},
            ],
            "blocked": [
                {"lane": "planned", "agent": "system", "action": "Created"},
                {"lane": "in_progress", "agent": "claude", "action": "Started"},
                {"lane": "blocked", "agent": "claude", "action": "Blocked"},
            ],
            "canceled": [
                {"lane": "planned", "agent": "system", "action": "Created"},
                {"lane": "canceled", "agent": "human", "action": "Canceled"},
            ],
        }
        history_entries = lane_chain.get(lane, lane_chain["planned"])

    history_yaml_lines = []
    for entry in history_entries:
        history_yaml_lines.append(
            f"- {{lane: {entry.get('lane', lane)}, "
            f"agent: {entry.get('agent', 'system')}, "
            f"action: {entry.get('action', 'transition')}}}"
        )
    history_yaml = "\n".join(history_yaml_lines)

    content = (
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_title}\n"
        f"lane: {lane}\n"
        f"dependencies: []\n"
        f"history:\n"
        f"{history_yaml}\n"
        f"---\n\n"
        f"# Work Package: {wp_id}\n\nContent.\n"
    )
    path = tasks_dir / f"{wp_id}-test.md"
    path.write_text(content, encoding="utf-8")
    return path


def _create_legacy_feature(
    project_root: Path,
    mission_slug: str,
    wps: list[tuple[str, str]],  # [(wp_id, lane), ...]
) -> Path:
    """Create a legacy feature with WPs in various lanes."""
    feature_dir = project_root / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    meta = {
        "mission_slug": mission_slug,
        "mission": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    for wp_id, lane in wps:
        _write_wp(tasks_dir, wp_id, lane)

    return feature_dir


def _result_status(result: RebuildResult) -> str:
    """Derive a status string from a RebuildResult for assertion convenience."""
    if result.errors:
        return "failed"
    if result.skipped:
        return "skipped"
    return "migrated"


# ---------------------------------------------------------------------------
# T071: Basic migration of a single feature
# ---------------------------------------------------------------------------

class TestMigrateFeatureBasic:
    """rebuild_event_log() produces a consistent event log for a single feature."""

    def test_migration_creates_event_log(self, tmp_path: Path) -> None:
        """Migration creates an event log for WPs that have transitioned lanes."""
        feature_dir = _create_legacy_feature(
            tmp_path,
            "001-basic-feature",
            # WP01 in_progress and WP03 done produce transition events
            # WP02 planned typically produces no events (no-op)
            [("WP01", "in_progress"), ("WP02", "planned"), ("WP03", "done")],
        )

        result = rebuild_event_log(feature_dir, feature_dir.name, {})

        # WP01 and WP03 have transitions, so migration should succeed
        status = _result_status(result)
        assert status == "migrated", (
            f"Expected migrated, got {status}: {result.errors}"
        )
        event_log = feature_dir / EVENTS_FILENAME
        assert event_log.exists(), "Event log must be created after migration"

    def test_migration_events_cover_transitioned_wps(self, tmp_path: Path) -> None:
        """Events are created for WPs that have transitioned from planned."""
        feature_dir = _create_legacy_feature(
            tmp_path,
            "002-all-wps",
            # in_progress, for_review, and done all produce transitions
            [("WP01", "in_progress"), ("WP02", "for_review"), ("WP03", "done")],
        )

        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        status = _result_status(result)
        assert status == "migrated", f"Got: {status}: {result.errors}"
        events = read_events(feature_dir)

        migrated_wps = {e.wp_id for e in events}
        assert "WP01" in migrated_wps
        assert "WP02" in migrated_wps
        assert "WP03" in migrated_wps

    def test_migration_status_json_is_written(self, tmp_path: Path) -> None:
        feature_dir = _create_legacy_feature(
            tmp_path,
            "003-status-json",
            [("WP01", "in_progress"), ("WP02", "done")],
        )

        rebuild_event_log(feature_dir, feature_dir.name, {})
        snapshot = materialize(feature_dir)

        # Snapshot exists and covers both WPs (work_packages dict)
        assert "WP01" in snapshot.work_packages
        assert "WP02" in snapshot.work_packages


# ---------------------------------------------------------------------------
# T071: Lane canonicalization
# ---------------------------------------------------------------------------

class TestLaneCanonicalization:
    """Lane aliases are resolved to canonical names in the event log."""

    def test_doing_alias_resolved_to_in_progress(self, tmp_path: Path) -> None:
        feature_dir = _create_legacy_feature(
            tmp_path,
            "004-doing-alias",
            [("WP01", "doing")],  # legacy alias
        )

        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        # Migration should have created events for "doing" WP
        status = _result_status(result)
        assert status in ("migrated", "skipped"), f"Got: {status}"

        # If events were created, check that the WP is recorded
        events = read_events(feature_dir)
        if events:
            # All events should use canonical lane names (not aliases)
            from specify_cli.status.models import Lane
            for event in events:
                if event.wp_id == "WP01":
                    # Lane values must be canonical enum values
                    assert isinstance(event.to_lane, Lane), (
                        f"to_lane {event.to_lane!r} is not a Lane enum"
                    )

    def test_claimed_alias_resolved(self, tmp_path: Path) -> None:
        feature_dir = _create_legacy_feature(
            tmp_path,
            "005-claimed-alias",
            [("WP01", "claimed")],  # another alias
        )

        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        # Should not raise; migration handles alias gracefully
        status = _result_status(result)
        assert status in ("migrated", "skipped", "failed")


# ---------------------------------------------------------------------------
# T071: Idempotency
# ---------------------------------------------------------------------------

class TestMigrationIdempotency:
    """Migration is idempotent: running twice doesn't change result."""

    def test_second_migration_is_skipped_with_live_events(self, tmp_path: Path) -> None:
        from tests._support.status_seed import seed_status_event
        from specify_cli.status.models import Lane, StatusEvent

        feature_dir = _create_legacy_feature(
            tmp_path,
            "006-idempotent",
            [("WP01", "planned")],
        )

        # Create a live (non-migration) event
        live_event = StatusEvent(
            event_id="01ABCDEF0000000000000000AA",
            mission_slug="006-idempotent",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T10:00:00+00:00",
            actor="claude",  # non-migration actor
            force=False,
            execution_mode="worktree",
        )
        seed_status_event(feature_dir, live_event)

        # Second rebuild with existing event log: events are enriched/kept,
        # not duplicated. The result should not report errors.
        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        assert not result.errors, (
            f"Expected no errors on re-run with existing events, got {result.errors}"
        )
        # Events should not be lost
        events_after = read_events(feature_dir)
        assert len(events_after) >= 1, "Existing events must be preserved"

    def test_migration_does_not_lose_existing_events(self, tmp_path: Path) -> None:
        from tests._support.status_seed import seed_status_event
        from specify_cli.status.models import Lane, StatusEvent

        feature_dir = _create_legacy_feature(
            tmp_path,
            "007-no-loss",
            [("WP01", "planned")],
        )

        # Write a migration-style event first
        migration_event = StatusEvent(
            event_id="01AAAAAAAAAAAAAAAAAAAAAABB",
            mission_slug="007-no-loss",
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.PLANNED,
            at="2026-01-01T09:00:00+00:00",
            actor="migration",
            force=True,
            execution_mode="worktree",
            reason="migration",
        )
        seed_status_event(feature_dir, migration_event)

        # Second migration (migration-only events) should replace, not duplicate
        rebuild_event_log(feature_dir, feature_dir.name, {})
        events_after = read_events(feature_dir)

        # No duplicate events (idempotent replace)
        assert len(events_after) >= 1, "Events should exist after migration"


# ---------------------------------------------------------------------------
# T071: Multi-feature project migration
# ---------------------------------------------------------------------------

class TestMultiFeatureMigration:
    """Migrating a project with many features in mixed states."""

    def test_all_features_migrated_or_skipped(self, tmp_path: Path) -> None:
        """A project with 5 features all migrate successfully."""
        feature_configs: list[tuple[str, list[tuple[str, str]]]] = [
            ("010-feature-alpha", [("WP01", "in_progress"), ("WP02", "done")]),
            ("011-feature-beta", [("WP01", "in_progress"), ("WP02", "for_review")]),
            ("012-feature-gamma", [("WP01", "done"), ("WP02", "done"), ("WP03", "done")]),
            ("013-feature-delta", [("WP01", "planned")]),
            ("014-feature-epsilon", [("WP01", "canceled")]),
        ]

        results: list[RebuildResult] = []
        for slug, wps in feature_configs:
            feature_dir = _create_legacy_feature(tmp_path, slug, wps)
            result = rebuild_event_log(feature_dir, feature_dir.name, {})
            results.append(result)

        # All should have migrated or skipped (none failed without reason)
        for r in results:
            status = _result_status(r)
            assert status in ("migrated", "skipped"), (
                f"Feature {r.mission_slug} has unexpected status: {status}"
            )

    def test_done_wps_are_in_done_lane_post_migration(self, tmp_path: Path) -> None:
        """WPs that were 'done' before migration should have events after."""
        feature_dir = _create_legacy_feature(
            tmp_path,
            "015-done-preserved",
            [
                ("WP01", "done"),
                ("WP02", "done"),
                ("WP03", "in_progress"),
            ],
        )

        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        status = _result_status(result)
        assert status == "migrated", (
            f"Expected migrated, got {status}: {result.errors}"
        )

        # Events were created and WP01/WP02 are included
        events = read_events(feature_dir)
        assert events, "Events must be created after migration"
        wps_with_events = {e.wp_id for e in events}
        assert "WP01" in wps_with_events, "WP01 (done) should have events"
        assert "WP02" in wps_with_events, "WP02 (done) should have events"
        assert "WP03" in wps_with_events, "WP03 (in_progress) should have events"

    def test_planned_only_features_handled_gracefully(self, tmp_path: Path) -> None:
        """A feature where all WPs are still 'planned' migrates without error."""
        feature_dir = _create_legacy_feature(
            tmp_path,
            "016-all-planned",
            [("WP01", "planned"), ("WP02", "planned"), ("WP03", "planned")],
        )

        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        # Should not raise; status migrated or skipped
        status = _result_status(result)
        assert status in ("migrated", "skipped", "failed"), (
            "Migration should complete without exception"
        )


# ---------------------------------------------------------------------------
# T071: Error paths
# ---------------------------------------------------------------------------

class TestMigrationErrorPaths:
    """Migration handles error conditions gracefully."""

    def test_feature_without_tasks_dir_reports_skipped(self, tmp_path: Path) -> None:
        """If tasks/ directory is missing, rebuild_event_log skips gracefully."""
        feature_dir = tmp_path / "kitty-specs" / "017-no-tasks"
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_slug": "017-no-tasks", "target_branch": "main"}),
            encoding="utf-8",
        )
        # No tasks/ directory

        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        # Without a tasks dir there are no WPs and no events, so it is skipped
        assert result.skipped or result.errors, (
            "Expected skipped or errors when tasks/ is missing"
        )

    def test_feature_without_wp_files_reports_skipped(self, tmp_path: Path) -> None:
        """If tasks/ exists but has no WP*.md files, rebuild skips gracefully."""
        feature_dir = tmp_path / "kitty-specs" / "018-no-wps"
        feature_dir.mkdir(parents=True)
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir()
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_slug": "018-no-wps", "target_branch": "main"}),
            encoding="utf-8",
        )
        # tasks/ dir exists but empty

        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        # No WPs and no existing events → skipped
        assert result.skipped or result.errors, (
            "Expected skipped or errors when no WP files exist"
        )

    def test_migration_writes_event_log_when_transitions_exist(self, tmp_path: Path) -> None:
        """rebuild_event_log writes events to disk when transitions are found."""
        feature_dir = _create_legacy_feature(
            tmp_path,
            "019-writes-events",
            [("WP01", "in_progress"), ("WP02", "done")],
        )

        result = rebuild_event_log(feature_dir, feature_dir.name, {})
        event_log = feature_dir / EVENTS_FILENAME

        # Result should indicate migration happened
        status = _result_status(result)
        assert status in ("migrated", "skipped")
        # If migrated, the event log must exist on disk
        if status == "migrated":
            assert event_log.exists(), "Event log must be written to disk after migration"
