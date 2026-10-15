"""``mission close --discard`` for a protected single_branch mission (#5100).

Drives the REAL CLI entry point on a mission minted by ``mission create`` (its
write checkout sits on ``meta.mission_branch``). The discard must move the
checkout off the branch it is about to delete, and fail closed rather than
report success when the mission cannot be found on the checkout.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app
from tests.core.test_mission_create_protected_single_branch import _finalized_protected_mission

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"refs/heads/{branch}"], capture_output=True).returncode == 0


def test_discard_off_branch_without_meta_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A checkout that does not carry the mission (no meta.json) must not report a discard."""
    repo, slug, minted, feature_dir = _finalized_protected_mission(tmp_path, monkeypatch, "discard-no-meta")
    _git(repo, "checkout", "-q", "main")
    feature_dir.mkdir(parents=True, exist_ok=True)  # residue left behind by an earlier attempt
    (feature_dir / "retrospective.yaml").write_text("residue: true\n", encoding="utf-8")
    assert not (feature_dir / "meta.json").exists()

    result = runner.invoke(root_app, ["mission", "close", "--mission", slug, "--discard", "--force"])

    assert result.exit_code != 0, result.output
    assert "discarded" not in result.output.lower().replace("did not", "")
    assert _branch_exists(repo, minted), "the branch and its work must be left untouched"
