---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-28T21:33:50Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback, cycle 1 (reviewer-renata)

The production change is sound and I would approve it as is. Rulings:

- **C-002:** holds. There is one predicate, `surface_resolver.primary_read_targets_coord_worktree`, and all six guard sites go through it. No new `StatusReadSource` or `EventLogWriteTarget` member was added.
- **FR-014:** holds.
- **Hunk (c):** does not misroute today. See the forward note below.
- **Other checks:** all pass. Red-first order, cherry-pick provenance, mypy (5 errors, the same as base) and ruff check are all fine.

One blocking issue remains. It is in the NFR-001 oracle of the carried finalize test.

## Issue 1 (blocking): the NFR-001 R-snapshot comparison excludes too much

`tests/specify_cli/coordination/test_owned_status_read_contract.py::test_finalize_and_read_owned_mission_below_worktrees` compares only `files`, `head`, `index_stage` and `index_diff`. That leaves out two NFR-001 components entirely:

1. **`lock_files`.** The whole shared lock root `<common-dir>/spec-kitty-locks` is excluded.
2. **`home_files`.** The isolated `SPEC_KITTY_HOME` is not compared at all, and the comment does not mention it.

**What I measured.** I probed the test with the snapshot components printed:

- Lock root before the command: `{}`.
- Lock root after the command: `{'owned-fixture-01M2D900.status.lock': sha256(b'')}`. That is one **empty** lock file.
- `home_files`: identical before and after.

**Ruling on the lock file.** It is an expected artifact, not a write to R that must be prevented:

- It is the per-mission status mutex from `status/locking.py::feature_status_lock_path`. That function puts the lock in the git common dir, and P shares that directory with R by git construction.
- `BookkeepingTransaction.acquire` creates it for every owned transactional write, including owned P outside `.worktrees`.
- The acquire path is unchanged by this WP, and converting it is WP07 T033's scope.

The exclusion must still be narrow and named, not blanket.

**Required fix.** Replace the four separate asserts with a comparison that:

- asserts `files`, `head`, `index_stage`, `index_diff` **and `home_files`** are unchanged;
- asserts the lock-root delta is **exactly** one added key, named from the canonical composer rather than a hard-coded string. For example, `feature_status_lock_path(checkouts.owned_root, <lock_key>).name`, or the same `<slug>.status.lock` key that `_mission_specs_dir_name` produces;
- asserts that key's hash is `sha256(b"")`, so the file has no content and no holder sidecar is left behind;
- asserts no lock key was removed or changed;
- carries a comment that names this as the pre-existing shared-common-dir status mutex and cites NFR-001.

Mutation check: if the command wrote anything else into the lock root, or a non-empty lock, the test must go red. Please record that check in the Activity Log.

Please also note the NFR-001 wording tension ("shared lock root … 0 differences" against a cross-checkout mutex that has to live there) in the Activity Log or the PR body, so the orchestrator can decide whether to amend the spec or add a shared named tolerance in `tests/_owned_fixtures.py`. That file is WP02's, so do not edit it here.

## Non-blocking nits (fix if cheap, otherwise ignore)

- **N1, NFR-002 counter scope.** The T031 step 3 counter in `test_same_path_matrix` wraps only `surface_resolver.subprocess.run`. The WP asked for `subprocess.run` and `Popen` in both `status_service` and `surface_resolver`. The rows that are refused or accepted by shape never reach `status_service`'s branch-ref `subprocess.run`, but wrapping it makes the "0 git calls" claim literal.
- **N2, type ignores.** `_run(op, contract: object)` uses three `# type: ignore[arg-type]`. Typing `contract` as `EventLogReadContract | EventLogWriteContract` and narrowing with `isinstance` removes them (see the CLAUDE.md rule against suppressions).
- **N3, missing matrix row.** The T031 matrix row "registered coordination worktree | coordination label | accepted (unchanged)" is not present. There is only the coordination-label read on P's path. One extra assertion in the matrix file closes it.

## Forward note for WP07 / WP11 / WP19 (not a WP06 change)

Hunk (c) in `_read_contract_from_transaction_target` is unconditional on `identity.owned`. That is sound today:

- I built owned `lanes_with_coord` fixtures, sibling and under `.worktrees`, with a coordination branch.
- I threaded a `LANES_WITH_COORD` fact through `TransitionRequest(owned_mission=…)`, and also ran an unthreaded request and `read_events_transactional`.
- All three were refused with `OWNED_TOPOLOGY_UNSUPPORTED` before hunk (c) was reached. The refusals come from `resolve_placement_only` → `_require_owned_single_branch` and from `resolve_owned_mission`'s default `LIFECYCLE_OWNED_TOPOLOGIES`.

So an owned identity is single_branch by construction. If a later WP threads a `NEXT_OWNED_TOPOLOGIES` fact into the transition pipeline and lifts that placement refusal, hunk (c) must be gated on `not routes_through_coordination(identity.owned.topology)`. Otherwise an owned coordination-topology mission would read P's primary partition instead of the coordination surface.
