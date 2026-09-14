---
description: Interpret gathered evidence into traceable findings, naming limitations and alternatives honestly
---
# Findings Synthesis — Interpret the Evidence

**Mission type**: `research` | **Step**: `synthesis` (sequence index 3, depends on `gathering`) | **Agent profile**: `researcher-robbie`

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/findings.md`). Never refer to a file by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.**

## User Input

```text
$ARGUMENTS
```

Use `$ARGUMENTS` to focus which findings to prioritize, but every claim must still trace to `research/evidence-log.csv` — synthesis interprets evidence, it does not invent it.

## Bootstrap

```bash
spec-kitty charter context --action synthesis --json
```

## What This Step Produces

`kitty-specs/<mission>/findings.md`. This is the gate on `synthesis -> output` (`mission.yaml`: `artifact_exists("findings.md")`). If gathering turns out to be inadequate for a real conclusion, use the `gather_more` transition back to `gathering` rather than writing a findings document propped up on thin evidence.

## Distinguish Evidence from Interpretation

- Raw evidence rows live in `research/evidence-log.csv`. Synthesis **interprets** that evidence — naming patterns, identifying themes, drawing conclusions.
- Keep the line between the two visible. A synthesis claim must be reframable as "the evidence shows X, and from X we conclude Y." If the evidence step is missing, the claim is unmoored.
- Cite **every** synthesis claim back to the evidence row(s) that support it, per `research-citation-discipline`. Conclusions without traceable evidence are opinions, not findings.

## Trace Conclusions to Evidence Rows

- Reference evidence by row ID (or stable identifier) when stating findings in `findings.md`. Reviewers must be able to follow the trail without re-reading every source.
- When a conclusion rests on multiple evidence rows, list them all. When it rests on weak or low-confidence evidence, say so explicitly rather than smoothing it over.
- A pattern that appears in only one source is a hypothesis, not a finding — distinguish them in the prose.

## Apply Dialectical Testing to Load-Bearing Claims

For any finding that will drive a real decision downstream, run the `dialectic-research` tactic before writing it up as settled: state the finding as one falsifiable proposition, then deliberately build the strongest case against it from the same evidence base before accepting it. A finding that survives its own refutation attempt is a stronger finding; a finding that does not survive is either weakened with an honest confidence label or dropped back to `gathering` for more evidence.

## Identify Limitations and Threats to Validity

- Use a premortem mindset: "If this synthesis turns out to be wrong, what would the failure look like?" Write the candidate failure modes down.
- Document **limitations** — what the methodology could not see, what the source set under-represents, what time period the evidence is bounded by.
- Document **threats to validity** — selection bias, publication bias, confounders, alternative explanations.
- Be explicit about **confidence**. A synthesis that asserts everything with equal weight has not actually done synthesis.

## Alternative Interpretations

- For each major finding, consider at least one alternative interpretation that is consistent with the same evidence.
- If an alternative is ruled out, document why — what evidence rules it out.
- If alternatives cannot be ruled out, name them as open questions rather than burying the ambiguity.

## What This Phase Does NOT Cover

Synthesis produces interpreted findings with traceable evidence. It does **not**:

- Re-open scoping or methodology decisions (locked).
- Add new sources to the register — if a critical gap surfaces, use the `gather_more` transition back to `gathering` rather than quietly filling the gap here.
- Format the publication-ready output (`output` step's job).

If synthesis discovers the evidence base is inadequate to answer the research question, surface that as a finding and route back to gathering — do not paper over it with weakly-supported conclusions.

## What To Do

1. Read `research/evidence-log.csv` and `research/source-register.csv` in full.
2. Code and categorize findings; identify recurring patterns and themes.
3. For each candidate finding: state it as evidence-plus-interpretation, cite the supporting row IDs, and — for load-bearing claims — run the dialectic-research check above.
4. Write `kitty-specs/<mission>/findings.md`: findings with citations, limitations, threats to validity, and at least one alternative interpretation per major finding.
5. If evidence is insufficient for a conclusion the spec requires, invoke the `gather_more` transition back to `gathering` rather than weakening the finding to fit.
6. Record synthesis decisions (excluded evidence, resolved contradictions) per `003-decision-documentation-requirement`.
7. Commit `findings.md` per the `029-agent-commit-signing-policy` / `033-targeted-staging-policy` directives.

## Quality Gates

- Every conclusion cites at least one evidence row.
- Limitations and threats to validity are explicit, not implicit.
- At least one alternative interpretation is considered for each major finding.
- Confidence levels propagate from evidence to conclusion — low-confidence evidence cannot ground a high-confidence finding.
- `findings.md` exists **and** is substantive — an `artifact_exists("findings.md")` pass with unsupported claims fails this step's intent even though it clears the machine gate.
