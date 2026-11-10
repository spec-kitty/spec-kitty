"""Acceptance tests for the built-site publication check (#6932; ADR 2026-10-31-1 D-8, D-11).

``scripts/docs/site_built_check.py`` walks a built doc-kitty site and reports every
unpublished route (``_dockitty_contract.unpublished_routes``) that a surface still
names: a built page, a link, the sitemap, the OKF export, the search index,
``llms.txt`` and the agent index. These tests build a small ``docs/`` tree and the
``dist/`` a clean build of it would give, then plant one unpublished route on one
surface at a time (a mutant per surface): the clean tree passes and every mutant
fails, naming the route and the surface.
"""

from __future__ import annotations

import gzip
import importlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

from scripts.docs._dockitty_contract import LLMS_STANCE

pytestmark = [pytest.mark.unit, pytest.mark.fast]

SITE = "https://docs.spec-kitty.ai"


def _check() -> ModuleType:
    return importlib.import_module("scripts.docs.site_built_check")


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _page(status: str) -> str:
    return f"---\ntitle: t\ndoc_status: {status}\n---\n\n# Body\n"


def _html(route: str, body: str) -> str:
    """A built page with the head tags the render surface requires, so only *body* is under test."""
    url = f"{SITE}{route}"
    head = (
        f'<meta name="description" content="d"/><link rel="canonical" href="{url}"/>'
        f'<meta property="og:title" content="t"/><meta property="og:description" content="d"/><meta property="og:url" content="{url}"/>'
    )
    return f"<html><head>{head}</head><body>{body}</body></html>"


def _fragment(url: str) -> bytes:
    return gzip.compress(b"pagefind_dcd" + json.dumps({"url": url, "content": "words", "meta": {"title": "t"}}).encode())


@pytest.fixture
def site(tmp_path: Path) -> tuple[Path, Path]:
    """A docs tree (one published page per kind of neighbour) and the dist a clean build gives."""
    docs = tmp_path / "docs"
    _write(docs, "index.md", _page("active"))
    _write(docs, "guides/live.md", _page("active"))
    _write(docs, "guides/wip.md", _page("draft"))
    _write(docs, "archive/guides/gone.md", _page("active"))
    _write(docs, "plans/engineering-notes/note.md", _page("deprecated"))

    dist = tmp_path / "dist"
    _write(dist, "index.html", _html("/", '<a href="/guides/live/">Live</a> <a href="https://github.com/x/y">GH</a>'))
    _write(dist, "guides/live/index.html", _html("/guides/live/", '<a href="../../">Home</a> <a href="./#top">Top</a> <a href="wip.md">raw source link</a>'))
    _write(dist, "404.html", _html("/404/", "<p>Not found</p>"))
    _write(dist, "sitemap-index.xml", f"<sitemapindex><sitemap><loc>{SITE}/sitemap-0.xml</loc></sitemap></sitemapindex>")
    _write(dist, "sitemap-0.xml", f"<urlset><url><loc>{SITE}/</loc></url><url><loc>{SITE}/guides/live/</loc></url></urlset>")
    _write(dist, "okf/index.md", "# Home\n")
    _write(dist, "okf/guides/live.md", "# Live\n")
    _write(dist, "okf/guides/_index.meta.yaml", "title: Guides\n")
    (dist / "pagefind" / "fragment").mkdir(parents=True)
    (dist / "pagefind" / "fragment" / "en_live.pf_fragment").write_bytes(_fragment("/guides/live/"))
    _write(dist, "pagefind/pagefind-entry.json", '{"version":"1.6.0"}')
    _write(dist, "llms.txt", f"# Spec Kitty\n\n{LLMS_STANCE}\n- [Live]({SITE}/guides/live/): a page\n")
    _write(dist, "api/index.json", json.dumps({"pages": [{"url": f"{SITE}/guides/live/", "title": "Live"}]}))
    return docs, dist


def _findings(docs: Path, dist: Path) -> list[str]:
    module = _check()
    return [str(finding) for finding in module.check(dist, module.unpublished_routes(docs))]


def test_a_clean_build_has_no_finding(site: tuple[Path, Path]) -> None:
    docs, dist = site

    assert _findings(docs, dist) == []


def _plant_page(dist: Path) -> None:
    _write(dist, "guides/wip/index.html", "<h1>WIP</h1>")


def _plant_link(dist: Path) -> None:
    _write(dist, "guides/index.html", '<nav><a class="card" href="/guides/wip/">WIP</a></nav>')


def _plant_relative_link(dist: Path) -> None:
    _write(dist, "guides/live/index.html", '<a href="../wip/">WIP</a>')


def _plant_absolute_link(dist: Path) -> None:
    _write(dist, "index.html", f'<a href="{SITE}/guides/wip/#intro">WIP</a>')


def _plant_sitemap(dist: Path) -> None:
    _write(dist, "sitemap-0.xml", f"<urlset><url><loc>{SITE}/</loc></url><url><loc>{SITE}/guides/wip/</loc></url></urlset>")


def _plant_okf(dist: Path) -> None:
    _write(dist, "okf/guides/wip.md", "# WIP\n")


