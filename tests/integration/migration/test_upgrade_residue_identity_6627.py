"""#6627 red-first repro: ``spec-kitty upgrade`` must not mint a Mission identity into residue.

A Mission that ran ``agent decision open`` / ``resolve`` on a topic branch leaves
``kitty-specs/<slug>/decisions/index.json`` (and its ``.lock``) untracked. After a
switch to another branch only those leftovers remain: the directory is residue,
not a Mission (:func:`specify_cli.context.mission_resolver.is_mission_dir`, #5812).

On ``main`` the ``2.0.6_consistency_sweep`` and ``3.2.0a4_normalize_mission_lifecycle``
migrations enumerate every ``kitty-specs/`` directory. They write a baseline
``meta.json`` with a freshly minted ``mission_id`` (a second identity for a real
Mission's slug) plus a ``status.json`` into the residue directory, and the upgrade
auto-commit commits both.

Runs the real ``upgrade`` CLI in-process over a scratch git repository.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REAL = "real-mission-01REALMIS"
_REAL_ID = "01REALMISZZZZZZZZZZZZZZZZZ"
_RESIDUE = "rrule-repeat-editor-ui-01M5JYRC"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _build_project(root: Path) -> Path:
    """A committed real Mission plus an untracked ``decisions/`` leftover of another slug."""
    root.mkdir(parents=True)
    (root / ".kittify").mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    mission_dir = root / "kitty-specs" / _REAL
    mission_dir.mkdir(parents=True)
    meta = {
        "mission_id": _REAL_ID,
        "mission_slug": _REAL,
        "slug": _REAL,
        "friendly_name": "real mission",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    (mission_dir / "spec.md").write_text("# real\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    decisions = root / "kitty-specs" / _RESIDUE / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "index.json").write_text("{}\n", encoding="utf-8")
    (decisions / "index.json.lock").write_text("", encoding="utf-8")
    return root / "kitty-specs" / _RESIDUE


def _upgrade(project: Path) -> tuple[int, str]:
    with contextlib.chdir(project):
        result = CliRunner().invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)
    return result.exit_code, result.output


@pytest.mark.p0_repro(issue=6627)
def test_upgrade_does_not_mint_identity_into_residue_directory(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    residue = _build_project(project)

    exit_code, output = _upgrade(project)

    assert exit_code == 0, output
    leftovers = sorted(p.relative_to(residue).as_posix() for p in residue.rglob("*") if p.is_file())
    assert leftovers == ["decisions/index.json", "decisions/index.json.lock"], f"upgrade wrote into residue directory {_RESIDUE}: {leftovers}"
    tracked = _git(project, "ls-files", f"kitty-specs/{_RESIDUE}").split()
    assert not tracked, f"upgrade committed residue files: {tracked}"
    real_meta = json.loads((project / "kitty-specs" / _REAL / "meta.json").read_text(encoding="utf-8"))
    assert real_meta["mission_id"] == _REAL_ID
