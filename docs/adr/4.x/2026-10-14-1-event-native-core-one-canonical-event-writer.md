---
title: 'ADR: an event-native core with one canonical event writer behind a domain port'
description: 'One EventBridge module writes only spec-kitty-events contract events; the run loop calls its port; git and filesystem effects become internal consumers.'
status: Accepted
date: '2026-10-14'
---

# An event-native core with one canonical event writer behind a domain port

**Status:** Accepted (2026-10-14). Decided by the operator on 2026-10-14; this record writes the decision down.

**Date:** 2026-10-14

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- Operator ruling, 2026-10-14 (quoted under Context).
- It builds on [ADR 2026-10-13-2](2026-10-13-2-the-event-ledger-is-the-publication-seam-default-on-with-local-retention.md) (pub, ledger, sub; a versioned row contract in `spec-kitty-events`). It amends that record's D-1 row list: the lifecycle row kind is retired, not given its own schema (see the Amendments note added there).
- It builds on the produce side of [ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md), D-6: the read API stays a pull over the committed ledger, and this record names the one thing that writes that ledger.
- It keeps [ADR 2026-02-09-3](../2.x/2026-02-09-3-event-log-merge-semantics.md) (event-log merge semantics) unchanged. The writer changes, but the log keeps its merge and reduction rules.
- It keeps [ADR 2026-10-06-1](2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md) unchanged: hosted surfaces stay frozen.

**Reader:** a maintainer changing how the CLI or the runtime records what happened to a Mission or a work package, or adding a side effect that reacts to it.

---

## Context and Problem Statement

The operator's decision, verbatim:

> "The idea is to have a SINGLE canonical event writer module inside of the CLI. This writes `spec-kitty-events' published contract compatible events only. The event schema MUST contain a 'schemaVersion' field, so consumers know which events they are receiving, and async backwards compatibility is facilitated. Consumers can still choose whether to support multiple versions, or a single version. The producer ( usually ) produces only the latest version. Cfr. https://martinfowler.com/eaaDev/EventSourcing.html. Our runtime ( FSM ) core module sends these events as missions transition through their lifecycle. The internal 'lifecycle events' are to be removed and replaced by canonical events ONLY. We will use a ports-and-adaptors approach for the event creations: the core mission run loop needn't know about the structure of the event writer or pub-ledger-sub approach. It only needs to know to call the eventbridge ssot entrypoints when transitioning WPs or advancing mission state. Allowing it to be pure domain code, and having the git / filesystem operations handled by internal consumers of the events. This effectively makes our core system event-native by design."

The decisions of 2026-10-13 stand: runtime transitions create events; events flow pub, ledger, sub; producers and consumers (the consumers live in `spec-kitty/event-router`) share only `spec-kitty-events` contracts; ledger rows get a versioned row schema in `spec-kitty-events`.

### Current state (`origin/main`, 566b20b9)

**Many writers, several row shapes.** Counting each module that builds an event-like record and appends it to a log, there are twelve producers writing seven files:

