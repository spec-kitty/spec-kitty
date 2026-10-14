---
title: 'ADR: the event ledger is the publication seam, on by default, with a versioned row contract and local-log retention'
description: 'Integrations read the committed ledger through a versioned row schema in spec-kitty-events; publication is on by default, apart from hosted drain; local logs get retention.'
status: Accepted
date: '2026-10-13'
---

# The event ledger is the publication seam, on by default, with a versioned row contract and local-log retention

**Status:** Accepted (2026-10-13). The operator gave the direction on 2026-10-13: a versioned row schema in spec-kitty-events, publication on by default, and a retention or cleanup policy; accepted when the operator merged this pull request into `main`.

**Date:** 2026-10-13

**Deciders:** Stijn Dejongh (operator).

**Technical Story:**
- This is the produce/drain decision that the [4.0.0 milestone roadmap](../../plans/4-0-0-milestone-roadmap.md) lists as a next step. It amends that roadmap's item 3 ("each behind its own toggle"): this record rejects a publication toggle (see Considered Options).
- It amends the hosted-posture contract of mission `hosted-opt-in-drain-ledger-01M3FFEV` (`kitty-specs/hosted-opt-in-drain-ledger-01M3FFEV/contracts/hosted-posture.md`), whose drain-off line says "fan-out, producers, live-work, the widen prereq probe return silently". After this record the fan-out and the runtime moment producer no longer return on drain off; only the hosted handlers do.
- It amends [ADR 2026-09-26-3](../3.x/2026-09-26-3-hosted-interaction-opt-in.md), D-1 and D-2.
- It builds on the 2026-10-12 amendments to [ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md) and [ADR 2026-10-06-1](2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md).
- It retires, as follow-up debt, the `canonical-producer-exempt` markers that still cite the closed issues #1198 and #1248, and the eight `#1200` markers on the local glossary JSONL fallback (`src/glossary/events.py`).

**Reader:** a maintainer changing what the CLI writes to its event logs, how an integration reads them, or what the CLI may delete.

---

## Context and Problem Statement

The CLI already keeps an event ledger. Every lane transition is appended to the Mission's committed `status.events.jsonl` by `emit_status_transition` (`src/specify_cli/status/emit.py`, then `status/store.py::append_event_stream_atomic_verified`). Lifecycle and decision rows join that file. Decision input events go to `decisions.events.jsonl`. `spec-kitty next` writes its step events to a per-run journal, `.kittify/runtime/runs/<run>/run.events.jsonl` (`src/runtime/next/_internal_runtime/engine.py::_append_event`). ADR 2026-09-26-3 (D-2, FR-010) makes these committed records a non-optional floor, and no setting stops them being written.

The direction is now Pub, ledger, Sub:
- Runtime transitions produce events.
- The ledger keeps them.
- Integrations consume them from a separate package (`spec-kitty/event-router`).
- Producers and consumers know only the shared contracts in `spec-kitty-events`, not each other.
- The CLI is planned to offer services as integration points to the ledger (the Mission Status Read API of ADR 2026-10-01-2 is the first one). Traceability, dashboards and integrations all depend on the ledger being readable and published.

Three facts block that today:

1. **The ledger rows have no contract.**
   - The CLI writes them from its own `StatusEvent` dataclass (`status/models.py`) and from local envelopes. Lifecycle rows use `schema_version "5.0.0"` and carry an `aggregate_type` (`status/lifecycle_events.py::_build_envelope`). The run journal row has no `event_id` and no version.
   - `spec-kitty-events` publishes the canonical `Event` envelope 3.0.0 and typed payload schemas, but the on-disk row exists there only as the `diary.StatusEvent` dataclass. That dataclass has no JSON schema and no row version, and it silently drops the CLI's `reason_source`.
   - The package itself states that local rows are not canonical (`contracts/versioning-and-compatibility.md`).
   - A consumer that reads the ledger therefore depends on CLI internals.
2. **Publication is welded to hosted drain.** `status/adapters.py` is a clean, transport-free callback seam. Its `fire_*` functions return early unless `hosted_posture.drain_posture().enabled`, so the gate sits on the **seam**, not on the hosted handler. Drain is off by default and stays off: the hosted backend is frozen (ADR 2026-10-06-1). As long as the gate lives there, no integration can be told about an event without also turning on the hosted relay.
3. **Nothing cleans up the local logs.** The per-run journals, `.kittify/events/`, `.kittify/derived/` and the `kitty-ops/ops-index.jsonl` cache grow without bound. There is no retention code for any of them.