def _plant_search(dist: Path) -> None:
    (dist / "pagefind" / "fragment" / "en_wip.pf_fragment").write_bytes(_fragment("/guides/wip/"))


def _plant_llms(dist: Path) -> None:
    _write(dist, "llms.txt", f"# Spec Kitty\n\n- [WIP]({SITE}/guides/wip/): a draft\n")


def _plant_agent_index(dist: Path) -> None:
    _write(dist, "api/index.json", json.dumps({"pages": [{"url": f"{SITE}/guides/wip/"}]}))


def _plant_excluded_folder_page(dist: Path) -> None:
    _write(dist, "archive/guides/gone/index.html", "<h1>Gone</h1>")


def _plant_draft_folder_page(dist: Path) -> None:
    _write(dist, "sitemap-0.xml", f"<urlset><url><loc>{SITE}/plans/engineering-notes/note/</loc></url></urlset>")


@pytest.mark.parametrize(
    ("plant", "surface", "route"),
    [
        (_plant_page, "page", "/guides/wip/"),
        (_plant_link, "link", "/guides/wip/"),
        (_plant_relative_link, "link", "/guides/wip/"),
        (_plant_absolute_link, "link", "/guides/wip/"),
        (_plant_sitemap, "sitemap", "/guides/wip/"),
        (_plant_okf, "okf", "/guides/wip/"),
        (_plant_search, "search", "/guides/wip/"),
        (_plant_llms, "llms", "/guides/wip/"),
        (_plant_agent_index, "agent-index", "/guides/wip/"),
        (_plant_excluded_folder_page, "page", "/archive/guides/gone/"),
        (_plant_draft_folder_page, "sitemap", "/plans/engineering-notes/note/"),
    ],
)
def test_every_planted_unpublished_route_is_reported(site: tuple[Path, Path], plant: Callable[[Path], None], surface: str, route: str) -> None:
    docs, dist = site
    plant(dist)

    findings = _findings(docs, dist)

    own = [finding for finding in findings if finding.startswith(f"{surface}: ")]
    assert own, f"a {surface} naming {route} must fail the check: {findings}"
    assert all(finding.startswith(f"{surface}: {route} ") for finding in own), findings


def test_the_command_exits_one_with_a_line_per_finding(site: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    docs, dist = site
    _plant_page(dist)
    _plant_sitemap(dist)

    code = _check().main([str(dist), "--docs", str(docs)])

    out = capsys.readouterr()
    assert code == 1
    reported = [line for line in out.out.splitlines() if line.startswith(("page:", "sitemap:"))]
    assert len(reported) == 2, out.out


def test_the_command_exits_zero_on_a_clean_build(site: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    docs, dist = site

    assert _check().main([str(dist), "--docs", str(docs)]) == 0
    assert "unpublished" in capsys.readouterr().out


def test_a_missing_dist_is_refused(site: tuple[Path, Path]) -> None:
    docs, dist = site

    assert _check().main([str(dist / "absent"), "--docs", str(docs)]) == 2


@pytest.mark.parametrize(
    ("surface", "remove"),
    [
        pytest.param("sitemap", "sitemap-*.xml", id="sitemap"),
        pytest.param("okf", "okf", id="okf"),
        pytest.param("search", "pagefind/fragment", id="search"),
    ],
)
def test_a_surface_whose_artifact_is_not_built_is_a_finding(site: tuple[Path, Path], surface: str, remove: str) -> None:
    """An absent ``okf/``, pagefind fragment or sitemap must not make its check pass vacuously."""
    docs, dist = site
    for target in dist.glob(remove):
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    findings = _findings(docs, dist)

    assert [finding for finding in findings if finding.startswith(f"{surface}: missing ")] != [], findings


def test_a_corrupt_search_fragment_is_reported_not_skipped(site: tuple[Path, Path]) -> None:
    """A fragment the check cannot read could hide an unpublished route, so it fails the check."""
    docs, dist = site
    (dist / "pagefind" / "fragment" / "en_bad.pf_fragment").write_bytes(b"not gzip")

    findings = _findings(docs, dist)

    assert len(findings) == 1
    assert findings[0].startswith("search: unreadable ")


# --- Redirect stubs (#6933): a stub is a redirect, not a publication ------------------


def _stub(target: str, source: str) -> str:
    return (
        f"<!doctype html><title>Redirecting to: {target}</title>"
        f'<meta http-equiv="refresh" content="0;url={target}">'
        '<meta name="robots" content="noindex">'
        f'<link rel="canonical" href="{SITE}{target}">'
        f'<body>\t<a href="{target}">Redirecting from <code>{source}</code> to <code>{target}</code></a></body>'
    )


def test_a_redirect_stub_at_an_unpublished_route_is_not_a_published_page(site: tuple[Path, Path]) -> None:
    docs, dist = site
    _write(dist, "guides/wip/index.html", _stub("/guides/live/", "/guides/wip/index.html"))

    assert _findings(docs, dist) == []


def test_a_redirect_stub_pointing_at_an_unpublished_route_is_still_reported(site: tuple[Path, Path]) -> None:
    docs, dist = site
    _write(dist, "guides/old.html", _stub("/guides/wip/", "/guides/old.html"))

    assert _findings(docs, dist) == ["link: /guides/wip/ (guides/old.html)"]
