"""Capture the PRE-move published-URL baseline for the DocFX docs site.

This is **IC-02b** of the Common Docs Structural Move (mission B,
``common-docs-structural-move-01KW3SBK``). It snapshots the set of published
URLs of the *current* (pre-fold) documentation site and writes them to a
checked-in manifest (:data:`DEFAULT_MANIFEST`). That manifest is the
**immutable NFR-002 denominator**: WP07's redirect-coverage check asserts that
*every* baseline URL resolves post-move, directly or via a generated
``<meta http-equiv="refresh">`` stub.

The capture MUST run before WP03 moves the tree. Once the move lands the old
URLs can no longer be observed, and any coverage measured against a post-move
denominator silently reports a false 100% (see ``contracts/redirect-stub.md``,
"Pre-move baseline capture (IC-02b)"). For the same reason the committed
manifest MUST NOT be regenerated after WP03 — wholesale regeneration is
forbidden. A *targeted entry-level amendment* of the committed manifest is
permitted ONLY on two grounds:

(i)  removing URLs proven never-published (a capture defect, e.g. the phantom
     ``assets/index.html`` of #2348); or
(ii) an explicit operator/HiC ruling that accepts URL breakage instead of
     redirect stubs (e.g. retiring legacy URLs outright).

Every amendment MUST be recorded in the manifest's ``amendments`` list
(date, PR, ruling, removed/added entries) so the NFR-002 denominator keeps
its provenance trail.

Two capture methods with two distinct roles (their URL sets are NOT
identical by design):

``--site-dir _site`` (method ``docfx-site-walk``)
    Walk an emitted DocFX ``_site`` tree and normalise every ``*.html`` page
    into its published URL. This is the canonical *baseline-capture* method
    and the one CI uses, because it observes exactly what DocFX published.
    The baseline universe is deliberately restricted to ``*.html``: NFR-002
    protects URLs via ``<meta http-equiv="refresh">`` stubs, an HTML
    mechanism — a verbatim non-HTML resource URL (e.g. a resource-block
    ``*.md`` copied as-is, like ``assets/README.md``) cannot be
    redirect-protected and is therefore live-but-outside the baseline, on
    purpose. ``redirect_stub_generator.load_baseline`` fails loud if a
    non-``.html`` entry ever reaches the committed manifest.

(default) derive-from-source (method ``derived-from-source``)
    Resolve the ``docfx.json`` content/resource globs against the live source
    tree and map each non-excluded content ``*.md`` page to its ``.html`` URL,
    keeping resource-block files (including resource ``*.md``) at their
    verbatim paths. This models the *full served URL set* — the deterministic
    mapping DocFX applies — which the no-404/coverage simulation needs, and
    is a superset of the ``.html``-only baseline universe. Used when
    DocFX/.NET is not available locally; when its output feeds a baseline
    manifest, non-``.html`` entries must not enter the committed baseline.

Reproducing the canonical (site-walk) capture — DocFX is .NET, CI-only today
(invoked by ``.github/workflows/docs-pages.yml``; not installed locally):

    # T009 — install the pinned toolchain (matches docs-pages.yml: .NET 8.x)
    #   dotnet tool install -g docfx          # docs-pages.yml install command
    # T010 — build the PRE-move tree (must be green on the pre-fold tree)
    #   python3 scripts/docs/generate_kitty_specs_docs.py
    #   cd docs && docfx docfx.json && cd ..
    # T011 — snapshot the emitted _site into the committed manifest
    #   python3 scripts/docs/capture_baseline_urls.py --site-dir docs/_site

``docs-pages.yml`` currently installs ``docfx`` unpinned (latest); pinning a
concrete version there is recommended so this capture is bit-reproducible.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Published site root. Mirrors ``_siteUrl`` in ``docs/docfx.json``.
SITE_URL = "https://docs.spec-kitty.ai/"

SCHEMA_VERSION = 1
MD_SUFFIX = ".md"
HTML_SUFFIX = ".html"

METHOD_SITE_WALK = "docfx-site-walk"
METHOD_DERIVED = "derived-from-source"

# Recorded for reproducibility (T009/T010); see the module docstring.
DOCFX_INSTALL_CMD = "dotnet tool install -g docfx"
DOCFX_BUILD_CMD = "cd docs && docfx docfx.json"

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_DIR = _REPO_ROOT / "docs"
DEFAULT_DOCFX_JSON = DEFAULT_DOCS_DIR / "docfx.json"
DEFAULT_MANIFEST = _REPO_ROOT / "scripts" / "docs" / "redirect_baseline_urls.json"


@dataclass(frozen=True)
class GlobBlock:
    """A DocFX content/resource block (``files`` resolved under ``src``)."""

    files: tuple[str, ...]
    src: str = ""
    dest: str = ""
    exclude: tuple[str, ...] = field(default_factory=tuple)


def _as_block(raw: dict[str, Any]) -> GlobBlock:
    files = tuple(str(f) for f in raw.get("files", []))
    exclude = tuple(str(e) for e in raw.get("exclude", []))
    return GlobBlock(
        files=files,
        src=str(raw.get("src", "")),
        dest=str(raw.get("dest", "")),
        exclude=exclude,
    )


def load_blocks(docfx_json: Path) -> tuple[list[GlobBlock], list[GlobBlock]]:
    """Return ``(content_blocks, resource_blocks)`` from a ``docfx.json``."""
    data: dict[str, Any] = json.loads(docfx_json.read_text(encoding="utf-8"))
    build: dict[str, Any] = data.get("build", {})
    content = [_as_block(b) for b in build.get("content", [])]
    resource = [_as_block(b) for b in build.get("resource", [])]
    return content, resource


def _expand(base: Path, pattern: str) -> Iterator[Path]:
    """Expand one DocFX glob under ``base`` (``**`` recursive, ``*`` single).

    ``**`` recurses only below the directory prefix that precedes it, so
    ``assets/**`` stays scoped to ``assets/`` rather than the whole tree, while
    ``**.md`` / ``**/*.html`` recurse from ``base``.
    """
    if "**" in pattern:
        head, _, tail = pattern.partition("**")
        sub = base / head.strip("/") if head.strip("/") else base
        leaf = tail.lstrip("/")
        if not leaf:
            leaf = "*"
        elif leaf.startswith("."):
            leaf = f"*{leaf}"
        yield from sub.rglob(leaf)
    else:
        yield from base.glob(pattern)


def _is_excluded(rel_posix: str, name: str, exclude: tuple[str, ...]) -> bool:
    """Honour DocFX exclude globs: ``**/<leaf>`` matches by file name at any depth (``**/_*.md``);
    any other pattern, such as ``changelog/unreleased/**``, matches the whole relative path."""
    for pattern in exclude:
        if pattern.startswith("**/") and fnmatch.fnmatch(name, pattern.removeprefix("**/")):
            return True
        if fnmatch.fnmatch(rel_posix, pattern):
            return True
    return False


