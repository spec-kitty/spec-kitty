"""#6669 red-first repro: ``spec-kitty upgrade`` must not fabricate a Mission identity into
a residue folder that holds stray Mission-shaped files.

A branch switch (or a deleted lane worktree) can strand an untracked
``kitty-specs/<slug>/tasks/WP01-*.md`` or ``status.events.jsonl`` in a folder whose
tracked Mission files left with the branch. :func:`is_mission_dir` rejects it (no
``mission_id``, no tracked ``spec.md``/``meta.json``), but #6662's write-seam rule
counts ``tasks/`` and the event log as Mission content. So on ``main`` the
``2.0.6_consistency_sweep`` still writes a baseline ``meta.json`` there, and
``3.2.0a4_normalize_mission_lifecycle`` mints a ``mission_id`` that contradicts the
slug's mid8 and synthesizes ``status.json``. The upgrade auto-commit then commits them.

Runs the real ``upgrade`` CLI in-process over a scratch git repository.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app
from specify_cli.status.emit import build_status_event
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REAL = "real-mission-01REALMIS"
_REAL_ID = "01REALMISZZZZZZZZZZZZZZZZZ"
_RESIDUE = "my-mission-01M5JYRC"
_WP_WITH_LANE = "---\nwork_package_id: WP01\ntitle: leftover\nlane: doing\n---\n# WP01\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout


def _leftover_wp(residue: Path) -> None:
    (residue / "tasks").mkdir(parents=True)
    (residue / "tasks" / "WP01-leftover.md").write_text(_WP_WITH_LANE, encoding="utf-8")


def _leftover_event_log(residue: Path) -> None:
    residue.mkdir(parents=True)
    seed_status_event(
        residue,
        build_status_event(
            mission_slug=_RESIDUE,
            wp_id="WP01",
            from_lane="planned",
            to_lane="claimed",
            actor="claude",
            mission_id="01M5JYRCKRPS719E4EYGJH5WEP",
        ),
    )


def _build_project(root: Path, strand: Callable[[Path], None]) -> Path:
    """A committed real Mission plus an untracked, Mission-shaped leftover of another slug."""
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
    residue = root / "kitty-specs" / _RESIDUE
    strand(residue)
    return residue


def _snapshot(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


@pytest.mark.p0_repro(issue=6669)
@pytest.mark.parametrize("strand", [_leftover_wp, _leftover_event_log], ids=["tasks-leftover", "event-log-leftover"])
def test_upgrade_leaves_mission_shaped_residue_untouched(tmp_path: Path, strand: Callable[[Path], None]) -> None:
    project = tmp_path / "proj"
    residue = _build_project(project, strand)
    before = _snapshot(residue)

    with contextlib.chdir(project):
        result = CliRunner().invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    after = _snapshot(residue)
    added = sorted(after.keys() - before.keys())
    rewritten = sorted(name for name in before if name in after and after[name] != before[name])
    assert after == before, f"upgrade changed residue folder {_RESIDUE}: added {added}, rewrote {rewritten}"
    tracked = _git(project, "ls-files", f"kitty-specs/{_RESIDUE}").split()
    assert not tracked, f"upgrade committed residue files: {tracked}"
    real_meta = json.loads((project / "kitty-specs" / _REAL / "meta.json").read_text(encoding="utf-8"))
    assert real_meta["mission_id"] == _REAL_ID
