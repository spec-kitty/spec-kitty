"""#6669 regression guard: ``spec-kitty upgrade`` must leave Mission-shaped residue untouched.

Originally the red-first ``p0_repro`` reproduction for #6669 (nightly lane only; it was red
on ``origin/main`` in PR #6672's CI). The marker was removed when the fix landed
(ADR 2026-07-17-1), so this now runs per PR.

A branch switch (or a deleted lane worktree) can strand untracked Mission-shaped files in a
``kitty-specs/<slug>/`` folder whose tracked Mission files left with the branch:
a ``tasks/WP01-*.md``, a ``status.events.jsonl``, a ``status.json`` (with or without an event
log), a legacy ``tasks/doing/`` lane file, or a ``decisions/`` index. :func:`is_mission_dir`
rejects such a folder (no ``mission_id``, no tracked ``spec.md``/``meta.json``), but #6662's
write-seam rule counted ``tasks/``, the event log and the snapshot as Mission content. So on
``main`` the ``2.0.6_consistency_sweep`` wrote a baseline ``meta.json`` there,
``3.2.0a4_normalize_mission_lifecycle`` minted a ``mission_id`` that contradicted the slug's
mid8 and synthesized ``status.json``, the lane migrations moved or rewrote the leftover work
package, and the upgrade auto-commit committed the result.

One ``upgrade --yes`` run over a scratch git repository holds every shape at once, plus two
controls that must still be repaired: a real Mission with an identity, and a committed legacy
Mission (tracked ``spec.md``, no ``meta.json``, tracked ``tasks/doing/WP01-x.md``) that proves
the git-aware residue rule did not turn pre-identity Missions into residue. The same run proves
each residue folder is named once in the upgrade output. Runs the real ``upgrade`` CLI in-process.
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
from specify_cli.context.mission_resolver import residue_notice
from specify_cli.status.emit import build_status_event
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REAL = "real-mission-01REALMIS"
_REAL_ID = "01REALMISZZZZZZZZZZZZZZZZZ"
_LEGACY = "legacy-mission-01LEGACYM"
_LEGACY_WP = "WP01-x.md"
_WP_WITH_LANE = "---\nwork_package_id: WP01\ntitle: leftover\nlane: doing\n---\n# WP01\n"
_SNAPSHOT = '{"work_packages": {}}\n'


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
            mission_slug=residue.name,
            wp_id="WP01",
            from_lane="planned",
            to_lane="claimed",
            actor="claude",
            mission_id="01M5JYRCKRPS719E4EYGJH5WEP",
        ),
    )


def _leftover_status_snapshot(residue: Path) -> None:
    residue.mkdir(parents=True)
    (residue / "status.json").write_text(_SNAPSHOT, encoding="utf-8")


def _leftover_status_snapshot_with_log(residue: Path) -> None:
    _leftover_event_log(residue)
    (residue / "status.json").write_text(_SNAPSHOT, encoding="utf-8")


def _leftover_lane_file(residue: Path) -> None:
    (residue / "tasks" / "doing").mkdir(parents=True)
    (residue / "tasks" / "doing" / "WP01-x.md").write_text(_WP_WITH_LANE, encoding="utf-8")


def _leftover_decisions(residue: Path) -> None:
    (residue / "decisions").mkdir(parents=True)
    (residue / "decisions" / "index.json").write_text("{}\n", encoding="utf-8")


#: slug -> how the leftover is stranded (the five shapes of User Story 1; the snapshot shape twice).
_SHAPES: dict[str, Callable[[Path], None]] = {
    "res-tasks-wp-01M5JYR1": _leftover_wp,
    "res-event-log-01M5JYR2": _leftover_event_log,
    "res-status-json-01M5JYR3": _leftover_status_snapshot,
    "res-status-json-and-log-01M5JYR4": _leftover_status_snapshot_with_log,
    "res-lane-file-01M5JYR5": _leftover_lane_file,
    "res-decisions-01M5JYR6": _leftover_decisions,
}


def _commit_real_mission(root: Path) -> None:
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


def _commit_legacy_mission(root: Path) -> None:
    """A pre-identity Mission: tracked ``spec.md``, no ``meta.json``, a tracked legacy lane file."""
    mission_dir = root / "kitty-specs" / _LEGACY
    (mission_dir / "tasks" / "doing").mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# legacy\n", encoding="utf-8")
    (mission_dir / "tasks" / "doing" / _LEGACY_WP).write_text(_WP_WITH_LANE, encoding="utf-8")


def _build_project(root: Path) -> dict[str, Path]:
    """Two committed Missions plus one untracked leftover per shape; returns the residue folders by slug."""
    root.mkdir(parents=True)
    (root / ".kittify").mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _commit_real_mission(root)
    _commit_legacy_mission(root)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    folders = {slug: root / "kitty-specs" / slug for slug in _SHAPES}
    for slug, strand in _SHAPES.items():
        strand(folders[slug])
    return folders


def _snapshot(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


def _upgrade(project: Path) -> tuple[int, str]:
    with contextlib.chdir(project):
        result = CliRunner().invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)
    return result.exit_code, result.output


def test_upgrade_leaves_every_mission_shaped_residue_untouched_and_still_repairs_missions(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    folders = _build_project(project)
    before = {slug: _snapshot(folder) for slug, folder in folders.items()}

    exit_code, output = _upgrade(project)

    assert exit_code == 0, output
    flat_output = " ".join(output.split())  # the console wraps long lines
    for slug, folder in folders.items():
        after = _snapshot(folder)
        added = sorted(after.keys() - before[slug].keys())
        moved_or_rewritten = sorted(name for name in before[slug] if after.get(name) != before[slug][name])
        assert after == before[slug], f"upgrade changed residue folder {slug}: added {added}, moved or rewrote {moved_or_rewritten}"
        tracked = _git(project, "ls-files", f"kitty-specs/{slug}").split()
        assert not tracked, f"upgrade committed residue files: {tracked}"
        notice = residue_notice(f"kitty-specs/{slug}")
        assert flat_output.count(notice) == 1, f"residue folder {slug} must be named exactly once in the upgrade output"

    real_meta = json.loads((project / "kitty-specs" / _REAL / "meta.json").read_text(encoding="utf-8"))
    assert real_meta["mission_id"] == _REAL_ID


def test_upgrade_still_migrates_a_committed_legacy_mission_beside_residue(tmp_path: Path) -> None:
    """Control: tracked ``spec.md`` makes the folder a Mission, so identity is minted and the lane file moves."""
    project = tmp_path / "proj"
    _build_project(project)
    legacy = project / "kitty-specs" / _LEGACY

    exit_code, output = _upgrade(project)

    assert exit_code == 0, output
    meta = json.loads((legacy / "meta.json").read_text(encoding="utf-8"))
    assert isinstance(meta.get("mission_id"), str) and meta["mission_id"], "a committed legacy Mission must get an identity"
    assert (legacy / "tasks" / _LEGACY_WP).is_file(), "the legacy lane file must be flattened out of tasks/doing/"
    assert not (legacy / "tasks" / "doing").exists()
    assert residue_notice(f"kitty-specs/{_LEGACY}") not in " ".join(output.split())
