"""The ``render`` surface of the built-site check (#6935; ADR 2026-10-31-1 D-6, D-11).

Every built HTML page must carry the head tags DocFX's ``seo_postprocess.py`` and
``seo_verify.py`` guarantee today, and render GitHub alerts as callouts:

* a non-empty ``<meta name="description">``;
* a ``<link rel="canonical">`` equal to the page's own URL on the site's origin
  (``guides/x/index.html`` is ``/guides/x/``; ``404.html`` is ``/404/``);
* ``og:title``, ``og:description`` and ``og:url`` (non-empty);
* no literal alert marker (``[!NOTE]``, ``[!TIP]``, ``[!IMPORTANT]``, ``[!WARNING]``,
  ``[!CAUTION]``, any letter case) in the page text outside ``code``/``pre`` (an
  unrendered alert; ``githubAlerts`` in ``site/astro.config.mjs`` turns them into asides).

Starlight and doc-kitty emit these tags; this proves them on the built output so the
DocFX scripts can retire at #6943. A redirect stub (#6933,
:func:`~scripts.docs._dockitty_contract.redirect_stub_target`) is not a page and is skipped.
Standard library only (``html.parser``).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Final

from scripts.docs._dockitty_contract import redirect_stub_target

if TYPE_CHECKING:
    from scripts.docs.site_built_check import Finding

__all__ = ["ALERT_MARKERS", "OPEN_GRAPH", "SURFACE", "PageHead", "own_url", "page_defects", "surface"]

#: The surface name the findings carry (the key in ``site_built_check.SURFACES``).
SURFACE: Final[str] = "render"

#: The Open Graph properties every page carries.
OPEN_GRAPH: Final[tuple[str, ...]] = ("og:title", "og:description", "og:url")

#: The GitHub alert markers doc-kitty's ``githubAlerts`` renders.
ALERT_MARKERS: Final[tuple[str, ...]] = ("NOTE", "TIP", "IMPORTANT", "WARNING", "CAUTION")

_INDEX_HTML: Final[str] = "index.html"
_HTML_SUFFIX: Final[str] = ".html"
_CODE_TAGS: Final[frozenset[str]] = frozenset({"code", "pre", "script", "style", "template"})
_ALERT: Final[re.Pattern[str]] = re.compile(r"\[!(" + "|".join(ALERT_MARKERS) + r")\]", re.IGNORECASE)


class PageHead(HTMLParser):
    """The head tags of one page and its text outside code."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.canonical: str | None = None
        self.text: list[str] = []
        self._code_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if tag == "meta":
            key = values.get("name") or values.get("property")
            if key and key not in self.meta:
                self.meta[key] = values.get("content", "")
        elif tag == "link" and "canonical" in values.get("rel", "").split() and self.canonical is None:
            self.canonical = values.get("href", "")
        elif tag in _CODE_TAGS:
            self._code_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _CODE_TAGS and self._code_depth:
            self._code_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._code_depth:
            self.text.append(data)


def own_url(rel: str, origin: str) -> str:
    """The URL of the built page at *rel* (relative to ``dist``) on *origin*."""
    if rel == _INDEX_HTML:
        return f"{origin}/"
    if rel.endswith(f"/{_INDEX_HTML}"):
        return f"{origin}/{rel[: -len(_INDEX_HTML)]}"
    return f"{origin}/{rel[: -len(_HTML_SUFFIX)]}/"


def page_defects(html: str, url: str) -> Iterator[str]:
    """Every render defect of the page *html* whose own URL is *url*."""
    head = PageHead()
    head.feed(html)
    head.close()
    if not head.meta.get("description", "").strip():
        yield "no meta description"
    if head.canonical is None:
        yield "no canonical link"
    elif head.canonical != url:
        yield f"canonical {head.canonical} is not the page's own URL"
    for prop in OPEN_GRAPH:
        if not head.meta.get(prop, "").strip():
            yield f"no {prop}"
    for match in _ALERT.finditer("".join(head.text)):
        yield f"literal alert marker [!{match.group(1).upper()}]"


def surface(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    """The registered surface: every built HTML page's render defects.

    *routes* (the unpublished routes) are the other surfaces' concern, not this one's.
    """
    from scripts.docs.site_built_check import SITE_ORIGIN, Finding  # noqa: PLC0415  (site_built_check registers this surface; a top-level import is a cycle)

    del routes
    for page in sorted(dist.rglob(f"*{_HTML_SUFFIX}")):
        rel = page.relative_to(dist).as_posix()
        html = page.read_text(encoding="utf-8", errors="replace")
        if redirect_stub_target(html) is not None:
            continue  # a redirect stub (#6933) is not a page: no description, its canonical is its target
        url = own_url(rel, SITE_ORIGIN)
        for defect in page_defects(html, url):
            yield Finding(SURFACE, url.removeprefix(SITE_ORIGIN), f"{rel}: {defect}")
