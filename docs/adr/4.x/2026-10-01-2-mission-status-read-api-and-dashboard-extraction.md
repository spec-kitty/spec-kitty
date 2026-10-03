---
title: 'ADR: a mission status read API replaces the CLI-bundled dashboard (extract and replace)'
description: 'Remove the bundled dashboard daemon; keep one read-only mission status API with an overview and a detail granularity that external UIs consume (#645).'
status: Proposed
date: '2026-10-01'
---

**Status:** Proposed. D-1 and D-2 record a direction the operator stated on 2026-10-01 and
are **Accepted**. D-8 was **amended and accepted** later on 2026-10-01: the operator moved
deletion to the front (see D-8). D-3 to D-7 are architect amendments that wait for operator
ratification.
**Amendment 2026-10-03 (Accepted):** D-4 and D-7 are amended for the agreed Java service
design. D-5 records that the CLI's own read verbs stay native Python behind one read seam
for now. See "Amendment 2026-10-03" below.

**Date:** 2026-10-01 (amended 2026-10-03)

**Deciders:** Stijn Dejongh (operator). Analysis by `architect-alphonso`.

**Technical Story:** epic [#645](https://github.com/spec-kitty/spec-kitty/issues/645)
(Stable Application API Surface), its children #956 (registry and cache), #957 (mission and
WP resources, `WorkPackageAssignment`), #2789 (`--since` cursor reads) and #460 (transport);
dashboard defects #4520, #4767, #4768 and #4769; roadmap
[direction update 2026-10-01](../../plans/4-0-0-milestone-roadmap.md).

---

## Context and Problem Statement

