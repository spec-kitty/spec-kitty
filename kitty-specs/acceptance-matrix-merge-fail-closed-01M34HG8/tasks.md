# Tasks: Fail-closed acceptance-matrix merge driver (#4880)

**Mission**: `acceptance-matrix-merge-fail-closed-01M34HG8`
**Branch**: `fix/acceptance-matrix-merge-fail-closed`
**Plan**: [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md)

Small brownfield fix. Four work packages: three `code_change`, one `planning_artifact`
(the code-vs-planning ownership split is mandatory). WP03 and WP04 depend on WP01
(the mechanism must raise before the tests expect refusal and before the decision
docs describe the landed behavior). WP02 is independent and parallel.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `_merge_field` raises `RowMatrixMergeError` on the both-sides-diverged branch (was `_field_conflict_marker` at :424) | WP01 | |
| T002 | Delete the now-unreachable `_field_conflict_marker` function ONLY (KEEP the `_CONFLICT_MARKER_*` constants — used by the review-cycle driver) | WP01 | |
| T003 | Broaden both matrix drivers' `except` to also catch `AcceptanceMatrixParseError` → `Exit(1)` | WP01 | |
| T004 | Confirm both drivers surface `Exit(1)` and `_merge_branch_into` aborts | WP01 | |
| T005 | `AcceptanceMatrix.from_dict` rejects any value containing a conflict marker → `AcceptanceMatrixParseError` | WP02 | [P] |
| T006 | Focused test for the read-side marker-reject guard | WP02 | [P] |
| T007 | Red-first proof: the three pins assert marker-embed against the pre-fix product file | WP03 | |
| T008 | Re-anchor the three genuine-conflict pins to expect refusal | WP03 | |
| T009 | Keep controls green; confirm no distinct FR-004 negative-control green-pins the flip (post_consolidation is a red herring — do not edit) | WP03 | |
| T014 | CLI-entry refusal test: `merge_driver_acceptance_matrix` exits non-zero on a both-sides conflict (FR-002/SC-001) | WP03 | |
| T010 | Amend ADR 2026-07-23-2: qualify "no consolidation abort" to exclude gate/verdict artifacts | WP04 | [P] |
| T011 | Amend contract `merge-driver-algorithm.md:29` per the amendment note | WP04 | [P] |
| T012 | Amend 01KZPG7V spec FR-004 note (superseded → fail-closed) | WP04 | [P] |
| T013 | Consumer-facing changelog entry | WP04 | [P] |

## Work Packages

### WP01 — Fail-closed mechanism (`merge_driver.py`) `[code_change]`

- **Goal**: Close the corruption class by construction — `_merge_field` raises instead of embedding markers; delete the embed path; harden the drivers' `except`.
- **Priority**: P1 (the fix). **Dependencies**: none.
- **Independent test**: a both-sides-diverged field now raises `RowMatrixMergeError`; `_field_conflict_marker` is gone.
- **Subtasks**: T001, T002, T003, T004
- **Requirements**: FR-001, FR-002, FR-005, NFR-002, NFR-003
- **Prompt**: [tasks/WP01-failclosed-mechanism.md](./tasks/WP01-failclosed-mechanism.md) (~180 lines)

### WP02 — Read-side marker-reject guard (`matrix.py`) `[code_change]` `[P]`

- **Goal**: Defense-in-depth — `from_dict` rejects marker-laden values loudly instead of recomputing to `fail`.
- **Priority**: P2. **Dependencies**: none (parallel with WP01; different module).
- **Independent test**: a matrix dict with a marker string in a field raises `AcceptanceMatrixParseError`.
- **Subtasks**: T005, T006
- **Requirements**: FR-004, NFR-001
- **Prompt**: [tasks/WP02-read-guard.md](./tasks/WP02-read-guard.md) (~150 lines)

### WP03 — Red-first + re-anchor the divergence pins `[code_change]`

- **Goal**: Prove the fix witnesses the bug; re-anchor the three tests that green-pin the corruption to expect refusal.
- **Priority**: P1. **Dependencies**: WP01.
- **Independent test**: each pin fails against the pre-fix product file and passes (expecting refusal) after WP01.
- **Subtasks**: T007, T008, T009, T014
- **Requirements**: FR-002, FR-003, NFR-001
- **Prompt**: [tasks/WP03-redfirst-reanchor.md](./tasks/WP03-redfirst-reanchor.md) (~220 lines)

### WP04 — Amend recorded decisions + changelog `[planning_artifact]`

- **Goal**: Land the decision reversal in the same change: ADR, contract, 01KZPG7V FR-004 note, consumer changelog.
- **Priority**: P1 (must land with the fix — C-003). **Dependencies**: WP01.
- **Independent test**: ADR/contract/FR-004 prose reflect fail-closed for verdict artifacts; changelog has a consumer-facing entry.
- **Subtasks**: T010, T011, T012, T013
- **Requirements**: FR-006, C-003, C-004
- **Prompt**: [tasks/WP04-decision-amendments.md](./tasks/WP04-decision-amendments.md) (~140 lines)

## Dependency graph

```
WP01 ─┬─→ WP03   (tests expect the raise)
      └─→ WP04   (docs describe the landed behavior)
WP02  ── parallel (independent module)
```

## MVP scope

WP01 is the load-bearing fix. WP01+WP03 together are the releasable minimum (fix + proof + re-anchored pins). WP02 (defense-in-depth) and WP04 (decision docs) land in the same PR per C-003.
