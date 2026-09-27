"""Symlink-loop guard tests for charter containment seams (#3189, WP03/T012).

CPython 3.11/3.12's non-strict ``Path.resolve()`` raises ``RuntimeError`` when it
encounters a symlink loop; neither
``org_pack_config.resolve_relative_path_within_root`` nor
``PathGuard._assert_allowed`` catches ``RuntimeError``, so a loop leaked past
both guards on those interpreters instead of producing their documented
refusal (``OrgPackSubdirEscapeError`` / ``PathGuardViolation``). On 3.13+
non-strict ``resolve()`` silently accepted the loop instead. Routing the
candidate through ``kernel.resolution.resolve_rejecting_loops`` restores one
interpreter-invariant verdict.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from charter.activation.synthesizer.errors import PathGuardViolation
from charter.activation.synthesizer.path_guard import PathGuard
from charter.offering.drg.org_pack_config import (
    OrgPackSubdirEscapeError,
    resolve_relative_path_within_root,
)


pytestmark = pytest.mark.fast

_SYMLINK_UNAVAILABLE_REASON = "os.symlink unavailable on this platform"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_resolve_relative_path_within_root_loop_raises_escape_error(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    loop = root / "loop"
    loop.symlink_to(loop)

    with pytest.raises(OrgPackSubdirEscapeError):
        resolve_relative_path_within_root(root, "loop")


def test_resolve_relative_path_within_root_valid_subdir_is_accepted(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "subdir").mkdir(parents=True)

    resolved = resolve_relative_path_within_root(root, "subdir")

    assert resolved == (root / "subdir").resolve()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_path_guard_assert_allowed_loop_raises_violation(tmp_path: Path) -> None:
    guard = PathGuard(repo_root=tmp_path)
    loop = tmp_path / ".kittify" / "doctrine" / "loop"
    loop.parent.mkdir(parents=True)
    loop.symlink_to(loop)

    with pytest.raises(PathGuardViolation):
        guard._assert_allowed(loop, caller="test")


def test_path_guard_assert_allowed_allowed_target_is_accepted(tmp_path: Path) -> None:
    guard = PathGuard(repo_root=tmp_path)
    target_dir = tmp_path / ".kittify" / "doctrine"
    target_dir.mkdir(parents=True)
    target = target_dir / "file.yaml"

    guard._assert_allowed(target, caller="test")
