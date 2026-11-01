---
title: 'Scoping brief: evict runtime-mutable WP state into the event log (#2684 cluster)'
description: 'Scoping and code-grounding brief for the #2684 task-move / WP-metadata-split / task-status cluster: authority inventory, migration contract, and a proposed decomposition.'
doc_status: deprecated
updated: '2026-08-12T00:00:00Z'
related:
- docs/adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md
kind: Planning
---
> **RETIRED (shipped)** — the #2684 runtime-state eviction this brief scoped was ratified in ADR
> [`2026-07-19-1`](../../adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md)
> and shipped by mission `wp-runtime-state-eviction-01KXWN13` (impl `dfe6b2ead`). Evidence: #2684
> (+ #2093/#2816). Retained for historical reference; do not consult for current behavior.

# Scoping brief — evict runtime-mutable WP state into the event log (#2684 cluster)

> **Status: scoping input for `/spec-kitty.specify`.** This brief is the research spine for a
> single, exhaustive 3.2.6 mission. It is grounded by a four-lane research squad (2026-07-19)
> against the current `main` (HEAD `874673ea3`, which already carries the merged #2684 red-first
> test) plus the prior-art design corpus in the sibling `wp-op-schema-design` working tree. It is
> **not** a plan — it collects the decided facts and the still-open decisions so the spec author
> starts with zero undecided code facts. Every line number below was grep-verified on `main`;
> where the tracker's numbers had drifted, the correction is called out.

## 0. Decisions resolved (HiC, 2026-07-19)

The seven open decisions from §14 are now **closed**. These are binding inputs for
`/spec-kitty.specify`; §14 is retained as the rationale record.

1. **Off-axis events → Option A, realized as ONE generic `InnerStateChanged` event.** Non-transition
   mutations enter the log via a single annotation event carrying a **typed partial delta**
   (`WPInnerStateDelta` with optional typed fields — *not* a free `dict[str, Any]`, to avoid
   re-introducing the split-brain). It bypasses `validate_transition` (no `from_lane`/`to_lane`) and
   is folded by the reducer with a per-field merge rule and **no `force_count` increment**. This is
   the reusable realization of the Option A annotation class — one event kind, not per-kind variants.
2. **Subtask granularity → subsumed by the delta.** No separate per-subtask-vs-snapshot event: the
   `InnerStateChanged` delta carries `subtasks: Mapping[str, Status]`, which expresses a single mark
   *and* a batch mark naturally, and (per the HiC framing) the same generic event also carries the
   PID refresh — a reusable state-delta pattern.
3. **Activity notes → fold into `InnerStateChanged`.** A `note` delta field with **append**
   semantics; the reducer keeps a `notes` list on the snapshot; **AC-4** renders the Activity Log
   from it. One off-axis event class for pid + subtasks + notes.
4. **`tracker_refs` → EVICT (runtime, event-sourced).** `map-requirements` and `move-task` emit an
   `InnerStateChanged` delta (`tracker_refs` with **union/append** merge); FR-011 runtime append is
   preserved. Consistent with the eviction thesis.
5. **Review-cycle → evict ALL in this mission.** Delete the dead verdict-field read fallbacks
   (`workflow_cores.py:340-341`, `done_bookkeeping.py:104-105`) **and** evict the actively-written
   `review_artifact_override_*` into `InnerStateChanged`. **Governing principle:** #2684 is the
   *authoritative owner* of the WP-metadata surface — deferred PR **#2641** yields to the mission
   (its file-collision risk is moot; it was deferred precisely for treading on this active-design
   turf). AC-1 is fully complete within this mission. **Update 2026-07-19:** the same principle
   resolves the #2160 dependency — #2160's writer work is `pr:deferred` and yields to this mission, so
   **this mission owns the `implement.py:1730` shell_pid-writer restructuring** outright (the former
   "hard co-sequence" in §10/§13 is retired — no external `blocks/blocked_by` gate; see spec FR-014).
6. **Static-model election → DEFER to a follow-up.** Land + verify the eviction first (blocker B4:
   `WPMetadata` can't become a clean static-only projection until its runtime half is stripped);
   the election coordinates with #1619 and opens against a clean surface next.
7. **`progress` field → retire explicitly.** Remove from `MUTABLE_FIELDS`/schema; document the
   removal in the migration notes (backfill no-op — no writer ever existed).

**Net effect on the decomposition (§10):** WP-A collapses to *one* `InnerStateChanged` event class +
*one* typed `WPInnerStateDelta` + *one* reducer fold covering `shell_pid`(+baseline), `subtasks`
(map/replace), `notes` (append), and `tracker_refs` (union) — simpler than per-kind annotations. WP-F
(`tracker_refs`) is now decided (evict) and folds into WP-B/WP-D rather than standing alone.

## 1. The mission in one paragraph

`tasks/WP##.md` (and the `tasks.md` subtask surface) is **two authorities glued into one YAML
block**: static design-intent authored once, and runtime-mutable state written on every lifecycle
event. The runtime writes churn the dossier content hash, split subtask-completion truth between
markdown and the event log, and force operators to hand-tick checkboxes before a WP can move to
review. **#2684 (P0)** evicts *all* runtime-mutable state into the canonical append-only event log,
leaving WP files holding only static intent. It is the execution vehicle for the **#2093** authority
ruling and must land in **3.2.6** (milestone **#4 "3.2.x"**) — the reason a red-first repro
(#2806, merged) already reddens `main`.

## 2. Cluster ticket map

**Epic spine (native sub-issue edges, GraphQL-verified):**
`#1799` (Charter & Doctrine) → `#2400` (sub-epic: Metadata & profile authority) → **`#2093`**
(WP-metadata authority split — *the ruling*, P1) → **`#2684`** (the mission, P0) → `#2686`
(projection-hash child, blocked-by #2684). Parallel: `#1619` (unify mission execution context) →
`#2160` (coord task/status artifact authority — **co-sequence anchor**); `#2017` (workflow guards
epic); `#1914` (governed/gate ops must be no-op-stable).

**In the mission:**
- **#2684** — the eviction (AC-1..6): `shell_pid`(+baseline), `history[]` (dead — delete),
  subtask-checkbox state, review-cycle fields, `## Activity Log`, `agent`/`assignee`; the 4
  `shell_pid` writers + move-task; delete legacy fallbacks; repoint model readers.
- **#2686** — hash the WP static projection, not raw bytes (tail of this mission or immediate
  follow-up; delivered in substance by AC-5).

**Dependencies (land with/before, or share touched files):**
- **#2160** — *hard co-sequence.* Restructures `implement.py`/`workflow.py`, including the
  `implement.py:1730` `shell_pid` claim writer WP-D evicts. Set an explicit `blocks/blocked_by` edge
  on the writer-cutover WP.
- **#2647** (P1) — move-task cwd read-path; reconcile in the same move-task rewrite (write-side fix
  `5107c700f` is on `main` — see §7).

**Defer (adjacent `tasks_move_task.py` lane owners, but gate/placement concerns, not metadata
eviction):** #2549, #2626, #2300, #2573 (P0 pre-review-gate-hang), #1734, #2583, #2493, #2555, and
the pre-review-gate sub-cluster (#2794/#2801/#2534/#2741/#2598/#2705/#2802/#2602). Coordinate lane
ownership on `tasks_move_task.py`; do not fold in.

**Closed precedents — do NOT re-do (cite the fix):** #1862 & #1764 (analysis-freshness normalization
`analysis_report.py::_normalize_tasks_md`), #2513 & #2576 (rollback uncheck), #2510 (coord husk
fail-open), #2567/#2324/#2346/#2574 (subtask parser consolidation), **#2580** (the 4th `shell_pid`
writer routed through `write_shell_pid_claim` — confirms the "4 writers" inventory),
\#2575/#1231/#2369/#2512 (shell_pid-liveness precedent chain this generalizes), #2154/#2155 (via PR
\#2181, #2160 core), #2648/#2649/#2650 (#2533 write-side + degod/SSOT-consolidation of the exact
files #2684 edits), #2740, #2504.

**Out of scope but related:** #2736 (P0 catfooding mission that *re-confirmed* #2684; its fix is sync
bisection #2735, not eviction), #2644 (static task-graph authority — different field-class), #1341
(same append-only+derived-YAML pattern in the glossary domain — reference), #2533/#2602 (coord
placement).

