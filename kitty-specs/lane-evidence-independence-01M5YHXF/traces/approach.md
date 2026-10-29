# Approach

- **[2026-10-27][research] Red baseline reproduced through the real CLI.** Coord: hollow self-approval, accept and consolidate all exit 0 and the owned file is absent on the target; lanes is only caught by a commit-count check that `--force` or any non-owned commit defeats. Disposition: build one owned-file evidence predicate.
- **[2026-10-27][plan] Generalise the #5939 single_branch axis instead of adding a parallel one.** One module (`consolidation/wp_evidence.py`) serves move-task, accept, consolidate and orchestrator-api; `approved_bound` stays unchanged.
- **[2026-10-27][implement] WP01 rejected at review cycle 1, approved at cycle 2.** The reviewer found a vacuous lanes fixture (planning commit recorded before bootstrap; WPs owned their own task files) and a fail-open dependency-window widening; both reproduced by the orchestrator and fixed (window now `merge-base(dep_tip, lane_tip)..lane_tip`).
- **[2026-10-27][implement] WP02 rejected at cycle 1 (stale attestation), approved at cycle 2.** A container restart between cycles lost no state; the fix went to a fresh implementer because the first could not be resumed.
