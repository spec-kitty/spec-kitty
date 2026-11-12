"""Unit tests for the review-range block of ``prompt_builder`` (site 1; #7578 WP05, FR-008/FR-013).

Real git repositories and real ``status.events.jsonl`` files; the workspace and
WP metadata are lightweight stand-ins because only the fields the block reads
(``lane_id``, ``branch_name``, ``owned_files``, ``requirement_refs``) matter here.
The events are seeded without stamps, so the ``single_branch`` range is derived
from the claim and submission event commits.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from runtime.next.prompt_builder import _completion_lines, _review_command_lines
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "review-base-01M3M2ZB"
_CLAIM_ID = "01CLAIMAAAAAAAAAAAAAAAAAA1"
_PROGRESS_ID = "01PROGAAAAAAAAAAAAAAAAAAA1"
_SUBMIT_ID = "01REVWAAAAAAAAAAAAAAAAAAA1"
_UNAVAILABLE_COMMAND = "  (no deterministic range; inspect `spec-kitty agent tasks status` and the WP's commits)"


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
    meta = {"mission_slug": _SLUG, "mission_id": "01M3M2ZB000000000000000001", "topology": "single_branch", "target_branch": "main", "mission_type": "software-dev"}
    (directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    write_single_lane_manifest(directory, wp_ids=("WP01",))
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "mission")
    return directory


def _event(directory: Path, event_id: str, from_lane: Lane, to_lane: Lane) -> str:
    seed_status_event(
        directory,
        StatusEvent(
            event_id=event_id,
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-09-29T00:00:00+00:00",
            actor="tester",
            force=True,
            execution_mode="direct_repo",
        ),
    )
    repo = directory.parents[1]
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", f"status: {to_lane}")
    return _git(repo, "rev-parse", "HEAD")


def _claim(directory: Path) -> str:
    return _event(directory, _CLAIM_ID, Lane.PLANNED, Lane.CLAIMED)


def _work_and_submit(directory: Path, *paths: str) -> str:
    """Start, commit *paths* (one commit each) and submit WP01; returns the submission event commit."""
    repo = directory.parents[1]
    _event(directory, _PROGRESS_ID, Lane.CLAIMED, Lane.IN_PROGRESS)
    for path in paths:
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(f"{path}\n", encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", f"work: {path}")
    return _event(directory, _SUBMIT_ID, Lane.IN_PROGRESS, Lane.FOR_REVIEW)


def _workspace(*, lane_id: str | None) -> Any:
    return SimpleNamespace(lane_id=lane_id, context=None, branch_name="main")


def _meta(*owned_files: str) -> Any:
    return SimpleNamespace(owned_files=list(owned_files), requirement_refs=[])


def _lines(directory: Path, workspace: Any, meta: Any) -> list[str]:
    return _review_command_lines(directory.parents[1], _SLUG, "WP01", meta, workspace, None)


def _commands(lines: list[str]) -> list[str]:
    return [line for line in lines if line.startswith(("  git log", "  git diff"))]


@pytest.mark.parametrize("lane_id", ["lane-a", "lane-planning"])
def test_lane_workspace_renders_the_wp_review_range_not_a_lane_base(mission_dir: Path, lane_id: str) -> None:
    """re-pin (IC-05): a lane id (the production ``single_branch`` arm is ``lane-planning``) no longer picks a lane base.

    The range comes from the WP's own claim and submission, scoped to its owned files, on every workspace kind.
    """
    claim = _claim(mission_dir)
    tip = _work_and_submit(mission_dir, "wp01.py", "other.py")

    lines = _lines(mission_dir, _workspace(lane_id=lane_id), _meta("wp01.py"))

    assert lines[0] == f"REVIEW RANGE (WP01): {claim[:12]}..{tip[:12]}  [derived]"
    assert _commands(lines) == [f"  git log --oneline {claim}..{tip} -- wp01.py", f"  git diff {claim}..{tip} -- wp01.py"]
    assert not [line for line in lines[: lines.index("")] if "..HEAD" in line], "the block names no lane base..HEAD range"


def test_lane_less_root_checkout_diffs_against_the_claim_commit_scoped_to_owned_files(mission_dir: Path) -> None:
    claim = _claim(mission_dir)
    tip = _work_and_submit(mission_dir, "wp01.py", "docs/wp01.md")

    lines = _lines(mission_dir, _workspace(lane_id=None), _meta("wp01.py", "docs/wp01.md"))

    assert f"  base: {claim[:12]} (claim event commit)" in lines
    assert f"  tip:  {tip[:12]} (for_review event commit)" in lines
    assert f"  git log --oneline {claim}..{tip} -- wp01.py docs/wp01.md" in lines
    assert f"  git diff {claim}..{tip} -- wp01.py docs/wp01.md" in lines


def test_lane_less_root_checkout_without_a_claim_says_unavailable_and_never_diffs(mission_dir: Path) -> None:
    lines = _lines(mission_dir, _workspace(lane_id=None), _meta("wp01.py"))

    assert lines[0].startswith("REVIEW RANGE (WP01): unavailable — ")
    assert _UNAVAILABLE_COMMAND in lines
    assert not any(line.strip().startswith(("git log", "git diff")) for line in lines)


def test_lane_less_root_checkout_without_owned_files_keeps_the_legacy_unscoped_diff(mission_dir: Path) -> None:
    claim = _claim(mission_dir)
    tip = _work_and_submit(mission_dir, "wp01.py")

    lines = _lines(mission_dir, _workspace(lane_id=None), _meta())

    assert "  scope: unscoped (no owned_files declared)" in lines
    assert f"  git diff {claim}..{tip}" in lines


def test_review_commands_exclude_mission_bookkeeping_only_when_the_mission_dir_is_owned(mission_dir: Path) -> None:
    """re-pin (IC-05): the retired ``_review_pathspecs`` builder's rule now holds on the printed commands (``owned_pathspecs``)."""
    mission_root = f"kitty-specs/{_SLUG}/"
    _claim(mission_dir)
    _work_and_submit(mission_dir, "src/app.py", f"{mission_root}research.md")

    plain = _commands(_lines(mission_dir, _workspace(lane_id=None), _meta("src/app.py")))
    planning = _commands(_lines(mission_dir, _workspace(lane_id=None), _meta(f"{mission_root}research.md")))

    assert shlex.split(plain[1]).count("--") == 1 and shlex.split(plain[1])[-1] == "src/app.py"
    specs = shlex.split(planning[1])[shlex.split(planning[1]).index("--") + 1 :]
    assert specs[0] == f"{mission_root}research.md"
    assert {f":(exclude){mission_root}tasks/**", f":(exclude){mission_root}tasks.md"} <= set(specs)
    assert f":(exclude){mission_root}status.events.jsonl" in specs
    assert f":(exclude){mission_root}status.json" in specs
    assert f"':(exclude){mission_root}tasks/**'" in planning[1], "a pathspec with glob magic is quoted for the shell"


