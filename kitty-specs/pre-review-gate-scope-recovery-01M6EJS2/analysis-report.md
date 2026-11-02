---
schema_version: 1
artifact_type: spec-kitty.analysis-report
command: /spec-kitty.analyze
mission_slug: pre-review-gate-scope-recovery-01M6EJS2
mission_id: 01M6EJS28KN871H2E15PSJTTYS
generated_at: '2026-11-02T17:01:14.155359+00:00'
analyzer_agent: unknown
input_artifacts:
  spec.md:
    path: kitty-specs/pre-review-gate-scope-recovery-01M6EJS2/spec.md
    sha256: 4e512769250051aebcc4fd0d251f93d07e736670ca27aafc7fe76ee3b325a63d
  plan.md:
    path: kitty-specs/pre-review-gate-scope-recovery-01M6EJS2/plan.md
    sha256: ef22c62f7d4c4a2d4f34783211bba20def05307ce883c57d4bb062bae98ebbc2
  tasks.md:
    path: kitty-specs/pre-review-gate-scope-recovery-01M6EJS2/tasks.md
    sha256: 79edc868a5832d4dff2e3bf6698e3ba82dc53be68b59bfca88b09c1e308e6dbf
  charter:
    path: .kittify/charter/charter.yaml
    sha256: 83874f7451d21cf0615682164d7bb883844ee032e7622bb1359a343fd0e6fb03
verdict: ready
issue_counts:
  high: 0
  critical: 0
  low: 1
  medium: 1
  info: 0
findings:
- id: C1
  severity: medium
  category: coverage
  summary: FR-003 (pinned scope honoured end to end) has no dedicated end-to-end head-run assertion among T001-T003; it is carried implicitly by the observability harness update in T007.
- id: C2
  severity: low
  category: coverage
  summary: FR-009/SC-004 (no gate weakened) are covered by the pre-existing gate suites named only in the Test Strategy, not by a named subtask.
---

## Specification Analysis Report

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| C1 | Coverage | MEDIUM | spec.md FR-003; tasks.md T001-T003 | FR-003 ("pinned scope is honoured end to end") is only partly tasked: T001 proves the WP file parses and the roster resolves, and T002/T003 cover budget and refusal text, but no subtask names the head-run assertion that the pinned targets — not the declared command — are executed through the move-task CLI. | At implementation, extend the existing move-task observability harness (already an owned file) with a pinned-scope case that asserts the head run's argv is the scoped pytest invocation, and keep T001's roster proof as its paired readability control. FR-003 is already in the WP's `requirement_refs`, so no requirement is unmapped. |
| C2 | Coverage | LOW | spec.md FR-009, SC-004; tasks.md Test Strategy | The "no gate weakened" ratchet is satisfied by running the pre-existing gate suites, which the WP lists in the Test Strategy rather than in a subtask. | Acceptable as written: the ratchet is a command list, not new work. The reviewer re-runs it, and the WP's Review Guidance names the terminal/block/skip checks explicitly. |

### Coverage Summary

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| wp-model-accepts-pinned-scope (FR-001) | yes | T001, T004 | red-first then fix |
| roster-guard-reads-pinned-scope (FR-002) | yes | T001, T004 | paired positive control on the same fixture |
| pinned-scope-honoured-end-to-end (FR-003) | partial | T001, T007 (harness) | C1: the head-run assertion is carried by the harness update |
| whole-command-budget-default (FR-004) | yes | T002, T005, T006 | |
| declared-budget-wins (FR-005) | yes | T002, T005 | ratchet row with a paired default assertion |
| timeout-diagnostic-names-scope (FR-006) | yes | T003, T007 | |
| oversize-diagnostic-names-shape (FR-007) | yes | T003, T007 | |
| one-budget-per-transition (FR-008) | yes | T002, T006 | asserted through the production seam |
| no-gate-weakened (FR-009) | ratchet | Test Strategy | C2 |
| diff-coverage (NFR-001) | yes | T008 | every new branch has a case |
| diagnostic-size (NFR-002) | yes | T003 | single line, <= 800 chars |
| single-budget-authority (NFR-003) | yes | T005, T006 | one resolver, no new key |
| no-resurrected-census (C-001) | constraint | Review Guidance | no heuristic mapper |
| command-authority-unchanged (C-002) | constraint | Review Guidance | alias untouched |
| declared-budget-neutrality (C-003) | yes | T002 | |

### Charter Alignment Issues

None. The change extends existing single authorities (`WPMetadata`,
`resolve_review_test_timeout`, the resolved `ScopeSource`) instead of adding a
parallel reader, stays inside the existing modules, and is driven red-first.

### Unmapped Tasks

None. All eight subtasks map to at least one requirement; T008 carries the
documentation half of FR-006 and the NFR-001 verification.

### Metrics

- Total requirements: 12 (FR-001…FR-009, NFR-001…NFR-003)
- Total constraints: 3 (C-001…C-003)
- Total tasks: 8
- Coverage: 13/15 mapped explicitly (2 carried by evidence elsewhere, see C1/C2)
- Ambiguity count: 0
- Duplication count: 0
- Critical issues: 0

### Next Actions

1. Implement WP01 red-first, in the T001 → T008 order.
2. At T007/T008, close C1 by adding the pinned-scope head-run assertion to the
   existing move-task observability harness.
3. Re-run the gate ratchet suites (C2) before review and report both commands and
   results in the PR's `## Tests run` section.
