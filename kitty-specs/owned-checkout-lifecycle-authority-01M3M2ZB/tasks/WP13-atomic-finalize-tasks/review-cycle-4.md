---
affected_files: []
cycle_number: 4
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T11:05:13Z'
reviewer_agent: claude
wp_id: WP13
---

# WP13 review, cycle 4: REJECTED (reviewer-renata)

Both cycle-3 MEDIUMs are fixed.

- **mypy:** with my exact 16-file invocation (finalize, `mission_parsing`, `tasks_finalize_validation`, `_owned_checkout`, `owned_mission`, `bootstrap`, `commit_router`, `status_transition`, `surface_resolver`, `mission`, `acceptance/matrix`, `issue_matrix`, `context`, `tasks_finalize`, `lifecycle_events`, `mission_creation`):
  - base 5faee3662 has 9 errors and head has 9, identical;
  - adding `status/emit.py` (17 files) gives 9 and 9, identical.
- **Dependency gate:**
  - My `_match_wp_files` recorder shows an owned finalize reads WP01 and WP02 from **P**, and an owned claim reads WP01 from **P**.
  - The red pin `test_owned_claim_dependency_gate_reads_p_not_the_repository_root[absent|stale_declares_none]` is red with `src` at 7d7b20343: 3 failed, including the ledger pin.
  - Mutating `_declared_dependencies` to ignore `owned` fails all 3.

Three items block approval.

## Blocking

1. **[MEDIUM] `coordination/status_transition.py:1573` and `:1820` use conditional kwargs, which the operator has ruled out.**
   - Both lines use `**({"owned": identity.owned} if identity.owned is not None else {})`. The operator's standing ruling from WP14: no conditional-kwargs pattern. Widen the test double instead.
   - **Fix:**
     - Pass `owned=identity.owned` unconditionally at both sites.
     - Widen `tracking_readiness` in `tests/status/test_dependency_guard.py:818` to `(planning_dir, wp_id, snapshot, *, owned=None)`, forwarding `owned=owned` to the real function.
     - Declare the test edit in the commit body. That file is WP07's.

2. **[MEDIUM] `mission_finalize.py:3813`: `_scaffold_issue_matrix_if_present` is never given `owned`, so the owned arm is dead and the ledger now approves its non-owned reads.**
   - The call passes `ctx.repo_root`, which is P, but no `owned=ctx.owned`. In an owned finalize the helper therefore runs its **non-owned** arm:
     - the `effective_root` bridging expression (`# bridging: WP17 converts`) never fires;
     - `scaffold_issue_matrix` takes the `coord_read_dir_for(P, …)` branch;
     - the owned fail-closed `if owned: raise` is dead, so an owned scaffold failure is downgraded to a warning.
   - This is why the ledger's 17 `coord_read_dir_for` reads exist. They are attributed to "surface classification", but they are a missed owned thread.
   - The shape predates WP13 (base cd5581772 has it too), but it sits in WP13's authoritative file and the conversion scope.
   - **Fix:**
     - Add a red-first pin: in an owned finalize, `scaffold_issue_matrix` receives the owned root, or `coord_read_dir_for` is never reached. It must be red now.
     - Then pass `owned=ctx.owned` and lower the ledger. `coord_read_dir_for` should drop to 0, or to whatever remains with a stated reason.

3. **[MEDIUM] `test_owned_lifecycle_acceptance_finalize.py:797-872`: the ledger design can still hide a leak.**
   - (a) **Inequality instead of equality.** The pin fails only when `count > ledger`. After any legitimate shrink, the headroom stays and a new read fits silently under the old number. It is "shrink-only" in name but not enforced. **Fix:** assert `counts == _RESOLVER_READ_LEDGER` exactly, so every shrink must lower the ledger in the same commit.
   - (b) **Outermost attribution.** The whole subtree under an allowed entry frame is one bucket. Finding 2 is the proof: a missed owned thread's 17 reads were blessed as "coord_read_dir_for surface classification". A new content read nested under `mission_has_coordination_branch`, `_resolve_group_placement` or `coord_read_dir_for` would be counted identically, and would be hidden completely if paired with a shrink.
   - **Fix:** key the ledger on `(outermost entry frame, immediate caller of get_main_repo_root)`, i.e. leaf attribution, with exact counts. Measured on head, the keys are:
     - `(mission_has_coordination_branch, _compose_primary_feature_dir)` 16
     - `(coord_read_dir_for, _compose_primary_feature_dir)` 14
     - `(_resolve_group_placement, _compose_primary_feature_dir)` 12
     - `(mission_has_coordination_branch, resolve_topology)` 2
     - `(ledger_posture, resolve_canonical_root)` 2
     - `(coord_read_dir_for, resolve_artifact_surface)` 1
     - `(coord_read_dir_for, resolve_topology)` 1
     - `(coord_read_dir_for, _primary_feature_dir)` 1
     - `(_resolve_group_placement, resolve_topology)` 1
   - After Finding 2, the `coord_read_dir_for` rows should disappear. Keep the explicit `_declared_dependencies` ban.

## Verified OK

- **`status/emit.py`:** the edit is additive and safe by default. `owned=None` keeps the legacy re-anchor, and with a fact the WP files are read from `owned.mission_dir`. It is declared.
- **`status_transition.py`:** the two call sites are declared (apart from Finding 1).
- **Lint:** ruff check and format are clean. C901 ≤ 15 in `emit.py` and `status_transition.py`.
- **Tests:** 899 passed, 2 skipped. The run covers:
  - the Test Strategy set;
  - `test_dependency_guard`, `status/test_emit*` and `coordination/test_status_transition*`;
  - `test_lifecycle_events`;
  - the create decomposition, owned-charter and checkout-restore tests;
  - the issue-matrix tests;
  - the architectural gate files;
  - `test_issue_4827` and `tests/tasks/test_finalize*`.
