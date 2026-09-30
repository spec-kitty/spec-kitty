---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T17:21:01Z'
reviewer_agent: claude
wp_id: WP19
---

# WP19 review, cycle 2: REJECT (one blocking item, small)

Reviewer: reviewer-renata. Lane-r at 27d13af04; new commits fe725c52a, b1a9075ca, 27d13af04.

## Blocking

### [MEDIUM] src/mission_runtime/resolution.py:1520: the fail-closed boundary of `tolerate_unmaterialized_coord` is unpinned
The code is right. With the flag set, the arm tolerates only `CoordState.UNMATERIALIZED`, and EMPTY, NONE and DELETED still refuse. No test holds that boundary, though.

**Mutation evidence.** I changed the guard to `if tolerate_unmaterialized_coord:`, which returns `coord_dir` for EMPTY and NONE too. All 384 tests still passed, with 1 xfailed. The suite was the mission_runtime owned tests, the coordination owned tests, test_owned_next_runtime (WP11's O8 rows), both acceptance files, and the acceptance-context file.

**Why it matters.** EMPTY is #1716's "never silently substitute" condition. Under that mutation, `_dn_bootstrap` (runtime_bridge.py ~1712) would receive a coord `status_dir` that is not a directory. It would then fall back to `primary_metadata_dir`. That is exactly the silent substitution this seam exists to refuse, and nothing would catch it.

**Required fix.** Add a test commit, red against the mutation above, in `tests/mission_runtime/test_placement_seam_owned.py`, next to `test_unmaterialized_coord_fails_closed_never_a_predicted_path` (:424). It should call `mission_context_for(..., owned=fact, tolerate_unmaterialized_coord=True)` or `_resolve_status_surface_dir(..., tolerate_unmaterialized_coord=True)` and pin these cases:
- **UNMATERIALIZED + flag:** returns the declared coord candidate under `fact.repository_root/.worktrees/...`. It is neither P nor `fact.mission_dir`.
- **EMPTY + flag** (the coord worktree exists, but the mission dir is missing inside it): raises `ActionContextError` with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
- **NONE + flag** (no mid8 or coordination signal): raises the same typed refusal.
- **DELETED + flag:** raises `CoordinationBranchDeleted`.

Parametrize the cases where you can. The UNMATERIALIZED case also gives the new branch its first unit-level coverage, since today only the integration twin reaches it.

## Non-blocking (LOW)
- **Simplify: 3 flagged sites only need the PRIMARY dir.** The sites are `next_invocation_lifecycle.pair_previous_lifecycle_record` / `write_issuance_lifecycle_record` (PRIMARY_METADATA only) and `runtime_bridge._mission_routes_through_coordination` (PRIMARY_METADATA only). They could read `owned.mission_dir` directly, the way `committed_authority.primary_surface_dir` and `_run_mission_id` now do. Then they would need no flag.
  - `write_issuance_lifecycle_record` is a write site that passes the flag. The flag's own docstring says "a caller that WRITES to the surface must not". It does no harm here, because the site only uses PRIMARY_METADATA, but it contradicts the stated rule.
  - The flag remains genuinely needed at `_query_resolve_mission_context`, `_dn_bootstrap`, `_build_finalized_override_query_decision`, `_wrap_with_decision_git_log` (whole context) and `emit_mission_next_invoked` (STATUS_STATE; its `is_dir()` guard keeps the write off the absent path).
- **resolution.py:1470-1483 and :1524-1529:** the `_resolve_status_surface_dir_owned` docstring and the trailing comment still say UNMATERIALIZED "fails closed". Qualify both with "unless `tolerate_unmaterialized_coord`".
- **Red-first:** the FR-022 advance leg (`test_advance_after_create_materialises_the_coordination_worktree_and_is_not_an_error`) landed with the fix in b1a9075ca. I verified it is red on the pre-fix tree (fe725c52a src: `error_code: OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`). The same FR-022 row already had a red-first query leg in fe725c52a, so I accept this. Next time, put every leg in the red commit.
- **owned_mission.py:367:** with `discover_sole`, the sole-mission listing of P runs after the claim check, which is correct. It also runs before `_require_not_mission_worktree`, though. When there is no handle, that check cannot run first. Document the ordering in the docstring.

## Verified OK
- **Red-first.** On a scratch detached worktree of fe725c52a, `TestFr022CoordinationTwin::test_next_after_create_is_a_non_error_decision` and `TestHandlelessOwnedNext::test_sole_mission_is_discovered_in_p_and_never_in_r` both fail (2 failed, 3 passed).
- **Flag mutations.**
  - **Flag defaulted to True everywhere** (5 defaults): `test_placement_seam_owned.py::test_unmaterialized_coord_fails_closed_never_a_predicted_path` goes red.
  - **Flag dropped at `_query_resolve_mission_context`:** `test_next_after_create_is_a_non_error_decision` goes red.
  - **Flag dropped at `_dn_bootstrap`:** `test_advance_after_create_…` goes red.
- **No write reaches an absent coord path, and nothing falls through to R.**
  - `emit_mission_next_invoked` passes `feature_dir` only when it is a directory.
  - The lifecycle and routes sites use PRIMARY (P).
  - `_wrap_with_decision_git_log` materialises the worktree before it resolves the worktree root.
  - `_dn_bootstrap`'s status_dir-or-primary choice is byte-identical to the merge-base 9b524be7d legacy arm, so FR-022 parity is restored.
  - The flag is a clean narrowing parameter on WP04's seam, not a second authority.
- **Single validation.**
  - The handle-less path runs `resolve_owned_mission(discover_sole=True)`: one `_require_owned_claim`, then `OwnedMissionSelectionRequired`.
  - `_discover_owned_handle` is deleted, and so is its second path composer.
  - Mutation: adding a second `_require_owned_claim` makes `test_sole_mission_is_discovered_in_p_and_never_in_r` go red.
- **LOW fixes from cycle 1 are done.**
  - `mission_create.py:507` and `test_agent_feature.py:698` are re-pointed to `emit_owned_refusal`.
  - `test_next_answer_effective_root.py:129` poisons `next_cmd.get_main_repo_root`.
  - The out-of-map lists are complete in the b1a9075ca and 27d13af04 bodies, and each edit is minimal.
- **xfails:** only 2 remain. Both are `strict=True` and owned by WP12: `test_owned_lifecycle_acceptance_next.py:257` (T068) and `test_explicit_checkout_commands.py:309` (T069).
- **Markers:** `TRANSITIONAL(WP18)` in next_cmd = 0, and no new markers were added. No new `noqa` or `type: ignore`.
- **ruff:** check and C901 at 15 are clean. `format --check` is clean except `tests/agent/test_agent_feature.py`, which is in the repo's format-exclude list (`--force-exclude` is clean).
- **mypy** `--strict --explicit-package-bases` over 11 files (next_cmd, _owned_checkout, owned_mission, mission_create, decision, runtime_bridge, runtime_bridge_io, committed_authority, next_invocation_lifecycle, resolution, owned_checkout): 20 errors on base fa3b70961 and 20 on head 27d13af04, identical. All 20 are pre-existing, in runtime_bridge_engine.py and _internal_runtime/engine.py.
- **`test_no_dead_symbols` failure is pre-existing mission debt, not WP19's.** It lists 10 symbols from WP01, WP02 and WP08 (`_owned_checkout.*`, `OwnedMission`, `OwnedCheckoutPathRefused`). The same list is red on the WP19 base fa3b70961.
