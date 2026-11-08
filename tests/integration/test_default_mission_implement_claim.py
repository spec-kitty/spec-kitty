"""#7372: ``implement`` claims a WP of a default ``lanes_with_coord`` Mission with auto-commit on.

A Mission created without ``--topology`` and settled to ``lanes_with_coord`` at its first
``finalize-tasks`` keeps its PRIMARY partition on its topic branch until it lands (FR-061). The
repository root checkout goes back to ``create_return_branch``, so the coordination worktree is
the checkout that holds the topic branch and the Mission directory.

Before the fix the claim refused at "Validate planning state" with ``SAFE_COMMIT_PATH_POLICY``
(the planning-commit probe relativized the coordination-worktree directory against the repository
root), then at workspace allocation with ``SafeCommitHeadMismatch`` (the claim commit expected the
repository root checkout on the topic branch), and ``move-task --to for_review`` refused the lane
as contaminated (the lane-hygiene guard measured it against ``target_branch``, which carries no
PRIMARY content yet). Each test drives the real ``spec-kitty`` CLI (a subprocess on this
checkout's ``src``), with no shim, no ``auto_commit: false``, no hand commit and no ``--force``.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.integration.test_default_mission_consolidate_lands_primary import _ANALYSIS
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]

_SRC = str(Path(__file__).resolve().parents[2] / "src")
_TARGET = "work"
_CLI_TIMEOUT_SECONDS = 300


def _cli(mission: DefaultMission, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in (_SRC, os.environ.get("PYTHONPATH")) if p), NO_COLOR="1")
    return subprocess.run(
        [sys.executable, "-m", "specify_cli", *args],
        cwd=mission.root,
        env=env,
        capture_output=True,
        text=True,
        timeout=_CLI_TIMEOUT_SECONDS,
        check=False,
    )


def _ok(proc: subprocess.CompletedProcess[str]) -> subprocess.CompletedProcess[str]:
    assert proc.returncode == 0, f"exit {proc.returncode}\nSTDOUT:\n{proc.stdout[-3000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
    return proc


def _coord_worktree(mission: DefaultMission) -> Path:
    return mission.coord_mission_dir.parents[1]


def _tracked_dirt(checkout: Path) -> str:
    """``git status --porcelain`` without untracked files (a fixture repo does not ignore ``.kittify/workspaces/``)."""
    return git(checkout, "status", "--porcelain", "--untracked-files=no")


@pytest.fixture(scope="module")
def settled(tmp_path_factory: pytest.TempPathFactory) -> Iterator[DefaultMission]:
    """A default Mission settled to ``lanes_with_coord``, with its plan and analysis recorded."""
    from unittest.mock import patch

    import specify_cli.status.emit as emit_module

    tmp_path = tmp_path_factory.mktemp("default-claim")
    with contextlib.chdir(Path(__file__).resolve().parents[2]), patch.object(emit_module, "_status_fan_out", lambda *a, **k: None):
        mission = make_default_mission(tmp_path, THREE_LANES, standing_on=_TARGET)
        code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict) and decision["settled_topology"] == "lanes_with_coord"
    coord = _coord_worktree(mission)
    (mission.coord_mission_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    git(coord, "add", "-A")
    git(coord, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", "plan")
    analysis = tmp_path / "analysis.md"
    analysis.write_text(_ANALYSIS, encoding="utf-8")
    _ok(_cli(mission, "agent", "mission", "record-analysis", "--mission", mission.slug, "--input-file", str(analysis)))
    yield mission


def test_implement_claims_every_wp_with_auto_commit(settled: DefaultMission) -> None:
    """Each claim exits 0, commits on the topic branch, and leaves both checkouts clean."""
    coord = _coord_worktree(settled)
    root_head_before = git(settled.root, "rev-parse", "HEAD")
    for index in (1, 2, 3):
        topic_before = git(coord, "rev-parse", "HEAD")
        proc = _ok(_cli(settled, "agent", "action", "implement", f"WP0{index}", "--agent", "impl", "--mission", settled.slug))
        assert "SAFE_COMMIT_PATH_POLICY" not in proc.stdout and "refusing to stage path under .worktrees/" not in proc.stdout
        assert git(coord, "rev-parse", "HEAD") != topic_before, f"WP0{index}: the claim committed nothing on the topic branch"
        assert _tracked_dirt(coord) == "", f"WP0{index}: the claim left the coordination worktree dirty"
        assert _tracked_dirt(settled.root) == "", f"WP0{index}: the claim left the repository root checkout dirty"
        assert (settled.root / ".worktrees" / f"{settled.slug}-lane-{'abc'[index - 1]}").is_dir()
    assert git(coord, "branch", "--show-current") == settled.topic
    assert git(settled.root, "branch", "--show-current") == settled.return_branch
    assert git(settled.root, "rev-parse", "HEAD") == root_head_before, "the claims must not commit on the return branch"
    # Nothing under .worktrees/ was ever staged into the repository root checkout's history.
    assert ".worktrees/" not in git(settled.root, "log", "--all", "--name-only", "--format=")


def test_for_review_accepts_a_lane_cut_from_the_topic_branch(settled: DefaultMission) -> None:
    """``move-task --to for_review`` judges the lane against the topic branch, so no ``--force`` is needed."""
    if not (settled.root / ".worktrees" / f"{settled.slug}-lane-a").is_dir():
        _ok(_cli(settled, "agent", "action", "implement", "WP01", "--agent", "impl", "--mission", settled.slug))
    lane = settled.root / ".worktrees" / f"{settled.slug}-lane-a"
    owned = lane / THREE_LANES[0]
    owned.parent.mkdir(parents=True, exist_ok=True)
    owned.write_text("X = 1\n", encoding="utf-8")
    git(lane, "add", THREE_LANES[0])
    git(lane, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", "feat(WP01)")
    proc = _ok(_cli(settled, "agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", settled.slug, "--agent", "impl", "--note", "ready"))
    assert "Committed kitty-specs files on this lane branch" not in proc.stdout
    assert _tracked_dirt(_coord_worktree(settled)) == ""


def test_for_review_refuses_a_lane_that_edits_primary_planning_content(settled: DefaultMission) -> None:
    """Negative end-to-end: a lane commit to the Mission's ``spec.md`` is still refused without ``--force``.

    The guard measures the lane against the topic branch (the seam's PRIMARY ref) rather than
    ``target_branch``; that must not turn it permissive: genuine planning-file edits on a lane
    branch stay contamination.
    """
    lane = settled.root / ".worktrees" / f"{settled.slug}-lane-b"
    if not lane.is_dir():
        _ok(_cli(settled, "agent", "action", "implement", "WP02", "--agent", "impl", "--mission", settled.slug))
    owned = lane / THREE_LANES[1]
    owned.parent.mkdir(parents=True, exist_ok=True)
    owned.write_text("Y = 2\n", encoding="utf-8")
    spec = lane / "kitty-specs" / settled.slug / "spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("# Spec\n\nEdited on a lane branch.\n", encoding="utf-8")
    git(lane, "add", "--sparse", "-f", THREE_LANES[1], str(spec.relative_to(lane)))
    git(lane, "-c", "user.name=e", "-c", "user.email=e@x", "commit", "-qm", "feat(WP02): touch the spec")
    proc = _cli(settled, "agent", "tasks", "move-task", "WP02", "--to", "for_review", "--mission", settled.slug, "--agent", "impl", "--note", "ready")
    assert proc.returncode != 0, f"a lane editing spec.md must be refused\nSTDOUT:\n{proc.stdout[-3000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
    assert "Committed kitty-specs files on this lane branch" in proc.stdout + proc.stderr
