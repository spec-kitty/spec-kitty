---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T16:59:13Z'
reviewer_agent: claude
wp_id: WP05
---

# WP05 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata, opus). Lane-a tip reviewed: `8b6546924a`. Base: the WP04 tip `0c056d2da1`.

## What already passes

- **Red-first is verified.**
  - R12 is red at `ef723697a4`: the target advanced from `554362…` to `e7052d…`. It is green at `b9f70c5753`.
  - R2 is red at `620cdb417d` and at `e28e54a4d1`, with `status='unchanged' reason='no_op_already_committed'`. R2b is green.
  - R12 carries the `merge-base --is-ancestor` non-vacuity precondition (FR-008).
- **FR-006, "commit is the required outcome"**: R2 calls `pytest.fail` on any non-`committed` result for the standard fixture, so a router that always refuses fails R2.
- **FR-007 masking**: `test_mixed_batch_error_on_one_group_still_carries_both_surfaces` and `test_mixed_batch_populates_surfaces_primary_then_coordination` pin both surfaces. `_merge_group_results` attaches the union on every return path, including the error early-return.
- **`_try_advance_ref`**: gone, with no remaining references.
- **Commit `55c99766d9`**: `tests/specify_cli/coordination/test_commit_router_partition.py` is byte-identical to the base (empty diff).
- **Commit `8b6546924a`** (the anchor-helper tests): it keeps each test's intent honest. `for_write=True` is the probe-free arm. The new `test_probes_git_only_when_not_for_write` states the real I/O boundary, and the read-path pre-fix quiet case is still pinned against a real repo by WP04's `test_pre_fix_coord_stays_quiet`. Accepted. (The regression was my own WP04 review miss: I did not run `test_surface_resolver_anchor_helpers.py`.)
- **Static checks**: ruff, format, C901, RUF100 and mypy --strict are clean.
- **Diff coverage**: 94.0% on changed source lines (commit_router 148/163, commit_outcome 81/81, surface_authority 6/6).
- **`surface_authority._exit_code_for` not rewired**: accepted. It maps the static `NonCommittable` verdict, which is disjoint from `SurfaceOutcome`. The literals now have one owner and the polarity matches.
- **`owned` not threaded into `_materialise_coord_worktree`**: accepted as inert. The real reason is `use_coord = owned is None and …` in `_resolve_group_placement`, so an owned call can never reach coordination staging. Fix the comment, though (see L1).
- **`CoordSeedForkRefused`**: cured by a real production importer (`commit_outcome` and `commit_router`).

## Blocking

**B1 (HIGH, data loss / regression in green guards): "owning copy wins" for non-log COORD kinds drops writes from writers that have not migrated yet.**
- `_act_on_stage_plan`'s translate-if-present arm (`TRACER_FILE` / `REVIEW_CYCLE` / `ISSUE_MATRIX` / `ACCEPTANCE_MATRIX`) uses the existing coordination copy and never copies the newer root copy over it.
- No writer has migrated yet: WP08, WP10 and WP15 come later. Today's writers still write the root copy, so their updates never reach the commit. The legacy status is `unchanged` (exit 0), and only `surfaces` says `COORD_RECORD_IN_ROOT_CHECKOUT`. `_log_split_commit_outcome` logs that at DEBUG, and only for split batches.
- Four guards that are green at the base `0c056d2da1` turn red at the tip. Bisected to `8ffa7cc96a`; it is green at `e28e54a4d1`.
  - `tests/integration/test_accept_matrix_coord_partition.py::test_matrix_lands_on_coord_via_all_three_write_paths_no_stale_copy`. The finalize acceptance-matrix update is lost: `T011_SPEC_COMMIT_MARKER` is seen instead of `T012_FINALIZE_MARKER`.
  - `tests/integration/test_issue_verdict_coord_legacy_md_preservation.py::test_coord_legacy_md_verdict_is_preserved_when_recording_a_new_issue`. Issue-verdict row `#B` is dropped.
  - `tests/integration/test_issue_verdict_coord_legacy_md_preservation.py::test_second_verdict_after_migration_preserves_all_rows_no_primary_residue`. Rows `#B` and `#C` are dropped.
  - `tests/integration/test_issue_verdict_selfmat_hardening.py::test_materialized_coord_verdicts_succeed`. Row `#4444` is dropped.
- **Required:** WP05 must not apply contract rule 3 ("coordination copy wins; root-dirty is skipped") to a non-log COORD kind before that kind's writer writes in place. Pick one of these and record the choice in `design-decisions`:
  - **(a)** Keep the legacy `shutil.copy2` overwrite for the four non-log kinds. Move the "owning copy wins" switch to the WP that migrates each kind's writer: WP08 (review-cycle), WP10 (tracer, issue-matrix) and WP15 (finalize, acceptance-matrix). This is the simplest option.
  - **(b)** Decide by which side is dirty. A dirty root with a clean coordination copy means the legacy writer is authoritative: copy. A dirty coordination copy means an in-place writer: the coordination copy wins. Both dirty: refuse with a named reason. Never pick silently.

  Either way, all four tests above must be green at the tip. Add them to WP05's test surface by name; they are targeted files, not the integration directory.
- **Also the seed:** the absent-copy fallback (`copy2` into an EMPTY coordination surface) creates the Mission dir without the WP03 seed. The state then becomes MATERIALIZED and root-only status records are never carried.
  - This existed before WP05, but now that a seed exists the router should not pre-empt it.
  - If you touch this arm: when the coordination Mission dir is absent, establish it through `write_dir` first, then apply the copy rule.
  - At minimum, record it as a follow-up for WP08/WP10.

