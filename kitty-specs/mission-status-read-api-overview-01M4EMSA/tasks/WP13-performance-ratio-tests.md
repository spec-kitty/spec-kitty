---
work_package_id: WP13
title: 'Phase 5b: performance ratio tests (NFR-001, NFR-002, NFR-004)'
dependencies:
- WP12
requirement_refs:
- NFR-001
- NFR-002
- NFR-004
- NFR-005
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T069
- T070
- T071
- T072
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/test/java/org/speckitty/missionstatus/
create_intent:
- .github/workflows/mission-status-api.yml
- tests/ci/test_mission_status_api_build.py
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/mission-status-api.yml
- tests/ci/test_mission_status_api_build.py
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/perf/**
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/nativesmoke/**
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP13 - Phase 5b: performance ratio tests

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Assert NFR-001 (overview latency), NFR-002 (native start-up) and NFR-004 (memory and concurrency under 100 SSE connections) as runner-relative RATIO assertions with provisional absolute ceilings beside them, on the JVM leg and (where specified) on each native leg, so a regression is a failing test and a miss is classified under ADR `2026-10-05-2`, never retried to green.

## Context

- Plan section 11 test-strategy row "NFR-001/002/004" ("ratio assertions; a miss is classified under ADR `2026-10-05-2`, never retried") and the phase 5 row. Spec NFR-001, NFR-002, NFR-004, "Wall-clock bounds". ADR: `docs/adr/4.x/2026-10-05-2-runner-relative-performance-budgets.md` - read it first; follow its method exactly (floor sampled in the SAME run, ratio limit set from the first measurement, absolute figure as the ceiling beside it, miss classification: runner noise versus regression).
- Depends on WP12 (the `nativesmoke` package, the digest/CI wiring and the workflow's native-leg shape). Sequential with WP12, WP14, WP15 on `mission-status-api.yml` and `tests/ci/test_mission_status_api_build.py` (append a `# --- WP13 ---` section). Concurrent with WP11 (no shared files).
- The build script already registers (WP03 T012 step 8) the `nativePerf` task running `org.speckitty.missionstatus.nativesmoke.NativePerfTest` with `-PnativeBinary`, and the `perfTest` task that runs the JUnit tag `perf`; `check` depends on `perfTest` and the default `test` excludes both `perf` and `native-binary`. This WP supplies the classes (JVM perf classes tagged `@Tag("perf")`; `NativePerfTest` tagged `@Tag("native-binary")`) and the workflow step. NO build-script edit (if one is needed, raise a reviewed amendment to WP03's files and say why).
- All numbers are PROVISIONAL: NFR-001 warm p95 < 200 ms and cold first call < 5 s over >= 500 Missions; NFR-002 first request within 2 s of process start; NFR-004 over 100 SSE connections held 60 s while 10 rows are appended: platform threads +<= 16, JVM used heap +<= 64 MB after a forced GC, native RSS +<= 128 MB, reducer-invocation counter after 100 connections equals its value after one connection plus the appends' invocations, all 100 connections receive every forwarded append. They are amended by a measurement (amend the spec row), never by a retry.
- The warm-request design assumption (one stat + one bounded tail read per Mission, zero `readLedger` on a warm call) was measured in the WP02 record (`stampLedger` cost over 588 Missions); if that record flagged a risk to the 200 ms ceiling, start by reading it.
- Public repo: the 500-Mission fixture is generated at test time in a temp dir with synthetic ULIDs; nothing generated is committed.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- `create_intent` note: `finalize-tasks` checks every literal path in `owned_files` once, at planning time, when no later file exists yet, so this frontmatter also lists shared files that an EARLIER WP creates. The workflow and the build test are created by WP04 and WP03, amended here (and the README is created by WP19 for WP16). This WP creates: the `perf/` classes and the `NativePerfTest` body.

## Subtask T069: The 500-Mission fixture generator and the NFR-001 ratio test (JVM)

**Purpose**: Overview latency, warm and cold.

**Steps** (red-first: write the ratio assertion with an intentionally impossible limit, see it fail with a readable message, then set it from measurement):
1. A generator (test support in `perf/`) that writes >= 500 Missions (default 588, the corpus size on the planning checkout) with realistic ledgers (mixed lengths, several lanes, interleaved ids) into a temp project root. Deterministic seed.
2. Floor: the p95 of a no-op route of the same service over the same connection count (the contract-document route or a trivial controller already present: choose the cheapest existing route and name it). Measure in the SAME run, same connections, warm-up discarded (state warm-up counts).
3. Assertions: (a) warm `GET /api/v1/missions` p95 / floor p95 <= ratio R1 (set from the first measurement with headroom per the ADR; record the measurement and the rule used) and p95 < 200 ms ceiling; (b) cold first call / floor <= R2 and < 5 s ceiling; (c) after ONE appended event, the next call re-reduces ONE Mission only (reducer-invocation counter) and performs `stampLedger` for every Mission but `readLedger` for one; (d) warm call performs zero `readLedger` calls.
4. A miss prints the measured ratio, the ceiling, the floor and the run's thread/CPU hint, and fails once: no retry loop, no `@RepeatedTest` masking.
5. Revert-fails: disable the cache (key never equal) and (c)/(d) are red; add a 50 ms sleep in the route and the ratio is red.

**Files**: `perf/*` (~350 lines; the test class is `Nfr001OverviewLatencyTest`, the generator a plain helper class without test annotations).
**Validation**: `cd services/mission-status-api && ./gradlew perfTest --tests 'org.speckitty.missionstatus.perf.Nfr001*'` (the class carries `@Tag("perf")`, so it is NOT run by `test`; `check` runs it through `perfTest`).

## Subtask T070: NFR-004 on the JVM leg (100 SSE connections)

**Purpose**: Threads, heap, reducer counter, delivery.

**Steps**:
1. Open 100 unscoped SSE connections (real sockets, virtual-thread clients are fine) over the 500-Mission fixture, hold 60 s, append 10 rows to different Missions.
2. Assertions: (a) peak live platform threads (`ThreadMXBean`) rise <= 16 over the pre-connection count; (b) used heap after a forced GC exceeds the pre-connection value by <= 64 MB; (c) reducer-invocation counter after the 100 connections == its value after ONE connection + the invocations caused by the 10 appends (no per-connection rescan); (d) all 100 connections receive every forwarded append (10 each). The floor for the ratio form is the same fixture with ONE connection (ADR method); state the measurement and the rule for each budget.
3. Revert-fails: make the feed rescan per connection (c) red; leak a platform thread per connection (a) red; skip delivery to one connection (d) red.
4. 60 s hold: tag the class `@Tag("perf")` like the NFR-001 class. Per WP03 T012 step 8 `test` excludes that tag and `perfTest` (which `check` depends on) runs it, so the NFR-004 JVM proof is part of CI's `check` and of nothing else; do not shorten the 60 s and do not move the class out of the tag.

**Files**: `perf/*` (~300 lines; the test class is `Nfr004SseConnectionsTest`).
**Validation**: `cd services/mission-status-api && ./gradlew perfTest --tests 'org.speckitty.missionstatus.perf.Nfr004*'`.

## Subtask T071: Native legs: NFR-002 start-up and NFR-004 native memory/threads

**Purpose**: The native-only half.

**Steps**:
1. `nativesmoke.NativePerfTest` (run by the `nativePerf` Gradle task with `-PnativeBinary`): (a) NFR-002: time from process start to the first accepted `GET /api/v1/project` (accepted Host) <= 2 s ceiling AND a ratio to the floor sampled in the same run: the start-up time of a trivial native binary built on the same leg (build it with `native-image` from the same `JAVA_HOME` in a workflow step from a one-class source the step writes; no file committed). If that floor cannot be built within the leg timeout, record NFR-002 as ceiling-only and UNMEASURED-ratio in the PR (the spec permits it) - decide after the first CI timing and state it. (b) NFR-004 native: 100 connections, 60 s, 10 appends: the process thread count (Linux `/proc/<pid>/status` Threads; macOS `ps -M`/JNA-free alternative; Windows via a small PowerShell/`Get-Process` call from the test, TEST code only) rises <= 16 and the resident set grows <= 128 MB; all 100 connections receive every append. Where an OS cannot measure a figure, the test records "not measurable on this leg" in the JUnit output and the job summary (never a silent skip), and the JVM leg carries the proof.
2. The harness reuses WP12's process start/stop helpers (same package); no duplicate process code.
3. Misses are classified, not retried.

**Files**: `nativesmoke/NativePerfTest*` (~300 lines).
**Validation**: on this workstation (Linux x64): `cd services/mission-status-api && ./gradlew nativeCompile && ./gradlew nativePerf -PnativeBinary=<built binary>`; the other three legs are CI, stated as owed.

## Subtask T072: Workflow wiring, pins and hand-off

**Purpose**: The legs run the perf task; the structure is pinned.

**Steps**:
1. Workflow: after `nativeSmoke` in each native leg add the `nativePerf` step (and the trivial-binary floor step if kept), with the leg `timeout-minutes` raised only as the first-run timing demands (state the budget in a comment-free YAML field; justify in the PR).
2. Pins appended to `tests/ci/test_mission_status_api_build.py`: each native leg has the `nativePerf` step with `-PnativeBinary`; every class under `perf/` that contains a test method carries `@Tag("perf")` and the build script's `check` depends on `perfTest` (so the NFR-004 JVM proof runs in the JVM job's `check`; the WP03 pin covers the build-script half, this pin the class half and that at least two perf classes exist); no step runs `pytest`; the perf classes exist and carry both ratio and ceiling assertions (a source-text pin: each perf test file mentions both a `RATIO`-named constant and a `CEILING`-named constant). Revert rows: remove the step; delete a ceiling constant: red.
3. `.venv/bin/python -m pytest tests/ci/test_mission_status_api_build.py tests/ci/test_fork_guard.py -q`.
4. Hand-off: list what was measured (numbers, runner), what is provisional, and the ADR classification for any miss. Append tracer entries (friction: flaky vs real; decisions: ratio rule used).

**Validation**: pytest above green; measurements recorded.

## Definition of Done

- NFR-001, NFR-002, NFR-004 asserted as ratios with provisional ceilings beside them, with measurements recorded; reducer/`readLedger` counters assert the cache design; revert-fails rows observed red.
- No retry loops; misses fail once and print the classification inputs.
- Workflow runs `nativePerf` on each native leg; pins green. Unmeasurable figures on a leg are recorded explicitly.

## Risks

- Runner noise: the ADR method (same-run floor, ratio from the first measurement) exists for this; never widen a limit to make a red green without a measurement.
- 60 s holds lengthen `check`/legs: tag, do not shorten.
- Windows/macOS process metrics need OS-specific test code; keep it in test sources only (rule 10 covers main).

## Reviewer Guidance

- Check every budget asserts BOTH a ratio and a ceiling and that the floor is sampled in the same run.
- Check there is no retry or `Thread.sleep`-until-green pattern.
- Check the fixture is generated, not committed, and deterministic.

## Implementation command

`spec-kitty agent action implement WP13 --agent claude`
