"""Symlink-loop refusal tests for the containment seams (issue #3189, WP02/T005).

``ensure_within_directory`` and ``ensure_within_any`` (``specify_cli.core.utils``)
must refuse a symlink loop with their documented ``ValueError`` on every
supported interpreter. Before T006 wires them through
``kernel.resolution.resolve_rejecting_loops``, they instead call
``Path.resolve()`` directly, which:

- on CPython 3.11/3.12 raises a bare ``RuntimeError`` (pathlib's own loop
  probe), which leaks past the seam's ``except ValueError`` undocumented; and
- on CPython 3.13+ silently returns an unresolved path instead of raising
  anything, so the loop is accepted rather than refused.

Each refusal case is paired with a same-fixture positive control, per the WP
prompt's review guidance.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from specify_cli.core.utils import _unresolvable_path_refusal, ensure_within_any, ensure_within_directory

pytestmark = [pytest.mark.fast]

_SYMLINK_UNAVAILABLE = pytest.mark.skipif(not hasattr(os, "symlink"), reason="os.symlink is unavailable on this platform")


def _make_loop(a: Path, b: Path) -> None:
    """Create a real two-link symlink loop: ``a`` -> ``b`` -> ``a``."""
    a.symlink_to(b)
    b.symlink_to(a)


@_SYMLINK_UNAVAILABLE
class TestEnsureWithinDirectorySymlinkLoops:
    """``ensure_within_directory`` refuses every symlink-loop shape."""

    def test_loop_directly_under_root_is_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        loop_a = root / "loop-a"
        loop_b = root / "loop-b"
        _make_loop(loop_a, loop_b)

        with pytest.raises(ValueError):
            ensure_within_directory(loop_a, root)

    def test_loop_in_intermediate_component_is_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        loop_a = root / "loop-a"
        loop_b = root / "loop-b"
        _make_loop(loop_a, loop_b)
        candidate = loop_a / "child.txt"

        with pytest.raises(ValueError):
            ensure_within_directory(candidate, root)

    def test_ordinary_file_under_root_is_returned_resolved(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = root / "file.txt"
        target.write_text("content", encoding="utf-8")

        result = ensure_within_directory(target, root)

        assert result == target.resolve()

    def test_not_yet_existing_path_under_root_is_accepted(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        candidate = root / "does" / "not" / "exist.txt"

        result = ensure_within_directory(candidate, root)

        assert result == candidate.resolve()

    def test_escaping_regular_symlink_is_still_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        escape = root / "escape"
        escape.symlink_to(outside)

        with pytest.raises(ValueError):
            ensure_within_directory(escape, root)


@_SYMLINK_UNAVAILABLE
class TestEnsureWithinAnySymlinkLoops:
    """``ensure_within_any`` refuses every symlink-loop shape."""

    def test_loop_directly_under_root_is_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        loop_a = root / "loop-a"
        loop_b = root / "loop-b"
        _make_loop(loop_a, loop_b)

        with pytest.raises(ValueError):
            ensure_within_any(loop_a, roots=[root])

    def test_loop_in_intermediate_component_is_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        loop_a = root / "loop-a"
        loop_b = root / "loop-b"
        _make_loop(loop_a, loop_b)
        candidate = loop_a / "child.txt"

        with pytest.raises(ValueError):
            ensure_within_any(candidate, roots=[root])

    def test_ordinary_file_under_root_is_returned_resolved(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        target = root / "file.txt"
        target.write_text("content", encoding="utf-8")

        result = ensure_within_any(target, roots=[root])

        assert result == target.resolve(strict=False)

    def test_not_yet_existing_path_under_root_is_accepted(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        candidate = root / "does" / "not" / "exist.txt"

        result = ensure_within_any(candidate, roots=[root])

        assert result == candidate.resolve(strict=False)

    def test_escaping_regular_symlink_is_still_refused(self, tmp_path: Path) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        escape = root / "escape"
        escape.symlink_to(outside)

        with pytest.raises(ValueError):
            ensure_within_any(escape, roots=[root])


def test_refusal_names_a_symlink_loop_only_for_eloop(tmp_path: Path) -> None:
    loop = _unresolvable_path_refusal(tmp_path / "a", OSError(errno.ELOOP, "loop"))
    missing = _unresolvable_path_refusal(tmp_path / "a", FileNotFoundError(errno.ENOENT, "gone"))

    assert "(symlink loop)" in str(loop)
    assert "(symlink loop)" not in str(missing)
    assert str(missing).startswith("Refusing to access unresolvable path:")
