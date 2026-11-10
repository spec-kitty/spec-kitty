"""Acceptance tests for the built-site ``llms.txt`` and agent-index check (#6934; ADR 2026-10-31-1 D-8, D-9).

``scripts/docs/site_built_check_llms.py`` is a surface of the built-site check
(``site_built_check.py``): the built ``llms.txt`` exists and carries the version
stance (``_dockitty_contract.LLMS_STANCE``) exactly, lists no route of a section
whose ``feeds`` in ``docs/_meta/sections.yaml`` leave out ``llms`` (``plans``), and
the agent index it names (``api/index.json``) is built. An unpublished route in
``llms.txt`` is the ``llms`` surface's finding, so the whole check is exercised
here too. A clean fixture build passes; each mutant fails, naming the defect.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

SITE = "https://docs.spec-kitty.ai"
HEADER = "# Spec Kitty\n\n> Spec Kitty documentation.\n\n"
SECTIONS = """\
version: 1
sections:
  - id: guides
    label: Guides
    order: 10
  - id: plans
    label: Plans
    order: 140
    # Restricted feeds: no llms.
    feeds: [sitemap]
  - id: context
    label: Context
    order: 20
    feeds:
      - sitemap
      - llms
"""


def _llms() -> ModuleType:
    return importlib.import_module("scripts.docs.site_built_check_llms")


def _built_check() -> ModuleType:
    return importlib.import_module("scripts.docs.site_built_check")


def _stance() -> str:
    return str(importlib.import_module("scripts.docs._dockitty_contract").LLMS_STANCE)


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _llms_txt(*entries: str) -> str:
    lines = "".join(f"- [{route}]({SITE}{route}): a page\n" for route in entries)
    return f"{HEADER}{_stance()}\nFull machine index: {SITE}/api/index.json\n\n## Guides\n\n{lines}"


@pytest.fixture
def site(tmp_path: Path) -> tuple[Path, Path]:
    """A docs tree with a restricted-feeds section and the dist a clean build of it gives."""
    docs = tmp_path / "docs"
    _write(docs, "_meta/sections.yaml", SECTIONS)
    _write(docs, "guides/live.md", "---\ntitle: t\ndoc_status: active\n---\n")
    _write(docs, "guides/wip.md", "---\ntitle: t\ndoc_status: draft\n---\n")
    _write(docs, "plans/roadmap.md", "---\ntitle: t\ndoc_status: active\n---\n")
    _write(docs, "context/terms.md", "---\ntitle: t\ndoc_status: active\n---\n")

    dist = tmp_path / "dist"
    _write(dist, "llms.txt", _llms_txt("/guides/live/", "/context/terms/"))
    _write(dist, "api/index.json", json.dumps({"pages": [{"url": f"{SITE}/guides/live/"}]}))
    return docs, dist


def _findings(docs: Path, dist: Path) -> list[str]:
    module = _llms()
    return [str(finding) for finding in module.findings(dist, sections=docs / "_meta" / "sections.yaml", stance=_stance())]


def test_a_clean_build_has_no_finding(site: tuple[Path, Path]) -> None:
    docs, dist = site

    assert _findings(docs, dist) == []


def _drop_stance(dist: Path) -> None:
    _write(dist, "llms.txt", (dist / "llms.txt").read_text(encoding="utf-8").replace(_stance(), ""))


def _alter_stance(dist: Path) -> None:
    text = (dist / "llms.txt").read_text(encoding="utf-8")
    _write(dist, "llms.txt", text.replace("Charter-era Spec Kitty", "Spec Kitty 2.x"))


def _list_plans_route(dist: Path) -> None:
    _write(dist, "llms.txt", _llms_txt("/guides/live/", "/plans/roadmap/"))


def _drop_index(dist: Path) -> None:
    (dist / "api" / "index.json").unlink()


def _drop_llms(dist: Path) -> None:
    (dist / "llms.txt").unlink()


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_drop_stance, "llms-content: stance (llms.txt"),
        (_alter_stance, "llms-content: stance (llms.txt"),
        (_list_plans_route, "llms-content: /plans/roadmap/ (llms.txt"),
        (_drop_index, "llms-content: missing (api/index.json"),
        (_drop_llms, "llms-content: missing (llms.txt"),
    ],
)
def test_every_mutant_is_reported(site: tuple[Path, Path], mutate: Callable[[Path], None], expected: str) -> None:
    docs, dist = site
    mutate(dist)

    findings = _findings(docs, dist)

    assert findings, f"the mutant {mutate.__name__} must fail the check"
    assert all(finding.startswith(expected) for finding in findings), findings


def test_a_section_without_feeds_feeds_llms(site: tuple[Path, Path]) -> None:
    """An absent ``feeds`` means every feed (doc-kitty's ``feedsSurface``): a guides route is allowed."""
    docs, dist = site
    _write(dist, "llms.txt", _llms_txt("/guides/live/", "/guides/other/"))

    assert _findings(docs, dist) == []


def test_the_registered_surface_checks_the_real_site_contract(tmp_path: Path) -> None:
    """Through the whole built-site check, with the repository's own sections and stance.

    A clean ``llms.txt`` passes; a ``plans`` route (sitemap-only in ``docs/_meta/sections.yaml``)
    and a missing stance fail as ``llms-content``; a draft route fails as ``llms`` (unpublished).
    """
    docs = tmp_path / "docs"
    _write(docs, "guides/wip.md", "---\ntitle: t\ndoc_status: draft\n---\n")
    dist = tmp_path / "dist"
    _write(dist, "api/index.json", "{}")
    check = _built_check()
    routes = check.unpublished_routes(docs)

    def run(llms_txt: str) -> list[str]:
        _write(dist, "llms.txt", llms_txt)
        # This dist carries no sitemap, okf or search artifact: only the llms surfaces are under test.
        return [str(finding) for finding in check.check(dist, routes) if finding.surface.startswith("llms")]

    assert run(_llms_txt("/guides/live/")) == []
    assert run(_llms_txt("/plans/")) == ["llms-content: /plans/ (llms.txt: section plans does not feed llms)"]
    assert [finding.split(" (")[0] for finding in run(_llms_txt("/guides/wip/"))] == ["llms: /guides/wip/"]
    assert [finding.split(" (")[0] for finding in run(HEADER)] == ["llms-content: stance"]
