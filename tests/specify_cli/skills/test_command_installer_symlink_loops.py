"""Symlink-loop refusal tests for command_installer's containment sites (#3189, WP02/T008).

Both ``_ensure_project_confined`` and ``_resolve_observed_input`` previously
translated a 3.11/3.12 loop-shaped ``RuntimeError`` by hand, and accepted a
loop silently on 3.13+ (``Path.resolve()`` no longer probes for it there).
Each is now routed through ``kernel.resolution.resolve_rejecting_loops``,
which raises the same ``OSError(errno.ELOOP)`` on every interpreter.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from specify_cli.skills.command_installer import (
    InstallerError,
    _ensure_project_confined,
    _resolve_observed_input,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SYMLINK_UNAVAILABLE = pytest.mark.skipif(not hasattr(os, "symlink"), reason="os.symlink is unavailable on this platform")


def _make_loop(a: Path, b: Path) -> None:
    a.symlink_to(b)
    b.symlink_to(a)


@_SYMLINK_UNAVAILABLE
class TestEnsureProjectConfinedSymlinkLoops:
    def test_loop_target_raises_unsafe_path(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        loop_a = repo_root / "loop-a"
        loop_b = repo_root / "loop-b"
        _make_loop(loop_a, loop_b)

        with pytest.raises(InstallerError) as excinfo:
            _ensure_project_confined(repo_root, "loop-a", loop_a)

        assert excinfo.value.code == "unsafe_path"

    def test_normal_in_project_path_passes(self, tmp_path: Path) -> None:
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        target = repo_root / "skills" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("content", encoding="utf-8")

        _ensure_project_confined(repo_root, "skills/SKILL.md", target)


@_SYMLINK_UNAVAILABLE
class TestResolveObservedInputSymlinkLoops:
    def test_loop_raises_oserror_eloop(self, tmp_path: Path) -> None:
        loop_a = tmp_path / "loop-a"
        loop_b = tmp_path / "loop-b"
        _make_loop(loop_a, loop_b)

        with pytest.raises(OSError) as excinfo:
            _resolve_observed_input(loop_a)

        assert excinfo.value.errno == errno.ELOOP

    def test_regular_file_resolves(self, tmp_path: Path) -> None:
        target = tmp_path / "file.txt"
        target.write_text("content", encoding="utf-8")

        assert _resolve_observed_input(target) == target.resolve()
