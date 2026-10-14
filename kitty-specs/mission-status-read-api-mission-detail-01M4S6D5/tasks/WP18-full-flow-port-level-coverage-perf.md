---
work_package_id: WP18
title: '[PR B] P13 (2/2) Full-flow, port-level, coverage-floor and perf tests'
dependencies:
- WP13
- WP14
- WP15
- WP16
- WP17
requirement_refs:
- FR-008
- FR-009
- FR-011
- FR-012
- FR-015
- FR-016
- FR-017
- FR-018
- FR-022
- NFR-001
- NFR-002
- NFR-003
- NFR-004
- SC-003
- SC-007
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
subtasks:
- T126
- T127
- T128
- T129
- T130
- T131
- T132
- T133
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/test/java/org/speckitty/missionstatus/
create_intent:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/AdmissionGatePortLevelTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/ProjectionRowCoverageTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PermissionCaseFloorTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/ServedRoutesCompleteTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/rest/DetailRoutesFlowTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/contract/DetailResponseContractValidationTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/perf/Nfr001DetailLatencyTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/perf/Nfr002BoundedMemoryScenarioTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/WorkPackageIndexLocaleProcessTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/SharedBeansUniqueTest.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/AdmissionGatePortLevelTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/ProjectionRowCoverageTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PermissionCaseFloorTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/ServedRoutesCompleteTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/flow/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/hostorigin/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/rest/DetailRoutesFlowTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/contract/DetailResponseContractValidationTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/perf/Nfr001DetailLatencyTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/perf/Nfr002BoundedMemoryScenarioTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/WorkPackageIndexLocaleProcessTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/SharedBeansUniqueTest.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP18 – [PR B] P13 (2/2) Full-flow, port-level, coverage-floor and perf tests

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: B (draft, stacked on PR A). Plan phase **P13 part 2 of 2** (plan.md section 11, row P13). Part 1 is WP17 (CI, native, nightly, README); this WP depends on it so the closing evidence comes last (open fork F3).
- **Work-package dependencies**: WP13, WP14, WP15, WP16 (the four route phases) and WP17.
- **External dependency (not a `dependencies` entry)**: the re-cut tip of #5529 (side-first layout) is merged into the branch by the orchestrator before WP01; PR A (WP01 to WP12) is below PR B. PR B cannot merge before PR A, and #957 cannot merge before #5529 (C-005). #5533's Java work stacks on PR A. No agent pushes, opens or retargets a PR.
- **Named edits (out-of-map; not in `owned_files`)**: each one follows the rule "rebase, state the edit in the commit message, touch nothing else of the file".
  - `T/adapter/in/http/rest/OutOfScopeRoutesTest.java`, **final form (AC-18.2)**: the file is owned by WP13; WP14, WP15 and WP16 each removed only their own path before this WP, so rebase and re-read it first.
  - `T/perf/MissionCorpus.java`, **additive NFR-001 detail shape**: the file is owned by WP05 (the NFR-009 corpus option); add the detail shape without changing what the existing callers (`Nfr001OverviewLatencyTest`, `Nfr009CacheGrowthTest`, `PerfServer`) receive.
  - `R/jacoco-class-floor.properties` (WP01's file): only as the D-145 repair path of T133 step 1, a recount commit of its own if the equality comparison finds a mismatch.
  - none in `M/**` (interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`): the tracer entries (`approach.md`, `design-decisions.md`, `tooling-friction.md`) and the status materialisation are kept locally by the orchestrator; draft them in the hand-off report.
- **Write scope**: `owned_files` only. **This WP is tests only: no production line** (wps.yaml comment). A test that cannot pass without a production change is a finding for the orchestrator, not an edit. Aliases: `S=services/mission-status-api`, `J=S/src/main/java/org/speckitty/missionstatus`, `T=S/src/test/java/org/speckitty/missionstatus`, `R=S/src/test/resources`, `M=kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`.

## Objective

Add the tests that only make sense once all four route phases exist: the eight-route full flow under the instrumented port, the contract validation of every detail response, the final form of the out-of-scope test, the port-level admission-gate legs, the child-JVM locale leg, the three coverage floors, and the NFR-001 and NFR-002 perf tests.

## Context

- Plan.md section 11, row P13 (the test half), section 8 (FRESH3-003: the 26 (row, route) pairs of 18 rows), the "Permission-denied fixtures" paragraph (floor of four ids), section 13 (the layout) and the "Test strategy" table. Red-first form: **red on the phase base** (each class is new, or extends a directory the phase widens).
- **Everything this WP asserts is already served by WP13 to WP16.** A new test that goes red on its first run is either a defect of an earlier WP (report it, do not patch production) or a test bug.
- Existing test directories this phase extends (checkout today): `T/adapter/in/http/flow/` (`Flow`, `Fingerprint`, `ReadOnlyFlowTest`, `CanaryScanTest`, `NoProcessStartTest`, `VirtualThreadProbeTest`), `T/adapter/in/http/hostorigin/` (`HostOriginRig`, `EntryCounting`, `HostOriginFilterTest`, `HostTableTest`, `OriginTableTest`, `MalformedQueryTest`, `RegistrationTest`, `RequestEchoTest`), `T/adapter/in/http/rest/`, `T/adapter/in/http/contract/` (`ContractValidator`, `ResponseContractValidationTest`), `T/perf/` (`PerfServer`, `Latency`, `RatioBudget`, `PerfBudgets`, `MissionCorpus`, `Nfr001OverviewLatencyTest`), `T/conformance/golden/`, `T/testsupport/http/HttpHarness`. The classes `T/application/query/*`, `HttpHarness#startWith`, `DetailFixture`, `PlainCaller`, `PermissionCase`, `ProjectionRow`, `Utf8Host`, `ServedRoutes` and the `served/*ServedRoute` providers **exist after the re-cut and WP07/WP13 to WP16** (plan section 1.1 mapping and section 13); read them before writing against them. Never invent a path: if a name differs, follow the section 1.1 mapping.
- Perf rules: **ratio to a same-run floor is the primary assertion; the figure is the ceiling beside it**; a miss is classified under ADR `2026-10-05-2`, never retried to green. Local perf runs are allowed by E-7; `nativePerf` is CI only.
- Gate G needs a UTF-8 file-name locale: `export LC_ALL=C.UTF-8` first (plan section 5, Gate G preconditions).

### Subtask T126: Full-flow tests over the eight routes

**Purpose**: FR-016, FR-017, AC-11.1, AC-8.3, AC-16.1 to AC-16.3, AC-17.1, AC-17.2: the fence, the read-only fingerprint, the drain posture, the Host/Origin guard and the canary scan hold over all eight data routes.

**Steps**:

1. **C-005 pre-flight, first step of the phase** (plan section 5): from `S`, `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'`; record the #5529 tip sha (`git log -1 --format=%H <ref>`) in the first commit message; run the two string-literal greps of plan section 5 over `S/src/test`, `S/build.gradle.kts`, `tests`, `scripts`, `.github`.
2. Create `T/adapter/in/http/rest/DetailRoutesFlowTest.java`: starts the service through `HttpHarness#startWith` with the **four fixture-built detail services** (`MissionDetail`, `WorkPackage`, `WorkPackageDetail`, `Artifact`, built over `DetailFixture`), so the recorded accesses of the fixture's allowlist seam are in the request path. It runs the curated detail request set (one request per route plus the refusal of each) and asserts: status and Problem codes; the AC-11.1 set per route: any access outside that route's (scope, class) set, from the wrong directory (coordination `meta.json`, a coordination ledger for the primary) or in a non-read-only mode fails; the flow includes a Mission whose `meta.json` stores no topology (so `lanes.json` is read to classify it) and a coord-routed Mission; over the same two Missions the artifact routes record none of LEDGER, LANES_JSON or a coordination class.
3. AC-11.1 control (replacing #5529's control): a read of `<primary-dir>/tasks/WP01-x.md` during `/missions` fails because that route may touch no new class; the same read during `getWorkPackage` passes. Write both legs.
4. Extend `T/adapter/in/http/flow/Flow.java` (package-private; its `requests(HttpHarness)` list holds the curated request set of the three #5529 routes) with a detail request list, and add the corresponding legs without changing existing expectations: in `ReadOnlyFlowTest` the read-only mode check (AC-16.1; control: a write injected into the recorder turns it red), the fingerprint before/after (AC-16.2: content hash, listing including `.lock` and temporary names, modification times; including the fixtures that hold links and refused files), the drain equality (AC-16.3: byte-identical with `hosted.drain` and `[hosted] drain` both true, both false and both absent; and no recorded read of `config.toml`), and in `CanaryScanTest` the extension of AC-8.3: canary values (a host path, an address, a token-shaped string) planted in a Work Package body, a title, an artifact and a `lanes.json` appear in no response and no log line, **except** `promptMarkdown` of the `includePrompt=true` request, where the canary **must** be found (the control that proves the scan can see it).
5. Extend `T/adapter/in/http/hostorigin/` (`HostOriginRig.TARGETS` at the checkout lists five targets; add the five detail routes): AC-17.1 for each refused Host and Origin value of the #5529 AC-9b and AC-9c tables answers 403 `request_refused` (or the container's 400 for the closed list) and the instrumented port records **zero** accesses of any class (`EntryCounting`); control: the accepted `127.0.0.1:<port>` and `localhost:<port>` requests read normally. AC-9.3 (guard flow for the prompt variant): add the target `getWorkPackage?includePrompt=true` to `HostOriginRig.TARGETS`; a refused Host or Origin answers 403 `request_refused` with **no** prompt byte in the body and **zero** recorded port reads (`EntryCounting`), while the accepted `127.0.0.1:<port>` and `localhost:<port>` Host gives 200 with the `promptMarkdown` bytes (this is the multi-route AC-9.3 flow that WP14 defers to this WP). AC-17.2: #5529's AC-9a (non-loopback bind refused, port in use refused) runs with the five routes registered, and the test asserts the routes are registered (a startup that lacks them would leave the AC vacuous).

**Files**: `DetailRoutesFlowTest.java` (new, about 220 lines), additions to `Flow.java`, `ReadOnlyFlowTest.java`, `CanaryScanTest.java`, `HostOriginRig.java`, `HostOriginFilterTest.java` (about +200 lines in total). `NoProcessStartTest` extends to the five routes: no child process is started (AC-10.2).

**Validation**: `./gradlew --no-daemon test --tests '*DetailRoutesFlowTest' --tests '*ReadOnlyFlowTest' --tests '*CanaryScanTest' --tests '*HostOriginFilterTest' --tests '*NoProcessStartTest'`. Revert-fails: add a `Files.write` in a test branch (AC-16.1 red), drop the Host check from one route registration in a scratch copy (AC-17.1 red), remove the canary from the `true` request (AC-8.3 control red).

### Subtask T127: DetailResponseContractValidationTest

**Purpose**: AC-15.1 to AC-15.3: every response of the five operations validates against the contract.

**Steps**:

1. Create `T/adapter/in/http/contract/DetailResponseContractValidationTest.java` in the style of the existing `ResponseContractValidationTest` (a `@ParameterizedTest` over fixtures; `ContractValidator` is the networknt validator). Parameter set: every detail golden fixture of the manifest, served through the real routes with the four detail services, plus the refusals.
2. AC-15.1 control: a deliberately invalid body (one extra member) fails the validator; one wrong type fails.
3. AC-15.2 (examples): every example under `contracts/mission-status/examples/` for the five operations validates, and each of `WorkPackageDetail.*`, `ArtifactListing.*`, `ArtifactContent.*`, `ArtifactRefusal.*`, `MissionDetail.*` and `WorkPackage.*` is either reproduced by a fixture or named in a test list as not reproduced with the reason. An unreferenced example fails (discovered-count guard: assert a named floor of examples so a glob matching nothing fails).
4. AC-15.3 (drift probe, S-30): `ContractDriftProbe` (WP06 owns it) is a model-level check: assert that the probe covers every model of the five operations (generated or hand-written), and that `/api/v1/drift` and `/api/v1/ops/invocations` answer 404 through `OutOfScopeRoutesTest` (T128). No operation-set check is built; this test edits no probe.

**Files**: `DetailResponseContractValidationTest.java` (about 160 lines).

**Validation**: `./gradlew --no-daemon test --tests '*DetailResponseContractValidationTest' --tests '*ResponseContractValidationTest'`.

### Subtask T128: OutOfScopeRoutesTest final form (named edit)

**Purpose**: AC-18.2: the five detail routes no longer 404 and the out-of-scope routes still do.

**Steps**:

1. Rebase and **re-read** `T/adapter/in/http/rest/OutOfScopeRoutesTest.java` (WP14, WP15, WP16 each removed their own path, one line each, serialised by merge order). The checkout form has `everyOutOfScopeOperationAnswersLikeAnUnknownPath` and `aPathOutsideThePrefixIsNotServed`.
2. Final form: a new test asserts that the five new routes answer non-404 for a fixture Mission (`/api/v1/missions/{missionId}`, `.../work-packages/{wpId}`, `.../work-packages/{wpId}/detail`, `.../artifacts`, `.../artifacts/content`; copy the exact paths from the contract and from `ContractRoutes`), and the existing 404 assertion keeps only `/api/v1/drift` and `/api/v1/ops/invocations` (drift and Ops have no Java owner yet). The old assertion that the five paths are 404 must not stand.
3. The commit message states the named edit and that nothing else of the file was touched.

**Files**: `OutOfScopeRoutesTest.java` (named edit, about +25 lines, -5).

**Validation**: `./gradlew --no-daemon test --tests '*OutOfScopeRoutesTest'`. Revert-fails (plan section 11): restore the old 404 assertion and the test goes red; WP17's README test is the other half of AC-18.2.

### Subtask T129: AdmissionGatePortLevelTest

**Purpose**: AC-22.1 to AC-22.4: the admission gate bounds concurrency at the port, never refuses, and a bypass is red.

**Steps**:

1. Create `T/application/query/AdmissionGatePortLevelTest.java`. The plain-Java caller is `PlainCaller` (WP12, `T/testsupport/PlainCaller`): no Spring context, no HTTP. The test lives in `application/query`, outside `conformance.port`, and is **not** registered in `R/portlevel-tests.txt` (that file is WP05's and no WP appends port-leg ids to it: `PortLevelClassSetTest` and `PortSubsetSecondLegTest` reject a class or id that opens no selector fixture; TASKS-GREEN-001). Name both gates in the Gate G run to prove nothing changed.
2. AC-22.1: 16 concurrent calls to each of the **four** gated operations (`getWorkPackageDetail`, `listArtifacts`, `getArtifactContent` and `getWorkPackage` with `includePrompt=true`; E-1, D-148), 64 calls in all, through the port over a source whose reads block on a latch; while they block, `AdmissionGate#highWaterMark()` equals 4; releasing the latch lets all 64 complete with normal results. (The spec text of AC-22.1 still says three operations and 48 calls; the plan's four-operation reading is binding.)
3. AC-22.2: 100 calls queued behind 4 blocked holders all complete after the release, none answered with a status; during the block, `getMission`, `getWorkPackage` without a prompt and the three #5529 operations still complete (they are not behind the gate).
4. AC-22.3: a test-only variant of one port implementation that does not pass the gate (planted bypass) makes AC-22.1 fail (mark above 4); the unmutated implementations pass. The variant lives inside this test class (nested), not in production.
5. The HTTP leg AC-22.4 is part of T132 (the NFR-002 scenario run through HTTP reads the same mark and asserts it is not above 4); here assert only the port level.

**Files**: `AdmissionGatePortLevelTest.java` (new, about 200 lines).

**Validation**: `./gradlew --no-daemon test --tests '*AdmissionGatePortLevelTest' --tests '*AdmissionGateTest'`. Revert-fails: a permit count of 5 (WP12's `AdmissionGateTest` red) and a service that skips the gate (its `...GateTest` red, WP14 to WP16; here the planted bypass is red).

### Subtask T130: WorkPackageIndexLocaleProcessTest

**Purpose**: AC-6.6 process leg: the three-route child-JVM leg for a non-UTF-8 locale.

**Steps**:

1. Create `T/config/WorkPackageIndexLocaleProcessTest.java`, in the style of the existing `ConfigPinProcessTest` and `BindGuardProcessTest` (they start a child JVM through `AppProcess`). Start the service in a child JVM **without** `LC_ALL=C.UTF-8` (the process leg uses `LC_ALL=C`) over a fixture holding `WP01-é.md`, and request the three Work Package routes (`getMission`, `getWorkPackage`, `getWorkPackageDetail`).
2. Assert the documented behaviour of FRESH3-004: the non-UTF-8 file-name locale refusal of the Work Package index (the coded refusal the plan names for each route), not a crash and not a partial answer. The stub leg (the `NameEncoding` stub) is WP10's and runs under any locale; do not duplicate it.
3. Guard: use `Utf8Host`'s convention so the test never turns red for a mis-set parent locale: the child gets its own `LC_ALL`, and the parent only needs to create the fixture file (skip with the recorded `not run: precondition unmet: <test id>` line when the parent cannot create `WP01-é.md`).

**Files**: `WorkPackageIndexLocaleProcessTest.java` (new, about 120 lines).

**Validation**: `./gradlew --no-daemon test --tests '*WorkPackageIndexLocaleProcessTest'`. Revert-fails (plan section 11, AC-6.6): start the child JVM with `LC_ALL=C.UTF-8` and the omission test goes red (the test must fail loudly if the child inherits a UTF-8 locale).

### Subtask T131: Coverage floors that own the last case

**Purpose**: discovered-count guards (plan "Discovered-count guards"): iterations that silently match nothing fail.

**Steps**:

1. `T/application/query/ProjectionRowCoverageTest.java`: assert over the production tests the **26 (row, route) pairs** of FRESH3-003 (the `Member-to-route list` section of `M/data-model.md`, WP04, is the source; the figures below repeat it) covering all **18 rows** T1 to T18: P9/`MissionDetailMapper` 7 pairs (T1, T2, T3, T4, T5, T6, T10); P10/`WorkPackageMapper` 10 pairs (T5, T6, T7, T8, T10, T11, T12, T13, T14, T17); P11/`WorkPackageDetailMapper` 9 pairs (T1, T5, T7, T8, T9, T15, T16, T17, T18). Discover the `@ProjectionRow(row, route)` annotated cases by reflection or the class-path scan the existing `PermissionCaseCoverageTest` uses; assert the exact pair set (not a count alone) and a named floor of 26, so deleting a case or adding a stray one fails. Control: a planted test-local class missing one pair is red.
2. `T/testsupport/PermissionCaseFloorTest.java`: over the production tests, with a named floor of **four** `@PermissionCase` ids, every id has exactly one injected-fault test and one real-permission test (both legs); control with planted test-local cases (a missing leg, a duplicate id). `PermissionCaseCoverageTest` (WP10) holds the coverage function; this test only asserts the production floor, because WP15 and WP16 write those tests.
3. `T/conformance/golden/ServedRoutesCompleteTest.java`: every **(detail fixture, golden file) pair** of the manifest (`ConformanceTree` `surface` partition, WP07; the pairs are `ServedRoutes.expectedEntries` over the six golden file names of WP07 T044 step 5, i.e. every fixture with a committed golden x each golden file it holds, TASKS-FRESH3-002/003) is served by **exactly one** `ServedRoute` provider (`served/{MissionDetail,WorkPackage,WorkPackageDetail,Artifact}ServedRoute`): the test asserts `ServedRoutes.ownershipProblems(<default registry's loaded providers>)` is empty (no pair unclaimed, none claimed twice, none outside the provider's `OWNER` row), that all four providers are loaded, and a named floor on the pair count (D-109), so a fixture served for one operation but not for another cannot hide behind a fixture-level check; a golden-bearing pair with no provider fails; a planted provider-less fixture with a golden (and a planted fixture whose second golden file no provider claims) is the control. **The rule for golden-less Java-only fixtures:** a fixture of a Java-only class (`artifacts-links`, `lookup-faults`, `projection-refusals`; no golden, V9/V18) has nothing to compare byte for byte and is exempt from this floor; the route WP's named tests cover it, and a second control proves a planted golden-less fixture is not required. The golden-bearing classes are all served by construction: `detail-*`, `phases-matrix`, `projection-nulls` (WP13, WP14, WP15), `wp-*`, `resolved-state` (WP14, which serves the `getWorkPackage` goldens of the `resolved-state` class), `cycles`, `tasks-md`, `legacy-lanes-json`, `worktree-states` (WP15) and the `artifacts-*` classes with a golden (WP16). No exemption list by class name exists, so the test cannot go vacuous by an over-wide exemption. **This file must not appear in PR A** (plan section 11): it is created only here.

4. `T/config/SharedBeansUniqueTest.java` (TASKS-FRESH2-001, the single-owner guard for shared beans): over the full application context (`@SpringBootTest`, the production configuration at the PR B tip), assert **exactly one** bean of each shared type: `WorkPackageIndex` (owner WP13), `TextSource` and `AdmissionGate` (owner WP12), `FrontmatterDecoder` and `LanesDecoder` (owner WP11), and one bean each of `MissionDetailQuery`, `WorkPackageQuery`, `WorkPackageDetailQuery`, `ArtifactQuery`; control: a planted test-local second `WorkPackageIndex` definition in a throwaway context makes the same assertion helper fail. (`ProblemMapper`, `ServedRoutes` and the other non-bean shared pieces each have one owner by the ownership table; a wiring class other than the named owner that declares one of these beans is a review finding.)

**Files**: four new test classes (about 80 to 120 lines each).

**Validation**: `./gradlew --no-daemon test --tests '*ProjectionRowCoverageTest' --tests '*PermissionCaseFloorTest' --tests '*ServedRoutesCompleteTest' --tests '*PermissionCaseCoverageTest'`. Revert-fails: delete one `@ProjectionRow` case or one real-permission test and the matching floor goes red.

### Subtask T132: Perf tests (NFR-001, NFR-002) and the additive corpus shape

**Purpose**: NFR-001, NFR-002, AC-22.4: latency and bounded memory as a ratio to a same-run floor, with the figure as the ceiling.

**Steps**:

1. Named edit of `T/perf/MissionCorpus.java` (WP05 owns it): add the NFR-001 detail shape additively (a Mission with 40 Work Package files and a 1000-file Mission, among at least 500 Missions, with the requested Mission sorted first: the worst case for the duplicate-detection scan, AC-1.8(c)). Existing callers must see identical output for their existing methods.
2. `T/perf/Nfr001DetailLatencyTest.java`, `@Tag("perf")`, in the shape of `Nfr001OverviewLatencyTest` (floor route `GET /api/v1/openapi.yaml`, alternating rounds, discarded warm-up, `Latency.run`/`timedGet`, `RatioBudget.evaluate`): p95 of `getMission` (40 Work Packages) under 100 ms, `getWorkPackageDetail` under 100 ms, `listArtifacts` of a 1000-file Mission under 1500 ms, `getArtifactContent` of a 262144-byte file under 100 ms, each as a **ratio** constant (`..._RATIO_LIMIT`) with the figure as a `..._CEILING_MS` constant beside it. `PerfBudgets.java` is not owned by this WP: declare the new budget constants as private constants of the test class. Names should contain `RATIO` and `CEILING`, as `Nfr001OverviewLatencyTest` does; the pin of WP17 does not check that for these two new classes (it enforces the `@Tag("perf")` rule for them and RATIO and CEILING for the two classes it names), so the budget assertions and their exceed-the-budget controls are what guard them. A miss fails once; the failure message carries the classification hint (ADR `2026-10-05-2`); no retry loop.
3. `T/perf/Nfr002BoundedMemoryScenarioTest.java`, `@Tag("perf")`: the NFR-002 scenario, all held at once: 100 concurrent `getArtifactContent`, 10 concurrent `listArtifacts` over a 1000-file Mission, 10 concurrent `getWorkPackageDetail` over a Mission whose `tasks.md` is 4 MiB, 20 concurrent `getMission` over a 40-file Mission, **plus ten concurrent `getWorkPackage?includePrompt=true`** (S-13). Assert: used heap after a forced collection grows by at most 96 MB (ratio to the same-run floor primary; the figure is the ceiling beside it); the instrumented port records the largest single read per cap (not above cap + 1: 262145, 1048577, 4194305); and, for AC-22.4, the gate's high-water mark is not above 4.
4. Local runs under E-7: `./gradlew --no-daemon perfTest --tests 'org.speckitty.missionstatus.perf.Nfr001DetailLatencyTest'` and the same for `Nfr002BoundedMemoryScenarioTest` (`perfTest` includes only the `perf` tag; `test --tests` would find nothing). Record the figures in the commit message. `nativePerf` stays CI only.

**Files**: two new test classes (about 150 and 180 lines), `MissionCorpus.java` (named edit, about +60 lines).

**Validation**: the two `perfTest` runs above; `./gradlew --no-daemon test` must still pass (the plain `test` task excludes the `perf` tag). Revert-fails: the control that exceeds the budget (a cache told to keep 10 times the history, or a deliberately slow floor) is red.

### Subtask T133: Phase gate

**Purpose**: the PR B tip is green alone.

**Steps** (`export LC_ALL=C.UTF-8`; bundle and `CONTRACT_BUNDLE` variables as in plan section 5):

1. Gate G from `S`: `./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`. This WP adds no `domain.*` or `application.*` production class, so `R/jacoco-class-floor.properties` is not edited; re-run the D-145 equality comparison that WP17 T125 owns (plan section 2 command) and record the result. If it finds an understated count, repair it by a named edit of `R/jacoco-class-floor.properties` (WP01's file) in a commit of its own: that is the stated repair path for D-145 in PR B (the only exception to "not edited").
2. Gate P: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` (the perf-class tag rule: both new perf classes carry `@Tag("perf")`; RATIO and CEILING are not checked by the pin for them).
3. Acceptance checklist, each by a named test: AC-8.3, AC-11.1, AC-15.1 to AC-15.3, AC-16.1 to AC-16.3, AC-17.1, AC-17.2, AC-18.2 (the Java half), AC-22.1 to AC-22.4, AC-6.6 (process leg).
4. **`ServedRoutesCompleteTest` appears in PR B only**: `git diff` of the PR A range must not contain it.
5. Optional under E-7: `./gradlew --no-daemon check` once locally before review.
6. Python hygiene commands of plan section 5 are not required (no Python file is touched); the Windows-filename guard still runs after staging new files.

## Self-contained green

This WP's tip, and PR B's tip at this WP, must be green on every CI gate on its own (plan section 11, "Each PR is self-contained and green at its own tip").

- **Fixtures live with their tests.** All detail fixtures and providers were created with their routes (WP07, WP08, WP13 to WP16). This WP adds no fixture directory; its tests consume the `DetailFixture` services and the manifest as they stand. `MissionCorpus` gets an additive shape together with the perf tests that use it.
- **Floors and counts satisfiable now (plan section 11, "Counts and floors").** The floors asserted here (26 pairs, 18 rows, four permission ids, the served-fixture floor, the example floor) are satisfiable because WP13 to WP16 wrote the cases and the providers; no later WP raises any of them (this is the last WP). `ServedRoutesComplete` is created here, not before.
- **No test or gate names a type of a later WP.** There is none after WP18. The tests name only types of WP01 to WP17 (and the re-cut layout); `DetailFixture` and `HttpHarness#startWith` are WP10's and `PlainCaller` is WP12's.
- **Pin clauses kept green** in `tests/ci/test_mission_status_api_build.py` (owned by WP17): the `@Tag("perf")` rule (both new classes tagged), the tracked-path scan (no Windows-invalid filename; the NFR-007 character sets), the probe list, the rule-9 literals, the models list and drift probe, the native floor (unchanged: no native-tagged test is added here), `requests.json` and the workflow.
- **JaCoCo.** Test-only WP: no domain or application class, no count line edit.
- **Mission record.** `M/meta.json` complete; `M/status.json` only through `spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`, never hand-edited, no untracked CLI state committed blind; cutover-guard, the mission-state audit and corpus-blocking pass. `M/**` files already on `main` after PR A lands are frozen (interim default F1/E-12): this WP adds nothing to and modifies nothing under `M/**`; the orchestrator keeps status and tracer appends locally.

## Plan defects found

1. **WP17 is a dependency of this WP but nothing in this WP's tests needs it.** The wps.yaml order (F3) is "closing evidence last"; the gate is correct either way. No action unless the operator rules F3 the other way.
2. **Resolved (TASKS-GREEN-001): no port-level id is appended by any WP13 to WP16 and `AdmissionGatePortLevelTest` is not listed in `R/portlevel-tests.txt`.** The list (WP05's file) is not touched by this WP; a `PortLevelClassSetTest` or `PortSubsetSecondLegTest` failure is a finding to report, not a reason to edit the list.
3. **NFR-002 scenario text differs between spec and plan.** The spec scenario is 100/10/10/20 and the plan's P13 row adds ten concurrent prompt requests (S-13). This prompt implements both; the numbers are provisional.
4. The perf budget constants cannot go into `PerfBudgets.java` (not owned): they are private constants of the two new test classes.

## Definition of Done

- `DetailRoutesFlowTest`, the flow, host/origin and canary additions green over eight routes with their controls.
- `DetailResponseContractValidationTest` green; examples floor named.
- `OutOfScopeRoutesTest` in final form (five routes non-404; drift and Ops 404); commit message states the named edit.
- `AdmissionGatePortLevelTest`: mark equals 4 for the four gated operations, 100 queued calls complete, planted bypass red.
- `WorkPackageIndexLocaleProcessTest` green; red when the child inherits a UTF-8 locale.
- `ProjectionRowCoverageTest` (26 pairs / 18 rows), `PermissionCaseFloorTest` (four ids), `ServedRoutesCompleteTest` green with controls.
- `Nfr001DetailLatencyTest` and `Nfr002BoundedMemoryScenarioTest` green locally, tagged `perf`, ratio primary with ceiling beside it; figures recorded.
- AC-9.3 holds on the shared rig for `getWorkPackage?includePrompt=true` (T126 step 5): 403 `request_refused`, no prompt byte, zero port reads; accepted Host gives 200 with the bytes.
- The D-145 equality comparison is re-run and recorded (T133 step 1); a mismatch is repaired by the named edit stated there.
- Gate G and Gate P green; `ServedRoutesCompleteTest` absent from PR A.
- Per-subtask evidence via `spec-kitty agent tasks mark-status T126 --status done` (and T127 to T133); conventional commits.

## Risks

- A first run that is red because of an earlier WP's defect: report to the orchestrator with the failing assertion; do not patch production.
- Flaky perf figures on a loaded machine: the ratio to a same-run floor is the guard; never retry to green, classify under ADR `2026-10-05-2` (a miss is a finding).
- `OutOfScopeRoutesTest` conflicts: three earlier WPs edited it; rebase and re-read before editing.
- Locale: Gate G needs `LC_ALL=C.UTF-8`; the process leg deliberately removes it for the child only.
- Heap measurement noise: force a collection before and after, same-run floor, no absolute-only assertion.
- Test names and file counts: a rename that breaks `PortLevelClassSetTest` or the tracked-path scan turns an unrelated gate red.

## Reviewer Guidance

- Verify **no production file** is in the diff, and that the only edits outside `owned_files` are the two named ones (`OutOfScopeRoutesTest`, `MissionCorpus`), each stated in its commit message and touching nothing else.
- Verify every floor asserts an exact set or a named floor, never a bare `> 0`; check each control is planted in the test itself.
- Verify perf tests assert the ratio first and the figure beside it, with no retry.
- Run one revert per subtask (listed in Validation) and confirm it goes red for the stated reason.
- Check the C-005 pre-flight sha is in the first commit message and the PR "Tests run" section lists the local perf figures and counts.

## Implementation command

`spec-kitty agent action implement WP18 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5`
