# Work Packages: One checkout verdict for the planning commands

**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)
**Scope**: slice 1 (#7594). Slice 2 (#7633) gets its work package after the operator ruling Q8.

## Work Package WP01: Shared planning checkout verdict (Priority: P1)

**Goal**: setup-plan and check-prerequisites consume one shared checkout verdict taken from the placement seam.
**Prompt**: `tasks/WP01-shared-checkout-verdict.md`
**Requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-002, C-001, C-002, SC-001, SC-002

### Included Subtasks

- [ ] T001 Commit the red acceptance test `test_planning_checkout_verdict.py` (red on the base)
- [ ] T002 Add `PlanningCheckoutVerdict` + `resolve_planning_checkout_verdict` in `mission_branch_context.py`
- [ ] T003 setup-plan consumes the verdict; retire `_resolve_branch_match_operands` and `read_minted_mission_branch`
- [ ] T004 check-prerequisites consumes the verdict from the invoking checkout
- [ ] T005 Re-point the tests that patched the retired helpers; changelog fragment

### Dependencies

None.

### Risks & Mitigations

- Pins that hand-seed a legacy `mission_branch` without a stored `single_branch` topology: an expectation edit is escalated, not done silently.