The CLI ships a local web dashboard in `src/specify_cli/dashboard/`: about 9.4k lines of
Python, JavaScript, CSS and HTML. `spec-kitty dashboard` starts it as a detached daemon. The
daemon records itself in `.kittify/.dashboard`, scans for a free port and kills stale
processes. The browser polls `/api/features` once a second
(`static/dashboard/dashboard.js:1749`). Each poll rescans every mission and re-reduces each
`status.events.jsonl`, with no cache (`scanner.py:895`, #4520: 9–10 s per scan on this
repository's 436 missions). The daemon has open trust defects: it SIGKILLs a recycled PID
(#4767), leaks its shutdown token through `/api/health` (#4768), and does no Host or Origin
check, so DNS rebinding can read the whole API (#4769).

The bigger problem is architectural. Mission and work package (WP) state reaches consumers
along several independent paths, and nothing checks that they agree (#645, "Why"):

- The dashboard computes mission state in its presentation layer. `_derive_mission_status`,
  `_derive_next_action` and `build_mission_registry` live in `dashboard/scanner.py:219`,
  `:249` and `:565`. `dashboard --json` (`cli/commands/dashboard.py:44`) serves the same
  registry.
- `orchestrator-api mission-state` and `list-ready` reduce through `reduce(read_events(...))`
  (`orchestrator_api/commands.py:1165`, `:1226`). That function is the wall-clock
  `reduce_parsed` reducer (`status/reducer.py:175-183`). The dashboard reads through
  `materialize_snapshot` (`status/reducer.py:367`), which is the Lamport `reduce_shared_state`
  reduction. Two external read surfaces therefore use the two different reducers that
  CLAUDE.md's "reducer duality" note describes. *Inferred:* they can disagree when events
  are concurrent (#4941).
- `agent tasks status --json` (`cli/commands/agent/tasks.py:1419`) builds a third board.
- The living architecture docs already record the gap: "Dashboard reads filesystem directly
  rather than through Event Store interface"
  ([implementation mapping](../../architecture/04_implementation_mapping/README.md),
  Divergence Notes 4).

On 2026-10-01 the operator proposed two things. First, remove the dashboard but keep a read
path to mission status. Second, expose that read path at two granularities: a high-level
status built from the ledger and events, and a detail view with WP content, status and
assignment. An external dashboard can then pick the granularity it needs.

## Decision Drivers

- **Single canonical authority** (`DIRECTIVE_044`): one read surface, backed by one service
  layer, which every consumer reads through (#645, "Intended effect").
- **Bounded contexts** (`DIRECTIVE_031`): status reads belong to the status domain, not to a
  UI. Governance and glossary views belong to their own contexts.
- **The adapter-seam rule** (roadmap direction update, rule 2): the CLI core does not talk to
  external systems. A UI is a consumer, not part of the core.
- **Local-first, read-only:** the read path must work offline, with hosted drain off, and
  must never write.
- **Modulith first:** keep the module in-process today, with a boundary that can be
  extracted later into another package or repository.

## Considered Options

1. **Keep and harden the bundled dashboard.** Fix #4767–#4769, add the #956 cache and adopt
   FastAPI (#460).
2. **Remove the dashboard and let consumers read files and `events tail`.** Ship no read API.
3. **Remove the dashboard and keep a mission status read API with two granularities,
   in-process plus CLI `--json`** (chosen).
4. **Remove the dashboard and ship a mission status HTTP service in the CLI.** This would be
   a slimmer server that keeps the daemon.

## Decision Outcome

**Chosen option:** Option 3. It meets every driver. It keeps the operator's two granularities
and moves the logic the dashboard holds today behind the status boundary. It also drops the
daemon and the poll-and-rescan cost from the CLI.

- **D-1 (Accepted): remove the CLI-bundled dashboard.** The server, daemon, static UI,
  `spec-kitty dashboard` command, `/spec-kitty.dashboard` slash command and the
  `spk-admin-dashboard` skill are removed. A replacement UI is built in its own repository
  as an ordinary consumer. The original plan was extract-and-replace: move the domain logic
  in `dashboard/scanner.py` into the read API and rehome every route before deleting
  anything. The amended D-8 deletes first instead; the read API and the route rehoming then
  build the replacement read path from the remaining read models, and the deleted code
  stays recoverable from git history.
- **D-2 (Accepted): keep a read path, the Mission Status Read API, at two granularities.**
  - **Overview** (low detail, many missions): for each mission, its identity (`mission_id`,
    `mid8`, slug, friendly name, display number), lane counts, weighted progress, a derived
    lifecycle status, the latest event, and a change cursor.
  - **Detail** (one mission): each WP's authored plan and resolved runtime state, kept
    separate. That covers lane, assignment (agent, profile, role, model), dependencies and
    readiness, review evidence, and the WP's event history. The WP prompt body is returned
    only on request.
- **D-3 (Proposed): each granularity maps onto a read model that already exists. The API
  composes these models and never re-derives them.**

  | Granularity | Reads | Existing read model |
  |---|---|---|
  | Overview | `meta.json` and `status.events.jsonl` only, no WP files | `materialize_snapshot` (`status/reducer.py:367`) gives lane summary; `compute_weighted_progress` (`status/progress.py:119`); identity resolution; `TailCursor` (`status/tail_reader.py:60`) gives the change cursor |
  | Detail | plus `tasks/WP*.md` frontmatter and body | `reconstruct_wp_view` (`status/wp_view.py:256`), which never conflates authored and resolved state; the dependency graph and `dependency_readiness_for_wp` |

  Every read goes through the coordination-aware status read surface: the
  `_read_path_resolver` and `MissionStatus.load` path. Callers never rebuild paths. The
  contract carries a schema version, as #2789 requires. Its types must not reuse the name
  `MissionStatus`, because the aggregate root at `status/aggregate.py:168` already owns it.
- **D-4 (Proposed): the first form is an in-process query module plus CLI `--json` verbs.
  It is not an HTTP endpoint.** The API has one typed, versioned query function per
  granularity. Each function has one CLI `--json` verb that a non-Python consumer can call
  as a subprocess. The CLI wheel ships no server, daemon, port or PID file. Choosing a
  transport such as HTTP, OpenAPI or a change feed belongs to the consumer repository
  (#460 moves with it). A consumer running a server imports the module or shells out to
  the verb. Change detection comes from polling the overview cursor and then
  `events tail --json` (#3858). It does not come from the in-process status fan-out, which
  runs only while a CLI command runs.
  *Amended 2026-10-03:* the external form is now a separate read-only service. The
  in-process module remains the CLI's own read path, behind one seam. See
  "Amendment 2026-10-03".
- **D-5 (Proposed): fold existing surfaces into the API instead of duplicating them.**
  - The overview verb replaces the deleted `dashboard --json`.
  - `agent tasks status --json` renders from the detail query.
  - `orchestrator-api mission-state` and `list-ready` keep their verbs and envelopes (the
    contract is owned by #5231) but compute through the read API. This also moves them onto
    the Lamport reducer.
  - `events tail --json` stays as the change feed, and the overview exposes its cursor.
  - The TypedDicts in the deleted `dashboard/api_types.py` (recover from git history) seed the contract types, renamed to the
    Mission canon (#957 shapes): `/api/features` and `FeatureItem` become missions.
  - An architectural gate fails any display or external consumer that reduces status itself,
    using the shrink-only allowlist pattern (#645 acceptance). Domain-internal reducers such
    as consolidation, migrations and gates are out of scope for that gate.
- **D-6 (Proposed): the API is read-only and independent of drain.** It never calls the
  writing `materialize()`, never refreshes derived views, never takes a lock, and returns the
  same answer whether hosted drain is on or off. It is a pull over the committed ledger. The
  produce/drain decoupling is push-side and gets its own ADR (roadmap next step 3). Neither
  decision blocks the other.
- **D-7 (Proposed): placement in the layer chain.** The module lives in the `specify_cli`
  layer, next to the status domain it reads. The read models it composes are there already
  (`status/`, `missions/_read_path_resolver.py`, `mission_metadata`). Placing it in
  `runtime` or `mission_runtime` would add edges to their shrink-only outbound ledgers
  (`tests/architectural/test_layer_rules.py`). The contract types depend only on the
  standard library, so they can be extracted later into a client package without bringing
  the CLI along.
  *Amended 2026-10-03:* the in-process module and its seam stay here. The external service
  lives in its own JVM module in this repository, outside the Python wheel. See
  "Amendment 2026-10-03".
- **D-8 (Amended and accepted 2026-10-01): order of work. Delete first.** The operator
  reversed the original order, which put deletion last, after the read API, the reader
  re-pointing and the route rehoming. Reason: the dashboard carries open P1 security
  defects (#4767, #4769) and its replacement does not gate 4.0.0 GA. If the new UI does not
  arrive in time, the code is restored from git.
  1. Delete `src/specify_cli/dashboard/`, `spec-kitty dashboard`, the slash command and the
     skill, with an upgrade migration that removes the installed command files and the
     dashboard's runtime files, touching only paths it can prove are package-owned (version
     marker or managed path; charter, "User Customization Preservation"), and stops a
     dashboard server an older CLI left running when its command line proves it (#5530).
  2. Build the Mission Status Read API and its contract tests (#5528).
  3. Re-point the orchestrator-api reads and `tasks status` to the API (#5532).
  4. Assign read surfaces to the former artifact and governance routes (#5533).
  5. Land the bypass gate.

  `verify-setup --diagnostics` imported `dashboard.diagnostics`; that module moved to
  `specify_cli/diagnostics/project.py` without its dashboard health probe. The docs site's
  glossary page assets moved to `scripts/docs/glossary_page/`. There is no deprecation
  release. None of this gates 4.0.0 GA.

  The original order (Proposed, superseded): build the API, re-point readers and dashboard
  handlers, land the bypass gate, deprecate `spec-kitty dashboard` for one release, run the
  removal migration, then delete the package.

**Where the deleted dashboard's routes go** (former `dashboard/handlers/router.py`). With
deletion first, these are the homes the follow-ups build; until then the routes have no
replacement:

| Route | New home |
|---|---|
| `/api/features`, `/api/kanban/<id>` | This API: overview and detail |
| `/api/research/`, `/api/contracts/`, `/api/checklists/`, `/api/artifact/`, `/api/dossier/` | Mission artifact reads. Planning artifacts are files, not events. A follow-up assigns their read surface (mission dossier or artifact placement); this ADR does not |
| `/api/charter`, `/api/charter-lint`, `/api/glossary-health`, `/api/glossary-terms`, `/glossary` | Governance and glossary contexts (#954, #955). Not this API |
| `/api/diagnostics` | `verify-setup --diagnostics` |
| `/api/health`, `/api/shutdown` | Removed with the daemon |

### Consequences

#### Positive

- One read authority replaces four ad-hoc readers that use two different reducers.
- The CLI loses a daemon, its PID-file and kill-sweep defects (#4767–#4769), and the per-poll
  rescan (#4520). Those issues close when the dashboard is deleted, not by hardening it.
- External UIs, MCP adapters and SDKs get a documented, versioned contract and can choose a
  granularity.
- The boundary is ready for extraction: contract types without dependencies, in-process today.

#### Negative

- Until a replacement UI ships, users have no browser kanban. `agent tasks status` is the
  interim view.
- Removal ships without a deprecation release; an upgrade migration cleans the 17 agent
  surfaces.
- Until the read API lands, external readers have `agent tasks status --json`,
  `orchestrator-api mission-state` and `events tail --json`, which still use the two
  reducers the Context section describes.
- Mission artifact and governance views lose their only UI until their own read surfaces land.

#### Neutral

- The `orchestrator-api` lifecycle verbs and their contract are unchanged.
- The landscape's Dashboard container stays as a concept. Only its in-repo implementation
  leaves ([landscape](../../architecture/00_landscape/README.md)).

### Confirmation

- Contract tests pin the overview and detail shapes and their schema version.
- On the same fixture mission, the orchestrator-api reads, `tasks status --json` and the
  overview and detail queries agree.
- The bypass gate stays green and its allowlist only shrinks.
- The overview of a mission reads no `tasks/` files (asserted by a test).
- `src/specify_cli/dashboard/` is gone and `pyproject.toml` ships no server dependency.

## Amendment 2026-10-03 (Accepted): a separate Java read service; the CLI stays native behind one seam

**Deciders:** Stijn Dejongh (operator), 2026-10-03. The service design was agreed with the
UI contributors and recorded on
[#5528](https://github.com/spec-kitty/spec-kitty/issues/5528#issuecomment-5937187090).

**Why.** External consumers (the new dashboard in `spec-kitty-mission-ui` and Kitty Desktop)
need a browser-friendly transport with a change stream, and the UI team builds both sides.
Option 4 was rejected because it put a daemon *inside the CLI*. A separately built and
separately released binary keeps the wheel server-free and keeps that trust model out of the
CLI core.

- **D-4 (amended).** The external form of the Mission Status Read API is a detached,
  read-only HTTP service: Java 25, Spring Boot 4 (Spring MVC on virtual threads),
  distributed as a GraalVM native binary per OS. It serves REST resources for the two D-2
  granularities (`/api/v1/missions`, `/api/v1/missions/{id}`), an SSE change stream on
  `/api/v1/events`, and an OpenAPI 3.1 document. It binds to `127.0.0.1` only, checks Host
  and Origin, and puts no secrets in responses (the #4767–#4769 lessons). It may serve a
  pinned, checksummed dashboard bundle at `/`. The contract is written first
  (`contracts/mission-status/openapi.yaml`, #5558); the service and the UI both build
  against it.
- **D-5 (amended): the CLI stays native for now, behind one read seam that is ready for the
  cut-over.**
  - The status module exposes a single read port for the D-2 granularities (overview and
    detail). Every CLI command that reads mission status, including
    `agent tasks status --json` and orchestrator-api `mission-state` / `list-ready`, calls
    only that port. No command reduces events, resolves read paths or composes read models
    itself.
  - Today the port has one adapter: the native, in-process Python implementation (D-3). It
    never calls the service, so the CLI keeps working offline with no JVM binary present.
  - The service ports the Lamport reduction (`status.reducer.materialize`). A conformance
    test runs both implementations over the same missions and fails on any difference, so
    there is one *answer* while there are two implementations.
  - **Cut-over (later, separate decision).** Once the Java service has proven itself, a
    second adapter that calls its API replaces the native one *inside the seam*. The CLI
    commands do not change and cannot tell the difference. The native implementation is
    then retired.
  - The D-5 bypass gate enforces the seam: a CLI command that reads status without going
    through the port fails it.
- **D-6 (unchanged).** Both implementations are read-only and independent of drain.
- **D-7 (amended).** The service is its own build in this repository (for example
  `services/mission-status-api/`), with a path-filtered CI workflow and its own release
  artifact. It is not part of the Python wheel, so "the CLI wheel ships no server, daemon,
  port or PID file" still holds. The read port and its native adapter stay in the
  `specify_cli` status domain as D-7 originally placed them.

**Consequences.** Until the cut-over there are two reducer implementations. That is
acceptable only because the conformance test is a gate, not a report. Tightening the status
module's encapsulation is now prerequisite work for the cut-over, tracked with the reader
re-pointing (#5532). The JVM toolchain and the native release matrix are new CI cost,
confined to the path-filtered workflow. Still open on #5528: the lifecycle-status
vocabulary, the WP status chips, and the artifact reads (#5533).

## Pros and Cons of the Options

### Option 1: keep and harden

**Pros:** no user-visible gap. **Cons:** keeps a daemon and a UI in the CLI core, against
the adapter-seam rule. Needs security, cache and transport work (#4791, #956, #460) on a
surface the operator wants out. Does not fix the duplicate read paths.

### Option 2: files and `events tail` only

**Pros:** least code. **Cons:** every consumer re-implements reduction, the read-path
resolution for the coordination topology, and the authored/resolved WP split. That is the
divergence #645 exists to end. It is a shadow path by construction.

### Option 3: in-process read API plus CLI `--json` (chosen)

**Pros:** a single authority, no daemon, extractable later, and both granularities served
from existing read models. **Cons:** consumers that are not Python pay a subprocess per
call. That cost is acceptable because change detection uses the cursor, not a rescan.

### Option 4: HTTP service in the CLI

**Pros:** browser-friendly. **Cons:** reintroduces the daemon lifecycle and the trust model
of #4767–#4769 in a new form. It also decides the transport for consumers who should own
it.

## Open questions (operator)

1. **Name.** Resolved 2026-10-01: the operator ratified **Mission Status Read API**.
   "Runtime status" was rejected because it already names three things: `src/runtime/`
   (the control loop), `src/specify_cli/runtime/` (agent assets) and WP runtime state
   (`DIRECTIVE_032`).
2. **Interim risk.** Resolved 2026-10-01: the dashboard is deleted first (amended D-8),
   which closes #4767, #4768 and #4769.
3. **Charter.** "Dashboard must support 100+ work packages without lag" (charter,
   Performance and Scale) refers to the dashboard. It needs a charter amendment that
   restates it as a read-API budget.

## More Information

- [API & Dashboard domain plan](../../plans/domains/api-dashboard-domain-plan.md): the
  durable plan for #645 and #650, updated to point here.
- [4.0.0 milestone roadmap](../../plans/4-0-0-milestone-roadmap.md): Strangler prep lane.
- [Status model](../../architecture/status-model.md): the event log and reducers.
- [ADR 2026-09-26-3](../3.x/2026-09-26-3-hosted-interaction-opt-in.md): drain posture. The
  produce/drain amendment is a separate 4.x ADR.
