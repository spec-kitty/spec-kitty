"""``spec-kitty safe-commit`` refuses a symlink-loop file argument (#3189).

CPython 3.13 reworked non-strict ``pathlib.Path.resolve()`` to silently
return an unresolved path for a symlink loop instead of raising
``RuntimeError`` (3.11/3.12's behavior). ``safe_commit_command`` resolved its
file arguments with a bare ``.resolve()``, so on 3.11/3.12 a symlink-loop
file argument was refused cleanly (the ``RuntimeError`` fell into the
command's broad except-all, producing a JSON error payload and
``typer.Exit(1)`` with nothing committed) -- but on 3.13+ the same argument
resolved silently to a path still inside the loop, and the command went on
to stage and COMMIT the two looping symlinks instead of refusing.

This module pins the fix (``_resolve_file_argument`` routing through
``kernel.resolution.resolve_rejecting_loops``): the same clean refusal, on
every interpreter, paired with a positive control on the identical fixture
proving an ordinary file still commits normally.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli import app as cli_app

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

runner = CliRunner()


def _init_lane_repo(repo: Path, *, branch: str = "kitty/mission-test-01ABCDEF") -> None:
    """Initialize a tmp git repo checked out to a non-protected lane branch (mirrors test_safe_commit_cli.py)."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", f"--initial-branch={branch}"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md", ".kittify/config.json"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _invoke_safe_commit(*file_args: str, message: str) -> Result:
    result = runner.invoke(
        cli_app,
        [
            "safe-commit",
            "--to-branch",
            "kitty/mission-test-01ABCDEF",
            "--message",
            message,
            "--json",
            *file_args,
        ],
        catch_exceptions=False,
    )
    return result


def test_safe_commit_refuses_symlink_loop_file_argument(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#3189 production-path regression: a real ``a -> b``, ``b -> a`` loop is refused, nothing committed.

    Exercises the actual ``safe-commit`` CLI command (not a bare helper call):
    the command's own file-argument resolution is what must refuse the loop
    on every interpreter, not merely the underlying
    ``resolve_rejecting_loops`` primitive in isolation.
    """
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    _init_lane_repo(tmp_path)
    head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    (tmp_path / "a").symlink_to("b")
    (tmp_path / "b").symlink_to("a")

    monkeypatch.chdir(tmp_path)
    result = _invoke_safe_commit("a", "b", message="loop")

    assert result.exit_code == 1, result.stdout + (getattr(result, "stderr", "") or "")
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload.get("error"), "expected an error message naming the refusal"

    # Nothing committed: HEAD unchanged, and the two symlinks are still
    # sitting there untracked (never staged, let alone committed).
    head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert head_after == head_before, "a refused commit must not advance HEAD"
    status = _git(tmp_path, "status", "--porcelain").stdout
    assert "a" in status or "b" in status or status == "", status
    tracked = set(_git(tmp_path, "ls-files").stdout.split())
    assert "a" not in tracked
    assert "b" not in tracked


def test_safe_commit_positive_control_normal_file_still_commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control on the identical fixture: an ordinary file commits normally.

    Proves the refusal above is specific to the symlink loop, not a fixture
    or harness problem that would refuse everything.
    """
    monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
    _init_lane_repo(tmp_path)
    head_before = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()

    (tmp_path / "ordinary.txt").write_text("not a loop\n", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    result = _invoke_safe_commit("ordinary.txt", message="ordinary file commits")

    assert result.exit_code == 0, result.stdout + (getattr(result, "stderr", "") or "")
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["committed"] is True

    head_after = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    assert head_after != head_before, "expected a new commit on HEAD"
    tracked = set(_git(tmp_path, "ls-files").stdout.split())
    assert "ordinary.txt" in tracked
