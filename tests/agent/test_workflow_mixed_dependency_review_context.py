"""Regression test for the planning-artifact + code-change mixed dependency
crash in ``_resolve_review_context`` (PR 555).

Reproduces the original failure mode:

* The current WP resolves to a normal lane workspace with a real branch name.
* A *dependency* WP resolves to the repository-root planning workspace and
  therefore has ``branch_name=None``.
* Before the fix, the dependency's ``None`` branch name was appended into the
  candidate list and later passed to ``subprocess.run(["git", "merge-base", branch, None])``
  which raised ``TypeError: expected str, bytes or os.PathLike object, not NoneType``.

The fix in ``workflow.py`` skipped dependency workspaces with no branch name
instead of letting them flow into the merge-base loop. #7578 retired that
loop: the review base is the work package's review range
(``review.wp_range.resolve_wp_review_range``), so no dependency workspace is
consulted at all. These tests keep the mixed-dependency case end-to-end with a
real git worktree and now pin that no ``git merge-base`` runs and nothing
crashes (re-pin, IC-05, DIRECTIVE_041).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent.workflow import _resolve_review_context
from specify_cli.review.wp_range import RangeStatus, WpReviewRange
from specify_cli.workspace.context import ResolvedWorkspace

pytestmark = [pytest.mark.git_repo]


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "seed")
    return repo


def _make_lane_worktree(repo: Path, branch: str, worktree_rel: str) -> Path:
    worktree = repo / worktree_rel
    _git(repo, "worktree", "add", "-b", branch, str(worktree))
    (worktree / "feature.py").write_text("x = 1\n", encoding="utf-8")
    _git(worktree, "add", "feature.py")
    _git(worktree, "commit", "-m", "feat(WP02): add feature")
    return worktree


class TestMixedDependencyReviewContext:
    """``_resolve_review_context`` must not crash when a dependency WP
    resolves to a repo-root planning workspace with ``branch_name=None``.
    """

    def test_planning_artifact_dependency_does_not_crash_review_context(
        self, tmp_path: Path
    ) -> None:
        repo = _make_repo(tmp_path)
        lane_branch = "kitty/mission-078-feature-lane-a"
        worktree = _make_lane_worktree(repo, lane_branch, ".worktrees/078-feature-lane-a")

        current_workspace = ResolvedWorkspace(
            mission_slug="078-feature",
            wp_id="WP02",
            execution_mode="code_change",
            mode_source="frontmatter",
            resolution_kind="lane_workspace",
            workspace_name="078-feature-lane-a",
            worktree_path=worktree,
            branch_name=lane_branch,
            lane_id="lane-a",
            lane_wp_ids=["WP02"],
            context=None,
        )

        # The crash-inducing dependency: planning_artifact resolved to repo
        # root, with branch_name=None.
        planning_dependency = ResolvedWorkspace(
            mission_slug="078-feature",
            wp_id="WP01",
            execution_mode="planning_artifact",
            mode_source="frontmatter",
            resolution_kind="repo_root",
            workspace_name="078-feature-repo-root",
            worktree_path=repo,
            branch_name=None,
            lane_id=None,
            lane_wp_ids=[],
            context=None,
        )

        def fake_resolve(_repo_root: Path, _mission_slug: str, wp_id: str) -> ResolvedWorkspace:
            if wp_id == "WP02":
                return current_workspace
            if wp_id == "WP01":
                return planning_dependency
            raise ValueError(f"unexpected wp_id {wp_id}")


        with patch(
            "specify_cli.cli.commands.agent.workflow.resolve_workspace_for_wp",
            side_effect=fake_resolve,
        ):
            ctx = _resolve_review_context(
                workspace_path=worktree,
                repo_root=repo,
                mission_slug="078-feature",
                wp_id="WP02",
                owned_files=[],  # the WP declares dependencies but no owned_files
            )

        # The contract: no crash, branch is the lane branch, and the base is the
        # WP review range's (#7578 re-pin): this repository records no status
        # events for WP02, so the range is unavailable and the base stays
        # unknown -- never a common-ancestor branch guess.
        assert ctx["branch_name"] == lane_branch
        review_range = ctx["review_range"]
        assert isinstance(review_range, WpReviewRange) and review_range.status is RangeStatus.UNAVAILABLE
        assert ctx["base_branch"] == "unknown"
        assert ctx["commit_count"] == 0

    def test_planning_artifact_dependency_does_not_pollute_candidates(
        self, tmp_path: Path
    ) -> None:
        """The exact mechanism: dependency ``branch_name=None`` never reaches
        ``git merge-base`` -- since #7578 no candidate search runs at all.
        """
        repo = _make_repo(tmp_path)
        lane_branch = "kitty/mission-078-feature-lane-b"
        worktree = _make_lane_worktree(repo, lane_branch, ".worktrees/078-feature-lane-b")

        current_workspace = ResolvedWorkspace(
            mission_slug="078-feature",
            wp_id="WP03",
            execution_mode="code_change",
            mode_source="frontmatter",
            resolution_kind="lane_workspace",
            workspace_name="078-feature-lane-b",
            worktree_path=worktree,
            branch_name=lane_branch,
            lane_id="lane-b",
            lane_wp_ids=["WP03"],
            context=None,
        )
        planning_dependency = ResolvedWorkspace(
            mission_slug="078-feature",
            wp_id="WP01",
            execution_mode="planning_artifact",
            mode_source="frontmatter",
            resolution_kind="repo_root",
            workspace_name="078-feature-repo-root",
            worktree_path=repo,
            branch_name=None,
            lane_id=None,
            lane_wp_ids=[],
            context=None,
        )

        def fake_resolve(_repo_root: Path, _mission_slug: str, wp_id: str) -> ResolvedWorkspace:
            return current_workspace if wp_id == "WP03" else planning_dependency

        observed_calls: list[list[str]] = []
        original_run = subprocess.run

        def tracking_run(args, *a, **kw):  # type: ignore[override]
            if isinstance(args, list) and args[:2] == ["git", "merge-base"]:
                observed_calls.append(args)
                # Every argument passed to git merge-base must be a string,
                # not None — that's the contract this regression test guards.
                for arg in args:
                    assert arg is not None, f"git merge-base called with None: {args}"
                    assert isinstance(arg, str), f"git merge-base arg is not str: {arg!r} in {args}"
            return original_run(args, *a, **kw)


        with (
            patch(
                "specify_cli.cli.commands.agent.workflow.resolve_workspace_for_wp",
                side_effect=fake_resolve,
            ),
            patch("specify_cli.cli.commands.agent.workflow.subprocess.run", side_effect=tracking_run),
        ):
            ctx = _resolve_review_context(
                workspace_path=worktree,
                repo_root=repo,
                mission_slug="078-feature",
                wp_id="WP03",
                owned_files=[],  # the WP declares dependencies but no owned_files
            )

        assert observed_calls == [], "the review base comes from the WP review range, never a git merge-base search"
        assert ctx["branch_name"] == lane_branch
