---
affected_files: []
cycle_number: 1
mission_slug: lane-worktree-model-hardening-01M6QY1M
reproduction_command:
reviewed_at: '2026-11-06T17:33:00Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP10
---

# WP10 review, cycle 1: REJECTED (reviewer-renata)

Lane lane-g at 85ce83e217. Dead-symbol and dead-module gates are green (40 passed, serial). The order-manifest gate and the requires_git_repository audit are green. The four WP10 test files pass (30 passed, together with those two gates).

## Blocking

### B1. Six existing coordination tests go red. All six are green on the lane base 665e950d01 (verified by running them at that commit).

`PYTHONPATH=src pytest tests/specify_cli/coordination/test_status_transition.py::test_transactional_emit_fail_closed_surface_refusal_stays_structured tests/specify_cli/coordination/test_status_surface_owned.py::test_same_path_matrix`

- `test_transactional_emit_fail_closed_surface_refusal_stays_structured`: a coordination root that exists but is not registered (a husk) used to give the structured `BookkeepingCommitFailed`. It now gives a raw `StatusContractError("coordination_transaction_append requires a registered coordination worktree; ... is not inside one")` from `_require_registered_coordination_target` (transaction.py). This is review question (3) failing. A deleted or husked coordination worktree now fails with an unstructured contract error that names no remedy. Raise a structured Bookkeeping refusal with a remedy instead (for example: re-materialize the coordination worktree, or `spec-kitty doctor ...`), or keep the husk check after the existing structured path.
- `test_same_path_matrix[owned-p-with-own-fact-append, owned-p-without-fact-append, coord-worktree-*-append]` (5 cases): NFR-002 of the owned-checkout work requires zero git subprocess calls on the write-contract validation path (`primary_read_targets_coord_worktree`, see its docstring). `refuse_status_write_into_lane_checkout` is now called unconditionally at the top of `_validate_write_contract` and runs `git rev-parse` and `git worktree list` (8 extra calls). Two ways to fix it:
  - Keep the FR-041 lane refusal out of the zero-git contract validator. Do the registry check once at the transaction or write seam, where git is already used.
  - Or let an `owned` fact that covers the path short-circuit the check, and handle the coordination-label rows without git.
  Either way, NFR-002 must still hold. Do not edit the NFR-002 assertion to make the tests pass.

### B2. The migration settles a lane it refused, permanently (review question 4)

When some lane worktree is `refused_lane_only_events` or `skipped_mid_operation`, `apply()` still returns `MigrationResult(success=True)`. The runner then records `success` (runner.py `_apply_migration`, line ~700). `migration_settled` treats that as applied. For this migration `reselect_when_recorded` is False, because it is not `runs_first`. So the migration is never selected again in this clone. That lane never gets the exclusion, even after the operator reconciles the lane-only events or the rebase finishes.

Nothing else reports it either. The doctor probe `LANE_STATUS_AUTHORED` compares committed branch content only, so it cannot see an uncommitted dirty lane copy, and nothing reports a lane worktree that lacks the exclusion. This applies to the mixed case too: one clean lane excluded and one refused lane gives `success` and settles the migration.

The test `test_migration_refuses_lane_only_event_ids_untouched` asserts `result.success`, but it never runs the migration through the runner or the ledger.

Possible fixes. Choose one and add a runner-level test (apply, reconcile, upgrade again: the lane is now excluded):
- (a) Have `can_apply()` refuse (return False with the reason) while any lane is in an unmigrated outcome. The runner returns `skipped` without recording it, so the migration does not settle, the warning names the lane-only ids on every upgrade, and the upgrade does not fail. Clean lanes then wait for the refused lane. That is acceptable: it is reported, and every new lane checkout is excluded at creation anyway.
- (b) Keep the partial apply, and add a doctor finding with a remedy for a registered lane worktree that lacks the exclusion. For example, `doctor sparse-checkout` could report it, and `--fix` could apply `exclude_lane_status_files` after the same lane-only-event check.

The point is that a lane must never be left unexcluded with nothing reporting it.

### B3. `LANE_STATUS_AUTHORED` gives a false positive on every lane of this Mission (review question 5)

On the repository root checkout (read-only), `find_lane_status_authored(Path('/home/user/spec-kitty'))` reports all 9 live lanes of `lane-worktree-model-hardening-01M6QY1M` (lanes a, b, c, f, g, h, i, j, l). So `doctor sparse-checkout` exits 1 on a healthy repository.

Cause: this is a `lanes` Mission. It has no coordination branch, and its status surface is the target branch (`issue-7276-lane-worktree-hardening`, on the PRIMARY partition). `_consolidation_base` picks `mission_branch` before `target_branch`. The lanes carry target-branch status commits that came in through dependency-lane merges (for example `3fc7e30cb3 chore(spec-kitty): status transition WP05`).

