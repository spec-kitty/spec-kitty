"""Integration coverage for the WP03 migration engine (SC-006 / NFR-002).

Exercises the full ``backfill → verify(pre-strip, fail-closed)`` unit against an
on-disk mission corpus carrying evictable frontmatter + checkbox state:

- run #1 seeds N>0 and the post-migration reduced snapshot equals the OLD
  reader's snapshot by count + value;
- run #2 seeds 0 (idempotent, NFR-002);
- a fault-injected corrupt seed makes verify abort **before cutover**
  (fail-closed, SC-006);
- a strip-then-backfill round-trips to the same parity the pre-strip legacy read
  produced.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.migrate_cmd import app as migrate_app
from specify_cli.migration import backfill_runtime_state as b
from specify_cli.migration import runtime_state_cutover
from specify_cli.migration.runtime_state_cutover import stamp_accept_cutover
from specify_cli.migration.strip_frontmatter import strip_mutable_fields
from specify_cli.upgrade.migrations.m_zz_runtime_state_backfill import (
    RuntimeStateBackfillMigration,
)
from specify_cli.status.models import Lane
from specify_cli.status.reducer import materialize_snapshot
from tests.unit.migration._backfill_fixture import build_mission, corrupt_seed_value

pytestmark = pytest.mark.integration

_MIGRATE_LOCATE = "specify_cli.cli.commands.migrate_cmd.locate_project_root"


def _build_issue_2985_terminal_mission(
    tmp_path: Path,
    *,
    slug: str,
) -> Path:
    """Build legacy claim state plus a direct terminal transition."""
    feature_dir = build_mission(
        tmp_path,
        slug=slug,
        mission_id=f"01{slug.upper().replace('-', '')}000000000000",
    )
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    terminal = {
        "event_id": "01AAAAAAAAAAAAAAAAAAAAAAA1",
        "mission_slug": slug,
        "mission_id": meta["mission_id"],
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "done",
        "at": "2026-01-02T03:04:05+00:00",
        "actor": "legitimate-history",
        "force": True,
        "execution_mode": "worktree",
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(terminal, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return feature_dir


def _pin_synthetic_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_state_cutover,
        "_resolve_primary_home_or_degrade",
        lambda feature_dir, **_owned: feature_dir,
    )


def _snapshot_runtime(feature_dir: Path) -> dict[str, object]:
    wp = materialize_snapshot(feature_dir).work_packages["WP01"]
    return {
        "shell_pid": wp.get("shell_pid"),
        "agent": wp.get("agent"),
        "assignee": wp.get("assignee"),
        "tracker_refs": sorted(wp.get("tracker_refs") or []),
        "subtasks": dict(wp.get("subtasks") or {}),
        "review": wp.get("review"),
    }


def test_sc006_first_run_seeds_and_matches_old_reader(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    legacy = b.read_legacy_runtime(feature_dir)["WP01"]

    backfill_result, verify_result = b.run_backfill_and_verify(feature_dir)
    assert backfill_result.seeded_count > 0
    assert verify_result.ok is True

    snap = _snapshot_runtime(feature_dir)
    # Count + value parity against the OLD frontmatter/checkbox reader.
    assert snap["shell_pid"] == legacy.shell_pid
    assert snap["agent"] == legacy.agent
    assert snap["assignee"] == legacy.assignee
    assert snap["tracker_refs"] == sorted(legacy.tracker_refs)
    assert snap["subtasks"] == {sid: str(status) for sid, status in legacy.subtasks.items()}
    assert snap["review"] == (legacy.review.to_dict() if legacy.review else None)


def test_nfr002_second_run_is_idempotent(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    first = b.backfill_runtime_state(feature_dir)
    assert first.seeded_count > 0
    second = b.backfill_runtime_state(feature_dir)
    assert second.seeded_count == 0
    # Snapshot is unchanged between the two runs.
    assert b.verify_backfill(feature_dir).ok is True


def test_sc006_corrupt_seed_aborts_before_cutover(tmp_path: Path) -> None:
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    assert b.verify_backfill(feature_dir).ok is True

    # Corrupt the deterministic claim seed and re-run the fail-closed unit.
    corrupt_seed_value(
        feature_dir,
        field_name="claim",
        slot_name="shell_pid",
        value=1,
    )
    with pytest.raises(b.BackfillVerificationError):
        b.run_backfill_and_verify(feature_dir)


def test_strip_then_backfill_round_trips_to_pre_strip_parity(tmp_path: Path) -> None:
    # Prove strip_mutable_fields + backfill round-trips: capture the pre-strip
    # legacy read, backfill (pre-strip), verify parity, THEN strip. The seeded
    # snapshot equals what the pre-strip legacy read produced.
    feature_dir = build_mission(tmp_path)
    pre_strip_legacy = b.read_legacy_runtime(feature_dir)["WP01"]

    b.run_backfill_and_verify(feature_dir)
    seeded_snapshot = _snapshot_runtime(feature_dir)

    # The downstream strip now runs; the event-log snapshot is unaffected by it.
    strip_mutable_fields(feature_dir)
    post_strip_snapshot = _snapshot_runtime(feature_dir)

    assert seeded_snapshot == post_strip_snapshot
    assert post_strip_snapshot["shell_pid"] == pre_strip_legacy.shell_pid
    assert post_strip_snapshot["subtasks"] == {
        sid: str(status) for sid, status in pre_strip_legacy.subtasks.items()
    }


def test_repo_walker_backfills_every_mission(tmp_path: Path) -> None:
    build_mission(tmp_path, slug="042-demo")
    build_mission(tmp_path, slug="043-other")
    results = b.backfill_runtime_state_repo(tmp_path)
    assert {r.slug for r in results} == {"042-demo", "043-other"}
    assert all(r.action == "wrote" and r.seeded_count > 0 for r in results)
    # Idempotent second sweep.
    again = b.backfill_runtime_state_repo(tmp_path)
    assert all(r.seeded_count == 0 for r in again)


def test_lane_history_preserved_through_backfill(tmp_path: Path) -> None:
    # The seed claim transition slots at the WP's real claimed `at`, so it never
    # reverts a WP that has already advanced past claimed.
    feature_dir = build_mission(tmp_path)
    b.backfill_runtime_state(feature_dir)
    wp = materialize_snapshot(feature_dir).work_packages["WP01"]
    assert wp["lane"] == str(Lane.IN_PROGRESS)


def test_accept_stamp_preserves_terminal_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_dir = _build_issue_2985_terminal_mission(
        tmp_path,
        slug="accept-terminal",
    )
    _pin_synthetic_primary(monkeypatch)

    result = stamp_accept_cutover(feature_dir)

    assert result.error is None
    assert result.verify is not None and result.verify.ok
    assert result.flipped
    assert materialize_snapshot(feature_dir).work_packages["WP01"]["lane"] == "done"


def test_upgrade_migration_preserves_terminal_lane(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    feature_dir = _build_issue_2985_terminal_mission(
        tmp_path,
        slug="upgrade-terminal",
    )
    _pin_synthetic_primary(monkeypatch)

    result = RuntimeStateBackfillMigration().apply(tmp_path)

    assert result.success
    assert materialize_snapshot(feature_dir).work_packages["WP01"]["lane"] == "done"


def test_migrate_cli_single_then_corpus_preserves_terminal_lanes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    single = _build_issue_2985_terminal_mission(
        tmp_path,
        slug="single-terminal",
    )
    corpus = _build_issue_2985_terminal_mission(
        tmp_path,
        slug="corpus-terminal",
    )
    _pin_synthetic_primary(monkeypatch)
    runner = CliRunner()

    with patch(_MIGRATE_LOCATE, return_value=tmp_path):
        single_result = runner.invoke(
            migrate_app,
            [
                "backfill-runtime-state",
                "--mission",
                "single-terminal",
                "--json",
            ],
        )
        corpus_result = runner.invoke(
            migrate_app,
            ["backfill-runtime-state", "--json"],
        )

    assert single_result.exit_code == 0, single_result.stdout
    assert corpus_result.exit_code == 0, corpus_result.stdout
    for feature_dir in (single, corpus):
        assert (
            materialize_snapshot(feature_dir).work_packages["WP01"]["lane"]
            == "done"
        )
