"""The pre-#4090 ``merged_at`` backfill migration (#7433, operator ruling 2026-11-08).

A Mission that landed before consolidation stamped ``merged_at`` has no marker, so the one landed
signal (``mission_runtime.mission_has_landed``) reads it as not landed, and a coordination-topology
one refuses with ``COORDINATION_BRANCH_DELETED`` (#7335). The backfill stamps the marker only when
the committed status log, read through the status read door, shows every work package done or
canceled (at least one done) and no reopen; the date is the latest transition to done.
``mission_number`` is not evidence (#5471). Every fixture is a REAL git repository: the
coordination refusal and the coordination-ref read are the door's real verdicts, not mocks.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from mission_runtime import mission_has_landed
from specify_cli.migration.backfill_merged_at import backfill_merged_at
from specify_cli.status.landing_evidence import LandingVerdict, read_landing_evidence
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.upgrade.migrations.m_4_0_0rc8_backfill_merged_at import BackfillMergedAtMigration
from tests._support.status_seed import seed_status_events

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_LATEST_DONE = "2026-03-04T05:06:07.123456+00:00"
_EARLIER_DONE = "2026-02-01T00:00:00+00:00"

#: ``(wp_id, final lane, done at)``: a WP ends in *final lane*; a done WP's last hop is stamped *done at*.
WpPlan = tuple[str, Lane, str | None]


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=dict(os.environ))
    return done.stdout.strip()


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-qb", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".kittify").mkdir()
    (root / ".kittify" / "config.yaml").write_text("agents:\n  available: []\n", encoding="utf-8")
    (root / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "init")
    return root


def _mission_id(tag: str) -> str:
    return ("01KZ" + "".join(char for char in tag.upper() if char.isalnum()) + "0" * 26)[:26]


def _write_meta(feature_dir: Path, meta: Mapping[str, object]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(dict(meta), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _meta(feature_dir: Path) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return loaded


def _path_to(lane: Lane) -> list[tuple[Lane, Lane]]:
    if lane is Lane.PLANNED:
        return [(Lane.GENESIS, Lane.PLANNED)]
    if lane is Lane.CANCELED:
        return [(Lane.GENESIS, Lane.PLANNED), (Lane.PLANNED, Lane.CANCELED)]
    return [(Lane.GENESIS, Lane.PLANNED), (Lane.PLANNED, Lane.APPROVED), (Lane.APPROVED, lane)]


def _seed_wps(feature_dir: Path, slug: str, plans: Sequence[WpPlan]) -> None:
    """Seed each WP's history, the done hops LAST in reverse date order (file order is not date order)."""
    events: list[StatusEvent] = []
    done_hops: list[StatusEvent] = []
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    for wp_id, lane, done_at in plans:
        (tasks / f"{wp_id}-work.md").write_text(f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\nexecution_mode: code_change\n---\n# {wp_id}\n", encoding="utf-8")
        for hop_no, (from_lane, to_lane) in enumerate(_path_to(lane)):
            is_done_hop = to_lane is Lane.DONE
            event = StatusEvent(
                event_id=f"seed-{slug}-{wp_id}-{hop_no}",
                mission_slug=slug,
                wp_id=wp_id,
                from_lane=from_lane,
                to_lane=to_lane,
                at=(done_at or _EARLIER_DONE) if is_done_hop else f"2026-01-0{hop_no + 1}T00:00:00+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            )
            (done_hops if is_done_hop else events).append(event)
    done_hops.sort(key=lambda event: event.at, reverse=True)
    seed_status_events(feature_dir, [*events, *done_hops])


def _mission(
    repo: Path,
    slug: str,
    plans: Sequence[WpPlan],
    *,
    topology: str | None = "lanes",
    mission_id: str | None = "auto",
    commit: bool = True,
    **extra: object,
) -> Path:
    """A Mission without ``merged_at`` whose status log ends in *plans*."""
    feature_dir = repo / "kitty-specs" / slug
    meta: dict[str, object] = {"mission_slug": slug, "mission_type": "software-dev", "target_branch": "main", "friendly_name": slug, **extra}
    if topology is not None:
        meta["topology"] = topology
    if mission_id is not None:
        resolved = _mission_id(slug) if mission_id == "auto" else mission_id
        meta.update(mission_id=resolved, mid8=resolved[:8])
    _write_meta(feature_dir, meta)
    _seed_wps(feature_dir, slug, plans)
    if commit:
        _git(repo, "add", ".")
        _git(repo, "commit", "-qm", f"mission {slug}")
    return feature_dir


_ALL_TERMINAL: tuple[WpPlan, ...] = (("WP01", Lane.DONE, _EARLIER_DONE), ("WP02", Lane.DONE, _LATEST_DONE), ("WP03", Lane.CANCELED, None))
#: ``next`` accepts a canceled WP only with operator provenance, so its end-to-end fixture is all done.
_ALL_DONE: tuple[WpPlan, ...] = (("WP01", Lane.DONE, _EARLIER_DONE), ("WP02", Lane.DONE, _LATEST_DONE))


# ---------------------------------------------------------------------------
# Stamped: every WP terminal, at least one done, never reopened
# ---------------------------------------------------------------------------


def test_all_terminal_lanes_mission_is_stamped_with_the_latest_done_at(repo: Path) -> None:
    feature_dir = _mission(repo, "landed-lanes", _ALL_TERMINAL, mission_number=7)
    assert not mission_has_landed(feature_dir)

    result = BackfillMergedAtMigration().apply(repo)

    assert result.success, result.errors
    assert _meta(feature_dir)["merged_at"] == _LATEST_DONE
    assert mission_has_landed(feature_dir)
    assert result.changes_made == [f"landed-lanes: stamped merged_at {_LATEST_DONE} (latest done transition)"]
    assert result.warnings == []


def test_mission_number_is_not_needed_for_terminal_evidence(repo: Path) -> None:
    feature_dir = _mission(repo, "landed-unnumbered", _ALL_TERMINAL)

    [row] = backfill_merged_at(repo)

    assert (row.action, row.merged_at) == ("stamped", _LATEST_DONE)
    assert _meta(feature_dir)["merged_at"] == _LATEST_DONE


def test_naive_done_timestamp_is_normalized_to_aware_utc(repo: Path) -> None:
    feature_dir = _mission(repo, "naive-stamp", (("WP01", Lane.DONE, "2026-03-02T16:58:36"),))

    backfill_merged_at(repo)

    assert _meta(feature_dir)["merged_at"] == "2026-03-02T16:58:36+00:00"


def test_offset_done_timestamp_is_converted_to_utc(repo: Path) -> None:
    feature_dir = _mission(repo, "offset-stamp", (("WP01", Lane.DONE, "2026-01-01T02:00:00+02:00"), ("WP02", Lane.DONE, "2026-01-01T00:30:00+00:00")))

    backfill_merged_at(repo)

    # 02:00+02:00 is 00:00Z, so the 00:30Z transition is the latest (instant order, not string order).
    assert _meta(feature_dir)["merged_at"] == "2026-01-01T00:30:00+00:00"


# ---------------------------------------------------------------------------
# Not stamped (and reported): the shapes the review measured
# ---------------------------------------------------------------------------


def test_mission_number_with_planned_wps_is_not_stamped_and_is_reported(repo: Path) -> None:
    """The #5471 shape: ``doctor mission-state --fix`` numbered a Mission that never landed."""
    plans = tuple((f"WP0{index}", Lane.PLANNED, None) for index in range(1, 4))
    feature_dir = _mission(repo, "numbered-never-landed", plans, mission_number=79)
    before = (feature_dir / "meta.json").read_bytes()

    result = BackfillMergedAtMigration().apply(repo)

    assert (feature_dir / "meta.json").read_bytes() == before
    assert result.success
    assert result.changes_made == []
    assert result.warnings == [
        "merged_at not stamped on 1 Mission(s): not every work package is done or canceled: numbered-never-landed (WP01 planned, WP02 planned, WP03 planned)"
    ]
    assert not BackfillMergedAtMigration().detect(repo)


def test_legacy_numbered_slug_with_unfinished_wps_is_not_stamped(repo: Path) -> None:
    """A legacy ``NNN-`` Mission (no ``mission_id``, no topology) with one WP still in progress."""
    feature_dir = _mission(
        repo,
        "042-legacy-mission",
        (("WP01", Lane.DONE, _LATEST_DONE), ("WP02", Lane.IN_PROGRESS, None)),
        topology=None,
        mission_id=None,
        mission_number=42,
    )
    before = (feature_dir / "meta.json").read_bytes()

    [row] = backfill_merged_at(repo)

    assert (row.action, row.verdict) == ("skipped", LandingVerdict.UNFINISHED)
    assert row.detail == "WP02 in_progress"
    assert (feature_dir / "meta.json").read_bytes() == before


def test_legacy_numbered_slug_with_terminal_wps_is_stamped(repo: Path) -> None:
    """Non-vacuity for the legacy shape: the same Mission, every WP done, is stamped."""
    feature_dir = _mission(repo, "043-legacy-landed", (("WP01", Lane.DONE, _LATEST_DONE),), topology=None, mission_id=None, mission_number=43)

    backfill_merged_at(repo)

    assert _meta(feature_dir)["merged_at"] == _LATEST_DONE


def test_all_canceled_mission_is_not_stamped(repo: Path) -> None:
    feature_dir = _mission(repo, "all-canceled", (("WP01", Lane.CANCELED, None), ("WP02", Lane.CANCELED, None)), mission_number=5)
    before = (feature_dir / "meta.json").read_bytes()

    [row] = backfill_merged_at(repo)

    assert (row.action, row.verdict) == ("skipped", LandingVerdict.NO_DONE)
    assert (feature_dir / "meta.json").read_bytes() == before


def test_reopened_mission_is_never_stamped(repo: Path) -> None:
    from specify_cli.status import emit_mission_reopened

    feature_dir = _mission(repo, "reopened-mission", _ALL_TERMINAL, commit=False)
    meta = _meta(feature_dir)
    # ``mission reopen`` records the event and clears merged_*; reproduce that end state.
    _write_meta(feature_dir, {**meta, "merged_at": _EARLIER_DONE})
    event = emit_mission_reopened(
        feature_dir,
        mission_id=str(meta["mission_id"]),
        mission_slug="reopened-mission",
        reason="follow-up",
        reopened_by="tester",
        reopened_at="2026-04-01T00:00:00+00:00",
    )
    assert event is not None
    _write_meta(feature_dir, meta)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "reopen")
    before = (feature_dir / "meta.json").read_bytes()

    result = BackfillMergedAtMigration().apply(repo)

    assert (feature_dir / "meta.json").read_bytes() == before
    assert result.changes_made == []
    assert result.warnings == ["merged_at not stamped on 1 Mission(s): a MissionReopened event is recorded: reopened-mission"]
    assert not BackfillMergedAtMigration().detect(repo)


def test_missions_without_status_or_with_an_unreadable_log_are_reported(repo: Path) -> None:
    no_log = repo / "kitty-specs" / "no-log"
    _write_meta(no_log, {"mission_slug": "no-log", "mission_id": _mission_id("nolog"), "mission_type": "software-dev", "topology": "lanes"})
    corrupt = _mission(repo, "corrupt-log", _ALL_TERMINAL, commit=False)
    with (corrupt / "status.events.jsonl").open("a", encoding="utf-8") as log:
        log.write("{not json\n")

    rows = {row.slug: row for row in backfill_merged_at(repo)}

    assert (rows["no-log"].action, rows["no-log"].verdict) == ("skipped", LandingVerdict.NO_STATUS_LOG)
    assert (rows["corrupt-log"].action, rows["corrupt-log"].verdict) == ("error", LandingVerdict.UNREADABLE)
    assert "merged_at" not in _meta(no_log)
    assert "merged_at" not in _meta(corrupt)


def test_missions_with_merged_at_are_untouched(repo: Path) -> None:
    already = _mission(repo, "already-stamped", _ALL_TERMINAL, commit=False, merged_at="2025-12-01T00:00:00+00:00")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "already")
    before = (already / "meta.json").read_bytes()

    assert backfill_merged_at(repo) == []
    assert not BackfillMergedAtMigration().detect(repo)
    assert (already / "meta.json").read_bytes() == before


