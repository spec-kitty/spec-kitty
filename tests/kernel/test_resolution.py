"""Tests for kernel.resolution — interpreter-invariant loop-rejecting resolve (#3189).

Pins the contract of ``resolve_rejecting_loops``: behaves exactly like
non-strict ``Path.resolve()``, except that a symlink loop anywhere in the
path raises ``OSError(errno.ELOOP, ...)`` on every interpreter (3.11-3.14).
CPython 3.13 dropped the post-realpath ``stat()`` probe that 3.11/3.12
``pathlib.Path.resolve()`` used to surface loops (see research.md R-1), so
non-strict ``resolve()`` on 3.13+ silently returns an unresolved path for a
loop instead of raising. This module pins that the primitive papers over
the divergence.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from kernel.resolution import is_symlink_loop_error, resolve_rejecting_loops


pytestmark = pytest.mark.fast

_SYMLINK_UNAVAILABLE_REASON = "os.symlink unavailable on this platform"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_two_link_loop_raises_eloop(tmp_path: Path) -> None:
    """a -> b -> a is a genuine loop: ELOOP, and is_symlink_loop_error(exc) is true."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.symlink_to(b)
    b.symlink_to(a)

    with pytest.raises(OSError) as excinfo:
        resolve_rejecting_loops(a)

    assert excinfo.value.errno == errno.ELOOP
    assert is_symlink_loop_error(excinfo.value)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_self_loop_raises_eloop(tmp_path: Path) -> None:
    """a -> a is a degenerate one-node loop."""
    a = tmp_path / "a"
    a.symlink_to(a)

    with pytest.raises(OSError) as excinfo:
        resolve_rejecting_loops(a)

    assert excinfo.value.errno == errno.ELOOP
    assert is_symlink_loop_error(excinfo.value)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_loop_in_intermediate_component_raises_eloop(tmp_path: Path) -> None:
    """The loop need not be the final component: loop/child must still raise."""
    loop_a = tmp_path / "loop_a"
    loop_b = tmp_path / "loop_b"
    loop_a.symlink_to(loop_b)
    loop_b.symlink_to(loop_a)
    child = loop_a / "child"

    with pytest.raises(OSError) as excinfo:
        resolve_rejecting_loops(child)

    assert excinfo.value.errno == errno.ELOOP
    assert is_symlink_loop_error(excinfo.value)


def test_regular_file_matches_plain_resolve(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")

    assert resolve_rejecting_loops(target) == target.resolve()


def test_directory_matches_plain_resolve(tmp_path: Path) -> None:
    directory = tmp_path / "dir"
    directory.mkdir()

    assert resolve_rejecting_loops(directory) == directory.resolve()


def test_relative_path_with_dotdot_segments_matches_plain_resolve(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / "deeper"
    nested.mkdir(parents=True)
    relative = nested / ".." / ".." / "nested"

    assert resolve_rejecting_loops(relative) == relative.resolve()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_valid_symlink_chain_matches_plain_resolve(tmp_path: Path) -> None:
    target = tmp_path / "real.txt"
    target.write_text("hello", encoding="utf-8")
    link1 = tmp_path / "link1"
    link2 = tmp_path / "link2"
    link1.symlink_to(target)
    link2.symlink_to(link1)

    assert resolve_rejecting_loops(link2) == link2.resolve()


def test_missing_path_matches_plain_resolve_non_strict(tmp_path: Path) -> None:
    missing = tmp_path / "does" / "not" / "exist.txt"

    assert resolve_rejecting_loops(missing) == missing.resolve()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason=_SYMLINK_UNAVAILABLE_REASON)
def test_dangling_non_looping_symlink_matches_plain_resolve(tmp_path: Path) -> None:
    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "never-created.txt")

    assert resolve_rejecting_loops(dangling) == dangling.resolve()


def test_non_loop_runtime_error_propagates_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A programmer defect (RuntimeError with no OSError context) must not be masked as a loop."""
    target = tmp_path / "whatever"

    def _boom(self: Path, *, strict: bool = False) -> Path:
        raise RuntimeError("programmer defect")

    monkeypatch.setattr(Path, "resolve", _boom)

    with pytest.raises(RuntimeError, match="programmer defect"):
        resolve_rejecting_loops(target)


class TestIsSymlinkLoopError:
    def test_true_for_eloop_oserror(self) -> None:
        exc = OSError(errno.ELOOP, os.strerror(errno.ELOOP), "some/path")
        assert is_symlink_loop_error(exc) is True

    def test_true_for_windows_cant_resolve_filename(self) -> None:
        exc = OSError("cannot resolve")
        exc.winerror = 1921  # type: ignore[attr-defined]
        assert is_symlink_loop_error(exc) is True

    def test_false_for_file_not_found_error(self, tmp_path: Path) -> None:
        exc = FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(tmp_path / "missing"))
        assert is_symlink_loop_error(exc) is False

    def test_false_for_plain_value_error(self) -> None:
        assert is_symlink_loop_error(ValueError("not an OSError at all")) is False
