---
work_package_id: WP01
title: 'RealHomeFingerprint: scope policy, excused surfaces, non-vacuity control'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-003
- SC-002
- SC-003
- SC-004
planning_base_branch: issue-7026-acceptance-real-home-shared-host
merge_target_branch: issue-7026-acceptance-real-home-shared-host
branch_strategy: Planning artifacts for this mission were generated on issue-7026-acceptance-real-home-shared-host. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7026-acceptance-real-home-shared-host unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-acceptance-real-home-shared-host-01M6EJXK
base_commit:
created_at: '2026-11-02T17:00:13.440100+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - The narrowed fingerprint and its control
history:
- at: '2026-11-02T17:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: acceptance-jvm/src/test/java/kitty/acceptance/environment/
create_intent:
- acceptance-jvm/src/test/java/kitty/acceptance/environment/RealHomeFingerprint.java
execution_mode: code_change
model: ''
owned_files:
- acceptance-jvm/src/test/java/kitty/acceptance/environment/RealHomeFingerprint.java
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7026'
---

# Work Package Prompt: WP01 – `RealHomeFingerprint`: scope policy, excused surfaces, non-vacuity control

## ⚡ Do This First: Load Agent Profile

```bash
spec-kitty agent profile show python-pedro
spec-kitty charter context --action implement --include agent-profile:python-pedro
```

## Objective

Add **one** package-private class, `RealHomeFingerprint`, in
`acceptance-jvm/src/test/java/kitty/acceptance/environment/`. It owns three things and nothing else:

1. the *comparison scope* — `strict` (today's whole-tree comparison) or `shared-host` (the same tree
   minus two per-mission runtime-state subtrees);
2. the fingerprint string of a root, with one `Files.walk` and the fields the current guard already
   reports (`files=`, `newestMtime=`, `bytes=`, or `absent`);
3. a runtime negative control that proves a narrowed comparison still detects a genuine leak.

`ScenarioLifecycle` is WP02's file; do not edit it here.

## Requirements

- **T001 — scope resolution.** `static boolean sharedHost(Map<String,String> env)`:
  truthy(`SPEC_KITTY_ACCEPTANCE_SHARED_HOST`) **and** not truthy(`GITHUB_ACTIONS`). Truthy =
  `1`, `true`, `yes`, `on`, trimmed and case-insensitive; anything else (including absent) is false.
  Passing the map in keeps the function pure — the control and the guard can exercise both scopes
  without mutating the process environment. Name both environment variables as constants with a
  comment saying why CI refuses the switch (spec FR-003, C-002).
- **T002 — excused surfaces.** In `shared-host` scope only, a *regular file* is excused when the first
  path component below the fingerprinted root is `spec-kitty-prompts` or `gate-locks`. Match the `Path`
  component (`root.relativize(file).getName(0)`), never a joined string, so Windows separators and
  nested directories behave. A file at the root, or one under a sibling such as `credentials`, is never
  excused. The existing `*.lock` filename exclusion stays in **every** scope, exactly as today.
  Declare the two names once as constants; the class comment must name their production owners
  (`src/runtime/next/_tmp_namespace.py`'s `SPEC_KITTY_PROMPT_NAMESPACE` and the `gate-locks` directory
  of `src/spec_cli/review/pre_review_gate.py`) so a reader can verify the literals.
- **T003 — fingerprint.** `String value()` returns the same string `main` produces for the same tree in
  strict scope, byte-identical, so a strict-mode message keeps its shape (NFR-002). Same single walk,
  same three stats, same `absent` sentinel for a missing root. Do not sort, hash or reformat.
- **T004 — non-vacuity control.** `static void proveStillDetectsLeaks(Path scratchRoot)` builds one
  small synthetic tree under `scratchRoot`, fingerprints it in both scopes, and checks four
  expectations on that single fixture:
  1. a planted file at the tree root (a leak) changes the fingerprint in **both** scopes;
  2. a planted file under `spec-kitty-prompts/<hex>/` changes it in **strict** scope;
  3. the same planted file does **not** change it in **shared-host** scope;
  4. appending a byte to that already-excused file still does not change the shared-host fingerprint.
  On any failure throw `IllegalStateException` naming the exact expectation that broke and the scope it
  broke in (NFR-004) — never a skip, never a warning. The control removes what it created before it
  returns (best-effort, like `ScenarioLifecycle.deleteQuietly`), so a later walk of the scenario tree
  cannot mistake it for output.

## Constraints

- No new dependency: the class uses `java.nio.file`, `java.util`, and nothing else. The subproject has no
  JUnit Jupiter engine, so do not add a test class here; the control *is* the executable proof and it
  runs inside the acceptance suite (nightly, three OSes).
- `javac` must be clean with the Java 25 toolchain; this module has no checkstyle, but keep the code in
  the style of its neighbours (package-private `final class`, javadoc on the class and on the control,
  no `var`-heavy style changes elsewhere).
- Do not touch `ScenarioWorld`, the step classes or any feature file.

## Verification

1. `javac -d <tmp> acceptance-jvm/src/test/java/kitty/acceptance/environment/RealHomeFingerprint.java`
   with the JDK 25 toolchain compiles clean.
2. Compile the class together with a throwaway `main` **outside the repository** (a scratch directory
   under the system temp root) that calls `proveStillDetectsLeaks` and prints both scopes over a synthetic
   tree: the run must show a root-level write changing both fingerprints and a prompt write changing
   only the strict one. This is the red/green proof for SC-002/SC-003/SC-004; do not commit the harness.
3. Report the four observed expectations in the WP completion note.

## Definition of done

- `RealHomeFingerprint.java` exists, compiles, and holds T001–T004.
- The throwaway harness shows the four expectations holding, and a deliberately broken expectation
  (for instance, excusing every file) makes the control raise.
- No file outside `owned_files` is modified.