def test_dry_run_writes_nothing(repo: Path) -> None:
    feature_dir = _mission(repo, "dry-run-mission", _ALL_TERMINAL)
    before = (feature_dir / "meta.json").read_bytes()

    result = BackfillMergedAtMigration().apply(repo, dry_run=True)

    assert result.changes_made == [f"dry-run-mission: would stamp merged_at {_LATEST_DONE} (latest done transition)"]
    assert (feature_dir / "meta.json").read_bytes() == before


def test_running_twice_changes_nothing_the_second_time(repo: Path) -> None:
    lanes = _mission(repo, "twice-lanes", _ALL_TERMINAL)
    coord = _pre_marker_coordination_mission(repo)
    unfinished = _mission(repo, "twice-unfinished", (("WP01", Lane.IN_PROGRESS, None),))
    migration = BackfillMergedAtMigration()
    assert migration.detect(repo)

    first = migration.apply(repo)
    after_first = {path: (path / "meta.json").read_bytes() for path in (lanes, coord, unfinished)}
    second = migration.apply(repo)

    assert len(first.changes_made) == 2
    assert second.changes_made == []
    assert second.warnings == first.warnings  # the unfinished Mission is reported again, never written
    assert {path: (path / "meta.json").read_bytes() for path in after_first} == after_first
    assert not migration.detect(repo)


