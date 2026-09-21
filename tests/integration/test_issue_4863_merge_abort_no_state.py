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
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.merge import merge
from specify_cli.coordination import CoordinationWorkspace
from specify_cli.merge.state import MergeState, load_state, save_state

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
        patch(f"{_CORE_MODULE}.locate_project_root", return_value=repo),
        patch(f"{_CORE_MODULE}.is_worktree_context", return_value=False),
        patch(f"{_CORE_MODULE}.is_git_repo", return_value=True),
        patch(f"{_CORE_MODULE}.get_current_branch", return_value="main"),
        patch(f"{_CORE_MODULE}._commit_feature_file"),
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
    with patch("specify_cli.cli.commands.merge.find_repo_root", return_value=repo):
        return CliRunner().invoke(app, ["--abort", "--mission", mission_slug])


def test_abort_valid_coord_mission_without_state_is_true_noop(
    cli_created_coord_mission: tuple[Path, str, str, str],
) -> None:
    """#4863: a resolved mission alone is not proof of an active merge."""
    repo, mission_slug, mission_id, mid8 = cli_created_coord_mission
    mission_dir = repo / "kitty-specs" / mission_slug
    ledger = mission_dir / "status.events.jsonl"
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    ledger_before = ledger.read_bytes()

    assert load_state(repo, mission_id) is None
    result = _invoke_abort(repo, mission_slug)

    assert result.exit_code == 0, result.output
    assert "No active merge state found" in result.output
    assert "Workspace cleaned up" not in result.output
    assert _git(repo, "rev-parse", "HEAD").stdout.strip() == head_before
    assert ledger.read_bytes() == ledger_before
    assert not (mission_dir / "retrospective.yaml").exists()
    assert CoordinationWorkspace.is_present(repo, mission_slug, mid8)


def test_real_abort_tears_down_without_completion_provenance(
    cli_created_coord_mission: tuple[Path, str, str, str],
) -> None:
    """A real abort keeps cleanup semantics but skips the completion terminus."""
    repo, mission_slug, mission_id, mid8 = cli_created_coord_mission
    mission_dir = repo / "kitty-specs" / mission_slug
    ledger = mission_dir / "status.events.jsonl"
    head_before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    ledger_before = ledger.read_bytes()
    save_state(
        MergeState(
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
    assert ledger.read_bytes() == ledger_before
    assert not (mission_dir / "retrospective.yaml").exists()
    assert not CoordinationWorkspace.is_present(repo, mission_slug, mid8)
