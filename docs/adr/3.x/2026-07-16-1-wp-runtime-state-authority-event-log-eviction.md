---
title: 'WP runtime-state authority — evict runtime-mutable state from tasks/WP##.md into the canonical event log'
description: 'Runtime-mutable work-package state leaves `tasks/WP##.md` for the append-only event log, carried by an annotation event class so the 9-lane machine gains no self-edges.'
status: Proposed
doc_status: active
kind: ADR
date: '2026-07-16'
---

**Status:** Proposed

**Date:** 2026-07-16

**Deciders:** Architecture squad (architect-alphonso · paula-patterns · planner-priti), reconciled with #2093 / #2400 owner

**Technical Story:** Charter-completion of #2093 / #2400 (WP-metadata authority split). Prerequisite mission for the YAML-authoritative / markdown-derived WP prompt (proposal Parts 1–3). Sequenced with #2160 (coord-authority Wave 2).

---

## Context and Problem Statement

The shipped `lane` retirement (`frontmatter.py:47-49`, migration-only in
`task_metadata_validation.py:82`) moved one runtime-mutable field out of the WP
file into the append-only event log. It generalised badly: **`tasks/WP##.md`
still holds other runtime-mutable state that live phase-2 code writes and reads
on every `implement`, `move-task`, `mark-status`, and review action.**

This blocks two shipped-intent goals at once:

1. **#2093 / #2400's own charter** — "static intent stays canonical in the WP
   file; dynamic runtime state retires to event-log / invocation authority" —
   is only half-delivered. `lane` moved; `shell_pid`, subtask-checkbox state,
   review-cycle fields, activity-log narrative, `agent`, `assignee`, and more
   did not.
2. **The YAML-authoritative WP-prompt schema** (proposal Part 4 **B3**) cannot
   be built. Declaring `WP##.md` "derived, do not edit" clobbers claim-liveness
   (`stale_detection.py`) and done-inference (`emit.py` `done==total`) on the
   very next `implement`, because those signals are read back out of the file
   the render would overwrite.

An architecture-and-roadmap review squad (2026-07-16, recorded in
[`docs/plans/investigations/wp-runtime-state-eviction-scope.md`](../../plans/investigations/wp-runtime-state-eviction-scope.md)
§"Squad review corrections") pressure-tested the eviction scope. Verdict:
**direction correct and correctly homed under #2093 / #2400, but one
load-bearing architectural decision was unaddressed and the writer/reader
inventory was materially incomplete.** This ADR pins the five decisions that
scope §C8 requires before the mission is planned.

### The load-bearing gap — runtime state mutates OFF the transition axis (scope §C1)

`StatusEvent` is a **transition ledger**: it mandates `from_lane` / `to_lane`
(`status/models.py:224-226`) and `validate_transition` rejects any edge not in
the 9-lane FSM (`status/transitions.py:53,83-99`). But three of the evicted
mutations are **non-transition** — they happen with no accompanying lane change:

- **`shell_pid` refresh on resume** — rewritten on *every*
  `implement` / `agent action` invocation, including resume of an already
  `in_progress` WP (`implement.py:1730`, `workflow_executor.py:669`).
- **subtask marking** — mid-`in_progress` `- [x] T###` flips
  (`tasks_materialization.py:260,304`, and an uncheck in `tasks.md` at
  `tasks_move_task.py:1662`).
- **activity-log notes** — free-text narrative appended mid-work (six writers,
  incl. external `orchestrator_api/commands.py:1563`).

A `claimed`-event payload captures only `planned→claimed`; it cannot carry a
resume refresh or a mid-`in_progress` mark. **This is the pivotal decision (C1),
and everything else rests on it.**

## Decision

**Adopt the eviction as the charter-completion of #2093 / #2400, and resolve
the C1 axis mismatch by introducing a non-transition annotation event class
rather than polluting the 9-lane FSM.** The five scope §C8 decisions are pinned
below.

