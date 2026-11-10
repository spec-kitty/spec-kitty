"""NUL-delimited Git boundaries used by report-only recording."""

import re
import subprocess
from pathlib import Path

import pytest

from kernel.git import GitPath
from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
from specify_cli.coordination.commit_router import CommitRouterResult
from specify_cli.git import report_transaction
from specify_cli.git.report_transaction import _dirty_paths, _git, _index, _working

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def test_rename_keeps_both_unusual_path_endpoints(tmp_path: Path) -> None:
    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "work")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    old, new = "old\nname.md", "new\tname.md"
    (tmp_path / old).write_text("same content\n")
    git("add", "--", old)
    git("-c", "commit.gpgsign=false", "commit", "-qm", "seed")
    git("mv", "--", old, new)
    assert _dirty_paths(tmp_path) == {old, new}
    entries = _index(tmp_path, "analysis-report.md")
    assert len(entries) == 1
    assert entries[0].path == GitPath.parse(new)


def _init_seeded_repo(tmp_path: Path) -> None:
    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "work")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.invalid")
    (tmp_path / "seed.txt").write_text("seed\n")
    git("add", "-A")
    git("-c", "commit.gpgsign=false", "commit", "-qm", "seed")


# ---------------------------------------------------------------------------
# T003: ``_guard_unchanged_inputs`` — the concurrency re-check WP14 extracted
# from ``record_report_transaction`` (git/report_transaction.py, C901 15->13).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_guard_unchanged_inputs_passes_when_nothing_moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_seeded_repo(tmp_path)
    monkeypatch.setattr(report_transaction, "collect_material_inputs", lambda feature_dir, repo_root: {})
    head = _git(tmp_path, "rev-parse", "HEAD").strip()
    index = _index(tmp_path, "report.md")
    working = _working(tmp_path, "report.md")

    report_transaction._guard_unchanged_inputs(repo_root=tmp_path, feature_dir=tmp_path, relative="report.md", head=head, index=index, working=working, inputs={})


@pytest.mark.unit
def test_guard_unchanged_inputs_raises_when_head_moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_seeded_repo(tmp_path)
    monkeypatch.setattr(report_transaction, "collect_material_inputs", lambda feature_dir, repo_root: {})
    head = _git(tmp_path, "rev-parse", "HEAD").strip()
    index = _index(tmp_path, "report.md")
    working = _working(tmp_path, "report.md")
    (tmp_path / "other.txt").write_text("extra\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "extra"], cwd=tmp_path, check=True)

    with pytest.raises(ValueError, match="Repository changed before report commit"):
        report_transaction._guard_unchanged_inputs(
            repo_root=tmp_path, feature_dir=tmp_path, relative="report.md", head=head, index=index, working=working, inputs={}
        )


@pytest.mark.unit
def test_guard_unchanged_inputs_raises_when_working_tree_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_seeded_repo(tmp_path)
    monkeypatch.setattr(report_transaction, "collect_material_inputs", lambda feature_dir, repo_root: {})
    head = _git(tmp_path, "rev-parse", "HEAD").strip()
    index = _index(tmp_path, "report.md")
    working = _working(tmp_path, "report.md")
    (tmp_path / "seed.txt").write_text("changed\n")

    with pytest.raises(ValueError, match="Repository changed before report commit"):
        report_transaction._guard_unchanged_inputs(
            repo_root=tmp_path, feature_dir=tmp_path, relative="report.md", head=head, index=index, working=working, inputs={}
        )


@pytest.mark.unit
def test_guard_unchanged_inputs_raises_when_material_inputs_changed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _init_seeded_repo(tmp_path)
    monkeypatch.setattr(report_transaction, "collect_material_inputs", lambda feature_dir, repo_root: {"drifted": {"path": "x"}})
    head = _git(tmp_path, "rev-parse", "HEAD").strip()
    index = _index(tmp_path, "report.md")
    working = _working(tmp_path, "report.md")

    with pytest.raises(ValueError, match="Repository changed before report commit"):
        report_transaction._guard_unchanged_inputs(
            repo_root=tmp_path, feature_dir=tmp_path, relative="report.md", head=head, index=index, working=working, inputs={}
        )


# ---------------------------------------------------------------------------
# T003: ``_commit_report`` — the ``commit_for_mission`` call plus outcome
# interpretation WP14 extracted into its own helper (WP14 renders through it).
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_commit_report_returns_outcome_on_committed_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outcome = CommitRouterResult(status="committed", placement_ref="refs/heads/work", commit_hash="abc123")
    monkeypatch.setattr(report_transaction, "commit_for_mission", lambda **_kwargs: outcome)

    result = report_transaction._commit_report(
        repo_root=tmp_path, feature_dir=tmp_path / "kitty-specs" / "m", report=tmp_path / "analysis-report.md", message="msg", target_branch="work"
    )

    assert result is outcome


@pytest.mark.unit
@pytest.mark.parametrize(
    ("outcome", "expected_message"),
    [
        (
            CommitRouterResult(status="unchanged", placement_ref="refs/heads/work", reason="no_op_no_changes"),
            "Report commit did not complete: unchanged",
        ),
        (
            CommitRouterResult(status="no_op_wrong_surface", placement_ref="refs/heads/work"),
            "Report commit did not complete: no_op_wrong_surface",
        ),
        (CommitRouterResult(status="error", placement_ref="refs/heads/work", diagnostic="boom"), "boom"),
        (
            CommitRouterResult(status="committed", placement_ref="refs/heads/work", commit_hash=None),
            # B4 (cycle 2 review): the OLD message here -- "Report commit did
            # not complete: committed" -- was contradictory: ``status`` IS
            # "committed". Named the real problem (missing hash) instead.
            "Report commit did not complete: committed status without a resolved commit hash",
        ),
    ],
    ids=["unchanged", "no_op_wrong_surface", "error", "committed_without_hash"],
)
def test_commit_report_raises_unless_cleanly_committed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: CommitRouterResult, expected_message: str) -> None:
    monkeypatch.setattr(report_transaction, "commit_for_mission", lambda **_kwargs: outcome)

    with pytest.raises(report_transaction.ReportCommitRefused, match=re.escape(expected_message)):
        report_transaction._commit_report(
            repo_root=tmp_path, feature_dir=tmp_path / "kitty-specs" / "m", report=tmp_path / "analysis-report.md", message="msg", target_branch="work"
        )