## 3. In-flight PR watchlist (conflict zones)

**No open PR pre-empts the eviction itself** — nothing in flight touches `tasks_mark_status.py`,
`tasks_transition_core.py`, `core/subtask_rows.py`, `migration/strip_frontmatter.py`,
`frontmatter.py`, or the status reducer/snapshot. Collision risk is concentrated in three PRs:

| PR | State | Cluster files | Conflict |
| --- | --- | --- | --- |
| **#2641** | CHANGES_REQUESTED | `tasks_move_task.py`, `tasks_materialization.py`, `review/{cycle,artifacts,arbiter}.py` | **HIGH** — the exact move-task/materialization/review surfaces WP-A/D rewrite |
| **#2766** | open, 3 CI reds | `workflow.py`, `workflow_executor.py`, `core/worktree_topology.py` | **Med-High** — `workflow_executor.py` hosts two `shell_pid` writers (:695, :1370) |
| **#2800** | MERGEABLE (nearest landing) | `merge/done_bookkeeping.py` + move-task/mark-status/rollback tests | **Med** — WP-E must *delete* `done_bookkeeping.py:104-105`; expect test churn collision |

Also watch #2612 (review auto-commit path), #2492/#2611 (grazing move-task test files). **Rebase the
mission on `main` after #2641/#2766/#2800 land, or coordinate lane ownership up front.**

