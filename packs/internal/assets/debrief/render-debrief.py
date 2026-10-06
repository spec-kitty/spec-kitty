#!/usr/bin/env python3
"""Stage C — deterministic render of a debrief.

Fills `debrief-template.html` from a Stage-B synthesis object (the slot contract
in docs/development/reporting/debrief-styleguide.md) and enforces the **ref-existence guard**:
every `#NNNN` in the rendered output must appear in the collector's `valid_refs`.
If synthesis invented an issue, this refuses rather than shipping a lie.

    python packs/internal/assets/debrief/render-debrief.py \
        --synthesis synthesis.json --collector debrief.json --out report.html

PDF is a separate step (headless browser print), so this stays dependency-free
and unit-testable. Template dialect:
  * {{ TOKEN }}                     scalar substitution
  * <!-- @each NAME --> … <!-- @end -->   repeat inner per list item
  * <!-- @if NAME --> … <!-- @end -->     keep inner iff NAME is truthy
Blocks may nest (a SECTION's SEC_ITEM loop lives inside the SECTION loop).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCALAR = re.compile(r"\{\{\s*([A-Z0-9_]+)\s*\}\}")
_OPEN = re.compile(r"<!--\s*@(each|if)\s+([A-Z0-9_]+)\s*-->")
_END = "<!-- @end -->"
# A GitHub ref is `#` + digits with no trailing hex letter — the negative
# lookahead keeps CSS hex colours that start with a digit (e.g. #1A1A14) out.
# The whole rendered doc is scanned (including any <style> block): stripping
# <style> before scanning was an evasion vector — an invented #ref hidden inside
# a synthesis-injected <style> block would escape the guard. The lookahead alone
# excludes the template's hex palette (every colour has a hex letter after its
# leading digit), so no strip is needed.
_REF = re.compile(r"#\d+(?![0-9A-Fa-f])")


class RenderError(RuntimeError):
    """Synthesis/template mismatch, or an invented ref — fail closed."""


def _find_matching_end(text: str, after: int) -> int:
    """Index of the `@end` that closes the block whose opener ends at `after`.

    Depth-aware so nested @each/@if pairs resolve correctly.
    """
    depth = 1
    pos = after
    while depth:
        nxt_open = _OPEN.search(text, pos)
        nxt_end = text.find(_END, pos)
        if nxt_end == -1:
            raise RenderError("unbalanced @each/@if — missing @end")
        if nxt_open and nxt_open.start() < nxt_end:
            depth += 1
            pos = nxt_open.end()
        else:
            depth -= 1
            pos = nxt_end + len(_END)
    return pos - len(_END)


def render(template: str, ctx: dict[str, Any]) -> str:
    """Expand blocks (recursively) then substitute scalars, against `ctx`."""
    out: list[str] = []
    i = 0
    while True:
        m = _OPEN.search(template, i)
        if not m:
            out.append(template[i:])
            break
        out.append(template[i : m.start()])
        kind, name = m.group(1), m.group(2)
        inner_start = m.end()
        inner_end = _find_matching_end(template, inner_start)
        inner = template[inner_start:inner_end]
        value = ctx.get(name)
        if kind == "each":
            for item in value or []:
                if not isinstance(item, dict):
                    raise RenderError(f"@each {name} expects a list of objects")
                out.append(render(inner, {**ctx, **item}))
        else:  # @if
            if value:
                out.append(render(inner, ctx))
        i = inner_end + len(_END)
    body = "".join(out)
    return _SCALAR.sub(lambda mm: str(ctx.get(mm.group(1), "")), body)


def build_context(synth: dict[str, Any]) -> dict[str, Any]:
    """Map the Stage-B slot contract (lower snake) onto the template's tokens."""
    return {
        "EYEBROW": synth.get("eyebrow", "SPEC KITTY · EXECUTIVE OVERVIEW"),
        "TITLE": synth.get("title", ""),
        "META_LINE": synth.get("meta_line", ""),
        "LEDE": synth.get("lede", ""),
        "HIGHLIGHTS_HEADING": synth.get("highlights_heading", ""),
        "BODY_HEADING": synth.get("body_heading", ""),
        "DECISIONS_HEADING": synth.get("decisions_heading", ""),
        "AUTHORS_LINE": synth.get("authors_line", ""),
        "METHOD": synth.get("method", ""),
        "TILE": [{"TILE_N": t.get("n", ""), "TILE_LABEL": t.get("label", ""), "TILE_CLASS": t.get("class", "")} for t in synth.get("tiles", [])],
        "HIGHLIGHT": [{"HL_PILL": h.get("pill", ""), "HL_PILL_CLASS": h.get("pill_class", ""), "HL_TEXT": h.get("text", "")} for h in synth.get("highlights", [])],
        "SECTION": [
            {
                "SEC_TITLE": s.get("title", ""),
                "SEC_COUNT": s.get("count", ""),
                "SEC_INTRO": s.get("intro", ""),
                "SEC_ITEM": [{"ITEM_PILL": it.get("pill", ""), "ITEM_TEXT": it.get("text", ""), "ITEM_REFS": it.get("refs", "")} for it in s.get("items", [])],
            }
            for s in synth.get("sections", [])
        ],
        "DECISIONS": synth.get("decisions", []),
        "DECISION": [{"D_ITEM": d.get("item", ""), "D_STATUS": d.get("status", ""), "D_OWNER": d.get("owner", "")} for d in synth.get("decisions", [])],
    }


def enforce_ref_guard(rendered: str, valid_refs: list[str]) -> None:
    """Every #ref in the output must be one the collector actually returned."""
    valid = set(valid_refs)
    used = set(_REF.findall(rendered))
    invented = sorted(used - valid, key=lambda r: int(r[1:]))
    if invented:
        raise RenderError(f"synthesis cited refs not present in the collected data (invented / out of scope): {', '.join(invented)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--synthesis", required=True, help="Stage-B slot JSON.")
    parser.add_argument("--collector", required=True, help="Stage-A collector JSON (for valid_refs).")
    parser.add_argument("--template", default=str(Path(__file__).parent / "debrief-template.html"))
    parser.add_argument("--out", default="-", help="Output HTML path, or '-' for stdout.")
    args = parser.parse_args(argv)

    try:
        synth = json.loads(Path(args.synthesis).read_text(encoding="utf-8"))
        collector = json.loads(Path(args.collector).read_text(encoding="utf-8"))
        template = Path(args.template).read_text(encoding="utf-8")
        rendered = render(template, build_context(synth))
        enforce_ref_guard(rendered, collector.get("valid_refs", []))
    except RenderError as exc:
        print(f"render-debrief: {exc}", file=sys.stderr)
        return 1

    if args.out == "-":
        print(rendered)
    else:
        Path(args.out).write_text(rendered, encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
