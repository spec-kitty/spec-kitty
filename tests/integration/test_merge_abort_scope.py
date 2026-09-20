"""Regression tests for ``spec-kitty merge --abort`` destructive-op scoping (#4754).

Pre-fix, ``_dispatch_abort`` called ``abort_git_merge(repo_root)`` UNCONDITIONALLY
whenever ``MERGE_HEAD`` existed in ``repo_root`` -- even when NO spec-kitty merge
state was active. Since the merge pipeline never runs ``git merge`` against
``repo_root`` (only inside spec-kitty-owned worktrees), a ``MERGE_HEAD`` found
there is always the OPERATOR'S OWN in-progress merge. The bug destroyed it,
printing the contradictory pair "No active merge state to abort." followed by
"Aborted in-progress git merge."

Post-fix: a git-level merge abort only ever runs when active spec-kitty merge
state exists, scoped to that mission's own merge workspace -- never
``repo_root`` -- and messaging is internally consistent (FR-005/FR-006).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import specify_cli.cli.commands.merge as merge_mod
from specify_cli.cli.commands.merge import _dispatch_abort
from specify_cli.merge.state import MergeState, load_state, save_state
from specify_cli.merge.workspace import get_merge_workspace_path

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _init_repo(repo_root: Path) -> str:
    """Initialize a real git repo with one commit; return the branch name."""
    assert _git("init", "-q", cwd=repo_root).returncode == 0
    assert _git("config", "user.email", "test@example.com", cwd=repo_root).returncode == 0
    assert _git("config", "user.name", "Test User", cwd=repo_root).returncode == 0
    (repo_root / "file.txt").write_text("base\n", encoding="utf-8")
    assert _git("add", "file.txt", cwd=repo_root).returncode == 0
    assert _git("commit", "-q", "-m", "base commit", cwd=repo_root).returncode == 0
    branch = _git("branch", "--show-current", cwd=repo_root).stdout.strip()
    assert branch
    return branch


def _create_conflicting_merge(repo_root: Path, base_branch: str) -> None:
    """Diverge two branches on the same file and leave an unresolved conflict.

    After this call, ``MERGE_HEAD`` exists in *repo_root* and ``file.txt``
    carries unmerged conflict markers -- a genuine, unresolved in-progress
    merge exactly as an operator would leave it mid-resolution.
    """
    assert _git("checkout", "-q", "-b", "incoming", cwd=repo_root).returncode == 0
    (repo_root / "file.txt").write_text("incoming change\n", encoding="utf-8")
    assert _git("commit", "-q", "-am", "incoming change", cwd=repo_root).returncode == 0

    assert _git("checkout", "-q", base_branch, cwd=repo_root).returncode == 0
    (repo_root / "file.txt").write_text("base branch change\n", encoding="utf-8")
    assert _git("commit", "-q", "-am", "base branch change", cwd=repo_root).returncode == 0

    merge_result = _git("merge", "incoming", cwd=repo_root)
    assert merge_result.returncode != 0, "expected a real conflict"
    assert (repo_root / ".git" / "MERGE_HEAD").exists()


class TestAbortNeverTouchesRepoRootWithoutSpecKittyState:
    """T017: red-first #4754 -- the operator's own merge must survive --abort."""

    def test_abort_preserves_users_in_progress_merge_when_no_spec_kitty_state(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """No spec-kitty merge state anywhere: --abort must not touch repo_root.

        Pre-fix this was RED: ``_dispatch_abort`` ran ``git merge --abort`` in
        ``repo_root`` unconditionally, destroying the operator's own conflict
        resolution and the MERGE_HEAD marker, while still printing "No active
        merge state to abort." -- a contradictory pair with "Aborted
        in-progress git merge.".
        """
        branch = _init_repo(tmp_path)
        _create_conflicting_merge(tmp_path, branch)

        merge_head_path = tmp_path / ".git" / "MERGE_HEAD"
        merge_head_sha_before = merge_head_path.read_text(encoding="utf-8")
        conflicted_contents_before = (tmp_path / "file.txt").read_text(encoding="utf-8")
        assert "<<<<<<<" in conflicted_contents_before

        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)

        _dispatch_abort(tmp_path, None)

        output = capsys.readouterr().out
        # The genuine bug: MERGE_HEAD destroyed and the operator's conflict
        # resolution work wiped out.
        assert merge_head_path.exists(), "spec-kitty merge --abort destroyed the operator's own in-progress git merge (#4754 regression)"
        assert merge_head_path.read_text(encoding="utf-8") == merge_head_sha_before
        assert (tmp_path / "file.txt").read_text(encoding="utf-8") == conflicted_contents_before

        # FR-006: messaging must be internally consistent -- never claim an
        # abort happened when nothing was aborted.
        assert "No active merge state to abort." in output
        assert "Aborted in-progress git merge" not in output


