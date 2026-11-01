---
title: WP Runtime-State Eviction — Prerequisite Mission Scope
description: 'Scope for evicting runtime-mutable state (shell_pid, history, subtask-checkbox, review) from tasks/WP##.md into the event log — prerequisite for the WP-prompt flip.'
doc_status: deprecated
updated: '2026-08-12T00:00:00Z'
related:
- docs/plans/investigations/wp-op-schema-proposal.md
- docs/plans/investigations/wp-op-schema-model.md
- docs/plans/investigations/wp-op-schema-related-tickets.md
kind: Planning
---
> **RETIRED (shipped)** — this prerequisite eviction mission was ratified in ADR
> [`2026-07-19-1`](../../adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md)
> and shipped by mission `wp-runtime-state-eviction-01KXWN13` (impl `dfe6b2ead`). Evidence: #2684
> (+ #2093/#2816). Retained for historical reference; do not consult for current behavior.

# WP Runtime-State Eviction — Prerequisite Mission Scope

The squad pressure-test ([wp-op-schema-proposal.md](wp-op-schema-proposal.md) Part 4,
**B3/B4**) established that the YAML-authoritative / markdown-derived WP prompt
**cannot be built** while `tasks/WP##.md` still holds runtime-mutable state that
live code writes and reads. Declaring that file "derived, do not edit" would
clobber claim-liveness and implementation evidence on the very next `implement`.

**This mission is that unblock.** It moves *all* runtime-mutable WP state out of
the WP file into the canonical append-only status/event log — generalising the
already-shipped `lane` retirement (`frontmatter.py:47-49`;
`task_metadata_validation.py:82` MIGRATION-ONLY). After it lands, `WP##.md` holds
**only static design-intent**, and the WP-prompt schema work (proposal Parts 1–3)
becomes a pure formalization with no runtime collision.

This is not new construction against the milestone — it **is the charter of #2093 / #2400** (static intent stays canonical; dynamic runtime state retires to
event-log/invocation authority), carried to completion.

---

