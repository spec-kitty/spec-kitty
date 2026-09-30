"""Issue-pinned red-first regression for #3931 F-30 (P0 data-loss).

The move-task lane gate prints a ``git restore`` remedy when it finds
``kitty-specs/`` files committed on a lane branch. The pre-fix remedy was:

    git restore --source <planning-branch-TIP> --staged --worktree -- kitty-specs/

Following it (as mission ``verdict-matrix-rmw-preservation`` did, PR #4881)
restored the *whole* ``kitty-specs/`` tree from the planning tip, which
**deleted** lane-local files the planning branch did not carry
(``issue-matrix.json``, ``acceptance-matrix.json``) and pulled unrelated,
advanced planning content into the lane.

This test builds that exact scenario, takes the remedy the real gate prints,
runs it verbatim, and asserts the lane-local files survive and no foreign
planning content is dragged in. RED before the fix (directory scope from the
planning tip); GREEN after (named files from the merge-base).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent.tasks_parsing_validation import (
    _check_kitty_specs_contamination,
)

pytestmark = [pytest.mark.regression, pytest.mark.integration]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _build_lane_scenario(repo: Path) -> None:
    """A planning branch advanced past a lane; the lane owns matrix files the
    planning branch never had, plus one contaminating kitty-specs commit."""
    _git(repo, "init", "-q", "-b", "planning")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")

    # C0 — the shared base (the eventual merge-base).
    _write(repo, "kitty-specs/demo/plan.md", "# plan\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base plan")

    # Lane branches off C0.
    _git(repo, "branch", "lane")

    # Planning advances (C1): another mission's notes the lane must NOT receive.
    _write(repo, "kitty-specs/other-mission/notes.md", "# other mission\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "advance planning with unrelated mission")

    # Work on the lane: a contaminating design note plus lane-local matrix files
    # the planning branch never carried.
    _git(repo, "checkout", "-q", "lane")
    _write(repo, "kitty-specs/demo/tasks/WP02-note.md", "# design note\n")
    _write(repo, "kitty-specs/demo/issue-matrix.json", '{"WP02": "open"}\n')
    _write(repo, "kitty-specs/demo/acceptance-matrix.json", '{"WP02": "pending"}\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "lane work + local matrices")


def test_lane_restore_remedy_preserves_lane_local_files(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _build_lane_scenario(repo)

    # The gate only detects the design note as contamination; the lane-local
    # matrices are legitimate lane-owned files it does not name.
    contamination = ["kitty-specs/demo/tasks/WP02-note.md"]

    with patch(
        "specify_cli.mission_metadata.load_meta",
        return_value={"planning_base_branch": "planning"},
    ):
        guidance = _check_kitty_specs_contamination(
            worktree_path=repo,
            check_branch="planning",
            feature_dir=repo,
            wp_id="WP02",
            target_lane="for_review",
            list_wp_branch_specs_changes_for_guard=lambda **_k: list(contamination),
        )

    assert guidance is not None

    # Run the printed remedy verbatim, exactly as an operator would paste it.
    # (Pre-fix this was `git restore --source <planning-tip> ... -- kitty-specs/`;
    # post-fix it names only the offending file and sources from the merge-base.)
    restore_line = next(line.strip() for line in guidance if line.strip().startswith("git restore"))
    subprocess.run(restore_line, cwd=repo, shell=True, check=True, capture_output=True, text=True)

    # The core guarantee (RED pre-fix, GREEN post-fix): lane-local files the
    # operator wrote MUST survive following the printed remedy.
    assert (repo / "kitty-specs/demo/issue-matrix.json").read_text(encoding="utf-8") == '{"WP02": "open"}\n', (
        "following the printed remedy deleted a lane-local file (#3931 F-30 data-loss)"
    )
    assert (repo / "kitty-specs/demo/acceptance-matrix.json").read_text(encoding="utf-8") == '{"WP02": "pending"}\n'
    # The unrelated mission's planning content is NOT dragged into the lane.
    assert not (repo / "kitty-specs/other-mission/notes.md").exists()
    # The contaminating note is cleaned (it did not exist at the merge-base).
    assert not (repo / "kitty-specs/demo/tasks/WP02-note.md").exists()

    # And the remedy is file-scoped from a resolved merge-base, never the whole
    # directory and never the planning tip.
    assert restore_line.rstrip().endswith("kitty-specs/demo/tasks/WP02-note.md")
    assert not restore_line.rstrip().endswith("kitty-specs/")
    assert "$(" not in restore_line  # a concrete merge-base SHA was resolved
