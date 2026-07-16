"""Tests for `.templateignore` copy behaviour (WP02 T006/T007)."""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.doctrine.template_render.ignore_copy import (
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
