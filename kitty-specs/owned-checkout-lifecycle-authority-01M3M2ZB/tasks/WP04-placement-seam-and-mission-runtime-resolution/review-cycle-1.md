---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T21:15:54Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback, cycle 1 (reviewer-renata)

**Verdict: CHANGES REQUESTED.** Lane commits reviewed: 7832c5501 (red) and c220d467d (fix).

## What is already good (keep it)

- **Red-first holds.** At 7832c5501, 17 of the 42 tests in the four WP04 test files fail. The three legacy-keyword O3/O4/US2-AS2 tests fail for the right reasons: an R `meta.json` path, a `wp_file` under R's stale copy, and WP05 found under R. All of them pass at the lane tip.
- **The O3/O4 fix is in place.** `_resolve_wp_bearing_fields` now forwards `owned=` and `effective_root=` into `locate_work_package`. A stale copy never wins `wp_file`. A missing WP raises `WORK_PACKAGE_UNRESOLVED` and the message names P, never R.
- `_require_owned_single_branch` is deleted, and so are both of its call sites.
- There are exactly 9 `TRANSITIONAL(WP18)` markers: 8 in resolution.py and 1 in support.py, as the DoD lists. `_refuse_both` raises `TypeError`.
- `resolve_workspace_for_wp` is untouched and carries a plain comment. There is no TODO or FIXME token.
- The `OwnedCheckout` import in resolution.py is under `TYPE_CHECKING`, so there is no import cycle.
- Targeted tests: 433 passed. `ruff check` is clean, and complexity is ≤ 11.

## Blocking findings

### F1 (focus A, Architecture-B fidelity): the fact never reaches the readers. It is turned back into a bare Path at every seam entry.

`_owned_read_root(owned, effective_root)` returns `owned.owned_root`. Every seam then runs the pre-existing `effective_root: Path` code unchanged. Evidence:

- **`mission_context_for` does none of T018 step 1.** On the owned arm it:
  - re-walks the handle with `candidate_feature_dir_for_mission` and still consults `resolver`;
  - re-reads topology from meta through `_resolve_topology` instead of using `owned.topology`, and has no conflicting-`topology` refusal;
  - re-reads the target branch from meta, falling back to `resolve_primary_branch` (git), instead of using `owned.target_branch`;
  - never reads `owned.mission_dir`.

  `resolve_action_context` has the same gaps against T018 step 2: `_resolve_mission_slug` does not receive the fact, the target-branch fork does not use `owned.target_branch`, and `_resolve_topology` is not skipped.
- **IC-02 and contract §7 are violated: "PRIMARY-partition kinds read `owned.mission_dir` and never call `get_main_repo_root`".** An instrumented probe of `resolve_artifact_surface(R, slug, SPEC/STATUS_STATE, owned=fact)` counted 8 `get_main_repo_root` calls for the two reads. All of them come from `_read_path_resolver` (`candidate_feature_dir_for_mission`, `_compose_primary_feature_dir`, `_canonicalize_bare_modern_handle`, `read_primary_meta`, `_stored_topology_best_effort`).
- **The T017 test was weakened.** `test_primary_kinds_read_dir_is_mission_dir_with_zero_git_calls` does not monkeypatch `get_main_repo_root` to raise, although T017 step 1 requires it. Its docstring explains the omission away. Restore the patch, and make the owned arm pass it.
- **Unmarked transitional surface (plan: "An unmarked transitional surface is a review rejection").** Running WP01's scanner on resolution.py reports 87 G4 offenders and 17 G5 offenders. Only 8 are the marked legacy declarations, and 2 are the normaliser signatures. That leaves **7 unmarked private `effective_root: Path | None` parameters**:
  - `_resolve_mission_slug` (:523)
  - `_resolve_wp_bearing_fields` (:740, **newly added by WP04**)
  - `_resolve_coordination_branch` (:947)
  - `_resolve_topology` (:1009)
  - `_resolve_mission_id` (:1229)
  - `_resolve_status_surface_dir` (:1291)
  - `_assemble_core_fragments` (:1446)

  About 70 further identifier or keyword uses remain besides those parameters. After WP18 T096 deletes the marked lines, G4/G5 would still fail on all of them. WP18 would then face a **large internal conversion**, not a keyword removal. That is the deferred ratchet the operator rejected.

