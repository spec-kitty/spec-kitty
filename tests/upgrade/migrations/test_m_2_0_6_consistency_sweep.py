"""Scope: m 2 0 6 consistency sweep unit tests — no real git or subprocesses."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.store import EVENTS_FILENAME
from specify_cli.status.transitions import CANONICAL_LANES
from specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep import (
    ConsistencySweepMigration,
)

pytestmark = pytest.mark.fast

def _write_wp(tasks_dir: Path, wp_id: str, lane: str) -> Path:
    wp_file = tasks_dir / f"{wp_id}-upgrade.md"
    wp_file.write_text(
        "\n".join(
            [
                "---",
                f'work_package_id: "{wp_id}"',
                f'title: "{wp_id} Upgrade"',
                f'lane: "{lane}"',
                "---",
                f"# {wp_id}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return wp_file


def test_detect_flags_malformed_meta_as_repairable(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "001-broken-meta"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{not-json", encoding="utf-8")

    migration = ConsistencySweepMigration()
    assert migration.detect(repo_root) is True


def test_detect_flags_incomplete_meta_as_repairable(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "001-incomplete-meta"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "feature_number": "001",
                "slug": "001-incomplete-meta",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    migration = ConsistencySweepMigration()
    assert migration.detect(repo_root) is True


def test_apply_repairs_feature_state_and_legacy_prompt_refs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "001-upgrade-sweep"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    _write_wp(tasks_dir, "WP01", "doing")
    (feature_dir / "tasks.md").write_text(
        "\n".join(
            [
                "# Tasks",
                "",
                "**Prompt**: `.claude/prompts/tasks/doing/WP01-upgrade.md`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (feature_dir / "status.json").write_text(
        json.dumps(
            {
                "mission_slug": "",
                "event_count": 0,
                "work_packages": {},
                "summary": dict.fromkeys(CANONICAL_LANES, 0),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "specify_cli.upgrade.feature_meta.resolve_primary_branch",
        lambda _repo_root: "2.x",
    )
    monkeypatch.setattr(
        "specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep._migrate_runtime_assets",
        lambda _project_path, dry_run: ([], []),
    )

    migration = ConsistencySweepMigration()
    result = migration.apply(repo_root, dry_run=False)

    assert result.success is True

    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["target_branch"] == "2.x"
    assert meta["mission_type"] == "software-dev"

    wp_text = (tasks_dir / "WP01-upgrade.md").read_text(encoding="utf-8")
    assert 'lane: "doing"' not in wp_text
    assert "lane: in_progress" in wp_text

    tasks_md = (feature_dir / "tasks.md").read_text(encoding="utf-8")
    assert ".claude/prompts/tasks/WP01-upgrade.md" in tasks_md

    # WP05: Migration no longer bootstraps events from frontmatter.
    # No event log is created. The orphan status.json (event_count=0,
    # work_packages={}) is backed up — the event log is the sole authority.
    assert not (feature_dir / EVENTS_FILENAME).exists()

    backup_files = sorted(feature_dir.glob("status.json.orphan.bak.*"))
    assert len(backup_files) == 1  # (timestamp-suffixed name)


def test_apply_quarantines_unreadable_planned_only_event_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    feature_dir = repo_root / "kitty-specs" / "001-corrupt-events"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    _write_wp(tasks_dir, "WP01", "planned")
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "feature_number": "001",
                "slug": "001-corrupt-events",
                "mission_slug": "001-corrupt-events",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / EVENTS_FILENAME).write_text("{bad json\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep._migrate_runtime_assets",
        lambda _project_path, dry_run: ([], []),
    )

    migration = ConsistencySweepMigration()
    result = migration.apply(repo_root, dry_run=False)

    assert result.success is True
    assert not (feature_dir / EVENTS_FILENAME).exists()
    assert len(list(feature_dir.glob("status.events.jsonl.unreadable.bak.*"))) == 1
    assert any("archived unreadable status.events.jsonl" in change for change in result.changes_made)

    status = json.loads((feature_dir / "status.json").read_text(encoding="utf-8"))
    assert status["work_packages"] == {}
    assert status["event_count"] == 0


def test_apply_cleans_legacy_worktree_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    worktree = repo_root / ".worktrees" / "001-feature-lane-a"
    commands_dir = worktree / ".claude" / "commands"
    scripts_dir = worktree / ".kittify" / "scripts"
    commands_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    (commands_dir / "spec-kitty.tasks.md").write_text("legacy", encoding="utf-8")
    (scripts_dir / "task.sh").write_text("#!/bin/sh\n", encoding="utf-8")

    monkeypatch.setattr(
        "specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep._migrate_runtime_assets",
        lambda _project_path, dry_run: ([], []),
    )

    migration = ConsistencySweepMigration()
    result = migration.apply(repo_root, dry_run=False)

    assert result.success is True
    assert not commands_dir.exists()
    assert not scripts_dir.exists()
    assert any("cleaned 1 worktree" in change for change in result.changes_made)