## 4. The authority ruling (#2093)

Split by **field-class**, do not unify into one store:

- **STATIC design-intent — frontmatter STAYS canonical**, never mirrored into events/`meta.json`:
  `work_package_id`, `title`, `dependencies`, `requirement_refs`, `plan_concern_refs`,
  `owned_files`, `create_intent`, `authoritative_surface`, `scope`, `task_type`, `cross_cutting`,
  `priority`, `phase`, the planning trio, `agent_profile` (authored *assignment* only), prompt body.
- **DYNAMIC runtime state — the event log / invocation record is the SOLE authority**; frontmatter
  copies are *retired, not left as fallback readers*: `lane` (already retired — the precedent),
  `shell_pid`(+baseline), `agent`/`assignee`, `history[]`, subtask checkbox state, review-cycle
  fields, `activity_log`, `base_branch`/`base_commit`/`created_at`.
- **AMBIGUOUS — `agent_profile`:** authored *assignment* stays STATIC; the *resolved binding*
  (which profile actually ran, id + hash) records DYNAMIC on the status event / Op record
  (precondition for #2399's enforcement seam).

**Target invariant** (enforced by a refactor-stable architectural test — the generalization of the
shipped phase-2 lane-authority guard): no consumer ever *reads a dynamic frontmatter field as
authority*; static fields are never mirrored into events; `agent_profile` is split intent-vs-binding.
\#2684 accepts this verbatim and deliberately stops at "file holds only static intent," **not** "file
is derived" (that is the 3.3.x YAML-flip — §9).

## 5. Field-by-field authority inventory (grep-verified on `main`)

**T** = write fires on a lane transition (fits a `StatusEvent`); **OFF** = off-axis (no lane change).

| Field | Current authority | Writers (verified file:line) | Key readers | T/OFF | Eviction note |
| --- | --- | --- | --- | --- | --- |
| **shell_pid** (+`shell_pid_created_at`) | frontmatter `tasks/WP##.md`; co-write helper `frontmatter.py:357` `write_shell_pid_claim` | `implement.py:1730` ✓; `workflow_executor.py:695` (was :669); `workflow_executor.py:1370` (was :1337); `tasks_move_task.py:1770` (was :1638). **Delete site:** `tasks_move_task.py:1747` | claim-liveness `stale_detection.py:402-403` → `:221/:244`; `WorkPackage.shell_pid` `support.py:295`; `WPMetadata` `wp_metadata.py:251,361-363`; `summary_core.py:69` | **MIXED** (claim=T; resume refresh=OFF, the pivotal case) | in `MUTABLE_FIELDS`; carry `(shell_pid,baseline)` in `policy_metadata` on the claim event |
| **history[]** | frontmatter list `WPMetadata.history` `wp_metadata.py:259` | `frontmatter.py:176`/`:347` — **ZERO live callers**; `wp_metadata.py:570` docstring-only | build merge `wp_metadata.py:585` (never fires); `audit/shape_registry.py:113` | N/A dead | **TRULY DEAD + MIS-FILED in `STATIC_FIELDS` (`strip:56`).** Delete outright; no migration |
| **subtask checkbox** (`- [x] T###`) | `tasks.md` WP-section rows (`core/subtask_rows.py`) | `tasks_mark_status.py:266` `_resolve_checkbox`; uncheck `subtask_rows.py:192/:218` ← `tasks_move_task.py:1806` | **done-inference** `emit.py:299→302` `done==total`; accept gate `gates_core.py:112`; dashboard `scanner.py:961` | **OFF (the P0)** | hardest: per-subtask stream, no lane event. Needs subtask-completion projection in the reduced snapshot; re-point `emit.py:302` + `_guard_subtasks`. **This is the merged red test.** |
| **review_status / reviewed_by / reviewer\* / review_feedback** | canonical = event log; **frontmatter = legacy fallback only** | **NO live runtime writers** | **DELETE fallbacks:** `workflow_cores.py:340-341` (provenance `"frontmatter"`); `done_bookkeeping.py:104-105` (`DoneEvidence` `frontmatter-migration:{wp}`) | T (verdict) | already in `MUTABLE_FIELDS`; **delete the two read fallbacks**, don't just stop writing |
| **review_artifact_override_\*** (`_at/_actor/_wp_id/_reason`) | frontmatter — **ACTIVELY written** | `tasks_materialization.py:58-61` and `:125-128` | `review/artifacts.py:134-136,181-182` | OFF | **NOT in `MUTABLE_FIELDS`** — live writer the issue's set omits; needs an event/`policy_metadata` home |
| **## Activity Log** (body) | `WP##.md` body; append `task_utils/support.py:221` | 6 writers: `workflow_executor.py:705`,`:1377`; `tasks.py:914`; `tasks_move_task.py:1777`; **external `orchestrator_api/commands.py:1563`**; `task_metadata_validation.py:135` (migration-only) | `tasks.py:1149-1150` validation; human narrative | MIXED | evict to event log; the **cross-package** writer `commands.py:1563` must migrate too |
| **agent** | frontmatter | `workflow_executor.py:694`,`:1369`; `tasks_move_task.py:1763`. Delete site `:1746` | `WorkPackage.agent` `support.py:291`; `wp_metadata.py:419-458` | claim=T, reassign=OFF | in `MUTABLE_FIELDS`; co-written with shell_pid at every claim → same vehicle |
| **assignee** | frontmatter | `tasks_move_task.py:1761` (only writer) | `support.py:287`; `wp_metadata.py:246` | OFF | in `MUTABLE_FIELDS` |
| **tracker_refs** | frontmatter (`WP_FIELD_ORDER`, "per DIR-012") **but runtime-written** | `tasks_map_requirements.py:428`; `tasks_move_task.py:1721→_mt_persist_tracker_refs:1787` | `wp_metadata.py:213,320-322` | OFF | **FR-011 tension: cannot be both static AND derived.** NOT in `MUTABLE_FIELDS`. Must re-decide (§8) |

**`MUTABLE_FIELDS` today (`migration/strip_frontmatter.py:23-34`)** — the canonical set to **extend, not
fork**: `{lane, review_status, reviewed_by, review_feedback, progress, shell_pid, assignee, agent}`.
In-scope additions: `shell_pid_created_at`, `history` (move out of `STATIC_FIELDS`), `tracker_refs`
(if evicted), `review_artifact_override_*`, `reviewer_shell_pid`. Note the Activity-Log **body** and
subtask **checkboxes** live in `tasks.md`/body, not frontmatter keys — `strip_mutable_fields`
(`:130-155`) only touches frontmatter, so they need a **parallel eviction path**. `progress` is in
`MUTABLE_FIELDS` with no live writer/reader → **explicitly retire it** (document the removal).

## 6. Mechanism map (task-status / gate / event-log / hash)

- **Two markdown subtask authorities, both to re-point:** (a) `_guard_subtasks`
  (`tasks_transition_core.py:384`) via `_check_unchecked_subtasks` (`tasks_shared.py:412`); (b)
  done-inference `_infer_subtasks_complete` (`emit.py:279→302`) feeding the FSM guard
  `wp_state.py:370`. Both count `tasks.md` rows (`core/subtask_rows.py:39,111,164`).
- **The reducer carries NO subtask state.** `reducer.py:48-65,118` folds only
  `{lane, actor, last_transition_at, last_event_id, force_count}`; `StatusSnapshot.work_packages`
  (`models.py:322`) has no subtask field. `mark-status` is **coreless** — it rewrites the checkbox
  (`tasks_mark_status.py:302`) and emits a free-text `HistoryAdded` note (`:326`, not a
  `StatusEvent`) that nothing folds back. **The eviction must add a reduced, gate-queryable
  subtask-completion projection** and re-point both (a) and (b) at it.
- **AC-5 content-hash churn root cause:** the dossier hashes **raw file bytes** of both `tasks.md`
  and `tasks/WP##.md` (`dossier/hasher.py:14`; `dossier/indexer.py:242`; parity
  `dossier/snapshot.py:25-53`; manifest `expected-artifacts.yaml:36`). Runtime writes into those
  files churn `content_hash_sha256` → parity churn → false drift. Eviction into `status.events.jsonl`
  (not a dossier artifact) stabilizes the hash.
- **FSM rejects self-edges (the constraint is real in code):** `StatusEvent` mandates
  `from_lane`/`to_lane` (`models.py:248-249`); `InProgressState.allowed_targets()` excludes
  `IN_PROGRESS` (`wp_state.py:351`); `check_transition` returns `Illegal transition: in_progress ->
  in_progress` (`:162,179`), and `force` additionally demands actor+reason and increments
  `force_count` (`reducer.py:64`). So off-axis mutations cannot be clean transition events.

## 7. The pivotal ADR decision (non-transition mutations)

Three evicted mutations are **off-axis** (no lane change): (a) `shell_pid` refresh on *resume* of an
already-`in_progress` WP, (b) mid-`in_progress` subtask marks, (c) activity-log notes.
`policy_metadata: dict|None` (`status/models.py:258`, threaded through `emit.py`) can already carry
`(shell_pid, baseline)` on the **claim** transition with **no wire-schema change**.

- **Option A — non-transition annotation event class (prior-art recommendation).** A new record in
  the same log distinguished by absent `from_lane`/`to_lane` + `annotation_kind`
  (`shell_refresh`|`subtask_marked`|`activity_note`), typed payload, truthful `at`. Deltas:
  `wp_state.py` sanctioned self-edge / `annotate()` primitive bypassing `check_transition`;
  `models.py` event discriminator round-tripped in `to_dict`/`from_dict`; **`reducer.py` precedence
  change** (fold annotation after transition, last-writer-wins per field, **no `force_count`
  increment**). Highest blast radius (touches FSM authority + wire model + reducer core) but the only
  option that makes the log a true SSOT for (a)+(b)+(c) — and it is what delivers the subtask
  projection §6 needs.
- **Option B — fold onto transitions + documented behavior change.** Carry `(shell_pid,baseline)` in
  `policy_metadata` of the next real transition only; near-zero FSM/reducer change. But resume emits
  no event → stale PID → claim-liveness degrades to the git-timestamp heuristic
  (`stale_detection.py:254,331`, path intact) → a resumed long-planning agent can be **falsely
  flagged stale** until its first commit. **Complete only for (a);** (b) and (c) still need a home.

**Gate re-sourcing (re-point `_guard_subtasks` and `_infer_subtasks_complete` at a reduced-snapshot
field) is required under BOTH options** — it is the part the merged red test's *control* protects
(the fix must re-source the gate, not delete it). **This decision gates the whole mission and must be
closed at spec time** (candidate standalone ADR — §10).

## 8. Migration contract

Strict order — **writer-first is prohibited**:
`backfill → verify → reader cutover → writer cutover → delete fallbacks + land hash guard`.

- **Why (the B3 clobber window):** readers keep the frontmatter fallback until backfill is
  *verified*; cutting writers first strips e.g. `shell_pid` while `stale_detection.py:402` still reads
  frontmatter → live claims read reclaimable, evidence clobbered on the next `implement`.
- **Seed-event determinism (AC-6):** the reducer dedups by `event_id`, which must match
  `ULID_PATTERN` (`reducer.py:139-149`, `models.py:70`) — **a content hash is NOT a valid ULID**. Use
  a **namespaced deterministic ULID from `mission_id + wp_id + field`** so backfill is idempotent;
  re-runs must not double-seed.
- **Subtask reconstruction contract (timestamp honesty):** checkboxes carry no `at` → clamp the
  reconstructed mark to the WP's `claimed` timestamp. **"No data loss" is stated against count+value
  parity of the reduced snapshot, NOT literal temporal fidelity** — say so in the spec. Verify (step
  2) confirms reduced snapshot == pre-migration state by count+value.

## 9. Acceptance criteria (AC-1..6) — which prove the mission

- **AC-1** No `implement`/`mark-status`/**`move-task`**/review action writes `tasks/WP##.md` (bytes +
  mtime unchanged across a full lifecycle). move-task is an explicit target (the god-write, §11.1).
- **AC-2** Claim-liveness resolves from the reduced snapshot; a claimed WP with empty frontmatter is
  detected live.
- **AC-3** Done-inference resolves from `subtask_marked` annotations; lane gating identical. **← the
  already-merged red test `test_issue_2684_subtask_completion_event_sourced.py` pins this** (RED
  today because `emit.py`/`_guard_subtasks` read `tasks.md`; GREEN when they read the snapshot).
- **AC-4** Activity Log / History / review sections render from events with no content loss (the
  annotation payloads add the prose home M7 needs).
- **AC-5** A full lifecycle produces a **stable content hash** (the churn fix; wired once, no mixed
  parity pool). **Headline proof of the mission.**
- **AC-6** Migration backfills the corpus idempotently (deterministic ULID seeds); honest
  reconstruction contract; no *unrecoverable* loss.

The "prove-it" quartet: **AC-1 + AC-2 + AC-3 + AC-5.**

## 10. Proposed decomposition (a PROPOSAL for the spec author)

Critical path `A → {B, C} → D → E`, with **F** parallelizable. WP-A's payload-shape choices (§ open
decisions) must be closed at spec time, not deferred into implementation.

