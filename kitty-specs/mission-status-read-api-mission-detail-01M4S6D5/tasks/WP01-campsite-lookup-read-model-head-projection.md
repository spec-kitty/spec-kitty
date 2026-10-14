---
work_package_id: WP01
title: '[PR A] P1 Campsite: extract lookup, read model and head projection (C-011); starts after the #5529 re-cut'
dependencies: []
requirement_refs:
- FR-001
- FR-021
- NFR-005
- NFR-006
- NFR-007
- C-005
- C-011
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionStatusQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionLookup.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/OverviewReader.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionReadModel.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionHeadProjection.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionHead.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/MissionLookupTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/OverviewReaderTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/MissionReadModelTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/MissionHeadProjectionTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/ReadModelSingletonTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/CoupledSymbolsShapeTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/HeadProjectionOwnershipTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/HeadBypass.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionStatusQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionLookup.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/OverviewReader.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionReadModel.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionHeadProjection.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/MissionHead.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/ServiceWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/MissionLookupTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/OverviewReaderTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/MissionReadModelTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/MissionHeadProjectionTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/config/ReadModelSingletonTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/ArchitectureRules.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/CoupledSymbolsShapeTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/HeadProjectionOwnershipTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/HeadBypass.java
- services/mission-status-api/src/test/resources/jacoco-class-floor.properties
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP01 – [PR A] P1 Campsite: extract lookup, read model and head projection (C-011); starts after the #5529 re-cut

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: **PR A** (draft; phase tag **P1**). PR A stacks on the branch that carries #5529's last slice; the operator retargets it to `main` after #5529 lands. No agent pushes, opens or retargets a PR.
- **External dependency (not a `dependencies` entry)**: this WP cannot start until the orchestrator has merged the re-cut tip of #5529 (the CQRS side-first layout, plan section 1.1) into this branch, and the P0 baseline record (`M/traces/baseline-red.yaml` and the `test_baseline_record_*` tests) is committed. PR A stacks on #5529's last slice; #957 cannot merge before #5529 (C-005). Until the re-cut is merged **none of the `application/query/**` paths of this prompt exists** (plan Unverified 18). If, when you start, `git ls-files 'services/mission-status-api/src/**' | grep -c 'application/query'` prints `0`, stop and report BLOCKED to the orchestrator; do not perform the re-cut yourself.
- **Dependents**: WP02 (P1a) depends on this WP; WP02 to WP12 are all PR A; #5533's Java work later stacks on PR A.
- **Write scope**: `owned_files` only. Every other file below is a named edit.
- **Named edits (out-of-map; not in `owned_files`)**. Each one: rebase onto the current branch tip first, state the edit in the commit message, touch nothing else of the file.
  - `tests/ci/test_mission_status_api_build.py`: the `NEW_FILES_IN_OUT_PACKAGES` probe list and its control only (plan 1.1 step 3a). WP17 (P13 part 1) owns the file.
  - `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5/traces/approach.md`: one append-only tracer entry (the surfaces this campsite surveyed and declined, plan section 9 table). Tracer files are never in `owned_files`.

**Path aliases used throughout this prompt** (all repo-relative): `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. The package root is `org.speckitty.missionstatus`.

## Objective

Make the surfaces this mission extends smaller and shareable before any functional change (charter Standing Order 2, C-011): extract `MissionLookup` and `OverviewReader` out of `MissionStatusQueryService`, add the public composition handle `MissionReadModel` that holds them and the one `ProjectionCache`, add the reusable head projection (`MissionHeadProjection`, `MissionHead`, `OverviewReader#head`) required by the operator's ruling A3 item 4, split `ArchitectureRules` into one builder per rule, and repair the one non-Java string site of the layout (the pin's probe list). Behaviour-preserving: every existing test is unchanged and green on the base and on the tip.

## Context

