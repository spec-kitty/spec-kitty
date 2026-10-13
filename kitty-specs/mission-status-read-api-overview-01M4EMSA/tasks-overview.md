# Tasks Overview: Mission Status Read API, overview (Java service)

Companion to the generated `tasks.md` (which `finalize-tasks` rewrites wholesale from `wps.yaml` and so cannot carry prose; see the Tooling friction entry of 2026-10-10 [tasks]). This file is authored and is the home of the PR shape, write-scope, open-PR, chokepoint and traceability analysis the tasks stage owes the plan (plan.md sections 11 and 14). Terms: Mission, Work Package (WP), Lane. Paths are repository-relative placeholders; no home paths.

## 1. Work packages by plan phase

Numbering note: the plan and research.md call the whole of phase 1 "WP01" (spike plus scaffold). In this Mission's numbering phase 1 is WP02 (spike, decisions), WP03 (scaffold, supply chain) and WP04 (workflow, gate helper); read every plan sentence "WP01 records/decides" as "WP02 decides, WP03/WP04 apply and append what only a CI run answers".

Second numbering note (tasks fix round 1): the four oversize Java WPs were split along the seams their own prompts named, and the second halves took the NEXT FREE ids, WP17 to WP20, instead of renumbering WP06 to WP16. Reason: the plan, the review trail (findings, rulings) and every cross-reference already cite WP06 to WP16; renumbering would invalidate them and risk silent drift in nineteen prompts. The execution order is the dependency order, not the numeric order: WP05 -> WP17 -> WP06 -> WP18 -> WP08 -> WP19 -> WP09 and WP10 -> WP20 -> WP11/WP12. There is no renumbering map because no existing id moved; the map of what went where is the table below (first half keeps its id and loses the listed subtasks).

| Original WP | Now | Moved to the new WP |
|-------------|-----|----------------------|
| WP05 | WP05 domain core (T023-T026) | WP17: projection (T027) and ledger codec (T028) |
| WP06 | WP06 ports, cache, feed, in-memory source (T029-T032) | WP18: ArchUnit (T033), port-level suite and interim machinery (T034), floor verification and 2a gate (T035) |
| WP08 | WP08 resolver, SafeFiles, allowlist and recorder, listing (T042-T045) | WP19: `FilesystemMissionEventSource` (T046) and README stub (T047) |
| WP10 | WP10 controllers, Problem, contract document and validation, wiring and bind guard (T053, T055, T056, T057 steps 1-4) | WP20: SSE controller (T054), cross-route flow checks (T085 = T057 steps 5-7), native-tagged tests (T058), 4a gate (T059) |

| WP | Phase | Title | Depends on | Mode | Lane | Parallel |
|----|-------|-------|------------|------|------|----------|
| WP01 | 0 | Phase 0: campsite-clean the contract-tools filter-group test | - | code_change | lane-a | - |
| WP02 | 1 | Phase 1a: spike and decision record (R-2, R-7 items, each with a fallback) | WP01 | planning_artifact | lane-planning | - |
| WP03 | 1 | Phase 1b: Gradle scaffold, supply chain and skeleton service | WP02 | code_change | lane-b | - |
| WP04 | 1 | Phase 1c: path-filtered workflow, four native hello-route legs, gate helper | WP03 | code_change | lane-b | - |
| WP05 | 2a | Phase 2a-1: domain core (reducer, derivations, cursors, paging) | WP04 | code_change | lane-b | - |
| WP17 | 2a | Phase 2a-2: projection component and ledger line codec | WP05 | code_change | lane-b | - |
| WP06 | 2a | Phase 2a-3: application layer, ports, cache, change feed, in-memory source | WP17 | code_change | lane-b | - |
| WP18 | 2a | Phase 2a-4: ArchUnit rule set, port-level conformance suite, interim id check and 2a exit gate | WP06 | code_change | lane-b | - |
| WP07 | 2b | Phase 2b: Python oracle, fixtures, goldens, golden-honesty test and CI routing | WP01 | code_change | lane-a | [P] with WP02-WP06, WP08, WP17-WP19 (own lane) |
| WP08 | 3 | Phase 3a-1: filesystem adapter primitives (resolver, containment, allowlist, listing) | WP18 | code_change | lane-b | - |
| WP19 | 3 | Phase 3a-2: FilesystemMissionEventSource, flow-level allowlist checks and README stub | WP08 | code_change | lane-b | - |
| WP09 | 3 | Phase 3b: golden suite on the real adapter, second leg of the port-level subset, FR-013 floor | WP07, WP19 | code_change | lane-b | - |
| WP10 | 4a | Phase 4a-1: HTTP controllers, Problem mapping, contract document, contract validation, wiring and bind guard | WP09 | code_change | lane-b | - |
| WP20 | 4a | Phase 4a-2: SSE events controller, cross-route flow checks and real native-tagged tests | WP10 | code_change | lane-b | - |
| WP11 | 4b | Phase 4b: Host and Origin filter (403 set, closed 400 set, provisional E-7 rows) | WP20 | code_change | lane-b | write-disjoint from WP12-WP15 (same lane: runs in order) |
| WP12 | 5 | Phase 5a: native smoke replay (stage base), per-leg digests, gate digest comparison; retires the skeleton hello route | WP20 | code_change | lane-b | - |
| WP13 | 5 | Phase 5b: performance ratio tests (NFR-001, NFR-002, NFR-004) | WP12 | code_change | lane-b | - |
| WP14 | 5 | Phase 5c: nightly full-corpus comparison job and script | WP13 | code_change | lane-b | - |
| WP15 | 5 | Phase 5d: tag-triggered release job (operator decision E-4) | WP14 | code_change | lane-b | - |
| WP16 | 5 | Phase 5e: Host/Origin smoke stage, README, docs and changelog close-out | WP11, WP15 | code_change | lane-b | - |

Splits relative to the plan's eight phases, each with its reason (one WP per phase otherwise):

- Phase 1 -> WP02/WP03/WP04: the spike is a decision record (planning artifact, no code, throwaway harness) that WP03 consumes; scaffold (Gradle, supply chain, skeleton) and CI (workflow, gate helper) are separate concerns with separate review expertise and the CI half needs a pushed run.
- Phase 2a -> WP05/WP17/WP06/WP18: domain core; projection plus ledger codec; application layer, ports, cache, feed and in-memory source; ArchUnit, port-level suite and the 2a gate. ~7,000 lines with tests would not fit one sitting, and so neither would the two halves the first round left (WP05 ~4,000, WP06 ~4,500): each of the four is now about 1,100 to 2,900 lines. WP17 precedes WP06 because the in-memory source and the cache mapping use the codec; WP18 precedes the adapter so the ArchUnit rules guard every adapter class from its first commit.
- Phase 3 -> WP08/WP19/WP09: the adapter primitives and the event source need only 2a and run beside 2b; the golden suite needs 2b and the complete adapter.
- Phase 4a -> WP10/WP20: JSON controllers, contract document and validation, wiring and bind guard (production wiring must come first so the application context, hence the native hello legs, stays valid); then the SSE controller, the cross-route flow checks and the real native-tagged tests.
- Phase 5 -> WP12..WP16: native smoke/digests, performance ratios, nightly, release job, close-out: five concerns with disjoint tests; the release job and nightly each need their own pin tests and run nowhere in this Mission.
- 2b (WP07) stays ONE WP although it is the largest Python WP (~2,500 lines of which ~1,450 are estimated fixture data, section 4): seam if it overruns is fixture authoring (T038-T039) versus machinery and routing (T036-T037, T040-T041).