def _join_url(site_url: str, dest: str, rel_posix: str) -> str:
    prefix = f"{dest.strip('/')}/" if dest.strip("/") else ""
    return f"{site_url}{prefix}{rel_posix}"


def _block_urls(
    base_root: Path,
    block: GlobBlock,
    site_url: str,
    *,
    render_markdown: bool,
) -> set[str]:
    """Resolve one block into its published URL set.

    ``render_markdown`` is True for *content* blocks, whose ``*.md`` pages
    DocFX renders to ``.html``, and False for *resource* blocks, whose files
    are copied verbatim — a resource ``*.md`` keeps its literal path. Mapping
    resource markdown to ``.html`` fabricates phantom baseline URLs (#2348).
    """
    base = base_root / block.src if block.src else base_root
    urls: set[str] = set()
    for pattern in block.files:
        for path in _expand(base, pattern):
            if not path.is_file():
                continue
            rel_posix = path.relative_to(base).as_posix()
            if _is_excluded(rel_posix, path.name, block.exclude):
                continue
            if rel_posix.endswith(MD_SUFFIX):
                published = (
                    f"{rel_posix[: -len(MD_SUFFIX)]}{HTML_SUFFIX}"
                    if render_markdown
                    else rel_posix
                )
                urls.add(_join_url(site_url, block.dest, published))
            elif rel_posix.endswith(HTML_SUFFIX):
                urls.add(_join_url(site_url, block.dest, rel_posix))
    return urls


def derive_urls_from_source(
    docs_dir: Path,
    docfx_json: Path,
    site_url: str = SITE_URL,
) -> list[str]:
    """Derive the published-URL set from the ``docfx.json`` globs + source tree.

    Content-block pages are ``*.md`` (excluding ``_*.md``/non-``.md`` like
    ``toc.yml``) mapped to ``.html``. Resource-block files are copied verbatim
    by DocFX — ``*.md`` keeps its literal path and standalone ``*.html`` is
    published as-is. Generated resources (``kitty-specs/**/*.html``, produced
    by ``generate_kitty_specs_docs.py`` at build time) are absent from a static
    tree and therefore not derived here — capture them via ``--site-dir`` after
    a full build if their continuity must be guaranteed.
    """
    content_blocks, resource_blocks = load_blocks(docfx_json)
    urls: set[str] = set()
    for block in content_blocks:
        urls |= _block_urls(docs_dir, block, site_url, render_markdown=True)
    for block in resource_blocks:
        urls |= _block_urls(docs_dir, block, site_url, render_markdown=False)
    return sorted(urls)


def urls_from_site(site_dir: Path, site_url: str = SITE_URL) -> list[str]:
    """Walk an emitted DocFX ``_site`` and normalise every page into its URL.

    Each ``*.html`` under ``site_dir`` becomes ``site_url`` + its path relative
    to ``site_dir`` (no ``_site/`` prefix leakage). The result is sorted and
    de-duplicated for a diff-stable manifest.
    """
    urls = {
        f"{site_url}{path.relative_to(site_dir).as_posix()}"
        for path in site_dir.rglob(f"*{HTML_SUFFIX}")
        if path.is_file()
    }
    return sorted(urls)


def build_manifest(
    urls: list[str],
    method: str,
    site_url: str = SITE_URL,
) -> dict[str, Any]:
    """Assemble the deterministic baseline manifest payload."""
    sorted_urls = sorted(set(urls))
    return {
        "schema_version": SCHEMA_VERSION,
        "site_url": site_url,
        "capture_method": method,
        "url_count": len(sorted_urls),
        "urls": sorted_urls,
    }


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    """Write the manifest as deterministic, diff-stable JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(f"{payload}\n", encoding="utf-8")


def _resolve_urls(args: argparse.Namespace) -> tuple[list[str], str]:
    if args.site_dir is not None:
        return urls_from_site(args.site_dir, args.site_url), METHOD_SITE_WALK
    urls = derive_urls_from_source(args.docs_dir, args.docfx_json, args.site_url)
    return urls, METHOD_DERIVED


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=None,
        help="Walk an emitted DocFX _site tree (canonical capture method).",
    )
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS_DIR)
    parser.add_argument("--docfx-json", type=Path, default=DEFAULT_DOCFX_JSON)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--site-url", default=SITE_URL)
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the URL count without writing the manifest.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    urls, method = _resolve_urls(args)
    manifest = build_manifest(urls, method, args.site_url)
    if not args.print_only:
        write_manifest(args.output, manifest)
    print(
        f"captured {manifest['url_count']} baseline URLs "
        f"(method={method}) -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
