"""Acceptance tests for the built-site diagram check (#6936; ADR 2026-10-31-1 D-11).

``scripts/docs/site_built_check_diagrams.py`` is a source surface of the built-site
check (``site_built_check.py``): for every page the site publishes
(``_dockitty_contract``), each ```` ```mermaid ```` and ```` ```plantuml ```` fence in
the source is a static SVG figure in the built page, the markup doc-kitty's
``diagramFigure`` emits in build mode (``<figure class="dk-diagram"><svg>``). These
tests build a small ``docs/`` tree and the ``dist/`` a clean build of it gives, then
plant one failure mode at a time (a mutant): the clean tree passes and every mutant
fails, naming the page and the reason.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MERMAID = "```mermaid\nflowchart LR\n  a --> b\n```\n"
PLANTUML = "```plantuml\n@startuml\nA -> B\n@enduml\n```\n"
#: A nested example: the ```mermaid lines are the content of a four-backtick markdown fence, not a diagram.
NESTED_EXAMPLE = "````markdown\n```mermaid\nflowchart LR\n```\n````\n"
#: An indented fence inside a list item (``changelog/2x/model-to-task_type.md`` has one).
LIST_ITEM_FENCE = "1. A step:\n\n   ```mermaid\n   flowchart LR\n     a --> b\n   ```\n"

#: The built markup doc-kitty v0.7.0 emits for a rendered diagram (``lib/rehype/diagram-figure.ts:191-202, 282-299``).
FIGURE = '<figure class="dk-diagram" role="group"><svg xmlns="http://www.w3.org/2000/svg" aria-roledescription="flowchart-v2"><g><text>a</text></g></svg></figure>'
#: A rendered figure with a caption (``diagram-figure.ts:195-200``).
CAPTIONED_FIGURE = (
    '<figure class="dk-diagram" role="group" aria-labelledby="dk-diagram-caption-plantuml-0">'
    '<svg xmlns="http://www.w3.org/2000/svg"><title>A</title></svg>'
    '<figcaption class="dk-diagram__caption" id="dk-diagram-caption-plantuml-0"><span class="dk-diagram__desc">A flow</span></figcaption></figure>'
)
#: A source fence left as code by expressive-code (what the site builds with ``diagrams: false``).
RAW_MERMAID = '<div class="expressive-code"><figure class="frame not-content"><pre data-language="mermaid"><code>flowchart LR</code></pre></figure></div>'
RAW_PLANTUML = '<pre class="astro-code"><code class="language-plantuml">@startuml</code></pre>'
#: doc-kitty's client-mode residue (``lib/integrations/diagrams.ts:70-81``): rendered in the browser, not at build time.
CLIENT_MERMAID = '<figure class="dk-diagram" role="group"><pre class="mermaid">flowchart LR</pre></figure>'
#: ``astro-plantuml``'s render-error fallback (``astro-plantuml@1.0.0 dist/render.js:122-126``).
PLANTUML_ERROR = (
    '<div class="plantuml-error">\n  <p>Error generating PlantUML diagram: Request failed with status code 400</p>\n'
    '  <pre><code class="language-plantuml">@startuml</code></pre>\n</div>'
)


def _diagrams() -> ModuleType:
    return importlib.import_module("scripts.docs.site_built_check_diagrams")


def _built_check() -> ModuleType:
    return importlib.import_module("scripts.docs.site_built_check")


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _source(body: str, status: str = "active") -> str:
    return f"---\ntitle: t\ndoc_status: {status}\n---\n\n# Body\n\n{body}"


def _html(body: str) -> str:
    return f"<!DOCTYPE html><html><head><title>t</title></head><body><main>{body}</main></body></html>"


@pytest.fixture
def site(tmp_path: Path) -> tuple[Path, Path]:
    """Published pages with diagrams, unpublished pages with diagrams, and the dist a clean build gives."""
    docs = tmp_path / "docs"
    _write(docs, "index.md", _source("No diagrams. The renderer is never plantuml.com.\n"))
    _write(docs, "architecture/flows.md", _source(f"{MERMAID}\nText.\n\n{PLANTUML}\n{MERMAID}"))
    _write(docs, "architecture/README.md", _source(f"{NESTED_EXAMPLE}\n{LIST_ITEM_FENCE}"))
    _write(docs, "guides/wip.md", _source(MERMAID, status="draft"))
    _write(docs, "archive/old.md", _source(f"{MERMAID}{PLANTUML}"))
    _write(docs, "plans/engineering-notes/note.md", _source(MERMAID, status="active"))

    dist = tmp_path / "dist"
    _write(dist, "index.html", _html("<p>No diagrams. The renderer is never plantuml.com.</p>"))
    _write(dist, "architecture/flows/index.html", _html(f"{FIGURE}<p>Text.</p>{CAPTIONED_FIGURE}{FIGURE}"))
    _write(dist, "architecture/index.html", _html(f'<pre data-language="markdown"><code>```mermaid</code></pre><ol><li>{FIGURE}</li></ol>'))
    _write(dist, "404.html", _html("<p>Not found</p>"))
    return docs, dist


def _findings(docs: Path, dist: Path) -> list[str]:
    return [str(finding) for finding in _diagrams().findings(dist, docs=docs)]


def test_a_clean_build_has_no_finding(site: tuple[Path, Path]) -> None:
    docs, dist = site

    assert _findings(docs, dist) == []


def _flows(dist: Path, body: str) -> None:
    _write(dist, "architecture/flows/index.html", _html(body))


FLOWS = "/architecture/flows/"
FLOWS_HTML = "architecture/flows/index.html"


@pytest.mark.parametrize(
    ("mutate", "reasons"),
    [
        pytest.param(
            lambda dist: _flows(dist, f"{RAW_MERMAID}{CAPTIONED_FIGURE}{FIGURE}"),
            ["raw mermaid code block", "3 diagram block(s) in the source, 2 rendered figure(s)"],
            id="raw-mermaid-fence",
        ),
        pytest.param(
            lambda dist: _flows(dist, f"{FIGURE}{RAW_PLANTUML}{FIGURE}"),
            ["raw plantuml code block", "3 diagram block(s) in the source, 2 rendered figure(s)"],
            id="raw-plantuml-fence",
        ),
        pytest.param(
            lambda dist: _flows(dist, f"{CLIENT_MERMAID}{CAPTIONED_FIGURE}{FIGURE}"),
            ["client-rendered mermaid block", "3 diagram block(s) in the source, 2 rendered figure(s)"],
            id="client-mode-residue",
        ),
        pytest.param(
            lambda dist: _flows(dist, f"{FIGURE}{PLANTUML_ERROR}{FIGURE}"),
            ["diagram error block", "raw plantuml code block", "3 diagram block(s) in the source, 2 rendered figure(s)"],
            id="error-block",
        ),
        pytest.param(
            lambda dist: _flows(dist, f"{FIGURE}{CAPTIONED_FIGURE}"),
            ["3 diagram block(s) in the source, 2 rendered figure(s)"],
            id="missing-figure",
        ),
        pytest.param(
            lambda dist: _flows(dist, f"{FIGURE}{CAPTIONED_FIGURE}{FIGURE}{FIGURE}"),
            ["3 diagram block(s) in the source, 4 rendered figure(s)"],
            id="extra-figure",
        ),
        pytest.param(
            lambda dist: _flows(
                dist, f'{FIGURE}<figure class="dk-diagram"><img src="https://www.plantuml.com/plantuml/svg/SyfFKj2rKt3CoKnELR1Io4ZDoSa70000"/></figure>{FIGURE}'
            ),
            ["plantuml.com URL https://www.plantuml.com/plantuml/svg/SyfFKj2rKt3CoKnELR1Io4ZDoSa70000", "3 diagram block(s) in the source, 2 rendered figure(s)"],
            id="plantuml-com-url",
        ),
        pytest.param(
            lambda dist: (dist / FLOWS_HTML).unlink(),
            ["3 diagram block(s) in the source, no built page"],
            id="page-not-built",
        ),
    ],
)
def test_every_mutant_is_reported(site: tuple[Path, Path], mutate: Callable[[Path], None], reasons: list[str]) -> None:
    docs, dist = site
    mutate(dist)

    findings = _findings(docs, dist)

    assert sorted(findings) == sorted(f"diagrams: {FLOWS} ({FLOWS_HTML}: {reason})" for reason in reasons)


def test_a_raw_block_marked_on_both_pre_and_code_is_reported_once(site: tuple[Path, Path]) -> None:
    """Astro's own highlighter marks the language on the ``pre`` and on its ``code``: one block, one finding."""
    docs, dist = site
    _flows(dist, f'<pre data-language="mermaid"><code class="language-mermaid">flowchart LR</code></pre>{CAPTIONED_FIGURE}{FIGURE}')

    assert _findings(docs, dist) == [
        f"diagrams: {FLOWS} ({FLOWS_HTML}: raw mermaid code block)",
        f"diagrams: {FLOWS} ({FLOWS_HTML}: 3 diagram block(s) in the source, 2 rendered figure(s))",
    ]