Execution lanes (confirmed against `lanes.json` after finalize): `lane-a` = WP01, WP07; `lane-planning` = WP02; `lane-b` = WP03 to WP06, WP08 to WP20 (one serial chain in the dependency order above). Lane `lane-b` depends on `lane-a` only through WP09 (needs WP07). `lanes.json` also records `lane-planning` after `lane-a` and `lane-b` after both (`depends_on_lanes`); that field is not a claim gate: claims are gated per WP by `dependency_readiness_for_wp` (`src/specify_cli/core/dependency_graph.py`), so WP03 to WP06 do not wait for WP07 and WP07 stays [P]. What `depends_on_lanes` does drive is the base of a freshly allocated lane worktree (`src/specify_cli/lanes/worktree_allocator.py`, dependency-lane route: the new lane starts from its dependency lanes' tips), which is why the orchestrator checks at the first `lane-b` claim that the allocated base already contains the WP01 and WP02 results. The allocator does this on EVERY claim, not only the first: on the reuse path (`allocate_lane_worktree`, `_merge_dependency_lane_tips`) it merges the current tip of each `depends_on_lanes` branch (`lane-a`, `lane-planning`) into the existing `lane-b` worktree, idempotently (an already-merged tip is skipped; a branch that no longer resolves is skipped with a warning). So every `lane-b` claim after WP07 has started picks up whatever commits `lane-a` has on its branch at that moment, including in-flight, unreviewed ones (`ci-router.yml`, `packs.yml`, `.gitattributes`, `test_contracts_workflows.py`, conformance trees). The same precondition is stated in the WP03 prompt, the first `lane-b` claim ("Before claiming, WP07 is approved, or the orchestrator has confirmed the lane-a tip is clean."; ANL-015). Orchestrator rule: before claiming a `lane-b` WP while WP07 is not yet approved, either drive WP07 to approval first, or confirm the merge is clean and re-run the workflow-enumerating sweep of WP04 T022 (AC-15d) and the architectural file checks after any such merge. A merge that cannot auto-resolve raises `DependencyLaneMergeConflictError` (the merge is aborted and the worktree reset to its pre-merge head, never half-merged): that is a lane-graph collision to resolve by hand in the lane, not a defect of the claimed WP; `lane-a` depends on nothing in `lane-b`, so the lane graph is acyclic. WP07 deliberately depends on WP01 only (plan sequences 2b after phase 1 for review order; a WP07 depending on WP04 would make the lane graph cyclic because WP09 depends on WP07).

## 2. Subtask index

| WP | Subtasks |
|----|----------|
| WP01 | T001 Sonar survey and green baseline of the target test; T002 Introduce `ROUTER_ONLY_EXTRA_GLOBS` and fold it into the assertion; T003 Targeted run, hygiene checks and the single campsite commit |
| WP02 | T004 Toolchain, supply-chain facts and library compatibility (Unverified 5, 11, 12, 13, 14, 18); T005 R-2 generated models versus hand-written DTOs (go/no-go, C-007); T006 Contract-document bundling mechanism (R-2 criterion 7, E-11); T007 Tomcat Host table CONFIRMATION in a throwaway harness (R-7, plan section 8); T008 JFR, SSE under native, native resource and Jackson-null behaviour, native test wiring (Unverified 3, 4, 10); T009 `stampLedger` cost over the real corpus (Unverified 16, NFR-001); T010 Write the decision record, tracers and fallback table |
| WP03 | T011 Wrapper, settings, properties, catalog and toolchain policy; T012 The COMPLETE `build.gradle.kts`; T013 Skeleton application, `ProjectRootCheck`, packaged defaults and native hints; T014 Skeleton tests and the native-tagged skeleton set (red-first); T015 Strict dependency verification metadata; T016 `tests/ci/test_mission_status_api_build.py` (pins, with revert-fails); T017 Build green, quickstart run, recorded evidence |
| WP04 | T018 The workflow skeleton and the JVM job; T019 Native matrix (hello route) and the terminal gate; T020 `scripts/ci/mission_status_gate_checks.py` and its tests (red-first); T021 CODEOWNERS and the workflow pins in `test_mission_status_api_build.py`; T022 AC-15d wide workflow-test sweep, first CI run and recording |
| WP05 | T023 Domain values, the ledger-line vocabulary (`LedgerLine`, its kind, `MalformedReason`, tail classification; step 3) and `SupportedSchemaRange`; T024 `StatusReducer` (port of the reduction `materialize_snapshot` runs); T025 `OverviewDeriver` (lifecycle status, progress, blocked count, last activity, topology); T026 Cursors and paging, and the creation of `jacoco-class-floor.properties` with the `domain` line (step 5) |
| WP17 | T027 `domain.projection` (the port of the oracle's `Projector`) and the raised `domain` floor; T028 `LedgerLineDecoder` codec (the one place ledger lines are decoded; it produces the `domain.model.LedgerLine` values and declares none) |
| WP06 | T029 Ports, results and the application service skeleton (red-first); T030 `ProjectionCache` and the fail-loud mapping (FR-004 L-rows at the port); T031 `ChangeFeed` and `subscribe` (stream rows S1-S6, overflow, diagnostics once); T032 In-memory `MissionEventSource`, `FixtureSpec`, `FixtureFactory`, `FixtureHandles`, `PortSourceSelector` (testsupport) and the `application` floor line |
| WP18 | T033 ArchUnit rule set (12 rules, positive controls, non-vacuity, literal rule-9 packages); T034 `portlevel-tests.txt`, the port-level suite, the interim id machinery and the AC-2a hook stub (all under `testsupport/**`); T035 JaCoCo floor verification and the 2a exit gate |
| WP07 | T036 Generator core, provisioning and the canonical writer (red-first); T037 `leak-patterns.json` and the manifest; T038 Fixture trees, batch A (and `resolver-cases.json`); T039 Fixture trees, batch B; T040 The golden-honesty test and its perturbations; T041 CI routing, registry, Packs deselect, `.gitattributes` and routing tests |
| WP08 | T042 `ReadDirResolver` (FR-006 rules 1-4) and the resolver-case table loader; T043 `SafeFiles` - NOFOLLOW reads and root containment (FR-010, AC-10d); T044 `Allowlist` and the instrumented recording seam (primitive-level AC-10a, AC-10e, AC-16a); T045 `Listing` (sorted by the code, never by file-system order) |
| WP19 | T046 `FilesystemMissionEventSource` (stamp, read, window, tear classification) and the flow-level AC-10a / AC-16a-d checks; T047 README stub with the allowlist fenced list, the terms list and the AC-10b parity test |
| WP09 | T048 `CanonicalJson`, materialisation step, `FilesystemFixtureFactory`; T049 The golden suite (AC-2a all classes, AC-8a comparator, AC-8b Java side); T050 Manifest, supported range, resolver cases, leak patterns (AC-1f, AC-6e, AC-9g); T051 The second leg of the port-level subset and the FR-013 floor (AC-13a/13b); T052 Phase 3 exit gate and evidence |
| WP10 | T053 Problem mapping and the generated-interface (or DTO) controllers, with the named AC-1b / AC-1c tests, the five out-of-scope 404 rows and the AC-4d HTTP leg (step 9); T055 `ContractDocumentController` (replaces the skeleton contract-document route only), springdoc absence, AC-11d; T056 Contract validation (AC-11a..11c) with the networknt validator; T057 `config` wiring, bind guard, properties, config pins (AC-9a, AC-9e) and the native hints of the classes added |
| WP20 | T054 `EventsController` (SSE) and the stream HTTP suites; T085 Cross-route flow checks (AC-9g canary scan, AC-10c runtime half, AC-16 over HTTP, AC-9h probe; = T057 steps 5-7 of the first round); T058 Real native-tagged tests and native hints; T059 Phase 4a exit gate |
| WP11 | T060 The filter, `OwnPortSource`, `OwnPortHolder` and registration (red-first); T061 AC-9b Host tables over real sockets (literal oracle); T062 AC-9c Origin table and AC-9d accepted controls; T063 Phase 4b exit gate |
| WP12 | T064 `requests.json` (stage `base`) and the group model; T065 `NativeSmokeTest` replay harness (red-first), retiring the skeleton hello route in the same commit; T066 Per-leg digest file; T067 Workflow wiring: digest upload, gate `digests` step, floors, pins; T068 Local proof, CI hand-off and evidence |
| WP13 | T069 The 500-Mission fixture generator and the NFR-001 ratio test (JVM); T070 NFR-004 on the JVM leg (100 SSE connections); T071 Native legs: NFR-002 start-up and NFR-004 native memory/threads; T072 Workflow wiring, pins and hand-off |
| WP14 | T073 Script core and unit cases (red-first); T074 The `nightly-corpus` job; T075 Pins, the AC-15d re-run and `workflow_dispatch` evidence; T076 First real-corpus run: triage hand-off |
| WP15 | T077 Tag trigger and the `release` job (red-first); T078 Pins in `tests/ci/test_mission_status_api_build.py` (AC-15a (iii)-(vii)); T079 AC-15d sweep on the edited workflow and hand-off |
| WP16 | T080 Stage `hostOrigin` of `requests.json` and the smoke replay; T081 Service README; T082 `ci-gate-mechanics.md` subsection; T083 Changelog line; T084 Mission-level close-out checks (Reflexivity diff check, hygiene) |

(Subtask counts: WP01 3, WP02 7, WP03 7, WP04 5, WP05 4, WP17 2, WP06 4, WP18 3, WP07 6, WP08 4, WP19 2, WP09 5, WP10 4, WP20 4, WP11 4, WP12 5, WP13 4, WP14 4, WP15 3, WP16 5; maximum 7, none above the 10 limit. T085 is the only new subtask id: it carries steps 5-7 of the first-round T057, which need every route and therefore cannot run before the SSE controller.)

## 3. Traceability

### 3.1 Requirement to Work Package (from `wps.yaml`, validated by finalize-tasks: every FR maps to at least one WP)

| ID | WPs |
|----|-----|
| C-001 | WP02, WP03, WP10 |
| C-002 | WP03 |
| C-003 | WP06, WP18 |
| C-004 | WP03, WP10 |
| C-005 | WP08, WP11, WP19 |
| C-006 | WP07, WP14 |
| C-007 | WP02, WP03 |
| C-008 | WP03, WP04 |
| C-009 | WP03, WP04 |
| C-010 | WP16 |
| C-011 | WP16 |
| C-012 | WP16 |
| C-013 | WP16 |
| FR-001 | WP05, WP07, WP09, WP10 |
| FR-002 | WP05, WP09, WP10 |
| FR-003 | WP06, WP20 |
| FR-004 | WP06, WP10, WP17, WP19, WP20 |
| FR-005 | WP05, WP07, WP09 |
| FR-006 | WP07, WP08, WP09 |
| FR-007 | WP06, WP19 (AC-7c/7d adapter tests) |
| FR-008 | WP01, WP07, WP09, WP12, WP14 |
| FR-009 | WP02, WP10, WP11, WP16, WP17 (AC-9g projection), WP20 |
| FR-010 | WP02, WP08, WP12, WP19, WP20 |
| FR-011 | WP02, WP03, WP10 |
| FR-012 | WP03, WP05, WP17, WP18 |
| FR-013 | WP09, WP18 |
| FR-014 | WP02, WP03, WP04 |
| FR-015 | WP04, WP12, WP14, WP15, WP16 |
| FR-016 | WP08, WP19, WP20 |
| NFR-001 | WP02, WP13 |
| NFR-002 | WP13 |
| NFR-003 | WP05, WP08, WP10, WP11, WP17, WP19, WP20 |
| NFR-004 | WP06, WP13 |
| NFR-005 | WP02, WP05, WP07, WP09, WP12, WP13, WP17 |
| NFR-006 | WP03, WP05, WP06, WP17, WP18 |
| NFR-007 | WP03 |
| NFR-008 | WP16, WP19 |
| NFR-009 | WP03 |
| SC-001 | WP07, WP09 |
| SC-002 | WP14 |
| SC-003 | WP10, WP20 |
| SC-004 | WP12, WP15, WP16 |
| SC-005 | WP11, WP16 |
| SC-006 | WP19 |
| SC-007 | WP04, WP07, WP16 |
| SC-008 | WP16 |

### 3.2 Acceptance criterion to Work Package (authored; the WP prompt of the named WP carries the red-first test and the revert-fails row)

| Criterion | Work Packages |
|-----------|---------------|
| AC-1a, AC-1d, AC-1e | WP10 (HTTP legs), WP20 (canary scan of 1d across every route and the stream), WP09 (project-header goldens, 1e), WP05 (derivations) |
| AC-1b | WP10 (named HTTP test, T053 step 6: metadata absent -> 200, `schemaVersion` null, health not healthy), WP05 (derivation) |
| AC-1c | WP10 (named HTTP test, T053 step 7: `missionCount` equals the drained item total), WP06 (count from the same enumeration) |
| AC-1f | WP05 (SupportedSchemaRange), WP07 (manifest vs `schema_version.py`), WP09 (Java equality) |
| AC-2a | WP09 (all classes, both sources); WP18 holds the shells, the single source selector use and the hook stub; the interim constant, id check and guard live under `testsupport/**` and WP09 deletes them |
| AC-2b | WP18 (port-level) |
| AC-2c | WP05 (cursor forms), WP10 (HTTP 400s and control) |
| AC-3a to AC-3o | WP06 (service/feed level, S1-S6, overflow, diagnostics once), WP20 (HTTP legs); 3g and 3i port legs are in the port-level subset (WP18, WP09) |
| AC-4a | WP06 (service-level mapping, one test per L-row), WP18 (port legs L1, L3a, L3b, L4, L4b in the subset), WP19 (adapter rows L2, L6, L7, L9, L11 and OS faults), WP10 (HTTP legs of the JSON routes), WP20 (stream rows) |
| AC-4b | WP07 (goldens, `knownDivergence`), WP09 (Java L4/L4b refusal) |
| AC-4c | WP06 (once per occurrence), WP20 (100-subscriber HTTP case) |
| AC-4d | WP19 T046 step 4 (latch and free-running at the adapter, port-level API), WP10 T053 step 9 (`TornTailConcurrencyHttpTest`: the HTTP leg, at least 200 `GET /api/v1/missions` during appends plus the latch stages) |
| AC-5a, AC-5c | WP05, WP18 (port-level), WP09 |
| AC-5b | WP18 (ArchUnit rule 1) |
| AC-5d | WP07 |
| AC-6a to AC-6d, AC-6f | WP08 (resolver), WP07 (goldens), WP09 |
| AC-6e | WP07 (Python half, `resolver-cases.json`), WP09 (Java half) |
| AC-7a, AC-7b | WP06 |
| AC-7c, AC-7d | WP19 |
| AC-8a | WP05 (ordering unit), WP07 (Python perturbations), WP09 (comparator and ordering suite perturbation) |
| AC-8b | WP07 (Python), WP09 (Java side) |
| AC-8c | WP14 |
| AC-8d | WP07 |
| AC-8e | WP07 (routing tests), WP04 (selection check) |
| AC-8f | WP07 |
| AC-9a, AC-9e | WP10 |
| AC-9b, AC-9c, AC-9d | WP11 (real sockets, literal oracle), WP16 (smoke stage hostOrigin on four legs) |
| AC-9f | withdrawn, replaced by AC-9g (spec.md Clarifications); the id is kept in spec.md, nothing is owed |
| AC-9g | WP17 (projection), WP07 (patterns, manifest), WP09 (per-pattern probes), WP20 (canary scan) |
| AC-9h | WP20 (JVM probe in T085 and native-tagged copy in T058) |
| AC-10a, AC-10b, AC-10d | WP08 (Allowlist constant and recorder at primitive level; SafeFiles, AC-10d), WP19 (flow-level AC-10a; README fence and its parity test, AC-10b), WP16 (final README) |
| AC-10c | WP18 (rule 10), WP20 (JFR runtime half), WP12 (native child-process sample) |
| AC-10e | WP18 (rule 7), WP08 |
| AC-11a (JSON routes), AC-11b, AC-11c | WP10 (WP03 pins the mode; WP02 T004 step 10 proves the AC-11c nested-build mechanism) |
| AC-11a (SSE event data) | WP20 T054 step 6, reusing the WP10 validator (ANL-001) |
| AC-11d | WP03 (skeleton), WP10 (real controller and bytes test) |
| AC-12a, AC-12b | WP18 |
| AC-13a | WP18 (interim), WP09 (final, floor) |
| AC-13b | WP18, WP09 |
| AC-14a, AC-14e, AC-14g | WP03 (AC-14a: standing `VerificationTamperTest` in `check`, T015 step 3, ANL-002) |
| AC-14b | WP04 (the one-time CI run on a scratch branch with a modified `gradle-wrapper.jar`, red at wrapper-validation, recorded in the spike record and the PR notes; T022 step 3); WP03 holds only the local wrapper-byte revert row |
| AC-14c | WP03 (Linux x64 write and local strict resolution), WP04 (strict-resolution exit status of the three verify-only legs plus Linux, all four recorded; T022 step 3) |
| AC-14d | WP16 (diff check: `contracts/` untouched) |
| AC-14f | WP03 (wrapper pin), WP04 (wrapper-validation action first) |
| AC-15a | WP04 ((i)-(iii), (vi)), WP15 ((iv), (v), (vii)) |
| AC-15b | WP12 (stage base), WP16 (stage hostOrigin) |
| AC-15c | WP04 (gate) |
| AC-15d | WP04 (first workflow commit), re-runs in WP14 and WP15 |
| AC-15e | WP04 (script `digests`), WP12 (producer and wiring), WP16 (floor) |
| AC-15f | WP04 |
| AC-16a to AC-16d | WP08 (recorder primitives), WP19 (port flow), WP20 (full HTTP flow) |
| NFR-001, NFR-002, NFR-004 | WP13 (WP02 measures the probe cost first) |
| NFR-005 | WP07 (determinism), WP09 (CanonicalJson), WP12 (digests) |
| NFR-006 | WP03 (rule and per-pattern scope task), WP05 (floor file created, `domain` line), WP17 (raised), WP06 (`application` line), WP18 (verification) |
| NFR-008 | WP19 (README stub), WP16 |
| NFR-009 | WP03 (tracked-path check) |
| C-009 | WP03 (packaging pin) |

### 3.3 Every gate the plan names has a test task

| Gate (plan section) | Test task |
|---------------------|-----------|
| ArchUnit rules 1-12 with positive controls and rule-count guard (13) | WP18 T033 |
| JaCoCo rule (3 minimums), `jacocoScopeCheck` (per pattern), `check` wiring (5) | WP03 T012/T016, floor file WP05 T026 step 5, WP17 T027 step 5, WP06 T032 step 4, WP18 T035 |
| Test partition (`native-binary` and `perf` tags, `nativeSmoke`/`nativePerf`/`perfTest`/`nativeTagJvmTest`, `check` dependencies) | WP03 T012 step 8, T016 step 10 |
| Campsite constant (9) | WP01 T002 |
| Golden-honesty test, deterministic provisioning, registered-worktree check, HEAD materialisation (1, 11) | WP07 T036, T040 |
| Routing test, Packs deselect pin, corpus registry (5, 11) | WP07 T041 |
| Build pins: wrapper, catalog, toolchain, springdoc absence, generated packages, bundle task, jar name, C-009, NFR-009 (1, 11) | WP03 T016 |
| Workflow pins: paths, fork guards, SHA pins, wrapper-validation first, matrix, gate `if:`, no pytest, ceiling 20 (5) | WP04 T021 |
| Gate helper: `native-tag-floor` and `digests` on planted files (1) | WP04 T020 |
| AC-15d workflow-enumerating sweep (5, Unverified 8) | WP04 T022 (re-runs WP14 T075, WP15 T079) |
| Contract document bytes and 404 rows (13, 11) | WP10 T055 |
| Contract validation and mode assertion (11) | WP10 T056 |
| Out-of-scope `Missions` operations answer 404 (WP02 T005 criterion 8) | WP10 T053 step 8 |
| Bind guard table (11) | WP10 T057 |
| Canaries, JFR runtime half, AC-16 over HTTP, virtual threads (11) | WP20 T085 |
| Host/Origin tables with literal oracle (8) | WP11 T061, T062; WP16 T080 |
| Smoke replay, digests, perturbation controls (11, 12) | WP12 T065-T067 |
| NFR-001/002/004 ratios (11) | WP13 T069-T071 |
| Nightly script cases and job pins (7) | WP14 T073, T075 |
| Release job pins and tag disjointness (12) | WP15 T078 |
| Port-level subset on both sources, FR-013 floor, interim constant deleted (11) | WP18 T034, WP09 T051 |
| Native-tag floor (11) | WP03 T014 (3 skeleton tests), WP04 T020, WP20 T058 |
| Wrapper negative run and four-leg strict-resolution statuses (AC-14b, AC-14c; spec) | WP04 T022 step 3 (orchestrator-pushed scratch branch, section 10) |
| Review diff check of shared surfaces (4) | WP16 T084 |
## 4. (a) PR shape

**DECIDED (ANL-013): five stacked slices; see section 11. The option list below is the pre-decision analysis, kept for the record.** Default stands: one PR per Mission, an ordered commit series by WP (charter; plan.md section 11 "One PR, readability"). The question the plan asked this stage to answer is whether the hand-written diff is reviewable in one sitting. It is not.

Estimated hand-written lines (tests included; generated and lock files, the wrapper jar, `verification-metadata.xml`, goldens and `manifest.json` excluded). Basis: the per-subtask sizes stated in the WP prompts, summed per WP. Exceptions, stated rather than hidden: the WP07 row rests on ~1,450 lines of ESTIMATED fixture data (about 35 hand-authored fixture trees, which are inputs rather than goldens; the prompt states no size for them) shown in its own column; the figures are estimates, not measurements. Fix round 1 corrected WP09 from 1,500 to 1,800 (T048-T051 state 350 + 250 + 600 + 350 + 250) and re-derived the rows of the four split Java WPs from their subtask sizes.

| WP | ~lines | WP | ~lines | WP | ~lines |
|----|--------|----|--------|----|--------|
| WP01 | 30 | WP08 | 1,920 | WP13 | 1,000 |
| WP02 | 150 (record) | WP19 | 1,210 | WP14 | 900 |
| WP03 | 1,250 | WP09 | 1,800 | WP15 | 350 |
| WP04 | 820 | WP10 | 2,830 | WP16 | 700 |
| WP05 | 2,900 | WP20 | 1,800 | | |
| WP17 | 1,100 | WP11 | 1,100 | | |
| WP06 | 2,750 | WP12 | 1,100 | | |
| WP18 | 1,350 | | | | |
| WP07 | 1,050 stated + 1,450 fixture data (estimated, not in the prompt) = 2,500 | | | total | about 27,600 |

About 27,600 hand-written lines, roughly 60% tests, is still seven times the plan's ~4,000-line threshold; the conclusion that the diff is not reviewable in one sitting is unchanged. What the split changed is the unit: the largest Java WPs are now WP05 (2,900), WP10 (2,830) and WP06 (2,750), none above half of the ~7,000 lines that the Phase 2a rationale of section 1 calls too much for one sitting (before the split WP05, WP06, WP08 and WP10 carried 4,000, 4,500, 3,400 and 4,900). Recommendation to the orchestrator and operator (they decide; nothing here changes the default unilaterally):

1. Treat the plan's seam after phase 4 as the minimum: PR 1 = WP01 to WP11 and WP17 to WP20 (phases 0 to 4b: JVM `check` green, native hello legs; about 23,500 lines), PR 2 = WP12 to WP16 (phase 5: native matrix completion, performance, nightly, release job, docs; about 4,050 lines), stacked, each independently green. Honest caveat: PR 1 alone is still about 23,500 lines.
2. Preferred, because even PR 1 is not reviewable by line: a stacked series of five slices, each independently green, reviewed mainly by the per-WP review verdicts, the adversarial squad and regeneration commands: S1 = WP01 to WP04 (campsite, spike record, scaffold, CI; ~2,250 lines), S2 = WP05, WP17, WP06, WP18 (Java core; ~8,100), S3 = WP07, WP08, WP19, WP09 (oracle, filesystem adapter, golden suite; ~7,430 of which ~1,450 fixture data), S4 = WP10, WP20, WP11 (HTTP, filter; ~5,730), S5 = WP12 to WP16 (~4,050). The first-round slice totals (S3 7,400, S5 4,000) shift by the WP09 correction and the re-derived split rows; the recommendation itself does not change. Lane structure allows it: `lane-a` (WP01, WP07) is the Python/CI side, `lane-b` the Java chain.
3. Why every slice is independently green, in particular S4 and PR 1 (finding TASKS-DECOMP-001): the skeleton hello route is what the skeleton `NativeSmokeTest` and the WP04 native legs assert. WP10 therefore replaces ONLY the skeleton contract-document route and its test (the real controller takes the same path), and the hello route, its tests and the skeleton `NativeSmokeTest` stay until WP12, which replaces the smoke test with the real replay and deletes the hello route in the same commit (WP12 owns `adapter/in/http/skeleton/**` and `src/test/.../skeleton/**` for that deletion only). WP10, WP20 and WP11 each carry a Definition of Done line "native legs green at this tip" (checked locally on Linux x64, the other three legs by CI), and WP03 T014 and WP11 state the Host form (`127.0.0.1:<port>`) the skeleton smoke uses so the filter cannot break it.
4. Generated artifacts are reviewed by regeneration command, never by line: wrapper jar, `verification-metadata.xml`, `libs.versions.toml` churn, goldens, `manifest.json`, `leak-patterns.json`.
5. Whatever shape is chosen, the PR description states the last workflow slot (E-5), that `Mission Status API gate` is not a required check (E-9), and what only CI can prove (the three non-Linux-x64 native legs, the AC-14b negative run and AC-14c four-leg statuses, first nightly, first tag).

## 5. (b) Write-scope disjointness

The ownership validator (`validate_no_overlap`) compares only dependency-UNORDERED pairs; a pair with a directed dependency path is "sequential" and may share files. The lane computation (`compute_lanes`) separately puts every pair with overlapping globs into ONE lane regardless of order, so shared surfaces are serialised in a single worktree. Both facts are used deliberately: `finalize-tasks --validate-only` passes with zero ownership errors and an acyclic lane graph (three lanes: `lane-a`, `lane-planning`, `lane-b`) at 20 WPs.

**Concurrent WPs (no dependency path between them)**

| Concurrent set | Owned by A | Owned by B | Why disjoint |
|----------------|-----------|-----------|--------------|
| WP07 (lane-a) versus WP02 to WP06, WP08, WP17 to WP19 | WP07: `tests/contract/_mission_status_conformance.py`, `tests/contract/test_mission_status_conformance.py`, `.../src/test/resources/conformance/**`, `.../src/main/resources/leak-patterns.json`, `ci-router.yml`, `packs.yml`, `tests/ci/test_mission_status_routing.py`, `tests/ci/test_contracts_workflows.py`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `.gitattributes` | Java trees, the new workflow, `tests/ci/test_mission_status_api_build.py`, `scripts/ci/mission_status_gate_checks.py`, `CODEOWNERS`, README, `research.md` | Different top-level trees and files; the only shared resource directories differ by file (`leak-patterns.json` versus `application.properties`; `conformance/**` versus `portlevel-tests.txt`) and by source set (`src/test/resources/conformance` versus `src/test/java/.../conformance/port`). The lane-a to lane-b edge is one-way (WP09 needs WP07). |
| WP11 versus WP12 to WP15 | WP11: `HostOriginFilter*`, `OwnPortSource*`, `HostOriginRefusal*`, `config/OwnPortHolder*`, `config/HostOriginRegistration*`, `adapter/in/http/hostorigin` tests | workflow, `tests/ci/test_mission_status_api_build.py`, `nativesmoke/**`, `perf/**`, `scripts/ci/mission_status_corpus_compare.py` and its test, and (WP12 only, for the one deletion) `adapter/in/http/skeleton/**` and `src/test/.../skeleton/**` | Disjoint paths: the skeleton directories are not WP11's (its filter classes sit beside them under `adapter/in/http/`, matched by name, not by directory). They share lane-b, so in practice they execute in order; the independence is a statement about write scope, not a scheduling promise. |

**PLAN-NEW5-001 (settled, review `plan-verify-r5.yaml`)**

1. `config/MissionStatusApplication*` is created by WP03 (phase 1) and WP10 (phase 4a) owns `config/**`. Settled by **dependency ordering**, not by an exclusion pattern: WP10 depends transitively on WP03 (sequential pair, exempt in the validator), both are in `lane-b`, and WP03 creates a minimal class that WP10 amends only to wire the real config. The validator has no negation syntax, so an exclusion pattern is not expressible; the plan's prose "`config/**` except `OwnPortHolder*`" is carried as a Must-NOT-touch clause in WP10 and WP20 (WP11 owns `OwnPortHolder*` and `HostOriginRegistration*`).
2. The `nativesmoke` test package is created by WP03 (three skeleton tests need `nativeSmoke` registered) and owned by phase 5. Settled by **dependency ordering**: WP03 creates the skeleton, WP12 replaces it and deletes the hello route with it, WP13 adds `NativePerfTest`, WP16 adds stage `hostOrigin` (WP12 -> WP13 -> WP14 -> WP15 -> WP16 chain, one lane).
3. Other hand-offs by the same mechanism: `ProjectRootCheck*` is WP03 only (WP08 and WP19 do not list it; a defect found later is a justified out-of-map edit, because the file is not theirs); `testsupport/**` is WP06 then WP18 then WP09 (plus `testsupport/http/**` created by WP10 and extended by WP20); `src/main/resources/application.properties` and `META-INF/native-image/**` are WP03 then WP10 then WP20; `README.md` is created by WP19 (stub) then extended by WP16; `src/test/resources/jacoco-class-floor.properties` is created by WP05 (`domain` line), raised by WP17 and completed by WP06 (`application` line), verified by WP18; the skeleton packages are created by WP03, lose the contract-document route in WP10 and the hello route in WP12.
4. `create_intent` semantics (a fix-round-1 finding on listing earlier-created files, TASKS-JVM-012, could not be applied as proposed): `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later WP's file exists yet, and rejects it unless the WP's frontmatter lists it in `create_intent` (verified: trimming WP10, WP17 and WP20 to only the files they create made `--validate-only` fail with `ownership_literal_path_errors`). So `create_intent` also names shared files an EARLIER WP creates. What was applied instead: each affected prompt carries a "`create_intent` note" stating which files it merely amends and what it creates, and WP08/WP19/WP06/WP18 had their lists corrected for the split. Open question for the orchestrator: whether the implement-time preflight reads `create_intent` as "this WP creates"; if it does, the validator and the preflight need to be reconciled upstream (tooling-friction entry).

**Rules that apply to every sequential hand-off**: the later WP appends or amends minimally in its own commit, rebases on its predecessor, and records the reason of any out-of-map edit in one line. An edit is "out-of-map" only when the file is in NO `owned_files` of that WP: an owned file is edited in-map, and calling it otherwise is a defect (WP16's workflow edit was mislabelled and fixed). Tracer files and `research.md` spike-record appends by WPs that do not own them are out-of-map by construction (cross-WP, append-only), committed on their own, never mixed with code.

## 6. (c) Open-PR overlap (read-only `gh pr list --repo spec-kitty/spec-kitty --state open --limit 100 --json number,files`, 11 open PRs when re-measured at fix round 2 on 2026-10-10; 10 at fix round 1; the count and the lists drift: first run at authoring time, re-run at fix rounds 1 and 2, and it changed each time)

- **Overlap with owned paths: one.** `docs/changelog/CHANGELOG.md` (WP16) is edited by NINE of the eleven open PRs now (fix round 2 measurement): #6004, #6002, #5957, #5954, #5953, #5950, #5945, #5944, #5540 (seven at authoring time, eight at fix round 1; #6002 and then #6004 added it). Expect a textual conflict on `[Unreleased]`; resolve by keeping both sides, never reordering their lines. No other owned path of any WP appears in any open PR.
- **No overlap** for: `services/**`, `contracts/**`, `.github/workflows/*` (`ci-router.yml`, `packs.yml`, the new workflow), `.github/CODEOWNERS`, `.gitattributes`, `tests/contract/*`, `tests/ci/*`, `tests/architectural/test_ci_corpus_trigger_completeness.py`, `docs/development/reference/ci-gate-mechanics.md`, `scripts/ci/*`, this Mission's `kitty-specs/` directory.
- **Semantic watch, not path overlap** (a landing before the named WP merges can shift goldens or the import-derived group pin without any path overlap; for each, run `--check` and the honesty test, and regenerate a shifted golden only with the Python generator, risk PR-2):
  - #5953 (mark-status by WP) touches `src/specify_cli/status/{__init__,models,store}.py` (`status/store.py` is an input of the Python oracle, WP07, and is named in the `contract_tools` group) and `src/specify_cli/core/subtask_rows.py` (a `contract_tools` group member in `ci-router.yml`).
  - #5951 (share coordination and identity meta keys) touches `src/specify_cli/mission_metadata.py` and `src/specify_cli/migration/mission_state.py`: `mission_metadata.py` is an input of the reader the oracle wraps, is imported by `tests/contract/_mission_status_payloads.py` and is a `contract_tools` group member, so a landing before WP07 merges can shift the goldens or the import-derived group pin.
  - #6002 touches `status/emit.py` (not an oracle import). Other PRs' `kitty-specs/*/tasks/README.md` paths belong to other Missions.
- Re-run the query before each WP claim and before the PR (a claim comment reserves nothing); this sentence is what keeps the section self-correcting.

## 7. (d) Chokepoints and serialisation order

| Chokepoint | Order (each later WP rebases and edits minimally) | Notes |
|------------|----------------------------------------------------|-------|
| `.github/workflows/mission-status-api.yml` | WP04 (create) -> WP12 -> WP13 -> WP14 -> WP15 -> WP16 | The single new workflow file (20th of 20). No other WP may add a workflow file; any further CI need is a job here. WP04 writes the tag-aware `concurrency` once. WP16 is last: its `digests --request-floor` edit is in-map. |
| Workflow-ceiling test/slot (`tests/architectural/test_module_shard_registry.py`, `.github/ci-module-registry.yml`) | WP04 only creates the file; WP04 pins file count == 20 | Run by WP04 T022 and re-run (workflow-enumerating subset) by WP14, WP15. Nothing raises `reusable_workflow_ceiling`. |
| `.github/workflows/ci-router.yml`, `.github/workflows/packs.yml` | WP07 only | One filter-group line; one `--deselect` token. `contracts*.yml`, `ci-nightly.yml`, `release.yml` untouched. `ci-fleet-verdict.yml` and `scripts/ci/fleet_verdict.py` gain the new workflow (WP04; E-3 superseded 2026-10-11). |
| `ROUTER_ONLY_EXTRA_GLOBS` in `tests/ci/test_contracts_workflows.py` | WP01 (empty constant) -> WP07 (first entry) | Same lane. |
| `tests/architectural/test_ci_corpus_trigger_completeness.py` | WP07 only | `_CORPUS_MARKED_MODULES` entry. |
| `tests/contract` shared helpers (`_mission_status_payloads.py`, `_mission_status_project.py`, `fixtures/mission_status_expected.json`) | No WP edits them (read-only inputs of WP07) | Both new modules match `*mission_status*.py`, so their `src` imports must stay within the `contract_tools` group. |
| `tests/ci/test_mission_status_api_build.py` | WP03 (create) -> WP04 -> WP10 -> WP20 -> WP12 -> WP13 -> WP14 -> WP15 | One named section per WP (`# --- WPnn ---`). |
| `scripts/ci/mission_status_gate_checks.py` and its test | WP04 only | Both subcommands (`native-tag-floor`, `digests`) land in WP04; WP12 only wires `digests`. Deviation from the plan, which splits the script across phases 1 and 5 (a cross-phase shared script is a chokepoint; the digest-file format is fixed by plan.md section 12). |
| `scripts/ci/mission_status_corpus_compare.py` and its test | WP14 only | |
| `.github/CODEOWNERS` | WP04 | one line |
| `.gitattributes` | WP07 | one scoped line |
| `services/mission-status-api/README.md` | WP19 (stub with the allowlist fence and its parity test) -> WP16 | The fence is parsed by the AC-10b test: keep it exact. |
| `src/test/resources/jacoco-class-floor.properties` | WP05 (create, `domain` line) -> WP17 (raise `domain`) -> WP06 (add `application`) -> WP18 (verifies; the only edit it may make is a one-line raise in its own commit, listed in its `owned_files`) | Only ever raised; `jacocoScopeCheck` is tolerant per pattern, so `check` is green at every tip. |
| `testsupport/**` (test sources) | WP06 (`FixtureSpec`, `FixtureFactory`, `FixtureHandles`, in-memory source, `PortSourceSelector`) -> WP18 (interim constant, id check, guard, `Ac2aGoldenHook` stub) -> WP09 (`CanonicalJson`, `FilesystemFixtureFactory`, hook implementation; deletes the interim machinery) ; `testsupport/http/**` WP10 -> WP20 | WP09 edits no `conformance/port/**` file. |
| `src/main/resources/application.properties`, `META-INF/native-image/**` | WP03 -> WP10 -> WP20 | |
| skeleton packages (`adapter/in/http/skeleton/**`, `src/test/.../skeleton/**`) | WP03 (create) -> WP10 (contract-document route and test only) -> WP12 (the rest, with the smoke test) | The hello route outlives WP10 on purpose (section 4, point 3). |
| `gradle/libs.versions.toml`, `gradle/verification-metadata.xml`, `build.gradle.kts`, `gradle.properties`, `settings.gradle.kts` | WP03 only | Every dependency any later WP needs is declared in WP03 (incl. the YAML library and the AC-11c nested-build mechanism that WP02 T004 steps 9-10 select); a later addition is a reviewed WP03 amendment, regenerated by command. WP03 also registers the whole test partition (`native-binary` and `perf` tags, `nativeSmoke`, `nativePerf`, `perfTest`, `nativeTagJvmTest`) so WP12/WP13 need no build-script edit. |
| `docs/changelog/CHANGELOG.md` | WP16 only | Nine open PRs edit it at the last measurement (section 6). |
| `docs/development/reference/ci-gate-mechanics.md` | WP16 only | Refresh `updated:`. |
| `research.md` | WP02 (owner); WP03/WP04 append answers only a CI run or the skeleton gives | Spike record; append-only, own commit. |
| `traces/*.md` | all WPs append | Append-only, own commit, never mixed with code. |
| `kitty-specs/` of any other Mission | untouched | `archive-freeze`. |

## 8. (e) Tracer files

Seeded/appended on 2026-10-10 under `traces/` (append-only; format `- **[YYYY-MM-DD][phase] Short symptom.** 1-3 sentences; disposition`, procedure `mission-tracer-files`): `approach.md` (tasks approach and the lane-graph reasoning), `design-decisions.md` (DD-19 to DD-25: tasks-stage decisions; DD-26 to DD-34: fix round 1; DD-35 to DD-39: fix round 2; DD-40 to DD-45: fix rounds 3 and 4; later entries continue from the last id: every WP that appends reads the last DD id first and never reuses one), `tooling-friction.md` (finalize-tasks and lane findings). Every WP appends its own dated entries during implementation; the Mission-closing entries are WP16 T084.

## 9. Deviations from the plan made by this stage (all recorded as design decisions)

1. `digests` subcommand implemented in WP04 with `native-tag-floor` (section 7).
2. WP03 registers `nativePerf` besides `nativeSmoke`; `NativePerfTest` is WP13's.
3. WP07 depends on WP01 only (lane graph).
4. `testsupport/http/**` (real-socket harness) created by WP10 for WP10/WP11 (extended by WP20).
5. Phase 5 split into WP12 to WP16; phase 1 into WP02 to WP04; 2a into WP05, WP17, WP06, WP18; 3 into WP08, WP19, WP09; 4a into WP10, WP20 (fix round 1 made the 2a, 3 and 4a splits finer).
6. The tasks-stage prose lives here, not in `tasks.md`.
7. (Fix round 1) The test partition is decided in WP03 T012 step 8 instead of being left to the implementer: tags `native-binary` and `perf`, `perfTest` wired into `check`, so neither the binary-dependent classes break `check` nor the NFR-004 proof goes unrun.
8. (Fix round 1) The skeleton hello route survives until WP12; WP10 replaces only the skeleton contract-document route.
9. (Fix round 1) `jacocoScopeCheck` is tolerant per pattern, and WP05 creates the floor file (WP03 T012 step 6).
10. (Fix round 1) In hand-DTO mode the openapi-generator plugin is not declared at all; the AC-11c drift test parses the contract YAML.
11. (Fix round 1) WP17 to WP20 are the second halves of WP05, WP06, WP08 and WP10 and take free ids, preserving every existing id (section 1).
12. (Fix round 2) The ledger-line vocabulary (`LedgerLine`, the sealed kind `Status`/`Lifecycle`/`Ignored`/`Blank`/`Malformed`, `MalformedReason`, the tail classification) lives in `domain.model` (WP05 T023 step 3), not in the codec: the outbound port in `application.port.out` carries these values, and ArchUnit rule 2 (application depends on application, domain, JDK) and rule 12 (codec used only by `adapter.out.filesystem` and `testsupport`) would otherwise be red. The codec (WP17) only produces them; `LedgerRead`, `LedgerWindow` and `LedgerStamp` stay in `application.port.out` (WP06).
13. (Fix round 2) The recording allowlist seam is public in `adapter.out.filesystem` and travels WP08 (seam) -> WP19 T046 step 0 (constructor) -> WP09 T048 (`FilesystemFixtureFactory`, `FixtureHandles`) -> WP10 `testsupport.http` -> WP20 T085, so the HTTP-served flow can observe file opens (AC-10a, AC-16). (Superseded in part by item 15: `RecordingAllowlistAccess` is a `src/test` class.)
14. (Fix round 2) Empty tag-filtered `Test` tasks under Gradle 9: WP02 T004 step 3 probes the behaviour, WP03 T012 step 8 applies the recorded answer to `perfTest` (and other tag-only tasks empty at their tip), WP03 T016 step 10 pins it. Nothing is asserted about Gradle 9 before the probe.
15. (Fix round 3, fix round 4 reconciliation) `RecordingAllowlistAccess` is a `src/test` class of `adapter.out.filesystem` (DD-42; `AllowlistAccess` stays in `src/main`); plan section 13 rule 11 is applied with test classes that live in the `adapter.out.filesystem` package itself treated as in-package, not as importers (DD-42), so the adapter-package suites of WP08, WP17 and WP19 do not trip it; WP18 owns `jacoco-class-floor.properties` for its one-line raise (DD-43). (Fix round 4) WP19 builds its own package-local `AdapterServiceHarness` for the real-adapter `MissionStatusQuery` tests, because `FilesystemFixtureFactory` (WP09 T048) does not exist yet (DD-45).

## 10. Orchestrator-owned items (not WP work)

- `research/baseline-red.md` (plan.md section 6): the baseline before WP01 is claimed and again before the PR. The repository-wide `make test-fast` comparison against it is HERE (the pre-PR baseline re-run), not in WP16: WP16 T084 runs only named test files.
- Assign #5529; board move; open-PR re-check at each claim.
- **Toolchain provisioning (prerequisite of WP02; finding TASKS-VERIFY-001, -002, -003).** The workstation had no JDK, Gradle or `native-image` at planning time. Before WP02 is claimed the orchestrator installs ONCE, under a persistent prefix outside the repository: GraalVM Community JDK 25.0.2 (graalvm-ce-builds release `jdk-25.0.2`, linux-x64; the tarball verified against the vendor `.sha256` asset, extracted from an empty directory) and the Gradle 9.7.1 binary distribution (`gradle-9.7.1-bin.zip`, verified against `https://services.gradle.org/distributions/gradle-9.7.1-bin.zip.sha256`, extracted from an empty directory); confirms `gcc` and the zlib headers (present at probe time); exports `JAVA_HOME` and the `PATH` entries in EVERY Java WP brief (WP02, WP03, WP05, WP17, WP06, WP18, WP08, WP19, WP09, WP10, WP20, WP11, WP12, WP13, WP16; the Python or workflow-only WPs WP01, WP04, WP07, WP14, WP15 need none); hands WP02 the versions and archive checksums (placeholder paths only in any committed text) so WP02 records them in the `research.md` environment block. Each Java WP prompt starts with a toolchain precondition ("`java -version` and `./gradlew --version` report the recorded versions, else STOP and report BLOCKED"; no substitute JDK, no self-install, no skipping a local gate). BLOCKED owner: orchestrator; the operator approves the install. WP03 onward stay unclaimed while WP02 is BLOCKED. **DECIDED (ANL-014, section 11): the install was approved and done; the question below is answered.** Formerly: **OPEN QUESTION for the operator:** approve installing GraalVM CE 25.0.2 and Gradle 9.7.1 on the workstation (prefix location, who runs it), or name the alternative (a container image or a CI-only build, which would turn the local-gate wording of the prompts into CI-only gates and remove the local red-first evidence of every Java WP).
- **Scratch-branch CI run (AC-14b, AC-14c).** After WP04, push (a) a scratch branch with a one-byte-modified `gradle-wrapper.jar` and confirm the `wrapper-validation` step turns the job red, and (b) the Mission branch to read the strict-resolution exit status of the four legs; both recordings go into the spike record and the PR notes (WP04 T022 step 3 states what to record). Never merged.
- CI babysitting for the four native legs, the `workflow_dispatch` exercise of `nightly-corpus`, and the maintainer's first release tag.
- Escalations still open with interim behaviour: E-2 (JFR event), E-5, E-7, E-8, E-9, E-12, E-13 (plan.md section 14).

## 11. Operator decisions after analyze (2026-10-10)

The analysis (`analysis-report.md`, verdict `ready`) was followed by operator decisions recorded in `reviews/analyze.ruling.md`; read that file for the wording. In short:

- **PR shape (ANL-013): five stacked slices.** (1) WP01-WP04; (2) WP05, WP17, WP06, WP18; (3) WP07, WP08, WP19, WP09; (4) WP10, WP20, WP11; (5) WP12-WP16. This settles the open question of section 4; the one-PR default is dropped.
- **Toolchain (ANL-014): installed.** GraalVM CE 25.0.2 (sha256-verified release tarball) and Gradle 9.7.1 (sha256-verified distribution) are installed locally with no system packages; the service build still uses its committed wrapper. The open question of section 10 is answered.
- **Tamper test (ANL-002): standing CI test** in WP03 (`VerificationTamperTest`, run by `check`).
- **AC-9b set 2 (ANL-005): amended.** The three container-decided Host rows joined the closed 400 list and are no longer provisional.
- Also folded in by the fix session: SSE event-data contract validation moved to WP20 (ANL-001), raw-byte golden comparison (ANL-003), the claim precondition on WP03 (ANL-015); ANL-011 (legacy noun in the four finalize-tasks commit subjects) is reworded when history is compacted before the PR, and ANL-012 (matrices) is populated through the CLI at accept.
