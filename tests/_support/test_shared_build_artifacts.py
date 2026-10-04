"""Tests for the run-stable source snapshot builder.

The nightly performance job checks out a single commit (a depth-1 clone), so
``default_source_snapshot_builder`` is routinely handed a *shallow* source. The
snapshot it builds is what every e2e test project is cloned from; if the
snapshot itself has commits whose parents are missing and no shallow marker,
any history walk in a consumer fails.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._support.shared_build_artifacts import default_source_snapshot_builder

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_COMMIT_COUNT = 3


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _git_ok(cwd: Path, *args: str) -> str:
    result = _git(cwd, *args)
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


@pytest.fixture
def origin(tmp_path: Path) -> Path:
    """A full-history repository with ``_COMMIT_COUNT`` commits."""
    repo = tmp_path / "origin"
    repo.mkdir()
    _git_ok(repo, "init", "-q", "-b", "main")
    _git_ok(repo, "config", "user.name", "Snapshot Test")
    _git_ok(repo, "config", "user.email", "snapshot@example.invalid")
    _git_ok(repo, "config", "commit.gpgsign", "false")
    for number in range(_COMMIT_COUNT):
        (repo / "file.txt").write_text(f"revision {number}\n", encoding="utf-8")
        _git_ok(repo, "add", "file.txt")
        _git_ok(repo, "commit", "-q", "-m", f"revision {number}")
    return repo


@pytest.fixture
def shallow(tmp_path: Path, origin: Path) -> Path:
    """A depth-1 clone of ``origin`` (the ``file://`` URL is required for ``--depth``)."""
    clone = tmp_path / "shallow"
    _git_ok(tmp_path, "clone", "-q", "--depth", "1", f"file://{origin}", str(clone))
    assert _git_ok(clone, "rev-parse", "--is-shallow-repository") == "true"
    return clone


def test_snapshot_of_shallow_source_has_readable_history(tmp_path: Path, shallow: Path) -> None:
    snap = tmp_path / "snap"

    default_source_snapshot_builder(shallow, snap)

    assert _git(snap, "log", "--format=%H", "HEAD").returncode == 0
    assert _git_ok(snap, "rev-parse", "--is-shallow-repository") == "true"
    assert _git(snap, "fsck", "--connectivity-only").returncode == 0

    consumer = tmp_path / "consumer"
    _git_ok(tmp_path, "clone", "-q", str(snap), str(consumer))
    assert _git(consumer, "log", "--format=%H", "HEAD").returncode == 0


def test_snapshot_of_full_source_keeps_full_history(tmp_path: Path, origin: Path) -> None:
    snap = tmp_path / "snap"

    default_source_snapshot_builder(origin, snap)

    assert _git_ok(snap, "rev-parse", "HEAD") == _git_ok(origin, "rev-parse", "HEAD")
    assert len(_git_ok(snap, "log", "--format=%H", "HEAD").splitlines()) == _COMMIT_COUNT
    assert _git_ok(snap, "rev-parse", "--is-shallow-repository") == "false"
