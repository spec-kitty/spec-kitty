# Work Packages: Owned Mission coordination status charter custody

**Inputs**: Design documents from `kitty-specs/owned-charter-status-custody-01M6TZKC/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md  
**Tests**: Explicit red-first integration and installed-CLI verification are required.

## Work Package WP01: Canonical coordination status custody (Priority: P1) 🎯 MVP

**Goal**: Admit only the same owned Mission's canonical coordination status directory in addition to its primary Mission directory.  
**Independent Test**: New canonical-status prompt integration behavior turns red→green, foreign paths stay refused, both owned integration files pass, and installed-CLI parameter `[0]` passes.  
**Prompt**: `tasks/WP01-canonical-coordination-status-custody.md`  
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, NFR-001, C-001, C-002, C-003, C-004, SC-001, SC-002, SC-003

### Included Subtasks

T001 Reconfirm current-main custody failure through installed-CLI parameter `[0]` (WP01)
T002 Add and commit red canonical-status positive and same-fixture foreign-path negative integration coverage (WP01)
T003 Implement unequal-arm canonical `STATUS_STATE.read_dir` admission while preserving primary fast path and charter anchor (WP01)
T004 Add the narrow #6788 changelog fragment without claiming umbrella closure (WP01)
T005 Run focused green validation, ordinary fast baseline, scoped quality checks, and record nightly residual (WP01)

### Implementation Notes

- Keep `src/runtime/next/runtime_bridge.py` and `CharterScope.resolve(owned.owned_root, owned.mission_dir)` unchanged.
- Use only `mission_context_for` on the unequal-path arm with `owned=owned` and `tolerate_unmaterialized_coord=True`.
- Do not modify the e2e expectations, startup budget, #7206, or nearby PR scopes.

### Parallel Opportunities

- None; T002's red contract precedes T003, and validation follows the final diff.

### Dependencies

- None.

### Risks & Mitigations

- Cross-Mission admission → exact resolved equality and same-fixture negative coverage.
- Fast-path regression → leave equality control flow first and verify existing same-path tests.
- False recovery claim → PR and issue explicitly leave merged-commit nightly verification pending.

---

## Dependency & Execution Summary

- **Sequence**: WP01 only, red test commit → minimal production edit → focused review.
- **Parallelization**: none required.
- **MVP Scope**: WP01 is the complete Mission slice; the umbrella startup failure remains independently owned.

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001..FR-004 | WP01 |
| NFR-001 | WP01 |
| C-001..C-004 | WP01 |
| SC-001..SC-003 | WP01 |

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Installed-CLI red reproduction | WP01 | P1 | No |
| T002 | Red-first integration contract | WP01 | P1 | No |
| T003 | Canonical status admission | WP01 | P1 | No |
| T004 | Narrow changelog fragment | WP01 | P1 | No |
| T005 | Focused validation and evidence | WP01 | P1 | No |
