---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T23:43:43Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP20
---

# WP20 review 1 - REJECT (reviewer-renata)

## Blocking

1. **Second landing path (flagged point 1).** `phase_teardown._land_topic_primary_before_teardown` writes topic-branch PRIMARY bytes into the repository root checkout and commits them through `_commit_projection_and_carry`, with its own `meta.json` key merge (`topic_primary_landing_bytes`, `_TARGET_AUTHORED_META_KEYS`). That is a parallel landing path beside `_phase_mission_to_target` / `integrate_mission_into_target`, and a second `meta.json` merge authority beside the #5460 two-way driver. The WP prompt (Context "One landing authority", T121, Risks, Review Guidance) says review rejects this. Fix: take the preferred route. Keep `unlanded_topic_primary_paths` as the pure check, and when it reports anything, refuse the coordination teardown through the existing `CoordinationTeardownError` / `PROJECTION_TEARDOWN_ABORTED` path (exit 1, triple kept, no new code). Remove `topic_primary_landing_bytes`, `_TARGET_AUTHORED_META_KEYS` merge-writing and the late write/commit. The other allowed route is a re-land through `integrate_mission_into_target` inside the recorded span; anything else is rejected.
2. **The Window B and orchestrator-api pins are not red-first (flagged point 2).** `test_primary_commit_after_landing_before_teardown_reaches_target_or_refuses` and `test_primary_landing_through_orchestrator_api` each accept two outcomes and passed on base 55fb46379a, so they prove nothing (C-011). Tighten Window B to the one outcome you choose in item 1 (refusal: exit 1, topic branch, worktree and marker kept, late commit still on the topic branch, target unchanged) and show it red on the lane base. Pin the orchestrator-api path to the one outcome it has today (state which, as a characterization pin, recorded as such).

## Rulings on the other flagged points
3. Out-of-map edits: `lands_topic_branch` in single_branch_landing.py (stored-meta keyed, `lands_mission_branch` unchanged), the post-landing re-anchor in phase_advance.py and the teardown hook in phase_teardown.py are within the recorded map; accepted. Resume base `state.pre_mutation_coord_sha` is accepted (it is the persisted pre-mutation anchor); keep a test that covers it after the rework.
4. Commit message misnames the predicate (`lanes_topic_branch`): note only, non-blocking.

## Non-blocking
- `_target_checkout_mission_dir` assumes the root checkout is on the target; add a one-line comment or assertion.
- Long single-line frozenset in bookkeeping_projection.py; check `ruff format`.

## Tests run (lane, 893dc2bbdd)
- tests/consolidation/test_topic_branch_primary_landing.py, test_projection_excludes_plan_outputs.py, test_single_rollback_authority.py: 44 passed.
- tests/architectural/test_no_dead_symbols.py -p no:xdist: 37 passed.
- Integration file not re-run: the rejection is a design defect independent of its result.
