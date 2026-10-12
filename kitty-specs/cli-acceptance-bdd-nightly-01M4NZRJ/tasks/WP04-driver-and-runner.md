---
work_package_id: WP04
title: SpecKittyDriver port, process driver, isolation & runner
dependencies:
- WP02
- WP03
requirement_refs:
- FR-007
- FR-008
- FR-009
- C-001
- C-002
- NFR-002
- SC-004
planning_base_branch: feat/cli-acceptance-bdd-nightly
merge_target_branch: feat/cli-acceptance-bdd-nightly
branch_strategy: Planning artifacts for this mission were generated on feat/cli-acceptance-bdd-nightly. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cli-acceptance-bdd-nightly unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-acceptance-bdd-nightly-01M4NZRJ
base_commit: 8ba8efbb286d53ef1cf29fb4b1fdd167362e733a
created_at: '2026-10-11T18:55:32.574186+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
phase: Phase 3 - Runner
history:
- at: '2026-10-11T17:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: java-jenny
authoritative_surface: acceptance-jvm/src/
create_intent:
- acceptance-jvm/src/test/java/kitty/acceptance/driver/SpecKittyDriver.java
- acceptance-jvm/src/test/java/kitty/acceptance/driver/CliProcessDriver.java
- acceptance-jvm/src/test/java/kitty/acceptance/env/ScenarioWorld.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/InitSteps.java
- acceptance-jvm/src/test/java/kitty/acceptance/RunCucumberTest.java
execution_mode: code_change
model: ''
owned_files:
- acceptance-jvm/src/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – SpecKittyDriver port, process driver, isolation & runner

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before reading anything else.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Implement the black-box harness under `acceptance-jvm/src/**`: the `SpecKittyDriver` port, the
`CliProcessDriver`, the per-scenario isolated environment + temp git repo, the wheel-under-test
provisioning, the step definitions binding WP02's two init scenarios, and the JUnit-Platform
Cucumber runner with Allure reporting.

Done when `gradle test` (under the WP03 scaffolding) builds a wheel via `uv build`, installs it
into a temp venv, runs both init scenarios through the driver, and reports Cucumber/JUnit/Allure
results — while touching no real home or global Spec Kitty state.

## Context & Constraints

- **Depends on WP02** (the `.feature` scenarios + their step vocabulary) and **WP03** (`build.gradle`, pinned Gradle, verification metadata). Read WP02's `tests/scenarios/init/init.feature` and bind exactly its steps.
- **C-001 black-box**: steps call ONLY the `SpecKittyDriver` port. Never import Python; never call internal Java classes. Published contracts (e.g. `contracts/mission-status/openapi.yaml`) are allowed if needed.
- **C-002 provenance**: the CLI under test is a wheel built by `uv build` from the repo, installed into a throwaway venv. Never PyPI; never an editable install.
- **NFR-002 hermeticity**: redirect `SPEC_KITTY_HOME`, `HOME`, `USERPROFILE`, the XDG dirs and `LOCALAPPDATA` inside the per-scenario temp dir; set UTF-8, `NO_COLOR`, a fixed `COLUMNS`.
- Spec refs: FR-007, FR-008, FR-009, C-001, C-002, NFR-002, SC-004.
- Package/paths in `create_intent` are a suggested layout — adjust names but keep everything under `acceptance-jvm/src/**`.

## Branch Strategy

- **Strategy**: already-confirmed
- **Planning base branch**: feat/cli-acceptance-bdd-nightly
- **Merge target branch**: feat/cli-acceptance-bdd-nightly

## Subtasks & Detailed Guidance

### Subtask T011 – `SpecKittyDriver` port

- **Purpose**: The single seam steps depend on (FR-007).
- **Steps**: Define an interface with a method like `CliResult run(List<String> args, Path cwd)` returning a value object `{ int exitCode; String stdout; String stderr; JsonNode json; Path workingTree; }`. Provide a helper to parse `--json` output. Keep it implementation-agnostic.
- **Files**: `acceptance-jvm/src/test/java/.../driver/SpecKittyDriver.java`, `CliResult.java`.

### Subtask T012 – `CliProcessDriver`

- **Purpose**: The real process implementation (FR-007).
- **Steps**: Implement with `ProcessBuilder`: launch the installed `spec-kitty` (from the temp venv, T013) with the given args and cwd; **drain stdout/stderr** on separate threads to avoid deadlock; enforce a **timeout** (fail the step on expiry); on exit/timeout **kill descendant processes** (`process.descendants()` / `toHandle().destroyForcibly()`); **normalise line endings** (CRLF→LF) before comparison; compare paths via `toRealPath()`.
- **Files**: `acceptance-jvm/src/test/java/.../driver/CliProcessDriver.java`.
- **Notes**: This is the cross-OS stability core — Windows descendant-kill and path canonicalisation matter most here.

