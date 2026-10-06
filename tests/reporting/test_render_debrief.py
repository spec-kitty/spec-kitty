"""Tests for the Stage-C debrief renderer: nested block expansion + ref guard."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = pytest.mark.unit

# The debrief scripts are internal-pack assets (hyphenated file names), so they
# are loaded by path rather than imported as a package.
_ASSET = Path(__file__).resolve().parents[2] / "packs" / "internal" / "assets" / "debrief" / "render-debrief.py"


def _load_asset(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rd = _load_asset("render_debrief_asset", _ASSET)


def test_nested_each_and_scalars():
    tpl = (
        "<h1>{{ TITLE }}</h1>"
        "<!-- @each SECTION -->"
        "<h3>{{ SEC_TITLE }}</h3><ul>"
        "<!-- @each SEC_ITEM --><li>{{ ITEM_TEXT }} {{ ITEM_REFS }}</li><!-- @end -->"
        "</ul><!-- @end -->"
    )
    ctx = {
        "TITLE": "Report",
        "SECTION": [
            {"SEC_TITLE": "A", "SEC_ITEM": [{"ITEM_TEXT": "one", "ITEM_REFS": "#1"}, {"ITEM_TEXT": "two", "ITEM_REFS": "#2"}]},
            {"SEC_TITLE": "B", "SEC_ITEM": [{"ITEM_TEXT": "three", "ITEM_REFS": "#3"}]},
        ],
    }
    out = rd.render(tpl, ctx)
    assert "<h1>Report</h1>" in out
    assert out.count("<h3>") == 2
    assert "one #1" in out and "two #2" in out and "three #3" in out


def test_if_block_toggles_on_truthiness():
    tpl = "<!-- @if DECISIONS -->TABLE<!-- @end -->"
    assert rd.render(tpl, {"DECISIONS": [{"x": 1}]}) == "TABLE"
    assert rd.render(tpl, {"DECISIONS": []}) == ""


def test_build_context_maps_contract():
    ctx = rd.build_context(
        {
            "title": "T",
            "tiles": [{"n": "18", "label": "open P0", "class": "alert"}],
            "sections": [{"title": "S", "count": "3", "items": [{"text": "x", "refs": "#9"}]}],
        }
    )
    assert ctx["TITLE"] == "T"
    assert ctx["TILE"][0] == {"TILE_N": "18", "TILE_LABEL": "open P0", "TILE_CLASS": "alert"}
    assert ctx["SECTION"][0]["SEC_ITEM"][0]["ITEM_REFS"] == "#9"


def test_ref_guard_rejects_invented_ref():
    rendered = "<li>real #5045</li><li>invented #9999</li>"
    with pytest.raises(rd.RenderError) as exc:
        rd.enforce_ref_guard(rendered, valid_refs=["#5045", "#5049"])
    assert "#9999" in str(exc.value)


def test_ref_guard_passes_when_all_present():
    rd.enforce_ref_guard("<li>#5045 and #5049</li>", valid_refs=["#5045", "#5049", "#5100"])


def test_ref_guard_ignores_css_hex_colours():
    # The template's palette (digit-leading hex like #1A1A14, #2A2A22, …) is
    # excluded by the _REF negative-lookahead alone — each has a hex letter after
    # its leading digit. No <style> strip is used, so this holds anywhere.
    rendered = "<style>:root{--a:#1A1A14;--b:#2A2A22;--c:#5C5C52;--d:#8FCB8F}</style><li>real ref #5045</li>"
    rd.enforce_ref_guard(rendered, valid_refs=["#5045"])


def test_ref_guard_catches_invented_ref_hidden_in_style_block():
    # Regression: the guard must NOT strip <style> before scanning — an invented
    # all-decimal #ref hidden inside a synthesis-injected <style> block would
    # otherwise evade the guard (the ref-guard's headline promise).
    rendered = "<p>legit #5045</p><style>/* sneaky #9999 */</style>"
    with pytest.raises(rd.RenderError) as exc:
        rd.enforce_ref_guard(rendered, valid_refs=["#5045"])
    assert "#9999" in str(exc.value)


def test_template_loads_its_logo_and_fonts_from_beside_it():
    """The template links its logo and fonts by relative path, so they must sit next to it."""
    template = (_ASSET.parent / "debrief-template.html").read_text(encoding="utf-8")
    linked = re.findall(r"""(?:src=["']|url\(['"])((?:fonts/)?[\w.-]+\.(?:png|otf))""", template)
    assert "logo.png" in linked
    assert sum(1 for name in linked if name.startswith("fonts/")) == 3
    for relative in linked:
        assert (_ASSET.parent / relative).is_file(), relative
