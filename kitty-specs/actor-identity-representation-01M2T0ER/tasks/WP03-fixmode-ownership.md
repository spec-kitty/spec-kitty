---
work_package_id: WP03
title: Fix-mode ownership after rejection (#4673)
dependencies:
- WP02
requirement_refs:
- FR-007
- FR-008
planning_base_branch: fix/actor-identity-representation
merge_target_branch: fix/actor-identity-representation
branch_strategy: Planning artifacts for this mission were generated on fix/actor-identity-representation. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/actor-identity-representation unless the human explicitly redirects the landing branch.
subtasks:
- T010
- T011
- T012
- T013
- T014
history:
- event: created
  at: '2026-09-18T10:41:10Z'
  note: Initial generation from /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- tests/specify_cli/cli/commands/agent/test_fixmode_ownership_4673.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/cli/commands/agent/tasks_move_task.py
- src/specify_cli/cli/commands/agent/tasks_transition_core.py
- src/specify_cli/status/work_package_lifecycle.py
- tests/specify_cli/cli/commands/agent/test_fixmode_ownership_4673.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned agent profile:

```
/ad-hoc-profile-load python-pedro
```

Red-first per ADR 2026-07-17-1. `--force` reassignment is a WORKAROUND, not the intended path
(C-003) — the fix must make the ordinary submission work.

---

## Objective

Fix #4673: after a reviewer rejects a WP and an implementer successfully claims it in fix mode, the
reduced ownership still points at the previous reviewer, so `move-task --to for_review --agent
<implementer>` is refused without `--force`. Make a successful fix-mode claim record the new
implementer as owner so the ordinary submission is accepted; keep genuine ownership conflicts
refused.

## Root (grounded — three authorities, C-006)

- Ownership is carried by THREE reduced slots consulted by different guards: transition `actor`
  (overwritten each hop; = reviewer after a rejection); runtime `agent` (released on rejection via
  `_CLAIM_RELEASE_SLOTS`; move-task reads it at `tasks_move_task.py:355`, fallback `:2329`); sticky
  resolved-binding `role` (NOT released with the claim).
- CLI-local mechanism (a) — **precise live root**: on a rejection (`--to planned`, run by the
  reviewer, `st.agent`=reviewer), `_mt_emit_runtime_state` (`tasks_move_task.py:2751-2774`) builds
  ONE `InnerStateChanged` delta carrying BOTH `fields["agent"] = st.agent` (reviewer, set at
  **:2753-2754** because `not st.claim_emitted`) AND `release_runtime_claim=True` (set
  UNCONDITIONALLY by `_build_claim_review_override` at **:2693**). The reducer applies the
  release-clear BEFORE its replace-slot loop, so the concrete `agent`=reviewer in the SAME delta
  overwrites the just-released slot → runtime `agent` holds the reviewer after a rejection. **Fix
  seam:** suppress `fields["agent"]` when `st.target_lane == Lane.PLANNED` (guard the :2752-2754
  block with `and st.target_lane != Lane.PLANNED`, or pop `agent` in `_build_claim_review_override`)
  so the release actually takes effect. **Scope the suppression to `target_lane == PLANNED` ONLY** —
  a broad removal breaks WP04's generic `move-task --agent` persistence (which relies on that exact
  line firing when target ≠ PLANNED). **This is the in-scope fix.**
- **Also reconcile the move-task ownership gate**: `_guard_agent_ownership`
  (`tasks_transition_core.py:425`) compares the runtime `agent` slot by RAW string equality
  (`req.current_agent != req.agent`) — it does NOT call `_actor_key`. So WP01's compact-vs-dict
  reconciliation does not reach it; a dict-vs-compact submit still trips here. Route this comparison
  through the same tool-scoped `_actor_key` (that is why `tasks_transition_core.py` is now owned).
- Upstream mechanism (b): the shared `spec-kitty-events` reducer folds all transitions then all
  annotations (not timestamp-interleaved), so a stale rejection annotation can overwrite the
  fix-claim. **Out of scope to edit (C-001)** — file a scoped upstream follow-up only if it still
  bites after (a) is fixed.

## Subtasks

