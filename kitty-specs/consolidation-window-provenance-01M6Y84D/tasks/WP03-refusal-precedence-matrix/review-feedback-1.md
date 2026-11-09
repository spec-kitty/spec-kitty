# WP03 review, cycle 1: changes requested

Reviewer: claude:claude-opus-5-5:reviewer-renata. Reviewed commit beb436c570 on lane-b (one file, `tests/consolidation/test_refusal_precedence_matrix.py`).

## What is right (keep it)

- I read `build_approved_wp_set` line by line (`reconciliation.py:1697-1824`). `REFUSALS` matches it: dependency_refs (both the unreadable-lane-heads return and the declared-ref return carry `Error code: DEPENDENCY_REF_`), then surface, unresolvable_branches, unreadable_canceled_dependency, canceled_dependency (compound), mixed_lane (compound), bound, evidence, presence. Every marker is present in the production text.
- The three places where you followed the code over plan IC-03 are correct. The code wins, per the WP. The tracer entry records them.
- Both co-occurring pairs are driven through `build_approved_wp_set`. The test asserts both markers before the order. The swapped-order control fails in a real way. `test_matrix_is_complete` is sound. No production code changed, and the lane reflog shows no rewrite.

## Issue 1 (blocking): the snapshot normalizer is flaky about 7% of the time

`_SHORT_SHA` (line 207) only matches a hex run that has at least one digit **and** at least one letter (`a-f`). The bound refusal prints 7-character short SHAs (`approved_bound._SHORT_SHA = 7`). The mixed-lane detail prints 10 characters (`wp_attribution._short_shas`). Commit SHAs are not deterministic: the fixtures do not pin `GIT_*_DATE`. So a short SHA made only of digits stays un-normalized and the `SNAPSHOTS` comparison fails. For 7 characters, P(all digits) = (10/16)^7 ≈ 3.7% per pair, so about 7% per run of the file. Demonstrated: `_SHORT_SHA.sub` leaves `commit(s) 1234567 (touching` and `` git show `4821930` `` unchanged.

Fix: normalize the SHAs the fixture knows, not a guessed pattern. Have each `_pair_*` factory return the text plus the commits it created (for example `git rev-parse` of the lane tip after `add_post_approval_commit` / `_plant_straggler`). Replace each full SHA and each of its 7- and 10-character prefixes with `<sha>`. Keep the 40-hex regex as a backstop. Do not just drop the `[a-f]` lookahead: an exact replacement cannot collide with other text and never misses.

## Issue 2 (blocking): most reorders of two checks fail no row

The Review Guidance asks: "would a reorder of two checks fail at least one matrix row?" Today the answer is mostly no. Only the two compound pairs and four witness rows execute anything. Swapping bound and evidence, evidence and presence, canceled_dependency and mixed_lane, or unresolvable_branches and unreadable_canceled_dependency passes every test. The `NON_CO_OCCURRING` value is a site string derived from `REFUSALS` order, so it moves with the table, not with the code. FR-017's purpose ("so that the split cannot reorder refusals unnoticed", C-006) is not met for those pairs. WP14 moves exactly this function.

The WP text does ask for short-circuited pairs to be listed as "cannot co-occur". So this is a gap in the WP design, not a deviation from it. The fix is still small and stays inside this file:

- **Adjacent-pair witnesses are enough.** If every adjacent pair (i, i+1) of `REFUSALS` keeps its order, transitivity keeps the whole order, and any permutation inverts at least one adjacent pair. mixed_lane < bound is already covered: a bound-first reorder makes `_pair_mixed_lane__bound` refuse with bound alone. For each other adjacent pair:
  - **Independent checks** (the later check does not read the earlier check's output): build a witness with both conditions live. Assert the earlier marker is present and the later marker absent. Use the existing witness test's shape. Candidates: canceled_dependency → mixed_lane, bound → evidence, evidence → presence, unresolvable_branches → unreadable_canceled_dependency, dependency_refs → surface.
  - **Data-dependent checks** (the later check consumes the earlier one's result, for example everything after surface needs `snapshot`): give the row a reason that says so (for example `data_dependency: <later> reads <value> produced by <earlier step>`) instead of the generic early-return site. A reorder of those is impossible without rewriting the code, which the move WPs must not do.
  - **A witness the builders cannot reach** without a production change: reason `unreachable_without_production_change`, and say so in the WP history (T015 note).
- Make `NON_CO_OCCURRING` carry that per-row reason as data. Then assert that every adjacent independent pair has an executable witness, so the completeness test covers witnesses as well as classification.

## Issue 3 (should fix): the unresolvable_branches witness is vacuous for its later rows

The docstring of `test_an_early_refusal_hides_the_compounding_refusals_that_follow_it` (line 346) says "the later checks hold on the same Mission". For `unresolvable_branches` they do not. `build_canceled_dependency_mission` has only two lanes, and `_witness_unresolvable_branches` deletes lane-b. Lane-b is the carrier of the canceled dependency **and** the lane holding the post-approval commit. Both later conditions are destroyed, so the markers cannot appear whatever the order. Either keep a second approved lane alive (delete a different approved lane's branch), or narrow the docstring and drop the `(unresolvable_branches, canceled_dependency|bound)` claim. Also, line 353 rebuilds the lane branch name by hand (`setdefault("WP02", f"kitty/mission-{slug}-lane-b")`). Read it from `lanes.json` / the builder instead of reconstructing it.

## Nits (non-blocking)

- Tracer count: the entry says "the other 34 pairs are short-circuited". Correct: 36 pairs total, 2 co-occurring, 34 not, of which 4 are executable. State that once in the module docstring so a reader does not count.

## Doc note for plan IC-03 (not yours to edit)

Plan IC-03's order list is stale. It omits `surface` and `unreadable_canceled_dependency` and lists `authored` / `excluded`, which never refuse. This WP owns only the test file, so it cannot fix that. After this WP the test module's `REFUSALS` is the authority. I recommend that WP21 (closeout docs sync) amend IC-03 to point at it, and that WP14's review guidance cite the module rather than the plan's list.

## Verified locally (lane-b at 08efce4f55)

- `uv run --frozen pytest -q tests/consolidation/test_refusal_precedence_matrix.py`: 8 passed
- `uv run --frozen pytest -q tests/consolidation/test_reconciliation.py tests/consolidation/test_approved_bound.py tests/consolidation/test_canceled_dependency_attribution.py tests/consolidation/test_single_rollback_authority.py -n auto --dist loadfile`: 320 passed, 1 xfailed
- ruff check / ruff format --check --force-exclude / mypy on the file: clean
- `make test-fast`: 2921 passed, 6 skipped

Fix forward with new commits on lane-b. Never amend or rebase (DoD R-13).
