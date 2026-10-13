---
work_package_id: WP20
title: 'Phase 4a-2: SSE events controller, cross-route flow checks and real native-tagged tests'
dependencies:
- WP10
requirement_refs:
- FR-003
- FR-004
- FR-009
- FR-010
- FR-011
- FR-016
- NFR-003
- SC-003
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T054
- T085
- T058
- T059
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
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/http/**
- services/mission-status-api/src/test/resources/application-test.properties
- services/mission-status-api/src/nativeTest/**
- tests/ci/test_mission_status_api_build.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP20 - Phase 4a-2: SSE events controller, flow checks, native-tagged tests

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Add the hand-written SSE `EventsController` and its stream HTTP suites, the cross-route flow checks that need every route (canary scan, JFR runtime half, AC-16 over HTTP, virtual-thread probe), and the real `@Tag("native")` tests that replace the three skeleton ones; close phase 4a.

## Context

- Plan phase 4a, second part (plan.md sections 8, 11 row 4a, 13 (SSE, Bind, Serialisation and Jackson), ArchUnit rules 3, 5, 6, 8, 9); spec FR-003 (AC-3a..3o HTTP legs), FR-004 (HTTP legs of the stream rows), FR-009 (AC-9g, AC-9h), FR-016 (AC-16 over HTTP), NFR-003, SC-003. WP10 (first part: JSON controllers, Problem mapping, contract document, contract validation, wiring, bind guard) is the dependency; the Host/Origin filter is WP11.
- Chokepoints edited in dependency order after WP10: `application.properties`, `META-INF/native-image/**`, `tests/ci/test_mission_status_api_build.py` (append a `# --- WP20 ---` section), `testsupport/http/**` (extend, do not rewrite). `OwnPortHolder*`, `HostOriginFilter*`, `OwnPortSource*` are WP11's: DO NOT create them here. **No filter is registered in this WP**; tests send an accepted-form Host (`127.0.0.1:<bound port>`).
- **The hello route stays** (see WP10 Context): the native legs assert it until WP12 replaces the smoke test and removes it. The three skeleton `@Tag("native")` tests are replaced here (T058); the skeleton `NativeSmokeTest` is not.
- Stream rules: see `contracts/mission-status/paths/events.yaml` (repository root) and the Mission directory's `contracts/service-contract-notes.md` (`kitty-specs/mission-status-read-api-overview-01M4EMSA/contracts/service-contract-notes.md`, not the repository-root `contracts/` tree). The heartbeat key name was fixed by WP10 T057 (`Properties`).
- Public repo: no absolute paths in logs or tests. Stream suites live in test package `org.speckitty.missionstatus.adapter.in.http.stream`, flow checks in `...adapter.in.http.flow`.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. `application.properties` and the build test are created by WP03, `application-test.properties` by WP10; all three are amended here. This WP creates: test classes only (inside the owned globs).

## Subtask T054: `EventsController` (SSE) and the stream HTTP suites

**Purpose**: FR-003 HTTP legs.

**Steps**:
1. Hand-written controller. `new SseEmitter(0L)` and `spring.mvc.async.request-timeout=-1` (the container default would end an idle stream at the first heartbeat). Each connection owns one virtual thread calling `Subscription.next(30 s)`; `Idle` becomes the comment line `: heartbeat` (interval is configuration so AC-3f can shorten it; the key name was fixed and recorded by WP10 T057 in `Properties`: read it from there, do not invent a second one). `onCompletion`, `onError`, `onTimeout` call `Subscription.close()`.
2. Framing exactly per `contracts/mission-status/paths/events.yaml`: event names `status-transition`, `mission-lifecycle`, `log-truncated`; `id:` = the cursor after that row (scoped); NO `id:` for unscoped streams and for `log-truncated`; `streamCursor` wins over `Last-Event-ID` (AC-3h); refusal statuses (AC-3d, one request per code, no event sent).
3. Suites (real-socket, accepted Host, the real adapter): AC-3a (exactly one event with the right `id:` within the bound), AC-3b (annotation, unknown-type, unknown-kind rows forwarded as nothing, connection stays open), AC-3c (shrunken log => `log-truncated` without `id:`; reconnect with the old id 409 `out_of_range`; same-length last-line rewrite => 409 `content_mismatch`), AC-3e, AC-3f (shortened heartbeat), AC-3g/3i stream legs (resume from a cursor; K rows in one write), AC-3j, AC-3k, AC-3l (unterminated tail), AC-3m (appearing Mission), AC-3n, AC-3o, plus the idle stream held 35+ s with a heartbeat received (provisional, ADR `2026-10-05-2`; revert: build the emitter with the container default timeout and the test is red), disconnect (closing the client socket unsubscribes after the next heartbeat write; feed subscriber count via the test seam), overflow over HTTP (queue-capacity 2, a client that never reads, three appends: that subscriber is closed, others unaffected). All time bounds are PROVISIONAL ceilings (wall-clock note in the spec): classify a miss against the ADR method; never retry-to-green.
4. 100-connection case: AC-4c with N subscribers at the HTTP level: remove one Mission under 100 unscoped streams and require exactly ONE `mission_vanished` log line.
5. Revert-fails per spec test-strategy row AC-3: drop the `id:` line, forward annotation rows, change the heartbeat text, remove the shrink check: each red.
6. SSE event-data contract validation (FR-011, AC-11a SSE leg, SC-003; moved here from WP10 T056 by the post-analyze ruling ANL-001): reuse WP10's validator helper (do not write a second one). In the AC-3a, AC-3c (`log-truncated`) and AC-3g/3i suites, every `status-transition`, `mission-lifecycle` and `log-truncated` event actually received over the real socket has its `data:` payload parsed and validated against the matching event schema of `contracts/mission-status/paths/events.yaml`; a floor asserts at least one event of each of the three names was validated (zero validated fails). Control: a received event with ONE added unknown property fails validation (the AC-11b control applied to the SSE schemas). Revert: skip the validation call and the floor test is red.

**Files**: `adapter/in/http/EventsController*` (~250 lines), tests (~900) extending the WP10 `testsupport.http` harness where needed.
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.in.http.stream.*'`; no sleeps longer than the stated bounds; stream tests (all in test package `...adapter.in.http.stream`) use the service's heartbeat/poll configuration seams.

## Subtask T085: Cross-route flow checks (AC-9g canary scan, AC-10c runtime, AC-16 over HTTP, AC-9h)

**Purpose**: The checks that need all three routes and the stream together (they used to close the single phase 4a WP; they depend on the JSON controllers of WP10 and the SSE controller of T054).

**Steps**:
1. AC-9g canary scan: the `secret-canaries` fixture (token-, absolute-path- and email-shaped values with distinct markers in `.kittify/config.yaml`, `.kittify/metadata.yaml`, `meta.json` and event payload text): every response body and header of the three routes (SSE frames and every refusal included) and every log line of the whole flow is scanned for each canary, the fixture root and `HOME`. Projection: free-text fields are served redacted, a strict field holding a non-representable value is nulled or refused (`projection_refused` 500). Revert: serve `friendlyName` unprojected => red.
2. AC-10c runtime half (JVM leg only): a Java Flight Recorder recording around the FULL request flow (all three routes, the contract document, an SSE round trip) asserted to hold no `jdk.ProcessStart` event (the exact event name is WP02's recorded answer; if WP02 recorded it absent, STOP: that is escalation E-2, an operator-approved amendment). Positive control: a probe that starts a process in the same recording MUST appear in it. The static half is ArchUnit rule 10 (WP18); the native-leg child-process sample is WP12. AC-16 over HTTP: re-run the AC-16a (no non-read-only open), AC-16b (fixture fingerprint identical before/after) and AC-16c (drain keys on/off give byte-identical responses, no read of the personal `config.toml`) checks across the full HTTP flow, reusing WP08's `RecordingAllowlistAccess` recorder, reached through the chain WP08 (public seam) -> WP19 T046 step 0 (constructor) -> WP09 T048 step 2 (`FilesystemFixtureFactory` and `FixtureHandles`) -> the WP10 `testsupport.http` harness, which takes the recorder from the `FixtureHandles` it was started over and exposes it to the tests.
3. AC-9h: a test-profile probe records `Thread.currentThread().isVirtual()` in the handlers of `/api/v1/missions` and the SSE handler on the JVM run (the `@Tag("native")` copy is T058).

4. Pins appended to `tests/ci/test_mission_status_api_build.py` section `# --- WP20 ---` only for what this WP adds (the heartbeat key appears in the packaged `application.properties` with its documented default; the `native`-tagged real tests exist), each with a revert row.

**Files**: tests (~400 lines, test package `org.speckitty.missionstatus.adapter.in.http.flow`), pins.
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.in.http.flow.*'`; port 0 for every real-socket test.

## Subtask T058: Native-tagged tests and native hints

**Purpose**: Replace the three skeleton `@Tag("native")` tests (floor stays 3, may rise).

**Steps**:
1. Real tests in `src/nativeTest/**` (or the tag-filtered package per the WP02 wiring): the AC-9h virtual-thread probe, a Jackson-and-SSE round trip (explicit `null` members, a heartbeat, one event with its `id:`), and a classpath-resource check (`contract/openapi.yaml` readable under native). Remove the skeletons.
2. Update `META-INF/native-image/**` hints for what the SSE controller and the real tests need (WP10 already added the hints of the JSON controllers and the contract resource); the hints live with the code that needs them. They are proven on this workstation (Linux x64) by `./gradlew nativeCompile nativeTest` and `./gradlew nativeCompile nativeSmoke -PnativeBinary=<built binary>` (the hello route still answers); the other three OS legs are WP04's CI proof, and a missing hint found there returns here as a fix.
3. Update the `nativeTagFloor` expectation only upward; keep the workflow's `--floor` argument in sync is WP12's edit, record the new count in the PR notes.

**Files**: tests (~250 lines), hints.
**Validation**: `cd services/mission-status-api && ./gradlew nativeTagJvmTest` (the JVM run of the same `@Tag("native")` classes, registered by WP03 T012 step 7) and `./gradlew nativeCompile nativeTest` (executed count recorded from the JUnit XML, at least 3).

## Subtask T059: Phase 4a exit gate (JSON side in WP10, stream side here)

**Purpose**: Close phase 4a.

**Steps**:
1. `cd services/mission-status-api && ./gradlew check` green: AC-3, AC-4 HTTP legs, AC-9g, AC-9h, the WP10 results (AC-9a, AC-9e, AC-11, the accepted-Host 404 rows), ArchUnit (rules 3, 5, 6, 8, 9 now with generated/hand classes in scope), JaCoCo, `perfTest` (no perf classes yet: the task is green with zero tests because WP03 T012 step 8 applied the WP02 probe record for an empty tag-filtered `Test` task; if it is red here, that is a WP03 defect to report, not something to hedge or fix in this WP) and the native-tagged JVM run.
2. `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`; ruff clean on the file.
3. Confirm `adapter.in.http` imports nothing from `application` internals, `adapter.out` or `config` (rule 3); nothing depends on `config` (rule 6).
4. Append tracer entries (design decisions: any stream or wiring choice).

**Validation**: all green; the native legs are green at this tip on this workstation (`nativeCompile nativeTest nativeSmoke`) and the other three legs are owed to CI; the hello route and the skeleton `NativeSmokeTest` are still in place (WP12 removes them).

## Definition of Done

- The SSE controller and the stream HTTP suites pass with deterministic seams; the flow checks (canary scan, JFR runtime half with its positive control, AC-16 over HTTP, AC-9h) pass with revert rows observed; real native-tagged tests replace the three skeletons (floor 3 or higher, recorded).
- `cd services/mission-status-api && ./gradlew check` is GREEN; on this workstation (Linux x64) `./gradlew nativeCompile nativeTest` and `./gradlew nativeSmoke -PnativeBinary=<built binary>` (hello route) are green; the other three legs are WP04's CI proof.
- Python pins appended and green; no file edited outside the owned trees.
- The skeleton hello route, its tests and the skeleton `NativeSmokeTest` are still in place; AC-9b/9c/9d and `HostOriginFilter` deliberately absent (WP11).

## Risks

- The SSE suite is the long pole (about 1,800 lines with tests). All time bounds are PROVISIONAL ceilings: classify a miss against the ADR method; never retry-to-green.
- Native-only failures (PR-5): the real proof on the other legs is WP04's CI; keep the hints minimal and evidence-based.

## Reviewer Guidance

- Check the heartbeat/timeout configuration and that tests are time-bounded but deterministic.
- Check the canary scan covers SSE frames, refusals, headers and every log line.
- Check the hello route and the skeleton `NativeSmokeTest` survive this WP.

## Implementation command

`spec-kitty agent action implement WP20 --agent claude`
