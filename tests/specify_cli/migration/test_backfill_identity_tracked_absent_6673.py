"""#6673: ``backfill_mission`` refuses to mint over a tracked-but-absent ``meta.json``.

The guard is defence in depth: no ``upgrade`` seam reaches ``backfill_mission`` with a missing
file (the ``3.2.0a4`` normalization returns before the call), but ``migrate backfill-identity``
does, and it must not fork a Mission's identity by minting a fresh ULID over one git already
holds. The no-op control on the same fixture is a normal on-disk ``meta.json`` that still gets
its identity minted.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.migration.backfill_identity import backfill_mission

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "tracked-meta-01REALMIS"
_MISSION_ID = "01REALMISZZZZZZZZZZZZZZZZZ"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return root


def _mission(root: Path) -> Path:
    mission_dir = root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _SLUG,
                "slug": _SLUG,
                "friendly_name": "tracked meta",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "mission")
    return mission_dir


def test_a_tracked_absent_meta_is_refused_not_minted(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = _mission(root)
    (mission_dir / "meta.json").unlink()

    result = backfill_mission(mission_dir)

    assert result.action == "skip"
    assert result.mission_id is None
    assert result.reason is not None
    assert f"git checkout -- kitty-specs/{_SLUG}/meta.json" in result.reason
    assert not (mission_dir / "meta.json").exists(), "backfill_mission wrote a meta.json over a tracked identity"


def test_an_on_disk_meta_without_identity_still_gets_one(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    mission_dir = _mission(root)
    without_id = {
        "mission_slug": _SLUG,
        "slug": _SLUG,
        "friendly_name": "tracked meta",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (mission_dir / "meta.json").write_text(json.dumps(without_id, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    result = backfill_mission(mission_dir)

    assert result.action == "wrote"
    assert result.mission_id is not None
    written = json.loads((mission_dir / "meta.json").read_text(encoding="utf-8"))
    assert written["mission_id"] == result.mission_id


def test_nothing_tracked_keeps_the_original_skip_reason(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    legacy = root / "kitty-specs" / "legacy-mission"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("# legacy\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "legacy")

    result = backfill_mission(legacy)

    assert result.action == "skip"
    assert result.reason == "meta.json not found"
    assert not (legacy / "meta.json").exists()
