---
title: "TO-BE design — Local event producer re-route (spec-kitty-events producer seam)"
mission: issue-6164-remove-hosted-from-core
follow_on_to: 6164
milestone: 11
status: design / to-be / follow-on (NOT part of #6164)
updated: 2026-10-13
authors: architect (stijn.dejongh@sddevelopment.be)
---

# TO-BE design: make mission lifecycle & status events the LOCAL producer of `spec_kitty_events`

> **Scope marker.** This is a **milestone-11 follow-on** design, deferred from
> issue **#6164** (which only *removes* the frozen hosted/sync/drain surfaces).
> #6164 removes the only code that today builds the shared `Event` envelope
> (`status/zeitgeist_bridge.py`), and because that build happens **only on the
> drain path — which ships OFF** (ADR `2026-09-26-3`; two gates, no env var),
> removing it breaks **no current production** (drain off ⇒ nothing is produced
> in the shared format today). It does, however, delete the *only producer
> code*, so the producer/consumer split (ADRs `2026-10-01-2`, `2026-10-06-1`,
> `2026-10-12-2`) needs a replacement. **This document designs that
> replacement. It is not a work item for #6164.** No product code changes here;
> the only artifact this mission produces is this doc.

---

## 0. Problem statement (grounded)

The 2026-10-13 executive debrief ("WTF is the event ledger for?") established:

- **Producer (open-core / Build Kitty):** the free CLI must *produce*
  `spec_kitty_events` envelopes.
- **Consumer (Team Kitty / event-router):** *consumes* them across the shared
  contract boundary, never reaching into CLI internals.

Today the shared `Event` (version `3.0.0`, `spec_kitty_events.models.Event`,
`models.py:59`) is assembled in exactly **one live place**:
`status/zeitgeist_bridge.py::_broadcast_status_transition` (relocated pristine:
`/home/user/event-router/relocated/src/specify_cli/status/zeitgeist_bridge.py:154`)
and `_broadcast_lifecycle_envelope` (`:207`) — and only on the **drain/relay**
path. #6164 deletes that module (research.md §2: `status/zeitgeist_bridge.py` is
in the confirmed REMOVE-set).

What **survives** #6164 and is the foundation this design builds on:

- The **produce/fan-out seam** `status/adapters.py` stays live (ADR `2026-10-06-1`
  amendment 2026-10-12: "Producing an event never depends on whether a drain is
  enabled"). Its registry (`register_*_fanout_handler`, `fire_*_fanout`,
  `reset_handlers`) survives **handler-less** after #6164
  (`status/adapters.py:1-15`, `:191-201`). Every `fire_*` is a no-op over an
  empty list until a handler registers.
- The **local native ledgers** stay the committed authority:
  - mission status log `kitty-specs/<slug>/status.events.jsonl`
    (`status/lifecycle_events.py:126`), union-merge-driver protected
    (`status/emit.py:22-27`);
  - project log `.kittify/canonical-events.jsonl`
    (`status/lifecycle_events.py:125,184-186`);
  - decision log `kitty-specs/<slug>/decisions.events.jsonl`
    (`events/decision_log.py:131`), committed via `safe_commit`
    (`events/decision_log.py:254-272`);
  - runtime journal `.kittify/runtime/<run>/run.events.jsonl`
    (`runtime/next/_internal_runtime/engine.py:107-118`).

**The gap.** Those native ledgers carry **CLI-native row shapes**, not the
shared `Event` envelope:

- `StatusEvent.to_dict` (`status/models.py:430-454`) writes the CLI row,
  including `reason_source` (`status/models.py:418,450-451`) — a field the
  package's wire model `StatusTransitionPayload` **does not declare** and
  **forbids** (`spec_kitty_events/status.py:411-467`, `extra="forbid"`). So the
  CLI row and the shared envelope already diverge in shape.
- The lifecycle envelope is schema `5.0.0` (`status/lifecycle_events.py:308-329`),
  the shared SaaS envelope is `3.0.0`
  (`status/lifecycle_events.py:456-472::build_saas_lifecycle_queue_event`).
- The runtime journal is a package-retired schema, carried under a producer-lint
  exemption (`runtime/.../engine.py:109`: `canonical-producer-exempt: #1248`).

So with drain off, **nothing in any ledger is in the shared format**; the only
code that ever produced the shared format rode on the relay. This design makes a
**drain-independent, on-by-default local producer** that emits the shared
`Event` format from the kept core, feeding the consumer across the contract.

