# Tasks: Bind the event-traceability acceptance scenario

**Mission**: `bind-event-traceability-scenario-01M6BTXK` · **Branch**: `issue-6260-bind-event-traceability-scenario` (planning base and merge target)
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Arrange steps: approved work package, and a rejection after that approval | WP01 | |
| T002 | Act steps: the rejection through `agent status emit`, and `consolidate` | WP01 | |
| T003 | Assert steps: sent back for rework, not reported as approved, consolidation refusal names the work package | WP01 | |
| T004 | `MissionLifecycle` helper that restamps the approval row into the future as a pull would deliver it | WP01 | |
| T005 | Compile the harness and run the bound scenarios in the acceptance-jvm runner | WP01 | |
| T006 | Remove `@wip`, `@wip-owner` and `@wip-since` from the two drafted scenarios | WP02 | |
| T007 | Add the same-fixture positive control scenario | WP02 | |
| T008 | Update `tests/scenarios/README.md` with the new step vocabulary | WP02 | |
| T009 | Update the testing guide with the binding and the crafted-pull note | WP02 | |
| T010 | Add the `[Unreleased]` changelog entry | WP02 | |
| T011 | Run the per-PR scenario contract and docs freshness checks | WP02 | |

## Phase 1 — Bind the harness (WP01)

### WP01 — Bind the two drafted scenarios to the real CLI

**Goal**: the drafted steps have real step definitions that drive the CLI, including the clock-skewed
approval row that models a teammate's pull. **Priority**: P1.
**Prompt**: [tasks/WP01-bind-scenario-steps.md](tasks/WP01-bind-scenario-steps.md)
**Independent test**: the two scenarios run green in the acceptance-jvm runner (adhoc filter on the
feature), and a deliberately unbound variant fails.

T001 Arrange steps: approved work package, and a rejection after that approval (WP01)
T002 Act steps: the rejection through `agent status emit`, and `consolidate` (WP01)
T003 Assert steps: sent back for rework, not reported as approved, consolidation refusal names the work package (WP01)
T004 `MissionLifecycle` helper that restamps the approval row into the future as a pull would deliver it (WP01)
T005 Compile the harness and run the bound scenarios in the acceptance-jvm runner (WP01)

Dependencies: none. Risk: the emitter may refuse the out-of-order rejection; that is a product
finding to report, not a reason to soften an assertion.

## Phase 2 — Gate the scenario (WP02)

### WP02 — Remove the @wip tags, add the positive control, record the change

**Goal**: the scenarios join the gating nightly, the fixture is proven by a positive control, and the
user-visible change is documented. **Priority**: P1.
**Prompt**: [tasks/WP02-gate-scenario.md](tasks/WP02-gate-scenario.md)
**Independent test**: `tests/architectural/test_scenario_contract.py` passes with no `UNBOUND_STEP`
error for the feature, and the gating pass selects the three scenarios.

T006 Remove `@wip`, `@wip-owner` and `@wip-since` from the two drafted scenarios (WP02)
T007 Add the same-fixture positive control scenario (WP02)
T008 Update `tests/scenarios/README.md` with the new step vocabulary (WP02)
T009 Update the testing guide with the binding and the crafted-pull note (WP02)
T010 Add the `[Unreleased]` changelog entry (WP02)
T011 Run the per-PR scenario contract and docs freshness checks (WP02)

Dependencies: WP01 (needs the step vocabulary). Risk: the contract check reports an unbound or
ambiguous step; fix the binding, never the assertion.
