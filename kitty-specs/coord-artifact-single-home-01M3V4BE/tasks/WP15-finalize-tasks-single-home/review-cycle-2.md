---
affected_files: []
cycle_number: 2
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T22:09:48Z'
reviewer_agent: claude
wp_id: WP15
---

# WP15 review, cycle 2: changes requested (small, focused)

Reviewer: claude (reviewer-renata, opus).
Lane `lane-m`, base `e7b085d26c`.
Commits reviewed: `f26a913ca9` (implementer), `21ae853333` (orchestrator).

## Verified fixed

| Item | What I checked | Result |
|---|---|---|
| B1 | My cycle-1 probe, rerun at HEAD | MATERIALIZED and pre-fix EMPTY Missions now report `total_wps=2, newly_seeded=2`, write planned rows to the coordination log, and report `mission_type="software-dev"` |
| B1 | New test `test_do_finalize_tasks_seeds_wps_on_every_coordination_shape` (EMPTY, UNMATERIALIZED and MATERIALIZED shapes × COORD and LANES_WITH_COORD) | All 6 cases red at `a17b88e269`, green at HEAD |
| B2 | My probe: `--validate-only` on the UNMATERIALIZED and EMPTY shapes | Coordination branch tip, worktree and Mission dir unchanged; no new commits |
| B2 | New test `test_do_finalize_tasks_validate_only_never_mutates_coordination_surface` | Red at `a17b88e269`; killed the mutation that calls `write_dir` unconditionally (6 failures) |
| B3 | Remote-only coordination branch, with and without `--json` | Exit 1, clean error with the fetch/doctor recovery hint, no `lanes.json`, no root status writes |
| B3 | Both new fail-closed tests (remote-only, `COORD_SEED_FORK_REFUSED`) | Red at `a17b88e269` |
| B4 | Mutation `has_relevant_changes=primary_dirty` | Now killed by `test_resolve_finalize_commit_candidates_sees_coord_only_dirt_with_clean_root`. That test passes at `a17b88e269`, as expected: the code was right there and only the test was missing. |
| B5 | `test_ruff_format_exclude_ratchet` | Green. Formatting-only hunks were reverted and `pyproject.toml` was not touched. |
| B6 | `_resolve_acceptance_matrix_home` | Uses `write_dir(ACCEPTANCE_MATRIX)` |
| B6 | Root `acceptance-matrix.json` candidate | Dropped from `_collect_finalize_artifacts` |
| B6 | `commit_router.py` | Not edited |
| B6 | Stale-root-matrix test | Red at `a17b88e269`; killed the mutation that adds the root candidate back |
| B6 | The 4 named guards | Green |
| B8 | `kept_with_warning` message | No longer names `--allow-orphaned` |
| B10 | Surface lines render on the refusal arm | Test red at `a17b88e269`; killed the mutation that removes rendering (2 failures) |
| B10 | `_finalize_pin_refresh_commit_outcome` extraction | C901 within limit |

## Blocking

### C2-1. B7 does not follow the orchestrator's ruling, and nothing pins it

The ruling was: follow `contracts/commit-outcome.md`, which means:
- emit `pin_class` and `reason`;
- report **INDETERMINATE as `kept_with_warning`, visibly**.

What the code does instead:

- `_resolve_preserve_planning_commit_decision` still returns a silent `preserved` for INDETERMINATE.
- The docstring of `_planning_commit_refresh_payload` calls this a "deliberate deviation". The ruling overrides that position.

Fix:
- Return `kept_with_warning` for INDETERMINATE, with a reason code such as `indeterminate_tip_uncapturable`, and print a visible warning.
- The tip may be `None`, so the warning must still read correctly when there is no candidate commit to name.

Test gaps:
- No test asserts `planning_commit_refresh.pin_class` or `.reason`. The mutation `"pin_class": None` survived all 116 tests in the commit-surface, phases and #4141 files.
- `reason` is never asserted either.

Add tests that read the JSON payload for:
- ADVANCED → `refreshed`;
- ADVANCED with no planning change → `preserved`;
- FOREIGN → `kept_with_warning` with `reason`;
- INDETERMINATE → `kept_with_warning` with `reason`.

### C2-2. The pin-refresh consumer's outcome rule is not pinned by a mutation-sensitive test

This is the outcome-consumer rule from the WP13 review. In `_finalize_pin_refresh_commit_outcome`, I replaced `if commit_outcome_exit_code(result) != 0:` with a legacy-status check (`if result.status not in ('committed',):`). The mutation survived the #4141 tests and all commit-surface tests (32 passed).

