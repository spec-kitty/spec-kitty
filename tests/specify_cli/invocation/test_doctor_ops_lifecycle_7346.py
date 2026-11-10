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

from kernel.clock import UTC, datetime, now_utc, timedelta
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
    # The sweep's own commit runs git without run_git's -c identity (linked worktrees share this config).
    run_git(repo, "config", "user.email", "fixture@example.com")
    run_git(repo, "config", "user.name", "Fixture")
    run_git(repo, "config", "commit.gpgsign", "false")
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
    assert record.metadata == {"closed_by": "doctor_sweep", "closes_started_at": (_NOW - timedelta(hours=48)).isoformat()}


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
    write_started(repo, canonical_action_id="implement::cli", agent="claude", mission_id=_MISSION, wp_id="WP04", at=now_utc() - timedelta(hours=hours_ago))
    monkeypatch.chdir(repo)

    result = runner.invoke(cli_app, ["doctor", "ops", "--close-stale", "--json"])

    assert result.exit_code == exit_code, result.output
    payload = json.loads(result.output)
    (entry,) = payload["lifecycle_records"]
    assert entry["canonical_action_id"] == "implement::cli"
    assert entry["action_taken"] == ("closed_abandoned" if exit_code == 0 else "none")
    assert payload["swept"] == 0


def test_two_identical_started_records_in_one_checkout_are_both_closed(tmp_path: Path) -> None:
    """This repository holds such pairs: the cross-checkout dedupe must count occurrences, not collapse them."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    at = _NOW - timedelta(hours=48)
    for _ in range(2):
        write_started(repo, canonical_action_id="implement::twin", agent="claude", mission_id=_MISSION, wp_id="WP03", at=at)
    _commit_all(repo, "twin orphans")
    worktree = tmp_path / "lane"
    run_git(repo, "worktree", "add", "-q", "-b", "lane-topic", str(worktree))

    entries = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert [entry.action_taken for entry in entries] == ["closed_abandoned", "closed_abandoned"]
    assert _abandoned(repo) == ["implement::twin", "implement::twin"]
    assert doctor_orphan_report(repo)["orphan_count"] == 0
    assert _abandoned(worktree) == []


def test_a_second_sweep_does_not_close_a_shared_record_again_in_a_worktree(tmp_path: Path) -> None:
    """WP02 review B1, scenario 1: once the root checkout closed it, the worktree's open copy is not closed again."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    _started(repo, "implement::shared", hours_ago=48)
    _commit_all(repo, "orphan on the issue branch")
    worktree = tmp_path / "lane"
    run_git(repo, "worktree", "add", "-q", "-b", "lane-topic", str(worktree))
    close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    entries = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entries == []
    assert _abandoned(repo) == ["implement::shared"]
    assert _abandoned(worktree) == []


def test_a_record_completed_in_the_root_checkout_is_not_closed_in_a_stale_worktree(tmp_path: Path) -> None:
    """WP02 review B1, scenario 2: a stale worktree's open copy of a record the root already paired stays alone."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    started = write_started(repo, canonical_action_id="implement::shared", agent="claude", mission_id=_MISSION, wp_id="WP04", at=_NOW - timedelta(hours=48))
    _commit_all(repo, "orphan on the issue branch")
    worktree = tmp_path / "lane"
    run_git(repo, "worktree", "add", "-q", "-b", "lane-topic", str(worktree))
    write_paired_completion(repo, started=started, phase="completed", at=_NOW - timedelta(hours=47))
    _commit_all(repo, "completed in the root checkout")

    entries = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entries == []
    assert _abandoned(worktree) == []


def test_a_record_completed_in_a_later_checkout_is_not_closed_in_an_earlier_one(tmp_path: Path) -> None:
    """WP02 review B2: the root checkout's open copy stays alone when a worktree holds the completion."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    started = write_started(repo, canonical_action_id="implement::shared", agent="claude", mission_id=_MISSION, wp_id="WP04", at=_NOW - timedelta(hours=48))
    _commit_all(repo, "orphan on the issue branch")
    worktree = tmp_path / "lane"
    run_git(repo, "worktree", "add", "-q", "-b", "lane-topic", str(worktree))
    write_paired_completion(worktree, started=started, phase="completed", at=_NOW - timedelta(hours=47))
    _commit_all(worktree, "completed in the lane")

    entries = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entries == []
    assert _abandoned(repo) == []


