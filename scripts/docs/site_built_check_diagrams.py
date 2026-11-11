"""The ``diagrams`` surface of the built-site check (#6936; ADR 2026-10-31-1 D-11).

The site renders every Mermaid and PlantUML diagram at build time to a static SVG
(``diagrams: true``, ``DK_DIAGRAM_BUILD_RENDER=build``). This surface proves it on the
built output, page by page:

* every page the site publishes (``_dockitty_contract.unpublished_routes`` is the one
  authority) holds as many rendered figures as its source holds diagram fences: a
  ```` ```mermaid ```` or ```` ```plantuml ```` fence, read as doc-kitty reads it (the
  first word of the info string, case-sensitive, ``lib/remark/diagram-meta.ts:51``,
  ``lib/remark/plantuml-meta.ts:77``). A rendered figure is doc-kitty's
  ``<figure class="dk-diagram">`` holding an ``<svg>`` (``lib/rehype/diagram-figure.ts:191-202``
  for Mermaid, ``:282-299`` for PlantUML);
* no raw diagram code block remains (a ``<pre data-language="mermaid">`` or a
  ``language-plantuml`` class: the fence was shipped as code);
* no client-rendered ``<pre class="mermaid">`` remains (doc-kitty's client mode,
  ``lib/integrations/diagrams.ts:70-81``, renders in the browser, not at build time);
* no diagram error block remains (``astro-plantuml``'s ``<div class="plantuml-error">``,
  ``astro-plantuml@1.0.0 dist/render.js:122-126``; doc-kitty throws on it,
  ``diagram-figure.ts:352-360``, and this catches a toolkit that stops doing so);
* no built page names a ``plantuml.com`` URL (the output half of doc-kitty's
  no-plantuml.com guard; the same URL-position pattern as its
  ``scripts/plantuml-guard.mjs:12``, so prose naming the host does not match).

A published page with diagram fences and no built page is a finding, not a pass.
Standard library only (``html.parser``), like ``site_built_check.py``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING, Final

from scripts.docs._dockitty_contract import body_of, redirect_stub_target, route_of, unpublished_routes
from scripts.docs.site_built_check_render import own_url

if TYPE_CHECKING:
    from scripts.docs.site_built_check import Finding

__all__ = ["DIAGRAM_LANGUAGES", "SURFACE", "PageDiagrams", "expected_figures", "findings", "page_defects", "source_blocks", "surface"]

#: The surface name the findings carry (the key in ``site_built_check.SOURCE_SURFACES``).
SURFACE: Final[str] = "diagrams"

#: The fence languages doc-kitty renders as diagrams.
DIAGRAM_LANGUAGES: Final[frozenset[str]] = frozenset({"mermaid", "plantuml"})

_MD_SUFFIX: Final[str] = ".md"
_HTML_SUFFIX: Final[str] = ".html"
_INDEX_HTML: Final[str] = "index.html"
_FIGURE_CLASS: Final[str] = "dk-diagram"
_ERROR_CLASS: Final[str] = "plantuml-error"
_CLIENT_CLASS: Final[str] = "mermaid"
_LANGUAGE_CLASS: Final[str] = "language-"
_FENCE: Final[re.Pattern[str]] = re.compile(r"^[ \t]*(?P<fence>`{3,}|~{3,})(?P<info>[^\n]*)$")
_PLANTUML_COM: Final[re.Pattern[str]] = re.compile(
    r"(?:(?:https?:)?//[a-z0-9.-]*plantuml\.com|[^\s\"'<>()]*plantuml\.com/plantuml)[^\s\"'<>()]*",
    re.IGNORECASE,
)


def _opening(line: str) -> tuple[str, str] | None:
    """The fence and the language of an opening fence line, or ``None``."""
    match = _FENCE.match(line)
    if match is None:
        return None
    fence, info = match["fence"], match["info"].strip()
    if fence[0] == "`" and "`" in info:
        return None
    return fence, info.split()[0] if info else ""


def _closes(line: str, fence: str) -> bool:
    match = _FENCE.match(line)
    return match is not None and match["fence"][0] == fence[0] and len(match["fence"]) >= len(fence) and not match["info"].strip()


def source_blocks(markdown: str) -> int:
    """The number of top-level diagram fences in *markdown* (a fence inside another fence is content)."""
    count = 0
    open_fence: str | None = None
    for line in markdown.splitlines():
        if open_fence is not None:
            if _closes(line, open_fence):
                open_fence = None
            continue
        opening = _opening(line)
        if opening is not None:
            open_fence = opening[0]
            count += opening[1] in DIAGRAM_LANGUAGES
    return count


def expected_figures(docs: Path) -> dict[str, int]:
    """Route -> diagram fence count, for every published page under *docs* that has one."""
    unpublished = unpublished_routes(docs)
    expected: dict[str, int] = {}
    for path in sorted(docs.rglob(f"*{_MD_SUFFIX}")):
        route = route_of(path.relative_to(docs).as_posix())
        if route in unpublished:
            continue
        count = source_blocks(body_of(path.read_text(encoding="utf-8")))
        if count:
            expected[route] = expected.get(route, 0) + count
    return expected


@dataclass
class _Block:
    """An open ``<figure>`` or ``<pre>`` the parser is inside."""

    marked: bool
    done: bool = False


class PageDiagrams(HTMLParser):
    """The diagram markup of one built page: its rendered figures and its defects, in document order."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.figures = 0
        self.defects: list[str] = []
        self._figures: list[_Block] = []
        self._pres: list[_Block] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        classes = values.get("class", "").split()
        if _ERROR_CLASS in classes:
            self.defects.append("diagram error block")
        if tag == "figure":
            self._figures.append(_Block(_FIGURE_CLASS in classes))
        elif tag == "svg":
            self._svg()
        elif tag == "pre":
            self._pre(values.get("data-language", ""), classes)
        elif tag == "code":
            self._code(classes)

    def handle_endtag(self, tag: str) -> None:
        stack = {"figure": self._figures, "pre": self._pres}.get(tag)
        if stack:
            stack.pop()

    def _svg(self) -> None:
        figure = self._figures[-1] if self._figures else None
        if figure is not None and figure.marked and not figure.done:
            figure.done = True
            self.figures += 1

    def _pre(self, data_language: str, classes: list[str]) -> None:
        language = data_language or _language_of(classes)
        raw = language in DIAGRAM_LANGUAGES
        if raw:
            self.defects.append(f"raw {language} code block")
        if _CLIENT_CLASS in classes:
            self.defects.append("client-rendered mermaid block")
        self._pres.append(_Block(raw or _CLIENT_CLASS in classes))

    def _code(self, classes: list[str]) -> None:
        pre = self._pres[-1] if self._pres else None
        language = _language_of(classes)
        if language in DIAGRAM_LANGUAGES and not (pre is not None and pre.marked):
            self.defects.append(f"raw {language} code block")


