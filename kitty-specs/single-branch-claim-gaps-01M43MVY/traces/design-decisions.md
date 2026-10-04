# Design decisions

- 2026-10-04: **The occupancy predicate is branch-scoped** (DM-01M43MY9BKY2BBJQN4D2GVM436, plan.md "Decision").
  - An occupant counts only when its mission's write branch (`mission_runtime.single_branch_write_ref` over `meta.json`) is the branch the write checkout is on.
  - The existing `is_mission_completed` filter stays.
  - Rejected: `mission_number` (display-only), wall-clock stale/abandoned, target-branch ancestry, remedy-only.
- 2026-10-04: **The refusal names the claimant's expected branch as the occupant's write branch.** After branch-scoping the two are equal by construction, so the scan's return type stays the same.
- 2026-10-04: **Fail closed when the write branch is unknown.** If `meta.json` has no `target_branch`, or the checkout is on a detached HEAD, the occupant counts.
- 2026-10-04 (implement): Dropped a `MissionMetaReadError` catch in `_writes_to_another_branch`. `read_topology` has already parsed the same `meta.json`, so the catch was unreachable and would only have cost coverage.
- 2026-10-04 (implement): The remedy suggests `--to blocked` rather than `--to canceled`. It is non-terminal, so it can be reversed, and it does not need `--force`. The operator of the other mission can still approve or cancel later.
- 2026-10-04 (review fold): Amends the entry above. The code now does one `load_meta_fail_closed` read and calls `topology_from_meta` on that dict, so `read_topology` is no longer called. The unreachable catch was dropped for the same reason: the one read already parsed `meta.json`.
- 2026-10-04 (pre-PR squad): The scan deliberately does not apply the primary-branch default of `read_target_branch_from_meta`. An occupant with an absent, empty or non-string `target_branch` keeps blocking (fail closed); a parametrized test pins all three cases.
