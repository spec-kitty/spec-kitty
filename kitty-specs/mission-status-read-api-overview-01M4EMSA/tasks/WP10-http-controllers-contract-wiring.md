---
work_package_id: WP10
title: 'Phase 4a-1: HTTP controllers, Problem mapping, contract document, contract validation, wiring and bind guard'
dependencies:
- WP09
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-009
- FR-011
- C-001
- C-004
- NFR-003
- SC-003
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T053
- T055
- T056
- T057
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/resources/application.properties
- services/mission-status-api/src/test/resources/application-test.properties
- tests/ci/test_mission_status_api_build.py
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/**
- services/mission-status-api/src/main/resources/application.properties
- services/mission-status-api/src/main/resources/META-INF/native-image/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/skeleton/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/http/**
- services/mission-status-api/src/test/resources/application-test.properties
- tests/ci/test_mission_status_api_build.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP10 - Phase 4a-1: HTTP controllers, contract document, wiring, bind guard

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Expose the application through the HTTP adapter's JSON side: controllers for `/api/v1/project` and `/api/v1/missions` (generated interfaces or hand DTOs per the WP02 decision), `ContractDocumentController` for `/api/v1/openapi.yaml`, the Problem mapping, the `config` wiring (`ServiceWiring`, bind guard, properties incl. the heartbeat key, virtual threads, feed executor, logging diagnostics), and the contract-validation suite; replace the skeleton contract-document route. The hand-written SSE `EventsController`, the cross-route flow checks and the real `@Tag("native")` tests are WP20; the skeleton hello route is removed by WP12, not here.

## Context

- Plan phase 4a, first part (plan.md sections 8 "Status constants", 11 row 4a, 13 (Contract document, Bind, Serialisation and Jackson), ArchUnit rules 3, 5, 6, 8, 9); spec FR-001, FR-002, FR-004 (HTTP legs), FR-009 (AC-9a, AC-9e here; AC-9g and AC-9h in WP20; the Host/Origin filter itself is WP11), FR-011 (AC-11a..11d), C-001, C-004, NFR-003, SC-003. Sequence in lane-b: this WP, then WP20 (SSE, flows, native tests), then WP11 and WP12.
- Depends on WP09 (it needs the real adapter, goldens and `FilesystemFixtureFactory`). Chokepoints: `src/main/resources/application.properties`, `META-INF/native-image/**` and `tests/ci/test_mission_status_api_build.py` were created by WP03; this WP edits them in dependency order (append pins in a named section `# --- WP10 ---`). `config/MissionStatusApplication*` was created by WP03 and is amended here under `config/**` by dependency ordering (PLAN-NEW5-001): edit it minimally. `OwnPortHolder*` and `HostOriginFilter*`/`OwnPortSource*` are WP11's: DO NOT create them here.
- **No filter is registered in this WP.** Tests send an accepted-form Host (`127.0.0.1:<bound port>`), so they stay valid unchanged when WP11 lands. AC-9b/9c/9d are not in this WP's gate.
- Status and Problem rules: see the Mission directory's `contracts/service-contract-notes.md` (`kitty-specs/mission-status-read-api-overview-01M4EMSA/contracts/service-contract-notes.md`, not the repository-root `contracts/` tree). 400 `invalid_page_cursor`; stream 400 (`negative`, `misaligned`, `cursor_without_mission`), 409 (`out_of_range`, `content_mismatch`), 404 unknown Mission; 500 for whole-read rows L3a/L3b/L4/L4b/L7/L11 and `projection_refused`, with a path-free, line-text-free body. Every non-2xx body is the shared Problem (`contracts/_shared/responses/Problem.yaml`).
- Production mapper (WP02 R-2/E-8 result): configured explicitly, not left at Boot defaults: no pretty printing, null members written, canonical key order, non-ASCII as UTF-8, `progress` rendered by ONE pinned function. If the WP02 record shows the mapper cannot emit canonical bytes, STOP and report (E-8 is an operator ruling).
- No springdoc anywhere (E-11): `/v3/api-docs*` and `/swagger-ui*` answer 404 after the filter (with an accepted Host here; 403 with a foreign Host is WP11).
- **The hello route stays.** The four native legs' `nativeSmoke` (WP03/WP04) asserts `GET /api/v1/hello` until WP12 replaces that smoke test; deleting the hello controller or the skeleton `NativeSmokeTest` here would turn every native leg and the terminal gate red between this WP and WP12. Only the skeleton contract-document route and its test are replaced here (T055).
- Shared test harness: this WP creates `testsupport.http` (a real-socket server harness on port 0 over `FilesystemFixtureFactory`, and a raw-socket client that sends literal request bytes; it takes the optional `RecordingAllowlistAccess` from the `FixtureHandles` of the `FilesystemFixtureFactory` it starts over and exposes it, which WP20 T085 step 2 needs) and WP11 reuses it. `testsupport/**` itself belongs to WP06/WP09 (earlier, same lane); only the `http` sub-package is added here.
- Public repo: no absolute paths in logs or tests.
- Test packages (so every validation line names a package): REST and Problem suites in `org.speckitty.missionstatus.adapter.in.http.rest`, contract-document suites in `...adapter.in.http.contractdoc`, contract-validation suites in `...adapter.in.http.contract`, wiring and bind-guard suites in `org.speckitty.missionstatus.config`; WP20 adds `...adapter.in.http.stream`.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. `application.properties` and `tests/ci/test_mission_status_api_build.py` are created by WP03 and amended here. This WP creates: `application-test.properties`.

## Subtask T053: Problem mapping and the generated-interface (or DTO) controllers

**Purpose**: `/project` and `/missions` over the inbound port.

**Steps** (acceptance test first: AC-1a..1e, AC-2a, AC-2c HTTP, AC-4a HTTP legs):
1. Controllers depend ONLY on `MissionStatusQuery` (ArchUnit rule 3). Generated mode: implement the generated `ProjectApi`/`MissionsApi` interfaces from `adapter.in.http.api`, models from `...http.model`. Hand mode: DTO records in `adapter.in.http.dto` mirroring `Project`, `MissionOverview`, `MissionOverviewPage`, Problem, plus the drift test of AC-11c (T056).
2. `ProblemMapper`: `MissionStatusUnavailable` => 500 Problem (`application/problem+json`, `code` = the diagnostic code, no path, no line text, no OS message); `InvalidPageCursor` => 400 `invalid_page_cursor`; `StreamRefused` => 404/400/409 per kind. A `ProjectionError` is already `MissionStatusUnavailable(projection_refused)` at the port. Any unexpected exception => 500 Problem with a generic code and one diagnostic-free log line carrying no path.
3. HTTP legs of the port rows: for each L1..L11 row assert status, Problem presence, listed body members, diagnostic code (L3a through `/project`, L3b through `/missions`, each its own 500). `GET /api/v1/missions` honours `pageSize`/`pageCursor` per the contract; AC-2c: the eight forged cursor values return 400 `invalid_page_cursor`; a control cursor from a real `nextPageCursor` returns 200 with the next page.
4. AC-1d scan: the body contains no fixture root path, `HOME`, or secret-canary.
5. Revert-fails: return 200 for L3/L4/L4b => AC-4a red; omit the Problem `code` => red.
6. AC-1b (named test): request `/api/v1/project` over the project-header fixture with `.kittify/metadata.yaml` deleted; assert status 200, `schemaVersion` null and `health` other than `healthy`. Revert: make the service answer 500 or `healthy` for the absent file => red.
7. AC-1c (named test): over a fixture with several pages (page size 1), request `/api/v1/project` and drain `/api/v1/missions` across ALL pages; assert `missionCount` equals the total number of items. Revert: count only the first page => red.
8. Out-of-scope operations (WP02 T005 criterion 8): `GET /api/v1/missions/{id}`, both work-package paths and both artifact paths answer 404 exactly like any unknown path (accepted Host), not 501 and not a Problem produced by a stub. Revert: implement the generated interface with default methods in a test branch => 501 => red.
9. AC-4d HTTP leg (the free-running and latch parts over the JSON route; WP19 T046 step 4 owns the adapter leg against the port-level API): in test package `org.speckitty.missionstatus.adapter.in.http.rest`, start the `testsupport.http` server on port 0 over `FilesystemFixtureFactory`. (a) Free-running: a writer thread appends valid status rows to the ledger of one fixture Mission while a reader issues at least 200 `GET /api/v1/missions` calls; every 200 body's item for that Mission has `eventCount`, `statusLaneCounts`, `lastEventId` AND `streamCursor` that ALL equal the tuple of ONE single prefix of complete lines of the FINAL log (the test computes the expected tuple for every prefix from the final log; a response whose counts come from one prefix and whose cursor from another fails), and every non-200 is the L4/L4b Problem (never a half-read prefix, never a 500 with another code). (b) Latch: with a latch-controlled writer, as SEPARATE reads: half a row => assert a 500 `ledger_torn_tail` Problem (L4); the whole row without its newline => assert the 500 Problem of L4b; the newline lands => assert the 200 item equals the four-field tuple of the NEW prefix. The test asserts that both the L4 stage and the L4b stage were observed as separate reads (a latch phase that does not observe both refusals is vacuous and fails). Revert rows: (i) make the port serve the prefix before a half-written trailing row (in a test branch of the adapter) => the prefix assertion or the 500 assertion goes red; (ii) take `statusLaneCounts` from the previous cache entry while the cursor advances => the four-field prefix assertion goes red. Name the class `TornTailConcurrencyHttpTest` and include it in the Validation line below.

**Files**: `adapter/in/http/**` (~600 lines), tests (~800).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.in.http.rest.*'` (includes `TornTailConcurrencyHttpTest`, the AC-4d HTTP leg of step 9; every test class of T053, including the named AC-1b and AC-1c tests, lives in that package so the filter selects it).

## Subtask T055: `ContractDocumentController`, springdoc absence, AC-11d

**Purpose**: Contract-first document at `GET /api/v1/openapi.yaml` (E-11).

**Steps**:
1. Delete ONLY the phase 1 skeleton contract-document route and its test (`SkeletonContractDocumentController` under `adapter/in/http/skeleton/` and `SkeletonContractDocumentTest` under `src/test/.../skeleton/`); leave the hello controller, its package and the skeleton `NativeSmokeTest` alone (WP12 removes them together, see Context). `ContractDocumentController` answers 200 from the classpath resource `contract/openapi.yaml` (the build output of `bundleContract`) with the bytes UNCHANGED, `Content-Type` an OpenAPI YAML type; it is a classpath read, not a project-root read, so the FR-010 allowlist is unchanged.
2. AC-11d test: the bytes served equal the bundle the contract tooling writes for the same commit (the procedure WP02 recorded: run the bundler into a temp dir outside the repo, compare bytes); 404 for the route, a document generated from controllers, or a hand-copied stale copy is red. Revert rows: change one byte of the served resource; hand-copy a stale document.
3. 404 rows with an accepted Host: `/v3/api-docs`, `/v3/api-docs.yaml`, `/swagger-ui.html`, `/swagger-ui/index.html` answer 404 AFTER the (future) filter. Revert: register a handler that answers 200 on `/v3/api-docs` in a test branch and the 404 row goes red. (The foreign-Host 403 variants are WP11.)
4. `grep`-level guard that no `springdoc` dependency or property exists is already pinned by WP03; extend with a resolved-configuration check if Gradle is available in the test.

**Files**: `ContractDocumentController*` (~80 lines), tests (~200).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.in.http.contractdoc.*'`.

## Subtask T056: Contract validation (AC-11a..11c) with the networknt validator

**Purpose**: Every real response validates against the contract; the generated types track the contract.

**Steps**:
1. Schemas extracted from the contract bundle; validator networknt (JSON Schema 2020-12; honours `unevaluatedProperties` and `type: [string, 'null']`). AC-11a, JSON routes only: all fixture responses of `/project` and `/missions` (incl. the 400) validate. The SSE controller does not exist until WP20, so the validation of each SSE event's data is NOT claimed here (post-analyze ruling ANL-001); build the validator as a reusable helper class in the test package `adapter.in.http.contract` (a package both WP10 and WP20 own; schema extraction from the bundle plus a `validateEventData(eventName, jsonText)` entry point over the three event data schemas, unit-tested here against hand-written valid and invalid sample documents) so that WP20 T054 step 6 reuses it. AC-11b: a response with ONE added unknown property fails (control that the validator really honours `unevaluatedProperties`). Revert: remove the control assertion and the build test of WP03/WP10 flags it.
2. AC-11c (generated mode): a build-time test copies the contract root to a temp directory, renames one property of `MissionOverview` (and separately removes one required property of `Project`), runs the generate-and-compile step on the copy through the mechanism WP02 T004 step 10 proved and WP03 declared (Gradle TestKit `GradleRunner` over a copy of the project, or the generator invoked as a library; a Python subprocess is used only by the AC-11d bundler comparison) and requires failure; a positive control on an unmutated copy succeeds. Hand mode: the drift test (a property of `Project`, `MissionOverview`, `MissionOverviewPage` or Problem with no DTO member, and the reverse, fails; a property added to a temp contract copy turns it red). The test asserts which mode the build is in.
3. Jackson contract: a required-nullable member is emitted as explicit `null`; member order equals the golden; revert: switch the mapper to omit nulls and it is red. NFR-005 pin: the production mapper's output for one non-ASCII string and one fractional `progress` value equals the Python-written golden bytes (use WP09's `CanonicalJson` for comparison only).

**Files**: tests (~500 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.in.http.contract.*'`.

## Subtask T057: `config` wiring, bind guard, properties (AC-9a, AC-9e)

**Purpose**: Composition root and the loopback-only bind.

**Steps**:
1. `ServiceWiring` is the ONE class that constructs `FilesystemMissionEventSource`, `ProjectionCache` and `MissionStatusService` and reads `leak-patterns.json` from the classpath into the leak-class value (compiles with `java.util.regex`). `FeedExecutorConfig` (the scheduled executor), `LoggingDiagnostics` (writes one path-free line: stable code, `mid8`; never a path, line text or OS message), `VirtualThreads`, `Properties` (`mission-status.project-root` required; `mission-status.port` default 8787, 0 = ephemeral; `mission-status.stream.queue-capacity` 1024; the heartbeat key, whose name is fixed and recorded HERE and consumed by WP20's `EventsController`), `NativeHints`.
2. `BindGuard` runs before the web server starts, reads the EFFECTIVE `server.address`: anything other than the literal `127.0.0.1` exits non-zero naming the address; absent or blank exits non-zero naming "unset"; after the server starts a `WebServerInitializedEvent` listener checks the address the connector actually bound (accessor per WP02 Unverified 19) and exits non-zero if not loopback. A port in use exits non-zero naming the port. Nothing in `config` calls a file API (ArchUnit rule 7); the directory check is `ProjectRootCheck`.
3. AC-9a table: configured `0.0.0.0`, `::`, a LAN address, a hostname, a blank `server.address`, and the property ABSENT (the packaged default removed through the test override), each exiting non-zero within the provisional 10 s bound and naming the address, and, for EACH of those non-loopback bind rows, a TCP connect to that address and the configured port is refused (nothing is listening, because the guard exits before or at the start of the connector; AC-9a requires the refused connect per row, ANL-010); with shipped defaults the bound address read back equals `127.0.0.1` and a connect to a non-loopback local address is refused. Revert: make the guard treat unset as a pass and the unset row is red. AC-9e: port already in use => non-zero, message names the port.
4. Config tests: `server.forward-headers-strategy=none`, no `ForwardedHeaderFilter` bean and no `server.tomcat.remoteip.*` property (asserts all three; WP11's filter additionally refuses forwarded headers). Pins appended to `tests/ci/test_mission_status_api_build.py` section `# --- WP10 ---`: the packaged `application.properties` defaults (parsed), no `springdoc.*` key, generated-package names (or hand mode), jar name; each with a revert row. One further pin ties WP18 T033 step 4 to the build: it parses `ArchitectureRulesTest` for the three rule-9 package literals (`adapter.in.http.api`, `adapter.in.http.model`, `adapter.in.http.dto`) and asserts that the package(s) populated under `src/main/java/.../adapter/in/http` and named by the build match the mode recorded by T016 (hand mode: `dto` is the populated package and its literal is present; generated mode: the `apiPackage`/`modelPackage` values equal the `api` and `model` literals). Revert row: drop the `dto` literal from a temporary copy of the ArchUnit test, read by the pin => red.
5. Native hints for what this WP added: `META-INF/native-image/**` gains the reflection/resource entries the new classes need (Problem and the chosen DTO/model mode, the `contract/openapi.yaml` resource-config), written with the code that needs them. Run `./gradlew nativeCompile` and `./gradlew nativeSmoke -PnativeBinary=<built binary>` locally (Linux x64): the hello route still answers (the AOT/context must start with the new beans). A hint gap on another OS leg returns here from WP04's CI.

**Files**: `config/**` (~450 lines), `application.properties` edits, tests (~300, in test package `org.speckitty.missionstatus.config`).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.config.*'` and `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`; port 0 for every real-socket test.

## Definition of Done

- The two JSON routes and the contract document serve the committed goldens' documents with canonical bytes; every refusal row has its HTTP-leg test, including the named AC-1b and AC-1c tests, the AC-4d HTTP leg (`TornTailConcurrencyHttpTest`: at least 200 GETs during appends, both latch stages, revert row observed) and the 404 rows of the five out-of-scope operations; no springdoc anywhere.
- Bind guard rows (AC-9a, AC-9e) and the config tests pass with revert rows observed; the skeleton CONTRACT-DOCUMENT route and its test are deleted, and the hello route, its tests and the skeleton `NativeSmokeTest` are still in place.
- `cd services/mission-status-api && ./gradlew check` is GREEN, and the native legs are green at this tip: `./gradlew nativeCompile nativeTest` and `./gradlew nativeSmoke -PnativeBinary=<built binary>` (hello route) are green on this workstation (Linux x64), and the hints for every class added here are in `META-INF/native-image/**`. The other three OS legs are WP04's CI proof; a missing hint found there returns here as a fix.
- Python pins appended and green; no file edited outside the owned trees (the shared `application.properties`/hints/pins edited in dependency order).
- AC-9b/9c/9d and `HostOriginFilter` deliberately absent (WP11); the SSE controller, the cross-route flow checks and the real native-tagged tests are WP20.

## Risks

- The wiring changes the application context of the skeleton: the hello route must keep answering with the packaged defaults and a plain project root (the `nativeSmoke` skeleton launches it that way); check it explicitly before closing.
- Native-only failures (PR-5): the real proof on the other legs is WP04's CI; keep the hints minimal and evidence-based.
- Canonical-bytes mismatch between mapper and goldens: stop and escalate as E-8, never canonicalise-before-compare.
- Size: about 2,800 lines with tests; the SSE half is WP20.

## Reviewer Guidance

- Check the controller depends only on `MissionStatusQuery` and the mapping never leaks path, line text or OS messages.
- Check AC-11b really bites, and the AC-11d bytes test cannot pass with a stale copy.
- Check the hello route and the skeleton `NativeSmokeTest` survive this WP and the native legs are green at its tip.

## Implementation command

`spec-kitty agent action implement WP10 --agent claude`