def _language_of(classes: list[str]) -> str:
    return next((name[len(_LANGUAGE_CLASS) :] for name in classes if name.startswith(_LANGUAGE_CLASS)), "")


def page_defects(html: str, expected: int) -> Iterator[str]:
    """Every diagram defect of the built page *html* whose source holds *expected* diagram fences."""
    page = PageDiagrams()
    page.feed(html)
    page.close()
    yield from page.defects
    for url in dict.fromkeys(match.group(0) for match in _PLANTUML_COM.finditer(html)):
        yield f"plantuml.com URL {url}"
    if page.figures != expected:
        yield f"{expected} diagram block(s) in the source, {page.figures} rendered figure(s)"


def _built_rel(route: str) -> str:
    clean = route.strip("/")
    return f"{clean}/{_INDEX_HTML}" if clean else _INDEX_HTML


def findings(dist: Path, *, docs: Path) -> Iterator[Finding]:
    """Every ``diagrams`` finding of the built site at *dist* built from the docs tree *docs*."""
    from scripts.docs.site_built_check import Finding  # noqa: PLC0415  (site_built_check registers this surface; a top-level import is a cycle)

    expected = expected_figures(docs)
    built: set[str] = set()
    for page in sorted(dist.rglob(f"*{_HTML_SUFFIX}")):
        html = page.read_text(encoding="utf-8", errors="replace")
        if redirect_stub_target(html) is not None:
            continue  # a legacy ``.html`` stub beside the page shares its route; it is a redirect, not the page (#6933)
        rel = page.relative_to(dist).as_posix()
        route = own_url(rel, "")
        built.add(route)
        for defect in page_defects(html, expected.get(route, 0)):
            yield Finding(SURFACE, route, f"{rel}: {defect}")
    for route, count in sorted(expected.items()):
        if route not in built:
            yield Finding(SURFACE, route, f"{_built_rel(route)}: {count} diagram block(s) in the source, no built page")


def surface(dist: Path, docs: Path) -> Iterator[Finding]:
    """The registered source surface: the built site at *dist* against the docs tree *docs*."""
    yield from findings(dist, docs=docs)
