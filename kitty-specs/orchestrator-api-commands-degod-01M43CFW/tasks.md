# Work Packages: Split the orchestrator-api commands god-module

**Inputs**: [spec.md](spec.md), [plan.md](plan.md)
**Issue**: #5628

One work package: the split, its test re-pointing and the gate companions must land together, or an intermediate commit goes red on a path-scoped gate.

## Subtask Format: `[Txxx] [P?] Description`

## Work Package WP01: Split commands.py behind an unchanged contract (Priority: P1) 🎯 MVP

**Goal**: Move every verb outside the #5532 readers into a per-concern module, register them from a façade command table in contract order, and re-point the tests and gates.
**Independent Test**: The help snapshot of the group and all 21 verbs is byte-identical; the blast-radius suite matches the baseline count.
**Prompt**: `/tasks/WP01-split-commands-module.md`

### Included Subtasks

- [ ] T001 Extract shared helpers into `orchestrator_api/_common.py` (IC-01)
- [ ] T002 Extract `wp_lifecycle`, `consolidation`, `design_phase`, `decision_verbs`, `design_status` and register them from `_COMMAND_TABLE` in `commands.py` (IC-02)
- [ ] T003 Re-point test patch targets and imports to the owning module (IC-03)
- [ ] T004 Re-point or widen source-scanning gates so none goes vacuous (IC-03)
- [ ] T005 Add `test_command_table.py` pinning verb order and owning module

### Implementation Notes

Bodies move verbatim (AST-equal except for added type arguments and the `_common.` seam qualification). Shared patch seams are reached through the `_common` module attribute.

### Dependencies

None.

### Risks & Mitigations

- Silent patch miss → seam rule, plus the full blast-radius suite.
- Vacuous gate → each re-pointed scan asserts presence; package-wide scans assert the package exists.

## Dependency & Execution Summary

WP01 only.
