"""#5812 red-first repro: a gitignored residue directory is not a Mission.

``kitty-specs/ghost-01ABCDEF/`` holds only a gitignored ``*.lock`` file. It has
no Mission file, so the mission-state audit must not report it as a Mission
with ``IDENTITY_MISSING``, and ``doctor mission-state --fix`` must not
materialise Mission files inside it.

Runs the real ``doctor`` CLI in-process over a scratch git repository; the
real Mission's history is produced by the live writer.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app
from specify_cli.status.emit import build_status_event
from specify_cli.status.store import append_event

pytestmark = [
    pytest.mark.integration,
    pytest.mark.git_repo,
]

_GHOST = "ghost-01ABCDEF"
_MISSION_FILES = ("meta.json", "status.json", "lanes.json", "status.events.jsonl")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _build_project(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / ".kittify").mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    slug = "real-mission-01REALMIS"
    mission_dir = root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps({"mission_slug": slug, "mission_id": "01HZZZZZZZZZZZZZZZZZZZZREA", "friendly_name": slug}) + "\n",
        encoding="utf-8",
    )
    (mission_dir / "spec.md").write_text("# real\n", encoding="utf-8")
    for from_lane, to_lane in (("planned", "claimed"), ("claimed", "in_progress")):
        append_event(
            mission_dir,
            build_status_event(
                mission_slug=slug,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                actor="claude",
                mission_id="01HZZZZZZZZZZZZZZZZZZZZREA",
            ),
        )
    (root / ".gitignore").write_text("*.lock\n", encoding="utf-8")
    ghost = root / "kitty-specs" / _GHOST
    (ghost / "decisions").mkdir(parents=True)
    (ghost / "decisions" / "index.json.lock").write_text("", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    _git(root, "check-ignore", "-q", f"kitty-specs/{_GHOST}/decisions/index.json.lock")
    return ghost


def test_residue_directory_is_not_reported_as_identity_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_project(tmp_path / "proj")
    monkeypatch.chdir(tmp_path / "proj")

    result = CliRunner().invoke(app, ["mission-state", "--audit", "--json"])

    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    ghost_codes = [finding["code"] for mission in report["missions"] if _GHOST in mission["mission_slug"] for finding in mission["findings"]]
    assert ghost_codes == ["RESIDUE_DIRECTORY"], f"residue directory {_GHOST} audited as a Mission: {ghost_codes}"


def test_fix_does_not_materialise_mission_files_in_residue_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ghost = _build_project(tmp_path / "proj")
    monkeypatch.chdir(tmp_path / "proj")

    result = CliRunner().invoke(app, ["mission-state", "--fix", "--allow-dirty"])

    assert result.exit_code in (0, 1), result.output
    created = [name for name in _MISSION_FILES if (ghost / name).exists()]
    assert not created, f"--fix created Mission files in residue directory {_GHOST}: {created}"