### Subtask T013 – Wheel-under-test provisioning

- **Purpose**: Install exactly what ships (FR-009, C-002).
- **Steps**: Once per JVM test run (e.g. a JUnit `BeforeAll` / Gradle setup task), run `uv build` to produce a wheel from the repo, create a temp venv, and `pip install` (or `uv pip install`) the built wheel into it. Expose the venv's `spec-kitty` entry point to `CliProcessDriver`. Never use PyPI; never `pip install -e`.
- **Files**: `acceptance-jvm/src/test/java/.../env/CliUnderTest.java` (or similar).
- **Notes**: cache the built wheel/venv across scenarios on one run for speed; rebuild per run, not per scenario.

### Subtask T014 – Isolated env + temp git repo (+ positive control)

- **Purpose**: Hermeticity (NFR-002, FR-008).
- **Steps**: For each scenario, create a temp dir; `git init` a repo inside it (the fixture repo, so a scenario can observe git state); set env `SPEC_KITTY_HOME`, `HOME`, `USERPROFILE`, `XDG_*`, `LOCALAPPDATA` to paths inside the temp dir; set `LANG`/`LC_ALL` UTF-8, `NO_COLOR=1`, a fixed `COLUMNS`. Tear down after. **Positive control**: assert the scenario observably wrote inside the temp dir (so "didn't touch real home" is non-vacuous).
- **Files**: `acceptance-jvm/src/test/java/.../env/ScenarioWorld.java`.

### Subtask T015 – Step definitions for the two init scenarios

- **Purpose**: Bind WP02's Gherkin to the driver (FR-003/FR-004 execution).
- **Steps**: Implement Cucumber step defs for exactly the step vocabulary WP02 authored (e.g. `Given an initialized project for agents "…"`, `When I run "spec-kitty …"`, `Then the directory "…" exists`, `Then the repository has no new commits`). Each step calls only `SpecKittyDriver`. Assert on files/exit/`--json`/git state — never on Python internals.
- **Files**: `acceptance-jvm/src/test/java/.../steps/InitSteps.java`.

### Subtask T016 – JUnit-Platform Cucumber runner + Allure + tag filter

- **Purpose**: Make it runnable and reportable (FR-006, FR-011 shape).
- **Steps**: Add the JUnit-Platform Cucumber runner (suite annotation or `junit-platform.properties`) pointing at `../tests/scenarios`; register `allure-cucumber7-jvm`; honour the tag filter passed via `-Dcucumber.filter.tags` so the nightly can select `not @wip and not @manual` or `@wip`.
- **Files**: `acceptance-jvm/src/test/java/.../RunCucumberTest.java`, `acceptance-jvm/src/test/resources/junit-platform.properties`.

## Test Strategy

- The scenarios ARE the tests. Validate by running `gradle test -Dcucumber.filter.tags="not @wip and not @manual"` locally (see `quickstart.md`) and confirming both init scenarios pass against the built wheel. Run on at least one POSIX OS; note any Windows-specific handling for reviewers.

## Risks & Mitigations

- **Deadlock on undrained streams** → drain on separate threads.
- **Zombie descendants on Windows** → `destroyForcibly()` on the descendant handles.
- **Flaky path comparison** → `toRealPath()` both sides; normalise line endings before asserting.
- **Non-hermetic leak** → all home-ish env vars redirected; positive control proves the temp dir is used.

## Review Guidance

- Confirm steps touch only the driver (no Python import, no internal Java), the wheel is `uv build` in a temp venv, env isolation covers all named vars with a positive control, and both init scenarios pass.

## Progress & Status

- Record a note: `spec-kitty agent tasks add-history WP04 --note "…"`
- Change status: `spec-kitty agent tasks move-task WP04 --to <status>`

## Activity Log

- 2026-10-11T19:19:11Z – claude – shell_pid=3126083 – Implemented black-box harness under acceptance-jvm/src/**: SpecKittyDriver port + CliResult + dependency-free Json parser, CliProcessDriver (ProcessBuilder, separate-thread stdout/stderr drain, 2m timeout, descendant destroyForcibly, CRLF->LF, toRealPath), CliUnderTest (uv build wheel -> temp venv -> uv pip install, once per run), ScenarioWorld (redirected HOME/USERPROFILE/SPEC_KITTY_HOME/XDG_*/LOCALAPPDATA + UTF-8/NO_COLOR/COLUMNS, temp git fixture, SHA-256 snapshot compare, NFR-002 positive control), InitSteps binding WP02's exact Gherkin, and junit-platform.properties glue. gradle test ran GREEN end-to-end against the built wheel: 2 init scenarios, 0 failures; Allure results emitted. Runner via junit-platform.properties + build.gradle sysprops (no @Suite, which would double-run).