## Decision Drivers

- **One contract for producers and consumers** (charter: single canonical authority; shared package boundary). A Java or other non-Python consumer must be able to implement it.
- **Local-first and drain-independent.** Producing an event never depends on whether a hosted drain is on (ADR 2026-10-06-1, Amendment 2026-10-12).
- **The committed record is never lost.** `status.events.jsonl` is the sole authority for lane state, and the floor of FR-010 holds.
- **Nothing hosted turns on by default.** Zeitgeist, auth and the SaaS surface stay frozen and opt-in.
- **Bounded local growth**, with no risk to an in-flight run.

## Considered Options

### The row contract

1. **A versioned ledger-row schema in spec-kitty-events (chosen, operator ruling 2026-10-13).**
2. Write canonical 3.0.0 `Event` envelopes into the ledger, replacing the flat rows.
3. Keep the rows CLI-internal and expose only the read API.

### Publication

1. **The ledger is the publication; subscribers read it by cursor. Publication is on by default, and the drain gate moves from the seam onto the hosted handlers (chosen).**
2. Turn `hosted.drain` on by default.
3. Keep publication behind drain and add a second toggle for local subscribers.

### Retention

1. **Two tiers: committed ledgers are never pruned; local logs get a policy (chosen).**
2. One policy for every log.
3. No retention.

## Decision Outcome

### D-1: the ledger row is a versioned contract in spec-kitty-events

`spec-kitty-events` publishes a JSON Schema for each row kind the CLI persists, with a row-level version marker. Producers and consumers both build against those schemas:
- the status transition row;
- the inner-state annotation row;
- the lifecycle row;
- the decision row in `status.events.jsonl` and in `decisions.events.jsonl`;
- the run-journal row;
- the glossary event row in `.kittify/events/glossary/<mission_id>.events.jsonl` (`src/glossary/events.py`), including the `StepCheckpointed` row a step resumes from.

The schemas follow the package's existing versioning rules (`contracts/versioning-and-compatibility.md`): a new row kind or an optional field is a minor change, and a changed required field or a changed accept/reject behaviour is a major one. The package also documents the file-level rules a reader needs: which row kinds share a file, how a reader tells them apart, and that a reader ignores a kind it does not know. Today those rules exist only in Python docstrings (`diary.py`).

The CLI then writes from the package's models, not from its own `StatusEvent`:
- `reason_source` either joins the schema or is dropped;
- `Lane` is defined once;
- the run journal gains an `event_id` and the row version.

