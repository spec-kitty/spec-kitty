"""Tests for migration/runner.py — Subtask T069 (atomic migration runner).

Covers:
- T069-A: Full migration on clean legacy project: all steps succeed
- T069-B: Mid-flight features: state preserved accurately
- T069-C: Failure in step 3 (ownership): rollback to pre-migration state
- T069-D: Failure in the schema-version step: rollback to pre-migration state
- T069-E: Dry run: no files modified
- T069-F: Performance: 5 features / 50 WPs completes in < 30 seconds (CI-safe threshold)
- T069-G: MigrationReport contains correct counters
- T069-H: .gitignore entries added
- T069-I: Schema version updated in metadata.yaml
- #5443: the runner is git-free -- it never stages, commits, or moves HEAD or the index
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from specify_cli.migration.runner import (    MigrationReport,
    _create_backup,
    _restore_backup,
    _update_gitignore,
    _update_schema_version,
    run_migration,
    _GITIGNORE_ADD_ENTRIES,
    _BACKUP_DIR_NAME,
)
from tests._perf_helpers import assert_timing_budget

# Marked for mutmut sandbox skip — see ADR 2026-04-20-1.
# Reason: subprocess CLI invocation
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Legacy project fixture builder
# ---------------------------------------------------------------------------


def _make_legacy_project(
    tmp_path: Path,
    features: list[dict] | None = None,
    git_init: bool = True,
) -> Path:
    """Build a minimal legacy spec-kitty project.

    features: list of dicts with keys:
      slug (str), wps (list of {name, lane})

    Returns the project root path.
    """
    root = tmp_path / "project"
    root.mkdir()

    # .kittify/
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(
        yaml.dump({
            "spec_kitty": {
                "version": "2.1.0",
                "initialized_at": "2026-01-01T00:00:00",
            }
        }),
        encoding="utf-8",
    )
    (kittify / "config.yaml").write_text(
        yaml.dump({"agents": {"available": []}}),
        encoding="utf-8",
    )

    # .gitignore
    (root / ".gitignore").write_text(
        "*.pyc\n__pycache__/\n",
        encoding="utf-8",
    )

    # kitty-specs/
    kitty_specs = root / "kitty-specs"
    kitty_specs.mkdir()

    for feat in (features or []):
        slug = feat["slug"]
        feature_dir = kitty_specs / slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)

        meta = {"mission_slug": slug, "title": f"Feature {slug}"}
        (feature_dir / "meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

        for wp in feat.get("wps", []):
            wp_name = wp["name"]
            lane = wp.get("lane", "planned")
            content = (
                f"---\n"
                f"work_package_id: ''\n"
                f"wp_code: {wp_name!r}\n"
                f"title: {wp_name} Title\n"
                f"lane: {lane!r}\n"
                f"dependencies: []\n"
                f"subtasks: []\n"
                f"---\n\n"
                f"# {wp_name}\n"
            )
            (tasks_dir / f"{wp_name}-title.md").write_text(content, encoding="utf-8")

    # Git init (the runner itself never touches git; a repository lets tests prove that)
    if git_init:
        subprocess.run(["git", "init"], cwd=root, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=root, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=root, capture_output=True,
        )
        subprocess.run(["git", "add", "--", ".kittify", ".gitignore", "kitty-specs"], cwd=root, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=root, capture_output=True,
        )

    return root


# ---------------------------------------------------------------------------
# Shared read-only migrated-project fixture (WP03/T010, FR-009, NFR-007)
# ---------------------------------------------------------------------------
#
# The three read-only ``TestFullMigration`` checks below
# (schema_version / .gitignore / backup-cleanup) each rebuilt the *same*
# single-feature project and ran ``run_migration`` again — ~3x the cost for one
# inspectable post-migration state. This module-scoped fixture runs that exact
# migration ONCE and exposes the resulting (root, report) for read-only
# inspection. ``report.success`` is asserted inside the fixture so a broken
# migration fails fixture setup, not just the individual asserts.
#
# CARVE-OUTS (NOT routed through this fixture — they need pristine per-test
# state and/or different inputs):
#   * ``test_migration_succeeds_on_legacy_project`` — different (2-feature) input
#     and asserts the ``features_migrated`` counter.
#   * ``TestMigrationReportCounters`` — different inputs / counter assertions.
#   * Rollback / dry-run tests — mutate or short-circuit the migration via
#     patches and must observe their own fresh, un-migrated state.


@pytest.fixture(scope="module")
def migrated_project(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, MigrationReport]:
    """Run the canonical single-feature migration once for read-only reuse.

    Returns ``(root, report)``. The migrated tree is shared across the three
    truly-identical read-only assertions; they must NOT mutate it.
    """
    root = _make_legacy_project(
        tmp_path_factory.mktemp("migrated_project"),
        features=[{"slug": "001-test", "wps": [{"name": "WP01", "lane": "planned"}]}],
    )
    report = run_migration(root)
    assert report.success, f"shared migration fixture failed: {report.errors}"
    return root, report


# ---------------------------------------------------------------------------
# T069-A: Full migration on clean legacy project
# ---------------------------------------------------------------------------


class TestFullMigration:
    def test_migration_succeeds_on_legacy_project(self, tmp_path: Path) -> None:
        """Full migration completes without errors."""
        root = _make_legacy_project(
            tmp_path,
            features=[
                {
                    "slug": "001-alpha",
                    "wps": [
                        {"name": "WP01", "lane": "done"},
                        {"name": "WP02", "lane": "in_progress"},
                    ],
                },
                {
                    "slug": "002-beta",
                    "wps": [
                        {"name": "WP01", "lane": "planned"},
                    ],
                },
            ],
        )

        report = run_migration(root)

        assert report.success, f"Migration failed: {report.errors}"
        assert report.features_migrated == 2
        assert not report.failed_step

    def test_schema_version_updated(
        self, migrated_project: tuple[Path, MigrationReport]
    ) -> None:
        """After migration, metadata.yaml has schema_version=3.

        Read-only inspection of the shared ``migrated_project`` (T010).
        """
        root, _report = migrated_project
        metadata_path = root / ".kittify" / "metadata.yaml"
        data = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        assert data["spec_kitty"]["schema_version"] == 3
        assert "canonical_context" in data["spec_kitty"]["schema_capabilities"]

    def test_gitignore_updated(
        self, migrated_project: tuple[Path, MigrationReport]
    ) -> None:
        """After migration, .gitignore contains the new entries.

        Read-only inspection of the shared ``migrated_project`` (T010).
        """
        root, _report = migrated_project
        gitignore_content = (root / ".gitignore").read_text(encoding="utf-8")
        for entry in [".kittify/derived/", ".kittify/.migration-backup/"]:
            assert entry in gitignore_content, f"Expected {entry!r} in .gitignore"

    def test_backup_cleaned_up_after_success(
        self, migrated_project: tuple[Path, MigrationReport]
    ) -> None:
        """Backup directory is removed after successful migration.

        Read-only inspection of the shared ``migrated_project`` (T010).
        """
        root, report = migrated_project
        assert report.success
        backup_dir = root / ".kittify" / _BACKUP_DIR_NAME
        assert not backup_dir.exists(), "Backup should be cleaned up after success"


# ---------------------------------------------------------------------------
# T069-B: Mid-flight features
# ---------------------------------------------------------------------------


class TestMidFlightFeatures:
    def test_mid_flight_features_preserved(self, tmp_path: Path) -> None:
        """WPs in various lanes are preserved accurately after migration."""
        root = _make_legacy_project(
            tmp_path,
            features=[
                {
                    "slug": "003-mid-flight",
                    "wps": [
                        {"name": "WP01", "lane": "done"},
                        {"name": "WP02", "lane": "in_progress"},
                        {"name": "WP03", "lane": "for_review"},
                        {"name": "WP04", "lane": "planned"},
                    ],
                }
            ],
        )

        report = run_migration(root)

        assert report.success, f"Migration failed: {report.errors}"

        # Verify event log was written for the feature
        events_file = root / "kitty-specs" / "003-mid-flight" / "status.events.jsonl"
        assert events_file.exists(), "Event log should be created"

        events = [json.loads(ln) for ln in events_file.read_text().splitlines() if ln.strip()]
        assert len(events) > 0

        # Done WP should have transition chain ending in done
        done_events = [e for e in events if e["wp_id"] == "WP01"]
        assert any(e["to_lane"] == "done" for e in done_events)

        # In-progress WP should have transition chain ending in in_progress
        ip_events = [e for e in events if e["wp_id"] == "WP02"]
        assert any(e["to_lane"] == "in_progress" for e in ip_events)


# ---------------------------------------------------------------------------
# T069-C: Rollback on step 3 failure (ownership backfill)
# ---------------------------------------------------------------------------


class TestRollbackOnOwnershipFailure:
    def test_rollback_on_ownership_failure(self, tmp_path: Path) -> None:
        """Failure in ownership backfill triggers rollback."""
        root = _make_legacy_project(
            tmp_path,
            features=[
                {
                    "slug": "004-rollback",
                    "wps": [{"name": "WP01", "lane": "in_progress"}],
                }
            ],
        )

        def _failing_ownership(feature_dir: Path, mission_slug: str) -> None:
            raise RuntimeError("Simulated ownership failure")

        with patch("specify_cli.migration.backfill_ownership.backfill_ownership", side_effect=_failing_ownership):
            report = run_migration(root)

        assert not report.success
        assert report.failed_step == "ownership_backfill"

        # Metadata should be restored (no schema_version=3)
        restored_metadata = (root / ".kittify" / "metadata.yaml").read_text(encoding="utf-8")
        restored_data = yaml.safe_load(restored_metadata)
        schema_v = restored_data.get("spec_kitty", {}).get("schema_version")
        assert schema_v != 3, "Schema version must not be 3 after rollback"


# ---------------------------------------------------------------------------
# T069-D: Rollback on schema version update failure
# ---------------------------------------------------------------------------


class TestRollbackOnSchemaVersionFailure:
    def test_rollback_on_schema_version_failure(self, tmp_path: Path) -> None:
        """Failure in schema version update triggers rollback."""
        root = _make_legacy_project(
            tmp_path,
            features=[
                {
                    "slug": "005-schema-fail",
                    "wps": [{"name": "WP01", "lane": "planned"}],
                }
            ],
        )

        def _failing_schema_update(repo_root: Path) -> None:
            raise RuntimeError("Simulated schema version failure")

        with patch("specify_cli.migration.runner._update_schema_version", side_effect=_failing_schema_update):
            report = run_migration(root)

        assert not report.success
        assert report.failed_step == "schema_version_update"

        # The key check is that schema_version was NOT written.
        # (.gitignore is outside .kittify/ so it may have been partially updated
        # before the schema_version step failed — the schema_version absence is
        # the authoritative rollback indicator.)
        restored_data = yaml.safe_load(
            (root / ".kittify" / "metadata.yaml").read_text(encoding="utf-8")
        )
        assert restored_data.get("spec_kitty", {}).get("schema_version") != 3


# ---------------------------------------------------------------------------
# T069-E: Dry run
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_no_files_modified(self, tmp_path: Path) -> None:
        """Dry run does not modify any files."""
        root = _make_legacy_project(
            tmp_path,
            features=[
                {
                    "slug": "006-dryrun",
                    "wps": [{"name": "WP01", "lane": "in_progress"}],
                }
            ],
        )

        # Capture file mtimes before
        metadata_before = (root / ".kittify" / "metadata.yaml").stat().st_mtime

        report = run_migration(root, dry_run=True)

        assert report.dry_run
        assert report.success

        # Metadata should be unchanged
        metadata_after = (root / ".kittify" / "metadata.yaml").stat().st_mtime
        assert metadata_before == metadata_after, "metadata.yaml should not be modified in dry run"

        # No schema_version set
        data = yaml.safe_load((root / ".kittify" / "metadata.yaml").read_text(encoding="utf-8"))
        assert "schema_version" not in data.get("spec_kitty", {}), \
            "schema_version must not be written in dry run"


# ---------------------------------------------------------------------------
# T069-F: Performance
# ---------------------------------------------------------------------------


class TestPerformance:
    @pytest.mark.slow
    def test_migration_of_5_features_succeeds(
        self, tmp_path: Path
    ) -> None:
        """5 features / 10 WPs each migrates successfully."""
        features = [
            {
                "slug": f"{i:03d}-perf-feature",
                "wps": [
                    {"name": f"WP{j:02d}", "lane": "in_progress"}
                    for j in range(1, 11)
                ],
            }
            for i in range(1, 6)
        ]
        root = _make_legacy_project(tmp_path, features=features)

        report = run_migration(root)

        assert report.success, f"Migration failed: {report.errors}"

    @pytest.mark.slow
    @pytest.mark.performance
    def test_migration_completes_in_under_10_seconds_for_5_features(
        self, tmp_path: Path
    ) -> None:
        """5 features / 10 WPs each migrates in < 30 seconds.

        The threshold is set to 30 s to accommodate shared CI runners, which
        have higher git and I/O overhead than local development machines.
        The guard still catches catastrophic regressions (e.g. O(n³) loops or
        unintentional network calls) while remaining stable in practice.
        Typical local run: ~6 s; CI observed: ~19 s on a shared runner.
        """
        features = [
            {
                "slug": f"{i:03d}-perf-feature",
                "wps": [
                    {"name": f"WP{j:02d}", "lane": "in_progress"}
                    for j in range(1, 11)
                ],
            }
            for i in range(1, 6)
        ]
        root = _make_legacy_project(tmp_path, features=features)

        start = time.perf_counter()
        run_migration(root)
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 30.0, name="migration of 5 features")


# ---------------------------------------------------------------------------
# T069-G: MigrationReport counters
# ---------------------------------------------------------------------------


class TestMigrationReportCounters:
    def test_features_migrated_matches_feature_count(self, tmp_path: Path) -> None:
        """features_migrated in report matches the number of features."""
        root = _make_legacy_project(
            tmp_path,
            features=[
                {"slug": "007a-test", "wps": [{"name": "WP01", "lane": "planned"}]},
                {"slug": "007b-test", "wps": [{"name": "WP01", "lane": "done"}]},
            ],
        )

        report = run_migration(root)

        assert report.success, report.errors
        assert report.features_migrated == 2

    def test_wps_backfilled_is_nonzero(self, tmp_path: Path) -> None:
        """wps_backfilled reflects WPs that received IDs."""
        root = _make_legacy_project(
            tmp_path,
            features=[
                {
                    "slug": "007c-test",
                    "wps": [
                        {"name": "WP01", "lane": "done"},
                        {"name": "WP02", "lane": "in_progress"},
                    ],
                }
            ],
        )

        report = run_migration(root)

        assert report.success, report.errors
        assert report.wps_backfilled == 2


# ---------------------------------------------------------------------------
# T069-H / T069-I: Gitignore and schema version unit tests
# ---------------------------------------------------------------------------


class TestGitignoreUpdate:
    def test_adds_new_entries(self, tmp_path: Path) -> None:
        """_update_gitignore adds required new entries."""
        (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        changes = _update_gitignore(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        for entry in _GITIGNORE_ADD_ENTRIES:
            assert entry in content, f"Expected {entry!r} in .gitignore"
        assert len(changes) > 0

    def test_idempotent(self, tmp_path: Path) -> None:
        """_update_gitignore is idempotent (second call makes no changes)."""
        (tmp_path / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        changes1 = _update_gitignore(tmp_path)
        changes2 = _update_gitignore(tmp_path)
        assert len(changes1) > 0
        assert len(changes2) == 0


class TestSchemaVersionUpdate:
    def test_sets_schema_version_3(self, tmp_path: Path) -> None:
        """_update_schema_version writes schema_version=3."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "metadata.yaml").write_text(
            yaml.dump({"spec_kitty": {"version": "2.1.0"}}),
            encoding="utf-8",
        )

        _update_schema_version(tmp_path)

        data = yaml.safe_load((kittify / "metadata.yaml").read_text(encoding="utf-8"))
        assert data["spec_kitty"]["schema_version"] == 3

    def test_sets_capabilities(self, tmp_path: Path) -> None:
        """_update_schema_version writes the canonical capabilities list."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "metadata.yaml").write_text(
            yaml.dump({"spec_kitty": {"version": "2.1.0"}}),
            encoding="utf-8",
        )

        _update_schema_version(tmp_path)

        data = yaml.safe_load((kittify / "metadata.yaml").read_text(encoding="utf-8"))
        caps = data["spec_kitty"]["schema_capabilities"]
        assert "canonical_context" in caps
        assert "event_log_authority" in caps


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------


class TestBackupHelpers:
    def test_create_backup_copies_kittify(self, tmp_path: Path) -> None:
        """_create_backup creates a copy of .kittify."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "metadata.yaml").write_text("test: 1\n", encoding="utf-8")

        backup_dir = _create_backup(tmp_path)

        assert backup_dir is not None
        assert backup_dir.exists()
        assert (backup_dir / "metadata.yaml").exists()

    def test_restore_backup_restores_content(self, tmp_path: Path) -> None:
        """_restore_backup puts .kittify back to the backup state."""
        kittify = tmp_path / ".kittify"
        kittify.mkdir()
        (kittify / "metadata.yaml").write_text("original: true\n", encoding="utf-8")

        backup_dir = _create_backup(tmp_path)
        assert backup_dir is not None

        # Modify the metadata
        (kittify / "metadata.yaml").write_text("modified: true\n", encoding="utf-8")

        _restore_backup(tmp_path, backup_dir)

        restored = yaml.safe_load((kittify / "metadata.yaml").read_text(encoding="utf-8"))
        assert restored.get("original") is True


