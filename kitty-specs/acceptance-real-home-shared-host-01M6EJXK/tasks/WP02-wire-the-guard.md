---
work_package_id: WP02
title: Wire the guard into the scenario lifecycle and report the scope
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- FR-005
- NFR-001
- NFR-003
- NFR-004
- C-001
- C-002
- SC-001
- SC-004
planning_base_branch: issue-7026-acceptance-real-home-shared-host
merge_target_branch: issue-7026-acceptance-real-home-shared-host
branch_strategy: Planning artifacts for this mission were generated on issue-7026-acceptance-real-home-shared-host. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7026-acceptance-real-home-shared-host unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-acceptance-real-home-shared-host-01M6EJXK
base_commit: 34a3100d624004ff993c8279baf1cb89fa3fb5ad
created_at: '2026-11-02T17:12:33.706396+00:00'
subtasks:
- T005
- T006
- T007
phase: Phase 2 - Wire the guard
history:
- at: '2026-11-02T17:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: acceptance-jvm/src/test/java/kitty/acceptance/environment/
create_intent:
- acceptance-jvm/src/test/java/kitty/acceptance/environment/ScenarioLifecycle.java
execution_mode: code_change
model: ''
owned_files:
- acceptance-jvm/src/test/java/kitty/acceptance/environment/ScenarioLifecycle.java
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7026'
---

# Work Package Prompt: WP02 – Wire the guard into the scenario lifecycle and report the scope

## ⚡ Do This First: Load Agent Profile

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

## Objective

`ScenarioLifecycle` keeps its shape — it captures the real-home state when a scenario starts and
compares it in `assertObservedWriteInsideTempDir()` — but it delegates the comparison to WP01's
`RealHomeFingerprint`, names the scope in the failure message, and runs the non-vacuity control once per
scenario.

## Requirements

- **T005 — fingerprint wiring.** Replace the `realHomeBefore` string field and the private static
  `fingerprint(Path)` helper with one `RealHomeFingerprint` built from
  `Path.of(System.getProperty("user.home"), ".spec-kitty")` and the process environment
  (`System.getenv()`). Keep the field-initializer timing: the "before" value must still be taken when
  the scenario starts, before any CLI invocation. `assertObservedWriteInsideTempDir()` compares
  `fingerprint.value()`. Delete the old helper rather than leaving a second implementation (C-003).
- **T006 — scope in the message.** The failure text keeps its current shape and gains one token:
  `The scenario changed the real <root> (scope=strict|shared-host, before: ..., after: ...)`. Strict-mode
  text therefore differs from today only by that token; the before/after values are unchanged
  (NFR-002).
- **T007 — control invocation.** Call `RealHomeFingerprint.proveStillDetectsLeaks(<a directory under the
  scenario temp root>)` once, from the constructor, before the "before" fingerprint is captured, and
  let the class clean up after itself. It must not use the redirected home (`homeDir`): writing there
  would satisfy the "redirection took effect" positive control by itself. If the control raises, let the
  exception propagate — a scenario that cannot prove its guard is not a pass (NFR-004).
- Update the class javadoc paragraph "The real home stayed clean." to say what is compared, in which
  scope, and why the two subtrees are excused — the docs page (WP03) cites this class as the owner.

## Constraints

- One `Files.walk` of the real home per scenario (NFR-001); the control's tree is three small files.
- No shared mutable static state: four scenarios run in parallel, each with its own temp root
  (NFR-003).
- The redirected-home positive control and `cleanUp()` keep their current behaviour and order.
- Do not edit `RealHomeFingerprint.java` (WP01) or any feature file (C-001).

## Verification

1. `gradle -p acceptance-jvm compileTestJava --no-daemon` (JDK 25 on `PATH`) compiles.
2. Ad-hoc acceptance run on this host, narrowed to a feature directory (an init script overriding
   `cucumber.features` is fine; it is local and not committed), with
   `SPEC_KITTY_ACCEPTANCE_SHARED_HOST=1`: **zero** "changed the real" failures.
3. The same run **without** the switch: the concurrent-mission prompt writes still fail the guard
   (strict scope unchanged) — this is SC-004 and proves the switch, not the code, relaxed the check.
4. Plant a file at the root of the real `~/.spec-kitty` for the duration of one scenario run (create it,
   run, delete it) and confirm the guard still fails, in shared-host scope, naming that file's effect —
   SC-002 through the production entry point. If touching the real home is unacceptable on this host,
   say so and rely on the WP01 control instead; either way record which proof ran.

## Definition of done

- `ScenarioLifecycle.java` uses the new class, reports `scope=`, and runs the control.
- 2, 3 and 4 above are recorded with their observed counts.
- No file outside `owned_files` is modified.
