"""#7600 fold: a dirty-checkout refusal from the mission_number bake names the consolidate next step.

After #7600 ``RefAdvanceDirtyWorktreeError`` ends at the blocker and each caller appends its
own next step. The bake's mission-branch advance is a consolidate step, so a fresh run blocked
there must say to resume the consolidation once the named checkout is clean, like a lane or
Mission merge failure does (``lanes.consolidation.lane_merge_error_text``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation.mission_number.bake import _write_mission_number_to_branch
from specify_cli.git.ref_advance import RefAdvanceDirtyWorktreeError

pytestmark = pytest.mark.fast

_SLUG = "bake-dirty-checkout"
_MISSION_BRANCH = "kitty/mission-bake-dirty-checkout-01ABCDEF"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _repo_with_mission_branch_checked_out_dirty(repo: Path) -> None:
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "tester")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    feature_dir = repo / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": _SLUG, "mission_number": None}) + "\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    _git(repo, "checkout", "-q", "-b", _MISSION_BRANCH)
    (repo / "app.py").write_text("x = 2  # operator edit\n", encoding="utf-8")


def test_bake_dirty_checkout_refusal_names_the_consolidate_next_step(tmp_path: Path) -> None:
    _repo_with_mission_branch_checked_out_dirty(tmp_path)

    with pytest.raises(RefAdvanceDirtyWorktreeError) as raised:
        _write_mission_number_to_branch(tmp_path, _MISSION_BRANCH, _SLUG, 7, target_branch="main")

    text = str(raised.value)
    assert "Commit, stash, or revert these changes" in text
    assert "spec-kitty consolidate --resume" in text
