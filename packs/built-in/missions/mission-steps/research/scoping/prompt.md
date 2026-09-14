---
description: Frame the research question, boundaries, and success criteria for a Deep Research Kitty mission
---
# Research Scoping — Define the Question

**Mission type**: `research` | **Step**: `scoping` (sequence index 0) | **Agent profile**: `researcher-robbie`

**Path reference rule:** When you mention directories or files, provide either the absolute path or a path relative to the project root (for example, `kitty-specs/<mission>/spec.md`). Never refer to a file by name alone.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). It is the seed for the research question — refine it, do not discard it.

## Bootstrap

Before drafting anything, load the action-scoped charter context so the directives and tactics below are pulled with their current text, not this file's paraphrase:

```bash
spec-kitty charter context --action scoping --json
```

## What This Step Produces

`kitty-specs/<mission>/spec.md`, rendered from the `research` mission type's `spec` artifact template (`research-spec-template.md`). This is the **only** gate on the `scoping -> methodology` transition (`mission.yaml`: `artifact_exists("spec.md")`) — the mission cannot advance until this file exists and reads as a real specification, not a scaffold.

## Core Authorship Focus

- Frame the **research question** precisely. A good question is answerable, falsifiable where possible, and bounded — a reader must be able to restate it without referring back to context.
- Distinguish the **primary research question** from supporting **sub-questions**; capture both in `spec.md`.
- State **what is in scope** and **what is explicitly out of scope**. Boundaries by time period, geography, domain, or population belong here, not in a later phase.
- Identify **expected outcomes**: what artifacts will the research produce (`findings.md`, `report.md`, a decision record), and how will results be applied?
- Name the **research type** up front — Literature Review, Empirical Study, Case Study, or Meta-Analysis. The type drives the methodology phase's framework choice, but naming it is a scoping decision.

## Stakeholders and Constraints

- Identify the **stakeholders** for the research outcome — who will read it, who will act on it, who is accountable for the questions it answers.
- Surface **constraints** early: time frame, available databases, budget, access restrictions, ethical considerations. A constraint invisible at scoping time becomes a methodology surprise later — write it down now.

## Success Criteria Standards

Success criteria in `spec.md` must be:

1. **Measurable** — e.g., "Review at least 50 peer-reviewed sources", "Identify 3+ validated patterns".
2. **Methodology-agnostic at the question level** — the criterion describes the research outcome, not the gathering technique (that belongs to methodology).
3. **Verifiable** — another researcher can determine whether the criterion was met from the published artifacts alone.

## Applying dialectic-research Early

Where the seed question already implies a preferred answer, apply the `dialectic-research` tactic's framing discipline now, before methodology locks a one-sided approach: state the claim as a single falsifiable proposition, and note in `spec.md` what evidence would corroborate it versus what would refute it. This does not require running the dialectic yet — it requires writing a question that a dialectic *could* be run against.

## What This Phase Does NOT Cover

Scoping produces the question, scope, stakeholders, constraints, and outcome targets. It does **not**:

- Design the research methodology in detail (`methodology` step's job).
- Register sources or extract evidence (`gathering` step's job).
- Synthesize findings or draw conclusions (`synthesis` step's job).
- Prepare publication-ready output (`output` step's job).

If a scoping deliverable starts specifying search strings, citation formats, or analysis frameworks, that work belongs to methodology. Hand off cleanly rather than pre-deciding it here.

## What To Do

1. Read the seed question in `$ARGUMENTS` and any prior mission context in `kitty-specs/<mission>/`.
2. Resolve `research-spec-template.md` (via `spec-kitty specify --mission-type research`, already invoked by mission creation) and fill every bracketed placeholder in `kitty-specs/<mission>/spec.md` with real content — no placeholder survives to commit.
3. Write the primary research question and sub-questions, the in/out-of-scope boundaries, the research type, expected outcomes, stakeholders, and constraints.
4. Write measurable, methodology-agnostic, verifiable success criteria (see standards above).
5. Record any scoping decision with a visible trade-off (e.g., "why this research type over an alternative") per the `003-decision-documentation-requirement` directive.
6. Commit `spec.md` to the mission branch, per the `029-agent-commit-signing-policy` / `033-targeted-staging-policy` directives.

## Quality Gates

- The research question is unambiguous and a reader can restate it without referring back to context.
- Scope boundaries are explicit; there is no unresolved `[NEEDS CLARIFICATION]` marker on the primary question itself.
- Expected outcomes are tied to stakeholder needs.
- Any unresolved ambiguity is captured as an explicit assumption, not buried in vague prose.
- `spec.md` exists and is substantive — the `artifact_exists("spec.md")` gate is necessary but not sufficient; a scaffold with unfilled placeholders does not satisfy this step's intent even if it satisfies the machine gate.
