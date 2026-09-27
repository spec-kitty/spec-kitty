"""Regression tests for the ``--feature`` alias removal on agent-namespace commands.

WP01 of codebase-sanitization-1060-1622 removed the hidden ``--feature`` alias
from ``agent tasks status`` (and all other agent-namespace commands).  This file
verifies the *post-removal* contract: ``--feature`` is now an unknown option and
must be rejected by the CLI.

The ``--mission`` path continues to work byte-for-byte as before; its correctness
is validated by the broader agent test suite.

Why in-process CliRunner instead of subprocess:
The WP07 contract explicitly requires testing the CURRENT source, not an
installed CLI version. Importing ``specify_cli.cli.commands.agent.app``
directly and exercising it with ``typer.testing.CliRunner`` guarantees
that — no version-skew risk, no PATH risk.
"""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app as agent_app


pytestmark = [pytest.mark.e2e, pytest.mark.git_repo]

REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_e2e_project(tmp_path: Path) -> Path:
    """Replicate the ``e2e_project`` fixture setup in-process.

    Creates a tmp project with .kittify scaffold copied from the repo,
    initializes git, and aligns metadata version. Returns the project
    directory.
    """
    project = tmp_path / "demo"
    project.mkdir()

    shutil.copytree(
        REPO_ROOT / ".kittify",
        project / ".kittify",
        symlinks=True,
    )

    missions_src = REPO_ROOT / "src" / "specify_cli" / "missions"
    missions_dest = project / ".kittify" / "missions"
    if missions_src.exists() and not missions_dest.exists():
        shutil.copytree(missions_src, missions_dest)

    (project / ".gitignore").write_text(
        "__pycache__/\n.worktrees/\n",
        encoding="utf-8",
    )

    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "alias-smoke@example.com"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Alias Smoke"],
        cwd=project,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial project"],
        cwd=project,
        check=True,
        capture_output=True,
    )

    # Align metadata version with source so version-mismatch guards stay quiet.
    metadata_file = project / ".kittify" / "metadata.yaml"
    if metadata_file.exists():
        with open(metadata_file, encoding="utf-8") as f:
            metadata = yaml.safe_load(f) or {}
        with open(REPO_ROOT / "pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)
        current_version = pyproject["project"]["version"] or "unknown"
        metadata.setdefault("spec_kitty", {})["version"] = current_version
        with open(metadata_file, "w", encoding="utf-8") as f:
            yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
        subprocess.run(
            ["git", "add", "."],
            cwd=project,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Align metadata version"],
            cwd=project,
            check=True,
            capture_output=True,
        )

    return project


@pytest.mark.e2e
def test_feature_alias_rejected_by_agent_tasks_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--feature`` must be rejected (unknown option) by ``agent tasks status``.

    WP01 of codebase-sanitization-1060-1622 removed the hidden alias; after
    removal Typer exits with code 2 ("No such option: --feature").
    """
    project = _build_e2e_project(tmp_path)
    runner = CliRunner()

    monkeypatch.chdir(project)

    feature_result = runner.invoke(
        agent_app,
        ["tasks", "status", "--feature", "any-slug", "--json"],
    )

    # Typer raises exit code 2 for unknown options.
    assert feature_result.exit_code == 2, (
        f"Expected exit 2 (unknown option) for --feature after alias removal, got {feature_result.exit_code}.\nOutput:\n{feature_result.output}"
    )
    assert "no such option" in (feature_result.output or "").lower(), f"Expected 'No such option' error message for --feature.\nOutput:\n{feature_result.output}"
