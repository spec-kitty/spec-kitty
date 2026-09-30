#!/usr/bin/env python3
"""Render a Markdown document to a Spec Kitty branded PDF.

Maintainer tooling. Produces a light "cream/paper" print treatment that leads with
the signature yellow (#F5C518) and dark-ink headings — the brand's print identity,
NOT the dark-mode website surface and NOT the sage green (which tokens.css reserves
for light-mode headings and is deliberately not used here). Typefaces: Falling Sky
(display/headings), Swansea (body), JetBrains Mono (code/labels/eyebrow).

First used for the 3.2.6 development-cycle postmortem (2026-09-04).

Requirements
------------
- ``pandoc``   on PATH        (Markdown -> HTML)
- ``weasyprint`` on PATH      (HTML -> PDF; honours @page, @font-face, local files)
- the sibling ``spec-kitty-design`` repo for the fonts + logo (``--design-repo`` to
  point elsewhere). Uses ``packages/tokens/dist/fonts`` and
  ``packages/tokens/assets/logo.png``. If the fonts are absent WeasyPrint falls
  back to system faces, so the PDF still renders, just off-brand.

Usage
-----
    python spec-kitty-branded-pdf.py --input report.md --output report.pdf \
        --title "3.2.6 Cycle Report" --subtitle "..." --lede "..." \
        [--eyebrow "Spec Kitty · Release Report"] [--footer-center "3.2.6 CYCLE REPORT"] \
        [--design-repo /path/to/spec-kitty-design]

Colour + type values are reconciled with the Spec Kitty design system
(``spec-kitty-design/packages/tokens/dist/tokens.css``).
"""

from __future__ import annotations

import argparse
import html as _html
import shutil
import subprocess
import sys
from pathlib import Path


def _default_design_repo() -> Path:
    # Sibling of the spec-kitty repo by default: <...>/spec-kitty-design
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "spec-kitty-design"
        if (cand / "packages/tokens/dist/fonts").is_dir():
            return cand
    return Path.home() / "spec-kitty-design"