- Why it exists: the later detail route services (WP13 to WP16) need a probe-free Mission lookup and one derivation of the Mission head that `/missions` and `getMission` share (AC-1.2, NFR-009). Today `MissionStatusQueryService` (a god class; `MissionStatusService` before the re-cut) owns lookup, head derivation, projection, reduction, diagnostics and the stream entry points. Plan section 9 item 1 is the exact extraction.
- Order of work (D-44): P0 baseline record, then this campsite, then P1a, P1b, P3a, and only then P3 (the first functional change). A reviewer rejects a functional change that precedes this WP.
- Commit prefix for the extraction commits: `refactor(campsite)`. The red-first test commit prefix is `test(campsite)`. A reviewer greps these commits for a changed `assert`, expected value or golden byte of an **existing** test: there must be none.
- Layout facts you rely on (plan section 1.1, mapping rows 1 to 4, 7 to 9, 11 to 13; all **exist after the re-cut**, none exists in the checkout this prompt was authored against): `J/application/query/MissionStatusQueryService.java`, `J/application/query/ProjectionCache.java` (package-private, left alone), `J/application/query/port/in/MissionStatusQuery.java`, `J/application/query/port/out/MissionEventSource.java`, `J/domain/readmodel/overview/**`, `J/domain/redaction/{LeakClasses,Projector,ProjectionError}.java`. In the pre-re-cut checkout the same classes sit flat at `J/application/{MissionStatusService,ProjectionCache}.java` and `J/application/port/**`; use the checkout names **only** to read this prompt against an old tree, never in code you write.
- Why the services of the later routes sit in `application.query` itself (plan 1.1): `ProjectionCache`, `MissionLookup`, `OverviewReader` and `MissionHead` are package-private; a sub-package would force a public `ProjectionCache`. Do not widen a visibility ad hoc.
- Meta-read arithmetic the new tests pin (plan Readiness facts, FRESH3-002): `overview(ref)` reads the matched Mission's `meta.json` **2 times warm, 3 cold**; `find` followed by `head` reads it **3 times warm, 4 cold**. A separate `probed()` call or a `ledger(ref, mid8)` call after `head` would make it 4 and 5, which is the defect.

### Gate vocabulary used in this prompt

- **Gate G** (Java phase exit gate; plan sections 5 and 11), run from `S` under a UTF-8 file-name locale:
  `export LC_ALL=C.UTF-8` then `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`. Never `check` as a phase gate (it adds `perfTest`, `kitTest`, `nativeTagJvmTest`).
- **Gate P** (the pin): from the repository root `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`.
- Targeted red-first loop: `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.<package>.<Class>'`.
- **E-7 (operator word given 2026-10-13)**: before review you MAY additionally run locally `./gradlew --no-daemon check`, `nativeCompile nativeTest` and `nativeSmoke -PnativeBinary=<binary>`. CI remains the authority; a local green replaces no CI leg and a local red is classified (plan section 6), never retried to green. This WP does not need them (no new bean with reflective access).
- Python hygiene when the pin file is edited: `.venv/bin/ruff check . && .venv/bin/ruff format --check .` and `make format-check-files FILES="tests/ci/test_mission_status_api_build.py"`. Use `.venv/bin/...` only, never a bare `uv run`.
- The Windows-filename guard reads `git ls-files`: stage the new files **before** running `.venv/bin/python -m pytest tests/architectural/test_no_invalid_windows_filenames.py -q`, or it passes vacuously.

---

### Subtask T001: Pre-flight (first step of the phase): CoupledSymbolsShapeTest, tip record, string-literal grep

**Purpose**: C-005 and D-107. Prove that the tree you start from is the re-cut layout and that the coupled #5529 symbols have the shape this plan relies on, and record which #5529 tip you ran against. This is the first commit of the WP and the first step of every phase after an orchestrator-run merge of a #5529 tip.

