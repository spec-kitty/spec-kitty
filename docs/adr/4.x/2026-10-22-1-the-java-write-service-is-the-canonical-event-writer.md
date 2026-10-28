---
title: 'ADR: the Java write service is the canonical event writer, one resident service per repository'
description: 'The command side of the Mission Write API is the one event writer: one resident Java service per repository behind the CLI EventBridge port, a JVM fallback, no Python writer.'
status: Accepted
date: '2026-10-22'
---

# The Java write service is the canonical event writer, one resident service per repository

**Status:** Accepted (2026-10-22). Operator rulings of 2026-10-22, recorded on #6117, #6185 and #6608. Amended by [ADR 2026-10-27-1](2026-10-27-1-the-write-service-protocol-is-loopback-http-with-a-bearer-token.md) (open question 3, D-3, D-7); see Amendment 2026-10-27.

> **What was ruled and what is derived.**
> - **Ruled by the operator:** the event writer is a Java service that reuses the read API's domain models; one service per repository; the CLI decides when and what, the service how and where; a JVM jar fallback for a missing native binary; #6185 folds into #6117's modules.
> - **Derived:** every clause marked *(derived)* follows from those rulings together with the charter's single-canonical-authority principle and ADR 2026-10-14-1. Each one comes from the research recommendation on #6608.
> - **Open:** the open questions at the end carry defaults that hold until the operator rules otherwise.

