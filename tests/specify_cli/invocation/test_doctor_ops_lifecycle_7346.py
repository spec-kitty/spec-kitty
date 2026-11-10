"""#7346: ``doctor ops --close-stale`` closes stale orphaned WP lifecycle records.

A work package's lifecycle record (``kitty-ops/lifecycle/<ulid>.json``) used to close
only when ``spec-kitty next`` reported a result, which also advances the Mission. The
stale sweep now closes every orphaned ``started`` record older than the threshold with
an ``abandoned`` record, in every checkout (each record once), commits the closures like
the Op sweep, and never touches Mission files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from kernel.clock import UTC, datetime, timedelta
from specify_cli import app as cli_app
from specify_cli.doctor.ops import close_stale_lifecycle_records
from specify_cli.invocation.lifecycle import (
    doctor_orphan_report,
    lifecycle_records_dir,
    read_lifecycle_records,
    write_paired_completion,
    write_started,
)
from tests.specify_cli.invocation._op_git import checkout_issue_branch, run_git

pytestmark = [pytest.mark.git_repo]

runner = CliRunner()

_NOW = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)
_MISSION = "01M6VYS1MISSION0000000000"
_REASON_24H = "abandoned by doctor ops --close-stale (older than 24h)"


def _started(root: Path, action: str, *, hours_ago: float, wp_id: str | None = "WP04") -> None:
    write_started(root, canonical_action_id=action, agent="claude", mission_id=_MISSION, wp_id=wp_id, at=_NOW - timedelta(hours=hours_ago))


def _repo(tmp_path: Path, *, track_lifecycle_on_primary: bool = True) -> Path:
    """A repository whose primary branch (``main``) tracks one paired lifecycle record."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    if track_lifecycle_on_primary:
        seed = write_started(repo, canonical_action_id="seed::seed", agent="claude", mission_id=_MISSION, at=_NOW - timedelta(days=30))
        write_paired_completion(repo, started=seed, phase="completed", at=_NOW - timedelta(days=30))
        run_git(repo, "add", "--force", "kitty-ops/lifecycle")
    run_git(repo, "commit", "-q", "--no-verify", "-m", "fixture base")
    return repo


def _commit_all(repo: Path, message: str) -> None:
    run_git(repo, "add", "--force", "-A")
    run_git(repo, "commit", "-q", "--no-verify", "-m", message)


def _abandoned(root: Path) -> list[str]:
    return sorted(record.canonical_action_id for record in read_lifecycle_records(root) if record.phase == "abandoned")


def _by_action(entries: list) -> dict[str, object]:
    return {entry.canonical_action_id: entry for entry in entries}


def test_only_stale_orphans_are_closed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    _started(repo, "implement::stale", hours_ago=48)
    _started(repo, "implement::fresh", hours_ago=1)
    _commit_all(repo, "orphans")

    entries = _by_action(close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW))

    assert _abandoned(repo) == ["implement::stale"]
    stale, fresh = entries["implement::stale"], entries["implement::fresh"]
    assert (stale.action_taken, stale.wp_id, stale.mission_id, stale.agent) == ("closed_abandoned", "WP04", _MISSION, "claude")
    assert stale.path is not None and stale.path.startswith("kitty-ops/lifecycle/")
    assert (fresh.action_taken, fresh.path) == ("none", None)
    (record,) = [r for r in read_lifecycle_records(repo) if r.phase == "abandoned"]
    assert record.reason == _REASON_24H
    assert record.metadata == {"closed_by": "doctor_sweep"}


