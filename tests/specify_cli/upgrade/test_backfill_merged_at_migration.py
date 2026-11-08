"""The pre-#4090 ``merged_at`` backfill migration (#7433).

A Mission that landed before consolidation stamped ``merged_at`` carries ``mission_number`` but
no marker, so the one landed signal (``mission_runtime.mission_has_landed``) reads it as not
landed, and a coordination-topology one refuses with ``COORDINATION_BRANCH_DELETED`` (#7335).
Every fixture is a REAL git repository: the landing date comes from git, and the coordination
refusal is the read door's real verdict, not a mock.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

from kernel.clock import from_epoch
from mission_runtime import mission_has_landed
from specify_cli.migration.backfill_merged_at import (
    SOURCE_BASELINE_MERGE_COMMIT,
    SOURCE_MISSION_NUMBER_COMMIT,
    backfill_merged_at,
)
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.upgrade.migrations.m_4_0_0rc8_backfill_merged_at import BackfillMergedAtMigration
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

#: Fixed committer dates (epoch seconds) so the stamped value is exact.
_BASELINE_EPOCH = 1_767_225_600  # 2026-01-01T00:00:00Z
_NUMBER_EPOCH = 1_769_904_000  # 2026-02-01T00:00:00Z
_LATER_EPOCH = 1_772_323_200  # 2026-03-01T00:00:00Z


def _iso(epoch: int) -> str:
    return from_epoch(float(epoch)).isoformat()


def _git(repo: Path, *args: str, epoch: int | None = None) -> str:
    env = dict(os.environ)
    if epoch is not None:
        env["GIT_COMMITTER_DATE"] = f"@{epoch} +0000"
        env["GIT_AUTHOR_DATE"] = f"@{epoch} +0000"
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, env=env)
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
    _git(root, "commit", "-qm", "init", epoch=_BASELINE_EPOCH)
    return root


def _mission_id(tag: str) -> str:
    return ("01KZ" + tag.upper().replace("-", "") + "0" * 26)[:26]


def _write_meta(feature_dir: Path, meta: Mapping[str, object]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(dict(meta), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _seed_done(feature_dir: Path, slug: str, wp_id: str = "WP01") -> None:
    tasks = feature_dir / "tasks"
    tasks.mkdir(parents=True, exist_ok=True)
    (tasks / f"{wp_id}-work.md").write_text(f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\nexecution_mode: code_change\n---\n# {wp_id}\n", encoding="utf-8")
    for event_no, (from_lane, to_lane) in enumerate(((Lane.GENESIS, Lane.PLANNED), (Lane.PLANNED, Lane.APPROVED), (Lane.APPROVED, Lane.DONE))):
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{slug}-{wp_id}-{event_no}",
                mission_slug=slug,
                wp_id=wp_id,
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-01-0{event_no + 1}T00:00:00+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )


def _landed_mission(repo: Path, slug: str, *, topology: str = "lanes", **extra: object) -> Path:
    """A pre-#4090 landed Mission: committed once unnumbered, then numbered at landing (no merged_at)."""
    feature_dir = repo / "kitty-specs" / slug
    mission_id = _mission_id(slug)
    base: dict[str, object] = {
        "mission_slug": slug,
        "mission_id": mission_id,
        "mid8": mission_id[:8],
        "mission_type": "software-dev",
        "target_branch": "main",
        "topology": topology,
        "friendly_name": slug,
        "mission_number": None,
    }
    _write_meta(feature_dir, base)
    _seed_done(feature_dir, slug)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", f"plan {slug}", epoch=_BASELINE_EPOCH)
    _write_meta(feature_dir, {**base, "mission_number": 7, **extra})
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", f"land {slug}", epoch=_NUMBER_EPOCH)
    return feature_dir


def _meta(feature_dir: Path) -> dict[str, object]:
    loaded: dict[str, object] = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    return loaded


def test_landed_lanes_mission_is_stamped_from_the_commit_that_set_mission_number(repo: Path) -> None:
    feature_dir = _landed_mission(repo, "landed-lanes")
    # A later unrelated meta edit must not move the date: the OLDEST assigning commit wins.
    _write_meta(feature_dir, {**_meta(feature_dir), "friendly_name": "renamed"})
    _git(repo, "commit", "-qam", "rename", epoch=_LATER_EPOCH)
    assert not mission_has_landed(feature_dir)

    result = BackfillMergedAtMigration().apply(repo)

    assert result.success, result.errors
    assert _meta(feature_dir)["merged_at"] == _iso(_NUMBER_EPOCH)
    assert mission_has_landed(feature_dir)
    assert result.changes_made == [f"landed-lanes: stamped merged_at {_iso(_NUMBER_EPOCH)} (from {SOURCE_MISSION_NUMBER_COMMIT})"]


