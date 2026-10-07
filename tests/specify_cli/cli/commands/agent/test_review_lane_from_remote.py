"""Focused tests for ``_reconcile_review_lane`` (#5758): the lane is brought to the remote's view before review.

Real git and a real bare remote; the lane workspace is a small hand-built
``ResolvedWorkspace``. The end-to-end #5758 arms live in
``tests/terminus/test_review_sees_teammate_fix.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.agent import workflow
from specify_cli.git import origin_freshness
from specify_cli.git.origin_freshness import FreshnessState, FreshnessVerdict, ReviewLaneAction, ReviewLaneKind
from specify_cli.git.ref_advance import RefAdvanceDirtyWorktreeError, RefAdvanceError, RefAdvanceNonFastForwardError, RefResyncError
from specify_cli.review.lock import LOCK_DIR, LOCK_FILE
from specify_cli.workspace.context import ResolvedWorkspace
from tests._support.two_clone import attach_and_push, clone_from, isolated_git_env, make_bare_remote, unreachable_remote

pytestmark = [pytest.mark.git_repo]

LANE = "kitty/mission-demo-lane-a"
WP = "WP01"
DEAD_PID = 2**22 + 12345


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, text: str, message: str) -> str:
    (repo / "code.py").write_text(text)
    _git(repo, "add", "code.py")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


@dataclass
class Setup:
    repo: Path
    clone_b: Path
    worktree: Path

    def workspace(self, *, kind: str = "lane_workspace") -> ResolvedWorkspace:
        return ResolvedWorkspace(
            mission_slug="demo",
            wp_id=WP,
            execution_mode="code_change",
            mode_source="test",
            resolution_kind=kind,
            workspace_name="demo-lane-a",
            worktree_path=self.worktree,
            branch_name=LANE,
            lane_id="lane-a",
            lane_wp_ids=[WP],
        )

    def push_from_b(self, text: str = "v2\n") -> str:
        _git(self.clone_b, "fetch", "-q", "origin")
        _git(self.clone_b, "checkout", "-q", "-B", LANE, f"origin/{LANE}")
        sha = _commit(self.clone_b, text, "v2")
        _git(self.clone_b, "push", "-q", "origin", f"{LANE}:refs/heads/{LANE}")
        return sha

    def write_lock(self, *, agent: str, pid: int) -> None:
        lock = self.worktree / LOCK_DIR / LOCK_FILE
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text(json.dumps({"worktree_path": str(self.worktree), "wp_id": WP, "agent": agent, "started_at": "2026-01-01T00:00:00+00:00", "pid": pid}))


@pytest.fixture
def setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Setup:
    isolated_git_env(monkeypatch, tmp_path)
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-qb", "main")
    for key, value in (("user.name", "T"), ("user.email", "t@t.com"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / ".gitignore").write_text(".worktrees/\n")
    _commit(repo, "v1\n", "v1")
    _git(repo, "branch", LANE)
    bare = make_bare_remote(tmp_path)
    attach_and_push(repo, bare, ["main", LANE])
    clone_b = clone_from(bare, tmp_path / "b")
    worktree = repo / ".worktrees" / "demo-lane-a"
    _git(repo, "worktree", "add", "-q", str(worktree), LANE)
    return Setup(repo=repo, clone_b=clone_b, worktree=worktree)


def _reconcile(s: Setup, agent: str = "reviewer", *, workspace: ResolvedWorkspace | None = None) -> str | None:
    return workflow._reconcile_review_lane(workspace or s.workspace(), s.repo, WP, agent)


def _refused(s: Setup, capsys: pytest.CaptureFixture[str], agent: str = "reviewer") -> str:
    with pytest.raises(typer.Exit) as exc:
        _reconcile(s, agent)
    assert exc.value.exit_code == 1
    return " ".join(capsys.readouterr().out.split())


def test_up_to_date_lane_is_left_alone_silently(setup: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    before = _git(setup.repo, "rev-parse", LANE)

    assert _reconcile(setup) is None

    assert capsys.readouterr().out == ""
    assert _git(setup.repo, "rev-parse", LANE) == before


def test_behind_lane_is_fast_forwarded_in_every_checkout_and_the_tip_recorded(setup: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    remote_tip = setup.push_from_b()

    assert _reconcile(setup) is None

    assert _git(setup.repo, "rev-parse", LANE) == remote_tip
    assert (setup.worktree / "code.py").read_text() == "v2\n"
    assert _git(setup.repo, "rev-parse", f"refs/spec-kitty/lane-tip/{LANE}") == remote_tip
    assert f"Updated {LANE} from origin/{LANE} (1 commit)" in capsys.readouterr().out


def test_behind_lane_with_several_new_commits_says_commits(setup: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    setup.push_from_b("v2\n")
    remote_tip = setup.push_from_b("v3\n")

    assert _reconcile(setup) is None

    assert _git(setup.repo, "rev-parse", LANE) == remote_tip
    assert f"Updated {LANE} from origin/{LANE} (2 commits)" in capsys.readouterr().out


def test_diverged_lane_is_refused_before_any_lock(setup: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    setup.push_from_b()
    local = _commit(setup.worktree, "local\n", "local only")

    out = _refused(setup, capsys)

    assert "ORIGIN_LANE_DIVERGED" in out
    assert _git(setup.repo, "rev-parse", LANE) == local
    assert not (setup.worktree / LOCK_DIR / LOCK_FILE).exists()


def test_diverged_refusal_names_both_recoveries_and_the_environment_opt_out(setup: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    setup.push_from_b()
    _commit(setup.worktree, "local\n", "local only")

    out = _refused(setup, capsys)

    assert f"merge origin/{LANE}" in out
    assert f"git push origin {LANE}" in out
    assert "SPEC_KITTY_ORIGIN_CHECK=warn" in out
    assert "--origin-check" not in out


def test_diverged_lane_only_warns_when_the_environment_opts_out(setup: Setup, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("SPEC_KITTY_ORIGIN_CHECK", "warn")
    setup.push_from_b()
    local = _commit(setup.worktree, "local\n", "local only")

    assert _reconcile(setup) is None

    out = " ".join(capsys.readouterr().out.split())
    assert "Warning: ORIGIN_LANE_DIVERGED" in out
    assert "source: environment" in out
    assert _git(setup.repo, "rev-parse", LANE) == local


@pytest.mark.parametrize("case", ["not-a-descendant", "unknown-object"])
def test_raced_divergence_only_warns_when_the_environment_opts_out(
    setup: Setup, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    monkeypatch.setenv("SPEC_KITTY_ORIGIN_CHECK", "warn")
    remote_sha = {"not-a-descendant": _sibling_of_local(setup), "unknown-object": "1" * 40}[case]
    before = _git(setup.repo, "rev-parse", LANE)
    monkeypatch.setattr(origin_freshness, "plan_review_lane", lambda *_a, **_k: _forced_fast_forward(remote_sha))

    assert _reconcile(setup) is None

    assert "Warning: ORIGIN_LANE_DIVERGED" in capsys.readouterr().out
    assert _git(setup.repo, "rev-parse", LANE) == before


def test_behind_with_a_dirty_tracked_file_is_refused_and_the_file_survives(setup: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    setup.push_from_b()
    before = _git(setup.repo, "rev-parse", LANE)
    (setup.worktree / "code.py").write_text("my uncommitted edit\n")

    out = _refused(setup, capsys)

    assert "code.py" in out
    assert (setup.worktree / "code.py").read_text() == "my uncommitted edit\n"
    assert _git(setup.repo, "rev-parse", LANE) == before


def test_behind_with_a_live_foreign_review_lock_is_refused(setup: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    setup.push_from_b()
    before = _git(setup.repo, "rev-parse", LANE)
    setup.write_lock(agent="someone-else", pid=os.getpid())

    out = _refused(setup, capsys)

    assert "someone-else" in out
    assert _git(setup.repo, "rev-parse", LANE) == before


@pytest.mark.parametrize(("agent", "pid"), [("reviewer", os.getpid()), ("someone-else", DEAD_PID)], ids=["own-live-lock", "foreign-stale-lock"])
def test_own_or_stale_lock_does_not_block_the_fast_forward(setup: Setup, agent: str, pid: int) -> None:
    remote_tip = setup.push_from_b()
    setup.write_lock(agent=agent, pid=pid)

    assert _reconcile(setup) is None

    assert _git(setup.repo, "rev-parse", LANE) == remote_tip


def test_unreachable_remote_warns_and_continues_on_the_last_known_view(setup: Setup, capsys: pytest.CaptureFixture[str]) -> None:
    before = _git(setup.repo, "rev-parse", LANE)
    unreachable_remote(setup.repo)

    assert _reconcile(setup) is None

    out = capsys.readouterr().out
    assert "Warning:" in out and "ORIGIN_UNREACHABLE" in out
    assert _git(setup.repo, "rev-parse", LANE) == before


def test_missing_local_lane_returns_the_remote_tracking_ref_to_cut_from(setup: Setup) -> None:
    _git(setup.repo, "worktree", "remove", "--force", str(setup.worktree))
    _git(setup.repo, "branch", "-D", LANE)

    assert _reconcile(setup) == f"refs/remotes/origin/{LANE}"


def test_checkout_root_workspace_never_consults_the_remote(setup: Setup, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("plan_review_lane must not run for a checkout-root workspace")

    monkeypatch.setattr(origin_freshness, "plan_review_lane", boom)

    for kind in ("repo_root", "owned_checkout"):
        assert _reconcile(setup, workspace=setup.workspace(kind=kind)) is None


def _forced_fast_forward(remote_sha: str | None) -> ReviewLaneAction:
    verdict = FreshnessVerdict(LANE, "origin", FreshnessState.BEHIND, behind=1, remote_sha=remote_sha)
    return ReviewLaneAction(ReviewLaneKind.FAST_FORWARD, verdict, remote_sha=remote_sha, remote_ref=f"refs/remotes/origin/{LANE}")


def _sibling_of_local(setup: Setup) -> str:
    """A commit that exists locally but does not descend from the lane (a force-pushed rewrite)."""
    _git(setup.repo, "checkout", "-q", "--orphan", "rewritten")
    sha = _commit(setup.repo, "rewritten\n", "rewritten history")
    _git(setup.repo, "checkout", "-qf", "main")
    return sha


@pytest.mark.parametrize("case", ["not-a-descendant", "unknown-object", "no-sha"])
def test_fast_forward_to_an_unverified_remote_tip_fails_closed(
    setup: Setup, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    """The listed remote tip can change under a concurrent force-push before the fetch: never advance to it unchecked."""
    remote_sha = {"not-a-descendant": _sibling_of_local(setup), "unknown-object": "1" * 40, "no-sha": None}[case]
    before = _git(setup.repo, "rev-parse", LANE)
    monkeypatch.setattr(origin_freshness, "plan_review_lane", lambda *_a, **_k: _forced_fast_forward(remote_sha))

    out = _refused(setup, capsys)

    assert "ORIGIN_LANE_DIVERGED" in out
    assert _git(setup.repo, "rev-parse", LANE) == before


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (RefAdvanceNonFastForwardError(branch=LANE, old_sha="a" * 40, new_sha="b" * 40), "ORIGIN_LANE_DIVERGED"),
        (RefAdvanceError("Compare-and-swap advance failed: the ref changed"), "Could not update"),
        (
            RefAdvanceDirtyWorktreeError(worktree_path=Path("/w"), branch=LANE, old_sha="a" * 40, new_sha="b" * 40, dirty_entries=[" M code.py"]),
            "code.py",
        ),
    ],
    ids=["non-fast-forward", "cas-race", "dirty-checkout"],
)
def test_every_ref_advance_failure_is_a_refusal(
    setup: Setup, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: Exception, expected: str
) -> None:
    from specify_cli.git import ref_advance

    setup.push_from_b()

    def fail(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(ref_advance, "advance_branch_ref", fail)

    assert expected in _refused(setup, capsys)


def test_resync_failure_records_the_advanced_tip_and_refuses(setup: Setup, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.git import ref_advance
    from specify_cli.lanes import lane_tip

    remote_tip = setup.push_from_b()
    real_advance = ref_advance.advance_branch_ref
    recorded: list[tuple[str, str]] = []

    def advance_then_fail_resync(repo: Path, branch: str, new_sha: str, *, expected_old_sha: str) -> None:
        real_advance(repo, branch, new_sha, expected_old_sha=expected_old_sha)
        raise RefResyncError("worktree demo-lane-a could not be resynced")

    monkeypatch.setattr(ref_advance, "advance_branch_ref", advance_then_fail_resync)
    monkeypatch.setattr(lane_tip, "record_tip", lambda _root, branch, sha: recorded.append((branch, sha)))

    out = _refused(setup, capsys)

    assert recorded == [(LANE, remote_tip)]
    assert "was advanced to the remote tip" in out
    assert "could not be resynced" in out
    assert "re-run the review" in out
