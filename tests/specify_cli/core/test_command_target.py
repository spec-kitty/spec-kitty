"""Unit coverage for the declaration-first command repo_root/branch entry (#6142, Inc 1).

The ONE typed producer of a mission-scoped command's ``(repo_root, target_branch)``
target (ADR ``docs/adr/4.x/2026-10-10-1``, Option B, Increment 1). These tests pin every
resolution branch directly:

* declaration present -> the declared ``target_branch`` + ``DECLARATION`` provenance;
* declaration absent -> the configured primary branch via a ``VALIDATED_FALLBACK`` that
  NEVER reads the ambient checked-out HEAD (the behaviour correction);
* corrupt ``meta.json`` -> fail-closed (``MissionMetaReadError`` propagates);
* invoked from a worktree -> ``repo_root`` is the canonical primary (worktree->primary
  collapse), never the raw worktree;
* no git marker -> fail-closed (``WorkspaceRootNotFound``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.core.command_target import (
    CommandRepoTarget,
    TargetProvenance,
    resolve_command_repo_target,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import (
    MissionMetaReadError,
    UnsafePathSegmentError,
    WorkspaceRootNotFound,
)
from specify_cli.core.git_ops import resolve_primary_branch

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "declaration-first-demo-01TEST000"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "--initial-branch=main")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test")
    _git(path, "config", "commit.gpgsign", "false")
    (path / ".kittify").mkdir(exist_ok=True)
    (path / "README.md").write_text("hi\n", encoding="utf-8")
    _git(path, "add", ".")
    _git(path, "commit", "-m", "init")
    return path.resolve()


def _write_mission_meta(repo_root: Path, *, target_branch: str | None) -> Path:
    mission_dir = repo_root / KITTY_SPECS_DIR / _SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {"mission_slug": _SLUG, "topology": "single_branch"}
    if target_branch is not None:
        meta["target_branch"] = target_branch
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return mission_dir


def test_declaration_present_wins_with_declaration_provenance(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write_mission_meta(repo, target_branch="release-4.x")
    # Even standing on a divergent branch, the declaration is the target.
    _git(repo, "checkout", "-b", "feature-x")

    result = resolve_command_repo_target(_SLUG, cwd=repo)

    assert isinstance(result, CommandRepoTarget)
    assert result.repo_root == repo
    assert result.target_branch == "release-4.x"
    assert result.provenance is TargetProvenance.DECLARATION


def test_declaration_absent_falls_back_to_configured_primary_not_ambient(tmp_path: Path) -> None:
    """The behaviour correction: ambient checked-out branch NEVER wins.

    With no declared ``target_branch`` and the checkout standing on a non-primary
    branch, the entry resolves to the configured primary (``main``), not the ambient
    branch. The contrast assertion documents the ambient seed the scattered call sites
    carried (``resolve_primary_branch(..., bias=True)`` returned the checked-out branch).
    """
    repo = _init_repo(tmp_path / "repo")
    _write_mission_meta(repo, target_branch=None)
    _git(repo, "checkout", "-b", "feature-x")

    result = resolve_command_repo_target(_SLUG, cwd=repo)

    assert result.target_branch == "main"
    assert result.provenance is TargetProvenance.VALIDATED_FALLBACK
    # Contrast: the ambient seed the entry replaces returned the checked-out branch.
    assert resolve_primary_branch(repo, bias=True) == "feature-x"


def test_no_mission_dir_falls_back_to_configured_primary(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")  # no kitty-specs/<slug> at all
    _git(repo, "checkout", "-b", "feature-y")

    result = resolve_command_repo_target(_SLUG, cwd=repo)

    assert result.target_branch == "main"
    assert result.provenance is TargetProvenance.VALIDATED_FALLBACK


def test_corrupt_meta_fails_closed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    mission_dir = repo / KITTY_SPECS_DIR / _SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

    with pytest.raises(MissionMetaReadError):
        resolve_command_repo_target(_SLUG, cwd=repo)


def test_worktree_collapses_to_canonical_primary(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write_mission_meta(repo, target_branch="release-4.x")
    worktree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane-x", str(worktree))

    result = resolve_command_repo_target(_SLUG, cwd=worktree)

    # repo_root is the canonical primary, never the worktree.
    assert result.repo_root == repo
    assert result.target_branch == "release-4.x"


def test_explicit_repo_root_is_collapsed(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    _write_mission_meta(repo, target_branch="release-4.x")
    worktree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-b", "lane-y", str(worktree))

    result = resolve_command_repo_target(_SLUG, repo_root=worktree)

    assert result.repo_root == repo
    assert result.target_branch == "release-4.x"


def test_no_git_marker_fails_closed(tmp_path: Path) -> None:
    bare = tmp_path / "not_a_repo"
    bare.mkdir()
    with pytest.raises(WorkspaceRootNotFound):
        resolve_command_repo_target(_SLUG, cwd=bare)


def test_unsafe_slug_is_rejected(tmp_path: Path) -> None:
    """A traversal payload is refused, not composed into a path outside kitty-specs."""
    repo = _init_repo(tmp_path / "repo")
    with pytest.raises(UnsafePathSegmentError):
        resolve_command_repo_target("../evil", repo_root=repo)


def test_cornerstone_less_repo_fallback_is_not_the_ambient_branch(tmp_path: Path) -> None:
    """Regression for the fallback hole: a repo with no origin/HEAD and no common branch,
    standing on a feature branch, with no declared target, must NOT fall back to the
    checked-out branch (the VALIDATED_FALLBACK contract)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=wip-ticket-123")  # no main/master/develop, no remote
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    _write_mission_meta(repo, target_branch=None)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")

    result = resolve_command_repo_target(_SLUG, cwd=repo.resolve())

    assert result.provenance is TargetProvenance.VALIDATED_FALLBACK
    assert result.target_branch != "wip-ticket-123"
    assert result.target_branch == "main"
    # Document that the un-guarded ambient resolver WOULD have returned the feature branch.
    assert resolve_primary_branch(repo.resolve(), bias=True) == "wip-ticket-123"


def test_explicit_repo_root_nongit_does_not_raise(tmp_path: Path) -> None:
    """The explicit repo_root path collapses via get_main_repo_root, which returns the
    resolved path for a non-repo input rather than raising (mirrors the resolver the routed
    call sites relied on) — so WorkspaceRootNotFound is scoped to the cwd path only."""
    bare = tmp_path / "plain_dir"
    bare.mkdir()
    result = resolve_command_repo_target(_SLUG, repo_root=bare)
    assert result.repo_root == bare.resolve()
    assert result.provenance is TargetProvenance.VALIDATED_FALLBACK
