---
name: spk-report-debrief
description: >-
  Generate a "WTF happened" executive debrief for Spec Kitty — a one-page
  overview of what shipped in a time window, or the open-issue state of a
  milestone/label. Triggers: "what landed since <time>", "WTF happened
  to/with/since <X>", "debrief the weekend", "milestone <N> overview",
  "exec overview of open issues", "write up what shipped". Two modes: a
  time-window "what landed" report and a milestone/label "open issues"
  snapshot. Runs as an Op (dispatch), not a Mission. Does NOT invent numbers:
  a deterministic collector owns every count; this skill only clusters,
  narrates and labels the collected facts, then renders the fixed template.
---

# spk-report-debrief — executive debrief generator

Produces the two report shapes in `docs/development/reporting/examples/`
(the "What landed since Friday morning" window report and the "Milestone 11
overview" backlog snapshot). Both are the **same pipeline** with a different
scope selector. This is an **in-house / maintainer** tool — it reports on how
the core team's own repos are moving; it never ships to consumers.

## Two layouts

The house style ([`debrief-styleguide.md`](../../../docs/development/reporting/debrief-styleguide.md))
defines two layouts over the same collected facts:

- **One-pager**: tiles, pills and cluster cards from the fixed template. Use it
  when the counts and a few labelled clusters answer the question.
- **Long-form debrief**: a multi-page branded document (cover, executive
  summary, parts, open risks, appendix) written as one Markdown file. Use it
  when the readers need a mechanism explained, a trend shown, or a decision
  prepared, or when the requester names several readers (CTO, CEO, CPO, Head of
  QA, maintainers) or points at an earlier long-form debrief as the example.

Ask who the debrief is for if the request does not say. The readers go on the
cover (`FOR`) and decide how plain the summary must be.

## When to use

Trigger on any "what happened / what shipped / what's open" ask over a repo
scope: a weekend debrief, a since-a-tag summary, a milestone status one-pager,
an exec overview for the operator. It is an **Op, not a Mission** (one sitting,
one deliverable, no reviewable work packages, no review gate) — per
`DIRECTIVE_053`, open it with `spec-kitty dispatch` and close it with the real
outcome. Do **not** spin up a full mission for a report.

## The three stages (never collapse them)

The reports carry a **Method** footer for a reason: the facts are queried and
labelled as such, and the editorial judgement is fenced off. Keep that split.

### Stage A — Collect (deterministic, zero judgement)

Run the collector; it owns every number. **You never count by hand or from
memory.**

```bash
# window mode ("what landed since <T>") — across both repos
python scripts/reporting/collect_debrief.py window \
  --repo spec-kitty/spec-kitty --repo spec-kitty/spec-kitty-planning \
  --since 2026-09-26T06:00:00Z --until 2026-09-28T05:50:00Z \
  --out /tmp/debrief.json

# scope mode ("open issues in milestone N")
python scripts/reporting/collect_debrief.py scope \
  --repo spec-kitty/spec-kitty --milestone 11 --out /tmp/milestone.json
```

The JSON it emits is the **sole input** to Stage B. Key fields:
`meta` (mode, filters, `main_shas`, generated `method` line), `metrics` (the
tiles), `authors`, `pull_requests`, `closed_issues`, `open_issues`, and
`valid_refs` — the set of every `#ref` seen.

### Stage B — Synthesize (LLM judgement, under contract)

Load governance context first, then read **only** the Stage-A JSON:

```bash
spec-kitty charter context --action review \
  --include agent-profile:synthesizer-sam --include agent-profile:comms-cleo
```

Apply the standing rubrics — the **launch-blocker customer-impact lens**
(release/MVP reports foreground consumer-facing, silent-false-success defects)
and the **issue-valuation rubric** (irreversibility × silence × blast radius).
Produce this structured object (the render slots), nothing else:

```jsonc
{
  "eyebrow": "SPEC KITTY · EXECUTIVE OVERVIEW",
  "title": "What landed since Friday morning",
  "meta_line": "Window: … · main at <sha> · Repos: …",   // build from meta
  "lede": "1–3 sentence synthesis of the window/scope.",
  "tiles": [{"n": "47", "label": "pull requests merged", "class": ""},
            {"n": "18", "label": "P0 issues still open", "class": "alert"}],
  "highlights_heading": "The bottom line",                // or "Key takeaways"
  "highlights": [{"pill": "SHIPPED", "pill_class": "shipped", "text": "…"},
                 {"pill": "WATCH",   "pill_class": "watch",   "text": "…"}],
  "body_heading": "What shipped, by theme",               // or "By cluster"
  "sections": [{"title": "1. Protecting user work", "count": "8 PRs · 9 P0s",
                "intro": "…", "items": [{"pill": "P0", "text": "…", "refs": "#5050"}]}],
  "decisions_heading": "What's next and needs a decision", // window mode only
  "decisions": [{"item": "…", "status": "PR OPEN", "owner": "Stijn"}],
  "authors_line": "Stijn authored 40 of 46 engine PRs; …",
  "method": "<copy meta.method verbatim; extend only with true caveats>"
}
```

**Long form.** Instead of the slot object, write one Markdown file in the
styleguide's fixed order: executive summary (bottom line, one headline table,
"What happened" as three to five numbered claims, "What we need from
leadership"), lettered parts, an open-risks table (Risk / Why it matters /
Issue / Owner), and an appendix with the Method line, definitions, data files
and caveats. Write the summary for the least technical named reader and explain
an internal term in one clause on first use. If you need facts the collector
does not return (open P0s, milestone counts, nightly runs, git statistics),
read each with `gh`/`git` into a file under `raw/` next to the collector JSON
and name those files in the appendix. Verify each claim that is not a plain
count (an owner, an author, "N PRs touch X") against the collected files before
it goes in.

