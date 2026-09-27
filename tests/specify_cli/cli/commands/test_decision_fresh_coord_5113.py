"""#5113 (FR-013/FR-014) — ``decision`` verbs materialize an absent
coordination worktree before any ledger write.

Guards against a real fresh ``COORD`` topology mission (branch created by
``create_mission_core``, worktree never materialized) hitting ``decision
open`` and exiting 1 with an **uncaught** ``CoordinationWorktreeUnmaterialized``
traceback that leaves a half-recorded Decision Moment behind
(``decisions/DM-<id>.md`` + ``decisions/index.json`` +
``decisions/index.json.lock``, with no corresponding
``status.events.jsonl``/coordination-branch commit). The existing
``_coord_declared_no_worktree`` / ``_coord_materialized`` fixtures in
``test_decision_single_authority.py`` cannot reproduce this: the former never
creates the coord branch (probes DELETED), the latter fakes coord dirs with
no git (probes MATERIALIZED).

This module reuses the REAL ``create_mission_core`` fixture helpers from
``tests/integration/test_placement_partition_golden_path.py`` (canonical
sources, DIRECTIVE_044) rather than hand-rolling a third fixture.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mission_runtime import MissionTopology
from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.coordination.workspace import CoordinationWorkspace
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_SLUG_BASE = "decision-fresh-coord-5113"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True)


def _fresh_coord_mission(tmp_path: Path):  # -> tuple[Path, MissionCreationResult]
    """Real fresh ``COORD`` topology mission: branch present, worktree absent."""
    _init_git_repo(tmp_path)
    result = _create_mission(tmp_path, _SLUG_BASE, MissionTopology.COORD)
    return tmp_path, result


def _invoke(args: list[str], cwd: Path):
    old_cwd = os.getcwd()
    try:
        os.chdir(cwd)
        return runner.invoke(agent_app, args, catch_exceptions=True)
    finally:
        os.chdir(old_cwd)


def _assert_no_raw_traceback(result) -> None:
    exc = result.exception
    assert exc is None or isinstance(exc, SystemExit), f"uncaught resolver traceback (the #5113 symptom): {exc!r}"


def _parse_json_lines(output: str) -> list[dict]:  # type: ignore[type-arg]
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def _open_args(slug: str, *, dry_run: bool = False) -> list[str]:
    args = [
        "decision",
        "open",
        "--mission",
        slug,
        "--flow",
        "plan",
        "--input-key",
        "approach",
        "--question",
        "Which approach?",
        "--options",
        '["a","b"]',
        "--step-id",
        "step-1",
        "--json",
    ]
    if dry_run:
        args.append("--dry-run")
    return args


def _resolve_args(slug: str, decision_id: str) -> list[str]:
    return [
        "decision",
        "resolve",
        decision_id,
        "--mission",
        slug,
        "--final-answer",
        "a",
        "--json",
    ]


def _defer_args(slug: str, decision_id: str) -> list[str]:
    return [
        "decision",
        "defer",
        decision_id,
        "--mission",
        slug,
        "--rationale",
        "not yet decidable",
        "--json",
    ]


def _cancel_args(slug: str, decision_id: str) -> list[str]:
    return [
        "decision",
        "cancel",
        decision_id,
        "--mission",
        slug,
        "--rationale",
        "no longer relevant",
        "--json",
    ]


def _list_args(slug: str) -> list[str]:
    return ["decision", "list", "--mission", slug, "--json"]


def _verify_args(slug: str) -> list[str]:
    return ["decision", "verify", "--mission", slug, "--json"]


def _snapshot_mission_dir(repo: Path, slug: str) -> tuple[dict[str, bytes], list[str]]:
    """Byte-for-byte snapshot of every file under ``kitty-specs/<slug>/``."""
    mission_root = repo / "kitty-specs" / slug
    if not mission_root.exists():
        return {}, []
    files = sorted(str(p.relative_to(mission_root)) for p in mission_root.rglob("*") if p.is_file())
    contents = {f: (mission_root / f).read_bytes() for f in files}
    return contents, files


def _rev_parse(repo: Path, ref: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _worktree_list(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _plant_worktrees_file_obstacle(repo: Path) -> None:
    """Make ``.worktrees`` a regular file so ``mkdir(parents=True)`` raises
    ``FileExistsError`` — a REAL obstacle, not a mock (per Test Strategy)."""
    worktrees_path = repo / ".worktrees"
    if worktrees_path.is_dir():
        shutil.rmtree(worktrees_path)
    worktrees_path.write_text("obstacle", encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. open materializes and returns the decision id
# ---------------------------------------------------------------------------


def test_open_materializes_and_returns_id(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path)
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])

    res = _invoke(_open_args(slug), cwd=repo)

    _assert_no_raw_traceback(res)
    assert res.exit_code == 0, f"open failed: {res.output!r}"
    payload = _parse_json_lines(res.output)[-1]
    assert payload["decision_id"]

    coord_worktree = CoordinationWorkspace.worktree_path(repo, slug, mid8)
    assert coord_worktree.exists(), "coordination worktree was not materialized"

    list_res = _invoke(_list_args(slug), cwd=repo)
    assert list_res.exit_code == 0
    list_payload = _parse_json_lines(list_res.output)[-1]
    decision_ids = {d["decision_id"] for d in list_payload["decisions"]}
    assert payload["decision_id"] in decision_ids


# ---------------------------------------------------------------------------
# 2. resolve re-materializes after the worktree is removed
# ---------------------------------------------------------------------------


def test_resolve_materializes(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path)
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])

    open_res = _invoke(_open_args(slug), cwd=repo)
    assert open_res.exit_code == 0, open_res.output
    decision_id = _parse_json_lines(open_res.output)[-1]["decision_id"]

    coord_worktree = CoordinationWorkspace.worktree_path(repo, slug, mid8)
    assert coord_worktree.exists()
    _git(repo, "worktree", "remove", "--force", str(coord_worktree))
    assert not coord_worktree.exists()

    resolve_res = _invoke(_resolve_args(slug, decision_id), cwd=repo)

    _assert_no_raw_traceback(resolve_res)
    assert resolve_res.exit_code == 0, resolve_res.output
    payload = _parse_json_lines(resolve_res.output)[-1]
    assert payload["status"] == "resolved"
    assert coord_worktree.exists()


# ---------------------------------------------------------------------------
# 3. a real materialization failure leaves everything byte-identical
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verb", ["open", "resolve"])
def test_materialization_failure_is_byte_identical(tmp_path: Path, verb: str) -> None:
    repo, result = _fresh_coord_mission(tmp_path)
    slug = result.mission_slug
    coord_branch = result.coordination_branch
    assert coord_branch is not None
    decision_id: str | None = None

    if verb == "resolve":
        # Open successfully on a materialized coordination surface first.
        open_res = _invoke(_open_args(slug), cwd=repo)
        assert open_res.exit_code == 0, open_res.output
        decision_id = _parse_json_lines(open_res.output)[-1]["decision_id"]
        mid8 = str(result.meta["mid8"])
        coord_worktree = CoordinationWorkspace.worktree_path(repo, slug, mid8)
        _git(repo, "worktree", "remove", "--force", str(coord_worktree))
        assert not coord_worktree.exists()

    _plant_worktrees_file_obstacle(repo)

    before_contents, before_files = _snapshot_mission_dir(repo, slug)
    before_branch_tip = _rev_parse(repo, coord_branch)
    before_worktrees = _worktree_list(repo)

    if verb == "open":
        res = _invoke(_open_args(slug), cwd=repo)
    else:
        assert decision_id is not None
        res = _invoke(_resolve_args(slug, decision_id), cwd=repo)

    after_contents, after_files = _snapshot_mission_dir(repo, slug)
    after_branch_tip = _rev_parse(repo, coord_branch)
    after_worktrees = _worktree_list(repo)

    _assert_no_raw_traceback(res)
    assert res.exit_code == 1
    assert "Traceback" not in res.output
    payload = _parse_json_lines(res.output)[-1]
    assert payload.get("code") == "COORDINATION_WORKTREE_UNMATERIALIZED"

    assert before_files == after_files
    assert before_contents == after_contents
    assert before_branch_tip == after_branch_tip
    assert before_worktrees == after_worktrees
    if verb == "open":
        # Fresh mission: no prior successful open, so no lock sidecar exists
        # yet — a materialization failure must not create one either.
        assert not (repo / "kitty-specs" / slug / "decisions" / "index.json.lock").exists()


# ---------------------------------------------------------------------------
# 4. a remote-only branch refuses before any write
# ---------------------------------------------------------------------------


def test_remote_only_branch_refuses_before_write(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path)
    slug = result.mission_slug
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    _git(repo, "update-ref", f"refs/remotes/origin/{coord_branch}", coord_branch)
    _git(repo, "branch", "-D", coord_branch)

    before_contents, before_files = _snapshot_mission_dir(repo, slug)
    before_worktrees = _worktree_list(repo)

    res = _invoke(_open_args(slug), cwd=repo)

    after_contents, after_files = _snapshot_mission_dir(repo, slug)
    after_worktrees = _worktree_list(repo)

    _assert_no_raw_traceback(res)
    assert res.exit_code == 1
    assert "Traceback" not in res.output
    payload = _parse_json_lines(res.output)[-1]
    assert payload.get("code") == "COORDINATION_WORKTREE_UNMATERIALIZED"

    assert before_files == after_files
    assert before_contents == after_contents
    assert before_worktrees == after_worktrees
    assert not (repo / "kitty-specs" / slug / "decisions" / "index.json.lock").exists()


# ---------------------------------------------------------------------------
# 4b. defer / cancel refuse before write too (same ``_terminal_command`` gate,
#     but each CLI verb has its OWN ``except StatusReadPathNotFound`` arm)
# ---------------------------------------------------------------------------


def test_defer_remote_only_branch_refuses_before_write(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path)
    slug = result.mission_slug
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    _git(repo, "update-ref", f"refs/remotes/origin/{coord_branch}", coord_branch)
    _git(repo, "branch", "-D", coord_branch)

    res = _invoke(_defer_args(slug, "01ARBITRARYDECISIONIDXXXXX"), cwd=repo)

    _assert_no_raw_traceback(res)
    assert res.exit_code == 1
    assert "Traceback" not in res.output
    payload = _parse_json_lines(res.output)[-1]
    assert payload.get("code") == "COORDINATION_WORKTREE_UNMATERIALIZED"


def test_cancel_remote_only_branch_refuses_before_write(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path)
    slug = result.mission_slug
    coord_branch = result.coordination_branch
    assert coord_branch is not None

    _git(repo, "update-ref", f"refs/remotes/origin/{coord_branch}", coord_branch)
    _git(repo, "branch", "-D", coord_branch)

    res = _invoke(_cancel_args(slug, "01ARBITRARYDECISIONIDXXXXX"), cwd=repo)

    _assert_no_raw_traceback(res)
    assert res.exit_code == 1
    assert "Traceback" not in res.output
    payload = _parse_json_lines(res.output)[-1]
    assert payload.get("code") == "COORDINATION_WORKTREE_UNMATERIALIZED"


# ---------------------------------------------------------------------------
# 5. list / verify never materialize (D2 read-path guard)
# ---------------------------------------------------------------------------


def test_list_and_verify_never_materialize(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path)
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo, slug, mid8)
    assert not coord_worktree.exists()

    list_res = _invoke(_list_args(slug), cwd=repo)
    verify_res = _invoke(_verify_args(slug), cwd=repo)

    assert list_res.exit_code == 0, list_res.output
    assert verify_res.exit_code == 0, verify_res.output
    assert not coord_worktree.exists()


# ---------------------------------------------------------------------------
# 6. dry-run never materializes
# ---------------------------------------------------------------------------


def test_dry_run_never_materializes(tmp_path: Path) -> None:
    repo, result = _fresh_coord_mission(tmp_path)
    slug = result.mission_slug
    mid8 = str(result.meta["mid8"])
    coord_worktree = CoordinationWorkspace.worktree_path(repo, slug, mid8)
    assert not coord_worktree.exists()

    res = _invoke(_open_args(slug, dry_run=True), cwd=repo)

    assert res.exit_code == 0, res.output
    assert not coord_worktree.exists()
