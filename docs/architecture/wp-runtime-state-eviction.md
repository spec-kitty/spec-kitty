---
title: WP Runtime-State Eviction — Architecture Design
description: 'Architecture design for evicting runtime-mutable state from tasks/WP##.md into the append-only event log via a non-transition annotation event class; ADR 2026-07-16-1.'
doc_status: proposal
updated: '2026-10-05'
audience: docs/context/audience/internal/system-architect.md
related:
- docs/adr/3.x/2026-07-16-1-wp-runtime-state-authority-event-log-eviction.md
- docs/architecture/status-model.md
- docs/architecture/execution-lanes.md
- docs/architecture/runtime-loop.md
---
# WP Runtime-State Eviction — Architecture Design

This design realises [ADR 2026-07-16-1](../adr/3.x/2026-07-16-1-wp-runtime-state-authority-event-log-eviction.md).
It moves *every* runtime-mutable field out of `tasks/WP##.md` (and the `tasks.md`
subtask surface) into the canonical append-only event log, so that `WP##.md`
holds **only static design-intent** and hashes stably across every runtime
mutation. It is the charter-completion of #2093 / #2400 and the prerequisite for
the YAML-authoritative WP-prompt schema (proposal Part 4 **B3**).

The authoritative scope, corrected writer/reader inventory, and the five pinned
decisions live in the ADR and in
[`docs/plans/investigations/wp-runtime-state-eviction-scope.md`](../plans/investigations/wp-runtime-state-eviction-scope.md)
§"Squad review corrections (2026-07-16)". This document is the buildable design
against those decisions.

## 1. The axis problem (why this is not a "move a field" change)

`status.events.jsonl` is a **transition ledger**. `StatusEvent` mandates
`from_lane` / `to_lane` (`status/models.py:224-226`), and `validate_transition`
rejects any edge outside the 9-lane FSM (`status/transitions.py:53,83-99`). Three
of the evicted mutations are **non-transition** — they carry no lane change:

| Mutation | When | Today's home |
|---|---|---|
| `shell_pid` refresh on **resume** | every `implement` / `agent action`, incl. resume of an already `in_progress` WP | `implement_claim.py::_start_wp_implementation_status`, `workflow_executor.py:669` |
| **subtask mark** (`- [x] T###`) | mid-`in_progress` | `tasks_materialization.py:260,304`; uncheck in `tasks.md` at `tasks_move_task.py:1662` |
| **activity-log note** | mid-work, any time | 6 writers incl. `orchestrator_api/wp_lifecycle.py::append_history` |

A transition-event payload cannot carry any of these without a lane change to
attach to. The design's core structural move is therefore a **non-transition
annotation event class** (ADR Decision 1) that shares the same append-only log
and reducer but is *not* a transition.

## 2. Target architecture per evicted field

`WP##.md` becomes a read-derived view for the runtime parts; each field gets
exactly one new authority.

| Evicted field | New authority | Mechanism |
|---|---|---|
| `shell_pid` + baseline (**initial claim**) | event log | rides the real `planned→claimed` transition via `policy_metadata` (no wire-schema change); typed in the reduced snapshot |
| `shell_pid` refresh (**resume**) | event log | `shell_refresh` **annotation event** (non-transition); reducer last-writer-wins |
| subtask `done/total` | event log | `subtask_marked` **annotation event** (id, status); done-inference counts from the reduced snapshot, not the checkbox |
| `activity_log` narrative | event log | `activity_note` **annotation event** with a free-text `note` payload (resolves M7 data-loss) |
| `history[]` frontmatter mirror | event log | already DEAD (`add_history_entry`, `frontmatter.py:347`, no live callers) — confirm-removed; render `## History` from events |
| review-cycle fields (`review_status`, `reviewed_by`, `review_feedback`) | event log | already modelled as review events + `review_ref`; drop the frontmatter mirror and its fallback readers |
| `agent` (scalar), `assignee` | event log | carried on the claim/transition actor + reduced snapshot; frontmatter scalars retired |
| `review_artifact_override_{at,actor,wp_id,reason}` | event log | evict (annotation or review-event payload) |
| `base_branch` / `base_commit` / `created_at` | event log | lane-genesis payload on the fresh-lane creation event (`implement_support.py:133-142`) |
| `tracker_refs` | **UNRESOLVED — decide in mission** | either author-immutable (move `--tracker-ref` write off the file) or evict; ship exactly one (ADR Decision 2 / scope §C3) |
| `progress` | — | **retire** (no live writer/reader) |

