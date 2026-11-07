---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T15:09:34Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP13
---

# WP13 review, cycle 1 (reviewer-renata): REJECT

The behaviour is sound. Default create mints one topic branch on both targets, explicit `--topology` is unchanged, FR-060 holds, the JSON fields match the contract, the golden diffs are intended, and the #5676 refusals keep the operator's work. The rejection is for the dead-code gate, plus two smaller fixes.

## Blocking

### B1. `tests/architectural/test_no_dead_symbols.py` is red on WP13 symbols
Command: `PYTHONPATH=$PWD/src python -m pytest -p no:xdist tests/architectural/test_no_dead_symbols.py`. Result: 2 failed, 35 passed (`test_no_public_symbol_in_all_is_unimported`, `test_m11c_gate_reads_the_widened_section_it_is_given`). The WP13 symbols with no src caller:
- `specify_cli.coordination.surface_authority::coord_topology_reachable`. WP13 removed its only caller (`_resolve_default_topology_phase`, the dropped `--pr-bound` fallback, DM 01M6R0QQM5FCPY736008AD4W6V). **Delete it**, with its `__all__` entry and its tests.
- `specify_cli.lanes.compute_and_persist::count_code_lanes`, needed by WP14.
- `specify_cli.mission_metadata::restamp_topic_branch_as_coordination`, needed by WP14. It is widened-in, so it is also flagged by the m11c control.

For the two WP14 helpers, do one of these: add allowlist entries in `tests/architectural/dead_symbol_allowlist.yaml` whose exit condition names WP14 (#7282), or move the helpers and their tests to WP14.

### B2. `switch_write_checkout` is dead, and its dead-ness is hidden by a façade re-export
The commit message calls `switch_write_checkout` "the shared core", but no production path calls it. Create runs its own copy of the sequence: `_gather_and_decide_protected_mint` calls `_refuse_occupied_write_checkout` and `_dirty_outside_scaffold`, and `_check_out_minted_branch` then calls `_git_switch`. The only reason the gate does not flag it is the unused `switch_write_checkout as switch_write_checkout` re-export in `core/mission_creation.py`. That re-export block also adds `_git_switch`, `_dirty_paths_outside`, `_recorded_mission_branches`, `_refuse_occupied_write_checkout`, `_resolve_planning_branch` and `_record_create_return_branch`; none of them is used through the façade. Fix with one of:
- (a) route create through `switch_write_checkout`, so there is one authority for occupied/dirty/switch. The dirty message and golden can stay as they are by passing the owned paths.
- (b) drop the re-export and give `switch_write_checkout` the same WP14 allowlist exit as B1.

Either way, remove the unused re-exports.

### B3. The completion manifest is stale (an out-of-matrix red that WP13 caused)
`tests/specify_cli/cli/commands/test_completion_fast_path.py::test_manifest_matches_live_cli` fails. The only drift is `/commands/specify/help`: the live text is "Create a Mission scaffold in kitty-specs/." and the committed text is "...a feature scaffold...". The cause is WP13's docstring edit in `lifecycle.py`. Regenerate the manifest with `SPEC_KITTY_ENABLE_SAAS_SYNC=1 python -m specify_cli.completion --regenerate` and commit it. This test sits in an out-of-matrix directory, so CI would not catch it before the nightly.

## Required (small)

### R1. The IC-13 guard replaces the implicit target without saying so
Reproduction (real CLI): alpha is created with `--target-branch release`, the checkout is left on alpha's topic branch, then `agent mission create beta` runs. Beta's target becomes `main`, the Primary Branch, not `release`. The human output only shows `Branch: kitty/mission-beta-… (mission branch; merges into main)`. The JSON shows only `target_branch: main`. Nothing tells the operator that the checked-out branch belonged to another Mission and was replaced, or that `--target-branch` would override the choice. `--target-branch` help still reads "defaults to current branch", which is now false in this case.

The fallback chain is sound: an explicit target wins; then the Primary Branch via `resolve_primary_branch(bias=False)`; then the owning Mission's target; otherwise a refusal with a remedy. It is what research R-6 specifies. But the operator must be told. Add a one-line notice in human output, plus a JSON field or warning naming the replaced branch, its owning Mission, the chosen target and the `--target-branch` remedy. Update the `--target-branch` help. Pin both with a test.

### R2. The coord factory's `topology=None` path is now dead
`tests/_factories/coord_mission.py` still documents and supports `topology=None` ("WP06's real default path"). `test_make_coord_mission_cli_pr_bound_no_topology_is_no_longer_coord` now only asserts that the factory crashes with an internal `AssertionError`. Remove `None` support from `make_coord_mission` (type it `MissionTopology`, update the docstring), and delete or rewrite those tests. The provisional default is already covered in `test_mission_create_provisional_topology.py`.

## Non-blocking nits
- The WRITE_CHECKOUT_DIRTY message on a default create against an **unprotected** target still says "Cannot mint the protected-target mission branch". Reword it to cover the topic branch.
- The pr-bound branch-strategy gate (`_enforce_branch_strategy_gate_phase`) runs before the IC-13 guard. It compares `current_branch` with itself as the merge target, so when the guard later picks the Primary Branch the gate has judged the wrong target.
- `create_return_branch` for a create run from another Mission's topic branch records that other topic branch. Settlement would return the checkout there. Confirm this is intended, or record the guarded target instead.

## Verified OK
- Red-first: e2095150d8 adds the tests before 13b9cd84c9.
- Default create on a protected (`main`) and an unprotected (`work`) target: exactly 1 new branch, 0 worktrees, no coordination branch. Explicit `--topology coord` still mints its coordination branch and records `topology_source: explicit`. `--commit-to-target` without `--topology` refuses, and is accepted with an explicit `single_branch`.
- #5676: a probe on both targets with a modified tracked file, a staged file and an untracked file. All three are intact after the WRITE_CHECKOUT_DIRTY refusal, HEAD is unchanged and no branch was created. The occupancy refusal happens before any git write.
- The protected-retry re-pin still asserts the operator's file is untouched. The duplicate-Mission tests are unaffected.
- `mission_create_cli.json`: cells with an explicit `--topology` only gain `topology_source` and `topology_provisional`. Default cells change as decided (single_branch, topic branch, no coordination branch). The refusal golden only gains the typed code.
- The `docs/api/orchestrator-api.md` edit is limited to the `--topology` row, and there is no `CONTRACT_VERSION` bump.
