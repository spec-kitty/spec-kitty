"""Check a built doc-kitty site publishes no unpublished route (#6932; ADR 2026-10-31-1 D-8, D-11).

The unpublished set comes from the single authority
(``scripts/docs/_dockitty_contract.py``, :func:`unpublished_routes`): pages in an
excluded folder, in a draft-only working-note folder, or not published. This
command walks a built site (``site/dist``) and reports every surface that still
names one of those routes:

* ``page`` -- a built page (``<route>/index.html``);
* ``link`` -- an ``<a href>`` on a built page that resolves to the route (a hub
  card, the sidebar, a route-form link in prose). An unrewritten source link
  (``x.md``) is not a publication: it is a broken link, the link gates' concern;
* ``sitemap`` -- a ``<loc>`` in ``sitemap-*.xml``;
* ``okf`` -- a file of the OKF export (``okf/``);
* ``search`` -- a pagefind fragment whose ``url`` is the route;
* ``llms`` -- a URL in ``llms.txt`` (when the site builds one);
* ``agent-index`` -- a URL in ``api/index.json`` (when the site builds one).

A surface whose artifact is absent from the built site is a ``missing`` finding, not a pass
(a toolkit layout change must not make a check vacuous).

Each surface is one entry of :data:`SURFACES`, so a later slice adds a surface
with one function and one line. Standard library only, like ``site_contract.py``.

doc-kitty exports no built-artifact check for unpublished routes (its own
``assert-build-artifacts`` is not a bin), so core carries this one until
``spec-kitty/doc-kitty#312`` lands.

Usage (from the repository root, after ``pnpm run build`` in ``site/``)::

    PYTHONPATH=.:src python3 -m scripts.docs.site_built_check site/dist [--docs docs]

Exit 0 when no surface names an unpublished route, 1 with one line per finding,
2 when the built site or the docs tree is missing.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import zlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import unquote, urljoin, urlsplit

# Runnable bare (`python3 scripts/docs/site_built_check.py`): resolve `scripts.*` from the script, not the cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.docs._dockitty_contract import redirect_stub_target, route_of, unpublished_routes  # noqa: E402  (after the path bootstrap above)
from scripts.docs import site_built_check_llms, site_built_check_render  # noqa: E402  (surfaces kept in their own modules)

__all__ = ["SITE_ORIGIN", "SURFACES", "Finding", "check", "main", "normalise_url", "unpublished_routes"]

#: The site's origin (``site`` in ``site/astro.config.mjs``); absolute URLs on it are site routes.
SITE_ORIGIN: Final[str] = "https://docs.spec-kitty.ai"

_SITE_HOST: Final[str] = urlsplit(SITE_ORIGIN).netloc
_INDEX_HTML: Final[str] = "index.html"
_HREF: Final[re.Pattern[str]] = re.compile(r"""<a\b[^>]*?\bhref\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_LOC: Final[re.Pattern[str]] = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_URL: Final[re.Pattern[str]] = re.compile(r"https?://[^\s)\]>\"'`]+")
_PAGEFIND_SIGNATURE: Final[bytes] = b"pagefind_dcd"
_OKF_FOLDER_META: Final[str] = "_index.meta.yaml"


@dataclass(frozen=True, slots=True)
class Finding:
    """One surface naming one unpublished route (or a surface the check could not read)."""

    surface: str
    route: str
    where: str

    def __str__(self) -> str:
        return f"{self.surface}: {self.route} ({self.where})"


def normalise_url(url: str, page_route: str = "/") -> str | None:
    """The site route *url* names, resolved against *page_route*; ``None`` when it is off-site.

    ``/guides/x``, ``../x/``, ``https://docs.spec-kitty.ai/guides/x/#a`` and
    ``/guides/x/index.html`` all name ``/guides/x/``. A path with a file extension
    (``x.md``, ``rss.xml``) keeps it, so it names no page route.
    """
    parts = urlsplit(urljoin(f"{SITE_ORIGIN}{page_route}", url.strip()))
    if parts.scheme not in ("http", "https") or parts.netloc != _SITE_HOST:
        return None
    path = unquote(parts.path) or "/"
    if path.endswith(f"/{_INDEX_HTML}"):
        path = path[: -len(_INDEX_HTML)]
    last = path.rsplit("/", 1)[-1]
    if last and "." not in last:
        path = f"{path}/"
    return path


def _route_of_dist_file(dist: Path, page: Path) -> str:
    parent = page.parent.relative_to(dist).as_posix()
    return "/" if parent == "." else f"/{parent}/"


def _html_pages(dist: Path) -> Iterator[Path]:
    yield from sorted(dist.rglob("*.html"))


