---
description: Publish a peer-review-ready report that stays faithful to findings and sources
---
# Publication Output — Prepare and Approve the Report

**Mission type**: `research` | **Step**: `output` (sequence index 4, depends on `synthesis`) | **Agent profile**: `reviewer-renata`

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/report.md`). Never refer to a file by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.**

## User Input

```text
$ARGUMENTS
```

Use `$ARGUMENTS` to focus formatting or audience concerns; it does not license introducing content that is not already in `findings.md`.

## Bootstrap

```bash
spec-kitty charter context --action output --json
```

## What This Step Produces

`kitty-specs/<mission>/report.md`, plus the `publication_approved` gate event. `output -> done` (`mission.yaml`) requires `gate_passed("publication_approved")` — a **review event**, not a rendering step. The run engine records that event only after the operator has verified the readiness checks below; writing `report.md` alone does not advance the mission.

## Publication Readiness

- A reader who arrives at `report.md` without `research/source-register.csv` or `research/evidence-log.csv` must still be able to evaluate the rigor of the work — the report stands on its own.
- The published artifact and the underlying evidence base must be **consistent**: every claim in the report traces to an evidence row, and every high-confidence evidence row that informs a finding is reflected in the report.
- Treat `publication_approved` as a review gate you earn, not a checkbox you tick — it exists specifically so a rushed or unfaithful report cannot reach `done`.

## Citation Completeness (research-citation-discipline)

- Every citation referenced in `report.md` must appear in `research/source-register.csv`, in the chosen format (BibTeX or APA).
- DOIs and URLs in the report match those in the register; access dates are preserved.
- Inline citations, footnotes, and bibliography are internally consistent — reviewers cross-check these, and inconsistencies erode trust in the whole report.
- Where the underlying evidence carried an explicit confidence tier, that tier (or its practical consequence — "treated as a secondary claim") survives into the report's prose; do not launder a low-confidence source into confident-sounding text.

## Methodology Clarity for Peer Review

- `report.md` describes the methodology in enough detail that a peer reviewer can assess whether the conclusions are warranted by the design (or clearly links to `plan.md` for the full detail).
- Inclusion and exclusion criteria, search strategy, and quality assessment approach appear in the report or a clearly-linked appendix.
- Limitations and threats to validity from `findings.md` are carried forward into the report — suppressing them here is a fidelity violation, not an editorial polish.

## Specification Fidelity (010-specification-fidelity-requirement)

- The output must be **faithful** to `findings.md` and the underlying evidence. Do not introduce findings that are not supported by `research/evidence-log.csv`.
- Do not soften limitations or drop alternative interpretations to make the narrative read more cleanly.
- If a late edit changes a finding, the supporting evidence row must change with it — drift between `report.md` and `findings.md` is a fidelity break the reviewer must catch.

## What This Phase Does NOT Cover

The output step publishes the research. It does **not**:

- Re-scope the question (locked at `scoping`).
- Re-design methodology (locked at `methodology`).
- Add new sources or evidence — that is `gathering`'s job; if late discovery is genuinely needed, route back through the proper phase rather than smuggling a new citation into the report.
- Re-synthesize findings from raw evidence — `output` consumes `synthesis`'s output, it does not redo the interpretation.

If preparing the output reveals that synthesis is incomplete or unfaithful to the evidence, hand back to `synthesis` — do not patch over it during formatting.

## What To Do

1. Read `kitty-specs/<mission>/findings.md` and `research/source-register.csv` in full.
2. Draft `kitty-specs/<mission>/report.md`: verify the publication candidate matches `findings.md` and every cited source.
3. Confirm every claim traces to a `research/source-register.csv` row and every source is cited (citation completeness).
4. Assess clarity, methodology disclosure, and risk of misinterpretation for peer review.
5. Once the readiness checks above pass, record the `publication_approved` gate event through your harness's review mechanism — this is what unblocks `output -> done`, not the file write alone.
6. Commit `report.md` with co-author attribution per the `029-agent-commit-signing-policy` / `033-targeted-staging-policy` directives.

## Quality Gates

- All citations in the report appear in the source register and resolve.
- Methodology is described at peer-review fidelity.
- Limitations and threats to validity are present, not hidden.
- Findings in the report are consistent with `findings.md`; no claim is unsupported.
- The artifact is in a form a peer reviewer would accept: proper structure, citations, abstract, conclusions.
- `publication_approved` is recorded as an explicit review outcome, not inferred from the file existing.