def test_threshold_zero_closes_every_orphan(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    _started(repo, "implement::stale", hours_ago=48)
    _started(repo, "implement::fresh", hours_ago=1)

    close_stale_lifecycle_records(repo, threshold_hours=0.0, now=_NOW)

    assert _abandoned(repo) == ["implement::fresh", "implement::stale"]
    assert doctor_orphan_report(repo)["orphan_count"] == 0


def test_a_second_sweep_writes_nothing_new(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    _started(repo, "implement::stale", hours_ago=48)
    close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)
    before = sorted(path.name for path in lifecycle_records_dir(repo).iterdir())

    entries = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entries == []
    assert sorted(path.name for path in lifecycle_records_dir(repo).iterdir()) == before


def test_the_closures_are_committed_and_nothing_else_changes(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    mission_dir = repo / "kitty-specs" / "fixture-01M6VYS1"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text('{"mission_id": "' + _MISSION + '"}\n', encoding="utf-8")
    (mission_dir / "status.events.jsonl").write_text('{"wp_id": "WP04", "to_lane": "in_progress"}\n', encoding="utf-8")
    _commit_all(repo, "mission files")
    checkout_issue_branch(repo)
    _started(repo, "implement::stale", hours_ago=48)
    _commit_all(repo, "orphan")
    base = run_git(repo, "rev-parse", "HEAD")

    (entry,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entry.commit == "committed"
    assert run_git(repo, "rev-parse", "HEAD~1") == base
    changed = run_git(repo, "diff", "--name-status", base, "HEAD").splitlines()
    assert changed == [f"A\t{entry.path}"]
    assert not run_git(repo, "status", "--porcelain")


def test_the_commit_is_skipped_when_the_primary_branch_tracks_no_lifecycle_records(tmp_path: Path) -> None:
    repo = _repo(tmp_path, track_lifecycle_on_primary=False)
    checkout_issue_branch(repo)
    _started(repo, "implement::stale", hours_ago=48)
    head = run_git(repo, "rev-parse", "HEAD")

    (entry,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entry.action_taken == "closed_abandoned"
    assert entry.commit is not None and entry.commit.startswith("skipped:")
    assert "lifecycle records" in entry.commit
    assert run_git(repo, "rev-parse", "HEAD") == head


def test_a_protected_branch_refuses_the_commit_and_keeps_the_closure(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _started(repo, "implement::stale", hours_ago=48)
    head = run_git(repo, "rev-parse", "HEAD")

    (entry,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entry.commit == "not_committed:protected branch 'main'"
    assert run_git(repo, "rev-parse", "HEAD") == head
    assert _abandoned(repo) == ["implement::stale"]


def test_an_orphan_in_a_linked_worktree_is_closed_and_committed_there(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    worktree = tmp_path / "lane"
    run_git(repo, "worktree", "add", "-q", "-b", "lane-topic", str(worktree))
    _started(worktree, "implement::in-lane", hours_ago=48)
    _commit_all(worktree, "orphan in lane")
    lane_head = run_git(worktree, "rev-parse", "HEAD")

    (entry,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entry.commit == "committed"
    assert _abandoned(worktree) == ["implement::in-lane"]
    assert _abandoned(repo) == []
    assert run_git(worktree, "rev-parse", "HEAD~1") == lane_head


def test_a_record_held_by_two_checkouts_is_closed_once(tmp_path: Path) -> None:
    """Analysis finding I1: a record tracked on a shared branch is read in every checkout."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    _started(repo, "implement::shared", hours_ago=48)
    _commit_all(repo, "orphan on the issue branch")
    worktree = tmp_path / "lane"
    run_git(repo, "worktree", "add", "-q", "-b", "lane-topic", str(worktree))

    entries = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert [entry.canonical_action_id for entry in entries] == ["implement::shared"]
    assert _abandoned(repo) == ["implement::shared"]
    assert _abandoned(worktree) == []


@pytest.mark.parametrize(("hours_ago", "exit_code"), [(48.0, 0), (1.0, 1)])
def test_the_cli_reports_lifecycle_records_and_exits_on_fresh_orphans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hours_ago: float, exit_code: int) -> None:
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    write_started(repo, canonical_action_id="implement::cli", agent="claude", mission_id=_MISSION, wp_id="WP04", at=datetime.now(UTC) - timedelta(hours=hours_ago))
    monkeypatch.chdir(repo)

    result = runner.invoke(cli_app, ["doctor", "ops", "--close-stale", "--json"])

    assert result.exit_code == exit_code, result.output
    payload = json.loads(result.output)
    (entry,) = payload["lifecycle_records"]
    assert entry["canonical_action_id"] == "implement::cli"
    assert entry["action_taken"] == ("closed_abandoned" if exit_code == 0 else "none")
    assert payload["swept"] == 0
