---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: runtime-status-read-door-01M73HHB
mission_id: 01M73HHBGCYKH10797R6YR21WS
generated_at: '2026-11-11T05:16:57.955648+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: .worktrees/runtime-status-read-door-01M73HHB-coord/kitty-specs/runtime-status-read-door-01M73HHB/spec.md
    sha256: b6d86f1e227e72f43cc4f06b3b7b62c12548c49cbe9ee07efa2a5d8e46649ec6
  plan.md:
    path: .worktrees/runtime-status-read-door-01M73HHB-coord/kitty-specs/runtime-status-read-door-01M73HHB/plan.md
    sha256: ddce8a6e32ab9a7353b7dde943099c71aa02b938e91ae57d2930684f4803d128
  tasks.md:
    path: .worktrees/runtime-status-read-door-01M73HHB-coord/kitty-specs/runtime-status-read-door-01M73HHB/tasks.md
    sha256: 380f3cb58f8dcd924bfadfb7ac6b0398fd99425f19d6151e34528938e1ce423a
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: blocked
issue_counts:
  low: 2
  high: 1
  critical: 0
  medium: 2
  info: 0
findings:
- id: I1
  severity: high
  category: inconsistency
  summary: FR-006 / User Story 3 AC2 assert that an advancing dispatch of an owned coordination Mission refuses for an EMPTY or UNMATERIALIZED worktree, but today's advancing outcome for the owned UNMATERIALIZED cell is unverified (bootstrap's decision-log wrap may materialize it, as it does for non-owned), so the [ratchet] row may encode a behaviour change no WP plans.
- id: C1
  severity: medium
  category: coverage
  summary: NFR-002's wall-time threshold (+10% on the existing next suites) has no task that measures it; only the one-read half is covered (WP01 T005, WP04 T019 spies).
- id: U1
  severity: medium
  category: underspecification
  summary: FR-001 is labelled [build], but its advancing-mode clause (dispatch the same WP as materialized) already holds today because bootstrap materializes the worktree; only the query cells and the advancing progress numbers are red. That clause is no-op passable.
- id: L1
  severity: low
  category: inconsistency
  summary: The gate files and decision.py / runtime_bridge.py are edited by later WPs out of their owners' maps (WP05, WP06). This is allowed by ownership leeway with a recorded rationale, and safe because the WPs are sequential, but reviewers must check each rationale.
- id: L2
  severity: low
  category: process
  summary: 'The artifacts cite #7507 and #7310 as owed work: each needs an issue-matrix row before its owning WP can be approved (#7507 -> WP04, #7310 -> WP06).'
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | HIGH | spec.md FR-006, User Story 3 AC2; data-model.md owned dispatch column; WP04 T017, WP05 T026 | FR-006 is a `[ratchet]` that claims today's behaviour. For owned + EMPTY the advancing refusal is real (`mission_context_for(owned=)` raises even with `tolerate`, research/code-grounding.md §3). For owned + UNMATERIALIZED, bootstrap passes `tolerate_unmaterialized_coord=True` and the decision-log wrap may materialize the worktree, so today's advancing outcome there may be "proceed", not "refuse". No task characterises it. | Reword FR-006 and User Story 3 AC2 to "an advancing dispatch keeps today's outcome for an owned coordination Mission whose workspace is unavailable to dispatch (`OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`)". Add a WP05 characterisation subtask that pins today's owned EMPTY and UNMATERIALIZED advancing outcomes first, and keep them. This matches DM-1's rationale: no agent is sent into a missing workspace; one the bootstrap materializes is not missing. |
| C1 | Coverage | MEDIUM | spec.md NFR-002; tasks.md | The +10% wall-time bound has no measuring task. | Add to WP06 T034: time the listed `next` suites on the base and on the branch (same machine, `-n0`), and record both in `add-history` and the PR. |
| U1 | Underspecification | MEDIUM | spec.md FR-001, User Story 1 AC2 | The advancing dispatch clause passes today (CLI probe `research/repro/advancing_cells.py`). | Narrow FR-001 to the query cells plus the board selector's EMPTY cell (both red today, WP04 T016). Move "advancing progress is true" under FR-001 explicitly (red today, WP05 T026). Keep AC2 as a ratchet. |
| L1 | Inconsistency | LOW | tasks/WP05, tasks/WP06 | Out-of-map edits of WP03/WP04-owned files. | None needed. Reviewers check the `add-history` rationale of each out-of-map edit. |
| L2 | Process | LOW | spec.md, tasks/WP04, tasks/WP06 | Issue-matrix rows will be required. | Record rows (`#7507` → WP04, `#7310` → WP06, `#7408` parent context-only) before approval. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 empty worktree real board | Yes | T016, T018, T019, T026 | see U1 |
| FR-002 selector block for direct callers | Yes | T016, T018, T020 | X pins stay green |
| FR-003 report materialization | Yes | T030, T031, T032 | |
| FR-004 no false report | Yes | T033 | |
| FR-005 owned query reads ref | Yes | T017, T019 | |
| FR-006 owned dispatch refusal | Yes | T017, T026 | see I1 |
| FR-007 door finds owned-only Mission | Yes | T006, T007, T008 | |
| FR-008 one read, one reduction | Yes | T001-T005, T011-T013, T018, T019 | |
| FR-009 lifecycle row via write seam | Yes | T029 | |
| FR-010 explicit seam for presence | Yes | T023, T024, T025 | |
| FR-011 gate drained by 8 | Yes | T021, T027, T034 | ledger 41 → 37 → 34 → 33 |
| FR-012 ADR amendment | Yes | T009 | |
| NFR-001 progress parity | Yes | T004, T014 | |
| NFR-002 no extra cost | Partial | T005, T019 | see C1 |
| NFR-003 unchanged elsewhere | Yes | T020, T022, T026, T028 | |
| NFR-004 code quality | Yes | every WP's test strategy | |
| C-001 to C-006 | Yes | all WPs | |
| SC-001 to SC-005 | Yes | WP04, WP06 | |

**Charter Alignment Issues:** none. Tidy-first enablers precede functional change (WP01, WP03); red-first is per behaviour change (C-002); no new gate, and the existing priced allowlist shrinks in the same commit as each move; no full heavy suites; single canonical authority (one door, one builder).

**Unmapped Tasks:** none (T001-T034 all map to a WP with requirement refs).

**Metrics:**

- Total Requirements: 12 FR, 4 NFR, 6 C, 5 SC (27)
- Total Tasks: 34 subtasks in 6 work packages
- Coverage: 27/27 have at least one task (NFR-002 partially)
- Ambiguity Count: 1 (I1)
- Duplication Count: 0
- Critical Issues Count: 0

## Next Actions

- Resolve **I1** (HIGH) before implementation: reword FR-006 / User Story 3 AC2 as a ratchet of today's owned advancing outcome, and add the WP05 characterisation subtask. Then re-run `/spec-kitty.analyze`.
- Fold C1 and U1 in the same edit (small spec and tasks wording changes).
- L1 and L2 need no edit now.
