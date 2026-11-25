"""The lane landing proof reads each immutable git answer once per consolidate run (#7848).

``spec-kitty consolidate`` proves every lane twice: once through the Mission branch projection
(:func:`is_landed_through_mission_branch`) and once in lane cleanup
(:func:`is_absorbed_but_for_mission_bookkeeping`). Both walk the same commits by id and read the
same blobs. Inside the run's git read cache scope, a read keyed only on commit ids is answered
once, and a blob lookup reads the whole Mission (or top-level) subtree of a commit in one process
instead of one process per path.

Every verdict must be the same with and without the cache: the cache saves processes, it never
changes an answer.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from kernel.git.read_cache import git_read_cache_scope
from specify_cli.lanes import lane_tip
from specify_cli.lanes.lane_tip import is_absorbed_but_for_mission_bookkeeping
from tests.lanes.landed_mission_support import (
    _COORD,
    _LOG,
    _MD,
    _META,
    _SLUG,
    _SPEC,
    _TARGET,
    _WP01,
    Landed,
    _commit,
    _git,
    _log,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

_REAL_POPEN = subprocess.Popen


class _GitSpawns:
    """Counts git processes started while patched in."""

    def __init__(self) -> None:
        self.count = 0

    def __call__(self, args: Any, *rest: Any, **kwargs: Any) -> Any:
        argv = args if isinstance(args, (list, tuple)) else [args]
        if argv and Path(str(argv[0])).name.startswith("git"):
            self.count += 1
        return _REAL_POPEN(args, *rest, **kwargs)


@pytest.fixture
def spawns() -> Iterator[_GitSpawns]:
    counter = _GitSpawns()
    with mock.patch.object(subprocess, "Popen", counter):
        yield counter


def _proof(landed: Landed, landing: str) -> bool:
    proven: bool = is_absorbed_but_for_mission_bookkeeping(landed.root, landed.tip(), landing, _SLUG)
    return proven


def _landing_sha(landed: Landed) -> str:
    return _git(landed.root, "rev-parse", "main")


def test_a_repeated_proof_in_one_run_starts_no_git_process(landed: Landed, spawns: _GitSpawns) -> None:
    tip = landed.tip()
    landing = _landing_sha(landed)
    with git_read_cache_scope():
        assert is_absorbed_but_for_mission_bookkeeping(landed.root, tip, landing, _SLUG)
        first = spawns.count
        assert is_absorbed_but_for_mission_bookkeeping(landed.root, tip, landing, _SLUG)
    assert first > 0
    assert spawns.count - first <= 1, "only the in-memory merge (merge-tree --write-tree) may run again"


def test_blob_lookups_of_one_commit_read_its_mission_subtree_once(landed: Landed, spawns: _GitSpawns) -> None:
    landing = _landing_sha(landed)
    paths = (_SPEC, _META, _LOG, _WP01, f"{_MD}/missing.md")
    with git_read_cache_scope():
        before = spawns.count
        inside = [lane_tip._blob_id(landed.root, landing, path) for path in paths]
        assert spawns.count - before == 1
    outside = [lane_tip._blob_id(landed.root, landing, path) for path in paths]
    assert inside == outside
    assert inside[-1] is None
    assert all(oid for oid in inside[:-1])


def test_a_directory_path_resolves_to_its_tree_with_and_without_the_cache(landed: Landed) -> None:
    landing = _landing_sha(landed)
    with git_read_cache_scope():
        inside = lane_tip._blob_id(landed.root, landing, f"{_MD}/tasks")
    assert inside == lane_tip._blob_id(landed.root, landing, f"{_MD}/tasks")
    assert inside == _git(landed.root, "rev-parse", f"{landing}:{_MD}/tasks")


def test_a_ref_name_is_read_per_path_without_the_subtree(landed: Landed, spawns: _GitSpawns) -> None:
    with git_read_cache_scope():
        before = spawns.count
        lane_tip._blob_id(landed.root, "main", _SPEC)
        lane_tip._blob_id(landed.root, "main", _SPEC)
    assert spawns.count - before == 2, "a ref name can move: it is never cached"


def _unchanged(_landed: Landed) -> None:
    return None


def _late_product(landed: Landed) -> None:
    _commit(landed.lane, "late work", {"src/late.py": "y = 2\n"})


def _lane_only_event(landed: Landed) -> None:
    _commit(landed.lane, "a lane-only event", {_LOG: _log("e1", "e2", "lane-only")})


def _lane_spec_edit(landed: Landed) -> None:
    _commit(landed.lane, "the lane edits the spec", {_SPEC: "# spec, lane edit\n"})


def _target_spec_edit(landed: Landed) -> None:
    _commit(landed.root, "spec edited after the last sync", {_SPEC: "# spec, revised\n"})


@pytest.mark.parametrize(
    ("shape", "expected"),
    [
        (_unchanged, True),
        (_late_product, False),
        (_lane_only_event, False),
        (_lane_spec_edit, False),
        (_target_spec_edit, True),
    ],
    ids=["squash-landed", "late-product", "lane-only-event", "lane-spec-edit", "target-spec-edit"],
)
def test_the_cache_never_changes_a_verdict(landed: Landed, shape: Callable[[Landed], None], expected: bool) -> None:
    shape(landed)
    landing = _landing_sha(landed)
    with git_read_cache_scope():
        cached = _proof(landed, landing)
        repeated = _proof(landed, landing)
    assert cached == repeated == _proof(landed, landing) == expected


def test_a_lane_moved_inside_the_scope_is_judged_on_its_new_tip(landed: Landed) -> None:
    landing = _landing_sha(landed)
    with git_read_cache_scope():
        assert _proof(landed, landing)
        _lane_spec_edit(landed)
        assert not _proof(landed, landing)


def test_a_landing_ref_name_is_resolved_once_per_proof(landed: Landed, spawns: _GitSpawns) -> None:
    """Lane cleanup hands the proof ``refs/heads/<target>``: inside a run it is pinned to one commit."""
    tip = landed.tip()
    with git_read_cache_scope():
        assert is_absorbed_but_for_mission_bookkeeping(landed.root, tip, _TARGET, _SLUG)
        first = spawns.count
        assert is_absorbed_but_for_mission_bookkeeping(landed.root, tip, _TARGET, _SLUG)
    assert spawns.count - first <= 2, "only the ref resolution and merge-tree may run again"


def test_a_landing_ref_that_moved_between_proofs_is_judged_at_its_new_commit(landed: Landed) -> None:
    with git_read_cache_scope():
        assert _proof(landed, _TARGET)
        _commit(landed.root, "the target drops the lane's product", {"src/lane.py": "x = 0\n"})
        assert not _proof(landed, _TARGET)
    assert not _proof(landed, _TARGET)


def test_an_unknown_landing_ref_fails_closed_inside_a_run(landed: Landed) -> None:
    with git_read_cache_scope():
        assert not _proof(landed, "refs/heads/nope")


@pytest.fixture
def shapes(tmp_path: Path) -> tuple[Path, str]:
    """A commit with a sibling-prefix Mission, a file-as-directory path, non-ASCII names and gitlinks."""
    root = tmp_path / "shapes"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "T")
    _git(root, "config", "commit.gpgsign", "false")
    _commit(
        root,
        "shapes",
        {
            "README": "r\n",
            "kitty-specs/foo/tasks/WP01.md": "w\n",
            "kitty-specs/foo-bar/x": "x\n",
            "kitty-specs/fo o/x": "y\n",
            "kitty-specs/top.md": "t\n",
            'dir/ünï/q"t': "q\n",
        },
    )
    head = _git(root, "rev-parse", "HEAD")
    _git(root, "update-index", "--add", "--cacheinfo", f"160000,{head},kitty-specs/foo/mod")
    _git(root, "update-index", "--add", "--cacheinfo", f"160000,{head},gl")
    _git(root, "commit", "-q", "-m", "gitlinks")
    return root, _git(root, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "path",
    [
        "kitty-specs/foo/tasks/WP01.md",
        "kitty-specs/foo",
        "kitty-specs/foo/",
        "kitty-specs",
        "kitty-specs/top.md",
        "kitty-specs/foo-bar/x",
        "kitty-specs/fo o/x",
        'dir/ünï/q"t',
        "dir/ünï",
        "README",
        "README/x",
        "kitty-specs/foo/missing",
        "kitty-specs/foo/mod",
        "gl",
        "gl/x",
    ],
)
def test_a_blob_lookup_inside_a_run_matches_the_per_path_read(shapes: tuple[Path, str], path: str) -> None:
    root, rev = shapes
    outside = lane_tip._blob_id(root, rev, path)
    with git_read_cache_scope():
        inside = lane_tip._blob_id(root, rev, path)
    assert inside == outside


def test_a_product_path_is_read_alone_never_its_whole_top_level_tree(landed: Landed, spawns: _GitSpawns) -> None:
    """#7848 review: only a Mission folder is listed whole; a product path costs one read per commit."""
    landing = _landing_sha(landed)
    listed: list[str] = []
    real = lane_tip.subtree_entries

    def recording(cwd: Path, rev: str, prefix: str, **kwargs: Any) -> Any:
        listed.append(prefix)
        return real(cwd, rev, prefix, **kwargs)

    with mock.patch.object(lane_tip, "subtree_entries", recording), git_read_cache_scope():
        before = spawns.count
        first = lane_tip._blob_id(landed.root, landing, "src/lane.py")
        assert lane_tip._blob_id(landed.root, landing, "src/lane.py") == first
        assert spawns.count - before == 1
        lane_tip._blob_id(landed.root, landing, _SPEC)
    assert listed == [_MD]
    assert first == lane_tip._blob_id(landed.root, landing, "src/lane.py")


