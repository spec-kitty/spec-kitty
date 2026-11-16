---
title: 'Context: System Events'
description: "Glossary context for system events: Spec Kitty's append-only event model, replay behavior, and system-level event types like the event envelope."
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: internal/lead-developer
  guidance_text: Read this to know which event logs and event types exist, how status events are ordered, and how events tail resumes.
- profile: internal/ai-collaboration-agent
  guidance_text: Read this before consuming events tail output or naming an event type, so the names and ordering match the code.
related:
- context/dossier
- context/execution
- context/identity
- context/orchestration
---
## Context: System Events

Terms describing Spec Kitty's append-only event model, replay behavior, and system-level event types.

### Event Envelope

| | |
|---|---|
| **Definition** | Standard wrapper for an emitted event, including identity, ordering, and payload fields. |
| **Context** | System Events |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Common fields** | `event_id`, `event_type`, `aggregate_id`, `lamport_clock` (optional), `payload` (the `Event` model in `spec_kitty_events.models`) |

---

### Glossary Evolution Log

| | |
|---|---|
| **Definition** | Append-only sequence of glossary-related events that records candidate extraction, semantic checks, clarifications, and sense updates. Stored per Mission in `.kittify/events/glossary/<mission_id>.events.jsonl` (`src/glossary/events.py`). |
| **Context** | System Events |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Semantic Check](./execution.md#semantic-check), [Clarification Prompt](./execution.md#clarification-prompt) |

---

### Glossary Scope

| | |
|---|---|
| **Definition** | Bounded semantic scope used for term/sense resolution. |
| **Context** | System Events |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Allowed values** | `spec_kitty_core`, `team_domain`, `audience_domain`, `mission_local` (`GlossaryScope` in `src/glossary/scope.py`) |

---

### Semantic Check Evaluation

| | |
|---|---|
| **Definition** | Deterministic pre-generation evaluation of extracted terms against active glossary scopes. |
| **Context** | System Events |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Block rule** | Depends on the glossary strictness (`src/glossary/strictness.py`): `off` never blocks, `medium` blocks on an unresolved high-severity conflict, `max` blocks on any unresolved conflict |

---

### Replay

| | |
|---|---|
| **Definition** | Reconstructing effective glossary state and decisions from canonical append-only events. |
| **Context** | System Events |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Invariant** | No side-channel state may be required for correctness |

---

### Telemetry (Out of Scope for This Slice)

| | |
|---|---|
| **Definition** | Optional usage/cost analytics and operational observability fields layered on top of core event contracts. |
| **Context** | System Events |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Note** | Not required for glossary semantic integrity in this 2.x adoption slice |

---

### Dossier Event

| | |
|---|---|
| **Definition** | An event emitted during dossier operations. Four types: `MissionDossierArtifactIndexed` (artifact scanned), `MissionDossierSnapshotComputed` (snapshot created), `MissionDossierArtifactMissing` (required artifact not found), `MissionDossierParityDriftDetected` (content changed since baseline). |
| **Note** | The four emitters in `src/specify_cli/dossier/events.py` are defined, but no code path in `src/` calls them today. |
| **Context** | System Events |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Mission Dossier](./dossier.md#mission-dossier), [Anomaly Event](#anomaly-event), [Event Envelope](#event-envelope) |

---

### Anomaly Event

| | |
|---|---|
| **Definition** | An event that is only emitted when something unexpected happens — such as a required artifact being missing or parity drift being detected. Unlike routine lifecycle events, anomaly events signal conditions that may need the Human-in-Charge's attention. |
| **Note** | The dossier anomaly events (`MissionDossierArtifactMissing`, `MissionDossierParityDriftDetected`) are not emitted by any code path in `src/` today; see [Dossier Event](#dossier-event). |
| **Context** | System Events |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Dossier Event](#dossier-event), [Human-in-Charge (HiC)](./identity.md#human-in-charge-hic) |

---

### WPStatusChanged

| | |
|---|---|
| **Definition** | The event type that carries a work package's move from one status lane to another (e.g., from `planned` to `claimed`). Part of the status model's event contract: the CLI writes each move as a `StatusEvent` row in `status.events.jsonl`, and `build_status_event_payload` (`src/specify_cli/status/wire_payload.py`) renders that row as a `WPStatusChanged` payload. |
| **Context** | System Events |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [work package](./orchestration.md#work-package), [Lane](./orchestration.md#lane), [Event Envelope](#event-envelope) |

---

### Lamport Clock

| | |
|---|---|
| **Definition** | A logical counter included in event envelopes that tracks the order events happened in, without relying on wall-clock time. Each new event increments the counter, ensuring events can be reliably ordered even across different machines. |
| **Note** | The field is optional in the envelope. The CLI's status lane transitions carry no Lamport clock, and the status reducer orders them by the writer's `at` timestamp, then `event_id` (ADR [2026-02-09-3](../adr/2.x/2026-02-09-3-event-log-merge-semantics.md), Amendment 2026-10-22). Do not describe the status path as Lamport-ordered. |
| **Context** | System Events |
| **Status** | canonical |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Event Envelope](#event-envelope), [Replay](#replay) |

---

### Tail cursor

| | |
|---|---|
| **Definition** | The reader's resumable position in `spec-kitty events tail` -- a byte offset into the selected log of a named Mission (`status.events.jsonl` by default; `--log` selects `decisions`, `mission`, `run`, `glossary`, `ops` or `canonical`), plus a content invariant (a fixed-size SHA-256 hex digest of the last-consumed line/boundary bytes at that offset, never the raw bytes themselves) used to re-verify on every poll that growth at that offset is a true continuation and not a rollback-then-regrow landing back at or above the same size. Always caller-supplied/caller-owned: `events tail` is stateless across invocations and never persists cursor or resume state to disk anywhere. |
| **Context** | System Events |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Distinct from** | [Event Envelope](#event-envelope) -- a Tail cursor is reader-side position/verification state (offset + content-invariant digest), never a wrapper around an emitted event's own identity/ordering/payload fields (`event_id`/`event_type`/`aggregate_id`/`lamport_clock`/`payload`). |
| **Related terms** | [Tail envelope](#tail-envelope), [resume token](#resume-token) |

---

### resume token

| | |
|---|---|
| **Definition** | The `(offset, content_invariant)` pair a consumer of `spec-kitty events tail` persists across restarts and supplies back via `--from-offset`/`--from-invariant`, so a cold-started process can resume where a prior run left off. Persisting the offset alone (with no invariant) only enables structural resume validation; supplying both enables FR-013's cross-restart content-mismatch check, which refuses the resume (structured stderr error, non-zero exit, no Tail envelope emitted) rather than silently trusting a stale or rolled-back-then-regrown position. |
| **Context** | System Events |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Distinct from** | [Event Envelope](#event-envelope) -- a resume token is the consumer's own persisted `(offset, content_invariant)` value, never an emitted event's `event_id`/`lamport_clock`-shaped wrapper; also distinct from [Tail cursor](#tail-cursor), which is the reader's own live in-memory position -- a resume token is what a consumer chooses to durably persist FROM a Tail cursor's offset/invariant, across process restarts, never automatically. |
| **Related terms** | [Tail cursor](#tail-cursor), [Tail envelope](#tail-envelope) |

---

### `log_truncated`

| | |
|---|---|
| **Definition** | The Tail envelope stream's truncation-resync signal shape, emitted when `spec-kitty events tail` detects a rollback (a size shrink, or a truncate-then-regrow whose content invariant no longer matches at the previously-consumed offset) while running. Carries a `"type": "log_truncated"` discriminator (absent from ordinary pass-through rows), a `reason` of `"size_shrink"` or `"content_mismatch"`, the `detected_at_offset`, and a resync `tail_offset`/`tail_invariant` pair at offset 0 -- never silently absorbed as "no new data." |
| **Context** | System Events |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Distinct from** | [Event Envelope](#event-envelope) -- `log_truncated` is one of the Tail envelope stream's own signal shapes, never a `StatusEvent`/canonical-Event-Envelope row; its `"type"` discriminator is exactly what lets a consumer tell the two apart on the same stream. |
| **Related terms** | [Tail envelope](#tail-envelope), [Tail cursor](#tail-cursor) |

---

### Tail envelope

| | |
|---|---|
| **Definition** | One JSON line emitted on stdout by `spec-kitty events tail` in `--json` mode (#6611) -- either a pass-through of an existing line of the selected log (for the default status log, a `StatusEvent` dict as already serialized by `store.py`), or one of the two new signal shapes this command defines: the [`log_truncated`](#log_truncated) truncation-resync signal (FR-005/FR-007) and a resolve-failure/error signal (FR-009), the latter emitted on stderr only, never on the stdout Tail-envelope stream itself. Every pass-through envelope also carries the offset and content-invariant value immediately past the emitted event, so a consumer can persist both (as a [resume token](#resume-token)) without deriving them itself. Without `--json` the command prints one human-readable plain-text line per event instead (the reader-injected cursor keys omitted); the Tail envelope is the machine channel. |
| **Context** | System Events |
| **Status** | candidate |
| **Applicable to** | `3.x` |
| **Distinct from** | [Event Envelope](#event-envelope) -- the canonical Event Envelope term names a differently-shaped wrapper (`event_id`/`event_type`/`aggregate_id`/`lamport_clock`/`payload`); a Tail envelope here is always either a raw line of the selected log (a `StatusEvent` JSON line for the status log) or one of `events tail`'s own signal shapes, never that canonical schema. |
| **Related terms** | [Tail cursor](#tail-cursor), [resume token](#resume-token), [`log_truncated`](#log_truncated) |