> ⚠ **The writer/reader inventory and AC list below were materially incomplete —
> see [Squad review corrections](#squad-review-corrections-2026-07-16) at the end,
> which supersede them.** The completeness lens found 4 `shell_pid` writers (this
> doc named 1), `move-task` missing from AC-1, and an existing canonical
> `MUTABLE_FIELDS` set that must be reconciled. Read the corrections as
> authoritative.

## Problem: what still lives in `WP##.md` and churns

| Runtime field | Where in file | Writer (live) | Reader (live) | Why it must move |
|---|---|---|---|---|
| `shell_pid`, `shell_pid_created_at` | frontmatter | `implement.py:1730` → `write_shell_pid_claim_to_file` (`frontmatter.py:393`) | `stale_detection.py:403` (claim-liveness) | Claim ownership written on every implement; a re-render from a static spec erases it → live claims read as reclaimable. |
| `history[]` | frontmatter | `add_history_entry` (`frontmatter.py:347`) | audit/display | In-place mutable list; perturbs the file hash on every event. |
| subtask **checkbox state** (`- [x] T###`) | body / `tasks.md` | `tasks_materialization.py:260,304` (mark-status) | `subtask_rows.py:181` → `emit.py:302` (done-inference: `done==total`) | Completion evidence that gates lane transitions; not reconstructable from a static spec. |
| `review_status`, `reviewed_by`, `reviewer*`, `review_feedback` (pointer) | frontmatter | review-cycle writes | `workflow_cores.py:341` | Review-cycle state; already declared event-log-owned in intent (`frontmatter.py:47-48`) but still written. |
| `activity_log` (narrative) | body `## Activity Log` (1670×) | appended mid-work | dashboard display | Free-form narrative; has no structured home today. |
| `lane` | — | **already evicted** ✅ | — | The precedent this mission generalises. |

The static residue that **stays** in the WP file: `work_package_id`, `title`,
`dependencies`, `requirement_refs`, `plan_concern_refs`, `owned_files`,
`create_intent`, `authoritative_surface`, `scope`, `task_type`, `cross_cutting`,
`agent_profile` (authored), `tracker_refs`, `branch_strategy` /
`merge_target_branch` / `planning_base_branch`, `priority`, `phase`, and the
prompt-body prose. (Note M1 from Part 4: the branch-contract + `priority`/`phase`
are static and must be **kept**, not evicted.)

## Target architecture

Each evicted field gets exactly one new home; `WP##.md` becomes a read-derived
view for the runtime parts.

| Field | New authority | Mechanism |
|---|---|---|
| `shell_pid` (+ baseline) | status event log | new `claimed`-event payload carrying `shell_pid`/`baseline`; `stale_detection` reads the reduced snapshot, not frontmatter. |
| `history[]` | status event log | already the event stream; drop the frontmatter mirror; render `## History` from reduced events at display time. |
| subtask checkbox `done/total` | status event log | a `subtask_marked` event (id, status); `count_wp_section_subtask_rows` is replaced by a reducer count; the body checkbox becomes a *rendered* view. |
| review-cycle fields | status event log | already modelled as review events; drop the frontmatter mirror. |
| `activity_log` narrative | status event log | new event payload with a free-text `note` (the one genuinely-new event shape — resolves Part 4 **M7** data-loss). |

**Invariant after eviction:** `content_hash(WP##.md)` (or its successor
`content_hash(spec)`) is stable across *every* runtime transition — claim,
subtask-done, review, history append. That is the acceptance test that proves the
mission (and directly delivers the original hash-churn fix).

## Acceptance criteria (draft)

- **AC-1** — No `spec-kitty implement` / `mark-status` / review action writes to
  `tasks/WP##.md`. (Guard test: snapshot file mtime+bytes across a full WP
  lifecycle; assert unchanged.)
- **AC-2** — Claim-liveness (`stale_detection`) resolves from the reduced event
  snapshot, not frontmatter `shell_pid`; a claimed WP is correctly detected as
  live with an empty frontmatter.
- **AC-3** — Done-inference (`emit.py` `done==total`) resolves from reduced
  subtask events; lane transitions gate identically to today.
- **AC-4** — `## Activity Log`, `## History`, review sections still render (from
  events) with no content loss vs today (resolves M7).
- **AC-5** — A full WP lifecycle produces a **stable content hash** (the churn
  fix; wire once, no mixed pool — resolves Part 4 **M2/M4**).
- **AC-6** — Migration backfills existing 278 missions' frontmatter runtime
  fields into seed events; idempotent; no data loss.

## Sequencing & dependencies

1. **Reconcile with #2093 / #2400** — this mission *is* their charter completion;
   it should land **under** #2400, not as a rival. Accept #2093's authority ruling
   (static intent stays canonical in the WP file).
2. **Blocks** the WP-prompt schema flip (proposal Parts 1–3) and the semantic
   content-hash (which must co-move with `sync/body_upload.py`, Part 4 M2).
3. **Independent of** the Op-debrief slice (proposal Part 4 — ships separately).
4. **Gated behind / coordinated with #1619** only for the *final* authority
   election (enrich `WPMetadata`); the eviction itself is #1619-neutral (it moves
   state to the already-shipped event log, adding no new aggregate).
5. **Coordinate with #2160** (coord-authority) — it also writes the `shell_pid`
   claim into frontmatter (`implement.py:1730`); the eviction must land with, not
   against, that writer's restructuring.

## Out of scope (explicitly)

- The WP-prompt body schema / YAML-authority flip (that is the *finish*, gated on
  this mission).
- Electing the canonical static model (`WorkPackageEntry` vs enrich `WPMetadata`)
  — deferred to the schema mission; grounding prefers enriching `WPMetadata`.
- The Op debrief (separate, landable now).

## Open questions

