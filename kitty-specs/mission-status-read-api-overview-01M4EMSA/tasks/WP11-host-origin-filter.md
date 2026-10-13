---
work_package_id: WP11
title: 'Phase 4b: Host and Origin filter (403 set, closed 400 set, provisional E-7 rows)'
dependencies:
- WP20
requirement_refs:
- FR-009
- C-005
- NFR-003
- SC-005
planning_base_branch: issue-5529-mission-status-read-api-overview
merge_target_branch: issue-5529-mission-status-read-api-overview
branch_strategy: Planning artifacts for this mission were generated on issue-5529-mission-status-read-api-overview. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5529-mission-status-read-api-overview unless the human explicitly redirects the landing branch.
subtasks:
- T060
- T061
- T062
- T063
history: []
agent_profile: java-jenny
authoritative_surface: services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/HostOriginFilter*
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/OwnPortSource*
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/OwnPortHolder*
- services/mission-status-api/src/test/java/org/speckitty/missionstatus/adapter/in/http/hostorigin/**
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/adapter/in/http/HostOriginRefusal*
- services/mission-status-api/src/main/java/org/speckitty/missionstatus/config/HostOriginRegistration*
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP11 - Phase 4b: Host and Origin filter

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `java-jenny`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Implement the Host and Origin servlet filter and its own-port seam so that a request with a foreign Host or Origin is refused with 403 `request_refused` before any Mission read, while the closed list of container-rejected Host values keeps Tomcat's own 400; prove every row with literal expected statuses and accepted controls.

## Context

- Plan phase 4b (plan.md section 8 in full - READ IT, including the 9-row table and the "Further rows" E-7 table; section 11 row 4b; section 13 "Host/Origin filter"; ArchUnit rules 3 and 6). Spec FR-009 (AC-9b, AC-9c, AC-9d), C-005, NFR-003, SC-005. Operator decision E-1 (2026-10-10) is binding: Set 1 (filter-visible Host values) => 403 `request_refused`; Set 2 (closed list, today exactly `evil.example@127.0.0.1:<port>`) => the container's 400, no custom valve, no `ErrorReportValve` re-rendering.
- Depends on WP20 (and through it WP10: the JSON and SSE controllers, the `testsupport.http` harness). Concurrent with WP12..WP15 (workflow/native/CI work): write-disjoint. The WP02 record (Tomcat 11.0.24 table observed in the throwaway harness) is the CONFIRMATION of section 8; where it DIVERGES from the plan, stop and report: the expected values in this WP are literals from section 8 and are never rewritten to match an observation.
- Design (fixed by the plan): `HostOriginFilter` extends `OncePerRequestFilter`, `Ordered.HIGHEST_PRECEDENCE`; reads the RAW `Host` header (`request.getHeader("Host")`), never `getServerName()`/`getServerPort()`; exact, case-sensitive comparison against `127.0.0.1:<own port>` and `localhost:<own port>`; absent or empty Host refused; any `Forwarded` or `X-Forwarded-Host` header refused; Origin absent allowed, present must be `http://` + an accepted host form (own port), `null` and anything else refused. One constant `HostOriginRefusal.STATUS = 403` for every refusal the filter makes; Problem `code: request_refused`, `title: Request refused`, no `detail` naming which check failed. The own port comes from the BOUND server (`WebServerInitializedEvent`, `getWebServer().getPort()`), held in `config.OwnPortHolder` which implements `adapter.in.http.OwnPortSource`; the filter takes `OwnPortSource` in its constructor and never depends on `config` (ArchUnit rules 3 and 6 stay without an exception). A configured port 0 therefore works.
- Public repo hygiene as everywhere. Test package for every suite here: `org.speckitty.missionstatus.adapter.in.http.hostorigin`.
- **Toolchain precondition (first step, before any other work).** Run `java -version` and `./gradlew --version` (from `services/mission-status-api/`) and compare them with the versions the orchestrator recorded in `research.md` (GraalVM Community 25.0.2, Gradle 9.7.1). `JAVA_HOME` and `PATH` for the persistent, orchestrator-provisioned install come from this brief (`tasks-overview.md` section 10). If either command is missing or reports another version: STOP and report BLOCKED (owner: orchestrator/operator, who install or repair the toolchain). Do not substitute another JDK, do not install one yourself, and do not skip a gate this WP lists as local: "CI is the proof" is not an alternative for a local Gradle gate.
- Three E-7 rows are NOT provisional: duplicate Host, HTTP/1.1 without Host and HTTP/1.1 absolute-form foreign target with an accepted Host are part of AC-9b set 2 (closed 400 list), amended into the spec after analyze (`reviews/analyze.ruling.md`, ANL-005). The other E-7 rows (HTTP/1.0 absolute-form foreign target, empty Host, `X-Forwarded-Host`, `Forwarded`, `LOCALHOST:<port>`, `localhost.:<port>`, port-0 control) are PROVISIONAL: behaviour and test land together here; a declined provisional E-7 row is removed with its behaviour. `[::1]` is NOT accepted (spec FR-009).
- Public repo: tests print no paths; the instrumented port counts reads, it does not log them.

## Subtask T060: The filter, `OwnPortSource`, `OwnPortHolder` and registration (red-first)

**Purpose**: The mechanism.

**Steps**:
1. Write the failing AC-9b/9c/9d tests first (T061/T062), then the filter. Create `adapter.in.http.OwnPortSource` (interface `int port()`), `adapter.in.http.HostOriginFilter`, `adapter.in.http.HostOriginRefusal` (the constant) and `config.OwnPortHolder implements OwnPortSource` listening for `WebServerInitializedEvent`.
2. Registration: a `FilterRegistrationBean` (or `@Component` filter with explicit order) in `config` at `HIGHEST_PRECEDENCE` so it runs before MVC dispatch and covers every path including unknown paths, error paths and the contract document route. Registration lives in `config.HostOriginRegistration` (owned by this WP, separate from `OwnPortHolder`).
3. The filter writes the Problem body itself (shared Problem shape, `application/problem+json`) through the same canonical writer the controllers use, with no request value echoed.
4. A test-profile counter incremented at filter entry (for `reachesFilter` assertions); production code carries no test counter (use a test-only `FilterRegistrationBean` decorator or a servlet listener bean in the test configuration).

**Files**: `adapter/in/http/HostOriginFilter*`, `OwnPortSource*`, `HostOriginRefusal*`, `config/OwnPortHolder*`, `config/HostOriginRegistration*` (~220 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.in.http.hostorigin.*'`.

## Subtask T061: AC-9b Host tables over real sockets (literal oracle)

**Purpose**: The two sets, hard-coded.

**Steps**:
1. Raw-socket client (not an HTTP client that normalises headers). Parameterised over the nine rows of plan section 8 and the five request targets: `/api/v1/project`, `/api/v1/missions`, `/api/v1/events` (no stream opens: the response is not `text/event-stream` and an append produces no data on the connection), the contract document route `/api/v1/openapi.yaml`, plus an unknown path (refusal, NOT 404).
2. Each row carries a LITERAL expected status (403 for rows 1-7 and 9; set 2: four 400 rows, row 8 `evil.example@127.0.0.1:<port>` plus the three container rows of step 3) and a LITERAL `reachesFilter` flag (false for row 8 and for the three container rows of step 3, i.e. false for all four set 2 rows) taken from the test source, never from the response just received. Assertions per row: status, `reachesFilter` via the counter, ZERO Mission reads through the instrumented filesystem port, no stream opened, no canary/path/`HOME` in the body (the AC-9g scan, applied to the container-generated 400 body too; the body of Tomcat's 400 is whatever WP02 recorded: assert it contains no secret).
3. AC-9b set 2, the three container-decided rows (spec-fixed, NOT provisional; each on the same five targets, each with literal status 400 and literal `reachesFilter` false): duplicate `Host` 400 (container); HTTP/1.1 without `Host` 400 (container); HTTP/1.1 absolute-form foreign target with accepted `Host` 400 (container, `inconsistentHosts`). Then the provisional filter-decided E-7 rows (same five targets, `reachesFilter` true): HTTP/1.0 absolute-form foreign target 403 (filter); empty `Host:` 403; accepted `Host` plus `X-Forwarded-Host: evil.example` 403; accepted `Host` plus `Forwarded: host=evil.example` 403; `LOCALHOST:<port>` 403 (interim: exact match; flips to 200 only if the operator rules case-insensitive); `localhost.:<port>` 403; configured port 0 with the accepted forms and the bound port 200 (control).
4. Revert-fails (each observed red once): widen the allowed Host set; move the filter behind MVC (register it at lowest precedence); accept `[::1]`; derive the expected status from the response; drop the `reachesFilter` assertion.
5. The foreign-Host 403 variants of the `/v3/api-docs*`, `/swagger-ui*` and `/api/v1/openapi.yaml` requests (the accepted-Host assertions are WP10's).

**Files**: `hostorigin/*` tests (~600 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.in.http.hostorigin.*'`; each row asserts BOTH status and filter entry.

## Subtask T062: AC-9c Origin table and AC-9d accepted controls

**Purpose**: Origin refusals with the controls that prove the guard does not over-refuse.

**Steps**:
1. AC-9c with an accepted Host on the same five targets: `Origin: https://evil.example`, `null`, `http://127.0.0.1:<port+1>`, `http://127.0.0.1.evil.example:<port>`, `https://127.0.0.1:<port>` (wrong scheme) each answer the refusal constant; assert no CORS response headers allow the origin; no Mission read.
2. AC-9d controls on `/api/v1/project`: `Host: 127.0.0.1:<port>` and `localhost:<port>`, each with no Origin, with `Origin: http://127.0.0.1:<port>` and with `Origin: http://localhost:<port>`: all 200. The guard must not refuse any.
3. Status-constant scope test: `HostOriginRefusal.STATUS` is used by the filter only; the contract's other statuses (400 `invalid_page_cursor`, the stream codes, 500 whole-read rows) are NOT governed by it (any lint or ArchUnit rule about the constant is scoped to the filter class).
4. Revert: change the constant to 421 for Host only and the Origin tests turn red (one constant serves both).

**Files**: tests (~300 lines).
**Validation**: `cd services/mission-status-api && ./gradlew test --tests 'org.speckitty.missionstatus.adapter.in.http.hostorigin.*'` (the Origin and accepted-control tables are in the same package).

## Subtask T063: Phase 4b exit gate

**Purpose**: Close 4b.

**Steps**:
1. `./gradlew check` green including AC-9b/9c/9d; re-run WP10's and WP20's suites (they send an accepted Host and must stay green with the filter registered, unchanged).
2. ArchUnit: rule 3 (the filter depends on `OwnPortSource` only), rule 6 (nothing depends on `config`) pass with NO exception added.
3. Config test of WP10 (no forwarded-header strategy) still green; the filter's refusal of `Forwarded`/`X-Forwarded-Host` complements it.
4. Record counts (rows run, Set 1 / Set 2) for the PR "Tests run" section; append tracer entries (design decisions: registration seam, any Tomcat observation).
5. If WP02's Tomcat table diverged from section 8, list the divergence for the orchestrator (a finding against the plan/spec; no automatic rewrite).

**Validation**: all green.

## Definition of Done

- The filter refuses every Set 1 value with 403 `request_refused`, leaves Set 2 to the container's 400, with literal expected statuses and `reachesFilter` flags, zero reads, no stream, no leak; Origin rows and controls pass; E-7 rows land with their behaviour.
- ArchUnit rules 3 and 6 pass without exceptions; WP10's and WP20's suites unchanged and green.
- The native legs stay green at this tip: the skeleton `NativeSmokeTest` addresses the binary as `127.0.0.1:<port>` (an accepted Host form), so `./gradlew nativeCompile nativeSmoke -PnativeBinary=<built binary>` (hello route) is green on this workstation with the filter registered.
- Each revert-fails row observed red once.

## Risks

- Tomcat version behaviour changes (PR-11): the literal oracle fails loudly on an upgrade, by design.
- E-7 rulings may remove rows: keep each row independently deletable with its behaviour.
- Raw sockets on the Windows leg: tests run on the JVM leg (Linux) and in the native smoke stage `hostOrigin` (WP16) on all four legs.

## Reviewer Guidance

- Check the expected statuses are literals in the source, not derived from responses.
- Check the filter reads the raw header and refuses `Forwarded`/`X-Forwarded-Host`.
- Check no `ErrorReportValve` or other container customisation exists.

## Implementation command

`spec-kitty agent action implement WP11 --agent claude`