def test_completion_lines_carry_no_owned_checkout_flag_without_a_fact() -> None:
    lines = _completion_lines("implement", "WP01", _SLUG, ["T001"])

    assert any(line.startswith("  spec-kitty agent tasks mark-status T001 --wp WP01 --status done") for line in lines)
    assert not any("--owned-checkout" in line for line in lines)


def test_review_completion_lines_offer_approve_and_reject_without_a_fact() -> None:
    lines = _completion_lines("review", "WP01", _SLUG, [])

    assert any("APPROVE:" in line for line in lines)
    assert any("REJECT:" in line for line in lines)
    assert not any("--owned-checkout" in line for line in lines)


def _root_workspace(branch_name: str | None) -> Any:
    return SimpleNamespace(resolution_kind="repo_root", branch_name=branch_name)


def test_completion_lines_name_the_commit_step_only_where_move_task_will_not_commit(tmp_path: Path) -> None:
    """#7510: the commit step follows ``move-task``'s own no-auto-commit condition."""
    owned: Any = SimpleNamespace(owned_root=tmp_path)
    commit_step = '  git status && spec-kitty safe-commit <your-files> -m "feat(WP01): <description>" --to-branch main'

    root = _completion_lines("implement", "WP01", _SLUG, ["T001"], None, _root_workspace("main"))
    owned_root = _completion_lines("implement", "WP01", _SLUG, ["T001"], owned, _root_workspace("main"))
    lane = _completion_lines("implement", "WP01", _SLUG, ["T001"], None, SimpleNamespace(resolution_kind="lane_workspace", branch_name="kitty/lane-a"))
    no_branch = _completion_lines("implement", "WP01", _SLUG, ["T001"], None, _root_workspace(None))
    review = _completion_lines("review", "WP01", _SLUG, [], None, _root_workspace("main"))

    assert root[2] == commit_step
    for lines in (owned_root, lane, no_branch, review):
        assert not any("safe-commit" in line for line in lines)