def _css(fonts: Path) -> str:
    f = str(fonts)
    return f"""
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

@font-face {{ font-family:'Falling Sky'; src:url('file://{f}/FallingSky-JKwK.otf');      font-weight:400; }}
@font-face {{ font-family:'Falling Sky'; src:url('file://{f}/FallingSkyMedium-ved9.otf'); font-weight:500; }}
@font-face {{ font-family:'Falling Sky'; src:url('file://{f}/FallingSkyBold-zemL.otf');   font-weight:700; }}
@font-face {{ font-family:'Falling Sky'; src:url('file://{f}/FallingSkyBlack-GYXA.otf');  font-weight:900; }}
@font-face {{ font-family:'Swansea'; src:url('file://{f}/Swansea-q3pd.ttf');          font-weight:400; font-style:normal; }}
@font-face {{ font-family:'Swansea'; src:url('file://{f}/SwanseaBold-D0ox.ttf');      font-weight:700; font-style:normal; }}
@font-face {{ font-family:'Swansea'; src:url('file://{f}/SwanseaItalic-AwqD.ttf');    font-weight:400; font-style:italic; }}
@font-face {{ font-family:'Swansea'; src:url('file://{f}/SwanseaBoldItalic-p3Dv.ttf'); font-weight:700; font-style:italic; }}

:root {{
  --yellow:#F5C518; --yellow-deep:#C99A0E;
  --page:#F8F5EC; --card:#FFFFFF; --input:#F5F1E6; --muted:#E8E2D0; --pill:#ECE7D8;
  --ink:#231D12; --ink-soft:#5A5342; --hair:#DED6C2;
  --display:'Falling Sky', ui-sans-serif, system-ui, sans-serif;
  --body:'Swansea', Georgia, ui-serif, serif;
  --mono:'JetBrains Mono', ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}}

@page {{
  size:A4; margin:20mm 25mm 18mm 25mm; background:#F8F5EC;
  @bottom-left   {{ content:"Spec Kitty"; font-family:var(--mono); font-size:7pt; color:#8A8578; letter-spacing:.08em; }}
  @bottom-center {{ content:"__FOOTER__"; font-family:var(--mono); font-size:7pt; color:#8A8578; letter-spacing:.14em; }}
  @bottom-right  {{ content:counter(page)" / "counter(pages); font-family:var(--mono); font-size:7pt; color:#8A8578; }}
}}
@page:first {{ margin:0; @bottom-left{{content:none}} @bottom-center{{content:none}} @bottom-right{{content:none}} }}

html {{ font-size:10.5pt; hyphens:none; }}
body {{ font-family:var(--body); color:var(--ink); background:var(--page); line-height:1.5; margin:0; }}

.cover {{ page-break-after:always; height:297mm; box-sizing:border-box; background:var(--page); padding:52mm 24mm 24mm; position:relative; }}
.cover .rule-top {{ position:absolute; top:0; left:0; right:0; height:9mm; background:var(--yellow); }}
.cover img.logo {{ width:33mm; height:33mm; display:block; margin-bottom:14mm; }}
.cover .eyebrow {{ font-family:var(--mono); font-size:9pt; letter-spacing:.16em; text-transform:uppercase; color:#5A5342; margin-bottom:8mm; }}
.cover h1.title {{ font-family:var(--display); font-weight:900; font-size:44pt; line-height:1.02; color:var(--ink); margin:0 0 6mm; letter-spacing:-.01em; }}
.cover .subtitle {{ font-family:var(--display); font-weight:500; font-size:15pt; color:var(--ink); margin:0 0 3mm; max-width:135mm; }}
.cover .lede {{ font-size:11pt; color:var(--ink-soft); max-width:130mm; margin:0 0 14mm; line-height:1.55; }}
.cover .meta {{
  position:absolute; bottom:26mm; left:24mm; right:24mm;
  border-top:1.5pt solid var(--yellow); padding-top:5mm;
  display:flex; justify-content:space-between;
  font-family:var(--mono); font-size:8.5pt; color:var(--ink-soft); letter-spacing:.04em;
}}
.cover .meta b {{ color:var(--ink); font-weight:500; }}

.content {{ padding:0; }}
h1, h2, h3, h4 {{ font-family:var(--display); color:var(--ink); line-height:1.15; }}
h1 {{ font-weight:900; font-size:22pt; margin:11mm 0 3mm; padding-bottom:2mm; border-bottom:2.5pt solid var(--yellow); page-break-after:avoid; }}
h2 {{ font-weight:700; font-size:15pt; margin:8mm 0 2mm; padding-left:3mm; border-left:3pt solid var(--yellow); page-break-after:avoid; }}
h3 {{ font-weight:600; font-size:12pt; color:var(--ink); margin:6mm 0 1.5mm; page-break-after:avoid; }}
h4 {{ font-weight:600; font-size:10.5pt; color:var(--ink-soft); margin:4mm 0 1mm; }}
p {{ margin:0 0 2.6mm; }}
strong {{ font-weight:700; color:var(--ink); }}
em {{ font-style:italic; }}
a {{ color:var(--ink); text-decoration:none; border-bottom:1.5pt solid var(--yellow); }}
ul, ol {{ margin:0 0 3mm; padding-left:6mm; }}
li {{ margin:.8mm 0; }}
ul li::marker {{ color:var(--yellow-deep); }}
hr {{ border:none; border-top:1pt solid var(--hair); margin:6mm 0; }}

code {{ font-family:var(--mono); font-size:8.4pt; background:var(--input); color:#6B4E00; padding:.3mm .15em; margin:0; border-radius:2px; }}
pre {{
  background:var(--muted); border:1pt solid var(--hair);
  border-left:3pt solid var(--yellow-deep); border-radius:3px;
  padding:3mm 4mm; overflow:hidden; page-break-inside:avoid;
}}
pre code {{ background:none; color:var(--ink); font-size:8pt; padding:0; line-height:1.45; }}

blockquote {{ margin:3mm 0; padding:2mm 4mm; background:var(--card); border-left:3pt solid var(--yellow); color:var(--ink-soft); }}
blockquote p {{ margin:1mm 0; }}

table {{ width:100%; border-collapse:collapse; margin:3mm 0 4mm; font-size:8.8pt; page-break-inside:avoid; }}
thead th {{
  font-family:var(--display); font-weight:700; font-size:8.6pt;
  background:var(--yellow); color:var(--ink); text-align:left;
  padding:1.6mm 2.4mm; letter-spacing:.01em;
}}
tbody td {{ padding:1.4mm 2.4mm; border-bottom:.6pt solid var(--hair); vertical-align:top; }}
tbody tr:nth-child(even) {{ background:var(--input); }}
tbody code {{ font-size:7.8pt; }}
.content > h1:first-child {{ margin-top:0; }}
"""