---

## 1. Producer boundary — extract the `Event` builder into a drain-independent core module

### 1.1 What to extract

In the pristine bridge the producer and relay are cleanly separable:

- **Producer half (keep, relocate):** `_broadcast_status_transition`
  (`zeitgeist_bridge.py:154-204`) and `_broadcast_lifecycle_envelope`
  (`:207-266`) build the `Event` 3.0.0 envelope using **only**:
  `spec_kitty_events.models.Event`, `spec_kitty_events.status.StatusTransitionPayload`,
  `spec_kitty_events.zeitgeist_attrs.PAYLOAD_MODEL_BY_EVENT_TYPE`
  (`:74-80,188-195,233,250-262`), plus `_envelope_bookkeeping` (`:615-643`),
  `_parse_stamp` (`:598-612`), and the lifecycle module's own SaaS projection
  `lifecycle_events._canonical_lifecycle_payload_for_saas`
  (`zeitgeist_bridge.py:269-280` → `status/lifecycle_events.py:394-408`). Every
  one of these is **drain-independent**.
- **Relay half (gone with #6164):** the single `_broadcast_moment(...)` call at
  the end of each builder (`zeitgeist_bridge.py:204,266`), which pulls
  `zeitgeist_client` (`:384,454,525`) → transitively `saas_client`/`auth`.
  **The producer/relay boundary is exactly `_broadcast_moment`.**

### 1.2 Proposed home

Create `src/specify_cli/status/event_envelope.py` — a pure, drain-independent
builder:

```python
# status/event_envelope.py  (NEW; proposed)
# Depends ONLY on: spec_kitty_events (models, status, zeitgeist_attrs payload
# models, strict profile) + status.lifecycle_events (canonical projection).
# NEVER imports zeitgeist_client / saas_client / auth.

def build_status_event_envelope(*, mission_slug, wp_id, metadata, ...) -> Event: ...
def build_lifecycle_event_envelope(envelope: Mapping[str, Any]) -> Event | None: ...
```

- `build_status_event_envelope` is the keep-half of `_broadcast_status_transition`
  (`zeitgeist_bridge.py:161-195`): validate a `StatusTransitionPayload`, assemble
  the `Event` with `_envelope_bookkeeping`/`_parse_stamp`. **Return the `Event`;
  do not offer it.**
- `build_lifecycle_event_envelope` is the keep-half of
  `_broadcast_lifecycle_envelope` (`zeitgeist_bridge.py:218-262`): project via
  `_canonical_lifecycle_payload_for_saas`, pick the payload model from
  `PAYLOAD_MODEL_BY_EVENT_TYPE`, assemble the `Event`.
- Move `_envelope_bookkeeping`, `_coerce_uuid`, `_parse_stamp`,
  `_normalise_evidence`, `_wire_lifecycle_payload` (`zeitgeist_bridge.py:269-654`)
  here verbatim. **Drop** everything downstream of the builders: `_broadcast_moment`,
  `_offer_and_log`, `_refresh_liveness*`, `_resolve_*credential/focus`, the
  `_FOCUS_REF_RE`/presence/focus machinery — all relay/liveness, all removed.
- **Volatile filtering is NOT a producer concern.** The bridge dropped
  non-`VOLATILE_EVENT_TYPES` events (`zeitgeist_bridge.py:222-227`) because the
  *relay* only carried the ephemeral subset. The local producer emits the full
  lifecycle vocabulary (`lifecycle_events.LIFECYCLE_EVENT_TYPES`,
  `status/lifecycle_events.py:108-123`) — drop the `VOLATILE_EVENT_TYPES` gate.

**Architecture note (gate-safe):** `status/` already imports `spec_kitty_events`
directly (`status/emit.py:111`, `status/lifecycle_events.py:376-378`), so this
module adds no new layer edge. It stays inside the `specify_cli` top layer and
has no edge into any removed package — satisfying `test_shared_package_boundary.py`
and the modularity landscape (CLAUDE.md "Shared Package Boundary").

---

## 2. Where it registers and fires — the `status/adapters.py` produce seam

The producer builds an `Event` for each kind and fires it through the surviving
seam. A new module `src/specify_cli/status/event_producer.py` owns the default
handlers and their registration (mirroring the removed
`adapters.ensure_zeitgeist_moment_handlers` wiring, `zeitgeist_bridge.py:10-11`):

| Event kind | Fired from | Seam call | Builder | Notes |
|---|---|---|---|---|
| **Status transition** (`WPStatusChanged`) | `emit.py::_saas_fan_out` → `fire_saas_fanout` (`status/emit.py:1027-1033`, `status/adapters.py:217`) | `register_saas_fanout_handler` | `build_status_event_envelope` | kwargs already carry `metadata`, `mission_slug`, `wp_id`, `repo_root` (`adapters.py:237`, bridge `:161-204`) |
| **Lifecycle** (Project/Mission/Specify/Plan/Tasks/WP/…) | `lifecycle_events.fanout_lifecycle_event_hosted` → `fire_lifecycle_saas_fanout` (`status/lifecycle_events.py:475-501`, `status/adapters.py:319`) | `register_lifecycle_saas_fanout_handler` | `build_lifecycle_event_envelope` | envelope + `log_path` already threaded (`adapters.py:329`, bridge `:218-266`) |
| **Resolved binding** (`WPResolvedBindingChanged`) | `emit.py::_resolved_binding_fan_out` → `fire_resolved_binding_fanout` (`status/emit.py:1034-1035`, `status/adapters.py:279`) | `register_resolved_binding_fanout_handler` | (new builder when the payload ships) | package lacks the codec today (`emit.py:122`); slot stays wired, no-op until then — same posture the bridge took (`zeitgeist_bridge.py:136-141`) |
| **Decision log** (`DecisionInput*`, `DecisionPoint*`) | `events/decision_log.py` + `decisions/emit.py` | *new*: route through a decision fan-out | reuse `build_lifecycle_event_envelope` path (decision payload models are in `PAYLOAD_MODEL_BY_EVENT_TYPE`) | decision rows already share `status.events.jsonl` as canonical store (`lifecycle_events.py:131-166`, `_DECISION_POINT_EVENT_TYPES`) |
| **Runtime journal** (`MissionRun*`, `NextStep*`, `SignificanceEvaluated`) | `runtime/.../engine.py::_append_event` (`:107-118`) | *new*: a runtime fan-out slot, or a direct `event_envelope` call at the emitter boundary (`events.py` `RuntimeEventEmitter`, `:75-96`) | new builder over `spec_kitty_events.mission_next` models | today `#1248`-exempt, package-retired schema — reconcile under §4 |

**Registration (on-by-default, §5):** a single idempotent
`ensure_local_event_producer()` registers all default handlers into the three
existing slots at CLI init, exactly where `ensure_zeitgeist_moment_handlers` was
invoked. `register_*` are idempotent-by-qualified-name
(`status/adapters.py:150-188`), so repeated init is safe.

**Non-raising contract preserved.** Every `fire_*` already catches and logs
per-handler (`status/adapters.py:250-276,298-316,329-344`) under a bounded
worker (`:76-116`), so a producer-handler failure can never block canonical
persistence — same guarantee the bridge's handlers carried
(`zeitgeist_bridge.py:114-133`). The producer handlers keep the same
"build-then-sink, swallow-and-log" shape.

---

## 3. The LOCAL sink — where produced `Event`s are written

### 3.1 Decision: native ledgers stay the committed SSOT; the shared-format stream is a **gitignored local spool**

Rationale, tied to debrief **C4** (committed ledgers never pruned; gitignored
local logs get retention N runs / X days):

- The native ledgers are **already the committed authority** and are
  union-merge-driver protected / rebuildable
  (`status/emit.py:22-27`; status & decision logs live in tracked
  `kitty-specs/<slug>/`; `.kittify/canonical-events.jsonl` is directly under
  `.kittify/` and is **not** matched by any `.gitignore` entry —
  `.gitignore:60-69` lists `.kittify/events/`, `runtime/`, `derived/` etc. but
  not that file — so it is tracked today). Duplicating them into a second
  committed shared-format file would double every mission's committed footprint
  and create a second merge surface for no gain.
- The shared-format `Event` stream is a **derived projection** of those
  committed ledgers. A derived artifact belongs in a **gitignored** location
  with bounded retention — the same class as `.kittify/derived/`
  (`.gitignore:65`) and the runtime journal under `.kittify/runtime/`
  (`.gitignore:64`).

### 3.2 Named sink

**Default sink file:** `.kittify/events/shared/events.jsonl`
(`.kittify/events/` is already gitignored — `.gitignore:66`).

- One append-only JSONL of `Event.to_dict()` rows (`models.py:166-168`), written
  by a default sink handler `event_producer.local_sink_handler` registered into
  the seam alongside the per-kind builders.
- Written through the **same crash-safe primitive** the native ledgers use,
  `status.store.append_raw_rows_atomic` (via `lifecycle_events._atomic_append`,
  `status/lifecycle_events.py:254-282`) — one durability mechanism, no new
  write-ahead path.
- **Retention (C4):** because it is gitignored and derived, apply retention —
  keep the last **N=50 runs** or **X=14 days**, whichever is larger, pruned at
  CLI init (a cheap size/age sweep in `event_producer`). The committed native
  ledgers are the replay source if the spool is pruned or absent, so pruning is
  always safe. (N/X are the proposed defaults; make them config knobs under
  `.kittify/config.yaml`.)

### 3.3 Why a spool and not direct hand-off

event-router (the consumer) may not be running when the CLI produces. A durable,
bounded local spool decouples producer cadence from consumer liveness without
reintroducing the deleted sync daemon/offline-queue (research.md §2.1: sync
transport already retired; **do not** re-introduce a queue/daemon/retry). The
consumer tails the spool and/or reads the committed ledgers via the Mission
Status Read API (§6). This keeps the bridge's "fire-and-forget, drop-no-retry"
discipline (`zeitgeist_bridge.py:53-56`) but makes the drop recoverable from the
committed SSOT rather than lost.

---

## 4. Row-schema follow-on (debrief C3) — a versioned ROW schema in `spec-kitty-events`

Today `spec_kitty_events` defines **payload** models and the envelope, but **not
a ledger-ROW schema**; the CLI writes its own native row shapes, and three
divergences exist (debrief B4):

1. **No ROW schema, writer is the CLI's own class.** `StatusEvent`
   (`status/models.py:383-454`) is a hand-rolled dataclass with no JSON schema;
   its `to_dict` is the de-facto status-row contract. The package's
   `StatusTransitionPayload` (`spec_kitty_events/status.py:411-467`) is only the
   *payload*, and `extra="forbid"`.
2. **`reason_source` is dropped.** The CLI row carries `reason_source`
   (`status/models.py:418,450-451`); `StatusTransitionPayload` has no such field
   and forbids extras — so a wire/shared build loses it. **Resolve** by adding
   `reason_source: Optional[str]` to the package payload (or to a new row model),
   so the producer no longer silently drops provenance.
3. **Stale producer-lint exemptions.** `#1198` (lifecycle/decision envelopes:
   `status/lifecycle_events.py:308,319,456`; `events/decision_log.py:224`) and
   `#1248` (runtime journal: `runtime/.../engine.py:109`) are
   `canonical-producer-exempt` precisely because the package has no row schema
   those producers can write *from*. Lint authority:
   `tests/lint/test_canonical_producers.py`.
4. **Lane list defined 3×.** `Lane` exists in the CLI
   (`status/models.py:29-79`, with `GENESIS`/`UNINITIALIZED` non-display lanes),
   in the package (`spec_kitty_events/status.py:179` + `LANE_ALIASES` `:285`),
   and is re-asserted by the strict profile's admitted set
   (`spec_kitty_events/strict.py:107-130`). These drift independently
   (e.g. `genesis` support is version-gated at `status/emit.py:110-127`).

### Proposed row-schema work (upstream `spec-kitty-events`, cross-repo)

- **Define a versioned ROW schema per row kind** — `status`, `annotation`
  (resolved-binding / inner-state), `run-journal` — as first-class models beside
  the envelope, each admitted by the strict `journal/v1` profile
  (`spec_kitty_events/strict.py:77,107-130`; `STRICT_PROFILE_ID = "journal/v1"`).
- **Producer writes from the package model, not the CLI class.** The CLI's
  `StatusEvent`/lifecycle envelope become thin adapters over the package row
  model; `build_*_event_envelope` (§1) already produces `Event` from package
  payload models — extend to the row models so the native ledgers themselves can
  be validated against the shared ROW schema and the `#1198`/`#1248` exemptions
  retired.
- **Add `reason_source`** to the status payload/row (point 2).
- **Single lane authority.** The CLI `Lane` should re-export or validate against
  the package `Lane` (non-display `GENESIS`/`UNINITIALIZED` stay CLI-internal and
  are never emitted — the version gate at `emit.py:110-127` becomes unnecessary
  once the package lane set is the source). Close the triplication by making the
  strict-profile admitted set derive from the package `Lane` enum.
- **Gate the schema version** the same way `emit.py` already gates capability
  (`emit.py:110-127`) so an older installed package degrades gracefully rather
  than raising.

This is a **cross-repo deliverable** (`spec-kitty/spec-kitty-events`, per the
Shared Package Boundary section of CLAUDE.md) and rides a dedicated package
version bump; the CLI side pins to it. It is sequenced **after** §1–§3 (the CLI
can produce the `Event` envelope from today's payload models immediately; the
ROW schema hardens and de-duplicates afterward).

---

## 5. On-by-default + separation from `hosted.drain`

- **On by default.** `ensure_local_event_producer()` registers the default
  handlers unconditionally at CLI init. There is **no drain check, no env var, no
  config gate** on the producer path — ADR `2026-10-06-1` amendment: "Producing
  an event never depends on whether a drain is enabled" (`status/adapters.py:9-10`).
- **Stays off the hosted path entirely.** `event_envelope.py` and
  `event_producer.py` import **only** `spec_kitty_events` + `status` siblings.
  They must never import `zeitgeist_client` / `saas_client` / `auth`
  (all removed by #6164) or consult `core/hosted_posture.py` / the drain gates.
  Enforce with an **architectural test** in the spirit of the existing
  `tests/architectural/test_remote_contact_owner.py` (empty-allowlist pattern,
  research.md §1): assert `status/event_envelope.py` and
  `status/event_producer.py` have **zero** edges into any hosted/relay module and
  make **zero** network calls.
- The hosted drain path (`status/zeitgeist_bridge.py` → `_broadcast_moment`) is
  **gone**; there is no `hosted.drain`-gated producer left to confuse with this
  one. The local producer is the *only* producer, and it is always on.
- **No CHANGELOG / no behavior change for consumers of the drain.** Drain was off
  everywhere; turning on a *local* producer changes no hosted behavior.

---

## 6. Consumer side (brief — out of scope for the CLI producer design)

event-router (Team Kitty) **consumes** across the shared contract (ADR
`2026-10-01-2` Mission Status Read API; ADR `2026-10-12-2`). It:

- reads the committed native ledgers through the **Mission Status Read API**
  (read-only, drain-independent — ADR `2026-10-01-2` D-6: "returns the same
  answer whether hosted drain is on or off"), and/or
- tails the §3 gitignored spool `.kittify/events/shared/events.jsonl` for a live
  feed,

validating every row against the shared `journal/v1` strict profile
(`spec_kitty_events/strict.py:556-648`). It **never** imports CLI internals. The
pristine relocated bridge in `/home/user/event-router/relocated/...` is the
consumer-side reference for the envelope shape it expects. Designing the
consumer's reader is a separate event-router mission.

---

## 7. Migration / compatibility

- **No data migration of existing ledgers.** Native ledgers are unchanged in
  shape; the producer is additive (a new gitignored spool + handler
  registration). Existing missions keep replaying from the committed logs.
- **Backward-compatible envelope build.** `build_*_event_envelope` tolerates
  legacy rows exactly as the bridge did (missing stamp → emission clock,
  `zeitgeist_bridge.py:598-612`; missing project_uuid → deterministic UUID5,
  `:635`; `mission_id` optional, `emit.py:130-142`).
- **Capability/version gates stay.** Reuse the `emit.py:110-127` pattern so an
  older installed `spec_kitty_events` degrades (skip-and-log) rather than raising
  — the producer is best-effort, never load-bearing on canonical persistence.
- **Clean rollback.** Because the producer only *adds* a handler and a gitignored
  file, disabling it is `reset_handlers()` + delete the spool; the committed SSOT
  is untouched.

---

## 8. Phased work-package outline (planner-ready)

> A mission planner can turn each WP below into a tasks slice. Sequenced so the
> CLI produces the shared format early (WP1–WP3), then the schema hardens (WP5).

- **WP1 — Extract the drain-independent envelope builder.**
  New `src/specify_cli/status/event_envelope.py`: relocate the keep-halves of
  `_broadcast_status_transition` / `_broadcast_lifecycle_envelope` and their
  helpers (`zeitgeist_bridge.py:154-266,269-654`), returning `Event` objects.
  Drop the `VOLATILE_EVENT_TYPES` gate. Unit tests: envelope shape parity with
  the pristine bridge's build (golden `Event.to_dict()` rows). **No seam wiring
  yet.**
- **WP2 — Default producer handlers + registration.**
  New `src/specify_cli/status/event_producer.py`: `ensure_local_event_producer()`
  registering status/lifecycle/(resolved-binding stub) handlers into the existing
  slots (`adapters.py:150-188`); invoke at CLI init where
  `ensure_zeitgeist_moment_handlers` used to be. Tests: `fire_*` now produces
  (non-raising, bounded).
- **WP3 — Local sink + retention.**
  `local_sink_handler` writing `Event.to_dict()` to
  `.kittify/events/shared/events.jsonl` via `append_raw_rows_atomic`; init-time
  retention sweep (N=50 runs / X=14 days, config-backed). Tests: durable append,
  prune bound, replay-from-committed-ledger when spool absent.
- **WP4 — Decision-log & runtime-journal producers.**
  Route `events/decision_log.py` + `decisions/emit.py` and the runtime
  `RuntimeEventEmitter` (`events.py:75-96`, `engine.py:107-118`) through the
  producer (new fan-out slot or direct `event_envelope` call). Tests: decision &
  run-journal rows reach the spool in shared format.
- **WP5 — ROW-schema hardening (cross-repo `spec-kitty-events`).**
  Versioned ROW schemas (`status`/`annotation`/`run-journal`) on `journal/v1`;
  add `reason_source` to the status payload; single lane authority; retire the
  `#1198`/`#1248` producer-lint exemptions
  (`tests/lint/test_canonical_producers.py`); bump the package, re-pin the CLI.
- **WP6 — Hosted-isolation architectural gate.**
  Empty-allowlist test asserting `event_envelope.py` / `event_producer.py` make
  zero network calls and have zero edges into any hosted/relay module (pattern:
  `tests/architectural/test_remote_contact_owner.py`).
- **WP7 — Consumer hand-off doc (event-router).**
  Document the spool + Read-API contract for event-router; its reader is a
  separate event-router mission (§6).

---

## 9. Key file:line index (grounding)

| Concern | Location |
|---|---|
| Shared `Event` envelope (v3.0.0) | `spec_kitty_events/models.py:59-173` |
| Pristine producer builders (extract source) | `event-router/relocated/.../status/zeitgeist_bridge.py:154-204,207-266` |
| Producer/relay boundary = `_broadcast_moment` | `.../zeitgeist_bridge.py:204,266,335-406` |
| Envelope bookkeeping / stamp / evidence helpers | `.../zeitgeist_bridge.py:598-654,283-304` |
| Produce/fan-out seam (survives #6164, handler-less) | `src/specify_cli/status/adapters.py:1-15,150-201,217-344` |
| Status write path → `fire_saas_fanout` | `src/specify_cli/status/emit.py:1027-1035` |
| Lifecycle local writer + SaaS projection | `src/specify_cli/status/lifecycle_events.py:308-329,394-408,456-501` |
| Lifecycle event vocabulary | `src/specify_cli/status/lifecycle_events.py:108-166` |
| Decision git-log producer | `src/specify_cli/events/decision_log.py:131,224-231,254-272` |
| Runtime journal writer (#1248 exempt) | `src/runtime/next/_internal_runtime/engine.py:107-118` |
| CLI `StatusEvent` row + `reason_source` | `src/specify_cli/status/models.py:383-454` (reason_source `:418,450-451`) |
| Package status payload (no `reason_source`, forbids extras) | `spec_kitty_events/status.py:411-467` |
| Strict `journal/v1` profile + admitted set | `spec_kitty_events/strict.py:77,107-130,556-648` |
| Lane triplication | CLI `status/models.py:29-79`; pkg `spec_kitty_events/status.py:179,285`; strict `strict.py:107-130` |
| Producer lint authority | `tests/lint/test_canonical_producers.py` |
| Gitignore (spool placement) | `.gitignore:64-66` (`runtime/`, `derived/`, `events/`) |
| Drain-independence of the seam | ADR `2026-10-06-1` (amendment 2026-10-12); `adapters.py:9-10` |
| Read API drain-independence | ADR `2026-10-01-2` D-6 |
