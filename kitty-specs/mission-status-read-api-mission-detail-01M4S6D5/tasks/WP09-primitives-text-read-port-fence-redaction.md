---
work_package_id: WP09
title: '[PR A] P5 Primitives: text-read port, read fence, redaction (FR-007, FR-008, FR-011)'
dependencies:
- WP05
requirement_refs:
- FR-007
- FR-008
- FR-011
- FR-012
- FR-010
- FR-004
- FR-005
- NFR-002
- NFR-003
- NFR-005
- C-006
- C-008
- SC-003
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T03:27:18.908852+00:00'
subtasks:
- T056
- T057
- T058
- T059
- T060
- T061
- T062
- T063
- T064
- T065
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/TextSource.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/FileRef.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/RelativePath.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/ReadScope.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/DirListing.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/EntryStat.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/BytesRead.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/TextRead.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/TextRefusal.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/TextRefusals.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/exceptions/TextFault.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/FilesystemTextSource.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/NameEncoding.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/StrictUtf8.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/redaction/TextScreen.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/redaction/LeakClasses.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/ArtifactKinds.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/ArtifactPaths.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactKind.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/artifact/Eligibility.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/port/out/dto/TextRefusalTableTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/port/out/exceptions/SourceFaultKindsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/NoUnboundedListingTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/A2cByteBuffer.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/TextSource.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/FileRef.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/RelativePath.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/ReadScope.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/DirListing.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/EntryStat.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/BytesRead.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/TextRead.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/TextRefusal.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/dto/TextRefusals.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/exceptions/TextFault.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/FilesystemTextSource.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/NameEncoding.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/Allowlist.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/AllowlistAccess.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/AllowlistPassThrough.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/SafeFiles.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/StrictUtf8.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/redaction/TextScreen.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/redaction/LeakClasses.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/DiagnosticCode.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/ArtifactKinds.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/derive/ArtifactPaths.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/readmodel/detail/ArtifactKind.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/artifact/Eligibility.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/FilesystemTextSource*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/NameEncoding*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/Allowlist*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/AllowlistAccess*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/SafeFiles*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/RecordingAllowlistAccess.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/AllowlistReadmeParityTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/StrictUtf8*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/redaction/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/ArtifactKinds*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/readmodel/derive/ArtifactPaths*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/artifact/Eligibility*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/port/out/dto/TextRefusalTableTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/port/out/exceptions/SourceFaultKindsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/NoUncappedReadTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/NoUnboundedListingTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/A2cByteBuffer.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP09 – [PR A] P5 Primitives: text-read port, read fence, redaction (FR-007, FR-008, FR-011)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: **PR A**, plan phase **P5** (a draft stacked on the branch that carries #5529's last slice; no route is served in PR A).
- **External dependency (not a `dependencies` entry)**: WP01 cannot start until the orchestrator has merged the re-cut tip of #5529 (the side-first layout) into this branch. PR A stacks on #5529's last slice and cannot merge before #5529 (C-005). #5533's Java work stacks on PR A, and this WP is the source of every seam in plan section 7.1 rows 1 to 7, 9, 10 and the recorder of row 11. By the time WP09 is claimed, WP01..WP05 are approved, so the re-cut layout exists in the lane workspace.
- **Write scope**: `owned_files` of the frontmatter only. Nothing else may be created or edited except the named edits below.
- **Named edits (out-of-map)**. Each one: rebase onto the current lane tip first, state the edit in the commit message, touch nothing else of the file.
  - `T/architecture/ArchitectureControlsTest.java`: add the `A2cByteBuffer` planted control only (owned by WP03; P1b).
  - `S/README.md`, allowlist section only: the fence list (first fenced list) and the "never opened" sentence (owned by WP17; P13). It must change in the same commit as `Allowlist.PATTERNS` because `AllowlistReadmeParityTest` compares them.
  - `R/jacoco-class-floor.properties`: the `application` and `domain` count lines only (owned by WP01).
  - M/traces/approach.md, M/traces/design-decisions.md, M/traces/tooling-friction.md: append-only tracer entries (charter Standing Order 3); never rewrite an earlier entry.
- **Alias key used in this file**: `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Every path in this file written with these aliases is the **post-re-cut** path (plan section 1.1 mapping table) unless it says "exists at the checkout".

## Objective

Land the shared read primitives of the mission in one phase, before any route: the capped, allowlisted text-read port (`TextSource`) with its vocabulary, the file-system adapter (`FilesystemTextSource`, `StrictUtf8`, `NameEncoding`, `SafeFiles.readCapped`, the bounded `listNames`), the read-fence amendment (ten new `PathClass` values, eleven new entries, scope-aware `classify`), the artifact-path, kind and eligibility rules, the redaction function (`TextScreen`, `LeakClasses.credential`) with its nine new `DiagnosticCode` values, and the guards that keep the fence closed (`NoUncappedReadTest`, `NoUnboundedListingTest`, the `A2cByteBuffer` control). Nothing in this WP serves a route.

## Context

- **Why now.** Plan section 11 puts P5 before every route phase because #5533's Java work imports these seams (plan section 7). A name in plan section 7.1 is frozen from the commit that lands this phase (stability promise, plan section 7 intro); a later change needs a decision note in both missions' `traces/design-decisions.md` and the operator's word.
- **Who consumes it.** WP10 (P7) builds `InMemoryTextSource`, `DetailFixture`, `CapRaceInjector` and the recorder's route supplier hook on this port. WP11 (P6) uses `Eligibility`, `ArtifactPaths`, `NameEncoding`/`DirListing.Names.trustworthy` and `readBytes`. WP12 (P8) uses `TextSource` in `DetailInfrastructureWiring` and maps `TextRefusal` to `DetailRefusal`. P11/P12 (PR B) use the rest.
- **Layout (plan section 1.1, 13).** Ports are interfaces only (rule 13): `TextSource` sits directly in `application.query.port.out`; every data type in `port/out/dto`; `TextFault` in `port/out/exceptions`. `SourceFault` and its `Kind` (five values) are **not touched** (D-91, D-68): `TextFault` is a new type so none of the four exhaustive switches over `SourceFault.Kind` changes (`ChangeFeed#metaStageCode`, `ChangeFeed#ledgerStageCode`, `MissionStatusQueryService#ledgerFault`, `MissionStatusQueryService#omitted`).
- **Key decisions to honour.** D-70 (strict UTF-8 decode lives only in `adapter.out.filesystem.codec.StrictUtf8`, rules 1b/2b forbid `ByteBuffer` elsewhere; the application never sees bytes of a text read; the NUL decision is the application's over the decoded `String`), D-77 (scope views of the fence), D-92 (bounded listing), D-116 (the three inline strict decoders of #5529 are left alone), D-68 (over-cap and I/O failure are distinct kinds), FRESH3-004 (`NameEncoding` and `trustworthy`).
- **Exists at the checkout (flat, unchanged location):** `J/adapter/out/filesystem/{Allowlist,AllowlistAccess,AllowlistPassThrough,SafeFiles}.java`, `T/adapter/out/filesystem/{RecordingAllowlistAccess,AllowlistReadmeParityTest}.java`, `T/architecture/{NoUncappedReadTest,ArchitectureControlsTest,ArchitectureRulesTest,ArchitectureRules}.java`, `J/domain/model/DiagnosticCode.java` (eight values today). **Exists after the re-cut, at the paths of plan section 1.1:** `J/domain/redaction/LeakClasses.java` (checkout: `domain/projection/LeakClasses.java`), `T/domain/redaction/LeakClassesPythonParityTest.java` (checkout: `T/domain/projection/`), `J/application/query/port/out/dto/MissionRef.java` (checkout: `application/port/out/MissionRef.java`), `J/application/query/port/out/exceptions/SourceFault.java`. **New in this WP:** everything else named below.

### Subtask T056: Pre-flight, then red-first tests

**Purpose**: prove the tree is the re-cut layout this WP relies on (C-005), then write the failing tests before any class (red-first, plan section 11 P5 row).

**Steps**:
1. Pre-flight (first step of every phase, D-107). From `S`: `./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'` with `LC_ALL=C.UTF-8` and the `CONTRACT_BUNDLE` / `CONTRACT_BUNDLE_SHA256` variables exported (plan section 5, Java block). It must be green. If it is red, the lane tree is not the re-cut tip: stop and report to the orchestrator (an orchestrator item, plan section 1.1 step 4); do not fix it here.
2. Record the #5529 tip: `git log -1 --format=%H refs/remotes/m5529/lane-b` (plan section 5 names `4dc35c7d5d771cca96f83ef5789f115ca8209b61` as today's value; use what the orchestrator tells you if it differs) and put the sha in the first commit message of this WP.
3. Run the C-005 string-literal grep: `grep -rnE '"org\.speckitty\.missionstatus\.(application|domain)' services/mission-status-api/src/test services/mission-status-api/build.gradle.kts`. Every hit must name a class of the right-hand column of plan section 1.1 or one of the two JaCoCo wildcards. Paste the result into the commit message.
4. Write the new tests first (they cannot compile until T057..T062 add the types, which is the red state on the phase base; for the changed classes `Allowlist`, `SafeFiles`, `AllowlistAccess` the tests compile and fail by assertion):
   - `T/application/query/port/out/dto/TextRefusalTableTest.java`
   - `T/application/query/port/out/exceptions/SourceFaultKindsTest.java`
   - `T/domain/readmodel/derive/ArtifactPathsTest.java`, `ArtifactKindsTest.java`
   - `T/application/query/artifact/EligibilityTest.java`
   - `T/adapter/out/filesystem/FilesystemTextSourceTest.java` (+ `...CapRaceTest` if you split), `NameEncodingTest.java`, `SafeFilesReadCappedTest.java`, `AllowlistScopeTest.java` (controls of AC-11.2/11.4), `AllowlistAccessScopedTest.java`, `codec/StrictUtf8Test.java`
   - `T/domain/redaction/TextScreenTest.java`, plus the extension of `LeakClassesPythonParityTest`
   - `T/architecture/NoUnboundedListingTest.java` (new) and the edit of `NoUncappedReadTest.java`
5. Run the new tests once and keep the failing output (counts) for the tip commit message: this is the red-first evidence.

**Files**: tests only in this subtask (~12 new test classes across T057..T063; sizes are given in each later subtask).

**Validation**: `CoupledSymbolsShapeTest` green; the new tests fail (compile error or assertion) on the phase base; the grep result and the #5529 sha are in the first commit message.

### Subtask T057: Port vocabulary (S-8)

**Purpose**: create the text-read port and everything it exchanges, exactly as plan section 7.1 designs it (rows 1 to 6); this is the surface #5533 imports.

**Steps** (all new files, package `org.speckitty.missionstatus.application.query.port.out...`):
1. `J/application/query/port/out/TextSource.java`: interface only, four methods and nothing else: `DirListing list(FileRef dir, int nameLimit, ReadScope scope)`; `EntryStat stat(FileRef path, ReadScope scope)`; `BytesRead readBytes(FileRef file, int cap, ReadScope scope)`; `TextRead readText(FileRef file, int cap, ReadScope scope)`. No `Path`, no `IOException`, no route or Work Package vocabulary (AC-7.3). It throws `TextFault` (unchecked).
2. `dto/FileRef.java`: sealed; `MissionFile(MissionRef mission, RelativePath path)` (relative to that Mission's **primary** directory) and `ProjectFile(RelativePath path)` (relative to the project root). `MissionRef` is the only Mission-status vocabulary on the port.
3. `dto/RelativePath.java`: record over `List<String> segments`; `of("a/b")` rejects an empty segment, `.`, `..`, a backslash, a NUL and a leading `/` (throws `IllegalArgumentException`); `child(String)`, `parent()`, `last()`.
4. `dto/ReadScope.java`: enum `AUTHORED`, `ARTIFACT` only (#5533 adds `GOVERNANCE`; do not add it).
5. Result types: `DirListing` (sealed: `Names(List<String> names, boolean limitReached, boolean trustworthy)` | `Absent` | `NotADirectory`); `EntryStat` (sealed: `Absent` | `Present(EntryKind kind, long sizeBytes, long modifiedEpochSecond)`, with `EntryKind` FILE, DIRECTORY, SYMLINK, OTHER as a nested enum; an `lstat`, a link is never followed); `BytesRead` (`Bytes(byte[])` | `Absent` | `NotRegular` | `OverCap`); `TextRead` (`Text(String text, long sizeBytes)` | `Absent` | `NotRegular` | `OverCap` | `NotText`).
6. `dto/TextRefusal.java`: enum with exactly the seven kinds of plan 7.2: `NOT_FOUND`, `NOT_REGULAR`, `PATH_REFUSED`, `OVER_CAP`, `NOT_TEXT`, `SECRET_REFUSED`, `IO_FAILURE`. `dto/TextRefusals.java`: the pure function `TextRefusals.of(...)` total over every outcome that can refuse: `BytesRead`/`TextRead` results, a `TextFault.Kind`, a `TextScreen.Screened.SecretFound` (overloads; `TextScreen` is created in T062, so write this overload against the T062 type and order the commits so the file compiles: add `TextScreen` first or in the same commit).
7. `exceptions/TextFault.java`: `final`, unchecked, no message; nested enum `Kind` = `PATH_REFUSED`, `VANISHED`, `DIR_UNREADABLE`, `FILE_UNREADABLE` (rule 13 judges a nested enum by its outermost class, which is a `Throwable`).
8. `TextRefusalTableTest`: reflection: the enum names equal the first column of plan 7.2; `TextRefusals.of` is total over every listed input; a planted eighth constant (a test-local copy of the enum with one more value, or a reflective check against a fixed expected set) turns it red. `SourceFaultKindsTest`: `SourceFault.Kind.values()` equals exactly its five values, so a sixth forces a review of the four switches.

**Files**: 9 production files (~250 lines in all), 2 tests (~120 lines).

**Validation**: `./gradlew --no-daemon test --tests '*TextRefusalTableTest' --tests '*SourceFaultKindsTest'`; ArchUnit rule 13 stays green (interfaces only in `port/out`, data in `dto`, throwables in `exceptions`); `grep -n "SourceFault" <the four switch sites>` shows no edit.

### Subtask T058: Adapter `FilesystemTextSource`, `NameEncoding`, `StrictUtf8`, `SafeFiles.readCapped`

**Purpose**: implement the port in the one place allowed to touch files (rule 7), with the cap enforced twice and the decode strict.

**Steps**:
1. `J/adapter/out/filesystem/SafeFiles.java` (exists at the checkout; `SMALL_FILE_MAX` = 1 MiB already public): add `readCapped(Path file, int cap)` returning a distinct result (`Bytes`, `Absent`, `NotRegular`, `OverCap`) and bounded to exactly `cap + 1` bytes. The order is fixed (plan 7.1 row 5): first the size of the **open handle** (a size above `cap` returns `OverCap` having read 0 bytes; AC-5.4), then the bytes actually read (stop at `cap + 1`, `OverCap` if the extra byte arrives; AC-7.1). Never trust a size read before the open. `readRegular(file, max, refused, unreadable)` **delegates** to `readCapped` and keeps its observable behaviour (every existing caller unchanged; no second whole-file reader exists, D-68). Reads go through `AllowlistAccess#openRead` only; a final-component link is never followed; every component below the Mission directory is `lstat`-ed (AC-7.2).
2. `J/adapter/out/filesystem/codec/StrictUtf8.java`: a `CharsetDecoder` for UTF-8 with `CodingErrorAction.REPORT` for both malformed input and unmappable characters; returns its own nested sealed result `StrictUtf8.Decoded` = `Text(String)` | `Rejected`; depends on nothing outside the JDK (rule 12a). A leading BOM is kept in the text. Not a hand-rolled validator and not a `new String` round trip (D-70).
3. `J/adapter/out/filesystem/NameEncoding.java`: the host probe: true (trustworthy) on Windows or when `sun.jnu.encoding` is UTF-8, false on a non-Windows host whose `sun.jnu.encoding` is not UTF-8. Constructor-injectable (a stub) so the stub legs of AC-4.8 and AC-6.6 run under any locale. `DirListing.Names.trustworthy` is `NameEncoding`'s answer for the listing.
4. `J/adapter/out/filesystem/FilesystemTextSource.java`: `implements TextSource`; holds one `SafeFiles` per `ReadScope` (built over `access.scoped(scope)`), so existing callers (`Listing`, `ReadDirResolver`, the event source) are unchanged and stay AUTHORED. `list` uses only the bounded `listNames(Path, int)` (T059). `readText` = `readCapped` then `StrictUtf8` mapped to `TextRead.NotText`. A `SourceFault` thrown by `SafeFiles` is translated to `TextFault` in **one private method** (`VANISHED`, `PATH_REFUSED`, `DIR_UNREADABLE` to their namesakes, `DIR_UNREADABLE` from a file read to `FILE_UNREADABLE`, `META_UNPARSEABLE` and `LEDGER_UNREADABLE` to `FILE_UNREADABLE`). `FileRef.MissionFile` resolves against the Mission's primary directory, via the same `requireContainedDir` containment check; `ProjectFile` against the root.
5. Tests: `SafeFilesReadCappedTest` (cap exactly, cap + 1, the open-handle size path reads 0 bytes, the grow-between-stat-and-read race, injected by a decorator declared inside the test class (WP10's reusable `CapRaceInjector` does not exist yet and must not be named here), gives `OverCap` with at most `cap + 1` bytes read: AC-7.1; a short read is not success), `StrictUtf8Test` (overlong `C0 AF`, surrogate `ED A0 80`, `F4 90 80 80`, truncated `E2 82`, lone `C3` are each `Rejected`; a valid four-byte character, a BOM and empty input decode), `NameEncodingTest`, `FilesystemTextSourceTest` (all four methods, each result variant, link in a middle component, link in the final component, same path without the link is read: AC-7.2; the Windows junction leg is `assumeTrue(isWindows)`).

**Files**: `SafeFiles.java` (edit, ~+60 lines), `StrictUtf8.java` (~60), `NameEncoding.java` (~40), `FilesystemTextSource.java` (~220); tests ~350 lines.

**Validation**: targeted `--tests` of the five classes; revert checks: change `REPORT` to `REPLACE` in `StrictUtf8` and `StrictUtf8Test` goes red (and later `wpm-24..26`); read `cap + 2` bytes in `readCapped` and `SafeFilesReadCappedTest` goes red.

### Subtask T059: `AllowlistAccess` scoped views and bounded listing

**Purpose**: give the fence a scope and give the walk a bounded name listing, without breaking any test double.

**Steps**:
1. `J/adapter/out/filesystem/AllowlistAccess.java` (exists): add two **default** methods (so `ListingTest.Reversing`, a double no phase owns, still compiles): `default AllowlistAccess scoped(ReadScope scope) { return this; }` and `default NameWindow listNames(Path dir, int limit) throws IOException` as a bounded view over the unbounded `listNames(Path)`; declare the nested record `NameWindow(List<String> names, boolean limitReached)` in the interface (names plus a more-exist flag; at most `limit + 1` names pulled lazily from one `DirectoryStream` in the pass-through).
2. `J/adapter/out/filesystem/AllowlistPassThrough.java` (exists): override both: `scoped` returns `this`, `listNames(Path, int)` takes names lazily from a single `DirectoryStream` and stops at `limit + 1` (this is what makes AC-4.9's bounded memory real).
3. `T/adapter/out/filesystem/RecordingAllowlistAccess.java` (exists; WP09 owns it): override both; log a `LIST` for the bounded variant; record the quadruple `(route, scope, class, mode)`. The route comes from a `Supplier<String>` field set on the recorder, default `() -> "-"`. The recorder names **no P7 type** (no `RouteMarker`); WP10's `RouteMarker` is what a harness installs as that supplier (PLAN-FRESH4-001). Keep the existing 3-component `Access` constructor and accessors so existing tests compile; add a scope.
4. A test pins that `AllowlistPassThrough` and `RecordingAllowlistAccess` each override both new methods (PLAN-FRESH2-006): reflection on `getDeclaredMethod`, so a future default fall-through is red.
5. `AllowlistAccessScopedTest` (a scoped view tags every access with its scope), and the bounded-pull test: a directory of `limit + 2` entries asserts that at most `limit + 1` names were pulled (use a counting `DirectoryStream` seam or the recorder's pulled-name count).

**Files**: three edits (~+80 lines), tests ~150 lines.

**Validation**: `ListingTest` and the existing recorder tests are unchanged and green; the new tests are green; deleting the override in `AllowlistPassThrough` turns the pinning test red.

### Subtask T060: `Allowlist`, ten new classes, eleven new entries, README fence

**Purpose**: amend the read fence once, atomically (spec FR-011; plan section 11 chokepoint: all ten classes and eleven entries land in one change so the README amendment is atomic).

**Steps**:
1. `J/adapter/out/filesystem/Allowlist.java` (exists; `PathClass` enum at line ~43, `ENTRIES` at ~97, patterns at ~115): add the ten `PathClass` values with their modes exactly as the spec table: `TASKS_DIR` (STAT, LIST), `WP_FILE` (STAT, READ), `TASKS_MD` (STAT, READ), `PLANNING_FILE` (STAT; `spec.md` and `plan.md`, two `ENTRIES` lines), `WP_CYCLE_DIR` (STAT, LIST), `WP_CYCLE_FILE` (STAT, READ), `WORKTREE_LANE` (STAT), `WORKTREE_LANE_GIT` (STAT), `ARTIFACT_DIR` (STAT, LIST), `ARTIFACT_FILE` (STAT, READ). Eleven new `ENTRIES` lines (twenty-two in all, in the spec's order, after the existing eleven). `status.events.jsonl` stays class `LEDGER` at its exact name under AUTHORED.
2. `classify(ReadScope scope, Path root, Path path)` (S-21 wording, plan section 13): under AUTHORED the existing specific-first classifier applies and `ARTIFACT_DIR`/`ARTIFACT_FILE` never match; under ARTIFACT only those two apply and `PLANNING_FILE`, `TASKS_MD`, `WP_FILE`, `WP_CYCLE_FILE`, `MISSION_META`, `LANES_JSON` are not consulted; the root `status.events.jsonl` and `status.json` (any case) are unclassified under ARTIFACT; `status.json` (any case) is unclassified under AUTHORED; everything outside the primary directory is unclassified under both. The primary directory is `MISSION_DIR` (STAT, REALPATH) under AUTHORED and `ARTIFACT_DIR` (STAT, LIST) under ARTIFACT.
3. Keep `permits`, `violations` and the old 3-component classify entry points working for existing tests.
4. `S/README.md`, allowlist section only (named edit): extend the first fenced list with the eleven lines, in the same order as `Allowlist.PATTERNS`, each stating its read scope; rewrite the sentence that lists what is "never" opened to the narrower truth (it must no longer name `tasks/*.md`, `spec.md`, `plan.md` or artifacts as never opened). No route is documented here (routes are PR B; plan section 11 PR A "files that name later routes").
5. `AllowlistScopeTest` implements AC-11.2: for every new class a deliberate forbidden access (red) and its own permitted access (green): READ `spec.md` under AUTHORED (red) / under ARTIFACT (green), same pair for `tasks.md` and `meta.json`; LIST `<primary-dir>` under AUTHORED (red) / first listing under ARTIFACT (green); READ `.worktrees/<..>/.git`; LIST `.worktrees/<..>/`; READ root `status.json`; READ `Status.JSON`; WRITE to any class; READ of a `WP_CYCLE_FILE` as if from `getWorkPackage`; READ of `TASKS_MD` as if from `getMission`. AC-11.4: the forbidden list (`status.json` and case variants, the coordination `meta.json`, `.git/refs/heads/main`, `.git/packed-refs`, `config.toml`, an absolute path outside the root, a `..` segment) is refused in every mode under both scopes; the control is a path in each of the ten new classes permitted for its modes. The S-21 green twin: a READ of the root `status.events.jsonl` under AUTHORED is permitted and under ARTIFACT fails. Extend `AllowlistReadmeParityTest` (entry for entry, plus the "never opened" sentence assertion: AC-11.3).

**Files**: `Allowlist.java` (~+150), `S/README.md` (~+30), tests ~300 lines.

**Validation**: `./gradlew --no-daemon test --tests '*Allowlist*Test'` (this glob covers `AllowlistReadmeParityTest`); the parity test is red if either the README or `ENTRIES` differs by one line.

### Subtask T061: Domain rules for later consumers (`ArtifactPaths`, `ArtifactKinds`, `ArtifactKind`, `Eligibility`)

**Purpose**: own the artifact-path rule once because the index (WP11), the review-cycle references (P11) and the artifact routes (P12) all apply it (D-111).

**Steps**:
1. `J/domain/readmodel/derive/ArtifactPaths.java`: the artifact-path rule of the contract (`contracts/**/schemas/ArtifactPath.yaml`, read it; do not re-derive): at most 512 characters, forward slashes, no empty or dot segment, no backslash, NUL, line break, drive letter or `~/` prefix, valid UTF-8 (at the string level: reject U+FFFD-bearing and unpaired surrogates as the contract says). Pure static functions; no `java.nio.file` (rule 7).
2. `J/domain/readmodel/derive/ArtifactKinds.java`: the ordered classifier of `schemas/ArtifactKind.yaml`: `review_cycle`, `work_package_prompt`, `spec`, `plan`, `tasks`, `data_model`, `quickstart`, `analysis_report`, `research`, `contract`, `checklist`, `other` (first match wins; AC-5.8 rows: `tasks/WP01-x/review-cycle-1.md` is `review_cycle`; `review-cycle-01.md` is `other`; `tasks/WP1-x.md` is `other`; `research.md` and `research/a.md` are `research`; `A.MD` media type `text/plain`).
3. `J/domain/readmodel/detail/ArtifactKind.java`: the 12-value enum with wire words (the one file of that directory that is **not** WP12's).
4. `J/application/query/artifact/Eligibility.java`: **`public final class Eligibility`** (consumed from `application.query.index` by WP11 and `application.query.detail` by WP15, both other packages; a package-private declaration would force those WPs to stop on a file they do not own, TASKS-COVER-004), with every method they call `public`: the eligibility rule over names and relative paths: a regular file whose path passes `ArtifactPaths`, not the root `status.events.jsonl` or `status.json` (case-insensitive, root only), every component a real directory; a name holding U+FFFD is ineligible under a UTF-8 locale. No I/O: it judges strings and `EntryStat` values the caller passes.
5. Table tests (`ArtifactPathsTest`, `ArtifactKindsTest`, `EligibilityTest`), including the ineligible-name cases the index (candidates named `WP01-�.md`, `.md` with a backslash, 513 characters) and the review-cycle references rely on, and the AC-5.2 request-value rows that do not depend on percent-decoding (`a+b`, `%252e%252e` as a literal name, a trailing slash, a 513-character path, `spec.md`).

**Files**: four production files (~300 lines), tests ~250 lines.

**Validation**: targeted tests; `ArchitectureRulesTest` green (rules 1/2: nothing but JDK in `domain`; `Eligibility` in `application.query.artifact` imports no `java.nio.file`).

### Subtask T062: Redaction and the nine diagnostic codes

**Purpose**: one function for every route (FR-008): does this text hold a credential; what is it with host paths and addresses substituted.

**Steps**:
1. `J/domain/redaction/LeakClasses.java`: add `credential(String)` over the same compiled `secrets` patterns `Projector` already uses (single owner; `leak-patterns.json` is generated by the Python generator and expected **unchanged**).
2. `J/domain/redaction/TextScreen.java`: `new TextScreen(LeakClasses)`; `Screened screen(String text)`; `Screened` sealed: `Clean(String text, boolean redacted)` (host paths replaced by `[path]` **together with the following non-space characters** (the `\S*` widening), addresses by `[email]`, `redacted` true exactly when the text changed) | `SecretFound` (no text).
3. `J/domain/model/DiagnosticCode.java` (exists): add nine constants, in this order after the existing eight: `WP_FILE_SKIPPED`, `WP_ID_DUPLICATE`, `SOURCE_UNREADABLE`, `MISSION_ID_DUPLICATE`, `ARTIFACT_TOO_LARGE`, `ARTIFACT_NOT_TEXT`, `ARTIFACT_SECRET`, `ARTIFACT_UNREADABLE`, `ARTIFACT_LISTING_UNREADABLE` (spec AC-12.2; `wire()` already lower-cases). Check every `switch` over `DiagnosticCode` with `grep -rn "DiagnosticCode" S/src` and keep each exhaustive.
4. `TextScreenTest`; extend `LeakClassesPythonParityTest` with the artifact corpus (AC-5.6): each pattern at its minimum length is `SecretFound` (assembled at test time from two fragments, never committed whole: C-006, D-48): `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` plus 36 alphanumerics, `github_pat_` plus 40 of `[A-Za-z0-9_]`, `AKIA`/`ASIA` plus 16 of `[0-9A-Z]`, a PEM private key header line; near misses at 35, 39, 15 and a bare prefix are `Clean`. AC-5.7 rows: host path becomes `[path]` plus the following non-space characters, an e-mail becomes `[email]`, a clean text has `redacted` false and is unchanged.
5. AC-8.1 (one function, two call sites): the same corpus through `TextScreen` and through the human-field entry of `Projector` gives the same substitution and the same decision on a credential. The field-class outcomes (null subtask title, id-substituted dependency title, `projection_refused` for the rest) belong to the route WPs; here assert only the function-level equivalence.
6. AC-8.2 (mutation in the suite): a test-only variant of `credential` that always answers "none" must fail at least one case of the AC-5.6 corpus, and a variant without the `\S*` widening must fail at least one case of the AC-5.7 corpus; the real function passes both (control).

**Files**: `LeakClasses.java` (~+25), `TextScreen.java` (~90), `DiagnosticCode.java` (+9 lines), tests ~250 lines.

**Validation**: `./gradlew --no-daemon test --tests '*TextScreenTest' --tests '*LeakClasses*Test'`; revert: make `credential` always false and AC-8.2 and the parity test go red.

### Subtask T063: Guards and the planted control

**Purpose**: keep the stat/list/read fence from being widened silently by a later phase.

**Steps**:
1. `T/architecture/NoUncappedReadTest.java` (exists, WP09 owns it): extend to cover `readCapped` (an `int` cap; only `SafeFiles` calls `openRead`): a planted class that calls `openRead` or a no-cap read from outside `SafeFiles` turns it red.
2. `T/architecture/NoUnboundedListingTest.java` (new, beside it): `FilesystemTextSource` may use only `listNames(Path, int)`; a planted call to the unbounded `listNames(Path)` from it must be red; and the directory-of-`limit + 2` test of T059 is referenced from here or lives here.
3. `T/architecture/fixture/application/query/A2cByteBuffer.java`: planted fixture class (an application class that wraps bytes in a `ByteBuffer`): turns rule 2b red. Its control test is a **named edit** of `T/architecture/ArchitectureControlsTest.java` (owned by WP03): add the `A2cByteBuffer` control only, and state it in the commit message. Do not touch the `SKELETON` list (WP12 does that).

**Files**: ~+60 lines in `NoUncappedReadTest`, new ~70-line `NoUnboundedListingTest`, a ~15-line fixture, a ~15-line control.

**Validation**: `./gradlew --no-daemon test --tests '*NoUncappedReadTest' --tests '*NoUnboundedListingTest' --tests '*ArchitectureControlsTest' --tests '*ArchitectureRulesTest'`; each planted violation is red when its guard is weakened.

### Subtask T064: JaCoCo count lines

**Purpose**: keep `jacocoScopeCheck` non-vacuous for the classes this WP adds.

**Steps**:
1. After the production classes compile and tests pass, run from `S`: `./gradlew --no-daemon test jacocoTestReport` then the command of plan section 2: `python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"`.
2. Edit **only** the two count lines of `R/jacoco-class-floor.properties` (`domain=`, `application=`; named edit, owned by WP01) to the numbers the command prints **at the commit that adds the classes**. Count nested records and sealed variants (`DirListing.Names`, `EntryStat.Present`, `TextRead.Text`, `Screened.Clean`, `StrictUtf8.Decoded.Text`, the `AllowlistAccess.NameWindow` record, ...) through the command, never by hand.
3. Merge rule (D-145): if a concurrent lane (WP07/WP08 do not touch the file; WP06 might) merged first, rebase, re-run the command on the merged tree and write what it prints, in a named-edit commit of its own.
4. Every new class must meet the per-class line floor 0.90 (`jacocoTestCoverageVerification`) through the tests above; add a focused test for any uncovered branch rather than lowering anything.

**Files**: `R/jacoco-class-floor.properties` (two lines).

**Validation**: `./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck` green; the diff of the properties file equals the classes added.

### Subtask T065: Phase exit gate

**Purpose**: prove the whole WP green on its own.

**Steps** (all with `export LC_ALL=C.UTF-8` first; stage new files with `git add` before Gate P, because the Windows-filename guard and the pin's tracked-path scan read `git ls-files`):
1. **Gate G**: `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`.
2. **Gate P**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`. Also `git check-ignore -v` on a sample new file in `application/query/port/out`, `port/out/dto` and `port/out/exceptions` (the `/out/` ignore rule is re-included for `src`; the pin's probe list covers the directories after WP01's edit).
3. Acceptance: `Eligibility` is `public` with public methods (a test in `EligibilityTest` calls it from a class in another package, for example through `application.query.index`-style usage in the test source tree). Acceptance targets by name: AC-7.1 to AC-7.4, AC-8.1, AC-8.2, AC-11.2 to AC-11.4, `AllowlistReadmeParityTest`, the `ByteBuffer` planted control, `TextRefusalTableTest`, `ArtifactPathsTest`, `ArtifactKindsTest`, `EligibilityTest`, the limit+2 listing test.
4. Python hygiene is not needed (no Python file touched). Run `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md | grep -v 'non-numeric-number feature'`: expect empty.
5. E-7 allows local `./gradlew --no-daemon check` and `nativeCompile nativeTest` if you want extra evidence; none is required by this phase (no new bean is added here; the first native-visible phase is WP11). CI is the authority.
6. Append tracer entries (approach, design-decisions with the P5 seam names, tooling-friction if any) and commit.

**Validation**: all of the above green; the commit message lists commands and counts.

## Self-contained green

This WP's tip, and PR A's tip with it, must be green on every CI gate on its own (plan section 11 "Each PR is self-contained and green at its own tip").

- **Fixtures with tests.** Every fixture a test here needs is created inside that test (temp directory, `ScratchDirs`) or is a test-local class: the credential fixtures are assembled at test time from two fragments (C-006), the oversized, NUL, link and non-ASCII files are generated at test time, the planted `A2cByteBuffer` is in the architecture fixture tree. No golden or conformance fixture is added or read by this WP, and `R/conformance/**` is untouched.
- **Floors and counts satisfiable here.** `R/jacoco-class-floor.properties` carries exactly the classes added up to this WP (plan section 11, shared-file row; section 2 command), counted at the adding commit; WP12 recounts after its own additions and compares the file with the command at PR A's tip (T088); WP17 T125 owns the single D-145 equality comparison at PR B's tip and WP18 re-runs it; a mismatch is repaired by a named edit of the properties file by the WP that found it (D-145). `DEFINED_RULE_COUNT` is untouched (WP12 raises it to 16). The `@Tag("native")` floor (3) and `requests.json` (49) are untouched.
- **No forward reference.** No test or gate here names a type of a later WP: no `RouteMarker`, no `MissionDetailQuery`, no `DetailRefusal`, no `DetailFixture`. The recorder's route is a `Supplier<String>` defaulting to `"-"` (PLAN-FRESH4-001). `TextRefusals` names `TextScreen`, which this WP creates. `Eligibility` and `ArtifactPaths` are used by WP11 and later, never the reverse.
- **Pin `tests/ci/test_mission_status_api_build.py`.** Clauses kept green: the tracked-path scan over `S` (new files staged), the probe list (`NEW_FILES_IN_OUT_PACKAGES`, edited by WP01) now exercised by new files in `port/out/{,dto,exceptions}`, the `adapter/in/http` sub-directory names (untouched), the rule-9 literals (untouched). The file itself is not edited here.
- **Mission record.** `M/meta.json` is not edited; `M/status.json` is the materialisation of `status.events.jsonl` (`spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`, never hand-edited; compare with the coordination copy before committing any status file) so cutover-guard, the mission-state audit and corpus-blocking pass at PR A's tip. Only the append-only trace files change under `M/`.
- **Windows-filename guard / terminology.** New file names use only ASCII and no reserved characters; `Mission` is the term, never `feature`.

## Plan defects found

- None blocking. (The spec's `wpm-28` reading was folded in commit 462bb3c63 and is WP11's, not this WP's.)
- `SourceFaultKindsTest` is listed under `T/application/query/port/out/exceptions/` (WP09 scope) while `SourceFault` itself lives at the same package after the re-cut; confirm the test sits beside it when the re-cut tip lands (path exists only after the re-cut).

## Definition of Done

- T056..T065 each recorded with `spec-kitty agent tasks mark-status <Txxx> --status done --mission mission-status-read-api-mission-detail-01M4S6D5`.
- Every class of plan 7.1 rows 1 to 7, 9, 10 exists with the exact names and signatures above; `SourceFault.Kind` still has five values.
- The fence has 22 entries in `Allowlist.ENTRIES` and the README first fenced list, ten new `PathClass` values, scope-aware `classify`, and a red/green control per class.
- `readCapped` enforces handle size then at most `cap + 1` bytes read; `readRegular` delegates; `StrictUtf8` uses `REPORT`.
- `DiagnosticCode` has 17 values; `LeakClasses.credential` and `TextScreen` exist; AC-8.2 mutation tests pass.
- Gate G and Gate P green under `LC_ALL=C.UTF-8`; the JaCoCo count lines equal the command's output at the adding commit.
- Only `owned_files` and the named edits changed; the commit messages state each named edit.

## Risks

- **Fence widening by accident.** Mitigated by AC-11.2/11.4 controls, `NoUncappedReadTest`, `NoUnboundedListingTest` and the parity test; do not add a convenience overload that bypasses `scoped`.
- **Default-method fall-through** hiding an access from the recorder: the pinning reflection test.
- **JaCoCo undercount** after a concurrent lane merge (floor semantics cannot see it): recount on the merged tree (D-145).
- **Locale-dependent tests** red for a non-WP reason: always `LC_ALL=C.UTF-8`; use `Utf8Host.assumeUtf8()` only after WP10 exists (not available here: for non-ASCII file creation in this WP use an in-test `assumeTrue("UTF-8".equals(System.getProperty("sun.jnu.encoding")))`).
- **Root runner**: permission-denied legs belong to later WPs; nothing here depends on file modes.

## Reviewer Guidance

- Check the port against plan 7.1 row by row (names, layer, signatures; no `Path`, no `IOException`, no route words).
- Confirm cap order (handle size first, then `cap + 1` bytes) and that `readRegular` still behaves identically for old callers (run the pre-existing `SafeFilesTest`).
- Confirm `status.events.jsonl` is LEDGER at its exact name under AUTHORED and unclassified under ARTIFACT (S-21 twin).
- Confirm README and `Allowlist.PATTERNS` parity is entry for entry and the "never opened" sentence is rewritten.
- Run `git diff --stat` and verify no file outside `owned_files` or the named edits changed; verify the JaCoCo diff equals the classes added; grep for `ByteBuffer` outside the codec.
- Reviewer must run the implicated architectural gates (`ArchitectureRulesTest`, `ArchitectureControlsTest`, `PortLevelClassSetTest`) and the pin.

## Implementation command

```bash
spec-kitty agent action implement WP09 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
