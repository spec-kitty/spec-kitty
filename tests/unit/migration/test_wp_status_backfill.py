"""WP-status backfill: the snapshot must carry every WP file (#5579).

The reduced snapshot omits WPs that have no lane events (ADR 2026-06-07-3), so a
Mission whose log seeds only some WPs under-counts on every read surface that
lists WPs from ``tasks/WP*.md``. These tests pin the canonical repair.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation.wp_attribution import MIGRATION_ACTOR_PREFIX
from specify_cli.migration import backfill_runtime_state as b
from specify_cli.migration import wp_status_backfill as planner
from specify_cli.review.rejection_signal import is_documented_review_rejection
from specify_cli.status.models import GuardContext, Lane
from specify_cli.status.reducer import materialize_snapshot
from specify_cli.status.store import read_event_stream
from specify_cli.status.transitions import validate_transition
from specify_cli.status.zeitgeist_bridge import _normalise_evidence
from tests.unit.migration._backfill_fixture import build_mission

pytestmark = [pytest.mark.fast]

MISSION_ID = "01JMISSIONULID0000000000BB"
SLUG = "demo-mission-01JMISSI"
PLANNED_SEED_ID = "01AAAAAAAAAAAAAAAAAAAAAAB1"
SEED_AT = "2026-01-02T03:04:05+00:00"


def _write_wp_file(tasks_dir: Path, wp_id: str) -> None:
    (tasks_dir / f"{wp_id}-demo.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Demo {wp_id}\nexecution_mode: code_change\n---\n\n# {wp_id}\n",
        encoding="utf-8",
    )


def _planned_row(wp_id: str, event_id: str) -> dict[str, object]:
    return {
        "event_id": event_id,
        "mission_slug": SLUG,
        "mission_id": MISSION_ID,
        "wp_id": wp_id,
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": SEED_AT,
        "actor": "tester",
        "force": False,
        "execution_mode": "worktree",
    }


def _build_mission(
    tmp_path: Path,
    *,
    wp_ids: tuple[str, ...],
    seeded: tuple[str, ...],
    meta_extra: dict[str, Any] | None = None,
) -> Path:
    """Create ``kitty-specs/<slug>`` with *wp_ids* files and planned seeds for *seeded* only."""
    feature_dir = tmp_path / "kitty-specs" / SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    meta: dict[str, Any] = {"mission_id": MISSION_ID, "mission_slug": SLUG, "mission_type": "software-dev"}
    meta.update(meta_extra or {})
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    for wp_id in wp_ids:
        _write_wp_file(tasks_dir, wp_id)
    if seeded:
        rows = [_planned_row(wp_id, f"01AAAAAAAAAAAAAAAAAAAAAAB{index}") for index, wp_id in enumerate(seeded, start=1)]
        (feature_dir / "status.events.jsonl").write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
            encoding="utf-8",
        )
    return feature_dir


def test_issue_5579_repair_makes_snapshot_count_every_wp_file(tmp_path: Path) -> None:
    """#5579: a log seeding only WP01 leaves WP02/WP03 out of the snapshot; the repair fixes it."""
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01", "WP02", "WP03"), seeded=("WP01",))
    assert set(materialize_snapshot(feature_dir).work_packages) == {"WP01"}

    result = b.apply_wp_status_backfill(feature_dir, dry_run=False, evidence=None)

    assert result.error is None
    assert set(materialize_snapshot(feature_dir).work_packages) == {"WP01", "WP02", "WP03"}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

THREE = ("WP01", "WP02", "WP03")


def _lanes(feature_dir: Path) -> dict[str, str]:
    return {wp: str(state["lane"]) for wp, state in materialize_snapshot(feature_dir).work_packages.items()}


def _log_bytes(feature_dir: Path) -> bytes | None:
    path = feature_dir / "status.events.jsonl"
    return path.read_bytes() if path.exists() else None


def _seed_events(feature_dir: Path) -> list[Any]:
    return [e for e in read_event_stream(feature_dir).transitions if e.actor == planner.WP_STATUS_BACKFILL_ACTOR]


