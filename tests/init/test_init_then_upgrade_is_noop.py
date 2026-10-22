"""#6416: ``spec-kitty upgrade`` on a project ``init`` just set up changes nothing.

Before the fix, ``init`` wrote the canonical merge-driver ``.gitattributes``
lines but not the inert ``issue-matrix.md`` line that the historical
``3.2.6_gate_artifact_merge_drivers`` migration still seeds, and the upgrade's
schema stamp rewrote init's ``last_upgraded_at:`` as ``last_upgraded_at: null``.
The first upgrade then auto-committed both files.
"""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_runner = CliRunner()


def _git(project: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, text=True).stdout.strip()


def _committed_init_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "-q")
    _git(project, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(project, "config", "user.email", "test@example.com")
    _git(project, "config", "user.name", "Test")
    (project / "README.md").write_text("seed\n", encoding="utf-8")
    _git(project, "add", ".")
    _git(project, "commit", "-qm", "seed")
    with contextlib.chdir(project):
        result = _runner.invoke(root_app, ["init", "--non-interactive", "--ai", "claude"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "init")
    return project


def test_upgrade_after_init_makes_no_commit_and_no_tracked_change(tmp_path: Path) -> None:
    project = _committed_init_project(tmp_path)
    head_before = _git(project, "rev-parse", "HEAD")
    attributes_before = (project / ".gitattributes").read_bytes()
    metadata_before = (project / ".kittify" / "metadata.yaml").read_bytes()

    with contextlib.chdir(project):
        result = _runner.invoke(root_app, ["upgrade", "--yes"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert _git(project, "rev-parse", "HEAD") == head_before, _git(project, "log", "--stat", "-1")
    assert _git(project, "status", "--porcelain") == ""
    assert (project / ".gitattributes").read_bytes() == attributes_before
    assert (project / ".kittify" / "metadata.yaml").read_bytes() == metadata_before


def test_init_writes_the_legacy_issue_matrix_line_an_upgrade_seeds(tmp_path: Path) -> None:
    project = _committed_init_project(tmp_path)
    written = (project / ".gitattributes").read_text(encoding="utf-8").splitlines()

    assert "kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix" in written