The `canonical-producer-exempt` markers (#1198, #1248, #1200) are retired once every persisted line validates against its row schema, and a producer gate checks persisted lines, not only payloads.

**Release order (shared-package boundary).** The row schemas ship in a `spec-kitty-events` minor release first. The CLI then raises its floor (today `spec-kitty-events>=10.4.6,<11` in `pyproject.toml`) and extends `tests/contract/spec_kitty_events_consumer/` before any writer migrates. A row with no version marker reads as version 1 and is never rewritten, so committed history, and the archive freeze of [ADR 2026-10-11-1](2026-10-11-1-archive-freeze-verifies-reducer-outcome-not-byte-identity.md), stay valid.

The canonical 3.0.0 `Event` envelope stays the wire contract for anything that leaves the machine. The row schema is the contract for anything that reads the ledger.

### D-2: the ledger is the publication seam, and publication is on by default

A subscriber learns about events by reading the ledger, never by being called by the CLI. The supported read paths are:
- `spec-kitty events tail`, with its cursor (`status/tail_reader.py::TailCursor`);
- the Mission Status Read API, with its overview cursor and the planned SSE change stream (ADR 2026-10-01-2).

Today `events tail` reads only the Mission's `status.events.jsonl`, and its `--json` flag has no effect, because JSON is the only output mode (`cli/commands/events.py`). `decisions.events.jsonl`, `.kittify/canonical-events.jsonl` and the run journals have no tail path yet; adding one is follow-up work.

These need no daemon in the CLI, and they need no knowledge of the subscriber. That is what makes "producers and consumers do not need to know about each other" true. `spec-kitty/event-router` is such a subscriber.

The in-process fan-out seam in `status/adapters.py` stays transport-free, but the drain gate moves off it:
- The `fire_*` functions no longer read `drain_posture()`.
- The runtime moment producer (`events/runtime_moments.py`) drops its own drain check and always calls the seam.
- Only the Zeitgeist handlers in `status/zeitgeist_bridge.py` check drain, before codec or credential work, and return when it is off.
- The `SPEC_KITTY_NO_MOMENT_HANDLERS` / `SPEC_KITTY_SYNC_DISABLE` registration gate keeps binding only those hosted handlers.
- Any local, in-process adapter registered on the seam therefore fires by default, and the hosted relay stays silent by default.

**Publication on by default** therefore means two things:
- the ledger and its read paths are always available, which they already are under FR-010;
- the seam fires for local adapters without an opt-in.

**`hosted.drain` stays off by default, is unchanged in meaning, and still gates every hosted edge.** No new toggle is added for publication.

`ledger.projection` (default `true`) keeps its narrow meaning from ADR 2026-09-26-3, D-2: it gates only the derived, gitignored read model under `.kittify/derived/`.

### D-3: retention has two tiers

**Committed tier: never pruned by the CLI.**
- These files are tracked by git: `status.events.jsonl`, `decisions.events.jsonl`, the Mission's `mission-events.jsonl`, `.kittify/canonical-events.jsonl`, the decision ledger (`decisions/`) and committed Op records (`kitty-ops/<id>.jsonl`). Their history is git's to keep.
- A finished Mission is archived under the archive-freeze rule of [ADR 2026-10-11-1](2026-10-11-1-archive-freeze-verifies-reducer-outcome-not-byte-identity.md), not truncated.
- No retention setting may delete or rewrite a committed row.

**Local tier: a retention policy, cleaned by an explicit command.** The gitignored local logs and caches are:
- `.kittify/runtime/runs/<run>/` (the run journal);
- `.kittify/events/`;
- `.kittify/derived/` (always rebuildable);
- `kitty-ops/ops-index.jsonl` (a cache of the durable Op records).

These are kept under a policy read from `.kittify/config.yaml`:

```yaml
ledger:
  projection: true          # unchanged (ADR 2026-09-26-3, D-2)
  retention:
    keep_runs: 20           # proposed default: keep at least the newest N runs
    max_age_days: 30        # proposed default: and every run newer than this
```

Eligibility applies alike to a run directory under `.kittify/runtime/runs/` and to a per-Mission log under `.kittify/events/` (for example `.kittify/events/glossary/<mission_id>.events.jsonl`). An item is eligible for cleanup only when all of these hold:
- it is outside both limits;
- its Mission is not open;
- it holds no lock;
- for a `.kittify/events/` log, its Mission has no unfinished step. `glossary/checkpoint.py::load_checkpoint` reads the `StepCheckpointed` rows of every `.kittify/events/glossary/*.events.jsonl` to resume a step, so pruning that log would lose the resume point.

Deleting a run directory also removes its entry from `.kittify/runtime/feature-runs.json`, under that index's own lock (`runtime/next/run_index.py::index_lock`), so the index never names a run that is gone.

Durable Op records (`kitty-ops/<op-id>.jsonl`) are tracked and never pruned; only the `kitty-ops/ops-index.jsonl` cache is in scope.

Cleanup never touches the committed tier. It is done by an explicit, dry-run-first command in the `doctor` family, and automatically only where the operator has opted in. A rebuildable cache (`.kittify/derived/`, `ops-index.jsonl`) may be deleted at any time, because it is recomputed on the next read.

The default numbers above are a proposal for the operator to confirm.

### Follow-up debt

- The seam's slots and registration functions are still named after the retired SaaS fan-out (`register_saas_fanout_handler`, `register_lifecycle_saas_fanout_handler`, `fire_saas_fanout`, `fire_lifecycle_saas_fanout` in `status/adapters.py`). Local adapters would register into slots called `saas_fanout`; renaming them to transport-neutral names is recorded here as follow-up debt.
- A tail path for `decisions.events.jsonl`, `.kittify/canonical-events.jsonl` and the run journals (D-2).

### Consequences

#### Positive

- An integration such as event-router can be built against a published, language-neutral contract and never reaches into CLI internals.
- Traceability, dashboards and integrations work on a default install, with nothing hosted switched on.
- The hosted relay keeps its two-scope opt-in. Moving the gate onto its handlers makes that opt-in more precise, not weaker.
- Local disk use is bounded, with no risk to the record of what happened.

#### Negative

- `spec-kitty-events` takes on schemas for rows that were CLI-internal, and the CLI must migrate its writers to the package models. That is the #1198 / #1248 debt, now scheduled.
- Moving the drain gate changes a guarantee callers may rely on ("an empty seam when drain is off"). Tests that pin the seam-level gate move to the handlers.
- A row-schema change becomes a cross-repository release, like any other contract change in `spec-kitty-events`.

#### Neutral

- The read API (ADR 2026-10-01-2) is unchanged. It already reads the committed ledger and stays read-only and independent of drain.
- `hosted.drain`, `[hosted] drain` and the hidden hosted CLI entries are unchanged.

### Confirmation

- Every line the CLI persists, glossary event rows included, validates against its `spec-kitty-events` row schema in a producer gate, and every `canonical-producer-exempt` marker (#1198, #1248, #1200) is gone.
- With drain off, a test adapter registered on `status/adapters.py` is called on a lane transition, and the Zeitgeist handler makes no network call.
- With drain on (both scopes), the hosted handler fires as before.
- An architectural test pins that every handler registered by `ensure_zeitgeist_moment_handlers` checks drain first.
- The cleanup command, run against a fixture with open and closed Missions, deletes only eligible local runs and logs, removes their `feature-runs.json` entries, keeps every log of a Mission with an unfinished step, and never changes a tracked file.

## Pros and Cons of the Options

### Row contract: canonical 3.0.0 envelopes in the ledger

**Pros:** one shape on disk and on the wire. **Cons:** it rewrites the authoritative file's format. The reducers, migrations, archive freeze and every replay golden would move at once, and the envelope carries fields (build, node, Lamport) the local file has no use for. Rejected by the operator in favour of a row schema.

### Row contract: rows stay internal, read API only

**Pros:** least work. **Cons:** every consumer depends on CLI internals or on the CLI process. It contradicts "producers and consumers know only the shared contracts".

### Publication: `hosted.drain` on by default

**Pros:** no code change. **Cons:** it turns the frozen hosted relay on for every install and reverses ADR 2026-09-26-3, which the operator does not want.

### Publication: a second toggle for local subscribers

**Pros:** explicit. **Cons:** it adds a setting for something that should simply work, and it leaves the drain gate on the seam, where it does not belong.

### Retention: one policy for every log

**Pros:** simple. **Cons:** a policy that can reach the committed ledger can destroy the sole authority for lane state.

## More Information

- [ADR 2026-09-26-3](../3.x/2026-09-26-3-hosted-interaction-opt-in.md), hosted interaction opt-in: D-1 unchanged in meaning (the gate moves from the seam to the hosted handlers); D-2 unchanged, now with a `ledger.retention` sibling.
- [ADR 2026-10-01-2](2026-10-01-2-mission-status-read-api-and-dashboard-extraction.md), the producer read surface.
- [ADR 2026-10-06-1](2026-10-06-1-team-kitty-surfaces-are-hidden-unless-drain-is-on.md), Amendment 2026-10-12, which unblocked the adapter seam.
- [ADR 2026-10-11-1](2026-10-11-1-archive-freeze-verifies-reducer-outcome-not-byte-identity.md), the archive freeze for the committed tier.
- `spec-kitty-events`: `contracts/versioning-and-compatibility.md` (the versioning rules the row schema follows) and `diary.py` (the current row model and reducer).

## Amendments

- **2026-10-14:** the hosted surfaces this ADR fences were removed from open-core by #6164; the code is preserved in spec-kitty/event-router.
- **Amended by [ADR 2026-10-14-1](2026-10-14-1-event-native-core-one-canonical-event-writer.md)** (an event-native core with one canonical event writer). D-1's row list loses the lifecycle row: the internal lifecycle events are retired, and their facts are written as canonical `spec-kitty-events` events. One module, the EventBridge, writes every row D-1 lists. D-1's row schema is read as the persisted form of a canonical `spec-kitty-events` event: the package's row envelope, whose `schema_version` is the row-level version marker, around the typed payload. It is not a second, CLI-owned schema, and it is not the 3.0.0 wire envelope (ADR 2026-10-14-1, D-3a). D-2 and D-3 are unchanged.
