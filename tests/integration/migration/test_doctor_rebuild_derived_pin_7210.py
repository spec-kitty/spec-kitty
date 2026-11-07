"""#7210: ``doctor mission-state --fix`` rebuilds ``lanes.json`` with a derived planning commit.

When the rebuild runs (the #4758 wedge: execution has begun and ``lanes.json`` is absent), no
planning commit was ever recorded. Before #7210 the rebuild recorded the live target tip, which
leaves the #6715 evidence window ``planning_commit..<tip>`` empty for every work package already
committed. It now records the same base ``finalize-tasks`` derives: the target-branch commit
before the Mission's ``tasks/WP*.md`` first appeared on its first-parent line
(``lanes/planning_base.py``). When none can be derived it keeps the live tip and says so.

Runs the real ``doctor`` CLI in-process over a scratch git repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.migration.mission_state import LANES_REBUILT_ACTION, LANES_REBUILT_WITH_TARGET_TIP_ACTION
from tests.unit.migration.test_mission_state_lanes_rebuild import _seed_wedged_events, _write_meta, _write_owned_wp_files

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "071-doctor-derived-pin"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


def _init_repo(root: Path) -> str:
    root.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    (root / ".kittify").mkdir()
    (root / ".kittify" / ".keep").write_text("", encoding="utf-8")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    return _git(root, "rev-parse", "HEAD")


def _wedged_mission(root: Path, *, commit_tasks: bool) -> tuple[Path, str]:
    """A wedged ``lanes`` Mission; returns its directory and the commit before its WP task files."""
    base = _init_repo(root)
    feature_dir = root / "kitty-specs" / _SLUG
    _write_meta(feature_dir, _SLUG)
    _write_owned_wp_files(root, feature_dir / "tasks", ("WP01", "WP02"))
    if commit_tasks:
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "plan: add WP task files")
        (root / "src" / "wp01" / "mod.py").write_text("x = 2\n", encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "WP01 implementation on the target")
    _seed_wedged_events(feature_dir, _SLUG)
    assert read_lanes_json(feature_dir) is None, "fixture precondition: no lanes.json before repair"
    return feature_dir, base


def _run_fix(root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ["mission-state", "--fix", "--allow-dirty", "--mission", _SLUG])
    assert result.exit_code == 0, result.output
    return result.output


def test_fix_rebuilds_lanes_with_the_derived_planning_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    feature_dir, base = _wedged_mission(root, commit_tasks=True)
    tip = _git(root, "rev-parse", "main")

    output = _run_fix(root, monkeypatch)

    lanes = read_lanes_json(feature_dir)
    assert lanes is not None, output
    assert lanes.planning_commit_sha == base, (
        f"the rebuild must record the commit before the WP task files ({base}), not the live tip ({tip}); got {lanes.planning_commit_sha}"
    )
    assert LANES_REBUILT_WITH_TARGET_TIP_ACTION not in output


def test_fix_keeps_the_live_tip_and_warns_when_no_base_can_be_derived(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    feature_dir, _base = _wedged_mission(root, commit_tasks=False)
    tip = _git(root, "rev-parse", "main")

    output = _run_fix(root, monkeypatch)

    lanes = read_lanes_json(feature_dir)
    assert lanes is not None, output
    assert lanes.planning_commit_sha == tip, "with no derivable base the rebuild keeps today's behaviour: the live target tip"
    assert LANES_REBUILT_ACTION in output
    assert LANES_REBUILT_WITH_TARGET_TIP_ACTION in output
    assert "records the live target-branch tip" in " ".join(output.split())
