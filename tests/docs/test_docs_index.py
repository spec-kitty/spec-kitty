"""Tests for the docs retrieval index: packaged model + build-tooling generator.

Covers WP01 subtasks T001-T006 (mission ``common-docs-query``):

* T001 — red-first byte-stability (NFR-001): ascending path order + a
  subprocess run under a *different* ``PYTHONHASHSEED``, not merely
  "twice-equal" (which a same-process run would fake even without sorting).
* T002 — ``Anchor``/``DocsQueryEntry`` schema + ``slug_for_headings`` ordinal
  dedup.
* T003 — pure helpers: ``scan_headings``/``resolve_title``/``resolve_abstract``.
* T004 — generator API (``render_index``/``parse_index``/``compare_index``/
  ``run_generate_and_compare``), mirroring ``inventory_lockfile.py``.
* T005 — sanity checks on the committed, generated
  ``docs/development/3-2-docs-retrieval-index.yaml``.
* T006 — C-001 (no ``PageInventoryEntry``) and packaging-layering regressions,
  plus the positive "``slugify`` is imported, not forked" assertion.

The fixture docs tree is built **locally** (module-level helper, not a shared
``conftest.py``) per the WP01 prompt: WP02/WP03 build their own fixtures, and
a shared fixture would couple this WP's ownership to theirs.
"""

from __future__ import annotations

import ast
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest

# Make ``scripts.docs`` importable (mirrors tests/docs/conftest.py — the
# repository's pytest.ini only puts ``src`` on ``pythonpath``).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs import docs_index, generate_kitty_specs_docs  # noqa: E402
from specify_cli.docs import index_model  # noqa: E402
from specify_cli.docs.index_model import (  # noqa: E402
    DEFAULT_INDEX_PATH,
    Anchor,
    DocsIndexStore,
    DocsQueryEntry,
    compare_index,
    parse_index,
    render_index,
)

# NOT `fast`: the byte-stability test spawns a subprocess (a fresh interpreter
# under a different PYTHONHASHSEED), which Rule 2 of the marker-correctness gate
# forbids under `fast` (it would inflate the -m fast inner-loop wall-clock).
pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Fixture tree (module-level helper — not conftest.py)
# ---------------------------------------------------------------------------

_ZETA_MD = """---
type: how-to
---
# Zeta Page

Zeta has no `description` frontmatter, so its abstract falls back to this
first paragraph.

## Setup

Steps here.
"""

_ALPHA_MD = """---
title: Alpha Title
description: The alpha page abstract, from frontmatter.
type: reference
---
# Alpha (ignored — frontmatter title wins)

## Overview

First overview section.

```text
## fake heading inside a fence — must not be scanned
```

## Overview

Second overview section (duplicate heading text).

### Details

Sub-section.
"""

_MIDDLE_MD = """# Middle

No frontmatter at all; title falls back to the H1 above.
"""


def _build_fixture_tree(root: Path) -> Path:
    """Build a small docs tree with files written in NON-alphabetical order.

    Creation order is zeta -> nested/middle -> alpha — the reverse of
    path-sort order — so a rendering path that merely relies on filesystem/
    ``rglob`` enumeration order (rather than an explicit ``path`` sort) would
    fail T001's ordering assertion.
    """
    docs_root = root / "docs"
    docs_root.mkdir(parents=True)
    (docs_root / "zeta.md").write_text(_ZETA_MD, encoding="utf-8")
    nested = docs_root / "nested"
    nested.mkdir()
    (nested / "middle.md").write_text(_MIDDLE_MD, encoding="utf-8")
    (docs_root / "alpha.md").write_text(_ALPHA_MD, encoding="utf-8")
    return docs_root


# ---------------------------------------------------------------------------
# AST-based import inspection helpers (T006)
# ---------------------------------------------------------------------------


def _import_from_map(module: object) -> dict[str, str]:
    """Map each ``from X import name`` binding to its source module string ``X``."""
    source = inspect.getsource(module)  # type: ignore[arg-type]
    tree = ast.parse(source)
    mapping: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                mapping[alias.asname or alias.name] = node.module
    return mapping


def _imported_top_level_modules(module: object) -> set[str]:
    """Top-level module names referenced by any import statement in ``module``."""
    source = inspect.getsource(module)  # type: ignore[arg-type]
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


