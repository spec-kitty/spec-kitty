"""``resolve_commit_path``: parents resolved, the final component never followed (#5671)."""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from kernel.resolution import is_symlink_loop_error, resolve_commit_path

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _symlink(link: Path, target: str | Path) -> None:
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("os.symlink unavailable in this environment (Windows without developer mode)")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    r = tmp_path / "root"
    r.mkdir()
    return r


def test_final_link_is_kept_not_followed(root: Path) -> None:
    (root / "real.md").write_text("x")
    _symlink(root / "link.md", "real.md")
    assert resolve_commit_path(root, root / "link.md") == root.resolve() / "link.md"


def test_relative_input_is_joined_to_root(root: Path) -> None:
    (root / "real.md").write_text("x")
    _symlink(root / "link.md", "real.md")
    assert resolve_commit_path(root, Path("link.md")) == root.resolve() / "link.md"


def test_parent_symlink_is_resolved(root: Path) -> None:
    (root / "real_dir").mkdir()
    _symlink(root / "alias", root / "real_dir")
    assert resolve_commit_path(root, root / "alias" / "f.md") == root.resolve() / "real_dir" / "f.md"


def test_symlinked_directory_is_a_single_path(root: Path) -> None:
    (root / "real_dir").mkdir()
    _symlink(root / "linkdir", "real_dir")
    assert resolve_commit_path(root, root / "linkdir").name == "linkdir"


def test_dangling_link_is_returned_unchanged(root: Path) -> None:
    _symlink(root / "dangling", "nowhere")
    assert resolve_commit_path(root, root / "dangling") == root.resolve() / "dangling"


def test_looping_leaf_is_refused(root: Path) -> None:
    _symlink(root / "a", "b")
    _symlink(root / "b", "a")
    with pytest.raises(OSError, match="symbolic links") as ei:
        resolve_commit_path(root, root / "a")
    assert is_symlink_loop_error(ei.value)
    assert ei.value.errno == errno.ELOOP


def test_loop_in_parent_is_refused(root: Path) -> None:
    _symlink(root / "a", "b")
    _symlink(root / "b", "a")
    with pytest.raises(OSError, match="symbolic links") as ei:
        resolve_commit_path(root, root / "a" / "f.md")
    assert is_symlink_loop_error(ei.value)


def test_loop_in_parent_is_refused_when_resolve_is_silent(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """3.13 shape: ``Path.resolve`` returns its input unchanged for a loop."""
    _symlink(root / "a", "b")
    _symlink(root / "b", "a")
    monkeypatch.setattr(Path, "resolve", lambda self, strict=False: self)
    with pytest.raises(OSError, match="symbolic links") as ei:
        resolve_commit_path(root, root / "a" / "f.md")
    assert is_symlink_loop_error(ei.value)


def test_containment_is_left_to_the_caller(root: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere" / "x.md"
    outside.parent.mkdir()
    got = resolve_commit_path(root, root / "sub" / ".." / "up.md")
    assert got == root.resolve() / "up.md"
    got_out = resolve_commit_path(root, outside)
    assert got_out == outside.parent.resolve() / "x.md"
    with pytest.raises(ValueError, match="not in the subpath"):
        got_out.relative_to(root.resolve())


def test_directory_argument_without_leaf_name_resolves_normally(root: Path) -> None:
    (root / "docs").mkdir()
    assert resolve_commit_path(root, root / "docs" / ".") == root.resolve() / "docs"
