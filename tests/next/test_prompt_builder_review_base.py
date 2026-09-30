"""Unit tests for the review-base arms of ``prompt_builder`` (WP12, FR-010/FR-025).

Real git repositories and real ``status.events.jsonl`` files; the workspace and
WP metadata are lightweight stand-ins because only the fields the arm reads
(``lane_id``, ``context``, ``owned_files``) matter here.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from runtime.next.prompt_builder import _completion_lines, _review_command_lines, _review_pathspecs
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "review-base-01M3M2ZB"
_CLAIM_ID = "01CLAIMAAAAAAAAAAAAAAAAAA1"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@pytest.fixture
def mission_dir(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "seed")
    directory = repo / "kitty-specs" / _SLUG
    directory.mkdir(parents=True)
    return directory


def _claim(directory: Path) -> str:
    append_event(
        directory,
        StatusEvent(
            event_id=_CLAIM_ID,
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-09-29T00:00:00+00:00",
            actor="tester",
            force=True,
            execution_mode="direct_repo",
        ),
    )
    repo = directory.parents[1]
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "status: claimed")
    return _git(repo, "rev-parse", "HEAD")


def _workspace(*, lane_id: str | None, base_branch: str | None = None) -> Any:
    context = SimpleNamespace(base_branch=base_branch) if base_branch else None
    return SimpleNamespace(lane_id=lane_id, context=context)


def _meta(*owned_files: str) -> Any:
    return SimpleNamespace(owned_files=list(owned_files))


def _lines(directory: Path, workspace: Any, meta: Any) -> list[str]:
    return _review_command_lines(directory.parents[1], directory, _SLUG, "WP01", meta, workspace, None)


def test_lane_workspace_diffs_against_its_lane_base_with_no_pathspec(mission_dir: Path) -> None:
    lines = _lines(mission_dir, _workspace(lane_id="lane-a", base_branch="kitty/mission-base"), _meta("wp01.py"))

    assert "  git log kitty/mission-base..HEAD --oneline" in lines
    assert "  git diff kitty/mission-base..HEAD --stat" in lines


def test_lane_less_root_checkout_diffs_against_the_claim_commit_scoped_to_owned_files(mission_dir: Path) -> None:
    claim = _claim(mission_dir)

    lines = _lines(mission_dir, _workspace(lane_id=None), _meta("wp01.py", "docs/wp01.md"))

    assert f"  git log {claim}..HEAD --oneline -- wp01.py docs/wp01.md" in lines
    assert f"  git diff {claim}..HEAD --stat -- wp01.py docs/wp01.md" in lines


def test_lane_less_root_checkout_without_a_claim_says_unavailable_and_never_diffs(mission_dir: Path) -> None:
    lines = _lines(mission_dir, _workspace(lane_id=None), _meta("wp01.py"))

    assert "  unavailable: no deterministic implementation claim commit found for this WP" in lines
    assert not any(line.strip().startswith(("git log", "git diff")) for line in lines)


def test_lane_less_root_checkout_without_owned_files_keeps_the_legacy_unscoped_diff(mission_dir: Path) -> None:
    claim = _claim(mission_dir)

    lines = _lines(mission_dir, _workspace(lane_id=None), _meta())

    assert f"  git diff {claim}..HEAD --stat" in lines


def test_review_pathspecs_exclude_mission_bookkeeping_only_when_the_mission_dir_is_owned() -> None:
    mission_root = f"kitty-specs/{_SLUG}/"

    plain = _review_pathspecs(_SLUG, _meta("src/app.py"))
    planning = _review_pathspecs(_SLUG, _meta(f"{mission_root}research.md"))

    assert plain == ["src/app.py"]
    assert planning[0] == f"{mission_root}research.md"
    assert {f":(exclude){mission_root}tasks/**", f":(exclude){mission_root}tasks.md"} <= set(planning)
    assert f":(exclude){mission_root}status.events.jsonl" in planning
    assert f":(exclude){mission_root}status.json" in planning


def test_completion_lines_carry_no_owned_checkout_flag_without_a_fact() -> None:
    lines = _completion_lines("implement", "WP01", _SLUG, ["T001"])

    assert any(line.startswith("  spec-kitty agent tasks mark-status T001 --status done") for line in lines)
    assert not any("--owned-checkout" in line for line in lines)


def test_review_completion_lines_offer_approve_and_reject_without_a_fact() -> None:
    lines = _completion_lines("review", "WP01", _SLUG, [])

    assert any("APPROVE:" in line for line in lines)
    assert any("REJECT:" in line for line in lines)
    assert not any("--owned-checkout" in line for line in lines)
