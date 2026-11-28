# Plan Specification: Architecture recovery assessment

**Plan Branch**: `claude/spec-kitty-arch-reconnaissance-fdeicj`
**Created**: 2026-11-28
**Status**: Draft
**Input**: The human architect's change of objective of 2026-11-28, recorded with the rulings in `docs/reports/architecture-recovery-assessment/2026-11-28/00-mandate-and-rulings.md`.

## Problem Statement *(mandatory)*

Spec Kitty's dependency rules hold, but structural compliance is not architectural coherence. The architect needs to know which mechanisms deserve to remain, what a simpler coherent architecture would be for the 4.0 release, what obstructs it, and how to reach it in steps while the product keeps working. The earlier reconnaissance did not assess duplicated domain logic, competing mechanisms, bypassed extension points or accidental complexity.

## Goals & Non-Goals *(mandatory)*

### Goals

- Establish necessity before implementation quality for: worktrees, lanes, mission-type configuration, Mission and work-package lifecycle, Charter integration, event handling, execution coordination, consolidation with its approval-evidence rules, and upgrade migrations with compatibility shims.
- Produce a desired architecture from the capabilities and quality attributes actually required, with viable alternatives.
- Produce an obstruction map that links present implementation arrangements to that architecture, with source references.
- Recommend a provisional disposition per capability or mechanism: retain, simplify, consolidate, replace, remove, investigate further.
- Produce an incremental roadmap with sequencing, prerequisites, risks and early deletions.
- Propose constraints and acceptance scenarios that would preserve the resulting design, and list the decisions that need the architect.

### Non-Goals

- No production implementation, remediation, issue or pull request.
- No reconstruction of causal history and no attribution to humans or agents.
- No repeat of the reconnaissance's experimental apparatus.
- No design of Wayfinder; its scope follows from what this work finds.
- No treatment of existing formats, Missions, APIs, upgrade paths or recorded decisions as fixed constraints.

## Stakeholders & Decision Owners *(mandatory)*

| Stakeholder | Interest / Concern | Decision Authority |
|-------------|---------------------|---------------------|
| Human architect (human in charge) | A credible, actionable simplification proposal with stated uncertainties | Decides intent, dispositions, priorities and any later implementation |
| Maintainers and agents working on 4.0 | Which mechanisms to stop investing in, and in what order to simplify | Advised; act only after the architect decides |
| Outside observer | Interprets the result | None |

## Constraints *(mandatory)*

- **Time-box**: one working session; proportionate evidence, representative not exhaustive.
- **Resourcing**: the coordinator and profile-loaded subagents; read-only access to the repositories; experiments only in disposable copies.
- **Dependencies**: the reconnaissance findings under `docs/reports/wayfinder-reconnaissance/2026-11-28/`, freely reusable.
- **Other**: additive documentation only, on the research branch. Principles to preserve, open to challenge: Human in Charge, responsible delegation, explicit responsibility ownership, independent evolvability, governed Mission coordination.

## Success Criteria *(mandatory)*

1. Each of the nine mechanisms has a stated need, its essential complexity, its present mechanisms, a necessity judgement, at least two simpler alternatives, and a blast radius, with source references.
2. Every disposition carries rationale, evidence, expected benefit, migration obstacles, risks and confidence, and separates decision-material uncertainty from what an experiment can settle.
3. The candidate architecture distinguishes essential capabilities from present mechanisms and has been challenged by an independent perspective; disagreements are kept.
4. The obstruction map gives representative source references for each obstruction and names the roadmap step that removes it.
5. The roadmap names at least the first reversible experiments and the deletions available early.
6. The architect can decide what to do next from the report alone.

## Open Questions *(carried into Research)*

- Which capabilities do documented needs and user journeys actually require?
- For each mechanism: does the need justify the complexity, and is it a remnant of an older design?
- Where do mechanisms exist only to compensate for other mechanisms?
- Which simplifications are reversible experiments and which touch persistent data or public contracts?

## Out of Scope

- Hosted and SaaS surfaces removed from core.
- Performance and security assessment beyond what a disposition needs.
- Brand, website and design repositories.
