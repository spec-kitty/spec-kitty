---
title: 'ADR: Evict runtime-mutable WP state into the event log via a single generic InnerStateChanged annotation event'
description: 'One generic `InnerStateChanged` event carries a typed `WPInnerStateDelta`, folded per field by the reducer, bypassing transition validation and never touching `force_count`.'
status: Accepted
date: '2026-07-19'
doc_status: active
kind: ADR
updated: '2026-07-19T00:00:00Z'
---

**Status:** Accepted

**Date:** 2026-07-19

**Deciders:** Operator / HiC (Stijn Dejongh); four-lane research squad (2026-07-19); building on prior-art ADR `wp-op-schema-design/docs/adr/3.x/2026-07-16-1-wp-runtime-state-authority-event-log-eviction.md`.

**Technical Story:** [#2684](https://github.com/Priivacy-ai/spec-kitty/issues/2684) (P0) — the execution vehicle for the [#2093](https://github.com/Priivacy-ai/spec-kitty/issues/2093) authority ruling. Full grounding: `docs/plans/investigations/2684-task-move-cluster-scoping.md`.

---

## Context and Problem Statement

`tasks/WP##.md` (and the `tasks.md` subtask surface) is **two authorities glued into one YAML
block**: static design-intent authored once, and runtime-mutable state written on every lifecycle
event. This split is load-bearing and actively harmful:

- Runtime writes into the dossier-hashed files (`dossier/indexer.py:242` hashes both `tasks.md` and
  `tasks/WP##.md`) churn `content_hash_sha256` on every transition → false drift (**AC-5**).
- Subtask-completion truth lives in `tasks.md` markdown bytes (`core/subtask_rows.py:39`), which the
  review gate (`_guard_subtasks`, `tasks_transition_core.py:384`) and done-inference
  (`_infer_subtasks_complete`, `status/emit.py:279`) read — while the append-only event log, the
  declared authority for lane/status, carries **no subtask state at all** (`reducer.py:48-65`). A WP
  whose work is complete is refused `move-task --to for_review` until an operator hand-ticks N
  checkboxes (the merged P0 red test `tests/regression/test_issue_2684_subtask_completion_event_sourced.py`).
- Claim-liveness reads `shell_pid` from frontmatter (`stale_detection.py:402-403`); evicting it
  naively corrupts the allocator.

The hard constraint: `StatusEvent` is a **transition ledger** — it mandates `from_lane`/`to_lane`
(`status/models.py:248-249`) and `validate_transition` rejects any edge outside the 9-lane FSM
(`wp_state.py:162,351`). But three of the evicted mutations are **off-axis** (no lane change):
(a) `shell_pid` refresh on *resume* of an already-`in_progress` WP, (b) mid-`in_progress` subtask
marks, (c) activity-log notes. They cannot be clean transition events. **How off-axis runtime state
enters the append-only log is the decision everything else rests on.**

## Decision Drivers

- **One authority per datum** — runtime state has exactly one read path (the reduced snapshot); no
  frontmatter field is ever read as authority; static fields are never mirrored into events.
- **Preserve every gate** — claim-liveness (AC-2), done-inference (AC-3), review gating — through the
  cutover, not after it.
- **AC-5 stable content hash** across a full lifecycle — the churn/false-drift fix.
- **Reusability** — prefer one extensible mechanism over per-field special cases.
- **No split-brain regression** — a generic sidecar must stay *typed*, or it re-creates the very
  ambiguity being removed.
- **Writer ownership** — this mission **owns** the `implement.py:1730` shell_pid-writer restructuring
  (the former #2160 co-sequence is resolved: #2160's writer work is `pr:deferred` and yields to this
  mission). Every new emit site must resolve its write target from stored topology, never `Path.cwd()`,
  or it reopens #2647.
- **Migration safety** — readers keep a frontmatter fallback until backfill is verified (the "B3
  clobber window").

## Considered Options

- **Option A — a non-transition annotation event class** in the same append-only log, distinguished
  by the absence of `from_lane`/`to_lane`, bypassing `validate_transition`, folded by the reducer.
- **Option B — fold onto existing transitions + `policy_metadata`.** Carry `(shell_pid, baseline)` on
  the next real transition; no FSM/reducer change.
- **Option C — self-edges (`X→X`) legalised in the FSM matrix.** (Weighed and rejected in the
  prior-art ADR: redefines the "a transition changes lane" invariant; ripples into rendering, drift,
  done-inference; zero capture benefit over A.)

## Decision Outcome

**Chosen option: Option A, realised as a *single generic* `InnerStateChanged` event carrying a typed
partial delta.** Rather than per-kind annotation variants, there is **one** off-axis event whose
payload is a **typed** `WPInnerStateDelta` (optional typed fields — *not* a free `dict[str, Any]`),
folded by the reducer with a per-field merge rule and **no `force_count` increment**. This is the
reusable realisation of the annotation class and it is what gives the reduced snapshot the
gate-queryable projection the subtask gates need.

The seven cluster decisions (HiC, 2026-07-19) that this ADR ratifies:

1. **Off-axis events → Option A as one generic `InnerStateChanged` event** with a typed delta,
   bypassing `validate_transition`, reducer-folded, no `force_count`.
2. **Subtask granularity → subsumed by the delta** (`subtasks: Mapping[str, Status]`) — a single mark
   and a batch mark are the same event; the same generic event also carries the PID refresh.
3. **Activity notes → a `note` delta field with append semantics** (reducer keeps a `notes` list;
   AC-4 renders the Activity Log from it). One event class for pid + subtasks + notes.
4. **`tracker_refs` → evict** (runtime, event-sourced): `map-requirements` and `move-task` emit an
   `InnerStateChanged` delta with **union/append** merge; FR-011 runtime append preserved.
5. **Review-cycle → evict all in this mission**: delete the dead verdict-field read fallbacks
   (`workflow_cores.py:340-341`, `done_bookkeeping.py:104-105`) **and** evict the actively-written
   `review_artifact_override_*`. **#2684 is the authoritative owner of the WP-metadata surface;**
   deferred PRs (#2641, #2766, #2612, and #2160's writer work) yield to the mission and rebase onto
   it — their file-collision risk is moot. Consequently this mission **owns** the `implement.py:1730`
   shell_pid-writer restructuring outright (no external co-sequence gate).
6. **Static-model election → deferred** to a follow-up (blocker B4: `WPMetadata` cannot become a
   clean static-only projection until its runtime half is stripped; coordinates with #1619).
7. **`progress` field → retired explicitly** (removed from `MUTABLE_FIELDS`/schema; backfill no-op).

The initial claim's `(shell_pid, baseline)` still rides the **real** `planned→claimed` transition via
the existing generic `policy_metadata` sidecar (`status/models.py:258`) — no wire-schema change there;
only the resume/mid-work/notes mutations use `InnerStateChanged`.

### Consequences

#### Positive

- The append-only log becomes a **true SSOT** for all off-axis runtime state; the reduced snapshot
  gains typed slots (`shell_pid`, `shell_pid_created_at`, `subtasks`, `notes`, `tracker_refs`).
- `tasks/WP##.md` and `tasks.md` become **static design-intent only** → stable content hash (AC-5),
  the long-homeless dossier/sync churn fix.
- Re-pointing `_guard_subtasks` and `_infer_subtasks_complete` at the snapshot turns the merged P0
  red test green (AC-3) and removes the manual N-tick friction.
- One extensible event + typed delta: future runtime fields ride free without new event kinds.

#### Negative

- Highest-blast-radius option: touches the FSM authority (a sanctioned self-edge / `annotate()`
  primitive), the wire model (an event discriminator round-tripped in `to_dict`/`from_dict`), and the
  reducer precedence core (fold-after-transition, last-writer-wins per field).
- Adds a reducer fold on the hot path (additive, but real).
- Requires disciplined migration ordering (backfill → verify → reader → writer → delete fallbacks) to
  keep the B3 clobber window closed.

#### Neutral

- `WPInnerStateDelta` is generic in shape but typed per field — deliberately not a free bag.
- The static-model election (enrich `WPMetadata` vs elect `WorkPackageEntry`) is unblocked by this
  work but intentionally out of scope.

### Confirmation

- **AC-1** no `implement`/`mark-status`/`move-task`/review action writes `tasks/WP##.md`.
- **AC-2** claim-liveness resolves from the snapshot; a claimed WP with empty frontmatter is live.
- **AC-3** done-inference resolves from `InnerStateChanged` subtask deltas — the **merged red test
  `test_issue_2684_subtask_completion_event_sourced.py` flips green**.
- **AC-4** Activity Log / History / review sections render from events with no content loss.
- **AC-5** a full lifecycle produces a **stable content hash** (headline proof).
- **AC-6** migration backfills idempotently (deterministic namespaced ULID seed-ids), with an honest
  timestamp-reconstruction contract for checkbox marks (clamp to `claimed`).
- A **refactor-stable architectural test** asserts no consumer reads a dynamic frontmatter field as
  authority (the #2093 invariant, generalising the shipped phase-2 lane-authority guard).

## Pros and Cons of the Options

### Option A — generic `InnerStateChanged` annotation event (chosen)

**Pros:** true SSOT for (a)+(b)+(c); delivers the subtask projection the gates need; one reusable,
extensible mechanism; typed delta avoids a new split-brain.
**Cons:** touches FSM + wire model + reducer precedence; additive hot-path fold; migration discipline.

### Option B — fold onto transitions + `policy_metadata`

**Pros:** near-zero FSM/reducer change.
**Cons:** complete only for `shell_pid`; resume emits nothing → stale PID → claim-liveness degrades to
the git-timestamp heuristic (a false-stale window on the exact path AC-2 protects); subtasks and notes
still need a home; gate re-sourcing is *still* required. **Rejected** — partial SSOT for more net work.

### Option C — self-edges in the FSM matrix

**Pros:** reuses the transition path.
**Cons:** redefines the "a transition changes lane" invariant; ripples into rendering, drift, and
done-inference for no capture benefit over A. **Rejected.**

---

## Addendum (2026-07-20): Per-field authority for a WP's runtime identity — resolves blocker B4

**Status:** Accepted · **Date:** 2026-07-20 · **Deciders:** Operator / HiC (Stijn Dejongh);
architect (mission `runtime-state-corpus-cutover`, [#2816](https://github.com/Priivacy-ai/spec-kitty/issues/2816)).

**Extends:** Decision 6 (Decision Outcome, above) — the *static-model election* it **deferred as
blocker B4**. **Requirement:** FR-013. **Constraint gate:** C-009 (this addendum is the ADR of record
that C-009 requires **before** the IC-08 event vocabulary lands — WP09 is gated on it). **Lineage:**
[#2093](https://github.com/Priivacy-ai/spec-kitty/issues/2093) (canonical-authority ruling) →
[#2400](https://github.com/Priivacy-ai/spec-kitty/issues/2400) (WP-metadata half) → #2816;
[#2399](https://github.com/Priivacy-ai/spec-kitty/issues/2399) owns the full fail-closed *enforcement*
and stays **out of scope** here (this ruling records **record + reconstruct** only).

### Context — why blocker B4 is now actionable, and why it grew

Decision 6 deferred the static-model election because "`WPMetadata` cannot become a clean static-only
projection until its runtime half is stripped." The #2816 corpus cutover (WP01–WP07) strips that
runtime half: the runtime-mutable fields leave `tasks/WP##.md` frontmatter and become event-sourced.
B4 is therefore now decidable.

Deciding it surfaced a finding that reframes the original "elect the static model" question. A WP does
not carry *one* identity that is either static or dynamic — it carries **two distinct
representations** of `role`/`agent_profile`/`model`, and the earlier framing risked collapsing them:

- The **authored recommendation** — who/what a WP was *designed* to be run by, authored once at
  tasks-finalize. This is fixed for the life of the WP.
- The **resolved actual** — who/what *actually* resolved and ran the WP at a given lifecycle
  transition. This **shifts** across the lifecycle: an implementer profile on model A claims the WP; a
  reviewer profile on model B picks it up for review; a model can be swapped mid-cycle. A single static
  value is therefore **wrong mid-cycle** — only the event log's latest-actual reduction is correct.

Electing a static model (or a static profile/role) as *the* identity would re-manufacture the very
split-brain #2093 forbids: a consumer reading the static value would report the wrong actor for any WP
past its first pick-up. B4 is resolved not by "make the model static" but by **ratifying a per-field
authority that keeps authored intent and resolved actual as separate, single-authority data.**

### Decision — per-field authority (unambiguous, per field)

For each of `role`, `agent_profile` (+ `agent_profile_version`), `model`, and `provider`, the two
representations have **different, single canonical authorities**:

| Field | Authored / recommended (static) | Resolved / actual (dynamic) |
|---|---|---|
| `role` | **frontmatter-canonical** — authored once at tasks-finalize | **event-log / snapshot-authoritative** — folded latest-wins at each pick-up/claim/reassign |
| `agent_profile` (+`agent_profile_version`) | **frontmatter-canonical** | **event-log / snapshot-authoritative**, latest-wins |
| `model` | **frontmatter-canonical** | **event-log / snapshot-authoritative**, latest-wins |
| `provider` | (no authored form) | **event-log / snapshot-authoritative**, latest-wins |

Read plainly:

- The **resolved actual** `role`/`agent_profile`(+version)/`model`/`provider` are **dynamic →
  event-log/snapshot-authoritative**. They are recorded on the append-only log at each
  **pick-up/claim/reassign** transition and folded **latest-wins** into the reduced snapshot. The
  snapshot is their sole read authority — no consumer reads them from frontmatter.
- The **authored recommendation** `role`/`agent_profile`/`model` are **static →
  frontmatter-canonical**. They are authored once at tasks-finalize and never mirrored into events.

This mirrors the two-column authority table in the mission data-model (`data-model.md`, "Resolved
runtime identity (event-sourced) vs authored recommendation (frontmatter)") so that no field's
authority is left implicit. It is the concrete, per-field realisation of Decision Driver
**"one authority per datum"** for the identity fields specifically.

### Binding constraints of the ruling

- **C-007 — the recorded resolved value MUST come from the resolver, never a frontmatter copy.** The
  recorded resolved `role`/`agent_profile`/`model` MUST be produced by `resolve_profile` /
  `resolved_agent()` / the dispatch resolution. Copying the static frontmatter `agent_profile` string
  into an event is **forbidden** — it manufactures a *new* split-brain (the exact #2093 anti-pattern:
  static design-intent masquerading as recorded runtime truth). Where a genuine resolved value is
  unavailable on a given path (e.g. no dispatch-resolved model), it is recorded **explicitly absent**,
  never fabricated or frontmatter-coerced.
- **C-008 — authored intent and resolved actual are never conflated.** Every WP-view consumer surfaces
  the frontmatter **authored recommendation** and the event-sourced **resolved actual** as **distinct**
  values. No consumer treats the authored value as "what ran", nor the resolved value as "what was
  intended". A WP with no resolved-binding events shows the authored recommendation and an **empty**
  resolved actual — never the authored value masquerading as resolved. The single reconstruction reader
  (`reconstruct_wp_view`, IC-07) is the **one** assembly point that joins the snapshot's resolved
  fields with frontmatter's authored fields, distinctly labelled.

### Ratification — the `role` reversal

An interim note had kept `role` as a frontmatter-only field ("keep role frontmatter"). The #2093
ruling text lists `role` among the *dynamic* fields. **This addendum ratifies the reversal:** the
**authored** role recommendation stays frontmatter-canonical, but the **actual** role that ran a WP is
**event-sourced** (dynamic, latest-wins) — exactly like `agent_profile` and `model`. `role` is not an
exception to the per-field rule above; it follows it. The interim "keep role frontmatter" note is
**superseded**.

### Scope and lineage

This ruling records the **resolved-binding "record + reconstruct" slice** of #2093 plus the
WP-metadata half of #2400. It does **not** ratify the full fail-closed *enforcement* of #2399 (an agent
being unable to act without a resolved+recorded profile, across ops/dispatch/ad-hoc/mission-WP) — that
stays out of scope and #2399 remains open for it. Recording a per-field canonical-authority ruling as
an ADR follows the #2093 precedent: a canonical-authority decision is a system-design decision, not an
implementation detail.

### Consequences

**Positive**

- Blocker B4 is resolved: the identity fields have an unambiguous, per-field authority, so the event
  vocabulary (IC-08), the reconstruction reader (IC-07), and the SaaS `actor` delivery (IC-09) can be
  built against a ratified contract rather than an open question.
- The reduced snapshot becomes the single read authority for "who/what is *actually* running this WP",
  correct at every lifecycle stage — the dashboard, the `agent tasks status` board, and `WorkPackage`
  can converge on one reconstruction reader.
- The split-brain #2093 forbids is closed for the identity fields, not merely for lane/status.

**Negative**

- The WP view must now always join two sources (snapshot + frontmatter); a consumer that reads only one
  is, by construction, wrong. The single reconstruction reader (IC-07) is the mitigation, and the
  extended #2093 architectural detector guards against a reader that reaches back into frontmatter for a
  resolved field.

**Neutral**

- This addendum is the **gate**, authored **before** the IC-08 vocabulary and the IC-07 reader exist;
  it presupposes neither. It records the ruling; WP09/WP10 implement it.