def test_migration_routes_to_the_tracked_partition_and_needs_git() -> None:
    assert BackfillMergedAtMigration.clone_local_effect is False
    assert BackfillMergedAtMigration.requires_git_repository is True
    assert BackfillMergedAtMigration.runs_on_worktrees is False


# ---------------------------------------------------------------------------
# Read through the door: a status that lives only on the coordination surface is seen
# ---------------------------------------------------------------------------

_LIVE_COORD_ID = "01KZLIVE0000000000000000AB"
_LIVE_COORD_SLUG = f"live-coord-{_LIVE_COORD_ID[:8]}"
_LIVE_COORD_BRANCH = f"kitty/mission-{_LIVE_COORD_SLUG}"


def _live_coordination_mission(repo: Path, coord_plans: Sequence[WpPlan], root_plans: Sequence[WpPlan]) -> Path:
    """A ``lanes_with_coord`` Mission whose coordination branch exists (no worktree) and differs from the root copy."""
    feature_dir = _mission(
        repo,
        _LIVE_COORD_SLUG,
        root_plans,
        topology="lanes_with_coord",
        mission_id=_LIVE_COORD_ID,
        coordination_branch=_LIVE_COORD_BRANCH,
    )
    _git(repo, "checkout", "-qb", _LIVE_COORD_BRANCH)
    (feature_dir / "status.events.jsonl").unlink()
    _seed_wps(feature_dir, _LIVE_COORD_SLUG, coord_plans)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "coordination status")
    _git(repo, "checkout", "-q", "main")
    return feature_dir


