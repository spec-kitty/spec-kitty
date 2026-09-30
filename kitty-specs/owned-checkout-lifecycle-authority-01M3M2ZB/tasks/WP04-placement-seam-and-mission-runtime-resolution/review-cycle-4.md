---
affected_files: []
cycle_number: 4
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T23:03:20Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback, cycle 4 (reviewer-renata)

**Verdict: CHANGES REQUESTED.** This round asks for test changes only. The production code is correct.

Commits reviewed: e81801bf7 (red-first) and 6ff8178b6 (fix).

## The S1 code fix is verified

- `_mission_context_for_owned` now builds every artifact by calling `_owned_read_dir_for_kind` and `_owned_commit_target_for_kind`. The duplicated rule and the memo closure are gone, and the docstring states the whole-context fail-closed contract honestly.
- **Independent probe.** I compared `mission_context_for(owned=)` with `resolve_artifact_surface` and `resolve_placement_only` over **all 4 topologies** × {materialized, empty, unmaterialized} × **all 18 kinds, RETROSPECTIVE included**. That is 216 cells, and **0 diverge**:
  - Wherever the whole context resolves, it matches both per-kind resolvers.
  - Wherever it refuses (coord and lanes_with_coord, each EMPTY and UNMATERIALIZED), PRIMARY kinds still resolve per kind, and every COORD kind refuses per kind with the same `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.

## Blocking: the agreement test does not pin what the code already does

The grid `test_mission_context_for_owned_agrees_with_the_per_kind_resolvers` falls short in four ways:

1. **`coord` topology is omitted with no reason, and none exists.**
   - The test mints the fact with `OwnedCheckout._mint(topology=...)`, so the minter is not involved. `_lanes_with_coord_repo` already declares `coordination_branch`.
   - My probe produced every `coord` cell with the same fixture just by passing `MissionTopology.COORD`.
   - `coord` is the second coordination-routing topology, and it is half of the refusal cells. **Add it to the parametrisation.**
2. **The RETROSPECTIVE skip has no stated reason, and the kind passes.**
   - `resolve_artifact_surface`, `resolve_placement_only` and `mission_context_for` all agree for RETROSPECTIVE; only `PlacementSeam.read_dir` routes it specially.
   - **Include it,** or, if you keep the skip, state that reason in a comment and add a separate assertion for `PlacementSeam.read_dir(RETROSPECTIVE)` under `owned.owned_root`.
3. **The refusal branch checks only PRIMARY kinds.** When the whole context refuses, also assert the other half of "raise the documented code consistently": for a COORD-partition kind, `resolve_artifact_surface(..., kind, owned=fact)` raises `ActionContextError` with `OwnedRefusalCode.OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`.
4. **The coordination state is never applied to non-coordination topologies.**
   - The `empty` and `unmaterialized` mutations run only when `topology is LANES_WITH_COORD`.
   - For single_branch and lanes, all three `coord_state` cells therefore run the identical materialised fixture, and the docstring's claim that they "resolve regardless of coord_state" is untested.
   - **Apply the mutation for every topology.**

After these edits the grid is 4 topologies × 3 states × 18 kinds. The code already passes all of it, so no src change is expected.

## Verified (no action)

- **Red-first:** at e81801bf7 exactly one test is red, the spy test `test_mission_context_for_owned_calls_the_per_kind_helpers` (1 failed, 154 passed).
- **The resolver test is non-vacuous now:** against the c220d467d source it fails with `resolver.resolve('01M3PACE') must not be called`.
- **Markers:** 16 in resolution.py and 1 in support.py, 17 in total, matching the DoD.
- **mypy:** one `--strict --explicit-package-bases` invocation over 100 files (seams, every caller, callees) gives 49 errors on base 2a61b0e3b and 49 on head. The error lists are byte-identical.
- **Hygiene:** the lane tree is clean and the stash stack is empty.
- **Tests and lint:** targeted tests pass (608), and `ruff check` is clean.
