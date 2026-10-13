---
work_package_id: WP19
title: 'Phase 3a-2: FilesystemMissionEventSource, flow-level allowlist checks and README stub'
dependencies:
- WP08
requirement_refs:
- FR-004
- FR-007
- FR-010
- FR-016
- C-005
- NFR-008
- NFR-003
- SC-006
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T046
- T047
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/
create_intent:
- services/mission-status-api/README.md
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/out/filesystem/FilesystemMissionEventSource*
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/out/filesystem/**
- services/mission-status-api/README.md
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP19 - Phase 3a-2: FilesystemMissionEventSource and README stub

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Implement `FilesystemMissionEventSource` (the production `MissionEventSource`, composing WP08's resolver, `SafeFiles`, allowlist seam and `Listing` with WP17's `LedgerLineDecoder`), the flow-level allowlist, read-only and drain-independence checks that need it, and the service README stub carrying the allowlist fenced list with its parity test.

## Context

- Plan phase 3 (the adapter half). Plan sections 7 (Q-3, no git), 11 row 3, 13 (layout, "Cache probe versus read", ArchUnit rules 4, 7, 10, 12), data-model.md "Ports". Spec FR-004 (L-rows at the adapter), FR-006, FR-007 (AC-7c/7d), FR-010 (AC-10a, AC-10b, AC-10e), FR-016 (AC-16a..16d), C-005, NFR-003, SC-006.
- Depends on WP08 (the primitives) and through it WP18, WP06 and WP17. Concurrent with WP07 (Python oracle): no shared files; build tree fixtures in temporary directories inside the tests (WP07's fixtures may not exist yet). WP09 later runs the goldens against this adapter.
- `ProjectRootCheck*` was created by WP03 and is not edited here unless a defect is found (then an out-of-map edit, because the file belongs to WP03, with a one-line rationale, in its own commit).
- This adapter family is the ONLY code that touches `java.io`/`java.nio.file` file APIs (rule 7; the `codec` sub-package is excluded and has none). It starts no process and writes nothing (FR-016, AC-10c static rule 10).
- The service reads NO git: path decision is by directory existence and the stored topology only (FR-006; plan Q-3 interim). Do not read `.git/worktrees`, `packed-refs` or `refs/`. The one `.git` exception: `.git/HEAD`, or a `.git` pointer file with a `gitdir:` line and the single file `HEAD` of the directory it names.
- README: created here as a stub with ONLY the allowlist fenced list and the terms list heading; WP16 extends it (sequential). Terms rule (NFR-008): use Mission, Work Package, Lane, Tail cursor, `log_truncated` (glossary); "reducer", "status event", `Diagnostic`, "overview read model", "conformance golden" are code identifiers defined in the README's own short terms list the first time they are used and are never presented as glossary terms.
- Public repo: tests build trees under JUnit temp dirs; no absolute home paths in sources, README or messages; fault injection never prints paths.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.

## Subtask T046: `FilesystemMissionEventSource` (stamp, read, window, tear classification)

**Purpose**: The production `MissionEventSource`.

**Steps**:
00. Adapter test harness (before steps 4, 5 and 8): the tests of those steps need a `MissionStatusQuery` over the REAL adapter, but `FilesystemFixtureFactory` is created later (WP09 T048). Create a package-local helper `AdapterServiceHarness` in the test package `adapter.out.filesystem` (inside this WP's owned test glob; no `testsupport` path is touched) that builds the real `MissionStatusService` over `FilesystemMissionEventSource` (with the recording `AllowlistAccess` of step 0) using a fixed `Clock`, a recording `Consumer<Diagnostic>` and a deterministic scheduled executor, and returns the `MissionStatusQuery` plus the recorder, clock and executor handles. Reuse the WP06 `testsupport` types (`FixtureHandles`, the deterministic executor and recording consumer) rather than re-implementing them; if a WP06 type has no accessible constructor, use a minimal local equivalent and do not edit `testsupport`. WP09 `FilesystemFixtureFactory` later supersedes this helper for the golden and HTTP legs; the helper stays for the adapter-level cases.
0. Constructors: a public constructor taking the root, the `Allowlist` and an `AllowlistAccess` (WP08 T044 step 2: the recording seam must be settable from `testsupport`), and the production constructor that delegates with the pass-through; `ServiceWiring` (WP10) uses the production one.
1. `projectInputs()`: reads `.kittify/config.yaml` (`project.slug` only), `.kittify/metadata.yaml` (`spec_kitty.version`, `spec_kitty.schema_version`), `HEAD` (no process) with the `.git` pointer-file rule; a missing/unreadable `metadata.yaml` yields null version/schema (the application derives health); a pointer naming a missing or unreadable `HEAD` gives a null branch. YAML parsing: use the library WP02 T004 step 9 selected and WP03 declared (do not add another); read ONLY the keys listed.
2. `listMissions()` via `Listing`; `readMeta(ref)` reads the OWN primary `meta.json` (invalid JSON, not an object, empty, non-UTF-8 or OS-unreadable => the single L7 outcome; the application maps it to `meta_unparseable`).
3. `stampLedger(ref)`: stat (size, mtime, file key) plus a bounded read of the final physical line; returns the opaque `LedgerStamp` with value equality over (size, mtime, file key, terminated length, SHA-256 of the last terminated line). `readLedger(ref, stamp)`: full decode through `LedgerLineDecoder`, the read-directory class, and the tail classification (`none`/`whitespace`/`non_whitespace`). `readLedgerFrom(ref, offset)`: decoded lines from the offset, the SHA-256 of the line ending at the offset, the current size and whether the offset is line-aligned.
4. Torn-tail bytes written by a concurrent writer (AC-4d): the latch-controlled part (half a row, then the whole row without newline, then the newline) and the free-running part (>= 200 reads while a writer appends valid rows; every observed 200 result matches ONE prefix of complete lines of the final log in all four fields `eventCount`, `statusLaneCounts`, `lastEventId` and `streamCursor`, and the latch part observes the L4 and the L4b refusal as separate reads and then the result of the new prefix) are tested at the adapter through `AdapterServiceHarness` (`MissionStatusQuery` over the real adapter, because the four fields are application-derived) here, in test class `FilesystemMissionEventSourceTornTailTest`; the HTTP legs of AC-4d are WP10 T053 step 9 (`TornTailConcurrencyHttpTest`).
5. AC-7c/AC-7d adapter tests (through `AdapterServiceHarness`, test class `FilesystemMissionEventSourceStampTest`): equal-length rewrites (last line only; middle line only with mtime advanced => served fresh; middle line with the mtime restored => served stale and no `log_truncated`, named as the documented limit).
6. CRLF: the raw line keeps `\r` for position and digest.
7. Run the L1..L11 rows through the REAL adapter as well, including the Java-only rows L2, L7 (OS-unreadable), L9, L11 by fault injection (AC-4a port legs: the L2/L6/L7/L9/L11 legs are adapter-suite tests).
8. Flow-level checks under WP08's recording seam (`RecordingAllowlistAccess`, moved here from WP08 T044 because they need this source; test class `FilesystemMissionEventSourceAllowlistFlowTest`, using `AdapterServiceHarness`): AC-10a - the full fixture flow (all three routes through `MissionStatusQuery` over the real adapter here; the HTTP flow is re-run in WP20) under the recorder fails on any path outside the allowlist or read from the wrong directory (coordination `meta.json`, primary ledger of a coord Mission); positive controls (scratch edits, each observed red once): add a deliberate read of `tasks/WP01.md`, and separately of the coordination `meta.json`. AC-16a: the recorder fails on any non-read-only open; control: add one write in a scratch edit => red. AC-16c: with `hosted.drain` true in `.kittify/config.yaml` and a personal `config.toml` (test-only path) vs false vs absent, responses are byte-identical and the recorder shows NO read of `config.toml`. AC-16b: fingerprint of the fixture project (content hash, directory listing names/counts incl. lock/temp names, mtimes) identical before and after. AC-16d: read-only directory run where the platform enforces it (non-root Linux), recording on other legs that it did not run.

**Files**: `FilesystemMissionEventSource*` (~450 lines), `AdapterServiceHarness` (~120, test), tests (~700, in test package `adapter.out.filesystem`). Every T046 test class name starts with `FilesystemMissionEventSource` (so the Validation filter selects it); `AdapterServiceHarness` is a helper, not a test class.
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.out.filesystem.FilesystemMissionEventSource*'` and then `./gradlew check` (green with the JaCoCo rule; adapters are excluded from the threshold).

## Subtask T047: README stub with the allowlist fenced list and the terms list

**Purpose**: AC-10b and NFR-008, ready for WP16 to extend.

**Steps**:
1. Create `services/mission-status-api/README.md` with: a one-paragraph purpose, a "Read allowlist" section containing ONE fenced list (parsed by the AC-10b test: one path pattern per line, exactly the constant's entries), and a short "Terms" list defining the code identifiers it uses (reducer, status event, `Diagnostic`, overview read model, conformance golden) as code terms, not glossary terms. No docs claims about running or releasing yet (WP16).
2. No absolute paths, no version numbers, Mission/Work Package vocabulary only; the README lives outside the docs spelling scope but write it as if inside.
3. The AC-10b parity test (`AllowlistReadmeParityTest`, in test package `adapter.out.filesystem`): the `Allowlist` constant (WP08) equals the README's fenced allowlist list, entry for entry and in order; a test parses the fence.
4. Revert-fails: add a file to the constant without the README and the AC-10b test is red; and the reverse.

**Files**: `README.md` (new, ~60 lines), the parity test (~60 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.out.filesystem.AllowlistReadmeParityTest'` green.

## Definition of Done

- `FilesystemMissionEventSource` implemented test-first; all L-rows at the adapter, the AC-7c/7d rewrite cases, the torn-tail latch and free-running cases, CRLF handling, and the flow-level AC-10a, AC-16a..16d checks pass; every positive control was observed red once.
- `cd services/mission-status-api && ./gradlew check` is GREEN at this tip; the adapter family is the only file-API user (rule 7 passes); no process started; no write opened.
- README stub with the allowlist fence present and equal to the constant (parity test green).
- Native legs stay green at this tip (nothing here touches the hello route).
- Tracer entries appended (any Python-parity decision in `meta.json`/YAML reading).

## Risks

- mtime resolution differences across file systems affect AC-7c/7d: assert the documented behaviour, never sleep-to-green; use explicit `setLastModifiedTime`.
- Real-corpus behaviours not in fixtures show up only in the nightly (WP14); do not widen the allowlist to chase them.
- Size: about 1,200 lines with tests; the primitives are WP08.

## Reviewer Guidance

- Check there is no read outside the allowlist and no `.git` registry/ref read; check the controls.
- Check the `stampLedger` cost is one stat and one bounded tail read per Mission.
- Check the README fence equals the constant and the terms are code terms.

## Implementation command

`spec-kitty agent action implement WP19 --agent claude`