def test_status_only_on_the_coordination_branch_is_read_through_the_door(repo: Path) -> None:
    from specify_cli.status import StatusReadSource, resolve_status_read

    feature_dir = _live_coordination_mission(repo, coord_plans=_ALL_TERMINAL, root_plans=(("WP01", Lane.PLANNED, None),))
    assert resolve_status_read(repo, _LIVE_COORD_SLUG).source is StatusReadSource.COORD_BRANCH_REF

    [row] = backfill_merged_at(repo)

    assert (row.action, row.merged_at) == ("stamped", _LATEST_DONE)
    assert _meta(feature_dir)["merged_at"] == _LATEST_DONE


def test_terminal_root_copy_does_not_outvote_an_unfinished_coordination_branch(repo: Path) -> None:
    """Non-vacuity: the root checkout's copy is not the evidence while the coordination branch exists."""
    feature_dir = _live_coordination_mission(repo, coord_plans=(("WP01", Lane.IN_PROGRESS, None),), root_plans=_ALL_TERMINAL)

    [row] = backfill_merged_at(repo)

    assert (row.action, row.verdict, row.detail) == ("skipped", LandingVerdict.UNFINISHED, "WP01 in_progress")
    assert "merged_at" not in _meta(feature_dir)


# ---------------------------------------------------------------------------
# End to end: the case #7431's review measured (a pre-#4090 coordination Mission refusing).
# ---------------------------------------------------------------------------

