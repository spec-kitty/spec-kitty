"""Scope: create() target_branch logic over a real git repository; the commit runs
for real and only the SaaS fan-out stays mocked."""

from __future__ import annotations

import contextlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner
from click.testing import Result

from specify_cli.cli.commands.agent.mission import app

pytestmark = pytest.mark.fast

_FEATURE_MODULE = "specify_cli.cli.commands.agent.mission"

runner = CliRunner()


def _setup_kittify(repo: Path) -> None:
    """Create minimal .kittify structure required by create()."""
    kittify = repo / ".kittify"
    kittify.mkdir(exist_ok=True)
    (kittify / "config.yaml").write_text(
        "agents:\n  available:\n    - claude\nmission_type_activations:\n  - software-dev\n",
        encoding="utf-8",
    )
    (kittify / "charter.md").write_text("# Charter\n", encoding="utf-8")
    (repo / "kitty-specs").mkdir(exist_ok=True)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo_on(repo: Path, branch: str, *, also: tuple[str, ...] = ()) -> None:
    """A real repository with one commit, checked out on ``branch``; ``also`` names
    further branches created at the same commit."""
    _git(repo, "init", "-q", "-b", branch)
    for key, value in (("user.email", "t@t"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    for other in also:
        _git(repo, "branch", other)


def _run_create_feature(
    repo: Path, slug: str, current_branch: str, extra_args: list[str] | None = None, *, also: tuple[str, ...] = ()
) -> tuple[Result, dict[str, object] | None]:
    """Invoke create on a real repository checked out on ``current_branch``; return (result, meta)."""
    _init_repo_on(repo, current_branch, also=also)
    args = ["create", slug, "--json"] + (extra_args or [])
    # The create's worktree guard reads the real process cwd: run from ``repo``.
    with (
        contextlib.chdir(repo),
        patch(f"{_FEATURE_MODULE}.locate_project_root", return_value=repo),
        # Keep the canonical local MissionCreated event while disabling the
        # transport fan-out, so the failure-atomic persistence contract is
        # exercised without touching the network.
        patch("specify_cli.status.adapters.fire_lifecycle_saas_fanout"),
    ):
        result = runner.invoke(app, args)

    # Find written meta.json
    meta = None
    kitty_specs = repo / "kitty-specs"
    if kitty_specs.exists():
        for d in kitty_specs.iterdir():
            meta_file = d / "meta.json"
            if meta_file.exists():
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
                break

    return result, meta


# ============================================================================
# target_branch recording
# ============================================================================


def test_create_feature_records_current_branch_2x(tmp_path: Path) -> None:
    """create_feature records target_branch='2.x' when current branch is '2.x'."""
    # Arrange
    _setup_kittify(tmp_path)
    # Assumption check
    assert (tmp_path / ".kittify" / "config.yaml").exists()
    # Act
    result, meta = _run_create_feature(tmp_path, "test-feature", "2.x")
    # Assert
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert meta is not None
    assert meta["target_branch"] == "2.x"


def test_create_feature_records_current_branch_main(tmp_path: Path) -> None:
    """create_feature records target_branch='main' when current branch is 'main'."""
    # Arrange
    _setup_kittify(tmp_path)
    # Assumption check
    assert (tmp_path / ".kittify").exists()
    # Act
    result, meta = _run_create_feature(tmp_path, "test-feature", "main")
    # Assert
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert meta is not None
    assert meta["target_branch"] == "main"


def test_create_feature_records_current_branch_master(tmp_path: Path) -> None:
    """create_feature records target_branch='master' when current branch is 'master'."""
    # Arrange
    _setup_kittify(tmp_path)
    # Assumption check
    assert (tmp_path / ".kittify").exists()
    # Act
    result, meta = _run_create_feature(tmp_path, "test-feature", "master")
    # Assert
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert meta is not None
    assert meta["target_branch"] == "master"


def test_create_feature_records_custom_branch(tmp_path: Path) -> None:
    """create_feature records target_branch='v3-next' when current branch is 'v3-next'."""
    # Arrange
    _setup_kittify(tmp_path)
    # Assumption check
    assert (tmp_path / ".kittify").exists()
    # Act
    result, meta = _run_create_feature(tmp_path, "test-feature", "v3-next")
    # Assert
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert meta is not None
    assert meta["target_branch"] == "v3-next"


def test_create_feature_explicit_target_branch_flag_overrides_current(tmp_path: Path) -> None:
    """--target-branch flag overrides the current branch."""
    # Arrange
    _setup_kittify(tmp_path)
    # Assumption check
    assert (tmp_path / ".kittify").exists()
    # Act
    result, meta = _run_create_feature(tmp_path, "test-feature", "main", extra_args=["--target-branch", "2.x"])
    # Assert
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert meta is not None
    assert meta["target_branch"] == "2.x"


# TODO(conventions): retrofit remaining test bodies


def test_create_feature_2x_wins_even_when_main_coexists(tmp_path: Path) -> None:
    """The critical regression test: on 2.x, target_branch is '2.x' not 'main'."""
    _setup_kittify(tmp_path)
    # Really on 2.x while a real main branch also exists
    result, meta = _run_create_feature(tmp_path, "test-feature", "2.x", also=("main",))
    assert result.exit_code == 0, f"Command failed: {result.output}"
    assert meta is not None
    assert meta["target_branch"] == "2.x"


# ============================================================================
# Guard conditions
# ============================================================================


def test_create_feature_rejects_worktree_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """create_feature exits non-zero when run from inside a real linked worktree."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _setup_kittify(repo)
    _init_repo_on(repo, "main")
    linked = tmp_path / "linked"
    subprocess.run(["git", "worktree", "add", "-q", "--detach", str(linked)], cwd=repo, check=True)
    monkeypatch.chdir(linked)
    with patch(f"{_FEATURE_MODULE}.locate_project_root", return_value=repo):
        result = runner.invoke(app, ["create", "test-feature", "--json"])

    assert result.exit_code != 0
    assert "worktree" in result.output
    assert not list((repo / "kitty-specs").iterdir())


def test_create_feature_rejects_detached_head(tmp_path: Path) -> None:
    """create_feature exits non-zero on a real detached HEAD."""
    _setup_kittify(tmp_path)
    _init_repo_on(tmp_path, "main")
    _git(tmp_path, "checkout", "-q", "--detach")
    with (
        contextlib.chdir(tmp_path),
        patch(f"{_FEATURE_MODULE}.locate_project_root", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["create", "test-feature", "--json"])

    assert result.exit_code != 0
    assert "detached HEAD" in result.output


def test_create_feature_rejects_invalid_slug(tmp_path: Path) -> None:
    """create_feature exits non-zero for non-kebab-case slugs."""
    _setup_kittify(tmp_path)
    # Slug validation happens before any git checks, so no core patches needed
    result = runner.invoke(app, ["create", "Invalid_Slug", "--json"])

    assert result.exit_code != 0
