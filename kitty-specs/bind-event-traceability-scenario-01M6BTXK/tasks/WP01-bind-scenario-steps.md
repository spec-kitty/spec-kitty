---
work_package_id: WP01
title: Bind the two drafted scenarios to the real CLI
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-003
- C-001
- C-003
- SC-001
- SC-004
planning_base_branch: issue-6260-bind-event-traceability-scenario
merge_target_branch: issue-6260-bind-event-traceability-scenario
branch_strategy: Planning artifacts for this mission were generated on issue-6260-bind-event-traceability-scenario. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6260-bind-event-traceability-scenario unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Bind the harness
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: acceptance-jvm/src/test/java/kitty/acceptance/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- acceptance-jvm/src/test/java/kitty/acceptance/environment/MissionLifecycle.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/ArrangeSteps.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/ActSteps.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/AssertSteps.java
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6260'
---

# Work Package Prompt: WP01 – Bind the two drafted scenarios to the real CLI

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Add the Arrange/Act/Assert vocabulary the two drafted scenarios in
`tests/scenarios/status/event-traceability.feature` need, so that each step drives the real
`spec-kitty` CLI as a separate process and the scenario's promise is checked positively.

- The approved-state Arrange reuses `MissionLifecycle.planMission` + `advance(..., "approved")`.
  **Do not** add a second approval path.
- The rejection is recorded through `spec-kitty agent status emit <wp> --to in_progress --actor <actor> --mission <slug>`,
  after the approval row has been restamped ten minutes into the future as a pulled row carries it.
- The assertions read the CLI's own output: the lane from `spec-kitty agent tasks status --json`, and
  the consolidation refusal message.
- Nothing in `tests/scenarios/` changes in this work package (WP02 owns those files).

## Context

- Feature: `tests/scenarios/status/event-traceability.feature` (two `@wip` scenarios, unbound).
- The promise: the last decision recorded on a work package counts — a rejection recorded after an
  approval sends it back, and a Mission with such a work package is refused at consolidation.
- The behaviour is shipped and already guarded by `tests/consolidation/test_wall_clock_claim_p0_repro.py`.
  This work package binds its customer-facing description; it changes no product code.
- Read `acceptance-jvm/README.md`, `docs/development/testing/acceptance-scenarios.md` and the
  environment classes before writing a line: the harness has one `ScenarioContext`, one
  `SpecKittyDriver` port, and Arrange/Assume/Act/Assert step classes.

## Detailed Guidance

### T001 — Arrange steps

In `ArrangeSteps`:

- `@Given("a Mission whose work package {string} has been approved")`
  - `context.lifecycle().planMission(MISSION, List.of(wp))` then `advance(MISSION, wp, "approved")`.
  - Use the fixed Mission name `"demo"`, as the other features do.
  - Fail fast: `advance` already throws with the CLI output when a lane cannot be reached.
- `@Given("a reviewer has recorded a rejection of {string} after that approval")`
  - Delegate to the same routine the Act step uses (T002) so the arrange and the act cannot drift.

### T002 — Act steps

In `ActSteps`:

- `@When("a reviewer records a rejection of {string} after that approval")`
  - Call `context.lifecycle().plantFutureStampedApproval(MISSION, wp)` (T004).
  - Run the emit command: `spec-kitty agent status emit <wp> --to in_progress --actor reviewer --reason "review: changes requested" --mission <slug>`.
  - `context.recordResult(...)` so `Then` steps can inspect exit code and output. Do **not** assert
    success here: the scenario's own assertions decide, and a refusal must surface as a red
    scenario with the CLI's diagnostics.
- `@When("I consolidate the Mission")`
  - `spec-kitty consolidate --mission <slug> --yes`, recorded the same way.

### T003 — Assert steps

In `AssertSteps`:

