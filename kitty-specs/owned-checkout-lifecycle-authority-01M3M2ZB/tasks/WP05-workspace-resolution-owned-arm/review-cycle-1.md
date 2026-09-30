---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T00:07:40Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review feedback, cycle 1: changes requested

Reviewer: reviewer-renata (claude). Head: 19e37621d (plus lane merge eadbf7761). Base for the diff: 4f4e0aa18.

What passed:
- Red-first order: 1e5923762 is red at its own tree (verified in a detached scratch worktree, 14 failed).
- `TRANSITIONAL(WP18)` count: exactly 1, on `resolve_workspace_for_wp(effective_root=)`.
- No `bridging:` markers were needed.
- ruff check is clean, ruff format is clean on the changed files, and C901 is at most 11.
- mypy --strict: 20 errors on the base and the same 20 on the head, so 0 new.
- The single_branch owned arm, `runs_in_checkout_root` and the stale_detection/implement conversions are sound.

## BLOCKING

### [HIGH] 1. `src/specify_cli/workspace/context.py:_lanes_manifest_workspace` / `_context_backed_workspace` / `_planning_artifact_workspace`: the coordination-topology owned arm takes its anchor from the caller, not from the fact

For an owned `lanes_with_coord` / `coord` mission, three paths are composed from whatever `repo_root` the caller passes:
- lane worktree paths: `_seam_worktree_path(repo_root, …)`;
- the context lookup: `find_context_for_wp(repo_root, …)`, joined via `repo_root / context.worktree_path`;
- the planning-lane and planning_artifact `worktree_path=repo_root`.

The callers pass different roots:
- `next` passes `repo_root=P` (`next_cmd.py:176`), so lane worktrees resolve to `P/.worktrees/<slug>-lane-x`. That is a nested path inside the owned checkout, which `implement` never creates. This is the defect WP04 was rejected for.
- `resolve_action_context(R, owned=fact)` passes R, so the planning lane resolves to R, which does not hold the owned mission at all.

Either way one leg misroutes, and the answer depends on the caller rather than on the validated fact. That breaks "the fact is the single internal representation".

The "characterise and preserve" rationale does not hold. `tests/e2e/test_worktree_owned_root_concurrency.py:405-520` only runs query-mode `next` on freshly created missions with no WPs. It asserts nothing about lane paths.

`test_owned_coordination_topology_keeps_lane_arm` currently pins the defect: it asserts `P/.worktrees/...`.

**Required fix.** When `owned` is set on the coordination arms:
- compose lane worktree paths under `owned.repository_root` (`_seam_worktree_path(owned.repository_root, …)`);
- run the context lookup and join under `owned.repository_root`;
- resolve the planning-lane and planning_artifact workspace to `owned.owned_root`, because the mission's planning surface is the owned checkout.

Re-pin the characterisation test and parametrise it over caller `repo_root ∈ {R, P}`:
- the lane path is `R/.worktrees/<slug>-lane-a` in both cases, and never under P;
- the planning-lane path is P in both cases.

If you believe the planning-lane anchor should be something other than P, raise it with the orchestrator. Do not leave it dependent on the caller. Record the change in the Activity Log.

### [HIGH] 2. `tests/specify_cli/workspace/test_owned_workspace_resolution.py` (T024 section): the FR-019 cache-key change is untested

Evidence:
- All six T024 tests pass on the red commit 1e5923762, which still has the pre-fix repo_root key.
- Mutation on the head: I changed both `_normalized_feature_cache_key(tasks_dir, …)` calls back to `_normalized_feature_cache_key(repo_root, …)` and kept the `owned` threading. Result: `test_owned_workspace_resolution.py` plus `test_workspace_context_unit.py` gave **44/44 passed**.

There are two causes:
- The T024 tests call bare `get_normalized_wp(p, …)` on plain directories, so `repo_root` already differs between R and P and the old key was already distinct. The prompt asked for R as `repo_root` plus a fact minted via `OwnedCheckout._mint`.
- The snapshot check (`(name, st_mtime_ns)`) masks key collisions whenever the snapshots differ. That includes the git-built `test_same_slug_cache_isolated_per_checkout`, which is red on base only by `TypeError`.

