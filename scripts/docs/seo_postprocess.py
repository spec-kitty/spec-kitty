"""Post-process generated DocFX output with static SEO metadata."""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from kernel.clock import now_utc
from pathlib import Path
from urllib.parse import quote


DEFAULT_BASE_URL = "https://docs.spec-kitty.ai/"
DEFAULT_IMAGE = "assets/images/logo_small.webp"

#: Bare site title used when a page carries no usable ``<title>``. A rendered
#: page whose title equals this is indistinguishable from every other page and
#: is a violation of NFR-001 — ``seo_verify`` imports this constant rather than
#: retyping the string, so there is one authority for "the default title".
DEFAULT_TITLE = "Spec Kitty Documentation"

#: Boilerplate description used as a last-resort backstop when a page supplies
#: none. It is deliberately **detectable** (C-B3): both the source gate and the
#: built-output verifier treat a page carrying this exact string as equivalent
#: to a page carrying no description at all. Making the backstop look like an
#: authored description would let it mask the very defect it exists to reveal.
FALLBACK_DESCRIPTION = (
    "Spec Kitty documentation for CLI workflows, governed missions, AI harnesses, and 3.2 upgrades."
)

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
DESCRIPTION_RE = re.compile(
    r'<meta\s+name="description"\s+content="(.*?)"\s*/?>',
    re.IGNORECASE | re.DOTALL,
)
#: Matches ``</head>`` **together with the whitespace in front of it**. Consuming
#: that whitespace is what makes injection a fixed point: ``SEO_BLOCK_RE`` strips
#: the block *and* its leading whitespace, so an insertion that added its own
#: indentation on top of the page's would drift by a couple of characters on the
#: second pass. Normalizing here means strip-then-reinsert is byte-stable (C-B2).
HEAD_CLOSE_RE = re.compile(r"\s*</head>", re.IGNORECASE)
SEO_BLOCK_RE = re.compile(
    r"\n?\s*<!-- spec-kitty-seo:start -->.*?<!-- spec-kitty-seo:end -->\n?",
    re.IGNORECASE | re.DOTALL,
)
ROBOTS_RE = re.compile(r'<meta\s+name="robots"\s+content="([^"]+)"', re.IGNORECASE)


@dataclass(frozen=True)
class Page:
    path: Path
    relative_path: str
    title: str
    description: str
    url: str


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/"


def canonical_url(base_url: str, relative_path: str) -> str:
    base = normalize_base_url(base_url)
    rel = relative_path.replace("\\", "/")
    if rel == "index.html":
        return base
    if rel.endswith("/index.html"):
        rel = rel[: -len("index.html")]
    return base + quote(rel, safe="/.-_~")


def should_index(relative_path: str, markup: str) -> bool:
    rel = relative_path.replace("\\", "/")
    if rel.endswith("/toc.html") or rel == "toc.html":
        return False
    if rel.startswith("assets/"):
        return False
    # kitty-specs are dogfooded mission artifacts (spec/plan/tasks/... per
    # mission) surfaced in the site for provenance, not curated public pages:
    # they legitimately share a per-mission description and carry glossary-linked
    # titles. They are internal, so they stay out of search indexing — and, as
    # the single indexability authority (I-08), out of the SEO rules (og:title,
    # duplicate-description) and the sitemap too.
    if rel.startswith("kitty-specs/") or "/kitty-specs/" in rel:
        return False
    if 'http-equiv="refresh"' in markup.lower():
        return False
    robots = ROBOTS_RE.search(markup)
    return not (robots and "noindex" in robots.group(1).lower())


def _normalize(value: str) -> str:
    """Collapse whitespace and resolve entities in an extracted attribute."""
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def find_title(markup: str) -> str | None:
    """Return the page's own ``<title>``, or ``None`` when it has none.

    Unlike :func:`extract_title` this never substitutes :data:`DEFAULT_TITLE`,
    so callers that must distinguish "absent" from "defaulted" (the built-output
    verifier's NFR-001 rule) can do so without a second parser.
    """
    match = TITLE_RE.search(markup)
    if not match:
        return None
    title = _normalize(match.group(1))
    return title.replace(f" | {DEFAULT_TITLE}", "").strip() or None


def find_description(markup: str) -> str | None:
    """Return the page's own ``<meta name="description">``, or ``None``.

    The optional-returning counterpart to :func:`extract_description`: it is the
    single authority both this module (to decide whether the backstop tag is
    needed, C-B1) and ``seo_verify`` (to apply V-06) read a description with.
    """
    match = DESCRIPTION_RE.search(markup)
    if not match:
        return None
    return _normalize(match.group(1)) or None


def extract_title(markup: str) -> str:
    return find_title(markup) or DEFAULT_TITLE


def extract_description(markup: str) -> str:
    return find_description(markup) or FALLBACK_DESCRIPTION


