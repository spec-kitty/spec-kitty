"""A changelog fragment is not a docs page: adding one touches no shared, generated file.

Per-PR fragments live in ``docs/changelog/unreleased/`` (operator ruling, 2026-11-01). Every other
``docs/**/*.md`` file is a page: it needs frontmatter, a row in ``page-inventory.yaml`` and an entry
in ``docs-retrieval-index.yaml``. If a fragment counted as a page, every PR would edit those two
shared files again, which is the merge conflict fragments exist to remove. So the page walk has
one authority, :func:`scripts.docs._page_scope.iter_docs_pages`, and it leaves the fragment
directory out.

The live ``docs/changelog/unreleased/README.md`` deliberately has no frontmatter: any scanner that
walks ``docs/`` without the shared exclusion fails the live docs gates on it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.docs._page_scope import FRAGMENT_PAGE_DIR, is_docs_page, iter_docs_pages
from scripts.docs.docs_index import generate_index
from scripts.docs.inventory_lockfile import generate_inventory, render_lockfile
from scripts.release.changelog_fragments import FRAGMENT_DIR_REL
from specify_cli.docs.index_model import render_index

pytestmark = [pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
_PAGE = (
    "---\ntitle: Guide\n"
    "description: A guide page that exists so the generated files are not empty for this test.\n"
    "type: how-to\nupdated: '2026-11-01'\n---\n# Guide\n\n## Steps\n"
)


def _tree(tmp_path: Path, *, with_fragment: bool) -> Path:
    docs = tmp_path / "docs"
    (docs / "guides").mkdir(parents=True)
    (docs / "guides" / "guide.md").write_text(_PAGE, encoding="utf-8")
    if with_fragment:
        fragments = docs / "changelog" / "unreleased"
        fragments.mkdir(parents=True)
        (fragments / "README.md").write_text("# Fragments\n", encoding="utf-8")
        (fragments / "6999.fixed.md").write_text("- **A fix** (#6999). Short.\n", encoding="utf-8")
    return docs


def test_the_page_scope_names_the_fragment_directory() -> None:
    assert f"docs/{FRAGMENT_PAGE_DIR}" == FRAGMENT_DIR_REL


@pytest.mark.parametrize("with_fragment", [False, True])
def test_a_new_fragment_changes_neither_generated_file(tmp_path: Path, with_fragment: bool) -> None:
    baseline = _tree(tmp_path / "base", with_fragment=False)
    candidate = _tree(tmp_path / "cand", with_fragment=with_fragment)

    def generated(docs: Path) -> tuple[str, str]:
        index = render_index(generate_index(docs, repo_root=docs.parent))
        inventory = render_lockfile(generate_inventory(docs, repo_root=docs.parent))
        return index, inventory

    assert generated(candidate) == generated(baseline)


def test_the_walk_skips_fragments_but_keeps_the_changelog_page(tmp_path: Path) -> None:
    docs = _tree(tmp_path, with_fragment=True)
    (docs / "changelog" / "CHANGELOG.md").write_text(_PAGE, encoding="utf-8")

    pages = [path.relative_to(docs).as_posix() for path in iter_docs_pages(docs)]

    assert pages == ["changelog/CHANGELOG.md", "guides/guide.md"]
    assert not is_docs_page(docs / "changelog" / "unreleased" / "6999.fixed.md", docs)


def test_the_live_tree_has_fragments_outside_the_page_set() -> None:
    """Non-vacuity: the live fragment directory exists and none of its files is a page."""
    docs = REPO_ROOT / "docs"
    live = sorted((REPO_ROOT / FRAGMENT_DIR_REL).glob("*.md"))

    assert live, "docs/changelog/unreleased/ must exist with its README"
    assert not any(is_docs_page(path, docs) for path in live)
    assert all(not path.is_relative_to(REPO_ROOT / FRAGMENT_DIR_REL) for path in iter_docs_pages(docs))