**Steps**:
1. Confirm the start state: `git status` clean on your lane; `git log -1 --format=%H <the ref that carries #5529>` (today `refs/remotes/m5529/lane-b` = `4dc35c7d5d771cca96f83ef5789f115ca8209b61`, the merged re-cut tip is whatever the orchestrator merged: read it from the merge commit, do not guess). Record that sha in the **first commit message** of this WP.
2. Create `T/architecture/CoupledSymbolsShapeTest.java` (JUnit 5, package `org.speckitty.missionstatus.architecture`), written against rows 1 to 11 of the plan 1.1 mapping table:
   - For each row, `Class.forName("org.speckitty.missionstatus.<new name>")` loads (use a table of `String` names: this is test code, not `domain`/`application`, so the reflection ban of P1b does not apply to it). The new names: `application.query.MissionStatusQueryService`, `application.query.ProjectionCache`, `application.query.stream.{ChangeFeed,StreamSubscriber,Resume,StreamSettings}`, `application.query.port.in.{MissionStatusQuery,Subscription}`, `application.query.port.in.dto.{Change,ChangeBatch,Closure,PageRequest,StreamCursorText,StreamScope,StreamSignal}`, `application.query.port.in.exceptions.{MissionStatusUnavailable,StreamRefused}`, `application.query.port.out.MissionEventSource`, `application.query.port.out.dto.{LedgerRead,LedgerStamp,LedgerWindow,MissionRef,ProjectInputs}`, `application.query.port.out.exceptions.SourceFault`, `domain.readmodel.{overview,reducer,paging,cursor}` (one known class each: pick a class you have seen in the tree, for example `domain.readmodel.overview.OverviewDeriver`), `domain.redaction.{LeakClasses,Projector,ProjectionError}`.
   - Each checkout name must **not** load (`application.MissionStatusService`, `application.ProjectionCache`, `application.port.in.MissionStatusQuery`, `domain.projection.LeakClasses`, ...): assert `ClassNotFoundException`.
   - Shape facts: `ProjectionCache` is package-private (not `Modifier.isPublic`); `MissionStatusQueryService` has a **public six-argument** constructor and a **package-private seven-argument** constructor with the parameter types `(MissionEventSource, Clock, Consumer<Diagnostic>, ScheduledExecutorService, StreamSettings, LeakClasses, ProjectionCache)`; `SourceFault.Kind` has **exactly five values** (the one exact assertion: no phase touches it, D-91); `AllowlistAccess` declares at least the four methods `openRead`, `stat`, `realPath`, `listNames(Path)` (a presence check: P5 adds `scoped(ReadScope)` and `listNames(Path, int)`).
   - Lower bounds only for what this mission extends (D-117, so the test stays green after P5 and P8): at least 15 `Allowlist.PathClass` values, at least 11 `ENTRIES`, at least 8 `DiagnosticCode` values, `ArchitectureRules.DEFINED_RULE_COUNT >= 12`. Never an equality on these.
   - Every production class sits under `adapter`, `application`, `config` or `domain` (scan the class path of the main source set; no sibling top-level package can escape the JaCoCo patterns and the ArchUnit rules).
   - Stream assertions are written in their **pre-ruling shape** (`Change` and `ChangeBatch` in `port.in.dto`; `StreamSignal` with `Forwarded` and `Truncated`); WP02 edits exactly those assertions in the commit that retypes the symbols (named edit).
