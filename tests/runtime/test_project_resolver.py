"""Scope: project resolver unit tests — no real git or subprocesses."""

from __future__ import annotations

from pathlib import Path

import pytest
from specify_cli.core.project_resolver import (
    locate_project_root,
)

pytestmark = pytest.mark.fast


def test_env_root_authoritative(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T004: SPECIFY_REPO_ROOT overrides everything — no .kittify needed (#1965)."""
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    result = locate_project_root(start=tmp_path)
    assert result == tmp_path.resolve()


def test_worktree_pointer_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T005: locate_project_root follows .git file pointer to main repo."""
    main_repo = tmp_path / "main_repo"
    (main_repo / ".kittify").mkdir(parents=True)
    worktrees_dir = main_repo / ".git" / "worktrees" / "test_lane"
    worktrees_dir.mkdir(parents=True)

    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {worktrees_dir}\n", encoding="utf-8")

    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    result = locate_project_root(start=worktree)
    assert result == main_repo


def test_locate_project_root_with_explicit_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """T006: locate_project_root respects the start parameter for .kittify walk (Tier 3)."""
    (tmp_path / ".kittify").mkdir()
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    result = locate_project_root(start=tmp_path)
    assert result == tmp_path
