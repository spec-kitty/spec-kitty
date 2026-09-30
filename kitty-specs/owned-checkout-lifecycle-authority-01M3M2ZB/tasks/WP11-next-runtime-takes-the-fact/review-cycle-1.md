---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T08:54:32Z'
reviewer_agent: claude
wp_id: WP11
---

# WP11 review, cycle 1: CHANGES REQUESTED

Reviewer: reviewer-renata (claude). Base bb67d7982, head 2e11096dd (lane-j).

## What passed

- Red-first order: I checked this in a detached scratch worktree.
  - ea6057b67 has 5 of 7 red.
  - f0139e154 has 2 of 2 red.
  - Both campsites (5db5af729, cb71f5ffb) come before the signature changes.
- Ruff check and format are clean. No function is above C901 15.
- mypy `--strict --explicit-package-bases` over the 12 files gives 24 errors on the base and 24 on the head. The error set is identical.
- `test_layer_rules.py`: 74 passed. The runtime ledger is unchanged.
- `TRANSITIONAL(WP18)` counts are 1/2/3 = 6, which matches the DoD. `bridging: WP11` is empty.
- `Decision.error_code` is emitted only when non-null. The field-set gate update is legitimate.

## Findings

### 1. [BLOCKER] `DecideNextContext.owned` is never populated, so the whole `_dn_*` owned threading is dead

**Where:** `src/runtime/next/runtime_bridge.py:1836-1851` (`_dn_bootstrap`).

**Problem:**
- `DecideNextContext(...)` is built without `owned=owned`, so `ctx.owned` is always `None`.
- As a result, every downstream arm reached through the context never sees the fact:
  - `_dn_composition_dispatch` (config_root, `_advance_run_state_after_composition(owned=ctx.owned)`);
  - `_dn_decision_materialize` (retrospective config_root);
  - the new `_dn_preresolve_wp_workspace(owned=ctx.owned)`;
  - `_map_runtime_decision`.

**Reproduced at the real runtime entry point.** Fixture: `make_owned_checkouts("single_branch")`, then `_finalize`, then `advance_to_step(owned_root, slug, "software-dev", "tasks")`, then `decide_next("claude", slug, "success", R, owned=fact)`.
- `_wp_iteration_action_and_state` is called with `owned=None` and `repo_root=R`.
- The board declines and falls back to `_state_to_action`, which raises `ValueError: Work package WP01 was not found under <R>/kitty-specs/<slug>/tasks`.
- The decision is `blocked` with "Run-state advancement after composition failed … ValueError".
- The run's `state.json` is already advanced to `implement` (`completed_steps` includes `tasks`). That is exactly the O5/FR-008 wedge this WP exists to fix.

**Required fix:**
- Pass `owned=owned` into `DecideNextContext`.
- Add the T057 step-4 FR-009 composition test the WP requires. It asserts `kwargs["owned"] is fact` and `repo_root == fact.owned_root` on the composition stubs. It was never written, and it would have caught this.

### 2. [BLOCKER] Resolve-before-persist does not cover the composition advance path that software-dev tasks→implement actually takes

**Where:**
- `runtime_bridge_engine.advance_run_state_after_composition` (`:350-385`) runs `_write_snapshot` and then `_rb._map_runtime_decision` (resolution after persist).
- The T061 step-3 preview lives only in `_dn_decision_materialize`, the legacy `runtime_next_step` path.

**Problem:** software-dev `tasks` is a composed action, so O5 goes through `_dn_composition_dispatch`. The wedge is still reachable there even after Finding 1 is fixed, whenever resolution fails.

**Required fix:** resolution must happen before persistence on **both** advance paths. Put it in one shared place; do not add a second copy. For example:
- have `advance_run_state_after_composition` resolve the planned WP step before `_apply_decision_effects` / `_write_snapshot`;
- or (preferred, see Finding 3) give the engine a plan/commit split that both paths use.

Also, the composition path's `except Exception` wraps the resolution error into `blocked`, which FR-008 forbids. The typed error must propagate unwrapped with nothing persisted.

