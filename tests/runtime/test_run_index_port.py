"""Unit tests for the RunIndex port (mission runindex-feature-runs-port).

Covers the port's three invariants directly (the end-to-end behaviour is pinned by
``test_run_index_portability_regression.py``):

- token serialization NEVER persists an in-repo absolute ``run_dir`` (#5390 root
  cause; Stijn empty-allowlist ratchet) and leaves foreign/out-of-tree entries
  untouched (adversarial review C2);
- read-time resolution anchors a relative token at the invoking repo root and
  returns an ABSOLUTE path (adversarial review C1);
- containment refuses a ``run_dir`` that resolves outside the invoking repo
  (#2624), including through symlinked roots without false refusals (review I2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.next import run_index
from runtime.next.run_index import RunDirOutsideRepoError

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_serialize_relativizes_in_repo_absolute_and_never_returns_absolute(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    run_dir = repo / ".kittify" / "runtime" / "runs" / "abc123"
    token = run_index.serialize_run_dir(str(run_dir), repo)
    assert token == ".kittify/runtime/runs/abc123"
    assert not Path(token).is_absolute()


def test_serialize_normalizes_relative_and_passes_foreign_absolute_through(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    # already-relative token → normalized posix, still relative
    assert run_index.serialize_run_dir(".kittify/runtime/runs/x", repo) == ".kittify/runtime/runs/x"
    # foreign absolute (outside repo) → left byte-for-byte unchanged (C2)
    foreign = "/somewhere/else/.kittify/runtime/runs/y"
    assert run_index.serialize_run_dir(foreign, repo) == foreign


def test_resolve_relative_token_returns_absolute_under_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    resolved = run_index.resolve_run_dir(".kittify/runtime/runs/abc123", repo)
    assert resolved.is_absolute()
    assert resolved == repo / ".kittify" / "runtime" / "runs" / "abc123"


def test_resolve_absolute_inside_repo_is_allowed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    inside = repo / ".kittify" / "runtime" / "runs" / "abc"
    assert run_index.resolve_run_dir(str(inside), repo) == inside


def test_resolve_refuses_run_dir_outside_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "other" / ".kittify" / "runtime" / "runs" / "abc"
    with pytest.raises(RunDirOutsideRepoError) as exc:
        run_index.resolve_run_dir(str(outside), repo)
    assert exc.value.to_dict()["error_code"] == "RUN_DIR_OUTSIDE_REPO"


def test_resolve_refuses_relative_token_escaping_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(RunDirOutsideRepoError):
        run_index.resolve_run_dir("../escape/runs/abc", repo)


def test_serialize_resolve_round_trip(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    run_dir = repo / ".kittify" / "runtime" / "runs" / "rt"
    token = run_index.serialize_run_dir(str(run_dir), repo)
    assert run_index.resolve_run_dir(token, repo) == run_dir


def test_resolve_through_symlinked_repo_root_is_not_refused(tmp_path: Path) -> None:
    """I2: a repo reached via a symlink (macOS /var↔/private/var class) must not be
    spuriously refused — containment compares fully-resolved real paths."""
    real = tmp_path / "real-repo"
    (real / ".kittify" / "runtime" / "runs" / "s").mkdir(parents=True)
    link = tmp_path / "link-repo"
    link.symlink_to(real, target_is_directory=True)
    resolved = run_index.resolve_run_dir(".kittify/runtime/runs/s", link)
    assert resolved == link / ".kittify" / "runtime" / "runs" / "s"


def test_save_index_tokenizes_in_repo_and_preserves_foreign(tmp_path: Path) -> None:
    """C2 + never-persist-absolute: save tokenizes in-repo absolutes and never
    writes an in-repo absolute, while a foreign absolute passes through untouched."""
    repo = tmp_path / "repo"
    inside = repo / ".kittify" / "runtime" / "runs" / "in"
    foreign = "/elsewhere/.kittify/runtime/runs/out"
    index = {
        "01IN": {"run_id": "in", "run_dir": str(inside), "mission_id": "01IN"},
        "01OUT": {"run_id": "out", "run_dir": foreign, "mission_id": "01OUT"},
    }
    run_index.save_index(repo, index)

    on_disk = json.loads(run_index.feature_runs_path(repo).read_text(encoding="utf-8"))
    assert on_disk["01IN"]["run_dir"] == ".kittify/runtime/runs/in"
    assert not Path(on_disk["01IN"]["run_dir"]).is_absolute()
    assert on_disk["01OUT"]["run_dir"] == foreign  # foreign left for the heal migration
    # the in-memory index passed in must not be mutated
    assert index["01IN"]["run_dir"] == str(inside)


def test_save_index_never_persists_an_in_repo_absolute_run_dir(tmp_path: Path) -> None:
    """The empty-allowlist invariant Stijn asked for: no in-repo absolute run_dir
    is ever written by the port."""
    repo = tmp_path / "repo"
    index = {"01Z": {"run_id": "z", "run_dir": str(repo / ".kittify" / "runtime" / "runs" / "z")}}
    run_index.save_index(repo, index)
    on_disk = json.loads(run_index.feature_runs_path(repo).read_text(encoding="utf-8"))
    stored = on_disk["01Z"]["run_dir"]
    resolved = run_index.resolve_run_dir(stored, repo)
    assert not Path(stored).is_absolute()
    assert resolved.is_relative_to(repo)