**Hallucination guard (non-negotiable).** Every `#NNNN` you write in any slot
MUST appear in `valid_refs`. Before rendering, diff your output's refs against
`valid_refs`; if any ref is not in the set, you invented it — remove it or fix
it. You may cluster, narrate, prioritise and label; you may not add a number,
an issue, or a PR the collector did not return. For the long form the allowed
set is `valid_refs` plus the numbers in your saved `raw/` files; the renderer
does not check it for you, so run the diff yourself before rendering.

**Honesty rules baked into the examples:**
- "Closed as fixed" is GitHub's `state_reason`, not proof of a shipped fix.
  Where `verified_fixed` is null, say "closed", not "fixed", for a specific
  issue you call out (the #4891 caveat in the window example).
- In scope mode, impact tags are a *preliminary read of each issue's own
  description* until verified against the code — say so in the footer, and
  offer a research-squad verify pass before dropping that caveat.
- Author attribution comes from the PR author field, not a guess.

### Stage C — Render (deterministic look)

Fill `scripts/reporting/debrief_template.html` from the Stage-B object
(`{{ SLOT }}` scalars, `<!-- @each NAME -->` repeats). Then print to PDF with a
headless browser if a PDF is wanted. The template is light-theme, print-sized;
do not restyle per report — the consistency is the point.

**Long form.** Render the Markdown with the canonical branded generator, never
a hand-built cover or stylesheet:

```bash
python packs/internal/assets/spec-kitty-branded-pdf.py \
  --input body.md --output debrief.pdf \
  --eyebrow "Spec Kitty · Executive Debrief" \
  --title "WTF happened<br>since <T>" --subtitle "…" --lede "…" \
  --footer-center "<SHORT LABEL> · <YYYY-MM-DD>" \
  --meta "AS OF=<date>" --meta "SCOPE=<owner/repo>" --meta "FOR=<readers>"
```

The generator draws `#` as a part title and `##` as a subsection, so the body
starts at `# Executive summary`. It needs `pandoc`, WeasyPrint and the sibling
`spec-kitty-design` repo. Look at every page of the result before handing over.

The look is the **design system's**, not ad-hoc: tokens (colours, type, pills)
come from `@spec-kitty/tokens` in the sibling `spec-kitty-design` repo. The
house style — palette, typography, layout grammar, pill vocabulary and the
voice/Method-honesty rules — is documented in
[`docs/development/reporting/debrief-styleguide.md`](../../../docs/development/reporting/debrief-styleguide.md).
Follow it; re-sync the template's token subset from the package rather than
forking values.

## Where the output goes

A debrief is **handed over, not committed**.

- Send the PDF to the operator. Keep the collector JSON, the synthesis, charts
  and any one-off collector script in the gitignored `work/` directory.
- **Never commit a PDF**, and never open a pull request into `spec-kitty` (or
  any product repository) for a debrief. `docs/reports/` in `spec-kitty` holds
  engineering analyses, not executive debriefs; it is not a precedent.
- When the operator wants the findings kept (open risks, a confirmed waiver, a
  decision), write a short Markdown note under `spec-kitty-planning`
  `reference/` (`<TOPIC>-DEBRIEF-<YYYY-MM-DD>.md`): findings, as-of and refs only,
  no PDF and no raw-data dump.
- If a request asks for a different placement, raise the conflict with the
  operator before committing anything.

## Guardrails checklist (run before handing over the report)

- [ ] Every tile or table number came from `metrics` or a saved `raw/` file — none typed by hand.
- [ ] Every `#ref` in the rendered report is in `valid_refs` (long form: or in a saved `raw/` file).
- [ ] The readers are named, and the summary ends with what they must decide (long form).
- [ ] The Method footer names the exact window/scope + as-of (from `meta`).
- [ ] "fixed" vs "closed" distinction honoured for any issue singled out.
- [ ] scope-mode impact tags marked preliminary unless a verify pass ran.
- [ ] Nothing was committed to a product repository; the PDF went to the operator.
- [ ] The Op is closed with `spec-kitty profile-invocation complete … --outcome done`.

## Doctrine home

The house style is shipped as internal doctrine (never ships to consumers):
- `packs/internal/styleguides/executive-debrief.styleguide.yaml` — the activatable
  styleguide, refining `report-writing`.
- `packs/internal/procedures/executive-debrief-generation.procedure.yaml` — the
  collect → synthesize → render → review workflow, in `org-charter.yaml`'s
  `required_procedures`.

This SKILL orchestrates; that doctrine is the durable authority it points at, and
[`docs/development/reporting/debrief-styleguide.md`](../../../docs/development/reporting/debrief-styleguide.md)
is the detailed palette/print-treatment reference. Remaining follow-ups: per-PR CI
enrolment of `tests/reporting/` (#5275) and brand-asset convergence with the
canonical `spec-kitty-branded-pdf` generator (#5273).