### 3. [HIGH] The preview is a second, divergence-prone computation of the engine's next step (parallel authority)

**Where:** `_snapshot_after_result` / `_preview_next_step`, `runtime_bridge.py:2345-2386`.

**Problem:** `_snapshot_after_result` restates the engine's "complete the issued step" prelude (`engine.py:299-322`), including its two blocked-reason literals. Known divergences:
- **(a) Significance re-plan.** The engine re-plans after an `audit:` significance LOW band (`engine.py:388-423`). The preview sees `decision_required`, does not pre-resolve, and the engine then issues a different step, which is resolved after persist. The wedge is reachable there.
- **(b) Silent drift.** Any future change to the engine prelude silently drifts from the mirror.

**Required fix (the canonical ordering):** make the engine the single authority.
- Extract the prelude into one pure engine function, e.g. `_internal_runtime.engine.apply_result(snapshot, result) -> MissionRunSnapshot`, used by `next_step`, by `advance_run_state_after_composition`'s `_mark_step_completed`, and by the preview.
- Better: add an engine-level `plan_advance(run_ref, agent_id, result) -> planned decision` (pure, including the significance re-plan) and have `next_step` / the composition adapter commit that plan. The bridge then resolves the planned step between plan and commit.
- Delete the mirror.
- Narrow the preview's `except Exception` once the code is shared. Right now it is a broad debug-only handler.

### 4. [HIGH] The two ordering tests do not pin the preview's correctness (mutation survivors)

**Where:** `tests/next/test_runtime_bridge_unit.py::TestResolveWpWorkspaceBeforePersistingTheAdvance`. `plan_next` is stubbed to always return `review`.

**Mutation results on head:**

| Mutant | Result |
|---|---|
| `_snapshot_after_result` → identity | survives |
| always plan with result `"failed"` | survives |
| reuse `wp_resolution` without the `step_id == preview_step_id` check | survives |
| never reuse the pre-resolution | killed |
| preview → `None` | killed |

**Required fix:** add a test through the **real** engine and planner, with no `plan_next` stub. Seed a run at `tasks` via `advance_to_step` and assert:
- the previewed step equals the step `runtime_next_step` / the composition adapter issues;
- a mismatch is not reused.

Add a significance-LOW case, or make it structurally impossible via Finding 3.

### 5. [HIGH] The FR-008 "no wedge" test bypasses the entry point the spec names, and a runtime-level walk is feasible

**Where:** `tests/integration/test_owned_next_runtime.py::TestFr008NoWedge`. It calls `_wp_iteration_action_and_state` directly.

**Problem:** T057 step 2 requires `decision.decide_next("claude", slug, "success", R, owned=fact)` on a finalized owned mission. It must assert:
- no traceback;
- not blocked;
- `action == "implement"`, `wp_id == "WP01"`, `workspace_path == str(fact.owned_root)`;
- a following `query_current_state(..., owned=fact)` has advanced.

This is feasible with existing fixtures: `make_owned_checkouts` + `_finalize` + `tests/runtime/_next_mission_scaffold.advance_to_step(fact.owned_root, slug, "software-dev", "tasks")`. I ran exactly this, and it is red on head (Finding 1).

**Required fix:**
- Write that test (it fails today). Wrap it in `r_snapshot`.
- Also add the T057 step-3 `_state_to_action(..., owned=fact)` pre-finalize pin, which is missing.

A CLI `next --owned-checkout` walk is WP19's scope; the runtime-entry walk is this WP's scope.

### 6. [HIGH] The owned coord-less `DecisionGitLog` is anchored on the repository root checkout R (root-discipline regression)

**Where:** `_wrap_with_decision_git_log`, `runtime_bridge.py:293-400`.

**Problem:**
- For an owned `single_branch` fact, `resolve_commit_target(repo_root=R)` returns `worktree_root = R`. I verified this: `DecisionGitLog._worktree_root == R`.
- On the base, next_cmd passed P, so it was P.
- T060 step 4 requires every git cwd and `DecisionGitLog(repo_root=…)` to use `owned.owned_root`.
- Decision-input events would now be appended and committed under `R/kitty-specs/<slug>/`, which violates NFR-001.

