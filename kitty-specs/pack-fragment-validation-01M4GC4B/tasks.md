# Work Packages: Canonical org-fragment reference validation

**Audience**: software-engineer. **Updated**: 2026-10-09.
**Inputs**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/pack-validation.md](contracts/pack-validation.md), [quickstart.md](quickstart.md), [reasons-canvas.md](reasons-canvas.md).
**Prerequisites**: Parent-adjudicated architect recommendation; canonical substantive plan; finalized requirements and analysis before implement.
**Tests**: Explicitly required by spec/charter. These tasks request future proof; planner ran no tests.
**Organization**: One focused WP, seven serial subtasks. Reference rows only; event log owns completion.

## Work Package WP01: Canonical fragment endpoint validation (Priority: P1)

**Goal**: Both existing validation commands reject authored unbindable canonical endpoints through existing charter authorities while valid declarations/trusted identities and graph-document/intent behavior remain correct.
**Independent Test**: Issue-pinned committed RED via requires fixtures; GREEN category/file/role/token assertions on doctrine JSON, rendered charter output, valid/invalid twins, and both packs/internal commands.
**Prompt**: [tasks/WP01-canonical-fragment-endpoint-validation.md](tasks/WP01-canonical-fragment-endpoint-validation.md).
**Requirement Refs**: FR-001–FR-012, NFR-001–NFR-004, C-001–C-009, SC-001–SC-004 (registered explicitly through map-requirements).

### Included Subtasks

T001 Pre-RED inspection/scope reconciliation ONLY; no production-code edit or commit (WP01)
T002 Witness and separately commit issue-pinned outside-in RED before ANY production-code commit (WP01)
T003 AFTER committed RED, apply bounded tidy/provenance/public typed seam enablers before functional changes (WP01)
T004 Project schema trust from the same scan and thread one loaded org fragment to consumers (WP01)
T005 Add authored endpoint-only adapter using shared binding/dangling authorities (WP01)
T006 Prove compatibility and non-vacuous twins with focused coverage (WP01)
T007 Update author guidance/changelog and perform bounded validation for independent review (WP01)

### Implementation Notes

- T001 is read-only inspection, not tidy implementation. T002 acceptance RED is witnessed and separately committed before ANY production-code commit; T003 performs distinct behavior-preserving tidy/provenance/enabler work AFTER RED and before functional changes. T004/T005 implement the supplied design, not the unreviewed prototype.
- No schema-table expansion, runtime severity rewrite, invented relation enum, second parser or graph-document registry/order change.
- Single_branch execution stays in the validated topic checkout. Canonical implement resolves the workspace; no manually created lane/worktree or fabricated branch.
- Every new helper/branch is tested in its own change. Subtasks complete through `agent tasks mark-status`, never Markdown checkboxes.

### Parallel Opportunities

None within this shared-surface WP. One targeted test command at a time and <=2 workers; documentation may be prepared after behavior is settled, but no concurrent competing writes.

### Dependencies

None (starting and only package). Implementation also requires canonical analysis readiness; no dependency on draft PR #5962.

### Risks & Mitigations

Schema-trust shortcut/profile-id and generated-node leakage require twins; generic view avoids relation coercion; source/target independent binding prevents short circuits; sharded snapshots remain order-sensitive; sibling assembled checking is not a standalone bypass. Parent rechecks draft PR #5962 before implementation/rebase, adapting only if it lands.

**Prompt size**: target 200–500 lines, seven subtasks; actual size verified at finalization.

## Dependency & Execution Summary

- **Sequence**: WP01, T001 → T002 → T003 → T004 → T005 → T006 → T007.
- **Parallelization**: none, by shared ownership and QA-capacity constraint.
- **MVP Scope**: all of WP01; no artificially separated compatibility/docs package.
- **Handoff**: independent implementer-ivan, then independent reviewer selected by parent. Planner neither implements nor reviews product evidence.

## Requirements Coverage Summary

| Requirement IDs | Covered By Work Package | Subtasks |
|---|---|---|
| FR-001, FR-002, FR-003, FR-004 | WP01 | T002, T003, T005, T006 |
| FR-005, FR-006, FR-007 | WP01 | T003, T004, T005, T006 |
| FR-008, FR-009, FR-010 | WP01 | T002, T005, T006, T007 |
| FR-011, FR-012 | WP01 | T007 |
| NFR-001, NFR-002 | WP01 | T004, T005, T006 |
| NFR-003, NFR-004 | WP01 | T001–T007 |
| C-001, C-002 | WP01 | T003, T004, T005 |
| C-003, C-004, C-005, C-006 | WP01 | T001, T005, T006, T007 |
| C-007, C-008, C-009 | WP01 | T001, T002, T007 |
| SC-001, SC-002, SC-003, SC-004 | WP01 | T002, T006, T007 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|---|---|---|---|---|
| T001 | Pre-RED inspection only | WP01 | P1 | No |
| T002 | Witnessed separate RED before any production commit | WP01 | P1 | No |
| T003 | Post-RED tidy/provenance/public typed seams | WP01 | P1 | No |
| T004 | Trusted scan/single load | WP01 | P1 | No |
| T005 | Authored endpoint adapter | WP01 | P1 | No |
| T006 | Compatibility/coverage | WP01 | P1 | No |
| T007 | Docs/bounded validation/review | WP01 | P1 | No |
