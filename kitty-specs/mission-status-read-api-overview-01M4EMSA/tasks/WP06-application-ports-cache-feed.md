---
work_package_id: WP06
title: 'Phase 2a-3: application layer, ports, cache, change feed, in-memory source'
dependencies:
- WP17
requirement_refs:
- FR-003
- FR-004
- FR-007
- C-003
- NFR-004
- NFR-006
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T029
- T030
- T031
- T032
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/**
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/oracle/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/**
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP06 - Phase 2a-3: application layer, ports, cache, change feed, in-memory source

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Write the framework-free `application` package (the two ports, `MissionStatusService`, `ProjectionCache`, package-private `ChangeFeed`), the in-memory `MissionEventSource`, the source-neutral `FixtureSpec`, the fixture factory and the single source selector, and add the `application` line to the JaCoCo class-count floor file. The ArchUnit rule set, the port-level suite and the 2a exit gate are WP18.

## Context

- Plan phase 2a, third part (plan.md section 11 row 2a and "Parallelism and the honest dependency of 2a on 2b", section 13 ports/diagnostics/SSE bullets, data-model.md "Ports", "Results and invariants", "Stream state", "Diagnostics"). Spec FR-003 (stream table S1-S6, AC-3a..3o service-level legs), FR-004 (L-rows), FR-007 (AC-7a..7d), NFR-004 (c), NFR-006, C-003.
- Depends on WP17 (projection, codec) and through it WP05 (domain core). Concurrent with WP07 (Python oracle): the two are write-disjoint. This WP therefore CANNOT use WP07's goldens or fixtures. The ArchUnit set and the port-level suite (`portlevel-tests.txt`) are WP18, which also owns the interim-ids machinery; FR-013's id floor and the full AC-13a equality are first met at WP09's gate.
- Two seams only (operator Architecture decision): inbound `MissionStatusQuery`, outbound `MissionEventSource`. NO other named port. The diagnostics consumer is `java.util.function.Consumer<Diagnostic>`; scheduling uses an injected `ScheduledExecutorService` plus `Clock`; both are constructor arguments of `MissionStatusService` supplied by `config` (WP10). The application creates no thread (ArchUnit rule 2).
- The adapter side of `MissionEventSource` (filesystem) is WP08 (primitives) and WP19 (the source itself); the JSON side is WP10 and the stream side WP20. Here only the in-memory test source implements the outbound port.
- JaCoCo: `application.*` line >= 90% from this WP on; `jacocoScopeCheck` (WP03) requires a line for every pattern with a matching class in `src/test/resources/jacoco-class-floor.properties` (WP05 created it with the `domain` line, WP17 raised it; this WP adds the `application` line, recorded from the real report; only ever raised).
- Cross-WP appends: the tracer files are appended (append-only, own commit; they are in no WP's `owned_files`); public repo hygiene.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. The floor file is created by WP05 and only amended here. This WP creates: no file by that list.

## Subtask T029: Ports, results and the application service skeleton (red-first)

**Purpose**: The two seams and the typed contract between layers.

**Steps**:
1. `application/port/in/MissionStatusQuery`: `ProjectHeader project()`, `MissionPage missions(PageRequest)`, `ChangeBatch changesSince(StreamScope, Optional<StreamCursor>)`, `Subscription subscribe(StreamScope, Optional<StreamCursor>)`. Typed exceptions: `MissionStatusUnavailable(code, diagnostic)`, `InvalidPageCursor`, `StreamRefused(code, kind)`. `Subscription`: `StreamSignal next(Duration)` (blocking), `close()`. `StreamSignal` sealed: `Forwarded(ChangeBatch)`, `Truncated`, `Dropped(mid8)`, `Closed(closure)`, `Idle`.
2. `application/port/out/MissionEventSource`: `ProjectInputs projectInputs()`, `List<MissionRef> listMissions()` (sorted by the source, name order), `MissionMeta readMeta(MissionRef)`, `LedgerStamp stampLedger(MissionRef)`, `LedgerRead readLedger(MissionRef, LedgerStamp)`, `LedgerWindow readLedgerFrom(MissionRef, long offset)`. Faults are typed exceptions or `Unreadable` results, never `IOException`. `LedgerStamp` is opaque: value equality over (size, mtime, file key, terminated length, last-line digest); the application never interprets the fields. `LedgerRead`, `LedgerWindow` and `LedgerStamp` live in `application.port.out`; the `LedgerLine` values they carry (with `Malformed`, its reason enum and the tail classification) are `domain.model` types declared by WP05 T023 step 3, so no application class imports the codec (ArchUnit rules 2 and 12).
3. Write the first red tests (a `MissionStatusService` test with an in-memory source stub): `project()` and `missions()` happy paths. Then implement `MissionStatusService` (public; constructor takes `MissionEventSource`, `Clock`, `Consumer<Diagnostic>`, `ScheduledExecutorService`, `StreamSettings`).
4. `missions(PageRequest)`: list, read metas, stamp each ledger, serve from cache or reduce, build `MissionOverview`, page. `missionCount` from the SAME enumeration as the items. `project()`: reduces every ledger for `lastActivityAt` (cache-served), counts Missions.

**Files**: `application/**` (~500 lines), tests (~400).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.application.*'`.

## Subtask T030: `ProjectionCache` and the fail-loud mapping (FR-004 L-rows at the port)

**Purpose**: FR-007 and the typed error rows.

**Steps**:
1. `ProjectionCache` keyed by the `LedgerStamp`: an equal stamp never calls `readLedger` and never re-reduces (AC-7a, a reducer counter); a changed stamp invalidates only that Mission (AC-7b). The warm-request budget row: two `/missions` calls with no appends perform ZERO `readLedger` calls and one `stampLedger` per Mission on the second, asserted through an instrumented outbound port in tests. Revert: derive the key inside `readLedger` and the warm call reads every ledger (red).
2. Map decoded `LedgerLine.Malformed` and the tail classification: L3a/L3b (`ledger_unparseable`, 1-based line, none for non-UTF-8), L4/L4b (`ledger_torn_tail`, ANY unterminated non-whitespace tail refused so `eventCount`, `statusLaneCounts`, `lastEventId`, `streamCursor` describe one prefix of terminated lines), L1 (absent ledger => empty, `draft`/`discarded`, offset 0, no diagnostic), L2 (unreadable => 200 item, `wpTotal` 0, zero counts, diagnostic `ledger_unreadable`), L7 (`meta_unparseable`, ONE code), L6 (vanished => omitted, `mission_vanished`, `missionCount` agrees), L9 (`path_refused`, omitted), L11 (`mission_dir_unreadable`, whole read refused), plus `ProjectionError` => `projection_refused`. Whole-read rows (L3a, L3b, L4, L4b, L7, L11) throw `MissionStatusUnavailable` from BOTH `project()` and `missions()` and name no path or line text.
3. Diagnostics: exactly one `Consumer<Diagnostic>` call per occurrence, `mid8` from `meta.json` when it was read, the token `none` otherwise (L7, L9, L11).
4. Tests: one per row L1..L11 at the port leg (AC-4a); AC-4a port legs for L1, L3a, L3b, L4, L4b will be members of the port-level subset (T034).

**Files**: `application/ProjectionCache*`, mapping code, tests (~500 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.application.ProjectionCacheTest' --tests 'org.speckitty.missionstatus.application.FailLoudMappingTest'` (these are the required class names); AC-7c/7d are adapter-suite tests in WP19 (T046 step 5).

## Subtask T031: `ChangeFeed` and `subscribe` (stream rows S1-S6, overflow, diagnostics once)

**Purpose**: One shared poller fanning out to bounded per-subscriber queues (NFR-004 c), connect-time decisions made in the service.

**Steps**:
1. `ChangeFeed` (package-private): runs on the injected `ScheduledExecutorService` (500 ms poll tick: stat size/mtime first, read only appended bytes via `readLedgerFrom`; 1 s re-list of `kitty-specs/` for the unscoped discovery rule: a Mission appears with a `meta.json` and a ledger in either creation order; a directory with a ledger but never a `meta.json` yields no event and no diagnostic; a Mission present at connect delivers none of its history). Fans out through bounded queues of `StreamSettings.queueCapacity`.
2. `MissionStatusService.subscribe` decides EVERY connect-time outcome before a subscription exists: scoped S1 `StreamRefused(unknown_mission)` (no diagnostic for a plainly unknown id; `path_refused` for an L9 Mission), scoped S2 `MissionStatusUnavailable` with the row's code, unscoped S1/S2 (Mission left out, one diagnostic, `subscribe` still returns; unlistable `kitty-specs/` => `MissionStatusUnavailable(mission_dir_unreadable)`), cursor refusals (`negative`, `misaligned`, `cursor_without_mission` => 400; `out_of_range`, `content_mismatch` => 409 kinds). The service emits connect-time diagnostics ONCE; the feed never repeats them.
3. While open: S3 (ledger unreadable: scoped Closed + one `ledger_unreadable`; unscoped Dropped), S4 (bad terminated line: scoped Closed after delivering prior rows; unscoped Dropped; one `ledger_unparseable`), S5 (vanished: `mission_vanished`), S6 (`kitty-specs/` unlistable: nothing dropped, one `mission_dir_unreadable` per transition into failure, state held in the feed), `Truncated` for a shrunk log or a same-length last-line rewrite (no `id:`, re-baseline), the unterminated tail as a non-event (AC-3l), `streamCursor` wins over `Last-Event-ID` at HTTP (WP20 T054 step 2, AC-3h), batch order (AC-3i port leg) and successful resume (AC-3g port leg).
4. Overflow (E-12): a subscriber whose queue cannot take a signal is closed with `Closed(slow_consumer)`; nothing dropped or reordered before the close; no diagnostic; other subscribers unaffected. Test with capacity 2 and a subscriber that never calls `next`: three appends close it. Revert: unbounded queue or drop-oldest => red.
5. Diagnostics once: open 100 unscoped subscribers, remove one Mission: exactly ONE `mission_vanished` line (revert: log from the per-subscriber path => 100 lines, red). Connect-time: exactly one diagnostic line, by the service, not again by the feed (revert: also emit from the feed => 2, red).
6. Tests drive the feed with a deterministic scheduled executor and fixed `Clock` (no sleeps); the heartbeat interval and `Idle` after the wait are exercised via `next(Duration)`.
7. Disconnect: closing a subscription unsubscribes it from the feed after the next heartbeat write (a count of feed subscribers through a test seam).

**Files**: `application/ChangeFeed*`, `StreamSettings`, tests (~900 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.application.ChangeFeedTest' --tests 'org.speckitty.missionstatus.application.SubscribeConnectTest'` (these are the required class names; the first is in package `application` because `ChangeFeed` is package-private); reducer counter after 100 connections equals the value after one connection plus the appends' invocations (NFR-004 c at unit level).

## Subtask T032: In-memory `MissionEventSource`, `FixtureFactory`, `FixtureHandles` (testsupport)

**Purpose**: The second in-test source of FR-013 / AC-13a, built from RAW ledger lines.

**Steps**:
1. `testsupport.InMemoryMissionEventSource`: constructed from raw ledger lines (byte arrays or text; never `LedgerLine`), decoded through the production `LedgerLineDecoder` (the codec sub-package may be imported by `testsupport`, and by `testsupport` alone among tests). A test asserts by reflection that no public constructor or factory accepts a `LedgerLine` (E-13 division: bytes in, typed results out).
2. `testsupport.FixtureSpec`: the source-NEUTRAL description of a fixture that port-level classes build by hand (per Mission: `meta.json` text, raw ledger bytes, optional `lanes.json`/`.kittify` text). `testsupport.FixtureFactory`: realises a `FixtureSpec` in memory (the in-memory source above) and builds the real `MissionStatusService` over it with a fixed `Clock`, a recording `Consumer<Diagnostic>` and a deterministic scheduled executor it owns; returns only `MissionStatusQuery` (and the source it was given). The recorder and executor are reachable through a separate `testsupport.FixtureHandles`, not through the returned interfaces. (WP09 adds `FilesystemFixtureFactory`, which realises the SAME `FixtureSpec` as a temporary tree, plus `CanonicalJson` and the project-header materialisation; do not create them.)
3. `testsupport.PortSourceSelector`: the ONE place that decides which source backs a port-level class. Port-level classes (WP18) never construct a factory; they ask the selector for a `MissionStatusQuery` over a `FixtureSpec`. The default is `FixtureFactory` (in memory); the selector exposes a single package-level override (a `Supplier`-style factory slot set by a launcher) that WP09 points at `FilesystemFixtureFactory` for the second leg, so WP09 changes only `testsupport/**` and `conformance/golden/**`. Tests: the default resolves to the in-memory source; an override is honoured and is restored afterwards (no cross-test leakage).
4. WP exit: `./gradlew jacocoTestReport`, count the classes under `org.speckitty.missionstatus.application.*` and add the line `org.speckitty.missionstatus.application.*=<count>` to `jacoco-class-floor.properties` (leave the `domain` line as WP17 left it). Prove the guard in a scratch copy (delete the `application` line: `jacocoScopeCheck` red; restore). `cd services/mission-status-api && ./gradlew check` is green.

**Files**: `src/test/java/.../testsupport/*` (~450 lines), tests.
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.testsupport.*' --tests 'org.speckitty.missionstatus.application.*'` and then `./gradlew check` (step 4).

## Definition of Done

- Ports, service, cache, feed, in-memory source, factory and selector exist, each test-first with its revert-fails mutation observed red.
- `cd services/mission-status-api && ./gradlew check` is GREEN at this WP's tip: the JaCoCo rule and `jacocoScopeCheck` are satisfied with the `application` line added to the floor file (the `domain` line was raised by WP17). A red `check` is not an exit state; report BLOCKED instead.
- Native legs stay green at this tip (nothing here touches the hello route).
- No Spring, JSON, `java.io`/`java.nio.file`, thread creation or adapter import in `application` (the ArchUnit rule set that enforces this is WP18; write to it now).

## Risks

- Size: this WP is the application layer and its test source (about 2,750 lines with tests); the ArchUnit rule set, the port-level suite and the 2a exit gate were split into WP18 (sequential, depends on this WP).
- Flaky time-based stream tests: forbidden. Deterministic executor and fixed clock only; never retry-to-green.
- The `LedgerStamp` fields leaking into the application: reviewers must see `equals` only.

## Reviewer Guidance

- Check one diagnostic per occurrence under 100 subscribers and at connect time.
- Check `missionCount` and items come from the same enumeration; whole-read rows refuse both routes.
- Check the in-memory source accepts raw bytes only and the selector is the single place that picks a source.

## Implementation command

`spec-kitty agent action implement WP06 --agent claude`