def test_completions_reported_from_different_checkouts_close_nothing(tmp_path: Path) -> None:
    """WP02 review B3: one group, each work package completed in a different checkout."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    first = write_started(repo, canonical_action_id="implement::implement", agent="claude", mission_id=_MISSION, wp_id="WP01", at=_NOW - timedelta(hours=50))
    second = write_started(repo, canonical_action_id="implement::implement", agent="claude", mission_id=_MISSION, wp_id="WP02", at=_NOW - timedelta(hours=49))
    _commit_all(repo, "two starts on the issue branch")
    worktree = tmp_path / "lane"
    run_git(repo, "worktree", "add", "-q", "-b", "lane-topic", str(worktree))
    write_paired_completion(worktree, started=first, phase="completed", at=_NOW - timedelta(hours=48))
    _commit_all(worktree, "WP01 completed in the lane")
    write_paired_completion(repo, started=second, phase="completed", at=_NOW - timedelta(hours=48))
    _commit_all(repo, "WP02 completed in the root checkout")

    entries = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entries == []
    assert (_abandoned(repo), _abandoned(worktree)) == ([], [])
    run_git(repo, "merge", "-q", "--no-edit", "lane-topic")
    assert doctor_orphan_report(repo)["orphan_count"] == 0
    assert sum(1 for record in read_lifecycle_records(repo) if record.phase != "started" and record.canonical_action_id == "implement::implement") == 2


def test_the_closure_names_the_work_package_that_has_no_completion(tmp_path: Path) -> None:
    """WP02 review B3: a completion pairs its own work package's started record, not the latest one."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    write_started(repo, canonical_action_id="implement::implement", agent="claude", mission_id=_MISSION, wp_id="WP01", at=_NOW - timedelta(hours=50))
    second = write_started(repo, canonical_action_id="implement::implement", agent="claude", mission_id=_MISSION, wp_id="WP02", at=_NOW - timedelta(hours=49))
    write_paired_completion(repo, started=second, phase="completed", at=_NOW - timedelta(hours=48))

    (entry,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert (entry.wp_id, entry.action_taken) == ("WP01", "closed_abandoned")
    (closure,) = [record for record in read_lifecycle_records(repo) if record.phase == "abandoned"]
    assert closure.wp_id == "WP01"


def test_exact_matches_pair_before_any_fallback() -> None:
    """WP02 review N1: a completion with no matching work package never takes another's match.

    Read order: started WP02, started WP01, started WP02 (a retry); then a completion
    for WP09 (no match) and one for WP02. WP02's completion pairs the WP02 retry (the
    latest one started before it, as ``spec-kitty next`` pairs), the unmatched
    completion takes the oldest remaining record, and WP01 stays unpaired.
    """
    from specify_cli.doctor.ops import _unpaired_ids
    from specify_cli.invocation.record import ProfileInvocationRecord

    def record(phase: str, wp_id: str, minutes: int) -> ProfileInvocationRecord:
        return ProfileInvocationRecord.from_dict(
            {
                "canonical_action_id": "implement::implement",
                "phase": phase,
                "at": (datetime(2026, 11, 1, tzinfo=UTC) + timedelta(minutes=minutes)).isoformat(),
                "agent": "claude",
                "mission_id": "01M6VYS1MISSION0000000000",
                "wp_id": wp_id,
            }
        )

    first, other, retry = record("started", "WP02", 0), record("started", "WP01", 1), record("started", "WP02", 2)
    records = [first, other, retry, record("completed", "WP09", 3), record("completed", "WP02", 4)]

    assert _unpaired_ids(records) == {id(other)}


def test_a_retry_closed_across_checkouts_is_not_closed_again(tmp_path: Path) -> None:
    """Pre-PR review M1: an ``abandoned`` record pairs the exact record it closes, so a second sweep is a no-op."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    write_started(repo, canonical_action_id="implement::implement", agent="claude", mission_id=_MISSION, wp_id="WP04", at=_NOW - timedelta(hours=50))
    retry = write_started(repo, canonical_action_id="implement::implement", agent="claude", mission_id=_MISSION, wp_id="WP04", at=_NOW - timedelta(hours=49))
    _commit_all(repo, "a start and its retry on the issue branch")
    worktree = tmp_path / "lane"
    run_git(repo, "worktree", "add", "-q", "-b", "lane-topic", str(worktree))
    write_paired_completion(worktree, started=retry, phase="completed", at=_NOW - timedelta(hours=48))
    _commit_all(worktree, "the retry completed in the lane")

    (first,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)
    second = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert first.started_at == (_NOW - timedelta(hours=50)).isoformat()
    assert second == []
    assert _abandoned(repo) == ["implement::implement"]
    assert _abandoned(worktree) == []


def test_a_retry_completed_in_the_same_checkout_leaves_the_first_start_to_close(tmp_path: Path) -> None:
    """Pre-PR review m2: a completion pairs the latest record started before it, so the stale first start is closed."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    write_started(repo, canonical_action_id="implement::implement", agent="claude", mission_id=_MISSION, wp_id="WP01", at=_NOW - timedelta(hours=50))
    retry = write_started(repo, canonical_action_id="implement::implement", agent="claude", mission_id=_MISSION, wp_id="WP01", at=_NOW - timedelta(hours=10))
    write_paired_completion(repo, started=retry, phase="completed", at=_NOW - timedelta(hours=9))

    (entry,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entry.started_at == (_NOW - timedelta(hours=50)).isoformat()
    assert entry.action_taken == "closed_abandoned"
    assert doctor_orphan_report(repo)["orphan_count"] == 0


def test_an_unwritable_closure_is_reported_and_the_sweep_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    _started(repo, "implement::stale", hours_ago=48)

    def refuse(*_args: object, **_kwargs: object) -> Path:
        raise OSError("read-only file system")

    monkeypatch.setattr("specify_cli.doctor.ops.write_abandoned_completion", refuse)

    (entry,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entry.action_taken == "none"
    assert entry.error is not None and "read-only file system" in entry.error
    assert entry.commit is None


def test_an_unreadable_lifecycle_store_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    _started(repo, "implement::stale", hours_ago=48)

    def unreadable(_root: Path) -> list[object]:
        raise OSError("permission denied")

    monkeypatch.setattr("specify_cli.doctor.ops.read_lifecycle_records", unreadable)

    assert close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW) == []


def test_a_commit_that_cannot_start_is_reported_and_the_closure_kept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pre-PR review m1: a failure building the committer never crashes the sweep."""
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    _started(repo, "implement::stale", hours_ago=48)

    def broken(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("charter unavailable")

    monkeypatch.setattr("specify_cli.invocation.executor.ProfileInvocationExecutor", broken)

    (entry,) = close_stale_lifecycle_records(repo, threshold_hours=24.0, now=_NOW)

    assert entry.action_taken == "closed_abandoned"
    assert entry.commit is not None and entry.commit.startswith("not_committed:")
    assert "charter unavailable" in entry.commit
    assert _abandoned(repo) == ["implement::stale"]


def test_the_cli_text_report_lists_lifecycle_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _repo(tmp_path)
    checkout_issue_branch(repo)
    write_started(repo, canonical_action_id="implement::stale", agent="claude", mission_id=_MISSION, wp_id="WP04", at=now_utc() - timedelta(hours=48))
    write_started(repo, canonical_action_id="implement::fresh", agent="claude", mission_id=_MISSION, wp_id="WP05", at=now_utc() - timedelta(hours=1))
    monkeypatch.chdir(repo)

    result = runner.invoke(cli_app, ["doctor", "ops", "--close-stale"], terminal_width=200)

    assert result.exit_code == 1, result.output
    assert "Lifecycle records" in result.output
    assert "1 closed as abandoned, 1 fresh" in result.output
    assert "Fresh lifecycle records remain open" in result.output
