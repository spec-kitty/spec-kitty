---
work_package_id: WP03
title: 'Phase 1b: Gradle scaffold, supply chain and skeleton service'
dependencies:
- WP02
requirement_refs:
- FR-014
- FR-011
- FR-012
- C-001
- C-002
- C-004
- C-007
- C-008
- C-009
- NFR-006
- NFR-007
- NFR-009
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-overview-01M4EMSA
base_commit: 4bb9af1d2a0c6c826c52f7952d406ca8df704d6f
created_at: '2026-10-11T11:36:51.699248+00:00'
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
- T017
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/
create_intent:
- services/mission-status-api/build.gradle.kts
- services/mission-status-api/settings.gradle.kts
- services/mission-status-api/gradle.properties
- services/mission-status-api/gradlew
- services/mission-status-api/gradlew.bat
- services/mission-status-api/.gitignore
- services/mission-status-api/src/main/resources/application.properties
- tests/ci/test_mission_status_api_build.py
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/build.gradle.kts
- services/mission-status-api/settings.gradle.kts
- services/mission-status-api/gradle.properties
- services/mission-status-api/gradlew
- services/mission-status-api/gradlew.bat
- services/mission-status-api/.gitignore
- services/mission-status-api/gradle/**
- services/mission-status-api/src/main/resources/application.properties
- services/mission-status-api/src/main/resources/META-INF/native-image/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/MissionStatusApplication*
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/skeleton/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/ProjectRootCheck*
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/build/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/skeleton/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/nativesmoke/**
- services/mission-status-api/src/nativeTest/**
- tests/ci/test_mission_status_api_build.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 - Phase 1b: Gradle scaffold, supply chain and skeleton service

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Create the standalone Gradle (Kotlin DSL) project `services/mission-status-api/` with its COMPLETE `build.gradle.kts`, supply chain (wrapper hash, version catalog, strict verification metadata, toolchain policy), a skeleton Spring Boot application that reads and validates `mission-status.project-root`, and the Python pinning tests, so that every later WP only adds source files and never edits the build script.

## Context

- Plan phase 1 ("scaffold" half; the spike half is WP02, the workflow half is WP04). Plan sections: 1 (seam, generated artifacts), 2 (regeneration commands), 5 (JaCoCo wiring and non-vacuity, pinning), 11 (phase 1 row, native test partition), 12 (toolchain policy, versions), 13 (layout, bind and configuration keys, Jackson). Spec FR-011, FR-014 (AC-14a to AC-14g), C-001/C-002/C-004/C-007/C-008/C-009, NFR-006/007/009.
- **Consume the WP02 decision record in `research.md` (spike record) first.** Decisions you apply: generated models versus hand DTOs (R-2 go/no-go), bundling mechanism A or B for `bundleContract`, native test wiring (dedicated `src/nativeTest` source set versus tag filter), JaCoCo pattern syntax, ArchUnit/networknt/JaCoCo versions, OS classifiers, JFR event name. If a record entry says "BLOCKED" or "escalated", stop and report.
- **The build script is phase 1's alone** (plan.md "Write-scope completeness"). Anything a later WP needs from the build (task registrations, source sets, dependencies) must exist here. Where a later need is discovered, it is a reviewed amendment to THIS WP's files, not a parallel edit.
- Ownership notes (PLAN-NEW5-001): `config/MissionStatusApplication*` and the `nativesmoke` test package are CREATED here and later amended by WP10 and WP12/WP16. They are not disjoint by pattern; they are made safe by dependency ordering (WP10 and WP12 depend on WP03 transitively, so they run in the same lane chain after it). Create them minimal.
- The `skeleton` main and test packages are created here. They are removed in two steps so the four native legs stay green at every tip: WP10 deletes only the skeleton contract-document route and its test (the real `ContractDocumentController` replaces them at the same path); the hello route (`adapter/in/http/skeleton/**`) stays, because the skeleton `NativeSmokeTest` and the WP04 native legs assert it, until WP12 replaces that smoke test and deletes the hello route together with it.
- **Claim precondition (lane-b is claimed first here; post-analyze ruling ANL-015).** Before claiming, WP07 is approved, or the orchestrator has confirmed the lane-a tip is clean.
- **Toolchain precondition (first step, before any other work).** The orchestrator provisioned GraalVM Community 25.0.2 and Gradle 9.7.1 once under a persistent prefix and put them on `JAVA_HOME`/`PATH` in this brief (`tasks-overview.md` section 10; WP02 recorded the versions and vendor checksums in `research.md`). Before T011 run `java -version` and `native-image --version` and `gradle --version` (the provisioned binary distribution, used only to create the wrapper in T011) and compare with that record; from T011 on, `./gradlew --version` must report Gradle 9.7.1. If any is missing or different: STOP and report BLOCKED (owner: orchestrator/operator). Do not substitute another JDK, do not install one, and do not skip a gate this WP lists as local: "CI is the proof" applies only to the three non-Linux-x64 legs.
- Directory/file names must avoid `< > : " \ | ? * $ { }` (NFR-009).
- Public repository: no absolute home-directory paths anywhere in committed files (placeholders only).

## Subtask T011: Wrapper, settings, properties, catalog and toolchain policy

**Purpose**: The reproducible, pinned build root (FR-014, C-002, C-008).

**Steps**:
1. `settings.gradle.kts`: `rootProject.name = "mission-status-api"`; NO foojay resolver plugin; NOT included in `contracts/settings.gradle`; dependency resolution management pointing at Maven Central and the Gradle plugin portal only.
2. `gradle.properties`: `org.gradle.java.installations.auto-download=false`; `org.gradle.daemon` left default (CI passes `--no-daemon`); no build-cache sharing property; no secrets.
3. Wrapper: from `services/mission-status-api/` run the PROVISIONED Gradle 9.7.1 (the install the orchestrator made, the same one WP02 T004 step 1 used for the scratch wrapper): `gradle wrapper --gradle-version 9.7.1 --gradle-distribution-sha256-sum <sha256 from the official .sha256 file, as re-verified in the WP02 record>`. That install is used only for this command; every later build uses `./gradlew`. Commit `gradle/wrapper/gradle-wrapper.jar`, `gradle-wrapper.properties` (must carry `distributionSha256Sum`), `gradlew` (executable bit) and `gradlew.bat`.
4. `gradle/libs.versions.toml`: every dependency and plugin by version-catalog alias, exact versions only (no `+`, no `latest`, no ranges): Spring Boot 4.1.1 plugin, spring-dependency-management as Boot requires, openapi-generator plugin 7.25.0 (equal to `contracts/tools/pins.json`), JaCoCo 0.8.15, networknt json-schema-validator 3.0.8, ArchUnit 1.4.2 (or the WP02 replacement), JUnit via the Boot BOM, Native Build Tools (Boot-managed version, recorded). Declare EVERY dependency any later WP needs now (the WP02 record fixes them, and its T004 steps 9 and 10 are what makes this list complete): the YAML parser WP19 uses for `.kittify/*.yaml` (the library WP02 T004 step 9 selected, mandatory), the nested-build mechanism WP10 T056 uses for AC-11c in generated mode (`gradleTestKit()` as a test dependency, or the alternative WP02 T004 step 10 proved; mandatory in BOTH generated and hand modes, because the standing `VerificationTamperTest` of T015 step 3 needs a nested build in either mode), the Jackson/JSON stack, test libraries for WP09 to WP13 (HTTP client, raw sockets need none). Both are declared as `testImplementation`/`implementation` entries that `check` resolves, so T015's single run covers them. `libs.versions.toml` and `verification-metadata.xml` are touched by this WP alone (plan.md chokepoint rule: dependency additions land in phase 1; a later addition is a reviewed amendment to this WP's files, regenerated by command, reviewed by command). NO springdoc and no swagger-ui anywhere (E-11, C-004).
5. `.gitignore`: `build/`, `.gradle/`, `*.class`, IDE directories. Verify no tracked path contains a Windows-illegal character.
6. `java { toolchain { languageVersion = JavaLanguageVersion.of(25) } }` with the vendor left unconstrained; `graalvmNative { toolchainDetection.set(false) }` so the image comes from `JAVA_HOME`.

**Files**: the Gradle root files above (new, about 200 lines in total).
**Validation**: `./gradlew --version` prints Gradle 9.7.1 and the wrapper verifies its checksum; `./gradlew help` is green on JDK 25.

## Subtask T012: The COMPLETE `build.gradle.kts`

**Purpose**: One build script that serves every phase (plan.md phase 1 row).

**Steps** (each item is a task or configuration that a later WP relies on):
1. Plugins and dependencies from the catalog only. Main: Spring Boot web (MVC, virtual threads), Jackson as per the WP02 decision. Test: JUnit 5, ArchUnit, networknt, Spring Boot test.
2. Contract consumption per the WP02 mode. Generated mode: `openApiGenerate` (spring generator, `interfaceOnly`, models, `apiPackage` `org.speckitty.missionstatus.adapter.in.http.api`, `modelPackage` `org.speckitty.missionstatus.adapter.in.http.model`, input = `contracts/mission-status/openapi.yaml`), output under `build/`, wired into `compileJava`, nothing generated committed. Generation is limited to `getProject` and `listMissions` by exactly the mechanism WP02 T005 criterion 8 recorded (trimmed input built at build time, normalizer filter, or `defaultInterfaces=false` with only the two in-scope methods overridden): put those settings here, because the contract tags six operations `Missions` and an unrestricted run yields five more live routes answering 501. Hand mode: no generator task and the openapi-generator plugin is NOT declared (no unused supply-chain surface); the package `adapter.in.http.dto` is reserved and the build test records the mode (T016).
3. `bundleContract`: per the WP02 mechanism A or B, writes `build/.../contract/openapi.yaml` into the main resources (`processResources` depends on it). A build output: never committed. Under mechanism B accept the downloaded file only after a SHA-256 check against a property.
4. `bootJar { archiveFileName = "mission-status-api.jar" }`; the project version stays `0.0.0-dev`.
5. JaCoCo: `jacocoTestReport` (XML + HTML); `jacocoTestCoverageVerification` with exactly three rules (LINE >= 0.90 on `org.speckitty.missionstatus.domain.*`, LINE >= 0.90 on `org.speckitty.missionstatus.application.*`, BRANCH >= 0.80 on `domain.*`; generated sources, `config`, `adapter.*` excluded); `check` depends on both the verification task and `jacocoScopeCheck`.
6. `jacocoScopeCheck` (verification task, runs after `jacocoTestReport`): parses the XML report and fails unless each include pattern matched at least the class count recorded in `src/test/resources/jacoco-class-floor.properties`. The tolerance is PER PATTERN: a pattern's line (and the whole file) may be absent only while the report holds no class matching THAT pattern; it fails on an absent line, an absent file or a zero floor as soon as one class matches that pattern. Hand-off of the file: WP05 creates it with the `domain` line (the first classes appear under `domain.*` there, so `check` must be green at WP05's tip while `application.*` is still empty), WP17 raises the `domain` line, WP06 adds the `application` line; the floor only ever rises. Implement it as ordinary Kotlin DSL with unit-testable parsing (a pure function) and cover it with a scratch run (T016), including the case "domain present with a line, application absent without a line" (green) and "domain present without a line" (red).
7. Native: GraalVM Native Build Tools via the Spring Boot plugin, `nativeCompile` and `nativeTest`; a dedicated `native`-tagged test source set wired per the WP02 decision (placeholder dir `src/nativeTest/java`), with `nativeTest` running ONLY `@Tag("native")` tests (ArchUnit, networknt and JaCoCo cannot run in native mode). Record the tag filter in the script. Also register `nativeTagJvmTest`, a JVM `Test` task over the same `native`-tagged classes, and make `check` depend on it, so the native-tagged tests are also exercised on the JVM (WP10/WP20 validate with it).
8. **Test partition (decided here, no later WP may edit the build script).** Three JUnit tags and four Test tasks, stated in the script:
   - Tag `native-binary` marks `NativeSmokeTest` and `NativePerfTest` (they need a built binary). The default `test` task EXCLUDES tag `native-binary` (`useJUnitPlatform { excludeTags("native-binary") }`), so `check` never runs them. Untagged JVM-only tests that live in the `nativesmoke` package (digest unit tests, the `requests.json` parse test) keep running in `test` and `check`.
   - `nativeSmoke` and `nativePerf` are `Test` tasks that include only tag `native-binary` plus a class filter (`NativeSmokeTest` resp. `NativePerfTest`). Each requires `-PnativeBinary=<path>`: a missing property fails the task with a clear message BEFORE any test starts, and the value is forwarded to the test JVM with `systemProperty("nativeBinary", ...)` (a Gradle `-P` property is not a system property by itself).
   - Tag `perf` marks the perf-ratio classes of WP13. The default `test` task also EXCLUDES `perf`; a `perfTest` `Test` task includes only tag `perf`, and `check` DEPENDS on `perfTest`. The 60 s NFR-004 hold is fixed by the spec and is therefore part of `check` (via `perfTest`), not an optional extra; there is no dependence on a WP02 timing record. Until WP13 adds the first `perf` class, `perfTest` finds no test and `check` (which depends on it) must still be green at every tip from WP03 on. Apply the WP02 T004 step 3 probe record: if it recorded that an empty tag-filtered `Test` task FAILS under Gradle 9.7.1, set the switch it named (expected: `failOnNoDiscoveredTests = false`) on `perfTest` and on any other tag-only `Test` task whose tests do not exist yet at this tip (`nativeTagJvmTest`, if its tag has no member at this tip), with a script comment citing the record; if the probe recorded that the empty task passes, set nothing and say so in the comment. Either way WP13's pin (at least two `@Tag("perf")` classes exist) is what keeps the task non-vacuous afterwards, so the setting never hides a missing perf class once WP13 is done.
9. State the partition in a script comment and keep it pinned by T016 step 10 (the pins parse the build script for each registration, each exclusion and each `check` dependency).
10. A `verifyNoSpringdoc` guard is NOT needed in Gradle; the dependency-absence test lives in `tests/ci/test_mission_status_api_build.py` (T016) and inspects every configuration of a resolved dependency report.

**Files**: `services/mission-status-api/build.gradle.kts` (new, about 250 lines).
**Validation**: `./gradlew help`; `./gradlew tasks --all` lists `bundleContract`, `jacocoScopeCheck`, `nativeSmoke`, `nativePerf`, `perfTest`, `nativeTagJvmTest` and (generated mode) `openApiGenerate`.

## Subtask T013: Skeleton application, `ProjectRootCheck`, packaged defaults and native hints

**Purpose**: The smallest service that exercises the whole toolchain (bind, config keys, one route, the contract-document route).

**Steps**:
1. `config/MissionStatusApplication` (public, `@SpringBootApplication`): reads `mission-status.project-root` through `adapter.out.filesystem.ProjectRootCheck` (created here; the directory check is not a file-API call in `config`, so ArchUnit rule 7 holds from this WP on). Absent or blank -> exit non-zero naming "project root unset"; not a directory -> exit non-zero naming the key (never an OS message).
2. `src/main/resources/application.properties` carrying EVERY default of plan section 13: `server.address=127.0.0.1`, `server.port=${mission-status.port:8787}`, `server.forward-headers-strategy=none`, `spring.threads.virtual.enabled=true`, `spring.mvc.async.request-timeout=-1`, `mission-status.stream.queue-capacity=1024`. No `springdoc.*` property.
3. `adapter.in.http.skeleton`: one hello controller (`GET /api/v1/hello`, returns a fixed body; it stays until WP12 replaces the smoke test that asserts it) and a skeleton contract-document route (class `SkeletonContractDocumentController`) serving the bundled `contract/openapi.yaml` classpath resource unchanged at `GET /api/v1/openapi.yaml` (WP10 deletes this route and its test, replacing them with the real controller).
4. `META-INF/native-image/**`: reachability hints the WP02 record found necessary (resource-config for the contract resource, Jackson hints for the chosen mode).
5. Run the exact documented command ONCE on the skeleton jar and record the output in the research.md spike record (out-of-map append, own commit): `java -jar build/libs/mission-status-api.jar --mission-status.project-root=<project root> --mission-status.port=8787`, then `curl http://127.0.0.1:8787/api/v1/hello`.

**Files**: Java sources under `config`, `adapter/in/http/skeleton`, `adapter/out/filesystem/ProjectRootCheck` (about 150 lines), resources.
**Validation**: JVM boot works; unset/blank/non-directory root exits non-zero with the named messages.

## Subtask T014: Skeleton tests and the native-tagged skeleton set (red-first)

**Purpose**: `nativeTagFloor` is 3 from the first native leg (plan.md native test partition).

**Steps**:
1. Write the failing tests first: the skeleton contract-document test (class `SkeletonContractDocumentTest`) in `src/test/java/.../skeleton/` asserts the bytes served at `/api/v1/openapi.yaml` equal the bundled `contract/openapi.yaml` (deleted together with the skeleton contract-document route by WP10, which replaces it with the AC-11d test). Run it red (route absent), then green.
2. Three skeleton `@Tag("native")` tests in the native source set: virtual-thread probe (a request is handled on a virtual thread), a Jackson-and-SSE round-trip, a resource-loading check. They are skeletons that WP20 replaces with the real ones (AC-9h and friends); floor stays 3.
3. Skeleton `nativesmoke.NativeSmokeTest` (and `NativePerfTest`), both tagged `native-binary` (so the default `test` and `check` exclude them, step 8 of T012), that assert the `nativeBinary` system property is set and the binary answers the hello route addressed as `127.0.0.1:<port>` (the accepted Host form WP11's filter will enforce; `NativePerfTest` only the property); WP12 replaces the `NativeSmokeTest` body and deletes the hello route with it, WP13 replaces the `NativePerfTest` body. They run only through `nativeSmoke`/`nativePerf` with `-PnativeBinary`, never under `check`.
4. Revert-fails: serve a modified byte from the skeleton route and the skeleton test goes red.

**Files**: tests under `skeleton/`, `src/nativeTest/`, `nativesmoke/` (about 200 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.skeleton.*'`; `./gradlew nativeTagJvmTest`; the three native-tagged tests execute on THIS workstation (Linux x64, the WP02 toolchain gate) in `./gradlew nativeCompile nativeTest` and the executed count (3, from the JUnit XML) is recorded; `./gradlew nativeCompile nativeSmoke -PnativeBinary=<built binary>` is green locally. The other three OS legs are WP04's CI proof.

## Subtask T015: Strict dependency verification metadata

**Purpose**: AC-14a/14c: every resolved artifact checksummed, generated by one Linux x64 run.

**Steps**:
0. Precondition: the WP02 record's native toolchain gate (T008 step 6: `native-image`, C toolchain, zlib headers present and `nativeCompile` of the hello app succeeded) is PASS and re-confirmed here by `native-image --version`. If it is FAIL or cannot be re-confirmed: STOP and report BLOCKED (owner: orchestrator); there is no CI-only generation path, because CI never commits and a metadata file generated without the native configurations would fail the verify-only native legs.
1. Generate once, on Linux x64, with a run that resolves EVERY configuration (a `help`-only run resolves only plugin classpaths): `./gradlew --write-verification-metadata sha256 check nativeCompile nativeTest nativeSmoke -PnativeBinary=<built binary> jacocoTestReport --refresh-dependencies`, plus `openApiGenerate` in generated mode only (hand mode has no such task; plan.md section 2). `check` already resolves the test classpaths that carry the YAML library and the nested-build mechanism (step 4 of T011). Set `verify-metadata` true and `verify-signatures` false (the same stated limit as `contracts/`). Never hand-edit the file.
2. Record in the spike record (R-4): whether any artifact carries an OS or arch classifier (WP02 predicted the answer; confirm), the file size, and that the other three OS legs run verify-only. If a classifier exists, add the exact command the verify-only step prints on failure, to run on that OS or in a `workflow_dispatch` job that uploads the diff (CI never commits).
3. Standing tamper test (AC-14a; operator ruling after analyze, ANL-002: a committed test that runs in CI, not a one-time scratch run). Commit `services/mission-status-api/src/test/java/org/speckitty/missionstatus/build/VerificationTamperTest.java`, an untagged JUnit class, so it runs in the default `test` task and therefore in `./gradlew check` on the `jvm` job (plan sections 5 and 12). It is modelled on `contracts/tools/tamper_check.py` (copy the tree, alter checksums in the copy's `gradle/verification-metadata.xml`, run the copy's build, require a verification failure) but is written for the service tree and does not call that script. Steps of the test: (a) copy to a temp directory the files a nested build needs (`build.gradle.kts`, `settings.gradle.kts`, `gradle.properties`, `gradle/`, the wrapper files, a minimal main source set) and never touch the original; (b) assert the copy's metadata holds at least one `<sha256 value="` (non-vacuity: zero checksums fails the test); (c) positive control: the unmutated copy resolves (`--offline`) and the nested build succeeds; (d) alter the leading eight hex characters of ONE checksum in the copy (a `deadbeef` prefix, as `tamper_check.py` does) and require the nested build to exit non-zero with a dependency-verification failure in its output (match the Gradle text recorded by WP02 T004 step 10, not a bare non-zero exit); (e) run the nested build through the mechanism WP02 T004 step 10 proved and T011 step 4 declared (Gradle TestKit `GradleRunner`, or the equivalent), with a generous timeout. Revert row (observed red once, recorded in the PR "Tests run"): make the test skip the alteration and the control-versus-tamper difference collapses (the tamper step then reports the build succeeded) => red. The test never uses the network (`--offline`). TestKit's default Gradle user home is empty, so the runner is pinned to the real Gradle user home with `withTestKitDir(<GRADLE_USER_HOME>)` (the directory the outer build resolved into, taken from the `GRADLE_USER_HOME` environment variable or its default `~/.gradle`, never a literal path) so `--offline` resolves from the outer build's populated cache; the test requires the cache to be populated (the outer `check` resolves the test classpath first) and fails with a message naming that precondition if the control build cannot resolve offline. WP02 T004 step 10 proves this in both modes.

**Files**: `gradle/verification-metadata.xml` (generated, large: reviewed by regeneration command); `src/test/java/org/speckitty/missionstatus/build/VerificationTamper*` (~150 lines).
**Validation**: `./gradlew --offline check` resolves strictly and runs `VerificationTamperTest` (green: control passes, tampered copy fails with a verification error); `./gradlew --offline test --tests 'org.speckitty.missionstatus.build.*'`.

## Subtask T016: `tests/ci/test_mission_status_api_build.py` (pins, with revert-fails)

**Purpose**: The Python pins for the scaffold (plan.md section 1). Later WPs append their own pins to this same file in dependency order; keep each pin group in a clearly named section so appends rebase cleanly.

**Steps** (write each pin red-first against a missing/mutated input, then green):
1. AC-14a/14b/14g: wrapper properties carry `distributionSha256Sum` and Gradle 9.7.1; the catalog has no `+`/`latest`/range, every version literal in `build.gradle.kts` goes through the catalog; no literal version in the build script. Revert rows: alter a checksum, one wrapper byte, or a literal version in a temp copy.
2. AC-14e: in generated mode the openapi-generator plugin version equals `contracts/tools/pins.json`; in hand mode the pin reads the mode recorded by this build test and asserts the plugin is absent from the catalog and the build script (the AC-11c drift test parses the contract YAML and needs no plugin). AC-14f: wrapper-validation SHA pin is asserted in WP04 (leave a named TODO-free section header only).
3. Toolchain pin: `auto-download=false`, no foojay plugin in `settings.gradle.kts`, `JavaLanguageVersion.of(25)`, `toolchainDetection` off. Revert: add a foojay plugin or `auto-download=true`.
4. No springdoc/swagger dependency in any configuration (parse the catalog and build script text AND, when a `gradle` run is not possible, the catalog aliases): revert by adding `org.springdoc` to a temp copy.
5. JaCoCo pins: the three minimums (0.90, 0.90, 0.80) parsed from `build.gradle.kts`; `check` depends on `jacocoTestCoverageVerification` and `jacocoScopeCheck`. The workflow-step half (CI invokes `check`) is added by WP04.
6. Generated mode: the generated-package names (`apiPackage`, `modelPackage`) and the generation restriction of T012 step 2 are pinned; hand mode: the mode and the reserved package `adapter.in.http.dto` are recorded and there is no `openApiGenerate` task. Either way: `bundleContract` task present and its resource path `contract/openapi.yaml`; `bootJar` file name `mission-status-api.jar`.
7. C-009: `pyproject.toml` `packages` stay `src/*`, `services/` is in neither the wheel `packages` nor the sdist `include`. Revert: add `services/` to a temp copy.
8. NFR-009: apply the guard's own character sets (`WINDOWS_ILLEGAL_CHARS`, `SHELL_EXPANSION_TELLTALE_CHARS`, imported from `tests/architectural/test_no_invalid_windows_filenames.py`; if the import fails inside the `tests/ci` run, use the shared re-export fallback decided at WP02/Unverified 17) to every tracked path under `services/mission-status-api/`, with a discovered-count guard (at least the recorded number of tracked service paths) and a planted-path control (`:` in a temp copy goes red).
9. Every discovered-set test asserts a named floor (zero matches fails). Use `.venv/bin/ruff` clean and typed annotations (Python 3.11+).
10. Test-partition pins (T012 step 8; text-level, parsing `build.gradle.kts`): `test` excludes tags `native-binary` and `perf`; `nativeSmoke`, `nativePerf` and `perfTest` are registered as `Test` tasks with their tag includes and class filters; `nativeSmoke`/`nativePerf` read the `nativeBinary` project property and forward it with `systemProperty("nativeBinary", ...)`; `check` depends on `perfTest`, `nativeTagJvmTest`, `jacocoTestCoverageVerification` and `jacocoScopeCheck`. If the WP02 record named a no-discovered-tests switch, a pin asserts it is set on `perfTest` (and on each other tag-only `Test` task the record says needs it), with a revert row (remove the line in a temp copy => red). Revert rows (temp copy): drop the `native-binary` exclusion; drop the `check` dependency on `perfTest`; drop the `systemProperty` forwarding; each red.

**Files**: `tests/ci/test_mission_status_api_build.py` (new, about 350 lines; later WPs append).
**Validation**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`; `.venv/bin/ruff check tests/ci/test_mission_status_api_build.py && .venv/bin/ruff format --check --force-exclude tests/ci/test_mission_status_api_build.py`; `.venv/bin/python -m pytest tests/architectural/test_no_invalid_windows_filenames.py -q` (a targeted gate, not the bare directory).

## Subtask T017: Build green, quickstart run, recorded evidence

**Purpose**: The exit gate of the scaffold half.

**Steps**:
1. `cd services/mission-status-api && ./gradlew check` green on JDK 25 (jacoco rule tolerant of the empty `domain` and `application` patterns by the per-pattern T012 rule 6; `check` does not run the `native-binary` classes). Prove `jacocoScopeCheck` reds when a pattern is emptied (scratch copy of the build file; paste the failing line in the PR "Tests run" later).
2. Gate selection for a services-only diff and the workflow-ceiling test are NOT this WP's gates (WP07 and WP04 own them); this WP adds no workflow file.
3. Append the quickstart-run output and the recorded facts (versions, classifier answer, metadata churn size) to the research.md spike record (out-of-map append; own commit via `.venv/bin/spec-kitty safe-commit`).
4. Append tracer entries (friction: anything that cost time; design decisions: any build-script choice not in the plan, e.g. the `nativePerf` registration, DD-20).

**Validation**: all of the above green; `git status --short` clean apart from intended files; `grep -rnE "/(home|Users)/" services/mission-status-api tests/ci/test_mission_status_api_build.py` finds nothing.

## Definition of Done

- `services/mission-status-api/` builds with `./gradlew check` (JDK 25) and the Python pin tests are green; every pin has a revert-fails row observed red once.
- The build script is complete for later phases (generated models or hand mode, `bundleContract`, JaCoCo three rules plus `jacocoScopeCheck`, native tagged source set and `nativeTagJvmTest`, `nativeSmoke`, `nativePerf`, `perfTest`, the test partition, `bootJar` name).
- Strict verification metadata committed, generated by command; standing `VerificationTamperTest` committed and running in `check`, observed red once under its revert row.
- Skeleton service bound to loopback with the documented defaults; skeleton contract-document test green; three native-tagged skeleton tests exist (`nativeTagFloor` 3).
- No springdoc anywhere; no tracked Windows-illegal path; no absolute home path.
- Native legs and the first CI run are WP04's gate; note here what was exercised locally (Linux x64: native compile, the three native-tagged tests, the native smoke on the hello route) and what is owed to CI (the other three OS legs).
- The test partition of T012 step 8 is in the script and pinned; `check` neither runs the binary-dependent classes nor omits the perf proof.

## Risks

- A dependency with an OS classifier makes the single-OS metadata run insufficient (PR-7): the verify-only legs fail with the printed command; WP04 handles it.
- Generated-model fallback taken: `adapter.in.http.dto` and the AC-11c drift test replace generation; the build test must pin the mode.
- Gradle 9.7.1 with Boot 4.1.1 / Native Build Tools incompatibility surfaced late: the WP02 record is the guard; escalate rather than bumping the pinned versions silently.

## Reviewer Guidance

- Review `verification-metadata.xml` by regeneration command, not by line; review the catalog and the build script by line.
- Check there is no way for a later WP to need a build-script edit (task registrations, source sets, `nativePerf`, `perfTest`, the tag partition and the `check` dependencies).
- Check every Python pin has a revert row and a discovered-count floor; check the springdoc absence is tested.

## Implementation command

`spec-kitty agent action implement WP03 --agent claude`