- **WP-A — Annotation event class + reducer fold (foundation).** New off-axis record shape;
  `validate_transition` bypass; reducer precedence + `force_count` neutrality; typed snapshot slots
  (`shell_pid`, `shell_pid_created_at`, `baseline`, `subtask_state`, `notes`). FSM untouched. Closes
  subtask-granularity + activity-log-home decisions. Independent of #2160.
- **WP-B — Reader cutover.** Repoint `WorkPackage.{shell_pid,agent,assignee}` (`support.py:287-296`),
  `WPMetadata` coercion (`wp_metadata.py:361,580`), `stale_detection.py:402-403`, `emit.py:302`
  done-inference, and `_guard_subtasks`/`tasks_shared.py:412` to the reduced snapshot; frontmatter
  fallback behind a flag until backfill verified. **Turns the merged AC-3 red test green.** Needs A.
- **WP-C — Migration (backfill + verify).** Extend `MUTABLE_FIELDS`; emit seed transition + annotation
  events with deterministic namespaced ULIDs; subtask clamp; read-back count+value verify. Needs A;
  gates D.
- **WP-D — Writer cutover.** Cut all writers off the file: the 4 `shell_pid` writers
  (`implement.py:1730`, `workflow_executor.py:695`&`:1370`, `tasks_move_task.py:1770`),
  `agent`/`assignee` writers, the 6 `activity_log` writers (incl. external `commands.py:1563`),
  subtask materialization + the `tasks.md` uncheck (`tasks_move_task.py:1806`), `tracker_refs`
  (`:1787`) per §8 decision. **Must co-sequence with #2160.** Needs C's verify gate. **Delivers AC-1.**