def _pages(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    # A redirect stub (#6933) at an unpublished route publishes nothing; the ``link`` surface
    # still reports one whose target is unpublished.
    for route in sorted(routes):
        page = dist / route.strip("/") / _INDEX_HTML
        if page.is_file() and redirect_stub_target(page.read_text(encoding="utf-8", errors="replace")) is None:
            yield Finding("page", route, page.relative_to(dist).as_posix())


def _links(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    for page in _html_pages(dist):
        page_route = _route_of_dist_file(dist, page)
        for match in _HREF.finditer(page.read_text(encoding="utf-8", errors="replace")):
            target = normalise_url(match.group(1) or match.group(2) or "", page_route)
            if target in routes:
                yield Finding("link", target, page.relative_to(dist).as_posix())


def _sitemaps(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    sitemaps = sorted(dist.glob("sitemap-*.xml"))
    if not sitemaps:
        yield Finding("sitemap", "missing", "sitemap-*.xml: not built")
    for sitemap in sitemaps:
        for match in _LOC.finditer(sitemap.read_text(encoding="utf-8")):
            target = normalise_url(match.group(1))
            if target in routes:
                yield Finding("sitemap", target, sitemap.name)


def _okf_route(rel: str) -> str:
    if rel == _OKF_FOLDER_META or rel.endswith(f"/{_OKF_FOLDER_META}"):
        folder = rel[: -len(_OKF_FOLDER_META)].rstrip("/")
        return route_of(f"{folder}/index.md" if folder else "index.md")
    return route_of(rel)


def _okf(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    root = dist / "okf"
    if not root.is_dir():
        yield Finding("okf", "missing", "okf/: not built")
        return
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        route = _okf_route(path.relative_to(root).as_posix())
        if route in routes:
            yield Finding("okf", route, path.relative_to(dist).as_posix())


def _fragment_url(path: Path) -> str:
    raw = gzip.decompress(path.read_bytes())
    payload = raw[len(_PAGEFIND_SIGNATURE) :] if raw.startswith(_PAGEFIND_SIGNATURE) else raw
    return str(json.loads(payload)["url"])


def _search(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    fragments = sorted((dist / "pagefind" / "fragment").glob("*.pf_fragment"))
    if not fragments:
        yield Finding("search", "missing", "pagefind/fragment/: no fragment built")
    for path in fragments:
        where = path.relative_to(dist).as_posix()
        try:
            url = _fragment_url(path)
        except (OSError, EOFError, zlib.error, ValueError, KeyError, TypeError):
            yield Finding("search", "unreadable", where)
            continue
        target = normalise_url(url)
        if target in routes:
            yield Finding("search", target, where)


def _llms(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    path = dist / "llms.txt"
    if not path.is_file():
        return
    for match in _URL.finditer(path.read_text(encoding="utf-8")):
        target = normalise_url(match.group(0))
        if target in routes:
            yield Finding("llms", target, "llms.txt")


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _agent_index(dist: Path, routes: frozenset[str]) -> Iterator[Finding]:
    path = dist / "api" / "index.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        yield Finding("agent-index", "unreadable", "api/index.json")
        return
    for text in _strings(data):
        target = normalise_url(text) if text.startswith(("/", "http")) else None
        if target in routes:
            yield Finding("agent-index", target, "api/index.json")


#: Every surface the check walks: name -> checker. Add a surface with one entry.
SURFACES: Final[dict[str, Callable[[Path, frozenset[str]], Iterator[Finding]]]] = {
    "page": _pages,
    "link": _links,
    "sitemap": _sitemaps,
    "okf": _okf,
    "search": _search,
    "llms": _llms,
    "agent-index": _agent_index,
    site_built_check_llms.SURFACE: site_built_check_llms.surface,
    site_built_check_render.SURFACE: site_built_check_render.surface,
}


def check(dist: Path, routes: frozenset[str]) -> list[Finding]:
    """Every finding of every surface of the built site at *dist* for the unpublished *routes*."""
    return [finding for surface in SURFACES.values() for finding in surface(dist, routes)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("dist", type=Path, help="the built site (site/dist)")
    parser.add_argument("--docs", type=Path, default=Path("docs"), help="the docs tree the site was built from (default: docs)")
    args = parser.parse_args(argv)
    for name, folder in (("built site", args.dist), ("docs tree", args.docs)):
        if not folder.is_dir():
            print(f"site built check: the {name} {folder} does not exist", file=sys.stderr)
            return 2
    routes = unpublished_routes(args.docs)
    findings = check(args.dist, routes)
    for finding in findings:
        print(finding)
    surfaces = ", ".join(SURFACES)
    if findings:
        print(f"site built check: {len(findings)} finding(s): an unpublished route is on a built surface ({surfaces})", file=sys.stderr)
        return 1
    print(f"site built check: {len(routes)} unpublished route(s), none on a built surface ({surfaces})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
