"""The declaration-first entry and the placement seam give ONE answer (#6142).

``resolve_command_repo_target`` must hand a command the SAME ``target_branch`` the
placement authority resolves for that command's write
(``placement_seam(...).write_target(kind).ref``). When the two disagree, a
transaction that re-checks placement before its preflight refuses: this is the
``spec-kitty agent record-analysis --report-only`` regression, where an undeclared
``meta.json`` on a non-primary branch made the entry answer ``main`` while placement
answered the checked-out branch, so ``record_report_transaction`` raised "Analysis
report placement changed before preflight".

The entry's fallback is the placement authority's. Making that fallback independent of
the checked-out branch changes the placement seam itself and is follow-up #6152.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.core.command_target import TargetProvenance, resolve_command_repo_target
from specify_cli.core.constants import KITTY_SPECS_DIR

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_SLUG = "placement-parity-01TEST0000"
# record-analysis writes this kind; its placement ref is what the report transaction checks.
_KIND = MissionArtifactKind.ANALYSIS_REPORT


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


def _repo(tmp_path: Path, *, initial_branch: str, target_branch: str | None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", f"--initial-branch={initial_branch}")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    mission_dir = repo / KITTY_SPECS_DIR / _SLUG
    mission_dir.mkdir(parents=True)
    meta: dict[str, object] = {
        "mission_id": "01TEST0000000000000000000A",
        "mission_slug": _SLUG,
        "slug": _SLUG,
        "mission_type": "software-dev",
        "topology": "single_branch",
    }
    if target_branch is not None:
        meta["target_branch"] = target_branch
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo.resolve()


def _with_origin_head(repo: Path, tmp_path: Path) -> None:
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(remote))
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "push", "-q", "origin", "main")
    _git(repo, "remote", "set-head", "origin", "main")


def _assert_one_answer(repo: Path, expected_provenance: TargetProvenance) -> str:
    entry = resolve_command_repo_target(_SLUG, repo_root=repo)
    placement = placement_seam(repo, _SLUG).write_target(_KIND)
    assert entry.target_branch == placement.ref
    assert entry.provenance is expected_provenance
    return entry.target_branch


def test_declared_target_matches_placement(tmp_path: Path) -> None:
    repo = _repo(tmp_path, initial_branch="main", target_branch="release-4.x")
    _git(repo, "checkout", "-b", "feature-x")

    assert _assert_one_answer(repo, TargetProvenance.DECLARATION) == "release-4.x"


def test_undeclared_with_origin_head_matches_placement(tmp_path: Path) -> None:
    repo = _repo(tmp_path, initial_branch="main", target_branch=None)
    _with_origin_head(repo, tmp_path)
    _git(repo, "checkout", "-b", "feature-x")

    assert _assert_one_answer(repo, TargetProvenance.VALIDATED_FALLBACK) == "main"


def test_undeclared_without_remote_on_non_primary_branch_matches_placement(tmp_path: Path) -> None:
    """The record-analysis regression shape: no origin/HEAD, ``main`` exists, HEAD on ``release-2``."""
    repo = _repo(tmp_path, initial_branch="main", target_branch=None)
    _git(repo, "checkout", "-b", "release-2")

    _assert_one_answer(repo, TargetProvenance.VALIDATED_FALLBACK)


def test_cornerstone_less_repo_matches_placement(tmp_path: Path) -> None:
    """No origin/HEAD and no common primary branch: the entry follows placement, never an invented ``main``."""
    repo = _repo(tmp_path, initial_branch="wip-ticket-123", target_branch=None)

    _assert_one_answer(repo, TargetProvenance.VALIDATED_FALLBACK)
