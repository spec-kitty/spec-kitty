---
work_package_id: WP02
title: Per-pass results and run metadata in acceptance-jvm
dependencies: []
requirement_refs:
- FR-008
- FR-009
- NFR-004
- C-002
- C-004
- C-005
planning_base_branch: ccr-002603b2-bip646
merge_target_branch: ccr-002603b2-bip646
branch_strategy: Planning artifacts for this mission were generated on ccr-002603b2-bip646. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into ccr-002603b2-bip646 unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
history: []
agent_profile: java-jenny
authoritative_surface: acceptance-jvm/
create_intent:
- acceptance-jvm/src/test/java/kitty/acceptance/environment/RunMetadata.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/RunHooks.java
execution_mode: code_change
model: ''
owned_files:
- acceptance-jvm/build.gradle
- acceptance-jvm/src/test/java/kitty/acceptance/environment/CliUnderTest.java
- acceptance-jvm/src/test/java/kitty/acceptance/environment/RunMetadata.java
- acceptance-jvm/src/test/java/kitty/acceptance/steps/RunHooks.java
- acceptance-jvm/README.md
role: implementer
tags: []
tracker_refs: []
---

# WP02: Per-pass results and run metadata in acceptance-jvm

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Implementation command: `spec-kitty agent action implement WP02 --agent claude --mission acceptance-scenario-contract-01M4T9GC`

---

## Objective

Give each nightly pass its own result folder chosen by one Gradle property, and stamp each pass's Allure results with the build that produced them.

## Context

Defect (#6136): the `@wip` pass, run with `--rerun-tasks`, rewrites the gating pass's Cucumber JSON and JUnit XML and mixes Allure results. Plan IC-02 holds the design. Local JDK is 21 and the build needs 25: verify in a scratch copy of `acceptance-jvm/` with `languageVersion = 21` (never commit that); CI compiles with 25.

### Subtask T004: Failing-first proof

- **Steps**: in the scratch copy, run `gradle test -Dcucumber.filter.tags="not @wip and not @manual"` then the `@wip` run with `--rerun-tasks`; record that `build/cucumber-report/cucumber.json` changed. Keep the transcript for the PR body.

### Subtask T005: `acceptance.pass` property in `build.gradle`

- **Steps**: read `findProperty('acceptance.pass')`; map `gating` → `not @wip and not @manual`, `wip` → `@wip`; unknown value fails configuration; giving both the property and `-Dcucumber.filter.tags` fails; with neither, keep the pass-through and use pass name `adhoc`. Output root `layout.buildDirectory.dir("acceptance/<pass>")`: `allure-results` via `systemProperty 'allure.results.directory'`, Cucumber plugin `json:<root>/cucumber.json`, `reports.junitXml.outputLocation = <root>/junit`, `binaryResultsDirectory = <root>/binary`. Declare the pass and filter as `inputs.property`. Pass `acceptance.pass` and the root to the JVM as system properties. Zero-scenario guard exempts only `wip`.
- **Validation**: gating then wip into one build dir leaves `acceptance/gating/` byte-identical (sha256 before and after).

### Subtask T006: `CliUnderTest.version()`

- **Steps**: keep the wheel path; parse the version as the second `-`-separated field of `spec_kitty_cli-<version>-....whl`; expose `version()`.

### Subtask T007: `RunMetadata` + static `@BeforeAll` hook

- **Steps**: `steps/RunHooks.java` with a static `io.cucumber.java.BeforeAll` that calls `RunMetadata.write(CliUnderTest.instance())`. `environment/RunMetadata.java` writes into `System.getProperty("allure.results.directory")`: `environment.properties` (`cli.version`, `commit.sha` from `GITHUB_SHA` else `git rev-parse HEAD`, `os.name`, `java.version`, `acceptance.pass`) and, only when `GITHUB_RUN_ID` is set, `executor.json` (`name: GitHub Actions`, `type: github`, `buildName`, `buildOrder` = run number, `buildUrl` = `$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID`). Use `Properties.store` / a small hand-written JSON with escaping. Update `acceptance-jvm/README.md` run instructions to `-Pacceptance.pass=gating|wip`.
- **Validation**: after a scratch run, both files exist with the keys.

## Definition of Done

- T004 to T007 done; scratch-copy run green for both passes; gating folder unchanged after the wip pass; no new dependency (verification metadata untouched).

## Risks

- Allure's property name: confirm `allure.results.directory` is honoured by 2.29.1 (check `io/qameta/allure/util/PropertiesUtils` in the jar).
- `@BeforeAll` runs once per JVM; keep it idempotent.

## Reviewer Guidance

- No shell-specific paths; Gradle layout APIs only. Black-box: no Python import, no project-state writes.