Evidence for lane-g:
- The lane's `status.events.jsonl` blob `396db77432` is exactly the target's blob at `4caf8e2244`.
- `git diff merge-base(lane-g, target)..lane-g -- <status files>` is empty.
- Against `merge-base(lane-g, mission branch)` = `a4e342649c`, the same diff is non-empty.

So the probe flags bytes that the lane did not author, which contradicts its own docstring ("coordination bytes merged into the lane do not count").

Fix: use the Mission's resolved status-surface branch as the base: the coordination branch when one exists, otherwise the branch the status surface resolves to (the target for `lanes`, the write branch for `single_branch`). Do not use the mission branch first. A stronger check would also clear a lane whose status blob is reachable from the surface branch. Add a test in which a lane merges a dependency lane that carries surface status commits; it must not be flagged.

### B4. WP10's own migration tests fail depending on test order (this is the one failure the implementer left unclassified)

To reproduce:

`PYTHONPATH=src pytest -p no:xdist -p no:randomly tests/upgrade/test_auto_discovery.py tests/specify_cli/upgrade/test_lane_checkout_status_exclusion_migration.py`

Result: 4 failed (excludes_clean, flags_redundant, refuses_lane_only, skips_mid_rebase), each with `assert <LaneCheckoutOutcome.EXCLUDED: 'excluded'> is <LaneCheckoutOutcome.EXCLUDED: 'excluded'>`.

Cause: `test_auto_discovery` re-imports the migration modules. The test module's top-level `LaneCheckoutOutcome` then belongs to a different class object than the one the re-imported module returns, so the `is` comparisons fail.

Impact: the full `tests/specify_cli/upgrade + tests/upgrade` run (the out-of-matrix nightly lane) goes red on these tests whenever `--dist loadfile` puts them on a worker after `test_auto_discovery`. That happened in my run (gw5).

Fix: compare by value (`item.outcome == "excluded"` or `.value`), or resolve the enum from `sys.modules` at call time, as the other migration tests do. Do not mark them flaky.

## Non-blocking (fix if convenient)

- N1 (FR-042 red-first): the test was green before the change because `is_coord_residue_churn` already dropped these paths, as the handoff notes. It is not vacuous: it has a dirty status file, a paired deliverable control and C-008 assertions. It is acceptable as a regression guard. A mutation that removes `is_mission_status_file(rel) or` keeps it green, so it does not pin the new by-name rule. You could add a case on a topology where `is_coord_residue_churn` returns False.
- N2: `is_lane_branch` (pre-existing, used here as the registry classifier) also matches the planning lane (`kitty/mission-x-<mid8>-lane-planning`) and plain-legacy Mission branches whose slug ends in `-lane-<letters>` (`kitty/mission-my-lane-a`). It is harmless today, because a planning lane is the repository root checkout (`is_main`). Consider excluding `lane-planning` explicitly in `RegisteredCheckout.is_lane`.
- N3: `run_sparse_checkout`: with `--fix` and only `LANE_STATUS_AUTHORED` findings, it falls through to `_emit_clean_state(fix)`, which prints a clean state right after the warning.
- N4: owned_files still names rc9 for the migration module. This is a known planning mismatch, not a rejection reason.

## Checked and fine

- `clone_local_effect = True`.
- `apply()` is idempotent (`already_excluded`; `test_migration_second_run_changes_nothing`).
- The `order_manifest.txt` entry is last and has a justified `# tie:`.
- `exclude_lane_status_files` is the one exclusion authority.
- Lane-only events are detected by event id, reported, and that worktree is left byte-identical (fingerprint test).
- The `test_no_dead_modules` allowlist entry matches the other auto-discovered `m_4_0_0rc8_*` migrations.
- An unreadable registry fails closed (`WorktreeRegistryUnavailable` maps to `MigrationStateUnreadableError`, a recorded failure).
- NFR-008: `normcase`, separator-agnostic `is_mission_status_file`, git-only commands. Nothing Windows-specific is broken.

## Failure classification: tests/specify_cli/upgrade + tests/upgrade + tests/lanes + tests/integration/sparse_checkout (-n 6 --dist loadfile)

33 failed, 3979 passed, 16 skipped.
- 28 failures: "Source mismatch". A subprocess imports the stale editable install from the repository root checkout `src/`. These are environmental (category 3) and not WP10's.
- 1 failure: `test_mission_corpus_recovery::test_original_full_corpus_residue_then_recovered_and_landed_corpus_passes`, a pytest-timeout after 450 s under load. This is a load flake.
- 4 failures: B4 above. They are WP10's, and order-dependent.