**Required fix:**
- Re-point the P-side lookups in the T024 tests to `get_normalized_wp(r, slug, wp, owned=fact)` / `build_normalized_wp_index(r, slug, owned=fact)`. This covers the R-P-R, mtime-invalidation, malformed-WP-error-scoping and R/P1/P2 cycle tests.
- Add a collision test in which R's and P's WP files have **identical file names and identical `st_mtime_ns`**, set with `os.utime(path, ns=(t, t))`, but different titles. R-then-P(owned)-then-R must return three correct titles.
- Also cover the error cache under an identical snapshot: malformed in P, valid in R.
- Show in the Activity Log that this test is red against the repo_root-keyed mutant.

### [MEDIUM] 3. `tests/specify_cli/cli/commands/agent/test_status_baseline_wiring.py:180,225`: blast-radius regression caused by this WP

`test_recycled_pid_caught_through_check_doing_wps` and `test_matching_baseline_still_trusts_live_pid_through_check_doing_wps` now fail. The error is `TypeError: <lambda>() got an unexpected keyword argument 'owned'`, because `stale_detection.py:488` now always passes `owned=owned`. Both tests are green on base 4f4e0aa18 (verified). The Activity Log's "stale-detection suites (targeted, all green)" is therefore inaccurate.

**Required fix:** update the fakes to `lambda root, slug, wp_id, **_kw: …`. This is a declared out-of-map test edit; name it in the commit body. Then re-run every file found by `grep -rl "stale_detection\|check_doing_wps_for_staleness" tests` and record the counts.

### [MEDIUM] 4. `src/specify_cli/workspace/context.py:resolve_workspace_for_wp` identity gate: no pin that the owned arm never calls `get_main_repo_root`

The code is correct: it uses `owned.repository_root`. The pin is missing. Mutation: forcing the `get_main_repo_root(repo_root)` branch for owned calls leaves 21/21 tests passing. The subprocess test runs without `write_intent`, and the owned arm of `enforce_checkout_identity` ignores `primary_root`.

**Required fix:** add a test that runs `resolve_workspace_for_wp(r, slug, "WP01", owned=fact, write_intent=True, current_cwd=p)` with both `specify_cli.core.paths.get_main_repo_root` and `subprocess.run` monkeypatched to raise. Show it is red against that mutant.

## NON-BLOCKING (fix in the same cycle)

- **[LOW]** `test_owned_arm_raises_on_both_keywords` is vacuous. It passed on the red commit because an unknown keyword also raises `TypeError`. Add `match="not both"`.
- **[LOW]** T025 step 5 asked for a test that the `repo_root` kind is always exempt. It is missing. Add a direct `enforce_checkout_identity(..., resolution_kind="repo_root", current_cwd=<foreign dir>)` test that expects no raise.
- **[LOW]** `src/mission_runtime/resolution.py:797-799`: the prompt said to remove WP04's comment at this call. It was replaced by a WP-bookkeeping comment ("declared in WP05's PR"). Delete it; the rationale belongs in the commit body and the PR.
- **[LOW]** The Activity Log `resolution_kind` inventory omits `src/specify_cli/core/worktree_topology.py:67,200,205,270,273,305,336`. That file has `== "repo_root"` / `!= "repo_root"` comparisons and is fed by `implement_support`'s `resolution_kind` field. It is in WP12's file list. Add these rows to the inventory, with WP12 as the owner.
- **[LOW, informational]** The body of the red commit says `get_normalized_wp(P, ...)` "returns R's stale title". On that tree it actually raises `TypeError` for the `owned=` keyword. No rewrite is required; note it accurately in the Activity Log.

## Commands you must re-run and record

- `pytest tests/specify_cli/workspace/test_owned_workspace_resolution.py tests/runtime/test_workspace_context_unit.py`
- `pytest tests/specify_cli/cli/commands/agent/test_status_baseline_wiring.py` plus the stale-detection hits
- `pytest tests/mission_runtime/test_resolution_owned.py tests/specify_cli/core/test_worktree_topology.py tests/integration/test_coord_loop_workspace.py`
- ruff check, ruff format and mypy `--strict` over the changed files.

Pre-existing reds that are not yours: `tests/integration/test_review_durability_matrix.py` has 3 arbiter tests that are red on base 4f4e0aa18 too (lanes.json absent).
