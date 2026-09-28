"""Symlink-loop guard tests for coordination.atomic_write confinement (#3189, WP03/T010).

CPython 3.11/3.12's non-strict ``Path.resolve()`` raises ``RuntimeError`` when it
encounters a symlink loop; 3.13+ silently returns an unresolved path instead
(research.md R-1). ``_confine_path_to_worktree`` and
``_resolve_confined_artifact_path`` both call ``.resolve(strict=False)`` directly on
the candidate path, so before this change a loop leaked the 3.11/3.12
``RuntimeError`` through their ``except OSError`` handler untouched, and was
silently accepted on 3.13+. Routing the candidate through
``kernel.resolution.resolve_rejecting_loops`` restores the single
interpreter-invariant verdict the module's own ``except OSError`` already
translates to ``ValueError``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from specify_cli.coordination.atomic_write import (
    _confine_path_to_worktree,
    _resolve_confined_artifact_path,
    _write_confined_artifact_bytes,
)


pytestmark = pytest.mark.fast

_SYMLINK_UNAVAILABLE_REASON = "os.symlink unavailable on this platform"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_confine_final_component_self_loop_raises_value_error(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    loop = worktree / "loop"
    loop.symlink_to(loop)

    with pytest.raises(ValueError):
        _confine_path_to_worktree(worktree, loop)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_confine_intermediate_component_loop_raises_value_error(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    loop_a = worktree / "loop_a"
    loop_b = worktree / "loop_b"
    loop_a.symlink_to(loop_b)
    loop_b.symlink_to(loop_a)
    child = loop_a / "child.txt"

    with pytest.raises(ValueError):
        _confine_path_to_worktree(worktree, child)


def test_confine_normal_relative_path_is_accepted(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    result = _confine_path_to_worktree(worktree, Path("artifact.json"))

    assert result == worktree / "artifact.json"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_resolve_confined_artifact_path_self_loop_raises_value_error(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    loop = worktree / "loop"
    loop.symlink_to(loop)

    with pytest.raises(ValueError):
        _resolve_confined_artifact_path(worktree, loop)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_write_confined_artifact_bytes_loop_target_raises_and_leaves_symlink(tmp_path: Path) -> None:
    """A loop symlink target must raise, and must NOT be silently replaced.

    Confirmed on 3.13 by the brownfield scout: non-strict ``resolve()`` there
    used to return the unresolved loop path, which downstream code then wrote
    through, replacing the loop symlink with a regular file. The fix must
    raise before any write occurs, leaving the loop symlink in place.
    """
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    loop = worktree / "loop.json"
    loop.symlink_to(loop)

    with pytest.raises(ValueError):
        _write_confined_artifact_bytes(
            worktree,
            loop,
            b"payload",
            resolve=_resolve_confined_artifact_path,
        )

    assert os.path.islink(loop)


def test_write_confined_artifact_bytes_normal_path_is_written(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    target = Path("artifact.json")

    resolved = _write_confined_artifact_bytes(
        worktree,
        target,
        b"payload",
        resolve=_resolve_confined_artifact_path,
    )

    assert resolved.read_bytes() == b"payload"