def test_a_figure_holding_several_svgs_counts_once(site: tuple[Path, Path]) -> None:
    """A diagram whose SVG nests another ``<svg>`` (or carries a sibling icon) is one figure, not two."""
    docs, dist = site
    nested = '<figure class="dk-diagram" role="group"><svg><g><svg><rect/></svg></g></svg><svg class="icon"></svg></figure>'
    _flows(dist, f"{nested}{CAPTIONED_FIGURE}{FIGURE}")

    assert _findings(docs, dist) == []


def test_a_figure_on_a_page_without_a_source_diagram_is_reported(site: tuple[Path, Path]) -> None:
    docs, dist = site
    _write(dist, "index.html", _html(FIGURE))

    assert _findings(docs, dist) == ["diagrams: / (index.html: 0 diagram block(s) in the source, 1 rendered figure(s))"]


def test_a_plantuml_com_url_on_any_built_page_is_reported(site: tuple[Path, Path]) -> None:
    docs, dist = site
    _write(dist, "404.html", _html('<a href="http://plantuml.com/plantuml/png/abc">x</a>'))

    assert _findings(docs, dist) == ["diagrams: /404/ (404.html: plantuml.com URL http://plantuml.com/plantuml/png/abc)"]


@pytest.mark.parametrize("rel", ["guides/wip.md", "archive/old.md", "plans/engineering-notes/note.md"])
def test_a_diagram_on_an_unpublished_page_is_not_counted(site: tuple[Path, Path], rel: str) -> None:
    """A draft, an excluded folder and a draft-only folder are not built, so their diagrams are not expected."""
    docs, dist = site
    assert (docs / rel).is_file()

    assert _diagrams().expected_figures(docs).get("/" + rel.removesuffix(".md") + "/") is None
    assert _findings(docs, dist) == []