- **WP-E — Delete legacy fallbacks + land the AC-5 hash guard.** Remove `workflow_cores.py:340-341`
  and `done_bookkeeping.py:104-105`; wire the stable-hash guard once (no mixed pool); add the
  refactor-stable "no consumer reads a dynamic frontmatter field as authority" architectural test
  (#2093 invariant). Needs B + D.
- **WP-F — Resolve `tracker_refs` (author-immutable OR evict).** Ship exactly one (§ open decision).
  Parallelizable once decided.

## 11. Highest-risk couplings (where naive eviction breaks a gate)

1. **move-task god-write** — `_mt_persist_wp_file` rewrites `assignee`(:1761)+`agent`(:1763)+
   `shell_pid`(:1770)+Activity-Log(:1777) atomically, and on planned rollback also clears
   `agent`/`shell_pid`(:1746-1747), unchecks subtasks(:1806), persists `tracker_refs`(:1787).
   Piecemeal eviction breaks the co-write atomicity the others rely on.
2. **done-inference vs checkboxes** — evict checkbox state but leave `emit.py:302` counting `tasks.md`
   → the done gate silently mis-fires (the #2684 P0).
3. **claim-liveness** — evict `shell_pid` without redirecting `stale_detection.py:402-403` → every
   claim mis-reads alive/dead → allocator/resume corruption.
4. **merge DoneEvidence fallback** — strip `reviewed_by`/`review_status` while leaving
   `done_bookkeeping.py:104-105` → merge loses done-evidence. Delete the fallback **and** guarantee
   canonical evidence together.
5. **external orchestrator writer** — `orchestrator_api/commands.py:1563` writes the Activity Log from
   outside the host CLI; a host-only rewire leaves it writing the retired surface.
6. **review-feedback provenance fallback** — `workflow_cores.py:340-341` returns provenance
   `"frontmatter"`; rejection-cycle gating for legacy WPs depends on it until deletion + backfill land
   together.

## 12. #2647 interaction (same cluster)

The write-side fix `5107c700f` is on `main`: a *modern* coordination-less mission
(`single_branch`/`lanes`/`flattened`) writes to `worktree_root = repo_root` on a caller-supplied,
CWD-invariant `destination_ref` (`coordination/transaction.py:783-799`), no longer re-derived from
`Path.cwd()` (the #2647 taint at `:300-302`). Eviction **increases append-only write frequency on the
target branch**, riding this exact path. **Every new emit site (Option A annotation, or Option B
`policy_metadata` fold) MUST resolve `destination_ref` from stored topology/target branch, never
`Path.cwd()`,** or it silently reopens #2647. There is no runtime provenance check — the guard is the
`test_transaction_legacy_topology_routing` regression test.

## 13. Sequencing with other tickets

- **#2160 — hard co-sequence** (`blocks/blocked_by` on WP-D): it restructures the same
  `implement.py:1730` `shell_pid` writer; the eviction lands with/behind it, never racing.
- **#1619 — neutral** for the eviction (moves state to the already-shipped log, no new aggregate);
  only the *final static-model election* (out of scope, §B4) coordinates with it.
- **Op-debrief slice — independent** (shares no code); do not couple.
- **#2686 semantic-only hash — follow-up** that shrinks once nothing writes runtime state (co-move
  `sync/body_upload.py` TOCTOU; no mixed spec/raw parity pool across the un-migrated corpus).

## 14. Open decisions the spec MUST close — RESOLVED 2026-07-19 (see §0)

> All seven are now closed; see **§0** for the binding calls. Retained below as the rationale record.

1. **`tracker_refs` — author-immutable vs evict.** Runtime-written today (`tasks_move_task.py:1721`,
   `tasks_map_requirements.py:428`, FR-011) yet listed static in the schema proposal. Cannot be both.
   **Hardest classification call.** → WP-F.
2. **Subtask-event granularity** — per-subtask `subtask_marked` vs single `subtasks_snapshot`. → WP-A.
3. **`activity_log` home** — first-class annotation event vs Tier-2 evidence sidecar. → WP-A.
4. **Review-cycle eviction timing** — evict here vs fold into #2160's review-state work. Interacts
   with the #2160 co-sequence.
5. **Static-model election is deferred** — enrich `WPMetadata` vs elect `WorkPackageEntry`. Real
   tension but **out of scope**; flag so the spec doesn't pull it in (this mission unblocks it via B4).
6. **`progress` field** — retire explicitly (no writer/reader), don't silently drop.
7. **The pivotal ADR (Option A vs B)** — §7. Everything rests on it.

## 15. Candidate NEW tickets — REQUIRES HiC APPROVAL, not filed

Per the governance boundary (no new `spec-kitty` tickets without HiC approval), drafted for review only:

1. **Standalone ADR/decision ticket for the self-edge / non-transition annotation-event design**
   (§7) — currently buried in #2684's body.
2. **`tracker_refs` authority re-decision** (§14.1) — small decision ticket; must resolve before
   writer cutover.
3. **Migration/backfill contract as its own sub-issue** under #2684 (§8) — deterministic ULID seeding
   - honest reconstruction contract is substantial.
4. **3.3.x YAML-authoritative / markdown-derived WP-prompt flip** epic — explicitly out of #2684
   scope; requires re-ratification by the #2400 owner; gated on this mission.

## 16. Sources

- Research squad (2026-07-19): tracker archaeology + PRs; field-authority inventory; status/gate/
  event-log mechanism map; prior-art synthesis. Code grounded on `spec-kitty` `main` `874673ea3`.
- Prior art (sibling `wp-op-schema-design` tree): `docs/adr/3.x/2026-07-16-1-wp-runtime-state-authority-event-log-eviction.md`;
  `docs/architecture/wp-runtime-state-eviction.md`; `docs/plans/investigations/wp-runtime-state-eviction-scope.md`;
  `docs/plans/investigations/wp-op-schema-proposal.md` (Part 4: B3/B4, M2/M4/M7).
- Tracker: #2684, #2093, #2400, #2160, #2686 and the cluster in §2. Milestone #4 "3.2.x".
- Merged anchor: `tests/regression/test_issue_2684_subtask_completion_event_sourced.py` (PR #2806).