def _append_raw(feature_dir: Path, row: dict[str, object]) -> None:
    with (feature_dir / "status.events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# US1: planned seeding
# ---------------------------------------------------------------------------


def test_existing_wp_state_is_untouched_and_gaps_get_exactly_one_planned_seed(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",))
    claim = {**_planned_row("WP01", "01AAAAAAAAAAAAAAAAAAAAAAC1"), "from_lane": "planned", "to_lane": "claimed", "at": "2026-01-03T00:00:00+00:00"}
    _append_raw(feature_dir, claim)

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.files_only == ("WP02", "WP03")
    assert (result.seeded, result.would_seed) == (2, 2)
    assert _lanes(feature_dir) == {"WP01": "claimed", "WP02": "planned", "WP03": "planned"}
    assert sorted(e.wp_id for e in _seed_events(feature_dir)) == ["WP02", "WP03"]


def test_mission_without_event_log_gets_log_created_and_every_wp_seeded(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=())
    assert _log_bytes(feature_dir) is None

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.error is None
    assert result.seeded == 3
    assert _lanes(feature_dir) == {"WP01": "planned", "WP02": "planned", "WP03": "planned"}
    assert not (feature_dir / "status.json").exists()
    assert result.status_json_refreshed is False


def test_wp_with_only_a_wp_created_lifecycle_row_is_seeded(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01", "WP02"), seeded=("WP01",))
    _append_raw(
        feature_dir,
        {
            "aggregate_id": "WP02",
            "aggregate_type": "WorkPackage",
            "event_id": "01AAAAAAAAAAAAAAAAAAAAAAD1",
            "event_type": "WPCreated",
            "payload": {
                "actor": "finalize-tasks",
                "created_at": "2026-01-02T00:00:00Z",
                "depends_on": [],
                "mission_number": None,
                "mission_slug": SLUG,
                "wp_id": "WP02",
                "wp_path": None,
                "wp_title": "Demo WP02",
            },
            "project_slug": None,
            "project_uuid": None,
            "schema_version": "5.0.0",
            "timestamp": "2026-01-02T00:00:00+00:00",
        },
    )
    assert set(materialize_snapshot(feature_dir).work_packages) == {"WP01"}

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.files_only == ("WP02",)
    assert _lanes(feature_dir) == {"WP01": "planned", "WP02": "planned"}


def test_consistent_mission_is_a_noop_and_second_run_appends_nothing(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",))
    first = b.apply_wp_status_backfill(feature_dir)
    after_first = _log_bytes(feature_dir)

    second = b.apply_wp_status_backfill(feature_dir)

    assert first.seeded == 2
    assert (second.seeded, second.would_seed, second.files_only) == (0, 0, ())
    assert second.skip_reason is not None and "idempotent" in second.skip_reason
    assert _log_bytes(feature_dir) == after_first


def test_dry_run_reports_the_plan_and_writes_nothing(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",), meta_extra={"merged_at": "2026-02-01T00:00:00Z"})
    before = _log_bytes(feature_dir)

    result = b.apply_wp_status_backfill(feature_dir, dry_run=True)

    assert (result.seeded, result.would_seed) == (0, 4)
    assert result.files_only == ("WP02", "WP03")
    assert _log_bytes(feature_dir) == before
    assert set(materialize_snapshot(feature_dir).work_packages) == {"WP01"}


def test_dry_run_on_mission_without_log_does_not_create_one(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=())

    result = b.apply_wp_status_backfill(feature_dir, dry_run=True)

    assert result.would_seed == 3
    assert _log_bytes(feature_dir) is None


def test_snapshot_only_wps_are_reported_and_never_touched(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01",), seeded=("WP01", "WP09"))
    before = _log_bytes(feature_dir)

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.snapshot_only == ("WP09",)
    assert result.seeded == 0
    assert _log_bytes(feature_dir) == before


def test_malformed_wp_file_is_reported_and_skipped(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01",), seeded=("WP01",))
    (feature_dir / "tasks" / "WP02-broken.md").write_text("---\ntitle: no id here\n---\n", encoding="utf-8")

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.malformed == ("WP02-broken.md",)
    assert result.seeded == 0


def test_mission_without_tasks_dir_is_skipped(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "no-tasks"
    feature_dir.mkdir(parents=True)

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.skip_reason == "no tasks/ directory"
    assert result.seeded == 0 and result.error is None


def test_unreadable_event_log_is_reported_not_raised(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",))
    (feature_dir / "status.events.jsonl").write_text("{not json\n", encoding="utf-8")

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.error is not None
    assert result.seeded == 0


def test_status_json_is_regenerated_only_when_it_already_exists(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",))
    (feature_dir / "status.json").write_text("{}", encoding="utf-8")

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.status_json_refreshed is True
    on_disk = json.loads((feature_dir / "status.json").read_text(encoding="utf-8"))
    assert set(on_disk["work_packages"]) == set(THREE)


# ---------------------------------------------------------------------------
# US2: terminal seeding
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["merged_at", "accepted_at"])
def test_finished_mission_drives_seeded_wps_to_done_with_forced_cited_events(tmp_path: Path, key: str) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=(), meta_extra={key: "2026-02-01T00:00:00Z"})

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.terminal_reason is not None and key in result.terminal_reason
    assert _lanes(feature_dir) == {"WP01": "done", "WP02": "done", "WP03": "done"}
    done_events = [e for e in _seed_events(feature_dir) if e.to_lane == Lane.DONE]
    assert len(done_events) == 3
    for event in done_events:
        assert event.force is True
        assert event.evidence is None
        assert event.reason is not None and key in event.reason
        ok, error = validate_transition(
            str(event.from_lane),
            str(event.to_lane),
            GuardContext(actor=str(event.actor), reason=event.reason, force=event.force),
        )
        assert ok, error


def test_every_seed_event_passes_validate_transition(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=(), meta_extra={"merged_at": "2026-02-01T00:00:00Z"})
    b.apply_wp_status_backfill(feature_dir)

    for event in _seed_events(feature_dir):
        ok, error = validate_transition(
            str(event.from_lane),
            str(event.to_lane),
            GuardContext(actor=str(event.actor), reason=event.reason, force=event.force),
        )
        assert ok, f"{event.wp_id} {event.from_lane}->{event.to_lane}: {error}"


def test_manifest_evidence_marks_mission_finished_and_records_the_reason(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01", "WP02"), seeded=())

    result = b.apply_wp_status_backfill(feature_dir, evidence={SLUG: "landed via PR #1234"})

    assert _lanes(feature_dir) == {"WP01": "done", "WP02": "done"}
    assert result.terminal_reason is not None and "PR #1234" in result.terminal_reason
    assert all("PR #1234" in (e.reason or "") for e in _seed_events(feature_dir) if e.to_lane == Lane.DONE)


def test_manifest_entry_for_another_mission_is_ignored(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01",), seeded=())

    b.apply_wp_status_backfill(feature_dir, evidence={"some-other-mission": "landed"})

    assert _lanes(feature_dir) == {"WP01": "planned"}


def test_no_evidence_leaves_seeded_wps_planned(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",))

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.terminal_reason is None
    assert _lanes(feature_dir) == {"WP01": "planned", "WP02": "planned", "WP03": "planned"}


def test_finished_mission_does_not_rewrite_a_wp_with_real_lane_events(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",), meta_extra={"merged_at": "2026-02-01T00:00:00Z"})

    b.apply_wp_status_backfill(feature_dir)

    assert _lanes(feature_dir) == {"WP01": "planned", "WP02": "done", "WP03": "done"}
    assert {e.wp_id for e in _seed_events(feature_dir)} == {"WP02", "WP03"}


def test_done_event_without_evidence_is_tolerated_by_readers(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01",), seeded=(), meta_extra={"merged_at": "2026-02-01T00:00:00Z"})
    b.apply_wp_status_backfill(feature_dir)
    rows = [json.loads(line) for line in (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    done_row = next(row for row in rows if row["to_lane"] == "done")

    assert done_row["evidence"] is None
    assert _normalise_evidence(done_row["evidence"]) is None
    assert is_documented_review_rejection(done_row) is False


# ---------------------------------------------------------------------------
# FR-006 / FR-012: surface safety and interleaving
# ---------------------------------------------------------------------------


def test_meta_naming_a_deleted_coordination_branch_neither_raises_nor_mints_a_branch(tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, text=True).stdout

    git("init", "-q")
    feature_dir = _build_mission(
        tmp_path,
        wp_ids=THREE,
        seeded=("WP01",),
        meta_extra={"topology": "coord", "coordination_branch": "kitty/mission-gone-01JMISSI"},
    )

    result = b.apply_wp_status_backfill(feature_dir)

    assert result.error is None
    assert result.seeded == 2
    assert _lanes(feature_dir) == {"WP01": "planned", "WP02": "planned", "WP03": "planned"}
    assert git("branch", "--list", "kitty/*").strip() == ""


@pytest.mark.parametrize("wp_status_first", [True, False])
def test_runtime_backfill_interleaving_leaves_seeded_wp_lanes_unchanged(tmp_path: Path, wp_status_first: bool) -> None:
    feature_dir = build_mission(tmp_path, with_transitions=False, with_review=False)
    (feature_dir / "tasks" / "WP02-plain.md").write_text("---\nwork_package_id: WP02\ntitle: Plain\nexecution_mode: code_change\n---\n", encoding="utf-8")
    evidence = {feature_dir.name: "landed via PR #1"}

    if wp_status_first:
        b.apply_wp_status_backfill(feature_dir, evidence=evidence)
        settled = _lanes(feature_dir)
        b.backfill_runtime_state(feature_dir)
    else:
        b.backfill_runtime_state(feature_dir)
        b.apply_wp_status_backfill(feature_dir, evidence=evidence)
        settled = _lanes(feature_dir)
        b.backfill_runtime_state(feature_dir)

    assert _lanes(feature_dir) == settled
    assert settled["WP02"] == "done"
    assert settled["WP01"] == ("done" if wp_status_first else "claimed")
    assert b.apply_wp_status_backfill(feature_dir, evidence=evidence).seeded == 0


# ---------------------------------------------------------------------------
# repo walker
# ---------------------------------------------------------------------------


def test_repo_walk_covers_every_mission_and_honours_the_mission_selector(tmp_path: Path) -> None:
    one = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",))
    other = tmp_path / "kitty-specs" / "other-mission"
    (other / "tasks").mkdir(parents=True)
    _write_wp_file(other / "tasks", "WP01")

    scoped = b.apply_wp_status_backfill_repo(tmp_path, mission=SLUG, dry_run=True)
    assert [r.slug for r in scoped] == [SLUG]
    assert _log_bytes(other) is None

    walked = b.apply_wp_status_backfill_repo(tmp_path)
    assert sorted(r.slug for r in walked) == sorted([SLUG, "other-mission"])
    assert sum(r.seeded for r in walked) == 3
    assert set(materialize_snapshot(one).work_packages) == set(THREE)
    assert set(materialize_snapshot(other).work_packages) == {"WP01"}


def test_repo_walk_without_kitty_specs_or_unknown_mission_returns_empty(tmp_path: Path) -> None:
    assert b.apply_wp_status_backfill_repo(tmp_path) == []
    (tmp_path / "kitty-specs").mkdir()
    assert b.apply_wp_status_backfill_repo(tmp_path, mission="missing") == []


@pytest.mark.parametrize("unsafe", ["../outside", "nested/mission", ".", ".."])
def test_repo_walk_rejects_unsafe_mission_selector(tmp_path: Path, unsafe: str) -> None:
    (tmp_path / "kitty-specs").mkdir()

    with pytest.raises(ValueError, match="safe path segment"):
        b.apply_wp_status_backfill_repo(tmp_path, mission=unsafe)


def test_repo_walk_skips_and_selector_refuses_a_symlink_escaping_kitty_specs(tmp_path: Path) -> None:
    outside = tmp_path / "outside" / "evil"
    (outside / "tasks").mkdir(parents=True)
    _write_wp_file(outside / "tasks", "WP01")
    (tmp_path / "kitty-specs").mkdir()
    (tmp_path / "kitty-specs" / "evil").symlink_to(outside, target_is_directory=True)

    assert b.apply_wp_status_backfill_repo(tmp_path) == []
    with pytest.raises(ValueError, match="resolves outside kitty-specs"):
        b.apply_wp_status_backfill_repo(tmp_path, mission="evil")
    assert _log_bytes(outside) is None


# ---------------------------------------------------------------------------
# planner (pure)
# ---------------------------------------------------------------------------


def test_gap_is_set_based_in_both_directions() -> None:
    gap = planner.compute_gap({"WP01", "WP02"}, {"WP02", "WP09"}, ("bad.md",))

    assert gap.files_only == frozenset({"WP01"})
    assert gap.snapshot_only == frozenset({"WP09"})
    assert gap.malformed == ("bad.md",)


def test_equal_counts_with_different_ids_is_still_a_gap() -> None:
    gap = planner.compute_gap({"WP01", "WP02"}, {"WP01", "WP03"})

    assert (gap.files_only, gap.snapshot_only) == (frozenset({"WP02"}), frozenset({"WP03"}))


def test_terminal_evidence_precedence_and_blank_values() -> None:
    both = {"merged_at": "2026-02-01", "accepted_at": "2026-01-01"}
    merged = planner.resolve_terminal_evidence(both, "m", {"m": "manifest"})
    accepted = planner.resolve_terminal_evidence({"merged_at": "  ", "accepted_at": "2026-01-01"}, "m", None)
    manifest = planner.resolve_terminal_evidence({"merged_at": None, "accepted_at": 7}, "m", {"m": " PR #9 "})

    assert merged is not None and merged.source == "meta.merged_at"
    assert accepted is not None and accepted.source == "meta.accepted_at"
    assert manifest is not None and manifest.source == "manifest" and "PR #9" in manifest.description
    assert planner.resolve_terminal_evidence(None, "m", None) is None
    assert planner.resolve_terminal_evidence({}, "m", {"m": "   "}) is None


@pytest.mark.parametrize(
    ("created_at", "expected"),
    [
        ("2026-03-04T05:06:07Z", "2026-03-04T05:06:07+00:00"),
        ("2026-03-04T05:06:07+02:00", "2026-03-04T03:06:07+00:00"),
        ("2026-03-04T05:06:07", "2026-03-04T05:06:07+00:00"),
        ("not a date", planner.FALLBACK_SEED_AT),
        ("", planner.FALLBACK_SEED_AT),
        (None, planner.FALLBACK_SEED_AT),
        (12345, planner.FALLBACK_SEED_AT),
    ],
)
def test_seed_timestamp_is_deterministic_utc(created_at: object, expected: str) -> None:
    assert planner.seed_timestamp({"created_at": created_at}) == expected


def test_seed_timestamp_without_meta_uses_the_fixed_epoch() -> None:
    assert planner.seed_timestamp(None) == planner.FALLBACK_SEED_AT


def test_seed_ids_are_deterministic_and_distinct_per_lane_wp_and_mission() -> None:
    first = planner.seed_event_id("m1", "WP01", "planned")
    others = {
        planner.seed_event_id("m1", "WP01", "done"),
        planner.seed_event_id("m1", "WP02", "planned"),
        planner.seed_event_id("m2", "WP01", "planned"),
    }

    assert first == planner.seed_event_id("m1", "WP01", "planned")
    assert first not in others and len(others) == 3


def test_actor_carries_the_migration_prefix_attribution_ignores() -> None:
    assert planner.WP_STATUS_BACKFILL_ACTOR.startswith(MIGRATION_ACTOR_PREFIX)
    assert planner.WP_STATUS_BACKFILL_ACTOR == "migration:backfill_wp_status"


def test_planner_never_writes(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=THREE, seeded=("WP01",), meta_extra={"merged_at": "2026-02-01T00:00:00Z"})
    before = sorted((p.relative_to(feature_dir), p.read_bytes()) for p in feature_dir.rglob("*") if p.is_file())

    plan = planner.plan_wp_status_backfill(feature_dir)

    assert [e.wp_id for e in plan.events] == ["WP02", "WP02", "WP03", "WP03"]
    assert [str(e.to_lane) for e in plan.events] == ["planned", "done", "planned", "done"]
    assert sorted((p.relative_to(feature_dir), p.read_bytes()) for p in feature_dir.rglob("*") if p.is_file()) == before


def test_planned_seed_precedes_done_and_ids_key_on_the_mission_ulid(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01",), seeded=(), meta_extra={"created_at": "2026-03-04T05:06:07Z", "accepted_at": "x"})

    planned, done = planner.plan_wp_status_backfill(feature_dir).events

    assert planned.at < done.at
    assert planned.at == "2026-03-04T05:06:07+00:00"
    assert planned.event_id == planner.seed_event_id(MISSION_ID, "WP01", "planned")
    assert planned.mission_id == MISSION_ID
    assert (planned.force, done.force) == (False, True)


def test_mission_without_a_ulid_keys_ids_on_the_slug_and_omits_mission_id(tmp_path: Path) -> None:
    feature_dir = _build_mission(tmp_path, wp_ids=("WP01",), seeded=())
    (feature_dir / "meta.json").write_text("{}", encoding="utf-8")

    (planned,) = planner.plan_wp_status_backfill(feature_dir).events

    assert planned.mission_id is None
    assert planned.event_id == planner.seed_event_id(SLUG, "WP01", "planned")
