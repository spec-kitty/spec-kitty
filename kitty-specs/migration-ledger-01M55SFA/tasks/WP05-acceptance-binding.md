---
work_package_id: WP05
title: 'Acceptance binding: rebind read surface, lift @wip, bind the ten steps (FR-015)'
dependencies:
- WP01
- WP02
- WP03
- WP04
requirement_refs:
- FR-015
- SC-007
planning_base_branch: issue-5230-migration-ledger-impl
merge_target_branch: issue-5230-migration-ledger-impl
branch_strategy: Planning artifacts for this mission were generated on issue-5230-migration-ledger-impl. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5230-migration-ledger-impl unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-migration-ledger-01M55SFA
base_commit: 103b68497fcab2d9e84668a8aa9db27d6d93a4a0
created_at: '2026-10-18T06:04:51.559900+00:00'
subtasks:
- T027
- T028
- T029
- T030
history:
- timestamp: '2026-10-17T21:06:30Z'
  lane: planned
  agent: system
  shell_pid: ''
  action: Prompt generated via /spec-kitty.tasks-packages
agent_profile: java-jenny
authoritative_surface: acceptance-jvm/
create_intent: []
execution_mode: code_change
lane: planned
owned_files:
- tests/scenarios/upgrade/migration-ledger.feature
- acceptance-jvm/src/test/java/kitty/acceptance/steps/ArrangeSteps.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/AssertSteps.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP05 – Acceptance binding

## ⚡ Do This First: Load Agent Profile

Load `java-jenny` (`role: implementer`) — the step bindings are Cucumber-JVM Java. Implementation
command (depends on WP01–WP04): `spec-kitty implement WP05 --base WP04`

---

## Objective

Make the seven `@wip` scenarios in `tests/scenarios/upgrade/migration-ledger.feature` pass: rebind
the three `When` lines to the canonical `spec-kitty migrate ledger` surface, lift `@wip`, and bind
the ten new acceptance-jvm steps (4 Given + 6 Then), including the clone fixture that seeds a
recorded-but-locally-absent state. `tests/architectural/test_scenario_contract.py` must stay green.

Grounded in `plan.md` **Cross-cutting (X1–X4)** / **IC-08**; spec FR-015, SC-007.

## Context & Constraints — design invariants (carry these exactly)

- **Rebind to ONE surface.** The three `When` lines that today name `spec-kitty upgrade
  --list-applied` (1×, scenario "I can ask what setup steps ran…") and `spec-kitty doctor migrations`
  (2×, the "local-only step in place here" and the drift scenario) all become
  **`spec-kitty migrate ledger`** (OQ-1). The scenarios' Then-asserts are command-agnostic — only the
  `When` step text and the footer note change.
- **Lift `@wip`** from all seven scenarios; update the feature footer's read-surface note to name
  `migrate ledger`.
- **Steps follow Arrange / Assume / Act / Assert.** The four new **Given** steps bind in
  `ArrangeSteps.java`; the six new **Then** steps bind in `AssertSteps.java`. The `When I run "…"`
  steps are generic CLI-run steps already bound (ActSteps) — do NOT add new When bindings.
- **Consumer language only** — keep "ledger"/"migration internals" out of scenario prose; this is a
  text rebind of the command token, nothing else.
- **No PROMISES.md / no `@promise` tag** here (operator ruling, 2026-10-17; untagged-gating style).

## Pointcut Map (file:line → change)

| # | file | change | what |
|---|------|--------|------|
| X1 | `tests/scenarios/upgrade/migration-ledger.feature` (3 `When` lines) | **MODIFY** | rebind `upgrade --list-applied` + 2× `doctor migrations` → `spec-kitty migrate ledger`. |
| X2 | same feature (`@wip` tags on 7 scenarios + footer) | **MODIFY** | lift `@wip`; update footer read-surface note. |
| X3a | `acceptance-jvm/src/test/java/kitty/acceptance/steps/ArrangeSteps.java` | **ADD** | 4 new `@Given` bindings. |
| X3b | `acceptance-jvm/src/test/java/kitty/acceptance/steps/AssertSteps.java` | **ADD** | 6 new `@Then` bindings. |
| X4 | `tests/architectural/test_scenario_contract.py` | **VERIFY (no edit)** | stays green after rebind + `@wip` lift (SC-007). |

## Owned files (disjoint)

- `tests/scenarios/upgrade/migration-ledger.feature`
- `acceptance-jvm/src/test/java/kitty/acceptance/steps/ArrangeSteps.java`
- `acceptance-jvm/src/test/java/kitty/acceptance/steps/AssertSteps.java`

## The ten steps to bind (from the feature footer)

**Given (ArrangeSteps.java):**
1. "a setup step the project declares but has not recorded as run"
2. "a freshly pulled clone whose shared records show its local git setup ran but whose own local git
   state is missing" — the clone fixture that seeds a **pushed record WITHOUT the clone-local
   effect** (reuse the existing `git check-ignore` / commit helpers the two non-`@wip` scenarios use).
3. "a project set up before Spec Kitty recorded its applied setup steps"
4. "a project whose recorded setup step no longer matches its current definition"

**Then (AssertSteps.java):**
5. "the previously pending setup step has taken effect"
6. "this clone's own local git setup is in place"
7. "the setup steps that ran are listed in the order they ran"
8. "the report shows a local-only setup as recorded elsewhere but not yet in place here"
9. "the setup work already done is not done again"
10. "the report flags a setup step whose content changed since it ran"

## Red-first approach

Lift `@wip` FIRST so the seven scenarios run and fail (steps unbound / surface asserts), then bind
the steps until green. The two already-gating scenarios must stay green throughout.

## Subtasks & Detailed Guidance

### T027 – Rebind 3 When lines + lift @wip + footer (X1, X2, FR-015)
Change the command token to `spec-kitty migrate ledger` in the three `When` lines; remove the seven
`@wip` tag blocks; update the footer read-surface note.

### T028 – Bind 4 new @Given in ArrangeSteps.java (X3a, FR-015)
Bind the four Arrange steps, including the recorded-but-locally-absent clone fixture.

### T029 – Bind 6 new @Then in AssertSteps.java (X3b, FR-015)
Bind the six Assert steps against the `migrate ledger` output and the on-disk/working-tree effects.

### T030 – Verify scenario contract + gating (X4, SC-007)
Confirm `test_scenario_contract.py` stays green and all nine scenarios gate the nightly.

## Test strategy & blast radius (targeted — NOT whole dirs)

Run the seven previously-`@wip` scenarios + the two gating ones (the acceptance-jvm runner for
`tests/scenarios/upgrade/migration-ledger.feature`); run the single named gate
`tests/architectural/test_scenario_contract.py` (NOT the bare `tests/architectural/`). CI owns full
suites.

## Quality gates

Java: idiomatic Cucumber step bindings, no dead/duplicate glue. Python gate untouched. Feature file
stays consumer-language. No suppressions.

## Acceptance criteria satisfied

SC-007 (seven `@wip` scenarios pass with ten steps bound; all nine gate the nightly;
`test_scenario_contract.py` green); FR-015.

## Risks & Mitigations

- **R5 step/fixture location:** reuse the helpers the two non-`@wip` scenarios already bind; the
  clone Given needs a pushed record without the local effect.
- **Ambiguous glue:** ensure new step regex does not collide with existing Arrange/Assert bindings.

## Review Guidance

Confirm: exactly one command token (`migrate ledger`) in all three rebinds; `@wip` fully lifted; ten
steps bound in the convention-correct modules; scenario contract green.

## Activity Log

- 2026-10-17T21:06:30Z – system – lane=planned – Prompt created.
