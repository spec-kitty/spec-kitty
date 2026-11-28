# Review: Architecture recovery assessment

The review of this plan is held in `docs/reports/architecture-recovery-assessment/2026-11-28/challenge/`. This file is its index. The plan is a proposal for the human architect; this review does not approve it.

## Summary

- `steelman.md`, `steelman.csv`: the best reason for each mechanism proposed for simplification or removal (36 items; for 7 a recorded failure would return).
- `candidate-challenge.md`, `forks.csv`, `reference-checks.csv`: both candidate architectures checked against the needs, the steelman, the code at head and the principles. Seven major findings (F1 to F7); 19 of 20 sampled source references true; of 20 load-bearing claims 13 true, 5 partly true, 2 false.
- `04-candidate-architecture.md` section 5 answers each major finding. Two of the four structural choices stay conditional on decisions D2 and D3.

## Decisions

No decision is taken here. The 27 open decisions are in `09-open-decisions.md`.

## Limits

Evidence is representative. The command layer and about forty packages had no assessor of their own. The Java services were read, not built or run. Sizes of deletions are estimates.
