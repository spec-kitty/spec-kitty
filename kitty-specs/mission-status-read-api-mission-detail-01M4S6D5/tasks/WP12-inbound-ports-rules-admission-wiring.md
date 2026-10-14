---
work_package_id: WP12
title: '[PR A] P8 Inbound ports, rules 15 and 16, admission gate, Problem mapping, shared wiring (FR-013, FR-022)'
dependencies:
- WP09
- WP10
- WP06
requirement_refs:
- FR-013
- FR-022
- FR-012
- NFR-005
- SC-006
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T06:25:40.607251+00:00'
subtasks:
- T081
- T082
- T083
- T084
- T085
- T086
- T087
- T088
- T089
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/MissionDetailQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/WorkPackageQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/WorkPackageDetailQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/ArtifactQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/ArtifactPathInput.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/exceptions/DetailRefusal.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/MissionDetail.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/MissionPhase.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/PhaseName.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/PhaseStatus.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/PhaseBasis.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/WorkPackageSummary.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/WorkPackageView.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/Readiness.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/SubtaskProgress.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ReviewView.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/WorkPackageDetail.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/SubtaskEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/DependencyEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ReviewCycleEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/WorkspaceView.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/OwnedFileEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactReferences.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactReference.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactListing.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactContent.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/MissionIdParseTest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/AdmissionGate.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/AdmissionGateTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PlainCaller.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PlainCallerTest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/RawQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/IncludePrompt.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/DetailInfrastructureWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/adapter/in/http/detail/DetailController.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/adapter/in/http/detail/R15Controller.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/MissionDetailQuery.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/R16Spring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/R16IoException.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/R16StringId.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/StreamSpring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/domain/readmodel/detail/DetailValue.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/domain/readmodel/derive/R15Deriver.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/MissionDetailQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/WorkPackageQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/WorkPackageDetailQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/ArtifactQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/dto/ArtifactPathInput.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/in/exceptions/DetailRefusal.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/MissionDetail.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/MissionPhase.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/PhaseName.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/PhaseStatus.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/PhaseBasis.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/WorkPackageSummary.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/WorkPackageView.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/Readiness.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/SubtaskProgress.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ReviewView.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/WorkPackageDetail.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/SubtaskEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/DependencyEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ReviewCycleEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/WorkspaceView.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/OwnedFileEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactReferences.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactReference.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactListing.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactEntry.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactContent.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/detail/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/MissionId.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/MissionIdParseTest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/AdmissionGate.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/AdmissionGateTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PlainCaller.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/PlainCallerTest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/ProblemMapper.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/ProblemMapper*Test.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/RawQuery.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/IncludePrompt.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/detail/RawQuery*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/detail/IncludePrompt*Test.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/DetailInfrastructureWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/DetailInfrastructureWiring*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/adapter/in/http/detail/DetailController.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/adapter/in/http/detail/R15Controller.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/MissionDetailQuery.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/R16Spring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/R16IoException.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/R16StringId.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/port/in/StreamSpring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/domain/readmodel/detail/DetailValue.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/domain/readmodel/derive/R15Deriver.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP12 – [PR A] P8 Inbound ports, rules 15 and 16, admission gate, Problem mapping, shared wiring (FR-013, FR-022)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: **PR A**, plan phase **P8**, the **last WP of PR A**: PR A must be green at this tip alone (no route served, no `@Tag("native")` test, native floor 3 and `requests.json` 49 unchanged, `DEFINED_RULE_COUNT` 16, rule 15 non-zero through `RawQuery` and `IncludePrompt`, beans constructed with no consumer). Runs **concurrently with WP11 (P6)**, disjoint scopes, but is the LAST PR A work package to merge: the orchestrator merges WP11 first (wps.yaml OO-6), and this WP owns the D-145 JaCoCo equality at PR A's merged tip (T088).
- **External dependency (not a `dependencies` entry)**: WP01 cannot start until the orchestrator has merged the re-cut tip of #5529 (the side-first layout) into this branch; PR A stacks on #5529's last slice and #957 cannot merge before #5529 (C-005). PR B stacks on PR A. **#5533's Java work stacks on PR A** (operator ruling E-8): "primitives complete" is the PR A tip; the post-compaction commits of P5, P7 and P8 are recorded by the orchestrator in `design-decisions.md` (plan section 7).
- **Dependencies inside the mission**: WP09 (P5: `ArtifactKind`, `TextSource`, `TextRefusal`), WP10 (P7: harness, `HttpHarness#startWith`), WP06 (P2: contract models / hand-DTO decision, `ContractDriftProbe`), and transitively WP05 (`WpId.parse`) and WP03/WP04.
- **Write scope**: `owned_files` of the frontmatter only.
- **Named edits (out-of-map; not in `owned_files`)**. Rule for each: rebase onto the lane tip, state the edit in the commit message, touch nothing else of the file.
  - `J/adapter/in/http/ProblemAdvice.java`: exactly ONE new handler, `@ExceptionHandler(DetailRefusal.class)` -> `ProblemMapper.detail` (owned by WP02; P1a). The plan's four names (`DetailRefusal`, `invalid_parameter`, `invalid_artifact_path`, detail `source_unreadable`) are realised as the eight `DetailRefusal.Kind` mappings inside `ProblemMapper.detail` plus `ProblemMapper.invalidParameter()` (wps.yaml DV-3 and DV-4); no other handler is added.
  - `T/architecture/ArchitectureRules.java`: rules 15 and 16 and `DEFINED_RULE_COUNT` 16 (owned by WP01).
  - `T/architecture/ArchitectureControlsTest.java` and `T/architecture/ArchitectureRulesTest.java`: rules 15 and 16, the count of 16, the `SKELETON` list (owned by WP03); shared with WP11, which adds two `Control` rows concurrently (union rule of the wps.yaml header, DV-5).
  - `R/jacoco-class-floor.properties`: the `application` and `domain` count lines only (owned by WP01).
  - `J/config/MissionStatusApplicationHints.java`: only on a miss proven by the local `nativeTest`/`nativeSmoke` run (E-7) or by CI at PR A's tip (owned by WP17); serialised by merge order with WP11.
  - `M/traces/approach.md`, `design-decisions.md`, `tooling-friction.md`: append-only tracer entries.
  - `J/domain/model/MissionId.java` is #5529's file; this WP owns it for the **`parse` factory only** (listed in `owned_files`, E-5, D-150): change nothing else in it.
