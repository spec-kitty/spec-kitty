"""Bookkeeping-ref helpers in :mod:`specify_cli.git.ref_advance` (#5100 / #5115).

``write_bookkeeping_ref`` / ``delete_bookkeeping_ref`` are the one sanctioned
way to move a spec-kitty bookkeeping ref (``refs/spec-kitty/**`` -- lane work
tips, repo-root claim bases) so the AC-B3 ratchet
(``tests/architectural/test_merge_pipeline_ratchets.py``) keeps every raw
``git update-ref`` inside ``ref_advance.py``. They must refuse any ref outside
that namespace -- a branch is only ever moved by :func:`advance_branch_ref`.

Real-git tests over throwaway temp repositories; git is never mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.git.ref_advance import (
    BookkeepingRefError,
    delete_bookkeeping_ref,
    write_bookkeeping_ref,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_REF = "refs/spec-kitty/lane-tip/kitty/mission-demo-lane-a"


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=check)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "--quiet")
    _git(tmp_path, "config", "user.email", "bk@example.com")
    _git(tmp_path, "config", "user.name", "Bookkeeping Test")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    _git(tmp_path, "add", "a.txt")
    _git(tmp_path, "commit", "--quiet", "-m", "init")
    return tmp_path


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _resolve(repo: Path, ref: str) -> str | None:
    result = _git(repo, "rev-parse", "--verify", "--quiet", ref, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def test_write_creates_and_moves_a_bookkeeping_ref(repo: Path) -> None:
    first = _head(repo)
    assert write_bookkeeping_ref(repo, _REF, first) is True
    assert _resolve(repo, _REF) == first

    (repo / "b.txt").write_text("b\n", encoding="utf-8")
    _git(repo, "add", "b.txt")
    _git(repo, "commit", "--quiet", "-m", "second")
    second = _head(repo)
    assert write_bookkeeping_ref(repo, _REF, second) is True
    assert _resolve(repo, _REF) == second


def test_write_reports_failure_for_an_unknown_object(repo: Path) -> None:
    assert write_bookkeeping_ref(repo, _REF, "f" * 40) is False
    assert _resolve(repo, _REF) is None


def test_delete_removes_the_ref_and_is_idempotent(repo: Path) -> None:
    write_bookkeeping_ref(repo, _REF, _head(repo))
    assert delete_bookkeeping_ref(repo, _REF) is True
    assert _resolve(repo, _REF) is None
    assert delete_bookkeeping_ref(repo, _REF) is True


@pytest.mark.parametrize(
    "ref",
    ["refs/heads/main", "refs/tags/v1", "refs/spec-kitty/", "HEAD", "refs/spec-kittyx/lane-tip/b"],
)
def test_refs_outside_the_bookkeeping_namespace_are_refused(repo: Path, ref: str) -> None:
    before = _head(repo)
    with pytest.raises(BookkeepingRefError):
        write_bookkeeping_ref(repo, ref, before)
    with pytest.raises(BookkeepingRefError):
        delete_bookkeeping_ref(repo, ref)
    assert _head(repo) == before
