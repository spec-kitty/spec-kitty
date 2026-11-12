"""The ``for_review`` baseline artifact on a settled default Mission (#7551, FR-005).

A default Mission settled ``lanes_with_coord`` at its first ``finalize-tasks`` keeps its PRIMARY
partition on the Mission topic branch, held by the coordination worktree, while the repository root
checkout returns to ``create_return_branch``. ``tasks/<WP>/baseline-tests.json`` is written into that
coordination copy, so the "does it need a commit" probe and the commit itself must run in the checkout
that holds it. Probed from the repository root checkout, ``git status`` saw a path under the ignored
``.worktrees/`` and reported nothing; the commit was silently skipped and the file stayed untracked.

The end-to-end case drives the real CLI in a subprocess from an unprotected root (``dev``) on a
Mission built by the real ``agent mission create`` core and ``finalize-tasks``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    REPO_ROOT,
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_ANALYSIS_REPORT = "# Analysis\n\nNo critical issues.\n"
_HATCH = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"
_BASELINE = "baseline-tests.json"
_WP01_DIR = "WP01-work"
_CLEAN_JUNIT = '<testsuite name="s" tests="1" failures="0"><testcase classname="c" name="t"/></testsuite>'


def _spec_kitty(root: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["SPEC_KITTY_NON_INTERACTIVE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=root,
        input=stdin,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _configure_review_test_command(root: Path) -> None:
    """A real ``review.test_command`` that writes a clean one-test JUnit report to ``{output_file}``."""
    config_path = root / ".kittify" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    config = config or {}
    config["review"] = {"test_command": f"printf '%s' '{_CLEAN_JUNIT}' > {{output_file}}"}
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    git(root, "add", str(config_path))
    git(root, "commit", "-qm", "review test command")


@pytest.fixture(autouse=True)
def _isolated_run(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    # Vacuity guard: with the operator hatch set, no protected-branch check would ever refuse.
    monkeypatch.delenv(_HATCH, raising=False)
    # The in-process ``finalize-tasks`` runs from the source tree and fans out no status event.
    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


@pytest.fixture
def settled_on_dev(tmp_path: Path) -> DefaultMission:
    """A finalized three-lane default Mission, settled ``lanes_with_coord``, the root checkout on ``dev``."""
    mission = make_default_mission(tmp_path, THREE_LANES, standing_on="dev")
    (mission.root_mission_dir / "plan.md").write_text("# Plan\n\nDo it.\n", encoding="utf-8")
    git(mission.root, "add", "kitty-specs")
    git(mission.root, "commit", "-qm", "plan")
    code, payload = run_finalize(mission)
    assert code == 0, payload
    recorded = _spec_kitty(
        mission.root, "agent", "mission", "record-analysis", "--mission", mission.slug, "--input-file", "-", "--agent", "claude", stdin=_ANALYSIS_REPORT
    )
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert git(mission.root, "branch", "--show-current") == "dev"
    assert mission.coord_mission_dir.is_dir()
    # Before settlement the root checkout holds the topic branch; configure once it is back on ``dev``.
    _configure_review_test_command(mission.root)
    return mission


def _lane_worktree(mission: DefaultMission) -> Path:
    lanes = sorted(p for p in (mission.root / ".worktrees").iterdir() if "-lane-" in p.name)
    assert lanes, list((mission.root / ".worktrees").iterdir())
    return lanes[0]


def test_for_review_commits_the_baseline_on_the_topic_branch_in_its_holder(settled_on_dev: DefaultMission) -> None:
    """FR-005: the baseline is committed on the topic branch; nothing is left untracked in the holder."""
    mission = settled_on_dev
    implement = _spec_kitty(mission.root, "agent", "action", "implement", "WP01", "--mission", mission.slug, "--agent", "claude")
    assert implement.returncode == 0, implement.stdout + implement.stderr

    lane = _lane_worktree(mission)
    (lane / "src").mkdir(exist_ok=True)
    (lane / "src" / "one.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(lane, "add", "src/one.py")
    git(lane, "commit", "-qm", "feat: one")

    moved = _spec_kitty(
        mission.root, "agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", mission.slug, "--agent", "claude", "--note", "Ready"
    )
    assert moved.returncode == 0, moved.stdout + moved.stderr

    artifact = mission.coord_mission_dir / "tasks" / _WP01_DIR / _BASELINE
    assert artifact.is_file(), "the baseline was never captured; the end-to-end case is vacuous"
    committed = subprocess.run(
        ["git", "show", f"{mission.topic}:kitty-specs/{mission.slug}/tasks/{_WP01_DIR}/{_BASELINE}"],
        cwd=mission.root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert committed.returncode == 0, committed.stderr
    holder = mission.coord_mission_dir.parents[1]
    assert git(holder, "status", "--porcelain", "--untracked-files=all", "--", f"kitty-specs/{mission.slug}/tasks/{_WP01_DIR}/{_BASELINE}") == ""
