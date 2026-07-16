"""Tests for `.templateignore` copy behaviour (WP02 T006/T007)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.doctrine.template_render.ignore_copy import (
    BUILT_IN_EXCLUDES,
    copy_template_tree,
    load_ignore_rules,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_tree(root: Path) -> None:
    (root / "pack").mkdir()
    (root / "pack" / "org-charter.yaml").write_text('org_name: "{{ORG_NAME}}"\n', encoding="utf-8")
    (root / "README.md").write_text("hello\n", encoding="utf-8")
    (root / "kitty-specs").mkdir()
    (root / "kitty-specs" / "secret.md").write_text("secret\n", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("gitdir\n", encoding="utf-8")
    (root / ".templateignore").write_text(
        "# Spec Kitty Template Renderer ignores these items\n"
        "kitty-specs/\n",
        encoding="utf-8",
    )


def test_copy_excludes_templateignore_git_and_listed_paths(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    _write_tree(src)

    rules = load_ignore_rules(src)
    copy_template_tree(src, dest, rules)

    assert (dest / "pack" / "org-charter.yaml").is_file()
    assert (dest / "README.md").is_file()
    assert not (dest / "kitty-specs").exists()
    assert not (dest / ".git").exists()
    assert not (dest / ".templateignore").exists()


def test_built_in_excludes_apply_without_templateignore_file(tmp_path: Path) -> None:
    """`.git` and `.templateignore` stay out of PACK_PATH with no ignore file."""
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    (src / "pack").mkdir()
    (src / "pack" / "README.md").write_text("keep\n", encoding="utf-8")
    (src / ".git").mkdir()
    (src / ".git" / "config").write_text("gitdir\n", encoding="utf-8")
    # Simulate a stray ignore file name that must still be excluded by built-ins
    # even when it is not the loaded rules file (rules load finds none).
    assert not (src / ".templateignore").exists()

    rules = load_ignore_rules(src)
    assert ".git" in rules.patterns
    assert ".git/" in rules.patterns
    assert ".templateignore" in rules.patterns
    assert set(BUILT_IN_EXCLUDES).issubset(set(rules.patterns))

    copy_template_tree(src, dest, rules)

    assert (dest / "pack" / "README.md").is_file()
    assert not (dest / ".git").exists()
    assert not (dest / ".templateignore").exists()


def test_built_in_excludes_drop_templateignore_even_if_present(tmp_path: Path) -> None:
    src = tmp_path / "src"
    dest = tmp_path / "dest"
    src.mkdir()
    (src / "ok.txt").write_text("ok\n", encoding="utf-8")
    (src / ".templateignore").write_text("# empty defaults only\n", encoding="utf-8")
    (src / ".git").mkdir()
    (src / ".git" / "HEAD").write_text("ref\n", encoding="utf-8")

    rules = load_ignore_rules(src)
    copy_template_tree(src, dest, rules)

    assert (dest / "ok.txt").is_file()
    assert not (dest / ".git").exists()
    assert not (dest / ".templateignore").exists()