- **Alias key**: `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Paths are post-re-cut (plan section 1.1) unless "exists at the checkout" is said.

## Objective

Land the inbound side of the five operations without serving a route: the four inbound port interfaces with typed identifiers (`MissionId`, `WpId`, `ArtifactPathInput`), `DetailRefusal`, the 21 `domain.readmodel.detail` records and enums, `MissionId.parse`, `AdmissionGate`, the HTTP shared pieces (`RawQuery`, `IncludePrompt`, `ProblemMapper` additions, the `ProblemAdvice` `DetailRefusal` handler), `DetailInfrastructureWiring`, ArchUnit rules 15 and 16 with planted controls and conforming skeleton members, and `PlainCaller` (the second adapter proof). After this WP, PR B only adds services, controllers and wiring on top.

## Context

- **Contract of the ports (plan section 13).** `MissionDetailQuery#mission(MissionId)`; `WorkPackageQuery#workPackage(MissionId, WpId, boolean includePrompt)`; `WorkPackageDetailQuery#workPackageDetail(MissionId, WpId)`; `ArtifactQuery#list(MissionId)` and `#content(MissionId, ArtifactPathInput)`. Results are the `domain.readmodel.detail` records. Refusals are `DetailRefusal` (a `final` unchecked `RuntimeException` with a nested `Kind` and nothing else: no message text beyond the kind's wire word, no HTTP status, no path) and the existing `MissionStatusUnavailable` for the generic 500s. No type in `application.query.port.in` or the detail records references Spring, `jakarta`, `org.openapitools` or a generated DTO (rules 2a, 9, 16).
- **Typed identifiers (E-5, D-150).** `MissionId.parse(String)` returns `Optional<MissionId>` (lenient: lowercase, short, long, empty or ill-formed gives empty; nothing throws); `WpId.parse(String)` is WP05's. An empty result becomes `DetailRefusal.notFound()` in the adapter, so no adapter chooses between 400 and 404 (rows C2 and W1). A `mid8`, a slug or a number is not a ULID, so it parses empty and answers 404 (AC-1.5).
- **The kinds of `DetailRefusal`**: `NOT_FOUND`, `INVALID_ARTIFACT_PATH`, `ARTIFACT_TOO_LARGE`, `ARTIFACT_NOT_TEXT`, `ARTIFACT_SECRET`, `ARTIFACT_UNREADABLE`, `ARTIFACT_LISTING_UNREADABLE`, `SOURCE_UNREADABLE`. The kind-to-status mapping exists **once**, in `ProblemMapper`/`ProblemAdvice` (404 `not_found`, 400 `invalid_artifact_path`, 413 `artifact_too_large`, 415 `artifact_not_text`, 422 `artifact_secret`, 500 `artifact_unreadable`, 500 `artifact_listing_unreadable`, 500 `source_unreadable`; the contract's `ArtifactRefusalCode.yaml` is the vocabulary: read it at `contracts/mission-status/schemas/ArtifactRefusalCode.yaml`). `ArtifactPathInput` is sealed: `Values(List<String>)` or `Undecodable`.
- **The admission gate (FR-022, S-13, E-1).** `AdmissionGate` in `application.query`: a fair `Semaphore(4, true)`; `<T> T run(Supplier<T>)` acquires uninterruptibly and releases in `finally`; never refuses, never times out, creates no thread (rule 2c); test accessor `int highWaterMark()`. It will be held by the detail, artifact and prompt-bearing services (PR B). The port-level AC-22.1..22.3 need the real heavy operations and are WP18's.
- **Exists at the checkout:** `J/adapter/in/http/{ProblemMapper,ProblemAdvice,ProblemBody}.java` (`ProblemMapper` has `unavailable`, `pageCursor`, `stream`, `streamCapacity`, `status(HttpStatus)`, `unexpected`; `ProblemAdvice` is a `@RestControllerAdvice` with handlers incl. `TypeMismatchException` -> status-only 400), `J/domain/model/MissionId.java` (record over `String value`, a ULID pattern `^[0-9A-HJKMNP-TV-Z]{26}$`, `mid8()`), `T/architecture/{ArchitectureRules,ArchitectureControlsTest,ArchitectureRulesTest}.java` (`DEFINED_RULE_COUNT = 12` at the checkout; 14 after P1b/WP03), `T/architecture/fixture/{application,adapter,domain,config}/**`. **Exist after earlier WPs:** the rules 13/14 and fixtures (WP03), `WpId` (WP05), `ArtifactKind` (WP09), `HttpHarness#startWith` (WP10). **New here:** every other owned file.

### Subtask T081: Red-first, the four interfaces, `ArtifactPathInput`, `DetailRefusal`

**Purpose**: define the inbound contract; tests first.

**Steps**:
1. Pre-flight (first step): `cd services/mission-status-api && export LC_ALL=C.UTF-8 && ./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'` (with `CONTRACT_BUNDLE`/`CONTRACT_BUNDLE_SHA256` exported, plan section 5). Green or stop and report. Put the #5529 tip sha in the first commit message and paste the C-005 string-literal grep result.
2. Add the failing tests first (red on the phase base, the types do not exist): `MissionIdParseTest`, `AdmissionGateTest`, `PlainCallerTest`, the `RawQuery*Test`, `IncludePrompt*Test`, `ProblemMapper*Test` additions, `DetailInfrastructureWiring*Test`, the detail record tests, and the rules 15/16 tests (T086). Run once; keep the failing counts for the tip commit message.
3. Create the interfaces in `J/application/query/port/in/` (interfaces only, rule 13): `MissionDetailQuery`, `WorkPackageQuery`, `WorkPackageDetailQuery`, `ArtifactQuery`, with exactly the signatures above. No `String` identifier parameter anywhere (rule 16 clause c), no checked exception (clause b), no Spring/servlet/JSON import (clause a).
4. `J/application/query/port/in/dto/ArtifactPathInput.java`: sealed interface with `Values(List<String> values)` and `Undecodable` (a record or enum constant singleton); immutable list copy.
5. `J/application/query/port/in/exceptions/DetailRefusal.java`: `public final class DetailRefusal extends RuntimeException`; nested `enum Kind` with the eight kinds above and a `wire()` word (lower-case snake, equal to the contract code where one exists: `not_found`, `invalid_artifact_path`, `artifact_too_large`, `artifact_not_text`, `artifact_secret`, `artifact_unreadable`, `artifact_listing_unreadable`, `source_unreadable`); static factories `notFound()`, `invalidArtifactPath()`, ...; `kind()` accessor; no message text beyond the wire word, no HTTP status, no path, no cause with a path (`super(kind.wire(), null, false, false)` to suppress stack-trace noise is acceptable). Rule 13 clause c: lives in `port.in.exceptions` and is a `Throwable`.

**Files**: 4 interfaces (~20 lines each), `ArtifactPathInput.java` (~30), `DetailRefusal.java` (~80).

**Validation**: compile; `ArchitectureRulesTest` rules 2a, 9, 13 green on production classes.

### Subtask T082: The 21 `domain.readmodel.detail` records and enums

**Purpose**: P8 owns every file of the directory but `ArtifactKind.java` (WP09's), shaped from the contract so that P8 compiles before any route; the records are to be **complete from the contract schemas** (every member, nullability and order of the schema of the route that returns them), so that a route WP has nothing to amend. A route WP edits one of these records only if its own schema or golden proves a member missing or wrong; that is a named edit of this WP's file (accepted named-edit risk under the plan section 11 shared-file table, TASKS-DECOMP-003): rebase first, touch only that record, state the edit and the schema evidence in the commit message (D-111).

**Steps** (package `domain.readmodel.detail`; records and enums only; no framework, no `java.nio`, no Jackson):
1. For each of `MissionDetail`, `MissionPhase`, `PhaseName`, `PhaseStatus`, `PhaseBasis`, `WorkPackageSummary`, `WorkPackageView`, `Readiness`, `SubtaskProgress`, `ReviewView`, `WorkPackageDetail`, `SubtaskEntry`, `DependencyEntry`, `ReviewCycleEntry`, `WorkspaceView`, `OwnedFileEntry`, `ArtifactReferences`, `ArtifactReference`, `ArtifactListing`, `ArtifactEntry`, `ArtifactContent` read the schema `contracts/mission-status/schemas/<Name>.yaml` (they exist at the checkout; the wire name may differ: for example `WorkPackageView` is the `WorkPackage` schema; read `contracts/mission-status/openapi.yaml` for the five operations' response schemas) and model every member with the Java type that carries the schema constraint without loss: required-nullable members as nullable components documented `@Nullable`-style in Javadoc (no annotation library), enums with their wire words (`wire()`), lists defensively copied (`List.copyOf`), open maps whose key order matters on the wire are carried as an **ordered list of entries**, never as a `Map` (TASKS-FRESH3-001): `WorkPackageView.subtasks` is `List<Map.Entry<String, Lane>>` (JDK `Map.Entry` with the `Lane` enum of `domain.model`; `List.copyOf`, entries immutable), held **already in code-point order of the subtask id** by whoever builds the view (WP14's `WorkPackageQueryService`, an application class that may use `CodePoints.compare`); the Javadoc states that the order is significant and that the mapper must not re-sort. The mapper then needs nothing from `domain.model` but records and enums (rule 15).
2. Keep each record to its schema: **no derived logic** beyond validation of invariants and defensive copies. Derivers (`PhaseDeriver`, `ReadinessDeriver`, ...) are PR B's (`domain.readmodel.derive`).
3. `T/domain/readmodel/detail/**`: one construction/immutability test per record and enum (a generic parameterised "records are immutable and null-hostile" test plus one targeted test per enum wire mapping is enough); every class must meet the 0.90 per-class line floor (records with no code have no lines; enums with `wire()`/`fromWire()` need a test).
4. Do not add `ArtifactKind` (WP09's); reference it from `ArtifactEntry`.

**Files**: 21 production files (~25-70 lines each, ~900 lines in all), tests ~350 lines.

**Validation**: `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.domain.readmodel.detail.*'`; rule 16 clause a (no Spring/jakarta/openapi in the detail records) green.

### Subtask T083: `MissionId.parse`

**Purpose**: the typed, lenient identifier factory (E-5).

**Steps**:
1. `J/domain/model/MissionId.java` (exists at the checkout; named scope: **the `parse` factory only**): add `public static Optional<MissionId> parse(String raw)`: `Optional.empty()` for `null`, empty, lowercase, short, long or any ill-formed value (reuse the existing ULID `Pattern`); never throws; do not change the canonical constructor or `mid8()`.
2. `T/domain/model/MissionIdParseTest.java`: a ULID parses; a lowercase ULID, 25 and 27 characters, an empty string, `null`, a 8-character `mid8`, a slug and a decimal number each yield empty; nothing throws; a value with an invalid Crockford letter (`I`, `L`, `O`, `U`) yields empty.

**Files**: `MissionId.java` (+~12 lines), test ~70 lines.

**Validation**: `./gradlew --no-daemon test --tests '*MissionIdParseTest' --tests '*MissionId*'`.

### Subtask T084: `AdmissionGate`

**Purpose**: the unit contract of FR-022.

**Steps**:
1. `J/application/query/AdmissionGate.java`: `public final class AdmissionGate` with a fair `java.util.concurrent.Semaphore(4, true)`; `public <T> T run(Supplier<T> work)` acquires with `acquireUninterruptibly()`, runs `work`, releases in `finally`; tracks the high-water mark of concurrently held permits with an `AtomicInteger` current and a `LongAccumulator`/CAS max; `public int highWaterMark()` (test accessor, Javadoc says so). It never refuses, never times out, creates no thread, spawns nothing (rule 2c). A `Runnable` overload is optional.
2. `T/application/query/AdmissionGateTest.java`: permit count 4 (fifth caller blocks until a release: prove with latches, not sleeps); fairness (FIFO order of waiters released in arrival order: use a deterministic hand-off with latches); release in `finally` (a supplier that throws still releases: the next call is not blocked); never refuses (100 queued callers behind 4 blocked holders all complete after release); high-water mark equals 4 under 16 concurrent callers over a latch, and never exceeds 4; uninterruptible acquire (interrupt a waiter: it still gets the permit and the interrupt flag is preserved). Bounded waits (`await(5, SECONDS)`) so a failure is red, not a hang.
3. The port-level AC-22.1..22.3 (over the real heavy operations) are **not** here: they need P10..P12 services and belong to WP18 (`AdmissionGatePortLevelTest`).

**Files**: `AdmissionGate.java` (~70), `AdmissionGateTest.java` (~200).

**Validation**: `./gradlew --no-daemon test --tests '*AdmissionGateTest'`; revert: use `new Semaphore(5, true)` and the high-water assertion goes red; use a non-fair semaphore and the fairness test goes red (if deterministic).

### Subtask T085: HTTP shared pieces and wiring

**Purpose**: the transport pieces every PR B controller reuses, with no controller yet.

**Steps**:
1. `J/adapter/in/http/detail/RawQuery.java`: strict percent decoding of the raw query string: collects **every** value of `path` (a repeated parameter is seen, not joined), percent-decodes each value once and strictly as UTF-8 (`+` is a literal plus sign, DC-6; a percent sequence that is not valid UTF-8, such as `%ff`, `%c0%af`, `%e2%82`, is undecodable and never replaced by U+FFFD); returns an `ArtifactPathInput` (`Values(list)` or `Undecodable`). No Spring type in its signature (it takes the raw query `String`); it is a plain helper the controller calls. A malformed percent-encoding anywhere else in the query stays the status-only 400 that `ProblemAdvice` already gives (row W2 note).
2. `J/adapter/in/http/detail/IncludePrompt.java`: parses the raw values of `includePrompt`: absent -> `false`; exactly one value `true` or `false` (case-sensitive) -> that boolean; anything else (`1`, `yes`, `TRUE`, an empty value, a repeated parameter) -> is refused. **Pinned form (the contract with WP14): `static Optional<Boolean> parse(List<String> rawValues)`; an empty result means refused (no sealed type, no exception type is added).** WP14's controller turns an empty result into the response of `ProblemMapper.invalidParameter()` (400 `invalid_parameter`) before any file is read (OQ-2, AC-2.5); `IncludePrompt` therefore adds no `ProblemAdvice` handler, and the single-handler rule of step 4 is unaffected. `IncludePromptTest` covers each refused value and the absent, `true` and `false` cases.
3. `J/adapter/in/http/ProblemMapper.java` (exists; WP12 owns it): add `ResponseEntity<ProblemBody> detail(DetailRefusal refusal)` mapping each `Kind` to its status and fixed title/detail (404 `not_found`, 400 `invalid_artifact_path`, 413, 415, 422, 500, 500, 500; the bodies carry a stable `code`, a fixed title and, where the contract requires, a fixed detail: never a path, line text, OS message, exception text or enum name; use the 3-argument `ProblemBody` the existing methods use) and `invalidParameter()` (400 `invalid_parameter`). Keep the existing methods byte-identical. `ProblemMapper*Test`: one case per kind, scanning the body for the fixture root, `HOME` and file-name canaries (AC-12.4).
4. `J/adapter/in/http/ProblemAdvice.java` (**named edit**, owned by WP02): add exactly ONE handler: `@ExceptionHandler(DetailRefusal.class)` -> `ProblemMapper.detail`, which covers all eight kinds (`INVALID_ARTIFACT_PATH` -> 400 `invalid_artifact_path` and `SOURCE_UNREADABLE` -> 500 with the contract code, one path-free Problem, are kinds of the same mapping, not separate handlers; a second `@ExceptionHandler` for the same type is ambiguous and Spring rejects it at start-up; `invalid_parameter` has no exception, DV-3). A `ProblemAdviceTest` case per kind proves the status and code. Touch nothing else of the file; state the edit in the commit message.
5. `J/config/DetailInfrastructureWiring.java`: `@Configuration` with two beans: `TextSource textSource(...)` returning the one `FilesystemTextSource` over the project root and the production `AllowlistAccess` (plan 7.1 row 12; #5533's own wiring injects it) and `AdmissionGate admissionGate()`. No consumer exists in PR A (no `MissionDetailQuery` bean, no controller). `DetailInfrastructureWiring*Test` in `T/config/` **loads only `DetailInfrastructureWiring`** (for example `ApplicationContextRunner` or `@SpringJUnitConfig` with that one configuration class, never the full application context) and asserts the two positive facts: exactly one `TextSource` and exactly one `AdmissionGate` bean. **Collaborators of the partial context (TASKS-FRESH3-005):** `textSource(...)` needs the project root and an `AllowlistAccess`, which only `ServiceWiring`-side properties supply, so the test supplies them as **test-local `@Bean` stubs** in a nested `@Configuration` (a `MissionStatusProperties` pointing at a `@TempDir` project root, and an `AllowlistAccess` over a test pass-through or recorder) and does **not** import `ServiceWiring`; the test needs no `MissionReadModel`, no `Consumer<Diagnostic>` and no decoder bean, and `DetailInfrastructureWiring` declares none of them. Read the real signature of `textSource(...)` at the lane tip and stub exactly the parameters it takes. It makes **no negative assertion** about the four inbound interfaces: WP13 to WP16 add `MissionDetailQuery` and the other beans through their own wiring classes, and this WP12-owned test must stay green at every PR B tip. The 'no consumer in PR A' fact stays a reviewer check (the Verify list), not a test.
6. Native image: the new beans are plain Java and AOT-friendly; the E-7 local run in T088 proves it; add a hint in `MissionStatusApplicationHints` only on a proven miss (named edit).
7. Tests for `RawQuery` (all AC-5.2 percent-decoding rows: `..%2fx`, `%252e%252e` decodes once to the literal `%2e%2e`, repeated `path=a&path=b`, `path=spec.md&path=plan.md`, missing and empty `path=`, `%ff`, `%c0%af`, `%e2%82`, literal `+`; the port-level rows that do not need percent-decoding run again at the port in WP18) and `IncludePrompt` (`true`, `false`, absent, `1`, `yes`, `TRUE`, empty, repeated).

**Files**: `RawQuery.java` (~110), `IncludePrompt.java` (~60), `ProblemMapper.java` (+~60), `ProblemAdvice.java` (+~20, named edit), `DetailInfrastructureWiring.java` (~50), tests ~350 lines.

**Validation**: `./gradlew --no-daemon test --tests '*RawQuery*' --tests '*IncludePrompt*' --tests '*ProblemMapper*' --tests '*DetailInfrastructureWiring*' --tests '*ProblemAdvice*'` (the existing advice tests stay unchanged and green).

### Subtask T086: Rules 15 and 16 (named edits), planted controls, skeleton members

**Purpose**: bind the inbound side structurally, non-vacuously (plan section 13).

**Steps**:
1. `T/architecture/ArchitectureRules.java` (**named edit**, owned by WP01): add rule 15 and rule 16 as defined in plan section 13 and raise `DEFINED_RULE_COUNT` to 16 (it is 14 after P1b: confirm at the lane tip; if the number differs, stop and report). Rule 15: subject `adapter.in.http.detail..`, depend among project packages only on `application.query.port.in..` (root, `dto/`, `exceptions/`), the records and enums of `domain.model`, `domain.readmodel.overview`, `domain.readmodel.detail` (so **not** the non-record classes of `domain.model`: `CodePoints`, `PyText`, `SupportedSchemaRange`; any ordering, text or range work they do happens in the application layer, never in a controller or mapper), `adapter.in.http` itself and the generated model/dto packages; not on `domain.readmodel.reducer`, `domain.redaction`, `domain.readmodel.derive`, a non-record class of `domain.readmodel.overview`, or `application..` other than `application.query.port.in..`; non-zero scanned count asserted (production: `RawQuery`, `IncludePrompt`). Rule 16: clause a (no `org.springframework..`, `jakarta..`, `org.openapitools..` or generated package in `application.query.port.in..` including the stream vocabulary, and `domain.readmodel.detail..`); clause b (no public method of those interfaces declares a checked exception, except `MissionStatusQuery` and `Subscription`: `Subscription#next` declares `InterruptedException`, D-50); clause c (no parameter of a public method of the four new interfaces is a `String`).
2. `T/architecture/ArchitectureControlsTest.java` and `ArchitectureRulesTest.java` (**named edits**, owned by WP03): a control for ids 15 and 16, the count of 16, the `SKELETON` list gains `DetailController`, `MissionDetailQuery`, `DetailValue`; the contiguity guard and the non-vacuity counts stay green. **Shared with WP11 (wps.yaml header rule, DV-5):** WP11 adds two `Control` rows (`C12aPortOut`, `A12cUsesCodec`) to the same file concurrently. Whichever lane merges second keeps the UNION of the `Control` rows of both lanes, and the count assertions and the contiguity guard are re-run on the merged tree (a count computed on one lane's rows is recomputed, never kept).
3. Fixtures (all owned here, under `T/architecture/fixture/`): conforming skeleton members `adapter/in/http/detail/DetailController` (calls only the skeleton's `port/in/MissionDetailQuery` and returns its `DetailValue` record), `application/query/port/in/MissionDetailQuery`, `domain/readmodel/detail/DetailValue`; planted violations `adapter/in/http/detail/R15Controller` (calls the non-record `domain/readmodel/derive/R15Deriver`; red on rule 15 only), `application/query/port/in/R16IoException` (a method declaring `IOException`; red on 16 only), `R16StringId` (a method with a `String` identifier parameter; red on 16 only, clause c), `R16Spring` (imports Spring; red on rules 2, 8 and 16, the co-reds pinned), `StreamSpring` (an interface whose simple name starts with `Stream` that imports Spring: red on 2, 8 and 16 like `R16Spring`, showing the stream vocabulary is inside clause a).
4. Run `ArchitectureRulesTest` (16 rules, each non-vacuous) and the skeleton test.

**Files**: fixtures 9 files (~15-40 lines each), named edits ~+120 lines across three files.

**Validation**: `./gradlew --no-daemon test --tests '*ArchitectureRulesTest' --tests '*ArchitectureControlsTest'`; revert: delete a planted class and its control is red (the controls require a planted class for ids 1..16); drop the `String` clause and `R16StringId` goes green (so the control fails).

### Subtask T087: `PlainCaller` and `PlainCallerTest`

**Purpose**: AC-13.3, the proof that no HTTP type is needed to call the five operations.

**Steps**:
1. `T/testsupport/PlainCaller.java`: a helper that drives any implementation of the four interfaces with `MissionId`, `WpId` (built with the `parse` factories), a `boolean` and an `ArtifactPathInput` only (methods `mission(String raw)`, `workPackage(String rawMission, String rawWp, boolean includePrompt)`, ... that call `parse`, map an empty result to `DetailRefusal.notFound()`, and call the port). A refusal is the typed exception, never a status. It also passes an invalid path as zero values, two values and an undecodable input; each must be the typed `invalid_artifact_path` refusal (the port rule, WP15's service; at P8 the stubs reproduce it).
2. `T/testsupport/PlainCallerTest.java`: drives the caller through **stub implementations declared in the test**; no P9..P12 service is named. Assert: valid ids reach the stub with typed arguments; a malformed id never reaches the stub and yields `DetailRefusal.notFound()`; a stub-thrown `DetailRefusal` surfaces as the typed exception (control for AC-13.3: "the caller's result for a refusal is the typed exception, not a status"). Each route WP calls `PlainCaller` with its real service in its own port-level test (PR B); `AdmissionGatePortLevelTest` uses it too.
3. Beside P1a's `PlainStreamCallerTest` (exists after WP02): do not edit it.

**Files**: `PlainCaller.java` (~90), `PlainCallerTest.java` (~140).

**Validation**: `./gradlew --no-daemon test --tests '*PlainCallerTest'`; ArchUnit rule 16 clause c green for the four interfaces.

### Subtask T088: JaCoCo count lines and the PR A tip checks

**Purpose**: PR A must be green on every CI leg alone (E-7, D-153).

**Steps**:
1. After `./gradlew --no-daemon test jacocoTestReport`, run the plan section 2 command from `S`: `python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"` and write the two numbers into `R/jacoco-class-floor.properties` (named edit; WP01 owns it) at the commit that adds the classes. WP11 is merged before this WP (OO-6): do not start this step until the orchestrator has merged WP11's lane into this lane (the PR A branch tip carrying WP11 merged into the lane workspace, the OO-5 mechanism); stop and report if WP11 is not yet approved. Then re-run the command on that merged tree and write what it prints in a named-edit commit of its own (D-145).
2. **The D-145 equality comparison**: the two lines of the file equal the command's output **on the merged tree that carries WP01..WP11 and this WP**, which is PR A's tip (this WP is the last PR A work package to merge, wps.yaml OO-6; WP11's own recount covers only its lane and is not the PR A claim). Record the comparison and the sha of the merged tree in the commit message. Floor semantics cannot see an understated count; WP17 T125 owns the equivalent check at PR B's tip.
3. **PR A tip evidence (E-7, D-153)**: locally run `./gradlew --no-daemon check`, then `./gradlew --no-daemon nativeCompile nativeTest` and `./gradlew --no-daemon nativeSmoke -PnativeBinary=<binary>` (GraalVM needed; `nativePerf`, `native-tag-floor` and `digests` stay CI-only). The new beans (`DetailInfrastructureWiring`, and WP11's `DecoderWiring` if merged) are constructed at start-up, so a missing reflection hint would turn PR A's native legs red: on a proven miss add the hint to `J/config/MissionStatusApplicationHints.java` as a named edit, stating the proof. A local red is classified under plan section 6, never retried to green; CI is the authority.

**Files**: `R/jacoco-class-floor.properties` (two lines).

**Validation**: `jacocoTestCoverageVerification jacocoScopeCheck` green; the equality comparison recorded in the commit message.

### Subtask T089: Gate

**Steps** (`export LC_ALL=C.UTF-8`; stage new files with `git add` first, the pin reads `git ls-files`):
1. **Gate G**: `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`.
2. **Gate P**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` (this WP edits `ArchitectureRulesTest`, so the rule-9 literals clause is exercised, and adds the `detail` directory under `adapter/in/http`, so the sub-directory-names clause is exercised: `detail` is allowed, no `dto` directory unless WP06's spike said so).
3. Acceptance: AC-13.1, AC-13.2, AC-13.4; `MissionIdParseTest`; `ArchitectureRulesTest` (16 rules, each non-vacuous) and the skeleton test of `ArchitectureControlsTest`; `AdmissionGateTest`; `PlainCallerTest`.
4. Run `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md | grep -v 'non-numeric-number feature'`: expect only the marked legacy literal `feature_slug` of WP11 (D-115) if merged.
5. Append tracer entries (record the P8 seam names in `design-decisions.md`: the orchestrator re-records the post-compaction shas) and commit; state each named edit in the commit message.

## Self-contained green

PR A's tip (this WP) must be green on every CI gate alone (plan section 11, "Each PR is self-contained").

- **Fixtures with tests.** The only fixtures are the architecture fixture classes under `T/architecture/fixture/**` (planted and conforming) and test-local stubs; `PlainCallerTest` uses stubs declared in the test; no conformance golden is read or added.
- **Floors and counts satisfiable here.** `DEFINED_RULE_COUNT` is 16 at this tip and every id 1..16 has a control; rule 15's non-zero scanned count is satisfied by the production classes `RawQuery` and `IncludePrompt` (no controller exists); rule 16's subject (`application.query.port.in..` and `domain.readmodel.detail..`) is non-zero; `R/jacoco-class-floor.properties` carries exactly the counts of WP01..WP12 (equality comparison recorded, D-145); native floor 3 and `requests.json` 49 unchanged (no `@Tag("native")` test, no smoke stage, no workflow line).
- **No forward reference.** No test or gate names a type of WP13..WP18: no `MissionDetailQueryService`, no controller of the four routes, no `ServedRoutesCompleteTest`. `PlainCallerTest` uses test-local stubs; `OutOfScopeRoutesTest` is unchanged (the five routes still answer 404); `S/README.md` is untouched (routes documented in PR B).
- **Beans.** `DetailInfrastructureWiring` (and `DecoderWiring`) are constructed at start-up with no consumer; no `MissionDetailQuery` bean exists and no controller injects one at PR A's tip (a reviewer check; `DetailInfrastructureWiringTest` loads only `DetailInfrastructureWiring` and asserts the two positive beans, so it stays green when PR B adds consumers).
- **Pin `tests/ci/test_mission_status_api_build.py`.** Kept green: the rule-9 literals of `ArchitectureRulesTest`, the `adapter/in/http` sub-directory names (`detail` holds `RawQuery` and `IncludePrompt` only), the tracked-path scan (new files staged), the `EventsController` needles (untouched), the models list/drift probe (untouched). The file itself is not edited.
- **Mission record.** `M/meta.json` untouched; `M/status.json` is the `materialize`d snapshot of `status.events.jsonl`, never hand-edited (compare with the coordination copy before committing any status file), so cutover-guard, the mission-state audit and corpus-blocking pass at PR A's tip; at that tip the WPs of P1..P8 are in their recorded lanes and P9..P13 `planned`. Run the audit (`spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`) before the operator publishes the ref.

## Plan defects found

- **Rule-count arithmetic depends on WP03's tip.** The plan says `DEFINED_RULE_COUNT` is 12 at the checkout, 14 after P1b, 16 here. The instruction in T086 stops and reports if the lane tip is not 14; no change to the plan needed. (Exists at the checkout: 12.)
- **`PlainCaller` takes raw strings in its helpers** while rule 16 clause c forbids a `String` identifier in the **interfaces**; clause c covers only the four interfaces, so this is consistent, but the helper's `String` parameters must stay in `testsupport` (not in `application.query.port.in`). Stated, not a defect.
- No unsatisfiable floor or forward reference found for WP12.

## Definition of Done

- T081..T089 recorded with `spec-kitty agent tasks mark-status <Txxx> --status done --mission mission-status-read-api-mission-detail-01M4S6D5`.
- The four interfaces, `ArtifactPathInput`, `DetailRefusal`, the 21 detail records/enums, `MissionId.parse`, `AdmissionGate`, `RawQuery`, `IncludePrompt`, `ProblemMapper` additions, the single `ProblemAdvice` `DetailRefusal` handler and `DetailInfrastructureWiring` exist; no route is served.
- `DEFINED_RULE_COUNT` is 16; rules 15 and 16 each have a planted control red on exactly their rule and non-zero scanned counts; the skeleton test is green.
- `AdmissionGate` unit contract (4 permits, fair, release in `finally`, never refuses, high-water accessor) is tested with latches.
- `PlainCaller` drives stubs of all four interfaces with typed ids only.
- The NFR-006 terminology grep (T089 step 4) shows only the marked legacy literal or nothing.
- The JaCoCo lines equal the command's output at this tip; local `check`, `nativeCompile nativeTest`, `nativeSmoke` evidence is recorded (E-7); Gate G and Gate P green; only `owned_files` and the named edits changed.

## Risks

- **A typed signature drifting back to `String`** (rule 16 clause c catches it; the `R16StringId` control proves the clause bites).
- **Understated JaCoCo count after the WP11 merge** (floor semantics): the equality comparison.
- **Native reflection miss** for the new beans: prove locally before review, named edit on a proven miss.
- **`ProblemAdvice` edit scope creep**: the diff of `ProblemAdvice` adds the `DetailRefusal` handler only (one method); a reviewer diff should show nothing else changed.
- **Record shapes diverging from the contract**: the response-validation and drift tests of WP06/WP17 catch it in PR B; read each schema, do not guess.

## Reviewer Guidance

- Verify the interface signatures verbatim against plan section 13 (no `String` identifier, no checked exception, no Spring/servlet/JSON import).
- Verify `DetailRefusal` carries nothing but its kind and that `ProblemMapper` is the only kind-to-status table.
- Verify rules 15 and 16 are non-vacuous: run the two controls and the production scan counts; mutate a control (delete the planted class) and see red.
- Verify the diff of `ProblemAdvice`, `ArchitectureRules`, `ArchitectureControlsTest`, `ArchitectureRulesTest`, `MissionId`, `R/jacoco-class-floor.properties` is limited to the named edit and stated in the commit message.
- Verify no `MissionDetailQuery` bean and no controller exist (PR A serves no route); `OutOfScopeRoutesTest` unchanged.
- Run the implicated architectural gates (`ArchitectureRulesTest`, `ArchitectureControlsTest`, `PortLevelClassSetTest`) and the pin; check the commit messages record the equality comparison and the E-7 runs.

## Implementation command

```bash
spec-kitty agent action implement WP12 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
