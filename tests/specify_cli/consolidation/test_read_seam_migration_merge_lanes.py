"""Acceptance coverage for the merge/lanes read-side seam migration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.lanes.recovery import scan_recovery_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "merge-lanes-seam"
_MISSION_ID = "01KTDVHZKGCHCW6HQ4V577PNES"
_COORD_BRANCH = "kitty/mission-merge-lanes-seam-01KTDVHZ-coord"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _seed_repo(tmp_path: Path, *, deleted_coord: bool) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")

    mission_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    mission_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": _MISSION_ID,
        "topology": "lanes_with_coord" if deleted_coord else "lanes",
        "mission_branch": "kitty/mission-merge-lanes-seam-01KTDVHZ",
    }
    if deleted_coord:
        meta["coordination_branch"] = _COORD_BRANCH
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    _git(repo_root, "add", ".")
    _git(repo_root, "commit", "-q", "-m", "seed mission")
    return repo_root


def test_recovery_scan_preserves_healthy_primary_read(tmp_path: Path) -> None:
    """A healthy lanes mission still resolves its recovery inputs from PRIMARY."""
    repo_root = _seed_repo(tmp_path, deleted_coord=False)

    assert scan_recovery_state(repo_root, _MISSION_SLUG) == []


def test_recovery_scan_fails_loud_when_coordination_branch_was_deleted(
    tmp_path: Path,
) -> None:
    """A deleted declared coordination branch must not silently read PRIMARY."""
    repo_root = _seed_repo(tmp_path, deleted_coord=True)

    with pytest.raises(CoordinationBranchDeleted) as exc_info:
        scan_recovery_state(repo_root, _MISSION_SLUG)

    assert exc_info.value.error_code == "COORDINATION_BRANCH_DELETED"
    assert _COORD_BRANCH in str(exc_info.value)
