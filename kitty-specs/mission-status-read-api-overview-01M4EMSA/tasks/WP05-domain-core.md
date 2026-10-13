---
work_package_id: WP05
title: 'Phase 2a-1: domain core (reducer, derivations, cursors, paging)'
dependencies:
- WP04
requirement_refs:
- FR-001
- FR-002
- FR-005
- FR-012
- NFR-003
- NFR-005
- NFR-006
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/**
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP05 - Phase 2a-1: domain core

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Write the framework-free Java `domain` core (status reducer with injected ordering, the overview derivations, the two cursors, paging), each test-first, so that Java reproduces what `materialize_snapshot` and the contract rules compute, and create the JaCoCo class-count floor file with its `domain` line so `./gradlew check` is green at this WP's tip. The projection component and the ledger codec are WP17.

## Context

- Plan phase 2a, first part (plan.md sections 11 row 2a, 13 ArchUnit rule 1; data-model.md "Domain values", "Reduction", "Cursors"). Spec FR-005 (AC-5a to AC-5c), FR-001 (AC-1f supported range), FR-002 (page cursor), NFR-005, NFR-006. Sequence in lane-b: this WP, then WP17 (projection component and ledger codec), then WP06 (application layer), then WP18 (ArchUnit, port-level suite); WP07 (Python oracle) is independent and concurrent.
- **Python references to read before coding**: `src/specify_cli/status/reducer.py` (`materialize_snapshot`, cancellation/implementer projections), the installed `spec_kitty_events` 10.4.0 `status`/`diary` modules (`reduce_parsed`, `parse_diary`: read the INSTALLED source in `.venv`, not memory), `src/specify_cli/status/progress.py` (`compute_weighted_progress`), `src/specify_cli/status/tail_reader.py` (`TailCursor`, `_content_invariant_for`), `tests/contract/_mission_status_payloads.py` (`build_overview`, `Projector`, `_latest_instant`), `contracts/tools/leak_patterns.py`, `contracts/mission-status/schemas/{Project,MissionHead,MissionOverview}.yaml`.
- Domain rules: no Spring, HTTP, JSON, `java.io`, `java.nio.file`, `java.net`; only `java.lang`, `java.util` (not `java.util.concurrent`), `java.time`, `java.security` (SHA-256) and `java.nio.charset` (ArchUnit rule 1, WP18 enforces it; write to it now). The reducer ordering is a constructor argument (AC-8a perturbation).
- Coverage: JaCoCo thresholds apply to `domain.*` (line >= 90%, branch >= 80%) from this WP on. `jacocoScopeCheck` (WP03 T012 step 6) fails once a class matches a pattern whose line is absent from `src/test/resources/jacoco-class-floor.properties`; this WP creates that file with the `domain.*` line (see T026 step 5), WP17 raises it, WP06 adds the `application.*` line. Write the tests so the rule is met by this WP's own tests; do not wait for later WPs.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- Q-7: sort by `(at, event_id)` as TEXT by Unicode code point (not UTF-16 units, not parsed instants). `lastActivityAt` is compared as parsed INSTANT and served as the WP's own string; equal instants keep the first in snapshot order. These two comparisons are separate on purpose.
- Public repo: test data uses synthetic ULIDs and `<repo>` placeholders; no absolute home paths.
- Cross-WP appends: the tracer files are appended (append-only, own commit; they are in no WP's `owned_files`).

## Subtask T023: Domain values and `SupportedSchemaRange`

**Purpose**: The typed vocabulary (data-model.md "Domain values").

**Steps** (test-first: write the value-object tests, see them red, implement):
1. Package layout `domain/{model,reducer,overview,projection,cursor,paging}`. Immutable records: `MissionId` (ULID text, `mid8()` first 8), `Lane` (enum of the contract `StatusLane` values, read from `contracts/mission-status/schemas/StatusLane.yaml`; an unknown lane in a lane row is malformed input, not a default), `StatusEvent` (`eventId`, `at` as text, `wpId`, `fromLane`, `toLane`, `force`, plus exactly the cancellation-provenance members `materialize_snapshot` projects; NO logical-clock field), `LifecycleEvent` (the seven lifecycle `type` strings from the contract), `Topology`, `MissionMeta` (`missionId`, `slug`, `friendlyName`, `displayNumber`, `missionType`, `targetBranch`, `topology?`, `createdAt`, `acceptedAt`, `mergedAt`, `discardedAt`, baseline record), `Diagnostic(code, mid8, line?)` with the closed code set `ledger_unreadable, ledger_unparseable, ledger_torn_tail, meta_unparseable, mission_vanished, path_refused, mission_dir_unreadable, projection_refused`.
2. `SupportedSchemaRange` (the single constant min/max). Do NOT hard-code a guess: read `MIN_SUPPORTED_SCHEMA` and `MAX_SUPPORTED_SCHEMA` from `src/specify_cli/migration/schema_version.py` (the Python golden test in WP07 asserts the manifest equals them; WP09's Java test asserts this constant equals the manifest).
3. The ledger-line vocabulary the outbound port carries, declared HERE in `domain.model` (framework-free records and enums, no JSON, JDK types only, so ArchUnit rules 1, 2 and 12 hold for every later WP): `LedgerLine` (`lineNumber`, `rawLineSha256`, `byteLength`, `kind`), its sealed kind `Status(StatusEvent)` | `Lifecycle(LifecycleEvent)` | `Ignored` | `Blank` | `Malformed(reason)`, the `MalformedReason` enum (`not_json`, `not_object`, `not_utf8`) and the unterminated-tail classification enum (`none`, `whitespace`, `non_whitespace`). WP17's codec only PRODUCES these types and WP06's `application.port.out.LedgerRead` (with `LedgerWindow` and `LedgerStamp`, which stay in the application) only CARRIES them; neither declares them. Test them with the other value objects.
4. Results used later by WP06 (`MissionOverview`, `MissionPage`, `ProjectHeader`, `StatusSnapshot`) live in `domain/overview` and `domain/model` as plain records following the contract member names exactly (FR-002 list).

**Files**: ~25 small Java files (about 500 lines) plus tests (about 300 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.domain.model.*'`.

## Subtask T024: `StatusReducer` (port of the reduction `materialize_snapshot` runs)

**Purpose**: FR-005 / AC-5a / AC-5c.

**Steps**:
1. Red-first: build the `interleaved` shape by hand in a JUnit test (no Spring): rows with equal `at` and different `event_id`; file order different from sort order; a duplicated `event_id`; a `+02:00` offset row against a `Z` row; two rows differing only in fractional-second digit count. State the expected lanes/counts by hand-derived reasoning from the reference algorithm (dedup first-wins, sort, rollback-aware fold, annotation pass, lane counts). The goldens of WP07 later cross-check this against live Python.
2. `StatusReducer(EventOrdering)`; production ordering `AtThenEventId` compares by Unicode code point (`String.codePoints()` / `compareTo` is UTF-16: write a code-point comparator and test it with a supplementary-plane character). Steps: dedup by `event_id` (first occurrence), sort, rollback-aware fold, annotation pass separately, display lane counts. Rows `parse_diary` skips in place are skipped here with the same rule (read the installed source for the exact skip rule and cover each with a case).
3. The cancellation-provenance projection and implementer projection of `materialize_snapshot` (the wrapper part in `reducer.py`) are ported, with cases.
4. Revert-fails (AC-8a mechanism 2, unit level here; the full suite perturbation is WP09): inject a wrong `EventOrdering` (sort by `at` only, no tie-break) and require the interleaved unit test red; change the dedup to last-wins and require red; switch to UTF-16 comparison and require the supplementary-plane test red.

**Files**: `domain/reducer/*` (~400 lines), tests (~400 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.domain.reducer.*'`; no Spring on the test classpath path used (AC-5c: the test class has no Spring annotation and the test would not start a context).

## Subtask T025: `OverviewDeriver` (lifecycle status, progress, blocked count, last activity, topology)

**Purpose**: The derivations of FR-005 against `build_overview` and the contract text.

**Steps**:
1. `lifecycleStatus`: the discard rule first (contract rule 1: `discardedAt` set => `discarded`, evaluated before rule 2), then the `wpTotal` rule (unreadable/empty log => `wpTotal` 0 and `draft`), then the lane-derived values; read `MissionHead.yaml` `lifecycleStatus` description verbatim and implement each rule as its own tested branch.
2. `progress` equivalent to `compute_weighted_progress` (read `progress.py`; the weights table and rounding; one pinned rendering function used for serialisation later, see NFR-005): table-driven tests including the fractional case WP10's canonical-form test will reuse.
3. `blockedCount`, `wpTotal`, `eventCount`, `statusLaneCounts` (all lanes present, zero-filled in contract order), `lastEventId` (the id of the last event in sorted order; read what Python returns), `lastActivityAt` (maximum by parsed instant, first on ties, served as the WP's own string; invalid instants follow Python's helper `_latest_instant`), `topology` (classified when absent per FR-006 rule 3; the resolver cases are WP08/WP07, here only the pure classification given inputs).
4. Project header derivation: `ProjectHeader` from inputs (slug, version, schema version, branch name): `health` values and the null rules of FR-001 (missing metadata => `specKittyVersion` null, `schemaVersion` null, health not healthy; out-of-range => contract drift value; branch name pattern `^[A-Za-z0-9][A-Za-z0-9._/-]*$`, max 255, not a host path => else null). `missionCount` is supplied by the caller (equals the listed items).
5. Revert-fails: swap rule 1 and 2 order and the discarded case goes red; compare `lastActivityAt` as text and the interleaved instant case goes red.

**Files**: `domain/overview/*` (~350 lines), tests (~400).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.domain.overview.*'`; branch coverage of the rule ladders is part of the JaCoCo rule.

## Subtask T026: Cursors and paging

**Purpose**: `StreamCursor`, `PageCursor`, comparator (FR-002, FR-003, data-model "Cursors").

**Steps**:
1. `StreamCursor(offset, invariant)` text form `offset:invariant`; invariant = SHA-256 hex of the single most recently consumed physical line (CRLF included); the empty digest at offset 0 (`TailCursor` equivalent: read `tail_reader.py`). Parse rejects negative offsets and malformed text with typed reasons `negative`, `misaligned` (alignment is checked by the adapter), `cursor_without_mission` is application-level; keep the parse reasons that exist at the domain.
2. `PageCursor`: `v1.` + URL-safe base64 without padding of UTF-8 `<createdAt>` LF `<missionId>`, at most 512 characters; the eight invalid forms of AC-2c each produce a typed `InvalidPageCursor` (empty, not `v1.`, `v2.`, not base64, no LF, unlisted `missionId`, wrong `createdAt`, > 512 chars); a cursor from a real position round-trips.
3. Comparator `(createdAt desc, missionId asc)` and a paging function over a sorted list: `PageSize` bounds from the contract (`parameters/`), `nextPageCursor` only when more items remain, `missionCount` from the same enumeration.
4. Revert-fails: flip the comparator direction or the tie-break and the paging unit test goes red.
5. WP exit (floor file and gate): run `./gradlew jacocoTestReport`, count the classes the report holds under `org.speckitty.missionstatus.domain.*`, and create `src/test/resources/jacoco-class-floor.properties` with exactly the line `org.speckitty.missionstatus.domain.*=<that count>` (no `application.*` line yet: no class matches it). Prove `jacocoScopeCheck` bites in a scratch copy (delete the `domain` line: red; restore). Then `./gradlew check` must be green. WP17 raises the `domain` line when it adds the projection classes; the count only ever rises.

**Files**: `domain/cursor/*`, `domain/paging/*` (~250 lines), tests (~300).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.domain.cursor.*' --tests 'org.speckitty.missionstatus.domain.paging.*'`; determinism: same inputs give equal bytes (NFR-005) asserted by a test.

## Definition of Done

- Domain core (values, reducer, derivations, cursors, paging) exists, every behaviour red-first with its revert-fails mutation observed; reducer and derivation tests run with no Spring context (AC-5c).
- `cd services/mission-status-api && ./gradlew check` is GREEN at this WP's tip: the JaCoCo domain thresholds (line 90%, branch 80%) are met by this WP's own tests and `jacocoScopeCheck` passes because this WP created `jacoco-class-floor.properties` with the `domain` line (and no `application` line while no class exists there). A red `check` is not an exit state; report BLOCKED instead.
- Native legs stay green at this tip (nothing here touches the hello route).
- Nothing outside the owned trees changed; no JSON, Spring or file API in `domain`.
- Evidence recorded per subtask with `spec-kitty agent tasks mark-status <Txxx> --status done`; tracer entries appended.

## Risks

- Size: this WP is the domain core only (about 2,900 lines with tests). The projection component and the ledger codec were split into WP17 (a sequential WP in the same lane, depending on this one); do not pull them in.
- Python parity subtleties of the reducer: decided only from the installed Python source, never from memory.
- Code-point ordering versus UTF-16: the supplementary-plane test is mandatory.

## Reviewer Guidance

- Verify the sort comparator is a code-point comparison and that the two `at` comparisons stay separate.
- Verify the floor file carries the real `domain` class count from the JaCoCo report and that `check` is green without an `application` line.
- Check each revert-fails row was observed.

## Implementation command

`spec-kitty agent action implement WP05 --agent claude`
