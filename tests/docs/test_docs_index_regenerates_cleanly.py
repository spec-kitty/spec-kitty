"""Real-tree gate: the generated docs surfaces regenerate cleanly from the live tree.

The docs retrieval index (``docs/development/docs-retrieval-index.yaml``), the page
inventory (``docs/development/page-inventory.yaml``) and the ADR era tables are no
longer regenerated in pull requests: the ``ci/regen-docs-index`` bot pull request
regenerates them on ``main`` after a merge (``.github/workflows/docs-index-regen.yml``,
``scripts/ci/regen_docs_index.py``). This file replaces the former
``test_committed_docs_index_fresh.py``, whose "committed index equals a regeneration"
assertion made every docs PR edit the same sorted file and conflict with every other.

What a pull request must still guarantee is that the bot CAN regenerate them from the
tree it merges, and that the result is well formed. So instead of comparing with the
committed copy, these tests run the canonical generators over the live ``docs/`` tree
and check the CONTENT: one entry per page, sorted unique paths, non-empty titles, valid
Divio types, unique heading slugs, and a render -> parse round trip that reproduces the
entries exactly. For the inventory: one row per page, sorted, and the rendered lockfile
passes the canonical loader's validation. For the ADR era tables: every ADR the bot
reconciles has the frontmatter its table row needs.

Runs in the ``tests (docs)`` router job (``docs`` filter group). Not ``fast``: a
full-tree generation is seconds-class.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts.docs import inventory_lockfile
from scripts.docs._inventory import load_inventory
from scripts.docs.docs_index import generate_index
from scripts.docs.freshen_adr_inventory import indexed_era_adrs, read_adr_meta
from specify_cli.docs.index_model import (
    DEFAULT_INDEX_PATH,
    DivioType,
    DocsQueryEntry,
    parse_index,
    render_index,
)

#: Repo root: tests/docs/<this file> -> parents[2].
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_ROOT = _REPO_ROOT / "docs"

pytestmark = pytest.mark.unit


def _live_pages() -> list[str]:
    """Every ``docs/**/*.md`` page, repo-relative, sorted -- what the generators walk."""
    return sorted(path.relative_to(_REPO_ROOT).as_posix() for path in _DOCS_ROOT.rglob("*.md"))


@pytest.fixture(scope="module")
def index_entries() -> list[DocsQueryEntry]:
    return generate_index(_DOCS_ROOT, repo_root=_REPO_ROOT)


def _assert_sorted_unique(paths: Sequence[str]) -> None:
    assert list(paths) == sorted(paths), "entries are not sorted by path"
    assert len(set(paths)) == len(paths), "duplicate paths in the generation"


# ---------------------------------------------------------------------------
# Docs retrieval index
# ---------------------------------------------------------------------------


def test_index_has_one_entry_per_live_page(index_entries: list[DocsQueryEntry]) -> None:
    pages = _live_pages()
    assert pages, "the live docs tree has no pages (vacuous)"
    assert [entry.path for entry in index_entries] == pages


def test_index_paths_are_sorted_and_unique(index_entries: list[DocsQueryEntry]) -> None:
    _assert_sorted_unique([entry.path for entry in index_entries])


def test_index_titles_are_non_empty(index_entries: list[DocsQueryEntry]) -> None:
    untitled = [entry.path for entry in index_entries if not entry.title.strip()]
    assert not untitled, f"pages with an empty title: {untitled[:10]}"


def test_index_divio_types_are_valid(index_entries: list[DocsQueryEntry]) -> None:
    valid = {member.value for member in DivioType}
    invalid = [(entry.path, entry.divio_type) for entry in index_entries if entry.divio_type not in valid]
    assert not invalid, f"invalid Divio types: {invalid[:10]}"


def test_index_anchors_are_unique_level_two_or_three(index_entries: list[DocsQueryEntry]) -> None:
    problems: list[str] = []
    for entry in index_entries:
        slugs = [anchor.slug for anchor in entry.anchors]
        if len(set(slugs)) != len(slugs):
            problems.append(f"{entry.path}: duplicate anchor slugs")
        if any(anchor.level not in (2, 3) or not anchor.slug for anchor in entry.anchors):
            problems.append(f"{entry.path}: anchor with a bad level or empty slug")
    assert not problems, problems[:10]
    assert any(entry.anchors for entry in index_entries), "no page has a heading anchor (vacuous)"


def test_index_render_parse_round_trip_reproduces_the_entries(index_entries: list[DocsQueryEntry]) -> None:
    rendered = render_index(index_entries)
    assert parse_index(rendered) == index_entries
    assert render_index(parse_index(rendered)) == rendered, "rendering is not byte-stable"


def test_committed_index_exists_and_parses() -> None:
    """The committed file stays (``docs query`` and two terminology gates read it); it may
    lag the tree on a branch, but it must stay a well-formed index."""
    committed = parse_index((_REPO_ROOT / DEFAULT_INDEX_PATH).read_text(encoding="utf-8"))
    assert committed, "the committed retrieval index is empty"
    _assert_sorted_unique([entry.path for entry in committed])


# ---------------------------------------------------------------------------
# Page inventory
# ---------------------------------------------------------------------------


def test_inventory_regenerates_and_validates(tmp_path: Path) -> None:
    rows = inventory_lockfile.generate_inventory(_DOCS_ROOT, repo_root=_REPO_ROOT)
    paths = [row.path for row in rows]
    assert paths == _live_pages()
    _assert_sorted_unique(paths)

    rendered = tmp_path / "page-inventory.yaml"
    rendered.write_text(inventory_lockfile.render_lockfile(rows), encoding="utf-8")
    assert load_inventory(rendered) == rows  # the canonical loader validates every row


# ---------------------------------------------------------------------------
# ADR era tables
# ---------------------------------------------------------------------------


def test_every_indexed_adr_has_the_frontmatter_its_era_row_needs() -> None:
    """``freshen_adr_inventory --all`` (run by the bot) builds each row from the ADR's
    ``title`` and ``date``; a page missing either would fail the bot after merge."""
    adrs = indexed_era_adrs(_DOCS_ROOT)
    assert adrs, "no ADR in a table-bearing era (vacuous)"
    for adr in adrs:
        meta = read_adr_meta(adr)
        assert meta.title and meta.date, adr