**Required:**

1. Make the fact the one internal representation in resolution.py. The private helpers above take `owned: OwnedCheckout | None` and read `owned.mission_dir`, `owned.target_branch`, `owned.topology` and `owned.repository_root`.
2. On the owned arm, skip the handle walk and the resolver.
3. Where a legacy Path arm must survive until WP18 for unconverted callers, keep it as a separate parameter, each marked `# TRANSITIONAL(WP18)`.
4. Amend the WP04 DoD marker list and count in the same PR, as the DoD itself allows ("any deviation is amended here in the same PR"). WP18 T096 must stay a pure deletion.
5. Add the T018 tests:
   - a resolver that raises when called is never consulted with a fact;
   - a conflicting explicit `topology` raises `OWNED_TOPOLOGY_UNSUPPORTED` (import it from `OwnedRefusalCode`);
   - the target branch comes from the fact when meta differs.

### F2 (focus B): the COORD surface of an owned coordination-topology fact is a path that does not exist, even when the coordination worktree is materialised. WP04 turned this into a silent return.

- **Probe:** use the test's own `_lanes_with_coord_repo`, with the coordination worktree materialised at `R/.worktrees/<slug>-coord`, and call `resolve_artifact_surface(R, slug, STATUS_STATE, owned=fact)`. It returns `P/.worktrees/<slug>-coord/kitty-specs/<slug>`: `exists()` is False and the stamp is COORD. It returns the same thing when the coordination worktree is removed (UNMATERIALIZED).
- **Cause:** `_resolve_status_surface_dir`'s owned arm composes the coordination worktree under `effective_root`, which is P, not the repository root. It then falls through to `return coord_dir` on `UNMATERIALIZED`. This is a direct consequence of F1: once the fact is folded into `owned_root`, `owned.repository_root` is lost.
- **Before WP04,** the placement surfaces (`resolve_placement_only` and `resolve_artifact_surface`) refused this case with a typed error. **After WP04** they return the wrong path silently. That makes it a regression **introduced at these surfaces by this WP**, even though the fall-through code predates it. `_resolve_status_surface_dir` is in resolution.py, a WP04-owned file, so the "code this WP does not own" rationale in the re-expressed test does not hold.
- **T019 step 7 required** the re-expressed `test_coord_read_seam_callers.py` test to assert a **typed** coordination error and never a silent path. The rewrite instead pins the silent `-coord` path as the contract.
- The row-4 test `test_lanes_with_coord_fact_stamps_status_state_coord_and_spec_primary` asserts only the stamp, not the path, so it is vacuous on exactly this defect.

**Required:**

1. On the owned arm, compose the coordination worktree under `owned.repository_root`, so a materialised worktree resolves to the real path.
2. Fail closed with a typed error on `UNMATERIALIZED`, such as `CoordinationWorktreeUnmaterialized` or an `ActionContextError` coded from `OwnedRefusalCode`. Never return the predicted path.
3. Rewrite the `test_coord_read_seam_callers.py` pin to assert the typed refusal.
4. Extend the row-4 test to assert that `path.exists()` and that the path is under `owned.repository_root/.worktrees`.
5. Record the git-call count for row 4 in the Activity Log.

This is not the #4867 hardening that WP11 owns. It is the correctness of the placement arm that WP04 opened.

### F3: the T019 behaviour table, row 2, is wrong for single_branch

