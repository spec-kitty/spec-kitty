---
work_package_id: WP13
title: '[PR B] P9 getMission (FR-001)'
dependencies:
- WP06
- WP05
- WP11
- WP10
- WP12
requirement_refs:
- FR-001
- FR-008
- FR-012
- NFR-003
- NFR-004
- SC-004
- C-003
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T08:16:43.430171+00:00'
subtasks:
- T090
- T091
- T092
- T093
- T094
- T095
- T096
- T097
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionDetailQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/PhaseDeriver.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/ReadinessDeriver.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/MissionDetailController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/MissionDetailMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/MissionDetailWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/MissionDetailServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/portlegs/MissionDetailPortLegsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/MissionDetailServedRouteTest.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionDetailQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/PhaseDeriver.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/ReadinessDeriver.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/MissionDetailController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/MissionDetailMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/MissionDetailWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/MissionDetailWiring*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/MissionDetail*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/PhaseDeriver*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/ReadinessDeriver*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/detail/MissionDetail*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/MissionDetailServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/rest/OutOfScopeRoutesTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/portlegs/MissionDetailPortLegsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/MissionDetailServedRouteTest.java
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP13 – [PR B] P9 getMission (FR-001)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request: B (a draft), plan phase P9.** PR B = WP13 to WP18 (phases P9 to P13). It stacks on PR A (WP01 to WP12) and cannot merge before PR A. PR A stacks on the branch that carries #5529's last slice. No agent pushes, opens or retargets a pull request; publishing any ref is an operator act.
- **External dependency (not a `dependencies` entry).** WP01 could not start before the orchestrator merged the re-cut tip of #5529 (the side-first layout) into this branch; every path of this prompt assumes that merge (plan section 1.1, C-005). #957 cannot merge before #5529 (C-005). #5533's Java work stacks on PR A, never on PR B.
- **Work package dependencies.** WP06 (P2: contract models, drift probe, build spike), WP05 (P3: resolved Work Package state, `WpId`, `HistoryOrder`), WP11 (P6: decoders and the Work Package index), WP10 (P7: Java harness, `HttpHarness#startWith`, `MetaReadCounter`, `ServedRoute`, `DetailGoldenSuiteTest`), WP12 (P8: the four inbound interfaces, `DetailRefusal`, the 21 read-model records, `MissionId.parse`, `AdmissionGate`, rules 15 and 16, Problem mapping, shared wiring). WP12 owns the eight records of this route and ships them complete from the contract schemas (no routine edit; see the records bullet).
- **Write scope: `owned_files` only** (frontmatter). One owner per file (ledger SK-357): any other writer of a shared file is a named edit.
- **Named edits (out-of-map; not in `owned_files`).** For each: rebase first, state the edit in the commit message, touch nothing else of the file.
  - `J/domain/readmodel/detail/{MissionDetail,MissionPhase,PhaseName,PhaseStatus,PhaseBasis,WorkPackageSummary,Readiness,SubtaskProgress}.java`: the eight records of this route; WP12 owns them, this work package may reshape only these eight, only where the route needs it. The shapes are final from the contract schemas (WP12 T082): the default is **no edit**. Edit a record only when this route's schema or golden proves a member missing or wrong; that is a named edit of WP12's file (accepted risk under the plan section 11 shared-file table, TASKS-DECOMP-003): rebase first, one record per commit, schema evidence in the commit message.
  - `R/jacoco-class-floor.properties` (two count lines; WP01 owns it; merge rule D-145). This work package appends **nothing** to `R/portlevel-tests.txt` (WP05's file): the port-level legs live outside `conformance.port` and are not listed (TASKS-GREEN-001; see the port-level subtask).
  - none in `M/**` (interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`; the orchestrator keeps the tracer and status appends locally).
- **Concurrency.** WP16 (P12) has no dependency on this work package and may run beside it with a disjoint write scope. WP14 and WP15 start after this work package. The shared files serialise by merge order: the later lane rebases and re-reads `OutOfScopeRoutesTest.java`, and recounts JaCoCo on the merged tree. **Merge order WP13 -> WP14 -> WP15 -> WP16** for the shared files `OutOfScopeRoutesTest.java` and `R/jacoco-class-floor.properties`: the orchestrator merges in that order and each later lane rebases onto the merged tree. Neither file has a git merge driver, so a conflict is real and is resolved by rule: in `OutOfScopeRoutesTest.java` keep the **intersection** of the remaining paths (a path removed by any lane stays removed); in the properties file take neither side, re-run the section 2 command on the merged tree and write what it prints. Nothing is claimed to merge silently.

Aliases used in this prompt (plan section 11, expanded to repo-relative paths): `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`.

Every layout path below is the **side-first layout of #5529's re-cut** (plan section 1.1, mapping table rows 1 to 13). The re-cut classes (`application/query/MissionStatusQueryService`, `application/query/ProjectionCache`, `application/query/port/in/**`, `application/query/port/out/**`, `domain/readmodel/**`, `domain/redaction/**`, the test mirror paths) **exist after the re-cut**, not in a checkout that lacks it. If a cited path is missing on your tree, the orchestrator has not merged the re-cut: STOP and report; never create the path, never "fix" it by using the flat checkout names. Paths of other work packages' classes (WP05 to WP12) exist after those work packages are on this branch; the work package list in the dependencies block says which.

---

## Objective

Serve `GET /api/v1/missions/{missionId}` (`getMission`, FR-001) from the Java service: the `MissionDetail` body made of the unchanged Mission head, the five derived `phases` and the `workPackages` summaries, byte-identical to the Python oracle's golden for every fixture, with the exact `meta.json` read counts of AC-1.8 and the fail-loud rows of FR-012 that apply to this route. This is the first route of PR B: after it `getMission` answers 200 where `OutOfScopeRoutesTest` used to assert 404.

## Context

- **One head, one cache (D-93, FRESH2-003).** The head is produced by `MissionReadModel#head(ref)`, which returns `MissionHead(overview, entry)` from a single pass (`readMeta`, the ledger stamp and, on a miss, the ledger read). This route never derives a head itself, never calls `probed()`, `stampLedger`, `readLedger` or `OverviewReader#ledger(ref, mid8)`. The per-Work-Package snapshot (resolved map, `lifecycleTypes`, lane per Work Package) is read from `MissionHead#entry`. `MissionDetailQueryService` lives directly in `application.query` (public, beside the package-private `ProjectionCache`) because a sub-package would force a public cache (plan section 1.1, placement rule).
- **Call sequence fixed by D-104 (plan section 8, FRESH3-002):** `MissionLookup#find(id)` (probe-free lookup), then the duplicate continuation (reads only the Missions that sort after the match; one `mission_id_duplicate` diagnostic when a second readable directory holds the id), then `MissionReadModel#head(ref)`. Nothing else. The matched Mission's `meta.json` is read **3 times on a warm ledger cache, 4 on a cold one**; every other Mission exactly once per request; the stream route (`resolve`, which does probe) reads the matched Mission twice before the feed starts (the control that makes the difference visible).
- **Identifiers are typed (E-5, D-150).** The controller calls `MissionId.parse(String)` (WP12, `Optional<MissionId>`, never throws) and turns an empty result into `DetailRefusal.notFound()`; `ProblemMapper` holds the one kind-to-status mapping (404). A `mid8`, a slug, a display number, a lowercase ULID, a 25-character and a 27-character id all parse empty: 404, never 400 (rows C2, AC-1.5). The port signature `MissionDetailQuery#mission(MissionId)` carries no raw `String` (rule 16 clause c).
- **Redaction placement.** Controllers and mappers may not depend on `domain.redaction` or `domain.readmodel.derive` (rule 15). Projection of strict and human fields (`Projector.strict`, `Projector.human`) happens in the application layer, in the same place the overview item projects its head; the mapper only shapes JSON from the typed records.
- **Phases.** Exactly five entries in the order specify, plan, tasks, implement, review. Specify, plan, tasks: `complete`/`artifact` when `spec.md`, `plan.md` or `tasks.md` is a regular non-symlink file in the Mission's **primary** directory (a `lstat`, never the coordination read directory, SK-310); else `complete`/`lifecycle_event` when the matching Completed event is in the ledger; else `in_progress`/`lifecycle_event` when the Started event is; else `pending`/`artifact`. Implement and review come from `statusLaneCounts` and `wpTotal` alone (`derive_phase_status`; neither reads the other). A planning file that is a symbolic link is not an artifact: the phase falls through to the lifecycle events and one `path_refused` diagnostic is written (a recorded, stricter divergence from the oracle). A stat that fails for a reason other than "absent" is 500 `source_unreadable` (row M8, a recorded divergence).
- **Red-first form: red on the phase base.** On PR A's tip the route does not exist: `getMission` answers 404 and none of the route's classes exist.
- **Charter rules in force.** Squad after every plan phase belongs to the orchestrator, not to this work package. Gate discipline: every new test is non-vacuous (a named discovered-count floor, a planted control). No retry-to-green: a red is classified under plan section 6.

---

### Subtask T090: Pre-flight, red-first tests and fixtures registration

**Purpose**: Run the C-005 pre-flight, then write the route's tests before any production class so that every one of them is red on the phase base for the reason it exists.

**Steps**:

1. Run the pre-flight (the whole block, in order). Record the #5529 tip sha in the first commit message of this work package.

```bash
# Environment. <scratch> is a directory OUTSIDE the repository (bundle.py refuses one inside).
export LC_ALL=C.UTF-8          # a UTF-8 file-name locale is a precondition of Gate G (plan section 5, D-128)
.venv/bin/python contracts/tools/bundle.py --root contracts --out "<scratch>/bundle-out" --module mission-status --bundle-only
export CONTRACT_BUNDLE="<scratch>/bundle-out/bundle/mission-status/openapi.yaml"
export CONTRACT_BUNDLE_SHA256="$(sha256sum "$CONTRACT_BUNDLE" | cut -d' ' -f1)"

# C-005 pre-flight, first step of the phase (plan section 1.1 steps 2 and 3, section 5)
cd services/mission-status-api
./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'
cd ../..
git log -1 --format=%H <the ref that carries the #5529 re-cut tip merged by the orchestrator>   # record this sha in the first commit message of this work package
grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' services/mission-status-api/src/test services/mission-status-api/build.gradle.kts
grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github      # must be empty from the end of WP01
```

`CoupledSymbolsShapeTest` is green on the re-cut layout and red on the flat checkout by design. Red on your tree means the re-cut tip is not merged, or a #5529 symbol changed shape: **stop and report to the orchestrator** (plan section 1.1 step 4: the mapping table is amended by a decision note, never by a work package). Every hit of the first grep must name a class of the right-hand column of the mapping table or one of the two JaCoCo wildcards.

2. Create the red tests (all new files; names fit the `owned_files` patterns):
   - `T/application/query/MissionDetailMetaReadCountTest.java`. Uses WP10's `MetaReadCounter` (instrumented port; counts `MISSION_META` READ per Mission, per route, warm and cold, first-sorted and last-sorted requested Mission). It runs **on the real `MissionDetailQueryService` over `MissionReadModel`** (not only on the extracted `/missions` path). Asserts: the matched Mission 3 reads warm and 4 cold; every other Mission exactly 1 read; the same totals when the requested Mission is the last in name order; the stream-route control (a `resolve` call records two reads of the matched Mission before the feed starts); a **discovered-row floor** so an empty class fails.
   - `T/domain/readmodel/derive/PhaseDeriverMatrixTest.java`: the table test of AC-1.3 over the 19 fixtures of class `phases-matrix` (WP07 Count 19, plan section 14 S-20; `marker-row-without-event-id` is the D-98 marker row: it feeds `lifecycleTypes`, not a planning-phase cell, and the test iterates the manifest listing, not a literal 18) (R: `R/conformance/phases-matrix/**`, generated by WP07).
   - `T/domain/readmodel/derive/PhaseDeriverTest.java` and `ReadinessDeriverTest.java`: the unit tests of T092 (written now, red now).
   - `T/adapter/in/http/detail/MissionDetailRowsTest.java`: one fixture and one assertion per row of FR-012 that applies to `getMission` (C1 to C7, M1 to M3, M4a, M5 to M8, M10, M13, M14; M13 is served by the `NameEncoding` stub leg, M14 by the `projection-nulls` fixture `head-dates-nulled`) at the HTTP leg, and at the port (typed result or `MissionStatusUnavailable` carrying the diagnostic code). Rows M2 and M5 assert the 200 **and** the diagnostic together (a body alone cannot tell M1 from M2). Includes the per-route fixture of **row C2 proving 404, never 400** (a `mid8`, a slug, a display number, a lowercase ULID, 25 and 27 characters).
   - `T/conformance/golden/served/MissionDetailServedRoute.java`: the `ServedRoute` provider (WP10 T071 step 1 defines the interface) serving every manifest fixture that holds `get-mission.json` (T094).
3. The red commit must compile. Add only empty shells of the production classes that make the tests link (`MissionDetailQueryService`, `PhaseDeriver`, `ReadinessDeriver`, controller, mapper, wiring) with bodies that throw `UnsupportedOperationException`, so each test fails by assertion and not by a compile error. Do not add behaviour in this commit.
4. Prove "red on the phase base": in a scratch worktree of PR A's tip (`git worktree add <scratch>/base <PR A tip sha>`), copy only the new test files in and run the classes; they must fail there. Never prove red by reverting inside the working tree under review; never use `git stash`; never run tests under `git rebase -x`.

**Files**: 5 new test files plus the shells (~400 lines of tests at this point).

**Validation**: each new test class is red on the base for its stated reason; `CoupledSymbolsShapeTest` green on the tip; the first grep of the pre-flight is clean.

---

### Subtask T091: `MissionDetailQueryService`

**Purpose**: Implement `MissionDetailQuery#mission(MissionId)` over the lookup, the one head and the shared Work Package index, with no second head derivation.

**Steps**:

1. Create `J/application/query/MissionDetailQueryService.java`: `public final class MissionDetailQueryService implements MissionDetailQuery` (port from `J/application/query/port/in/`, WP12). It is constructed only by `MissionDetailWiring` (T093), which is in `config`; hence public. Constructor arguments are the collaborators the plan names and nothing else: the `MissionReadModel` (lookup and head, the one `ProjectionCache`), the `WorkPackageIndex` bean (class of WP11, bean declared in this WP's `MissionDetailWiring`), the `TextSource` of WP09 (planning-file `lstat`), and the diagnostics `java.util.function.Consumer<Diagnostic>` handed in by `config`. Read the signatures on the tips of WP11 and WP12; do not invent any.
2. Sequence per request, exactly: `MissionLookup#find(missionId)` (empty becomes `DetailRefusal.notFound()`; the lookup rules D-39 hold: a readable Mission that holds the id wins over any faulted sibling; with no match the first fault in byte order decides: C3 404 plus `path_refused`, C4 500 `meta_unparseable`, C5 500 `mission_dir_unreadable`); the duplicate continuation (C6: serve the first in byte order, write one `mission_id_duplicate`, ignore the faults of later siblings: C7 / AC-1.5 `duplicate-then-broken`); `MissionReadModel#head(ref)`. **No** `probed()`, `stampLedger`, `readLedger` or `OverviewReader#ledger`.
3. Rows M1 to M3 are decided inside `head` (absent ledger: 200 `draft`/`discarded` head; unreadable ledger: 200 as the overview item plus `ledger_unreadable`; undecodable or torn tail: 500 `ledger_unparseable` / `ledger_torn_tail`). Do not re-decide them; map `MissionStatusUnavailable` (carrying the diagnostic code) unchanged (DC-2 option A).
4. Build the Work Package list from the index: one `WorkPackageSummary` per Work Package **file** of the shared index, ordered by `wpId` ascending compared as plain strings (not collation, not numeric). Call the index builder with `Optional.empty()` for the body to capture (this route never holds a body, NFR-002). A Work Package with a file and no events: `statusLane` null, absent from `wpTotal` and `statusLaneCounts` (those come from the head). A Work Package with events and no file: **not listed** while it still counts in `wpTotal`; one fixture asserts both facts side by side (AC-1.4).
5. Summary members: `title` and `phaseLabel` are human text projected by `Projector.human` (FR-008 class 3: a credential or an unremovable leak is row M7, 500 `projection_refused`); `dependencies` are the authored ids (strict, `WpId` pattern: row T5); `readiness` and `readyToStart` from `ReadinessDeriver` (T092) over the snapshot lanes and provenance; `subtaskProgress` counts the resolved subtask map of the snapshot; `lastTransitionAt` is the snapshot's (a non-instant there is already the whole-head M3 failure, T10).
6. Index outcomes map as the table says: M4a (`tasks/` unlistable, a Work Package file unreadable or over 1 MiB) 500 `source_unreadable`; M5 skipped file 200 plus `wp_file_skipped`; M6 duplicate id the first file served plus `wp_id_duplicate`; M10 `tasks/` not a real directory 500, absent `tasks/` an empty index and 200. These are produced by WP11's index; this service only propagates them.
7. This service does **not** hold the `AdmissionGate` (`getMission` is not one of the heavy operations, plan section 13).

**Files**: `J/application/query/MissionDetailQueryService.java` (new, ~220 lines); named edits to the eight records of T092 as needed.

**Validation**: `MissionDetailMetaReadCountTest` and `MissionDetailRowsTest` rows C1 to C7 and M1 to M3 green; AC-1.2 (the body without `phases` and `workPackages` equals the `/missions` item byte for byte) green in T094.

---

### Subtask T092: `PhaseDeriver`, `ReadinessDeriver` and the eight records

**Purpose**: The two framework-free derivations of the route and the shape of its records.

**Steps**:

1. `J/domain/readmodel/derive/PhaseDeriver.java` (package `domain.readmodel.derive`; only `java.lang`, `java.util` except `concurrent`, `java.time`; no file API: rules 1b and 7). Inputs: the five lane counts and `wpTotal`, the set of present planning artifacts (what the service found by `lstat` of `spec.md`, `plan.md`, `tasks.md`), and `StatusSnapshot.lifecycleTypes()`. Output: five `MissionPhase` records in the fixed order. Inside a planning phase the checks run in the order **file, Completed event, Started event, pending**: a file plus a Completed event says basis `artifact`; a Completed plus a Started event says `complete`. Implement and review use `derive_phase_status`'s rules on the counts alone: an empty Mission is `pending` for both; an all-`canceled` Mission is `complete` for both.
2. The `lstat` is made in the service (T091) through `TextSource#stat(FileRef.MissionFile, ReadScope.AUTHORED)` on the **primary** directory; `EntryStat.Present(kind=SYMLINK|...)` is a link: not an artifact, one `path_refused` diagnostic, fall through to events. A fault that is not `Absent` (a thrown `TextFault` of kind `DIR_UNREADABLE`/`FILE_UNREADABLE`) is row M8: `MissionStatusUnavailable` with code `source_unreadable`. The oracle's `Path.is_file` would call that `pending`; the service must not (recorded divergence).
3. `J/domain/readmodel/derive/ReadinessDeriver.java`: a port of `dependency_readiness_for_wp` (`src/specify_cli/core/dependency_graph.py`) over the snapshot's lanes and provenance: `approved` and `done` satisfy a dependency; an id that names no Work Package of the Mission stays unsatisfied with a null lane. Read the Python function and the golden `readiness` members before writing; the golden is the arbiter.
4. Records (owned by WP12, final from the schemas under `contracts/mission-status/schemas/`): `MissionDetail`, `MissionPhase`, `PhaseName`, `PhaseStatus`, `PhaseBasis`, `WorkPackageSummary`, `Readiness`, `SubtaskProgress`. Default: no edit. Edit one only if the schema or the golden proves a member missing or wrong (named edit of WP12's file; one record per commit; state the evidence in the commit message).
5. Unit tests (T090 wrote them red): `PhaseDeriverTest`, `PhaseDeriverMatrixTest` (all 19 fixtures, iterated from the manifest listing, with and without a symlinked planning file for each of the three planning phases; the seven lane-count sets for implement and review), `ReadinessDeriverTest`.

**Files**: `PhaseDeriver.java` (~110 lines), `ReadinessDeriver.java` (~90 lines) and the unit tests.

**Validation**: AC-1.3 table green; reversing the check order (Completed event before the file) turns `phases-matrix` red.

---

### Subtask T093: Controller, mapper and wiring

**Purpose**: The HTTP edge of the route, holding no logic (FR-013).

**Steps**:

1. `J/adapter/in/http/detail/MissionDetailController.java`: `@RestController`, `GET /api/v1/missions/{missionId}` (the bean-level prefix follows the existing controllers; read `EventsController` for the registration style, and do not touch it: the build pin reads its needles). Holds only: (a) `MissionId.parse(missionId)`, empty becomes `throw DetailRefusal.notFound()`; (b) one call `MissionDetailQuery#mission`; (c) the status mapping, which is `ProblemMapper`/`ProblemAdvice` (WP12 added the one `DetailRefusal` handler; do not edit it); (d) the response through `MissionDetailMapper`.
2. `J/adapter/in/http/detail/MissionDetailMapper.java`: shapes the `MissionDetail` records into the generated contract model (`adapter.in.http.model`, WP06) or the JSON the canonical mapper writes, whichever the P2 spike decided; the mapper imports no class of `domain.readmodel.derive`, `domain.redaction` or `application..` other than `application.query.port.in..` (rule 15). Canonical writer: `MissionStatusApplicationJson.mapper()` (alphabetical properties, map entries sorted by key); the bytes must equal the oracle's.
3. `J/config/MissionDetailWiring.java`: `@Configuration` with exactly two beans. (1) The **one `WorkPackageIndex` bean of the whole mission** (TASKS-FRESH2-001): `public WorkPackageIndex workPackageIndex(TextSource, FrontmatterDecoder)` calling WP11's public constructor, from the `TextSource` bean of WP12's `DetailInfrastructureWiring` and the `FrontmatterDecoder` bean of WP11's `DecoderWiring`. WP11 declares no such bean (its lane has no `TextSource` bean) and WP14 and WP15 (and no other work package; WP16 has no index in its lane) inject this one and never declare another. (2) The `MissionDetailQuery` bean (constructed from the `MissionReadModel` bean of `ServiceWiring`, that `WorkPackageIndex` bean, the `TextSource` bean of `DetailInfrastructureWiring` and the diagnostics `Consumer<Diagnostic>` bean of `LoggingDiagnostics`; **neither `DecoderWiring` nor `DetailInfrastructureWiring` provides the `MissionReadModel` or the diagnostics consumer**). Nothing else. Add `T/config/MissionDetailWiring*Test.java` (owned): a context test loading only `MissionDetailWiring`, `DecoderWiring` and `DetailInfrastructureWiring` (never the full application context) that asserts **exactly one** `WorkPackageIndex` bean and exactly one `MissionDetailQuery` bean. The partial context cannot resolve the remaining collaborators by itself (TASKS-FRESH3-005): the test supplies them as **test-local `@Bean` stubs** in a nested `@Configuration` (a `MissionReadModel` stub or an in-memory model over the fixture, a `Consumer<Diagnostic>` that records, a `MissionStatusProperties` for a `@TempDir` project root and the `AllowlistAccess` that `DetailInfrastructureWiring#textSource` takes), without importing `ServiceWiring`; if it imports `ServiceWiring` instead, it names that explicitly and adds the project-root property, and the 'never the full application context' rule still holds. Do not edit `ServiceWiring`. Class and bean names in `config` follow the pattern of the other wiring classes.
4. Do not create `J/adapter/in/http/dto/`: generated mode forbids a populated hand-DTO package (the build pin); a hand DTO for this route, if the spike needed one, is WP06's.
5. HTTP tests install the service through `HttpHarness#startWith(Built, Map<Class<?>, Object> inbound, String... properties)` (WP10). Do not edit `HttpHarness`.
6. Controller tests in `T/adapter/in/http/detail/MissionDetailControllerTest.java`: 200 body shape, `Content-Type`, foreign Host/Origin 403 `request_refused` with zero reads recorded (row C1), and the row C2 404-not-400 fixture of T090. Rule 15 and rule 3b (controller annotations only in `adapter.in..`) must stay green with a non-zero scanned count.

**Files**: 3 production classes (~60, ~120 and ~40 lines) and the controller test.

**Validation**: controller and row tests green; ArchUnit rules 3, 3b, 15, 16 green (they scan `adapter.in.http.detail..` and now see real classes).

---

### Subtask T094: Served route, goldens and AC-14.2

**Purpose**: Make `DetailGoldenSuiteTest` compare this route's fixtures byte for byte.

**Steps**:

1. `T/conformance/golden/served/MissionDetailServedRoute.java` implements WP10's `ServedRoute` (the shape is WP10 T071 step 1; there is no Javadoc to read, and this work package does not edit that file). `goldenFiles()` is `{get-mission.json}`; `served()` is `ServedRoutes.expectedEntries(goldenFiles())`, i.e. **every fixture of the detail surface whose `golden/` holds `get-mission.json`**, derived from the manifest and not from a hand list; the only request key is `"-"` and `body(entry, "-")` is `GET /api/v1/missions/{missionId}`. The classes that carry that golden (the review checklist; the test of step 2 pins the derived set against this enumeration so a manifest change is a deliberate edit; all committed by WP07 under `R/conformance/**`, this work package writes none): `detail-populated` (8, including `bad-sibling-before` and `bad-sibling-after`: 200, equals the golden, no fault diagnostic, AC-1.7), `detail-early`, `detail-planning-only`, `phases-matrix` (19: the 18 planning-phase and lifecycle-type fixtures and `marker-row-without-event-id`, the D-98 marker row, plan section 14 S-20; the marker-row fixture feeds the `lifecycleTypes` set, not a planning-phase cell), **`wp-malformed-frontmatter` (28: the 28 `getMission` goldens, index-fed oracle; TASKS-FRESH3-003)**, `wp-duplicate-id` (3, including `duplicate-then-broken`), `projection-nulls` fixture `head-dates-nulled` (T4, a `knownDivergence` fixture V19) and any other fixture whose `golden/` holds `get-mission.json`. **Java-only fixtures have no golden and are not `ServedRoute` entries**; this route's named tests cover them: `projection-refusals` fixture `dependency-id-leak` (served first here; asserts 500 `projection_refused` and one diagnostic) and the Java-only class `lookup-faults` (`bad-sibling-unknown-meta` 500 `meta_unparseable`, `bad-sibling-unknown-link` 404 `path_refused`, `bad-sibling-unknown-two-faults` decided by the first in byte order; recorded divergence V9).
2. `ServedRoutes` (WP10) loads providers by name and treats a missing class as an empty route, so a typo in the provider name would leave the golden suite green with zero comparisons. Therefore add `T/conformance/golden/served/MissionDetailServedRouteTest.java` (owned): it asserts that `ServedRoutes` (through the WP10 accessor of the providers actually loaded) loaded `MissionDetailServedRoute`, that `goldenFiles()` equals its `ServedRoutes.OWNER` row, and the **provider-level completeness assertion**: `served()` equals `ServedRoutes.expectedEntries(goldenFiles())` (every manifest fixture that holds `get-mission.json`, so a fixture or golden file no provider registers cannot hide behind a fixture-level check; the fixture-level `ServedRoutesCompleteTest` of WP18 alone could not see it) and its per-class counts match step 1 (in particular 28 `wp-malformed-frontmatter` entries and the `detail-planning-only` entry), not a bare non-zero. Registering the provider is then the red-to-green step of these fixtures. Do not create `ServedRoutesCompleteTest` (it is WP18 and must not appear before the other three routes are served).
3. AC-1.2 (one head): for every fixture the `getMission` body without `phases` and `workPackages` equals that Mission's item on `/api/v1/missions` byte for byte. Control (a standing test): alter `nextAction` in the detail path only and the test goes red.
4. AC-14.2 (comparator control): reordering `phases` in the Java output, or perturbing one golden byte, turns the route's golden comparison red.

**Files**: `MissionDetailServedRoute.java` (~90 lines); test additions in `MissionDetailRowsTest`.

**Validation**: `DetailGoldenSuiteTest` green with this provider and red with one golden byte perturbed in a scratch copy.

---

### Subtask T095: Mapper cases, rows and the stub leg

**Purpose**: The per-pair projection cases and the fault rows.

**Steps**:

1. Seven `@ProjectionRow` cases in `T/adapter/in/http/detail/MissionDetailMapperTest.java` (the annotation is WP10's, T068 step 2: `String row()` and `String route()`): the pairs (row, route) T1 (`missionId`, `slug`, `targetBranch`: M7), T2 (`missionType`, `lastEventId`: null, 200), T3 (`friendlyName`, `nextAction`: M7 on an unremovable leak), T4 (`acceptedAt`, `mergedAt`, `discardedAt`: null, 200, M14, oracle differs V19), and, for the `WorkPackageSummary` the route lists, T5 (`wpId`, `dependencies[]`, `readiness.unsatisfied[]`: M7), T6 (`title`, `phaseLabel`: M7) and T10 (`lastTransitionAt`: whole-head M3 `ledger_unparseable`). Each case plants the unshowable value and asserts the row's outcome from plan section 8 FRESH3-003: an M7 row is 500 `projection_refused` plus one diagnostic, an M14 row is the member `null` with 200 and **zero** diagnostics. The case drives the real projection (application layer) and the mapper together. Fails if a nullable member refuses or a non-nullable member is nulled. The discovered count of this class is 7; `ProjectionRowCoverageTest` (WP18) closes the 26 pairs.
2. AC-12.1 rows for `getMission`, remaining ones not covered by T090: M4a, M5, M6, M7, M8, M10 (each its own fixture, asserted at the port and at the HTTP leg). A row whose condition is a permission failure is made under the D-32/D-101 rule: injected fault (`failWhen` with `AccessDeniedException`) always; the real-permission leg behind `RealPermissionFixture.refusedForThisUser(path)` only when the OS refuses it (it records `not run: precondition unmet: <test id>` otherwise). AC-12.3: no fixture answers 200 with an empty `workPackages` unless a row says 200.
3. AC-12.2/AC-12.4 for these rows: exactly one diagnostic line per occurrence, with the code and a `mid8` field (or `none`), and no absolute path, `HOME`, fixture root or canary in the line or in any Problem body.
4. The stub leg of AC-6.6: with the `NameEncoding` stub installed (WP10/WP11), a non-ASCII `WP01-é.md` is served by the route regardless of the host locale (the stub cases run under any locale and are not skipped); tests that need a real non-ASCII file name call `Utf8Host.assumeUtf8()`.

**Files**: `MissionDetailMapperTest.java` (~180 lines), additions to `MissionDetailRowsTest`.

**Validation**: the class discovers exactly 7 `@ProjectionRow` pairs; removing one makes the discovery assertion red.

---

### Subtask T096: `OutOfScopeRoutesTest`, port-level legs and counts

**Purpose**: The shared-file edits this work package owns or appends to.

**Steps**:

1. `T/adapter/in/http/rest/OutOfScopeRoutesTest.java` (this work package is the owner; the file exists at the checkout): remove **only** the line `"/api/v1/missions/01J01000000000000000000001"` from `OUT_OF_SCOPE`. The other six entries stay: the four routes of WP14 to WP16 and `/api/v1/drift`, `/api/v1/ops/invocations` still answer 404 like an unknown path. WP14 to WP16 each remove their own paths later (serialised by merge order); WP18 writes the final form (AC-18.2). Re-read the file before editing; touch nothing else.
2. Port-level legs (FR-013, AC-13.3): obtain the port through WP12's `PlainCaller` and assert, with no Spring context and no HTTP, that `MissionDetailQuery#mission(MissionId)` returns the typed result for a populated fixture, throws `DetailRefusal.notFound()` for an unknown id, and that a `MissionStatusUnavailable` carries the diagnostic code for rows M3/M4a. The legs live in `T/application/query/portlegs/MissionDetailPortLegsTest.java` (new, owned; **outside** `conformance.port` and **not** listed in `R/portlevel-tests.txt`): `PortLevelClassSetTest` requires every class of `conformance.port` to depend on `PortSourceSelector` or `PortFixtures`, and `PortSubsetSecondLegTest` runs every listed id on an in-memory and a filesystem source through a selector fixture, which carries only `MissionStatusQuery` and cannot carry a detail port (TASKS-GREEN-001). Obtain the port from `DetailFixture` (WP10) behind `PlainCaller` (WP12). Append no line to `R/portlevel-tests.txt`; run `PortLevelClassSetTest` and `PortSubsetSecondLegTest` to show nothing changed.
3. JaCoCo recount, using the command below. Expected shape (the command is the authority): `domain` plus the classes you added under `domain.*` (`PhaseDeriver`, `ReadinessDeriver`, and any nested type), `application` plus `MissionDetailQueryService` (and any nested type). `config` and `adapter` classes are not in the two counts.

`R/jacoco-class-floor.properties` holds two count lines, `domain=` and `application=` (55 and 44 on the flat checkout; the numbers on your tree are whatever PR A's tip holds). This work package is **not** the owner of the file (WP01 is); it makes a **named edit**: rebase, state the edit in the commit message, touch nothing else of the file. The new number is **derived by command at the commit that adds the classes**, never typed from memory or from the "expected" figures in this prompt:

```bash
cd services/mission-status-api
./gradlew --no-daemon test jacocoTestReport
python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"
```

Write the two printed numbers into the two lines. The count is over `<class>` elements, so a nested record, enum or sealed variant you declare inside a counted class raises it too. `jacocoScopeCheck` has floor semantics (a stale or lowered count is not detected by design, D-65), so the review brief compares the diff of the file with the classes this work package added. **Merge rule (D-145):** lanes that run concurrently each derive a count on their own tree; the lane merged second rebases, re-runs the command on the merged tree and writes what it prints in a named-edit commit of its own. WP17 T125 owns the single D-145 equality comparison on the PR B tip and WP18 re-runs it; a mismatch is repaired by a named edit of this file by the WP that found it.

**Files**: `OutOfScopeRoutesTest.java` (one line removed), `jacoco-class-floor.properties` (two lines), one new class `T/application/query/portlegs/MissionDetailPortLegsTest.java` (~70 lines; see "Plan defects found").

**Validation**: `OutOfScopeRoutesTest`, `PortLevelClassSetTest`, `PortSubsetSecondLegTest`, `PortLevelIdsTest` and `jacocoScopeCheck` green.

---

### Subtask T097: Gate

**Purpose**: Prove the whole work package at its tip.

**Steps**:

1. Run Gate G and Gate P:

```bash
export LC_ALL=C.UTF-8                      # plus the CONTRACT_BUNDLE variables of the pre-flight block
cd services/mission-status-api
./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.<package>.<Class>'            # the red-first loop, one class at a time
./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck                    # GATE G: the exit gate of every Java phase (never `check`)
cd ../..
.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q                         # GATE P: the pin of the build, the workflow and the tracked paths
```

Gate G is the module's fast tier (`test`, which excludes the tags `perf` and `native-binary`) plus the two JaCoCo gates. It is **not** `check` (that adds `perfTest`, `kitTest` and `nativeTagJvmTest`: `NO_FULL_HEAVY_SUITES_IN_MISSION`, plan section 5, D-88). Under the operator's E-7 ruling (2026-10-13, D-151) you MAY additionally run, before review, `./gradlew --no-daemon check`, `nativeCompile nativeTest` and `nativeSmoke -PnativeBinary=<binary>`; CI is the authority, a local green replaces no CI leg, and a local red is classified under plan section 6 and never retried to green. `nativePerf`, `native-tag-floor` and the `digests` comparison stay CI-only. Do not run `make test-full` or any whole-repository suite.

Stage new files (`git add`) before Gate P: the tracked-path scan reads `git ls-files`, so an unstaged new file passes it vacuously.

2. Targeted surface that must be green: AC-1.1 to AC-1.8 (`MissionDetailMetaReadCountTest` with the stream-route control; the golden comparison by `DetailGoldenSuiteTest` for the registered fixtures; `bad-sibling-*`; `duplicate-then-broken`), AC-12.1 rows for `getMission`, AC-14.2, the golden classes `detail-*`, `phases-matrix`, `projection-nulls` (`head-dates-nulled`), `projection-refusals` (`dependency-id-leak`), the 7 mapper cases, the stub leg of AC-6.6, `PortLevelClassSetTest`, `PortSubsetSecondLegTest` (both named explicitly in the Gate G run: they fail on a class or id that opens no selector fixture), `MissionDetailServedRouteTest`, the ArchUnit rules with their controls, `OutOfScopeRoutesTest`. NFR-006 terminology grep of plan section 5 (expect only the marked legacy `feature_slug` literal of `LanesCodec`, WP11; any other hit is a defect): `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md`.
3. Optional before review (E-7, plan section 5 expects the heavy local runs at P6, P8 and P13, not here): `./gradlew --no-daemon check`. A new controller bean is constructed at start-up on the native legs; if you suspect a missing reflection hint, run `nativeCompile nativeTest` and `nativeSmoke` locally and report a proven miss to the orchestrator (see "Plan defects found" item 2).
4. Revert-fails rows for this work package, each a standing named test (plan section 11, test strategy): AC-1.1 to AC-1.4 comparator controls (change one phase `status` in a golden; alter `nextAction` in the detail path only; test the Completed event before the file in `PhaseDeriver`; reverse the list rule for a ledger-only Work Package); AC-1.5/AC-1.7 (accept a `mid8`, a slug or a number; stop the lookup at the first faulted sibling, `bad-sibling-before` goes red; take the fault of a later sibling into the answer); AC-1.6 (200 without the `wp_file_skipped` diagnostic, or 500 for row M2; delete one row's fixture and the discovered-count guard goes red); AC-1.8 (re-read the matched `meta.json` once more, add a `probed()` call before the head, or restart the duplicate scan: `MissionDetailMetaReadCountTest` red); typed identifiers (make `MissionId.parse` throw, or map an empty parse result to 400 in the adapter: the row C2 fixture goes red).
5. Do not write to `M/**` (interim default F1/E-12). Put the tracer entry text in your hand-off report; the orchestrator appends it locally.

- **Public repository hygiene (C-006).** No home-directory path, user name, address or token in any file, fixture, test name or commit message. Use the placeholders `<repo>` and `<scratch>`. Credential-shaped test inputs are assembled at test time from two fragments (prefix and body) in a temporary directory; a committed fixture holds at most a near-miss one character short (D-48). Terminology: say Mission and Work Package, never "feature" in new prose (NFR-006; the grep of plan section 5 is run in step 2 and shows only the marked legacy `feature_slug` literal of `LanesCodec`).
- **Tracer entry (charter standing order 3).** Not written by this work package: interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`. Draft the entry (approach, deviations, and for WP15/WP16 the `@PermissionCase` ids) in the hand-off report; the orchestrator appends it to `M/traces/approach.md` locally.

**Validation**: Gate G and Gate P green; `git status` shows only files of `owned_files` plus the named edits.

---

## Self-contained green

PR B is a draft that must be green at this work package's tip, and its own tip (plan section 11, "Each PR is self-contained and green", D-153). What that means for WP13:

- **Fixtures live with their tests.** The golden fixtures (`R/conformance/**`, classes `detail-*`, `phases-matrix`, `projection-nulls`, `wp-duplicate-id`) are WP07/WP08's and already on the branch; this work package adds no fixture directory. The provisioned cases (links) come from `PROVISION_PLAN` (WP10), never committed. The Java-only classes `projection-refusals` and `lookup-faults` have no golden and are asserted in this work package's tests. Generated-at-test-time inputs (the 100000-entry trees are WP16's; here only the credential-shaped strings of AC-8.1) are built in a temporary directory.
- **Floors and counts satisfiable here.** `R/jacoco-class-floor.properties`: PR A's tip holds the counts of P1a to P8; WP13 adds its own classes and recounts (the command above), so `jacocoScopeCheck` and the per-class 0.90 line gate hold with this work package's tests covering `MissionDetailQueryService`, `PhaseDeriver` and `ReadinessDeriver`. The ArchUnit non-zero scanned count of rule 15 (`adapter.in.http.detail..`) is already non-zero from WP12's `RawQuery` and `IncludePrompt`; WP13 adds real controllers under it (plan section 11, rule 15 paragraph). `DEFINED_RULE_COUNT` stays 16. The 26-pair `ProjectionRowCoverageTest`, the `PermissionCaseFloorTest` floor of four ids and `ServedRoutesCompleteTest` are WP18's and are **not** satisfiable yet: none of them may exist at this tip. The native floors (`--floor 3`, `--request-floor 49`) and `R/nativesmoke/requests.json` stay as #5529 left them: this work package adds no `@Tag("native")` test and no smoke stage (D-99), WP17 raises them.
- **No test or gate names a type of a later work package.** The route tests use WP05 to WP12 types only. `OutOfScopeRoutesTest` still asserts 404 for the paths of WP14 to WP16. `DetailGoldenSuiteTest` compares only the providers that exist. The port-level class names only `MissionDetailQuery`.
- **The pin `tests/ci/test_mission_status_api_build.py` stays green, clause by clause (Gate P):** the rule-9 literals (the `api` and `model` packages unchanged); the `adapter/in/http` sub-directory clause (`detail` only; no `dto` directory); the `EventsController` needles (the file is not touched); the models list and the drift probe (not touched); the `@Tag("perf")` rule (no perf class here); the tracked-path scan (no `:`, `$` or illegal character in a new path; new files staged first); the probe list `NEW_FILES_IN_OUT_PACKAGES` (WP01's); the native-tag and `requests.json` clauses (unchanged numbers); the partition pin (no new source set). This work package edits none of the pin's inputs.
- **Mission record.** `M/meta.json` is complete and untouched. Under interim default F1/E-12 this work package commits nothing under `M/**`: the orchestrator keeps the `M/status.json` materialisation and the tracer appends locally. `M/status.json` is the materialisation of `M/status.events.jsonl` (`.venv/bin/spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`), never hand-edited; do not commit untracked CLI state blind (compare with the coordination copy first). Lane transitions are made with `spec-kitty agent tasks move-task`, never by editing a file. With the record intact `cutover-guard`, the mission-state audit (`.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`) and the corpus-blocking job stay green. This work package writes nothing under `M/**` (interim default F1/E-12).

---

## Plan defects found

1. **Resolved (TASKS-DECOMP-009, TASKS-ORDER-004, TASKS-COVER-001): `MissionDetailPortLegsTest` is owned by this work package** (wps.yaml and the frontmatter `owned_files`/`create_intent`; it lives in `T/application/query/portlegs/`, outside `conformance.port`, and is not listed in `R/portlevel-tests.txt`). Nothing is out-of-map and nothing is asked of the orchestrator.
2. **A reflection-hint miss caused by this route has no named-edit permission.** The shared-file table lets P6 and P8 (named edit) and P13 (owner) touch `J/config/MissionStatusApplicationHints.java`, and says nothing for P9 to P12. The route's controller, mapper and records are first exercised on the native legs only by WP17's smoke stage, so a miss would surface there. Treat a proven miss (local `nativeCompile nativeTest nativeSmoke`) as an orchestrator item, not as an edit of this work package. **RULED: OO-3 (orchestrator ruling 2026-10-13, binding; formerly TASKS-COVER-009 item 3).** Of the PR B work packages only WP17 edits `J/config/MissionStatusApplicationHints.java`. WP13 to WP16 do not edit it: on a locally proven native reflection-hint miss (`nativeCompile nativeTest nativeSmoke`) this work package STOPS and reports the miss to the orchestrator, who routes the hint to WP17. The JaCoCo recount stays a named edit under the plan's merge rule (D-145).
3. **AC-9.3 (guard flow) belongs to WP18 in the traceability table but WP14's gate names AC-9.1 to AC-9.4.** Not a WP13 matter; noted so the WP14 author's reviewer sees it. (WP13 covers the foreign-Host case of its own route, row C1.)

## Definition of Done

Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.

- T090: pre-flight green and recorded; every new test red on the phase base for its stated reason; shells compile.
- T091: `MissionDetailQueryService` follows the fixed sequence; `MissionDetailMetaReadCountTest` green (3 warm, 4 cold, others 1, the stream control, a discovered-row floor).
- T092: `PhaseDeriver` and `ReadinessDeriver` match the 19-fixture matrix and the readiness golden; the eight records unchanged, or edited only as evidenced named edits.
- T093: controller, mapper and wiring hold no logic; rules 3, 3b, 15, 16 green with non-zero scanned counts; row C2 is 404, never 400.
- T094: `MissionDetailServedRoute` registered and `MissionDetailServedRouteTest` green (provider loaded; `goldenFiles()` equals its `OWNER` row; `served()` equals the manifest-derived `expectedEntries`); `DetailGoldenSuiteTest` green; AC-1.2 and AC-14.2 controls green.
- T095: 7 `@ProjectionRow` pairs discovered; every FR-012 row applying to `getMission` has its fixture at port and HTTP; no path or canary in any line or Problem.
- T096: only the one line removed from `OutOfScopeRoutesTest`; no line appended to `R/portlevel-tests.txt`; `MissionDetailPortLegsTest` exists outside `conformance.port`; `PortLevelClassSetTest` and `PortSubsetSecondLegTest` green and unchanged; JaCoCo lines equal the command's output.
- T097: Gate G and Gate P green; tracer entry text in the hand-off report; no `M/**` write; `git status` clean of anything outside `owned_files` and the named edits.

## Risks

- **The head is read twice by accident.** A convenience call to `OverviewReader#ledger` or `probed()` makes the counts 4 warm and 5 cold. Mitigation: `MissionDetailMetaReadCountTest` on the real service; do not add any ledger call beside `head`.
- **A second head derivation.** Writing `nextAction` or the counts again in the detail path breaks AC-1.2. Mitigation: the body minus `phases` and `workPackages` is compared with the overview item for every fixture.
- **Projection in the wrong layer.** Importing `Projector` or `LeakClasses` into the mapper turns rule 15 red. Mitigation: project in the application layer, shape in the mapper.
- **JaCoCo count race with WP16.** A concurrent lane writes a different number. Mitigation: the merge rule above; the second lane recounts on the merged tree.
- **Locale-dependent tests.** `sun.jnu.encoding` not UTF-8 makes non-ASCII file-name tests fail before the service is reached. Mitigation: `LC_ALL=C.UTF-8` and `Utf8Host.assumeUtf8()`.
- **Native image.** See "Plan defects found" item 2.

## Reviewer Guidance

- Verify the **red-first form**: the new tests fail on PR A's tip for the stated reasons (scratch worktree), and the green tip holds without any assertion weakened. Reject a vacuous red.
- Check the call sequence in `MissionDetailQueryService` against FRESH3-002: lookup, duplicate continuation, `head`, nothing else.
- Check every revert-fails row of T097 step 4 exists as a standing test and bites (run a scratch mutation for the two `(M)`-free rows of your choice).
- Check `git diff` touches only `owned_files` and the named edits, `OutOfScopeRoutesTest` lost exactly one line, `R/portlevel-tests.txt` is untouched, and the JaCoCo lines match the command run on the tip.
- Check the architectural gates implicated by the touched files (rules 3, 3b, 7, 15, 16, `PortLevelClassSetTest`) by file, not the bare directory.
- Look for host paths, user names or tokens in tests, fixtures and commit messages.

## Implementation command

```bash
spec-kitty agent action implement WP13 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
