# Implementation Plan: Bind the event-traceability acceptance scenario

**Branch**: `issue-6260-bind-event-traceability-scenario` | **Date**: 2026-10-30 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/bind-event-traceability-scenario-01M6BTXK/spec.md`
**Research**: [research.md](research.md)

## Summary

The feature file `tests/scenarios/status/event-traceability.feature` states the promise that the last
decision recorded on a work package counts: a rejection recorded after an approval sends it back, and
the Mission cannot consolidate while that work package is rejected. Its two scenarios are `@wip` and
unbound. This plan binds them with Arrange/Act/Assert step definitions in `acceptance-jvm/`, adds a
same-fixture positive control, and removes the `@wip` tags so the scenarios join the gating nightly.
No product code changes.

## Technical Context

**Language/Version**: Java 25 (test harness, `acceptance-jvm/`); Gherkin feature files under `tests/scenarios/`
**Primary Dependencies**: Cucumber-JVM 7.20.1, JUnit Platform, AssertJ 3.27.7, PicoContainer
**Storage**: filesystem only; the CLI's `status.events.jsonl` event log is the state under test
**Testing**: Cucumber-JVM acceptance run of the gating pass, plus the per-PR
`tests/architectural/test_scenario_contract.py` (`scripts/ci/scenario_contract.py`)
**Target Platform**: Linux/macOS/Windows nightly; the change is platform-neutral
**Project Type**: repository-internal acceptance harness (no shipped product surface)
**Performance Goals**: each bound scenario finishes inside the nightly leg's existing budget; the
Mission adds no sleep, retry or polling
**Constraints**: the harness drives the CLI as a separate process and never imports Python; the only
non-CLI state write is the crafted pulled approval row the issue authorises
**Scale/Scope**: two bound scenarios plus one positive control; ~6 step definitions and ~4 helpers

## Charter Check

| Gate | Status |
|------|--------|
| ATDD-first (`ATDD-First Discipline`, DIRECTIVE_034) | The red proof is the gating scenario contract: removing `@wip` before binding turns `UNBOUND_STEP` into an error and fails `test_real_tree_is_non_empty_and_clean`. Bind first, prove green, then drop the tag in the same change. |
| Single canonical authority | The status log is written by the CLI; the fixture restamps one row to simulate a pulled clock-skewed approval and says so in its javadoc. |
| Locality of change (DIRECTIVE_024) | Edits are confined to `acceptance-jvm/`, the one feature file, the testing guide and the changelog. |
| Terminology canon | "Mission", "work package", "lane", "consolidate" are used as the CLI uses them; no new vocabulary. |
| NO_FULL_HEAVY_SUITES_IN_MISSION | Only the feature under binding is run in the acceptance runner, plus the scenario contract test. |
| Pre-existing Failure Reporting Rule | Any red outside this diff is reproduced on pristine `origin/main` and reported, not muted. |
| Code Quality / test quality (DIRECTIVE_041) | Every new step guards a promise assertion; no test-only helper is added without a caller. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/bind-event-traceability-scenario-01M6BTXK/
├── plan.md
├── research.md
├── spec.md
├── tasks.md
└── traces/{approach,design-decisions,tooling-friction}.md
```

### Source Code (repository root)

```
tests/scenarios/status/event-traceability.feature   # bind: tags come off; one positive-control scenario added
tests/scenarios/README.md                           # available-steps table gains the new steps
acceptance-jvm/src/test/java/kitty/acceptance/
├── environment/MissionLifecycle.java               # + the crafted-pull approval restamp helper
├── steps/ArrangeSteps.java                         # + approved-state and rejection-after-approval arrangements
├── steps/ActSteps.java                             # + rejection act, consolidation act
└── steps/AssertSteps.java                          # + rework / not-approved / consolidation-refusal assertions
docs/development/testing/acceptance-scenarios.md    # binding status and the crafted-pull note
docs/changelog/CHANGELOG.md                         # [Unreleased] entry
```

## Phase 0 — Research

Recorded in [research.md](research.md): D1–D8 (mission shape, step reuse, crafted row, real CLI act,
refusal message, positive control, no invented promise id) with evidence and three open questions
(QA promise id, ADR decision-6 wording, emitter refusal behaviour).

## Phase 1 — Design

