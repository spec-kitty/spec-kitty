"""Unit tests for ``scripts/docs/_dockitty_contract.py`` (#6929): slugs, publication, personas, history."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs._dockitty_contract import (
    EXCLUDED_FOLDERS,
    body_of,
    is_dated_adr,
    is_excluded,
    is_immutable,
    is_published,
    page_for_slug,
    persona_page,
    profile_of_persona_path,
    slug_of,
    split_frontmatter,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


@pytest.mark.parametrize(
    ("rel", "slug"),
    [
        ("guides/x.md", "guides/x"),
        ("adr/4.x/index.md", "adr/4.x"),
        ("architecture/README.md", "architecture"),
        ("index.md", ""),
        ("README.md", ""),
        ("guides/index-of-things.md", "guides/index-of-things"),
        ("Guides/Mixed.md", "Guides/Mixed"),
    ],
)
def test_slug_of(rel: str, slug: str) -> None:
    assert slug_of(rel) == slug


@pytest.mark.parametrize(
    ("rel", "excluded"),
    [
        ("archive/x.md", True),
        ("reports/a/b.md", True),
        ("convergence/x.md", True),
        ("changelog/unreleased/1.fixed.md", True),
        ("archived/x.md", False),
        ("changelog/CHANGELOG.md", False),
        ("plans/archive/x.md", False),
    ],
)
def test_is_excluded(rel: str, excluded: bool) -> None:
    assert is_excluded(rel) is excluded


def test_excluded_folders_name_the_site_exclusions() -> None:
    assert EXCLUDED_FOLDERS == ("archive", "reports", "convergence", "changelog/unreleased")


@pytest.mark.parametrize(
    ("rel", "frontmatter", "published"),
    [
        ("guides/x.md", {"doc_status": "active"}, True),
        ("guides/x.md", {"doc_status": "deprecated"}, True),
        ("guides/x.md", {"doc_status": "draft"}, False),
        ("guides/x.md", {}, False),
        ("guides/x.md", {"doc_status": "  "}, False),
        ("archive/x.md", {"doc_status": "active"}, False),
    ],
)
def test_is_published(rel: str, frontmatter: dict[str, str], published: bool) -> None:
    assert is_published(rel, frontmatter) is published


def _touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ntitle: t\n---\n", encoding="utf-8")


def test_page_for_slug_prefers_file_then_readme_then_index(tmp_path: Path) -> None:
    _touch(tmp_path, "a.md")
    _touch(tmp_path, "b/README.md")
    _touch(tmp_path, "c/index.md")
    _touch(tmp_path, "index.md")
    assert page_for_slug(tmp_path, "a") == tmp_path / "a.md"
    assert page_for_slug(tmp_path, "b") == tmp_path / "b/README.md"
    assert page_for_slug(tmp_path, "c/") == tmp_path / "c/index.md"
    assert page_for_slug(tmp_path, "") == tmp_path / "index.md"
    assert page_for_slug(tmp_path, "missing") is None


def test_persona_resolution(tmp_path: Path) -> None:
    _touch(tmp_path, "context/audience/internal/maintainer.md")
    _touch(tmp_path, "context/audience/external/index.md")
    assert persona_page(tmp_path, "internal/maintainer") == tmp_path / "context/audience/internal/maintainer.md"
    assert persona_page(tmp_path, "external") == tmp_path / "context/audience/external/index.md"
    assert persona_page(tmp_path, "internal/ghost") is None
    assert persona_page(tmp_path, "") is None
    assert persona_page(tmp_path, "../secrets") is None


@pytest.mark.parametrize(
    ("value", "profile"),
    [
        ("docs/context/audience/internal/maintainer.md", "internal/maintainer"),
        ("../context/audience/external/project-owner.md", "external/project-owner"),
        ("../../context/audience/internal/lead-developer.md", "internal/lead-developer"),
        ("end-users", None),
        ("docs/context/charter.md", None),
    ],
)
def test_profile_of_persona_path(value: str, profile: str | None) -> None:
    assert profile_of_persona_path(value) == profile


@pytest.mark.parametrize(
    ("rel", "adr", "immutable"),
    [
        ("adr/4.x/2026-10-31-1-x.md", True, True),
        ("adr/4.x/index.md", False, False),
        ("adr/1.x/README.md", False, False),
        ("plans/x.md", False, True),
        ("reports/x.md", False, True),
        ("changelog/CHANGELOG.md", False, True),
        ("archive/x.md", False, True),
        ("guides/x.md", False, False),
        ("plans/x.yaml", False, False),
    ],
)
def test_adr_and_immutable(rel: str, adr: bool, immutable: bool) -> None:
    assert is_dated_adr(rel) is adr
    assert is_immutable(rel) is immutable


def test_split_frontmatter_keeps_body_bytes() -> None:
    text = "---\r\ntitle: x\r\n---\r\n\r\n# Body\r\n"
    parts = split_frontmatter(text)
    assert parts == ("---\r\ntitle: x\r\n---\r\n", "\r\n# Body\r\n")
    assert body_of(text) == "\r\n# Body\r\n"


@pytest.mark.parametrize("text", ["# No frontmatter\n", "", "---\ntitle: never closed\n"])
def test_text_without_closed_frontmatter_is_all_body(text: str) -> None:
    assert split_frontmatter(text) is None
    assert body_of(text) == text
