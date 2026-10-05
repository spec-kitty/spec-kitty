"""Regression coverage for ``merge --abort`` false completion (#4863).

The destructive abort path used to enter coordination teardown whenever a
mission handle resolved, even when no Spec Kitty merge state existed.  The
shared teardown seam persists a successful-completion retrospective by default,
so the nominal no-op changed the target branch, stamped the mission ledger, and
removed the active coordination worktree.

These tests drive an actual CLI-created coordination mission.  They pin both
sides of the contract: no state means no mission mutation, while a real abort
may clean its coordination topology but must never fabricate completion
provenance.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import AbstractContextManager, chdir
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.consolidate import consolidate as merge
from specify_cli.coordination import CoordinationWorkspace
from specify_cli.consolidation.state import ConsolidationState, load_state, save_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_CORE_MODULE = "specify_cli.core.mission_creation"
_MISSION_SLUG_REQUEST = "issue-4863-abort-no-state"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    (repo / ".kittify").mkdir()
    (repo / "kitty-specs").mkdir()
    (repo / ".kittify" / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initialize project")


def _mission_create_patches(repo: Path) -> list[AbstractContextManager[Any]]:
    return [
        chdir(repo),
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=repo,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission.get_current_branch",
            return_value="main",
        ),
    ]


def _json_payload(output: str) -> dict[str, Any]:
    for line in output.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    pytest.fail(f"No JSON payload in mission-create output: {output!r}")


@pytest.fixture
def cli_created_coord_mission(tmp_path: Path) -> tuple[Path, str, str, str]:
    """Create and materialize a clean coordination mission through the CLI."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    patches = _mission_create_patches(repo)
    for context in patches:
        context.__enter__()
    try:
        result = CliRunner().invoke(
            mission_app,
            [
                "create",
                _MISSION_SLUG_REQUEST,
                "--mission-type",
                "software-dev",
                "--topology",
                "coord",
                "--branch-strategy",
                "already-confirmed",
                "--target-branch",
                "main",
                "--friendly-name",
                "Abort Without State",
                "--purpose-tldr",
                "Prove abort is inert without merge state.",
                "--purpose-context",
                "Issue #4863 regression fixture for a live coordination mission.",
                "--json",
            ],
        )
    finally:
        for context in reversed(patches):
            context.__exit__(None, None, None)

    assert result.exit_code == 0, result.output
    payload = _json_payload(result.output)
    mission_slug = str(payload["mission_slug"])
    mission_id = str(payload["mission_id"])
    mid8 = mission_id[:8]

    _git(repo, "add", f"kitty-specs/{mission_slug}")
    _git(repo, "commit", "-q", "-m", "seed active coordination mission")
    CoordinationWorkspace.resolve(repo, mission_slug, mid8)
    assert CoordinationWorkspace.is_present(repo, mission_slug, mid8)
    return repo, mission_slug, mission_id, mid8


def _invoke_abort(repo: Path, mission_slug: str) -> Any:
    app = typer.Typer()
    app.command()(merge)
    with patch("specify_cli.cli.commands.consolidate.find_repo_root", return_value=repo):
        return CliRunner().invoke(app, ["--abort", "--mission", mission_slug])


def _read_coord_ledger_via_git_show(repo: Path, mission_slug: str) -> bytes:
    """Read ``status.events.jsonl`` from the coordination branch's git history.

    Re-pinned (coord-artifact-single-home-01M3V4BE T031): the ledger now lives
    on the coordination surface from birth (#5440), never the primary
    checkout. A REAL abort tears down the coordination WORKTREE (teardown's
    own contract: it "does NOT delete the coordination branch" -- branch
    deletion belongs to ``spec-kitty merge``), so reading via ``git show
    <branch>:<path>`` -- the branch's own git history -- survives that
    teardown, unlike a now-destroyed worktree-relative file path.
    """
    meta = json.loads((repo / "kitty-specs" / mission_slug / "meta.json").read_text(encoding="utf-8"))
    coordination_branch = str(meta["coordination_branch"])
    result = _git(repo, "show", f"{coordination_branch}:kitty-specs/{mission_slug}/status.events.jsonl")
    return result.stdout.encode("utf-8")


def test_abort_valid_coord_mission_without_state_is_true_noop(
    cli_created_coord_mission: tuple[Path, str, str, str],
) -> None:
    """#4863: a resolved mission alone is not proof of an active merge."""
    repo, mission_slug, mission_id, mid8 = cli_created_coord_mission
    mission_dir = repo / "kitty-specs" / mission_slug
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    ledger_before = _read_coord_ledger_via_git_show(repo, mission_slug)
    # B4 (review cycle 2, MEDIUM): this no-state abort is a true no-op, so the
    # coordination WORKTREE survives (asserted below) -- read its on-disk
    # ledger bytes too. Comparing only the COMMITTED coordination blob (via
    # git show) would pass even if abort appended an uncommitted row directly
    # to the live worktree log; this closes that gap.
    coord_worktree = CoordinationWorkspace.worktree_path(repo, mission_slug, mid8)
    coord_worktree_ledger = coord_worktree / "kitty-specs" / mission_slug / "status.events.jsonl"
    worktree_ledger_before = coord_worktree_ledger.read_bytes()

    assert load_state(repo, mission_id) is None
    result = _invoke_abort(repo, mission_slug)

    assert result.exit_code == 0, result.output
    assert "No active merge state found" in result.output
    assert "Workspace cleaned up" not in result.output
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _read_coord_ledger_via_git_show(repo, mission_slug) == ledger_before
    assert coord_worktree_ledger.read_bytes() == worktree_ledger_before
    # #5440 regression guard: a no-state abort must never resurrect a
    # status.events.jsonl on the PRIMARY (repository root) checkout -- its
    # only home since T031 is the coordination surface.
    assert not (mission_dir / "status.events.jsonl").exists()
    assert not (mission_dir / "retrospective.yaml").exists()
    assert CoordinationWorkspace.is_present(repo, mission_slug, mid8)


def test_real_abort_tears_down_without_completion_provenance(
    cli_created_coord_mission: tuple[Path, str, str, str],
) -> None:
    """A real abort keeps cleanup semantics but skips the completion terminus."""
    repo, mission_slug, mission_id, mid8 = cli_created_coord_mission
    mission_dir = repo / "kitty-specs" / mission_slug
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    ledger_before = _read_coord_ledger_via_git_show(repo, mission_slug)
    save_state(
        ConsolidationState(
            mission_id=mission_id,
            mission_slug=mission_slug,
            target_branch="main",
            wp_order=[],
        ),
        repo,
    )

    result = _invoke_abort(repo, mission_slug)

    assert result.exit_code == 0, result.output
    assert f"Aborted merge for {mission_slug}" in result.output
    assert load_state(repo, mission_id) is None
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _read_coord_ledger_via_git_show(repo, mission_slug) == ledger_before
    # #5440 regression guard (B4, review cycle 2): a real abort's coordination
    # teardown must never resurrect a status.events.jsonl on the PRIMARY
    # (repository root) checkout either.
    assert not (mission_dir / "status.events.jsonl").exists()
    assert not (mission_dir / "retrospective.yaml").exists()
    assert not CoordinationWorkspace.is_present(repo, mission_slug, mid8)
