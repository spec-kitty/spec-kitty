---
work_package_id: WP02
title: '[PR A] P1a Stream seam behind the inbound port (operator ruling A3 items 1 to 3)'
dependencies:
- WP01
requirement_refs:
- FR-013
- NFR-003
- NFR-004
- NFR-005
- C-005
- C-011
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-13T19:48:34.676934+00:00'
subtasks:
- T009
- T010
- T011
- T012
- T013
- T014
- T015
- T016
- T017
- T018
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamEvent.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamBatch.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamRequest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamSignal.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamScope.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamCursorText.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/exceptions/StreamCapacityReached.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/exceptions/StreamRefused.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/MissionStatusQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/Subscription.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/EventProjection.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/ProjectedSubscription.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/StreamAdmission.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/StreamSettings.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/ChangeFeed.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/StreamSubscriber.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/Resume.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/Change.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/ChangeBatch.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/FeedSignal.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/FeedSubscription.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/StreamShutdown.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamEvent.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamBatch.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamRequest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamSignal.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamScope.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/StreamCursorText.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/exceptions/StreamCapacityReached.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/exceptions/StreamRefused.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/MissionStatusQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/Subscription.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/EventProjection.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/ProjectedSubscription.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/StreamAdmission.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/StreamSettings.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/ChangeFeed.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/StreamSubscriber.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/Resume.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/Change.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/ChangeBatch.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/FeedSignal.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/stream/FeedSubscription.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/EventsController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/EventData.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/ProblemAdvice.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/StreamShutdown.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/MissionStatusProperties.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/PortLeakCanaryTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/EventProjectionTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/StreamAdmissionTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/StreamRequestTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/StreamScopeTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/StreamCursorTextTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/StreamSettingsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/PlainStreamCallerTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/FixtureHandlesLoggingTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/RefusalRowsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/PortTypesTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/SubscribeConnectTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/StreamFx.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/BlankFinalLineCursorTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/ChangeFeedTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/Ac3ResumeAndBatchTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/FilesystemMissionEventSourceStampTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/**/FilesystemMissionEventSourceAllowlistFlowTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/http/SpyQuery.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/http/StreamRig.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/FilesystemFixtureFactory.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/FixtureHandles.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – [PR A] P1a Stream seam behind the inbound port (operator ruling A3 items 1 to 3)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: **PR A** (draft; phase tag **P1a**). PR A stacks on the branch carrying #5529's last slice; the operator retargets it to `main` after #5529 lands. No agent pushes, opens or retargets a PR.
- **Depends on**: WP01 (P1) within the manifest. **External dependency (not a `dependencies` entry)**: the #5529 re-cut tip must already be merged into this branch by the orchestrator (WP01 cannot start otherwise, so this WP cannot either). Every path below is a re-cut path (**exists after the re-cut**); in a pre-re-cut tree none of `application/query/**` exists. If you find the flat layout, stop and report BLOCKED.
- **Dependents**: WP03 (P1b) builds its ArchUnit gates on the result; #5533's Java work and the MCP adapters of #6116 stack on the port this WP shapes.
- **Write scope**: `owned_files` only (the `**/` test globs admit any directory; put each test in the directory that mirrors the main package of the class it tests, listed per subtask).
- **Named edits (out-of-map; not in `owned_files`)**. Each: rebase first, state the edit in the commit message, touch nothing else of the file.
  - `J/application/query/MissionStatusQueryService.java` (the `subscribe` path, admission, `changesSince`, `endStreams`; `maxConnections` plumbing). **Owned by WP01.**
  - `J/config/ServiceWiring.java` (the `maxConnections` setting, its second and last edit, before P3). **Owned by WP01.**
  - `T/architecture/CoupledSymbolsShapeTest.java` (the stream assertions move to the post-ruling shape; lower bounds and presence only). **Owned by WP01.**
  - `R/jacoco-class-floor.properties` (the `application` count line only). **Owned by WP01.**
  - `R/portlevel-tests.txt` only if a test id changes (none is expected: the ten retyped files keep their ids). **Owned by WP05.**
  - `M/traces/approach.md`, `M/traces/tooling-friction.md` (append-only, if a friction is observed). Tracer files are never in `owned_files`.

