# WP08 — review feedback, reopen after cycle 3 (found during WP09 review)

**Verdict:** reopened. The approval in cycle 3 missed a functional gap: FR-008 is not met.

## Blocker — `--commit-to-target` is inert after create (FR-008, US3 AS3, research R-5)

The persisted opt-out is written and never read. To reproduce, run the reviewer's steps on a scratch repo whose `main` is protected by default, with `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS` unset:

1. `agent mission create … --topology single_branch --commit-to-target` → `meta.commit_to_target == true`, and no mission branch is minted. This part is correct.
2. `agent mission finalize-tasks` → exit 1, `PROTECTED_BRANCH_REFUSED` (destination 'main' is protected).
3. `implement WP01` → fails as well.

Outside mission creation, nothing reads `commit_to_target`: not `ProtectionPolicy`, the commit router / `coordination/policy.py` / `surface_authority.py`, or `safe_commit`'s guard in `git/commit_helpers.py`. `test_commit_to_target_overrides` checks only the create step, which is how it passed.

### Required fix

`commit_to_target: true` must act as a **mission-scoped** protection bypass. It goes through the existing operator-hatch concept (C-002: no second bypass mechanism, no new env var), and it applies only:

- to writes for **that mission**,
- to **its own `target_branch`**.

It must NOT make the branch unprotected for other missions or for non-mission commits.

- Find every refusal site that a mission-scoped write on a protected target hits: finalize-tasks, status transitions (`move-task`, claim/implement bookkeeping), planning commits, `safe_commit`, and consolidate's mission→target landing or no-landing path. Thread the mission's `read_commit_to_target(meta)` (fail-closed reader, already in `core/paths.py`) into the one place the verdict is decided. Prefer extending `ProtectionPolicy` (for example an `allows_mission_write(branch, *, commit_to_target, target_branch)` or an equivalent hatch-fold) over sprinkling checks across call sites.
- A non-boolean `commit_to_target` must still fail closed. It must refuse, never bypass.
- Edits outside owned_files (commit router / policy / commit_helpers) are expected; list each hunk with a rationale in the Activity Log.

### Required tests (red-first: commit them alone, and show they fail for the right reason first)

1. **`test_commit_to_target_overrides`** (`tests/integration/test_issue_5100_single_branch_topology.py`, an out-of-map assertion addition only). Extend it past create to cover:
   - `finalize-tasks` exits 0 and commits on `main`;
   - `implement WP01` exits 0 in the repo root on `main`, stamped `direct_repo`;
   - an owned-file commit, then `move-task WP01 --to for_review` succeeds, and the status commit lands on `main`.

   Keep `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS` explicitly unset in the test env.
2. **Negative controls** (unit level, next to the new policy seam):
   - a different mission with no `commit_to_target`, on the same protected `main`, is still refused;
   - a non-mission commit on `main` is still refused;
   - `commit_to_target: "yes"` (a non-bool) refuses.
3. **Mutation check.** Remove the new hatch-fold and confirm that test 1 goes red. Record this in the Activity Log.

## Not blocking

None beyond the above. The rest of WP08 stays approved as reviewed in cycle 3.

## Test policy

Run the named files only: the #5100 integration file, the WP08 test files, the new unit test, and the direct test files of each module you touch, found with grep as the WP prompt describes. No directories, no e2e, no timing tests, no `make test-fast`.
