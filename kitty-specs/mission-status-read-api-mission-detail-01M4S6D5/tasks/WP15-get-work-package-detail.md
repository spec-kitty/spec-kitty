---
work_package_id: WP15
title: '[PR B] P11 getWorkPackageDetail (FR-003, FR-010)'
dependencies:
- WP13
requirement_refs:
- FR-003
- FR-010
- FR-008
- FR-012
- FR-022
- SC-004
- NFR-003
- NFR-004
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T09:31:49.705346+00:00'
subtasks:
- T105
- T106
- T107
- T108
- T109
- T110
- T111
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/WorkPackageDetailQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/TitleRows.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/LaneNames.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/OwnedFilePatterns.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/CycleNames.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageDetailController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageDetailMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/WorkPackageDetailWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/WorkPackageDetailServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/portlegs/WorkPackageDetailPortLegsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/WorkPackageDetailServedRouteTest.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/WorkPackageDetailQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/detail/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/TitleRows.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/LaneNames.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/OwnedFilePatterns.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/CycleNames.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageDetailController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageDetailMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/WorkPackageDetailWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/WorkPackageDetail*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/detail/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/TitleRows*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/LaneNames*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/OwnedFilePatterns*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/CycleNames*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/detail/WorkPackageDetail*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/WorkPackageDetailServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/portlegs/WorkPackageDetailPortLegsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/WorkPackageDetailServedRouteTest.java
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP15 – [PR B] P11 getWorkPackageDetail (FR-003, FR-010)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request: B (a draft), plan phase P11.** PR B = WP13 to WP18 (P9 to P13); it stacks on PR A (WP01 to WP12), which stacks on the branch that carries #5529's last slice. PR B cannot merge before PR A. #5533's Java work stacks on PR A, never on PR B. No agent pushes, opens or retargets a pull request.
- **External dependency (not a `dependencies` entry).** The re-cut tip of #5529 (the side-first layout) was merged into this branch by the orchestrator before WP01 started (C-005). If the re-cut is absent on your tree, stop and report.
- **Work package dependency.** WP13 (P9): `MissionDetailQueryService`, `ReadinessDeriver`, the wiring and controller pattern, the ownership of `OutOfScopeRoutesTest`. Through WP13 this work package has WP05 (resolved state, `HistoryOrder`), WP06, WP09 (P5: `TextSource` and its vocabulary, `Eligibility`, `ArtifactPaths`, `ArtifactKinds`, `TextScreen`, the `WORKTREE_LANE` and `WORKTREE_LANE_GIT` classes of the fence), WP10 (harness, `Utf8Host`, `RealPermissionFixture`, `@PermissionCase`), WP11 (decoders `FrontmatterDecoder` and `LanesDecoder`, the index), and WP12 (the port `WorkPackageDetailQuery`, `DetailRefusal`, `AdmissionGate`, the records).
- **Write scope: `owned_files` only** (frontmatter).
- **Named edits (out-of-map; not in `owned_files`).** For each: rebase first, state the edit in the commit message, touch nothing else of the file.
  - `J/domain/readmodel/detail/{WorkPackageDetail,SubtaskEntry,DependencyEntry,ReviewCycleEntry,WorkspaceView,OwnedFileEntry,ArtifactReferences,ArtifactReference}.java`: the eight records of this route (WP12 owns them). The shapes are final from the contract schemas (WP12 T082): the default is **no edit**. Edit a record only when this route's schema or golden proves a member missing or wrong; that is a named edit of WP12's file (accepted risk under the plan section 11 shared-file table, TASKS-DECOMP-003): rebase first, one record per commit, schema evidence in the commit message.
  - `T/adapter/in/http/rest/OutOfScopeRoutesTest.java`: one line, this route's own path (WP13 owns the file; removals are serialised by merge order with WP14 and WP16).
  - `R/jacoco-class-floor.properties` (two count lines; WP01 owns it; merge rule D-145). This work package appends **nothing** to `R/portlevel-tests.txt` (WP05's file): the port-level legs live outside `conformance.port` and are not listed (TASKS-GREEN-001; see the port-level subtask).
  - none in `M/**` (interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`; the orchestrator keeps the tracer and status appends locally).
- **Concurrency.** WP14 (P10) and WP16 (P12) run beside this work package with disjoint scopes. The later merge recounts JaCoCo and rebases `OutOfScopeRoutesTest`. **Merge order WP13 -> WP14 -> WP15 -> WP16** for the shared files `OutOfScopeRoutesTest.java` and `R/jacoco-class-floor.properties`: the orchestrator merges in that order and each later lane rebases onto the merged tree. Neither file has a git merge driver, so a conflict is real and is resolved by rule: in `OutOfScopeRoutesTest.java` keep the **intersection** of the remaining paths (a path removed by any lane stays removed); in the properties file take neither side, re-run the section 2 command on the merged tree and write what it prints. Nothing is claimed to merge silently.

Aliases used in this prompt (plan section 11, expanded to repo-relative paths): `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`.

Every layout path below is the **side-first layout of #5529's re-cut** (plan section 1.1, mapping table rows 1 to 13). The re-cut classes (`application/query/MissionStatusQueryService`, `application/query/ProjectionCache`, `application/query/port/in/**`, `application/query/port/out/**`, `domain/readmodel/**`, `domain/redaction/**`, the test mirror paths) **exist after the re-cut**, not in a checkout that lacks it. If a cited path is missing on your tree, the orchestrator has not merged the re-cut: STOP and report; never create the path, never "fix" it by using the flat checkout names. Paths of other work packages' classes (WP05 to WP12) exist after those work packages are on this branch; the work package list in the dependencies block says which.

---

## Objective

Serve `GET /api/v1/missions/{missionId}/work-packages/{wpId}/detail` (`getWorkPackageDetail`, FR-003) with the closed, self-contained `WorkPackageDetail` body (subtasks, dependencies, review cycles, workspace, owned files, artifact references), `changeState` always `unknown` and `worktreePresent` from a stat-only read (FR-010), byte-identical to the oracle's goldens for every fixture class, behind the admission gate.

## Context

- **Composition.** The route composes the shared index (WP11), the snapshot of `MissionHead#entry` (WP13's path, `MissionReadModel#head`; no `probed()`, no second stamp: 3 reads of the matched `meta.json` warm, 4 cold; every other Mission once), and these sources: `tasks.md` (subtask titles), the dependency files' display titles (from the index), `tasks/<wp-slug>/review-cycle-<N>.md` files, `lanes.json`, a stat of `.worktrees/<recorded slug>-<lane id>`, and a directory read of `tasks/`.
- **Fail loud (FR-012).** Rows M4b (`tasks.md` over 4 MiB, not UTF-8 or unreadable; a review-cycle directory unlistable; a `.worktrees` stat that fails other than absent), M9 (an `lstat` of a path component of the artifact references fails other than absent), M11 (a review-cycle file over 262144 bytes or one that does not parse: a **200 with null members**, no diagnostic), M12 (a subtask or dependency title holding a credential: 200 with the title withheld or replaced, plus `projection_refused`), W3 (`lanes.json` corrupt, legacy `feature_slug` shape, or over 1 MiB: 500 `source_unreadable`, one `source_unreadable` diagnostic per request), W1 (ill-formed, unknown or ledger-only `wpId`: 404). On the detail route a refusal that other routes call `projection_refused` is 500 `source_unreadable` (M7).
- **The gate.** `getWorkPackageDetail` is one of the heavy operations (FR-022): the whole call runs inside `AdmissionGate#run` (WP12; a fair `Semaphore(4, true)`; never refuses, never times out).
- **Identifiers are typed (E-5, D-150).** The controller parses `missionId` and `wpId` with `MissionId.parse` and `WpId.parse`; an empty result is `DetailRefusal.notFound()`; rows C2 and W1 are 404, never 400.
- **Pre-existing helpers at the checkout.** `domain/model/PyText.java` (`strip`, `isBlank`, `nullIfEmpty`: the existing port of Python's whitespace class, which `TitleRows` must use, never `String.strip`) and `domain/model/CodePoints.java` (`compare`). Both are in `domain.model`, which the re-cut leaves unchanged.
- **Not opening files for references (AC-3.6).** `artifactReferences` are pointers found by one read of the `tasks/` directory and a `lstat` of each path component; no file is opened. The review-cycle files are opened (for `reviewedAt` and `reviewer`) but `artifactPath` is decided by `Eligibility` and `ArtifactPaths` of WP09, not by opening.
- **Red-first form: red on the phase base.** On the base (WP13's tip) the route answers 404 and none of this route's classes exist.
- **Charter rules in force.** The squad belongs to the orchestrator. Every gate you add is non-vacuous. A red is classified under plan section 6, never retried to green.

---

### Subtask T105: Pre-flight and red-first tests

**Purpose**: Run the C-005 pre-flight, then write the gate test, the read-count test and the permission cases before any production class.

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

2. Create (new files; names fit the `owned_files` patterns):
   - `T/application/query/WorkPackageDetailQueryServiceGateTest.java`: 16 concurrent calls whose reads block on a latch; the gate's high-water mark equals 4; releasing the latch completes all with normal results; a test-only variant that skips the gate turns the "mark above 4" assertion red (AC-22.3 for this route).
   - `T/application/query/WorkPackageDetailMetaReadCountTest.java` (AC-1.8): the matched Mission 3 reads warm, 4 cold; every other Mission once; last-sorted control; the stream control; a discovered-row floor.
   - `T/application/query/WorkPackageDetailPermissionTest.java`: the permission cases of AC-10.3 and rows M4b/M9, **both legs under D-101**: (a) fault injection through the recorder (`failWhen` with an `AccessDeniedException`, any user, any OS) and (b) the real file system behind `RealPermissionFixture.refusedForThisUser(path)`, which skips by assumption and records `not run: precondition unmet: <test id>` when the OS does not refuse (root runner, Windows). Mark both legs of a case with `@PermissionCase("<id>")` (WP10); an id has exactly one injected-fault test and one real-permission test. Use exactly **two** distinct ids of the form `AC-10.3/<case>` (WP15 writes two, WP16 two: the floor of four of WP18 is 2+2) and write them into the tracer entry: WP18's `PermissionCaseFloorTest` asserts a floor of four ids over WP15 and WP16 together.
   - `T/application/query/WorkPackageDetailQueryServiceTest.java`, `T/adapter/in/http/detail/WorkPackageDetailControllerTest.java`, `T/adapter/in/http/detail/WorkPackageDetailMapperTest.java`, `T/conformance/golden/served/WorkPackageDetailServedRoute.java`: red now, completed in T106 to T109.
3. The red commit compiles: production classes exist only as shells that throw `UnsupportedOperationException`. No behaviour in the red commit.
4. Prove red on the phase base in a scratch worktree of WP13's tip (`git worktree add <scratch>/base <sha>`; copy the new tests in; run them). Never prove red by reverting in the working tree; never `git stash`; never run tests under `git rebase -x`.

**Files**: 7 new test files plus shells.

**Validation**: each class is red on the base for its stated reason; `CoupledSymbolsShapeTest` green on the tip.

---

### Subtask T106: Service, `TasksMdReader`, `TitleRows`, `ReviewCycleReader`, `CycleNames`

**Purpose**: The application service and the subtask, dependency and review-cycle sources.

**Steps**:

1. `J/application/query/WorkPackageDetailQueryService.java`: `public final class WorkPackageDetailQueryService implements WorkPackageDetailQuery` (`workPackageDetail(MissionId, WpId)`); public because `config` constructs it. Wrap the whole call in `gate.run(...)`. Sequence: `MissionLookup#find`, duplicate continuation, `MissionReadModel#head(ref)`, the index with `Optional.empty()` (this route holds no body), then the readers below. Collaborators come from beans that exist; read the signatures on the tips of WP09 to WP13.
2. `J/application/query/detail/TasksMdReader.java`: `TextSource#readText(FileRef.MissionFile(ref, RelativePath.of("tasks.md")), 4194304, ReadScope.AUTHORED)`. `Text` goes to `TitleRows`; `Absent` gives no titles (null `title`); `OverCap` (including a file that grows during the read), `NotText` (invalid UTF-8) or a thrown `TextFault` is 500 `source_unreadable` (M4b). The cap is applied by the port by bytes read, never by a size read earlier (AC-3.4, AC-3.9).
3. `J/domain/readmodel/derive/TitleRows.java` (pure; mirrors the oracle's `title_rows` and `read_tasks_md`): the text is decoded strictly (done by the adapter), a leading byte order mark **stays** (a heading on the first line then does not match), there is **no newline translation**: split on `\n` only, so a `\r` stays at the end of a CRLF line and inside a title and is removed only where Python's `str.strip` removes it. Every `strip`, `lstrip` and cell trim uses `domain.model.PyText.strip` (Unicode whitespace including U+00A0, U+0085, U+2028), never `String.strip`; `\bWP\d{2,}\b` and `T\d{3,}` use Python's Unicode word boundary and Unicode decimal digits (compile with `Pattern.UNICODE_CHARACTER_CLASS`; an Arabic-Indic digit is a digit). Section rules: a section opens at the heading whose first `WP` token is this Work Package and closes for good at the next heading naming another (a heading that re-opens a closed section does not re-open); fenced blocks hold no rows; a checkbox row belongs to its section; a table row belongs to the Work Package its cells name, else to its section; the first row of an id wins; `[P]` and one `**` pair are stripped. Read `_mission_status_detail.py` (`title_rows`) next to the code; the golden class `tasks-md` is the arbiter.
4. `J/domain/readmodel/derive/CycleNames.java`: the file-name rule of review-cycle files and their numeric parse (cycle 10 follows cycle 9; `review-cycle-01.md` is not a cycle file by the artifact classifier of AC-5.8 and must agree with the oracle). Port the rule from the oracle, not from this prompt.
5. `J/application/query/detail/ReviewCycleReader.java`: `tasks/<wp-slug>/review-cycle-<N>.md` of the **primary** directory, `<wp-slug>` the stem of the Work Package's prompt file; no prompt file means no cycles. `tasks/` and `tasks/<wp-slug>` must be real directories (`lstat`; a link is not entered: AC-3.3, an empty list); a directory that cannot be listed is M4b. Order ascending by `cycleNumber` numerically. A symlinked cycle file is an entry with null members and a null `artifactPath`; its target is never read. Each regular file is read with `readBytes(file, 262144, AUTHORED)` and decoded by `FrontmatterDecoder#decodeReviewCycle(byte[])`: over the cap or unparseable is still an entry with null `reviewedAt` and `reviewer` and **no diagnostic** (M11, AC-3.9: 262144 bytes parsed, 262145 not). `reviewedAt` is the file's value when an RFC 3339 date-time else null (T15, M14); `reviewer` is the handle projection (T17); `feedbackReference` is the `review-cycle://` pointer, null when the product's builder or validator refuses a segment or the contract pattern does (T16); `artifactPath` is null when the file is not an eligible artifact (`Eligibility`, `ArtifactPaths`); **`verdict` is read from the ledger** (the last status event of this Work Package whose trimmed `review_result.reference` equals the cycle's pointer), never from the file (AC-3.2; a cycle whose pointer matches no event has a null verdict).
6. Subtask entries: the authored roster in authored order; `title` from `TitleRows` (a title holding a credential or an unremovable leak is `null` and writes one `projection_refused` diagnostic, class 1 withhold, M12; a title holding only a host path is `[path]` and writes none); `statusLane` is the resolved subtask lane, null when none is recorded (never `planned`). Dependency entries: authored order; `title` is the dependency's display title from the index else its id (a credential or unremovable leak: the id plus one `projection_refused`, class 2); an id naming no Work Package keeps its id as title and a null lane.

**Files**: `WorkPackageDetailQueryService.java` (~250 lines), `TasksMdReader.java` (~70), `TitleRows.java` (~160), `CycleNames.java` (~50), `ReviewCycleReader.java` (~170), (the eight records are final from the schemas; no routine edit).

**Validation**: AC-3.2, AC-3.3, AC-3.4, AC-3.7, AC-3.9 and the `tasks-md`/`cycles` goldens green; ASCII `\d`, `String.strip`, `BufferedReader` or newline translation each turn the `tasks-md` class red.

---

### Subtask T107: `WorkspaceReader`, `LaneNames`, `OwnedFilePatterns`, `ArtifactReferenceBuilder`

**Purpose**: The workspace, owned-file and artifact-reference sources, none of which runs a process or opens a pointed-to file.

**Steps**:

1. `J/domain/readmodel/derive/LaneNames.java`: ports of `lane_branch_name` (`src/specify_cli/lanes/branch_naming.py`: the planning lane yields no branch) and `worktree_dir_name`; the recorded slug is verbatim. A `laneId` or `laneBranch` that fails the contract's pattern or length is `null` with 200 (T9, M14, no diagnostic); a `planningBranch` over 255 characters or path-shaped is `null` (T8, M14).
2. `J/application/query/detail/WorkspaceReader.java`: read `lanes.json` of the primary directory whenever the route runs (`readBytes(..., 1048576, AUTHORED)`, `SafeFiles.SMALL_FILE_MAX`; this route applies the cap itself whatever the classification read of #5529 does with an over-cap file) and decode with `LanesDecoder#decode(byte[])` into `LanesResult`: `Manifest` is used; `Corrupt`, `Legacy` (the `feature_slug` shape with no `mission_slug`, SK-351) and `OverCap` are 500 `source_unreadable` for **every** Work Package of that Mission, with one `source_unreadable` diagnostic per request (W3, AC-3.5, AC-3.9: 1048576 bytes read, 1048577 refused). A missing `lanes.json`, or a Work Package in no lane, gives null lane members and `worktreePresent` false. `planningBranch` comes from the authored file.
3. `worktreePresent` (FR-010, D-75): true exactly when the Work Package is in a code lane (`laneId` neither null nor `lane-planning`) **and** `.worktrees/<recorded slug>-<lane id>` (composed as `worktree_dir_name` composes it, under the project root: `FileRef.ProjectFile`) is a real directory (`lstat`, not a link) **and** its `.git` entry exists as a regular file or a directory, **not a symbolic link or reparse point** (`lstat`, never followed). Stat only: nothing under the directory is listed or read. A stat that fails for a reason other than "absent" is 500 `source_unreadable` (M4b/FR-010). `changeState` is never computed.
4. `J/domain/readmodel/derive/OwnedFilePatterns.java`: port of `is_glob_pattern` (`src/specify_cli/ownership/validation.py`); `{pattern, isGlob, changeState}` entries in authored order, `changeState` the constant `unknown` (AC-10.1). A `pattern` that is not a showable `RelativeReference` is M7 (T7, 500 `source_unreadable` on the detail route).
5. `J/application/query/detail/ArtifactReferenceBuilder.java`: one `TextSource#list` of `tasks/` (bounded by a `nameLimit`) and a `lstat` of each path component, then pointers for `prompt` and `spec`: the prompt file is the first regular non-symlink `tasks/WP[0-9]{2,}-*.md` in byte order (`CodePoints.compare`) whose name starts with `<wpId>-`; eligibility and the artifact path come from `Eligibility` and `ArtifactPaths` (WP09). No file is opened (AC-3.6: the recorded access shows the directory read and the `lstat`s, no READ of the prompt file or of `spec.md`). An `lstat` that fails other than "absent" is M9, 500 `source_unreadable`.
6. Visibility: `Eligibility` lives in `application.query.artifact`; `ArtifactReferenceBuilder` lives in `application.query.detail`. `Eligibility` is `public` by WP09 T061 step 4 (consumed from this package); use it as is.

**Files**: `LaneNames.java` (~70), `OwnedFilePatterns.java` (~60), `WorkspaceReader.java` (~140), `ArtifactReferenceBuilder.java` (~120).

**Validation**: `worktree-states` (7 fixtures), the false rows also under `NO_WORKTREES`, the symbolic-link rows (V7: Java refuses a link, the oracle follows it), and the recorded-access tests (STAT only on the two paths; no LIST or READ below `.worktrees/<..>/`) green; stat with link-following turns `git-entry-symlink` red.

---

### Subtask T108: Controller, mapper and wiring

**Purpose**: The HTTP edge of the route, holding no logic.

**Steps**:

1. `J/adapter/in/http/detail/WorkPackageDetailController.java`: `GET /api/v1/missions/{missionId}/work-packages/{wpId}/detail`. It holds only: `MissionId.parse` and `WpId.parse` (an empty result is `throw DetailRefusal.notFound()`), one call `WorkPackageDetailQuery#workPackageDetail`, mapping through `WorkPackageDetailMapper`. The status mapping is `ProblemMapper`/`ProblemAdvice` (WP12); do not edit them.
2. `J/adapter/in/http/detail/WorkPackageDetailMapper.java`: shapes the records into the contract body (the generated model, or a hand DTO only if WP06 put one in `adapter/in/http/dto`; this work package creates **no** DTO package). It imports nothing from `domain.readmodel.derive`, `domain.redaction` or `application..` other than `application.query.port.in..` (rule 15). Every array is present and possibly empty (`subtasks`, `dependencies`, `reviewCycles`, `ownedFiles`).
3. `J/config/WorkPackageDetailWiring.java`: one `@Configuration` with the `WorkPackageDetailQuery` bean built from existing beans (`MissionReadModel`, **the `WorkPackageIndex` bean of WP13's `MissionDetailWiring`**, `TextSource`, the two decoder beans of WP11's `DecoderWiring`, `AdmissionGate`, diagnostics). Declare no `WorkPackageIndex`, `TextSource`, `AdmissionGate` or decoder bean (WP18's `SharedBeansUniqueTest` asserts exactly one of each). Do not edit `ServiceWiring`, `MissionDetailWiring` or `DetailInfrastructureWiring`.
4. Rows C2 and W1 fixtures prove a malformed or unknown `missionId` and a malformed, unknown or ledger-only `wpId` answer **404 `not_found`, never 400**, through `HttpHarness#startWith` (WP10; do not edit the harness). Foreign Host or Origin is 403 `request_refused` with zero reads (row C1).

**Files**: `WorkPackageDetailController.java` (~60), `WorkPackageDetailMapper.java` (~210), `WorkPackageDetailWiring.java` (~45).

**Validation**: controller tests and the row fixtures green; rules 3, 3b, 15, 16 green with their non-zero scanned counts.

---

### Subtask T109: Served route, fixture classes, mapper pairs, stub leg

**Purpose**: Make `DetailGoldenSuiteTest` compare this route and pin its projection rows.

**Steps**:

1. `T/conformance/golden/served/WorkPackageDetailServedRoute.java` implements WP10's `ServedRoute` (shape and request-key conventions: WP10 T071 step 1; this work package does not edit it). `goldenFiles()` is `{get-work-package-detail.json}`; `served()` is `ServedRoutes.expectedEntries(goldenFiles())`, request keys are Work Package ids and `body(entry, wpId)` is `GET .../work-packages/{wpId}/detail`. The classes that carry that golden (the review checklist; the test of step 1b pins the derived set against it; committed by WP07, none written here): `worktree-states` (7), `cycles`, `tasks-md`, `legacy-lanes-json` (the oracle's 500 refusal body), and the detail goldens of `detail-populated`, `wp-duplicate-id`, `wp-malformed-frontmatter` (28), `wp-two-selectors`; `projection-nulls`: `planning-branch-too-long` (T8), `lane-id-fails-pattern` (T9), `reviewed-at-junk` (T15). **Java-only fixtures have no golden and are not entries**; this route's named tests cover them: `projection-refusals` (500 `source_unreadable` plus one diagnostic): `owned-file-pattern-leak` (`OwnedFileEntry.pattern`, T7) and `dependency-id-leak` (`DependencyEntry.wpId`, T5) again. The `worktree-states` goldens are generated under `HostCapability(git=False, worktrees=True)` and the false rows also run under `NO_WORKTREES`; the symbolic-link rows and the resolution branches a stat cannot reproduce are `knownDivergence` entries (V7), whose two outcomes must differ.
1b. **Provider-loaded guard and provider-level completeness (TASKS-GREEN-002, TASKS-FRESH3-003).** `ServedRoutes` (WP10) treats a missing class as an empty route, so a mistyped provider name would leave the golden suite green with zero comparisons. Add `T/conformance/golden/served/WorkPackageDetailServedRouteTest.java` (owned): it asserts that `ServedRoutes` (through the WP10 accessor of the providers actually loaded) loaded `WorkPackageDetailServedRoute`, that `goldenFiles()` equals its `ServedRoutes.OWNER` row (`get-work-package-detail.json`), and the **provider-level completeness assertion**: `served()` equals `ServedRoutes.expectedEntries(goldenFiles())`, i.e. every manifest fixture holding one of those golden files is served by this provider (a fixture-by-golden pair that no provider registers is red here even when the fixture is served for another operation, which the fixture-level `ServedRoutesCompleteTest` of WP18 alone cannot see) and its per-class counts match step 1. `ServedRoutesCompleteTest` stays WP18's whole-set floor.
2. Nine `@ProjectionRow` pairs in `WorkPackageDetailMapperTest` (WP10's annotation): T1 (`missionId`), T5 (`wpId`, `DependencyEntry.wpId`), T7 (`SubtaskEntry.id`, `OwnedFileEntry.pattern`), T8 (`workspace.planningBranch`), T9 (`laneId`, `laneBranch`), T15 (`reviewedAt`), T16 (`feedbackReference`, `artifactPath`), T17 (`reviewCycles[].reviewer`) and T18 (`SubtaskEntry.title` withheld, `DependencyEntry.title` id-substituted, 200 plus `projection_refused`). Each case plants the unshowable value and asserts the row's outcome (M7: 500; M14: member `null`, 200, zero diagnostics). The discovered count of this class is 9.
3. AC-3.1 golden parity for the classes above; AC-3.8 one fixture per row of FR-012 that applies (C1 to C7, M1 to M3, M4a, M4b, M5 to M7, M9 to M14, W1, W3; M13 by the stub leg of step 4, M14 by `planning-branch-too-long`, `lane-id-fails-pattern` and `reviewed-at-junk`) at the port and the HTTP leg; AC-3.5 the `legacy-lanes-json` fixture answers 500 `source_unreadable` for each of its Work Packages and writes the diagnostic once per request (control: a current-shape `lanes.json` answers 200); AC-3.6 recorded access; AC-3.7 credential-in-title fixtures assembled at test time (control: a path-only title is `[path]` and writes none); AC-8.1 subtask and dependency outcomes.
4. AC-6.6 stub leg: with the `NameEncoding` stub a non-ASCII `WP01-é.md` is found by the route regardless of the host locale; real non-ASCII file names are behind `Utf8Host.assumeUtf8()`.
5. AC-12.2/AC-12.4: one diagnostic line per occurrence (code, `mid8` or `none`), no absolute path, `HOME`, fixture root or canary in a line or a Problem body.

**Files**: `WorkPackageDetailServedRoute.java` (~120), `WorkPackageDetailMapperTest.java` (~240), `WorkPackageDetailQueryServiceTest.java` (~300), `WorkPackageDetailControllerTest.java` (~120).

**Validation**: `DetailGoldenSuiteTest` green with this provider; nine pairs discovered; stat-with-follow turns `git-entry-symlink` red.

---

### Subtask T110: Shared-file edits: `OutOfScopeRoutesTest`, port-level legs, JaCoCo (records only if evidenced)

**Purpose**: The named edits.

**Steps**:

1. The eight records listed under "Named edits" are final from the schemas: default no edit; edit one only when the schema or golden proves a member missing or wrong (evidence in the commit message).
2. `T/adapter/in/http/rest/OutOfScopeRoutesTest.java`: **rebase and re-read first** (WP13 removed the Mission path; WP14 and WP16 may have removed theirs). Remove only the line `"/api/v1/missions/01J01000000000000000000001/work-packages/WP01/detail",` of `OUT_OF_SCOPE`; leave the `WP01` line (WP14's) and the artifact lines (WP16's). Touch nothing else.
3. Port-level legs (FR-013, AC-13.3): through WP12's `PlainCaller`, no Spring context, `WorkPackageDetailQuery#workPackageDetail` returns the typed result for a populated Work Package, throws `DetailRefusal.notFound()` for an unknown one, and a corrupt `lanes.json` surfaces as `MissionStatusUnavailable` carrying `source_unreadable`. The legs live in `T/application/query/portlegs/WorkPackageDetailPortLegsTest.java` (new, owned; **outside** `conformance.port` and **not** listed in `R/portlevel-tests.txt`): `PortLevelClassSetTest` requires every class of `conformance.port` to depend on `PortSourceSelector` or `PortFixtures`, and `PortSubsetSecondLegTest` runs every listed id on an in-memory and a filesystem source through a selector fixture, which carries only `MissionStatusQuery` and cannot carry a detail port (TASKS-GREEN-001). Obtain the port from `DetailFixture` (WP10) behind `PlainCaller` (WP12). Append no line to `R/portlevel-tests.txt`; run `PortLevelClassSetTest` and `PortSubsetSecondLegTest` to show nothing changed.
4. JaCoCo recount on the merged tree. Expected shape (the command is the authority): `domain` plus `TitleRows`, `LaneNames`, `OwnedFilePatterns`, `CycleNames`; `application` plus `WorkPackageDetailQueryService`, `TasksMdReader`, `ReviewCycleReader`, `WorkspaceReader`, `ArtifactReferenceBuilder` (and any nested type you declare).

`R/jacoco-class-floor.properties` holds two count lines, `domain=` and `application=` (55 and 44 on the flat checkout; the numbers on your tree are whatever PR A's tip holds). This work package is **not** the owner of the file (WP01 is); it makes a **named edit**: rebase, state the edit in the commit message, touch nothing else of the file. The new number is **derived by command at the commit that adds the classes**, never typed from memory or from the "expected" figures in this prompt:

```bash
cd services/mission-status-api
./gradlew --no-daemon test jacocoTestReport
python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"
```

Write the two printed numbers into the two lines. The count is over `<class>` elements, so a nested record, enum or sealed variant you declare inside a counted class raises it too. `jacocoScopeCheck` has floor semantics (a stale or lowered count is not detected by design, D-65), so the review brief compares the diff of the file with the classes this work package added. **Merge rule (D-145):** lanes that run concurrently each derive a count on their own tree; the lane merged second rebases, re-runs the command on the merged tree and writes what it prints in a named-edit commit of its own. WP17 T125 owns the single D-145 equality comparison on the PR B tip and WP18 re-runs it; a mismatch is repaired by a named edit of this file by the WP that found it.

**Files**: `OutOfScopeRoutesTest.java` (one line), `jacoco-class-floor.properties`, `WorkPackageDetailPortLegsTest.java` (~70).

**Validation**: `OutOfScopeRoutesTest`, `PortLevelClassSetTest`, `PortSubsetSecondLegTest`, `PortLevelIdsTest` and `jacocoScopeCheck` green.

---

### Subtask T111: Gate

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

2. Targeted surface that must be green: AC-3.1 to AC-3.9, AC-10.1 to AC-10.3, AC-8.1 (subtask and dependency outcomes), `WorkPackageDetailMetaReadCountTest`, `WorkPackageDetailQueryServiceGateTest`, goldens for the registered fixtures, the nine mapper pairs, the permission cases (both legs), the stub leg of AC-6.6, `PortLevelClassSetTest`, `PortSubsetSecondLegTest` (both named explicitly in the Gate G run: they fail on a class or id that opens no selector fixture), `WorkPackageDetailServedRouteTest`, `OutOfScopeRoutesTest`, the ArchUnit rules. NFR-006 terminology grep of plan section 5 (expect only the marked legacy `feature_slug` literal of `LanesCodec`, WP11; any other hit is a defect): `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md`.
3. Revert-fails rows (standing named tests): AC-3.1 comparator control (perturb one byte of a detail golden; set `worktreePresent` from the host in a class generated under `NO_WORKTREES`); AC-3.2 to AC-3.5 (order cycles lexically; read a verdict from a file; ASCII `\d`/`String.strip`/`BufferedReader` in `TitleRows`; apply the cap by a size read earlier; accept a legacy `lanes.json`); AC-3.6 (open the prompt file or `spec.md` in `ArtifactReferenceBuilder`: the recorded-access test goes red); AC-3.7 (serve a title holding a credential); AC-3.8 (answer one row with another status or drop its diagnostic); AC-3.9 (move either cap by one byte); AC-10.1 to AC-10.3 (emit `changed`; follow a link on the lane directory or its `.git`; list or read below `.worktrees/<..>/`); AC-22 (skip the gate); typed identifiers (let an empty parse reach the service or map it to 400).
4. Do not write to `M/**` (interim default F1/E-12). Put the tracer entry text (with the `@PermissionCase` ids you created) in your hand-off report; the orchestrator appends it locally.

- **Public repository hygiene (C-006).** No home-directory path, user name, address or token in any file, fixture, test name or commit message. Use the placeholders `<repo>` and `<scratch>`. Credential-shaped test inputs are assembled at test time from two fragments (prefix and body) in a temporary directory; a committed fixture holds at most a near-miss one character short (D-48). Terminology: say Mission and Work Package, never "feature" in new prose (NFR-006; the grep of plan section 5 shows only the marked legacy `feature_slug` literal of `LanesCodec`).
- **Tracer entry (charter standing order 3).** Not written by this work package: interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`. Draft the entry (approach, deviations, and for WP15/WP16 the `@PermissionCase` ids) in the hand-off report; the orchestrator appends it to `M/traces/approach.md` locally.

**Validation**: Gate G and Gate P green; `git status` shows only `owned_files` plus the named edits.

---

## Self-contained green

PR B is a draft that must be green at this work package's tip and at its own tip (plan section 11, "Each PR is self-contained and green", D-153).

- **Fixtures live with their tests.** The goldens and fixture trees (`R/conformance/**`: `worktree-states`, `cycles`, `tasks-md`, `legacy-lanes-json`, `projection-nulls`, `projection-refusals`, `detail-populated`, `wp-*`) were committed by WP07/WP08 and are registered here by `WorkPackageDetailServedRoute`; this work package adds none. Links and worktree directories come from `PROVISION_PLAN` (WP10), never committed; boundary files (4194304/4194305 bytes of `tasks.md`, 1048576/1048577 of `lanes.json`, 262144/262145 of a cycle file) and credential-shaped strings are generated at test time.
- **Floors and counts satisfiable here.** JaCoCo recounted at the commit that adds the classes; the per-class 0.90 line gate holds only if every new class is exercised by this work package's tests (a class covered only by a later work package would be red here). The nine `@ProjectionRow` pairs of this class are discovered; the 26-pair `ProjectionRowCoverageTest` and the `PermissionCaseFloorTest` (floor of four ids over WP15 and WP16) are WP18's and absent here. Native floors (`--floor 3`, `--request-floor 49`) and `R/nativesmoke/requests.json` are unchanged (no `@Tag("native")` test and no smoke stage here: D-99); WP17 raises them.
- **No test or gate names a type of a later work package.** The route uses types of WP05 to WP13 only. `OutOfScopeRoutesTest` still asserts 404 for the paths of WP14 and WP16 that are not yet removed by their merge. `ServedRoutes` treats a missing provider as an empty route; `ServedRoutesCompleteTest` is WP18 and absent.
- **The pin `tests/ci/test_mission_status_api_build.py` stays green (Gate P):** rule-9 literals; the `adapter/in/http` sub-directory clause (`detail` only; **no `dto` directory created here**); the `EventsController` needles (untouched); the models list and drift probe (WP06's); `@Tag("perf")` (none); the tracked-path scan (no `:` or `$` in a new path; a name with a non-ASCII character is generated at test time, never committed under a path the scan rejects; stage new files first); the probe list; native-tag and `requests.json` clauses (numbers unchanged); the partition pin.
- **Mission record.** `M/meta.json` is complete and untouched. Under interim default F1/E-12 this work package commits nothing under `M/**`: the orchestrator keeps the `M/status.json` materialisation and the tracer appends locally. `M/status.json` is the materialisation of `M/status.events.jsonl` (`.venv/bin/spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`), never hand-edited; do not commit untracked CLI state blind (compare with the coordination copy first). Lane transitions are made with `spec-kitty agent tasks move-task`, never by editing a file. With the record intact `cutover-guard`, the mission-state audit (`.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`) and the corpus-blocking job stay green. This work package writes nothing under `M/**` (interim default F1/E-12).

---

## Plan defects found

1. **Resolved (TASKS-DECOMP-009, TASKS-ORDER-004, TASKS-COVER-001): `WorkPackageDetailPortLegsTest` is owned by this work package** (wps.yaml and the frontmatter `owned_files`/`create_intent`; it lives in `T/application/query/portlegs/`, outside `conformance.port`, and is not listed in `R/portlevel-tests.txt`). Nothing is out-of-map and nothing is asked of the orchestrator.
2. **Cross-package use of `Eligibility`.** Plan section 13 puts `ArtifactReferenceBuilder` in `application.query.detail` and `Eligibility` in `application.query.artifact` (section 1.2 prints them with a `/` between the two groups, which reads ambiguously; section 13 and the `owned_files` of WP15 and WP16 settle it). **Resolved (TASKS-COVER-004):** WP09 T061 step 4 now declares `Eligibility` `public` with public methods, so this work package has nothing to stop on and no stop-and-report branch.
3. **A reflection-hint miss from this route has no named-edit permission** (see WP13 item 2): `MissionStatusApplicationHints` may be edited by P6, P8 (named) and P13 only. A proven native miss is an orchestrator item. **RULED: OO-3 (orchestrator ruling 2026-10-13, binding; formerly TASKS-COVER-009 item 3).** Of the PR B work packages only WP17 edits `J/config/MissionStatusApplicationHints.java`. WP13 to WP16 do not edit it: on a locally proven native reflection-hint miss (`nativeCompile nativeTest nativeSmoke`) this work package STOPS and reports the miss to the orchestrator, who routes the hint to WP17. The JaCoCo recount stays a named edit under the plan's merge rule (D-145).
4. **Resolved (TASKS-COVER-010 c): `PermissionCaseFloorTest` counts four ids = WP15 two + WP16 two.** Each reports its two ids in its hand-off report (not in an `M/**` file, interim default F1/E-12) so WP18 can check the floor.

## Definition of Done

Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.

- T105: pre-flight green and recorded; every new test red on the base for its stated reason; shells compile.
- T106: the service runs inside the gate; `tasks.md` is read with the 4 MiB cap by bytes read; `TitleRows` uses `PyText.strip` and Unicode classes; cycles are numeric, verdicts from the ledger, an over-cap or unparseable cycle file is an entry with nulls and no diagnostic.
- T107: `worktreePresent` is stat-only with the `.git` link rule; `lanes.json` corrupt, legacy or over 1 MiB is 500 for every Work Package; references open no file.
- T108: controller, mapper and wiring hold no logic; C2 and W1 are 404; rules 3, 3b, 15, 16 green.
- T109: route registered and `WorkPackageDetailServedRouteTest` green (provider loaded; `goldenFiles()` equals its `OWNER` row; `served()` equals the manifest-derived `expectedEntries`); nine `@ProjectionRow` pairs discovered; the fixture classes and rows served; no path or canary in any line or Problem.
- T110: one line removed from `OutOfScopeRoutesTest` (the `/detail` path only); no line appended to `R/portlevel-tests.txt` (the legs are in the owned `WorkPackageDetailPortLegsTest`); JaCoCo lines equal the command's output; the eight records unchanged or edited only as evidenced named edits.
- T111: Gate G and Gate P green; tracer entry text in the hand-off report with the permission ids; no `M/**` write; no write outside `owned_files` and the named edits.

## Risks

- **Python-versus-Java text semantics** (whitespace, word boundary, digits, newline handling) are the main source of golden failures. Mitigation: `PyText`, `UNICODE_CHARACTER_CLASS`, and the `tasks-md` class with its Arabic-Indic digit, U+00A0/U+0085 and lone `\r` fixtures.
- **Following a link by accident** (`Files.exists`, `Files.isDirectory` default to following). Mitigation: only `TextSource#stat`, which is an `lstat`; recorded-access tests.
- **An over-cap cycle file denying the Work Package.** It must be an entry with null members. Mitigation: AC-3.9 boundary fixtures.
- **Heavy request memory.** Bytes of `tasks.md` up to 4 MiB plus decode: one buffer at a time, and the gate. Do not log content.
- **Concurrent lanes.** WP14 and WP16 edit `OutOfScopeRoutesTest` and JaCoCo. Mitigation: merge order WP13 -> WP14 -> WP15 -> WP16 and the conflict rule of the Concurrency bullet.
- **Locale-dependent tests.** Mitigation: `LC_ALL=C.UTF-8` and `Utf8Host.assumeUtf8()`.

## Reviewer Guidance

- Verify the **red-first form** (scratch worktree of WP13's tip) and that no assertion was weakened.
- Check that the call is inside the gate and that no heavy read occurs outside it; check the three caps are applied by the port by bytes read (4 MiB, 1 MiB, 262144).
- Check `TitleRows` against the oracle's `title_rows` line by line for the Unicode rules; the golden class `tasks-md` is the arbiter.
- Check the recorded-access tests: no READ of the prompt file or `spec.md`; STAT only on the two worktree paths.
- Check `OutOfScopeRoutesTest` lost exactly one line, `R/portlevel-tests.txt` is untouched, the JaCoCo lines match the command run on the tip, and both legs of every `@PermissionCase` exist.
- Check the architectural gates implicated by the touched files by file (rules 3, 3b, 7, 15, 16, `PortLevelClassSetTest`, `PortSubsetSecondLegTest`).
- Look for host paths, user names or tokens in tests, fixtures and commit messages.

## Implementation command

```bash
spec-kitty agent action implement WP15 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