**Path aliases** (repo-relative): `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Package root `org.speckitty.missionstatus`.

## Objective

Make the live-stream projection, the stream cap and the shutdown registry belong to the inbound port, so a second inbound adapter (the MCP resource adapters of #6116) can neither bypass the leak projection nor the cap: the port emits only a projected, sealed `StreamEvent`, refuses on capacity with `StreamCapacityReached`, decodes its own scope and cursor text (`StreamRequest`), and ends every stream on `endStreams()`. **Behaviour-preserving: the HTTP stream is unchanged byte for byte and the HTTP stream suites are not edited.**

## Context

- Source: operator ruling A3 ("operator 2026-10-13, #5529 landing finding A3"), plan section 15. It is binding: implement it, do not weigh it. Items 1 to 3 are this WP; item 4 (head projection) was WP01; item 5 (ArchUnit gates) is WP03.
- Classification (plan 15.2, D-119): a behaviour-preserving structural change to #5529 code, a widened campsite. Commits use `refactor(campsite)`; the first red-first commit uses `test(campsite)`. The HTTP stream suites keep every assertion, expected value and golden byte; **ten** named files get type-level edits that never change an expected value (a changed expected value, a deleted assertion or a weakened matcher in them is a rejection).
- What changes where (plan 15.3 table), in one list:
  - Port: `MissionStatusQuery#changesSince` returns `StreamBatch` and gains abstract `void endStreams()`; `subscribe` also throws `StreamCapacityReached`; `Subscription` keeps `next(Duration)`/`close()` but signals are the port's `StreamSignal` with `Events`.
  - New port values: `StreamEvent` (sealed), `StreamBatch`, `StreamRequest`; exception `StreamCapacityReached`; `StreamRefused` gains an optional fixed detail; `StreamScope#parse`; `StreamCursorText` unparseable detail.
  - Application-internal (`application.query.stream`): `EventProjection`, `ProjectedSubscription`, `StreamAdmission`, `FeedSubscription`, `FeedSignal`, and the moved `Change`/`ChangeBatch`; `StreamSettings` gains `maxConnections`.
  - Adapter: `EventsController`, `EventData`, `ProblemAdvice` reduced to transport.
  - Config: `StreamShutdown` (the `ContextClosedEvent` listener), `MissionStatusProperties.Stream.maxConnections`.
- Why the Spring event stays in `config`: `@EventListener(ContextClosedEvent.class)` cannot live in `application` (rule 2a: no Spring), and a destroy method would run after the web server's graceful shutdown has waited.
- Two mechanisms, two names (plan 15.4 item 2): `StreamAdmission` (a **refusing** cap on open streams, 128) is different from `AdmissionGate` (WP12/P8: a fair four-permit semaphore that **never refuses**). They share no state and no name.
- Plan references: sections 15.1 to 15.7, 1.1 (placement), 1.2 (layer table), 5 (gates), 11 (P1a row), 13 (ports).

### Gate vocabulary

- **Gate G**: `export LC_ALL=C.UTF-8` then `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`. Never `check` as a phase gate.
- **Gate P**: from the repository root `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` (stage new files first: it reads `git ls-files`). For this WP also `-k "events_controller or http_adapter_packages"`.
- Targeted loop: `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.<pkg>.<Class>'`.
- **E-7 (operator word given)**: local `check`, `nativeCompile nativeTest`, `nativeSmoke -PnativeBinary=<binary>` are allowed before review; CI is the authority. This WP's native-image note (plan 15.7): `StreamEvent` is not serialised by Jackson (the adapter writes sorted maps), `EventProjection`/`StreamAdmission` are plain Java, `StreamShutdown` is an ordinary bean AOT processes, `maxConnections` binds like `queueCapacity`; `MissionStatusApplicationHints` stays unchanged unless a local `nativeTest` proves a miss (then it is a named edit of the P6/P8 rule, not yours: report it).

---

### Subtask T009: First commit (red-first): PortLeakCanaryTest; pre-flight; read the visibility of the moved classes

**Purpose**: ATDD first (C-011). Prove the defect before the fix: today the port hands out raw ledger rows. Also run the C-005 pre-flight of this phase.

**Steps**:
1. Pre-flight (C-005, D-107): `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'` green; `git log -1 --format=%H <ref carrying #5529>` recorded in the first commit message; the string-literal grep `grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' services/mission-status-api/src/test services/mission-status-api/build.gradle.kts` and the old-path grep (`grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github`, empty after WP01) read and clean.
2. Read, from the tip you start on, the visibility of the ChangeFeed classes the re-cut moved into `application.query.stream` (`ChangeFeed` and its nested records are package-private at the pre-re-cut checkout; `Change`, `ChangeBatch` are re-cut `port.in.dto` records). If a moved class stayed package-private while `MissionStatusQueryService` (parent package) needs it, **widen it as a named edit** in the first refactor commit and say so (plan 1.1; R-36). Otherwise record "none needed".
3. Write `PortLeakCanaryTest` (put it in `T/application/query/PortLeakCanaryTest.java`). It is a **port-level** test, no HTTP, no Spring: plant a ledger whose status rows carry a credential-shaped `reason`, a path-shaped `reviewRef`, and an address in `reasonSource` and `claimAgent` (all synthetic canaries; never a home path or a real name: C-006), build the service over the in-memory/fixture source the other port-level tests use, subscribe and read `changesSince` through `MissionStatusQuery` **only**, and assert:
   - nothing the port returns (a record-component walk by reflection plus `toString` of every signal and event) contains any canary string;
   - no returned type has a member named `reason`, `reviewRef`, `reasonSource` or `claimAgent` (the four raw names, with no exception for the `LogTruncated` wire word: that component is `truncationCause`).
   Write every call so that it **compiles on the phase base and on the tip**: assign results to `Object`/`var`, walk with reflection, do not import `StreamEvent`/`StreamBatch` (they do not exist on the base).