def build(args: argparse.Namespace) -> int:
    design = Path(args.design_repo).resolve()
    fonts = design / "packages/tokens/dist/fonts"
    logo = design / "packages/tokens/assets/logo.png"
    if not fonts.is_dir():
        print(f"warning: brand fonts not found under {fonts}; PDF will use fallback faces", file=sys.stderr)

    body = subprocess.run(
        ["pandoc", "-f", "gfm", "-t", "html5", str(Path(args.input).resolve())],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    css = _css(fonts).replace("__FOOTER__", _html.escape(args.footer_center))
    meta = "".join(f"<span>{_html.escape(k)} <b>{_html.escape(v)}</b></span>" for k, v in (args.meta or []))
    cover = (
        f"""
<section class="cover">
  <div class="rule-top"></div>
  <img class="logo" src="file://{logo}" alt="Spec Kitty">
  <div class="eyebrow">{_html.escape(args.eyebrow)}</div>
  <h1 class="title">{args.title}</h1>
  <div class="subtitle">{_html.escape(args.subtitle)}</div>
  <p class="lede">{_html.escape(args.lede)}</p>
  <div class="meta">{meta}</div>
</section>"""
        if args.title
        else ""
    )

    doc = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{_html.escape(args.title or Path(args.input).stem)}</title>"
        f"<style>{css}</style></head><body>{cover}"
        f'<section class="content">{body}</section></body></html>'
    )

    out = Path(args.output).resolve()
    tmp_html = out.with_suffix(".build.html")
    tmp_html.write_text(doc, encoding="utf-8")
    try:
        # weasyprint is an optional runtime dep: it ships no type stubs, and may
        # be absent entirely (we fall back to the CLI below). A bare ignore covers
        # both import-untyped and import-not-found without pinning an env-specific code.
        import weasyprint  # type: ignore

        weasyprint.HTML(filename=str(tmp_html)).write_pdf(str(out))
    except ImportError:
        wp = shutil.which("weasyprint")
        if not wp:
            print("error: weasyprint not importable and not on PATH; install it (pip install weasyprint) or run this with a Python that has it", file=sys.stderr)
            return 1
        subprocess.run([wp, str(tmp_html), str(out)], check=True)
    tmp_html.unlink(missing_ok=True)
    print(f"wrote {out}")
    return 0


def _meta_pair(value: str) -> tuple[str, str]:
    label, _, val = value.partition("=")
    return label.strip(), val.strip()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Render Markdown to a Spec Kitty branded PDF.")
    p.add_argument("--input", required=True, help="source Markdown file")
    p.add_argument("--output", required=True, help="destination PDF path")
    p.add_argument("--title", default="", help="cover title (HTML allowed for line breaks); omit for no cover")
    p.add_argument("--subtitle", default="")
    p.add_argument("--lede", default="")
    p.add_argument("--eyebrow", default="Spec Kitty · Release Report")
    p.add_argument("--footer-center", default="SPEC KITTY", help="centered running-footer label")
    p.add_argument("--meta", type=_meta_pair, action="append", help="cover meta chip 'LABEL=value' (repeatable)")
    p.add_argument("--design-repo", default=str(_default_design_repo()), help="path to the spec-kitty-design repo (fonts + logo)")
    return build(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
