---
work_package_id: WP02
title: Gate the scenario, add the positive control, record the change
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-008
- FR-009
- NFR-002
- C-002
- SC-002
- SC-003
planning_base_branch: issue-6260-bind-event-traceability-scenario
merge_target_branch: issue-6260-bind-event-traceability-scenario
branch_strategy: Planning artifacts for this mission were generated on issue-6260-bind-event-traceability-scenario. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6260-bind-event-traceability-scenario unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
- T009
- T010
- T011
phase: Phase 2 - Gate the scenario
history:
- at: '2026-11-01T15:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/scenarios/status/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/scenarios/status/event-traceability.feature
- tests/scenarios/README.md
- docs/development/testing/acceptance-scenarios.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs:
- '6260'
---

# Work Package Prompt: WP02 – Gate the scenario, add the positive control, record the change

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Take the `@wip` tags off the two drafted scenarios now that WP01 bound them, add the same-fixture
positive control that proves the fixture, and record the user-visible change.

- `@wip`, `@wip-owner:stijn-dejongh` and `@wip-since:2026-10-15` are gone; the two drafted scenarios
  keep every Given/When/Then line they had.
- A third scenario consolidates a Mission whose only decision is the approval and succeeds.
- `@promise:<id>` is **not** added: the id is a QA-team assignment from the promise registry and
  tooling never invents one. Note it as pending in the PR hand-off, not in the feature file.
- The per-PR contract test reports zero errors, and the docs freshness check reports zero errors.

## Context

- WP01 added the step vocabulary: `a Mission whose work package "<wp>" has been approved`,
  `a reviewer records a rejection of "<wp>" after that approval`,
  `a reviewer has recorded a rejection of "<wp>" after that approval`, `I consolidate the Mission`,
  `the work package "<wp>" is sent back for rework`, `"<wp>" is not reported as approved`,
  `consolidation is refused because "<wp>" is not approved`.
- `tests/scenarios/README.md` lists the available steps and the tag vocabulary; the testing guide
  `docs/development/testing/acceptance-scenarios.md` explains drafting, binding and the gating pass.
- The feature's maintainer notes currently say the scenario is `@wip` and unbound; they must now say
  it is bound and gating, keep the #6260 tracker reference, and record the crafted-pull exception.

## Detailed Guidance

### T006 — Remove the tags

- Delete the `@wip @wip-owner:stijn-dejongh @wip-since:2026-10-15` line above `Feature:`.
- Do not touch a single Given/When/Then line of the two drafted scenarios. If a step wording does not
  match WP01's definition, fix the definition's expression, not the scenario.
- Update the maintainer notes: unbound -> bound; "runs only in the non-gating @wip pass" -> "gates the
  nightly"; keep the note that the pytest regression is the guard and this is the promise it satisfies.

### T007 — Positive control

Add one scenario to the same feature. It proves the fixture, not a second promise:

```gherkin
  Scenario: The approval stands when it is the last decision
    Given a Mission whose work package "WP01" has been approved
    And the mission "demo" has been accepted
    When I consolidate the Mission
    Then the command succeeds
    And the branch "work" has the file "src/wp01/__init__.py" mentioning "hello from WP01"
```

- Reuse the shipped `the mission "<name>" has been accepted` step and the existing branch/file
  assertion; add no new step for it.
- It uses the same Arrange and the same `I consolidate the Mission` Act as the refusal scenario, so a
  fixture that failed to approve or accept cannot let the refusal pass.

### T008 — README step table

Add the new steps to `tests/scenarios/README.md` "Available steps": three Arrange rows (approved work
package; rejection after that approval), two Act rows (rejection after that approval; consolidate the
Mission), three Assert rows (sent back for rework; not reported as approved; consolidation refused
because a work package is not approved). Keep alphabetical/grouped style consistent with the table.

### T009 — Testing guide

In `docs/development/testing/acceptance-scenarios.md`:

- If the guide states which promises are still drafted, update the `status/` area description to say
  the event-traceability scenarios gate the nightly after #6260.
- Add one short paragraph under "Write a scenario" or the step-structure section recording that a
  fixture may model a teammate's clock-skewed status row arriving by pull, as the one documented
  exception to the Arrange writes allowance (ADR 2026-10-15-1 decision 6), citing #6260 and
  `MissionLifecycle.plantFutureStampedApproval`.
- Keep the `doc_status` front matter valid; bump `updated:` to the mission date.

### T010 — Changelog

Add one `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink):
a bold impact-first lead with `(#6260)`, then before/after, under 1,200 characters. Impact: the
work-package decision-ordering promise now gates the nightly acceptance suite on every supported OS
instead of running in the non-gating drafts pass.

### T011 — Checks

- `uv run --frozen pytest -q tests/architectural/test_scenario_contract.py` (expect pass; if it
  reports `UNBOUND_STEP` for this feature, the binding is wrong — fix the binding).
- `python -m scripts.ci.scenario_contract --features tests/scenarios --steps acceptance-jvm/src/test/java`
  (expect exit 0).
- `uv run python -m scripts.docs.check_docs_freshness --ci` (expect `errors=0`).
- Re-run the feature in the acceptance-jvm runner in the gating pass
  (`-Pacceptance.pass=gating` restricted with `-Dcucumber.filter.tags` is refused by the build; use
  the adhoc name filter for the single feature, and record which pass you ran).

## Definition of Done

- The feature file has no `@wip*` tag and no `@promise:` tag; its two drafted scenarios are unchanged
  step for step, plus the new positive-control scenario.
- The contract test and docs freshness check pass with zero errors.
- The changelog entry is under 1,200 characters with the `(#6260)` reference.
- No file under `acceptance-jvm/` is modified (WP01 owns it).

## Risks and Reviewer Guidance

- The biggest risk is weakening an assertion to get a green run. Reviewer asks: does every drafted
  assertion survive word for word? Is the positive control on the same fixture? Is the promise id
  absent rather than invented?
- If the gating runner finds a real product failure, stop and report it; do not re-tag `@wip`.