| # | Producer | File | Row shape and version marker |
|---|---|---|---|
| 1 | Lane transitions: `status/transition_pipeline.py::prepare_transition` (:245) builds a `StatusEvent`, appended by `status/emit.py::_persist_prepared` (:831) or `BookkeepingTransaction.append_events` (`coordination/transaction.py:985`) | `status.events.jsonl` | `StatusEvent.to_dict` (`status/models.py:470`): flat row, **no version** |
| 2 | Inner-state annotations: `status/emit.py::emit_inner_state_changed` (:1212) | `status.events.jsonl` | `InnerStateChanged.to_dict` (`status/models.py:793`), no version |
| 3 | Internal lifecycle events: `status/lifecycle_events.py::persist_lifecycle_event_local` (:536), envelope from `_build_envelope` (:309) | `.kittify/canonical-events.jsonl` and `status.events.jsonl` (:10-18, :125-126) | local envelope, `schema_version "5.0.0"` (:317), marked `canonical-producer-exempt: #1198` (:308, :319) |
| 4 | Decision points: `decisions/emit.py::_append_raw_event` (:117) | `status.events.jsonl` (:65) | `DECISIONPOINT_SCHEMA_VERSION` (:185) |
| 5 | Retrospective lifecycle: `retrospective/lifecycle_events.py` (:320-331) | `status.events.jsonl` (:55) | integer `schema_version = 1` (:146) |
| 6 | Retrospective events, superseded entry: `retrospective/events.py` (:208-226) | `status.events.jsonl` | own envelope |
| 7 | Backfill migration: `migration/backfill_runtime_state.py` (:1200, :1440) | `status.events.jsonl` | synthesized `StatusEvent` rows |
| 8 | Run journal: `runtime/next/_internal_runtime/engine.py::_append_event` (:107-123) | `.kittify/runtime/runs/<run>/run.events.jsonl` | `{event_type, timestamp, payload}`, no `event_id`, no version, `canonical-producer-exempt: #1248` (:109) |
| 9 | Decision input log: `events/decision_log.py::DecisionGitLog` (:78, append at :252) | `decisions.events.jsonl` | sanitized `mission_next` payloads |
| 10 | Mission v1 events: `mission_v1/events.py::_write_event` (:60-66) | `mission-events.jsonl` (:23) | own dict |
| 11 | Glossary: `glossary/events.py::_local_append_event` (:162-173) | `.kittify/events/glossary/<mission_id>.events.jsonl` | own dict (#1200 markers) |
| 12 | Op records: `invocation/writer.py` (:194-205), `invocation/lifecycle.py::append_lifecycle_record` (:57) | `kitty-ops/<op>.jsonl`, `kitty-ops/lifecycle.jsonl` | Op record schema v2 |

Rows 1 to 7 share `status.events.jsonl` and two low-level append primitives in `status/store.py` (`append_raw_rows_atomic` :369, `append_event_stream_atomic_verified` :496). The file stays readable only because a hand-kept registry tells the lane reader which `event_type` rows to skip and keep (`AUTHORITATIVE_NON_LANE_EVENT_TYPES`, `status/lifecycle_events.py:166`). A thirteenth shape exists only on the way out: `build_saas_lifecycle_queue_event` (:421) rewrites a lifecycle row into a 3.0.0 envelope (:462) for the hosted relay.

**There are two internal lifecycle-event writers, with many importers.** `git grep -l lifecycle_events origin/main -- src` lists 23 files (`status/lifecycle_events.py` itself and 22 others), and they cover two modules:
- `status/lifecycle_events.py` (producer 3) has 14 direct module importers, among them `migration/mission_state.py`, `status/doctor.py`, `status/views.py`, `status/zeitgeist_bridge.py` and the upgrade migration `m_3_2_9_migrate_lifecycle_envelope.py`. More callers reach it through the `specify_cli.status` re-exports, for example `core/mission_creation_events.py:76`. `MissionReopened` and `FollowUpRecorded` stay local-only because the hosted strict path would reject them (:85-106).
- `retrospective/lifecycle_events.py` (producer 5) is imported by `runtime/next/runtime_bridge_retrospective.py:227`, `cli/commands/agent_retrospect.py:36`, `post_merge/retrospective_terminus.py:128` and `retrospective/events.py:222`.

**Where transitions are triggered, and where side effects run inline.**
- The runtime run loop (`runtime/next/`) reads lane state (`decision.py`, `discovery.py`) but does not write it. Lane writes inside composed steps go through `emit_status_transition` (`runtime_bridge_composition.py:93-95`), and production callers use the transactional door `emit_status_transition_transactional` (`coordination/status_transition.py:1598`): CLI commands (`agent/tasks_move_task_executor.py`, `agent/tasks.py`), `orchestrator_api/wp_lifecycle.py:846`, consolidation (`done_bookkeeping.py`, both attestations) and the `MissionStatus` facade (`status/aggregate.py:168`).
- The runtime already has the shape of a port: `RuntimeEventEmitter` is a `Protocol` over canonical `mission_next` payloads (`runtime/next/_internal_runtime/events.py:76`), with a reject-on-conflict factory registry (:240) and `runtime_emitter_for_mission` (:288). But the engine also writes its own journal and snapshot directly (`engine.py:107`, `:132`), and the bridge wraps the emitter in `DecisionGitLog` (`runtime_bridge.py:497-512`), which calls `safe_commit` inline on every answered decision and swallows a failed commit as a warning (`events/decision_log.py:85-87`, `:269-276`).
- The validation step is already pure: `prepare_transition` has "zero writes, zero locks, zero git, zero fan-out" (`status/transition_pipeline.py:27-35`). Its git-derived `lane_head` stamp is injected as a probe (`status/emit.py:996-1006`).
- The shells around it do the git and filesystem work in line. `BookkeepingTransaction` appends to the worktree log, commits through `safe_commit` (`coordination/transaction.py:1225-1266`), cuts the appended rows on failure (`_cut_event_log`, :1350) and runs deferred outbound effects only after the commit (:952-962, :1431). The coordination fallback commits status artifacts itself (`coordination/status_transition.py:362-395`, `:487`). Mission creation commits its creation events to the coordination branch (`core/mission_creation_events.py:163`).
- Outbound notification is a third concern mixed into the same shells: the flat shell fans out after releasing its lock (`status/emit.py:1026-1035`), the lifecycle writer fans out after its append (`status/lifecycle_events.py:646`), and the seam `status/adapters.py` (`fire_saas_fanout` :265, `fire_lifecycle_saas_fanout` :382) still gates on hosted drain (:295, :393) until ADR 2026-10-13-2 D-2 lands.

**What "schemaVersion" means against the published contract.** `spec-kitty-events` (`origin/main` 5599380, package 10.4.6; the CLI pins `>=10.4.4,<11`, `pyproject.toml:80`) already has:
- An **envelope** version: `Event.schema_version`, snake_case on the wire, default and only accepted value `"3.0.0"` (`models.py:141`; `strict.py:144`, `:629`; `contracts/versioning-and-compatibility.md`). The contract says producers keep emitting `3.0.0` whatever the package major.
- **Per-family payload versions** for five families: `CONNECTOR_SCHEMA_VERSION` 2.8.0, `DECISIONPOINT_SCHEMA_VERSION` 3.0.0, `AUDIT_SCHEMA_VERSION` 2.5.0, `PROFILE_INVOCATION_SCHEMA_VERSION` 3.1.0, `RETROSPECTIVE_SCHEMA_VERSION` 4.1.0.

So the requirement is met at the envelope level for events that leave the machine. It is not met where the operator needs it:
- The envelope version is pinned to one value, so it tells a consumer nothing about the **payload** shape. The families a Mission run produces most (`status` lane transitions, `project_lifecycle`, `mission_next`) have no payload version at all.
- The **ledger rows** carry no version (rows 1, 2, 8), a local one that contradicts the wire (row 3's `"5.0.0"`), or a different type (row 5's integer). The row schema of ADR 2026-10-13-2 D-1 does not exist yet.

## Decision Drivers

- **Single canonical authority** (charter): one writer, one contract, one place to change.
- **Pure domain core** (charter: DDD and tiered rigour): the run loop and the lane state machine decide; they do not touch git, files or transports.
- **Consumers choose their versions**: every persisted or published event says which shape it is.
- **No lost history**: the committed logs stay readable and are never rewritten (ADR 2026-10-13-2 D-3; the archive freeze of [ADR 2026-10-11-1](2026-10-11-1-archive-freeze-verifies-reducer-outcome-not-byte-identity.md)).
- **The consolidation gates keep their evidence** (status events with `policy_metadata.lane_head`, `review_result` and `force`).

## Considered Options

1. **One canonical event writer, the EventBridge, behind a domain port; side effects move into internal consumers (chosen, operator ruling 2026-10-14).**
2. Keep the twelve producers and enforce the contract with a producer gate on persisted lines only (ADR 2026-10-13-2's Confirmation).
3. Keep writing internal rows and canonicalize only at the outbound edge, as `build_saas_lifecycle_queue_event` does today.

## Decision Outcome

**Chosen option:** "One canonical event writer behind a domain port", because it is the only option that gives the ledger one authority and lets the core stay domain code. Option 2 checks shapes but leaves twelve writers and inline git. Option 3 keeps the ledger non-canonical, so every consumer still needs a CLI-side translation.

### D-1: one canonical event writer, the EventBridge

The CLI has exactly one module that creates and persists events: the EventBridge. It is the single source of truth for event creation. Every event-like record the CLI persists, today's producers 1 to 12 included, is created through it. No other module appends to an event log. The low-level append primitives become private to it.

### D-2: the domain depends on a port, not on the writer

The run loop and the state machine see only an EventBridge **port**: a small interface owned by the domain layer, in the direction the layer rules allow (`kernel <- charter <- {runtime, mission_runtime} <- specify_cli`). The port has SSOT entry points for the facts the domain decides:
- a work package transition (the event `prepare_transition` already builds);
- a Mission state advance (run started, step issued, step completed, decision requested and answered, run completed).

The domain calls an entry point and knows nothing else: not the row format, not the ledger file, not the pub, ledger, sub flow, not git. The writer is an **adapter** in `specify_cli`, bound at the composition root. `RuntimeEventEmitter` and its factory registry are the existing seed of this port and are grown into it, not duplicated. Facts produced outside the run loop (decision points, retrospective, glossary, Op records) use family entry points on the same bridge.

### D-3: contract events only, latest version, every event versioned

- The bridge writes only events that conform to a contract published by `spec-kitty-events`: a typed payload from the package, carried in the ledger row schema of ADR 2026-10-13-2 D-1. The full 3.0.0 envelope remains the wire contract for events that leave the machine.
- It produces only the **latest** version of each event type. It does not write older shapes and does not dual-write.
- Every event carries its schema version, so a consumer knows what it is reading. On the wire the field is `schema_version`, the published contract's name, and it stays that name unless `spec-kitty-events` changes it. The operator's "schemaVersion" names this requirement, not a new field name. Two versions are needed and both must be present:
  - the envelope or row version (D-1 of ADR 2026-10-13-2);
  - a payload version per event type, for every family the bridge writes. `status`, `project_lifecycle` and `mission_next` have none today. `spec-kitty-events` adds them; their field placement and name are that package's call.
- Consumers decide whether to support one version or several. The producer makes no promise to emit an old version for a consumer that has not upgraded. Compatibility is carried by the version marker and the package's versioning rules (`contracts/versioning-and-compatibility.md`).

### D-4: the internal lifecycle events are retired

Both internal lifecycle-event modules go. `status/lifecycle_events.py` is removed with its `"5.0.0"` local envelope, its `LIFECYCLE_EVENT_TYPES` and `LOCAL_ONLY_LIFECYCLE_EVENT_TYPES` sets and the CLI-side envelope rewrite for the hosted relay. `retrospective/lifecycle_events.py` is removed with its integer-versioned rows; the retrospective facts are written as the canonical `spec-kitty-events` retrospective events (`RETROSPECTIVE_SCHEMA_VERSION`). Each lifecycle fact (project initialized, Mission created, specify, plan and tasks started and completed, work package created, reviewer self-approval, Mission reopened, follow-up recorded) is written as the canonical `spec-kitty-events` event for it. A fact with no canonical event yet gets one in `spec-kitty-events` first (a minor release under its rules) before the CLI writes it. No new internal event type is added in the meantime.

### D-5: git and filesystem effects are internal consumers

Status commits, artifact writes, coordination commits, worktree work, the lane-state mirror, the derived projection refresh and outbound publication stop being inline steps of the transition shells. Each becomes an **internal consumer** (a subscriber in the CLI) of the events the bridge writes. Two kinds:
- **Synchronous consumers** run inside the bridge's unit of work, after the append and before it returns. The status commit is one: today's guarantee holds that an event is announced only after its commit succeeded (`coordination/status_transition.py:26-29`).
- **Asynchronous consumers** run after the unit of work. They include the derived projection, the outbound publication adapter and the in-process seam of `status/adapters.py`. Their failure never undoes or blocks the event.

External publication is not one of these. The bridge's external publication adapter is `spec-kitty/event-router`'s concern; it reads the ledger as ADR 2026-10-13-2 D-2 describes. The Zeitgeist handlers stay frozen and drain-gated (ADR 2026-10-06-1, ADR 2026-10-13-2 D-2).

This follows Martin Fowler's [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html): every change of state is captured as an event, and the event log, not the side effects, is the record. Lane state already works this way: `status.events.jsonl` is its sole authority. This decision makes the rest of the core work the same way.

### Consequences

#### Positive

- One writer and one contract. A consumer, in this repository or in event-router, needs only `spec-kitty-events`.
- The run loop and the state machine become testable without git or a filesystem; a test port records the calls.
- The `canonical-producer-exempt` markers (#1198, #1248, #1200), the lifecycle envelope, the hosted canonicalizer and the non-lane registry's lifecycle half go away.
- Adding a side effect means adding a consumer, not editing a transition shell.

#### Negative

- A large migration across the 22 files that use the two lifecycle modules, three transition shells and the consolidation code. It cannot ship as one change.
- `spec-kitty-events` takes on payload versions for `status`, `project_lifecycle` and `mission_next`, and the lifecycle events that have no canonical form today. Each is a cross-repository release before the CLI can switch.
- Moving side effects out of the shells changes their failure handling and needs new tests for every consumer.

#### Neutral

- The Mission Status Read API (ADR 2026-10-01-2) is unchanged; it reads the committed ledger.
- `hosted.drain`, `[hosted] drain` and the hidden hosted CLI entries are unchanged.

#### What must stay true during the migration

- **Existing logs.** Committed `status.events.jsonl`, `decisions.events.jsonl` and `.kittify/canonical-events.jsonl` rows are never rewritten. Readers keep accepting every historical shape: unversioned rows read as version 1 (ADR 2026-10-13-2 D-1), and `"5.0.0"` lifecycle rows stay readable as legacy. Only new rows use the canonical shape, so a Mission's log can hold both. The merge driver installed for these files keeps working on mixed logs. The archive freeze compares reducer outcomes, not bytes, so it still holds.
- **Reducer duality.** The bridge changes who writes, not how logs are reduced. Two reducers still ship: the Lamport wrapper `materialize_snapshot` (`status/reducer.py:373-377`, ADR 2026-02-09-3) and the wall-clock `reduce_parsed` (`status/reducer.py:17`, `:176-181`). The consolidation gates keep reading through the Lamport wrapper (`consolidation/reconciliation.py::build_approved_wp_set`, :1442). #4941 stays open, and nothing here resolves it.
- **Consolidation gates.** The approval-stamp bound, per-WP attribution, the reconciliation claim, the coordination status-surface guard and the origin-freshness gate read status events. They read `policy_metadata.lane_head`, `review_result`, `force`, `evidence` and actor provenance. The canonical status event carries each of these, so the gates' verdicts do not change. If a field changes form, the gate migrates in the same change. The `lane_head` probe stays a port the adapter fills; the domain never runs git to stamp it.
- **Ordering and atomicity.** The event is appended before any consumer runs. A synchronous consumer that fails rolls the append back and the call raises, as `BookkeepingTransaction` does today; no consumer runs for an event that was cut. An asynchronous consumer that fails leaves the event recorded and its own work pending. Because consumers are idempotent by `event_id`, it can be rerun. `DecisionGitLog`'s swallowed commit failure becomes a recorded, rerunnable consumer failure.
- **Hosted stays frozen.** Nothing in this decision turns on, extends or points at Zeitgeist, auth or the hosted backend.

### Confirmation

- An architectural gate finds exactly one module that appends to any event log (`*.events.jsonl`, `canonical-events.jsonl`, `run.events.jsonl`, `mission-events.jsonl`, `kitty-ops/*.jsonl`), with an empty allowlist.
- The layer rules show `runtime` and the transition pipeline import the EventBridge port and nothing that runs git or writes event files.
- Every row the bridge writes validates against its `spec-kitty-events` row schema and carries both version markers; no `canonical-producer-exempt` marker remains.
- `status/lifecycle_events.py` and `retrospective/lifecycle_events.py` are gone, and `git grep lifecycle_events -- src` finds no importer.
- The consolidation suites (`tests/consolidation/`) pass unchanged over logs that mix legacy and canonical rows.
- A failing synchronous consumer leaves the log byte-identical; a failing asynchronous consumer leaves the event recorded, and a rerun completes it.

### Open questions (each with a default)

1. **Where the port and the bridge live.** Default: the port in `src/runtime/` next to `RuntimeEventEmitter`; the bridge adapter in `src/specify_cli/events/`.
2. **Payload version placement and name.** Default: a version field on each typed payload, named and placed by `spec-kitty-events`, snake_case like `schema_version`.
3. **Do the file layouts change?** Default: no. The bridge writes the same files (`status.events.jsonl` per Mission, `.kittify/canonical-events.jsonl` for project facts, the run journal, `decisions.events.jsonl`); it does not merge them into one ledger file.
4. **Is the Mission state a projection of events?** Default: the run snapshot (`engine.py:132`) and `status.json` become projections rebuilt by consumers from the ledger; `meta.json` stays authored configuration.
5. **Consumer failure reporting.** Default: a pending asynchronous consumer is reported by `spec-kitty doctor` and rerun by an explicit command, never silently retried in a loop.
6. **Order of migration.** Default: the work package transition first (one bridge entry point behind the two existing doors), then the run loop, then the lifecycle facts, then the remaining families.

## Pros and Cons of the Options

### A producer gate over twelve writers

**Pros:** smallest change; ADR 2026-10-13-2 already plans the gate. **Cons:** compliance without one authority. The side effects stay inline, so the domain still runs git, and each new writer has to be caught by the gate after the fact.

### Canonicalize only at the outbound edge

**Pros:** the ledger is untouched. **Cons:** the ledger stays CLI-internal, which contradicts "producers and consumers share only the contracts". It keeps today's translation step, the one that made `MissionReopened` and `FollowUpRecorded` local-only.

## More Information

- Martin Fowler, [Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html).
- [ADR 2026-10-13-2](2026-10-13-2-the-event-ledger-is-the-publication-seam-default-on-with-local-retention.md): row contract, publication seam, retention.
- [ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md), D-6: the read side.
- [ADR 2026-02-09-3](../2.x/2026-02-09-3-event-log-merge-semantics.md): event-log merge semantics.
- [ADR 2026-10-06-1](2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md): hosted surfaces frozen.
- `spec-kitty-events`: `contracts/versioning-and-compatibility.md`, `models.py` (`Event.schema_version`), `strict.py`.
