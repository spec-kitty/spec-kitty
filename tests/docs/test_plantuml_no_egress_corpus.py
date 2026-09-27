"""No-egress corpus isolation proof (WP03, NFR-002(b) — the hard gate).

Renders the ACTUAL authored ``@startyaml`` schema-diagram corpus (discovered
dynamically, not a hand-picked sample) under ``docker run --network=none`` and
asserts each is a valid, error-free SVG. Rendering the whole corpus with NO
network available IS the no-egress proof: nothing can be sent off-machine because
there is no machine to send it to. Fails if the corpus is empty (no vacuous pass).

Plus a URL-grep secondary lint over the sources + rendered output.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.docs import plantuml_invoke

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.unit

_CORPUS_DOCS = (
    "docs/architecture/doctrine-relationships.md",
    "docs/architecture/mission-type-resolution.md",
    "docs/architecture/mission-type-resolution.md",
    "docs/architecture/doctrine-kinds.md",
)
_BLOCK_RE = re.compile(r"```plantuml\s*\n(@start\w+.*?@end\w+)\s*\n```", re.DOTALL)
# An external ref = an http(s) URL to a real host. Loopback and the SVG/XLink XML
# namespace declarations (www.w3.org, always present on any <svg> root) are not egress.
_EXTERNAL_URL_RE = re.compile(r"https?://(?!127\.0\.0\.1|localhost|www\.w3\.org)", re.IGNORECASE)


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, check=False).returncode == 0


def _ensure_jar() -> Path:
    # Concurrency-safe: see plantuml_invoke.ensure_jar (WP01 canonical provisioner
    # — a per-process temp download + atomic publish under a cross-process lock,
    # so xdist workers racing on the shared plantuml.jar path never truncate it).
    return plantuml_invoke.ensure_jar(plantuml_invoke.load_pins(), _REPO_ROOT / "plantuml.jar")


def _discover_corpus() -> list[tuple[str, str]]:
    """Every authored @start… block under the corpus docs: (doc, source_text)."""
    found: list[tuple[str, str]] = []
    for rel in dict.fromkeys(_CORPUS_DOCS):  # dedupe, preserve order
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        for block in _BLOCK_RE.findall(text):
            found.append((rel, block))
    return found


def test_corpus_is_non_empty() -> None:
    corpus = _discover_corpus()
    # WP05-WP07 authored 5 diagrams (overview, agent-profile, DRG, mission-step, action-index).
    assert len(corpus) >= 5, f"expected the authored diagram corpus, found {len(corpus)}"


def test_no_external_urls_in_corpus_sources() -> None:
    for rel, source in _discover_corpus():
        assert not _EXTERNAL_URL_RE.search(source), f"external URL in {rel} @startyaml source"


@pytest.mark.skipif(not _docker_available(), reason="docker unavailable")
def test_full_corpus_renders_offline_error_free() -> None:
    _ensure_jar()
    jar = _REPO_ROOT / "plantuml.jar"
    pins = plantuml_invoke.load_pins()
    corpus = _discover_corpus()
    assert corpus, "empty corpus — refusing to pass vacuously"
    for rel, source in corpus:
        # render_startyaml runs docker --network=none + SANDBOX and fails closed on
        # any error SVG — so a clean return IS an error-free offline render.
        svg = plantuml_invoke.render_startyaml(source, workdir=_REPO_ROOT, jar_path=jar, pins=pins)
        assert svg.strip(), f"{rel}: empty SVG"
        assert not plantuml_invoke.svg_is_error(svg), f"{rel}: error SVG"
        # No remote xlink/image refs leaked into the rendered output.
        assert not _EXTERNAL_URL_RE.search(svg.decode("utf-8", "replace")), f"{rel}: external URL in SVG"
