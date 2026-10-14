---
work_package_id: WP06
title: '[PR A] P2 Contract models and build spike (FR-015, D-79)'
dependencies:
- WP05
requirement_refs:
- FR-015
- C-001
- C-004
- NFR-005
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T03:25:18.593506+00:00'
subtasks:
- T037
- T038
- T039
- T040
- T041
- T042
- T043
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/
create_intent:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/build/SkipReportNestedBuildTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/build/PlantedClassCoverageNestedBuildTest.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/build.gradle.kts
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/dto/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/dto/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/ContractDriftProbe.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/contract/ContractDriftNestedBuildTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/build/SkipReportNestedBuildTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/build/PlantedClassCoverageNestedBuildTest.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP06 – [PR A] P2 Contract models and build spike (FR-015, D-79)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: PR A (draft, stacked on the branch that carries #5529's last slice). **Phase tag**: P2 (plan section 11). WP06 runs beside WP07 (P4) and WP09 (P5) after WP05; WP11 (P6 decoders) and WP12 (P8 ports) depend on it ("`P2` must be merged into the stack before P8": the shared mappers and the hand-DTO decision depend on it).
- **Work package dependency**: WP05 (P3). Nothing here reads the resolved state; the dependency exists because no other functional change may land before the reduction (D-44, D-110).
- **External dependency (not a `dependencies` entry)**: the orchestrator-merged #5529 re-cut tip must be in the branch before WP01 started; the P0 baseline record is committed. #957 cannot merge before #5529 (C-005). No agent pushes, opens or retargets a PR; #5533's Java work stacks on PR A.
- **Named edits (out-of-map; not in `owned_files`)**. Rule for each: rebase first, state the edit in the commit message, touch nothing else of the file.
  1. `tests/ci/test_mission_status_api_build.py`: **the three clauses the build change turns red, and nothing else**, in the **same commit** as the `build.gradle.kts` change (T042): the `MODELS_LIST` literal and its needle in `generation_violations`, and the generated-mode clause of `contract_package_violations`. Operator-approved exception to C-004 (S-23, E-9, D-154, ruled 2026-10-13). WP17 (P13 part 1) owns the file afterwards.
  2. `M/research.md`: **created by this WP as its first commit** (the spike record and the hand-DTO decision table); appended by WP11 later. A `kitty-specs/` path, so a named edit and not an `owned_files` entry of a `code_change` WP (header fork F2 of `wps.yaml`).
  3. `M/traces/approach.md`: append-only tracer entry (never in `owned_files`).
- **Write scope**: `owned_files` only. `S/build.gradle.kts` is edited by this WP **only**; a later need is a reviewed amendment of this WP, not a parallel edit (shared-file table).
- **Aliases used below**: `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Side-first layout paths exist after the #5529 re-cut (plan section 1.1); `adapter/**` is unchanged by the re-cut, so every path in this prompt exists at the checkout today except the new `dto/` directory and the new test files.

## Objective

Make the contract models of the five detail operations available to the service without editing the contract: extend the explicit generation list to the closure of the five operations' response schemas, decide per model by the D-79 go/no-go rule whether the generated class or a hand-written record is used, write every hand record that decision names with its drift sensor, and add the skipped-test report hook. The branch stays green in the same commit.

## Context

- **Why**: FR-015. Every real response of the five operations is validated against `contracts/mission-status/openapi.yaml`. Consumption follows #5529's rule: generate from the split contract root; fall back to a hand record where generation is unusable. The controllers (PR B) are hand-written and implement no generated `*Api` interface (a generated `@RequestParam` would put the framework's boolean converter on `includePrompt` and a framework exception on `path`, plan 11 "P2's go/no-go rule").
- **Current state (read it, do not assume)**: `S/build.gradle.kts` runs `openApiGenerate` with `generatorName.set("spring")`, the `FILTER` normalizer `operationId:getProject|listMissions`, `apis` empty, `interfaceOnly` true, `typeMappings OffsetDateTime -> String`, and the explicit list `"models" to "MissionOverview,MissionOverviewPage,MissionProgress,PageCursorRefusal,PageInfo,Problem,Problem_1,Project,StatusLaneCounts,StreamCursor,Workspace"`. The pin `tests/ci/test_mission_status_api_build.py` repeats that list as `MODELS_LIST` (line 53) and checks it as `f'"models" to "{MODELS_LIST}"'` in `generation_violations`; `contract_package_violations` demands "generated mode: the hand-mode dto package must not be populated" when `adapter/in/http/dto` exists. `ContractDriftProbe` (`J/adapter/in/http/`, package-private) holds one hand-written compile-time reference per mutation target (`new MissionOverview().blockedCount(1)`, `new Project().currentBranch("main")`), and `ContractDriftNestedBuildTest` (kit source set; the name ends in `NestedBuildTest`) builds a copy of the service against a mutated copy of the contract and expects `cannot find symbol`.
- **Go/no-go rule (D-79, verbatim)**: generated models are used for every new schema **unless** the spike shows any of (a) a required-nullable member does not serialise as `null` through the canonical mapper; (b) member or map-entry order differs from the golden (`ORDER_MAP_ENTRIES_BY_KEYS` sorts map entries by Java `String` natural order, UTF-16, while the golden sorts by code point; the open `subtasks` map is the one member where that can differ, so the mapper emits it through a code-point-ordered list serializer and fixture `unicode-subtask-ids` of class `detail-populated` pins it: S-15); (c) `WorkPackage.promptMarkdown` cannot be omitted when not requested (the generated model writes `null`). On a miss, that model (certainly `WorkPackage`) is a hand record in `adapter.in.http.dto` (rule 9 already lists the package) with `@JsonInclude(NON_NULL)` on `promptMarkdown` only.
- **Single owner (D-111)**: this WP writes **every** hand record that the decision table names, each with its hand drift reference in `ContractDriftProbe` and its mutation target in `ContractDriftNestedBuildTest`; no route phase adds a record to `adapter/in/http/dto`. The `tests/ci` pin follows the same set (`HAND_DTO_RECORDS`, E-9).
- **Red-first form (a spike)**: the drift-probe mutation target of each new model is red when its member is renamed in a contract copy, and the skip-report test is red without the hook.
- **E-7 is given**: the plan expects a local `nativeCompile nativeTest nativeSmoke` at the first native-visible decoder (WP11, P6), not here. Hand records are not served by any controller in PR A, so nothing here is native-visible.
- **C-001**: `contracts/**` is untouched. **AC-19.4**: no new dependency; `gradle/verification-metadata.xml`, the wrapper and `libs.versions.toml` are untouched.

### Subtask T037: First commit - research.md and the extended models list

**Purpose**: Open the spike with its record and extend the generated closure.

**Steps**:
1. **C-005 pre-flight, first step of the phase (D-107)**, from the repository root (`<scratch>` is outside the repository):
   ```bash
   export LC_ALL=C.UTF-8
   .venv/bin/python contracts/tools/bundle.py --root contracts --out "<scratch>/bundle-out" --module mission-status --bundle-only
   export CONTRACT_BUNDLE="<scratch>/bundle-out/bundle/mission-status/openapi.yaml"
   export CONTRACT_BUNDLE_SHA256="$(sha256sum "$CONTRACT_BUNDLE" | cut -d' ' -f1)"
   cd services/mission-status-api && ./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'
   cd ../.. && git log -1 --format=%H refs/remotes/m5529/lane-b      # the ref that carries #5529; record the sha in the FIRST commit message
   grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' services/mission-status-api/src/test services/mission-status-api/build.gradle.kts
   grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github
   ```
2. Create `M/research.md` (the first commit of the WP): a heading per section, the date, the command log of the spike, and a table skeleton for T038. Public-hygiene rule: placeholders `<repo>`, `<scratch>`; no home path, user name, address or token.
3. **Derive the closure by reading the contract, not by memory.** The five operations are `getMission`, `getWorkPackage`, `getWorkPackageDetail`, `listArtifacts`, `getArtifactContent` (`contracts/mission-status/paths/`, `responses/`). Follow every `$ref` from their 200 and refusal responses transitively through `contracts/mission-status/schemas/`. At this checkout the closure of `MissionDetail`, `WorkPackage`, `WorkPackageDetail`, `ArtifactListing`, `ArtifactContent`, `WorkPackageDetailRefusal`, `ArtifactRefusal` is (indicative; recompute it with a script and paste the script and result in `research.md`): `Actor`, `ActorHandle`, `ArtifactContent`, `ArtifactEntry`, `ArtifactKind`, `ArtifactListing`, `ArtifactPath`, `ArtifactReference`, `ArtifactReferences`, `ArtifactRefusal`, `ArtifactRefusalCode`, `Assignment`, `Authored`, `Cancellation`, `ChangeState`, `DependencyRef`, `HistoryEntry`, `LifecycleStatus`, `MissionDetail`, `MissionHead`, `MissionId`, `MissionPhase`, `MissionProgress`, `OwnedFile`, `Readiness`, `RelativeReference`, `Review`, `ReviewCycle`, `ReviewOverride`, `ReviewResult`, `ReviewVerdict`, `Staleness`, `StatusLane`, `StatusLaneCounts`, `StreamCursor`, `Subtask`, `SubtaskProgress`, `Topology`, `WorkPackage`, `WorkPackageDetail`, `WorkPackageDetailRefusal`, `WorkPackageDetailRefusalCode`, `WorkPackageSummary`, `Workspace`, `WpId`. The generator names inline duplicates `Name_1`; the existing list shows `Problem_1`. Generate once with the candidate list, read `S/build/generated/openapi/.../model/` and add any missing or `_1` name the compiler asks for (a missing name is a compile error where it is referenced, an extra one is harmless; the comment above the task says so).
4. Edit **only** the `"models" to "..."` literal of the `openApiGenerate` task in `S/build.gradle.kts`. The `FILTER` stays `operationId:getProject|listMissions`, `apis` stays empty, `interfaceOnly` stays true: no `*Api` interface gains a method. Refresh the comment above the task (it says "the two in scope") to name the closure of the seven operations' models, keeping the sentence true.
5. Do **not** commit the `build.gradle.kts` change in isolation: the pin turns red on it. Hold it for T042's commit, or commit T037's `research.md` alone first and let the build edit travel with T042 (see T042).

**Files**: `M/research.md` (new, about 80 lines at this point), `S/build.gradle.kts` (the models literal, held for T042).

**Validation**: `cd S && ./gradlew --no-daemon openApiGenerate compileJava` succeeds on the candidate list; the generated model directory holds every name; the closure script's output is in `research.md`.

### Subtask T038: Decide generated versus hand DTO per model (D-79)

**Purpose**: Make the go/no-go decision a recorded table, not a guess.

**Steps**:
1. For each generated model of the closure, run the three checks of the D-79 rule through the **canonical mapper** (`MissionStatusApplicationJson.mapper()`; `CanonicalJsonMessageConverter.canWrite` accepts only classes under `org.speckitty.missionstatus.adapter.in.http.`): (a) build an instance with a required-nullable member left null and serialise it: is the member written as `"member":null`? (b) serialise an instance with several members and one map: is the member order alphabetical and the map-entry order the golden's? The only member that can differ is the open `subtasks` map of `WorkPackage` (UTF-16 against code point order, S-15); (c) serialise `WorkPackage` with `promptMarkdown` unset: is the member absent, or written as `null`?
2. A small throwaway harness in `T/adapter/in/http/dto/` (test-scoped, kept only if it becomes a real test in T039) is the way to run the checks; do not use reflection in `application` or `domain`.
3. Write the **decision table** in `M/research.md`: one row per model (model, check a, check b, check c, decision `generated` or `hand`, the hand class name when `hand`, the reason). It lists the hand-DTO class names exactly; T039 and T042 consume that list, and `HAND_DTO_RECORDS` of the pin is that list. Expected, to be confirmed or refuted by the checks: `WorkPackage` is hand (check c; the generated model writes `null`). Every other model is generated unless a check says otherwise. If the table decides that **no** model is hand (check c passes through a generated `@JsonInclude` setting you can justify), say so and `HAND_DTO_RECORDS` is empty and the `dto` directory must not exist.
4. Cite the mapper evidence (the exact serialised text) for every `hand` row so a reviewer can re-run it.

**Files**: `M/research.md` (decision table, about 60 lines).

**Validation**: the table has a row for every model of the closure; every `hand` row has a failing check quoted; every `generated` row passes all three.

### Subtask T039: Write every hand record the table names

**Purpose**: One owner for every hand record (D-111), with the response-validation coverage.

**Steps**:
1. For each `hand` row create `J/adapter/in/http/dto/<Name>.java`: a Java record whose components are the schema's properties in the schema's member names, `@JsonInclude(JsonInclude.Include.NON_NULL)` **on `promptMarkdown` only** (every other member is written, including explicit nulls, exactly as the golden shows). Nested objects refer to the generated models (`adapter.in.http.model.*`) where those were decided `generated`; a hand record composed of generated members is fine. The open `subtasks` map is emitted through a code-point-ordered serializer (a `@JsonSerialize` on the component that writes the entries sorted by `CodePoints.compare`, `domain.model.CodePoints` exists) so the UTF-16 default cannot reorder it; fixture `unicode-subtask-ids` of class `detail-populated` (WP07) pins it later.
2. Rule 9 of `ArchitectureRules` already lists the package `adapter.in.http.dto`; the records import no Spring and no `domain` class other than records and enums of `domain.model` (rule 15 bounds the controllers, not these, but keep them dependency-light).
3. Tests under `T/adapter/in/http/dto/**` (owned): one test per record that (i) serialises a fully populated instance and compares to the exact bytes the contract example shows (the examples live under `contracts/mission-status/examples/`; use one that exists, e.g. a `WorkPackage.*` example, read it from the contract root, never from a copy), (ii) serialises an instance with `promptMarkdown` unset and asserts the member is absent, (iii) serialises with `promptMarkdown` set and asserts it is present, (iv) validates the output against the bundled schema with the same networknt validator `ResponseContractValidationTest` uses (call its test-support helper; do not duplicate the validator wiring).
4. **No controller, no mapper and no wiring is added**: PR A serves no route. The records are unused at runtime until WP13 (the first route WP).

**Files**: `J/adapter/in/http/dto/<Hand>.java` (about 60 to 120 lines each; certainly `WorkPackage`), tests (about 150 lines each).

**Validation**: `test --tests 'org.speckitty.missionstatus.adapter.in.http.dto.*'` green; each test seen red first (red-first loop on the records).

### Subtask T040: Extend ContractDriftProbe and ContractDriftNestedBuildTest

**Purpose**: Contract drift fails the build for every new model, generated or hand (AC-15.3).

**Steps**:
1. `J/adapter/in/http/ContractDriftProbe.java` (package-private, hand-written compile-time references): add **one reference per new generated model** that the mutation will rename or remove a member of, in the style of `new MissionOverview().blockedCount(1)`. Keep the two existing references.
2. For each hand record the probe needs a **hand drift reference**. A compile-time reference to a hand record cannot fail when the contract changes, because a hand record is not generated. See "Plan defects found" item 1 for the mechanism this WP adopts and records in `research.md`: keep the schema of every hand record in the generated closure (its generated twin, unused at runtime, is the drift sensor) and reference one member of the twin in the probe next to the reference to the hand record's accessor, so a renamed member in the contract copy stops the probe compiling; and add a parity test (T039 tests) that compares the hand record's property names with the schema's property names read from the bundled contract.
3. `T/adapter/in/http/contract/ContractDriftNestedBuildTest.java` (kit source set): add one mutation target per new model, following the existing method shape (copy the service sources, copy the contract root, mutate one schema file in the copy, `runner(copy, mutated).buildAndFail()`, assert `cannot find symbol` and the renamed member). The existing positive control (the unmutated copy compiles) stays and now also covers the larger model set. Use the schema files that actually define each member (for example `MissionHead.yaml` for `MissionOverview.blockedCount`); read the schema before choosing the member.
4. Keep the helper methods (`copyService`, `copyTree`, `runner`, `dropCurrentBranch`) and the `@Timeout(1800)`; the nested build copies `src/main/java` only, so the probe and the hand records are part of the copy.

**Files**: `ContractDriftProbe.java` (edit, about +40 lines), `ContractDriftNestedBuildTest.java` (edit, about +100 lines).

**Validation**: `cd S && ./gradlew --no-daemon kitTest --tests '*ContractDriftNestedBuildTest'` green: the control compiles, each mutation fails with `cannot find symbol`.

### Subtask T041: Skipped-test report hook, SkipReportNestedBuildTest (D-101) and PlantedClassCoverageNestedBuildTest (AC-19.3)

**Purpose**: A JUnit skip is green in `check`; a precondition-unmet case must still be visible in the job summary.

**Steps**:
1. In `S/build.gradle.kts`, in the `tasks.named<Test>("test") { ... }` block (it already sets `useJUnitPlatform`, `excludeTags("native-binary", "perf")` and `finalizedBy("jacocoTestReport")`), add a `doLast` that, if `build/reports/not-run.txt` exists and is non-empty, copies it to the file named by the `GITHUB_STEP_SUMMARY` environment variable when that variable is set (append, UTF-8) and prints it to standard output otherwise. No file means no output and no failure. The tests of later phases (`Utf8Host.assumeUtf8()`, `RealPermissionFixture`, WP10 and PR B) append lines of the form `not run: precondition unmet: <test id>` to `build/reports/not-run.txt`; this WP writes none, only the hook.
2. `T/build/SkipReportNestedBuildTest.java` (kit source set; `T/build/**` is included by the kit patterns `**/org/speckitty/missionstatus/build/**` and `**/*NestedBuildTest.java`, `S/build.gradle.kts` lines 270 to 277): a TestKit nested build of a copy of the service holding one test class that appends a `not run: precondition unmet: <id>` line to `build/reports/not-run.txt` and skips by assumption. Assertions: with the hook, the build output (standard output leg) contains the line; with `GITHUB_STEP_SUMMARY` pointing at a temporary file (pass it through the TestKit environment), that file contains it; **without the hook** (a copy of `build.gradle.kts` with the `doLast` removed) the output does not contain it and the test fails (the red-first control). Copy the nested-build scaffolding of `ContractDriftNestedBuildTest` (`copyService`, runner with `kit.gradleUserHome`); keep the nested test small so `kitTest` stays fast.
3. Do not add a workflow step: the hook alone is inside C-004.
4. AC-19.3 (planted untested class): `T/build/PlantedClassCoverageNestedBuildTest.java` (kit source set, in the pattern of `VerificationTamperTest`): a TestKit nested build of a copy of the service inputs plus one planted untested `domain.*` class fails with `jacocoTestCoverageVerification` red, and the unmutated copy passes. Revert-fails: plant nothing and the mutated-copy leg has no failure to find, so the test is red.

**Files**: `S/build.gradle.kts` (about +20 lines, travels with T042's commit), `T/build/SkipReportNestedBuildTest.java` (new, about 120 lines), `T/build/PlantedClassCoverageNestedBuildTest.java` (new, about 120 lines).

**Validation**: `kitTest --tests '*SkipReportNestedBuildTest'` green; remove the `doLast` in a scratch copy and the test is red (record this once in the notes).

### Subtask T042: The three pin clauses, in the same commit as the build change

**Purpose**: Keep the branch green at every commit (PLAN-FRESH2-001, D-125, S-23, E-9).

**Steps**:
1. In **one commit**, together with the `build.gradle.kts` models literal (T037) and the hook (T041), edit `tests/ci/test_mission_status_api_build.py` (a named edit; nothing else of the file): (a) replace the `MODELS_LIST` literal (line 53) with the new list, exactly the string now in `build.gradle.kts` (the needle in `generation_violations` is `f'"models" to "{MODELS_LIST}"'`, so changing the literal changes the needle with it; keep the needle's form); (b) replace the generated-mode clause of `contract_package_violations`, "generated mode: the hand-mode dto package must not be populated", by: **the `dto` directory holds exactly the hand records `research.md` names**. Add a recorded set `HAND_DTO_RECORDS` (the file names without `.java`) in the test, and make `contract_package_violations` take the actual set of `*.java` stems in `dto/` (or an empty set when the directory is absent) and report a violation for an extra record file and for a missing one; `_http_dirs()` (line ~1316) keeps feeding the directory-name set, add a second helper for the record stems.
2. Controls in the same file, in the style of the existing `test_the_package_pin_turns_red_for_...`: an extra record file is red; a missing one is red; the old `dir | {"dto"}` mutation is replaced by the new pair. Keep the rule-9 literal checks and the api/model-package checks exactly.
3. Staging order: stage the new `dto/` files and tests **before** running the pin (the tracked-path scan reads `git ls-files` of `S`, and the Windows-filename guard reads it repo-wide; a guard run before staging passes vacuously).
4. Commit message states: the three clauses changed, why (the build change turns them red), the E-9 / S-23 exception, and the #5529 tip sha.

**Files**: `tests/ci/test_mission_status_api_build.py` (named edit, about +40 lines).

**Validation**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` green at that commit; `.venv/bin/ruff check tests/ci/test_mission_status_api_build.py` and `.venv/bin/ruff format --check --force-exclude tests/ci/test_mission_status_api_build.py` clean; `git diff` of the pin shows only the three clauses.

### Subtask T043: Gate

**Purpose**: Exit the phase on the plan's P2 gate.

**Steps** (UTF-8 locale, bundle variables exported, new files staged first):
1. C-005 pre-flight again on the final tree (T037 step 1).
2. `cd services/mission-status-api && ./gradlew --no-daemon openApiGenerate compileJava`.
3. `./gradlew --no-daemon kitTest --tests '*ContractDriftNestedBuildTest' --tests '*VerificationTamperTest' --tests '*SkipReportNestedBuildTest' --tests '*PlantedClassCoverageNestedBuildTest'` (named files, not the nested-build suite).
4. `./gradlew --no-daemon --dependency-verification strict bootJar testClasses` (this WP touches `build.gradle.kts`; the freshness check of `gradle/verification-metadata.xml` beside `VerificationTamperTest`).
5. **Gate G**: `./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`. The hand records and the generated models are under `adapter/**`, which the coverage class set excludes, so no JaCoCo count changes.
6. **Gate P** green at the tip: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`.
7. `git diff --stat origin/<base>..HEAD -- contracts gradle` shows no change (C-001, AC-19.4); `gradle/libs.versions.toml` and `verification-metadata.xml` unchanged.
8. Python hygiene for the one Python file: `.venv/bin/ruff check . && .venv/bin/ruff format --check .`; `make format-check-files FILES="tests/ci/test_mission_status_api_build.py"`; `.venv/bin/ruff check --select TID251 .`; the Windows-filename guard `tests/architectural/test_no_invalid_windows_filenames.py` after staging.

**Validation**: all green; record exact commands and counts.

## Self-contained green

- **Fixtures with tests**: the hand-record tests read the contract examples from `contracts/mission-status/examples/` and build their other inputs in the tests; nothing reads a golden of WP07/WP08 (not yet present). `SkipReportNestedBuildTest` carries its own nested test source. No fixture tree is added under `R/`.
- **Floors and counts**: `R/jacoco-class-floor.properties` is not touched (no `domain`/`application` class is added; `adapter/**` is outside the coverage class set, `S/build.gradle.kts` `coverageClassDirectories`). The native floors (`--floor 3`, `--request-floor 49`) and `requests.json` are unchanged (PR A adds no `@Tag("native")` test; plan section 11 "What PR A needs from P13").
- **No forward reference**: no test or gate here names a type of a later WP (`MissionDetail` read models, `DetailRefusal`, `HttpHarness#startWith` are WP10, WP12 and later). The hand records only compose generated models and `domain.model` records.
- **Pin clauses kept green**: the models-list literal, its needle and the `dto`-directory clause (edited here in one commit with the build change; E-9); the rule-9 literals (WP03 and WP12 write them, untouched here); the `adapter/in/http` sub-directory names (`dto` is the only addition; `detail` arrives with WP12); the `EventsController` needles (WP02, untouched); `ContractDriftProbe` presence and its needles (`new MissionOverview().blockedCount(1)`, `new Project().currentBranch("main")` stay verbatim); the timestamp mapping (`typeMappings`, untouched); the tracked-path scan (stage first).
- **Mission record**: `M/research.md` is a new add-only file (archive-freeze: `M/**` is not on `main` while PR A is open); `M/meta.json` is not touched; `M/status.json` stays the materialisation of `status.events.jsonl` (`spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`), never hand-edited, no untracked CLI state committed blind. That keeps `cutover-guard`, `mission-state audit` (`.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`, run before a push of an `M/**` change) and `corpus-blocking` green (plan section 11 Mission-record bullet).
- **Native**: the generated models and hand records are not constructed or served at start-up in PR A; no reflection hint is needed here. The first native-visible bean is WP11's decoder.

## Plan defects found

1. **"Hand drift reference" is undefined for a hand record.** The plan (section 11 P2 row, section 6 `ContractDriftProbe` fact) requires "a hand drift reference per hand record" and "a mutation target per new model", but the existing probe works because a **generated** model loses a member when the contract copy is mutated; a hand-written record is not generated, so a compile-time reference to it cannot fail on contract drift. Adopted here and to be recorded in `M/research.md`: keep the schema of each hand record in the explicit models list (its generated twin is unused at runtime and is the compile-time drift sensor, referenced in `ContractDriftProbe` next to the hand record), plus a parity test of property names against the bundled schema. If the twin cannot coexist (a name clash in `adapter.in.http.model` against `adapter.in.http.dto` is not expected because the packages differ), fall back to the parity test alone with a mutation target that asserts the parity test goes red on a renamed member, and report the change to the orchestrator.
2. **`HAND_DTO_RECORDS` can be empty.** The plan says "certainly `WorkPackage`", but the decision is the spike's; if no record is hand, the `dto` clause must still be rewritten (the directory must not exist). T042 covers both outcomes.
3. **F2 fork (open, header of `wps.yaml`)**: `M/research.md` ownership is a named edit because a `code_change` WP cannot own a `kitty-specs/` path; WP11 appends. Not decided here.

## Definition of Done

- `M/research.md` exists with the spike record, the closure script and result, and the decision table naming every hand record (T037, T038).
- The explicit models list covers the closure; `FILTER`, `apis` and `interfaceOnly` unchanged; `openApiGenerate compileJava` green (T037).
- Every hand record exists in `adapter/in/http/dto` with its tests and response-validation coverage; no other record is added by any route phase (T039).
- `ContractDriftProbe` and `ContractDriftNestedBuildTest` carry one mutation target per new model; the unmutated control compiles; each mutation fails with `cannot find symbol` (T040).
- The skipped-test report hook is in `build.gradle.kts`; `SkipReportNestedBuildTest` is green with it and red without it (T041).
- The three pin clauses are edited in the same commit as the build change; Gate P green at every commit that touches either (T042).
- Gate G, the kit tests, the strict-verification command, Gate P and the `contracts/`-untouched check are green and recorded (T043). Evidence of subtask completion is `.venv/bin/spec-kitty agent tasks mark-status <Txxx> --status done --mission mission-status-read-api-mission-detail-01M4S6D5` per subtask, not a ticked checkbox.

## Risks

- **Pin red between commits**: the build change and the pin edit must be one commit; otherwise a tip is red. Mitigation: T042 step 1.
- **Closure drift**: a missed `_1` duplicate name is a compile error far from the cause. Mitigation: generate, read the generated directory, compile; keep the derivation script in `research.md`.
- **`kitTest` cost and flakiness**: nested builds are slow and use `--offline`. Mitigation: run the three named classes only; classify a failure (never retry to green).
- **Supply chain**: any dependency or verification-metadata change is out of scope (AC-19.4); if `--dependency-verification strict` fails, stop and report instead of regenerating metadata by hand.
- **Ordering of map entries**: UTF-16 against code point. Mitigation: the serializer on the open `subtasks` map and WP07's `unicode-subtask-ids` fixture.
- **Scope creep**: no controller, mapper or wiring here; PR A serves no route.

## Reviewer Guidance

- Verify the red-first form of this phase: the drift mutation of each new model is red when its member is renamed, and `SkipReportNestedBuildTest` is red without the hook; a vacuous red is a rejection.
- `git diff` of `tests/ci/test_mission_status_api_build.py` shows **only** the models literal, its needle and the `dto` clause (plus controls); `contracts/**`, `gradle/**` and the version catalog are unchanged.
- The `build.gradle.kts` diff is the models literal, its comment and the `doLast` hook; `FILTER`, `apis` and `interfaceOnly` are untouched.
- `research.md` has the decision table with the quoted mapper evidence for every hand row; `HAND_DTO_RECORDS` in the pin equals that list.
- `@JsonInclude(NON_NULL)` is on `promptMarkdown` only; every other member keeps explicit nulls.
- No record is added to `dto/` by a later WP (one owner, D-111).
- Run the implied gates by name (`ContractDriftNestedBuildTest`, `VerificationTamperTest`, `SkipReportNestedBuildTest`, `ArchitectureRulesTest`), not a bare directory.

## Implementation command

```bash
.venv/bin/spec-kitty agent action implement WP06 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
