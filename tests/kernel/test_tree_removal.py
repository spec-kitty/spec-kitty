"""``kernel.tree_removal.remove_tool_owned_tree``: prove ownership, then delete (#5965 / #5966)."""

from __future__ import annotations

import ast
import stat
import sys
from pathlib import Path

import pytest

from kernel import tree_removal
from kernel.tree_removal import TOOL_OWNED_PATH_UNPROVEN, ToolOwnedPathUnproven, remove_tool_owned_tree


def _tree(root: Path) -> Path:
    target = root / "owned" / "child"
    (target / "deep").mkdir(parents=True)
    (target / "deep" / "f.txt").write_text("x", encoding="utf-8")
    return target


def test_removes_a_tree_inside_the_owned_root(tmp_path: Path) -> None:
    target = _tree(tmp_path)

    assert remove_tool_owned_tree(target, owned_root=tmp_path / "owned", reason="test") is True
    assert not target.exists()
    assert (tmp_path / "owned").exists()


def test_removes_the_owned_root_itself(tmp_path: Path) -> None:
    _tree(tmp_path)

    assert remove_tool_owned_tree(tmp_path / "owned", owned_root=tmp_path / "owned", reason="test") is True
    assert not (tmp_path / "owned").exists()


def test_removes_a_single_file(tmp_path: Path) -> None:
    target = _tree(tmp_path) / "deep" / "f.txt"

    assert remove_tool_owned_tree(target, owned_root=tmp_path / "owned", reason="test") is True
    assert not target.exists()


def test_refuses_a_path_outside_the_owned_root(tmp_path: Path) -> None:
    _tree(tmp_path)
    outsider = tmp_path / "elsewhere"
    outsider.mkdir()

    with pytest.raises(ToolOwnedPathUnproven, match=TOOL_OWNED_PATH_UNPROVEN):
        remove_tool_owned_tree(outsider, owned_root=tmp_path / "owned", reason="test")
    assert outsider.exists()


def test_refuses_a_dotdot_escape(tmp_path: Path) -> None:
    _tree(tmp_path)
    outsider = tmp_path / "elsewhere"
    outsider.mkdir()

    with pytest.raises(ToolOwnedPathUnproven):
        remove_tool_owned_tree(tmp_path / "owned" / ".." / "elsewhere", owned_root=tmp_path / "owned", reason="test")
    assert outsider.exists()


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privileges on Windows")
def test_refuses_a_symlink_that_escapes_the_owned_root(tmp_path: Path) -> None:
    _tree(tmp_path)
    outsider = tmp_path / "elsewhere"
    outsider.mkdir()
    (outsider / "keep.txt").write_text("keep", encoding="utf-8")
    link = tmp_path / "owned" / "link"
    link.symlink_to(outsider, target_is_directory=True)

    with pytest.raises(ToolOwnedPathUnproven):
        remove_tool_owned_tree(link, owned_root=tmp_path / "owned", reason="test")
    assert (outsider / "keep.txt").exists()


@pytest.mark.skipif(sys.platform == "win32", reason="symlink creation needs privileges on Windows")
def test_a_symlink_to_an_in_root_target_unlinks_only_the_link(tmp_path: Path) -> None:
    target = _tree(tmp_path)
    link = tmp_path / "owned" / "link"
    link.symlink_to(target, target_is_directory=True)

    assert remove_tool_owned_tree(link, owned_root=tmp_path / "owned", reason="test") is True
    assert not link.exists() and not link.is_symlink()
    assert (target / "deep" / "f.txt").exists()


def test_refuses_a_git_directory(tmp_path: Path) -> None:
    target = _tree(tmp_path)
    (target / ".git").mkdir()

    with pytest.raises(ToolOwnedPathUnproven, match="git checkout"):
        remove_tool_owned_tree(target, owned_root=tmp_path / "owned", reason="test")
    assert target.exists()


def test_refuses_a_git_file_of_a_linked_worktree(tmp_path: Path) -> None:
    target = _tree(tmp_path)
    (target / ".git").write_text("gitdir: /elsewhere\n", encoding="utf-8")

    with pytest.raises(ToolOwnedPathUnproven):
        remove_tool_owned_tree(target, owned_root=tmp_path / "owned", reason="test")
    assert target.exists()


def test_refuses_when_an_ancestor_below_the_owned_root_is_a_checkout(tmp_path: Path) -> None:
    target = _tree(tmp_path)
    (tmp_path / "owned" / ".git").mkdir()

    with pytest.raises(ToolOwnedPathUnproven):
        remove_tool_owned_tree(target / "deep", owned_root=tmp_path / "owned", reason="test")
    assert (target / "deep").exists()


def test_a_missing_path_is_false_or_raises(tmp_path: Path) -> None:
    gone = tmp_path / "owned" / "gone"
    (tmp_path / "owned").mkdir()

    assert remove_tool_owned_tree(gone, owned_root=tmp_path / "owned", reason="test") is False
    with pytest.raises(FileNotFoundError):
        remove_tool_owned_tree(gone, owned_root=tmp_path / "owned", reason="test", missing_ok=False)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_a_read_only_member_is_still_removed(tmp_path: Path) -> None:
    target = _tree(tmp_path)
    member = target / "deep" / "f.txt"
    member.chmod(stat.S_IREAD)
    (target / "deep").chmod(stat.S_IREAD | stat.S_IEXEC)

    assert remove_tool_owned_tree(target, owned_root=tmp_path / "owned", reason="test") is True
    assert not target.exists()


def test_a_failed_removal_raises_unless_best_effort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _tree(tmp_path)

    def boom(_path: Path) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(tree_removal, "_rmtree", boom)

    with pytest.raises(PermissionError):
        remove_tool_owned_tree(target, owned_root=tmp_path / "owned", reason="test")
    assert remove_tool_owned_tree(target, owned_root=tmp_path / "owned", reason="test", best_effort=True) is False
    assert target.exists()


def test_the_module_imports_only_the_standard_library() -> None:
    tree = ast.parse(Path(tree_removal.__file__).read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add((node.module or "").split(".")[0])
    assert roots <= set(sys.stdlib_module_names) | {"__future__"}
