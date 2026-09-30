"""Must-not-flip characterization tests (mission
``worktree-root-resolution-01M0B59R`` WP01, FR-008 / SC-003, C-004).

These pin the deliberate PRIMARY_READ anchors GREEN so no later WP (WP02–WP07)
can regress them. They characterize the *current* behavior of the primary-read
resolvers — they are GREEN on base and MUST stay green:

* ``get_feature_target_branch`` / ``resolve_merge_target_branch``
  (``core/paths.py``) — invoked from a linked worktree, still resolve the
  mission's ``target_branch`` from the PRIMARY-checkout ``meta.json`` (#2320),
  never re-anchored to the invoking worktree.
* ``mission_runtime.resolution.read_dir_for`` — the PRIMARY-metadata read dir
  composes against the primary root (#3328 / C-002), unchanged by ``cwd``.

Read-only characterization: this file MUST NOT modify the anchors.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.core.paths import (
    get_feature_target_branch,
    resolve_merge_target_branch,
)

pytestmark = [pytest.mark.git_repo]

_MISSION_SLUG = "anchor-fixture-01AAAAAA"


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


@pytest.fixture
def primary_with_mission(tmp_path: Path) -> Path:
    """Primary checkout carrying a mission whose meta.json pins a target branch."""
    repo = tmp_path / "primary"
    repo.mkdir()
    _run_git(["init"], cwd=repo)
    _run_git(["config", "user.email", "test@example.com"], cwd=repo)
    _run_git(["config", "user.name", "Test User"], cwd=repo)
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _MISSION_SLUG,
                "target_branch": "release/anchor",
                "merge_target_branch": "release/anchor",
            }
        ),
        encoding="utf-8",
    )
    (repo / "README.md").write_text("# Primary\n", encoding="utf-8")
    _run_git(["add", "-A"], cwd=repo)
    _run_git(["commit", "-m", "seed mission"], cwd=repo)
    _run_git(["branch", "-M", "main"], cwd=repo)
    return repo


@pytest.fixture
def lane_worktree(primary_with_mission: Path, tmp_path: Path) -> Path:
    wt = tmp_path / "lane-a"
    _run_git(["worktree", "add", "-b", "lane-a", str(wt)], cwd=primary_with_mission)
    return wt


def test_get_feature_target_branch_anchors_on_primary_from_worktree(primary_with_mission: Path, lane_worktree: Path) -> None:
    """Invoked with the worktree as ``repo_root``, still reads the PRIMARY meta."""
    branch = get_feature_target_branch(lane_worktree, _MISSION_SLUG)
    assert branch == "release/anchor"


def test_get_feature_target_branch_anchors_on_primary_from_primary(
    primary_with_mission: Path,
) -> None:
    branch = get_feature_target_branch(primary_with_mission, _MISSION_SLUG)
    assert branch == "release/anchor"


def test_resolve_merge_target_branch_anchors_on_primary_from_worktree(primary_with_mission: Path, lane_worktree: Path) -> None:
    branch, source = resolve_merge_target_branch(lane_worktree, _MISSION_SLUG, None)
    assert branch == "release/anchor"
    assert source == "meta.json"


def test_resolve_merge_target_branch_explicit_flag_wins(
    primary_with_mission: Path,
) -> None:
    branch, source = resolve_merge_target_branch(primary_with_mission, _MISSION_SLUG, "override/branch")
    assert branch == "override/branch"
    assert source == "flag"


def test_read_dir_for_primary_metadata_anchors_on_primary_root(
    primary_with_mission: Path,
) -> None:
    """``read_dir_for`` composes the PRIMARY-metadata dir against ``primary_root``.

    The default (no ``owned`` fact) arm composes against the passed
    ``primary_root`` regardless of any worktree ``cwd`` — the #3328 / C-002
    anchor. We assert the composed dir lives under the primary tree.
    """
    from mission_runtime.artifacts import MissionArtifactKind
    from mission_runtime.resolution import read_dir_for

    read_dir = read_dir_for(
        primary_with_mission,
        _MISSION_SLUG,
        kind=MissionArtifactKind.PRIMARY_METADATA,
    )

    assert read_dir.is_relative_to(primary_with_mission.resolve())
    assert _MISSION_SLUG in read_dir.parts