4. Run it on the phase base and record it **red** (the port returns `StatusEvent` inside `Change`, so the canaries/member names are found). Commit it alone as `test(campsite): PortLeakCanaryTest, red on the phase base`. This is the only commit of the WP that is allowed to be red.

**Files**: `T/application/query/PortLeakCanaryTest.java` (new, ~140 lines).

**Validation**: red on the base for the stated reason (not for a compile error: if it does not compile on the base it proves nothing); green at the WP tip (T018).

---

### Subtask T010: Raw feed becomes application-internal (git mv, copies, retype)

**Purpose**: item 1 prerequisite. The raw ledger-row vocabulary (`Change`, `ChangeBatch`, `LineKind`-bearing values) leaves the port and stays inside `application.query.stream`.

**Steps** (logic untouched; `git mv` keeps history):
1. `git mv` `J/application/query/port/in/dto/Change.java` and `.../ChangeBatch.java` to `J/application/query/stream/` and fix the `package` line. They become **public records** (application-internal visibility only: rules 3 and 4 let no adapter depend on `application.query.stream`).
2. Create `J/application/query/stream/FeedSignal.java`: a **copy** of the raw `port/in/dto/StreamSignal` (variants `Forwarded`, `Truncated`, `Dropped`, `Closed`, `Idle`) under the name `FeedSignal`. Create `J/application/query/stream/FeedSubscription.java`: a **copy** of the raw `port/in/Subscription` (`next(Duration)` returning `FeedSignal`, `close()`). The port keeps its own `Subscription` and its rewritten `StreamSignal` (T012).
3. Retype `ChangeFeed`, `StreamSubscriber` (implements `FeedSubscription`) and `Resume` to the raw feed vocabulary (`FeedSignal`, `FeedSubscription`, the moved `Change`/`ChangeBatch`). **No logic change**: the queue capacity, overflow, floors and order of signals are what #5529 built.
4. Edit `CoupledSymbolsShapeTest` (named edit, WP01's file) in the same commit that moves the symbols: the two row-5 assertions for `Change` and `ChangeBatch` now expect `application.query.stream.{Change,ChangeBatch}` and that the `port.in.dto` names do not load. Lower bounds and presence only.
5. Commit as `refactor(campsite): make the raw change feed application-internal`.

**Files**: `Change.java`, `ChangeBatch.java` (moved), `FeedSignal.java` (new, ~45), `FeedSubscription.java` (new, ~25), `ChangeFeed.java`, `StreamSubscriber.java`, `Resume.java` (retyped), `T/architecture/CoupledSymbolsShapeTest.java` (named edit).

**Validation**: it compiles only together with T012 (the port still names `Change` until then); keep the commit order such that **each commit compiles** (do T010 and the port retyping in one commit if a half-state does not compile). Run `ChangeFeedTest` after T016's type-level edit.

---

### Subtask T011: Sealed projected StreamEvent, StreamBatch and EventProjection

**Purpose**: item 1. `EventProjection` is the only code that turns a raw row into something a consumer can see.

**Steps**:
1. `J/application/query/port/in/dto/StreamEvent.java`: a `sealed interface`, records only, **projected values only**:
   - `StatusTransition(String missionId, String eventId, String wpId, String fromStatusLane, String toStatusLane, String at, ActorHandles actor, boolean force, StreamCursor cursor)`
   - `Lifecycle(String missionId, String eventId, String eventType, String at, StreamCursor cursor)`
   - `LogTruncated(String missionId, String truncationCause, long detectedAtOffset, StreamCursor resetCursor)` (`truncationCause` holds the existing wire word of `StreamSignal.Truncated.reason().wire()`, which `EventData` writes under the wire key `reason`: PLAN-FRESH3-003)
   - nested `ActorHandles(String tool, String role, String profile)` (each nullable, strict-projected)
   - `resumeCursor()` returns the cursor after the row for the first two and empty for `LogTruncated` (the reset cursor is data, never an id).
   No member named `reason`, `reviewRef`, `reasonSource` or `claimAgent` anywhere in the type.
2. `StreamBatch(List<StreamEvent> events, StreamCursor cursor)` in `port/in/dto` (the result of `changesSince`).
3. `J/application/query/stream/EventProjection.java`: `public final class` over `LeakClasses` and the injected `Consumer<Diagnostic>`:
   - `Optional<StreamEvent> project(Change)` and `Optional<StreamEvent> project(FeedSignal.Truncated)`;
   - it holds what `EventData` held, **moved**: the `WP_ID` pattern `^WP[0-9]{2,}$`, the drop of a non-display target lane, `Instants.parse` of `at` raising `ProjectionError` for a missing or non-instant value, `Projector.strict` of `missionId` and `eventId`, the three actor handles through `Projector.strict(..., true)`;
   - a `ProjectionError`, for a change **or** for a truncation, writes **one** `Diagnostic(PROJECTION_REFUSED, mid8, null)` and returns `Optional.empty()`; `ProjectedSubscription#next` turns that into `Events(List.of())`, so the stream goes on exactly as `EventsController#send`/`#sendTruncation` did (drop the frame, write the diagnostic, keep the stream open: PLAN-FRESH3-012).
   Projection runs **on the consuming thread, after the raw signal was queued**, so the feed is exactly what #5529 built.
4. `T/application/query/stream/EventProjectionTest.java`: every branch of the moved allow-list with the **same cases `EventData` had through HTTP** (invalid work package id, non-display target lane, missing `at`, non-instant `at`, strict field refused for Mission id/event id/each actor handle, the three event kinds), plus the **truncation-refusal case** (a `LeakClasses` that flags the Mission id: one diagnostic, an empty `Optional`, stream open). `EventProjection` must be branch-complete (0.90 per-class line floor).
5. Revert-fails (state in the commit): move a check (`WP_ID`, display lane, instant, actor handle) back out of `EventProjection`, or let a raw `StatusEvent` reach a `StreamSignal`: `EventProjectionTest` and `PortLeakCanaryTest` go red.

**Files**: `StreamEvent.java` (new, ~70), `StreamBatch.java` (new, ~20), `EventProjection.java` (new, ~190), `T/application/query/stream/EventProjectionTest.java` (new, ~260).

**Validation**: `--tests '*EventProjectionTest'` green; the diagnostic code/mid8/line shape is unchanged (T016 pins it with `CanaryScanTest`).

---

### Subtask T012: ProjectedSubscription, StreamSignal.Events, changesSince returns StreamBatch, abstract endStreams

**Purpose**: item 1 plumbing: the port speaks only projected values.

**Steps**:
1. `StreamSignal` (port, `port/in/dto`): variants become `Events(List<StreamEvent>)` (replaces `Forwarded` and `Truncated`; an empty list is legal and means "a row was consumed and dropped"), `Dropped`, `Closed`, `Idle`. Name and the `Subscription#next` contract stay.
2. `Subscription` (port, `port/in`): kept and retyped; its signal type is the port's `StreamSignal`. `ProjectedSubscription` implements it.
3. `J/application/query/stream/ProjectedSubscription.java`: `public final`; implements `Subscription` over a `FeedSubscription`: `next` maps one raw signal to one `StreamSignal` through `EventProjection` (on the caller's thread, so queue capacity, overflow and ordering are the raw feed's); `close` closes the feed subscription and releases the admission place **once**.
4. `MissionStatusQuery` (port): `changesSince` returns `StreamBatch`; new **abstract** `void endStreams()` (idempotent; ends every open subscription; the composition root's shutdown hook, not an adapter operation). It has **no default body** so a second implementer cannot forget it.
5. `MissionStatusQueryService` (named edit): `changesSince` projects through `EventProjection`; `endStreams()` delegates to `StreamAdmission#endAll` (T013).
6. Commit as `refactor(campsite): project the stream at the inbound port`.

**Files**: `StreamSignal.java`, `Subscription.java`, `MissionStatusQuery.java`, `ProjectedSubscription.java` (new, ~80), `MissionStatusQueryService.java` (named edit).

**Validation**: compiles (tests of T016 are updated in the same commit series); `PortLeakCanaryTest` green once T011 and T012 are in.

---

### Subtask T013: Admission and shutdown behind the port

**Purpose**: item 2. One cap and one shutdown registry serve **every** inbound adapter: an MCP subscription and an HTTP stream draw from the same 128 places.

**Steps**:
1. `J/application/query/stream/StreamAdmission.java`: `public final`; the admitted counter (`AtomicInteger`), the cap, the live registry (`ConcurrentHashMap.newKeySet()`); `admit()` throws `StreamCapacityReached` over the cap; `release()`; `register`; `endAll()`.
2. `J/application/query/port/in/exceptions/StreamCapacityReached.java`: `public final class` (unchecked, no message detail, no stack: the moved body of the controller's nested class).
3. `StreamSettings`: a fourth component `maxConnections` (default 128 = `application.properties`), compact-constructor check `maxConnections < 1` with the **moved message** `mission-status.stream.max-connections must be at least 1`, the existing three-argument constructor kept (defaulting it) so every `new StreamSettings(...)` compiles, `withMaxConnections(int)`.
4. `MissionStatusProperties.Stream`: gains `@DefaultValue("128") int maxConnections`. The property key `mission-status.stream.max-connections` and its default are **unchanged**; only the reader changes.
5. `MissionStatusQueryService#subscribe` (named edit): `admit()` **first** (the old controller order: the check ran before `subscribe()` cost a listing), then the existing resolve/connect wrapped in `ProjectedSubscription`; **any exception after `admit()` releases the place**; a refused call takes none. `ServiceWiring#missionStatusQuery` passes `maxConnections` into `StreamSettings` (named edit; its second and last).
6. `J/config/StreamShutdown.java`: `@Configuration(proxyBeanMethods = false)` holding `@EventListener(ContextClosedEvent.class)` that calls `MissionStatusQuery#endStreams()` on the injected **primary** `MissionStatusQuery` (the bean the controllers use, so a test wrapper delegates).
7. Tests: `T/application/query/stream/StreamAdmissionTest.java` (port level, **no HTTP**): cap-plus-one `subscribe` throws `StreamCapacityReached`; a closed subscription frees its place once; a failed `subscribe` frees its place; a refused call takes none; `endStreams` closes all and is idempotent. `T/application/query/stream/StreamSettingsTest.java`: `maxConnections < 1` throws with the moved message; the three-argument constructor defaults to 128.
8. Revert-fails: put the counter back in the controller, release a place twice, or not on a failed `subscribe`: `StreamAdmissionTest` goes red; drop `endStreams` from the shutdown listener: `StreamLifecycleTest` (graceful shutdown under 20 s) goes red.

**Files**: `StreamAdmission.java` (new, ~70), `StreamCapacityReached.java` (new, ~20), `StreamShutdown.java` (new, ~35), `StreamSettings.java`, `MissionStatusProperties.java`, `StreamAdmissionTest.java` (new, ~170), `StreamSettingsTest.java` (new, ~60), named edits to `MissionStatusQueryService.java` and `ServiceWiring.java`.

**Validation**: `--tests '*StreamAdmissionTest' --tests '*StreamSettingsTest' --tests '*StreamCapacityTest' --tests '*StreamLifecycleTest'` green; the HTTP-visible behaviour (503, `stream_capacity_reached`, freed place, `totalSubscriptions` unchanged by a refusal) is identical.

---

### Subtask T014: Request vocabulary: StreamRequest, StreamScope#parse, StreamCursorText detail, StreamRefused fixed detail

**Purpose**: item 3. The two mappings leave the controller; the order of the three connect-time decisions is fixed once so a second adapter cannot reorder them.

**Steps**:
1. `StreamScope.parse(String missionIdOrNull)`: `null` is `all()`, a ULID is `mission(...)`, anything else throws `StreamRefused(UNKNOWN_MISSION)` (the moved `EventsController#scope`).
2. `StreamCursorText`: the unparseable case throws `StreamRefused(MISALIGNED, UNPARSEABLE_DETAIL)` (the moved `UnparseableCursor` mapping); `NEGATIVE` unchanged; `UNPARSEABLE_DETAIL` stays public.
3. `StreamRefused`: optional fixed `detail()`; the existing constructor and the **six `Kind` values untouched** (so `PortTypesTest` keeps its exact-set assertion). `status()` is the HTTP contract's value: add Javadoc on the accessor saying so (E-11: moving it is #6116's plan, recorded as R-37). Do not move it.
4. `StreamRequest` (`port/in/dto`): `record StreamRequest(StreamScope scope, Optional<StreamCursor> cursor)` with `static StreamRequest parse(String missionIdOrNull, String cursorTextOrNull)` applying the legacy order once: (1) cursor text without a Mission is `CURSOR_WITHOUT_MISSION`; (2) `StreamCursorText.parse`; (3) `StreamScope.parse`. Then the service does admission and lookup (capacity, then lookup and ledger probe).
5. Tests (mirror directory `T/application/query/port/in/dto/`): `StreamRequestTest` (the order of the three decisions, table-driven; reorder it and the test goes red), `StreamScopeTest` (null, ULID, non-ULID), `StreamCursorTextTest` (parseable, negative, misaligned with the fixed detail).
6. Revert-fails: drop the order of `StreamRequest.parse`, or lose the fixed detail: `StreamRequestTest` and `StreamRefusalTest` go red.

**Files**: `StreamRequest.java` (new, ~45), `StreamScope.java`, `StreamCursorText.java`, `StreamRefused.java`, `StreamRequestTest.java` (new, ~110), `StreamScopeTest.java` (new, ~60), `StreamCursorTextTest.java` (new, ~80).

**Validation**: `--tests '*StreamRequestTest' --tests '*StreamScopeTest' --tests '*StreamCursorTextTest' --tests '*StreamRefusalTest' --tests '*PortTypesTest'` green.

---

### Subtask T015: Reduce EventsController and EventData to transport; update ProblemAdvice

**Purpose**: the adapter keeps only the pump, the framing and the wire shaping.

**Steps**:
1. `EventsController`: loses `LeakClasses`, its `Consumer<Diagnostic>` (it served only the projection refusals), `admitted`, `maxConnections`, `live`, `endStreams`, `scope()`, `parse()` and the two nested exception classes. It calls `StreamRequest.parse` then `query.subscribe`, and **closes the subscription on any failure between `subscribe` and the pump start** (the place was released by the old `finally`; it is now released by the close). **Keep every one of the five pinned needles** of `tests/ci` (`events_controller_violations`): `new SseEmitter(0L)`, `mission-status.stream.heartbeat-interval`, `.comment(" heartbeat")`, the `Last-Event-ID` and `streamCursor` parameter names, and **no import of `config`**.
2. `EventData`: `Frame of(StreamEvent)` writes the same sorted-key maps with explicit nulls through the same `JsonMapper`; takes no `LeakClasses`, holds no allow-list, pattern or `Projector`. Event names stay `status-transition`, `mission-lifecycle`, `log-truncated`; the wire key `reason` carries `truncationCause`.
3. `ProblemAdvice`: remove the `UnparseableCursor` handler; the `StreamRefused` handler uses `detail()` when present; the capacity handler names `application.query.port.in.exceptions.StreamCapacityReached` and keeps the 503 and code `stream_capacity_reached` through `ProblemMapper.streamCapacity()` unchanged. (WP12 adds the `DetailRefusal` handlers later as a named edit.)
4. Preserved on the wire, pinned by tests you do **not** edit: every SSE frame byte, the `id:` line on a Mission-scoped stream only, `log-truncated` without an id, the heartbeat comment, every connect-time refusal's status/`code`/`detail`/order, no event on a refusal.

**Files**: `EventsController.java`, `EventData.java`, `ProblemAdvice.java` (all shrink).

**Validation**: `StreamGoldenTest`, `StreamDeliveryTest`, `StreamTruncationTest`, `EventDataContractTest`, `StreamRefusalTest`, `StreamCapacityTest` unchanged and green; `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q -k "events_controller or http_adapter_packages"` green.

---

### Subtask T016: Ten named type-level edits and three plumbing edits; compiler-completeness grep

**Purpose**: keep the existing suites compiling on the new types without changing what they assert (plan 15.5, closed list).

**Steps**:
1. **The ten files** (test packages mirror the re-cut main packages; the paths below are the post-re-cut mirror of the pre-re-cut `application/...` paths): `PortTypesTest`, `SubscribeConnectTest`, `StreamFx`, `BlankFinalLineCursorTest`, `ChangeFeedTest` (in `T/application/query/...`), `T/conformance/port/Ac3ResumeAndBatchTest.java`, `T/adapter/out/filesystem/{FilesystemMissionEventSourceStampTest,FilesystemMissionEventSourceAllowlistFlowTest}.java`, `T/adapter/in/http/rest/RefusalRowsTest.java`, `T/testsupport/http/SpyQuery.java`. Allowed diff content: import lines, type names, the accessor an assertion reads from (`StreamEvent` components where `LineKind` and `Change` were read). **Forbidden**: a changed expected value, a deleted assertion, a weakened matcher. Specifics:
   - `ChangeFeedTest` changes only the renamed raw types (`FeedSignal`, `FeedSubscription`, the moved `Change`/`ChangeBatch`).
   - `RefusalRowsTest` (PLAN-FRESH3-002): `anUnexpectedExceptionIsAGeneric500ProblemWithoutDetail` builds an anonymous `MissionStatusQuery`; the edit changes `changesSince`'s return type to `StreamBatch` and adds an empty-bodied `endStreams()`. Nothing else (the `IllegalStateException` bodies of `project()` and `missions()`, the `UnsupportedOperationException` bodies and every assertion stay).
   - `SpyQuery` implements the retyped methods and delegates `endStreams`.
   - The two `PortTypesTest` cases that validate `Change` and `ChangeBatch` stay valid against the records' new package (`application.query.stream`).
2. **Three plumbing edits, no assertion in them**:
   - `FilesystemFixtureFactory`: a new overload taking a `StreamSettings` (the fixture's service, not the controller, owns the cap now); `#fromTreeWithOrdering` keeps reflecting the package-private seven-argument `MissionStatusQueryService` constructor (kept and pinned by WP01).
   - `StreamRig.of`: reads `mission-status.stream.max-connections` out of its property list and hands it to `FilesystemFixtureFactory` through that overload.
   - `FixtureHandles#recorder()`: **records the diagnostic and also writes the path-free line of `config.LoggingDiagnostics`** (logger `org.speckitty.missionstatus.diagnostics`, level WARN, text `diagnostic code=<wire> mid8=<mid8> line=<n or ->`), because the projection's diagnostic is now written by the fixture service whose consumer is the recorder, no longer by the controller's Spring consumer. This keeps `CanaryScanTest` (its three `code=projection_refused mid8=` assertions read the captured log) unchanged.
3. `T/testsupport/FixtureHandlesLoggingTest.java` (new, ~70): pins the parity of the recorder's log line with the `LoggingDiagnostics` line.
4. **Compiler-completeness grep** (the closed list is the output of a grep, not a recollection): `grep -rlE '\b(Change|ChangeBatch|StreamSignal|Subscription)\b|changesSince' services/mission-status-api/src/test`. The output must be exactly: the ten files above, `T/architecture/CoupledSymbolsShapeTest.java` (WP01's file, named edit), and the new tests of this phase. A further file is an orchestrator item (the re-cut added a consumer; the compiler finds it too): report it, do not edit a file you do not own without saying so in the commit.
5. Diff check you run before committing: over the ten files, `git diff` lines starting `-`/`+` that contain `assert`, `expected`, `assertThat`, a string/number literal on an assertion line are inspected; none changed.

**Files**: ten edited tests/helpers, `FilesystemFixtureFactory.java`, `StreamRig.java`, `FixtureHandles.java` (plumbing), `FixtureHandlesLoggingTest.java` (new).

**Validation**: `--tests '*RefusalRowsTest' --tests '*ChangeFeedTest' --tests '*SubscribeConnectTest' --tests '*FixtureHandlesLoggingTest' --tests '*CanaryScanTest'` green.

---

### Subtask T017: PlainStreamCallerTest, CoupledSymbolsShapeTest named edit, JaCoCo application count

**Purpose**: the AC-13.3 plain-Java caller extended to the stream; the shape pin moves to the post-ruling shape; the count line is derived.

**Steps**:
1. `T/application/query/PlainStreamCallerTest.java`: a plain-Java caller, **no Spring context, no HTTP type**: strings in (`StreamRequest.parse(missionIdOrNull, cursorTextOrNull)`), `MissionStatusQuery#subscribe`, `Subscription#next`, `StreamEvent` out; it observes the same cap (a `StreamCapacityReached` at cap-plus-one) and `endStreams()` ends its stream. It names no type of a later phase (not `PlainCaller`, which is WP12's).
2. `CoupledSymbolsShapeTest` (named edit): the stream assertions move to the post-ruling shape: presence of `StreamEvent`, `StreamBatch`, `StreamRequest`, `StreamCapacityReached`, `EventProjection`, `ProjectedSubscription`, `StreamAdmission`, `FeedSignal`, `FeedSubscription`, `endStreams` on `MissionStatusQuery`, `StreamSettings.maxConnections`; lower bounds and presence only (no equalities).
3. JaCoCo (named edit of `R/jacoco-class-floor.properties`, the `application` line only): after Gate G's `test jacocoTestReport`, run from `S` the plan section 2 command and write the number it prints **at the commit that adds the classes**:
   `python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"`
   This phase **adds** `StreamEvent` with its four nested records, `StreamBatch`, `StreamRequest`, `StreamCapacityReached`, `EventProjection`, `ProjectedSubscription`, `StreamAdmission`, `FeedSubscription`, `FeedSignal` with its five nested variants, and `StreamSignal$Events`; it **drops** the nested `StreamSignal$Forwarded` and `StreamSignal$Truncated` (PLAN-FRESH3-013), which **lowers** the number to write because `jacocoScopeCheck` fails when the recorded count exceeds the classes found. `Change`/`ChangeBatch` move within `application.*` and do not change the count. `domain` is unchanged. Do not predict; write the printed value and state before/after in the commit.
4. Every new application class must meet the 0.90 per-class line floor (`EventProjection` is branch-complete by `EventProjectionTest`).

**Files**: `PlainStreamCallerTest.java` (new, ~110), `T/architecture/CoupledSymbolsShapeTest.java` (named edit), `R/jacoco-class-floor.properties` (one line).

**Validation**: `--tests '*PlainStreamCallerTest' --tests '*CoupledSymbolsShapeTest'` green; `jacocoScopeCheck` green.

---

### Subtask T018: Gate

**Purpose**: exit evidence of the WP.

**Steps**:
1. **Gate G** (`LC_ALL=C.UTF-8`), whole.
2. The unchanged HTTP stream suites **by name**: `StreamGoldenTest`, `StreamDeliveryTest`, `StreamTruncationTest`, `StreamCapacityTest`, `StreamLifecycleTest`, `StreamFaultTest`, `StreamRefusalTest`, `EventDataContractTest`, and `CanaryScanTest` with its three `code=projection_refused mid8=` assertions byte for byte (`git diff` of these files over the WP range is empty).
3. `RefusalRowsTest`, `ChangeFeedTest`, `SubscribeConnectTest`; the new tests (`PortLeakCanaryTest`, `EventProjectionTest`, `StreamAdmissionTest`, `StreamRequestTest`, `StreamScopeTest`, `StreamCursorTextTest`, `StreamSettingsTest`, `PlainStreamCallerTest`, `FixtureHandlesLoggingTest`).
4. **Gate P** plus `-k "events_controller or http_adapter_packages"` (the five `EventsController` needles and the http-adapter packages).
5. The compiler-completeness grep of T016 (output = ten files + `CoupledSymbolsShapeTest` + this phase's new tests).
6. The native smoke stage `base` is the byte-for-byte evidence on the four CI legs (37 requests, stream requests among them): nothing to run locally; optional E-7 local `check`/`nativeCompile nativeTest`/`nativeSmoke` for the reviewer, never a substitute.
7. Hygiene: Windows-filename guard after staging; the terminology grep over `S/src/main` and `S/README.md` empty; no home path or username in any file or log you wrote.

**Validation**: all green; list commands and counts in the hand-off.

---

## Self-contained green

- **Fixtures live with their tests**: this WP plants nothing in `T/architecture/fixture/**` (WP03 does). Its fixtures are the existing stream fixtures plus test-support plumbing (`StreamRig`, `FilesystemFixtureFactory`, `FixtureHandles`), all owned here. `PortLeakCanaryTest` builds its canary ledger itself.
- **Floors and counts satisfiable now**: `application` line of `jacoco-class-floor.properties` = the printed count at the adding commit (lower than a naive sum, because two nested classes are dropped); `domain` unchanged; `DEFINED_RULE_COUNT` stays 12 (WP03 raises it); `CoupledSymbolsShapeTest` is lower-bound only; no `@Tag("native")` test is added (pinned count stays 3 until WP17/P13, D-99), no smoke stage, no workflow line, no `requests.json` change.
- **No test or gate names a type of a later WP**: nothing here names `WpId`, `MissionDetailQuery`, `PlainCaller`, `TextSource`, `AdmissionGate`, `DetailRefusal` (plan 11, PLAN-FRESH4-001). `StreamAdmission` and `AdmissionGate` share no state or name.
- **Pin clauses kept green**: the `EventsController` needles (T015) and the http-adapter sub-directory names (no new `adapter/in/http` directory), the tracked-path scan (stage new files first), the rule-9 literals of `ArchitectureRulesTest` (untouched), the probe list (WP01 already fixed it). The pin file is read, never edited, by this WP.
- **Mission record**: `meta.json`, `status.events.jsonl` and `status.json` are not touched; `status.json` is only ever produced by `spec-kitty agent status materialize --mission <slug>`, never by hand, so cutover-guard, the mission-state audit and corpus-blocking see a complete record; no untracked CLI state is committed blind (compare with the coordination copy first). Appends to tracer files are append-only.
- **Behaviour is preserved**: the HTTP stream suites are not edited; the ten retyped files change types only; the native smoke `base` replay is the byte-for-byte evidence on CI.

## Plan defects found

- **R-36 (visibility), not a defect but an open read**: plan 1.1 says the visibility of the #5529 classes the re-cut moved into `application.query.stream` is the re-cut's; T009 step 2 reads it from the tip. If `MissionStatusQueryService` needs a package-private class, widening is a named edit stated in the commit.
- **Test-glob scope**: `owned_files` lists the new and edited test classes with `**/` globs; they admit any directory. The T016 grep and the named locations in this prompt are the real constraint. No overlap with WP03's owned test paths (its files are all under `architecture/`).
- **`CoupledSymbolsShapeTest` is WP01's file** and WP02 must edit it twice (T010, T017). Both are declared named edits in wps.yaml; the plan's own sentence is "P1a edits those assertions to the post-ruling shape in the same commit that retypes the symbols", so a single edit in T010 plus the extension in T017 is the minimal reading; do not edit it beyond the stream assertions.
- Nothing forward-referencing or unsatisfiable was found for this WP.

## Definition of Done

- [ ] Each of T009 to T018 has a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- [ ] `PortLeakCanaryTest` red on the phase base (for the stated reason), green on the tip; the first commit is `test(campsite)` and carries the #5529 tip sha.
- [ ] Port emits only `StreamEvent`/`StreamBatch`/`StreamSignal.Events`; no `Change`, `ChangeBatch`, `LineKind`, `StatusEvent`, `LedgerLine` reachable from `application.query.port.in..`.
- [ ] `StreamAdmission` owns the cap and the live registry; `StreamCapacityReached`, `StreamShutdown`, `maxConnections` done; key and default unchanged.
- [ ] `StreamRequest.parse` applies the legacy order once; `StreamRefused` has the optional fixed detail with the six `Kind` values untouched.
- [ ] `EventsController`/`EventData` are transport only; five needles kept; no `config` import.
- [ ] The ten files carry type-level edits only (diff-checked); plumbing edits contain no assertion; compiler-completeness grep output as specified.
- [ ] Unchanged HTTP stream suites and `CanaryScanTest` green with an empty diff; Gate G and Gate P green; `application` count line derived by the section 2 command.
- [ ] No home path, username or token in any file; canaries synthetic.

## Risks

- **Silent behaviour drift on the wire** (event order, null members, diagnostic wording). Mitigation: the unchanged golden/delivery/truncation suites, `EventDataContractTest`, `CanaryScanTest`, and the native smoke `base` replay.
- **Admission order**: checking capacity after the lookup costs a listing; keep `admit()` first (old controller order). **Double release** of a place on a failed `subscribe` plus a `close`: `StreamAdmissionTest` covers it.
- **Diagnostic parity**: if `FixtureHandles#recorder()` does not write the same line as `LoggingDiagnostics`, `CanaryScanTest` goes red without a code defect; `FixtureHandlesLoggingTest` pins it.
- **Half-compiling commits**: the port retype touches many files; keep every commit compiling or squash the dependent edits into one.
- **Count off by the dropped nested classes**: derive, never sum.

## Reviewer Guidance

- Grep the diff of the ten files for a changed `assert`/expected value/matcher: any is a rejection. Confirm the HTTP stream suites and `CanaryScanTest` have an empty diff.
- Confirm `PortLeakCanaryTest` is red on the base commit (run it on a scratch checkout of the base) and not for a compile error.
- Confirm the port exposes no raw row (`StreamEvent` has no `reason`/`reviewRef`/`reasonSource`/`claimAgent`), and that `EventProjection` writes one path-free diagnostic and yields none on refusal, for a change and for a truncation.
- Confirm one cap and one registry for all adapters (`StreamAdmissionTest` is port level, no HTTP), and that `StreamShutdown` calls the port's `endStreams()`.
- Confirm `endStreams()` has no default body.
- Run the section 2 count command on the tip; compare with the `application` line.
- Check the five `EventsController` needles via Gate P.

## Implementation command

```bash
spec-kitty agent action implement WP02 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