def test_the_landing_ref_pin_runs_on_the_oldest_supported_git(landed: Landed) -> None:
    """#7848 review: ``rev-parse --end-of-options`` needs git 2.30; the project supports 2.25."""
    seen: list[tuple[str, ...]] = []
    real = lane_tip.run_git

    def recording(cwd: Path, *args: str, **kwargs: Any) -> Any:
        seen.append(args)
        return real(cwd, *args, **kwargs)

    with mock.patch.object(lane_tip, "run_git", recording), git_read_cache_scope():
        assert _proof(landed, _TARGET)
    pins = [args for args in seen if args[:1] == ("rev-parse",)]
    assert pins, "the landing ref is pinned inside a run"
    assert all("--end-of-options" not in args for args in pins)


def _pins_seen(run: Callable[[], object]) -> list[tuple[str, ...]]:
    seen: list[tuple[str, ...]] = []
    real = lane_tip.run_git

    def recording(cwd: Path, *args: str, **kwargs: Any) -> Any:
        seen.append(args)
        return real(cwd, *args, **kwargs)

    with mock.patch.object(lane_tip, "run_git", recording):
        run()
    return [args for args in seen if args[:2] == ("rev-parse", "--verify")]


def test_both_proofs_pin_a_ref_name_outside_a_run_too(landed: Landed) -> None:
    """#7848 review: one proof judges one commit whether or not a cache scope is open."""
    content = _pins_seen(lambda: _proof(landed, _TARGET))
    assert content == [("rev-parse", "--verify", f"{_TARGET}^{{commit}}")]
    through = _pins_seen(lambda: lane_tip.is_landed_through_mission_branch(landed.root, landed.tip(), _COORD, _TARGET, _SLUG, approved_tips=(landed.tip(),)))
    assert ("rev-parse", "--verify", f"{_COORD}^{{commit}}") in through
    assert ("rev-parse", "--verify", f"{_TARGET}^{{commit}}") in through


def test_a_commit_id_is_never_pinned_again(landed: Landed) -> None:
    landing = _landing_sha(landed)
    assert _pins_seen(lambda: _proof(landed, landing)) == []
