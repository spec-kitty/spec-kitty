"""Contract: ``append-history`` emits a ``note`` annotation, not a WP-file write.

write-surface-coherence WP03 (FR-003 / T013): a WP prompt file is a
``WORK_PACKAGE_TASK`` — a PRIMARY artifact kind, so its *existence* is still
checked on the mission's primary ``target_branch`` for every topology.

WP08 / FR-007 / T031 (runtime-state-eviction): ``append-history`` no longer
mutates the WP prompt file's ``## Activity Log`` section at all. It emits an
``InnerStateChanged`` ``note``-append delta via WP01's
``emit_inner_state_changed``, landing on the coord-aware STATUS-partition
mission directory (the coordination worktree for a coord-topology mission,
exactly as every other STATUS read/write in ``orchestrator_api`` resolves it)
-- never the primary ``target_branch`` WP file, and never a
``Path.cwd()``-derived join (C-003 / #2647). This re-pins the prior
WP-file-commit regression test onto the new event-sourced contract: the WP
file is byte-unchanged, and the coordination branch/worktree carries the
annotation.

Uses git (unlike ``test_orchestrator_commands_integration.py``, which is git-free).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.orchestrator_api.commands import app
from specify_cli.status.store import read_event_stream

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()

MISSION_SLUG = "hist-coord"
MID8 = "01KHIST0"
MISSION_ID = "01KHIST0000000000000000000"
MISSION_DIRNAME = f"{MISSION_SLUG}-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_DIRNAME}"
# The mission's primary feature target_branch. Planning/WP-prompt commits land
# here (FR-003), so it is a NON-protected feature branch the operator is on.
TARGET_BRANCH = "feat/hist-target"

_WP_FILE = (
    "---\n"
    "work_package_id: WP01\n"
    "title: Test WP01\n"
    "dependencies: []\n"
    "---\n\n"
    "# WP01\n\n"
    "## Activity Log\n"
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


@pytest.fixture
def coord_repo(tmp_path: Path) -> Path:
    """A git repo with a coordination-topology mission and a live coord worktree."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")

    feature_dir = repo / "kitty-specs" / MISSION_DIRNAME
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": MISSION_SLUG,
                "mission_id": MISSION_ID,
                "mid8": MID8,
                "coordination_branch": COORD_BRANCH,
                "target_branch": TARGET_BRANCH,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01.md").write_text(_WP_FILE, encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "seed mission")
    _git(repo, "branch", COORD_BRANCH)

    # The WP prompt file is a primary kind → lands on the primary feature
    # target_branch (FR-003 / T013). The operator is ON that feature branch (D-3),
    # so check it out as HEAD; the commit lands there directly with no coord
    # transit. The coordination worktree still exists (status routes there).
    _git(repo, "checkout", "-q", "-b", TARGET_BRANCH)
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    _git(repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
    return repo


def _invoke_append_history(repo: Path) -> object:
    with patch(
        "specify_cli.orchestrator_api._common._get_main_repo_root",
        return_value=repo,
    ):
        return runner.invoke(
            app,
            [
                "append-history",
                "--mission",
                MISSION_DIRNAME,
                "--wp",
                "WP01",
                "--actor",
                "claude",
                "--note",
                "Starting implementation",
            ],
        )


def test_append_history_emits_note_annotation_wp_file_unchanged(coord_repo: Path) -> None:
    result = _invoke_append_history(coord_repo)

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["success"] is True
    assert data["data"]["wp_id"] == "WP01"

    # WP08 / FR-007: the WP prompt file is byte-unchanged -- no more direct
    # ``## Activity Log`` mutation, on either branch.
    committed = _git(
        coord_repo,
        "show",
        f"{TARGET_BRANCH}:kitty-specs/{MISSION_DIRNAME}/tasks/WP01.md",
    )
    assert committed.stdout == _WP_FILE
    assert "Starting implementation" not in committed.stdout

    coord_show = subprocess.run(
        ["git", "show", f"{COORD_BRANCH}:kitty-specs/{MISSION_DIRNAME}/tasks/WP01.md"],
        cwd=coord_repo,
        capture_output=True,
        text=True,
    )
    assert "Starting implementation" not in coord_show.stdout, (
        "WP-prompt edit leaked onto the coordination branch -- append-history "
        "must no longer write the WP file at all (WP08 / FR-007)."
    )

    # The annotation itself lands in the coordination worktree's STATUS
    # partition (the same coord-aware surface every other STATUS read/write
    # in this module resolves through) -- never a Path.cwd()-derived join.
    coord_worktree = CoordinationWorkspace.worktree_path(coord_repo, MISSION_SLUG, MID8)
    feature_dir = coord_worktree / "kitty-specs" / MISSION_DIRNAME
    stream = read_event_stream(feature_dir)
    assert not stream.transitions
    assert len(stream.annotations) == 1
    annotation = stream.annotations[0]
    assert annotation.wp_id == "WP01"
    assert annotation.actor == "claude"
    assert annotation.delta.note is not None
    assert "Starting implementation" in annotation.delta.note
