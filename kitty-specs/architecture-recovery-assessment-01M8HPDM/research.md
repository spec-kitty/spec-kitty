# Research: Architecture recovery assessment

The research for this plan is held in `docs/reports/architecture-recovery-assessment/2026-11-28/`. This file is its index.

## Findings

| Question from the specification | Where it is answered |
|---|---|
| Which capabilities do documented needs and user journeys require? | `needs/needs-and-journeys.md`, `needs/capabilities.csv` (32 capabilities) |
| For each mechanism: does the need justify the complexity, and is it a remnant? | `mechanisms/M1.md` to `M8.md`, each with an evidence table |
| Where do mechanisms exist only to compensate for other mechanisms? | `duplication/catalogue.md` (46 cases), and section 7 of each mechanism assessment |
| What is the best reason for each mechanism to stay? | `challenge/steelman.md`, `steelman.csv` (36 items) |
| What could a simpler architecture be? | `candidates/CA.md` (delete-first), `candidates/CB.md` (consolidate-in-place) |
| Do the candidates survive a check against needs, the steelman and the code? | `challenge/candidate-challenge.md`, `forks.csv`, `reference-checks.csv` |

## Method

One assessor per mechanism, a cross-cutting duplication hunt, a needs analysis from documented journeys, a steelman, two independent candidate designs and one challenge with checks against the code at head. Evidence is representative, with source references. The rulings that bound the work are in `00-mandate-and-rulings.md`.

## Sources

Code at head of the five primary repositories and read-only clones of the supplementary ones; the Wayfinder reconnaissance under `docs/reports/wayfinder-reconnaissance/2026-11-28/`.
