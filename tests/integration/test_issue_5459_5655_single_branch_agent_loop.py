"""#5459 / #5655: the agent claim + status loop on a single_branch mission.

#5459: ``agent action implement`` must run the same write-checkout guard as
``implement`` (claim base, WRONG_BRANCH / OCCUPIED / DIRTY refusals).
#5655: ``mark-status`` and ``move-task`` must commit the status files they
write, leaving the write checkout clean.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli import app as root_app
from specify_cli.lanes.claim_base import read_claim_base
from tests.integration.test_single_branch_write_checkout_e2e import (
    _assert_setup_ok,
    _build_mission,
    _finalize,
    _git,
    _move_to_for_review,
    _read_events,
    _seed_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _action_implement(wp_id: str, mission_slug: str) -> Result:
    return runner.invoke(root_app, ["agent", "action", "implement", wp_id, "--agent", "claude", "--mission", mission_slug])


def _mark_done(task_id: str, mission_slug: str) -> Result:
    return runner.invoke(root_app, ["agent", "tasks", "mark-status", task_id, "--status", "done", "--mission", mission_slug])


def _lane_of(feature_dir: Path, wp_id: str) -> str | None:
    lanes = [e["to_lane"] for e in _read_events(feature_dir) if e.get("wp_id") == wp_id and e.get("to_lane")]
    return lanes[-1] if lanes else None


def _porcelain(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str, Path]:
    repo = _seed_repo(tmp_path, name="repo")
    mission_slug, feature_dir = _build_mission(repo, "issue-5459-sb", topology=MissionTopology.SINGLE_BRANCH, wp02_independent=True)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    (repo / ".gitignore").write_text(".kittify/derived/\n.kittify/runtime/\n.kittify/charter/context-state.json\n", encoding="utf-8")
    _assert_setup_ok("finalize-tasks", _finalize(mission_slug))
    _git(repo, "add", "-A")
    if _porcelain(repo):
        _git(repo, "commit", "-m", "finalize")
    analysis = tmp_path / "analysis.md"
    analysis.write_text("# Analysis\n\nNo blocking findings.\n", encoding="utf-8")
    _assert_setup_ok(
        "record-analysis",
        runner.invoke(root_app, ["agent", "mission", "record-analysis", "--mission", mission_slug, "--input-file", str(analysis)]),
    )
    return repo, mission_slug, feature_dir


def test_action_implement_records_claim_base_and_reaches_review(mission: tuple[Path, str, Path]) -> None:
    """#5459 symptom 1 + #5655: claim base recorded; for_review passes without --force; tree stays clean."""
    repo, slug, feature_dir = mission
    _assert_setup_ok("action implement WP01", _action_implement("WP01", slug))
    assert read_claim_base(repo, slug, "WP01") is not None, "agent action implement recorded no claim base"

    (repo / "src" / "wp01.py").write_text("VALUE = 10\n", encoding="utf-8")
    _git(repo, "commit", "-am", "WP01 work")

    _assert_setup_ok("mark-status T001", _mark_done("T001", slug))
    assert _porcelain(repo) == "", f"mark-status left the write checkout dirty:\n{_porcelain(repo)}"

    result = _move_to_for_review("WP01", slug)
    assert result.exit_code == 0, result.output
    assert _lane_of(feature_dir, "WP01") == "for_review"
    assert _porcelain(repo) == "", f"move-task left the write checkout dirty:\n{_porcelain(repo)}"


def test_action_implement_refuses_occupied_checkout(mission: tuple[Path, str, Path]) -> None:
    """#5459 symptom 2: a second WP is refused while WP01 is in_progress."""
    repo, slug, feature_dir = mission
    _assert_setup_ok("action implement WP01", _action_implement("WP01", slug))
    result = _action_implement("WP02", slug)
    assert result.exit_code != 0
    assert "already in_progress" in result.output
    assert _lane_of(feature_dir, "WP02") in (None, "planned")


def test_action_implement_refuses_dirty_checkout(mission: tuple[Path, str, Path]) -> None:
    """#5459: an operator's uncommitted edit refuses a fresh claim."""
    repo, slug, feature_dir = mission
    (repo / "README.md").write_text("operator edit\n", encoding="utf-8")
    result = _action_implement("WP01", slug)
    assert result.exit_code != 0
    assert "uncommitted changes" in result.output
    assert _lane_of(feature_dir, "WP01") in (None, "planned")
    assert read_claim_base(repo, slug, "WP01") is None


def test_action_implement_resume_in_dirty_checkout_is_allowed(mission: tuple[Path, str, Path]) -> None:
    """Positive control: resuming the in-flight WP with its own uncommitted work is not refused."""
    repo, slug, _ = mission
    _assert_setup_ok("action implement WP01", _action_implement("WP01", slug))
    base = read_claim_base(repo, slug, "WP01")
    (repo / "src" / "wp01.py").write_text("VALUE = 11\n", encoding="utf-8")
    _assert_setup_ok("resume WP01", _action_implement("WP01", slug))
    assert read_claim_base(repo, slug, "WP01") == base
