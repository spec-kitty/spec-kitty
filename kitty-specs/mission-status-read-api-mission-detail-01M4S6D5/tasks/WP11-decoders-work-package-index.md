---
work_package_id: WP11
title: '[PR A] P6 Decoders and the Work Package index (FR-006)'
dependencies:
- WP09
- WP07
- WP05
- WP06
- WP10
requirement_refs:
- FR-006
- FR-012
- FR-007
- NFR-005
- NFR-008
planning_base_branch: issue-957-mission-status-read-api-mission-detail
merge_target_branch: issue-957-mission-status-read-api-mission-detail
branch_strategy: Planning artifacts for this mission were generated on issue-957-mission-status-read-api-mission-detail. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-957-mission-status-read-api-mission-detail unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-status-read-api-mission-detail-01M4S6D5
base_commit: ed4acdd90df4f2dc14cf053b69abf0538f0a4e8f
created_at: '2026-10-14T06:24:37.551009+00:00'
subtasks:
- T073
- T074
- T075
- T076
- T077
- T078
- T079
- T080
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/
create_intent:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/FrontmatterDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/LanesDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/DecoderWiring.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/WpMetadata.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/FrontmatterResult.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/LanesManifest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/ReviewCycleMeta.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/LanesResult.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/YamlFrontmatterDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/JsonLanesDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/WpFrontmatterCodec.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/ReviewCycleCodec.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/LanesCodec.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/adapter/out/filesystem/codec/C12aPortOut.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/index/A12cUsesCodec.java
execution_mode: code_change
model: sonnet
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/FrontmatterDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/port/out/LanesDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/DecoderWiring.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/WpMetadata.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/FrontmatterResult.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/LanesManifest.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/ReviewCycleMeta.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/domain/model/LanesResult.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/application/query/index/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/YamlFrontmatterDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/JsonLanesDecoder.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/WpFrontmatterCodec.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/ReviewCycleCodec.java
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/LanesCodec.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/application/query/index/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/WpMetadata*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/FrontmatterResult*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/LanesManifest*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/ReviewCycleMeta*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/domain/model/LanesResult*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/YamlFrontmatterDecoder*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/JsonLanesDecoder*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/WpFrontmatterCodec*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/ReviewCycleCodec*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/codec/LanesCodec*Test.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/adapter/out/filesystem/codec/C12aPortOut.java
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/architecture/fixture/application/query/index/A12cUsesCodec.java
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP11 – [PR A] P6 Decoders and the Work Package index (FR-006)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Pull request and dependencies

