"""Tests for the docsite PlantUML render post-processor (WP02).

Pure-logic tests (fence recovery, caption derivation, accessible-SVG wrapping,
fail-closed on an unrendered fence) run everywhere. The real network-isolated
render round-trip is docker-gated (mirrors the WP01 spike); it downloads +
sha256-verifies the pinned jar, then renders through the isolated container.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.docs import plantuml_invoke, plantuml_render

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.unit


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "info"], capture_output=True, check=False).returncode == 0


def _ensure_jar() -> Path:
    # Concurrency-safe: see plantuml_invoke.ensure_jar (WP01 canonical provisioner
    # — a per-process temp download + atomic publish under a cross-process lock,
    # so xdist workers racing on the shared plantuml.jar path never truncate it).
    return plantuml_invoke.ensure_jar(plantuml_invoke.load_pins(), _REPO_ROOT / "plantuml.jar")


_docker = pytest.mark.skipif(not _docker_available(), reason="docker unavailable")


def _page(fence_class: str, title: str) -> str:
    body = f"@startyaml&#10;title {title}&#10;profile_id: &quot;x&quot;&#10;@endyaml&#10;"
    return f'<html><body><pre><code class="{fence_class}">{body}</code></pre></body></html>'


# ---- pure-logic (no docker) ----------------------------------------------------


def test_code_block_regex_matches_any_class_convention() -> None:
    # class-agnostic: lang-, language-, extra highlighter tokens all recover.
    for cls in ("lang-plantuml", "language-plantuml", "lang-plantuml hljs", "plantuml"):
        m = plantuml_render._CODE_BLOCK_RE.search(_page(cls, "T"))
        assert m and plantuml_render._START_RE.search(m.group("body"))


def test_prose_and_inline_mention_of_startyaml_is_not_a_fence() -> None:
    # A page that only *mentions* @startyaml in prose / inline <code> must render
    # unchanged and must NOT trip the fail-closed leftover check.
    page = "<html><body><p>The <code>@startyaml</code> diagram is generated.</p><p>See the @startyaml block below.</p></body></html>"
    assert plantuml_render.render_html(page, workdir=_REPO_ROOT) == page


def test_derive_caption_rejects_trivial() -> None:
    assert plantuml_render.derive_caption("@startyaml\ntitle Real Title\nx: 1\n") == "Real Title"
    with pytest.raises(plantuml_render.PlantumlRenderPageError):
        plantuml_render.derive_caption("@startyaml\ntitle diagram\nx: 1\n")
    with pytest.raises(plantuml_render.PlantumlRenderPageError):
        plantuml_render.derive_caption("@startyaml\nx: 1\n")  # no title at all


def test_accessible_svg_sets_role_aria_and_title() -> None:
    out = plantuml_render._accessible_svg(b'<svg width="10"><g/></svg>', "Agent Profile Schema")
    assert 'role="img"' in out
    assert 'aria-label="Agent Profile Schema"' in out
    assert "<title>Agent Profile Schema</title>" in out
    assert out.startswith("<figure")


@_docker
def test_unusual_code_class_still_renders() -> None:
    # The exact DocFX-build failure mode: a class the old strict regex missed
    # (extra highlighter token) is now recovered by content and rendered.
    _ensure_jar()
    out = plantuml_render.render_html(_page("lang-plantuml hljs", "Weird Class"), workdir=_REPO_ROOT)
    assert "<svg" in out and 'aria-label="Weird Class"' in out
    assert "@startyaml" not in out  # fully consumed


def test_mermaid_block_is_untouched() -> None:
    mermaid = '<pre><code class="lang-mermaid">graph TD; A--&gt;B;</code></pre>'
    assert plantuml_render.render_html(mermaid, workdir=_REPO_ROOT) == mermaid


# ---- docker-gated render round-trip -------------------------------------------


@_docker
def test_round_trip_renders_svg_with_exact_literal_alt() -> None:
    _ensure_jar()
    for cls in ("lang-plantuml", "language-plantuml"):
        out = plantuml_render.render_html(_page(cls, "Round Trip Alpha"), workdir=_REPO_ROOT)
        assert "<svg" in out and 'role="img"' in out
        assert 'aria-label="Round Trip Alpha"' in out  # exact literal title, not generic
        assert "@startyaml" not in out  # fence fully consumed
        assert not plantuml_invoke.svg_is_error(out.encode("utf-8"))


@_docker
def test_two_diagrams_get_distinct_alt() -> None:
    _ensure_jar()
    two = _page("lang-plantuml", "Alpha One") + _page("language-plantuml", "Beta Two")
    out = plantuml_render.render_html(two, workdir=_REPO_ROOT)
    assert 'aria-label="Alpha One"' in out
    assert 'aria-label="Beta Two"' in out
