---
affected_files: []
cycle_number: 3
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-02T05:52:29Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review — cycle 3 (reviewer-renata) — CHANGES REQUESTED (2 narrow items)

The design is correct and verified. Decision `plan.design.undeclared-coord-branch` is implemented faithfully: probes, real-CLI proof and 6 of 7 mutants all pass.
Two narrow items block. Both are small, with no redesign.

## C3-B1 (BLOCKING): new architectural-gate regression — raw `KITTY_SPECS_DIR` join in `transaction.py`

`tests/architectural/test_single_mission_surface_resolver.py::test_zero_functional_raw_bypass_on_collapsed_tree` is **red**. It was introduced by `aec27a6a74`, and CI's cross-cutting lane runs this gate:

```
specify_cli/coordination/transaction.py:166  key=('_canonical_coord_mission_slug',
  'if ( seam_repo_root / KITTY_SPECS_DIR / mission_slug / ) . exists ( ) :')
  — functional raw-bypass not in allowlist (FR-004 regression)
```

The intent is right: check the LITERAL dir, bypassing `read_primary_meta`'s bare-slug fold. M6 confirms the check is load-bearing: reverting it to `read_primary_meta(...)[1]` reds `tests/coordination/test_status_transition_write_dir.py::test_commit_idempotent_no_ops_when_the_seed_already_committed_everything`.

**Fix — preferred:** compose the literal primary dir through the sanctioned handle-blind primitive instead of a raw join:

- `primary_feature_dir_for_mission(seam_repo_root, mission_slug)`, or the module's `_compose_primary_feature_dir`, which `read_primary_meta` itself uses for exactly this literal compose;
- then test `/ "meta.json"`.

It is still literal, because neither primitive folds the handle.

**Fallback (prefer the primitive):** only add a `_ALLOWLISTED_RAW_JOINS` TBYD entry with a named rationale if no sanctioned literal composer fits.

**Re-run:** `test_single_mission_surface_resolver.py` plus `test_status_transition_write_dir.py`.

## C3-B2 (BLOCKING): surviving mutant on the topology gate — the `owned.topology` clause is unpinned

In `coord_seed.py::_stored_topology_routes_through_coordination`, mutant **M2** replaces the last line with `return False`:

```python
return owned is not None and routes_through_coordination(owned.topology)
```

M2 **SURVIVES** every relevant file:

- `test_coord_seed.py`
- `test_materialize_coord_surface.py`
- `test_decision_git_log_write_dir.py`
- `test_decision_write_location_refusals.py`
- `test_transaction.py`
- the read-path handle tests
- `test_service_coord_single_home.py`
- `test_status_transition_write_dir.py`
- `tests/integration/test_owned_next_runtime.py`

That is 149 + 59 tests, all green under the mutant.

The clause is reachable and load-bearing. Its own docstring cites the O8 shape. My probe used an owned fact with `topology=COORD`, the root `meta.json` stripped of `coordination_branch` (topology kept), and the derived branch present:

| owned meta copy | HEAD | under M2 |
|---|---|---|
| **missing** (`meta.json` deleted in the owned checkout) | coordination | **primary** |
| present but **topology-less** | coordination | **primary** |

So the one clause that stops an owned Mission from degrading to PRIMARY (the exact fail-open your Decision forbids) has no test.

**Fix:** add a red-first parametrised test in `tests/coordination/test_coord_seed.py` covering both rows above.

- Assert `surface == coordination`.
- Optionally add the absent-branch twin: owned meta missing + derived branch deleted → `CoordBranchUndeclaredAndAbsent`.
- Demonstrate red under M2 (`return False`).

Reference probe source: `scratchpad/owned_probe.py`. It uses `make_prefix_coord_mission(..., worktree="empty")`, plus `git worktree add` for the owned checkout, plus `mint_test_fact(..., topology=COORD)`.

## Verified (no action)

**Probe matrix:** owned and non-owned × coord and lanes_with_coord, with `coordination_branch` stripped.

| case | result |
|---|---|
| undeclared, branch exists | **coordination** |
| undeclared, branch exists, worktree unmaterialized | **coordination** (materialized via the identity pass-through) |
| undeclared, branch absent | **`CoordBranchUndeclaredAndAbsent` / `COORD_BRANCH_UNDECLARED_AND_ABSENT`** |
| legacy (no topology; owned fact coord-less) | **PRIMARY** |

All 16 cells are correct.

**Mutants killed (6 of 7):**

| mutant | result |
|---|---|
| M1 gate → `False` | 9 failed |
| M3 gate → `True` | 3 failed (coord-less and legacy controls) |
| M4 drop the `materialize_coord_surface_for_write` identity pass-through | 2 failed |
| M5 drop the bridge surface check | 1 failed (now matches "resolved a PRIMARY surface") |
| M6 transaction literal → `read_primary_meta` | 1 failed (in `test_status_transition_write_dir.py`) |
| M7 `read_primary_meta` without the bare fold | 3 failed |
| M8 derived-branch existence check off | 4 failed |

**`ae8a2455ab` — judged a legitimate pass-through, not a second identity input:**

