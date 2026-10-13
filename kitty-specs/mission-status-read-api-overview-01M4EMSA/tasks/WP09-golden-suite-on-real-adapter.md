---
work_package_id: WP09
title: 'Phase 3b: golden suite on the real adapter, second leg of the port-level subset, FR-013 floor'
dependencies:
- WP07
- WP19
requirement_refs:
- FR-008
- FR-013
- FR-001
- FR-002
- FR-005
- FR-006
- NFR-005
- SC-001
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T048
- T049
- T050
- T051
- T052
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/conformance/golden/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/testsupport/**
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP09 - Phase 3b: golden suite on the real adapter, second leg, FR-013 floor

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Make Java prove it equals live Python: run the committed goldens through the real application service and the real filesystem adapter, run the port-level subset on BOTH sources, consume `resolver-cases.json`, `manifest.json` and `leak-patterns.json`, and meet the FR-013 id floor with the interim constant deleted.

## Context

- Plan phase 3, golden half (plan.md section 11 row 3 and "Parallelism ..."; the Mission directory's contracts/service-contract-notes.md (kitty-specs/mission-status-read-api-overview-01M4EMSA/contracts/, not the repository-root contracts/) "Comparison rule"; data-model.md; ArchUnit rule 11). Spec FR-008 (iii) (AC-8a, AC-8b Java side, AC-8d byte determinism), FR-013 (AC-13a, AC-13b), FR-001 (AC-1f), FR-006 (AC-6e), AC-9g (leak patterns), NFR-005, SC-001.
- Needs BOTH WP07 (goldens, manifest, `resolver-cases.json`, `leak-patterns.json`) and WP19 (the filesystem event source; WP08's primitives sit under it). `testsupport/**` was created by WP06, extended by WP18 and is extended here (sequential, both are ancestors). This WP edits ONLY `testsupport/**` and `conformance/golden/**`: the `conformance/port/**` classes and their AC-2a shells (WP18) are never touched, because every port-level class obtains its query from `testsupport.PortSourceSelector` and every AC-2a shell delegates to `testsupport.Ac2aGoldenHook`.
- Comparison rule: exact equality of the canonical serialisation of the ENTIRE response document; the ignore-list is one named EMPTY constant, asserted empty. Canonical form: sorted keys, compact separators, UTF-8 without ASCII escaping, produced by the Python golden writer. ONE test-support class, `CanonicalJson`, does every comparison here AND in `nativeSmoke` (WP12), so the two cannot disagree: create it here and make it independent of the production mapper. The comparison is on RAW bytes: the response body bytes exactly as received are compared with the golden file's bytes (the golden is the canonical form); the response is NEVER parsed and re-serialised before the comparison (that would weaken AC-15b/NFR-005 from raw to canonical byte equality; post-analyze ruling ANL-003). The parsed tree is used only to build a readable diff message after a byte mismatch.
- The Java fixture factory copies a committed static tree into a temporary directory and runs the SAME project-header materialisation as the Python side (a `HEAD` file installs to `.git/HEAD`; a `GITDIR_POINTER` file is written as the regular file `.git` with `gitdir-target/HEAD` left as copied; no git binary involved). It never provisions a git repository.
- `ServiceWiring` is WP10: here `FilesystemFixtureFactory` builds `LeakClasses` itself from the classpath `leak-patterns.json` (the file WP07 committed) so the projection class runs now.
- Rule 11: nothing in `..conformance.port..` imports an adapter; the launcher `conformance.golden.PortSubsetSecondLegTest` imports `testsupport` only, and `testsupport.FilesystemFixtureFactory` is the only new class that imports the real adapter.
- Public repo: copy fixtures into temp dirs; never print paths.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.

## Subtask T048: `CanonicalJson`, materialisation step, `FilesystemFixtureFactory`

**Purpose**: The shared plumbing.

**Steps** (test-first):
1. `testsupport.CanonicalJson`: `assertBodyEqualsGolden(byte[] actualRawBody, byte[] goldenBytes)` compares the two byte arrays for exact equality (no parsing on the pass path). Only when they differ does it parse both documents and re-serialise canonically (sorted keys, `,`/`:`, UTF-8 without escaping; number text preserved as parsed so a fractional `progress` renders like Python) to name the first differing member in the failure message; the parsed tree decides nothing. A unit test pins that a body equal as a document but different in bytes (key order, whitespace, `\u00e9` escape) FAILS the comparison. Unit tests against Python-written golden bytes: one non-ASCII string and one fractional `progress` value (the NFR-005 canonical-form pin; WP10 re-uses it against the production mapper). Revert: enable ASCII escaping or change double rendering and the test is red.
2. `testsupport.ProjectHeaderMaterialisation` (the shared step) and `FilesystemFixtureFactory` (copies the static tree, runs the step, builds `FilesystemMissionEventSource` + the real `MissionStatusService` with the leak-class value, returns `MissionStatusQuery` plus the source). The factory accepts an optional `AllowlistAccess` (WP19 T046 step 0) and exposes the `RecordingAllowlistAccess` it was given through `FixtureHandles` (extend `FixtureHandles`, which WP06 created, with a nullable recorder accessor), so the HTTP harness and WP20 can read recorded opens. Fixed `Clock`, recording diagnostics, deterministic executor as in WP06's `FixtureFactory` (`FixtureHandles`).
3. Assert the branch read from the materialised `.git/HEAD` equals the manifest `headText`-parsed branch for each project-header fixture.

**Files**: `testsupport/CanonicalJson`, `FilesystemFixtureFactory`, materialisation (~350 lines), tests (~250).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.testsupport.*'`.

## Subtask T049: The golden suite (AC-2a all classes, AC-8a comparator, AC-8b Java side)

**Purpose**: Java equals the goldens for every Python-parity fixture class.

**Steps**:
1. For every fixture of every `python-golden` class in `manifest.json`: materialise, call `project()` and `missions()` (page sizes as the golden records), serialise the application result to bytes with the test-side serialiser, then call `CanonicalJson.assertBodyEqualsGolden(bytes, goldenBytes)` against the committed golden file (`golden/*.json`); WP10 repeats this over the production mapper's raw HTTP body. `javaOnly` classes are skipped by tag AND the test asserts the tag is present.
2. Discovered-count guards: fixtures and goldens counted against the manifest's per-class floor (zero matches fails); the test lists the class tags it exercised and requires them equal to the manifest's.
3. Knowns: `torn-final-line` (a) the unparseable fixture is refused with the L4 observable (`ledger_torn_tail` on `project()` and `missions()`), (b) the unterminated-but-valid-JSON fixture is tagged `knownDivergence`: assert the Java side REFUSES it with the L4b observable instead of matching the golden; `projection` class: the non-nullable strict token-shaped case answers `MissionStatusUnavailable(projection_refused)` (the golden records the oracle's refusal); `malformed-rows`: each variant's Java outcome maps to the code the golden's Python exception class implies (`StoreError`/`DiaryError`/`UnicodeDecodeError`/`ValueError` => `ledger_unparseable` / `meta_unparseable`).
4. AC-8a (1) comparator test: for EVERY member of `MissionOverview` and `Project`, copy a passing actual document, mutate that one member, and require the comparator to report a difference NAMING the member (a comparator ignoring `lastActivityAt` or reordering silently fails here). AC-8a (2) ordering perturbation (runs once, against the filesystem-backed source, red by construction, NOT in the dual-source subset): inject the wrong `EventOrdering` (sort by `at` only) and require the conformance suite red on the `interleaved` class.
5. The ignore-list constant exists, is empty, and a test asserts it.
6. The suite must pass on all four OS legs: no `\n` assumptions in paths; CRLF fixtures stay CRLF (WP07's `.gitattributes` line).

**Files**: `conformance/golden/*` (~600 lines).
**Validation**: `./gradlew test --tests 'org.speckitty.missionstatus.conformance.golden.*'`.

## Subtask T050: Manifest, supported range, resolver cases, leak patterns (AC-1f, AC-6e, AC-9g)

**Purpose**: The data files consumed by both languages stay coupled.

**Steps**:
1. AC-1f: `SupportedSchemaRange` (domain constant, WP05) equals `manifest.json` `supportedSchemaMin`/`supportedSchemaMax`. Revert: change the constant and it is red.
2. AC-6e (Java half): every row of `conformance/resolver-cases.json` yields the expected read-directory class (`own`/`coord`) through `ReadDirResolver` on a materialised static tree; the executed id set EQUALS the file's ids AND `manifest.json` `resolverCaseIds`. Revert: remove one row from ONE language's input in a temp copy and the sibling suite goes red (do it once, record).
3. Each fixture's `readDirectoryClass` in the manifest equals the class the adapter chose (the Java test asserts the same class as live Python).
4. `leak-patterns.json`: its SHA-256 equals `manifest.json` `leakPatternsSha256`; for each pattern, probe strings with the Python verdicts: one Java test per pattern requires the same verdicts from `java.util.regex` (a pattern that behaves differently is red; raise it as a finding). Revert: remove one pattern from a scratch copy and the SHA check and the projection class are red.
5. `specKittyEventsVersion` is read for information only on the Java side (the Python test enforces equality with the installed package).

**Files**: `conformance/golden/*` (~350 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.conformance.golden.*'`.

## Subtask T051: The second leg of the port-level subset and the FR-013 floor (AC-13a/13b)

**Purpose**: The same port-level ids run on the filesystem source AND the in-memory source.

**Steps**:
1. `conformance.golden.PortSubsetSecondLegTest` launches the `..conformance.port..` classes with `testsupport.PortSourceSelector` pointed at `FilesystemFixtureFactory` (the launcher imports `testsupport` only; ArchUnit rule 11 stays true). Implement `testsupport.Ac2aGoldenHook` (the stub WP18 declared) over the committed fixture trees and goldens, so the AC-2a shells run on the selected source without any edit to `conformance/port/**`. Each run records the ids it executed and asserts the set EQUALS the ids of `portlevel-tests.txt`, and that the file holds at least the ids FR-013 names (recorded floor, so an emptied list fails); no listed test is skipped in either run; the second run executes as many ids as the first.
2. DELETE `INTERIM_GOLDEN_DEPENDENT_IDS`, the interim "minus constant" id check and its guard test from `testsupport` (all three live there, WP18 T034 step 0); add a reflection test asserting the constant no longer exists. The AC-2a members (classes `interleaved`, `lifecycle-only`, `no-ledger`, `log-truncated`, `crlf-and-listing`) now run on both sources.
3. Re-run the ArchUnit suite (WP18) including the rule 13b scan and its positive control; the scanned class set equals the classes named by the id list.
4. Revert-fails: empty `portlevel-tests.txt` (floor red); skip one id in the second leg (equality red); add an adapter import to a port-subset class (rule 11 red).

**Files**: `conformance/golden/PortSubsetSecondLegTest`, `testsupport` edits (~250 lines).
**Validation**: `./gradlew test --tests 'org.speckitty.missionstatus.conformance.*' --tests 'org.speckitty.missionstatus.architecture.*'`.

## Subtask T052: Phase 3 exit gate and evidence

**Purpose**: Close the Java core: "needs both 2a and 2b merged; goldens pass against the real adapter; the full id set is executed on both sources; the FR-013 floor is met".

**Steps**:
1. `cd services/mission-status-api && ./gradlew check` green (JaCoCo rule, ArchUnit, port-level on both sources, golden suite, adapter suites).
2. Run the Python golden test to confirm the committed goldens still equal live Python (cross-check, not a Java gate): `PWHEADLESS=1 .venv/bin/python -m pytest tests/contract/test_mission_status_conformance.py -m "corpus and not windows_ci" -q`.
3. Record counts (ids executed per leg, fixtures compared per class) for the PR "Tests run" section; append tracer entries (any Python/Java parity finding).
4. Any golden difference is a finding: fix the Java port; the golden is regenerated only by the Python script and only by WP07-owned process (report instead of editing).

**Validation**: all green; findings listed.

## Definition of Done

- Every `python-golden` fixture's golden equals Java's canonical output; `javaOnly` and `knownDivergence` handling asserted; the comparator and ordering perturbations observed red.
- `portlevel-tests.txt` ids executed on both sources and equal to the file; floor met; `INTERIM_GOLDEN_DEPENDENT_IDS` deleted with a reflection test.
- AC-1f, AC-6e, AC-9g (patterns) coupled to the manifest with revert rows observed red.
- `./gradlew check` green; no edit outside the two owned trees.

## Risks

- A Java/Python parity bug found late: the fix lands in the domain/codec (WP05/WP17/WP06 files, not owned here) as a justified out-of-map edit in its own commit; the golden never moves.
- Regex semantic differences between `re` and `java.util.regex`: probe tests are the guard; the nightly (WP14) catches the rest.
- Test runtime growth: keep fixtures small; no sleeps.

## Reviewer Guidance

- Check the comparison is whole-document byte equality of the canonical form with an empty ignore-list.
- Check the second leg really goes through the filesystem source and that the id-equality assertion cannot pass vacuously.
- Check `javaOnly`/`knownDivergence` fixtures are asserted, not skipped silently.

## Implementation command

`spec-kitty agent action implement WP09 --agent claude`
