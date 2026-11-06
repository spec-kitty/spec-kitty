"""FR-044 / NFR-002 / NFR-005 / SC-009: the clone-local lane-checkout migration.

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP10 (S6). Existing lane
worktrees, created before the one lane-checkout helper excluded the Mission's
status files, are brought in line through that helper's one exclusion
authority. Per worktree the outcome is exactly one of ``excluded``,
``flagged_redundant``, ``refused_lane_only_events``, ``skipped_mid_operation``
and ``already_excluded``. An event id held only by a lane copy is reported and
the worktree is left untouched: the migration never drops an event (C-009).

Portable on Linux and Windows (NFR-008): git's own commands, ``pathlib`` paths,
no symlinks, no case-sensitivity assumptions.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.upgrade.migrations.m_4_0_0rc8_lane_checkout_status_exclusion import (
    MIGRATION_ID,
    LaneCheckoutOutcome,
    LaneCheckoutStatusExclusionMigration,
    migrate_lane_checkouts,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION = "s6mig-01M6QY1M"
_MISSION_ID = "01M6QY1MAAAAAAAAAAAAAAAAAA"
_EVENTS = "status.events.jsonl"
_SNAPSHOT = "status.json"


@pytest.fixture(autouse=True)
def _confine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def _row(event_id: str) -> str:
    return json.dumps(
        {
            "actor": "claude",
            "at": "2026-11-06T12:00:00+00:00",
            "event_id": event_id,
            "evidence": None,
            "execution_mode": "worktree",
            "mission_slug": _MISSION,
            "force": False,
            "from_lane": "planned",
            "reason": None,
            "review_ref": None,
            "to_lane": "claimed",
            "wp_id": "WP01",
        },
        sort_keys=True,
    )


def _project(tmp_path: Path, lanes: tuple[str, ...] = ("lane-a",)) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "metadata.yaml").write_text("spec_kitty:\n  version: 4.0.0rc8\n", encoding="utf-8")
    mission_dir = repo / "kitty-specs" / _MISSION
    mission_dir.mkdir(parents=True)
    meta = {"mission_slug": _MISSION, "mission_id": _MISSION_ID, "topology": "lanes", "target_branch": "main", "mission_type": "software-dev"}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (mission_dir / _EVENTS).write_text(_row("01M6QY1MEVENT0000000000001") + "\n", encoding="utf-8")
    (mission_dir / _SNAPSHOT).write_text("{}\n", encoding="utf-8")
    write_lanes_json(
        mission_dir,
        LanesManifest(
            version=1,
            mission_slug=_MISSION,
            mission_id=_MISSION_ID,
            mission_branch=f"kitty/mission-{_MISSION}",
            target_branch="main",
            lanes=[ExecutionLane(lane_id=lane, wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0) for lane in lanes],
            computed_at="2026-11-06T12:00:00+00:00",
            computed_from="test",
        ),
    )
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    for lane in lanes:
        _git(repo, "worktree", "add", "-q", "-b", f"kitty/mission-{_MISSION}-{lane}", str(repo / ".worktrees" / f"{_MISSION}-{lane}"), "main")
    return repo


def _lane(repo: Path, lane: str = "lane-a") -> Path:
    return repo / ".worktrees" / f"{_MISSION}-{lane}"


def _copy(repo: Path, lane: str = "lane-a") -> Path:
    return _lane(repo, lane) / "kitty-specs" / _MISSION / _EVENTS


def _surface_append(repo: Path, event_id: str) -> None:
    with (repo / "kitty-specs" / _MISSION / _EVENTS).open("a", encoding="utf-8") as handle:
        handle.write(_row(event_id) + "\n")


def _lane_append(repo: Path, event_id: str, lane: str = "lane-a") -> None:
    with _copy(repo, lane).open("a", encoding="utf-8") as handle:
        handle.write(_row(event_id) + "\n")


def _only(repo: Path) -> object:
    items = migrate_lane_checkouts(repo, dry_run=False)
    assert len(items) == 1, items
    return items[0]


def _sparse_on(worktree: Path) -> bool:
    out = subprocess.run(["git", "-C", str(worktree), "config", "--get", "core.sparseCheckout"], capture_output=True, text=True, check=False).stdout
    return out.strip() == "true"


def _fingerprint(repo: Path) -> dict[str, str]:
    """Hash every file of both checkouts, every ref and every sparse configuration."""
    digest: dict[str, str] = {}
    for root in (repo, _lane(repo)):
        for path in sorted(root.rglob("*")):
            if path.is_file() and ".git" not in path.relative_to(root).parts[:1]:
                digest[str(path)] = path.read_bytes().hex()
    digest["refs"] = _git(repo, "for-each-ref", "--format=%(refname) %(objectname)")
    for worktree in (repo, _lane(repo)):
        sparse = Path(_git(worktree, "rev-parse", "--path-format=absolute", "--git-path", "info/sparse-checkout").strip())
        digest[f"sparse:{worktree}"] = sparse.read_text(encoding="utf-8") if sparse.exists() else "<absent>"
        digest[f"sparse-config:{worktree}"] = str(_sparse_on(worktree))
    return digest


def test_migration_excludes_clean_lane_worktree(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    assert LaneCheckoutStatusExclusionMigration().detect(repo)

    item = _only(repo)

    assert item.outcome is LaneCheckoutOutcome.EXCLUDED
    assert item.lane_id == "lane-a"
    assert _sparse_on(_lane(repo))
    assert not _copy(repo).exists(), "a clean copy leaves the disk"
    assert not LaneCheckoutStatusExclusionMigration().detect(repo)


def test_migration_flags_redundant_dirty_copy(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _surface_append(repo, "01M6QY1MEVENT0000000000002")
    _lane_append(repo, "01M6QY1MEVENT0000000000002")

    item = _only(repo)

    assert item.outcome is LaneCheckoutOutcome.FLAGGED_REDUNDANT
    assert item.event_ids_only_in_lane == ()
    assert _sparse_on(_lane(repo))
    assert _copy(repo).exists(), "git keeps a locally modified status file on disk"


def test_migration_refuses_lane_only_event_ids_untouched(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _lane_append(repo, "01M6QY1MLANEONLY0000000001")
    before = _fingerprint(repo)

    item = _only(repo)

    assert item.outcome is LaneCheckoutOutcome.REFUSED_LANE_ONLY_EVENTS
    assert item.event_ids_only_in_lane == ("01M6QY1MLANEONLY0000000001",)
    assert _fingerprint(repo) == before, "a refused worktree is left byte-for-byte untouched"
    result = LaneCheckoutStatusExclusionMigration().apply(repo)
    assert result.success
    assert any("01M6QY1MLANEONLY0000000001" in warning for warning in result.warnings), result.warnings


def test_migration_skips_mid_rebase(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    lane = _lane(repo)
    (lane / "conflict.txt").write_text("lane\n", encoding="utf-8")
    _git(lane, "add", "conflict.txt")
    _git(lane, "commit", "-q", "-m", "lane side")
    (repo / "conflict.txt").write_text("main\n", encoding="utf-8")
    _git(repo, "add", "conflict.txt")
    _git(repo, "commit", "-q", "-m", "main side")
    subprocess.run(["git", "-C", str(lane), "rebase", "main"], capture_output=True, text=True, check=False)
    before = _fingerprint(repo)

    item = _only(repo)

    assert item.outcome is LaneCheckoutOutcome.SKIPPED_MID_OPERATION
    assert _fingerprint(repo) == before
    subprocess.run(["git", "-C", str(lane), "rebase", "--abort"], capture_output=True, check=False)


def test_migration_second_run_changes_nothing(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _surface_append(repo, "01M6QY1MEVENT0000000000003")
    _lane_append(repo, "01M6QY1MEVENT0000000000003")
    migrate_lane_checkouts(repo, dry_run=False)
    after_first = _fingerprint(repo)

    second = migrate_lane_checkouts(repo, dry_run=False)

    assert [item.outcome for item in second] == [LaneCheckoutOutcome.ALREADY_EXCLUDED]
    assert _fingerprint(repo) == after_first, "a second run changes 0 files, refs and sparse configurations"
    assert LaneCheckoutStatusExclusionMigration().apply(repo).changes_made == []


def test_no_event_lost(tmp_path: Path) -> None:
    """NFR-002: every pre-existing event id is on the resolved surface or in the report."""
    repo = _project(tmp_path, lanes=("lane-a", "lane-b"))
    _surface_append(repo, "01M6QY1MEVENT0000000000004")
    _lane_append(repo, "01M6QY1MEVENT0000000000004", "lane-a")
    _lane_append(repo, "01M6QY1MLANEONLY0000000002", "lane-b")
    seen: set[str] = set()
    for lane in ("lane-a", "lane-b"):
        seen |= {json.loads(line)["event_id"] for line in _copy(repo, lane).read_text(encoding="utf-8").splitlines() if line.strip()}

    items = migrate_lane_checkouts(repo, dry_run=False)

    surface = {json.loads(line)["event_id"] for line in (repo / "kitty-specs" / _MISSION / _EVENTS).read_text(encoding="utf-8").splitlines() if line.strip()}
    reported = {event_id for item in items for event_id in item.event_ids_only_in_lane}
    assert seen <= surface | reported, seen - surface - reported
    assert _copy(repo, "lane-b").exists(), "the lane-only copy stays on disk"


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    before = _fingerprint(repo)

    result = LaneCheckoutStatusExclusionMigration().apply(repo, dry_run=True)

    assert result.success
    assert result.changes_made, "a dry run says what it would do"
    assert _fingerprint(repo) == before


def test_not_a_git_repository_is_not_applicable(tmp_path: Path) -> None:
    project = tmp_path / "plain"
    (project / ".kittify").mkdir(parents=True)
    migration = LaneCheckoutStatusExclusionMigration()
    assert migration.migration_id == MIGRATION_ID
    assert migration.clone_local_effect is True
    assert not migration.detect(project)
    assert migration.apply(project).changes_made == []
