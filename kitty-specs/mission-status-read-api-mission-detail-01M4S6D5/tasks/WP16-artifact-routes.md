---
work_package_id: WP16
title: '[PR B] P12 Artifact routes (FR-004, FR-005)'
dependencies:
- WP06
- WP09
- WP10
- WP12
requirement_refs:
- FR-004
- FR-005
- FR-012
- FR-022
- NFR-002
- SC-004
- NFR-003
- NFR-004
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T08:18:05.137124+00:00'
subtasks:
- T112
- T113
- T114
- T115
- T116
- T117
- T118
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/ArtifactQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/artifact/ArtifactWalk.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/artifact/ArtifactReader.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/artifact/ArtifactLimits.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/ArtifactController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/ArtifactMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/ArtifactWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/ArtifactMetaReadCountTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/ArtifactServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/portlegs/ArtifactPortLegsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/ArtifactServedRouteTest.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/ArtifactQueryService.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/artifact/ArtifactWalk.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/artifact/ArtifactReader.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/artifact/ArtifactLimits.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/ArtifactController.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/detail/ArtifactMapper.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/ArtifactWiring.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/ArtifactQueryService*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/ArtifactMetaReadCountTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/artifact/ArtifactWalk*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/artifact/ArtifactReader*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/artifact/ArtifactLimits*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/detail/Artifact*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/ArtifactServedRoute.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/portlegs/ArtifactPortLegsTest.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/served/ArtifactServedRouteTest.java
role: implementer
tags: []
tracker_refs: []
---
# Work Package Prompt: WP16 – [PR B] P12 Artifact routes (FR-004, FR-005)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request: B (a draft), plan phase P12.** PR B = WP13 to WP18 (P9 to P13); it stacks on PR A (WP01 to WP12), which stacks on the branch that carries #5529's last slice. PR B cannot merge before PR A. #5533's Java work stacks on PR A, never on PR B. No agent pushes, opens or retargets a pull request.
- **External dependency (not a `dependencies` entry).** The re-cut tip of #5529 (the side-first layout) was merged into this branch by the orchestrator before WP01 started (C-005). If the re-cut is absent on your tree, stop and report.
- **Work package dependencies.** WP06 (P2), WP09 (P5: `TextSource`, `FilesystemTextSource`, the read fence with the `ARTIFACT` scope, `NameEncoding`, `Eligibility`, `ArtifactKinds`, `ArtifactPaths`, `StrictUtf8`, `TextScreen`, `TextRefusals`), WP10 (P7: `HttpHarness#startWith`, `MetaReadCounter`, `ServedRoute`, `Utf8Host`, `RealPermissionFixture`, `@PermissionCase`, `InMemoryTextSource`, `CapRaceInjector`), WP12 (P8: the port `ArtifactQuery`, `ArtifactPathInput`, `RawQuery`, `DetailRefusal`, `AdmissionGate`, the three records, rules 15 and 16, Problem mapping). It needs **neither the ledger nor the Work Package index** (it does not depend on WP11 or WP13) and may run beside WP13 to WP15 on a disjoint scope. Do not reference any type of WP11, WP13, WP14 or WP15.
- **Write scope: `owned_files` only** (frontmatter).
- **Named edits (out-of-map; not in `owned_files`).** For each: rebase first, state the edit in the commit message, touch nothing else of the file.
  - `S/README.md`, the **locale sentence** only (WP17 owns the file; other sections arrive from WP09 and WP14): one sentence stating the UTF-8 locale requirement for file names of the artifact routes and the Work Package index (D-31, FR-018), containing the literals `UTF-8 locale`, `sun.jnu.encoding` and `LC_ALL` (T117 step 6).
  - `J/domain/readmodel/detail/{ArtifactListing,ArtifactEntry,ArtifactContent}.java`: the three records of this route (WP12 owns them). The shapes are final from the contract schemas (WP12 T082): the default is **no edit**. Edit a record only when this route's schema or golden proves a member missing or wrong; that is a named edit of WP12's file (accepted risk under the plan section 11 shared-file table, TASKS-DECOMP-003): rebase first, one record per commit, schema evidence in the commit message.
  - `T/adapter/in/http/rest/OutOfScopeRoutesTest.java`: this route's two paths (listing and content; WP13 owns the file; removals are serialised by merge order with WP14 and WP15).
  - `R/jacoco-class-floor.properties` (two count lines; WP01 owns it; merge rule D-145). This work package appends **nothing** to `R/portlevel-tests.txt` (WP05's file): the port-level legs live outside `conformance.port` and are not listed (TASKS-GREEN-001; see the port-level subtask).
  - none in `M/**` (interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`; the orchestrator keeps the tracer and status appends locally).
- **Concurrency.** WP13, WP14 and WP15 may run beside this work package. The later merge recounts JaCoCo on the merged tree and rebases `OutOfScopeRoutesTest`. **Merge order WP13 -> WP14 -> WP15 -> WP16** for the shared files `OutOfScopeRoutesTest.java` and `R/jacoco-class-floor.properties`: the orchestrator merges in that order and each later lane rebases onto the merged tree. Neither file has a git merge driver, so a conflict is real and is resolved by rule: in `OutOfScopeRoutesTest.java` keep the **intersection** of the remaining paths (a path removed by any lane stays removed); in the properties file take neither side, re-run the section 2 command on the merged tree and write what it prints. Nothing is claimed to merge silently.

Aliases used in this prompt (plan section 11, expanded to repo-relative paths): `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`.

Every layout path below is the **side-first layout of #5529's re-cut** (plan section 1.1, mapping table rows 1 to 13). The re-cut classes (`application/query/MissionStatusQueryService`, `application/query/ProjectionCache`, `application/query/port/in/**`, `application/query/port/out/**`, `domain/readmodel/**`, `domain/redaction/**`, the test mirror paths) **exist after the re-cut**, not in a checkout that lacks it. If a cited path is missing on your tree, the orchestrator has not merged the re-cut: STOP and report; never create the path, never "fix" it by using the flat checkout names. Paths of other work packages' classes (WP05 to WP12) exist after those work packages are on this branch; the work package list in the dependencies block says which.

---

## Objective

Serve `GET /api/v1/missions/{missionId}/artifacts` (`listArtifacts`, FR-004) and `GET /api/v1/missions/{missionId}/artifacts/content?path=` (`getArtifactContent`, FR-005) from the Java service: the eligible files of a Mission under its **primary** directory in UTF-8 byte order, bounded at 1000 entries with a bounded path set, and the redacted text of one artifact in the fixed order of decision, both behind the admission gate, both reading `meta.json` exactly once for the matched Mission, byte-identical to the oracle's goldens.

## Context

- **No ledger, no head, no index.** The two artifact routes never probe, never stamp, never read the ledger and touch no coordination class (AC-1.8 b). The sequence is `MissionLookup#find`, the duplicate continuation, then the work: the matched Mission's `meta.json` is read **exactly once**, every other Mission once. A Mission whose ledger is unreadable (the M2 fixture) is answered as a healthy one.
- **Scope ARTIFACT.** Reads go through `TextSource` with `ReadScope.ARTIFACT` (WP09): the listing's first read is class `ARTIFACT_DIR` (STAT, LIST), a content read is `ARTIFACT_FILE` READ (so a content read of `spec.md` is permitted, while a READ of `spec.md` under `AUTHORED` fails the fence). Under ARTIFACT the root `status.events.jsonl` and `status.json` (any case) are unclassified. A fence test asserts against the quadruple `(route, scope, class, mode)`, never the path alone.
- **The gate.** Both operations run inside `AdmissionGate#run` (WP12; fair `Semaphore(4, true)`; never refuses, never times out); they are two of the four heavy operations (FR-022, E-1).
- **Typed identifiers and the raw query (E-5, D-150, D-28).** The controller parses `missionId` with `MissionId.parse` (no `wpId` on these routes); an empty result is `DetailRefusal.notFound()`; row C2 is 404, never 400. For the content route the controller uses `RawQuery` (WP12): it reads the raw query string, collects every value of `path` (so a repeated parameter is seen, not joined), percent-decodes each value **once and strictly as UTF-8** (`+` is a literal plus sign, DC-6; `%ff`, `%c0%af` and a truncated `%e2%82` are undecodable and never become U+FFFD) and hands the port an `ArtifactPathInput`: `Values(List<String>)` or `Undecodable`. Everything else about `path` (zero or two or more values, the artifact-path rule, the 512-character limit) is decided **behind the port**, so an MCP adapter duplicates nothing.
- **Eligibility is WP09's.** `Eligibility` (the name-level rule), `ArtifactKinds` (the ordered classifier of `schemas/ArtifactKind.yaml`) and `ArtifactPaths` (the artifact-path rule of `schemas/ArtifactPath.yaml`) are consumed, not rewritten; `domain/model/CodePoints.compare` (exists at the checkout) is the code-point comparison whose order equals UTF-8 byte order.
- **Locale (D-31).** On a non-Windows host the JDK decodes directory entries with `sun.jnu.encoding`, which follows the process locale. If it is not UTF-8 a name that is not pure ASCII cannot be told from a mangled one: the listing answers 500 `artifact_listing_unreadable` and the content route 500 `artifact_unreadable` (row A8), each with one path-free diagnostic; nothing is omitted silently. Under a UTF-8 locale a name that contains U+FFFD is not eligible and not listed (a recorded divergence). WP09's `DirListing.Names(..., trustworthy)` and `NameEncoding` carry the probe; this work package maps its result.
- **Red-first form: red on the phase base.** On the base (WP12's tip) both routes answer 404 and none of this route's classes exist.
- **Charter rules in force.** The squad belongs to the orchestrator. Every gate you add is non-vacuous (a discovered-count floor or a planted control). A red is classified under plan section 6, never retried to green.

---

### Subtask T112: Pre-flight and red-first tests

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
   - `T/application/query/ArtifactQueryServiceGateTest.java`: for **each** of the two operations, 16 concurrent calls whose reads block on a latch; the gate's high-water mark equals 4; releasing the latch completes all with normal results; a test-only variant that skips the gate turns the "mark above 4" assertion red (AC-22.3 for this route).
   - `T/application/query/ArtifactMetaReadCountTest.java` (AC-1.8): the matched Mission **1** read, every other Mission 1 read, first-sorted and last-sorted control, a discovered-row floor; plus (b) over the M2 fixture (unreadable ledger) both routes answer as for a healthy ledger and the instrumented port records **no LEDGER access and no coordination class**. Revert: make an artifact route touch the ledger and it goes red.
   - `T/application/query/ArtifactQueryServicePermissionTest.java`: the permission cases of AC-4.3 and AC-4.7 **both legs under D-101**: (a) fault injection through the recorder (`failWhen` with an `AccessDeniedException`, any user, any OS) and (b) the real file system behind `RealPermissionFixture.refusedForThisUser(path)`, which skips by assumption and appends `not run: precondition unmet: <test id>` to `build/reports/not-run.txt` when the OS does not refuse (root runner, Windows). Mark both legs of a case with `@PermissionCase("<id>")` (WP10), ids distinct, of the form `AC-4.3/<case>` and `AC-4.7/<case>`; record exactly **two** (one case of AC-4.3 and one of AC-4.7) in the tracer entry (WP18's floor of four ids is WP15 two + WP16 two).
   - `T/application/query/ArtifactQueryServiceTest.java`, `T/application/query/artifact/ArtifactWalkTest.java`, `ArtifactReaderTest.java`, `ArtifactLimitsTest.java`, `T/adapter/in/http/detail/ArtifactControllerTest.java`, `ArtifactMapperTest.java`, `T/conformance/golden/served/ArtifactServedRoute.java`: red now, completed in T113 to T117.
3. The red commit compiles: production classes exist only as shells that throw `UnsupportedOperationException`. No behaviour in the red commit.
4. Prove red on the phase base in a scratch worktree of WP12's tip (`git worktree add <scratch>/base <sha>`; copy the new tests in; run them). Never prove red by reverting in the working tree; never `git stash`; never run tests under `git rebase -x`.

**Files**: 10 new test files plus shells.

**Validation**: each class is red on the base for its stated reason; `CoupledSymbolsShapeTest` green on the tip.

---

### Subtask T113: `ArtifactQueryService` and `ArtifactLimits`

**Purpose**: The application service of both operations and the constants of the route.

**Steps**:

1. `J/application/query/ArtifactQueryService.java`: `public final class ArtifactQueryService implements ArtifactQuery` (`list(MissionId)`, `content(MissionId, ArtifactPathInput)`); public because `config` constructs it. Collaborators: the `MissionLookup` of the `MissionReadModel` (lookup only; **not** `head`), the `TextSource`, the `AdmissionGate`, the diagnostics consumer (all existing beans; declare none). Read the signatures on the tips of WP09 and WP12; invent none.
2. Both operations run their whole body inside `gate.run(...)`.
3. `content`: decide in the fixed order of FR-005 (T115). The service validates the `ArtifactPathInput` **before** the lookup: step (1) `INVALID_ARTIFACT_PATH` (zero values, two or more values, `Undecodable`, or a value failing `ArtifactPaths`), then (2) the lookup (an unknown Mission is `NOT_FOUND`). See "Plan defects found" item 2 for the one combination this cannot order.
4. `list`: lookup, duplicate continuation, then `ArtifactWalk` (T114). Map faults to `DetailRefusal` kinds: `ARTIFACT_LISTING_UNREADABLE` (Mission directory unlistable, walk bound exceeded, untrustworthy names), `NOT_FOUND` for an unknown Mission; mapping of a `TextRefusal` to a `DetailRefusal` is the one table of plan section 7.2 (`TextRefusals.of` is WP09's pure function; `TextRefusalTableTest` pins it).
5. Lookup rows C3 to C7 apply as in WP13 but with this route's codes: C4 500 `artifact_listing_unreadable` (listing) or `artifact_unreadable` (content) plus `meta_unparseable`; C5 the same codes plus `mission_dir_unreadable`; C6 serves the first in byte order plus `mission_id_duplicate`; C7 a faulted sibling is ignored.
6. `J/application/query/artifact/ArtifactLimits.java`: the route's constants and nothing else (not a seam: #5533 does not import it): listing size 1000 and collector size 1001; path length 512; walk counter limit 100000; content and `readable` read cap 262144 (a read asks for at most 262145 bytes). Give them names that state the rule.

**Files**: `ArtifactQueryService.java` (~230 lines), `ArtifactLimits.java` (~30 lines).

**Validation**: `ArtifactQueryServiceGateTest`, `ArtifactMetaReadCountTest` and the AC-12.1 lookup rows green.

---

### Subtask T114: `ArtifactWalk`

**Purpose**: The bounded walk and the bounded sorted collection of FR-004.

**Steps**:

1. `J/application/query/artifact/ArtifactWalk.java`. Lists with `nameLimit = 100000 - counter` through `TextSource#list(dir, nameLimit, ReadScope.ARTIFACT)` (the bounded `listNames(Path, int)` underneath; `limitReached` true means the next name would be the 100001st). Every name returned by a directory listing during the walk counts one: regular files, directories, links, ineligible names and the root records `status.events.jsonl` and `status.json`; the primary directory itself does not count; a directory counts once, as a name in its parent's listing, and the names inside it count when it is entered; a directory that is not entered (a link, or one whose relative path already has 512 characters) counts as a name and its content does not. Boundary: a walk whose counter reaches 100000 is served; the name that would make it 100001 stops the walk with 500 `artifact_listing_unreadable` (OQ-4) and writes that diagnostic.
2. Eligibility per entry (AC-4.5): a regular file whose path passes `ArtifactPaths`, is not the root `status.events.jsonl`/`status.json` (compared without regard to case, **root only**; `notes/status.json` is listed), and whose every path component below the Mission directory is a real directory or the file itself: each component is `lstat`-ed through `TextSource#stat` and nothing is resolved. A symbolic link or reparse point is neither followed nor listed. A file that vanishes during the walk is omitted (no diagnostic).
3. The collector is a bounded max-heap of the **1001 smallest paths** under `CodePoints.compare` (code-point order of a path equals UTF-8 byte order, AC-4.2: not `String.compareTo`, not a `Collator`, not file-system order); `truncated` is true exactly when the 1001st exists. Expose the collector's high-water mark through a package-private test accessor (the tests of the same package read it).
4. Per entry: `path`, `kind` (`ArtifactKinds`, WP09), `sizeBytes` from `stat` without opening, `modifiedAt` the modification time **floored** (`modifiedEpochSecond`) rendered in UTC with `Z` (AC-4.6: a fraction of 0.9999 s is the floor, not `Math.round`). `readable` is computed only for the final at most 1000 entries by `TextSource#readText(file, 262144, ARTIFACT)`: a size above the cap is decided from `stat` alone and the file is not opened; `Text` is readable only if it contains no NUL and `TextScreen` finds no secret; an over-cap, NUL, non-UTF-8 or credential file is `readable` false with **no** diagnostic; a thrown `TextFault` of kind `FILE_UNREADABLE` is `readable` false with exactly one `artifact_unreadable` diagnostic; `VANISHED` omits the entry. One read buffer is held at a time (NFR-002).
5. `DirListing.Names(..., trustworthy=false)` (a non-ASCII name under a non-UTF-8 `sun.jnu.encoding`) is 500 `artifact_listing_unreadable` with one path-free diagnostic; never omit the name (AC-4.8).

**Files**: `ArtifactWalk.java` (~230 lines).

**Validation**: `ArtifactWalkTest` green on: 1001 files lists 1000 with `truncated` true, exactly 1000 lists 1000 with `truncated` false (AC-4.4); the two bound fixtures (T117); the sort corpus of `artifacts-sort` (`U+FF5E` against `U+1F600`; `B.md` against `a.md`; an ASCII control pair that every comparator orders the same, which proves the fixture sees the difference only through the two special pairs); the collector never holds more than 1001 paths.

---

### Subtask T115: `ArtifactReader`

**Purpose**: The order of decision of `getArtifactContent`.

**Steps**:

1. `J/application/query/artifact/ArtifactReader.java` consumes `Eligibility`, `ArtifactKinds` and `ArtifactPaths` of WP09, `StrictUtf8` through the port (the application never sees bytes of a text read) and `TextScreen`. The fixed order (FR-005; `read_content` and `read_file` of the oracle):
   1. the `path` parameter is missing, repeated or malformed (including strings that are not UTF-8, a backslash, a NUL, a line feed, a drive-letter prefix, `~/`, an empty segment, a trailing slash, a 513-character path) -> 400 `invalid_artifact_path`;
   2. the Mission is unknown, or the path names no eligible artifact (a directory, a link, a path through a link, a root status record, a missing file) -> 404 `not_found` (a link or path through a link is `TextFault.PATH_REFUSED` -> `NOT_FOUND`; the target is never read; no diagnostic below the Mission directory);
   3. the file is larger than 262144 bytes by the size of the **open handle** -> 413 `artifact_too_large` and the file is not read (the instrumented port records 0 bytes read for 262145);
   4. the Mission directory or the file cannot be opened or read -> 500 `artifact_unreadable`; a byte beyond the cap while reading is 413 (a file whose size is 100 at `stat` and 300000 at read is 413 by bytes read, at most 262145 bytes read: `CapRaceInjector`);
   5. a NUL byte, or bytes that are not strict UTF-8 -> 415 `artifact_not_text` (a BOM is kept; a lone `0xC3`, an overlong sequence and an encoded surrogate are 415);
   6. a credential in the decoded text -> 422 `artifact_secret`, no content in the body;
   7. 200: `TextScreen.Clean(text, redacted)`; a file of 0 bytes is 200 with `content` empty and `sizeBytes` 0; `sizeBytes` is the byte size (greater than the character count for multibyte text).
2. Diagnostics (rows A2 to A8): A2 and A3 none; A4 `artifact_too_large`; A5 `artifact_unreadable`; A6 `artifact_not_text`; A7 `artifact_secret`; A8 `artifact_unreadable` for a non-ASCII requested path under a non-UTF-8 `sun.jnu.encoding`. Exactly one line per occurrence, with the code and a `mid8` field, and no path, no content, no OS message.
3. Redaction (AC-5.7): a host path becomes `[path]` **together with the non-space characters that follow it** (the `\S*` widening), an address becomes `[email]`, `redacted` is true; a file with neither has `redacted` false and `content` equal to the text. `kind` and `mediaType` come from the classifier (`tasks/WP01-x/review-cycle-1.md` is `review_cycle`; `review-cycle-01.md` and `tasks/WP1-x.md` are `other`; `research.md` and `research/a.md` are `research`; `A.MD` is `text/plain`: AC-5.8).
4. Credential patterns (AC-5.6) are those of `contracts/tools/leak_patterns.py` as carried in the committed `leak-patterns.json`; no second list. The 422 fixtures are assembled at test time from two fragments (prefix, body) in a temporary directory; the committed near-miss fixtures are one character short (35, 39 and 15 characters; a bare prefix) and are 200 (D-48).
5. Order of decision: each status is its own fixture next to a 200 control file in the same Mission; every refusal body is checked for the absence of a byte of the file and of a path.

**Files**: `ArtifactReader.java` (~190 lines).

**Validation**: `ArtifactReaderTest` green for every row; the mutation `AC-8.2` pair (a test-only variant whose credential check always answers "none", a variant without the `\S*` widening) is red against its corpus (WP09's test; here the real function passes both).

---

### Subtask T116: Controller, mapper and wiring

**Purpose**: The HTTP edge: raw-query decoding, one call, status mapping, shaping.

**Steps**:

1. `J/adapter/in/http/detail/ArtifactController.java`: `GET /api/v1/missions/{missionId}/artifacts` and `GET /api/v1/missions/{missionId}/artifacts/content`. Holds only: `MissionId.parse` (empty is `throw DetailRefusal.notFound()`), for content the `RawQuery` decoding of every `path` value into `ArtifactPathInput`, one call on `ArtifactQuery`, mapping through `ArtifactMapper`. Status mapping is `ProblemMapper`/`ProblemAdvice` (WP12; do not edit them). A malformed percent-encoding in the query is the status-only 400 that `ProblemAdvice` already gives (WP12).
2. `J/adapter/in/http/detail/ArtifactMapper.java`: `ArtifactListing` -> body (`entries[]` with `path`, `kind`, `sizeBytes`, `modifiedAt`, `readable`, and `truncated`) and `ArtifactContent` -> body per the contract schema `ArtifactContent` (`content`, `redacted`, `sizeBytes`, `kind`, `mediaType`, `path`; read `contracts/mission-status/schemas/`). It imports nothing from `domain.readmodel.derive`, `domain.redaction` or `application..` other than `application.query.port.in..` (rule 15). This route carries no `@ProjectionRow` pair (the 26 pairs are P9 to P11).
3. `J/config/ArtifactWiring.java`: one `@Configuration` with the `ArtifactQuery` bean built from existing beans (`MissionReadModel` for the lookup, `TextSource`, `AdmissionGate`, diagnostics). Do not edit `ServiceWiring` or `DetailInfrastructureWiring`.
4. Row C2: a per-route fixture proves a malformed or unknown `missionId` is **404, never 400**, for both operations, through `HttpHarness#startWith` (WP10; do not edit the harness). Foreign Host or Origin is 403 `request_refused` with zero reads (row C1).
5. The path-rule table of AC-5.2 runs at the HTTP leg: `..%2fx` 400; `%252e%252e` decodes once to the literal `%2e%2e` and is 404 (never traversal, never double-decoded); `path=a&path=b` and `path=spec.md&path=plan.md` 400 (never a 404 for a joined name); a missing `path` and an empty `path=` 400 with the contract Problem body (`code` `invalid_artifact_path`); `%ff`, `%c0%af` and `%e2%82` each 400; a literal `+` is a plus (`a+b` names a file `a+b`, 404 when absent, never `a b`); a backslash, NUL, line feed, drive letter, `~/`, empty segment, trailing slash and a 513-character path each 400; a name with a space, an accent, an at sign, a leading dot or a segment named `home` is accepted. Control: `spec.md` is 200. The rows that do not depend on percent-decoding (zero, two or one value; an undecodable input; the artifact-path rule) also run at the port through the plain-Java caller (AC-13.3).

**Files**: `ArtifactController.java` (~90 lines), `ArtifactMapper.java` (~110), `ArtifactWiring.java` (~45).

**Validation**: controller tests and the path table green; rules 3, 3b, 15, 16 green with their non-zero counts.

---

### Subtask T117: Served route, fixtures, README sentence, shared-file edits

**Purpose**: Golden coverage of both routes, the AC-12.1 rows A1 to A8, and the named edits.

**Steps**:

1. `T/conformance/golden/served/ArtifactServedRoute.java` implements WP10's `ServedRoute` (shape and request-key conventions: WP10 T071 step 1; this work package does not edit it). `goldenFiles()` is `{list-artifacts.json, get-artifact-content.json}`; `served()` is `ServedRoutes.expectedEntries(goldenFiles())`: for `list-artifacts.json` the only request key is `"-"` (`GET .../artifacts`), for `get-artifact-content.json` the keys are artifact paths (`GET .../artifacts/content?path=<key>`). The fixtures that carry them (WP07's; none written here; the review checklist, pinned by the test of step 1b): `artifacts-populated` (both files), `artifacts-sort` (listing), `artifacts-refusals` and `artifacts-redaction` (content). A fixture with no golden is Java-only and is not an entry (`artifacts-links` is Java-only, links created at test time; rule of WP18 T131 step 3). The listing goldens (`artifacts-populated`: nested directories, `research/`, `contracts/`, `checklists/`, `tasks/WP01-x/review-cycle-1.md`, a file with a space and an accented name, a file with a leading dot, and `spec.md`, `tasks.md`, `meta.json`, `lanes.json`, `tasks/WP01-x.md` as artifacts; it reads those authored files under scope ARTIFACT and must not fail the fence: AC-11.2) and the content goldens (AC-5.9: every fixture file's response equals the oracle's byte for byte).
1b. **Provider-loaded guard and provider-level completeness (TASKS-GREEN-002, TASKS-FRESH3-003).** `ServedRoutes` (WP10) treats a missing class as an empty route, so a mistyped provider name would leave the golden suite green with zero comparisons. Add `T/conformance/golden/served/ArtifactServedRouteTest.java` (owned): it asserts that `ServedRoutes` (through the WP10 accessor of the providers actually loaded) loaded `ArtifactServedRoute`, that `goldenFiles()` equals its `ServedRoutes.OWNER` row (`list-artifacts.json` and `get-artifact-content.json`), and the **provider-level completeness assertion**: `served()` equals `ServedRoutes.expectedEntries(goldenFiles())`, i.e. every manifest fixture holding one of those golden files is served by this provider (a fixture-by-golden pair that no provider registers is red here even when the fixture is served for another operation, which the fixture-level `ServedRoutesCompleteTest` of WP18 alone cannot see). `ServedRoutesCompleteTest` stays WP18's whole-set floor.
2. AC-4.9 fixtures **generated at test time** (never committed) in a `@TempDir`: `flat-bound` (the three root records `meta.json`, `status.events.jsonl`, `status.json` plus 99997 regular files `f00000.md` to `f99996.md`: counter 100000, 99998 eligible) and `nested-bound` (the three root records, 997 regular files and 99 directories each holding 999 regular files: counter 3 + 997 + 99 + 98901 = 100000, 99899 eligible). Each lists 1000 entries with `truncated` true while the collector's high-water mark (test accessor) is asserted at most 1001; the same trees with one more regular file (counter 100001) answer 500 `artifact_listing_unreadable`. A directory or a root record not counted would let the nested tree pass at 100001 (the mutation row). Create empty files; clean the temporary directory afterwards.
3. AC-4.3 (`readable` agrees with content): a property test over every fixture listing: for each entry, `content` of its path is 200 exactly when `readable` is true (fixtures: oversized, NUL, invalid UTF-8, credential and unreadable files; control: the 200 file is `readable` true).
4. AC-4.5/AC-4.6/AC-4.7/AC-4.8: links (provisioned from `PROVISION_PLAN`, never committed), root records in any case, `notes/status.json` listed, floor of `modifiedAt`, the diagnostics of an injected-fault entry (exactly one `artifact_unreadable`; none for an oversized, NUL, non-UTF-8 or credential file; a vanished file omitted), the file-name encoding legs: the `NameEncoding` stub twin (runs under any locale, not skipped) and the real-locale legs behind `Utf8Host.assumeUtf8()`; the process-level `LC_ALL=C` leg belongs to WP18.
5. AC-12.1 rows for the two operations: C1 to C7, A1 to A8 (A1 listing unlistable or walk bound; A2 to A7 content; A8 locale), each with its fixture at the port and the HTTP leg; AC-12.3 no silent success (no fixture answers 200 with empty `entries` unless a row says 200); AC-12.2/AC-12.4 no absolute path, `HOME`, fixture root or canary in any diagnostic line or Problem body; AC-8.3 canaries.
6. README locale sentence (named edit; touch no other line of `S/README.md`): one sentence that says the artifact routes and the Work Package index need a UTF-8 locale for file names (`LC_ALL=C.UTF-8` or any installed UTF-8 locale; it names `sun.jnu.encoding`). **The sentence must contain the three literal substrings `UTF-8 locale`, `sun.jnu.encoding` and `LC_ALL`** (for example: "The artifact routes and the Work Package index need a UTF-8 locale for file names (`LC_ALL=C.UTF-8` or any installed UTF-8 locale; the JVM reports it as `sun.jnu.encoding`) ..."); "UTF-8 file-name locale" does not contain `UTF-8 locale` and is wrong and what the service answers otherwise (500, nothing omitted silently). Test `T/adapter/in/http/detail/ArtifactControllerReadmeLocaleTest.java` asserts the README contains all three literals `UTF-8 locale`, `sun.jnu.encoding` and `LC_ALL`; WP17 writes the rest of the README, keeps that sentence, and its Java README test (`MissionStatusReadmeTest`) asserts the same three literals.
7. `T/adapter/in/http/rest/OutOfScopeRoutesTest.java`: **rebase and re-read first** (WP13, WP14 and WP15 may have removed theirs). Remove only the two lines `"/api/v1/missions/01J01000000000000000000001/artifacts",` and `"/api/v1/missions/01J01000000000000000000001/artifacts/content?path=spec.md",` of `OUT_OF_SCOPE` (two lines, not one: this work package serves two routes; "Plan defects found" item 3). Touch nothing else.
8. Port-level legs (AC-13.3): through WP12's `PlainCaller`, no Spring context: `list` and `content` return typed results for a populated Mission; `content` throws `DetailRefusal` with the kind of each non-network row (a path value count of zero, two or one, `Undecodable`, the artifact-path rule); the plain-Java caller runs the 64-call concurrency of AC-22.1 (four gated operations, E-1) only in WP18, not here. The legs live in `T/application/query/portlegs/ArtifactPortLegsTest.java` (new, owned; **outside** `conformance.port` and **not** listed in `R/portlevel-tests.txt`): `PortLevelClassSetTest` requires every class of `conformance.port` to depend on `PortSourceSelector` or `PortFixtures`, and `PortSubsetSecondLegTest` runs every listed id on an in-memory and a filesystem source through a selector fixture, which carries only `MissionStatusQuery` and cannot carry a detail port (TASKS-GREEN-001). Obtain the port from `DetailFixture` (WP10) behind `PlainCaller` (WP12). Append no line to `R/portlevel-tests.txt`; run `PortLevelClassSetTest` and `PortSubsetSecondLegTest` to show nothing changed.
9. JaCoCo recount on the merged tree. Expected shape (the command is the authority): `application` plus `ArtifactQueryService`, `ArtifactWalk`, `ArtifactReader`, `ArtifactLimits` (and any nested type you declare); `domain` unchanged.

`R/jacoco-class-floor.properties` holds two count lines, `domain=` and `application=` (55 and 44 on the flat checkout; the numbers on your tree are whatever PR A's tip holds). This work package is **not** the owner of the file (WP01 is); it makes a **named edit**: rebase, state the edit in the commit message, touch nothing else of the file. The new number is **derived by command at the commit that adds the classes**, never typed from memory or from the "expected" figures in this prompt:

```bash
cd services/mission-status-api
./gradlew --no-daemon test jacocoTestReport
python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"
```

Write the two printed numbers into the two lines. The count is over `<class>` elements, so a nested record, enum or sealed variant you declare inside a counted class raises it too. `jacocoScopeCheck` has floor semantics (a stale or lowered count is not detected by design, D-65), so the review brief compares the diff of the file with the classes this work package added. **Merge rule (D-145):** lanes that run concurrently each derive a count on their own tree; the lane merged second rebases, re-runs the command on the merged tree and writes what it prints in a named-edit commit of its own. WP17 T125 owns the single D-145 equality comparison on the PR B tip and WP18 re-runs it; a mismatch is repaired by a named edit of this file by the WP that found it.

**Files**: `ArtifactServedRoute.java` (~140), the walk, reader and service tests (~900 lines together), `ArtifactControllerReadmeLocaleTest.java` (~40), the README sentence, `OutOfScopeRoutesTest.java` (two lines), `jacoco-class-floor.properties`, `ArtifactPortLegsTest.java` (~80).

**Validation**: `DetailGoldenSuiteTest` green with this provider; both bound trees pass at 100000 and fail at 100001; `PortLevelClassSetTest`, `PortSubsetSecondLegTest`, `PortLevelIdsTest`, `OutOfScopeRoutesTest`, `jacocoScopeCheck` green.

---

### Subtask T118: Gate

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

2. Targeted surface that must be green: AC-4.1 to AC-4.9, AC-5.1 to AC-5.9, AC-12.1 rows A1 to A8 and C1 to C7, `ArtifactMetaReadCountTest`, `ArtifactQueryServiceGateTest`, goldens for the registered fixtures, the permission cases (both legs), `PortLevelClassSetTest`, `PortSubsetSecondLegTest` (both named explicitly in the Gate G run: they fail on a class or id that opens no selector fixture), `ArtifactServedRouteTest`, `OutOfScopeRoutesTest`, the ArchUnit rules. NFR-006 terminology grep of plan section 5 (expect only the marked legacy `feature_slug` literal of `LanesCodec`, WP11; any other hit is a defect): `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md`.
3. Revert-fails rows (standing named tests unless marked): AC-4.1 comparator control (perturb one byte of a listing golden; classify `spec.md` under AUTHORED for the listing and the fence test, AC-11.2, goes red); AC-4.2/4.4/4.9 (`String.compareTo`, a `Collator` or file-system order; an unbounded heap (M, one-off in a scratch copy, command and result in the PR's "Tests run"); count a directory or a root record as zero so the nested tree passes at 100001; hold more than 1001 paths); AC-4.3 (ignore the NUL check, or answer content 200 for a `readable: false` entry); AC-4.5 (follow a symlinked directory, list a symlinked file, admit root `STATUS.JSON`); AC-4.6 (`Math.round`); AC-4.7 (drop the `artifact_unreadable` diagnostic, or write one for a NUL file); AC-4.8 (drop the locale probe, omit a non-ASCII entry under the stub); AC-5.1 to AC-5.8 (each status of the order of decision, a double percent-decode, `+` as a space, a missing pattern in `leak-patterns.json`, redaction without the `\S*` widening); AC-5.9 comparator control; AC-1.8 (make an artifact route touch the ledger); AC-22 (skip the gate in either operation); typed identifiers (let an empty parse reach the service or map it to 400).
4. Do not write to `M/**` (interim default F1/E-12). Put the tracer entry text (with the `@PermissionCase` ids you created) in your hand-off report; the orchestrator appends it locally.

- **Public repository hygiene (C-006).** No home-directory path, user name, address or token in any file, fixture, test name or commit message. Use the placeholders `<repo>` and `<scratch>`. Credential-shaped test inputs are assembled at test time from two fragments (prefix and body) in a temporary directory; a committed fixture holds at most a near-miss one character short (D-48). Terminology: say Mission and Work Package, never "feature" in new prose (NFR-006; the grep of plan section 5 shows only the marked legacy `feature_slug` literal of `LanesCodec`).
- **Tracer entry (charter standing order 3).** Not written by this work package: interim default F1/E-12 (orchestrator, 2026-10-13; binding until the operator rules on plan E-12): PR B adds only NEW files to the mission directory (archive freeze); no work package of PR B edits an existing `M/**` file already on `main`. Draft the entry (approach, deviations, and for WP15/WP16 the `@PermissionCase` ids) in the hand-off report; the orchestrator appends it to `M/traces/approach.md` locally.

**Validation**: Gate G and Gate P green; `git status` shows only `owned_files` plus the named edits.

---

## Self-contained green

PR B is a draft that must be green at this work package's tip and at its own tip (plan section 11, "Each PR is self-contained and green", D-153). This work package does not depend on WP13: its base does not contain WP13 to WP15.

- **Fixtures live with their tests.** The goldens and fixture trees (`R/conformance/**`: `artifacts-populated`, `artifacts-sort` and the content fixtures) were committed by WP07 and are registered here by `ArtifactServedRoute`; this work package adds none. The 100000-entry trees, the near-limit files and every credential-shaped string are generated at test time; links come from `PROVISION_PLAN`.
- **Floors and counts satisfiable here.** JaCoCo recounted at the commit that adds the four classes; the per-class 0.90 line gate holds because the walk, reader, service and limits tests cover them. The `PermissionCaseFloorTest` (floor of four ids over WP15 and WP16) and `ServedRoutesCompleteTest` are WP18's and absent here; no test asserts a count that only a sibling work package can satisfy. The native floors (`--floor 3`, `--request-floor 49`) and `R/nativesmoke/requests.json` are unchanged (no `@Tag("native")` test, no smoke stage: D-99); WP17 raises them and adds the stage.
- **No test or gate names a type of a later or sibling work package.** The route uses types of WP05, WP06, WP09, WP10 and WP12 only (no `MissionDetail*`, `WorkPackage*` or `WorkPackageDetail*` type of WP13 to WP15; no `ReadinessDeriver`). `OutOfScopeRoutesTest` at this tip still lists the Mission and Work Package paths as 404 and loses only the two artifact lines. `ServedRoutes` treats a missing provider as an empty route.
- **The pin `tests/ci/test_mission_status_api_build.py` stays green (Gate P):** rule-9 literals; the `adapter/in/http` sub-directory clause (`detail` only; **no `dto` directory created here**); the `EventsController` needles (untouched); the models list and drift probe (WP06's); `@Tag("perf")` (none); the tracked-path scan (no `:` or `$` in a new path; the non-ASCII and 100000-name trees exist only under a temporary directory; stage new files first); the probe list; native-tag and `requests.json` clauses (numbers unchanged); the partition pin.
- **Mission record.** `M/meta.json` is complete and untouched. Under interim default F1/E-12 this work package commits nothing under `M/**`: the orchestrator keeps the `M/status.json` materialisation and the tracer appends locally. `M/status.json` is the materialisation of `M/status.events.jsonl` (`.venv/bin/spec-kitty agent status materialize --mission mission-status-read-api-mission-detail-01M4S6D5`), never hand-edited; do not commit untracked CLI state blind (compare with the coordination copy first). Lane transitions are made with `spec-kitty agent tasks move-task`, never by editing a file. With the record intact `cutover-guard`, the mission-state audit (`.venv/bin/spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`) and the corpus-blocking job stay green. This work package writes nothing under `M/**` (interim default F1/E-12).

---

## Plan defects found

1. **Resolved (TASKS-DECOMP-009, TASKS-ORDER-004, TASKS-COVER-001): `ArtifactPortLegsTest` is owned by this work package** (wps.yaml and the frontmatter `owned_files`/`create_intent`; it lives in `T/application/query/portlegs/`, outside `conformance.port`, and is not listed in `R/portlevel-tests.txt`). Nothing is out-of-map and nothing is asked of the orchestrator.
2. **Order of decision versus typed identifiers.** FR-005 puts the `path` check (400) before the Mission lookup (404). The plan makes the controller turn an ill-formed `missionId` into `DetailRefusal.notFound()` before any `path` check, because the artifact-path rule lives behind the port and is barred from controllers by rule 15. For a well-formed ULID of an unknown Mission this prompt validates the path first inside the service (spec order holds). For an ill-formed `missionId` together with a malformed `path` the answer is 404, not 400 (ruling OO-2, folded into the spec as S-27 and FR-005 "Identifier precedence"; AC-5.2 states it). This work package's own test covers the combination. **RULED: OO-2 (orchestrator ruling 2026-10-13, binding; formerly TASKS-COVER-009 item 2): an ill-formed `missionId` answers 404 (E-5), also when `path` is malformed.** This work package implements 404 for the mixed case (the controller maps the ill-formed id to `DetailRefusal.notFound()` before any `path` check) and pins it with one controller test: an ill-formed `missionId` together with a malformed `path` (for example `..%2fx`) is 404 `not_found`, never 400 (the case is recorded in plan section 14 and the spec-fold S-list by the orchestrator, not here).
3. **`OutOfScopeRoutesTest`: "one line each" is two lines for this work package.** The plan's shared-file row says each of P10 to P12 removes one line; P12 serves two routes (listing and content) and so removes two. Not a conflict, but the wording differs from the table.
4. **A reflection-hint miss from this route has no named-edit permission** (see WP13 item 2): `MissionStatusApplicationHints` may be edited by P6, P8 (named) and P13 only. A proven native miss is an orchestrator item. **RULED: OO-3 (orchestrator ruling 2026-10-13, binding; formerly TASKS-COVER-009 item 3).** Of the PR B work packages only WP17 edits `J/config/MissionStatusApplicationHints.java`. WP13 to WP16 do not edit it: on a locally proven native reflection-hint miss (`nativeCompile nativeTest nativeSmoke`) this work package STOPS and reports the miss to the orchestrator, who routes the hint to WP17. The JaCoCo recount stays a named edit under the plan's merge rule (D-145).
5. **Locale sentence has no pinned wording.** The plan names "the README locale sentence" (named edit of P12) but no test string. This prompt fixes the contract at the three literals `UTF-8 locale`, `sun.jnu.encoding` and `LC_ALL` (T117 step 6); WP17 must keep them and its Java README test asserts the same three (one contract, two tests).
6. **Resolved (TASKS-COVER-010 c): `PermissionCaseFloorTest` split is 2+2** (WP15 two, WP16 two, see WP15 item 4); report the two ids in the hand-off report (no `M/**` write, interim default F1/E-12).

## Definition of Done

Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.

- T112: pre-flight green and recorded; every new test red on the base for its stated reason; shells compile.
- T113: both operations run inside the gate; the matched `meta.json` is read once; no ledger or coordination access; the path is validated before the lookup.
- T114: the walk counter, the 1001-path heap and the exact boundaries (100000 served, 100001 refused) hold; `readable` is computed for at most 1000 entries; the sort is by code point.
- T115: the order of decision is exactly FR-005's; the cap is applied twice (open handle, bytes read); redaction and the credential refusal use `TextScreen`.
- T116: controller, mapper and wiring hold no logic; C2 is 404; the AC-5.2 table is green at the HTTP leg and, where it does not need percent-decoding, at the port; rules 3, 3b, 15, 16 green.
- T117: route registered and `ArtifactServedRouteTest` green (provider loaded; `goldenFiles()` equals its `OWNER` row; `served()` equals the manifest-derived `expectedEntries`); both bound trees pass at 100000 and fail at 100001; rows A1 to A8 and C1 to C7 have fixtures; README locale sentence present; two lines removed from `OutOfScopeRoutesTest` (the artifact paths only); no line appended to `R/portlevel-tests.txt` (the legs are in the owned `ArtifactPortLegsTest`); JaCoCo lines equal the command's output.
- T118: Gate G and Gate P green; tracer entry text in the hand-off report with the permission ids; no `M/**` write; no write outside `owned_files` and the named edits.

## Risks

- **Walk cost.** 100000 `lstat` calls and a 100000-entry directory in two tests. Mitigation: empty files in a `@TempDir`, one listing per directory, the collector bounded; `/tmp` shares the root disk (check `df -h /` before running) and the temporary directory is cleaned afterwards.
- **Hidden second sort.** Sorting the whole walk defeats the bound. Mitigation: the collector's high-water-mark assertion.
- **Locale-dependent tests.** A POSIX locale makes file creation throw before the service is reached. Mitigation: `LC_ALL=C.UTF-8`, `Utf8Host.assumeUtf8()`, the stub twin.
- **Double decoding or `+` as a space** in the adapter. Mitigation: the AC-5.2 table, including `%252e%252e`.
- **Content leaks in a refusal body or a log line.** Mitigation: AC-5.1 and AC-12.4 scans; never log content.
- **Concurrent lanes.** WP13 to WP15 edit `OutOfScopeRoutesTest` and JaCoCo. Mitigation: merge order WP13 -> WP14 -> WP15 -> WP16 and the conflict rule of the Concurrency bullet.

## Reviewer Guidance

- Verify the **red-first form** (scratch worktree of WP12's tip) and that no assertion was weakened.
- Check the read counts and the recorded accesses: one `meta.json` read of the matched Mission, no LEDGER access, no coordination class, scope ARTIFACT quadruples.
- Check the walk counter arithmetic against the two bound fixtures and that the collector never exceeds 1001 paths; check `CodePoints.compare` is the only comparison.
- Check the order of decision of `ArtifactReader` against FR-005 status by status, and that the cap is applied by the open handle then by bytes read.
- Check the gate wraps both operations, and `OutOfScopeRoutesTest` lost exactly the two artifact lines, `R/portlevel-tests.txt` is untouched, the JaCoCo lines match the command on the tip, and both legs of every `@PermissionCase` exist.
- Check the architectural gates implicated by the touched files by file (rules 3, 3b, 7, 15, 16, `PortLevelClassSetTest`, `NoUncappedReadTest`, `NoUnboundedListingTest`).
- Look for host paths, user names or tokens in tests, fixtures, README and commit messages.

## Implementation command

```bash
spec-kitty agent action implement WP16 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
