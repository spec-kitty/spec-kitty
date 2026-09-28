# Debrief house style — "WTF happened" executive one-pagers

**Status:** initial house style (seeded from the design system; not yet a
formal doctrine artifact — see *Promotion* below).
**Applies to:** the reports produced by the `spk-report-debrief` skill — the
time-window "what landed since <T>" debrief and the milestone/label open-issue
snapshot. Examples: [`examples/`](examples/).

## Provenance — this is the design system's style, not ad-hoc

The look is taken from **`@spec-kitty/tokens`** in the sibling
**`spec-kitty-design`** repo (`packages/tokens/src/tokens.css`, ADR-003
`--sk-<category>-<name>` naming). The debrief template
(`scripts/reporting/debrief_template.html`) inlines a **curated light-theme
subset** of those tokens; when a value here and a token there ever disagree,
the token package wins — re-sync the subset, don't fork it.

## Palette (light theme — these are printed one-pagers)

| Role | Token | Value |
|------|-------|-------|
| Signature primary | `--sk-color-yellow` | `#F5C518` |
| Link / accent (light) | `--sk-color-sage` | `#4F8F4F` |
| Success · **SHIPPED** | `--sk-color-green` | `#8FCB8F` on `--sk-surface-tint-mint` `#E8F4E8` |
| Alert · **WATCH / P0** | `--sk-color-red` | `#E97373` on `--sk-surface-tint-sky` `#E4EDF8` |
| Page | `--sk-surface-page` | `#F8F5EC` (warm cream) |
| Card | `--sk-surface-card` | `#FFFFFF` |
| Chip rail | `--sk-surface-pill` | `#ECE7D8` |
| Ink / body / muted / label | `--sk-fg-default/body/muted/subtle` | `#1A1A14` / `#2A2A22` / `#5C5C52` / `#8A8A7E` |
| Hairline / card border | `--sk-border-default/strong` | `#EAE4D2` / `#D6CFB9` |

Yellow is the brand signature — use it sparingly (it is the CTA/logo colour),
not for status. Status colour is green (good) / red (attention) only.

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

## Layout grammar (fixed order)

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

- **BLUF, consumer-first.** Lead each bullet with the impact a user/operator
  saw, then the mechanism. Plain language, active voice, concrete before→after.
- **Name the failure class.** The recurring "silent and exit 0" framing (a
  command that destroys/hides/mis-lands work while reporting success) is the
  house way to describe the most damaging defects — use it.
- **Consumer-impact lens for release scopes.** Foreground consumer-facing,
  silent-false-success defects; hold internal/loud/unreachable ones off the top.
- **Method-footer honesty (non-negotiable):**
  - Every number is queried, stated as such — never estimated.
  - "closed as fixed" (GitHub's reason) ≠ "verified fixed" (a linked PR); say
    *closed* for anything not verified (the #4891 caveat).
  - Impact tags in scope mode are a preliminary read until code-verified — say so.
  - Author attribution comes from the PR author field.

## Promotion (deferred)

Once this has driven a handful of real reports and the grammar has settled,
promote it to a **styleguide artifact in the internal doctrine pack**
(`packs/internal/`, never `built-in` — it governs how *we* report, not
consumers), and run `spec-kitty doctrine regenerate-graph`. This document is the
seed; the internal-pack artifact is the durable, activatable form.