def breadcrumb_items(page: Page, base_url: str) -> list[dict[str, object]]:
    parts = page.relative_path.replace("\\", "/").split("/")
    crumbs: list[dict[str, object]] = [
        {"@type": "ListItem", "position": 1, "name": "Spec Kitty Docs", "item": normalize_base_url(base_url)}
    ]
    running: list[str] = []
    for part in parts[:-1]:
        running.append(part)
        name = part.replace("-", " ").replace("_", " ").title()
        crumbs.append(
            {
                "@type": "ListItem",
                "position": len(crumbs) + 1,
                "name": name,
                "item": canonical_url(base_url, "/".join(running + ["index.html"])),
            }
        )
    if page.relative_path != "index.html":
        crumbs.append(
            {"@type": "ListItem", "position": len(crumbs) + 1, "name": page.title, "item": page.url}
        )
    return crumbs


def kitty_specs_json_ld(page: Page, base_url: str) -> list[dict[str, object]]:
    rel = page.relative_path.replace("\\", "/")
    if not rel.startswith("kitty-specs/"):
        return []

    docs_url = normalize_base_url(base_url)
    if rel == "kitty-specs/index.html":
        return [
            {
                "@context": "https://schema.org",
                "@type": "CollectionPage",
                "name": "Spec Kitty Mission Runs",
                "description": page.description,
                "url": page.url,
                "isPartOf": {"@type": "WebSite", "name": DEFAULT_TITLE, "url": docs_url},
                "about": [
                    "Spec Kitty mission runs",
                    "spec-driven development",
                    "AI coding agents",
                    "work packages",
                ],
            },
            {
                "@context": "https://schema.org",
                "@type": "ItemList",
                "name": "Spec Kitty mission run index",
                "url": page.url,
                "itemListOrder": "https://schema.org/ItemListOrderDescending",
            },
        ]
    if rel == "kitty-specs/glossary.html":
        return [
            {
                "@context": "https://schema.org",
                "@type": "DefinedTermSet",
                "name": "Spec Kitty Glossary",
                "description": page.description,
                "url": page.url,
                "inLanguage": "en",
                "isPartOf": {"@type": "WebSite", "name": DEFAULT_TITLE, "url": docs_url},
                "about": [
                    "Spec Kitty terminology",
                    "spec-driven development",
                    "AI coding agents",
                    "mission governance",
                    "work packages",
                ],
            }
        ]

    parts = rel.split("/")
    mission_slug = parts[1] if len(parts) > 1 else ""
    artifact = parts[-1].removesuffix(".html")
    if artifact == "index":
        artifact = "overview"
    artifact_name = artifact.replace("-", " ").title()
    return [
        {
            "@context": "https://schema.org",
            "@type": "TechArticle",
            "headline": page.title,
            "description": page.description,
            "url": page.url,
            "inLanguage": "en",
            "isPartOf": {"@type": "WebSite", "name": DEFAULT_TITLE, "url": docs_url},
            "about": [
                "Spec Kitty mission run",
                mission_slug,
                artifact_name,
                "spec-driven development",
                "AI coding agents",
            ],
            "mainEntity": {
                "@type": "CreativeWork",
                "name": page.title,
                "description": page.description,
                "identifier": mission_slug,
                "url": page.url,
                "genre": "Software specification artifact",
                "isPartOf": {
                    "@type": "CreativeWorkSeries",
                    "name": "Spec Kitty mission run artifacts",
                    "url": canonical_url(base_url, f"kitty-specs/{mission_slug}/index.html"),
                },
            },
            "publisher": {
                "@type": "Organization",
                "name": "Spec Kitty",
                "url": "https://github.com/spec-kitty/spec-kitty",
            },
        }
    ]


def seo_block(page: Page, base_url: str, image_path: str, *, emit_description: bool = False) -> str:
    """Render the injected SEO block for ``page``.

    ``emit_description`` adds a ``<meta name="description">`` tag to the block.
    It is a **backstop** (C-B1): callers pass ``True`` only when the page does
    not already carry a description tag of its own, so DocFX's frontmatter-derived
    output stays the single canonical authority wherever it exists. The tag lives
    *inside* the delimited block, so the existing strip-then-reinsert cycle keeps
    the pass idempotent (C-B2).
    """
    image_url = normalize_base_url(base_url) + quote(image_path.lstrip("/"), safe="/.-_~")
    json_ld = [
        {
            "@context": "https://schema.org",
            "@type": "TechArticle" if page.relative_path != "index.html" else "WebPage",
            "headline": page.title,
            "description": page.description,
            "url": page.url,
            "inLanguage": "en",
            "isPartOf": {
                "@type": "WebSite",
                "name": DEFAULT_TITLE,
                "url": normalize_base_url(base_url),
            },
            "publisher": {
                "@type": "Organization",
                "name": "Spec Kitty",
                "url": "https://github.com/spec-kitty/spec-kitty",
            },
            "about": ["Spec Kitty", "AI coding agents", "spec-driven development", "CLI documentation"],
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": breadcrumb_items(page, base_url),
        },
    ]
    json_ld.extend(kitty_specs_json_ld(page, base_url))
    escaped_title = html.escape(page.title, quote=True)
    escaped_desc = html.escape(page.description, quote=True)
    escaped_url = html.escape(page.url, quote=True)
    escaped_image = html.escape(image_url, quote=True)
    lines = ["", "      <!-- spec-kitty-seo:start -->"]
    if emit_description:
        lines.append(f'      <meta name="description" content="{escaped_desc}">')
    lines += [
        f'      <link rel="canonical" href="{escaped_url}">',
        f'      <meta property="og:site_name" content="{html.escape(DEFAULT_TITLE, quote=True)}">',
        '      <meta property="og:type" content="article">',
        f'      <meta property="og:title" content="{escaped_title}">',
        f'      <meta property="og:description" content="{escaped_desc}">',
        f'      <meta property="og:url" content="{escaped_url}">',
        f'      <meta property="og:image" content="{escaped_image}">',
        '      <meta name="twitter:card" content="summary">',
        f'      <meta name="twitter:title" content="{escaped_title}">',
        f'      <meta name="twitter:description" content="{escaped_desc}">',
        f'      <meta name="twitter:image" content="{escaped_image}">',
        "      <script type=\"application/ld+json\">"
        f"{json.dumps(json_ld, ensure_ascii=False, separators=(',', ':'))}</script>",
        "      <!-- spec-kitty-seo:end -->",
    ]
    return "\n".join(lines) + "\n"


