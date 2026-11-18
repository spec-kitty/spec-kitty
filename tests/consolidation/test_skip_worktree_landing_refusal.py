"""``preflight.skip_worktree_landing_refusal``: which skip-worktree entries refuse a landing up front.

Only an entry the landing's checkout resync would have to rewrite refuses: the bit set by hand
(its file present; a sparse-checkout exclusion has none), on a path under the Mission directory or
one the Mission branch changes. End to end: ``tests/terminus/test_consolidate_skip_worktree_checkout.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.consolidation import preflight
from specify_cli.coordination.types import Refused
from specify_cli.lanes.models import LanesManifest

pytestmark = [pytest.mark.git_repo]

_SLUG = "m"
_META = f"kitty-specs/{_SLUG}/meta.json"
_MISSION_BRANCH = "kitty/mission-m"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True)
    for key, value in (("user.email", "t@t.com"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    for rel in (_META, "src/b.py", "README.md"):
        _write(repo, rel, "base\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "checkout", "-qb", _MISSION_BRANCH)
    _write(repo, "src/b.py", "mission\n")
    _write(repo, _META, "mission\n")
    _git(repo, "commit", "-qam", "mission work")
    _git(repo, "checkout", "-q", "main")
    return repo


def _manifest() -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=_SLUG,
        mission_id="01ABCDEF" + "0" * 18,
        mission_branch=_MISSION_BRANCH,
        target_branch="main",
        lanes=[],
        computed_at="2026-11-17T00:00:00+00:00",
        computed_from="test",
    )


def _verdict(repo: Path) -> Refused | None:
    return preflight.skip_worktree_landing_refusal(repo, _SLUG, _manifest(), target_branch="main")


def test_no_bit_is_no_refusal(repo: Path) -> None:
    assert _verdict(repo) is None


@pytest.mark.parametrize("path", [_META, "src/b.py"], ids=["mission-dir", "landing-diff"])
def test_a_skip_worktree_entry_the_landing_writes_refuses(repo: Path, path: str) -> None:
    _git(repo, "update-index", "--skip-worktree", path)
    verdict = _verdict(repo)
    assert verdict is not None and verdict.error_code == preflight.CHECKOUT_SKIP_WORKTREE_ENTRIES
    assert path in verdict.message and "'main'" in verdict.message
    assert verdict.next_step == f"Clear the bit (`git update-index --no-skip-worktree {path}`), then re-run."


def test_a_skip_worktree_entry_the_landing_does_not_write_is_left_alone(repo: Path) -> None:
    _git(repo, "update-index", "--skip-worktree", "README.md")
    assert _verdict(repo) is None


def test_a_sparse_exclusion_with_no_file_is_left_alone(repo: Path) -> None:
    _git(repo, "update-index", "--skip-worktree", _META)
    (repo / _META).unlink()
    assert _verdict(repo) is None


def test_an_assume_unchanged_bit_is_left_alone(repo: Path) -> None:
    _git(repo, "update-index", "--assume-unchanged", _META)
    assert _verdict(repo) is None


def test_a_checkout_on_another_branch_is_not_judged(repo: Path) -> None:
    _git(repo, "update-index", "--skip-worktree", _META)
    assert preflight.skip_worktree_landing_refusal(repo, _SLUG, _manifest(), target_branch="develop") is None
