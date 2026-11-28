# Plan: Architecture recovery assessment

The plan is held in `docs/reports/architecture-recovery-assessment/2026-11-28/`. This file is its index. Nothing in it is approved and no work item is created; the human architect decides.

## Summary

A recommended simplified architecture for Spec Kitty 4.0, the obstructions to it, a disposition for each capability and mechanism, and an incremental roadmap. Two of the four structural choices of the recommended architecture are conditional on decisions of the architect.

## Deliverables

| # | Deliverable | File |
|---|---|---|
| 1 | Current capability and responsibility map | `01-capability-and-responsibility-map.md`, `.csv` |
| 2 | Essential versus accidental complexity | `02-essential-vs-accidental-complexity.md` |
| 3 | Semantic duplication and competing mechanisms | `03-duplication-and-competing-mechanisms.md`, `.csv` |
| 4 | Candidate simplified architecture, with alternatives | `04-candidate-architecture.md` |
| 5 | Obstruction map | `05-obstruction-map.md`, `.csv` |
| 6 | Capability dispositions | `06-capability-dispositions.md`, `.csv` |
| 7 | Incremental remediation roadmap | `07-remediation-roadmap.md` |
| 8 | Architectural constraints and acceptance scenarios | `08-constraints-and-acceptance-scenarios.md` |
| 9 | Outstanding decisions for the architect | `09-open-decisions.md` |

## Decisions

The decisions that need the architect are D1 to D22 in `09-open-decisions.md`, in the order of how much each unblocks, each with the default the roadmap assumes.

## Sequencing

Steps T1 to T15 and probes P1 to P10 in `07-remediation-roadmap.md`. It starts with deletions and reversible experiments that need no ruling.