Fix: add a test where the router result has `status="committed"` but a `refused` (or `error`) surface. The pin-refresh path must refuse, restore `lanes.json`, and exit non-zero.

### C2-3. The `--refresh-planning-commit` help text recommends a command that always fails

The B9 rewrite (`mission_finalize.py`, the `--refresh-planning-commit` option, around L5295-5306) says to use the flag "to advance a pin the automatic path could not safely verify on its own and warned about instead (a recorded SHA whose object is absent from this repository…)".

That cannot work. `_resolve_refresh_planning_commit_decision` refuses a FOREIGN pin unconditionally, and the new `kept_with_warning` message says the pin "cannot be re-pointed automatically".

This is the B8 defect again, in the help text. Remove that clause, or state that a FOREIGN pin must be corrected by hand.

## Non-blocking (record or fold as convenient)

- **No red-first commit for the regressions.** All fixes for B1–B10 landed in one commit with their tests, so there is no committed red-first evidence for the regressions. I verified red independently at `a17b88e269`: B1, B2, B3, B6 and the B10 refusal arm are all red for the right reasons. Record this in the activity log.
- **B3 tests are not independently sensitive.** Each `write_dir`-outside-`try` fix is masked by the other: `_emit_tasks_started` runs first, so it fails closed before `_emit_local_canonical_events` is reached. Swallowing either one alone survives; swallowing both is killed (2 failures). This is acceptable as defense in depth.
- **B6 read/write swap is not observable by tests.** Changing `_resolve_acceptance_matrix_home` back to `read_dir` survives every test, because the surface is already established by the earlier `write_dir` call. WP20's AST gate is the real guard here.
- **`assert` in production code.** The guard in `_commit_finalize_artifacts` (owned candidates) is a bare `assert`, which `python -O` strips. Consider raising an explicit error instead.
- **Root `status.json` residue (pre-existing).** It still comes from `bootstrap_canonical_state`'s `materialize(feature_dir)` with the PRIMARY dir. This is a WP16/WP21 concern.

## Evidence (HEAD `21ae853333`)

- **Finalize suite** (46 files: the cycle-1 set plus `test_mission_finalize_phases.py`): **1202 passed, 2 skipped, 0 failed**.
- **Cycle-2 test files run at the rejected tip `a17b88e269`**: 19 failed, 131 passed. Failures are listed above, each for the expected reason.
- **Named gates, run one file at a time:**

  | Gate | Result |
  |---|---|
  | `layer_rules` | 74 passed |
  | `no_write_side_rederivation` | 27 passed |
  | `write_surface_placement_guard` | 17 passed |
  | `ruff_format_exclude_ratchet` | 6 passed |
  | `no_legacy_terminology` | 96 passed |
  | `finalize_refresh_pin_authority` | 5 passed |
  | `status_state_read_dir_single_authority` | 13 passed |
  | `no_dead_symbols` | 1 failed, 35 passed |
  | `dead_symbol_allowlist_contract` | 1 failed, 3 passed |
  | `status_events_writes_gate` | 1 failed, 24 passed |
  | `mission_resolver_walker_gate` | 1 failed, 3 passed |
  | `destructive_op_routing` | 1 failed, 36 passed |

  All five reds are inherited from lane-a: `COORD_SEED_TRAILER` (twice), the lock census (`coord_seed`), the walker (`coord_seed:420`), and destructive-op (`commit_router::_dirty_paths_in_checkout`). None are caused by WP15.
- **Diff coverage against `e7b085d26c`:** 97% (161 lines; missing `mission_finalize.py` lines 2958, 2974, 4063, 4321).
- **Static checks:**
  - `ruff check`: clean.
  - `ruff format --check --force-exclude`: clean.
  - `mypy --strict`: 3 errors, the same set as at base.
  - C901: at most 14 (`finalize_tasks` 14, `_ft_apply_writes` 13).

- **Mutation summary:**

  | Mutation | Result |
  |---|---|
  | M3: coordination dirt dropped from `has_relevant_changes` | killed (1) |
  | B2: `write_dir` called even in validate-only mode | killed (6) |
  | B10: rendering removed from the pin-refresh consumer | killed (2) |
  | B6: root acceptance-matrix candidate re-added | killed (1) |
  | B3: both `write_dir` swallows | killed (2) |
  | B3: either swallow alone | survived (masked) |
  | B6b: `read_dir` used for the matrix home | survived |
  | B10b: pin-refresh outcome taken from legacy status | **survived** |
  | B7: `pin_class` forced to `None` | **survived** |