class TestAbortActiveStateParity:
    """NFR-002 parity: the fix must not regress the legitimate abort path."""

    def test_abort_with_active_state_still_clears_state_and_workspace(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Active spec-kitty merge state (no git-level merge anywhere) is still cleared."""
        _init_repo(tmp_path)
        mission_slug = "abort-scope-parity-01M2XQF8"
        mission_id = "01M2XQF8ULIDABORTSCOPE0000"
        save_state(
            MergeState(
                mission_id=mission_id,
                mission_slug=mission_slug,
                target_branch="main",
                wp_order=["WP01"],
            ),
            tmp_path,
        )

        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(merge_mod, "_resolve_mission_slug", lambda *_a, **_k: mission_slug)

        _dispatch_abort(tmp_path, mission_slug)

        output = capsys.readouterr().out
        assert load_state(tmp_path, mission_id) is None
        assert f"Aborted merge for {mission_slug}" in output
        # No workspace merge existed, so no git-level abort claim either.
        assert "Aborted in-progress git merge" not in output

    def test_abort_with_active_state_aborts_workspace_scoped_merge_not_repo_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A genuine spec-kitty-owned merge conflict inside the merge WORKSPACE
        is legitimately abortable -- but the operator's repo_root state must
        stay untouched even when it happens to also carry its own conflict.
        """
        branch = _init_repo(tmp_path)

        mission_slug = "abort-scope-workspace-01M2XQF8"
        mission_id = "01M2XQF8ULIDABORTWORKSPACE0"
        save_state(
            MergeState(
                mission_id=mission_id,
                mission_slug=mission_slug,
                target_branch=branch,
                wp_order=["WP01"],
            ),
            tmp_path,
        )

        # Set up the operator's OWN unrelated in-progress merge in repo_root --
        # this must survive regardless of the active spec-kitty state below.
        _create_conflicting_merge(tmp_path, branch)
        repo_root_merge_head = tmp_path / ".git" / "MERGE_HEAD"
        repo_root_merge_head_before = repo_root_merge_head.read_text(encoding="utf-8")

        # Reset repo_root to a clean branch tip so worktree creation for the
        # workspace below is possible from an unconflicted ref, while leaving
        # the MERGE_HEAD marker (git tracks it independently of the index).
        workspace_path = get_merge_workspace_path(mission_id, tmp_path)
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        worktree_result = _git("worktree", "add", "--detach", str(workspace_path), "incoming", cwd=tmp_path)
        assert worktree_result.returncode == 0, worktree_result.stderr

        # Create a genuine conflict INSIDE the merge workspace, mirroring
        # spec-kitty's own conflict-resolution flow.
        merge_result = _git("merge", branch, cwd=workspace_path)
        assert merge_result.returncode != 0, "expected a real workspace-side conflict"
        assert (workspace_path / ".git").exists()
        workspace_merge_head_exists_before = _git("rev-parse", "-q", "--verify", "MERGE_HEAD", cwd=workspace_path).returncode == 0
        assert workspace_merge_head_exists_before

        monkeypatch.setattr(merge_mod, "show_banner", lambda: None)
        monkeypatch.setattr(merge_mod, "find_repo_root", lambda: tmp_path)
        monkeypatch.setattr(merge_mod, "_resolve_mission_slug", lambda *_a, **_k: mission_slug)

        _dispatch_abort(tmp_path, mission_slug)

        output = capsys.readouterr().out

        # The operator's OWN repo_root merge must survive untouched.
        assert repo_root_merge_head.exists()
        assert repo_root_merge_head.read_text(encoding="utf-8") == repo_root_merge_head_before

        # spec-kitty's own state was cleared as usual.
        assert load_state(tmp_path, mission_id) is None
        assert f"Aborted merge for {mission_slug}" in output
