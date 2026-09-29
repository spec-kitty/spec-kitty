# WP05 review feedback, cycle 1 (reviewer-renata)

**Verdict: changes requested.** The core activation is correct, and the three named mutations are all caught (see "Verified"). Two test-honesty defects block approval, plus one required single-authority consolidation.

## Blocking

**Issue 1: `test_second_implement_refused_names_in_progress_wp` (AS6) and `test_dirty_checkout_refused_but_resume_allowed` (AS8) pass for the wrong reason.**

- **Fixture.** WP02 depends on WP01. While WP01 is `in_progress`, `implement WP02` is refused by **dependency readiness**, which also names WP01. It is not refused by the write-checkout occupancy or dirty refusals these tests claim to cover.
- **Evidence.** I ran each mutation in a throwaway worktree against `tests/integration/test_issue_5100_single_branch_topology.py`:

  | Mutation | Result |
  |---|---|
  | M6: occupancy check off (`if occupants:` → `if False:` in `implement_support._ensure_repo_root_checkout_available`) | 6 passed, 2 xfailed |
  | M7: dirty check off (`if not is_resume:` → `if False:`) | 6 passed, 2 xfailed |

  Test 5 also already passes at the red commit 8652f2b5 for the same reason.
- **Required fix.**
  - Make the claimed WP independent of WP01: drop the dependency for these two tests, or add an independent WP03 to the fixture.
  - Assert the refusal **reason**:
    - AS6: the occupancy message ("…is already in_progress in the shared write checkout…") naming the mission and WP01;
    - AS8: the dirty message listing `scratch_outside_spec_kitty.txt`.
  - Confirm M6 and M7 each turn the corresponding test red.

**Issue 2: the "golden compare" control in `tests/lanes/test_compute_lanes_single_branch.py::TestOtherTopologiesUnchanged` is tautological for LANES.**

- **Why.** `before` calls `compute_lanes(...)` with no `topology` kwarg, whose default is `MissionTopology.LANES`. `after` passes `topology=MissionTopology.LANES`. Both run the identical post-WP05 code path, so nothing is compared against pre-WP05 output.
- **Contrast.** The COORD / LANES_WITH_COORD cases at least compare a different enum value against the default, but they too only prove that "non-SINGLE_BRANCH equals the default path", not that it equals pre-WP05 behaviour.
- **Required fix.** Pin a literal expected manifest: a frozen dict of lane ids, wp_ids, write_scope, depends_on_lanes, parallel_group, mission_branch and `planning_artifact_wps`. Capture it from the pre-WP05 base (cfb75bc4) for the fixture graph, and assert every non-SINGLE_BRANCH topology equals it.

**Issue 3: `worktree_allocator._stored_topology_for_fail_closed_guard` is a second parse of the stored `topology` field (charter: single canonical authority).**

- **What it duplicates.** It re-implements `topology_from_meta`'s "stored value is a valid `MissionTopology` string" check, without the derive fallback.
- **The rationale is sound.** A stored-only read is right for this guard:
  - Deriving from an on-disk `lanes.json` that the in-memory allocation has not written yet would falsely classify the mission `single_branch`.
  - A mission with **no** stored topology cannot violate Invariant T-1 by construction, since its derived topology is `lanes` whenever code lanes exist, and the create path always stamps `topology`.

  So the concern is duplication, not semantics.
- **Required fix.**
  - Extract one stored-only reader, for example `backfill_topology.stored_topology(meta) -> MissionTopology | None`.
  - Have `topology_from_meta` use it (stored-or-derive), and have the allocator guard delegate to it after its `load_meta`.
  - Add a one-line unit test.

## Verified

**Red-first.** At 8652f2b5 the #5100 file shows 4 failed, 2 passed and 2 xfailed:

| Test | At 8652f2b5 |
|---|---|
| T1 | red: `assert 2 == 1` lanes |
| T2 | red: a `.worktrees/*-lane-a` directory exists |
| T4 | red: "No implementation commits on lane branch" |
| T6 | red on its `direct_repo` stamp assertion only; its dirty leg is vacuous (Issue 1) |
| T3 (lanes control) | passes on base, correctly |
| T5 | passes on base, for the wrong reason (Issue 1) |
| T7, T8 | strict xfail (WP08); no unexpected pass |

**Mutations caught.**
- M1, the `compute_lanes` SINGLE_BRANCH arm off: 10 failures.
- M2, the `_preserved_mission_branch` single_branch branch off: `test_single_branch_never_preserves_stale_value`.
- M3, the `compute_and_write_lanes` previous-manifest assertion off: `test_finalize_write_fails_closed_on_unmigrated_manifest`.
- M4, the allocator guard off: `test_allocate_lane_worktree_fails_closed_on_unmigrated_manifest`.
- M5, the mission_branch fallback broken: 5 failures.

**Assertion placement.** The check runs against `previous_lanes` (the manifest about to be overwritten). It refuses an unmigrated single_branch + code-lane re-finalize (`mission_finalize` reports it as JSON/console, with no traceback). It is a structural no-op for a fresh finalize (`previous_lanes is None`) and for a `lanes`-topology mission. This is the right semantics; checking the freshly computed single-lane manifest would be vacuous.

**Out-of-map edits are minimal and justified.**
- `tasks_finalize.py` and `mission_state.py` only thread `mission_branch` and update comments.
- `test_refinalize_mission_branch.py` adds the `topology=` keyword plus a new SINGLE_BRANCH test.
- `test_issue_2684` flips its fixture to `lanes`, with a rationale.
- `test_explicit_checkout_commands.py` and `test_owned_checkout_mark_status.py` needed no change and pass.

**Tests and tools.**
- Targeted files: 252 passed, 2 xfailed. The run covered:
  - the #5100 file (`-n 4`), the two new `tests/lanes` files, and `refinalize`;
  - the three blast-radius fixtures;
  - `lane_base_honoring`, `worktree_allocator`, `compute_and_persist_core`, `mission_state_lanes_rebuild` and `mission_finalize_phases`.
- Gates: `test_layer_rules` 74, `test_no_dead_symbols` 34, `test_mission_runtime_surface` 7.
- ruff is clean. The e2e files were not run, per the operator rule.