def noindex_block() -> str:
    return """
      <!-- spec-kitty-seo:start -->
      <meta name="robots" content="noindex, follow">
      <!-- spec-kitty-seo:end -->
"""


def _replace_head_close(markup: str, replacement: str) -> str:
    """Insert ``replacement`` in place of the first ``</head>``.

    Substitutes via a callable so ``re.sub`` treats ``replacement`` literally:
    the block embeds JSON-LD and author-written descriptions, and backslash
    sequences (``\\1``, ``\\g``) in a replacement *string* would be interpreted
    as group references and silently corrupt the output.
    """
    return HEAD_CLOSE_RE.sub(lambda _match: replacement, markup, count=1)


def process_html(site_dir: Path, base_url: str, image_path: str) -> list[Page]:
    pages: list[Page] = []
    for path in sorted(site_dir.rglob("*.html")):
        relative_path = path.relative_to(site_dir).as_posix()
        markup = path.read_text(encoding="utf-8")
        markup = SEO_BLOCK_RE.sub("", markup)
        if should_index(relative_path, markup):
            # Read *after* the previous block was stripped, so a description this
            # module injected on an earlier pass is not mistaken for the page's
            # own — that is what keeps repeated runs byte-identical (C-B2).
            page = Page(
                path=path,
                relative_path=relative_path,
                title=extract_title(markup),
                description=extract_description(markup),
                url=canonical_url(base_url, relative_path),
            )
            block = seo_block(
                page,
                base_url,
                image_path,
                emit_description=find_description(markup) is None,
            )
            pages.append(page)
        else:
            block = noindex_block()
        markup = _replace_head_close(markup, block + "  </head>")
        path.write_text(markup, encoding="utf-8")
    return pages


def write_sitemap(site_dir: Path, pages: list[Page]) -> None:
    # FR-011 (kernel-clock-single-door): the door has no date-only producer
    # (plan Sec 1.1). Prior site was local-time `date.today()` -- a naive
    # local-time read masquerading as a date. Routed onto the door's aware
    # `now_utc().date()`, which flips local -> UTC date: BYTE-CHANGING when
    # the build host's local date differs from the UTC date at build time
    # (e.g. near midnight). See research/migration-notes.md (WP14) for the
    # adjudication record and pinning test.
    today = now_utc().date().isoformat()
    urls = "\n".join(
        f"  <url><loc>{html.escape(page.url)}</loc><lastmod>{today}</lastmod></url>" for page in pages
    )
    site_dir.joinpath("sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n",
        encoding="utf-8",
    )


def write_robots(site_dir: Path, base_url: str) -> None:
    site_dir.joinpath("robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /toc.html\n"
        "Disallow: /*/toc.html\n"
        f"Sitemap: {normalize_base_url(base_url)}sitemap.xml\n",
        encoding="utf-8",
    )


def write_cname(site_dir: Path, base_url: str) -> None:
    host = normalize_base_url(base_url).removeprefix("https://").removeprefix("http://").strip("/")
    if host:
        site_dir.joinpath("CNAME").write_text(host + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=Path("docs/_site"))
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    args = parser.parse_args(argv)

    site_dir = args.site_dir.resolve()
    if not site_dir.is_dir():
        raise SystemExit(f"Site directory not found: {site_dir}")

    pages = process_html(site_dir, args.base_url, args.image)
    write_sitemap(site_dir, pages)
    write_robots(site_dir, args.base_url)
    write_cname(site_dir, args.base_url)
    site_dir.joinpath(".nojekyll").write_text("", encoding="utf-8")
    print(f"SEO postprocess complete: {len(pages)} indexed HTML pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