# ---------------------------------------------------------------------------
# T001 — red-first byte-stability (NFR-001)
# ---------------------------------------------------------------------------


def test_generate_index_orders_entries_ascending_by_path(tmp_path: Path) -> None:
    docs_root = _build_fixture_tree(tmp_path)
    entries = docs_index.generate_index(docs_root)
    paths = [entry.path for entry in entries]

    assert paths == sorted(paths)
    assert paths == ["docs/alpha.md", "docs/nested/middle.md", "docs/zeta.md"]


def test_render_index_is_byte_stable_across_hash_seeds(tmp_path: Path) -> None:
    """Regenerate in a subprocess under a *different* ``PYTHONHASHSEED``.

    Guards against hash-seed-dependent set/dict ordering — a same-process
    "run twice -> equal" check would pass even if the generator never sorted
    by path (CPython dict/rglob order is stable within one process).
    """
    docs_root = _build_fixture_tree(tmp_path)
    entries = docs_index.generate_index(docs_root)
    in_process_rendered = render_index(entries)

    src_root = _REPO_ROOT / "src"
    script = (
        "import sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(_REPO_ROOT)!r})\n"
        f"sys.path.insert(0, {str(src_root)!r})\n"
        "from scripts.docs import docs_index as di\n"
        "from specify_cli.docs.index_model import render_index\n"
        f"entries = di.generate_index(Path({str(docs_root)!r}))\n"
        "sys.stdout.write(render_index(entries))\n"
    )
    env = dict(os.environ)
    current_seed = env.get("PYTHONHASHSEED")
    env["PYTHONHASHSEED"] = "4242" if current_seed != "4242" else "13"

    # Invoke via ``uv run`` (not bare ``sys.executable``) so the subprocess
    # resolves the SAME project environment as this test process regardless
    # of shell/shim PATH quirks (repo convention: always ``uv run``).
    # ``--no-sync`` (#4866 WP04 scope extension, was #4922): this call wants
    # the project environment as-is, never a resync — a bare
    # ``uv run --frozen`` silently resyncs whatever ``UV_PROJECT_ENVIRONMENT``
    # (or the default ``.venv``) currently names down to the repo's
    # ``.python-version`` pin, corrupting a concurrently-running xdist
    # worker's environment underneath it. ``--no-sync`` composes cleanly with
    # the custom ``env=`` above: it does not touch the environment mapping,
    # only skips uv's own sync step, so the ``PYTHONHASHSEED`` override this
    # test depends on still reaches the subprocess unchanged (verified
    # empirically; see ``tracer-design-decisions.md``).
    result = subprocess.run(
        ["uv", "run", "--frozen", "--no-sync", "python", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=_REPO_ROOT,
        check=True,
    )
    assert result.stdout == in_process_rendered


# ---------------------------------------------------------------------------
# T002 — Anchor/DocsQueryEntry + slug_for_headings ordinal dedup
# ---------------------------------------------------------------------------


def test_anchor_and_docs_query_entry_are_frozen_dataclasses() -> None:
    anchor = Anchor(slug="overview", text="Overview", level=2)
    with pytest.raises(AttributeError):
        anchor.slug = "changed"  # type: ignore[misc]

    entry = DocsQueryEntry(
        path="docs/example.md",
        title="Example",
        divio_type="explanation",
        anchors=(anchor,),
        abstract="An example abstract.",
    )
    with pytest.raises(AttributeError):
        entry.title = "changed"  # type: ignore[misc]
    assert entry.anchors == (anchor,)


def test_slug_for_headings_empty_input() -> None:
    assert docs_index.slug_for_headings([]) == []


def test_slug_for_headings_ordinal_dedup_triple_duplicate() -> None:
    assert docs_index.slug_for_headings(["Setup", "Setup", "Setup"]) == [
        "setup",
        "setup-2",
        "setup-3",
    ]


def test_slug_for_headings_preserves_order_with_interleaved_duplicates() -> None:
    texts = ["Overview", "Details", "Overview", "Overview"]
    assert docs_index.slug_for_headings(texts) == [
        "overview",
        "details",
        "overview-2",
        "overview-3",
    ]


def test_slug_for_headings_uses_canonical_slugify_for_unicode_and_punctuation() -> None:
    text = "Café, Déjà Vu!"
    expected = generate_kitty_specs_docs.slugify(text, fallback="section")
    assert docs_index.slug_for_headings([text]) == [expected]


# ---------------------------------------------------------------------------
# T003 — pure helpers: heading scan, title precedence, abstract fallback
# ---------------------------------------------------------------------------


def test_scan_headings_ignores_fenced_code_and_h1_and_deeper_levels() -> None:
    body = (
        "# Title (H1 is not an anchor)\n"
        "\n"
        "## First\n"
        "\n"
        "```python\n"
        "## not a heading — inside a fence\n"
        "```\n"
        "\n"
        "#### Too deep — not level 2/3\n"
        "\n"
        "### Second\n"
    )
    assert docs_index.scan_headings(body) == [(2, "First"), (3, "Second")]


def test_resolve_title_prefers_frontmatter_then_h1_then_path_stem(tmp_path: Path) -> None:
    path = tmp_path / "my-page.md"
    assert (
        docs_index.resolve_title({"title": "  From FM  "}, "# Ignored\n", path)
        == "From FM"
    )
    assert docs_index.resolve_title({}, "# From H1\n", path) == "From H1"
    assert docs_index.resolve_title({}, "No heading here.\n", path) == "my-page"


def test_resolve_abstract_prefers_frontmatter_then_paragraph_then_empty() -> None:
    assert (
        docs_index.resolve_abstract({"description": "  From FM.  "}, "# H\n\nBody.\n")
        == "From FM."
    )
    assert (
        docs_index.resolve_abstract({}, "# H\n\nFirst line.\nSecond line.\n\n## More\n")
        == "First line. Second line."
    )
    # No description and no leading prose paragraph -> "". This used to be
    # described as the "ADR/changelog exemption", pointing at
    # description_length_check.py's docs/adr/ carve-out; that carve-out was
    # retired once ADR descriptions were backfilled, and this assertion is
    # about resolve_abstract's own fallback, not about any exemption.
    assert docs_index.resolve_abstract({}, "## Only a heading\n") == ""


# ---------------------------------------------------------------------------
# T004 — generator API mirroring inventory_lockfile.py
# ---------------------------------------------------------------------------


def test_render_index_then_parse_index_round_trips(tmp_path: Path) -> None:
    docs_root = _build_fixture_tree(tmp_path)
    entries = docs_index.generate_index(docs_root)
    rendered = render_index(entries)
    assert parse_index(rendered) == entries


def test_render_index_header_present() -> None:
    assert render_index([]).startswith("# GENERATED — do not edit by hand")


def test_compare_index_detects_added_removed_changed() -> None:
    base = render_index(
        [
            DocsQueryEntry(path="docs/a.md", title="A", divio_type="reference", anchors=(), abstract=""),
            DocsQueryEntry(path="docs/b.md", title="B", divio_type="reference", anchors=(), abstract=""),
        ]
    )
    regenerated = render_index(
        [
            DocsQueryEntry(path="docs/a.md", title="A changed", divio_type="reference", anchors=(), abstract=""),
            DocsQueryEntry(path="docs/c.md", title="C", divio_type="reference", anchors=(), abstract=""),
        ]
    )
    drift = compare_index(base, regenerated)
    assert drift.has_drift
    assert drift.added == ("docs/c.md",)
    assert drift.removed == ("docs/b.md",)
    assert drift.changed == ("docs/a.md",)


def test_compare_index_no_drift_when_identical() -> None:
    rendered = render_index(
        [DocsQueryEntry(path="docs/a.md", title="A", divio_type="reference", anchors=(), abstract="")]
    )
    drift = compare_index(rendered, rendered)
    assert not drift.has_drift
    assert drift.summary() == "added=0 removed=0 changed=0"


def test_run_generate_and_compare_write_then_strict_is_clean(tmp_path: Path) -> None:
    docs_root = _build_fixture_tree(tmp_path)
    index_path = tmp_path / "index.yaml"

    write_report = docs_index.run_generate_and_compare(
        docs_root, index_path, write=True, strict=True
    )
    assert write_report.exit_code == 0
    assert index_path.exists()

    strict_report = docs_index.run_generate_and_compare(
        docs_root, index_path, write=False, strict=True
    )
    assert strict_report.exit_code == 0
    assert not strict_report.drift.has_drift


def test_run_generate_and_compare_detects_stale_index(tmp_path: Path) -> None:
    docs_root = _build_fixture_tree(tmp_path)
    index_path = tmp_path / "index.yaml"
    index_path.write_text(render_index([]), encoding="utf-8")

    report = docs_index.run_generate_and_compare(
        docs_root, index_path, write=False, strict=True
    )
    assert report.exit_code == 1
    assert report.drift.has_drift


def test_docs_index_store_query_matches_and_filters(tmp_path: Path) -> None:
    docs_root = _build_fixture_tree(tmp_path)
    store = DocsIndexStore(docs_index.generate_index(docs_root))

    assert [entry.path for entry in store.query("overview")] == ["docs/alpha.md"]
    assert store.query("does-not-exist-anywhere") == []

    assert [entry.path for entry in store.query("alpha", divio_type="reference")] == [
        "docs/alpha.md"
    ]
    assert store.query("alpha", divio_type="tutorial") == []

    assert [entry.path for entry in store.query("alpha", section="overview-2")] == [
        "docs/alpha.md"
    ]
    assert store.query("alpha", section="not-a-real-section") == []


def test_docs_index_store_query_rejects_empty_term() -> None:
    store = DocsIndexStore([])
    with pytest.raises(ValueError):
        store.query("   ")


def test_docs_index_store_load_round_trips(tmp_path: Path) -> None:
    docs_root = _build_fixture_tree(tmp_path)
    entries = docs_index.generate_index(docs_root)
    index_path = tmp_path / "index.yaml"
    index_path.write_text(render_index(entries), encoding="utf-8")

    store = DocsIndexStore.load(index_path)
    assert store.entries == tuple(entries)


# ---------------------------------------------------------------------------
# T005 — the committed, generated index file
# ---------------------------------------------------------------------------


def test_committed_live_index_is_sorted_headed_and_nonempty() -> None:
    index_path = _REPO_ROOT / DEFAULT_INDEX_PATH
    assert index_path.exists(), f"Expected a generated index at {index_path}"

    text = index_path.read_text(encoding="utf-8")
    assert text.startswith("# GENERATED — do not edit by hand")

    entries = parse_index(text)
    assert len(entries) > 0
    paths = [entry.path for entry in entries]
    assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# T006 — C-001 + packaging-layering regressions
# ---------------------------------------------------------------------------


def test_docs_index_imports_canonical_slugify_not_a_fork() -> None:
    """Positive import assertion (C-005/DIRECTIVE_044): no re-implemented slugger."""
    imports = _import_from_map(docs_index)
    assert imports.get("slugify") == "scripts.docs.generate_kitty_specs_docs"


def test_neither_new_module_imports_page_inventory_entry() -> None:
    """C-001 negative assertion: the sibling index never touches the pinned schema.

    The inventory YAML's own byte-identity is left to the existing guards
    (``test_inventory_path_stable.py``,
    ``test_bulk_ref_rewrite.py::test_inventory_lockfile_untouched``) — this
    test only proves the *symbol* is absent from these two new modules.
    """
    assert "PageInventoryEntry" not in vars(docs_index)
    assert "PageInventoryEntry" not in vars(index_model)
    assert "PageInventoryEntry" not in _import_from_map(docs_index)
    assert "PageInventoryEntry" not in _import_from_map(index_model)


def test_cli_facing_symbols_import_from_packaged_index_model() -> None:
    """The WP02/WP03 seam: DocsQueryEntry/Anchor/DocsIndexStore live in the
    packaged module and are importable without pulling in ``scripts``."""
    from specify_cli.docs.index_model import (
        Anchor as ImportedAnchor,
        DocsIndexStore as ImportedDocsIndexStore,
        DocsQueryEntry as ImportedDocsQueryEntry,
    )

    assert ImportedAnchor is Anchor
    assert ImportedDocsQueryEntry is DocsQueryEntry
    assert ImportedDocsIndexStore is DocsIndexStore


def test_index_model_imports_no_scripts_symbol() -> None:
    """Packaging invariant (the wheel excludes ``scripts``): ``index_model``
    must not import anything from ``scripts``, or the installed CLI's
    dependency would ``ModuleNotFoundError``."""
    assert "scripts" not in _imported_top_level_modules(index_model)