def test_baseline_merge_commit_date_wins_when_it_resolves(repo: Path) -> None:
    baseline = _git(repo, "rev-parse", "HEAD")
    feature_dir = _landed_mission(repo, "landed-baseline", baseline_merge_commit=baseline)

    [row] = backfill_merged_at(repo)

    assert (row.action, row.source, row.merged_at) == ("stamped", SOURCE_BASELINE_MERGE_COMMIT, _iso(_BASELINE_EPOCH))
    assert _meta(feature_dir)["merged_at"] == _iso(_BASELINE_EPOCH)


def test_unresolvable_baseline_falls_back_to_the_mission_number_commit(repo: Path) -> None:
    feature_dir = _landed_mission(repo, "landed-gone-baseline", baseline_merge_commit="deadbeef" * 5)

    [row] = backfill_merged_at(repo)

    assert (row.action, row.source) == ("stamped", SOURCE_MISSION_NUMBER_COMMIT)
    assert _meta(feature_dir)["merged_at"] == _iso(_NUMBER_EPOCH)


def test_reopened_mission_is_never_stamped(repo: Path) -> None:
    from specify_cli.status import emit_mission_reopened

    feature_dir = _landed_mission(repo, "reopened-mission")
    meta = _meta(feature_dir)
    # ``mission reopen`` records the event and clears merged_*; reproduce that end state.
    _write_meta(feature_dir, {**meta, "merged_at": _iso(_NUMBER_EPOCH)})
    event = emit_mission_reopened(
        feature_dir,
        mission_id=str(meta["mission_id"]),
        mission_slug="reopened-mission",
        reason="follow-up",
        reopened_by="tester",
        reopened_at=_iso(_LATER_EPOCH),
    )
    assert event is not None
    _write_meta(feature_dir, meta)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "reopen", epoch=_LATER_EPOCH)
    before = (feature_dir / "meta.json").read_bytes()

    result = BackfillMergedAtMigration().apply(repo)

    assert (feature_dir / "meta.json").read_bytes() == before
    assert result.changes_made == []
    assert any(warning.startswith("reopened-mission: merged_at not stamped") for warning in result.warnings)
    assert not BackfillMergedAtMigration().detect(repo)


def test_mission_without_git_evidence_is_skipped_and_reported(repo: Path) -> None:
    feature_dir = repo / "kitty-specs" / "never-committed"
    _write_meta(feature_dir, {"mission_slug": "never-committed", "mission_id": _mission_id("never"), "mission_number": 3, "mission_type": "software-dev"})
    before = (feature_dir / "meta.json").read_bytes()

    [row] = backfill_merged_at(repo)
    result = BackfillMergedAtMigration().apply(repo)

    assert row.action == "unresolved"
    assert (feature_dir / "meta.json").read_bytes() == before
    assert result.success
    assert result.changes_made == []
    assert result.warnings == [f"never-committed: merged_at not stamped: {row.reason}"]
    assert not BackfillMergedAtMigration().detect(repo)


def test_missions_that_need_no_marker_are_untouched(repo: Path) -> None:
    already = repo / "kitty-specs" / "already-stamped"
    _write_meta(already, {"mission_slug": "already-stamped", "mission_number": 2, "merged_at": "2025-12-01T00:00:00+00:00"})
    unlanded = repo / "kitty-specs" / "not-landed"
    _write_meta(unlanded, {"mission_slug": "not-landed", "mission_number": None})
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "others", epoch=_NUMBER_EPOCH)
    snapshot = {path: (path / "meta.json").read_bytes() for path in (already, unlanded)}

    assert backfill_merged_at(repo) == []
    assert not BackfillMergedAtMigration().detect(repo)
    assert {path: (path / "meta.json").read_bytes() for path in snapshot} == snapshot


def test_dry_run_writes_nothing(repo: Path) -> None:
    feature_dir = _landed_mission(repo, "dry-run-mission")
    before = (feature_dir / "meta.json").read_bytes()

    result = BackfillMergedAtMigration().apply(repo, dry_run=True)

    assert result.changes_made == [f"dry-run-mission: would stamp merged_at {_iso(_NUMBER_EPOCH)} (from {SOURCE_MISSION_NUMBER_COMMIT})"]
    assert (feature_dir / "meta.json").read_bytes() == before