- `@Then("the work package {string} is sent back for rework")`
  - Read `spec-kitty agent tasks status --mission <slug> --json` through `context.run(...)`.
  - Require the per-work-package entry to report lane `in_progress` (the rework lane). Match the
    `id` → `lane` pair with a regex on the JSON, as `ArrangeSteps.theWorkPackageIsInLane` does, so
    the assertion does not depend on a JSON library the harness does not have.
- `@Then("{string} is not reported as approved")`
  - Same status read; there must be an entry for the work package, it must not say `approved`, and
    the rework lane must be visible. Never satisfy this by absence of output.
- `@Then("consolidation is refused because {string} is not approved")`
  - The last result must exit non-zero.
  - The output must carry the merge-readiness refusal and name the work package. Today the CLI
    prints `Mission is not merge-ready — WP(s) missing review approval: <ids>`
    (`src/specify_cli/consolidation/phase_claim.py::_assert_mission_terminal_ready`); assert on a
    stable fragment (`not merge-ready`, `missing review approval`) plus the `<wp>` id, not on the
    whole sentence, so a wording tweak does not make the scenario brittle.

### T004 — The crafted pulled approval row

In `MissionLifecycle`, add `plantFutureStampedApproval(String name, String wp)`:

- Read `<repo>/kitty-specs/<slug>/status.events.jsonl` (use the slug field the class already holds).
- Find the single row where `"wp_id"` is `<wp>` and `"to_lane"` is `"approved"`.
- Parse its `"at"` with `java.time.OffsetDateTime.parse`, add a fixed `Duration.ofMinutes(10)`,
  write the row back with the new stamp formatted `DateTimeFormatter.ISO_OFFSET_DATE_TIME`.
  Preserve everything else on the row byte-for-byte apart from the `at` value; **never** add a
  `lamport_clock` (the CLI writes none for lane transitions).
- Commit the file through the existing `git` function with a message that says it is a pulled row
  (`"pull the approval recorded on a clock that runs ahead"`), as `git pull` + the status-log union
  driver would leave it.
- Fail fast with a clear message when no approved row is found, so a broken fixture is never read as
  a product failure.
- Javadoc: name spec-kitty/spec-kitty#6260 as the authorising issue and state explicitly that this
  is a narrow, documented exception to ADR 2026-10-15-1 decision 6 (builders never write CLI-managed
  state) used only to model a teammate's clock-skewed approval arriving by pull. The reducer's
  handling of that row is the behaviour under test, so the row must look exactly like a pulled one.

### T005 — Compile and run

- Toolchain: a JDK 25 and the pinned Gradle. On this host they are at
  `/home/exedev/.local/jvm/temurin-25` and `/tmp/sk6260-tools/tools/gradle-8.14.5/bin`.
  Never commit `.tools/`, a JDK path or a Gradle path.
- Compile: `gradle compileTestJava --no-daemon` in `acceptance-jvm/`.
- Run only this feature (adhoc pass, no full suite):
  `gradle test --no-daemon -Dcucumber.filter.tags='@status'` (or `-Dcucumber.filter.name='rejection
  recorded after an approval'` if the area tag is not present). Read
  `acceptance-jvm/build/acceptance/adhoc/cucumber.json` for the per-step result.
- The runner builds a wheel from the checkout and installs it into a throwaway venv; that is
  expected and slow the first time. Do not run the whole suite.

## Definition of Done

- `gradle compileTestJava --no-daemon` passes.
- The two drafted scenarios run green with their existing steps (the `@wip` tags may still be present
  — WP02 removes them).
- No product code, no `tests/scenarios/**` file and no docs file is modified.
- The restamp helper's javadoc names #6260 and the decision-6 exception.
- Every new step follows the Arrange/Act/Assert split and talks to the CLI only through
  `ScenarioContext`/`MissionLifecycle`.

## Risks and Reviewer Guidance

- A refusal of the out-of-order rejection is a finding: report it, do not weaken the assertion.
- Reviewer asks: is the restamp the only non-CLI write, and is it committed before the emit? Are the
  assertions positive (they fail on empty output)? Does the step reuse the shipped builders instead
  of growing a parallel one?