- **Pull request**: **PR A**, plan phase **P6** (a draft stacked on the branch that carries #5529's last slice; no route is served in PR A). This WP runs **concurrently with WP12 (P8)** with disjoint scopes; the lane merged second recounts the JaCoCo lines on the merged tree (D-145).
- **External dependency (not a `dependencies` entry)**: WP01 cannot start until the orchestrator has merged the re-cut tip of #5529 (the side-first layout) into this branch; PR A stacks on #5529's last slice and #957 cannot merge before #5529 (C-005). PR B stacks on PR A; #5533's Java work stacks on PR A.
- **Dependencies inside the mission**: WP09 (P5: `TextSource`, `Eligibility`, `ArtifactPaths`, `NameEncoding`, `readBytes`), WP07 (P4: fixtures `wpm-01..28`, goldens, manifest), WP05 (P3: `WpId` with `parse`), WP06 (P2: creates `M/research.md`; the YAML spike appends to it), WP10 (P7: `ProvisionPlan`, `DetailFixture`, `Utf8Host`; D-126).
- **Write scope**: `owned_files` of the frontmatter only. The index and decoder classes are the only production code; the route services that use the index are WP13..WP15 (PR B).
- **Named edits (out-of-map; not in `owned_files`)**. Rule for each: rebase onto the current lane tip, state the edit in the commit message, touch nothing else of the file.
  - `M/research.md`: **append** the YAML 1.1/1.2 parity spike section (a kitty-specs file: a `code_change` WP may not own one; the file is created by WP06; append-only).
  - `R/jacoco-class-floor.properties`, the `application` and `domain` count lines only (owned by WP01): rebase and recount if a concurrent lane merged first (plan merge rule, D-145).
  - `J/config/MissionStatusApplicationHints.java`: only on a miss proven by the local `nativeTest`/`nativeSmoke` run (E-7) or by CI at PR A's tip (owned by WP17). Serialised by merge order with WP12.
  - `T/architecture/ArchitectureControlsTest.java` (owned by WP03): exactly two `Control` rows for the AC-6.5 planted fixtures `C12aPortOut` and `A12cUsesCodec` (T078), nothing else of the file (a recorded deviation, wps.yaml DV-5). WP12 edits it concurrently; the shared-file rule of the wps.yaml header applies: the lane merged second rebases onto the merged tree, keeps the UNION of the `Control` rows of both lanes, and re-runs `ArchitectureControlsTest` and `ArchitectureRulesTest` (the contiguity guard and the count assertions) on the merged tree before its commit.
  - `M/traces/approach.md`, `design-decisions.md`, `tooling-friction.md`: append-only tracer entries.
- **Alias key**: `S` = `services/mission-status-api`; `J` = `S/src/main/java/org/speckitty/missionstatus`; `T` = `S/src/test/java/org/speckitty/missionstatus`; `R` = `S/src/test/resources`; `M` = `kitty-specs/mission-status-read-api-mission-detail-01M4S6D5`. Paths are post-re-cut (plan section 1.1) unless "exists at the checkout" is said.

## Objective

Implement the shared Work Package file index of FR-006 and its two outbound decoder ports: `FrontmatterDecoder` and `LanesDecoder`, their domain records, the pure codecs, the adapters, the `WorkPackageIndex` (candidate selection, id rule, first-valid-wins duplicates, skip diagnostics, the locale rule, single-pass body capture of one id), and the recorded YAML 1.1/1.2 parity spike, verified against the oracle outcome class of every fixture `wpm-01..28`.

## Context

- **Why.** `getMission`, `getWorkPackage` and `getWorkPackageDetail` all define "what a Work Package is" through this one index (FR-006); it mirrors the oracle's `index_work_packages` and `wp_task_files` (`src/specify_cli/status/wp_metadata.py`, exists at the checkout). The route services of PR B only call it.
- **Layering (D-41, D-57, AC-6.5, plan section 13).** The decoder bytes-in/record-out port lives in `application.query.port.out` (interfaces only: rule 13); the implementing class sits **directly** in `adapter.out.filesystem` and delegates to the pure, port-free codec in `adapter.out.filesystem.codec`, which depends among project packages only on `domain` and itself (rule 12a) and is used only by `adapter.out.filesystem` and `testsupport` (rule 12c). The application never calls the codec, it calls the port. The domain records the codecs return (`WpMetadata`, `FrontmatterResult`, `LanesManifest`, `ReviewCycleMeta`, `LanesResult`) are in `domain.model` so the codec may return them (rule 12a). No ArchUnit rule text is amended (the rules 4, 7, 12a to 12c pass with planted violations: AC-6.5).
- **The index record never holds the body (D-76, FRESH3-007).** `IndexedWorkPackage` holds the validated frontmatter fields and the file name only. `WorkPackageIndex.build(mission, Optional<WpId> captureBodyOf)` keeps the body of the first valid file that holds the requested id and of no other; there is no second read. One capped read buffer at a time.
- **The locale rule (D-73, FRESH3-004).** Restricted to **candidate names** (start with `WP`, end with `.md`): when `DirListing.Names.trustworthy` is false (a non-Windows host whose `sun.jnu.encoding` is not UTF-8) and a candidate holds a non-ASCII character (or U+FFFD), the index refuses with a source fault that the route turns into 500 `source_unreadable` plus one path-free `source_unreadable` diagnostic; a non-candidate such as `tasks/notes-é.md` is not refused. Under a UTF-8 locale a candidate holding U+FFFD is an ineligible path and is skipped (FR-006 item 2).
- **SK-353 (D-97, S-19).** Work Packages whose `subtasks` are written as mappings are refused with `projection_refused` (the decoder does not reproduce Python's `str()` of a mapping), pinned by fixture `wpm-28`, which stores the oracle's outcome; where the oracle serves a stringified mapping the difference is `knownDivergence` V20 (WP07's). Note: the spec text still says `wpm-01..27` until the orchestrator's spec-fold (plan section 14, S-19) is applied; the plan's 28-case reading is binding.
- **E-6 (escalation, not a quiet addition).** If snakeyaml cannot decode the YAML 1.2 subset the corpus needs identically, **stop and escalate**; add no dependency (AC-19.4). The default is a restricted `SafeConstructor` that refuses what it cannot decode identically (R-15).
- **Exists at the checkout:** `J/config/MissionStatusApplicationHints.java`, `J/config/ServiceWiring.java`, `J/adapter/out/filesystem/codec/{LedgerLineDecoder,RowClassifier,PythonJson}.java`. **Exist after earlier WPs / the re-cut:** `J/application/query/port/out/TextSource.java` and DTOs (WP09), `J/domain/model/WpId.java` (WP05), `J/application/query/artifact/Eligibility.java` (WP09), `J/application/query/MissionLookup.java` (WP01), `T/testsupport/{ProvisionPlan,DetailFixture,Utf8Host}.java` (WP10), the fixture classes `wp-malformed-frontmatter` (28) and `wp-duplicate-id` (3) under `R/conformance/` (WP07). **New here:** every owned file.

### Subtask T073: Pre-flight and red-first

**Purpose**: confirm the tree, then write the index and decoder tests before the code.

**Steps**:
1. Pre-flight (first step): `cd services/mission-status-api && export LC_ALL=C.UTF-8 && ./gradlew --no-daemon test --tests 'org.speckitty.missionstatus.architecture.CoupledSymbolsShapeTest'` (with `CONTRACT_BUNDLE` and `CONTRACT_BUNDLE_SHA256` exported as in plan section 5). Green or stop and report. Record the #5529 tip sha in the first commit message; run the C-005 string-literal grep of plan section 5 and paste the result.
2. Read the oracle outcome class of each fixture: `R/conformance/wp-malformed-frontmatter/wpm-NN/` and its golden/`outcome` data as WP07 generated it (do not guess; list the directory and read the manifest entries of the class). For `wpm-01..28` the index test asserts, per fixture, the oracle outcome class: parsed with these fields, skipped (with `wp_file_skipped`), or fault.
3. Write first: `T/application/query/index/WorkPackageIndexTest.java` (table test over all 28 fixtures via `ConformanceTree.detailFixtures()`, the `valid` control, the duplicate fixtures `wp-duplicate-id` (3), first-valid-in-byte-order wins, `WP01-B.md` before `WP01-a.md`), `WorkPackageIndexLocaleTest.java`, `WorkPackageIndexAccessSetTest.java` (one `WP_FILE` READ per candidate, none twice), `IndexedWorkPackageShapeTest.java` (reflection: no component is a body), and the decoder/codec tests of T074/T075. Run them once: red on the phase base (the types do not exist). Keep the failing counts for the commit message.

**Files**: tests only here (sizes under later subtasks).

**Validation**: pre-flight green; the new tests are red; sha and grep in the commit message.

### Subtask T074: Ports and domain records

**Purpose**: the two outbound ports and the typed records they return (rule 12a).

**Steps**:
1. `J/application/query/port/out/FrontmatterDecoder.java`: interface only: `FrontmatterResult decodeWorkPackage(byte[] bytes)` and `ReviewCycleMeta decodeReviewCycle(byte[] bytes)`; bytes in, a typed record or a rejection out; no path and no file access.
2. `J/application/query/port/out/LanesDecoder.java`: `LanesResult decode(byte[] bytes)`.
3. `J/domain/model/WpMetadata.java`: the known fields of `WPMetadata` (`src/specify_cli/status/wp_metadata.py`, line ~222 onward: `work_package_id`, `title`, `dependencies`, `base_branch`, `base_commit`, `created_at`, `planning_base_branch`, `merge_target_branch`, `branch_strategy`, `requirement_refs`, `tracker_refs`, `priority`, `execution_mode`, `owned_files`, `create_intent`, `authoritative_surface`, `scope`, `task_type`, `subtasks`, `phase`, `phases`, `assignee`, `agent`, `model`, `agent_profile`, `role`, `shell_pid`, `shell_pid_created_at`, `history`, `lane`, `feature_slug`, `activity_log`, `review_status`, and the rest of the model: **read the file, copy the field list from it**, do not trust this list). Unknown keys are rejections (`extra="forbid"`). Record components only the routes need may be modelled; the rest are validated and dropped, but the validation must be equivalent. Records are immutable, no Spring.
4. `FrontmatterResult`: sealed: `Parsed(WpMetadata metadata, String body)` | `Rejected(RejectionClass kind)` (kinds: no frontmatter, no closing delimiter, YAML syntax error, duplicate key, not a mapping, validation failure, not strict UTF-8 is handled before decoding by the caller or by the decoder: pick one and document it in the Javadoc and in the test; the oracle skips a `UnicodeDecodeError` file with `wp_file_skipped`).
5. `LanesManifest` (the `lanes.json` shape of the current `mission_slug` form), `ReviewCycleMeta` (`reviewedAt`, `reviewer` strings, both optional, no more), `LanesResult` sealed: `Manifest(LanesManifest)`, `Corrupt`, `Legacy` (the legacy `feature_slug` shape with no `mission_slug`: ledger entry SK-351; the legacy literal `feature_slug` is the one allowed `feature` in `S/src/main`, marked as legacy, D-115).
6. Unit tests beside each record under `T/domain/model/{WpMetadata,FrontmatterResult,LanesManifest,ReviewCycleMeta,LanesResult}*Test.java` (construction, immutability, the sealed variants, equality). Each new record meets the per-class line floor 0.90 (JaCoCo class rule on `domain.*`; branch 0.80 on `domain.*` overall).

**Files**: two interfaces (~15 lines each), five records (~40-120 lines each), tests ~250 lines.

**Validation**: `./gradlew --no-daemon test --tests '*WpMetadata*' --tests '*FrontmatterResult*' --tests '*LanesManifest*' --tests '*ReviewCycleMeta*' --tests '*LanesResult*'`; ArchitectureRulesTest green (ports are interfaces only; domain imports nothing outside the JDK).

### Subtask T075: Codecs, adapters, wiring, and the YAML spike

**Purpose**: decode identically to Python or refuse; record how the dialect gap was settled.

**Steps** (package `adapter.out.filesystem.codec` for the codecs; `adapter.out.filesystem` for the adapters):
1. `WpFrontmatterCodec` (pure): strict UTF-8 through `StrictUtf8` (WP09); drop a leading BOM; translate `\r\n` and `\r` to `\n`; the text must start with `---`; the closing delimiter is the first later line whose stripped content is `---`; the text between is YAML; an empty document is an empty mapping; a document that is not a mapping, a duplicate key and a syntax error are rejections; the body is every line after the closing delimiter joined by `\n`; then validate as `WPMetadata` (unknown keys rejected; known keys coerced as `model_validate(..., strict=False)` coerces them: `shell_pid` as a string coerces to an int, `agent` may be a mapping, `reviewer` as a mapping, `on:` and `yes:` values, `010`, date-looking scalars: these are `wpm-11..17`). Use snakeyaml's restricted `SafeConstructor`, with duplicate-key detection (`allowDuplicateKeys(false)`), no custom tags, no anchors beyond what the corpus needs, and a **refuse-what-you-cannot-decode-identically** policy (R-15, S-19). **No new dependency.**
2. `ReviewCycleCodec` (pure): `reviewedAt` (RFC 3339 date-time, else null) and `reviewer` from the review-cycle frontmatter; a file that does not parse is an entry with null members and no diagnostic (row M11, D-46); the 262144 cap is applied by the caller via the port.
3. `LanesCodec` (pure): `LanesResult` from bytes (current shape, corrupt, legacy `feature_slug`).
4. `YamlFrontmatterDecoder implements FrontmatterDecoder` and `JsonLanesDecoder implements LanesDecoder`, **directly in `adapter.out.filesystem`**, each delegating to its codec and doing no file access (rule 7 unaffected).
5. `J/config/DecoderWiring.java`: the two decoder beans (`FrontmatterDecoder`, `LanesDecoder`) and nothing else; it is the single owner of both (only WP13 and WP15 inject them, WP13 for the index and WP15 for the lanes decoder; neither declares them, and WP14 and WP16 inject none; WP18's `SharedBeansUniqueTest` asserts exactly one each). They are constructed at start-up with no consumer until PR B, so a missing reflection hint would turn PR A's native legs red (plan section 5, `native` row). Run `./gradlew --no-daemon nativeCompile nativeTest` and `nativeSmoke -PnativeBinary=<binary>` locally (E-7; GraalVM required) and, on a proven miss only, add the hint in `J/config/MissionStatusApplicationHints.java` as a named edit stated in the commit message.
6. The spike (plan 11, P6): decode every `wpm-*` fixture, plus the dialect cases (`yes`/`on` booleans, `010`, timestamps), through snakeyaml and compare with the oracle outcome. Append a section to `M/research.md` (named edit): the table of dialect cases, the outcome of each (accepted identically / refused), the chosen policy, and the sha of the tree the spike ran on. If a case the corpus needs cannot be decoded identically **and** cannot be refused without breaking an oracle-parsed fixture, **stop and escalate (E-6)**; add no dependency.
7. Tests: `YamlFrontmatterDecoder*Test`, `JsonLanesDecoder*Test`, `WpFrontmatterCodec*Test`, `ReviewCycleCodec*Test`, `LanesCodec*Test` under their mirrored `T/adapter/out/filesystem[/codec]/` paths; assert `wpm-24..26` (a lone `0xC3`, `0xC0 0xAF`, `0xED 0xA0 0x80`) each skip with `wp_file_skipped` as the oracle does, and that `ReviewCycleCodec` never replaces a byte.

**Files**: `WpFrontmatterCodec.java` (~320), `ReviewCycleCodec.java` (~120), `LanesCodec.java` (~140), `YamlFrontmatterDecoder.java` (~50), `JsonLanesDecoder.java` (~50), `DecoderWiring.java` (~40); tests ~500 lines; `M/research.md` +~60 lines.

**Validation**: targeted tests; revert checks: replace the strict decode by a lenient `new String` and `wpm-24..26` go red; drop the duplicate-key guard and `wpm-07` goes red.

### Subtask T076: `WorkPackageIndex`, `IndexedWorkPackage`, `WpFile`

**Purpose**: the one component that defines what a Work Package is.

**Steps** (package `application.query.index`; uses only the ports and `Eligibility`/`WpId`):
1. `WpFile`: the file name plus its bytes buffer lifetime handle (never retained after decode).
2. `IndexedWorkPackage`: validated frontmatter fields (the ones the routes need, as a `WpMetadata` reference is acceptable) and the file name; no `body` component of any kind (`String` named `body`/`prompt` or `byte[]` is forbidden: `IndexedWorkPackageShapeTest`).
3. `WorkPackageIndex.build(MissionRef mission, Optional<WpId> captureBodyOf)` returns an index result with the winners in id order, the diagnostics to write, and the captured body of the first valid file holding the requested id. Algorithm exactly per FR-006 items 1 to 6:
   - candidates are the entries of `<primary dir>/tasks/` (list through `TextSource.list(..., nameLimit, ReadScope.AUTHORED)`; the bounded window from WP09) whose name starts with `WP` and ends with `.md`, case-sensitively, sorted by the **UTF-8 bytes** of the name (code point order; `WP01-B.md` before `WP01-a.md`); an absent `tasks/` is an empty set; a `tasks/` that exists and is not a real directory (file or link) is a fault (row M10);
   - a candidate that is a link, a directory (`stat` through the port, no follow) or not an eligible artifact path (`Eligibility`/`ArtifactPaths`) is skipped; a candidate that cannot be read is a fault (`source_unreadable`); one over 1 MiB (`SafeFiles.SMALL_FILE_MAX`) is a fault;
   - decode with `FrontmatterDecoder.decodeWorkPackage`; a rejection skips the file and writes `wp_file_skipped` with the Mission's `mid8` and no path;
   - a valid `work_package_id` (`WpId`) is required, else skipped; **the first valid file in byte order wins** an id; a later file with the same id is never served and writes `wp_id_duplicate`;
   - one capped read buffer at a time: read, decode, reduce to metadata (plus the single captured body), drop the buffer.
4. The locale rule: `trustworthy == false` and a candidate with a non-ASCII char or U+FFFD in its name refuses the whole index (fault -> 500 `source_unreadable` at the route, one path-free diagnostic, nothing omitted silently, no partial index); a non-candidate (`notes-é.md`) is not refused. The probe is `NameEncoding` through `DirListing.Names.trustworthy` (WP09); the stub leg injects a stub `NameEncoding` so it runs under any locale.
5. Diagnostics are written through the `Consumer<Diagnostic>` the service passes in (as the ledger side does); codes are `DiagnosticCode.WP_FILE_SKIPPED`, `WP_ID_DUPLICATE`, `SOURCE_UNREADABLE` (WP09).
6. **Visibility and bean ownership (TASKS-FRESH2-001).** `WorkPackageIndex` is a `public final class` with a `public` constructor taking exactly the `TextSource` (WP09) and the `FrontmatterDecoder` (this WP), because `config` constructs it. It holds no per-call state (the `MissionRef`, the body selector and the `Consumer<Diagnostic>` are `build` arguments). **This WP declares NO `@Bean` of it and adds no wiring class for it**: a bean needs a `TextSource` bean, and that bean is WP12's `DetailInfrastructureWiring` (a lane that does not contain this WP, and this lane does not contain WP12's). The one `WorkPackageIndex` bean is owned by WP13 (`MissionDetailWiring`, built from the `TextSource` bean of WP12 and the `FrontmatterDecoder` bean of this WP's `DecoderWiring`); WP14 and WP15 declare none and inject that bean; WP16 neither declares nor injects it (it is not in WP16's lane). A unit test (`WorkPackageIndexTest`) constructs it with an `InMemoryTextSource` and the real decoder to prove the public constructor.

**Files**: `WorkPackageIndex.java` (~280), `IndexedWorkPackage.java` (~50), `WpFile.java` (~40); tests ~450 lines.

**Validation**: `./gradlew --no-daemon test --tests '*WorkPackageIndex*' --tests '*IndexedWorkPackageShapeTest'`; revert: re-read the winning file for the prompt and the access-set test (one `WP_FILE` READ per file) goes red; drop the `trustworthy` check and the locale stub leg goes red (a silent omission); sort by case-folded order and `wpm-27` goes red.

### Subtask T077: AC-6.1 cases 22 and 23, the non-ASCII cases, SK-353

**Purpose**: the cases that need provisioning and the locale precondition.

**Steps**:
1. Cases 22 (a **directory** named `WP05-d.md`) and 23 (a **symlink** named `WP06-l.md`) are provisioned at test time through WP10's `ProvisionPlan` and `DetailFixture` (never committed, NFR-007); both are skipped candidates, the target of the link is never read (instrumented port: no READ recorded for it).
2. Non-ASCII cases: `tasks/WP01-é.md`, `tasks/WP02-x.md`, `tasks/notes-é.md` generated at test time; call `Utf8Host.assumeUtf8()` (WP10) before creating the non-ASCII names; under a UTF-8 locale both Work Packages are indexed and `notes-é.md` is ignored; the stub-leg case (a `NameEncoding` stub reporting non-UTF-8) runs under any locale and calls no `assumeUtf8`.
3. SK-353 (D-97): fixture `wpm-28` (`subtasks` as mappings) is refused with `projection_refused`, as the committed outcome class says; assert against the stored oracle outcome (WP07) and the `knownDivergence` V20 entry if present. Do not "fix" the oracle; if the stored outcome and the D-97 decision disagree, stop and report to the orchestrator.
4. AC-6.2 (duplicates), AC-6.3 (two selectors: authored `WP07-x.md` holding `work_package_id: WP08` and a prompt file `WP08-y.md`: the frontmatter comes from `WP07-x.md`, the prompt lookup selector is the file name; this WP only provides the frontmatter side and a helper that exposes the file name, the route WPs assert the reference).

**Files**: tests ~250 lines (in `T/application/query/index/**`).

**Validation**: `./gradlew --no-daemon test --tests '*WorkPackageIndex*'` under `LC_ALL=C.UTF-8` and, once, under `LC_ALL=C` (non-ASCII cases skip with the not-run line; the stub leg still runs).

### Subtask T078: AC-6.5 layering and the stub leg of AC-6.6

**Purpose**: prove the decoder layering without weakening a rule, and the locale stub leg.

**Steps**:
1. AC-6.5. Facts at the checkout: `T/architecture/ArchitectureRules.java` rule 12 is `r12a` (the codec depends, among project packages, only on `domain` and itself), `r12b` (no file API), `r12c` (the codec is used only by `adapter.out.filesystem` and `testsupport`); `ArchitectureControlsTest` already plants `C12aSafeFiles` (red on 12a) and `G11cUsesCodec` (red on 11 and 12), and `T/architecture/fixture/adapter/out/filesystem/codec/Decoder.java` is the conforming skeleton member. The planted shapes of AC-6.5 use the fixture pattern the spec names, not nested classes (TASKS-COVER-010 b): this WP owns two new planted fixtures, `T/architecture/fixture/adapter/out/filesystem/codec/C12aPortOut.java` (a codec class that references an `application.query.port.out` interface such as `FrontmatterDecoder`) and `T/architecture/fixture/application/query/index/A12cUsesCodec.java` (an application class that references `WpFrontmatterCodec`), both disjoint from WP12's fixture names (`DetailController`, `R15Controller`, `MissionDetailQuery`, `R16*`, `StreamSpring`, `DetailValue`, `R15Deriver`), and makes a **named edit** of `T/architecture/ArchitectureControlsTest.java` (owned by WP03) that adds exactly two `Control` rows, `new Control(12, C12aPortOut.class, <red set>)` red on 12a and `new Control(12, A12cUsesCodec.class, <red set>)` red on 12c, the red sets pinned from a first run and reviewed (the style of the existing `C12aSafeFiles` and `G11cUsesCodec` rows). The edit is a pair of rows plus two imports and touches nothing else; WP12 edits the same file concurrently (rules 15 and 16), so the lane merged second rebases and re-reads it (serialised by merge order, as for the JaCoCo lines). Commit the two fixtures first and show each red against its rule before the control rows are added. (c) two owned tests (`T/adapter/out/filesystem/codec/LanesCodecRulesTest.java`, matching the owned glob `LanesCodec*Test.java`, and `T/application/query/index/WorkPackageIndexRulesTest.java`) run rule 12 and rules 4 and 7 over the **production** classes added here (`WpFrontmatterCodec`, `ReviewCycleCodec`, `LanesCodec`, `YamlFrontmatterDecoder`, `JsonLanesDecoder`, `WorkPackageIndex`) and require green plus a non-zero scanned count that includes them. Build the rule objects through `ArchitectureRules.all(root, rule9Packages)` as `ArchitectureControlsTest#fixtureRules` does, or the public rule accessor of the re-cut `ArchitectureRules` (read it at the lane tip); do **not** edit `ArchitectureRules` or `ArchitectureRulesTest`; the only edit of `ArchitectureControlsTest` is the two-row named edit above. The text of every existing rule stays unchanged.
2. `WorkPackageIndexLocaleTest` (the stub leg of AC-6.6): `NameEncoding` stub with `trustworthy=false`: the three-route behaviour is represented at the index level as the refusal fault; the three-route child-JVM leg is WP18's (`WorkPackageIndexLocaleProcessTest`) and is **not** created here.
3. The route stub cases of AC-6.6 for `getMission`, `getWorkPackage`, `getWorkPackageDetail` belong to WP13..WP15, not here.

**Files**: tests ~180 lines.

**Validation**: the three planted-violation tests are red when the planted class is present and the rule is the one they target; production classes are green.

### Subtask T079: JaCoCo counts and (only if proven) the native hint

**Steps**:
1. After `./gradlew --no-daemon test jacocoTestReport`, run the plan section 2 command (`python3 -c "import re;x=open('build/reports/jacoco/test/jacocoTestReport.xml',encoding='utf-8').read();[print(k,len(re.findall('<class name=\"org/speckitty/missionstatus/'+k+'/',x))) for k in ('domain','application')]"` from `S`) and write the two numbers into `R/jacoco-class-floor.properties` (named edit; WP01 owns the file). Count at the adding commit. WP12 runs concurrently and merges AFTER this WP (wps.yaml OO-6), so the count you write is true for this lane only; it is NOT the PR A claim. The equality at PR A's merged tip is owned by WP12 T088 (the last PR A work package to merge). If, against OO-6, WP12 was merged first, rebase, re-run the command on the merged tree and write what it prints in a named-edit commit of its own (D-145).
2. If and only if the local native run (T075 step 5) or CI at PR A's tip proves a missing reflection hint for the decoder beans, add it to `J/config/MissionStatusApplicationHints.java` as a named edit and state the proof in the commit message.
3. Every new class meets 0.90 per-class line coverage: add focused tests for uncovered branches (do not lower anything).

**Validation**: `./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck` green.

### Subtask T080: Gate

**Steps** (`export LC_ALL=C.UTF-8`; stage new files with `git add` before Gate P):
1. **Gate G**: `cd services/mission-status-api && ./gradlew --no-daemon test jacocoTestCoverageVerification jacocoScopeCheck`.
2. **Gate P**: `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py -q`.
   NFR-006 terminology grep (plan section 5; expect empty): `grep -rnE '(^|[^A-Za-z])[Ff]eatures?([^A-Za-z]|$)|feature_' services/mission-status-api/src/main services/mission-status-api/README.md` (the one marked legacy literal `feature_slug` of D-115, if present, is the only allowed hit).
3. AC-6.1 to AC-6.5 (corpus `wpm-01..28` against the oracle outcome classes), the stub leg of AC-6.6, AC-6.5's planted violations.
4. **PR A native evidence before review (E-7)**: `./gradlew --no-daemon check` is allowed locally; at minimum `./gradlew --no-daemon nativeCompile nativeTest` then `nativeSmoke -PnativeBinary=<binary>` so PR A is green on every CI leg alone. CI remains the authority; a local red is classified under plan section 6, never retried to green.
5. Append tracer entries (the YAML spike result; D-97 outcome) and commit; state the named edits in the commit message.

## Self-contained green

- **Fixtures with tests.** The `wpm-01..28` and duplicate fixtures are WP07's committed trees, read through `ConformanceTree`; cases 22/23 and non-ASCII names are generated at test time through WP10's helpers; no fixture is added by this WP. Nothing is compared against a golden that a later WP generates.
- **Floors and counts satisfiable here.** The `application`/`domain` count lines carry exactly the classes of WP01..WP11 at this commit (true for this lane; the PR A tip recount is WP12 T088's, D-145, OO-6); `DEFINED_RULE_COUNT` is untouched by this WP (WP12 sets 16); the native floor (3) and `requests.json` (49) are untouched because no `@Tag("native")` test and no smoke stage is added.
- **No forward reference.** No test or gate names a WP12..WP18 type: no `MissionDetailQuery`, `DetailRefusal`, `AdmissionGate`, route service, controller or served-route provider. The route-service stub cases (AC-6.6) are WP13..WP15's; `WorkPackageIndexLocaleProcessTest` is WP18's.
- **Pin `tests/ci/test_mission_status_api_build.py`.** Kept green: tracked-path scan over `S`, the probe list for new files under `application/query/port/out`, the rule-9 literals untouched, no new `adapter/in/http` directory.
- **Mission record.** `M/research.md` gains an append-only section (named edit); `M/meta.json` untouched; `M/status.json` is the `materialize`d snapshot of `status.events.jsonl`, never hand-edited (compare with the coordination copy before committing any status file), so cutover-guard, the mission-state audit (`spec-kitty doctor mission-state --audit --fail-on teamspace-blocker --json`, run before pushing any `M/**` change) and corpus-blocking pass.

## Plan defects found

- **Spec/plan numbering.** Folded in commit 462bb3c63: the spec now reads 28 cases / `wp-malformed-frontmatter` (28) (S-19, `wpm-28`).
- **Resolved (TASKS-COVER-010 b): AC-6.5 planted controls have an owned home.** Spec AC-6.5 wants a planted codec class that references an `application.query.port.out` interface (red on 12a) and a planted application class that references the codec (red on 12c); wps.yaml now gives WP11 the two fixture paths `T/architecture/fixture/adapter/out/filesystem/codec/C12aPortOut.java` and `T/architecture/fixture/application/query/index/A12cUsesCodec.java` and lists the two-row named edit of `ArchitectureControlsTest` (T078), following the existing `C12aSafeFiles`/`G11cUsesCodec` pattern. (The plan's shared-file table names no P6 edit of that file; this is a recorded deviation for the orchestrator.)
- **WP11 and WP12 both edit the two JaCoCo count lines concurrently** (plan acknowledges it, D-145); the instructions above implement the rule: this lane's recount is lane-local and WP12 T088 owns the equality at PR A's merged tip. No unsatisfiable floor found.
- **`MissionStatusApplicationHints` is a named edit for both WP11 and WP12 and owned by WP17 (PR B)**; if both prove a miss, merge order serialises them. Stated, not a defect.

## Definition of Done

- T073..T080 recorded with `spec-kitty agent tasks mark-status <Txxx> --status done --mission mission-status-read-api-mission-detail-01M4S6D5`.
- `WorkPackageIndex` returns the oracle outcome class for each of `wpm-01..28` and the duplicate fixtures; first valid in byte order wins; `IndexedWorkPackage` has no body component; one `WP_FILE` READ per candidate.
- `FrontmatterDecoder`/`LanesDecoder` are interfaces-only ports; implementing classes sit directly in `adapter.out.filesystem` and delegate to the codec; ArchUnit rules 4, 7, 12a-12c pass, planted violations red.
- The `M/research.md` YAML parity section is appended, or the E-6 escalation is raised.
- `jacoco-class-floor.properties` counts equal the command's output at the adding commit.
- The NFR-006 terminology grep (T080 step 2) is empty (or only the marked legacy literal); the two AC-6.5 fixtures are shown red against 12a and 12c before the control rows were added;
- Gate G, Gate P and the local native evidence (E-7) are green; only `owned_files` and the named edits changed.

## Risks

- **YAML dialect divergence** (snakeyaml 1.1 vs ruamel 1.2: `yes`/`on`, octal-looking ints, timestamps): refuse-what-you-cannot-decode, corpus plus the nightly all-file comparison (WP18/WP17) decide; E-6 if a dependency would be needed.
- **Silent omission or partial index** under a non-UTF-8 locale: the stub leg and the process leg (WP18) guard it.
- **Memory**: a second buffer for the body breaks NFR-002; hold one buffer at a time.
- **Native image**: new beans at start-up; prove locally before review.
- **Concurrent JaCoCo recount** with WP12.

## Reviewer Guidance

- Compare each of the 28 fixtures' stored oracle outcome with the Java outcome; confirm a mutated decoder (lenient decode, case-folded sort, second-wins) turns a named test red.
- Confirm the layering: grep for `adapter.out.filesystem.codec` imports in `application..` (none), and that the implementing classes sit directly in `adapter.out.filesystem`.
- Confirm no `body` component in `IndexedWorkPackage` and a single read per file.
- Confirm no new dependency in `S/build.gradle.kts`, the version catalog or `gradle/verification-metadata.xml`.
- Confirm the `research.md` section is append-only and records the sha the spike ran on; confirm the commit messages state each named edit.
- Run the implicated architectural gates (`ArchitectureRulesTest`, `ArchitectureControlsTest`, `PortLevelClassSetTest`) and the pin.

## Implementation command

```bash
spec-kitty agent action implement WP11 --agent claude --mission mission-status-read-api-mission-detail-01M4S6D5
```