- **Probe:** with a `single_branch` fact, `resolve_artifact_surface(..., STATUS_STATE, owned=fact)` returns `path=owned.mission_dir` with `surface_kind=COORD`.
- **Required by the table:** the stamp should be PRIMARY for a COORD-partition kind under `single_branch` (the AH-2 affirmative home). Before WP04 it was PRIMARY.
- **Why it matters:** single_branch is the main lifecycle case. `artifact_home_for(kind, commit_target).read_surface` is not topology-collapsed, so the stamp now contradicts the path.
- **Fix:** derive the stamp from the home that `mission_context_for` actually chose (it already collapses read_dir by topology). Add a test that asserts every row of the T019 table, including row 2.

### F4: handle canonicalisation is missing (T017 edge case, T020 step 4)

- **Probe:** `locate_work_package(R, "01M1A900", "WP01", owned=fact)` and the same call with the full mission id both raise `ActionContextError("placement_seam fact is for mission 'owned-01M1A900' but was called with mission_slug '01M1A900'")`.
- **Why it matters:** callers pass the slug, mid8 or mission id.
- **Required:**
  - `PlacementSeam` and `locate_work_package` compare canonical forms: mid8 or mission id canonicalise to `owned.mission_slug`.
  - `locate_work_package` raises `TaskCliError` naming both slugs on a real mismatch, as T020 specifies.
  - Parametrise the owned happy path over slug, mid8 and mission id (T016 edge case).
  - Add the symlinked-P case (T016 edge case). Neither test exists yet.

### F5: WP04 adds new mypy --strict errors in callers (plan: mypy invocation discipline)

- Putting `owned: OwnedCheckout | None` ahead of the legacy keyword makes existing `**dict[str, Path]` splats fail type-checking. There are 5 new `arg-type` errors ("Argument 3 to "placement_seam" has incompatible type "**dict[str, Path]"; expected "OwnedCheckout | None""):
  - `agent_tasks_ports.py:251,258,280`
  - `tasks_move_task.py:501,1811`
- Base has 0 of these errors under the same invocation: `mypy --strict --explicit-package-bases` over every `effective_root_kwargs(` caller plus resolution.py and tasks_move_task.py.
- **Required:** fix without suppression, for example by typing the splat helper so mypy sees only the `effective_root` key. Record the before and after counts.

### F6: the Activity Log is empty

T016, T019 and T021 require the log to record:

- the red run, with test ids and failure lines;
- the T021 scanner classification table covering every hit;
- the row-4 git-call count;
- the RETROSPECTIVE `writer.py` fold check (T017 step 6);
- the reasoning about `next` / e2e (T019 edge case).

Add them.

## Non-blocking

- `test_owned_single_branch_ssot.py` replaced the minter-refusal pin with a NOTE comment. T019 step 5 asks for a test there that calls `resolve_owned_mission` with the default allowed set and asserts `OwnedRefusalCode.OWNED_TOPOLOGY_UNSUPPORTED`. Add it; it is a single call.
- The `owned=` twins of the WP-bearing tests do not assert "not under R". T016's non-vacuity rule asks for both assertions.
- `_OWNED_ARTIFACT_UNSUPPORTED_CODE = "OWNED_ARTIFACT_UNSUPPORTED"` is a string literal. If `OwnedRefusalCode` has this member, import it lazily. If it does not, note why.
- `locate_work_package` inlines the `TypeError` message instead of sharing the rule. That is acceptable across modules, but keep the text identical.
- `ruff format --check` flags context.py and support.py. Both were already unformatted on base, so this is not a WP04 regression. It is a campsite opportunity.

## Anti-pattern checklist

1. Dead code: PASS.
2. Synthetic fixture: PARTIAL. The row-4 path is untested (F2).
3. Silent empty or wrong return: FAIL (F2).
4. FR coverage: PASS for FR-006, FR-007 and FR-011. FR-023 is only partly covered (F2, F3).
5. Frozen surface: PASS.
6. Locked decision (IC-02 / §7 "never call get_main_repo_root"): FAIL (F1).
7. Shared-file ownership: resolution.py is also edited by WP05 (a one-line `owned=` forward) and support.py by WP16/WP17. Rebase notice to WP05, WP07, WP15, WP17 and WP18.
8. Production fragility: PASS. The new raises are documented.
