---
affected_files: []
cycle_number: 3
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T22:40:10Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04 review feedback, cycle 3 (reviewer-renata)

**Verdict: CHANGES REQUESTED.** Commits reviewed: 5ba2888e8 (red pins) and 66bfb2855 (fix).

One blocking item remains: two resolution paths on the owned arm, which disagree. Everything else from cycle 2 is verified fixed.

## Blocking

### S1: `_mission_context_for_owned` is a second per-kind resolution path, and it diverges from `_owned_read_dir_for_kind` / `_owned_commit_target_for_kind`

- **Duplicated rule.** The per-kind rule exists twice:
  - the loop body of `_mission_context_for_owned` (primary kind → `owned.mission_dir` / `CommitTarget(target_branch)`, else status surface / coordination ref);
  - `_owned_read_dir_for_kind` together with `_owned_commit_target_for_kind`.

  Both are copies of the same rule, including the duplicated `coord_ref = coordination_branch if routes_through_coordination(...) ...` expression. Only the per-kind pair routes `resolve_artifact_surface` and `resolve_placement_only`. That violates single canonical authority.
- **Probe of divergence.** I compared `mission_context_for(R, slug, owned=fact).artifact(k)` with `resolve_artifact_surface(..., k, owned=fact)` and `resolve_placement_only(..., kind=k, owned=fact)` for every kind, across topology {single_branch, lanes, coord, lanes_with_coord} × coordination state {materialized, empty, unmaterialized}.
  - **Where they agree:** everywhere except the coordination-topology EMPTY and UNMATERIALIZED cells.
  - **Where they diverge:** in those 4 cells (coord and lanes_with_coord, each EMPTY and UNMATERIALIZED), `mission_context_for(owned=)` raises `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE` for **all 17 kinds**, SPEC included. The per-kind helpers return `owned.mission_dir` for SPEC (row 3).
- **The laziness claim is false.** The docstring and commit say the status surface is resolved "lazily … and only when a non-primary kind actually needs it". The loop iterates every `MissionArtifactKind`, so it always reaches a COORD kind and always resolves the surface. The laziness never takes effect.
- **Knock-on effect.** In that window, `resolve_action_context(owned=)` fails for every action, including `plan` and `tasks_outline` (probe: `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`).
  - I accept failing closed for a *whole-context* request, since the context carries a status-surface fragment. IC-05 maps this code to a `blocked` decision for `next`.
  - But it must be the stated contract, and it must come from the same per-kind rule. Two copies that happen to agree only when the worktree is materialised are not acceptable.

**Required:**

1. `_mission_context_for_owned` builds every `MissionArtifactContext` by calling `_owned_read_dir_for_kind` and `_owned_commit_target_for_kind`. There must be exactly one per-kind rule. Delete the inline loop logic and the duplicated `coord_ref` expression.
2. Whole-context contract: rewrite the docstring to state it truthfully. A whole-context build for a coordination topology whose worktree is not MATERIALIZED fails closed with `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`, because it must resolve the COORD kinds. Single-kind callers (`resolve_artifact_surface` / `resolve_placement_only`) still get row 3 for PRIMARY kinds. Remove the "lazy / only when needed" wording and the memo closure, unless it has a real effect.
3. Add a parametrised agreement test in `test_placement_seam_owned.py`, over topology {single_branch, lanes, lanes_with_coord} × state {materialized, empty, unmaterialized} × every kind (skip RETROSPECTIVE). Assert:
   - whenever `mission_context_for(owned=)` resolves, its `read_dir` equals `resolve_artifact_surface(...).path` and its `commit_target` equals `resolve_placement_only(...)`;
   - when it refuses, the refusal code is `OWNED_COORDINATION_WORKSPACE_UNAVAILABLE`, and the PRIMARY kinds still resolve per kind.

   The `_lanes_with_coord_repo` builder plus a `meta.json` topology rewrite is enough to produce every cell. My probe did exactly that.

## Verified fixed (no action)

- **R1:** the pins raise, not merely count. `get_main_repo_root`, `candidate_feature_dir_for_mission`, `resolve_handle_to_read_path` and `subprocess.run` are all patched to raise AssertionError. They are non-vacuous: run against the cycle-1 src (c220d467d), 6 of the 7 R1 pins fail.
  - Non-blocking: `test_owned_resolver_never_consulted` passes on the cycle-1 src too. With the exact slug on disk, the legacy walk never called the resolver. Pass the mid8 handle so the old walk would have consulted it.
- **R2:** EMPTY, UNMATERIALIZED and NONE fail closed for COORD-partition kinds only, per kind. MATERIALIZED resolves under `R/.worktrees/<slug>-coord`. Placement never probes coordination state.
- **F3:** the stamp is COORD if and only if `routes_through_coordination(owned.topology)` holds and the kind is not primary. It no longer uses path equality. All 4 T019 rows are tested, plus the row-3 UNMATERIALIZED case and the row-4 EMPTY case.
- **R3/F4:** `mission_runtime.identity.handle_names_mission` is the only matcher. The private copies are gone from resolution.py and support.py.
  - It accepts exact forms only: the slug, an 8-character Crockford mid8, or a 26-character ULID whose first 8 characters are the mid8.
  - The negative test for `<mid8>-something-else` exists.
  - It is exported in `mission_runtime.__all__` and registered in `test_mission_runtime_surface.py`.
  - Non-blocking: a direct unit test of `handle_names_mission` in the identity tests (case-insensitivity, a 26-character non-ULID, an all-digit handle) would pin the public predicate itself.
- **R4/F5:**
  - `mission_finalize.py:3353` now passes `owned=owned`. Its `# bridging: WP13 converts` marker is correct, because the first argument still uses the legacy `owned.primary` property.
  - The 3 mislabelled `tasks_move_task.py` markers were dropped.
  - The out-of-map edit is declared in the commit body.
  - mypy: one `--strict --explicit-package-bases` invocation over 96 files (seams, every caller, callees) gives 48 errors on base 2a61b0e3b and 48 on head. The error lists are byte-identical, so there are 0 new errors.
- **R5:** `grep TRANSITIONAL(WP18)` finds 16 in resolution.py and 1 in support.py, 17 in total, matching the amended DoD, including `_refuse_both`.
  - Non-blocking: the commit body says "17 in resolution.py + 1 in support.py = 18". That is wrong; the tree has 16 + 1 = 17. Correct it in the Activity Log.
- **Red-first:** at 5ba2888e8, 3 pins are red: row 3 UNMATERIALIZED, row 4 EMPTY, and the prefix-match test. All are green at the tip.
- **Hygiene:** the tree is clean and the stash stack is empty.
- **Tests:** targeted tests pass (485). `ruff check` is clean and C901 ≤ 11 holds.