### Decision 1 — Non-transition event shape: annotation event class, NOT self-edges (scope §C1, §C8.1)

**Chosen: a distinct non-transition "annotation" event class in the same
append-only log, folded by the reducer as a payload update — the FSM transition
ledger is left untouched.** Self-transition (`X→X`) edges do **not** become
legal in the 9-lane matrix.

Concretely:

- The **initial claim's** `shell_pid` + `baseline` ride the real
  `planned→claimed` transition. Mechanism note A2 applies: `policy_metadata:
  dict|None` (`models.py:234`) is already a generic event sidecar
  (`implement.py:1328`), so this needs **no wire-schema change**; the
  reduced *snapshot* is where the pair becomes typed.
- The **non-transition mutations** — resume `shell_pid` refresh, mid-work
  subtask marks, activity-log notes — are recorded as **annotation events**: a
  new record class carrying `wp_id`, an `annotation_kind`
  (`shell_refresh` / `subtask_marked` / `activity_note`), a typed payload, and a
  truthful `at` timestamp, with **no `from_lane` / `to_lane`**. Annotation
  events bypass `validate_transition` (they are not transitions) and are folded
  by the reducer onto the reduced snapshot.

**Why not fold-onto-transition (scope §C1 option b).** Folding was considered
and rejected as the primary mechanism. It cannot carry a resume refresh (there
is no lane change on resume), so a resumed WP would carry a stale PID and
claim-liveness would silently degrade to the git-timestamp heuristic
(`stale_detection.py:254-301`) — a user-visible regression on the exact
claim-liveness path this mission exists to protect (AC-2). Worse, mid-work
subtask marks and activity-log notes have **no transition to attach to at all**
(they occur wholly within `in_progress`); folding them is not merely lossy, it
is impossible without inventing a fake transition. Option (b) "works" only by
dropping the M7 data the mission is chartered to preserve.

**Why not self-edges.** Making `X→X` legal in the transition matrix would
redefine the FSM invariant that a transition always changes lane, and would ripple
into kanban rendering, drift detection, and done-inference. The annotation class
achieves the same capture with **zero change to the transition contract**.

### Decision 2 — Stable-content-hash + total-eviction invariant (scope §C8.2)

**`tasks/WP##.md` (plus the `tasks.md` subtask surface) is the sole churn
surface, and it becomes stable across every runtime mutation.** After the
mission, `content_hash` over the authored WP spec is **invariant** across claim,
resume, subtask-done, review, and history append. That single guard is the
acceptance test that proves the mission — and directly delivers the original
hash-churn fix.

"Total eviction" forces scope §C2's missed writers into scope. Every one of
these must be repointed off the file, or the invariant leaks by construction:

| Field | Live writers that must be repointed |
|---|---|
| `shell_pid` (+`shell_pid_created_at`, baseline) | `implement.py:1730`, `workflow_executor.py:669` (implement), `:1337` (review), `tasks_move_task.py:1638` — **4 writers** |
| `agent` (scalar) | `workflow_executor.py:667`, `tasks_move_task.py:1631` |
| `assignee` | `tasks_move_task.py:1629` |
| `activity_log` (body) | `tasks.py:913`, `workflow_executor.py:679` & `:1344`, `tasks_move_task.py:1645`, `orchestrator_api/commands.py:1563` — **6 writers, incl. external orchestrator-api** |
| subtask checkbox | `tasks_materialization.py:260,304` (WP##.md) + `tasks_move_task.py:1662` uncheck (**`tasks.md`**) |
| `review_artifact_override_{at,actor,wp_id,reason}` | `tasks_materialization.py:58-61,125-128` |
| `base_branch` / `base_commit` / `created_at` | `implement_support.py:133-142` (fresh-lane creation) |

**`move-task` is the primary lane-transition writer** and must be an explicit
AC-1 target: it alone rewrites `shell_pid` + `agent` + `assignee` +
activity-log + `tracker_refs` and unchecks subtasks. A naive eviction that
misses it churns the hash on the very next transition. `history[]`'s frontmatter
mirror is already **DEAD** (`add_history_entry`, `frontmatter.py:347`, has no
live callers) — "evict" there means *confirm-removed* and render `## History`
from events.

**One canonical runtime-mutable field-set.** The eviction extends the existing
`migration/strip_frontmatter.py:MUTABLE_FIELDS` (`{lane, review_status,
reviewed_by, review_feedback, progress, shell_pid, assignee, agent}`) — adding
`history`, `shell_pid_created_at`, `activity_log`,
`review_artifact_override_*`, and resolving `tracker_refs`. It does **not**
author a rival list.

Two classification corrections from scope §C3 are pinned here:

- **`tracker_refs` cannot be both static and derived.** It is runtime-written
  (`tasks_move_task.py:1575-1595`, FR-011) yet the schema proposal lists it
  static. **Re-decide in the mission:** either keep it authored + immutable
  (move the `--tracker-ref` write elsewhere) or evict it. Do not ship it as
  both.
- **`progress`** is in `MUTABLE_FIELDS` but has no live writer or reader →
  **explicitly retire**, do not silently drop.

The static residue that **stays** authored in the WP file is confirmed sound
(no runtime writers anywhere): `branch_strategy` / `merge_target_branch` /
`planning_base_branch` / `priority` / `phase` / `task_type` / `cross_cutting` /
`owned_files` / `agent_profile` (authored assignment) / `requirement_refs` /
`plan_concern_refs` / `create_intent` / `authoritative_surface` / `scope` /
`work_package_id` / `title` / `dependencies`.

### Decision 3 — Migration contract (scope §C6, §C8.3)

**Order is strict: backfill → verify → reader cutover → writer cutover.**
Readers keep the frontmatter fallback *only until backfill is verified*.
Writer-first opens the exact B3 clobber window and is prohibited.

- **Deterministic, ULID-valid seed-ids.** The reducer dedups by `event_id`,
  which must match `ULID_PATTERN` (`reducer.py:139-149`, `models.py:70`). A
  content hash is **not** a valid ULID. Seed events use a **namespaced
  deterministic ULID** derived from `mission_id + wp_id + field`, so re-runs are
  idempotent (no double-seed).
- **Timestamp honesty.** Subtask checkboxes carry no `at`; a backfilled
  `subtask_marked` annotation has **no truthful timestamp**. AC "no data loss"
  is therefore not literally achievable for reconstructed marks — the mission
  states the reconstruction contract explicitly (clamp to the WP's `claimed`
  timestamp) rather than fabricating precision.
- **Extend `strip_frontmatter.py`** (Decision 2's single field-set) as the
  migration's canonical stripper — do not fork it.
- **Scale:** backfill covers the existing corpus of missions' frontmatter
  runtime fields into seed events; idempotent by construction (deterministic
  ids).

### Decision 4 — #2093 / #2400 relationship + delete legacy resolver fallbacks (scope §C5, §C8.4)

**This mission lands under #2400 as charter-completion, not as a rival ruling.**
It accepts #2093's authority decision unchanged: static intent stays canonical
in the WP file; dynamic runtime state is event-log-owned.

**Eviction means remove, not merely stop writing.** Leaving a dormant
"read frontmatter when the canonical field is absent" branch violates the
*no legacy resolver paths* invariant ([ADR
2026-07-01-1](2026-07-01-1-no-legacy-compat-branches-in-resolvers.md)). The
following fallbacks are **deleted** by this mission:

- `workflow_cores.py:340-341` — reads `review_status` / `review_feedback` from
  frontmatter when the canonical `review_ref` is absent.
- `done_bookkeeping.py:104-105` — reads `meta.reviewed_by` / `review_status`
  off `WPMetadata` (frontmatter).

And the most-consumed reader layer is repointed to the reduced snapshot:
`WorkPackage.{shell_pid, agent, assignee}` (`task_utils/support.py:288,292,296`)
and `WPMetadata` coercion (`wp_metadata.py:364,580`).

### Decision 5 — 9-lane FSM invariant preserved (scope §C8.5)

**The 9-lane FSM is unchanged. Self-transition edges do NOT become legal in the
transition matrix; `validate_transition` continues to reject any non-lane-
changing edge.** The non-transition mutations live in the annotation class
(Decision 1), *outside* the transition ledger.

**Reducer precedence (payload-only self-events).** The reducer folds in event
order: transition events set the lane and any transition-carried payload;
annotation events fold their typed payload onto the reduced snapshot **after**
transitions, last-writer-wins per field. At equal timestamps, annotation folds
apply after the transition fold, so a `claimed` transition carrying an initial
`shell_pid` is not clobbered by an out-of-order read, and a later
`shell_refresh` annotation deterministically supersedes it
(`reducer.py:160` precedence extended, not rewritten).

## Decision Drivers

- **Charter-completion, not new construction** — the mission finishes #2093 /
  #2400's own ruling; it must not re-litigate the authority split.
- **No data loss** — activity-log narrative and review-feedback prose (scope
  M7) must survive; that forces the annotation class, since the transition
  ledger carries only fields + a `review_ref` pointer.
- **No silent behaviour regression** — claim-liveness (AC-2) and done-inference
  (AC-3) must gate identically to today; fold-onto-transition would degrade the
  resume path.
- **No legacy resolver paths** — dormant frontmatter fallbacks are deleted, not
  left inert (ADR 2026-07-01-1).
- **Single canonical field-set** — extend `strip_frontmatter.py`; never author a
  rival `MUTABLE_FIELDS`.
- **FSM invariant is load-bearing** — the transition contract is consumed by
  kanban rendering, drift detection, and done-inference; it must not be widened
  to carry payload-only self-events.

## Considered Options (Decision 1, the pivotal one)

- **(A) Annotation event class, FSM untouched — CHOSEN.** New non-transition
  event kind folded by the reducer; transition ledger and 9-lane matrix
  unchanged.
- **(B) Fold onto existing transitions.** Carry runtime payload on the nearest
  lane transition; accept a documented resume-staleness behaviour change.
  *Rejected:* cannot carry resume refresh or mid-`in_progress` marks; lossy by
  construction.
- **(C) Self-edges in the FSM.** Make `X→X` legal so payload-only self-events
  are "transitions." *Rejected:* redefines the FSM invariant and ripples into
  every transition consumer for no capture benefit over (A).

## Consequences

**Positive**

- `WP##.md` becomes stable-hashing static intent — unblocks the YAML-authoritative
  WP-prompt schema (proposal Parts 1–3) as a pure formalization.
- The eviction **alone** delivers the churn fix; the separate "semantic-only
  hash" slice shrinks to a small follow-up (still co-moving
  `sync/body_upload.py` TOCTOU, no mixed parity pool — scope §C7).
- #2093 / #2400's charter is completed; one canonical runtime-mutable field-set;
  the dormant frontmatter fallbacks are gone.
- Activity-log and review narrative gain a truthful structured home (annotation
  events), resolving M7's data-loss.

**Negative / cost**

- A new event class is a real reducer change (fold + precedence rule) and a new
  record shape — additive, but it touches the hot reduce path.
- The migration is corpus-wide and must reconstruct timestamps it cannot know
  precisely (Decision 3 clamp).
- The `shell_pid` writers overlap #2160's Wave-2 `implement.py` / `workflow.py`
  degod; the shell_pid move must **co-sequence with (or land behind) #2160**,
  not race it (scope §C7). A `blocks` / `blocked_by` edge is required.

**Neutral**

- The C-007 PID-reuse hardening (`process_liveness.py:44-95`) is
  authority-neutral; the only interaction risk is option (B)'s dropped refresh,
  which the chosen option (A) avoids.

### Confirmation

The mission is proven when a full WP lifecycle (claim → resume → subtask-done →
review → history append) produces a **stable content hash** over the authored
spec while claim-liveness, done-inference, and all narrative views resolve
identically to today from the reduced snapshot. Acceptance criteria:

- **AC-1** — No `implement` / `move-task` / `mark-status` / review action writes
  to `tasks/WP##.md` (snapshot mtime + bytes across a full lifecycle; assert
  unchanged). **`move-task` is an explicit target.**
- **AC-2** — Claim-liveness resolves from the reduced snapshot, not frontmatter
  `shell_pid`; a claimed WP with empty frontmatter is correctly live.
- **AC-3** — Done-inference (`emit.py` `done==total`) resolves from
  `subtask_marked` annotations; lane transitions gate identically.
- **AC-4** — `## Activity Log`, `## History`, and review sections render from
  events with no content loss vs today (resolves M7).
- **AC-5** — A full WP lifecycle produces a stable content hash (the churn fix,
  wired once, no mixed pool).
- **AC-6** — Migration backfills the corpus into seed events; idempotent
  (deterministic ULID seed-ids); reconstruction contract stated for
  timestamp-less marks; no unrecoverable data loss.

## Implementation slices (sequenced)

1. **Annotation event class + reducer fold** (Decision 1, 5) — record shape,
   `validate` bypass for non-transitions, reducer precedence. FSM untouched.
2. **Reader cutover** (Decision 4) — repoint `WorkPackage.*`, `WPMetadata`
   coercion, `stale_detection`, `emit.py` done-inference to the reduced
   snapshot; keep frontmatter fallback behind a flag until backfill verified.
3. **Migration** (Decision 3) — extend `strip_frontmatter.py`; backfill seed +
   annotation events with deterministic ULIDs; **backfill → verify** gate.
4. **Writer cutover** (Decision 2) — cut all §C2 writers (incl. `move-task`,
   `orchestrator_api`) off the file; **co-sequenced with #2160**.
5. **Delete legacy fallbacks** (Decision 4) — remove `workflow_cores.py:340-341`
   and `done_bookkeeping.py:104-105`; add the stable-hash guard (AC-5).
6. **Resolve `tracker_refs` classification** (Decision 2) — author-immutable or
   evict; ship exactly one.

## Related

- Scope: [`docs/plans/investigations/wp-runtime-state-eviction-scope.md`](../../plans/investigations/wp-runtime-state-eviction-scope.md) (§"Squad review corrections (2026-07-16)" is authoritative)
- Proposal: [`docs/plans/investigations/wp-op-schema-proposal.md`](../../plans/investigations/wp-op-schema-proposal.md) Part 4 (the corrected 4-step arc; **B3** is this mission)
- Tickets: [`docs/plans/investigations/wp-op-schema-related-tickets.md`](../../plans/investigations/wp-op-schema-related-tickets.md)
- Design: [`docs/architecture/wp-runtime-state-eviction.md`](../../architecture/wp-runtime-state-eviction.md)
- [ADR 2026-07-01-1 — No legacy-compat branches in resolvers](2026-07-01-1-no-legacy-compat-branches-in-resolvers.md)
- [ADR 2026-06-11-1 — Op as a first-class execution artifact](2026-06-11-1-op-as-first-class-execution-artifact.md)
- [ADR 2026-06-07-3 — WP lane FSM, the `genesis` lane, and the finalize event-log clobber fix](2026-06-07-3-wp-lane-fsm-genesis-and-finalize-clobber.md)
- Issues: #2093, #2400 (charter parent), #2160 (co-sequence), #1619 / #1666 (aggregate, gates the later schema flip)