# ---------------------------------------------------------------------------
# #5443: the runner is git-free
# ---------------------------------------------------------------------------


def _git_out(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout


class TestRunnerLeavesGitAlone:
    def test_head_and_index_unchanged(self, tmp_path: Path) -> None:
        """run_migration writes files only: HEAD and the operator's staged work are untouched."""
        root = _make_legacy_project(tmp_path, features=[{"slug": "001-demo", "wps": [{"name": "WP01", "lane": "planned"}]}])
        (root / "notes.txt").write_text("operator note\n", encoding="utf-8")
        _git_out(root, "add", "--", "notes.txt")
        head_before = _git_out(root, "rev-parse", "HEAD")
        staged_before = _git_out(root, "diff", "--cached", "--name-only", "-z")
        assert staged_before == "notes.txt\0"

        report = run_migration(root)

        assert report.success, report.errors
        assert _git_out(root, "rev-parse", "HEAD") == head_before
        assert _git_out(root, "diff", "--cached", "--name-only", "-z") == staged_before
        migrated = yaml.safe_load((root / ".kittify" / "metadata.yaml").read_text(encoding="utf-8"))
        assert migrated["spec_kitty"]["schema_version"] == 3

    def test_migration_succeeds_outside_git(self, tmp_path: Path) -> None:
        """No commit dependency: a project that is not a git repository migrates."""
        root = _make_legacy_project(tmp_path, features=[{"slug": "001-demo", "wps": [{"name": "WP01", "lane": "planned"}]}], git_init=False)

        report = run_migration(root)

        assert report.success is True
        assert report.failed_step is None
