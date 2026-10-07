"""#5811 red-first repro: a no-op ``upgrade --yes`` must not rewrite Mission history.

Drives the real ``upgrade`` CLI entry point (in-process, so the autouse
drain-posture patch applies) over a scratch git repository that is already up
to date. The only work left is the finalizer's TeamSpace mission-state repair
offer, which ``--yes`` opts into. Today that repair rewrites every valid
Mission's ``status.events.jsonl`` and writes an audit manifest even though the
Mission had nothing wrong with it; the blocker sat in one unrelated Mission.

Histories are produced by the live writer (``build_status_event`` +
``append_event``), never hand-written JSON.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path

import pytest
import typer
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.upgrade import upgrade
from specify_cli.status.emit import build_status_event
from specify_cli.status.store import append_event

pytestmark = [
    pytest.mark.integration,
    pytest.mark.git_repo,
    pytest.mark.regression,
    pytest.mark.p0_repro(issue=5811),
]

_VERSION = "1.0.0a1"
_METADATA_YAML = (
    "spec_kitty:\n"
    f"  version: '{_VERSION}'\n"
    "  initialized_at: '2026-01-01T00:00:00'\n"
    "environment:\n"
    "  python_version: '3.12'\n"
    "  platform: linux\n"
    "  platform_version: ''\n"
    "migrations:\n"
    "  applied: []\n"
)
_AUDIT_DIR = Path(".kittify") / "mission-state-audit"
_BLOCKER_SLUG = "blocked-no-identity-01BLOCKED"
_VALID_SLUGS = ("valid-alpha-01VALIDAA", "valid-beta-01VALIDBB", "valid-ordered-01VALIDCC")
_LANE_CHAIN = (("planned", "claimed"), ("claimed", "in_progress"), ("in_progress", "for_review"))

_app = typer.Typer(add_completion=False)
_app.command()(upgrade)
_runner = CliRunner()


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return done.stdout


def _write_mission(repo: Path, slug: str, *, mission_id: str | None, timestamps: tuple[str, str, str]) -> None:
    mission_dir = repo / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    meta: dict[str, str] = {"mission_slug": slug, "friendly_name": slug}
    if mission_id is not None:
        meta["mission_id"] = mission_id
    (mission_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    (mission_dir / "spec.md").write_text(f"# {slug}\n", encoding="utf-8")
    if mission_id is None:
        return
    for (from_lane, to_lane), at in zip(_LANE_CHAIN, timestamps, strict=True):
        event = build_status_event(
            mission_slug=slug,
            wp_id="WP01",
            from_lane=from_lane,
            to_lane=to_lane,
            actor="claude",
            at=at,
            mission_id=mission_id,
            reason="driven by the live writer",
        )
        append_event(mission_dir, event)


def _build_project(root: Path) -> None:
    root.mkdir(parents=True)
    kittify = root / ".kittify"
    kittify.mkdir()
    (kittify / "metadata.yaml").write_text(_METADATA_YAML, encoding="utf-8")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    ascending = ("2026-01-01T00:00:01+00:00", "2026-01-01T00:00:02+00:00", "2026-01-01T00:00:03+00:00")
    # Appended out of ``(at, event_id)`` order: a re-sorting rewrite changes the bytes.
    out_of_order = ("2026-01-01T00:00:03+00:00", "2026-01-01T00:00:01+00:00", "2026-01-01T00:00:02+00:00")
    _write_mission(root, _VALID_SLUGS[0], mission_id="01HZZZZZZZZZZZZZZZZZZZZAAA", timestamps=ascending)
    _write_mission(root, _VALID_SLUGS[1], mission_id="01HZZZZZZZZZZZZZZZZZZZZBBB", timestamps=ascending)
    _write_mission(root, _VALID_SLUGS[2], mission_id="01HZZZZZZZZZZZZZZZZZZZZCCC", timestamps=out_of_order)
    _write_mission(root, _BLOCKER_SLUG, mission_id=None, timestamps=ascending)
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


def _snapshot(root: Path) -> dict[str, bytes]:
    base = root / "kitty-specs"
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def _run_upgrade(root: Path) -> Result:
    with contextlib.chdir(root):
        return _runner.invoke(_app, ["--target", _VERSION, "--yes", "--no-worktrees"], catch_exceptions=False)


def _audit_files(root: Path) -> set[str]:
    audit = root / _AUDIT_DIR
    return {str(p.relative_to(root)) for p in audit.rglob("*") if p.is_file()} if audit.exists() else set()


def _assert_gate_ran(output: str) -> None:
    assert "blocker" in output.lower(), f"the mission-state gate did not run (no blocker count printed):\n{output}"


def test_noop_upgrade_yes_leaves_mission_history_byte_identical(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _build_project(project)
    before = _snapshot(project)

    result = _run_upgrade(project)

    assert result.exit_code == 0, result.output
    _assert_gate_ran(result.output)
    after = _snapshot(project)
    changed = sorted(path for path in before if after.get(path) != before[path])
    created = sorted(set(after) - set(before))
    assert not changed, f"upgrade rewrote pre-existing Mission files (e.g. reason_source/review_result keys, re-sort): {changed}"
    assert not created, f"upgrade created new files under kitty-specs/: {created}"
    assert _git(project, "status", "--porcelain", "--", "kitty-specs") == ""


def test_noop_upgrade_yes_writes_no_audit_manifest(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _build_project(project)
    before = _audit_files(project)

    result = _run_upgrade(project)

    assert result.exit_code == 0, result.output
    _assert_gate_ran(result.output)
    new = sorted(_audit_files(project) - before)
    assert not new, f"upgrade wrote an audit manifest under .kittify/mission-state-audit/: {new}"


def test_noop_upgrade_yes_with_auto_commit_commits_no_mission_history(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    _build_project(project)
    # auto_commit defaults to enabled (``get_auto_commit_default``): no config needed.
    head_before = _git(project, "rev-parse", "HEAD").strip()

    result = _run_upgrade(project)

    assert result.exit_code == 0, result.output
    _assert_gate_ran(result.output)
    committed = _git(project, "diff", "--name-only", head_before, "HEAD").splitlines()
    mission_paths = [path for path in committed if path.startswith("kitty-specs/")]
    assert not mission_paths, f"auto_commit committed Mission history: {mission_paths}"
    # The churn commit runs before the repair offer on base, so the repair's rewrite is left dirty
    # instead of committed. Either outcome is a defect: a clean run touches neither.
    dirty = _git(project, "status", "--porcelain", "--", "kitty-specs").splitlines()
    assert not dirty, f"auto_commit run left Mission history modified in the working tree: {dirty}"