3. Run the C-005 string-literal grep and read every hit:
   `grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' services/mission-status-api/src/test services/mission-status-api/build.gradle.kts`
   Each hit must name a class of the right-hand column of the mapping table or be one of the two JaCoCo wildcards. A stale name (a checkout name still held in a string, for example in `FilesystemFixtureFactory#fromTreeWithOrdering`, `ArchitectureRulesTest`, `PortLevelClassSetTest`) means the re-cut left an inconsistency: report it to the orchestrator as an item (plan 1.1 step 4: the table is amended by a decision note in both missions' records, never by this WP on its own authority). Do not fix files you do not own.
4. Run the old-path grep and note the three expected hits in the tuple of the pin file (fixed by T006):
   `grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github`.

**Files**: `T/architecture/CoupledSymbolsShapeTest.java` (new, ~150 lines).

**Validation**: `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'` is green on the re-cut tree (it is red on the flat tree by design: if it is green there, it is vacuous). The first commit message carries the #5529 tip sha.

---

### Subtask T002: Extract MissionLookup and OverviewReader (refactor(campsite))

**Purpose**: split the scan of `resolve` and the overview derivation out of `MissionStatusQueryService`, with every existing answer and recorded access byte for byte unchanged (plan section 9, item 1).

**Steps** (package `org.speckitty.missionstatus.application.query`; both classes **package-private**):
1. `MissionLookup`: the probe-free lookup `find(MissionId)` that returns the first readable Mission while remembering the first fault, plus the optional continuation that detects a second readable directory carrying the id (D-58). `MissionStatusQueryService.resolve` becomes `MissionLookup.find` followed by the service's own `probed`; `project()`, `missions()` and the stream methods keep their answers and their recorded accesses.
2. `OverviewReader`: owns the one `ProjectionCache`; moves `overview(ref)`, `ledger(ref, mid8)`, `derive`, `requireInstant` and the omission table out of the service. (`head(ref)` arrives in T004; in this subtask `overview(ref)` is the moved body.)
3. `MissionStatusQueryService` delegates to both and keeps: the package-private accessors `cache()` and `feed()`, its **public six-argument constructor**, and the **package-private seven-argument constructor with its parameter types** (nothing in production calls it; `FilesystemFixtureFactory#fromTreeWithOrdering` reflects it to inject a reducer ordering, AC-8a). `MissionStatusQueryServiceTest`, `FailLoudMappingTest`, `SubscribeConnectTest` and `ProjectionCacheTest` must compile and pass **unchanged**.
4. `ProjectionCache` is left alone. It is not in `owned_files`; do not edit it.
5. Tests (new files, unit level, no Spring): `T/application/query/MissionLookupTest.java` (first readable wins; the first fault is remembered; the continuation finds a second readable directory; a faulted sibling before the match does not stop the lookup, D-39) and `T/application/query/OverviewReaderTest.java` with the **meta-read control**: over the recording allowlist seam, `overview(ref)` records 2 reads of the matched Mission's `meta.json` warm and 3 cold. Write the control now against `overview`; T004 extends it to `head`.
6. Commit as `refactor(campsite): extract MissionLookup and OverviewReader`. Diff check you run before committing: `git diff <base>..HEAD -- S/src/test` shows only **added** files and no changed line in an existing test.

**Files**: `J/application/query/MissionLookup.java` (new, ~110 lines), `J/application/query/OverviewReader.java` (new, ~170 lines), `J/application/query/MissionStatusQueryService.java` (shrinks), `T/application/query/MissionLookupTest.java` (new, ~120), `T/application/query/OverviewReaderTest.java` (new, ~140).

**Validation**: `--tests '*MissionLookupTest' --tests '*OverviewReaderTest' --tests '*MissionStatusQueryServiceTest' --tests '*FailLoudMappingTest' --tests '*ProjectionCacheTest'` green; the pre-existing tests were not touched.

---

### Subtask T003: MissionReadModel composition handle, single bean, kept constructors

**Purpose**: the detail services live in `application.query` but are constructed from `config` (another package). One public handle gives `config` a way to hand the same cache to four new services without widening `ProjectionCache` (D-93).

**Steps**:
1. `J/application/query/MissionReadModel.java`: `public final class MissionReadModel`, holding the `MissionLookup`, the `OverviewReader` and so the one `ProjectionCache`. A **public constructor** builds its own cache; a **package-private constructor** takes a given `ProjectionCache` (the seven-argument service constructor delegates to it). It exposes the lookup and the head derivation to same-package callers through package-private accessors `find(MissionId)` and (after T004) `head(MissionRef)`; the visibility stays package-level so rule 3 can bar an adapter from naming it (PLAN-FRESH3-008).
2. `MissionStatusQueryService` gains a **new public constructor** that takes a `MissionReadModel`; the existing public six-argument constructor stays and builds its own read model; the seven-argument package-private constructor stays and delegates to the package-private `MissionReadModel` constructor.
3. `J/config/ServiceWiring.java`: build the `MissionReadModel` **once, as one bean**, and pass it to `MissionStatusQueryService` through the new constructor. This is the first of the two edits ServiceWiring receives (WP02 makes the second, the `maxConnections` setting, before P3; after that never).
4. Tests: `T/application/query/MissionReadModelTest.java` (two consumers of one instance reduce one ledger once: the second `head`/`overview` is a cache hit) and `T/config/ReadModelSingletonTest.java` (a Spring context built from `ServiceWiring` holds exactly one `MissionReadModel` bean, and the `MissionStatusQueryService` bean was built from it: assert identity of the cache reached through the read model and through the service).
5. Extend `CoupledSymbolsShapeTest` (T001): pin **both** constructors of `MissionReadModel` by reflection (public builds its own cache; package-private takes a `ProjectionCache`) and the literal class name `FilesystemFixtureFactory` loads for `ProjectionCache`.

**Files**: `J/application/query/MissionReadModel.java` (new, ~70), `J/application/query/MissionStatusQueryService.java`, `J/config/ServiceWiring.java`, `T/application/query/MissionReadModelTest.java` (new, ~110), `T/config/ReadModelSingletonTest.java` (new, ~80).

**Validation**: `--tests '*MissionReadModelTest' --tests '*ReadModelSingletonTest' --tests '*CoupledSymbolsShapeTest'` green; every existing test compiles and passes unchanged (they use the six-argument constructor).

---

### Subtask T004: Reusable head projection (operator ruling A3 item 4)

**Purpose**: make `OverviewReader#head(ref)` the **only** way to obtain a projected Mission head, so `/missions` and `getMission` share one derivation, one projection and one cache by construction (D-123). The detail services take the per-Work-Package snapshot from `MissionHead#entry`; none may call `OverviewReader#ledger(ref, mid8)` (a second stamp: a fourth `meta.json` read).

**Steps**:
1. `J/application/query/MissionHeadProjection.java` (package-private): the extracted `projected(MissionOverview, mid8)`, `withProjectedDates(MissionMeta)` and `instantOrNull` that are private in `MissionStatusQueryService` today. Moved with no logic change.
2. `J/application/query/MissionHead.java`: a **package-private record** `MissionHead(MissionOverview overview, ProjectionCache.Entry entry)`: the projected overview and the cache entry (the whole `StatusSnapshot` with its per-Work-Package state) it was derived from.
3. `OverviewReader#head(MissionRef)` returns `Optional<MissionHead>` from **one pass** (`readMeta`, the ledger stamp, at most one ledger read). `overview(ref)` now **delegates to `head`**, so there is exactly one derivation. `MissionReadModel` exposes `find` and `head`.
4. Extend the tests: `OverviewReaderTest` and `MissionReadModelTest` assert the AC-1.8(c) totals on the extracted path: `head` records **the same reads `overview` recorded (2 warm, 3 cold)**; `find` followed by `head` records **3 warm and 4 cold**. New `T/application/query/MissionHeadProjectionTest.java`: the projection of the head dates and the credential/path refusals are exactly those `/missions` produced before (use the existing overview golden fixtures as inputs; do not change any golden).
5. Commit as `refactor(campsite): extract the Mission head projection`.

**Files**: `J/application/query/MissionHeadProjection.java` (new, ~120), `J/application/query/MissionHead.java` (new, ~25), `OverviewReader.java`, `MissionReadModel.java`, `T/application/query/MissionHeadProjectionTest.java` (new, ~130), the two test files above (extended; they are new in this WP so extending them is not a change to an existing test).

**Validation**: `--tests '*OverviewReaderTest' --tests '*MissionReadModelTest' --tests '*MissionHeadProjectionTest'` green; `GoldenRoutesTest` and the overview conformance suites unchanged and green (byte-identical overview).

---

### Subtask T005: ArchitectureRules builder split and HeadProjectionOwnershipTest (non-vacuous)

**Purpose**: item 2 of the campsite (one builder per rule, so rules 13 to 16 land as builders, not as screens of one method) and the ArchUnit gate that makes T004 binding.

**Steps**:
1. `T/architecture/ArchitectureRules.java`: split `all(root, rule9Packages)` into one private builder per rule (`rule1(root)` ... `rule12(root)`, plus the suffix-per-rule builders), each returning `Rule`; `all()` composes them **in order**. Rule ids 1 to 12 are unchanged and `DEFINED_RULE_COUNT` stays **12**. `ArchitectureRulesTest` and `ArchitectureControlsTest` pass **unchanged** (they are WP03's files from the next phase on; do not edit them here).
2. `T/architecture/HeadProjectionOwnershipTest.java`: an ArchUnit call-site gate. Subject: classes of `application.query..` other than `OverviewReader` and `MissionHeadProjection`. Rule: none of them calls `OverviewDeriver#derive` or any method of `MissionHeadProjection`. Non-vacuous: assert a non-zero scanned count (the subject has at least `MissionStatusQueryService`, `MissionLookup`, `MissionReadModel`).
3. Planted fixture `T/architecture/fixture/application/query/HeadBypass.java`: a class in the fixture tree that calls `OverviewDeriver#derive` (or `MissionHeadProjection`) directly. The fixture root evaluates the same predicate and must be red on `HeadBypass` only. Remember the fixture-tree mirror rule (plan 1.1 row 13): the fixture sits under `architecture/fixture/application/query/`.
4. Revert-fails rows (state in the commit, do not leave in the tree): add a second class in `application.query` that derives its own head, or make `head` re-read `meta.json`: `HeadProjectionOwnershipTest` or the read-count control goes red.
5. **Red-first proof for this subtask**: commit `HeadBypass` and the test's planted-violation control first, show the control red against a rule that does not yet forbid it (record the red run in the commit message), then add the rule.

**Files**: `T/architecture/ArchitectureRules.java` (restructured), `T/architecture/HeadProjectionOwnershipTest.java` (new, ~90), `T/architecture/fixture/application/query/HeadBypass.java` (new, ~20).

**Validation**: `--tests '*ArchitectureRulesTest' --tests '*ArchitectureControlsTest' --tests '*HeadProjectionOwnershipTest'` green; the two pre-existing ArchUnit test classes are untouched.

---

### Subtask T006: Named edit of the pin: NEW_FILES_IN_OUT_PACKAGES (plan 1.1 step 3a)

**Purpose**: the pin's probe list builds paths for the flat packages that no longer exist after the re-cut, so the guard behind "a new file in an `out` package must not be git-ignored" would quietly stop testing the packages this mission fills (PLAN-FRESH4-007, D-143). This is the first phase on the re-cut tree and it runs the pin, so it makes the edit; WP17 stays the owner of the file.

**Steps** (file `tests/ci/test_mission_status_api_build.py`; change **only** the probe tuple and add the control; rebase first, say "named edit of the pin: probe list only (WP01, plan 1.1 step 3a)" in the commit message):
1. `NEW_FILES_IN_OUT_PACKAGES` becomes **twelve** probe paths of the form `src/<tree>/java/org/speckitty/missionstatus/<package>/NewFile.java`:
   - `main` and `test` trees, `<package>` in: `application/query/port/out`, `application/query/port/out/dto`, `application/query/port/out/exceptions`, `adapter/out`. That is 4 packages x 2 trees = 8 paths.
   - `test` tree only (4 paths), `<package>` in: `architecture/fixture/application/query/port/out`, `architecture/fixture/application/query/port/out/dto`, `architecture/fixture/application/query/port/out/exceptions`, `architecture/fixture/adapter/out`.
   - 8 + 4 = **12**.
2. Add a pure function `out_probe_violations(entries)` returning a violation for (a) any entry that still holds a flat `application/port/` or `fixture/application/port/` segment and (b) a missing probe (each of the twelve expected paths must be present).
3. Add a control in the same file that passes `out_probe_violations` the **six old flat entries** and requires violations; and a test that passes the real tuple and requires none. A list edited back, or never edited, is then red, not vacuously green.
4. Keep `STILL_IGNORED` and `_is_ignored` as they are; the existing assertion `[rel for rel in NEW_FILES_IN_OUT_PACKAGES if _is_ignored(rel)] == []` now runs over the twelve paths. If a probe is ignored, the `.gitignore` re-include `!/src/**/out/` does not reach it: report it, do not edit `.gitignore` (not yours).
5. Confirm the old-path grep is **empty** from here on: `grep -rnE 'application/port|domain/(overview|reducer|projection|paging|cursor)' tests scripts .github` (the three tuple hits of T001 are gone, and nothing else matches).

**Files**: `tests/ci/test_mission_status_api_build.py` (named edit, ~+45 lines).

**Validation**: Gate P green. Red-first: before the edit, run the control against the unmodified tuple and record that `out_probe_violations` flags the six flat entries (the control is red on the old list). Then `.venv/bin/ruff check tests/ci/test_mission_status_api_build.py && make format-check-files FILES="tests/ci/test_mission_status_api_build.py"`.

---

### Subtask T007: JaCoCo class-floor count (application line)

**Purpose**: `R/jacoco-class-floor.properties` carries hand-edited counts that must equal what the build's own command prints at the commit that adds the classes (plan section 2; floor semantics, D-65). You own the file; later phases write named edits.

**Steps**:
1. After T002 to T004 are committed, run Gate G's `test jacocoTestReport` from `S` and then the plan section 2 command from `S`:
   `python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"`
2. The `application` line becomes the number printed. The classes this WP adds (with nested ones): `MissionLookup`, `OverviewReader`, `MissionReadModel`, `MissionHeadProjection`, `MissionHead` (plan 15.7). The `domain` line is **unchanged** (this WP adds no domain class). Do not predict the number: record the printed value, and in the commit message the count before and after.
3. Edit only the `application=` line. The file is `application=<n>` and `domain=<m>` (two lines); the keys stay.
4. Every new application class must meet the 0.90 per-class line floor (and the package-private `MissionHead` record must be covered by `MissionHeadProjectionTest`/`OverviewReaderTest`): `jacocoTestCoverageVerification` is part of Gate G.

**Files**: `R/jacoco-class-floor.properties` (one line).

**Validation**: `jacocoScopeCheck` green (the recorded count is not greater than the classes found); the diff of the file is exactly one line and equals the classes this WP added.

---

### Subtask T008: Phase gate, diff check and the approach tracer entry

**Purpose**: the exit evidence of the WP.

**Steps**:
1. **Gate G** (`LC_ALL=C.UTF-8`): `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`. Every existing test unchanged.
2. **Gate P**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q` (stage the new files first; the pin's tracked-path scan reads `git ls-files` of `S`).
3. `CoupledSymbolsShapeTest`, `OverviewReaderTest`, `MissionReadModelTest`, `MissionHeadProjectionTest`, `HeadProjectionOwnershipTest`, `ReadModelSingletonTest`, `MissionLookupTest` by name.
4. The `refactor(campsite)` diff check: for the extraction commits, `git diff <WP base>..HEAD -- services/mission-status-api/src/test` lists only added files and no changed or deleted line in a test that existed before; `git diff ... | grep -E '^[-+].*(assert|expected|golden)'` over pre-existing test files is empty.
5. Hygiene: Windows-filename guard after staging (`.venv/bin/python -m pytest tests/architectural/test_no_invalid_windows_filenames.py -q`); the terminology grep `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md | grep -v 'non-numeric-number feature'` is empty; ruff check and format for the pin file.
6. Append **one** entry to `M/traces/approach.md` (append-only; dated-entry format `- **[YYYY-MM-DD][P1] Short symptom.** 1-3 sentences; disposition.`): record the surveyed-and-left-alone surfaces of plan section 9 (`FilesystemMissionEventSource*`, `Allowlist`, `SafeFiles`, the strict-UTF-8 sites (D-116), `ChangeFeed`, `StatusReducer`, `RowClassifier`/`LedgerLineDecoder`, `ProjectionCache`, `ArchitectureRules` only split, `build.gradle.kts`, `ProblemMapper`/`ProblemAdvice`, `LeakClasses`/`DiagnosticCode`, `AllowlistAccess`/`AllowlistPassThrough`, `ServiceWiring`/`MissionStatusProperties`/`StreamSettings`, `StreamSubscriber`/`Resume`) each with its reason, and the fact that Java has no Sonar signal (`sonar.sources=src`). Named edit: touch nothing else of the file.
7. Optional local E-7 evidence for the reviewer: `./gradlew --no-daemon check` from `S` (state the result in the hand-off, never as a substitute for CI).

**Files**: `M/traces/approach.md` (append).

**Validation**: all of the above green; report the exact commands and the pass/fail counts in the hand-off.

---

## Self-contained green

This WP's tip, and PR A's tip, must be green on every CI gate on their own (plan section 11, "Each PR is self-contained", D-153).

- **Fixtures live with their tests (plan 11, "Green at every tip")**: the only fixture added is the planted `HeadBypass` (`T/architecture/fixture/application/query/HeadBypass.java`), read only by `HeadProjectionOwnershipTest`. The conforming skeleton (`Service`, `Query`, `Source`) is the one the fixture tree already holds and keeps its path under the mirror rule (row 13); you do not move it.
- **Floors and counts satisfiable now**: `jacoco-class-floor.properties` `application` is the number the section 2 command prints at the commit adding the five classes; `domain` unchanged; `DEFINED_RULE_COUNT` stays 12 (raised by WP03 and later WP12); `CoupledSymbolsShapeTest` uses lower bounds and presence only, so it stays green after WP09 and WP12 (D-117). Rule 3 and the discovered-adapter-set pin do not exist yet.
- **No test or gate names a type of a later WP**: nothing here names `StreamEvent`, `EventProjection`, `WpId`, `MissionDetailQuery`, `TextSource` or any other later class (PLAN-FRESH4-001, D-139). `CoupledSymbolsShapeTest` names only #5529 types and this WP's own.
- **Pin `tests/ci/test_mission_status_api_build.py` clauses kept green**: the probe-list clause is the one this WP rewrites (plan 11, "Pin ... clause by clause": "the probe list (P1)"); the tracked-path scan (every phase; stage new files first); the rule-9 literals of `ArchitectureRulesTest` (untouched here, so unchanged); the `EventsController` needles (untouched); `HTTP_MAIN` sub-directory names (no new `adapter/in/http` directory).
- **Mission record stays complete (plan 11, "The Mission record at each tip")**: you edit no `meta.json`, no `status.events.jsonl`, no `status.json`; the only `M/` file you touch is the append to `traces/approach.md` (matches the `.gitattributes` rule `kitty-specs/**/traces/*.md merge=spec-kitty-traces`). `status.json` is only ever produced by `spec-kitty agent status materialize --mission <slug>`, never by hand, so cutover-guard, the mission-state audit and corpus-blocking see a complete record; do not commit untracked CLI state blind (compare with the coordination copy first). If the orchestrator asks you to run the audit: `.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json > "<scratch>/audit.json"; echo "exit $?"` (scratch outside the repository).
- **PR A needs nothing from P13**: no `@Tag("native")` test is added (the pinned count stays 3), no smoke stage, no workflow line, no `requests.json` edit.

## Baseline precondition check (AC-21.1 to AC-21.3)

Before claiming: `traces/baseline-red.yaml` is present and the `test_baseline_record_*` tests of `tests/contract/test_mission_status_conformance.py` are green on the tip you start from; the first commit of this work package is a descendant of the commit that added the record (`git merge-base --is-ancestor`). If either fails, stop and report.

## Plan defects found

- None blocking this WP. Notes for the orchestrator: (1) plan 1.1 step 3a says "twelve probe paths" and lists the packages per tree; the count is 8 (main+test x 4) + 4 (test fixtures) = 12, which T006 states explicitly. (2) T001's "red on the flat checkout by design" cannot be demonstrated until the re-cut is merged; the red-first evidence for `CoupledSymbolsShapeTest` is therefore a run on a copy of the tree with one class moved back to its checkout name (scratch copy, never the working tree under review).

## Definition of Done

- [ ] All eight subtasks have a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- [ ] First commit message carries the #5529 tip sha and the `CoupledSymbolsShapeTest` pre-flight; the C-005 string-literal grep and the old-path grep outputs are in the hand-off.
- [ ] `MissionLookup`, `OverviewReader` (package-private), `MissionReadModel` (public), `MissionHeadProjection` (package-private), `MissionHead` (package-private record) exist in `J/application/query/`; `MissionStatusQueryService` delegates; the six-argument public and seven-argument package-private constructors are kept and pinned.
- [ ] `head` records 2 reads warm / 3 cold; `find` then `head` records 3 warm / 4 cold; `HeadProjectionOwnershipTest` is non-vacuous and red on `HeadBypass`.
- [ ] `ArchitectureRules` split into one builder per rule, `DEFINED_RULE_COUNT` = 12, ids unchanged, the two ArchUnit test classes unedited.
- [ ] Probe list rewritten to twelve paths with `out_probe_violations` and its control; the old-path grep is empty.
- [ ] `application` count line equals the section 2 command output at the adding commit; `domain` unchanged.
- [ ] Gate G and Gate P green; no changed assertion, expected value or golden byte in any pre-existing test.
- [ ] `traces/approach.md` has the one appended entry; nothing else outside `owned_files` and the two named edits changed.

## Risks

- **Re-cut not merged or different from the table**: stop and report; never improvise a layout. A difference between the tip and plan 1.1 is an orchestrator item.
- **Hidden fourth `meta.json` read**: calling `OverviewReader#ledger(ref, mid8)` or a separate `probed()` after `head` moves the count to 4 warm / 5 cold. The read-count controls exist to catch it.
- **Over-pinning `CoupledSymbolsShapeTest`**: an equality on a count this mission raises (15 `PathClass`, 11 `ENTRIES`, 8 `DiagnosticCode`, rule count 12) turns red after WP09 or WP12. Lower bounds and presence only.
- **Vacuous guard**: the Windows-filename guard and the pin read `git ls-files`; run them only after staging new files.
- **Ignored `out` directory**: a probe path under `out/` that `git check-ignore` flags is a `.gitignore` problem you do not own; report it.

## Reviewer Guidance

- Verify the commit-prefix discipline: `refactor(campsite)` commits touch no existing test line (grep the diff for changed `assert`, `expected` and golden lines); `test(campsite)` is for the new tests.
- Confirm the head projection has one owner: only `OverviewReader` and `MissionHeadProjection` derive a head; `overview(ref)` delegates to `head`; `HeadProjectionOwnershipTest` is red on the planted `HeadBypass` and non-zero scanned.
- Confirm the meta-read totals (2/3 and 3/4) in `OverviewReaderTest` and `MissionReadModelTest`, and that `ProjectionCache.java` is untouched.
- Check the JaCoCo diff is one line and equals the classes added; run the section 2 command yourself on the tip.
- Check the pin edit is the probe list and its control only; `out_probe_violations` flags the six old entries.
- Reject a visibility widening of `ProjectionCache`, `MissionLookup`, `OverviewReader` or `MissionHead`.

## Implementation command

```bash
spec-kitty agent action implement WP01 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