1. Is the `activity_log` note event a first-class status event, or a Tier-2
   evidence-style sidecar keyed by WP? (Affects M7's fix shape.)
2. Does subtask completion become an event per subtask, or a single
   `subtasks_snapshot`? (Reducer complexity vs event volume.)
3. Do we evict review-cycle frontmatter in this mission or fold it into the
   in-flight review-state work under #2160?
4. Migration ordering: backfill events **before** or **after** the writers are
   cut over? (AC-6 idempotency depends on the answer.)

---

# Squad review corrections (2026-07-16)

An architecture-and-roadmap review squad (architect-alphonso · paula-patterns ·
planner-priti) reviewed this scope. Verdict: **direction correct and correctly
homed under #2093/#2400, but REWORK-SCOPE before ADR-lock** — the inventory was
incomplete/inverted and one load-bearing architectural decision was unaddressed.
These corrections are authoritative over the tables above.

## C1 — The load-bearing gap: runtime state mutates OFF the transition axis

`StatusEvent` is a **transition ledger** — it mandates `from_lane`/`to_lane`
(`status/models.py:224-226`) and `validate_transition` rejects edges not in the
9-lane FSM (`status/transitions.py:53,83-99`). But three of the evicted mutations
are **non-transition**:

- **`shell_pid` refresh on resume** — rewritten on *every* `implement`/`agent action`
  invocation, including resume of an already-`in_progress` WP (`implement.py:1730`,
  `workflow_executor.py:669`), with no accompanying lane change.
- **subtask marking** — mid-`in_progress` `- [x] T###` flips.
- **activity-log notes** — appended mid-work.

A `claimed`-event payload captures only `planned→claimed`; it cannot carry the
resume refresh or mid-work marks. **This is the pivotal ADR decision:** either
(a) introduce a non-transition annotation/self-edge event class (a real FSM +
reducer change — `reducer.py:160` precedence), or (b) fold onto existing
transitions and accept a **documented behavior change** (a resumed WP carries a
stale PID → staleness falls back to the git-timestamp heuristic,
`stale_detection.py:254-301`). Everything else rests on this.

*Mechanism note (A2):* `policy_metadata: dict|None` (`models.py:234`) is already a
generic event sidecar (`implement.py:1328`), so `(shell_pid, baseline)` can ride it
with **no wire-schema change**; the reduced *snapshot* is where they become typed.
The C-007 PID-reuse move is authority-neutral (`process_liveness.py:44-95`) — the
only risk is option (b)'s dropped refresh.

## C2 — Corrected writer inventory (the table above named 1 of 4 shell_pid writers)

| Field | Live writers (corrected) |
|---|---|
| `shell_pid` (+baseline) | `implement.py:1730`, `workflow_executor.py:669` (implement action), `:1337` (review action), `tasks_move_task.py:1638` — **4 writers** |
| `agent` scalar | `workflow_executor.py:667`, `tasks_move_task.py:1631` |
| `assignee` | `tasks_move_task.py:1629` |
| `activity_log` (body) | `tasks.py:913`, `workflow_executor.py:679` & `:1344`, `tasks_move_task.py:1645`, `orchestrator_api/commands.py:1563` — **6 writers** (incl. external orchestrator-api) |
| subtask checkbox | `tasks_materialization.py:260,304` (WP##.md) + `tasks_move_task.py:1662` uncheck (**`tasks.md`**) |
| `review_artifact_override_{at,actor,wp_id,reason}` | `tasks_materialization.py:58-61,125-128` — **unclassified** in the original scope |
| `base_branch`/`base_commit`/`created_at` | `implement_support.py:133-142` (fresh-lane creation) |
| `history[]` frontmatter mirror | **DEAD** — `add_history_entry` (`frontmatter.py:347`) has **no live callers**; the mirror is already gone. |

**`move-task` is the primary lane-transition writer and was absent from AC-1** — it
alone rewrites `shell_pid`+`agent`+`assignee`+activity-log+`tracker_refs` and
unchecks subtasks. The first `move-task` after a naive eviction churns the hash on
the very next transition.

## C3 — Corrected classification

- **`agent`, `assignee`** → **EVICT** (runtime-written; original scope left them
  unclassified). Confirmed in the existing `strip_frontmatter.py:MUTABLE_FIELDS`.
- **`tracker_refs`** → **runtime-written** (`tasks_move_task.py:1575-1595`, FR-011) —
  **cannot be both static and derived.** Re-decide: either keep authored+immutable
  (move `--tracker-ref` writes elsewhere) or evict. (Original scope wrongly listed
  it static.)
- **`review_artifact_override_*`** → classify (evict).
- **`progress`** → in `MUTABLE_FIELDS` but no live writer/reader found → explicitly
  **retire**, don't silently drop.
- **`history`** → resolve the contradiction: `strip_frontmatter.py` files it
  **STATIC**, but the mission intends to evict it; since the frontmatter mirror is
  dead (C2), "evict" = confirm-removed + render `## History` from events.
- **Static residue confirmed sound:** `branch_strategy`/`merge_target_branch`/
  `planning_base_branch`/`priority`/`phase`/`task_type`/`cross_cutting`/
  `owned_files`/`agent_profile` have **no runtime writers** anywhere.

## C4 — Reconcile with the existing canonical seam

`migration/strip_frontmatter.py` already defines
`MUTABLE_FIELDS = {lane, review_status, reviewed_by, review_feedback, progress,
shell_pid, assignee, agent}`. **Extend this single authority** (add `history`,
`shell_pid_created_at`, `activity_log`, `review_artifact_override_*`, resolve
`tracker_refs`) rather than authoring a rival list. One canonical runtime-mutable
field-set, or the eviction leaks by construction.

## C5 — Delete legacy resolver fallbacks (don't leave them inert)

Eviction must **remove**, not merely stop writing:
- `workflow_cores.py:340-341` — reads `review_status`/`review_feedback` from
  frontmatter as a fallback when the canonical `review_ref` is absent.
- `done_bookkeeping.py:104-105` — reads `meta.reviewed_by`/`review_status` off
  `WPMetadata` (frontmatter).

Leaving these = a dormant no-canonical-field resolver path (violates the *no legacy
resolver paths* invariant). Also repoint the model-property readers
`WorkPackage.{shell_pid,agent,assignee}` (`task_utils/support.py:288,292,296`) and
`WPMetadata` coercion (`wp_metadata.py:364,580`) — the most-consumed reader layer,
omitted from the original reader census.

## C6 — Migration contract (AC-6 made honest)

- **Deterministic ULID-valid seed-ids** — the reducer dedups by `event_id` and it
  must match `ULID_PATTERN` (`reducer.py:139-149`, `models.py:70`); a content hash
  is not a valid ULID. Use a namespaced deterministic ULID from
  `mission_id+wp_id+field`, or re-runs double-seed.
- **Timestamp honesty** — subtask checkboxes carry no `at`; a backfilled
  `subtask_marked` event has no truthful timestamp. AC-6's "no data loss" is not
  literally achievable — state the reconstruction contract (e.g. clamp to the WP's
  `claimed` timestamp).
- **Strict order** — **backfill → verify → reader cutover → writer cutover**, with
  readers keeping the frontmatter fallback until backfill is verified. Writer-first
  opens the exact B3 clobber window.

## C7 — Sequencing correction

- **#2160 collision (material):** the `shell_pid` writers overlap #2160's Wave-2
  `implement.py`/`workflow.py` degod. The eviction's shell_pid move must
  **co-sequence with (or land behind) #2160**, not race it. Add a blocks/blocked_by
  edge.
- The eviction **alone delivers the churn fix** (once nothing writes runtime state,
  even the raw-byte hash is stable) → the separate "semantic-only hash" slice
  shrinks to a **small follow-up** (still co-move `body_upload` TOCTOU, no mixed
  parity pool).

## C8 — The five decisions the ADR must pin

1. **Non-transition event shape** (C1) — self-edge/annotation event class vs
   fold-onto-transition; typed snapshot fields vs `policy_metadata` blob.
2. **Stable-content-hash + total-eviction invariant** — `WP##.md` (+`tasks.md`
   subtask surface) is the *sole* churn surface; forces C2's missed writers into scope.
3. **Migration contract** (C6) — deterministic ULID seed-ids, timestamp honesty,
   backfill→verify→reader→writer ordering; extend `strip_frontmatter.py`.
4. **#2093/#2400 relationship** — land under #2400 as charter-completion; accept
   static-intent-canonical-in-file; **delete** the review-feedback fallbacks (C5).
5. **FSM invariant** — whether self-transition edges become legal in the 9-lane
   matrix, and reducer precedence for payload-only self-events.
