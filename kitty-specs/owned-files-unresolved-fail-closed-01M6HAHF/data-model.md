# Data Model: evidence verdicts

## Verdict precedence for one approved work package

1. Evidence window not computable: `EVIDENCE_WINDOW_UNCOMPUTABLE` (unchanged)
2. Window diff unreadable: `IMPLEMENTATION_UNREADABLE` (unchanged)
3. **Ownership unresolved**: `OWNERSHIP_UNRESOLVED` (new). The work package is absent from the resolved ownership map: the `tasks/` directory is missing, or its task file is absent or unreadable.
4. Ownership resolved, no owned change: `IMPLEMENTATION_MISSING` (unchanged; attestation may lift it)
5. Review not independent: `REVIEW_NOT_INDEPENDENT` (unchanged)

single_branch Missions emit the `SINGLE_BRANCH_*` alias of each code; `SINGLE_BRANCH_OWNERSHIP_UNRESOLVED` aliases `OWNERSHIP_UNRESOLVED`.

## Entities

- **Resolved ownership map**: work package id to authored `owned_files` patterns, built from the Mission's `tasks/` directory (resolved through the placement seam, owned-aware since #7099). A key is present only when the task file was read.
- **Ownership read location**: the `tasks/` directory the map was read from. It is carried with the scan so the refusal can name it.

## Invariants

- `IMPLEMENTATION_MISSING` is never emitted for a work package absent from the resolved ownership map.
- `--attest-no-implementation` never lifts `OWNERSHIP_UNRESOLVED`, `IMPLEMENTATION_UNREADABLE` or `EVIDENCE_WINDOW_UNCOMPUTABLE`.
