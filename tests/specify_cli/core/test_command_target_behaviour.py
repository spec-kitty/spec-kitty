"""WP03 behaviour-correction witness (#6142, Increment 1, FR-006).

The correction: a mission-scoped resolution whose AMBIENT location (the checked-out
branch) disagrees with the Mission's stored declaration resolves to the DECLARATION, and
when no declaration exists it resolves to the configured primary via a validated fallback
that NEVER reads the ambient checked-out HEAD. This is the behaviour the scattered
ambient seeds (``resolve_primary_branch(repo_root)`` with ``bias=True``, reached via
``get_feature_target_branch``'s fallback) did NOT have — the red-first witness landed with
the entry in WP01 (its unit contract was RED before the module existed) and the routing in
WP02; this file pins the correction explicitly against the ambient seed it replaces.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.core.command_target import TargetProvenance, resolve_command_repo_target
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.git_ops import resolve_primary_branch

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "declaration-first-behaviour-01TEST000"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


def _repo(tmp_path: Path, *, target_branch: str | None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    mission_dir = repo / KITTY_SPECS_DIR / _SLUG
    mission_dir.mkdir(parents=True)
    meta: dict[str, object] = {"mission_slug": _SLUG}
    if target_branch is not None:
        meta["target_branch"] = target_branch
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo.resolve()


def test_declaration_wins_over_disagreeing_ambient_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, target_branch="release-4.x")
    _git(repo, "checkout", "-b", "some-feature")  # ambient disagrees with the declaration

    resolved = resolve_command_repo_target(_SLUG, cwd=repo)

    assert resolved.target_branch == "release-4.x"
    assert resolved.provenance is TargetProvenance.DECLARATION
    # The ambient seed the entry replaces would have returned the checked-out branch.
    assert resolve_primary_branch(repo, bias=True) == "some-feature"


def test_validated_fallback_never_returns_the_ambient_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, target_branch=None)  # no declaration
    _git(repo, "checkout", "-b", "some-feature")

    resolved = resolve_command_repo_target(_SLUG, cwd=repo)

    assert resolved.target_branch == "main"  # configured primary, NOT "some-feature"
    assert resolved.provenance is TargetProvenance.VALIDATED_FALLBACK
    assert resolved.target_branch != resolve_primary_branch(repo, bias=True)