### Step vocabulary

| Group | Step | Behaviour |
|-------|------|-----------|
| Arrange | `Given a Mission whose work package "<wp>" has been approved` | `MissionLifecycle.planMission("demo", [wp])` then `advance("demo", wp, "approved")`; fails fast with the CLI output if the approved state was not reached. |
| Arrange | `Given a reviewer has recorded a rejection of "<wp>" after that approval` | Reuses the same rejection routine as the Act step: restamp the approval row into the future, then emit `approved -> in_progress`. |
| Act | `When a reviewer records a rejection of "<wp>" after that approval` | Same routine, recording the CLI result for the assertions. |
| Act | `When I consolidate the Mission` | `spec-kitty consolidate --mission <slug> --yes`, recorded like any Act. |
| Assert | `Then the work package "<wp>" is sent back for rework` | Reads `spec-kitty agent tasks status --mission <slug> --json` and requires exactly one entry for `<wp>` in lane `in_progress`. |
| Assert | `Then "<wp>" is not reported as approved` | The same status read must not report `approved` for `<wp>` anywhere; the rework lane must be visible, so the assertion cannot pass on empty output. |
| Assert | `Then consolidation is refused because "<wp>" is not approved` | The last result exits non-zero, the output names the merge-readiness refusal and names `<wp>`. |

### The crafted pulled approval row

`MissionLifecycle.plantFutureStampedApproval(name, wp)`:

1. Resolve the Mission folder from the slug the builder already holds.
2. Read `status.events.jsonl`, find the row whose `wp_id` is `<wp>` and `to_lane` is `approved`.
3. Parse its `at`, add a fixed ten minutes, write the row back with the new `at` as ISO-8601; never
   add `lamport_clock` (the CLI does not write one for lane transitions).
4. Commit the file, as `git pull` + the status-log union driver would have.

The javadoc names #6260 and the ADR 2026-10-15-1 decision-6 exception explicitly, so no later reader
mistakes it for a licence to write CLI state from a builder.

### Positive control

A third scenario in the same feature: plan the Mission, move `WP01` to `approved`, accept it, then
`When I consolidate the Mission` and require the command to succeed and
`src/wp01/__init__.py` (mentioning `hello from WP01`) to be on the target branch `work`. It uses the
same Arrange builders and the same Act step as the refusal scenario, so a fixture that silently fails
to approve or accept cannot let the refusal assertion pass.

### Red-first proof

The shipped per-PR contract test is the red lever for a missing binding: dropping `@wip` while the
steps are unbound makes `scripts/ci/scenario_contract.py` report `UNBOUND_STEP` as an error and fails
`tests/architectural/test_scenario_contract.py::test_real_tree_is_non_empty_and_clean`. Order of work:
add the step definitions, then remove the tags, then run the contract test and the feature in the
acceptance-jvm runner.

For the runtime red proof, plant the defect the scenario is meant to catch: with the approval row
**not** restamped into the future, an ordinary rejection must still send the work package back (the
scenario's own positive behaviour); with the restamp, the reducer's #4941 fix keeps the rejection last,
so the same assertions hold. If the tag came off with unbound steps, Cucumber reports the undefined
step and the scenario fails rather than passing.

## Phase 2 — Tasks

[task list generated by `spec-kitty tasks`; see tasks.md]

## Requirement coverage

| Requirement | Work package |
|-------------|--------------|
| FR-001, FR-002, FR-003, FR-004 | WP01 |
| FR-005, FR-006, FR-007 | WP02 |
| FR-008, FR-009; NFR-001..003; C-001..C-004 | WP02 (verification), WP01 (constraints in the code) |

## Risks

- **The emitter may refuse the out-of-order rejection.** The #4941 pytest guard treats a refusal as an
  accepted remedy; the scenario asserts the rework lane. If the CLI refuses, the scenario is red and
  the finding is reported to the owner rather than rewriting the scenario to accept both outcomes
  (Q3).
- **A status-log restamp could leave a dirty tree** that `consolidate` reports. Mitigation: commit the
  restamped row before the rejection emits, exactly as a pull leaves it.
- **Windows path/line-ending differences** in the restamp. Mitigation: read/write UTF-8 lines and let
  git's own autocrlf handling apply; no absolute machine paths in the diff.