def test_running_twice_changes_nothing_the_second_time(repo: Path) -> None:
    lanes = _landed_mission(repo, "twice-lanes")
    coord = _landed_mission(repo, "twice-coord", topology="lanes_with_coord", coordination_branch="kitty/mission-twice-coord")
    migration = BackfillMergedAtMigration()
    assert migration.detect(repo)

    first = migration.apply(repo)
    after_first = {path: (path / "meta.json").read_bytes() for path in (lanes, coord)}
    second = migration.apply(repo)

    assert len(first.changes_made) == 2
    assert second.changes_made == []
    assert second.warnings == []
    assert {path: (path / "meta.json").read_bytes() for path in after_first} == after_first
    assert not migration.detect(repo)


def test_migration_routes_to_the_tracked_partition_and_needs_git() -> None:
    assert BackfillMergedAtMigration.clone_local_effect is False
    assert BackfillMergedAtMigration.requires_git_repository is True
    assert BackfillMergedAtMigration.runs_on_worktrees is False


# ---------------------------------------------------------------------------
# End to end: the case #7431's review measured (a pre-#4090 coordination Mission refusing).
# ---------------------------------------------------------------------------

_COORD_SLUG = "pre-marker-coord"
_COORD_ID = "01KZCQRD7P0000000000000ABC"


def _pre_marker_coordination_mission(repo: Path) -> Path:
    """A landed ``lanes_with_coord`` Mission whose coordination branch consolidation removed."""
    feature_dir = repo / "kitty-specs" / _COORD_SLUG
    base: dict[str, object] = {
        "mission_slug": _COORD_SLUG,
        "mission_id": _COORD_ID,
        "mid8": _COORD_ID[:8],
        "mission_type": "software-dev",
        "target_branch": "main",
        "topology": "lanes_with_coord",
        "coordination_branch": f"kitty/mission-{_COORD_SLUG}-{_COORD_ID[:8]}",
        "friendly_name": "Pre-marker coordination Mission",
        "mission_number": None,
    }
    _write_meta(feature_dir, base)
    _seed_done(feature_dir, _COORD_SLUG)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "plan", epoch=_BASELINE_EPOCH)
    _write_meta(feature_dir, {**base, "mission_number": 12})
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "land", epoch=_NUMBER_EPOCH)
    return feature_dir


def test_pre_marker_coordination_mission_reads_as_done_after_the_backfill(repo: Path) -> None:
    from runtime.next.committed_authority import mission_terminal_verdict
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.status import StatusReadSource, read_status_stream, reduce, resolve_status_read

    feature_dir = _pre_marker_coordination_mission(repo)

    # Before: the door refuses, and its remedy names the backfill, never "drop coordination_branch".
    with pytest.raises(CoordinationBranchDeleted) as refused:
        resolve_status_read(repo, _COORD_SLUG)
    assert "spec-kitty upgrade" in refused.value.next_step
    assert "doctor coordination --fix" not in refused.value.next_step
    assert mission_terminal_verdict(repo, _COORD_SLUG) == "none"

    assert BackfillMergedAtMigration().apply(repo).success

    # After: the door reads the consolidated target, and both readers agree the Mission is done.
    surface = resolve_status_read(repo, _COORD_SLUG)
    assert surface.source is StatusReadSource.CONSOLIDATED_TARGET
    snapshot = reduce(read_status_stream(surface).transitions)
    assert {wp_id: str(state["lane"]) for wp_id, state in snapshot.work_packages.items()} == {"WP01": "done"}
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
    assert payload["by_lane"] == {"done": 1}
    assert [wp["lane"] for wp in payload["work_packages"]] == ["done"]


def test_unlanded_deleted_coordination_branch_keeps_the_flatten_remedy(repo: Path) -> None:
    """Non-vacuity for the remedy split: without ``mission_number`` the flatten remedy stands."""
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
    from specify_cli.status import resolve_status_read

    feature_dir = _pre_marker_coordination_mission(repo)
    _write_meta(feature_dir, {**_meta(feature_dir), "mission_number": None})

    with pytest.raises(CoordinationBranchDeleted) as refused:
        resolve_status_read(repo, _COORD_SLUG)
    assert "doctor coordination --fix" in refused.value.next_step
    assert "spec-kitty upgrade" not in refused.value.next_step
