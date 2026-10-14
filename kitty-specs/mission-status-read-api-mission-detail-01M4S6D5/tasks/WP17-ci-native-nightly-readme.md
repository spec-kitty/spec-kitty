---
work_package_id: WP17
title: '[PR B] P13 (1/2) CI, native, nightly and README'
dependencies:
- WP13
- WP14
- WP15
- WP16
requirement_refs:
- FR-014
- FR-006
- FR-018
- FR-019
- NFR-004
- NFR-006
- NFR-008
- SC-002
- SC-009
- C-009
- C-010
- SC-008
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
subtasks:
- T119
- T120
- T121
- T122
- T123
- T124
- T125
history: []
agent_profile: python-pedro
authoritative_surface: .github/workflows/
create_intent:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/readme/MissionStatusReadmeTest.java
execution_mode: code_change
model: sonnet
owned_files:
- .github/workflows/mission-status-api.yml
- services/mission-status-api/src/test/resources/nativesmoke/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/nativesmoke/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/nativetags/**
- scripts/ci/mission_status_*.py
- tests/ci/test_mission_status_*.py
- services/mission-status-api/README.md
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/MissionStatusApplicationHints.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/readme/MissionStatusReadmeTest.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP17 – [PR B] P13 (1/2) CI, native, nightly and README

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: B (draft, stacked on PR A). Plan phase **P13 part 1 of 2** (plan.md section 11, row P13). The part-2 work package is WP18; it depends on this one (closing evidence last, open fork F3).
- **Work-package dependencies**: WP13, WP14, WP15, WP16 (the four route phases P9 to P12). All eight data routes answer when this WP starts.
- **External dependency (not a `dependencies` entry)**: the re-cut tip of #5529 (the side-first layout) was merged into this branch by the orchestrator before WP01, and PR A (WP01 to WP12) is below this WP on the branch. #957 cannot merge before #5529 (C-005); PR B cannot merge before PR A (plan section 11, "Two pull requests"). #5533's Java work stacks on PR A, not on this WP. No agent pushes, opens or retargets a PR.
- **Named edits (out-of-map; not in `owned_files`)**: each one follows the rule "rebase, state the edit in the commit message, touch nothing else of the file".
  - `R/jacoco-class-floor.properties` (WP01's file): only as the D-145 repair path of T125 step 3, the two count lines, written from the section 2 command on the merged tree.
  - `.github/workflows/ci-router.yml` (WP07's file, conditionally written there): a router change, if the retargeted PR needs one (plan: one line, only if required), is a named edit of WP07's file.
  - `J/config/MissionStatusApplicationHints.java` is listed in `owned_files`, but it is edited **only on a miss proven** by a local `nativeTest` or `nativeSmoke` run (E-7) or by CI at this tip; absent a proof, leave it byte-identical (plan section 11 shared-file table; wps.yaml WP17 comment). Ruling OO-3 (2026-10-13, binding): of the PR B work packages **only WP17** edits this file; WP13 to WP16 stop and report a native hint miss to the orchestrator, who routes it here.
  - none in `M/**` (interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`): the tracer entries (`approach.md`, `design-decisions.md`, `tooling-friction.md`) and the status materialisation are kept locally by the orchestrator; draft them in the hand-off report.
- **Write scope**: `owned_files` only (frontmatter). Anything else you want to change is an escalation to the orchestrator, not an edit. Aliases used below: `S=services/mission-status-api`, `J=S/src/main/java/org/speckitty/missionstatus`, `T=S/src/test/java/org/speckitty/missionstatus`, `R=S/src/test/resources`, `M=kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`.

## Objective

Extend the CI surface of the service to the five new routes and raise every number that guards it, in the same commits as the tests that need them: the nightly corpus job (with `LC_ALL=C.UTF-8`) and its comparison script, the native-image tests and the smoke stage `detail`, the native and request floors, the pins in `tests/ci`, and the README routes-and-scope section. Close with the phase gate and the recorded local nightly run (AC-14.5).

## Context

- This is the CI half of the plan's closing phase P13 (plan.md section 11, row P13; section 12 "Native release matrix"). The test half (full-flow, port-level, coverage-floor, perf) is WP18 and has a disjoint write scope.
- The numbers are fixed by plan section 12: `native-tag-floor --floor` 3 -> **8** (exactly five plain `@Test` methods are added; the true pin is `native_test_count()` in `tests/ci/test_mission_status_api_build.py`), `requests.json` gains stage `detail` with `requestCountFloor` **14**, and the `--request-floor` of the `digests` step goes 49 -> **63**. If the counted values differ from these, the counted value wins and you record why (the pin computes both).
- `LC_ALL=C.UTF-8` is set for the **nightly** job (workflow, S-16) and, for the **smoke** binary, by the test harness on non-Windows hosts (D-90): no environment line is added to the native legs and no workflow line outside the C-004 list is written.
- The nightly job cannot be dispatched before #5529 reaches `main` (plan section 5; Unverified 11). The pre-merge evidence for AC-14.5 is the **recorded local run** of the plan's section 5 sequence; the first dispatch is a post-merge item owned by the orchestrator.
- E-7 (operator, 2026-10-13, D-151): this WP may run `./gradlew --no-daemon check`, `nativeCompile nativeTest` and `nativeSmoke -PnativeBinary=<binary>` locally before review. `nativePerf`, `native-tag-floor` and the `digests` comparison stay CI only. **The one local full-corpus nightly run is NOT covered by E-7: ask the operator before running it.**
- Shape of the checkout: the `#5529` re-cut layout classes (`application/query/...`, `adapter/in/http/detail/...`, the `testsupport` classes of WP10) **exist after the re-cut**; cite the plan's section 1.1 mapping for any class you cannot find by its old flat name. Before you rely on any path below, run the C-005 pre-flight (T119 step 1). Files named below that exist in the checkout today: `.github/workflows/mission-status-api.yml`, `scripts/ci/mission_status_corpus_compare.py`, `scripts/ci/mission_status_gate_checks.py`, `tests/ci/test_mission_status_api_build.py`, `tests/ci/test_mission_status_corpus_compare.py`, `tests/ci/test_mission_status_gate_checks.py`, `R/nativesmoke/requests.json`, `T/nativesmoke/{NativeSmokeTest,NativePerfTest,SmokeRequests,Replay,RequestsFileTest,ReplayGuardsTest}.java`, `T/config/nativetags/{NativeContractResourceTest,NativeJsonSseRoundTripTest,NativeVirtualThreadProbeTest,NativeProject}.java`, `S/README.md`.

### Subtask T119: Pre-flight, then the workflow edits

**Purpose**: C-005 pre-flight as the first step of the phase, then the three workflow changes (nightly environment, native floors, request floor).

**Steps**:

1. **C-005 pre-flight (first step, before any edit).** From `S` with `export LC_ALL=C.UTF-8`: `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'`, then record `git log -1 --format=%H` of the ref that carries #5529 (plan section 5; today `refs/remotes/m5529/lane-b`) in the **first commit message** of this WP. Run the two string-literal greps of plan section 5 (`grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' S/src/test S/build.gradle.kts` and `grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github`); every hit must name a class of the right-hand column of the section 1.1 mapping. A red pre-flight is an orchestrator item, not yours to fix.
2. **Nightly environment.** In `.github/workflows/mission-status-api.yml`, job `nightly-corpus`, step "Start the service against this checkout": the `java -jar build/libs/mission-status-api.jar ...` line becomes `LC_ALL=C.UTF-8 java -jar ...` (or an `env:` entry on that step; one form, chosen so the pin in T123 can assert it). Nothing else in the job changes except what T122 needs (the compare step already passes `--base-url`, `--repo-root`, `--report`). The 45-minute timeout stays provisional.
3. **Native floors.** Both `native-tag-floor ... --floor 3` literals (the Linux/macOS step and the Windows step; at the checkout lines 265 and 268) become the value `native_test_count()` returns after T121 (expected 8). **Do not write the number before the tests exist**: this edit goes in the same commit as T121 (D-99).
4. **Request floor.** The `--request-floor 49` literal of the `digests` step (checkout line 324) becomes the new sum of the stage floors (expected 63 = 37 + 12 + 14). It goes in the same commit as T120.

**Files**: `.github/workflows/mission-status-api.yml` (about 4 changed lines). Do not add a step, a job, a matrix entry or an environment line to the native legs (plan section 12).

**Validation**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py tests/ci/test_mission_status_gate_checks.py -q` after the matching T121/T120/T123 edits; before them the floor pins are intentionally red on a half-applied state, so never commit the workflow numbers apart from their tests.

### Subtask T120: Smoke stage `detail` and the locale of the launched binary

**Purpose**: AC-19.2: the four legs replay the five routes byte for byte, with `includePrompt=true`, a 422 and a 404, and write one digest.

**Steps**:

1. In `R/nativesmoke/requests.json` add `"detail": { "requestCountFloor": 14 }` to `stages` and the group(s) for the 14 requests of plan section 12, one request per entry with the file's existing keys (`id`, `method`, `path`, `expectedStatus`, `expectedGolden`, `expectedContentType`, `expectedProblemCode`): `d01` getMission 200; `d02` getMission with a `mid8` 404; `d03` getWorkPackage 200 without a prompt; `d04` getWorkPackage 200 with `includePrompt=true`; `d05` getWorkPackage with `includePrompt=1` 400 `invalid_parameter`; `d06` getWorkPackage of a ledger-only Work Package 404; `d07` getWorkPackageDetail 200; `d08` getWorkPackageDetail with a legacy `lanes.json` 500 `source_unreadable`; `d09` listArtifacts 200 (**one** request, over a tree whose names pin the UTF-8 byte order); `d10` getArtifactContent 200 redacted; `d11` 422 (a credential file assembled at start-up from fragments, D-48); `d12` 415 (a NUL file assembled at start-up); `d13` 400 (repeated `path`); `d14` 404 (a missing file).
2. Goldens are `tree:` references into the committed conformance trees of the detail manifest (WP07 and WP08, exist after those WPs). **No second copy of any golden is created** (plan section 12, last paragraph). Reuse `R/nativesmoke/golden/` only for what is not a tree file.
3. Provisioning: the smoke harness runs `ProvisionPlan` (WP10, `T/testsupport/ProvisionPlan`; WP07 owns only the Python `PROVISION_PLAN` format) over the tree before launching the binary, so modification times and links agree across legs (R-9) and the credential and NUL files exist only at run time. A leg that cannot create a link or junction reports `not run: link unsupported` in the job summary and never a pass. If `SmokeRequests`, `Replay` or `RequestsFileTest` (all in `T/nativesmoke/`, owned here) need a field for the provisioning step, add it there with a test.
4. `NativeSmokeTest` builds the child with `new ProcessBuilder(binary, "--mission-status.project-root=...", "--mission-status.port=...")` (checkout line 61). Extract the environment decision into a small package-private function, for example `static void applyLocale(Map<String,String> environment, boolean windows)`, which puts `LC_ALL=C.UTF-8` into the child's environment on non-Windows hosts and changes nothing on Windows (FR-004, D-90). Add `NativeSmokeLocaleTest` with three cases: non-Windows sets it, Windows leaves the map equal, an existing different `LC_ALL` is overridden.
5. Edit `T/nativesmoke/NativePerfTest.java` to run the NFR-002 scenario with ten concurrent prompt requests (S-13) **only if** that class already runs the NFR-002 scenario; otherwise leave it untouched and say so in the commit message.

**Files**: `R/nativesmoke/requests.json` (+14 requests), `T/nativesmoke/NativeSmokeTest.java`, `NativeSmokeLocaleTest.java` (new, about 40 lines), possibly `SmokeRequests.java`/`Replay.java`/`RequestsFileTest.java`.

**Validation**: `RequestsFileTest` (floor equals the number of requests in each stage), `ReplayGuardsTest`, `JvmReplayTest` (the JVM twin replays the new stage over the real service: this is the local proof that every golden matches); `NativeSmokeLocaleTest`. Optional under E-7: `./gradlew --no-daemon nativeCompile nativeTest`, then `./gradlew --no-daemon nativeSmoke -PnativeBinary=<binary>` once for the proof that the binary replays `detail`. Record the observed digest in the commit message only; never the path of your home directory.

### Subtask T121: The five native-tagged tests and the floor raise

**Purpose**: AC-19.1 and NFR-008: the YAML decoder, the JSON of the five bodies and the resources work in the native image.

**Steps**:

1. Under `T/config/nativetags/` add five classes in the style of `NativeContractResourceTest` (`@Tag("native")`, `@SpringBootTest(classes = MissionStatusApplication.class, webEnvironment = RANDOM_PORT)`, `NativeProject` for the project tree), **plain `@Test` methods only** (`native_test_count()` counts `@Test` lines and counts a `@ParameterizedTest` as 0, while the gate counts executed cases): decoder valid, decoder rejected, content 200, content 422, detail assembly. Suggested names: `NativeWorkPackageDecoderValidTest`, `NativeWorkPackageDecoderRejectedTest`, `NativeArtifactContentOkTest`, `NativeArtifactContentUnprocessableTest`, `NativeWorkPackageDetailTest`. One `@Test` per class keeps the count equal to the number of classes.
2. Extend `NativeProject` (same directory, owned here) with the Work Package files, the credential fragment file and the Mission the five tests need; keep its existing callers untouched.
3. The same commit raises everything that hard-codes 3 (PLAN-FRESH3-013): the two `--floor` literals (T119 step 3); the needle `"--floor 3"` in the native-job check of the pin (the `for needle in (...)` tuple); the literal `native_test_count() == 3` in `test_the_native_floor_is_the_number_of_native_tagged_tests`; and the controls that `replace("--floor 3", ...)` and pass `3`, `4` and `2` as the count. Rewrite those controls **relative to `native_test_count()`**: a `replace` of a literal that no longer occurs is a no-op and a control asserting a violation after a no-op would pass for the wrong reason. The value written is whatever `native_test_count()` returns after the five exist. Extend `REAL_NATIVE_TESTS` in the pin with the five new class names so `native_tag_violations` checks them too.
4. P6, P11 and P12 added no native-tagged test (plan section 12), so before this commit the pin is green at the floor of 3; after it, green at the new floor. There is no intermediate red commit.
5. A reflection or resource-hint miss shows as a failing `nativeTest`: only then edit `J/config/MissionStatusApplicationHints.java`, with the failing test named in the commit message (ruling OO-3: you are the only PR B work package that may edit it; a miss reported by WP13 to WP16 arrives through the orchestrator).

**Files**: five new test classes (about 40 to 70 lines each), `NativeProject.java`, `tests/ci/test_mission_status_api_build.py` (T123 owns the rest), the workflow floors.

**Validation**: `./gradlew --no-daemon nativeTagJvmTest` (the JVM twin; also T125); `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`. The red-first form: on the phase base `native_test_count()` is 3 and the new tests do not exist; the mutation check is to delete one new `@Test` and see `test_the_native_floor_is_the_number_of_native_tagged_tests` red.

### Subtask T122: Corpus comparison over the five routes and the Work Package file decode class

**Purpose**: AC-14.5 and AC-6.4: the nightly step compares, for every Mission and Work Package of the repository, the service with the Python oracle and names the first difference.

**Steps**:

1. Read `scripts/ci/mission_status_corpus_compare.py` first (579 lines at the checkout: `Reply`, the `MissionOracle` and `ServiceClient` protocols, `Row`, `Report`, `first_difference`, `refusal_classes_agree`, `PythonOracle`, `compare_corpus`, `independent_count`, `_non_vacuity`). Extend in the same shape; no new dependency (`uv.lock` and `pyproject.toml` stay unchanged).
2. Add oracle methods on `PythonOracle` for `getMission`, `getWorkPackage` (with and without `includePrompt=true`), `getWorkPackageDetail`, `listArtifacts`, `getArtifactContent`, using the detail oracle module `tests/contract/_mission_status_detail.py` (WP07's oracle extension; the file already exists in the checkout). Compare per Mission: `getMission`, the listing; per Work Package of every Mission: `getWorkPackage` twice and `getWorkPackageDetail`; per file of each Mission's listing: `getArtifactContent`.
3. Add the decode class of every Work Package file (AC-6.4): the outcome class and decoded fields of the oracle's frontmatter read against the service's decoder outcome (derive the service side from the `getWorkPackage` answer or its refusal class). The first difference is reported as **file, side, class** (AC-6.4) in the same `render_row` style the file uses for the other routes (side, route, Mission, class per AC-14.5).
4. The refused list is the **only** exemption (E-10 of #5529): SK-351 Missions, the SK-353 Mission `058-hybrid-prompt-and-shim-agent-surface` (served as the oracle serves it or refused with `projection_refused`, whichever the D-97 decision (WP11 T077) recorded; pinned by fixture `wpm-28`), and any Mission the oracle itself cannot read. Derive it by an independent scan (extend `independent_count`); a test fails when the list grows without an entry in the decision record.
5. Keep `_non_vacuity` honest: floors for the count of Missions, Work Packages, listed files and decoded Work Package files; zero matches fails.
6. Update `tests/ci/test_mission_status_corpus_compare.py` (475 lines) and `tests/ci/test_mission_status_gate_checks.py` (259 lines): fake oracle and fake service doubles (the file uses the two Protocols) with one planted difference per route and one per decode class, each asserting the named first difference; a control with no difference passes; an empty corpus fails.

**Files**: `scripts/ci/mission_status_corpus_compare.py` (about +250 lines), the two test files (about +200 lines).

**Validation**: `.venv/bin/python -m pytest tests/ci/test_mission_status_corpus_compare.py tests/ci/test_mission_status_gate_checks.py -q`; `.venv/bin/ruff check . && .venv/bin/ruff format --check .`; `make format-check-files FILES="<changed .py paths>"`; `.venv/bin/ruff check --select TID251 .`. Red-first form: red on the phase base (new tests name routes the script does not compare yet).

### Subtask T123: Own the pin `tests/ci/test_mission_status_api_build.py`

**Purpose**: the file (2737 lines) is owned here; WP01 (probe list and its control) and WP06 (the three clauses of FRESH2-001, E-9) made named edits earlier. Keep those clauses; add the perf-class, native-floor, requests.json and workflow clauses.

**Steps**:

1. Keep green and untouched: the `NEW_FILES_IN_OUT_PACKAGES` probe list and its control (WP01), the three FRESH2-001 clauses (WP06), the rule-9 literals, the `adapter/in/http` sub-directory names, the `EventsController` needles, the `@Tag("perf")` rule, the tracked-path scan.
2. Add (a) the native-floor clauses of T121; (b) a requests clause: `requests_floor_sum` equals the new `--request-floor` (already pinned) **and** the stage `detail` exists with floor 14 and 14 requests; (c) a workflow clause: the `nightly-corpus` start step carries `LC_ALL=C.UTF-8` and no native-leg step does (D-90); (d) **no widening of the perf clause**: `perf_class_violations` already requires `@Tag("perf")` of every test-holding class under `T/perf` and the `PERF_CLASS_FLOOR`, and `RATIO` and `CEILING` constants only of the two named classes `Nfr001OverviewLatencyTest` and `Nfr004SseConnectionsTest`. Do **not** extend the RATIO and CEILING requirement to every class: `Nfr004HeapMedianTest` (existing) and WP05's `Nfr009CacheGrowthTest` (its quantity is a retained-heap difference named `CEILING_BYTES`, with no `RATIO`) would turn the pin red at this tip. Keep the existing clause green and add a control only if you touch the perf rule at all. Do **not** list `Nfr001DetailLatencyTest` or `Nfr002BoundedMemoryScenarioTest` by name: they are WP18's and do not exist at this tip (see Plan defects found).
3. Each new clause gets a "turns red when" control that mutates the input text it reads (the file's existing pattern: `*_pin_turns_red_for_...`).

**Files**: `tests/ci/test_mission_status_api_build.py` (about +120 lines), possibly `test_mission_status_routing.py` only if the router/workflow edits require it (AC-14.6).

**Validation**: the four architectural workflow tests too (`.venv/bin/python -m pytest tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_workflow_coherence.py tests/architectural/test_module_shard_registry.py -q`); `.venv/bin/python -m pytest tests/ci/test_contracts_routing.py tests/ci/test_contracts_workflows.py tests/ci/test_fork_guard.py tests/ci/test_workflow_script_import_guard.py tests/ci/test_mission_status_api_build.py tests/ci/test_mission_status_routing.py tests/ci/test_mission_status_corpus_compare.py tests/ci/test_mission_status_gate_checks.py -q`.

### Subtask T124: README routes and scope (FR-018)

**Purpose**: SC-009: the README states the nine routes and that drift and Ops have no Java owner yet.

**Steps**:

1. Replace the "Routes and scope" section of `S/README.md` (checkout lines 27 to 36): list the nine routes (project, missions, events, openapi.yaml and the five new ones: `getMission`, `getWorkPackage`, `getWorkPackageDetail`, `listArtifacts`, `getArtifactContent`), keep "Any other path is `404` once the Host and Origin check has passed", and state that drift and Ops have **no Java owner yet** and that governance is #5533 on these primitives. The text must not contain "are issue #957" or "artifacts, drift, Ops".
2. Add the divergence list V1 to V19 to the existing "Recorded divergences from the Python reference" section (checkout line 114) and the note that the ledger and the Work Package files are read at slightly different instants (plan, Reflexivity). Add the one stream sentence: the stream projection, the stream cap and the shutdown registry belong to the inbound port and serve every adapter; the cap key `mission-status.stream.max-connections` and its README lines are unchanged.
3. The allowlist section (WP09), "Prompt text" (WP14) and the locale sentence (WP16, the three literals `UTF-8 locale`, `sun.jnu.encoding` and `LC_ALL`) arrive as named edits and are already there when this WP starts; **verify they exist, do not rewrite them**. If one is missing, stop and report (escalation).
4. NFR-006 terms: Mission, Work Package and Lane as product terms; the rest as code identifiers, defined in the README "Terms" list the first time they appear (Work Package index, read scope, text-read port, walk counter, admission gate).
5. AC-18.1 test, **a Java test (ruling 2026-10-13: the Java-only rule covers product code, and this test is moved from Python to the service test tree so that this work package adds no new Python)**: a new file `S/src/test/java/org/speckitty/missionstatus/readme/MissionStatusReadmeTest.java` (owned literal path, listed in `create_intent`; the test lives in its own package `readme`, outside `conformance.port`). It reads `README.md` from the module working directory (Gradle runs the tests in `S`; assert the file exists first) and holds one pure helper `problems(String readme)` returning the list of violations, so a control can feed it a mutated copy. It fails on "are issue #957", on "artifacts, drift, Ops", on a missing "no Java owner yet" inside the routes-and-scope section, and on a missing `UTF-8 locale`, `sun.jnu.encoding` or `LC_ALL` (the one locale-sentence contract with WP16, see "Plan defects found"); its control feeds `problems` a mutated copy (a revert of the README, each needle removed in turn) and expects the violation. The AC-18.2 positive half is WP18 (T128); see Plan defects found for what this tip can assert.
6. Run the NFR-006 grep from plan section 5 over `S/src/main` and `S/README.md`; expect empty apart from the marked legacy literal `feature_slug`.

**Files**: `S/README.md` (about +60 lines), `MissionStatusReadmeTest.java` (new, about 80 lines).

**Validation**: `./gradlew --no-daemon test --tests '*MissionStatusReadmeTest'` from `S`; the grep above; `.venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q`.

### Subtask T125: Phase gate

**Purpose**: prove this WP's tip is green on every gate it can reach, and record the nightly evidence.

**Steps** (order; `export LC_ALL=C.UTF-8` first; build the bundle and export `CONTRACT_BUNDLE` and `CONTRACT_BUNDLE_SHA256` as in plan section 5):

1. Gate G from `S` (it runs `MissionStatusReadmeTest` with the rest of `test`): `./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`; then `./gradlew --no-daemon nativeTagJvmTest`.
2. Gate P: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`, and the pins listed in T123.
   The four architectural workflow tests that police the workflow file, the CI scripts and the registry (plan section 5; a silent double run is the defect class): `.venv/bin/python -m pytest tests/architectural/test_ci_corpus_trigger_completeness.py tests/architectural/test_no_duplicate_suite_execution.py tests/architectural/test_workflow_coherence.py tests/architectural/test_module_shard_registry.py -q` (TASKS-COVER-003).
3. **D-145 equality comparison**: print the two counts with the plan section 2 command (`python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"` from `S`, after `test jacocoTestReport`) and compare with `R/jacoco-class-floor.properties` for **equality**. This WP is the **single owner** of the D-145 equality comparison on the PR B tip (PR A's tip was compared by WP12 T088; WP18 re-runs this one). This WP adds no class under `domain` or `application`, so it normally edits no count line; an inequality means a concurrent lane understated it, and the repair is a **named edit of `R/jacoco-class-floor.properties`** (WP01's file) by this WP in a commit of its own that writes what the command prints (see Plan defects found).
4. Python hygiene (plan section 5): `ruff check`, `ruff format --check`, `make format-check-files`, TID251, `spec-kitty regen --check`, the terminology test, `test_layer_rules.py` and `test_pyproject_shape.py`, `test_archive_root_byte_identical.py`, the Windows-filename guard (**after staging** the new files), `.venv/bin/python scripts/generate_contextive_glossaries.py check`, `local_gate_parity.py --base-ref origin/main`, the Contracts `python-checks` smoke scripts.
5. Optional under E-7: `./gradlew --no-daemon check`, `nativeCompile nativeTest`, `nativeSmoke -PnativeBinary=<binary>`.
6. AC-14.5 evidence: **ask the operator first**, then run the local nightly sequence of plan section 5 (`bootJar`; start the jar with `LC_ALL=C.UTF-8` and the recorded PID; run the compare script with `--report`; `kill "$SERVICE_PID"` by PID, never by pattern). Record in the PR "Tests run" section: counts of Missions and Work Packages compared, elapsed time, zero differences or the first named. If the operator declines, record "not run: operator word not given" and stop; do not substitute.
7. AC-19.1, AC-19.2, AC-19.4 and AC-6.4 are asserted by the items above (AC-19.3 is WP06 T041 step 4, `PlantedClassCoverageNestedBuildTest`); the four native legs and the gate are green on the PR (CI).

## Self-contained green

This WP's tip, and PR B's tip at this WP, must be green alone on every CI gate (plan section 11, "Each PR is self-contained and green at its own tip").

- **Fixtures live with tests (D-109).** The `detail` stage requests and their `tree:` goldens land with `RequestsFileTest`/`JvmReplayTest`, which replay them over the real service of WP13 to WP16 (all below this WP). The five native tests land with their `NativeProject` additions. The comparison script's tests carry their own doubles.
- **Floors satisfiable now (plan section 12).** `--floor` becomes `native_test_count()` in the same commit as the five tests; `--request-floor` becomes 63 in the same commit as stage `detail` (D-99); `requestCountFloor` 14 equals the 14 requests. No later WP raises either number.
- **No forward reference.** Nothing here names a type, test or file of WP18: the perf clause of the pin is generic, the README test does not read WP18's `OutOfScopeRoutesTest` final form, and `ServedRoutesCompleteTest` does not exist yet (and must not appear in PR A).
- **Pin clauses kept green** in `tests/ci/test_mission_status_api_build.py` (plan section 11): the probe list (WP01), the three clauses (WP06), rule-9 literals and `EventsController` needles, the models list and drift probe, the `@Tag("perf")` rule over the existing and WP18-future classes, the tracked-path scan, and the new native-floor, requests and workflow clauses.
- **JaCoCo.** No `domain.*` or `application.*` class is added, so `R/jacoco-class-floor.properties` is not routinely written by this WP; the T125 equality comparison reads it and, on a mismatch, the named edit of T125 step 3 repairs it (plan section 2, D-145, R-38).
- **Mission record.** `M/meta.json` stays complete; `M/status.json` is the materialisation of `M/status.events.jsonl` (`spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`), never hand-edited and no untracked CLI state committed blind (compare with the coordination copy first), so cutover-guard, the mission-state audit (`spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`, run locally before pushing any `M/**` change) and corpus-blocking pass (plan section 11, "The Mission record at each tip"). After PR A lands, `M/**` files already on `main` are frozen (interim default F1/E-12): this WP adds nothing to and modifies nothing under `M/**`; the orchestrator keeps status and tracer appends locally.

## Plan defects found

1. **Perf pin versus WP18 classes.** The existing pin names two required perf classes (`Nfr001OverviewLatencyTest`, `Nfr004SseConnectionsTest`) and the plan says T123 adds "the perf-class clauses". If that were read as naming `Nfr001DetailLatencyTest`/`Nfr002BoundedMemoryScenarioTest`, this WP's tip would be red (they are WP18's), and WP18 cannot edit the pin (not in its owned files or named edits). Resolution used here: the perf clause is left as it is (tag rule for every class, RATIO and CEILING for the two named classes); it is NOT widened to every class, because that fails on `Nfr004HeapMedianTest` and `Nfr009CacheGrowthTest` at this tip. Consequence: WP18's two classes are checked for RATIO and CEILING only by their own controls (the figures are asserted in the tests themselves), not by the pin. The orchestrator should confirm.
2. **AC-18.2 split across the two WPs.** The README (this WP) is written before `OutOfScopeRoutesTest` takes its final form (WP18, T128). The Java README test (`MissionStatusReadmeTest`) at this tip can assert only: nine routes listed, drift and Ops named as "no Java owner yet", and no path that `OutOfScopeRoutesTest` still asserts as 404 appears in the route list. The positive half (five routes non-404) is WP18's. The plan names no home for the AC-18.1 grep test; `MissionStatusReadmeTest` (Java, in the service test tree, ruling 2026-10-13) is proposed.
3. **Resolved (TASKS-GREEN-006): the D-145 comparison has one owner and a repair path.** This WP (T125 step 3) runs the equality comparison; WP18 re-runs it; a mismatch is repaired by a named edit of `R/jacoco-class-floor.properties` by the WP that found it. (Plan section 11 lists P1a to P12 as writers of the file, not P13: recorded as a deviation for the orchestrator.)

## Definition of Done

- Workflow: `LC_ALL=C.UTF-8` on the nightly start; two `--floor` literals equal `native_test_count()`; `--request-floor` equals the sum of stage floors (63 expected).
- `requests.json` stage `detail` with 14 requests; smoke child gets `LC_ALL=C.UTF-8` on non-Windows (unit-tested); `JvmReplayTest` green over the new stage.
- Five native-tagged plain `@Test` classes; `nativeTagJvmTest` green; pin and controls rewritten relative to the count.
- Compare script and its two test files cover all five routes, both `includePrompt` forms, per-file decode class, first difference as file/side/class, refused list as sole exemption.
- Pin file owns the new clauses with controls; README test green; README sections correct; NFR-006 grep clean.
- T125 gate recorded: Gate G, Gate P, the four architectural workflow tests (`test_ci_corpus_trigger_completeness.py`, `test_no_duplicate_suite_execution.py`, `test_workflow_coherence.py`, `test_module_shard_registry.py`), D-145 equality (this WP owns it), hygiene commands, nightly evidence (or a recorded operator refusal).
- C-009 and C-010 (constraints with no code): `git diff <PR A tip>..HEAD --stat` touches no `.kittify/charter` path and no file C-010 declares untouched; the diff stat is recorded in the PR "Tests run" section.
- SC-008 (reflexivity): its only check is the README divergence note (the V1 to V19 list and the note that the ledger and the Work Package files are read at slightly different instants, T124 step 2); `MissionStatusReadmeTest` asserts the note is present.
- Per-subtask evidence via `spec-kitty agent tasks mark-status T119 --status done` (and T120 to T125); commits are conventional commits.

## Risks

- A native leg that works on the JVM and fails in the image (hint miss): prove locally with `nativeCompile nativeTest nativeSmoke` first; fix only in `MissionStatusApplicationHints`.
- Listing bytes differing across legs (modification times, links): provisioning sets them; a leg reports `not run: link unsupported`, never a pass.
- Windows: a `LC_ALL` rule must not apply there; covered by `NativeSmokeLocaleTest`.
- The nightly job is untestable in CI before #5529 reaches `main`: the recorded local run is the evidence.
- The pin file is large (2737 lines): edit surgically, run the whole file after every clause.
- This WP mixes maintenance of existing Python pins and scripts (no new Python file; the README test is Java), workflow, README and Java test code; the Java parts follow the `java-jenny` conventions of neighbouring files.

## Reviewer Guidance

- Check commit grouping: each number change sits in the same commit as the tests that need it.
- Re-run `native_test_count()` and compare it with both workflow literals; confirm the controls no longer use literal 3.
- Confirm no golden is duplicated (`tree:` references) and no environment line appears on a native leg.
- Confirm `MissionStatusApplicationHints.java` is unchanged unless a failing native test is named.
- Check the comparison script cannot pass vacuously (empty corpus, zero files) and that the refused list is derived independently.
- Check the PR "Tests run" section carries the nightly counts and elapsed time, or the recorded refusal.

## Implementation command

`spec-kitty agent action implement WP17 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5`
