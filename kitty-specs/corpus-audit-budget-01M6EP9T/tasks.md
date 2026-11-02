# Work Packages: Calibrate the full-corpus recovery test budget

**Inputs**: `spec.md`, `plan.md`, `research.md` in this Mission.  
**Prerequisites**: Issue #5716 claimed; current-main failure and independent fold-versus-separate-work adjudication recorded.  
**Tests**: Existing full-corpus recovery contract is the acceptance test. No new permanent fixture-shape or configuration-value test.

## Work Package WP01: Measure and calibrate the corpus recovery contract (Priority: P1)

**Goal**: Obtain hosted-runner total/per-audit evidence, then apply the smallest independently justified correction without weakening any behavioral control.  
**Independent Test**: The complete existing corpus recovery node passes within the final evidence-calibrated bound; all eleven audits, memberships, inventories and attack/control pairs remain effective.  
**Prompt**: `tasks/WP01-corpus-budget.md`  
**Requirement Refs**: FR-001, FR-002, FR-003, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003

### Included Subtasks

T001 Implement bounded temporary hosted-runner measurement of the exact existing failing node, recording source, runner, total and per-audit durations and retaining every outcome.
T002 Review the measurement, choose and justify the smallest bounded correction, or report a demonstrated bottleneck requiring scope approval.
T003 Apply the approved correction to the existing test and remove disposable measurement wiring once evidence is durable.
T004 Validate the complete contract and focused gates; obtain independent test-integrity review and record all evidence before draft-PR closeout.

### Implementation Notes

- Execute sequentially: no final limit before the hosted measurement.
- No global pytest limit change, skipped/xfail/quarantine test, retry-to-green, reduced corpus, removed membership/inventory check, or omitted healthy control.
- Keep #7071's different fixture untouched.
- Diagnostic outer bound <=900 seconds; job <=25 minutes; unchanged inner CLI bound 180 seconds.
- Permanent production behavior changes or a CI scheduling tradeoff require scope escalation.

### Parallel Opportunities

Reviewers may inspect the spec, plan, existing code and later evidence read-only in parallel. Only one implementation agent writes this package's files; never run duplicate measurements concurrently.

### Dependencies

None.

### Risks & Mitigations

A setup/download failure is not test duration; fetch complete history and record source/environment. If an individual audit stalls, retain its timing and failure rather than guessing a wider budget. Preserve measurement artifacts when temporary wiring is removed.

## Dependency & Execution Summary

WP01 alone delivers the Mission. It has a measurement checkpoint before correction and a review checkpoint before acceptance.

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP01 |
| FR-003 | WP01 |
| NFR-001 | WP01 |
| NFR-002 | WP01 |
| NFR-003 | WP01 |
| C-001 | WP01 |
| C-002 | WP01 |
| C-003 | WP01 |
| SC-001 | WP01 |
| SC-002 | WP01 |
| SC-003 | WP01 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Bounded hosted diagnostic | WP01 | P1 | No |
| T002 | Evidence and correction review | WP01 | P1 | No |
| T003 | Minimal correction and diagnostic cleanup | WP01 | P1 | No |
| T004 | Full contract validation and review | WP01 | P1 | No |
