"""Regression: merge-mission resolves the target from the PRIMARY meta.json.

The mission's ``target_branch`` lives in the primary-checkout meta.json. Under
coordination topology the coord-aware read surface (the coord worktree mission
dir) has no meta.json, so the old resolver fell back to the repo default (main)
and merged into the wrong branch. The resolver must read the primary meta and
honor ``target_branch`` (and ``merge_target_branch`` if present).

Also covers the fail-closed contract (FR-005 / #2139): a corrupt meta.json
must surface a MissionMetaReadError rather than silently falling back to the
repo default.

Uses git (a real coordination worktree is needed to reproduce the bug).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.orchestrator_api.consolidation import _resolve_merge_target_branch

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

MISSION_SLUG = "merge-target"
MID8 = "01KMERGE"  # 8 chars (mid8 == mission_id[:8])
MISSION_ID = "01KMERGE000000000000000000"  # 26-char ULID
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

    # Build the coord branch so its mission dir exists but carries NO meta.json
    # (the real coord-worktree shape), then materialize the coord worktree so the
    # topology-aware candidate prefers it.
    _git(repo, "checkout", "-q", "-b", COORD_BRANCH)
    (feature_dir / "meta.json").unlink()
    (feature_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "coord surface without meta")
    _git(repo, "checkout", "-q", "main")
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    _git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    return repo


def test_merge_target_uses_primary_target_branch_under_coord_topology(
    coord_repo: Path,
) -> None:
    """No --target, merge_target_branch null -> primary target_branch, not main."""
    resolved = _resolve_merge_target_branch(coord_repo, MISSION_DIRNAME, None)
    assert resolved == TARGET


def test_merge_target_explicit_override_wins(coord_repo: Path) -> None:
    resolved = _resolve_merge_target_branch(coord_repo, MISSION_DIRNAME, "release/x")
    assert resolved == "release/x"


def test_merge_target_prefers_merge_target_branch_when_set(coord_repo: Path) -> None:
    """A non-null merge_target_branch takes precedence over target_branch."""
    primary_meta = coord_repo / "kitty-specs" / MISSION_DIRNAME / "meta.json"
    data = json.loads(primary_meta.read_text(encoding="utf-8"))
    data["merge_target_branch"] = "feat/explicit-merge-target"
    primary_meta.write_text(json.dumps(data) + "\n", encoding="utf-8")

    resolved = _resolve_merge_target_branch(coord_repo, MISSION_DIRNAME, None)
    assert resolved == "feat/explicit-merge-target"


def test_merge_target_corrupt_meta_raises_structured_error(coord_repo: Path) -> None:
    """Corrupt primary meta.json raises MissionMetaReadError (fail-closed, FR-005 / #2139).

    Pre-fix the corrupt meta silently fell back to the repo default; post-fix
    the structured error surfaces so the operator knows there is a corrupt file.
    """
    primary_meta = coord_repo / "kitty-specs" / MISSION_DIRNAME / "meta.json"
    primary_meta.write_text("{not valid json at all", encoding="utf-8")

    with pytest.raises(MissionMetaReadError) as exc_info:
        _resolve_merge_target_branch(coord_repo, MISSION_DIRNAME, None)

    assert "meta.json" in str(exc_info.value)
