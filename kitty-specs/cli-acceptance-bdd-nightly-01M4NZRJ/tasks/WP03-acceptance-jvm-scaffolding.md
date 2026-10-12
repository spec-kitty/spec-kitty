---
work_package_id: WP03
title: acceptance-jvm Gradle scaffolding + supply-chain pinning
dependencies: []
requirement_refs:
- FR-005
- FR-006
- C-006
- NFR-003
planning_base_branch: feat/cli-acceptance-bdd-nightly
merge_target_branch: feat/cli-acceptance-bdd-nightly
branch_strategy: Planning artifacts for this mission were generated on feat/cli-acceptance-bdd-nightly. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/cli-acceptance-bdd-nightly unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-cli-acceptance-bdd-nightly-01M4NZRJ
base_commit: b656680ab0bf339055691a7e731702bc9c32df0f
created_at: '2026-10-11T18:31:40.969615+00:00'
subtasks:
- T008
- T009
- T010
phase: Phase 3 - Runner
history:
- at: '2026-10-11T17:40:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: java-jenny
authoritative_surface: acceptance-jvm/
create_intent:
- acceptance-jvm/build.gradle
- acceptance-jvm/settings.gradle
- acceptance-jvm/tools/pins.json
- acceptance-jvm/gradle/verification-metadata.xml
- acceptance-jvm/README.md
execution_mode: code_change
model: ''
owned_files:
- acceptance-jvm/build.gradle
- acceptance-jvm/settings.gradle
- acceptance-jvm/tools/**
- acceptance-jvm/gradle/**
- acceptance-jvm/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – acceptance-jvm Gradle scaffolding + supply-chain pinning

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter before reading anything else.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Stand up the `acceptance-jvm/` Gradle subproject, mirroring the **`contracts/`** supply-chain
precedent exactly, wired to run Cucumber-JVM 7 on the JUnit Platform under **Java 25**, reading the
scenarios from `../tests/scenarios` in place.

Done when:
- `settings.gradle` + `build.gradle` declare the runner's deps and toolchain and point the test resources at `../tests/scenarios`.
- `tools/pins.json` pins the Gradle distribution (version + sha256), reusing `contracts/tools/install_tools.py` for install.
- `gradle/verification-metadata.xml` is Gradle-**generated** and committed.
- No committed wrapper jar / `gradle-wrapper.properties` / `gradlew`.

> This WP owns only the Gradle scaffolding + pinning. The driver port, step definitions, env
> isolation and the wheel build live in WP04 (`acceptance-jvm/src/**`).

## Context & Constraints

- **Study the precedent first**: `contracts/settings.gradle`, `contracts/build.gradle`, `contracts/tools/pins.json`, `contracts/tools/install_tools.py`, `contracts/gradle/verification-metadata.xml`, `contracts/README.md`. See research.md §2 for the exact mechanics.
- **Pins to mirror**: Gradle `8.14.5`, sha256 `6f74b601422d6d6fc4e1f9a1ab6522f642c2fdcbc15ae33ebd30ba3d7198e854`, url `https://services.gradle.org/distributions/gradle-8.14.5-bin.zip`.
- **JDK divergence**: `contracts/` uses Java 21; `acceptance-jvm` uses **Java 25** (ADR requirement). Do NOT copy the `java-version` verbatim.
- **Deps**: Cucumber-JVM 7 (`io.cucumber:cucumber-java`, `cucumber-junit-platform-engine`), JUnit Platform, `io.qameta.allure:allure-cucumber7-jvm`. Pin exact versions and let them land in the generated verification metadata.
- **Reuse, don't copy** `contracts/tools/install_tools.py` (single canonical installer) — reference it from the README and (later) the nightly workflow; do not fork it into `acceptance-jvm/tools/`.
- Spec refs: FR-005, FR-006, C-006, NFR-003. Supply chain: DIRECTIVE_051.

## Branch Strategy

- **Strategy**: already-confirmed
- **Planning base branch**: feat/cli-acceptance-bdd-nightly
- **Merge target branch**: feat/cli-acceptance-bdd-nightly

## Subtasks & Detailed Guidance

### Subtask T008 – settings.gradle + build.gradle

- **Purpose**: Define the subproject and its test toolchain.
- **Steps**:
  1. `acceptance-jvm/settings.gradle`: name the project (e.g. `rootProject.name = 'acceptance-jvm'`); include the `contracts/` comment verbatim-in-spirit: *"Invoked with a pinned Gradle distribution; there is no committed wrapper jar (see contracts/tools/install_tools.py and acceptance-jvm/tools/pins.json)."*
  2. `acceptance-jvm/build.gradle`: Java toolchain `languageVersion = JavaLanguageVersion.of(25)`; dependencies on Cucumber-JVM 7 + `cucumber-junit-platform-engine` + JUnit Platform + `allure-cucumber7-jvm`; a `test` task on the JUnit Platform; pass the Cucumber tag filter through a system property (`-Dcucumber.filter.tags`); point Cucumber's feature glue at `../tests/scenarios` (features) in place (no copy).
- **Files**: `acceptance-jvm/settings.gradle`, `acceptance-jvm/build.gradle`.
- **Notes**: a build-dir comment must mark `verification-metadata.xml` as generated, never hand-edited (mirror `contracts/build.gradle`).

### Subtask T009 – pins.json + README

- **Purpose**: Pin the Gradle distribution and document the supply-chain workflow.
- **Steps**:
  1. `acceptance-jvm/tools/pins.json`: one entry `name: "gradle"`, `kind: "archive"`, `version: "8.14.5"`, the `url` + `sha256` above, plus provenance strings mirroring `contracts/tools/pins.json`.
  2. `acceptance-jvm/README.md`: document installing the pinned Gradle via the shared installer — `python contracts/tools/install_tools.py --pins acceptance-jvm/tools/pins.json --dest "$RUNNER_TEMP/tools" --only gradle` — and the metadata-generation command `gradle --write-verification-metadata sha256 <tasks> --no-daemon`.
- **Files**: `acceptance-jvm/tools/pins.json`, `acceptance-jvm/README.md`.

### Subtask T010 – Generate verification-metadata.xml

- **Purpose**: Pin every resolved JVM dependency by sha256.
- **Steps**: With the pinned Gradle installed, run `gradle --write-verification-metadata sha256 test --no-daemon` in `acceptance-jvm/` and commit the generated `acceptance-jvm/gradle/verification-metadata.xml` (schema `dependency-verification-1.3.xsd`, `verify-metadata=true`, `verify-signatures=false`, `origin="Generated by Gradle"`). Never hand-edit it.
- **Files**: `acceptance-jvm/gradle/verification-metadata.xml`.
- **Notes**: WP05 generalizes `gradle_pin_check.py` to cross-check this file; keep the Gradle version consistent with `pins.json`.

## Test Strategy

- The acceptance scenarios run under Gradle (WP04 binds steps). For THIS WP, a green `gradle help`/`gradle dependencies` under the pinned distribution with verification enabled is the smoke test. No pytest here.

## Risks & Mitigations

- **Hand-edited metadata** → always regenerate; never edit by hand.
- **JDK mismatch** → Java 25 everywhere (toolchain + the nightly's setup-java in WP06).

## Review Guidance

- Confirm the pinning mirrors `contracts/` (sha256-checked distribution, no wrapper jar), Java 25, deps pinned in generated metadata, and the test reads `../tests/scenarios` in place.

## Progress & Status

- Record a note: `spec-kitty agent tasks add-history WP03 --note "…"`
- Change status: `spec-kitty agent tasks move-task WP03 --to <status>`

## Activity Log

- 2026-10-11T18:43:57Z – claude – shell_pid=3054327 – Scaffolded acceptance-jvm/ Gradle subproject mirroring contracts/ precedent: settings.gradle (names project, no committed wrapper jar), build.gradle (Java 25 toolchain, Cucumber-JVM 7 + cucumber-junit-platform-engine + JUnit Platform + allure-cucumber7-jvm, test task on JUnit Platform, -Dcucumber.filter.tags passthrough, reads ../tests/scenarios in place), tools/pins.json (Gradle 8.14.5 sha256-pinned), README.md (shared installer + metadata-gen commands). Generated gradle/verification-metadata.xml via pinned Gradle 8.14.5: 51 components, all origin=Generated by Gradle; verified green.
