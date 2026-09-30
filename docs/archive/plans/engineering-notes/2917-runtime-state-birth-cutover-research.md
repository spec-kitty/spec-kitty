---
title: "#2917 Runtime-State Birth-Cutover — Pre-Spec Research"
description: "Grounded findings from a 4-lens research squad on the #2917 runtime-state cutover drift: the problem, its true (inert) impact, and the solution fork the spec must choose."
doc_status: deprecated
updated: '2026-07-25'
---

# #2917 Runtime-State Birth-Cutover — Pre-Spec Research

> **Retired (deprecated).** Design shipped/superseded via merged mission `runtime-state-birth-cutover-all-paths-01KYH654` (#2917; `kitty-specs/runtime-state-birth-cutover-all-paths-01KYH654/`). Preserved as a historical record.

**Status: pre-spec. This grounds the problem and the solution space so the operator can choose the mission's shape before speccing.** Not a spec.

A 4-lens opus squad (architecture, scope/contract, failure-modes/verification, precedent/overlap) investigated on branch `research/2917-runtime-state-birth-cutover`.

---

## TL;DR — the decision you actually have to make

The `test_dogfood_corpus_backfilled` red is **not a bug** — it is a **decision about an invariant**. The corpus drifts un-flipped after every merge wave because the runtime-state cutover (`meta.json status_phase="1"` + deterministic seed events) is written **only** by a one-time migration; `create`/`finalize`/`merge` never stamp it. But the drift is **inert** — `status_phase`'s only live reader is a legacy `lane` mirror that is itself a no-op for new missions. So the mission is one of three shapes, in ascending scope:

- **(A) Relax the acceptance lock** — accept `status_phase` as a migration-only artifact; stop asserting a corpus-wide postcondition no live writer maintains. *Hours.*
- **(B) Merge-terminus seam** — stamp `cutover_mission` at `spec-kitty merge`. Unblocks + prevents recurrence *while the writer keeps dual-writing*. *Medium.*
- **(C) Close the authoring drift (the true root)** — event-source the claim/subtask writes (continue #2684) so nothing accrues to reconcile, *then* stamp at birth. *Large.*

**Two hard constraints regardless of A/B/C:** (1) a birth-time write touches the write-placement seam that **coord-trust #2841 owns → #2917 must consume its placement port and sequence after it**; (2) the 12 reds should be **front-loaded** (`migrate backfill-runtime-state` + commit) to unblock 3.2.6 CI immediately — necessary but not sufficient.

---

## The problem (converged, high confidence)

A mission is "cut over" iff `meta.json status_phase="1"` **and** the deterministic seed rows (`InnerStateChanged` quartet + seed `planned→claimed`) exist in `status.events.jsonl`. The **sole writer** is `migration/runtime_state_cutover.py::_flip_phase`/`cutover_mission` (`:107`), reached only on a fail-closed `verify_backfill().ok`, and invoked only from two one-time migrations (`migrate backfill-runtime-state`, `m_zz_runtime_state_backfill`). `create`/`finalize`/`merge` never stamp it (spec #2816 FR-003, by design). The one-time batch (`ecb6b452c`/`5aff7d0e8`, 2026-07-20/22) flipped 298/311; the 12 reds all merged **after** → never backfilled. Corpus split is exact: 298 flipped, 13 `null` = 12 + the excluded self-mission.

## Impact grounding — the drift is REAL but INERT (scope lens)

- `status_phase` has **exactly one live reader** in `src/`: `emit.py:375 _read_status_phase` → `_legacy_lane_mirror_enabled` (`:401`) → `_mirror_phase1_frontmatter_lane` (`:434`), which **"never creates a `lane` field; it only updates an already-present one."** Frontmatter `lane` is retired/migration-only, so for a new mission the mirror is a **no-op regardless of `status_phase`**.
- Runtime-slot snapshot authority is **unconditional** — #2816 deleted its `status_phase` predicate (`emit.py:397`). The reducer reads events regardless of the flip.
- **Net consumer consequence of an un-flipped new mission: effectively zero.** The 12 reds are our dogfood corpus asserting an invariant no live writer maintains.
- **Data-loss/strip risk: ruled out** on the birth path — `strip_mutable_fields` has one caller (the one-shot schema-v3 migration `runner.py:526`), never `create`/`finalize`/`merge`/`cutover`. (A narrow *cold-upgrade* pre-3.0→3.2.6 strip-before-backfill ordering caveat exists; pre-existing and orthogonal — the spec should note it, not own it.)
- **The birth-time seam was never designed** (#2816 scoped cutover as a one-time upgrade sweep; the drift is emergent). **#2917 is the first surfacing; no prior follow-up issue exists.**

## Why "just stamp at birth" is provably wrong (failure-modes lens)

`implement`/claim still **dual-writes** `shell_pid`/`agent` to WP frontmatter and subtask completion to `tasks.md` checkboxes (the #2684 authoring path is not fully retired). Therefore:

- **A bare stamp at create/finalize is INCORRECT.** Pre-claim the frontmatter is empty → `verify_backfill` returns a **vacuous** `ok=True, wp_count=0` → flip. Then implement authors runtime into frontmatter/tasks.md with **no seeds written** → the mission becomes *exactly the 12's shape* (flipped-but-unseeded) → the guard's `verify` assertion reds. **The 12 are living proof a birth-stamp doesn't stay valid.** (Verified: real cutover on an isolated copy of `common-docs-query-01KY541A` → `seeded=3, verify.ok=True, phase→1`; re-run `seeded=0`, byte-stable.)
- **Only a terminus (merge) stamp yields a passing verify** *while dual-writing continues* — that is the one moment runtime is complete + stable. Seed+live-claim coexist at the same `at` timestamp; the reducer folds idempotently (latest-wins); no double-count.
- **UNLESS** the fix also **retires frontmatter/tasks.md runtime authoring** (Option C) — then nothing accrues, and a birth stamp is trivially correct.

## Solution seam architecture (architecture lens)

- **Ride an existing land-time hook, not a bespoke one:** `_bake_mission_number_into_mission_branch` (`merge/ordering.py:485`, from `_phase_bake_and_pre_target_done` at `executor.py:425`) is a structural twin — it already stamps a `meta.json` bookkeeping fact on the mission branch at land via the same tolerant `write_meta(..., validate=False)` API, idempotent + resume-guarded + worktree-path-guarded. Add the cutover call adjacent to it (fire only after the target commit is durable).
- **Reuse `cutover_mission` (the sole writer)** — 3rd call site; zero duplicated logic; preserves the sole-writer invariant.
- **Coord/flat placement is the open architectural gap:** `cutover_mission` canonicalizes a *single* `feature_dir` for **both** meta and events, but for a coord mission `status_phase`→`meta.json` is **PRIMARY** while seed events→`status.events.jsonl` are **COORD**. Running the cutover as the **post-projection step against the target checkout** (where the executor has already reconciled coord→target) keeps the single-dir model correct — *or* a coord-aware two-target overload is needed. **This is exactly the write-placement concern #2841 owns.**
- **Coexistence:** the birth seam owns *forward* flow; the one-time migration stays for *backward* flow (pre-#2816 corpora + consumer-repo `spec-kitty upgrade`). Both call the same spine.

## Cross-mission constraints (precedent/overlap lens)

- **HARD DEPENDENCY on coord-trust #2841 (PR #2874).** #2917 writes two partitions at merge; #2841 makes "route every mission-artifact write through one placement port keyed on `kind_for_mission_file`" mandatory and explicitly targets the status write-authority fork. If #2917 hand-writes `status_phase`/events at merge first, it **re-creates the exact split-brain #2841 exists to make unrepresentable**, and both edit the same `merge/executor.py` region (textual collision). **#2917 must consume #2841's placement port and land after it.**
- **#2917 is a continuation of the #1619/#2816 runtime-state epic**, not standalone — reuse that family's writer + contract; file under the epic.
- **Guard-test extension is mandatory (green-wash risk HIGH).** The current guard only exercises missions carrying *legacy frontmatter* runtime. A writer-retirement fix (Option C) makes new missions drop out of the eligible set → the guard silently stops testing the born-flipped path. The guard must be re-keyed to an **event-log-keyed birth invariant** (every mission whose *event log* carries runtime must be `status_phase≥1` + non-empty snapshot).

## Edge cases the spec must rule

| Case | Squad read |
|---|---|
| No evictable runtime (never-claimed) | Not eligible — don't flip |
| Claim fields but no honest timestamp | Don't flip (fail-closed, no fabricated time) |
| Coord vs flat | Flip both — topology-agnostic predicate |
| **Already-merged / archived** missions carrying runtime (all 12 reds) | **UNDECIDED — the crux.** Inert, yet the guard demands it. Spec must settle. |
| `_SELF_MISSION` (the cutover mission itself) | Correct exclusion — keep |

---

## Squad recommendation (for your decision)

1. **Unblock 3.2.6 now, independently:** front-load `migrate backfill-runtime-state` over the 12 + commit. Idempotent, compatible with any seam, does not foreclose the structural choice.
2. **Pick the mission shape (A / B / C)** — this is the operator call the research exists to inform:
   - If `status_phase` is accepted as migration-only and its inert reality is fine → **(A)** re-scope the acceptance lock (cheapest, but scrutinize: is the guard a *stale* lock or a *valid* parity invariant? Keep the `verify_backfill` half; relax the corpus-wide `status_phase` postcondition).
   - If we want the corpus to stop drifting without the larger authoring rework → **(B)** merge-terminus seam, **routed through #2841's placement port**, guard re-keyed to the event-log invariant.
   - If we want the true root (and it aligns with the #2684/#1619 direction of event-sourcing all runtime writes) → **(C)** retire frontmatter/tasks.md authoring + birth stamp — largest, highest durable value, deepest overlap with #2841 + the epic.
3. **Sequence under coord-trust #2841 regardless** — B and C both touch its placement seam.

**My read:** front-load to unblock immediately; take **(C)** as the mission's north star *sequenced after #2841*, with **(B)** as the fallback if C's scope is too large for this cycle. **(A)** is legitimate only if the team formally accepts `status_phase` as migration-only — flag it explicitly because it would save the most work and the impact grounding supports it.

## Operator decision (2026-07-25): **Option C — close the authoring drift (root)**

Chosen shape: retire frontmatter/`tasks.md` runtime authoring (continue #2684) so nothing accrues to reconcile, then stamp `status_phase` at birth; re-key the guard to an event-log birth invariant. **Sequenced after coord-trust #2841** (consumes its placement port). The 12-mission front-load (`migrate backfill-runtime-state` + commit) is folded in as **WP1** to clear the 3.2.6 CI red immediately. Spec to follow.

## Key files

`src/specify_cli/migration/runtime_state_cutover.py:107-180` · `backfill_runtime_state.py:734-953` · `src/specify_cli/status/emit.py:375-439` · `src/specify_cli/merge/executor.py:378-425` · `merge/ordering.py:485` · `merge/bookkeeping_projection.py` · `cli/commands/agent/mission_create.py:321` · `upgrade/migrations/m_zz_runtime_state_backfill.py` · `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py:120-203` · `tests/regression/test_issue_2684_subtask_completion_event_sourced.py` · `kitty-specs/runtime-state-corpus-cutover-01KXZ0AX/spec.md` · ADR `docs/adr/3.x/2026-07-19-1-wp-runtime-state-event-log-eviction-via-innerstatechanged.md`.
