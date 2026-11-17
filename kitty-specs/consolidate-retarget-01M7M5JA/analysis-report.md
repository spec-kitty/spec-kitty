---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: consolidate-retarget-01M7M5JA
mission_id: 01M7M5JAYR1Q71P022W0EES7ZB
generated_at: '2026-11-17T08:11:53.833609+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: .worktrees/consolidate-retarget-01M7M5JA-coord/kitty-specs/consolidate-retarget-01M7M5JA/spec.md
    sha256: 224d4e35dffb68fbab9a0707d6e74dedf05ad09365c27837158f812f63df1ddd
  plan.md:
    path: .worktrees/consolidate-retarget-01M7M5JA-coord/kitty-specs/consolidate-retarget-01M7M5JA/plan.md
    sha256: 2c2485c133b96aea49ce28f8861bcd7f1f196805351a2d3bfa1857440eab8eb8
  tasks.md:
    path: .worktrees/consolidate-retarget-01M7M5JA-coord/kitty-specs/consolidate-retarget-01M7M5JA/tasks.md
    sha256: 83e0824dd195055f10052b267ee6cadcf4840aff9fff9463d19b1a4eb0a3793a
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  low: 2
  critical: 0
  high: 0
  medium: 3
  info: 0
findings:
- id: I1
  severity: medium
  category: inconsistency
  summary: FR-011 and Edge Case line 99 still say a meta.json absent on the new target is refused; the holder rule (C-006, operator ruling) admits it when the Mission branch carries the record.
- id: U1
  severity: medium
  category: underspecification
  summary: RETARGET_WITH_ATTESTATION_UNSUPPORTED (plan D10, contract, WP03 T008.6) has no FR or acceptance scenario in spec.md.
- id: C1
  severity: medium
  category: coverage
  summary: No WP04 arm pins RETARGET_WITH_ATTESTATION_UNSUPPORTED end to end (only WP03 unit tests).
- id: L1
  severity: low
  category: inconsistency
  summary: plan.md D10 keeps its superseded original text (marked) and the Summary still says D4 is the record placement; readable but redundant.
- id: L2
  severity: low
  category: ambiguity
  summary: NFR-003's 60 s budget covers the terminus/consolidation suites only; WP06's slow integration arms are outside it and unbudgeted.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | spec.md:99, spec.md:120 (FR-011) vs spec.md C-006 and Assumptions; plan D4/D10 | FR-011 and the edge case still list "absent on the new target" as a refusal. Under the holder rule, a Mission whose record lives on its Mission/topic branch is written there and carried to `<b>` by the landing. | Implementers follow the WP01 T003 holder rule, which is authoritative. Reword FR-011 to "neither branch the landing reads carries the record, or `<b>` carries it but cannot take the commit" at the next spec touch. Track this in the WP01 review. |
| U1 | Underspecification | MEDIUM | plan.md D10; contracts/cli-retarget.md; WP03 T008.6 | The attestation boundary code exists only in plan, contract and tasks. | Covered by WP03 T008.6 and WP02 T009.6. Add an Edge Case line to spec.md at the next spec touch. Report it to the operator in the PR (already planned). |
| C1 | Coverage | MEDIUM | WP04 T020 | The new refusal has unit coverage only. | WP04 may add one `_lanes` arm (`--retarget --attest-approved-reviewed WP01`) if NFR-003 allows; otherwise unit coverage plus the dry-run unit test suffice. |
| L1 | Inconsistency | LOW | plan.md Summary, D10 | Superseded text is kept for traceability. | No action. |
| L2 | Ambiguity | LOW | spec.md NFR-003; WP06 | Integration arms are unbudgeted. | WP06 records `--durations`; module-scoped fixtures. |

**Coverage Summary Table:**

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 explicit opt-in | yes | T007, T020 | |
| FR-002 plain override unchanged | yes | T002, T005, T008, T021 | |
| FR-003 everything lands on `<b>` | yes | T013, T014, T018, T025, T026 | |
| FR-004 recorded with provenance | yes | T013, T016, T018 | |
| FR-005 reason flag | yes | T007, T018 | |
| FR-006 rollback restores | yes | T015, T017, T019, T027 | |
| FR-007 resume honours | yes | T008, T013, T019 | |
| FR-008 no protection bypass | yes | T004, T008, T020 | |
| FR-009 dry-run parity | yes | T009, T020 | |
| FR-010 orchestrator-api refuses | yes | T010 | |
| FR-011 unwritable refused | yes | T003, T008, T020 | see I1 |
| FR-012 restating is not a retarget | yes | T003, T007, T020 | |
| NFR-001..004 | yes | T017, T018–T021, all WPs (gates) | |
| C-001..C-007 | yes | WP01, WP03, WP05, WP06 | |
| SC-001..SC-004 | yes | WP04, WP06 | |

**Charter Alignment Issues:** none. The plan keeps one rollback authority, one protection policy and one commit seam. Red-first is planned in every WP. Squads ran at post-plan and post-tasks, and every finding is dispositioned in research.md. No new architectural gate; `_SPAN_PHASES` is edited, not allowlisted.

**Unmapped Tasks:** none.

**Metrics:**
- Total Requirements: 12 FR, 4 NFR, 7 C, 4 SC (27)
- Total Tasks: 27 (T001–T027) across 6 WPs
- Coverage: 100%
- Ambiguity Count: 1
- Duplication Count: 0
- Critical Issues Count: 0

### Next Actions
- No critical or high findings, so implementation may proceed.
- I1 and U1 are wording drifts in spec.md, already resolved by the authoritative plan and tasks text. Fold them at the next spec touch.
- C1 is optional for WP04.
