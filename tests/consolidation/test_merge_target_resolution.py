"""Regression: `spec-kitty merge` resolves its target from the PRIMARY meta.json.

The CLI merge command and ``orchestrator-api merge-mission`` now share one
resolver (``core.paths.resolve_merge_target_branch``). Under coordination
topology the coord-aware read surface (the coord worktree mission dir) has no
meta.json, so the old resolver fell back to the repo default (main) and
``spec-kitty merge`` integrated the mission into the wrong branch. The resolver
must read the primary meta and honor ``target_branch`` /
``merge_target_branch``.

Uses git (a real coordination worktree is needed to reproduce the bug).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.consolidate import _resolve_target_branch
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.core.paths import resolve_merge_target_branch

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "merge-cli-target"
MID8 = "01KMCT00"  # 8 chars, valid Crockford base32 (no I/L/O/U)
MISSION_ID = "01KMCT00000000000000000000"  # 26-char ULID
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"
TARGET = "feat/peer-bot-observation"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


@pytest.fixture
def coord_repo(tmp_path: Path) -> Path:
    """Coord-topology mission: primary meta sets target_branch; coord worktree has no meta."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "coordination_branch": COORD_BRANCH,
                "target_branch": TARGET,
                "merge_target_branch": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")

    # Coord branch carries the mission dir but NO meta.json (the real shape); then
    # materialize the coord worktree so the topology-aware candidate prefers it.
    _git(repo, "checkout", "-q", "-b", COORD_BRANCH)
    (feature_dir / "meta.json").unlink()
    (feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "coord surface without meta")
    _git(repo, "checkout", "-q", "main")
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    _git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    return repo


def test_cli_merge_resolves_primary_target_under_coord_topology(coord_repo: Path) -> None:
    """No --target -> the mission's target_branch (from primary meta), not main."""
    branch, source = _resolve_target_branch(coord_repo, MISSION_DIRNAME, None)
    assert branch == TARGET
    assert source == "meta.json"


def test_cli_merge_explicit_target_wins(coord_repo: Path) -> None:
    branch, source = _resolve_target_branch(coord_repo, MISSION_DIRNAME, "release/x")
    assert (branch, source) == ("release/x", "flag")


def test_resolve_merge_target_branch_explicit_target_wins(coord_repo: Path) -> None:
    branch, source = resolve_merge_target_branch(coord_repo, MISSION_DIRNAME, "release/x")
    assert (branch, source) == ("release/x", "flag")


def test_resolve_merge_target_branch_prefers_merge_target_branch(coord_repo: Path) -> None:
    primary_meta = coord_repo / "kitty-specs" / MISSION_DIRNAME / "meta.json"
    data = json.loads(primary_meta.read_text(encoding="utf-8"))
    data["merge_target_branch"] = "feat/explicit-merge-target"
    primary_meta.write_text(json.dumps(data) + "\n", encoding="utf-8")

    branch, source = resolve_merge_target_branch(coord_repo, MISSION_DIRNAME, None)
    assert branch == "feat/explicit-merge-target"
    assert source == "meta.json"


def test_resolve_merge_target_branch_falls_back_when_no_mission(coord_repo: Path) -> None:
    branch, source = resolve_merge_target_branch(coord_repo, None, None)
    assert branch == "main"
    assert source == "primary_branch"
