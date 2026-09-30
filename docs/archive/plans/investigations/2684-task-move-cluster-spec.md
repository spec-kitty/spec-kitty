---
title: 'Feature spec: evict runtime-mutable WP state into the event log (#2684)'
description: 'Consolidated feature spec for the #2684 runtime-state eviction: field-by-field authority, the InnerStateChanged event model, migration contract, and acceptance criteria.'
doc_status: deprecated
updated: '2026-08-12'
related:
- docs/adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md
---
> **RETIRED (shipped)** — this spec's #2684 runtime-state eviction was ratified in ADR
> [`2026-07-19-1`](../../../adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md)
> and shipped by mission `wp-runtime-state-eviction-01KXWN13` (impl `dfe6b2ead`). Evidence: #2684
> (+ #2093/#2816). Retained for historical reference; do not consult for current behavior.

# Feature Specification: Evict runtime-mutable WP state into the event log

**feature branch**: `mission-prep/2684-wp-runtime-state-eviction`
**Created**: 2026-07-19
**Status**: Draft (spec + ADR authored; no cluster-touching work pending — the adjacent PRs are `pr:deferred` and yield to this mission)
**Input**: #2684 (P0) — "Evict runtime-mutable WP state (shell_pid, history, subtask-checkbox, review-cycle, activity-log) from tasks/WP##.md into the event log", the execution vehicle for the #2093 authority ruling.
**Grounding**: `docs/plans/investigations/2684-task-move-cluster-scoping.md` (§0 = the seven resolved decisions). **Design of record**: `docs/adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md`.

> This spec encodes decisions already ratified by HiC (brief §0 / the ADR), including that **this
> mission owns the `implement.py:1730` shell_pid-writer restructuring** (the #2160 co-sequence is
> resolved — see FR-014). No cluster-touching work is pending; the adjacent PRs are `pr:deferred`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Hand a completed WP to review without hand-ticking checkboxes (Priority: P1)

An operator/agent finishes a WP's work and moves it to `for_review`. Completion recorded through the
canonical path must be honored by the review gate — no manual `mark-status` per subtask.

**Why this priority**: This is the P0 operator friction (mission #2736 catfooding) and the invariant
the already-merged red test pins. It is the visible payoff of the eviction.

**Independent Test**: On a `single_branch` mission, complete WP01's subtasks via the canonical path
and run `move-task WP01 --to for_review` — it succeeds without touching `tasks.md` checkboxes.
(`tests/regression/test_issue_2684_subtask_completion_event_sourced.py` flips green.)

**Acceptance Scenarios**:
1. **Given** WP01 `in_progress` with its subtasks recorded complete in the reduced snapshot **and**
   `tasks.md` checkboxes not hand-edited, **When** `move-task WP01 --to for_review`, **Then** it
   succeeds and the WP is `for_review`.
2. **Given** WP01 with genuinely-incomplete subtasks (no completion recorded anywhere), **When**
   `move-task WP01 --to for_review`, **Then** it is correctly refused (the gate honors the log, it
   does not "always allow").

### User Story 2 - No false drift across a WP lifecycle (Priority: P1)

The dossier/sync content hash of `tasks/WP##.md` and `tasks.md` stays stable across
claim → subtask-done → review → history, because nothing writes runtime state into those files.

**Why this priority**: AC-5 is the headline proof of the mission and the long-homeless dossier churn
fix.

**Independent Test**: Run a WP through a full lifecycle; assert the raw-byte `content_hash_sha256` of
`tasks/WP##.md` and the WP's `tasks.md` section is unchanged from `claimed` to `done`.

**Acceptance Scenarios**:
1. **Given** a WP taken through claim, subtask completion, review, and history, **When** the dossier
   parity hash is computed at each step, **Then** the WP's file hashes are identical throughout.

### User Story 3 - Claim-liveness and resume resolve from the log, not frontmatter (Priority: P2)

Claim-liveness reads the reduced snapshot. A claimed WP whose frontmatter carries no `shell_pid` is
still detected live; a resumed `in_progress` WP refreshes its PID via an off-axis event and is not
falsely flagged stale.

**Why this priority**: AC-2; and it closes the Option-B false-stale window by construction (Option A
carries the resume refresh).

**Independent Test**: Claim a WP (empty frontmatter), assert liveness = live from the snapshot; resume
it, assert the PID refresh is recorded as an `InnerStateChanged` event and liveness stays live.

**Acceptance Scenarios**:
1. **Given** a claimed WP with no frontmatter `shell_pid`, **When** liveness is evaluated, **Then** it
   resolves live from the reduced snapshot.
2. **Given** a resumed `in_progress` WP, **When** its shell PID refreshes, **Then** an
   `InnerStateChanged` delta records it with a truthful `at`, no lane transition, and no `force_count`
   increment.

### User Story 4 - Activity Log / History / review render from events (Priority: P2)

The `## Activity Log`, `## History`, and review sections render from the event log with no content
loss, now that they are no longer written into the WP file.

**Why this priority**: AC-4; guards against the M7 data-loss risk during eviction.

**Independent Test**: Drive a WP through notes + a review cycle; assert the rendered Activity
Log/History/review content matches, sourced from events.

### User Story 5 - Existing missions migrate idempotently (Priority: P3)

A migration backfills existing missions' frontmatter/checkbox runtime state into seed events, and is
safe to re-run.

**Why this priority**: AC-6; makes the cutover safe for the live corpus.

**Independent Test**: Run the migration twice on a corpus; assert the reduced snapshot equals
pre-migration state by count+value and that re-running seeds nothing new.

### Edge Cases

- Subtask checkboxes carry **no timestamp** → the backfilled mark is clamped to the WP's `claimed`
  timestamp; "no data loss" is asserted against count+value parity, **not** literal temporal fidelity.
- A new off-axis emit site that resolves its write target from `Path.cwd()` silently reopens #2647 —
  targets MUST come from stored topology/target branch (guard: `test_transaction_legacy_topology_routing`).
- `history[]` frontmatter is dead **and** mis-filed in `STATIC_FIELDS` — delete outright, no migration.
- `progress` is dead — retire explicitly, don't silently drop.
- The external writer `orchestrator_api/commands.py:1563` (Activity Log) must migrate too, or it keeps
  writing the retired surface from outside the host CLI.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Introduce a single generic non-transition event, `InnerStateChanged`, carrying a
  **typed** partial delta (`WPInnerStateDelta` — optional typed fields, not a free `dict`). It has no
  `from_lane`/`to_lane`, bypasses `validate_transition`, and is folded by the reducer.
- **FR-002**: The reducer folds `InnerStateChanged` deltas onto the reduced snapshot with per-field
  merge rules — **replace** for `shell_pid`/`shell_pid_created_at` and per-subtask status, **union**
  for `tracker_refs`, **append** for `notes` — after transition folds, last-writer-wins, and **never**
  increments `force_count`. The snapshot gains typed slots: `shell_pid`, `shell_pid_created_at`,
  `subtasks: Mapping[str, Status]`, `notes: list`, `tracker_refs`.
- **FR-003**: Subtask completion is recorded as an `InnerStateChanged` `subtasks` delta (single or
  batch). The review gate `_guard_subtasks` (`tasks_transition_core.py:384` via `tasks_shared.py:412`)
  and done-inference `_infer_subtasks_complete` (`status/emit.py:279`) resolve unchecked/`done==total`
  from the reduced snapshot, **not** `tasks.md` bytes.
- **FR-004**: The claim `(shell_pid, shell_pid_created_at)` rides the real `planned→claimed`
  transition via the existing `policy_metadata` sidecar (no wire-schema change); a **resume** refresh
  of an already-`in_progress` WP is recorded as an `InnerStateChanged` delta.
- **FR-005**: Claim-liveness (`stale_detection.py:402-403`) and the model readers
  `WorkPackage.{shell_pid,agent,assignee}` (`task_utils/support.py:287-296`) and `WPMetadata`
  coercion resolve from the reduced snapshot; the frontmatter fallback is retained **behind a flag
  until backfill is verified**, then removed.
- **FR-006**: `tracker_refs` is runtime, event-sourced: `map-requirements`
  (`tasks_map_requirements.py:428`) and `move-task` (`tasks_move_task.py:1721`) emit an
  `InnerStateChanged` `tracker_refs` union delta; FR-011 runtime append is preserved; `tracker_refs`
  is removed as a WP-file write.
- **FR-007**: `## Activity Log` notes are recorded as `InnerStateChanged` `note` appends from all six
  writers, **including** the external `orchestrator_api/commands.py:1563`; the section renders from
  events.
- **FR-008**: No `implement`/`mark-status`/`move-task`/review action writes `tasks/WP##.md` or the
  `tasks.md` subtask surface. The four `shell_pid` writers (`implement.py:1730`,
  `workflow_executor.py:695` & `:1370`, `tasks_move_task.py:1770`), the `agent`/`assignee` writers,
  the subtask checkbox write/uncheck (`tasks_mark_status.py:266`, `tasks_move_task.py:1806`), and the
  move-task god-write (`_mt_persist_wp_file`) are cut off the file.
- **FR-009**: Evict all review-cycle state in this mission: **delete** the dead verdict-field read
  fallbacks `workflow_cores.py:340-341` and `done_bookkeeping.py:104-105` (guaranteeing canonical
  done-evidence), **and** evict the actively-written `review_artifact_override_*`
  (`tasks_materialization.py:58-61,125-128`) to the event log.
- **FR-010**: Extend the canonical `migration/strip_frontmatter.py:MUTABLE_FIELDS` (do not fork) to
  add `shell_pid_created_at`, `review_artifact_override_*`, `reviewer_shell_pid`, and move `history`
  out of `STATIC_FIELDS`; **retire `progress`** (remove from the set/schema; document the removal).
  Delete `history[]` outright (dead, no migration).
- **FR-011**: Migration order is **backfill → verify → reader cutover → writer cutover → delete
  fallbacks + land the AC-5 hash guard**. Backfill seeds transition + `InnerStateChanged` events with
  **deterministic namespaced ULID** ids (from `mission_id + wp_id + field`; a content hash is not a
  valid ULID); it is idempotent; verify confirms snapshot == pre-migration state by count+value.
- **FR-012**: Every new off-axis emit site resolves its write target from stored topology/target
  branch, **never `Path.cwd()`** (do not reopen #2647).
- **FR-013**: A refactor-stable architectural test asserts no consumer reads a dynamic frontmatter
  field as authority (the #2093 invariant).
- **FR-014**: This mission **owns** the restructuring of the `implement.py:1730` shell_pid claim
  writer required by the eviction. The prior "co-sequence with #2160" constraint is retired: #2160's
  writer work is `pr:deferred` and yields to this mission, so the writer cutover proceeds within this
  mission without an external `blocks/blocked_by` gate. The #2647 invariant (FR-012) still binds every
  emit site touched by that restructuring.

### Key Entities

- **`InnerStateChanged`** — the generic off-axis event; no lane transition; typed `WPInnerStateDelta`.
- **`WPInnerStateDelta`** — typed partial: `shell_pid?`, `shell_pid_created_at?`,
  `subtasks?: Mapping[str, Status]`, `note?: str`, `tracker_refs?: list`.
- **Reduced snapshot (per WP)** — gains typed runtime slots; the single read path for runtime state.

## Assumptions

- **This mission owns the `implement.py:1730` restructuring** (FR-014). The former #2160 hard
  co-sequence is resolved: #2160's writer work is `pr:deferred` and yields to this mission, so the
  writer cutover is **not** gated on external #2160 work and this branch does **not** wait on it.
- **#2684 is authoritative** over the WP-metadata surface; deferred PRs (#2641, #2766, #2612, and
  #2160's writer work) yield to the mission and rebase onto it, not the reverse.
- The seven design decisions (brief §0 / ADR 2026-07-19-1) are settled and not re-litigated here.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001 (AC-1)**: A full WP lifecycle leaves `tasks/WP##.md` bytes and mtime unchanged (no runtime
  write).
- **SC-002 (AC-2)**: A claimed WP with empty frontmatter resolves live from the snapshot; resume does
  not falsely flag stale.
- **SC-003 (AC-3)**: `move-task --to for_review` succeeds on log-recorded subtask completion with
  unchecked `tasks.md` — the merged red test is green; genuinely-incomplete WPs are still refused.
- **SC-004 (AC-4)**: Activity Log / History / review render from events with no content loss.
- **SC-005 (AC-5)**: The dossier content hash of the WP files is stable across the full lifecycle.
- **SC-006 (AC-6)**: Migration is idempotent on the live corpus; snapshot == pre-migration by
  count+value; re-runs seed nothing.

## Out of scope

- The final static-model authority election (enrich `WPMetadata` vs elect `WorkPackageEntry`) —
  deferred to a follow-up, gated on this landing (B4), coordinated with #1619.
- The 3.3.x YAML-authoritative / markdown-derived WP-prompt flip (requires #2400-owner re-ratification).
- The semantic-only content-hash slice (#2686) — shrinks to a small follow-up once this lands.