Static residue that **stays** authored in `WP##.md` (no runtime writers
anywhere — scope §C3): `work_package_id`, `title`, `dependencies`,
`requirement_refs`, `plan_concern_refs`, `owned_files`, `create_intent`,
`authoritative_surface`, `scope`, `task_type`, `cross_cutting`, `agent_profile`
(authored assignment), `branch_strategy` / `merge_target_branch` /
`planning_base_branch`, `priority`, `phase`, and the prompt-body prose.

## 3. Event-schema additions

The additions are **additive** and share the existing JSONL log + reducer.

### 3.1 Transition-carried payload (initial claim)

No new event type. The `planned→claimed` `StatusEvent` carries `(shell_pid,
baseline)` in the existing generic `policy_metadata: dict|None`
(`models.py:234`), already used as an event sidecar by `implement_claim.py::_start_wp_implementation_status` (via `status.claim_policy_metadata`, defined in `status/emit.py`). The
**reduced snapshot** is where the pair becomes typed — frontmatter never sees
it.

### 3.2 Annotation event class (non-transition)

A new record class in the same log, distinguished from transitions by the
**absence of `from_lane` / `to_lane`** and the presence of `annotation_kind`:

| Field | Notes |
|---|---|
| `event_id` | ULID; dedup key (`reducer.py:139-149`) |
| `wp_id` | target WP |
| `at` | truthful timestamp (see §5 for reconstructed marks) |
| `actor` | who annotated |
| `annotation_kind` | `shell_refresh` \| `subtask_marked` \| `activity_note` |
| `payload` | typed per kind: `{pid, created_at}` / `{subtask_id, status}` / `{note}` |

Annotation events **bypass `validate_transition`** (they are not transitions;
ADR Decision 5) and are folded by the reducer as payload updates. The 9-lane FSM
and its 27 transition pairs are unchanged.

### 3.3 Reducer fold + precedence

Fold in event order (`reducer.py:160` precedence extended, not rewritten):

