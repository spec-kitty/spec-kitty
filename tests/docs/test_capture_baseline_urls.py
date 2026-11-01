"""Tests for the pre-move baseline-URL capture (IC-02b, NFR-002 denominator).

These guard the normalisation logic independent of a live DocFX build:

- ``urls_from_site`` over a fixture ``_site`` tree (the canonical capture path
  CI uses) — correct normalisation, sorting, de-duplication, no ``_site/``
  prefix leakage.
- ``derive_urls_from_source`` over a tiny ``docfx.json`` + source tree — the
  glob-faithful fallback used to produce the committed manifest when DocFX is
  unavailable (md→html mapping, ``_*.md``/``toc.yml`` exclusion, ``src``/``dest``
  remapping, standalone ``*.html`` resources).
- ``build_manifest`` / ``write_manifest`` — deterministic, diff-stable output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.docs.capture_baseline_urls import (
    METHOD_DERIVED,
    METHOD_SITE_WALK,
    SITE_URL,
    build_manifest,
    derive_urls_from_source,
    urls_from_site,
    write_manifest,
)

# Pure manifest unit tests (no git/subprocess) — fast developer-loop shard.
pytestmark = pytest.mark.fast

_SITE = "https://example.test/"


def _make_site(root: Path) -> Path:
    """Stage a small emitted ``_site`` tree with nested pages + non-HTML noise."""
    site = root / "_site"
    (site / "how-to" / "harnesses").mkdir(parents=True)
    (site / "reference").mkdir(parents=True)
    (site / "index.html").write_text("<html></html>", encoding="utf-8")
    (site / "how-to" / "create-plan.html").write_text("x", encoding="utf-8")
    (site / "how-to" / "harnesses" / "claude.html").write_text("x", encoding="utf-8")
    (site / "reference" / "cli-commands.html").write_text("x", encoding="utf-8")
    # Non-HTML artefacts must be ignored.
    (site / "toc.json").write_text("{}", encoding="utf-8")
    (site / "reference" / "manifest.yml").write_text("a: b", encoding="utf-8")
    return site


def test_urls_from_site_normalises_sorts_and_dedups(tmp_path: Path) -> None:
    site = _make_site(tmp_path)

    urls = urls_from_site(site, site_url=_SITE)

    assert urls == [
        f"{_SITE}how-to/create-plan.html",
        f"{_SITE}how-to/harnesses/claude.html",
        f"{_SITE}index.html",
        f"{_SITE}reference/cli-commands.html",
    ]
    # Sorted, de-duplicated, and never leaks the ``_site/`` staging prefix.
    assert urls == sorted(set(urls))
    assert all("_site/" not in url for url in urls)
    # Non-HTML files are excluded.
    assert not any(url.endswith((".yml", ".json")) for url in urls)


def test_urls_from_site_default_site_url() -> None:
    assert SITE_URL == "https://docs.spec-kitty.ai/"


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_source_tree(root: Path) -> tuple[Path, Path]:
    """Stage a tiny docs tree + docfx.json exercising the glob semantics."""
    docs = root / "docs"
    # Block 1: base-relative content globs with an exclude.
    _write(docs / "index.md")
    _write(docs / "how-to" / "create-plan.md")
    _write(docs / "how-to" / "harnesses" / "claude.md")
    _write(docs / "how-to" / "_partial.md")  # excluded by **/_*.md
    _write(docs / "how-to" / "toc.yml")  # not a page
    # ``development/`` is NOT in the content globs -> must NOT be published.
    _write(docs / "development" / "internal-note.md")
    # Block 2: src/dest recursive block.
    _write(docs / "archive" / "1x" / "workflow.md")
    _write(docs / "archive" / "index.md")
    # Resource block: standalone HTML published as-is.
    _write(docs / "2x" / "snapshot.html", "<html></html>")

    docfx = docs / "docfx.json"
    docfx.write_text(
        json.dumps(
            {
                "build": {
                    "content": [
                        {
                            "files": [
                                "index.md",
                                "how-to/*.md",
                                "how-to/harnesses/*.md",
                                "how-to/toc.yml",
                            ],
                            "exclude": ["**/_*.md"],
                        },
                        {"files": ["**.md", "**/toc.yml"], "src": "archive", "dest": "archive"},
                    ],
                    "resource": [{"files": ["2x/*.html"]}],
                }
            }
        ),
        encoding="utf-8",
    )
    return docs, docfx


def test_derive_from_source_honours_globs(tmp_path: Path) -> None:
    docs, docfx = _make_source_tree(tmp_path)

    urls = derive_urls_from_source(docs, docfx, site_url=_SITE)

    assert urls == [
        f"{_SITE}2x/snapshot.html",
        f"{_SITE}archive/1x/workflow.html",
        f"{_SITE}archive/index.html",
        f"{_SITE}how-to/create-plan.html",
        f"{_SITE}how-to/harnesses/claude.html",
        f"{_SITE}index.html",
    ]
    assert urls == sorted(urls)


def test_derive_excludes_underscore_and_non_globbed_dirs(tmp_path: Path) -> None:
    docs, docfx = _make_source_tree(tmp_path)

    urls = derive_urls_from_source(docs, docfx, site_url=_SITE)

    # ``_partial.md`` (exclude), ``toc.yml`` (not .md), and the un-globbed
    # ``development/`` tree must never inflate the denominator.
    assert f"{_SITE}how-to/_partial.html" not in urls
    assert not any(url.endswith("toc.html") for url in urls)
    assert not any("development/" in url for url in urls)


def test_derive_maps_md_to_html_with_dest_prefix(tmp_path: Path) -> None:
    docs, docfx = _make_source_tree(tmp_path)

    urls = derive_urls_from_source(docs, docfx, site_url=_SITE)

    # src=archive/dest=archive recursive block keeps the dest prefix + nesting.
    assert f"{_SITE}archive/1x/workflow.html" in urls


def test_derive_scopes_double_star_to_its_prefix(tmp_path: Path) -> None:
    """``assets/**`` must stay inside ``assets/`` and not scoop the whole tree."""
    docs = tmp_path / "docs"
    _write(docs / "assets" / "report.html", "<html></html>")
    # A stray HTML outside every glob must NOT be captured.
    _write(docs / "internal" / "scratch.html", "<html></html>")
    docfx = docs / "docfx.json"
    docfx.write_text(
        json.dumps({"build": {"content": [], "resource": [{"files": ["assets/**"]}]}}),
        encoding="utf-8",
    )

    urls = derive_urls_from_source(docs, docfx, site_url=_SITE)

    assert urls == [f"{_SITE}assets/report.html"]
    assert not any("internal/" in url for url in urls)


def test_resource_block_md_kept_verbatim_never_html(tmp_path: Path) -> None:
    """Resource files are copied verbatim by DocFX — never rendered (#2348).

    A ``*.md`` matched by a *resource* glob (e.g. ``assets/**``) is published
    at its literal path; mapping it to ``.html`` fabricates a phantom baseline
    URL (witnessed live: ``assets/index.html`` 404 while ``assets/index.md``
    serves 200).
    """
    docs = tmp_path / "docs"
    _write(docs / "assets" / "index.md")
    docfx = docs / "docfx.json"
    docfx.write_text(
        json.dumps({"build": {"content": [], "resource": [{"files": ["assets/**"]}]}}),
        encoding="utf-8",
    )

    urls = derive_urls_from_source(docs, docfx, site_url=_SITE)

    assert urls == [f"{_SITE}assets/index.md"]
    assert f"{_SITE}assets/index.html" not in urls


def test_content_block_md_mapping_unchanged_beside_resource_block(tmp_path: Path) -> None:
    """The md→html mapping still applies to content blocks — and only to them."""
    docs = tmp_path / "docs"
    _write(docs / "index.md")
    _write(docs / "assets" / "index.md")
    docfx = docs / "docfx.json"
    docfx.write_text(
        json.dumps(
            {
                "build": {
                    "content": [{"files": ["index.md"]}],
                    "resource": [{"files": ["assets/**"]}],
                }
            }
        ),
        encoding="utf-8",
    )

    urls = derive_urls_from_source(docs, docfx, site_url=_SITE)

    assert urls == [f"{_SITE}assets/index.md", f"{_SITE}index.html"]


def test_build_manifest_shape_and_counts() -> None:
    urls = [f"{_SITE}b.html", f"{_SITE}a.html", f"{_SITE}b.html"]

    manifest = build_manifest(urls, METHOD_DERIVED, site_url=_SITE)

    assert manifest["schema_version"] == 1
    assert manifest["site_url"] == _SITE
    assert manifest["capture_method"] == METHOD_DERIVED
    assert manifest["urls"] == [f"{_SITE}a.html", f"{_SITE}b.html"]
    assert manifest["url_count"] == 2  # de-duplicated count


def test_write_manifest_is_deterministic(tmp_path: Path) -> None:
    manifest = build_manifest(
        [f"{_SITE}a.html", f"{_SITE}c.html", f"{_SITE}b.html"],
        METHOD_SITE_WALK,
        site_url=_SITE,
    )
    out1 = tmp_path / "m1.json"
    out2 = tmp_path / "m2.json"

    write_manifest(out1, manifest)
    write_manifest(out2, manifest)

    bytes1 = out1.read_bytes()
    assert bytes1 == out2.read_bytes()  # byte-identical regen -> diff-stable
    assert bytes1.endswith(b"\n")
    # Stored URLs are sorted on disk.
    on_disk = json.loads(out1.read_text(encoding="utf-8"))
    assert on_disk["urls"] == sorted(on_disk["urls"])


def test_a_directory_exclude_drops_only_that_directory(tmp_path: Path) -> None:
    """``changelog/unreleased/**`` keeps fragments unpublished without dropping every other page.

    Name-only matching is DocFX's ``**/<leaf>`` form; a directory-scoped pattern must match the
    whole relative path, or its ``**`` leaf matches every file name.
    """
    docs = tmp_path / "docs"
    _write(docs / "changelog" / "CHANGELOG.md")
    _write(docs / "changelog" / "unreleased" / "6999.fixed.md")
    _write(docs / "changelog" / "_partial.md")
    docfx = docs / "docfx.json"
    docfx.write_text(
        json.dumps({"build": {"content": [{"files": ["changelog/**.md"], "exclude": ["**/_*.md", "changelog/unreleased/**"]}]}}),
        encoding="utf-8",
    )

    assert derive_urls_from_source(docs, docfx, site_url=_SITE) == [f"{_SITE}changelog/CHANGELOG.html"]