**B2 (MEDIUM): tests the prompt and binding corrections require are missing. The uncovered new lines are exactly these branches.**
1. **T029 "one test per reason", each asserting `surfaces[*].refused[*].reason` and `commit_outcome_exit_code(result) == 1`:**
   - `WRONG_SURFACE` through `_classify_no_commit_paths`' B16 arm. Lines 516-523 are uncovered and `_paths_uncommitted_in_primary` (L1875) never runs in the coordination suites. `test_commit_router_fail_loud.py:359` asserts only the legacy status.
   - `PROTECTED_BRANCH_REFUSED` on the refusal arm of `_commit_partition_group`.
   - `COORDINATION_WORKTREE_UNMATERIALIZED` and `COORD_SEED_FORK_REFUSED` through `_resolve_owning_write_dir` (L1438 and L1445 are uncovered).
   - The Mission-relative `PATH_UNROUTABLE` arm (L1479).
2. **T028:** one end-to-end test per COORD kind through `commit_for_mission`, covering three cases: dirty owning copy → committed; clean owning copy plus dirty root → `COORD_RECORD_IN_ROOT_CHECKOUT` with the target-branch tip unchanged; both clean → unchanged. Only helper-level refine tests exist today.
3. **Binding "Recursion":** a test proving the WP03 seed's own `commit_for_mission` call (in-worktree paths, so it takes `IN_PLACE`) never re-enters `write_dir`. For example, a pre-fix EMPTY Mission whose first STATUS_STATE commit through the router seeds exactly once.

**B3 (governance): the transitional dead-symbol red now includes `partition_for_mission_path`.**
- Both the gate and its companion are red on exactly 2 names, `commit_router::partition_for_mission_path` and `coord_seed::COORD_SEED_TRAILER`:
  - `tests/architectural/test_no_dead_symbols.py::test_no_public_symbol_in_all_is_unimported`
  - `tests/architectural/test_dead_symbol_allowlist_contract.py::test_m11_gate_reads_the_allowlist_file_it_is_given`
- The binding correction assumed the predicate would be live through the router's own grouping. It is not: an `__all__` member needs a cross-module caller, and WP16, the curer, is about ten WPs away.
- Ruling:
  - Do **not** grow the allowlist.
  - **Preferred:** take the gate's own sanctioned option 2. Remove `partition_for_mission_path` from `__all__`; it keeps its intra-module reference. Confirm the gate goes green, and WP16 re-exports it when it imports it.
  - **Otherwise:** keep the red and record it in the activity log, with WP16 named as the curer and both companion tests listed.

## Non-blocking

- **L1:** the comment on the `_materialise_coord_worktree` call cites `LIFECYCLE_OWNED_TOPOLOGIES == {SINGLE_BRANCH}`. `NEXT_OWNED_TOPOLOGIES` includes `LANES_WITH_COORD`; the real guarantee is the `use_coord = owned is None and …` gate. State that instead, along with the "fixture stubs" convenience it currently gives.
- **L2:** `partition_for_mission_path(repo_root, mission_slug, path, *, owned)` deletes two unused parameters, and its verdict is topology-blind. WP16 must not treat it as a topology-aware dirty-gate verdict (the docstring already says so). Consider dropping the unused parameters before the first external caller pins the signature.
- **L3:** `render_commit_outcome` returns `✓`/`✗` in its strings. The binding asks for rich or an ASCII fallback on cp1252 consoles. That is fine as a pure function, but every consumer WP must print through rich or the ASCII fallback (see the notes for consumers below).
- **L4 (not WP05's to fix; please route it):** `tests/integration/test_issue_verdict_selfmat_hardening.py::test_second_verdict_from_stale_coord_preserves_committed_rows` is red since WP03's `1da5a87eaa`.
  - Bisected: green at `c833721eb3` and `0582d178a8`; red at `1da5a87eaa`, `d34a493663` and `40dd711620`. The failure is `DID NOT RAISE IssueVerdictError`.
  - It pins the stale-local-head refusal that research D22 deliberately removed. It needs the D22 re-pin: self-materialize, and the committed rows are preserved.
  - My WP03 review missed it (I did not run integration). Assign it to WP03 or to the issue-verdict owner (WP10) for a deliberate re-pin.

## Tests run by the reviewer (tip `8b6546924a`, `-n 4 --dist loadfile`)

| Suite | Result |
|---|---|
| `tests/coordination/` (whole directory) | **403 passed**, 0 failed (collection confirms 403; the earlier "847" was not this directory) |
| `tests/specify_cli/coordination/` + finalize_coord_staging, finalize_clobber_e2e, wp06_sc2_paused_mission_blockers, mission_shim_reexports, test_commit_to_target_scope_guards | 540 passed, 10 skipped |
| `test_analysis_report_rehome.py` | included in the `tests/coordination/` run (it lives there) |
| Named gates: layer_rules, write_surface_placement_guard, no_write_side_rederivation, no_dead_symbols, guard_capability_call_sites, dead_symbol_allowlist_contract, no_dead_modules | 165 passed, 2 failed (the B3 transitional red pair) |
| B16 consumers: test_issue_2739 guard, review/test_cycle, mission_planning_entry, protected_primary_spec_commit, accept_matrix_coord_partition | 82 passed, 1 skipped, 1 failed (B1) |
| Targeted integration, review and terminus (19 integration files + `tests/review` + `tests/terminus`) | tip: 830 passed, 4 failed; base `0c056d2da1`: 833 passed, 1 failed. Delta: the 3 B1 regressions; the shared failure is L4 |
