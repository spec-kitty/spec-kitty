---
work_package_id: WP12
title: 'Phase 5a: native smoke replay (stage base), per-leg digests, gate digest comparison'
dependencies:
- WP20
requirement_refs:
- FR-015
- FR-010
- FR-008
- NFR-005
- SC-004
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T064
- T065
- T066
- T067
- T068
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/test/
create_intent:
- .github/workflows/mission-status-api.yml
- tests/ci/test_mission_status_api_build.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/mission-status-api.yml
- tests/ci/test_mission_status_api_build.py
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/nativesmoke/**
- services/mission-status-api/src/test/resources/nativesmoke/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/skeleton/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/skeleton/**
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP12 - Phase 5a: native smoke replay, per-leg digests, gate digest comparison

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Replace the phase 1 skeleton `nativesmoke.NativeSmokeTest` with the real smoke replay, delete the skeleton hello route (and what is left of the skeleton packages) in the SAME commit that retires its last assertion, so the four native legs never see a moment where the smoke asserts a route that no longer exists: start the native binary over copies of the curated fixture trees, replay a literal request set (stage `base`), compare every body byte-for-byte with its golden through `CanonicalJson`, check refusal statuses and Problem codes, run an append-while-open SSE round trip, write the per-leg digest file, and wire the cross-leg digest comparison into the gate job.

## Context

- Plan phase 5, first part (plan.md section 11 row 5 "Dependencies" and AC-15 test-strategy rows, section 12 native release matrix and the digest definition). Spec FR-015 (AC-15b, AC-15c, AC-15e), NFR-005, SC-004, FR-008.
- Depends on WP20 (routes incl. the SSE stream, wiring, real adapter; hence WP10/WP09/WP19/WP08/WP07 transitively). It does NOT need WP11: stage `hostOrigin` of the request set is added by WP16 once the filter exists. AC-15b and AC-15e are NOT met for the Mission until stage `hostOrigin` is added; the Mission is not accepted on them without it.
- The gate helper `scripts/ci/mission_status_gate_checks.py` (both subcommands) and its tests were delivered by WP04; this WP does not edit them (not in the owned list). It only invokes `digests` from the workflow and produces the digest files the helper checks.
- Chokepoints edited in dependency order: `.github/workflows/mission-status-api.yml` (WP04 created; append, do not restructure), `tests/ci/test_mission_status_api_build.py` (append a `# --- WP12 ---` section). The `nativesmoke` test package is WP03's skeleton, replaced here (PLAN-NEW5-001, ordering-based); WP13 and WP16 add to it later.
- `CanonicalJson` (WP09) is the ONLY comparison code, shared with the JVM golden suite, so a native-only formatting difference is not misread as a reflection problem and the two suites cannot disagree.
- The native test image cannot run this; the smoke runs against the built binary through the Gradle `nativeSmoke` task (WP03 registered it, requires `-PnativeBinary=<path>`).
- Public repo: the harness passes only temp paths it creates; no absolute path in `requests.json`, digest files or logs.
- **This WP is where the skeleton leaves.** `adapter/in/http/skeleton/**` (the hello controller, kept by WP10/WP20 because the skeleton `NativeSmokeTest` and the WP04 native legs assert `GET /api/v1/hello`) and `src/test/.../skeleton/**` are owned here for exactly that deletion (T065 step 8). The skeleton contract-document route and its test were already replaced by WP10.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. The workflow and the build test are created by WP04 and WP03, amended here (and the README is created by WP19 for WP16). This WP creates: `requests.json` and the real replay classes.

## Subtask T064: `requests.json` (stage `base`) and the group model

**Purpose**: The literal, replayable oracle.

**Steps** (design the format first; the harness reads it, the pins parse it):
1. `src/test/resources/nativesmoke/requests.json`: `{ "stages": { "base": { "requestCountFloor": N }, "hostOrigin": { "requestCountFloor": M } }, "groups": [ { "stage": "base", "tree": "<fixture tree id from manifest.json>", "requests": [ {id, method, path, headers?, expectedStatus, expectedGolden?, expectedProblemCode?, expectedContentType?} ] } ] }`. Each distinct project tree = one binary start (a whole-read refusal row needs its own tree: a torn ledger makes `/missions` and `/project` refuse for every Mission, so it cannot share a tree with golden-backed requests). The digest covers the concatenated bodies of all groups in file order.
2. Stage `base` contents (every expected status and Problem `code` is a LITERAL in this file): golden-backed requests over the curated golden set including the `crlf-and-listing` and `secret-canaries` fixtures; one request per refusal code: `invalid_page_cursor` (400), the five stream refusal codes (`negative`, `misaligned`, `cursor_without_mission` => 400; `out_of_range`, `content_mismatch` => 409), the unknown-Mission 404, a row L3a 500 (`/api/v1/project`), a row L3b 500 (`/api/v1/missions`), a row L4b 500; plus the contract document request (bytes equal the bundle). Stage `hostOrigin` entries are added by WP16, not here; the file already declares both stages with `requestCountFloor` for `base` only recorded (WP16 raises it).
3. Trees come from the committed conformance tree (WP07) by id; the harness copies them to temp dirs (and runs WP09's project-header materialisation), so no new fixture data is needed except small whole-read-refusal trees if WP07's classes do not contain one: reuse `torn-final-line` and `malformed-rows` fixtures.
4. Windows-illegal characters are forbidden in every path; ids are plain ASCII slugs.

**Files**: `requests.json` (~200 lines of data).
**Validation**: parsed by a unit test (schema, unique ids, every golden path exists, every tree id exists in the manifest).

## Subtask T065: `NativeSmokeTest` replay harness (red-first)

**Purpose**: AC-15b.

**Steps**:
1. Red first: the test with an empty request set must FAIL on the request-count floor before any request logic exists.
2. The harness starts `<binary> --mission-status.project-root=<temp copy> --mission-status.port=<free port the test picks>` per group, waits for readiness (poll `GET /api/v1/project` with the accepted `Host: 127.0.0.1:<port>`, a bound of 30 s; NFR-002 timing is WP13), replays each request with the literal headers, compares status and Problem `code`, and compares each 2xx RAW response body (bytes as received, not parsed and re-serialised) with its golden bytes through `CanonicalJson.assertBodyEqualsGolden` (the parsed tree is used only to build diff messages). It stops the process in a `finally` and fails if the process died early (print only its exit code and a path-free tail of its log).
3. SSE round trip: open a Mission-scoped stream, append one valid `status-transition` row to the temp ledger, require exactly one event with the expected `id:` within the provisional 2 s bound (classify a miss under ADR `2026-10-05-2`, never retry). Also record the frame text into the digest body stream.
4. Failure-on-empty guards: zero requests replayed or zero bodies compared fails; fewer than the stage floor fails.
5. AC-10c native-leg half (a sample, weaker than the JVM JFR proof, and the AC says so): sample the number of child processes of the service process before and after the replay (Linux: the children listed under `/proc/<pid>/task/*/children`; macOS `pgrep -P`; Windows a process-tree query from TEST code) and require them equal; where an OS cannot sample, record "not measurable on this leg" in the job summary, never a silent skip.
6. AC-15b perturbation controls, each observed red once in a scratch copy (record in the PR "Tests run"): one body byte of one golden changed; one `expectedStatus` changed; one `expectedProblemCode` changed; an empty/glob-less `requests.json`.
7. The harness uses no Spring and no network except loopback; it must run on Windows (`.exe`, `ProcessBuilder` is fine in TEST code: ArchUnit rule 10 scans main only).
8. Retire the skeleton in the same commit as the first green replay: delete `adapter/in/http/skeleton/**` (the hello route), the remaining `src/test/.../skeleton/**` classes and the skeleton assertions of `NativeSmokeTest` (the tagged class is now the real replay, still tagged `native-binary`). Check that nothing else references the hello route (`grep -rn "api/v1/hello" services/mission-status-api tests/ci .github` must be empty); the native legs of the workflow keep calling `nativeSmoke`, which now runs the real replay. Revert: re-add a request to `/api/v1/hello` in a scratch `requests.json` => the replay is red (404 against a literal expectation).

**Files**: `nativesmoke/NativeSmokeTest*`, helpers (~450 lines).
**Validation**: on this workstation (Linux x64, the WP02 toolchain gate): `cd services/mission-status-api && ./gradlew nativeCompile && ./gradlew nativeSmoke -PnativeBinary=build/native/nativeCompile/mission-status-api` (the class is tagged `native-binary` and excluded from `check`, so it is run through this task); the other three legs are WP04's CI proof, stated as owed.

## Subtask T066: Per-leg digest file

**Purpose**: AC-15e producer side.

**Steps**:
1. After a green replay write `digest-<os>-<arch>.json` = `{os, arch, requestCount, bodyCount, sha256}` where `sha256` is the SHA-256 of the concatenated RAW response bodies (the bytes as received, never a parsed and re-serialised form) ONLY (never os or arch; SSE frames and refusals included), `os`/`arch` normalised to exactly `linux-x64`-style tokens (`linux`/`macos`/`windows` and `x64`/`arm64`) so the file names are `digest-linux-x64.json`, `digest-linux-arm64.json`, `digest-macos-arm64.json`, `digest-windows-x64.json`.
2. Output directory is a build directory (`build/nativesmoke/`), never the source tree.
3. Unit tests (JVM, no binary needed): the digest of two identical body lists is equal; reorder or alter one byte and it differs; os/arch do not enter the hash; a fractional/Unicode body round-trips. These tests also prove the file's keys match what `mission_status_gate_checks.py digests` expects (parse a sample with the Python helper in the pin test of T067).

**Files**: `nativesmoke/Digest*` (~120 lines), tests (~150).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.nativesmoke.*'` (this runs only the UNTAGGED JVM-side classes of the package, the digest unit tests and the `requests.json` parse test; `NativeSmokeTest` is excluded from `test` by its `native-binary` tag and runs through `nativeSmoke`).

## Subtask T067: Workflow wiring: digest upload, gate `digests` step, floors, pins

**Purpose**: Cross-OS determinism check (AC-15e) and the final native-leg shape.

**Steps**:
1. In each native leg: after `nativeSmoke`, upload `digest-<os>-<arch>.json` (artifact name `digest-<os>-<arch>`, 30 days, `if-no-files-found: error`). Update the `native-tag-floor --floor` argument to the count WP20 recorded (the floor only rises).
2. In `mission-status-api-gate`: download all `digest-*` artifacts (`merge-multiple`), then run `python scripts/ci/mission_status_gate_checks.py digests --dir <dir> --expected-count 4 --request-floor <N>`; fails unless exactly four files, equal `requestCount` at or above the floor, equal `sha256`; prints the four digests on failure. N equals the sum of the `requestCountFloor` of the stages present in `requests.json`.
3. Pins appended to `tests/ci/test_mission_status_api_build.py`: the gate downloads digests and calls `digests` with `--expected-count 4`; the `--request-floor` value equals the `requests.json` floor; each native leg uploads its digest with the exact name; the smoke step uses the same `-PnativeBinary` the compile step produced. Revert rows: drop the digest upload, change the floor, remove the `digests` step: each red.
4. Run the planted-digest tests of WP04 (`tests/ci/test_mission_status_gate_checks.py`) unchanged: `.venv/bin/python -m pytest tests/ci/test_mission_status_gate_checks.py tests/ci/test_mission_status_api_build.py tests/ci/test_fork_guard.py -q`.

**Files**: workflow (edit), pins (~120 lines appended).
**Validation**: the pytest command above; YAML parses.

## Subtask T068: Local proof, CI hand-off and evidence

**Purpose**: State exactly what is proven where.

**Steps**:
1. Build the Linux x64 binary on this workstation (the toolchain precondition guarantees it), run the smoke, write the digest; paste counts (requests replayed, bodies compared) into the PR notes. Run the controls of T065 once.
2. Hand-off to the orchestrator: the four-leg proof needs a pushed branch/PR run (and one `workflow_dispatch`); list the artifacts to inspect (`digest-*`, binaries `.sha256`). Do not claim AC-15c/15e as met until that run exists.
3. Record friction (e.g. timing, flakiness classification) in `traces/tooling-friction.md`; append design decisions (the group model, why trees are restarted per group).

**Validation**: evidence recorded; nothing claimed beyond what ran.

## Definition of Done

- `NativeSmokeTest` replays the `base` stage with literal expectations, compares raw body bytes with the golden bytes through `CanonicalJson`, runs the SSE round trip, writes `digest-<os>-<arch>.json`; zero-request/zero-body/under-floor all fail; AC-15b controls observed red.
- Workflow uploads the digest per leg and the gate compares four digests via the existing helper; pins green with revert rows.
- The skeleton hello route, the skeleton tests and the skeleton assertions are gone, replaced by the real replay in one commit; `grep` finds no `api/v1/hello` reference.
- `cd services/mission-status-api && ./gradlew check` stays green (the `native-binary` classes are excluded from it).
- AC-15b/15e remain open until stage `hostOrigin` (WP16) and the CI run are in; this is stated in the hand-off.

## Risks

- A body that differs only on one OS (line endings, path separators, ordering): the digest comparison is exactly the detector; fix the cause in the service, never normalise.
- Native-only failures (missing hints): the fix goes back to the `META-INF/native-image/**` files that WP10 and WP20 own, as a justified out-of-map edit (not owned here).
- Windows `.exe` and process-tree termination in the harness: test on the Windows leg first.

## Reviewer Guidance

- Check every expectation in `requests.json` is a literal and each perturbation turns the smoke red.
- Check the digest excludes os/arch and covers refusals and SSE frames.
- Check the gate's `--request-floor` is tied to the file.

## Implementation command

`spec-kitty agent action implement WP12 --agent claude`