**Required fix:**
- Coord-less owned: `worktree_root` / `repo_root` = `owned.owned_root`.
- Coord-routing owned: keep the coordination worktree under `owned.repository_root/.worktrees` (correct today, see Q3).
- Add a test asserting both anchors, plus an `r_snapshot` around a `decision_required` emission.

### 7. [MEDIUM] The O8 injections are vacuous on the fixture used

**Where:** `TestO8CoordinationWorkspaceUnavailable`.

**Problem:**
- The `make_owned_checkouts("lanes_with_coord")` fixture has no coordination branch.
- So `CoordinationWorkspace.resolve(R, …)`'s `git worktree add` always fails. I checked with no injection at all: `decide_next(..., owned=fact)` already returns `blocked` / `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
- Neither the zero-byte `commondir` nor the `worktree list` seam is what produces the asserted code.

**Required fix:**
- Build the fixture with the coordination branch present, so a no-injection control materializes and is non-blocked.
- Keep each injection as the only difference from that control.
- Also perform T057 step 5(a)'s "remove its coordination worktree directory" step.

### 8. [MEDIUM] FR-007 stale-copy assertion is vacuous

**Where:** `TestFr007StaleRootCopyBoard`.

**Problem:**
- It uses `query_current_state`, whose `workspace_path` is typically `None`, so the `if decision.workspace_path is not None:` guard makes the check a no-op.
- "WP set is P's" is not asserted.
- The spec says `decide_next(..., "success", R, owned=fact)`.

**Required fix:** assert unconditionally on a `decide_next` step decision, and assert the WP set is P's. Add the non-owned same-fixture controls from T057 step 9 for each row.

### 9. [MEDIUM] The legacy arm in `next_invocation_lifecycle.py` does not use the single helper

**Where:** `next_invocation_lifecycle.py:173, 268, 341`.

**Problem:**
- These forward `effective_root=effective_root` straight into `mission_context_for`.
- The Staging Strategy requires each legacy arm to mint once via `_transitional_owned_from_legacy` and continue on the `owned` path.
- T063's grep check therefore lists 3 extra `effective_root` lines beyond the six marked ones plus the helper body.

**Required fix:**

```python
if owned is None and effective_root is not None:
    owned = _transitional_owned_from_legacy(effective_root, mission_slug)
```

Then call `mission_context_for(..., owned=owned)` only.

### 10. [LOW] `bridging: WP12 converts` sits on a comment line above the `with` block rather than on the `build_prompt(` call

**Where:** `decision.py:667-671`.

**Required fix:** put the marker on the call line so WP12's grep and count gate reads it unambiguously. There is 1 call site, which is correct.

## Notes: no change required

- Q6: leaving `_with_guard_failure_paths` unchanged is acceptable. Its docstring says it resolves through the same placement seam as `gather_artifact_presence`, and the spec (T067.5) explicitly allows it with a logged reason. Re-check this once Finding 1 is fixed: `decide_next` still passes `repo_root` = R, so the guard paths for an owned mission are resolved against R's seam. If `guard_failure_artifact_paths` is not owned-aware, it would report R paths. Thread `owned` if so.
- Q3: `CoordinationWorkspaceUnavailable` is not a duplicate of WP04's `ActionContextError(OWNED_COORDINATION_WORKSPACE_UNAVAILABLE)` raised by `resolution.py`. They are different failure sites: the registry probe versus an unmaterialized surface read. Both carry the same registry code, and subclassing `CalledProcessError` is required for the retry. Keep both. Make sure `_dn_bootstrap` also maps WP04's `ActionContextError` with that code to `blocked`, since only `CoordinationWorkspaceUnavailable` is caught today.
- The formatting churn in `tests/runtime/test_bridge_cores.py` and the related test files matches `ruff format` of the base, which was failing format check. That is acceptable campsite cleaning, and it is declared in e32201737.