_COORD_SLUG = "pre-marker-coord"
_COORD_ID = "01KZCQRD7P0000000000000ABC"


def _pre_marker_coordination_mission(repo: Path, plans: Sequence[WpPlan] = _ALL_DONE, **extra: object) -> Path:
    """A ``lanes_with_coord`` Mission whose coordination branch consolidation removed (never created here)."""
    return _mission(
        repo,
        _COORD_SLUG,
        plans,
        topology="lanes_with_coord",
        mission_id=_COORD_ID,
        coordination_branch=f"kitty/mission-{_COORD_SLUG}-{_COORD_ID[:8]}",
        **extra,
    )


def test_pre_marker_coordination_mission_reads_as_done_after_the_backfill(repo: Path) -> None:
    from runtime.next.committed_authority import mission_terminal_verdict
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.status import StatusReadSource, read_status_stream, reduce, resolve_status_read

    feature_dir = _pre_marker_coordination_mission(repo)

    # Before: the door refuses, and its remedy names the backfill, never "drop coordination_branch".
    with pytest.raises(CoordinationBranchDeleted) as refused:
        resolve_status_read(repo, _COORD_SLUG)
    assert "spec-kitty upgrade" in refused.value.next_step
    assert _LATEST_DONE in refused.value.next_step
    assert "doctor coordination --fix" not in refused.value.next_step
    assert mission_terminal_verdict(repo, _COORD_SLUG) == "none"
    assert read_landing_evidence(repo, _COORD_SLUG).merged_at == _LATEST_DONE

    assert BackfillMergedAtMigration().apply(repo).success

    # After: the door reads the consolidated target, and both readers agree the Mission is done.
    assert _meta(feature_dir)["merged_at"] == _LATEST_DONE
    surface = resolve_status_read(repo, _COORD_SLUG)
    assert surface.source is StatusReadSource.CONSOLIDATED_TARGET
    snapshot = reduce(read_status_stream(surface).transitions)
    assert {wp_id: str(state["lane"]) for wp_id, state in snapshot.work_packages.items()} == {"WP01": "done", "WP02": "done"}
    assert mission_terminal_verdict(repo, _COORD_SLUG) == "terminal"
    assert mission_has_landed(feature_dir)


def test_status_board_refuses_before_and_shows_done_after_the_backfill(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``agent tasks status`` on the real door, unmocked: refusal with the upgrade remedy, then done."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.tasks import app

    _pre_marker_coordination_mission(repo)
    monkeypatch.chdir(repo)
    runner = CliRunner()

    before = runner.invoke(app, ["status", "--mission", _COORD_SLUG, "--json"])
    assert before.exit_code == 1, before.output
    assert "spec-kitty upgrade" in json.loads(before.output)["error"]["message"]

    assert BackfillMergedAtMigration().apply(repo).success

    after = runner.invoke(app, ["status", "--mission", _COORD_SLUG, "--json"])
    assert after.exit_code == 0, after.output
    payload = json.loads(after.output)
    assert payload["by_lane"] == {"done": 2}
    assert [wp["lane"] for wp in payload["work_packages"]] == ["done", "done"]


def test_numbered_unfinished_deleted_coordination_branch_keeps_the_flatten_remedy(repo: Path) -> None:
    """#5471 on a coordination Mission: ``mission_number`` set, WPs planned -> the flatten remedy, no upgrade claim."""
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.status import resolve_status_read

    feature_dir = _pre_marker_coordination_mission(repo, (("WP01", Lane.PLANNED, None),), mission_number=12)

    with pytest.raises(CoordinationBranchDeleted) as refused:
        resolve_status_read(repo, _COORD_SLUG)
    assert "doctor coordination --fix" in refused.value.next_step
    assert "spec-kitty upgrade" not in refused.value.next_step
    assert backfill_merged_at(repo)[0].action == "skipped"
    assert "merged_at" not in _meta(feature_dir)
