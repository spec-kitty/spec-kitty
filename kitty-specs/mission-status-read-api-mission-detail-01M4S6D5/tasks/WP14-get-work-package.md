---
work_package_id: WP14
title: '[PR B] P10 getWorkPackage and promptMarkdown (FR-002, FR-009)'
dependencies:
- WP13
requirement_refs:
- FR-002
- FR-009
- FR-008
- FR-012
- FR-020
- FR-022
- SC-004
- SC-005
- NFR-003
- NFR-004
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T09:30:41.569144+00:00'
subtasks:
- T098
- T099
- T100
- T101
- T102
- T103
- T104
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/WorkPackageQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/WorkPackageWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/WorkPackageMetaReadCountTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/WorkPackageServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/portlegs/WorkPackagePortLegsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/WorkPackageServedRouteTest.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/WorkPackageQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/WorkPackageWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/WorkPackageQueryService*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/WorkPackageMetaReadCountTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageController*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageMapper*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/WorkPackageServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/portlegs/WorkPackagePortLegsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/WorkPackageServedRouteTest.java
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP14 – [PR B] P10 getWorkPackage and promptMarkdown (FR-002, FR-009)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request: B (a draft), plan phase P10.** PR B = WP13 to WP18 (P9 to P13); it stacks on PR A (WP01 to WP12), which stacks on the branch that carries #5529's last slice. PR B cannot merge before PR A. #5533's Java work stacks on PR A, never on PR B. No agent pushes, opens or retargets a pull request.
- **External dependency (not a `dependencies` entry).** The re-cut tip of #5529 (the side-first layout) was merged into this branch by the orchestrator before WP01 started (C-005). If the re-cut is absent on your tree, stop and report.
- **Work package dependency.** WP13 (P9). That brings `MissionDetailQueryService`, `ReadinessDeriver`, `PhaseDeriver`, the first `config/*Wiring` of a route, the first real controller under `adapter.in.http.detail`, and the ownership of `OutOfScopeRoutesTest`. Through WP13 this work package also has WP05, WP06, WP10, WP11 and WP12 (the index and its body capture, `WpId.parse`, `HistoryOrder`, `HttpHarness#startWith`, `MetaReadCounter`, `ServedRoute`, `IncludePrompt`, `DetailRefusal`, `AdmissionGate`, the records).
- **Write scope: `owned_files` only** (frontmatter).
- **Named edits (out-of-map; not in `owned_files`).** For each: rebase first, state the edit in the commit message, touch nothing else of the file.
  - `S/README.md`, section **"Prompt text"** only (WP17 owns the file; other sections arrive as named edits from WP09 and WP16). Append or create that one section; touch no other line.
  - `J/domain/readmodel/detail/{WorkPackageView,ReviewView}.java`: the two records of this route (WP12 owns them). The shapes are final from the contract schemas (WP12 T082): the default is **no edit**. Edit a record only when this route's schema or golden proves a member missing or wrong; that is a named edit of WP12's file (accepted risk under the plan section 11 shared-file table, TASKS-DECOMP-003): rebase first, one record per commit, schema evidence in the commit message.
  - `T/adapter/in/http/rest/OutOfScopeRoutesTest.java`: one line, this route's own path (WP13 owns the file; removals are serialised by merge order with WP15 and WP16).
  - `R/jacoco-class-floor.properties` (two count lines; WP01 owns it; merge rule D-145). This work package appends **nothing** to `R/portlevel-tests.txt` (WP05's file): the port-level legs live outside `conformance.port` and are not listed (TASKS-GREEN-001; see the port-level subtask).
  - none in `M/**` (interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`; the orchestrator keeps the tracer and status appends locally).
- **Concurrency.** WP15 (P11) and WP16 (P12) run beside this work package with disjoint scopes. The later merge recounts JaCoCo on the merged tree and rebases `OutOfScopeRoutesTest`. **Merge order WP13 -> WP14 -> WP15 -> WP16** for the shared files `OutOfScopeRoutesTest.java` and `R/jacoco-class-floor.properties`: the orchestrator merges in that order and each later lane rebases onto the merged tree. Neither file has a git merge driver, so a conflict is real and is resolved by rule: in `OutOfScopeRoutesTest.java` keep the **intersection** of the remaining paths (a path removed by any lane stays removed); in the properties file take neither side, re-run the section 2 command on the merged tree and write what it prints. Nothing is claimed to merge silently.

Aliases used in this prompt (plan section 11, expanded to repo-relative paths): `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`.

Every layout path below is the **side-first layout of #5529's re-cut** (plan section 1.1, mapping table rows 1 to 13). The re-cut classes (`application/query/MissionStatusQueryService`, `application/query/ProjectionCache`, `application/query/port/in/**`, `application/query/port/out/**`, `domain/readmodel/**`, `domain/redaction/**`, the test mirror paths) **exist after the re-cut**, not in a checkout that lacks it. If a cited path is missing on your tree, the orchestrator has not merged the re-cut: STOP and report; never create the path, never "fix" it by using the flat checkout names. Paths of other work packages' classes (WP05 to WP12) exist after those work packages are on this branch; the work package list in the dependencies block says which.

---

## Objective

Serve `GET /api/v1/missions/{missionId}/work-packages/{wpId}` (`getWorkPackage`, FR-002) with the `WorkPackage` body, and its `promptMarkdown` member only when `includePrompt=true` (FR-009), byte-identical to the Python oracle's goldens, with the exact bytes of the authored prompt body, the admission gate for the prompt variant only, and the README section "Prompt text".

## Context

- **Authored plan from the file, resolved state from the ledger.** The shape and rules are those of `build_work_package` (`tests/contract/_mission_status_payloads.py`): `assignment` (seven handles), `subtasks` and `subtaskProgress` from the resolved map, `implementerOfRecord`, `lastTransitionAt`, `forceCount`, `lastEventId`, `actor` (three handles, `decode_actor` semantics as the existing `Actor` has it), `cancellation` only while the lane is `canceled`, `readiness`, `readyToStart`, `review.latestResult` and `review.override` (the partial-record rule of `review_override`), `history` (transitions only), `staleness` always `null`. Resolved state is **never** read from agent, assignee, shell, lane or review keys that old planning files still carry. `executionMode` has one pair of literal quotes stripped (`normalise_quoted`).
- **The history order.** `history` is ordered by the **parsed instant**, then `eventId` (`HistoryOrder`, WP05: `Z`, fractions and `+02:00` offsets sort by instant, not text). A stamp that is not an instant is row M7 (T13, 500 `projection_refused`; recorded divergence V18).
- **One read of the winning file (FRESH3-007, D-76).** The index record holds validated frontmatter fields and the file name, never the body. For `includePrompt=true` the body comes from **the same read and decode that indexed the winning file**: `WorkPackageIndex.build(mission, Optional<WpId> captureBodyOf)` keeps the body of the first valid file that holds the requested id and of no other. There is no second `WP_FILE` READ: the test records exactly one `WP_FILE` READ per candidate file for that request. The call with `includePrompt=false` passes `Optional.empty()` and holds no body.
- **`promptMarkdown` as authored (FR-009, deliberate exception, operator Q3).** Served unredacted, only on request. "As authored" is the body `FrontmatterManager.read` returns: the lines after the closing delimiter joined by `\n` after the newline translation of text mode, so CRLF and lone CR reach the client as LF; the Java side mirrors that and a golden pins the bytes. Every other text member of the same response is substituted (`title` has its host path replaced by `[path]` while `promptMarkdown` keeps the same path: AC-9.2). The guard is the loopback bind plus the Host and Origin filter, not the parameter alone. When `includePrompt` is absent or `false` the key `promptMarkdown` is **not in the JSON at all** (not null, not empty).
- **Admission gate for the prompt variant only (S-13, E-1, operator ruling D-148).** The service holds `AdmissionGate` (WP12, `Semaphore(4, true)`) and runs the request through it **only when `includePrompt=true`**: the with-prompt response holds the 1048577-byte read buffer, the decoded text, the captured body and the serialised JSON, about 11 MiB (NFR-002). `getWorkPackage` without a prompt is not gated.
- **Identifiers are typed (E-5, D-150).** The controller parses both path values with `MissionId.parse` and `WpId.parse` (WP12/WP05, `Optional`, never throw); an empty result is `DetailRefusal.notFound()`; rows C2 and W1 are 404, never 400. An id outside `WP[0-9]{2,}` or too long reaches no read of a Work Package file (AC-2.3).
- **Parameter.** `includePrompt` is parsed by `IncludePrompt` (WP12, `adapter.in.http.detail`): exactly `true` or `false`; `1`, `yes`, `TRUE`, the empty string or the parameter given twice is 400 `invalid_parameter` and no file is read (row W2, OQ-2); a malformed percent-encoding anywhere in the query is the status-only 400 that `ProblemAdvice` already gives.
- **Red-first form: red on the phase base.** On the base (WP13's tip) the route answers 404 and none of the route's classes exist.
- **Charter rules in force.** The squad belongs to the orchestrator. Every gate you add is non-vacuous. A red is classified under plan section 6, never retried to green.

---

### Subtask T098: Pre-flight and red-first tests

**Purpose**: Run the C-005 pre-flight and write the route's tests before any production class; AC-1.8 and the gate test first.

**Steps**:

1. Run the pre-flight (whole block, in order). Record the #5529 tip sha in the first commit message.

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

2. Create (new files, names fit the `owned_files` patterns):
   - `T/application/query/WorkPackageQueryServiceGateTest.java`: with `includePrompt=true` the call passes the gate (the gate's high-water mark reaches 4 under 16 concurrent calls whose reads block on a latch, then all complete); with `includePrompt=false` or absent the gate's mark stays 0 (the call is not gated). A test-only variant of the service that skips the gate for `includePrompt=true` must turn the mark-above-4 assertion red (AC-22.3 for this route).
   - `T/application/query/WorkPackageMetaReadCountTest.java` (AC-1.8): the matched Mission 3 reads warm and 4 cold, every other Mission exactly 1, first-sorted and last-sorted control, the stream control, a discovered-row floor. Extra assertion: for `includePrompt=true` exactly one `WP_FILE` READ per candidate file and none twice.
   - `T/application/query/WorkPackageQueryServiceTest.java`, `T/adapter/in/http/detail/WorkPackageControllerTest.java`, `T/adapter/in/http/detail/WorkPackageMapperTest.java`, `T/conformance/golden/served/WorkPackageServedRoute.java`: red now, completed in T099 to T102.
3. The red commit compiles: production classes exist only as shells whose bodies throw `UnsupportedOperationException`, so tests fail by assertion. No behaviour in the red commit.
4. Prove red on the phase base in a scratch worktree of WP13's tip (`git worktree add <scratch>/base <sha>`, copy the new tests in, run them). Never prove it by reverting in the working tree; never `git stash`; never run tests under `git rebase -x`.

**Files**: 6 new test files plus shells.

**Validation**: each class is red on the base for its stated reason; `CoupledSymbolsShapeTest` green on the tip.

---

### Subtask T099: `WorkPackageQueryService`

**Purpose**: The application service of the route, with the gate for the prompt variant and the one-read body capture.

**Steps**:

1. `J/application/query/WorkPackageQueryService.java`: `public final class WorkPackageQueryService implements WorkPackageQuery` (port `workPackage(MissionId, WpId, boolean includePrompt)`; public because `config` constructs it). Collaborators: the same set as `MissionDetailQueryService` (the `MissionReadModel`, the `WorkPackageIndex` bean of WP13, the diagnostics consumer) plus the shared `AdmissionGate` bean of `DetailInfrastructureWiring`. Read the signatures on the tips of WP11, WP12 and WP13.
2. Sequence: `MissionLookup#find`, duplicate continuation, `MissionReadModel#head(ref)` (3 reads warm, 4 cold; no `probed()`, no extra ledger call), then the index built with `Optional.of(wpId)` when `includePrompt` else `Optional.empty()`.
3. Resolve the Work Package in the index. A Work Package known only to the ledger is 404 `not_found` (W1); one whose only file has unusable frontmatter is 404 plus the `wp_file_skipped` diagnostic (AC-2.6); a later file with an already indexed id writes `wp_id_duplicate` and the first file is served (M6).
4. Build the result from the file's validated frontmatter (authored plan) and the snapshot (`MissionHead#entry`): resolved assignment, subtasks and `subtaskProgress` (**this service is the ordering owner of `subtasks`**, TASKS-FRESH3-001: it hands the mapper `WorkPackageView.subtasks` as the `List<Map.Entry<String, Lane>>` of WP12 T082, already sorted by `domain/model/CodePoints.compare` on the subtask id, AC-2.7; `CodePoints` is a non-record class that rule 15 forbids in `adapter.in.http.detail`, so only this application class and its unit tests use it), `implementerOfRecord`, `lastTransitionAt`, `forceCount`, `lastEventId`, `actor`, `cancellation` only while `canceled`, `readiness` and `readyToStart` through WP13's `ReadinessDeriver`, `review.latestResult` and `review.override` (a partial record is `null` for `override.at` per row T14/M14; a complete record with a junk `at` is M7), `history` ordered by `HistoryOrder`, `staleness` null. Human text members go through `Projector.human` (class 3: a credential or unremovable leak is M7, 500 `projection_refused`); strict members through `Projector.strict` (T5, T7, T8: `mergeTargetBranch` over 255 characters or a path-shaped value is `null` and 200, M14, **no diagnostic**).
5. Gate: wrap the body of the call in `gate.run(() -> ...)` **only** when `includePrompt` is true. Never hold the gate while waiting for a lock (there is none) and never catch the uninterruptible wait.
6. `promptMarkdown`: the captured body of the winning file, unprojected (no `Projector`, no `TextScreen`); absent from the record when `includePrompt` is false (use an `Optional`/nullable component that the mapper omits; not `null` in the JSON).
7. Faults: M3 `ledger_unparseable`/`ledger_torn_tail`, M4a `source_unreadable`, M10 `tasks/` not a directory, all as in the table of FR-012 (the index produces them; propagate `MissionStatusUnavailable` unchanged).

**Files**: `J/application/query/WorkPackageQueryService.java` (new, ~260 lines); `WorkPackageView` and `ReviewView` are final from the schemas (no routine edit).

**Validation**: `WorkPackageQueryServiceTest` (including the code-point order of `subtasks` on the `unicode-subtask-ids` fixture: `U+FF5E...` sorts before `U+1F600...` by code point though after it by UTF-16), `WorkPackageQueryServiceGateTest`, `WorkPackageMetaReadCountTest` green; AC-2.3 (no `WP_FILE` READ recorded for an ill-formed id) green.

---

### Subtask T100: Controller, mapper and wiring

**Purpose**: The HTTP edge: parsing, one call, status mapping, shaping.

**Steps**:

1. `J/adapter/in/http/detail/WorkPackageController.java`: `GET /api/v1/missions/{missionId}/work-packages/{wpId}` with the optional `includePrompt` request parameter. It holds only: `MissionId.parse` and `WpId.parse` (an empty result is `throw DetailRefusal.notFound()`), the `IncludePrompt` conversion of WP12 (`IncludePrompt.parse(List<String>)` returns `Optional<Boolean>`; an empty result is answered with `ProblemMapper.invalidParameter()` before any file is read; no exception type), one call `WorkPackageQuery#workPackage`, mapping through `WorkPackageMapper`. Status mapping is `ProblemMapper`/`ProblemAdvice` (WP12). Do not edit them.
2. `J/adapter/in/http/detail/WorkPackageMapper.java`: shapes the `WorkPackageView`/`ReviewView` records into the contract body (the generated model, or the hand `WorkPackage` DTO in `adapter/in/http/dto` only if the P2 spike (WP06) put it there; this work package creates **no** DTO package). The canonical writer sorts map entries by key in UTF-16 order (`ORDER_MAP_ENTRIES_BY_KEYS`); the open `subtasks` map must be emitted in **code-point order** (AC-2.7, fixture `unicode-subtask-ids`: keys whose UTF-16 and UTF-8 order differ), so the mapper writes the object from the **already ordered entry list** that `WorkPackageQueryService` put in `WorkPackageView.subtasks` (T099): a small `JsonSerializer` declared as a **private static nested class of `WorkPackageMapper`** (so no extra owned file) writes the entries in list order, as an object whose keys are the subtask ids and whose values are the `Lane` wire words. The mapper does no sorting and imports nothing outside rule 15: no `CodePoints`, no `PyText`, only Jackson, the JDK, the records and enums of `domain.model`, `domain.readmodel.detail` and the generated model. A mapper that omits `promptMarkdown` when it is absent must not write `null`.
3. `J/config/WorkPackageWiring.java`: one `@Configuration` with the `WorkPackageQuery` bean constructed from beans that exist (`MissionReadModel`, **the `WorkPackageIndex` bean of WP13's `MissionDetailWiring`**, `AdmissionGate`, diagnostics). Declare no `WorkPackageIndex` bean or private index factory (a second one is a duplicate-bean failure at the PR B merge; WP18's `SharedBeansUniqueTest` asserts exactly one). Do not edit `ServiceWiring`, `MissionDetailWiring` or `DetailInfrastructureWiring`.
4. Rules C2 and W1: per-route fixtures prove a malformed or unknown `missionId` and a malformed, unknown or ledger-only `wpId` answer **404 `not_found`, never 400**, through `HttpHarness#startWith` (WP10; do not edit the harness). Controller tests: foreign Host or Origin with `includePrompt=true` is 403 `request_refused`, the body holds no byte of the prompt and the instrumented port records no read (AC-9.3 for this route; the full-flow leg is WP18).
5. The mapper and controller depend, among project packages, only on what rule 15 admits: the records and enums of `domain.model`, `domain.readmodel.overview`, `domain.readmodel.detail`, the port packages and the generated model; no `domain.redaction`, no `domain.readmodel.derive`, and **no non-record class of `domain.model` (`CodePoints`, `PyText`)**. A mapper test (`unicode-subtask-ids`) proves the order from a hand-built view whose entries arrive ordered, and `ArchitectureRulesTest` rule 15 is green with a non-zero scanned count at this tip.

**Files**: `WorkPackageController.java` (~70 lines), `WorkPackageMapper.java` (~210 lines), `WorkPackageWiring.java` (~40 lines).

**Validation**: `WorkPackageControllerTest` and the row fixtures green; rules 3, 3b, 15, 16 green with their non-zero counts.

---

### Subtask T101: `promptMarkdown` exact bytes, parameter rules and README

**Purpose**: FR-009: the bytes, the guard and the documentation.

**Steps**:

1. Golden class `wp-prompt-bytes` (13 bodies, committed by WP07 under `R/conformance/wp-prompt-bytes/**`): a host path, an e-mail address, a near-miss token one character short, CRLF and lone-CR endings, trailing newline and none, U+2028, U+0085, a supplementary character, a quote and a backslash, an empty body and a 200000-byte body. The with-prompt response bytes equal the golden; the `false` request of the same fixture carries none of those bytes (AC-9.1). A full-length token in a prompt is asserted at test time against bytes computed in the test (DC-1), not from a committed fixture.
2. AC-9.2: in one response `title` shows `[path]` where `promptMarkdown` keeps the path.
3. AC-9.3: a foreign `Host`/`Origin` with `includePrompt=true` is 403, zero prompt bytes, zero reads; an accepted Host is 200 with the bytes.
4. AC-2.1/AC-2.2/AC-2.5: the with-prompt and without-prompt golden pair differs by exactly one member; the key is absent (not null) without the prompt; `1`, `yes`, `TRUE`, `` (empty) and a repeated `includePrompt` are 400 `invalid_parameter` with no file read; `true` on the same request is 200.
5. README: add the section **"Prompt text"** to `S/README.md` (a named edit; touch no other section). It names the exception to the leak projection and its guard; it contains the strings `includePrompt` and `Host and Origin`. Test `T/adapter/in/http/detail/WorkPackageControllerReadmePromptTextTest.java` (the name fits the `WorkPackageController*Test.java` pattern) reads the README and fails if the section is missing or lacks either string (AC-9.4). Revert row: delete the section or the string and it goes red.

**Files**: the README section (~15 lines), `WorkPackageControllerReadmePromptTextTest.java` (~40 lines), additions to the controller and mapper tests.

**Validation**: AC-9.1 to AC-9.4 green; the README test red on a scratch copy without the section.

---

### Subtask T102: Served route, AC-8.4 fixtures, mapper cases, stub leg

**Purpose**: Make `DetailGoldenSuiteTest` compare this route and pin its projection rows.

**Steps**:

1. `T/conformance/golden/served/WorkPackageServedRoute.java` implements WP10's `ServedRoute` (the shape, including the request-key and `includePrompt` conventions, is WP10 T071 step 1; there is no Javadoc to read and this work package does not edit that file). `goldenFiles()` is `{get-work-package.json, get-work-package-prompt.json}`; `served()` is `ServedRoutes.expectedEntries(goldenFiles())`: the request keys are the Work Package ids held by each golden, `body(entry, wpId)` is `GET .../work-packages/{wpId}` for `get-work-package.json` and the same URL with `includePrompt=true` for `get-work-package-prompt.json`. The classes that carry these goldens (the review checklist; the test of step 1b pins the derived set against this enumeration): for `get-work-package.json` `detail-populated` (8, including the fixture `unicode-subtask-ids`), **`detail-planning-only` (1, `planning-only`; TASKS-FRESH3-003)**, `wp-malformed-frontmatter` (28), `wp-duplicate-id` (3), `wp-two-selectors`, `wp-prompt-bytes` (13), **every fixture of the class `resolved-state` (WP08): the route emits exactly the resolved members those goldens pin and no other route could serve them, so this provider is their only server (WP18's `ServedRoutesCompleteTest` relies on it)**, and `projection-nulls`: `merge-target-branch-path` (T8) and `override-partial-junk-at` (T14); for `get-work-package-prompt.json` `detail-populated` and `wp-prompt-bytes` (the with-prompt twin of the without-prompt golden). **Java-only fixtures have no golden and are not entries**; this route's named tests cover them: `projection-refusals` (500 `projection_refused` plus one diagnostic): `history-at-not-instant` (T13), `history-event-id-leak` (T12), `owned-file-pattern-leak` (T7: `ownedFiles[]`, `requirementRefs[]`, `trackerRefs[]`), and `dependency-id-leak` (T5) again, first served by WP13.
1b. **Provider-loaded guard and provider-level completeness (TASKS-GREEN-002, TASKS-FRESH3-003).** `ServedRoutes` (WP10) treats a missing class as an empty route, so a mistyped provider name would leave the golden suite green with zero comparisons. Add `T/conformance/golden/served/WorkPackageServedRouteTest.java` (owned): it asserts that `ServedRoutes` (through the WP10 accessor of the providers actually loaded) loaded `WorkPackageServedRoute`, that `goldenFiles()` equals its `ServedRoutes.OWNER` row (`get-work-package.json` and `get-work-package-prompt.json`), and the **provider-level completeness assertion**: `served()` equals `ServedRoutes.expectedEntries(goldenFiles())`, i.e. every manifest fixture holding one of those golden files is served by this provider (a fixture-by-golden pair that no provider registers is red here even when the fixture is served for another operation, which the fixture-level `ServedRoutesCompleteTest` of WP18 alone cannot see) and its per-class counts match step 1 (in particular the `detail-planning-only` entry, the 28 `wp-malformed-frontmatter` entries and every `resolved-state` fixture). `ServedRoutesCompleteTest` stays WP18's whole-set floor.
2. Ten `@ProjectionRow` pairs in `WorkPackageMapperTest` (WP10's annotation): T5, T6, T7, T8, T10, T11, T12, T13, T14, T17 (T17: every `ActorHandle`: `assignment.*`, `implementerOfRecord`, `actor.*`, `latestResult.reviewer`, `override.actor`, `history[].actor`, null and never an error). T11 (`lastEventId`) is not separately reachable on a route that also carries `history[].eventId` and is pinned by its mapper case only. The discovered count of the class is 10.
3. AC-2.4: a ledger whose stamps mix `Z`, fractions and `+02:00`, ordered so that text order differs from instant order, lists `history` by instant (text order is red).
4. AC-2.6 rows C1 to C7, M1 to M3, M4a, M5 to M7, M10, M13, M14, W1 and W2 (M13 by the stub leg of step 5, M14 by the `projection-nulls` fixtures `merge-target-branch-path` and `override-partial-junk-at`; both also keep the identifier-precedence row: an ill-formed id with `includePrompt=1` is 404, S-27) each have a fixture at the port and at the HTTP leg; a permission-failure condition follows the D-32/D-101 two-leg rule (injected fault always; the real-permission leg behind `RealPermissionFixture.refusedForThisUser`, which records `not run: precondition unmet: <test id>` when the OS does not refuse).
5. AC-6.6 stub leg: with the `NameEncoding` stub, a non-ASCII `WP01-é.md` is served regardless of the host locale; tests needing a real non-ASCII file name call `Utf8Host.assumeUtf8()`.
6. AC-12.2/AC-12.4: one diagnostic line per occurrence (code, `mid8` or `none`), no absolute path, `HOME`, fixture root or canary in a line or in any Problem body; AC-8.3: a canary planted in a Work Package body, title and `lanes.json` appears only in the `promptMarkdown` of the `true` request (which proves the scan can see it).

**Files**: `WorkPackageServedRoute.java` (~110 lines), `WorkPackageMapperTest.java` (~260 lines), additions to the service and controller tests.

**Validation**: `DetailGoldenSuiteTest` green with this provider; ten pairs discovered; the unicode-key test red when the default UTF-16 map order is restored.

---

### Subtask T103: Shared-file edits: `OutOfScopeRoutesTest`, port-level, JaCoCo

**Purpose**: The three named edits.

**Steps**:

1. `T/adapter/in/http/rest/OutOfScopeRoutesTest.java`: **rebase and re-read the file first** (WP13 already removed the Mission path; WP15 and WP16 may have removed theirs). Remove only the line `"/api/v1/missions/01J01000000000000000000001/work-packages/WP01",` of `OUT_OF_SCOPE`. Do not remove the `/detail` line (WP15's). Touch nothing else.
2. Port-level legs (AC-13.3, FR-013): through WP12's `PlainCaller`, with no Spring context: `WorkPackageQuery#workPackage` returns the typed result for a populated Work Package with `includePrompt` true and false, throws `DetailRefusal.notFound()` for an unknown Work Package, and carries the `promptMarkdown` only in the first. The legs live in `T/application/query/portlegs/WorkPackagePortLegsTest.java` (new, owned; **outside** `conformance.port` and **not** listed in `R/portlevel-tests.txt`): `PortLevelClassSetTest` requires every class of `conformance.port` to depend on `PortSourceSelector` or `PortFixtures`, and `PortSubsetSecondLegTest` runs every listed id on an in-memory and a filesystem source through a selector fixture, which carries only `MissionStatusQuery` and cannot carry a detail port (TASKS-GREEN-001). Obtain the port from `DetailFixture` (WP10) behind `PlainCaller` (WP12). Append no line to `R/portlevel-tests.txt`; run `PortLevelClassSetTest` and `PortSubsetSecondLegTest` to show nothing changed.
3. JaCoCo recount on the merged tree. Expected shape (the command is the authority): `application` plus the classes you added (`WorkPackageQueryService` and any nested type); `domain` unchanged (this work package adds no `domain.*` class).

`R/jacoco-class-floor.properties` holds two count lines, `domain=` and `application=` (55 and 44 on the flat checkout; the numbers on your tree are whatever PR A's tip holds). This work package is **not** the owner of the file (WP01 is); it makes a **named edit**: rebase, state the edit in the commit message, touch nothing else of the file. The new number is **derived by command at the commit that adds the classes**, never typed from memory or from the "expected" figures in this prompt:

```bash
cd services/mission-status-api
./gradlew --no-daemon test jacocoTestReport
python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"
```

Write the two printed numbers into the two lines. The count is over `<class>` elements, so a nested record, enum or sealed variant you declare inside a counted class raises it too. `jacocoScopeCheck` has floor semantics (a stale or lowered count is not detected by design, D-65), so the review brief compares the diff of the file with the classes this work package added. **Merge rule (D-145):** lanes that run concurrently each derive a count on their own tree; the lane merged second rebases, re-runs the command on the merged tree and writes what it prints in a named-edit commit of its own. WP17 T125 owns the single D-145 equality comparison on the PR B tip and WP18 re-runs it; a mismatch is repaired by a named edit of this file by the WP that found it.

**Files**: `OutOfScopeRoutesTest.java` (one line), `jacoco-class-floor.properties` (the lines the command changes), `WorkPackagePortLegsTest.java` (~70 lines).

**Validation**: `OutOfScopeRoutesTest`, `PortLevelClassSetTest`, `PortSubsetSecondLegTest`, `PortLevelIdsTest`, `jacocoScopeCheck` green.

---

### Subtask T104: Gate

**Purpose**: Prove the work package at its tip.

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

2. Targeted surface that must be green: AC-2.1 to AC-2.7, AC-9.1 to AC-9.4, the class `wp-prompt-bytes` by `DetailGoldenSuiteTest`, `WorkPackageMetaReadCountTest` (AC-1.8), `WorkPackageQueryServiceGateTest`, the route's fixtures registered in `WorkPackageServedRoute` (including the AC-8.4 fixtures of T102), the ten mapper pairs, the stub leg of AC-6.6, AC-12.1 rows of the route, `PortLevelClassSetTest`, `PortSubsetSecondLegTest` (both named explicitly in the Gate G run: they fail on a class or id that opens no selector fixture), `WorkPackageServedRouteTest`, `OutOfScopeRoutesTest`, the ArchUnit rules. NFR-006 terminology grep of plan section 5 (expect only the marked legacy `feature_slug` literal of `LanesCodec`, WP11; any other hit is a defect): `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md`.
3. Revert-fails rows (standing named tests): AC-2.1 comparator control (perturb one byte of a with-prompt or without-prompt golden; drop `promptMarkdown` from the with-prompt answer and the "differs by exactly one member" control goes red); AC-2.2/AC-2.5 (always write `promptMarkdown` null, accept `1`/`yes`/`TRUE`, read the file twice for the prompt: the FRESH3-007 count goes red); AC-2.3 (read the Work Package file before validating the id: the recorded-access assertion goes red); AC-2.4 (sort `history` by text); AC-2.6 (answer a ledger-only Work Package 200, or the unusable-frontmatter file 404 without its diagnostic); AC-2.7 (UTF-16 key order of `subtasks`: `unicode-subtask-ids` red); AC-9.1 to AC-9.3 (redact `promptMarkdown`; translate no newlines; serve a prompt to a foreign Host); AC-9.4 (delete the README section or `Host and Origin`); AC-22 (skip the gate for `includePrompt=true`: the `...GateTest` goes red); typed identifiers (let an empty parse reach the service or map it to 400: the C2/W1 fixtures go red).
4. Do not write to `M/**` (interim default F1/E-12). Put the tracer entry text in your hand-off report; the orchestrator appends it locally.

- **Public repository hygiene (C-006).** No home-directory path, user name, address or token in any file, fixture, test name or commit message. Use the placeholders `<repo>` and `<scratch>`. Credential-shaped test inputs are assembled at test time from two fragments (prefix and body) in a temporary directory; a committed fixture holds at most a near-miss one character short (D-48). Terminology: say Mission and Work Package, never "feature" in new prose (NFR-006; the grep of plan section 5 shows only the marked legacy `feature_slug` literal of `LanesCodec`).
- **Tracer entry (charter standing order 3).** Not written by this work package: interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`. Draft the entry (approach, deviations, and for WP15/WP16 the `@PermissionCase` ids) in the hand-off report; the orchestrator appends it to `M/traces/approach.md` locally.

**Validation**: Gate G and Gate P green; `git status` shows only `owned_files` plus the named edits.

---

## Self-contained green

PR B is a draft that must be green at this work package's tip and at its own tip (plan section 11, "Each PR is self-contained and green", D-153).

- **Fixtures live with their tests.** The goldens and fixture trees (`R/conformance/**`: the classes `wp-prompt-bytes`, `projection-nulls`, `projection-refusals`, `wp-*`, `detail-populated` (whose fixture `unicode-subtask-ids` is one of its eight), `detail-planning-only` and `resolved-state`) were committed by WP07 and are registered here by `WorkPackageServedRoute`; this work package adds none. Links come from `PROVISION_PLAN` (WP10). Credential-shaped strings are assembled at test time; the committed near-miss is one character short (D-48).
- **Floors and counts satisfiable here.** JaCoCo: recounted at the commit that adds `WorkPackageQueryService`; the per-class 0.90 line gate holds because the service tests cover it. Ten `@ProjectionRow` pairs are discovered in this class; the 26-pair `ProjectionRowCoverageTest` is WP18's and does not exist yet. The `PermissionCaseFloorTest` (WP18) floor of four ids is not yet satisfiable (WP15 and WP16 write those tests), so no earlier test may assert it. The native floors (`--floor 3`, `--request-floor 49`) and `R/nativesmoke/requests.json` are unchanged: no `@Tag("native")` test and no smoke stage here (D-99); WP17 raises them in the commits that need them.
- **No test or gate names a type of a later work package.** The route uses types of WP05 to WP13 only. `OutOfScopeRoutesTest` still asserts 404 for the paths of WP15 and WP16 and the unserved paths; `ServedRoutes` treats a missing provider as an empty route; `ServedRoutesCompleteTest` is WP18 and absent.
- **The pin `tests/ci/test_mission_status_api_build.py` stays green (Gate P):** rule-9 literals (the `api` and `model` packages unchanged); the `adapter/in/http` sub-directory clause (`detail` only; **no `dto` directory created here**); the `EventsController` needles (not touched); the models list and the drift probe (WP06's; if a hand DTO exists it is WP06's); `@Tag("perf")` (none); the tracked-path scan (no `:` or `$` in a new path; stage new files first); the probe list (WP01's); native-tag and `requests.json` clauses (numbers unchanged); the partition pin (no new source set).
- **Mission record.** `M/meta.json` is complete and untouched. Under interim default F1/E-12 this work package commits nothing under `M/**`: the orchestrator keeps the `M/status.json` materialisation and the tracer appends locally. `M/status.json` is the materialisation of `M/status.events.jsonl` (`.venv/bin/spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`), never hand-edited; do not commit untracked CLI state blind (compare with the coordination copy first). Lane transitions are made with `spec-kitty agent tasks move-task`, never by editing a file. With the record intact `cutover-guard`, the mission-state audit (`.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`) and the corpus-blocking job stay green. This work package writes nothing under `M/**` (interim default F1/E-12).

---

## Plan defects found

1. **Resolved (TASKS-DECOMP-009, TASKS-ORDER-004, TASKS-COVER-001): `WorkPackagePortLegsTest` is owned by this work package** (wps.yaml and the frontmatter `owned_files`/`create_intent`; it lives in `T/application/query/portlegs/`, outside `conformance.port`, and is not listed in `R/portlevel-tests.txt`). Nothing is out-of-map and nothing is asked of the orchestrator.
2. **Wording of the shared-file table versus the gate list.** The plan's traceability row for FR-009 assigns the guard flow (AC-9.3) to P13, while the P10 gate lists AC-9.1 to AC-9.4. This prompt tests AC-9.3 for this route at the controller level (foreign Host, zero reads) and leaves the multi-route flow to WP18, whose T126 holds the shared-rig `getWorkPackage?includePrompt=true` target with the AC-9.3 assertion; the reviewer should not demand more or less.
3. **A reflection-hint miss from this route has no named-edit permission** (see WP13 item 2): `MissionStatusApplicationHints` may be edited by P6, P8 (named) and P13 only. A proven native miss is an orchestrator item. **RULED: OO-3 (orchestrator ruling 2026-10-13, binding; formerly TASKS-COVER-009 item 3).** Of the PR B work packages only WP17 edits `J/config/MissionStatusApplicationHints.java`. WP13 to WP16 do not edit it: on a locally proven native reflection-hint miss (`nativeCompile nativeTest nativeSmoke`) this work package STOPS and reports the miss to the orchestrator, who routes the hint to WP17. The JaCoCo recount stays a named edit under the plan's merge rule (D-145).

## Definition of Done

Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.

- T098: pre-flight green and recorded; every new test red on the base for its stated reason; shells compile.
- T099: `WorkPackageQueryService` follows lookup, duplicate continuation, `head`, index; the body is captured in the one read; the gate applies to `includePrompt=true` only; `WorkPackageMetaReadCountTest` and `WorkPackageQueryServiceGateTest` green.
- T100: controller, mapper and wiring hold no logic; C2 and W1 are 404; `subtasks` keys in code-point order; rules 3, 3b, 15, 16 green.
- T101: AC-9.1 to AC-9.4 green; README section "Prompt text" present with `includePrompt` and `Host and Origin`; the key absent without the prompt.
- T102: route registered and `WorkPackageServedRouteTest` green (provider loaded; `goldenFiles()` equals its `OWNER` row; `served()` equals the manifest-derived `expectedEntries`); ten `@ProjectionRow` pairs discovered; the AC-8.4 fixtures served; history ordered by instant; no path or canary in any line or Problem.
- T103: one line removed from `OutOfScopeRoutesTest` (the `WP01` path only); no line appended to `R/portlevel-tests.txt` (the legs are in the owned `WorkPackagePortLegsTest`); JaCoCo lines equal the command's output.
- T104: Gate G and Gate P green; tracer entry text in the hand-off report; no `M/**` write; no write outside `owned_files` and the named edits.

## Risks

- **A second read of the winning file** for the prompt (a "simple" re-read) breaks the one-READ count and AC-7.4. Mitigation: use the body the index captured.
- **`promptMarkdown` written as null** or redacted. Mitigation: the key-absence and exact-bytes tests.
- **Gate scope drift.** Gating the prompt-less call, or not gating the prompt call. Mitigation: `WorkPackageQueryServiceGateTest` asserts both directions.
- **UTF-16 map order of `subtasks`.** The default canonical writer would reorder keys of a `Map`. Mitigation: the view carries an ordered entry list built under `CodePoints.compare` in the application service, the mapper serialises it in list order (no `domain.model` class outside records and enums, rule 15); `unicode-subtask-ids` red-first.
- **Concurrent lanes.** WP15 and WP16 edit `OutOfScopeRoutesTest` and JaCoCo. Mitigation: merge order WP13 -> WP14 -> WP15 -> WP16 and the conflict rule of the Concurrency bullet.
- **Large response.** The 200000-byte prompt and the roughly 11 MiB peak: do not hold more than one read buffer; do not log the prompt.

## Reviewer Guidance

- Verify the **red-first form** (scratch worktree of WP13's tip), and that no assertion was weakened to reach green.
- Check the single read: a test records exactly one `WP_FILE` READ per candidate file for the prompt request.
- Check the gate is held for `includePrompt=true` only, in the service, never in the controller.
- Check the exact-bytes goldens and that `title` is substituted while `promptMarkdown` is not.
- Check `OutOfScopeRoutesTest` lost exactly one line, the README edit is the one section, `R/portlevel-tests.txt` is untouched, and the JaCoCo lines match the command run on the tip.
- Check the architectural gates implicated by the touched files by file (rules 3, 3b, 7, 15, 16, `PortLevelClassSetTest`, `PortSubsetSecondLegTest`).
- Look for host paths, user names or tokens in tests, fixtures, README and commit messages.

## Implementation command

```bash
spec-kitty agent action implement WP14 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
