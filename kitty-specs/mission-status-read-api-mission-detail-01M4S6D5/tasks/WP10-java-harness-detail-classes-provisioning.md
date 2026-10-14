---
work_package_id: WP10
title: '[PR A] P7 Java harness for the detail classes and provisioning (FR-014 Java half)'
dependencies:
- WP05
- WP07
- WP08
- WP09
requirement_refs:
- FR-014
- FR-011
- FR-020
- NFR-007
- SC-001
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T05:39:02.331985+00:00'
subtasks:
- T066
- T067
- T068
- T069
- T070
- T071
- T072
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/test/java/org/speckitty/missionstatus/
create_intent:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/ProvisionPlan.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/MetaReadCounter.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/RouteMarker.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/InMemoryTextSource.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/CapRaceInjector.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/RealPermissionFixture.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PermissionCase.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PermissionCaseCoverageTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/ProjectionRow.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/DetailFixture.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/DetailFixtureTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/Utf8Host.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/http/HttpHarnessDetailTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/ServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/ServedRoutes.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/DetailGoldenSuiteTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/ResolvedStateGoldenTest.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/ProvisionPlan.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/MetaReadCounter.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/RouteMarker.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/InMemoryTextSource.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/CapRaceInjector.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/RealPermissionFixture.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PermissionCase.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PermissionCaseCoverageTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/ProjectionRow.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/DetailFixture.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/DetailFixtureTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/Utf8Host.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/http/HttpHarness.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/http/HttpHarnessDetailTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/ServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/ServedRoutes.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/DetailGoldenSuiteTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/ResolvedStateGoldenTest.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP10 – [PR A] P7 Java harness for the detail classes and provisioning (FR-014 Java half)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: **PR A**, plan phase **P7** (a draft stacked on the branch that carries #5529's last slice; no route is served in PR A, and this WP is test-only).
- **External dependency (not a `dependencies` entry)**: WP01 cannot start until the orchestrator has merged the re-cut tip of #5529 (the side-first layout) into this branch; PR A stacks on #5529's last slice and #957 cannot merge before #5529 (C-005). PR B stacks on PR A; #5533's Java work stacks on PR A and reuses the doubles this WP writes (plan section 7.1 row 11).
- **Dependencies inside the mission**: WP05 (P3: the resolved-state reduction, goldens' Java members), WP07 (P4: the oracle, goldens, manifest, census, `PROVISION_PLAN`), WP08 (P4b: the `resolved-state` goldens), WP09 (P5: the text-read port, recorder route hook, `ReadScope`).
- **Write scope**: `owned_files` of the frontmatter only (all eighteen are under `S/src/test/java`). This WP adds **no production class**, so there is no JaCoCo count to edit.
- **Named edits (out-of-map)**:
  - `M/traces/approach.md`, `M/traces/design-decisions.md`, `M/traces/tooling-friction.md`: append-only tracer entries (not in `owned_files`). Rule for any named edit: rebase, state the edit in the commit message, touch nothing else of the file.
  - There is no other named edit. In particular this WP does **not** edit `T/testsupport/FilesystemFixtureFactory.java`, `T/testsupport/FixtureHandles.java`, `T/testsupport/ProjectHeaderMaterialisation.java` or `T/testsupport/ConformanceTree.java` (P1a / P4 files; the plan's shared-file table gives them no P7 writer), and it does not change the canonical constructors of `FilesystemFixtureFactory.Built` or `FixtureHandles`.
- **Alias key**: `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Paths are post-re-cut unless "exists at the checkout" is said.

## Objective

Build the Java side of the detail test harness before any route exists: provisioning (`ProvisionPlan`), the meta-read counter, the route marker, the in-memory text source, the cap-race injector, the real-permission fixture with `@PermissionCase`, the locale precondition (`Utf8Host`), `@ProjectionRow`, the detail fixture bundle (`DetailFixture`), `HttpHarness#startWith`, and the golden harness (`ServedRoute`, `ServedRoutes`, `DetailGoldenSuiteTest`, `ResolvedStateGoldenTest`). Nothing here names a type of a later WP.

## Context

- **Why a separate phase.** The route WPs (WP13..WP16, PR B) and the index WP (WP11) are red-first against fixtures and doubles that must already exist; D-126 moved P7 before P6 so that WP11's provisioned (symlink, directory) and non-ASCII cases use `ProvisionPlan`, `DetailFixture` and `Utf8Host` instead of writing a second applier.
- **The unwired-route rule (D-109).** From this WP on a detail class is compared only for the fixtures a route phase has registered in its `ServedRoute` provider; with no provider at PR A's tip `DetailGoldenSuiteTest` compares nothing and is not red; its non-vacuity is a planted self-test provider. `ServedRoutesCompleteTest` is WP18 (PR B) and must not appear in PR A.
- **No gate names a later type (PLAN-FRESH4-001, D-139, D-140).** `HttpHarness#startWith` takes `Map<Class<?>, Object>`; `HttpHarnessDetailTest` uses an interface declared inside the test; the coverage function of `PermissionCaseCoverageTest` runs over planted test-local classes; the production floors (`PermissionCaseFloorTest`, `ProjectionRowCoverageTest`) belong to WP18; the recorder's route is a `Supplier<String>` (WP09 added the hook; `RouteMarker` is what a harness installs).
- **Exists at the checkout:** `T/testsupport/http/HttpHarness.java` (`start`, `startOver`, `startWired`, `get`, `allowlistRecorder()`), `T/testsupport/FilesystemFixtureFactory.java` (`Built(query, source, handles, root)`; `fromTree`, `fromTreeRecording(Path)`, `over(Path root, Function<Path,AllowlistAccess>)`), `T/testsupport/FixtureHandles.java` (`allowlistRecorder()`, `recorder()`), `T/testsupport/ProjectHeaderMaterialisation.java` (copies a fixture tree to scratch without `NOT_COPIED`, runs `SYMLINK_PLAN`), `T/testsupport/ConformanceTree.java`, `T/conformance/golden/{GoldenSuiteTest,ManifestCouplingTest,ComparatorCompletenessTest}.java`, `T/adapter/out/filesystem/RecordingAllowlistAccess.java`. **Exist after the re-cut / earlier WPs:** `J/application/query/MissionReadModel.java` (WP01, plan 1.2), `ConformanceTree.detailFixtures()` and `allClasses()` (WP07), the P5 port and recorder route hook (WP09). **New here:** every owned file.
- **Key facts about provisioning.** The committed trees hold no `.git`, no symlink, no mtime (NFR-007, D-42); `PROVISION_PLAN` (generalising `SYMLINK_PLAN`) has lines `link`, `gitentry` (a plain file named `.git`) and `mtime`, plus the lane-worktree directories of the `worktree-states` fixtures; the generator (WP07) applies it to a temporary copy before the oracle runs and this WP applies the same plan to the temporary copy the Java tests read. Its exact line grammar is written by WP07 into `M/data-model.md` and `tests/contract/_mission_status_conformance.py`: **read those, do not re-derive** (plan section 11, P4 row).

### Subtask T066: `ProvisionPlan`, `MetaReadCounter`, `RouteMarker`, `InMemoryTextSource`, `CapRaceInjector`

**Purpose**: the small reusable doubles of plan 7.1 row 11 and the applier of the provisioning plan.

**Steps** (all in `T/testsupport/`, package `org.speckitty.missionstatus.testsupport`):
1. Pre-flight (first step): from `S`, with `LC_ALL=C.UTF-8` and the `CONTRACT_BUNDLE`/`CONTRACT_BUNDLE_SHA256` variables exported (plan section 5), run `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'`; green or stop and report. Record the #5529 tip sha (`git log -1 --format=%H refs/remotes/m5529/lane-b`, or the orchestrator's value) in the first commit message and run the C-005 string-literal grep of plan section 5.
2. `ProvisionPlan`: `static void apply(Path fixtureDir, Path scratchRoot)`: reads the fixture's `PROVISION_PLAN` file from the **source fixture directory** (`fixtureDir`, the committed tree) and applies it to the scratch copy: `link<TAB>target` creates a symbolic link (skip with an assumption on a platform that cannot, recording the not-run line through T068's hook); `gitentry` creates a plain file named `.git`; `mtime` sets the modification time; lane-worktree directories are created. It is idempotent, creates nothing outside `scratchRoot`, and removes any stray copy of the plan file from `scratchRoot` if `ProjectHeaderMaterialisation` copied one (its `NOT_COPIED` set names `SYMLINK_PLAN` but not `PROVISION_PLAN`; see "Plan defects found"). It never calls `ProjectHeaderMaterialisation`'s private helpers and edits that class not at all. A `ProvisionPlan` test plants a stray `PROVISION_PLAN` copy inside a Mission directory of the scratch root and asserts it is removed (ruling OO-4: the plan sits at the fixture top level).
3. `MetaReadCounter`: counts `(MISSION_META, READ)` accesses in a `RecordingAllowlistAccess` (AC-1.8: three reads of the matched Mission warm, four cold); API `int count(RecordingAllowlistAccess recorder)` and `void reset()`; no reference to any route class.
4. `RouteMarker`: a request-scoped marker: `static RouteMarker create()`, `void set(String route)`, `void clear()`, `Supplier<String> supplier()` (what a harness installs on the recorder through the hook WP09 added; default `"-"`). Thread-safe (the HTTP server answers on another thread: use a volatile or a thread-agnostic holder, not a bare `ThreadLocal`).
5. `InMemoryTextSource`: implements `application.query.port.out.TextSource` over an in-memory map keyed by `(FileRef, ReadScope)`; enforces the same cap rule (over-cap by length, `NotText` through `StrictUtf8`, `Absent`, `NotRegular`, `DirListing.Names` with `limitReached` and `trustworthy`) so the AC-13.5 subset gives identical results from both sources; builder methods `file(FileRef, byte[])`, `dir(FileRef, String... names)`, `link(FileRef)`, `fault(FileRef, TextFault.Kind)`.
6. `CapRaceInjector`: a decorating `AllowlistAccess` for use with `FilesystemTextSource`: its `stat`/`openRead` pair reports a declared size (for example 100) at the first call and serves a larger body (300000 bytes) when read, so AC-7.1 and AC-5.4's race leg are reproducible; also a variant that grows after the handle size check. Constructor takes the delegate, the path predicate, the declared size and the actual bytes.
7. Each double has a small test beside it (`...Test.java` is **not** in `owned_files` for these five except where listed; put their assertions in `DetailFixtureTest` (T069) and `HttpHarnessDetailTest` (T070) or in the matching existing glob if one exists; do not create unowned files). If a double needs its own test, add the assertions to `DetailFixtureTest`.

**Files**: `ProvisionPlan.java` (~140 lines), `MetaReadCounter.java` (~40), `RouteMarker.java` (~50), `InMemoryTextSource.java` (~200), `CapRaceInjector.java` (~110).

**Validation**: targeted `DetailFixtureTest` assertions for each double; `ArchitectureRulesTest` stays green (test classes are outside the production rules; `InMemoryTextSource` may use `StrictUtf8` under rule 12c).

### Subtask T067: `RealPermissionFixture`, `@PermissionCase`, `PermissionCaseCoverageTest`

**Purpose**: permission-denied cases are asserted twice (injected fault; real permissions) and never depend on the user running the tests (D-32, D-101).

**Steps**:
1. `RealPermissionFixture.refusedForThisUser(Path path)`: removes read permission (POSIX) or applies the platform equivalent, tries to open the file/dir **as the test user**, and when the operating system does not refuse it (a root runner, Windows) appends `not run: precondition unmet: <test id>` to `build/reports/not-run.txt` (create the directory if needed; the skipped-test report hook of `S/build.gradle.kts` is WP06's and copies the file to `$GITHUB_STEP_SUMMARY` or stdout) and skips the test with a JUnit assumption. The test id is the calling test's unique id (use a `TestInfo` or an explicit id parameter; define it once). Restores permissions in a close hook.
2. `@PermissionCase("<id>")`: runtime-retention annotation (method or type), `value` = the case id, an enum or string `leg` attribute (`INJECTED` / `REAL`) so the coverage function can check that each id has exactly one injected-fault test and one real-permission test.
3. `PermissionCaseCoverageTest`: holds the **coverage function** (reflect over a set of classes given to it) and its controls over **planted test-local annotated classes**: a missing leg (id with only an injected test) is red; a duplicate id is red; a complete pair is green. It asserts **no floor over production tests** (that is WP18's `PermissionCaseFloorTest`; PLAN-FRESH4-001, D-140): do not scan the classpath for production cases.

**Files**: `RealPermissionFixture.java` (~110), `PermissionCase.java` (~25), `PermissionCaseCoverageTest.java` (~140).

**Validation**: `./gradlew --no-daemon test --tests '*PermissionCaseCoverageTest'`; under a root user the real-permission helper skips and writes the not-run line (assert the helper's behaviour with an injected "OS does not refuse" seam so the test is also deterministic as root).

### Subtask T068: `Utf8Host` and `@ProjectionRow`

**Purpose**: the locale precondition and the row/route annotation the later coverage guards read.

**Steps**:
1. `Utf8Host.assumeUtf8()` (D-128): if `sun.jnu.encoding` is not UTF-8, append `not run: precondition unmet: <test id>` to `build/reports/not-run.txt` through the same hook as T067 (share one private static writer; do not duplicate the file logic) and skip by `Assumptions.assumeTrue(false, ...)`. Provide `static boolean isUtf8()` so tests can branch. It is what WP11 and the route WPs call before creating a non-ASCII file name. The cases that inject the `NameEncoding` stub (AC-6.6 stub leg, AC-4.8 stub twin) never call it (they run under any locale).
2. `@ProjectionRow`: runtime annotation carrying `String row()` (for example `T5`) and `String route()` (for example `getMission`) of one (row, route) pair (D-102). Its discovery guard (`ProjectionRowCoverageTest`, 26 pairs, 18 rows) is WP18's: this WP adds only the annotation.
3. Tests: put `Utf8Host`'s behaviour assertions (a stubbed encoding property reader) into `DetailFixtureTest` or a `@Nested` class of `PermissionCaseCoverageTest`; **do not create a new test file that is not in `owned_files`**.

**Files**: `Utf8Host.java` (~70), `ProjectionRow.java` (~25).

**Validation**: the stub-property assertions; manual check with `LC_ALL=C ./gradlew --no-daemon test --tests '*DetailFixtureTest'`: the Utf8Host-dependent assertion is skipped and `build/reports/not-run.txt` gets one line.

### Subtask T069: `DetailFixture` and `DetailFixtureTest`

**Purpose**: one bundle every route test builds its service on (PLAN-FRESH4-004).

**Steps**:
1. `DetailFixture` is a **new record in a new file** (do not touch `FilesystemFixtureFactory`, `FixtureHandles` or their constructors). It composes an already-built `FilesystemFixtureFactory.Built` (taken from `fromTreeRecording(Path)` or `over(...)`, which keep the one scratch-tree and provisioning path), with: a real `FilesystemTextSource` (WP09) over `Built#root()` and over **the recording seam `FixtureHandles#allowlistRecorder()`**, the very object the event source reads through, so both sets of accesses land on one recorder; and a `MissionReadModel` (WP01, `application.query`, public composition handle) over the built event source, `handles().clock()` and the diagnostics recorder `handles().recorder()`. It provisions nothing itself: a factory `static DetailFixture of(Path fixtureDir)` calls `fromTreeRecording(fixtureDir)` and then `ProvisionPlan.apply(fixtureDir, built.root())` (T066), so the plan is applied before any read. Accessors: `built()`, `textSource()`, `readModel()`, `recorder()`, `root()`, `diagnostics()`. No decoder is needed here (each route phase builds its own service on the fixture in its own tests).
2. `DetailFixtureTest`: (a) a `readText` through the fixture's `TextSource` and a `listMissions` read through `built().query()` both appear on the **one** recorder (`FixtureHandles#allowlistRecorder()`); (b) the fixture applies a `PROVISION_PLAN` `link` line (use a planted temp fixture dir, or a WP07 fixture with one) and does not leak the plan file into the artifact space; (c) the assertions for `MetaReadCounter`, `RouteMarker`, `InMemoryTextSource` (same results as `FilesystemTextSource` on a small subset: Absent, NotRegular, OverCap, NotText, Text, listing window) and `CapRaceInjector` (declared 100, served 300000 -> `OverCap`, at most cap + 1 bytes read); (d) `Utf8Host` stub assertions from T068.

**Files**: `DetailFixture.java` (~90), `DetailFixtureTest.java` (~260).

**Validation**: `./gradlew --no-daemon test --tests '*DetailFixtureTest'`; the existing callers of `FilesystemFixtureFactory.Built` (`RefusalRowsTest`, `StreamRig#withQueueCapacity`, `PerfServer`) compile unchanged (grep them; you edit none).

### Subtask T070: `HttpHarness#startWith`

**Purpose**: let PR B's tests serve a controller over a fixture-built service without the harness naming any P8 type.

**Steps**:
1. `T/testsupport/http/HttpHarness.java` (exists, now owned here): add `public static HttpHarness startWith(FilesystemFixtureFactory.Built built, Map<Class<?>, Object> inbound, String... properties)` that starts the production application as `startOver` does and registers each passed instance as a **primary bean under its map key**, exactly as `startOver` registers the `MissionStatusQuery` (look at the private `run(...)` and extend it with an `ApplicationContextInitializer` or `registerBean` with `setPrimary(true)`; keep every existing method and signature unchanged). The key is a plain `Class<?>`: P7 code and tests name none of the four inbound interfaces.
2. Also accept an installed `RouteMarker` so the recorder's route supplier is set for requests (an overload or a builder-style extra argument; keep the existing arities). Expose `handles()` and `allowlistRecorder()` as today.
3. `HttpHarnessDetailTest`: declares an interface **inside the test class** (for example `interface StandIn { String ping(); }`), passes a lambda/instance to `startWith` under `StandIn.class`, asserts it is the primary bean of the started context (`context().getBean(StandIn.class)`), and asserts the existing routes (`/api/v1/project`, `/api/v1/missions`) still answer. The test compiles and is green at this tip because it names no type of WP12.

**Files**: `HttpHarness.java` (~+60 lines), `HttpHarnessDetailTest.java` (~120).

**Validation**: `./gradlew --no-daemon test --tests '*HttpHarnessDetailTest'`; the existing HTTP tests (`MissionsControllerTest`, `ProjectionFlowTest` or whichever exist; list with `grep -rl HttpHarness S/src/test`) still pass unchanged.

### Subtask T071: Detail golden harness

**Purpose**: the Java comparison of served bytes with the committed goldens, ready for the route phases to register fixtures against.

**Steps** (package `org.speckitty.missionstatus.conformance.golden`):
1. `ServedRoute` (the complete shape; **no route work package edits it** and none needs to read a Javadoc to learn it, TASKS-FRESH3-002). A golden file of WP07 T044 step 5 is a canonical-JSON object keyed by **request key**, and one fixture carries up to four golden files (one per operation, plus the prompt variant), so a route serves a *(fixture, golden file)* pair and answers one request per key of that golden. Declare in `ServedRoute.java`:
   - `record Entry(String fixtureKey, String goldenFile)`: `fixtureKey` is `ConformanceTree.TreeFixture#key()` of a fixture of `ConformanceTree.detailFixtures()`; `goldenFile` is one of the six names of WP07 T044 step 5.
   - `Set<String> goldenFiles()`: the golden file names this provider **owns** (the partition below).
   - `Set<Entry> served()`: every `Entry` this provider serves.
   - `byte[] body(Entry entry, String requestKey)`: the **raw response body bytes** the route answers (whatever the status; an oracle refusal such as `legacy-lanes-json` compares the Problem body) for one request key of that golden. Request conventions, fixed here for WP13 to WP16: key `"-"` is the Mission-level request (`GET /api/v1/missions/{missionId}`, and `listArtifacts`); a Work Package id key is `GET .../work-packages/{wpId}` (`get-work-package.json`: no `includePrompt` parameter; `get-work-package-prompt.json`: the same URL with `includePrompt=true`) or `.../work-packages/{wpId}/detail` (`get-work-package-detail.json`); for `get-artifact-content.json` the key is the artifact path, requested as `.../artifacts/content?path=<key>` with the path percent-encoded once. The Mission id of the request is the synthetic ULID of the fixture's `meta.json`.
   - **Golden-file ownership partition** (constants `ServedRoutes.OWNER`, golden file name to provider simple name): `get-mission.json` -> `MissionDetailServedRoute` (WP13); `get-work-package.json` and `get-work-package-prompt.json` -> `WorkPackageServedRoute` (WP14); `get-work-package-detail.json` -> `WorkPackageDetailServedRoute` (WP15); `list-artifacts.json` and `get-artifact-content.json` -> `ArtifactServedRoute` (WP16). Every golden-bearing detail fixture x golden file pair is therefore claimed by exactly one provider, by construction.
   - `ServedRoutes.expectedEntries(Set<String> goldenFiles)`: the **manifest-derived** entry set: for every fixture of `ConformanceTree.detailFixtures()` and every given golden file name with `ConformanceTree.golden(fixture, file) != null`, one `Entry`. Providers and tests use it; nothing hard-codes a fixture list as the only source of truth.
   - `ServedRoutes.ownershipProblems(List<ServedRoute> providers)`: returns the list of violations: a pair served by two providers, a provider whose `goldenFiles()` leave its `OWNER` row or whose `served()` holds a golden file outside it, and (when the six golden files are all owned by the given list) any pair of `expectedEntries(all six)` that no provider serves. WP18 `ServedRoutesCompleteTest` asserts it is empty over the loaded providers.
2. `ServedRoutes`: the registry: loads the four optional provider classes by **name** (`org.speckitty.missionstatus.conformance.golden.served.MissionDetailServedRoute`, `...WorkPackageServedRoute`, `...WorkPackageDetailServedRoute`, `...ArtifactServedRoute`) with `Class.forName` inside a try/catch for `ClassNotFoundException` and treats a missing class as an empty route (the providers are WP13..WP16's and do not exist at this tip). No import of any provider. Provide a package-private `ServedRoutes.of(List<ServedRoute>)` so the self-test can inject a planted provider, and a **test-visible accessor of the providers actually loaded** (for example `static List<ServedRoute> loaded()` / `static Set<String> loadedProviderNames()`; the default registry's result, not the injected one) so that each route WP can assert its own provider was found (TASKS-GREEN-002); cover the accessor in `DetailGoldenSuiteTest` **tip-stably** (this file is WP10's and no PR B WP edits it): only through an injected registry (`ServedRoutes.of(List.of(planted))` reports the planted provider), plus the assertion that the default registry's loaded provider names are a **subset** of the four known provider names. Never assert that the default registry is empty or that a given provider is absent: WP13 to WP16 make the default registry non-empty, and each route's own `<Route>ServedRouteTest` asserts its provider is loaded.
3. `DetailGoldenSuiteTest`: for every `Entry` of every loaded provider, read the committed golden with `ConformanceTree.golden(fixture, entry.goldenFile())`, parse it as the object keyed by request key, and for **each request key of that golden** assert that `provider.body(entry, key)` equals the golden value of that key written by the canonical writer (`MissionStatusApplicationJson.mapper()`, the Java twin of Python `canonical_bytes`, byte for byte, as recorded by WP07 in `M/data-model.md`); an empty key set, a key the provider cannot answer, or a golden file the manifest says is absent is red. A fixture no provider serves is **neither compared nor red** here (WP18 `ServedRoutesCompleteTest` owns completeness). The planted self-test provider (a test-local `ServedRoute` serving one real fixture) proves non-vacuity (AC-14.1 (i)-(iii)): green on the unperturbed golden bytes and red on one perturbed golden byte (perturb a copy in a scratch directory, never the committed file).
4. `ResolvedStateGoldenTest` (AC-20.1): the golden members of WP05's reduction (the resolved state of the Java reducer over the fixture's event log) compared with the WP08 `resolved-state` goldens (`R/conformance/resolved-state/**`, via `ConformanceTree`), through the port-level path (`built.query()`/reducer entry WP05 provides).
5. Do not edit `GoldenSuiteTest`, `ManifestCouplingTest`, `DetailManifestCensusTest` or `ComparatorCompletenessTest` (WP07 owns them); they must stay green and unchanged.

**Files**: `ServedRoute.java` (~25), `ServedRoutes.java` (~80), `DetailGoldenSuiteTest.java` (~170), `ResolvedStateGoldenTest.java` (~120).

**Validation**: targeted tests; revert: make `ServedRoutes` ignore a planted provider and the self-test goes red; `ownershipProblems` over planted providers reports a doubly claimed pair, a pair outside the provider's `OWNER` row and an omitted `expectedEntries` pair (same self-test); flip one golden byte in the scratch copy and the self-test is red.

### Subtask T072: Phase exit gate

**Steps** (with `export LC_ALL=C.UTF-8`; stage the new files with `git add` first, because the Windows-filename guard and the pin's tracked-path scan read `git ls-files`):
1. **Gate G**: `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`. `GoldenSuiteTest`, `ManifestCouplingTest`, `DetailManifestCensusTest`, `ComparatorCompletenessTest` unchanged and green; `ResolvedStateGoldenTest`, `HttpHarnessDetailTest`, `DetailFixtureTest`, `PermissionCaseCoverageTest` green.
2. **Gate P**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` (tracked-path scan over `S`; no perf class is added here, so the `@Tag("perf")` clause is not exercised).
3. AC-14.1 (i) to (iii) for the harness (planted self-test provider).
4. Optional: `.venv/bin/python -m tests.contract._mission_status_conformance --check` to confirm the goldens this WP reads are fresh (read-only; WP07/WP08 own them).
5. No JaCoCo edit: this WP adds no production class. Assert it: `git diff --stat -- services/mission-status-api/src/main` is empty.
6. Append tracer entries and commit. E-7 local `check`/native runs are allowed but not required (no production code changed).

## Self-contained green

- **Fixtures with tests.** The only conformance fixtures read are those WP07/WP08 committed (`R/conformance/**`), read through `ConformanceTree`; every other fixture is created in the test (temp dirs, planted test-local providers and annotated classes). `ServedRoutes` has no provider at this tip, so nothing is compared that no one serves (a fact about this tip that no permanent test asserts).
- **Floors and counts satisfiable here.** No production class: `R/jacoco-class-floor.properties` untouched (WP09 raised it; WP12 recounts). `DEFINED_RULE_COUNT` untouched (14, as P1b/WP03 left it; WP10 depends on WP03 through WP05, so it always starts from 14, and WP12 recounts it). Native floor (3) and `requests.json` (49) untouched. The census floors of WP07/WP08 are not edited (`DetailManifestCensusTest` stays green).
- **No forward reference.** No test or gate names `MissionDetailQuery`, `WorkPackageQuery`, `WorkPackageDetailQuery`, `ArtifactQuery`, `DetailRefusal`, `AdmissionGate`, or any route service or provider class. `ServedRoutes` loads providers by string name; `PermissionCaseCoverageTest` and `HttpHarnessDetailTest` use planted/test-local types; the recorder's route is a `Supplier<String>`. `ServedRoutesCompleteTest`, `PermissionCaseFloorTest` and `ProjectionRowCoverageTest` are WP18's and are not created here.
- **Pin `tests/ci/test_mission_status_api_build.py`.** Kept green: tracked-path scan over `S` (new files staged); the `@Tag("perf")` rule is vacuous here; the probe list, rule-9 literals and `EventsController` needles are untouched.
- **Mission record.** `M/meta.json` untouched; `M/status.json` is `materialize`d from `status.events.jsonl`, never hand-edited (compare with the coordination copy before committing any status file); only append-only trace files change under `M/`, so cutover-guard, the mission-state audit and corpus-blocking are unaffected.

## Plan defects found

- **Copy step versus `PROVISION_PLAN` (handled; ruling OO-4).** Plan section 11 P7 says the Java harness applies the plan "to a temporary copy", but that copy is made by `ProjectHeaderMaterialisation` (exists at the checkout; P1a/#5529 file, owned by no WP of this mission), whose `NOT_COPIED` set names `SYMLINK_PLAN` and not `PROVISION_PLAN`. **Orchestrator ruling OO-4 (2026-10-13, binding): `PROVISION_PLAN` sits at the fixture top level (not inside a Mission directory); this placement is chosen.** Handled here without editing that file: `ProvisionPlan` reads the plan from the **source fixture directory** and removes any stray copy at the scratch root (a test pins the removal with a planted copy inside a Mission directory). WP07's `M/data-model.md` section records the placement; a plan file found inside a Mission directory is WP07's defect, reported, not worked around.
- **No other forward reference or unsatisfiable floor found for WP10.**

## Definition of Done

- T066..T072 recorded with `spec-kitty agent tasks mark-status <Txxx> --status done --mission mission-status-read-api-mission-detail-01M4S6D5`.
- All eighteen owned files exist; `git diff --stat -- services/mission-status-api/src/main` is empty.
- `HttpHarness#startWith(Built, Map<Class<?>,Object>, String...)` exists and `HttpHarnessDetailTest` is green; existing `HttpHarness` callers compile unchanged.
- `DetailFixture` puts a `readText` and a `listMissions` read on one recorder.
- `DetailGoldenSuiteTest` self-test proves red on one perturbed byte and green on the unperturbed one; `ResolvedStateGoldenTest` green.
- `Utf8Host`/`RealPermissionFixture` write `not run: precondition unmet: <test id>` to `build/reports/not-run.txt` when the host cannot satisfy the precondition.
- Gate G and Gate P green under `LC_ALL=C.UTF-8`; the four unchanged golden/census tests green.

## Risks

- **A harness that silently compares nothing.** Mitigated by the planted self-test provider; keep it.
- **Class loading by name** hides a typo in a provider name: each of WP13 to WP16 asserts through the `loaded()` accessor that its own provider was found, that its `goldenFiles()` equal its row of the `ServedRoutes.OWNER` partition and that its `served()` equals `ServedRoutes.expectedEntries(goldenFiles())` (the provider-level completeness assertion, `<Route>ServedRouteTest`); WP18's `ServedRoutesCompleteTest` is the whole-set floor over the six golden files. Add a comment listing the four names and WP numbers.
- **Root runners and non-UTF-8 hosts** turn permission/non-ASCII cases into skips: the not-run report makes them visible; never convert a skip into a pass.
- **Touching a P1a file by accident** (`FilesystemFixtureFactory`, `FixtureHandles`): forbidden; compose instead.
- **Recorder thread safety** under the HTTP server thread: `RouteMarker` must not use a plain `ThreadLocal`.

## Reviewer Guidance

- Verify that `DetailFixture` is a new file composing `Built` and edits no P1a file; grep the diff for changes to `FilesystemFixtureFactory`, `FixtureHandles`, `ProjectHeaderMaterialisation`, `ConformanceTree` (must be none).
- Verify no test or class here names a type of WP12..WP18 (`grep -rnE 'MissionDetailQuery|WorkPackageQuery|WorkPackageDetailQuery|ArtifactQuery|DetailRefusal|AdmissionGate|ServedRoutesComplete'` in the diff: empty except string literals of the four provider class names in `ServedRoutes`).
- Verify the self-test provider is genuinely red on a perturbed byte (run it by flipping a byte in a scratch copy).
- Verify the stray-plan-file handling and that `ProvisionPlan` cannot write outside the scratch root (path containment).
- Run the implicated architectural gates (`ArchitectureRulesTest`, `PortLevelClassSetTest`) and the pin.

## Implementation command

```bash
spec-kitty agent action implement WP10 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