1. Transition events set the lane and any transition-carried payload (e.g. the
   claim's `shell_pid`).
2. Annotation events fold their typed payload onto the reduced snapshot
   **after** transitions, **last-writer-wins per field**.
3. At equal timestamps, the annotation fold applies after the transition fold —
   so a later `shell_refresh` deterministically supersedes the claim's initial
   `shell_pid`, and an out-of-order read cannot clobber it.

The reduced snapshot gains typed slots: `shell_pid`, `shell_pid_created_at`,
`baseline`, `subtask_state: {id -> status}`, `notes: [str]`, plus the existing
review/lane fields. These slots are the **sole** read authority after cutover.

## 4. Reader-repoint list (incl. legacy-fallback deletions — scope §C5)

Eviction means **remove, not merely stop writing** (ADR Decision 4;
[ADR 2026-07-01-1](../adr/3.x/2026-07-01-1-no-legacy-compat-branches-in-resolvers.md)).

**Repoint to the reduced snapshot:**

| Reader | Today | After |
|---|---|---|
| claim-liveness | `stale_detection.py:403` reads frontmatter `shell_pid` | reads snapshot `shell_pid` |
| done-inference | `subtask_rows.py:181` → `emit.py:302` counts body checkboxes (`done==total`) | counts snapshot `subtask_state` |
| model properties | `WorkPackage.{shell_pid,agent,assignee}` (`task_utils/support.py:288,292,296`) | snapshot-backed |
| metadata coercion | `WPMetadata` coercion (`wp_metadata.py:364,580`) | snapshot-backed |

**Delete outright (dormant no-canonical-field fallbacks):**

| Fallback | Location | Reads |
|---|---|---|
| review-status frontmatter fallback | `workflow_cores.py:340-341` | `review_status` / `review_feedback` when canonical `review_ref` absent |
| reviewed-by frontmatter fallback | `done_bookkeeping.py:104-105` | `meta.reviewed_by` / `review_status` off `WPMetadata` |

Leaving either = a dormant no-canonical-field resolver path (violates the
*no legacy resolver paths* invariant). They are deleted in the same slice that
cuts the writers.

## 5. Migration sequence (ADR Decision 3 — scope §C6)

**Strict order — writer-first is prohibited (it opens the B3 clobber window):**

```
backfill  →  verify  →  reader cutover  →  writer cutover
                        (fallback kept until verify passes)
```

1. **Backfill** — extend `migration/strip_frontmatter.py:MUTABLE_FIELDS` (the
   single canonical field-set) with `history`, `shell_pid_created_at`,
   `activity_log`, `review_artifact_override_*`, resolved `tracker_refs`. For
   each WP, emit seed transition + annotation events reconstructing today's
   frontmatter/checkbox state.
   - **Deterministic ULID seed-ids** — `event_id` must match `ULID_PATTERN`
     (`models.py:70`); a content hash is not a valid ULID. Use a namespaced
     deterministic ULID from `mission_id + wp_id + field`, so re-runs are
     idempotent (the reducer dedups by `event_id`).
   - **Timestamp honesty** — subtask checkboxes carry no `at`. A reconstructed
     `subtask_marked` has no truthful timestamp; the reconstruction contract
     **clamps to the WP's `claimed` timestamp** rather than fabricating
     precision. "No data loss" is stated against this contract, not as literal
     millisecond fidelity.
2. **Verify** — read back persisted events; confirm the reduced snapshot equals
   the pre-migration frontmatter/checkbox state (count + value parity).
3. **Reader cutover** — repoint §4 readers to the snapshot; keep the frontmatter
   fallback **behind a flag** until verify passes for the corpus.
4. **Writer cutover** — cut every §2 / scope §C2 writer off the file, incl.
   `move-task` and the external `orchestrator_api`. **Co-sequence with #2160**
   (its Wave-2 `implement.py` / `workflow.py` degod owns the same `shell_pid`
   writers — add a `blocks` / `blocked_by` edge; do not race it).
5. **Delete fallbacks** (§4) + land the stable-hash guard.

## 6. Invariants & acceptance criteria

| Invariant | Guard (AC) |
|---|---|
| `WP##.md` is never written by runtime | **AC-1** — snapshot mtime+bytes unchanged across a full WP lifecycle; **`move-task` is an explicit target** |
| Claim-liveness from snapshot, not frontmatter | **AC-2** — a claimed WP with empty frontmatter is correctly detected live |
| Done-inference from annotation events | **AC-3** — `done==total` resolves from `subtask_marked`; lane transitions gate identically |
| No narrative data loss | **AC-4** — `## Activity Log` / `## History` / review render from events, no content loss (resolves M7) |
| Stable content hash | **AC-5** — a full lifecycle produces an invariant hash over the authored spec (churn fix; wired once, no mixed pool) |
| Idempotent, honest migration | **AC-6** — deterministic ULID seed-ids; reconstruction contract stated; no unrecoverable loss |
| **9-lane FSM unchanged** | self-transition edges never legal; `validate_transition` still rejects non-lane-changing edges; annotations live outside the matrix |
| **Single canonical field-set** | only `strip_frontmatter.py:MUTABLE_FIELDS` enumerates runtime-mutable fields; no rival list |

## 7. Explicitly out of scope (later missions)

- The YAML-authoritative / markdown-derived WP-prompt flip (proposal Parts 1–3)
  — this eviction is its *prerequisite*, not its delivery.
- Electing the canonical static model (`WorkPackageEntry` vs enrich `WPMetadata`)
  — deferred to the schema mission (grounding prefers enriching `WPMetadata`;
  proposal B4).
- The semantic-only content-hash slice — shrinks to a small follow-up once
  nothing writes runtime state (even the raw-byte hash is then stable); still
  co-moves `sync/body_upload.py` TOCTOU with no mixed parity pool (scope §C7).
- The Op-debrief slice (proposal Part 4) — independent, landable now.
- The final WP/Mission aggregate authority election — gated on #1619 / #1666.

## See also

- [ADR 2026-07-16-1 — WP runtime-state authority](../adr/3.x/2026-07-16-1-wp-runtime-state-authority-event-log-eviction.md)
- [Status Model](status-model.md) — the append-only event log this design extends
- [Execution Lanes](execution-lanes.md), [Runtime Loop](runtime-loop.md)