### T010 — Red-first canonical e2e regression (commit FIRST, RED on base)
Add `tests/specify_cli/cli/commands/agent/test_fixmode_ownership_4673.py`
(`@pytest.mark.regression`, issue ref): implement → for_review → independent review → rejection →
fix-mode claim by implementer → `for_review` WITHOUT `--force`. Assert the transition `actor` slot,
runtime `agent` slot, AND the `role` slot BY NAME at each hop (C-006); assert a genuinely different
agent is still refused. RED on base.

### T011 — Rejection releases the claim (no reviewer re-stamp)
Fix mechanism (a): the rejection must genuinely release the prior claim rather than re-stamping the
reviewer into the ownership slot the submit gate reads. Reconcile the three authorities so the
claim/review gates and the move-task gate agree on the owner; ensure a stale sticky `role` is not
read as current ownership.

### T012 — Fix-mode claim records the new implementer
Ensure a successful fix-mode implement claim writes the new implementer into the slot the
`for_review` submission gate consults, so the ordinary submission is accepted.

### T013 — Re-verify e2e on base; hedge honestly (C-001)
Re-verify the full loop green with only the CLI-side fix. The upstream-attribution escape is
reachable ONLY AFTER T011 (re-stamp removed) and T012 (fix-mode claim writes the new implementer)
are demonstrably landed and green in isolation. To claim "residual is upstream" you MUST attach a
reduced-event/fold trace showing the stale rejection annotation overwriting the fix-claim WITH the
CLI re-stamp already removed — a bare "looks upstream" assertion is rejected. Then file a scoped
`spec-kitty-events` follow-up and record FR-007 as *partially met, upstream-blocked* with the issue
handle (US3-AC4). The reviewer refuses the partial-met verdict absent that trace + handle.

### Test harness (extend, don't build)
Extend `tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py` (real
`move-task` CLI through reject→fix→re-approve). MUST-NOT-REGRESS:
`test_move_task_rollback_clears_claim.py` (exercises `release_runtime_claim` — the exact slot), `test_move_task_guard.py`
(`_guard_agent_ownership`), `tests/integration/test_rejection_cycle.py`,
`tests/integration/test_2939_move_task_clean_tree_after_rejection.py`.

### T014 — Green + gates
Witness green; `ruff`/`ruff format`/`mypy --strict` clean; complexity ≤15; zero new suppressions;
no historical event rewritten (NFR-001).

## Branch Strategy

Planning branch and local merge target: `fix/actor-identity-representation`. Runs in the shared
mission lane worktree from `lanes.json`, after WP02.

## Test strategy

`tests/specify_cli/cli/commands/agent/` (canonical e2e) + `tests/status/` if the ownership slot
logic in `work_package_lifecycle.py` gets a focused unit. Assert named slots, not one slot twice.

## Definition of Done

- FR-007/008 satisfied (or FR-007 partially-met-upstream-blocked with a filed follow-up); SC-003
  met via CLI paths; genuine conflict still refused; `--force` not required for the legitimate
  implementer. Gates clean. Distinct reviewer approves red→green.

## Red-first evidence protocol + cross-WP coupling (binding)

Commit the regression as its OWN commit BEFORE the fix; record base SHA + verbatim failing output;
name red-on-base (e.g. `for_review` submission accepted without `--force`) vs pre-existing-green
(different-agent still refused). Baseline = lane tip at WP start (WP01/WP02 landed); reviewer
re-runs on that SHA. **Coupling:** WP03 and WP04 both edit `_mt_emit_runtime_state:2753-2754`.
WP03's `agent`-suppression MUST be scoped to `target_lane == PLANNED` only; WP04 relies on that line
firing for a non-rollback `move-task --agent`. Because execution is one serial lane and WP04 runs
after WP03, the WP04 reviewer must re-run WP03's regression after WP04 lands.

## Reviewer guidance

Confirm the regression asserts THREE distinct named slots at each hop (not the same slot twice);
that the rejection genuinely releases the claim; that `_guard_agent_ownership` now uses the
tool-scoped key (dict-vs-compact submit no longer trips); that no reducer/upstream file was edited;
and that any residual is honestly reported per C-001 (trace + issue handle) rather than green-washed.
