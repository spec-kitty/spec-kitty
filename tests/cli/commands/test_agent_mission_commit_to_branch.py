"""Regression tests for mission artifact commit handling."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
from rich.console import Console

import specify_cli.cli.commands.agent.mission as mission_module
import specify_cli.cli.commands.agent.mission_setup_plan as setup_plan_module
import specify_cli.coordination.commit_router as commit_router_module
from specify_cli.cli.commands.agent.mission import _commit_to_branch

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _run_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")
    (repo / "plan.md").write_text("# Plan\n")
    _run_git(repo, "add", "plan.md")
    _run_git(repo, "commit", "-m", "Initial plan")
    _run_git(repo, "checkout", "-b", "mission/work")


def test_commit_to_branch_treats_empty_safe_commit_as_benign(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    head_before = _run_git(tmp_path, "rev-parse", "HEAD")

    _commit_to_branch(
        plan_file,
        "001-demo",
        "plan",
        tmp_path,
        "mission/work",
        json_output=True,
    )

    assert _run_git(tmp_path, "rev-parse", "HEAD") == head_before


def test_commit_to_branch_empty_resolved_paths_clean_artifact_noops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    head_before = _run_git(tmp_path, "rev-parse", "HEAD")

    def no_commit_paths(*_args: object, **_kwargs: object) -> tuple[Path, tuple[Path, ...]]:
        return tmp_path, ()

    monkeypatch.setattr(mission_module, "_planning_commit_worktree", no_commit_paths)

    _commit_to_branch(
        plan_file,
        "001-demo",
        "plan",
        tmp_path,
        "mission/work",
        json_output=True,
    )

    assert _run_git(tmp_path, "rev-parse", "HEAD") == head_before


def test_commit_to_branch_legacy_called_process_empty_commit_does_not_print_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    output = io.StringIO()

    def fake_safe_commit(**_kwargs: object) -> None:
        raise subprocess.CalledProcessError(
            1,
            ["git", "commit"],
            stderr="nothing to commit, working tree clean",
        )

    # WP06 (#2056): the ``mission.safe_commit`` re-export shim is gone. The
    # commit path now runs ``_commit_to_branch`` → ``commit_for_mission`` →
    # ``commit_router.safe_commit``. The empty-commit ``CalledProcessError`` is
    # caught inside ``commit_for_mission`` (mapped to ``status="unchanged"``), so
    # the canonical interception point is the router's ``safe_commit`` symbol.
    monkeypatch.setattr(commit_router_module, "safe_commit", fake_safe_commit)
    # WP06 (#2056): ``_commit_to_branch`` (and its ``_print_artifact_unchanged``
    # console write) relocated to ``mission_setup_plan``; patch that module's
    # ``console`` to capture the "unchanged" notice.
    monkeypatch.setattr(
        setup_plan_module,
        "console",
        Console(file=output, force_terminal=False, color_system=None, width=120),
    )

    _commit_to_branch(
        plan_file,
        "001-demo",
        "plan",
        tmp_path,
        "mission/work",
        json_output=False,
    )

    rendered = output.getvalue()
    assert "Plan unchanged, no commit needed" in rendered
    assert "Plan committed" not in rendered


def test_commit_to_branch_still_commits_changed_artifact(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n\nUpdated.\n")

    _commit_to_branch(
        plan_file,
        "001-demo",
        "plan",
        tmp_path,
        "mission/work",
        json_output=True,
    )

    assert _run_git(tmp_path, "log", "-1", "--pretty=%s") == "Add plan for mission 001-demo"


def test_commit_to_branch_hook_rejection_surfaces_as_error_not_unchanged(tmp_path: Path) -> None:
    """A rejecting pre-commit hook is a REAL commit failure, not an empty changeset.

    Fix 793872a19 / PR #3269: the router classifies ONLY the distinct
    `safe_commit: nothing to commit` shape as `unchanged` (staged tree matches
    HEAD). A hook `exit 1` leaves a real staged change, so it surfaces as an
    error and `_commit_to_branch` re-raises RuntimeError rather than silently
    reporting `unchanged`. The artifact stays dirty and uncommitted.

    Previously (WP02/#2056) this test asserted the opposite — that the generic
    `safe_commit: git commit failed` shape was classified `unchanged`. That was
    the masking bug 793872a19 deliberately corrected; the correct-contract
    regression lives in tests/git_ops/test_safe_commit_commit_failure_classification.py.
    """
    _init_repo(tmp_path)
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n\nUpdated.\n")

    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)

    with pytest.raises(RuntimeError, match="git commit failed"):
        _commit_to_branch(
            plan_file,
            "001-demo",
            "plan",
            tmp_path,
            "mission/work",
            json_output=True,
        )

    # The commit genuinely did not land — plan.md stays an uncommitted change.
    assert _run_git(tmp_path, "status", "--porcelain", "--", "plan.md") == "M plan.md"
