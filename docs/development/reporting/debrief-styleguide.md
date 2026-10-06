---
title: 'Executive Debrief House Style'
description: 'House style for Spec Kitty executive debriefs (what-happened reports): the long-form and one-pager layouts, readers and voice, brand palette, and print treatment.'
doc_status: active
updated: '2026-10-06'
audience: docs/context/audience/internal/maintainer.md
type: reference
related:
- docs/development/how-to/pr-landing.md
- docs/changelog/index.md
---
# Debrief house style — executive debriefs ("what happened")

**Status:** the design system's house style, now shipped as the internal
doctrine styleguide
[`packs/internal/styleguides/executive-debrief.styleguide.yaml`](../../../packs/internal/styleguides/executive-debrief.styleguide.yaml).
This page is that artifact's detailed layout, palette and print-treatment reference.
**Applies to:** the reports produced by the `kitty-report-debrief` pack skill — the
time-window "what landed since <T>" debrief and the milestone/label open-issue
snapshot. One-pager examples: [`examples/`](examples/).

## Two layouts

| | One-pager | Long-form debrief |
|---|---|---|
| Use when | counts and a few labelled clusters answer the question | readers need a mechanism explained, a trend shown, or a decision prepared |
| Length | 1 to 2 pages | about 5 to 12 pages |
| Source | a slot object (JSON) | one Markdown file |
| Renderer | `packs/internal/assets/debrief/render-debrief.py` + `debrief-template.html`, printed with a headless browser | `packs/internal/assets/spec-kitty-branded-pdf.py` (pandoc + WeasyPrint) |
| Status shown by | pills and tiles | words and tables |
| Reference check | the renderer fails closed on a `#ref` outside `valid_refs` | the writer checks every `#ref` against the collector output and the saved supplemental files |

