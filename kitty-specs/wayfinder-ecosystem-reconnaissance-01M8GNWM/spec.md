# Research Specification: Wayfinder ecosystem architectural reconnaissance

**Mission Branch**: `claude/spec-kitty-arch-reconnaissance-fdeicj`
**Created**: 2026-11-28
**Status**: Approved by the human architect
**Research Type**: Empirical Study

## Research Question & Scope

**Primary Research Question**: What is the intended, observed and evolving architecture of the Spec Kitty ecosystem, and what architectural knowledge and assurance would a separate repository (codename Wayfinder) have to provide?

**Sub-Questions**:

1. What do the ecosystem's records say each component is responsible for, and which decisions are current?
2. What dependency structure does the code show, in Python and Java, and how does it compare with the recorded intent?
3. How did change coupling evolve, and what did the convergence of the two lines change?
4. How independent is each capability on the logical, contract, source, distribution and deployment dimensions?
5. Which mechanisms assure the architecture, and what do they detect?
6. Where do the responsibilities of executing agent work sit?

**Scope**:

- **In Scope**: the five primary repositories at the revisions pinned in the report folder, the revisions and released artefacts core integrates, and thirteen supplementary repositories read-only.
- **Out of Scope**: remediation, implementation, changes to code, tests, rules, CI or existing documentation; any implementation of Wayfinder.
- **Boundaries**: core history from 2026-01 to 2026-11-28; earlier history as baseline only.

**Expected Outcomes**:

- The twelve deliverables of the design brief, as findings with evidence, a synthesis, an adversarial review, a post-hoc evaluation, a dialectical review and a consolidated report.
- Input for decisions that stay with the human architect.

## Research Methodology Outline

The method is fixed in the approved pre-registration and is not repeated here:

- `docs/reports/wayfinder-reconnaissance/2026-11-28/01-pre-registration.md`: revision model, measures, thresholds, samples, controls.
- `docs/reports/wayfinder-reconnaissance/2026-11-28/00-rulings-and-deviations.md`: the architect's rulings and the authorised deviations, including running the workstreams outside the mission runtime.
- `docs/reports/wayfinder-reconnaissance/2026-11-28/04-approval-and-dispatch.md`: approval, stages and dispatch.

## Deliverable Location

All findings, evidence and reports are in `docs/reports/wayfinder-reconnaissance/2026-11-28/`. This Mission directory holds only this specification and the Mission metadata. No work package is created, because the workstreams do not run through the mission runtime (authorised deviation D-1).

## Constraints

- Hypotheses are hypotheses. A disproved hypothesis is a successful outcome.
- Recorded intent, observed implementation, approved plans and proposals are kept apart.
- Experiments run in disposable environments only.
- The human architect decides intent, priorities, exceptions and any later implementation.