def test_publishing_a_draft_makes_its_diagram_expected(site: tuple[Path, Path]) -> None:
    """The unpublished case passes because the page is unpublished, not because the check skips drafts' blocks."""
    docs, dist = site
    _write(docs, "guides/wip.md", _source(MERMAID, status="active"))

    assert _findings(docs, dist) == ["diagrams: /guides/wip/ (guides/wip/index.html: 1 diagram block(s) in the source, no built page)"]


@pytest.mark.parametrize(
    ("markdown", "count"),
    [
        pytest.param(MERMAID, 1, id="mermaid"),
        pytest.param(PLANTUML, 1, id="plantuml"),
        pytest.param("~~~mermaid\nflowchart LR\n~~~\n", 1, id="tilde-fence"),
        pytest.param("```mermaid title=x\nflowchart LR\n```\n", 1, id="info-string-meta"),
        pytest.param(LIST_ITEM_FENCE, 1, id="list-item-fence"),
        pytest.param(NESTED_EXAMPLE, 0, id="nested-in-a-longer-fence"),
        pytest.param("```text\n```mermaid\n```\n", 0, id="inside-another-fence"),
        pytest.param("```Mermaid\nflowchart LR\n```\n", 0, id="language-is-case-sensitive"),
        pytest.param("```mermaid-js\nflowchart LR\n```\n", 0, id="other-language"),
        pytest.param("Inline ```mermaid``` is prose.\n", 0, id="inline-code"),
        pytest.param(f"{MERMAID}{MERMAID}{PLANTUML}", 3, id="several"),
    ],
)
def test_source_blocks_counts_diagram_fences_as_doc_kitty_reads_them(markdown: str, count: int) -> None:
    assert _diagrams().source_blocks(markdown) == count


def test_the_surface_runs_in_the_built_site_check_command(site: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    docs, dist = site
    _flows(dist, f"{RAW_MERMAID}{CAPTIONED_FIGURE}{FIGURE}")

    code = _built_check().main([str(dist), "--docs", str(docs)])

    out = capsys.readouterr().out
    assert code == 1
    assert f"diagrams: {FLOWS} ({FLOWS_HTML}: raw mermaid code block)" in out.splitlines()


def test_the_command_summary_names_the_failing_surfaces_not_only_unpublished_routes(site: tuple[Path, Path], capsys: pytest.CaptureFixture[str]) -> None:
    """A diagram finding is not an unpublished route: the summary counts findings per surface."""
    docs, dist = site
    _flows(dist, f"{RAW_MERMAID}{CAPTIONED_FIGURE}{FIGURE}")

    _built_check().main([str(dist), "--docs", str(docs)])

    summary = capsys.readouterr().err.strip().splitlines()[-1]
    assert "unpublished route" not in summary
    assert "diagrams: 2" in summary
