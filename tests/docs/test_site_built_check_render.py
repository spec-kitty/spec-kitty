"""Acceptance tests for the built-site render check (#6935; ADR 2026-10-31-1 D-6, D-11).

``scripts/docs/site_built_check_render.py`` is a surface of the built-site check
(``site_built_check.py``): every built HTML page carries a non-empty meta
description, a canonical link equal to its own URL on https://docs.spec-kitty.ai,
and ``og:title``, ``og:description`` and ``og:url`` (the tags DocFX's
``seo_postprocess.py`` / ``seo_verify.py`` guarantee today), and no page shows a
literal GitHub alert marker (``[!NOTE]`` ...) outside code. A clean fixture build
passes; each mutant fails, naming the page and the defect.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

SITE = "https://docs.spec-kitty.ai"


def _render() -> ModuleType:
    return importlib.import_module("scripts.docs.site_built_check_render")


def _built_check() -> ModuleType:
    return importlib.import_module("scripts.docs.site_built_check")


def _page(url: str, body: str = "<p>Body</p>", *, omit: str = "", canonical: str | None = None, description: str = "A page.") -> str:
    tags = {
        "description": f'<meta name="description" content="{description}"/>',
        "canonical": f'<link rel="canonical" href="{canonical or url}"/>',
        "og:title": '<meta property="og:title" content="A page"/>',
        "og:description": '<meta property="og:description" content="A page."/>',
        "og:url": f'<meta property="og:url" content="{url}"/>',
    }
    head = "".join(tag for name, tag in tags.items() if name != omit)
    return f"<!DOCTYPE html><html><head><title>A page</title>{head}</head><body>{body}</body></html>"


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    """A clean built site: a home page, a guide with a rendered alert and alert syntax in code, and the 404 page."""
    dist = tmp_path / "dist"
    _write(dist, "index.html", _page(f"{SITE}/"))
    guide = (
        '<aside class="starlight-aside starlight-aside--note"><p>Read this.</p></aside>'
        "<p>Write <code>&gt; [!NOTE]</code> for a note:</p>"
        "<pre><code>&gt; [!WARNING]\n&gt; Careful.</code></pre>"
    )
    _write(dist, "guides/live/index.html", _page(f"{SITE}/guides/live/", guide))
    _write(dist, "404.html", _page(f"{SITE}/404/"))
    _write(dist, "llms.txt", "> [!NOTE] not a page\n")
    return dist


def _findings(dist: Path) -> list[str]:
    return [str(finding) for finding in _render().surface(dist, frozenset())]


def test_a_clean_build_has_no_finding(dist: Path) -> None:
    assert _findings(dist) == []


def _guide(dist: Path, html: str) -> None:
    _write(dist, "guides/live/index.html", html)


GUIDE = f"{SITE}/guides/live/"
FOREIGN = "https://example.com/guides/live/"


@pytest.mark.parametrize(
    ("mutate", "defect"),
    [
        (lambda dist: _guide(dist, _page(GUIDE, omit="description")), "no meta description"),
        (lambda dist: _guide(dist, _page(GUIDE, description="  ")), "no meta description"),
        (lambda dist: _guide(dist, _page(GUIDE, omit="canonical")), "no canonical link"),
        (lambda dist: _guide(dist, _page(GUIDE, canonical=f"{SITE}/guides/")), f"canonical {SITE}/guides/ is not the page's own URL"),
        (lambda dist: _guide(dist, _page(GUIDE, canonical=FOREIGN)), f"canonical {FOREIGN} is not the page's own URL"),
        (lambda dist: _guide(dist, _page(GUIDE, omit="og:title")), "no og:title"),
        (lambda dist: _guide(dist, _page(GUIDE, omit="og:description")), "no og:description"),
        (lambda dist: _guide(dist, _page(GUIDE, omit="og:url")), "no og:url"),
        (lambda dist: _guide(dist, _page(GUIDE, "<blockquote><p>[!NOTE]\nRead this.</p></blockquote>")), "literal alert marker [!NOTE]"),
        (lambda dist: _guide(dist, _page(GUIDE, "<p>[!caution] mind the gap</p>")), "literal alert marker [!CAUTION]"),
    ],
)
def test_every_mutant_is_reported(dist: Path, mutate: Callable[[Path], None], defect: str) -> None:
    mutate(dist)

    findings = _findings(dist)

    assert findings == [f"render: /guides/live/ (guides/live/index.html: {defect})"]


def test_every_tip_important_and_warning_marker_is_caught(dist: Path) -> None:
    _guide(dist, _page(GUIDE, "<p>[!TIP] a</p><p>[!IMPORTANT] b</p><p>[!WARNING] c</p>"))

    defects = [finding.rsplit(": ", 1)[1] for finding in _findings(dist)]

    assert defects == ["literal alert marker [!TIP])", "literal alert marker [!IMPORTANT])", "literal alert marker [!WARNING])"]


def test_the_registered_surface_runs_in_the_built_site_check(dist: Path) -> None:
    check = _built_check()
    _guide(dist, _page(GUIDE, omit="og:url"))

    findings = [str(finding) for finding in check.check(dist, frozenset())]

    assert "render: /guides/live/ (guides/live/index.html: no og:url)" in findings