@pytest.mark.unit
def test_commit_report_raises_when_a_non_caller_surface_is_refused_despite_committed_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WP14 review correction (round 2, binding): the legacy top-level ``status``

    is only the CALLER-partition projection (contract rule 4) -- a
    ``"committed"`` top-level status must never be trusted alone when a SPLIT
    batch's OTHER surface was refused. ``_commit_report`` must cross-check
    ``commit_outcome_exit_code`` against every surface, not just inspect
    ``outcome.status``.

    Mutation-sensitive: deleting the ``commit_outcome_exit_code(outcome) != 0``
    clause from ``_commit_report`` (leaving only the ``status`` / ``commit_hash``
    checks) makes this test fail, because ``status`` here IS ``"committed"``.
    """
    mixed = CommitRouterResult(
        status="committed",
        placement_ref="refs/heads/work",
        commit_hash="abc1234567890",
        surfaces=(
            SurfaceOutcome(surface="primary", branch="refs/heads/work", status="committed", commit_hash="abc1234567890", committed=("report.md",)),
            SurfaceOutcome(
                surface="coordination",
                branch="kitty/mission-m-01ABCDEF",
                status="refused",
                commit_hash=None,
                refused=(PathFate(path="kitty-specs/m/status.events.jsonl", reason="STATUS_LOCK_HELD"),),
            ),
        ),
    )
    monkeypatch.setattr(report_transaction, "commit_for_mission", lambda **_kwargs: mixed)

    expected = "Report committed on its own surface, but a sibling surface was refused or errored"
    with pytest.raises(report_transaction.ReportCommitRefused, match=re.escape(expected)) as excinfo:
        report_transaction._commit_report(
            repo_root=tmp_path, feature_dir=tmp_path / "kitty-specs" / "m", report=tmp_path / "analysis-report.md", message="msg", target_branch="work"
        )

    # B4 (cycle 2 review): the raised exception carries the router's own
    # typed outcome -- the caller renders from THIS object, never a second,
    # hand-rolled re-parse of a serialized dict.
    assert excinfo.value.outcome is mixed
