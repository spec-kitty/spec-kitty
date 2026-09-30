---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T11:15:07Z'
reviewer_agent: claude
wp_id: WP11
---

# WP11 review, cycle 2: CHANGES REQUESTED (2 findings; everything else verified fixed)

- Reviewer: reviewer-renata (claude).
- Head: 8c8e75bae / merge 65648b14a (lane-j).
- Cycle-1 base for the re-check: 2e11096dd.

## Cycle-1 findings, re-verified against the code

| # | Finding | Status | How it was verified |
|---|---|---|---|
| 1 | `ctx.owned` never set | FIXED | Mutant "drop `owned=owned` from `DecideNextContext`" is killed by the walk test and the composition-seams test. |
| 2 | Composition path persisted before resolving | FIXED | `_dn_plan_composition_advance` resolves outside any `except` before `advance_run_state_after_composition` writes. `test_resolution_failure_leaves_run_state_untouched_and_propagates` pins a byte-identical run state. |
| 3 | Preview mirror | FIXED | The mirror is deleted. See the engine-split note below. |
| 4 | Fidelity mutants | FIXED | Every mutant I ran is killed (details below). |
| 5 | Runtime-level walk | FIXED | `TestFr008RuntimeWalk` drives `decide_next` from `tasks` and asserts implement / WP01 / workspace P. I re-ran the walk: green. |
| 6 | DecisionGitLog anchor | FIXED | P for coord-less; R/.worktrees for coord-routing. Both are tested. |
| 7 | O8 vacuity | FIXED | Controls plus a per-seam injection each. |
| 8 | FR-007 vacuity | FIXED | |
| 9 | Legacy lifecycle arms | FIXED | Each arm mints once via `_transitional_owned_from_legacy`. |
| 10 | Bridging marker | FIXED | It is on the `build_prompt(` call line. |

The mutants behind row 4:
- the preview plans with `"failed"`;
- reuse without the `step_id` equality check;
- the preview skips the result prelude (planning on the raw snapshot);
- the 3 cycle-1 survivors are all killed on the real engine.

**Engine split: behaviour-preserving.**
- `plan_advance` + `_commit_advance` reproduce the old single pass: the same event order (auto-completed → significance → issued / decision-requested / run-completed), the same snapshot fields, and the LOW re-plan.
- The one declared change is that a planner failure no longer writes the auto-completed event first. That is an improvement.
- `test_plan_advance_includes_the_significance_low_replan` pins the re-plan.

**The composition path's significance-less planning pre-dates this cycle.**
- On bb67d7982 the composition adapter already ran `_mark_step_completed` + `plan_next` with no significance step, so WP11 did not introduce the divergence.
- It is not a preview/commit split either: the composition path commits the very plan it resolved.
- Non-blocking. Please file a follow-up issue so the composition advance plans through `engine.plan_advance`.

## Required fixes

### 1. [HIGH] The committed-authority short-circuit reads the repository root checkout R for an owned mission (FR-007 leak with no owning WP)

**Where:**
- `runtime_bridge.py`: `decide_next_via_runtime` and `query_current_state` → `_merged_mission_short_circuit(repo_root=R)`.
- That calls `committed_authority.mission_terminal_verdict(R, slug)`, which calls `_committed_surface(R)` and returns `R/kitty-specs/<slug>`.
- Passing P gives the same result, because the identity seam folds a worktree root to R.

**Reproduction:**
- Fixture: `owned_checkouts` + `stale_root_copy()`.
- R's copy is given `mission_number: 7`; P's mission is not merged.
- The status-log read is stubbed to "all acceptable".
- `decide_next("claude", slug, "success", R, owned=fact)` then returns `terminal / done / "All work packages are done"`.

The owned mission is declared finished from a stale copy in R. No WP in the occurrence map owns `committed_authority.py` or this call site, and the call site is in WP11's `runtime_bridge.py`, so the fix belongs here.

**Required fix:**
- Thread `owned` into `_merged_mission_short_circuit` and `mission_terminal_verdict` (and `_committed_surface`).
- For an owned call, both the `mission_number` gate and the status read must anchor on the owned placement seam's PRIMARY leg (P). Never R.
- Add a red-first test: the stale merged copy in R does not short-circuit an owned `decide_next` or `query_current_state`.
- Add a same-fixture non-owned control that still short-circuits.
- Declare `committed_authority.py` as out-of-map in the commit body.

### 2. [MEDIUM] `_adopt_verified_unbound_run` uses a looser matcher than the canonical one and can adopt another mission's run

**Where:** `runtime_bridge_io.py`, `_adopt_verified_unbound_run`.

**Problem:**
- It matches `entry.get("mission_slug", mission_slug) == mission_slug`, and the default makes an entry with no `mission_slug` match every slug.
- The canonical predicate in `_entry_for_mission` is strict: `candidate.get("mission_slug") == mission_slug`.
- Reproduction: `_canonicalize_run_index` leaves a pre-WP05 slug-keyed foreign entry un-rekeyed (so it has no `mission_slug`) when its canonical slot is occupied, e.g. `{"other-mission": {...}, "legacy-other-mission": {..., "mission_slug": "other-mission"}}`. `_adopt_verified_unbound_run(owned slug, owned id)` then returns True and re-keys `other-mission`'s run under the owned `mission_id`. That is a silent hijack.

This bypasses the `RunIdentityMigrationRequired` safety guard for a run the fact does not vouch for.

**Required fix:**
- Use the same strict predicate `_entry_for_mission` uses; share one helper so the two cannot drift.
- Add negative tests: an unbound entry for a different slug, and one with no slug field, is never adopted; `_entry_for_mission` behaviour is unchanged.

The positive adoption path (query mode in memory only, persisted on `get_or_start_run`) and unchanged non-owned keys are correct and tested.

## Non-blocking notes (no change required this cycle)

- **Residual: `prompt_builder` resolves through R**, so the walk tolerates a block whose reason starts with "prompt resolution failed". This belongs to WP12 (`# bridging: WP12 converts`; WP19 carries the US3-AS1 CLI row as a strict xfail that WP12 removes). The walk still asserts implement / WP01 / workspace P and `error_code is None`. Acceptable.
- **Legacy path plans twice.** `_dn_preresolve_wp_workspace` calls `plan_advance`, then `runtime_next_step` re-plans. Both are the same pure function on the same state, and reuse is keyed on the step id. Consider a public `commit_advance(plan)` so the resolved plan is the committed plan by construction.
- **Adapter fallback branch is unpinned.** `advance_run_state_after_composition` resolves on its own only when a caller passes no `wp_resolution`; the live dispatch always pre-resolves. A mutant that writes before that fallback resolution survives. Either drop the fallback branch or pin it.

## Gates

- **Markers:** `TRANSITIONAL(WP18)` = 6 (decision 1, runtime_bridge 2, lifecycle 3). `bridging: WP12` ×1, on the call line. `bridging: WP11` = 0.
- **mypy:** `--strict --explicit-package-bases` over 14 files, engine.py and committed_authority.py included: base 24 errors, head 24, identical.
- **ruff:** check, format and C901 (≤15) are clean.
- **Targeted tests:** 1250 passed, 3 skipped.
