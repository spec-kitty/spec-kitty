---
affected_files: []
cycle_number: 2
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T08:17:42Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review 2 (reviewer-renata): changes requested

The cycle-1 item is fixed. With an empty `write_scope` the planning lane keeps `coord_base..<target>`. Both new tests go red when I revert the guard (I mutated it locally and reverted it; nothing was committed). The mypy fix at `_dropped_own_change` is correct, and the out-of-owned-files paths are explained.

The Mission-branch window still lets content through by three other routes. I reproduced issues 1 and 2 with scratch tests built on `test_planning_lane_authorship_7860._mission` (not committed).

## Issue 1 (blocking, fail-open under `--strategy merge` / `rebase`): a mixed commit is attributed whole, by SHA and patch-id

`src/specify_cli/consolidation/reconciliation_authorship.py`, `_collect_authored`: `_commits_touching` keeps every commit that touches at least one owned path. `_scoped_walk` limits the blobs and deletions to scope, but `shas` and `patch_ids` still receive the whole commit (`for sha in authored: shas.add(sha); patch_ids.add(pid)`).

The closed-world axis (`reconciliation_verifier.MergeOutcomeVerifier._unattributable_patch_id`) is the content check for merge and rebase. It returns `None` whenever `sha in claim.authored_shas` or `pid in claim.authored_patch_ids`. So a Mission-branch commit that changes the owned file and also `sneaky.py` (or any `src/...` path) is accepted whole. A cherry-picked copy of it is accepted too, by patch-id. Under squash it fails, as intended, because the blob axis is scoped. The test asserts `{owned, mixed} <= claim.shas`, which pins this behaviour.

Reproduction (scratch): build a claim from `_collect_authored` (planning lane `(_OWNED,)`), make an `ApprovedWpCommitSet(enforce_closed_world=True, excluded_window_base=pin, authored_shas=claim.shas, authored_patch_ids=claim.patch_ids, ...)` and call `MergeOutcomeVerifier(repo)._unattributable_in((coord_base,), cs)`. `stray` is flagged; `mixed` is **not**, so `sneaky.py` lands.

Before WP05 this commit failed the gate, because the planning lane authored nothing. The squash-only scoping does not hold up the module and test docstrings ("A planning lane's commit that also changed a path outside its owned paths never makes that path approved planning authorship"; "stray commits never read as approved planning authorship").

**Fix:** on a scoped walk, add a commit's SHA and patch-id to the claim only when every path it changes is inside scope or bookkeeping (`_is_bookkeeping`). A mixed commit then authors only its in-scope blobs, and the closed world judges it (fail closed). Add a test that runs the claim through `_unattributable_in` (or the merge-strategy gate) and asserts the mixed commit is un-attributable. Fix the test that asserts `mixed in claim.shas`.

## Issue 2 (blocking, fail-open): the scope includes canceled planning WPs' owned paths, and the canceled-content resolver never sees the Mission-branch window

`lane.write_scope` for `lane-planning` is the union of **every** planning WP's `owned_files`, canceled ones included (`lanes/compute.py::_build_planning_lane`). `_lane_walk_range` scopes the walk with it. The mixed-lane canceled resolver (`reconciliation_canceled._resolve_mixed_lane`) and `_collect_excluded` still walk the planning lane's old range (`coord_base..<target>`, or `sb_window`). On the Mission-branch window, a canceled planning WP's content is therefore never resolved as canceled, but it is claimed as approved authorship.

Reproduction (scratch): lane `ExecutionLane(PLANNING_LANE_ID, ("WP02","WP03"), (_OWNED, "curation/wp03.py"), ...)`, `{"WP02": approved, "WP03": canceled}`, plus a Mission-branch commit to `curation/wp03.py`. Result: `curation/wp03.py` is in `claim.blobs` and the commit is in `claim.shas`. Before WP05 that content failed the gate.

**Fix:** scope the walk to the owned files of the lane's **approved** WPs only (exclude any WP in `excluded_canceled_wp_ids`, or that is not in an approved membership lane). If that scope is empty, keep today's range, as in the cycle-1 fix. Alternatively, make the canceled resolver and the excluded set read the same `_lane_walk_range`. The first is smaller and fails closed. Add a test.

## Issue 3 (should fix: document it, or guard it): a broad owned glob turns the walk into an unscoped one

`matches_owned` uses `fnmatch`, so `*` matches every path, and `**` and `src/**` match whole trees. A planning WP whose body names no paths and declares no `owned_files` gets the inferred fallback `src/**` (`ownership/inference.py`, `SRC_FALLBACK_GLOB`, with a warning only). With scope `("*",)` my scratch probe attributed `stray.py`, `sneaky.py` and the status file, which is the cycle-1 hole again. These are declared or inferred ownership, so a refusal may not be needed. Still, either refuse (keep today's range) when a planning lane's scope contains a whole-tree glob (`*`, `**`, `**/*`) or the inference fallback, or record it as a residual in the module docstring, `docs/migrations/planning-lane-write-branch.md` and the ADR amendment.

## Issue 4 (nit): the end-to-end test does not exercise the scoping

`tests/integration/test_7860_consolidate_planning_lane.py` stayed green when I removed the `_commits_touching` filter, and again when I removed the `_scoped_walk` scoping. Only the unit tests caught either change. I accept that a full end-to-end case is costly, but issue 1 shows that the unit tests never reached the strategy at which the hole sits. Cover at least one negative at the verifier level (a mixed commit and a stray commit under the merge-strategy closed world, and a stray commit under the squash blob axis). Running it through the real `MergeOutcomeVerifier` is enough; it does not need the CLI.

## Issue 5 (nit): the changelog does not mention the claim change

`docs/changelog/unreleased/7860.fixed.md` says "`consolidate` lands the work". It does not say that the reconciliation claim now reads planning authorship from the Mission-branch window, limited to the planning WPs' owned paths. Add one sentence, so an operator whose gate result changes can find the cause.

## Checked and fine

- Tests: see the review report for the counts. ruff check, `ruff format --check --force-exclude` and mypy on the changed source files are clean, and WP05 adds no new suppressions.
- `approved_attestation.py` is unchanged, which is correct.
