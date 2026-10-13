---
work_package_id: WP02
title: 'Phase 1a: spike and decision record (R-2, R-7 items, each with a fallback)'
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-010
- FR-011
- FR-014
- C-001
- C-007
- NFR-001
- NFR-005
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
- T010
history: []
agent_profile: researcher-robbie
authoritative_surface: kitty-specs/mission-status-read-api-overview-01M4EMSA/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/mission-status-read-api-overview-01M4EMSA/research.md
role: researcher
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 - Phase 1a: spike and decision record

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `researcher-robbie`
- **Role**: `researcher`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Answer every phase 1 unknown of the plan by experiment, in a THROWAWAY, UNCOMMITTED scratch Gradle project outside the repository tree, and write the outcomes as the spike record at the end of `research.md`, each with a pass/fail result and the explicit fallback that WP03 follows when it fails. The decision record is the only committed output of this WP.

## Context

- This is the plan's "phase 1 spike" (plan.md section 11, row 1, and research.md "WP01 spike record (to be appended)"). In this Mission's WP numbering the plan's "WP01 spike" is WP02 (this WP, decisions) plus WP03 and WP04 (scaffold, workflow), which consume the decisions. Wherever the plan, research.md or the spec say "WP01 records/decides", read "WP02 decides, WP03/WP04 apply and, where only a real CI run can answer, append the answer".
- `execution_mode: planning_artifact`: every owned path is under `kitty-specs/`. The scratch harness, downloads and build outputs must live outside the repository (use the session scratchpad directory, never `/tmp` directly and never inside the repo). Nothing from the harness is committed. Downloaded JDK/GraalVM archives and jars are untrusted data: put each in its own new empty directory, verify the vendor checksum, and pass paths as arguments (plan.md section 8, spike harness rule).
- Prerequisite (orchestrator-owned, `tasks-overview.md` section 10): this workstation had no JDK, Gradle or `native-image` at planning time (tracer `tooling-friction.md`). The orchestrator, with the operator's approval, installs ONCE, before this WP is claimed, GraalVM Community JDK 25.0.2 (graalvm-ce-builds release `jdk-25.0.2`, linux-x64) and the Gradle 9.7.1 binary distribution under one persistent prefix outside the repository, each verified against the vendor `.sha256` asset and extracted from an empty directory, and hands the prefix to every Java WP brief as `JAVA_HOME` and `PATH` entries. This WP does NOT install anything: it verifies the toolchain, records its versions and checksums (no paths) and uses it. If `java -version` does not report GraalVM Community 25.0.2, `native-image --version` is missing, `gcc` or the zlib headers are missing, or no Gradle 9.7.1 is available: STOP and report BLOCKED with the exact error. Owner of the unblock: the orchestrator (operator for the install itself); WP03 onward stay unclaimed until this WP is done. Do not substitute another JDK major, do not install anything yourself and do not guess results.
- Plan sections to read: 2 (regeneration commands), 8 (Tomcat table), 11 (phase 1 row, native test partition), 12 (toolchain, versions), 13 (serialisation and Jackson, bind), Unverified list items 2-5, 9-14, 16, 18, 19; research.md R-2, R-3, R-4, R-5, R-7; spec FR-009, FR-010 (AC-10c), FR-011, FR-014.
- Binding constraints: Spring Boot 4.1.1 (BOM: Tomcat 11.0.24, Jackson 3.1.5 and 2.21.5), openapi-generator plugin 7.25.0 (equal to `contracts/tools/pins.json`), Gradle 9.7.1, JaCoCo 0.8.15, networknt 3.0.8, ArchUnit 1.4.2. A result that contradicts the plan is a FINDING recorded against the plan; the expected values in plan.md section 8 are never rewritten to match an observation.
- Tracer files: append dated entries (append-only) to `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md` (the next free DD id: read the LAST DD id in `traces/design-decisions.md` at the time of the append, DD-39 at fix round 2, and continue from it; never reuse an existing id). These are out-of-map appends (cross-WP tracers are not in anyone's `owned_files`); commit them as their own commit through `.venv/bin/spec-kitty safe-commit`.
- Public repository: no absolute home-directory paths in `research.md` or any tracer; use `<scratch>` and `<repo>` placeholders.

## Subtask T004: Toolchain, supply-chain facts and library compatibility (Unverified 5, 11, 12, 13, 14, 18)

**Purpose**: Prove the pinned toolchain works together before WP03 writes a build script around it.

**Steps**:
1. Toolchain gate first (the provisioning is the orchestrator's, see Context): record `java -version`, `native-image --version`, the C compiler and zlib-header presence, and `gradle --version` (versions only, no paths) as the "environment" block of the spike record, and re-fetch the vendor `.sha256` of the GraalVM tarball and of `gradle-9.7.1-bin.zip` to confirm the checksums the orchestrator verified at install time (each match recorded; a mismatch is BLOCKED). Then create the scratch project outside the repo. Fetch `https://services.gradle.org/distributions/gradle-9.7.1-bin.zip.sha256`, compare with the recorded `acd53f1edaf02f1a8ff99879f8a34b302661a057d9b063ae9e35b552f804d20a`, record both and the release date (Unverified 18). Generate the wrapper in the scratch project by running the PROVISIONED Gradle 9.7.1 (`bin/gradle wrapper --gradle-version 9.7.1 --gradle-distribution-sha256-sum <sha>`); that install is used only to run `wrapper`, and every later build uses the wrapper. This is how the wrapper chicken-and-egg is broken: WP03 T011 step 3 repeats exactly this command with the same provisioned install.
2. Record, with `gh api`, the commit SHAs for `gradle/actions` (wrapper-validation, tag v6.4.0, dereference the annotated tag), `graalvm/setup-graalvm` (v1.6.7), `actions/checkout` (`08c6903cd8c0fde910a37f88322edcfb5dd907a8`), `actions/upload-artifact`, `actions/download-artifact` and `astral-sh/setup-uv` (`20cfd1bf945f4377ade1205e4dbc17946fc9a30d`) as used by `contracts.yml`/`ci-router.yml` (read those files for the exact pins; reuse existing SHAs where the repository already pins the action). The record is the table WP04 copies.
3. Spring Boot 4.1.1 plugin on Gradle 9.7.1 with Java 25 toolchain: `./gradlew help` and a hello `@RestController` `bootJar` build green. Record the Native Build Tools plugin version Spring Boot manages. Also probe, in the same throwaway project, what a `Test` task does when its JUnit tag filter discovers no test: register a `Test` task `useJUnitPlatform { includeTags("perf") }` with no test carrying that tag (and test sources present) and run it with `check` depending on it. Record in `research.md` whether Gradle 9.7.1 passes or fails it, the exact failure text if it fails, and, if it fails, the name of the switch that makes it pass (the expected candidate is the `Test` task property `failOnNoDiscoveredTests`, which Gradle 9 is believed to default to true; that is the finder's recollection and is UNVERIFIED until this probe runs). WP03 T012 step 8 applies the recorded answer; do not leave it to the implementer of WP03 to guess.
4. openapi-generator-gradle-plugin 7.25.0 on Gradle 9.7.1: `openApiGenerate` green against `contracts/mission-status/openapi.yaml` (read the split root in place; do not copy it into the repo).
5. ArchUnit 1.4.2 reads a Java 25 class file (a one-rule smoke test, plus a deliberately violating class to see it fail). If not, record whether 1.5.1 works and name the catalog change for WP03.
6. JaCoCo 0.8.15 on a Java 25 test run: `jacocoTestReport` XML produced, the exact class-name pattern syntax of `jacocoTestCoverageVerification` (`org.speckitty.missionstatus.domain.*` crossing sub-packages) matched against real class files, and a pattern that matches zero classes passing vacuously (the reason `jacocoScopeCheck` exists).
7. networknt json-schema-validator 3.0.8: load an OpenAPI 3.1 component schema extracted from the contract and show a negative case that MUST fail (`unevaluatedProperties: false` with one extra property; a `type: [string, 'null']` member). If it does not honour them, the fallback is named (a different 3.1-capable validator, or schema pre-processing) before WP03.
8. `--write-verification-metadata sha256` over a build that resolves every configuration (`check nativeCompile nativeTest jacocoTestReport openApiGenerate`): record whether any resolved artifact has an OS or arch classifier, and whether re-running the write step merges additively (Unverified 14). Record the size of the generated file.
9. YAML library for `.kittify/config.yaml` and `.kittify/metadata.yaml` (WP08/WP19 T046 reads only a handful of keys). Fix the library now so WP03 declares it: preferred is the SnakeYAML the Spring Boot 4.1.1 BOM already manages (record the version and that it resolves under strict verification); name a stated alternative if it cannot be used. Record (a) that it parses a `.kittify/metadata.yaml`-shaped and a `.kittify/config.yaml`-shaped document and ignores unlisted keys, (b) the ArchUnit consequence: which package may import it (read plan.md section 13 rule 8 and name the packages the rule must allow or forbid), (c) the native hint it needs, if any.
10. Nested builds: (a) the AC-11c contract-drift build (generated mode only; hand mode uses the YAML-parsing drift test instead), and (b) the AC-14a tamper case for the standing `VerificationTamperTest` (BOTH generated and hand modes; post-verification ruling NEWA-001). Prove for each that a test can run a nested Gradle build of a mutated COPY of the contract under strict verification and offline resolution: Gradle TestKit (`gradleTestKit()` plus `GradleRunner` over a copy of the project, wrapper, `verification-metadata.xml` and the mutated contract), exit non-zero on a renamed `MissionOverview` property, zero on an unmutated copy. Pin the runner to the real Gradle user home with `withTestKitDir(<GRADLE_USER_HOME>)` (TestKit's own home has an empty cache, so `--offline` would fail there) and prove, in each mode, that an unmutated copy resolves offline and that a copy with one altered checksum in `verification-metadata.xml` exits non-zero with the dependency-verification failure text (record that text; WP03's test matches it). Record the wall-clock cost. If TestKit cannot do it under strict verification, name the alternative (for example invoking the generator as a library from the test with the generator artifact declared as a test dependency) and prove that one instead. Whichever works, WP03 declares its dependencies in T011 step 4 and resolves them in T015; WP10 T056 runs it.

**Files**: `research.md` spike record (appended in T010).
**Validation**: each item has a PASS/FAIL line and, on FAIL, the fallback and the WP that applies it.

## Subtask T005: R-2 generated models versus hand-written DTOs (go/no-go, C-007)

**Purpose**: Decide the contract-consumption mode with the rule research.md R-2 fixes; no partial or patched-generation mode exists.

**Steps**:
1. Run the spring generator (`interfaceOnly`, models, OpenAPI 3.1 input from the split root, `apiPackage` `org.speckitty.missionstatus.adapter.in.http.api`, `modelPackage` `org.speckitty.missionstatus.adapter.in.http.model`) limited to the generated in-scope operations `getProject` (tag `Project`) and `listMissions` (tag `Missions`); `streamEvents` is hand-written in WP20 and its `Events` tag is never generated, and the `Drift` and `Ops` paths are out of scope. The contract has ten paths and six of them carry the tag `Missions` (`/missions`, `/missions/{id}`, the two work-package paths, the two artifact paths), so a restriction by tag or by the `apis` global property alone also generates five out-of-scope operations; criterion 8 below decides the mechanism.
2. Evaluate criteria 1-6 of R-2 (criterion 7 is T006, criterion 8 is step 3 below) and record pass/fail for each: (1) the Jackson major on `runtimeClasspath` and what the generated annotations and `JsonNullable` need (Jackson 3 `tools.jackson` versus Jackson 2 beside it); (2) a required-nullable member serialises as an explicit `null`; (3) member order equals the canonical golden order; (4) number formatting of `progress` and non-ASCII output equal the Python canonical form (`json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))`; build a tiny golden by hand to compare bytes); (5) `openApiGenerate` green on Gradle 9.7.1; (6) the generated interfaces compile against Spring MVC under Boot 4.1.1.
3. Criterion 8 (out-of-scope operations): record the mechanism that limits generation to the in-scope operations `getProject` and `listMissions`: a trimmed input produced at build time, an `openapi-normalizer` filter, or `defaultInterfaces=false` (generated methods abstract) with a controller overriding only the in-scope methods. Show what the five other `Missions`-tag operations (`/missions/{id}`, both work-package paths, both artifact paths) become at runtime under that mechanism: with the generator's default interface methods they would come back as live routes answering 501, not 404, once a controller implements `MissionsApi`; that outcome FAILS the criterion. The model package must also stay free of the models only those five operations need (they enlarge ArchUnit rule 9's scan, the JaCoCo exclusions and the AC-11c mutation target). WP03 T012 step 2 applies the chosen settings; WP10 T053 carries an HTTP test that the five answer 404 like any unknown path.
4. Decide: ALL of criteria 1-6 and 8 pass without a hand patch of generated output = generated mode. ANY failure = hand-written DTOs in `adapter.in.http.dto` plus the AC-11c replacement (drift test). Write the decision and the reason per failing criterion.
5. Production mapper (E-8 criterion): demonstrate a configured mapper that emits the canonical bytes (no pretty print, nulls written, canonical key order, UTF-8 not escaped, `progress` rendered by one pinned function). If the production mapper cannot, record that E-8 is triggered (AC-15b would weaken to canonical equality) and STOP that line of work for an operator ruling; do not apply the weakening.

**Validation**: eight-line criteria table (criteria 1-6, criterion 8 and the mapper) with the go/no-go line; criterion 7 is recorded by T006.

## Subtask T006: Contract-document bundling mechanism (R-2 criterion 7, E-11)

**Purpose**: Choose how `GET /api/v1/openapi.yaml` gets its single-file bytes at build time.

**Steps**:
1. Candidate: `contracts/tools/bundle.py --root contracts --out <outside-repo-dir> --bundle-only` (Python resolver, no JVM, deterministic: it writes the bundle twice and compares). Run it from a clean checkout state and record the output path for `mission-status`, the `bundle sha256 mission-status <digest>` line and its determinism line. The `--out` directory must lie outside the repository tree (the tool refuses otherwise): this fixes the Gradle task's output dir (build directory, which is outside the source tree but inside `services/`, check this against `OUT_INSIDE_REPOSITORY` and record the finding).
2. Requirement analysis for the four legs: the tool needs Python 3 plus PyYAML plus the sibling `contract_resolver`; record what each runner image provides and what `setup-python`/`uv` step each leg would need (Windows and macOS included). The acceptance rule is plan.md section 13: the candidate is accepted only if the served bytes equal its output for the same commit on ALL FOUR legs. A local Linux run cannot prove the other three; record what is proven (determinism, byte equality served-versus-written on Linux) and mark the three other legs "confirmed by the first workflow run" (WP04 appends the answer).
3. State the fallback explicitly: a dedicated pre-job `contract-bundle` (ubuntu-24.04) that runs the tool once, uploads the single file as a workflow artifact, and every leg downloads it into the build's resource input before Gradle runs; `bundleContract` then verifies the downloaded file's SHA-256 against a value the job passes in. Bytes are equal on all four legs by construction. Record the cost (one more job, one more artifact) and that no second bundler (no SnakeYAML dereferencer) is written, because a second resolver can drift from the contract authority.
4. Decide mechanism A (task invokes the tool on every leg) or B (pre-job artifact) with the reason.

**Validation**: decision line plus the digest of the bundle at the current commit; the byte-equality procedure WP10's AC-11d test uses is written down.

## Subtask T007: Tomcat Host table CONFIRMATION in a throwaway harness (R-7, plan section 8)

**Purpose**: Confirm, never generate, the AC-9b expected statuses against the pinned Tomcat 11.0.24 jar.

**Steps**:
1. Scratch Gradle project booting Tomcat 11.0.24 (the version the Boot 4.1.1 BOM pins) with a counting servlet filter whose only job is to record "filter entered" per row. Send raw-socket requests (not an HTTP client that normalises headers).
2. Run all nine rows of the plan section 8 table (statuses 403/400 and the `reachesFilter` flag per row: set 2 is four 400 rows: row 8 `evil.example@127.0.0.1:<port>` plus the three container rows duplicate Host, HTTP/1.1 without Host and HTTP/1.1 absolute-form foreign target with an accepted Host, `reachesFilter` false for all four; these three are spec-fixed AC-9b rows, no longer provisional) and the provisional E-7 rows (HTTP/1.0 absolute-form foreign target, empty Host, `X-Forwarded-Host`, `Forwarded`, `LOCALHOST:<port>`, `localhost.:<port>`, configured port 0).
3. Record per row: observed status, filter entered yes/no, and the BODY of every container-generated 400 (HTML page or empty), which AC-9g's scan applies to (Unverified 2). Mark each row CONFIRMED or DIVERGES. A divergence is a finding against the plan or spec, never an automatic rewrite of the expected value (escalate to the orchestrator).
4. Also record the Tomcat accessor that reports the address a connector actually bound (Unverified 19; used by `BindGuard`'s post-start check) and the default bind when `server.address` is absent (to justify the "unset exits non-zero" rule).

**Validation**: a table in the spike record; the harness directory is NOT committed and not in the repository tree (check `git status` is clean of it).

## Subtask T008: JFR, SSE under native, native resource and Jackson-null behaviour, native test wiring (Unverified 3, 4, 10)

**Purpose**: Settle the native and runtime unknowns that decide WP03 hints and the WP10/WP20 tests.

**Steps**:
1. `jdk.ProcessStart` JFR event: on the pinned JDK in JVM mode start a recording, launch a child process, read the event; record the exact event name and whether it fires under the GraalVM CE JDK 25 (AC-10c). If absent, record it as the trigger of escalation E-2 (an operator-approved amendment may drop the runtime half); do not drop the assertion yourself.
2. `SseEmitter(0L)` with `spring.mvc.async.request-timeout=-1` under `nativeCompile`: an idle stream stays open past 35 s and receives a heartbeat comment; record the hints (if any) required.
3. A classpath resource (`contract/openapi.yaml`-shaped) read under native: record whether `resource-config` is needed and the exact hint.
4. Jackson null-member and ordering behaviour under native for the chosen mode of T005.
5. Native Build Tools test wiring: how to point the `nativeTest` binary at a dedicated `@Tag("native")` source set (working placeholder directory `services/mission-status-api/src/nativeTest/`), with the tag-filter-on-`test` fallback. Record which wiring works, the executed-test count visible in the JUnit XML (the `native-tag-floor` input), and the doubled native-compile time.
6. A native build of the hello app: record wall-clock for `nativeCompile` on this workstation as an input to the leg timeout budget. Record explicitly as a PASS/FAIL gate "native-image, the C toolchain and the zlib headers are present and `nativeCompile` of the hello app succeeded, and the resulting binary answered its route". WP03 T014 and T015 depend on this gate: on FAIL, WP03 stays unclaimed (BLOCKED, owner: orchestrator, who repairs the toolchain per `tasks-overview.md` section 10); there is no CI-only fallback for the metadata generation because CI never commits.

**Validation**: each line PASS/FAIL with its fallback named: JFR (E-2), SSE (fallback: heartbeat via a platform thread is NOT allowed; escalate), resource (hint), wiring (tag filter).

## Subtask T009: `stampLedger` cost over the real corpus (Unverified 16, NFR-001)

**Purpose**: Check the warm-request budget is feasible before the cache design is built.

**Steps**:
1. In a scratch Java harness (outside the repository), over this checkout's `kitty-specs/*/` (588 tracked `meta.json` on the planning checkout; recount with `git ls-files`), measure the per-Mission cost of a stat plus one bounded read of the last physical line, and the cost of listing and sorting the directory by code points.
2. Report cold and warm totals for 588 Missions and compare with NFR-001 (warm p95 under 200 ms and a cold first call under 5 s are PROVISIONAL, ratio to a same-run no-op floor, ADR `2026-10-05-2`). If the probe alone threatens the 200 ms ceiling, record it as a design finding (cache of the listing, or a coarser stamp) and escalate; do not weaken the NFR.

**Validation**: numbers with the method (run counts, JIT warm-up), no machine paths.

## Subtask T010: Write the decision record, tracers and fallback table

**Purpose**: The only committed output.

**Steps**:
1. Append to `research.md` under the existing heading "WP01 spike record (to be appended)" a dated section containing, in this order: environment (versions and vendor checksums, no paths; the toolchain provenance line "installed by the orchestrator once, checksum-verified"); T004 table (including the YAML library and the nested-build mechanism); T005 criteria and go/no-go (generated or hand DTO, with criterion 8); T006 bundling decision (A or B) with digest and the three-leg proof still owed; T007 Tomcat table with filter-entered flags and the container-400 body; T008 table (including the native toolchain gate); T009 numbers; and a final "Decisions consumed by WP03/WP04/WP10" list. Update R-2 (mode), R-4 (OS classifiers, metadata merge, churn size) and R-7 in place only where the plan text says the spike records them; keep the rest append-only.
2. Include a FALLBACK table with one row per spike item: item, pass condition, fallback, owning WP. Mandatory rows: generated models (hand DTOs plus drift test, WP03/WP10), out-of-scope operation restriction (hand DTOs), bundling (pre-job artifact), JFR event (E-2 escalation), SSE native (escalate), native test wiring (tag filter on `test`), native toolchain gate (BLOCKED, orchestrator), networknt (alternate validator), YAML library (stated alternative), AC-11c nested build (generator as a library), ArchUnit/JaCoCo Java 25 (catalog bump), runner labels (WP04 first run), `stampLedger` cost (design finding).
3. Append tracer entries: friction (anything that cost time: no JDK, download sizes), approach, and design decisions from the next free DD id (read the last DD id in `traces/design-decisions.md`, DD-39 at fix round 2, and continue from it) (generated-vs-hand decision; bundling mechanism; any plan finding).
4. Commit `research.md` and the tracer appends through `.venv/bin/spec-kitty safe-commit` (two commits: record, then tracers). Grep the files for absolute home-directory paths (`grep -rnE "/(home|Users)/"`) before committing.

**Files**: `research.md` (append, about +150 lines), `traces/*.md` (append).
**Validation**: `grep -nE "/(home|Users)/" kitty-specs/mission-status-read-api-overview-01M4EMSA/research.md` finds nothing; `git status --short` shows no scratch files.

## Definition of Done

- The spike record answers R-2 criteria 1-6 and 8 and the go/no-go, criterion 7 (bundling), the Tomcat table, JFR, SSE/native, JaCoCo, networknt, plugin-on-Gradle-9, the YAML library, the AC-11c nested-build mechanism, the native toolchain gate, verification-metadata facts and the `stampLedger` cost, each with PASS/FAIL and a named fallback.
- WP03 can start without re-deriving any of them; nothing in the record says "TBD".
- No scratch artefact is committed; no absolute home path is committed.
- Divergences from the plan are listed as findings, not silently absorbed.

## Risks

- Toolchain missing or different from the recorded versions: stop and report BLOCKED (owner: orchestrator); never install or substitute it here.
- The three-leg bundling proof cannot be obtained locally: stated explicitly and owed to WP04's first run.
- A Tomcat row diverging from the source-read expectation: escalate; the spec's closed 400 list (AC-9b) is an operator-ruled set.

## Reviewer Guidance

- Check every claim has an observed value or a stated "not observable here, owed to WP0x".
- Check the fallback table is complete and each fallback keeps the spec constraint (no weakening of AC-15b, AC-9b, AC-11d).
- Check the harness stayed outside the repository tree and no vendor archive or jar was committed.

## Implementation command

`spec-kitty agent action implement WP02 --agent claude`