**Date:** 2026-10-22

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- Epic #6608 (event-native core) and its child epic #6117 (Mission Write API).
- #6185 (the native producer, folded into #6117's modules).
- The research recommendation on #6608 (2026-10-22).
- The current-state map [event ledger writers and readers](../../architecture/event-ledger-writers-and-readers.md).
- It amends [ADR 2026-10-14-1](2026-10-14-1-event-native-core-one-canonical-event-writer.md) (D-1, D-2, D-5 and the Confirmation) and [ADR 2026-10-03-1](2026-10-03-1-charter-read-write-service-strangler.md) (its "event system" rationale).
- It keeps [ADR 2026-10-13-2](2026-10-13-2-the-event-ledger-is-the-publication-seam-default-on-with-local-retention.md) D-2 and D-3 (the committed ledger is the publication seam; retention) and [ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md) (the read API, read only) unchanged.
- [ADR 2026-02-09-3](../2.x/2026-02-09-3-event-log-merge-semantics.md) is amended the same day by a separate ruling: the ordering is wall clock for 4.0.0, the merge rules are kept, and Lamport-primary ordering is a post-GA direction (#6609). This record does not change the ordering.
- It supersedes three parts of #6117:
  - decision 4's recommendation of a per-command native binary;
  - the per-command description of `command-cli` in decision 12. The module names stand, and `command-cli` becomes the service deployable;
  - intended effect 6, "a write needs no running service".

**Reader:** a maintainer building the write side of the event ledger, or changing how the CLI records a work package transition or a Mission state change.

---

## Context and Problem Statement

ADR 2026-10-14-1 decided that core has **one** canonical event writer, the EventBridge, behind a domain port, and placed it as an adapter inside `specify_cli`. Nothing implements it yet:
- About fifteen append implementations in more than twelve modules write at least six row shapes.
- Only glossary writes through `spec_kitty_events.persistence.append_event` (see the current-state map).

Two Java efforts exist on the tracker beside it:
- **#6117 (Mission Write API).** It designs "one Java write core … the command side of a CQRS split; the read API is the query side". Decision 12 (ruled 2026-10-13) settles its modules: `domain-model` and `event-log` shared, with `query-service` and `command-cli` as the deployables. It ships as a native binary run once per command.
- **#6185.** A standalone native producer (`services/event-producer`), which warns and continues when the binary is missing.

The operator ruled on 2026-10-22, verbatim:

> "having a write service as a Java-based service is the way to go, as it enables many alternate deployment configurations, and makes it easier to reuse the same logical DSO models as the read api uses. If we ever decide to move from a local, file-based ledger to a database / hosted-first solution, the java-service architecture makes more sense."

> "Why does it need to be a per-worktree service daemon? Would that not defeat any and all benefits of a backend service? If we can run a GraalVM backend per repository, which writes to the required ledger location / worktrees / filesystem paths, that would make the CLI feel smoorther [sic] and snappier, as well as make ownership even clearer -> CLI controls when to send what. Service controls HOW and WHERE to store it, based on the request context."

Further rulings the same day:
- A missing native binary falls back to a **JVM jar**.
- #6185 **folds into #6117's modules**.
- #6117 becomes a **child of #6608**.

What the merged read service offers a write side (the #6608 recommendation):
- **Reusable:** an architecture and a current-state model: `Lane`, `WpState`, `StatusSnapshot`, `StatusReducer`, the hexagonal layout, and a directional ArchUnit rule (query never depends on command).
- **Missing:** a write domain.
  - `StatusEvent` and `Actor` are lossy read projections.
  - There is no encoder that reproduces Python's `json.dumps(sort_keys=True)` bytes.
  - The lane state machine and its guards (`src/specify_cli/status/wp_state.py`) are not ported.
- **Blockers before any Java writer shares a file with the CLI:**
  - Core locks with `fcntl.flock` (`src/kernel/locks.py:222`), which on Linux does not exclude Java's `fcntl` record locks.
  - No `spec-kitty-events` fixture covers a lane-transition row.

## Decision Drivers

- **Single canonical authority** (charter): one writer, one implementation of the row format, the lock and the fold.
- **No lost history:** the status log is the sole authority for lane state, and consolidation reads it, so a write either lands or fails loudly.
- **Reuse:** the write side shares the read side's domain models instead of keeping a second set.
- **Deployment freedom:** the same use cases can be deployed in more than one configuration, with storage behind a port.
- **A snappy CLI:** no process start or JVM warm-up on every transition.
- **Clear ownership:** the CLI decides when and what; the service decides how and where.

## Considered Options

1. **Python in-process EventBridge** (ADR 2026-10-14-1 as written).
2. **A native binary run once per command** (#6117 as originally designed).
3. **A resident daemon per worktree** (the charter service precedent, ADR 2026-10-03-1).
4. **A resident Java write service per repository, behind the CLI's EventBridge port** (chosen).

## Decision Outcome

**Chosen option:** "A resident Java write service per repository, behind the CLI's EventBridge port". It is the only option that:
- gives one writer and one implementation;
- reuses the read side's models;
- keeps storage swappable;
- avoids a start per transition.

All lane worktrees of a repository then share one writer.

### D-1: the canonical event writer is the Java write service

- The command side of the Mission Write API (#6117) is the one module that persists events. Every event log ADR 2026-10-14-1's Confirmation names is written only by its `event-log` module:
  - `status.events.jsonl`, `canonical-events.jsonl`, `run.events.jsonl`, `decisions.events.jsonl`, `mission-events.jsonl`, `kitty-ops/*.jsonl` and the glossary logs.
- The modules are #6117 decision 12's four: `domain-model`, `event-log`, `query-service` and `command-cli`. `command-cli` is now the write-service deployable (D-2). There is no second Java write build: #6185's producer folds into these modules, landing in #6193.
- Python keeps no in-process append once a file has moved.

### D-2: one resident service per repository

- **Unit.** One write service per repository. Reading "per repository" as "keyed on the git common dir" is *(derived)*. Under that reading:
  - every lane worktree, the coordination worktree and the repository root checkout of that repository talk to the same service;
  - the service is keyed where core already keeps its write locks (`<git-common-dir>/spec-kitty-locks/`).
- **Launch.** The CLI starts it when it is down and reuses it while it runs: the launch-when-down choice of ADR 2026-10-03-1 *(derived)*.
- **Reach.** It is local only and serves write operations only. The transport, token and identity check are open question 3.
- **Not per worktree.** A per-worktree daemon would split one repository's writes across processes and bring back cross-process locking. A per-command binary pays a start on every transition.

### D-3: the CLI decides when and what; the service decides how and where

- **The CLI** owns the domain decision. The run loop and the transition shells call the Python **EventBridge port**. The port of ADR 2026-10-14-1 D-2 is kept (grown from `RuntimeEventEmitter`); only its adapter changes (amended). The port's adapter in `specify_cli` sends a **command** with its request context: Mission identity, work package, intended transition, actor, evidence, and the caller's checkout.
- **The service** owns how and where:
  - It validates the command against the lane state machine and guards (open question 1).
  - It resolves the write location: which partition, worktree and branch.
  - It stamps git-derived evidence (`policy_metadata.lane_head`), appends and commits.
  - It returns the persisted event or a named refusal.
- **Write location during the strangler.** Resolving the location is today the Python placement seam (`mission_runtime` `PlacementSeam.write_dir`). Until that rule set is ported, the CLI sends the resolved write location in the request context and the service verifies it. Then the resolution moves into the service (open question 2).

### D-4: git and synchronous consumers run inside the service's unit of work *(derived)*

- **One unit of work.** The append, the status commit (where the topology commits status) and the cut-on-failure happen in one unit of work inside the service. The `lane_head` probe moves into the service's `GitPort`. This replaces `BookkeepingTransaction`'s in-process `safe_commit` and `_cut_event_log` (`coordination/transaction.py`). ADR 2026-10-14-1 D-5's synchronous consumers move here.
- **Asynchronous consumers** stay where they are: the produce seam `status/adapters.py`, derived projections and the read API by cursor. They run after the service returns, or read the committed ledger by cursor.
- **Exclusion.** The service serializes writes to one repository in process. While Python writers still exist, it also takes the same OS lock files with `flock(2)` semantics (through FFM), not with `FileChannel.lock`.
- **Handover.** Ownership of a log file is handed over **whole**, one file at a time. No file has a Python writer and a Java writer in the same release. The #6193 lock-interop spike is the go/no-go for the first handover.

### D-5: native first, JVM jar as fallback, and no Python writer

- **Fallback order** (ruled: the JVM jar fallback).
  1. The service runs from a native image where one ships for the platform. No native image exists yet: #6185 self-reports native feasibility on Linux x86_64, macOS arm64 and Windows x86_64, and the support matrix is set at release.
  2. Otherwise it runs the same build as a JVM jar on a local JDK.
  3. *(derived)* With neither available, every write refuses with a named error code and a remedy, and nothing is written. Read-only commands keep working.
- *(derived)* **No Python fallback writer.** A fallback writer would be a second implementation of the format, lock and fold (charter: single canonical authority; ADR 2026-10-14-1 D-1). #6185's warn-and-continue `binary-missing` behaviour is rejected, because it silently drops rows from the log that is the sole authority for lane state.

### D-6: storage is a port; only the file adapter ships *(derived from the ruled alternate deployments)*

- `EventLogPort` is a storage abstraction from the first Java write, and the only adapter that ships is the local file ledger.
- A database or hosted adapter is **not** a drop-in replacement under the current decisions:
  - the git-committed ledger is the publication seam (ADR 2026-10-13-2 D-2);
  - the read API pulls the committed ledger (ADR 2026-10-01-2 D-6);
  - merge semantics are file based (ADR 2026-02-09-3);
  - the consolidation gates rely on git ancestry and on `lane_head` stamps.
- Each of those needs its own ADR before such an adapter is built.
- This decision adds no hosted surface to open-core (#6164 stands).

### D-7: byte-exact contract for every row the service writes *(derived)*

- **Encoder.** The service encodes rows to the bytes the CLI writes today. That means `store.serialize_event_line`'s `json.dumps(sanitize_event_for_log(row), sort_keys=True)` for status rows, and the `persistence.append_event` bytes for contract rows.
- **Fixtures.** `spec-kitty-events` gains a `status_append` fixture family, generated from core's writer, beside `ledger_append`. Both gate the Java writer byte for byte, through the Java binding of events#92.
- **Append semantics.** Which semantics are authoritative is settled in the same step: core's temp-file-and-replace, or the contract's single `O_APPEND` write.

### D-8: the read service stays read-only and separate *(derived)*

- `query-service` (`services/mission-status-api/`) keeps its guarantees: loopback-only, never writes, takes no lock, starts no process.
- The write service is its own deployable, sharing `domain-model`.
- The read API stays conformance-gated against the Python reducer. #6268 (porting the #4941 approved-departure lift to the Java `StatusReducer`) lands before the shared domain model is used to validate writes.

### Consequences

#### Positive

- One writer and one implementation for every event log, across the CLI and any future deployment.
- The read and write sides share one domain model.
- A transition costs a local request to a warm service, not a process start.
- Ownership is explicit: the domain decides, the service persists.
- Storage can change behind one port without touching the CLI.

#### Negative

- A JVM toolchain, a native-image platform matrix, a JVM fallback and a port of the git policy sit on the event-writing critical path.
- The CLI's write path depends on a local service's lifecycle: launch, identity, token and crash recovery. Its launcher needs the same security review ADR 2026-10-03-1 requires for the charter service.
- "One canonical writer" now spans two languages, so it needs two gates.
- The lane state machine and guards must move, or be kept in parity, across languages.

#### Neutral

- ADR 2026-10-14-1's D-3, D-3a and D-4 are unchanged. The writer still writes only `spec-kitty-events` contract events, every event carries both version markers, and the internal lifecycle events are retired.
- The read API is unchanged.

### Confirmation

- **Python side:** the multi-file writes gate (#6603) shows no module appends to any event log once that file has moved, with an empty allowlist at the end of the migration.
- **Java side:** an ArchUnit rule shows only the `event-log` module opens a ledger for writing.
- **Bytes:** the `ledger_append` and `status_append` fixtures pass byte for byte against the Java writer.
- **One service per repository:** two worktrees of one repository reach the same service; a second repository gets its own.
- **Fail closed:** with no native image and no JDK, a write refuses with the named code and the log is byte-identical.
- **Consolidation:** `tests/consolidation/` passes unchanged over logs that mix rows from both writers, at each cut-over step.

### Migration order (each step gated on the previous) *(derived; a default the operator may resequence)*

0. **Python EventBridge port** behind the two existing doors (`status/emit.py` `_persist_prepared`, `coordination/transaction.py` `BookkeepingTransaction.append_events`), plus the multi-file writes gate. No behaviour change (#6603).
1. **Extract** `domain-model` and `event-log` (#6192).
2. **Java binding** plus the `status_append` fixture family (events#92).
3. **Lock-interop spike** (go/no-go), then the service writes **one file owned whole**. The glossary logs are the candidate, since they already use the contract writer (#6193).
4. **The service takes `status.events.jsonl`**: every row family in one cut, commit and cut inside the service, and the Python appenders deleted in the same release.
5. **The remaining logs:** run journal, decisions, Op records and lifecycle (ADR 2026-10-14-1 D-4). Then the `accept` writes, then the consolidation bookkeeping writes.

### Open questions (each with a default)

1. **Who validates a transition?**
   - **Default:** the service is authoritative and runs the ported lane state machine and guards, with a parity corpus against `status/wp_state.py`.
   - The CLI may pre-check only for messages.
   - Until the port lands, the service accepts a transition `prepare_transition` has validated and re-checks only `from_lane` continuity against its reducer.
2. **When does write-location resolution move into the service?**
   - **Default:** at step 4.
   - Before then, the request carries the resolved write location and the service verifies it.
3. **Transport and trust model.**
   - **Default:** a local socket (a named pipe on Windows) rather than TCP.
   - A per-repository token in the git common dir, readable only by the user.
   - An identity check before each session, and write operations only.
   - A security note precedes step 3.
4. **Idle shutdown.**
   - **Default:** the service exits after a period with no requests, and the CLI relaunches it on demand.
   - A crashed service is detected by the identity check and relaunched. A write is acknowledged only after it is durable: after its commit where the topology commits status, and after the fsynced append where it does not (the flat shell, `status/emit.py`).
5. **Several clones of one repository.**
   - **Default:** one service per git common dir, so separate clones get separate services.
   - Worktrees of one clone share one.

## Amendment 2026-10-27 (Accepted): loopback HTTP transport, rows during the strangler, one synced O_APPEND write

[ADR 2026-10-27-1](2026-10-27-1-the-write-service-protocol-is-loopback-http-with-a-bearer-token.md) settles points this record left open, by operator ruling of 2026-10-25 (#6675) and as derived there:

- **Open question 3 (transport and trust model).** The default of a local socket is replaced: the service listens on `127.0.0.1` only, on a random port, and the port and a random bearer token are written to a file in the git common dir, owner-only. The identity check before writes is the handshake of ADR 2026-10-27-1 D-4.
- **D-3 (the CLI sends a command).** During the strangler the request carries the rows the CLI built, with their context; the command form, in which the service also stamps `policy_metadata.lane_head` itself, arrives with migration step 4.
- **D-7 (append semantics).** The single `O_APPEND` write of full JSON lines, synced before the acknowledgement, is authoritative; a multi-event operation is one write and one `fsync`. Windows semantics follow the lock-interop spike (#6193).

Nothing else in this record changes.

## Pros and Cons of the Options

### Python in-process EventBridge

- **Pros:** the cheapest for 4.0.0; no new runtime.
- **Cons:**
  - The write domain stays in Python while the read domain is Java, so the models are kept twice.
  - Storage cannot change without touching the CLI.
  - #6117's and #6185's Java work becomes a second writer to reconcile later.

### A native binary run once per command

- **Pros:** nothing resident; works offline; no service lifecycle.
- **Cons:**
  - A process start on every transition.
  - No home for alternate deployments.
  - Every invocation re-reads and re-folds state.

### A resident daemon per worktree

- **Pros:** follows the charter-service precedent.
- **Cons:**
  - One repository's writes are split across processes, so cross-process locking comes back.
  - Lane worktrees of one Mission would talk to different writers.
  - It defeats the point of a backend service.

### A resident Java write service per repository (chosen)

- **Pros:** one writer per repository; warm state; clear ownership; storage behind a port; shares the read models.
- **Cons:** a service lifecycle and a JVM toolchain on the write path; a security-reviewed launcher; a cross-language parity burden during the migration.

## More Information

- The current-state map and gap table: [event ledger writers and readers](../../architecture/event-ledger-writers-and-readers.md).
- Contributor rules: [Events in core](../../development/reference/events-in-core.md).
- `spec-kitty-events`: `docs/api/ledger-write-contract.md`, `src/spec_kitty_events/conformance/fixtures/ledger_append/README.md`.
- The read service: `services/mission-status-api/README.md`.
