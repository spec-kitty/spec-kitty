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

Outcomes are compared by value, never by identity: ``tests/upgrade/test_auto_discovery.py``
re-imports the migration modules, after which a module-level enum import here
names a different class object than the one the re-imported module returns.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.upgrade.ledger import MigrationLedger
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import MigrationResult
from specify_cli.upgrade.registry import migration_settled
from specify_cli.upgrade.runner import MigrationRunner
from specify_cli.upgrade.migrations.m_4_0_0rc8_lane_checkout_status_exclusion import (
    MIGRATION_ID,
    LaneCheckoutMigrationItem,
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


def _only(repo: Path) -> LaneCheckoutMigrationItem:
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

    assert item.outcome == "excluded"
    assert item.lane_id == "lane-a"
    assert _sparse_on(_lane(repo))
    assert not _copy(repo).exists(), "a clean copy leaves the disk"
    assert not LaneCheckoutStatusExclusionMigration().detect(repo)


def test_migration_flags_redundant_dirty_copy(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _surface_append(repo, "01M6QY1MEVENT0000000000002")
    _lane_append(repo, "01M6QY1MEVENT0000000000002")

    item = _only(repo)

    assert item.outcome == "flagged_redundant"
    assert item.event_ids_only_in_lane == ()
    assert _sparse_on(_lane(repo))
    assert _copy(repo).exists(), "git keeps a locally modified status file on disk"


def test_migration_refuses_lane_only_event_ids_untouched(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _lane_append(repo, "01M6QY1MLANEONLY0000000001")
    before = _fingerprint(repo)

    item = _only(repo)

    assert item.outcome == "refused_lane_only_events"
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

    assert item.outcome == "skipped_mid_operation"
    assert _fingerprint(repo) == before
    subprocess.run(["git", "-C", str(lane), "rebase", "--abort"], capture_output=True, check=False)


def test_migration_second_run_changes_nothing(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    _surface_append(repo, "01M6QY1MEVENT0000000000003")
    _lane_append(repo, "01M6QY1MEVENT0000000000003")
    migrate_lane_checkouts(repo, dry_run=False)
    after_first = _fingerprint(repo)

    second = migrate_lane_checkouts(repo, dry_run=False)

    assert [item.outcome for item in second] == ["already_excluded"]
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


def _upgrade_once(repo: Path) -> tuple[MigrationResult, str]:
    """One pass of this migration through the production runner (ledger selection, detect, can_apply, apply, record)."""
    migration = LaneCheckoutStatusExclusionMigration()
    outcome: tuple[MigrationResult, str] = MigrationRunner(repo)._apply_migration(migration, ProjectMetadata.load(repo / ".kittify"), dry_run=False)
    return outcome


def _settled(repo: Path) -> bool:
    settled: bool = migration_settled(MigrationLedger(repo), LaneCheckoutStatusExclusionMigration())
    return settled


def test_can_apply_refuses_while_a_lane_holds_lane_only_events(tmp_path: Path) -> None:
    """The refusal names the lane, the lane-only ids and the remedy; it is not an error."""
    repo = _project(tmp_path)
    _lane_append(repo, "01M6QY1MLANEONLY0000000003")

    ok, reason = LaneCheckoutStatusExclusionMigration().can_apply(repo)

    assert not ok
    assert "01M6QY1MLANEONLY0000000003" in reason
    assert "lane-a" in reason
    assert "spec-kitty upgrade" in reason


def test_refused_lane_is_retried_on_next_upgrade_once_reconciled(tmp_path: Path) -> None:
    """B2: an incomplete run never settles the migration; the next upgrade excludes the reconciled lane."""
    repo = _project(tmp_path, lanes=("lane-a", "lane-b"))
    _lane_append(repo, "01M6QY1MLANEONLY0000000004", "lane-b")
    before = _copy(repo, "lane-b").read_bytes()

    first, first_status = _upgrade_once(repo)

    assert first_status == "skipped", "an incomplete run is a skip: the upgrade does not fail"
    assert first.success
    assert any("01M6QY1MLANEONLY0000000004" in warning for warning in first.warnings), first.warnings
    assert not _settled(repo), "a run that left a lane unexcluded must not settle the migration"
    assert _copy(repo, "lane-b").read_bytes() == before, "the refused lane copy is untouched"

    _surface_append(repo, "01M6QY1MLANEONLY0000000004")  # the operator records the event on the surface

    second, second_status = _upgrade_once(repo)

    assert second_status == "applied", second.warnings
    assert _settled(repo)
    assert _sparse_on(_lane(repo, "lane-a"))
    assert _sparse_on(_lane(repo, "lane-b"))


def test_mid_rebase_lane_is_retried_on_next_upgrade(tmp_path: Path) -> None:
    """A lane skipped mid-operation also leaves the migration unsettled until the operation ends."""
    repo = _project(tmp_path)
    rebase_dir = Path(_git(_lane(repo), "rev-parse", "--path-format=absolute", "--git-path", "rebase-merge").strip())
    rebase_dir.mkdir(parents=True)

    _, first_status = _upgrade_once(repo)
    assert first_status == "skipped"
    assert not _settled(repo)

    rebase_dir.rmdir()
    _, second_status = _upgrade_once(repo)
    assert second_status == "applied"
    assert _settled(repo)
    assert _sparse_on(_lane(repo))


def test_doctor_names_lanes_lacking_the_exclusion_with_a_remedy(tmp_path: Path) -> None:
    """B2: a lane left unexcluded is reported by ``doctor sparse-checkout``, with its remedy."""
    from specify_cli.cli.commands._sparse_checkout_doctor import LANE_STATUS_NOT_EXCLUDED, find_lanes_lacking_exclusion

    repo = _project(tmp_path, lanes=("lane-a", "lane-b"))
    _lane_append(repo, "01M6QY1MLANEONLY0000000005", "lane-b")

    findings = {finding.lane_id: finding for finding in find_lanes_lacking_exclusion(repo, fix=False)}

    assert set(findings) == {"lane-a", "lane-b"}
    assert all(finding.code == LANE_STATUS_NOT_EXCLUDED for finding in findings.values())
    assert "01M6QY1MLANEONLY0000000005" in findings["lane-b"].detail
    assert "spec-kitty upgrade" in findings["lane-b"].remedy
    assert "doctor sparse-checkout --fix" in findings["lane-a"].remedy
    assert not _sparse_on(_lane(repo, "lane-a")), "a report changes nothing"


def test_doctor_fix_excludes_safe_lanes_and_keeps_reporting_the_refused_one(tmp_path: Path) -> None:
    from specify_cli.cli.commands._sparse_checkout_doctor import find_lanes_lacking_exclusion

    repo = _project(tmp_path, lanes=("lane-a", "lane-b"))
    _lane_append(repo, "01M6QY1MLANEONLY0000000006", "lane-b")
    before = _copy(repo, "lane-b").read_bytes()

    remaining = find_lanes_lacking_exclusion(repo, fix=True)

    assert [finding.lane_id for finding in remaining] == ["lane-b"]
    assert _sparse_on(_lane(repo, "lane-a"))
    assert _copy(repo, "lane-b").read_bytes() == before
    assert find_lanes_lacking_exclusion(repo, fix=False) == remaining


# ---------------------------------------------------------------------------
# #7276 adversarial-review follow-ups: an operator's own sparse patterns, and a
# lane whose exclusion fails, are never silently expanded or recorded as done.
# ---------------------------------------------------------------------------


def _sparse_file(worktree: Path) -> Path:
    raw = Path(_git(worktree, "rev-parse", "--git-path", "info/sparse-checkout").strip())
    return raw if raw.is_absolute() else worktree / raw


def test_non_cone_sparse_lane_keeps_its_patterns_and_gains_the_exclusion(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    lane = _lane(repo)
    _git(lane, "sparse-checkout", "set", "--no-cone", "/kitty-specs/", "/.gitignore")
    assert not (lane / ".kittify").exists()

    item = _only(repo)

    assert item.outcome.value == "excluded"
    lines = _sparse_file(lane).read_text(encoding="utf-8").splitlines()
    assert "/kitty-specs/" in lines and "/.gitignore" in lines and "/*" not in lines
    assert not _copy(repo).exists()
    assert not (lane / ".kittify").exists()  # the operator's restriction is not expanded
    assert _only(repo).outcome.value == "already_excluded"


def test_cone_mode_lane_is_refused_untouched_and_blocks_the_migration(tmp_path: Path) -> None:
    repo = _project(tmp_path)
    lane = _lane(repo)
    _git(lane, "sparse-checkout", "set", "--cone", "kitty-specs")
    before = _sparse_file(lane).read_text(encoding="utf-8")

    item = _only(repo)

    assert item.outcome.value == "refused_sparse_cone"
    assert _sparse_file(lane).read_text(encoding="utf-8") == before
    ok, reason = LaneCheckoutStatusExclusionMigration().can_apply(repo)
    assert not ok and "cone" in reason


def test_a_lane_whose_exclusion_fails_is_reported_and_the_run_is_not_a_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import lane_checkout

    repo = _project(tmp_path, lanes=("lane-a", "lane-b"))
    real = lane_checkout.exclude_lane_status_files

    def _fail_on_a(checkout: Path, mission_dir_name: str) -> None:
        if checkout.name.endswith("lane-a"):
            raise lane_checkout.LaneCheckoutError("git sparse-checkout reapply failed: boom")
        real(checkout, mission_dir_name)

    monkeypatch.setattr(lane_checkout, "exclude_lane_status_files", _fail_on_a)
    result = LaneCheckoutStatusExclusionMigration().apply(repo)

    assert result.success is False
    assert any("lane-a" in w and "boom" in w for w in result.warnings)
    assert any("lane-b" in c for c in result.changes_made)
    assert not _copy(repo, "lane-b").exists()
    assert _copy(repo, "lane-a").exists()
