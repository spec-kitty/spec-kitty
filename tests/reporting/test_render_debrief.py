"""Tests for the Stage-C debrief renderer: nested block expansion + ref guard."""

from __future__ import annotations

import pytest

from scripts.reporting import render_debrief as rd

pytestmark = pytest.mark.unit


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
    # A <style> block with digit-leading hex colours (#1A1A14, #2A2A22, …) must
    # not be mistaken for GitHub refs — regression for the sample-render bug.
    rendered = "<style>:root{--a:#1A1A14;--b:#2A2A22;--c:#5C5C52;--d:#8FCB8F}</style><li>real ref #5045</li>"
    rd.enforce_ref_guard(rendered, valid_refs=["#5045"])