- The only caller passing the override is `coord_seed._materialize_for_write`, with the identity `establish_coord_write_location` resolved once (declared, or derived via `lanes.branch_naming.coord_reconstruct_branch`).
- The seam stops re-deriving when it is given that identity.
- The doctor `--fix` caller is unchanged.
- M4 proves it load-bearing.
- **Nit:** the docstring says "passing one without the other is a caller error", but only branch-without-mid8 raises; `mid8` alone is silently overwritten. Either raise on both, or reword.

**`fa7977928a` (`read_primary_meta` bare-slug fold) — correct, and its blast radius is bounded:**

- It changes only the raw-miss path (`if not meta`), so a composed or literal hit is byte-identical.
- It routes through the ONE shared `_canonicalize_primary_read_handle` (bare-modern fold first, identity cascade second), which is a superset of the old `_canonicalize_handle`-only path.
- `MissionSelectorAmbiguous` still propagates.
- Gates are green: `test_no_read_side_bypass` (38), `test_status_state_read_dir_single_authority` (13), `test_coord_read_residuals_closeout` (11), `test_trio_seam_only` (14).
- The read-path resolver test files are green; see the counts in the handback.

**`1f02eeac7a` (scaffold rewrite) — a legitimate fixture correction, not masking a regression.**

I built a REAL COORD Mission through the CLI core (`_build_golden_mission` → `create_mission_core` + setup-plan + WP01/lanes), then ran a real `move-task WP01 --to claimed`, with **no hand-seeding of the coordination log**. For both a bare and a canonical handle:

- `write_dir(DECISION_LOG)` gives the coordination surface;
- `_wrap_with_decision_git_log` gives a `DecisionGitLog` on `.worktrees/<slug>-<mid8>-coord/kitty-specs/<slug>-<mid8>/`;
- `decision open --mission <handle>` exits 0.

The fork refusal is never reached. The old fixture hand-wrote sentinel-only coordination logs with no root prefix; the real seed carries the root prefix, which the new fixture now mirrors.

**Other checks:**

- `6b2276b14c`: the refusal is rendered on all four decision verbs, with `NoReturn` and a `next_step`.
- `727752c0ed` / `9ed941336e`: the defence-in-depth surface check is real (M5 is killed). The test's fake seam now delegates `read_dir` to the real seam, so the false-positive pass is gone.
- `mypy --strict` on the touched `src` files: 0 new errors vs `7afabf4eff` (24 pre-existing lines, identical).
- `ruff check` is clean.
- `ruff format --check --force-exclude` is clean. The 10 "would reformat" files are on the exclude list, and the ratchet is green.
- No `pragma: no cover` in the diff.
- New suppressions are test-only:
  - `# noqa: ARG002` on fakes;
  - one `# type: ignore[arg-type]` in `test_decision_git_log_write_dir.py`'s delegating fake. It is narrow, but give it an inline rationale.

## Cycle-4 scope

Fix C3-B1 and C3-B2 only. Then re-run:

- `tests/architectural/test_single_mission_surface_resolver.py`
- `tests/coordination/test_coord_seed.py`
- `tests/coordination/test_status_transition_write_dir.py`
- `tests/specify_cli/coordination/test_transaction.py`

Re-verify by re-running the M2 mutant. Nothing else needs re-review.

## C3-N1 (non-blocking, recommended in the same cycle): pin the N2 chained code through the new refusal

`runtime_bridge.py:482-483` (N2 `typed_code` / `code_suffix`) is uncovered by the targeted set. It is reachable precisely through this cycle's new refusal:

- a non-owned `_wrap_with_decision_git_log` on a coord-routed Mission with undeclared + absent branch;
- `write_dir` raises `CoordBranchUndeclaredAndAbsent`;
- the bridge should then raise `DecisionGitLogUnavailable` with message `... (COORD_BRANCH_UNDECLARED_AND_ABSENT) ...`.

One test in `tests/runtime/test_decision_git_log_write_dir.py` covers both lines, and it proves the operator-visible code survives the fold.

## Evidence (cycle 3, targeted only, -n 3 --dist loadfile)
- Touched-module + read-path resolver + decision CLI + callers of read_primary_meta (31 named files): 529 passed, 1 skipped.
- Named integration: test_owned_next_runtime.py (O8) + test_placement_partition_golden_path.py + scaffold consumers (test_next_board_authority.py, test_wp_prompt_task_placement.py): 75 passed.
- test_owned_arm_translates_workspace_failure: green (in test_coord_seed.py).
- Named arch gates (16, individually): all green EXCEPT
  - test_single_mission_surface_resolver::test_zero_functional_raw_bypass_on_collapsed_tree — NEW red, C3-B1;
  - test_no_dead_symbols + test_dead_symbol_allowlist_contract — ONLY the known OD-DEAD `coord_seed::COORD_SEED_TRAILER` (transitional, WP17); the new `CoordBranchUndeclaredAndAbsent` is not flagged.
- Diff coverage vs 7afabf4eff (targeted set): 130/132 (98.5%); missing runtime_bridge.py:482-483 (C3-N1).
