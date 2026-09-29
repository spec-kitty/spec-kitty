# Research: Implement resumes after in_review to in_progress rejection

## R-01 Reproduction (red-first)

Real CLI, throwaway repo, `main` at `5c8d24d0`, no monkeypatching, `spec-kitty init --ai claude,codex`, lanes topology, one WP:

| # | Command | Result |
|---|---|---|
| 1 | `agent action implement WP01 --agent claude` (+ commit, `mark-status T001 --status done`) | exit 0 |
| 2 | `agent tasks move-task WP01 --to for_review --agent claude` | exit 0 |
| 3 | `agent tasks move-task WP01 --to in_review --agent codex` | exit 0 |
| 4 | `agent tasks move-task WP01 --to in_progress --agent codex --review-feedback-file feedback.md` | exit 0; event `in_review→in_progress`, actor `codex`, `force: false`, `review_ref: review-cycle://…/review-cycle-1.md` |
| 5 | `agent action implement WP01 --agent claude` | **exit 1** — `Error: WP WP01 is already claimed for implementation by 'codex'`; 17 → 17 events |

Control (`--to planned` at step 4): step 5 exits 0 and records `planned→claimed→in_progress` (fix mode from review-cycle-1).

## R-02 Root cause

`start_implementation_status` (`status/work_package_lifecycle.py`), `IN_PROGRESS` arm: `_actors_compatible(current_actor, actor, allow_generic_existing=True)` against the slot occupant (latest event's actor = reviewer) → `WorkPackageClaimConflict`. PR #5316 (#5196) already resolved the same class for `move-task` via `latest_implementer_actor`, which skips reviewer rework verdicts.

## R-03 Squad findings (post-spec, 2 lenses) and dispositions

| Finding | Disposition |
|---|---|
| move-task already encodes the "requester is the latest implementer" rule (`_ownership_role_allowance` + `_implementer_arm`); a second copy in the lifecycle would drift | **Folded**: one pure predicate `is_latest_implementer` in `status/review_roles.py`, used by both |
| `review_roles` imports from the lifecycle module at import time → top-level import cycles | **Folded**: function-local import |
| Do not narrow to "latest lane event is a rework verdict": with the None/generic guard the only realistic divergence is a rework verdict; narrowing would make the lifecycle stricter than move-task | **Accepted** |
| Keep the no-op; `in_progress→in_progress` is not in the transition matrix, re-seating needs `--force` or a `planned` detour that resets the claim | **Accepted** |
| Return the admitted requester in `claimed_by` on the new arm | **Folded** |
| Extract a helper to keep `start_implementation_status` ≤ 15 complexity; fail closed with the #5196 precedent | **Folded** |
| Forced rejection without `review_ref` keeps the implementer refused — pin it | **Folded** (edge case + unit test) |
| Consolidation preflight still treats the reviewer's rejection as the implementer (advisory, fails safe) | **Deferred** — Follow-up: #5340 (already names this exact case) |
| Projection is append-ordered, reducer slot is Lamport-ordered | **Accepted residual** — see #4941 |
| `test_rework_guard_ratchets.py` docstring pinned `in_review → in_progress` as residual R-07 | **Folded**: docstring points at the new test |