Both follow the same rules for facts, readers and voice (see "Voice & content
conventions" below). The Palette, Typography, One-pager layout grammar and Pill
vocabulary sections describe the one-pager template. The long form takes its
colours and type from the branded generator and needs no styling of its own.

## Long-form debrief

A long-form debrief is one Markdown file rendered by the branded PDF generator.
Do not build a cover, a footer or a stylesheet by hand: the generator draws
them from the design tokens. Its look is documented in
[`BRANDED_DOCUMENT_GENERATION.md`](../../../packs/internal/toolguides/BRANDED_DOCUMENT_GENERATION.md).

### Order (fixed)

1. **Cover**, set through generator arguments, not Markdown:
   - eyebrow: `Spec Kitty · Executive Debrief`
   - title: `WTF happened with <X>` or `WTF happened since <T>`, two lines at most
   - subtitle: the subject and the period, one line
   - lede: two or three sentences a reader can stop after
   - three meta chips: `AS OF` (date), `SCOPE` (repository), `FOR` (the readers,
     as the requester named them, separated by ` · `)
2. **Executive summary**, one page, readable alone:
   - **Bottom line.** Three to six sentences.
   - One small table of headline counts or a before/after comparison.
   - **What happened.** A numbered list of three to five items. Each starts with
     a bold one-sentence claim, then gives the evidence.
   - **Still open.** Optional, one sentence pointing at Open risks.
   - **What we need from leadership.** Two to four decisions, each with the
     fact that forces it.
3. **Parts** (`Part A. …`, `Part B. …`) with subsections. Four to six themes in
   total across the parts. Tables for before/after and for lists of four or
   more comparable items; prose for mechanisms.
4. **Open risks.** One table: Risk, Why it matters, Issue, Owner. Write the risk
   as the consequence for a user or a release. Issue is the ref with its
   priority, or "none filed". Owner is the GitHub assignee at collection time,
   "unassigned", or the role that must decide.
5. **Appendix: method, sources and caveats.** The Method line, scope and as-of,
   a definition for any measure that could be read two ways, the data files,
   and the caveats as a list.

### Headings

The generator draws a first-level heading (`#`) as a part title with a yellow
underline and a second-level heading (`##`) as a left-ruled subsection. The body
passed to the generator therefore starts at `# Executive summary`, with
`# Part A. …`, `# Open risks` and `# Appendix: …` at the same level. The document
title lives on the cover and is not repeated as a heading.

### Charts

Add a chart only for a trend or a comparison the reader would otherwise rebuild
from a table. One measure and one axis per chart. Title it with the measure and
the unit, label values directly when there are few marks, and draw it from a
collected file. Save it as SVG beside the Markdown and include it as an image.
A white chart card on the cream page is fine.

### Render

```bash
python packs/internal/assets/spec-kitty-branded-pdf.py \
  --input body.md --output debrief.pdf \
  --eyebrow "Spec Kitty · Executive Debrief" \
  --title "WTF happened<br>since 4.0.0rc5" \
  --subtitle "Four days on main after the fifth release candidate" \
  --lede "Two or three sentences." \
  --footer-center "SINCE 4.0.0RC5 · 2026-10-06" \
  --meta "AS OF=2026-10-06" --meta "SCOPE=spec-kitty/spec-kitty" \
  --meta "FOR=CTO · CEO · CPO · Head of QA · maintainers"
```

Then open the PDF and look at every page: a table header alone at a page
bottom, a chart label that collides with its title, or a cover chip that wraps
badly is fixed in the Markdown or the arguments, not left in.

### Supplemental facts

The collector returns merged PRs, closed issues and headline counts. A long-form
debrief often needs more: open P0s, milestone counts, nightly runs, git
statistics, file sizes. Read each with `gh` or `git` into a file under `raw/`
beside the collector output, and list those files in the appendix. Every number
and every `#ref` in the report must be in the collector output or one of those
files. A fact that was not saved does not go in.

## Provenance — this is the design system's style, not ad-hoc

The look is taken from **`@spec-kitty/tokens`** in the sibling
**`spec-kitty-design`** repo (the `packages/tokens` package, ADR-003
`--sk-<category>-<name>` naming). The debrief template
(`packs/internal/assets/debrief/debrief-template.html`) inlines a **curated light-theme
subset** of those tokens; when a value here and a token there ever disagree,
the token package wins — re-sync the subset, don't fork it.

## Palette (light theme — these are printed documents)

| Role | Token | Value |
|------|-------|-------|
| Signature primary | `--sk-color-yellow` | `#F5C518` |
| Link / accent (light) | `--sk-color-sage` | `#4F8F4F` |
| Success · **SHIPPED** | `--sk-color-green` | `#8FCB8F` on `--sk-surface-tint-mint` `#E8F4E8` |
| Alert · **WATCH / P0** | `--sk-color-red` | `#E97373` on `--sk-surface-tint-sky` `#E4EDF8` |
| Page | `--sk-surface-page` | `#FCFAF4` (light warm cream — the design system's "hero" tone; lighter than the `#F8F5EC` page surface so print reads easier) |
| Warm-gold accent | `--sk-color-haygold` | `#D9B36A` (card left-edge accent) |
| Card | `--sk-surface-card` | `#FFFFFF` |
| Chip rail | `--sk-surface-pill` | `#ECE7D8` |
| Ink / body / muted / label | `--sk-fg-default/body/muted/subtle` | `#1A1A14` / `#2A2A22` / `#5C5C52` / `#8A8A7E` |
| Hairline / card border | `--sk-border-default/strong` | `#EAE4D2` / `#D6CFB9` |

Yellow is the brand signature — use it sparingly, as an **accent**, never for
status: the title carries a short yellow "bow" underline (echoing the logo), and
the metric-tile card has a yellow top-accent bar. Section cards take a warm-gold
(`--sk-color-haygold`) left edge. Status colour stays green (good) / red
(attention) only.

**Full-bleed print, with an in-flow continuation-page top inset.** The
warm-cream page colour reaches every edge — no white printer margin anywhere —
via `@page { margin: 0 }`, the cream on both `html` and `body`, and
`print-color-adjust: exact`. Content on pages 2+ is shifted down **in flow**, not
with a page margin. Two rules make that work and survive a page break:

1. **Never split a top-level block across a page** — `break-inside: avoid` on
   `.tiles`, `.highlights`, `.section` and `table`, and `break-after: avoid` on
   `h2` — so every continuation page begins with a whole block, not a torn one.
2. **Reserve the top space with a transparent top *border*, not a margin.**
   Chromium *drops* a block's top margin when it starts a continuation page but
   *keeps* its border, so `h2` and `.section` carry a `~1.6–1.9rem` transparent
   top border. With `background-clip: padding-box` on the cards, that border
   shows the cream page through it — the content sits lower, the background does
   not turn white. (This is why the earlier `@page { margin-top }` attempt failed:
   Chromium paints the page-margin box white and does **not** propagate the root
   background into it.) The card's warm-gold left accent is drawn by a `::before`
   bar from the content top, so it never stubs into the cream gap.

Trade-off: `break-inside: avoid` can push a whole card to the next page, leaving
cream whitespace at a page bottom. That is intended — cream is easy on the eyes,
and a clean top edge matters more than dense packing.

These are **light-chromed on purpose**: print/PDF is far easier to read light,
so the dark-theme tokens are never used here.

## Typography

- **Display** (`h1`, `h2`, tile numbers): **Falling Sky**, weight 800
  (`--sk-font-display`). The OTFs live in
  `spec-kitty-design/packages/tokens/fonts`; embed them via `@font-face` for a
  fully-branded PDF. Without them the stack degrades to system sans.
- **Mono** (`--sk-font-mono`): **JetBrains Mono** — the eyebrow, the meta line,
  section titles, table headers, `code`, and status pills' cousins. Loaded from
  the same Google Fonts CDN the token package uses.
- **Body**: system sans (`--sk-font-sans`). **Swansea** is the design system's
  secondary reference face — reserve it for long-form, not these one-pagers.
- Scale: title 40px, section heading 24px, tile number 34px, body 15px, lede
  17px, eyebrow/label 12px.

## One-pager slot contract

The one-pager's synthesis step produces exactly one JSON object, the slots the
renderer fills into the template, and nothing else. Every `#NNNN` in any slot
must appear in the collector's `valid_refs`; the renderer fails closed on any
other. Meta-line values come from the collector's `meta`, tile numbers from its
`metrics`, and `method` is copied from `meta.method` (extend it only with true
caveats).

```jsonc
{
  "eyebrow": "SPEC KITTY · EXECUTIVE OVERVIEW",
  "title": "What landed since Friday morning",
  "meta_line": "Window: … · main at <sha> · Repos: …",   // built from meta
  "lede": "1–3 sentence synthesis of the window or scope.",
  "tiles": [{"n": "47", "label": "pull requests merged", "class": ""},
            {"n": "18", "label": "P0 issues still open", "class": "alert"}],
  "highlights_heading": "The bottom line",                // or "Key takeaways"
  "highlights": [{"pill": "SHIPPED", "pill_class": "shipped", "text": "…"},
                 {"pill": "WATCH",   "pill_class": "watch",   "text": "…"}],
  "body_heading": "What shipped, by theme",               // or "By cluster"
  "sections": [{"title": "1. Protecting user work", "count": "8 PRs · 9 P0s",
                "intro": "…", "items": [{"pill": "P0", "text": "…", "refs": "#5050"}]}],
  "decisions_heading": "What's next and needs a decision", // window mode only
  "decisions": [{"item": "…", "status": "PR OPEN", "owner": "the maintainer"}],
  "authors_line": "One maintainer authored 40 of 46 engine PRs; …",
  "method": "<copy meta.method verbatim>"
}
```

The collector's JSON carries `meta` (mode, filters, `main_shas`, the generated
`method` line), `metrics`, `authors`, `pull_requests`, `closed_issues`,
`open_issues` and `valid_refs`. The template dialect is `{{ SLOT }}` for a
scalar, `<!-- @each NAME -->` to repeat a block and `<!-- @if NAME -->` to keep
one when the value is non-empty.

## One-pager layout grammar (fixed order)

0. **Brand mark** — the Spec Kitty logo (`packs/internal/assets/debrief/logo.png`, mirrored from
   `@spec-kitty/tokens`) top-left, ~52px. The PNG carries a light baked
   background; `mix-blend-mode: multiply` dissolves it into the cream so only
   the line-art shows.
1. **Eyebrow** — mono, uppercase, tracked: `SPEC KITTY · EXECUTIVE OVERVIEW`.
2. **Title** — the question answered: *What landed since Friday morning* /
   *Milestone 11 — "4.0.0 release scope": open issues*.
3. **Meta line** — mono, generated from `meta`: window (both timezones), `main`
   SHA, repos / snapshot date. Never hand-typed.
4. **Lede** — 1–3 sentences of synthesis.
5. **Tiles** — one bordered card row of the headline metrics; the
   attention number (open P0s) uses `.n.alert` (red).
6. **Highlights** — "The bottom line" (window) / "Key takeaways" (scope), each
   line led by a pill.
7. **Body sections** — "What shipped, by theme" (window) / "By cluster" (scope),
   each a card with a mono title, a right-aligned count, an intro, and a
   ref-bearing bullet list. 4–6 sections; never more.
8. **Decision table** (window only) — Item / Status / Owner.
9. **Footer** — "Who shipped it" (author attribution) + the generated **Method**
   line.

## Pill vocabulary (the design system's `.sk-tag`)

| Pill | Class | Meaning |
|------|-------|---------|
| `SHIPPED` | `.sk-tag--shipped` (green tint) | landed in this window |
| `WATCH` | `.sk-tag--watch` (red on sky) | open risk / still catching up |
| `P0` | `.sk-tag--p0` (red on sky) | release-blocking item |

Status uses `STATUS`-style words in the decision table
(`ON MAIN, UNTAGGED`, `PR OPEN`, `AWAITING CALL`, `FILED`), mono, muted.

## Voice & content conventions

These apply to both layouts. General report voice (plain words, few em-dashes,
no puffery, every number attributed) comes from the `report-writing` styleguide
and is not repeated here.

- **Name the readers.** A debrief goes to leadership (for example CTO, CEO,
  CPO, Head of QA) and to the maintainers in one document. Ask who it is for if
  the request does not say, and put them on the cover (`FOR`) or in the meta
  line.
- **Write the top for the least technical named reader.** The executive summary
  (or the lede and highlights) must work for someone who knows the product but
  not the code. Module names, gate names, error codes and lane mechanics belong
  in the parts and the appendix. Explain an internal term in one clause the
  first time it appears: "`consolidate`, the command that lands finished work".
- **BLUF, consumer-first.** Lead each bullet with the impact a user/operator
  saw, then the mechanism. Plain language, active voice, concrete before→after.
- **End the summary with the ask.** Close with what the readers must decide,
  each decision next to the fact that forces it. If nothing needs deciding, say
  so in one line.
- **Name the failure class when it fits.** The recurring "silent and exit 0"
  framing (a command that destroys/hides/mis-lands work while reporting success)
  is the house way to describe the most damaging defects. Use it where the
  collected defects are of that kind. Do not force it onto a debrief about
  something else, such as CI runtime.
- **Say what the data does not show.** "A correlation, not a proven cause."
  "Three days and 119 runs: an early signal, not a settled trend." When a claim
  rests on an earlier debrief rather than on this collection, say so in the
  sentence.
- **State uncomfortable facts plainly and once.** A release shipped under a
  waiver, one author on most PRs, more issues opened than closed: give the
  count, put it in Open risks, and do not soften or repeat it.
- **Consumer-impact lens for release scopes.** Foreground consumer-facing,
  silent-false-success defects; hold internal/loud/unreachable ones off the top.
- **Method-footer honesty (non-negotiable):**
  - Every number is queried, stated as such — never estimated.
  - "closed as fixed" (GitHub's reason) ≠ "verified fixed" (a linked PR); say
    *closed* for anything not verified (the #4891 caveat).
  - Impact tags in scope mode are a preliminary read until code-verified — say so.
  - Author attribution comes from the PR author field.

## Promotion (done)

This house style is now shipped as an activatable styleguide artifact in the
internal doctrine pack: `packs/internal/styleguides/executive-debrief.styleguide.yaml`
(it *refines* `report-writing` and is *suggested* by the
`executive-debrief-generation` procedure, which is in `org-charter.yaml`'s
`required_procedures`). Internal doctrine never ships to consumers, it governs how
*we* report. That YAML is the durable, activatable doctrine; this page is the
detailed layout, palette and print-treatment reference it links to. Converging the
one-pager renderer's brand assets (fonts/logo/palette) with the canonical
`spec-kitty-branded-pdf` generator is tracked as follow-up #5273.
