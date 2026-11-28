---
affected_files: []
cycle_number: 3
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T09:41:58Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review 3 (reviewer-renata): changes requested

The cycle-2 items are fixed. A mixed commit no longer enters by SHA or patch-id, and a canceled work package with its own disjoint `owned_files` no longer counts. Whole-tree first-segment globs and the literal `src/**` author nothing. The verifier-level tests cover the merge closed world (mixed, stray, cherry-picked copy) and the squash blob axis. The changelog states the claim change. The mutations I ran are listed in the review report. ruff check, `ruff format --check --force-exclude`, C901 and mypy are clean on the changed files, and no suppressions were added.

I reproduced two remaining routes with a temporary probe in `tests/consolidation/` (built on `test_planning_lane_authorship_7860._mission`). I removed the probe afterwards and committed nothing.

## Issue 1 (blocking, fail-open): when ownership overlaps, a canceled or in-flight planning WP's commit is attributed to the approved WP

`src/specify_cli/consolidation/reconciliation_authorship.py`, `_approved_planning_scope` and `_scoped_commits`. The scope is the approved WPs' patterns. A commit enters whole when every path it changes matches that scope. Nothing checks who made the commit. `ownership/validation.py::validate_no_overlap` exempts dependency-ordered (sequential) pairs and `codebase-wide` WPs from the overlap rule. Every planning WP sits in the one planning lane, so two planning WPs can own the same path by design.

Reproduction: lane `(WP02, WP03)`. WP02 is approved and owns `curation/**`. WP03 owns `curation/wp03.py`. There is a Mission-branch commit to `curation/wp03.py`.

| WP03 state | WP03 commit in `claim.shas` | `curation/wp03.py` in `claim.blobs` |
|---|---|---|
| `canceled` | yes | yes |
| `for_review` | yes | yes |
| `in_progress` | yes | yes |

Before WP05 the gate refused this content. On code lanes, the mixed-lane resolver uses `lane_head` work windows to judge the same shape. The planning lane has no windows, so nothing judges it here. The canceled-content axis also walks the planning lane's old range, so it never sees this window. This is the cycle-2 issue 2 hole again, in the overlapping case.

**Fix (fail closed):** when any non-approved WP of the planning lane (canceled or in flight) declares an `owned_files` pattern that overlaps an approved WP's pattern, drop it from the scope. Reuse `ownership.validation._globs_overlap`, or make it public. If dropping overlapping patterns is too coarse, make the whole scope empty, as you already do for an unreadable list. Add a test for each of canceled and for_review. If you instead decide to accept the shape, record it as a residual in the module docstring, in the "Known residuals" section of `docs/migrations/planning-lane-write-branch.md`, and in the ADR amendment, and get an operator ruling. Silent acceptance is not OK.

## Issue 2 (should fix): `_is_whole_tree_pattern` lets through patterns exactly as broad as the `src/**` it refuses

The guard treats `src/**` as whole-tree, on the stated ground that "a declared `src/**` reads the same and is treated the same (fail closed)". `matches_owned` also has a prefix rule (`pattern.replace("/**","").replace("/*","")` followed by a `startswith(prefix + "/")` check), and `fnmatch`'s `*` crosses `/`. Because of that, these patterns all match every path under `src/` and none of them is guarded. I checked each with `matches_owned("src/deep/nested/evil.py", ...)`, and each returned True with `guarded=False`:

`src/*`, `src`, `src/`, `src/**/*`, `src/*/**`, `src/**/*.py`

**Fix:** base the check on what a pattern matches, not on how it is spelled. One option is to treat a pattern as whole-tree when its effective prefix (the same normalisation `matches_owned` uses) is empty or equals `src`, or when a wildcard appears before the second segment. Another is to compare it against a probe path under `src/` that no reasonable owner names. Add the six spellings above to the parametrized tests. The doc wording ("the inferred fallback `src/**`") then needs the same widening, in `docs/migrations/planning-lane-write-branch.md`, AGENTS.md / CLAUDE.md and `7860.fixed.md`.

## Issue 3 (nit, document): two residuals of the planning window are not recorded

- **No approval bound.** An approved planning WP's owned path that is changed after the approval, by any commit on the Mission branch, is still approved authorship. Code lanes are bounded by the approval stamp. The "planning lanes ... are not stamped and not bounded" residual was harmless while the planning lane authored nothing on this window. It now has an effect. Name it in the module docstring and in the migration doc's Known residuals.
- **The scope is read live.** `_planning_ownership` reads `owned_files` from the working tree of the placement seam's PRIMARY `tasks/` dir. It does not read the frozen claim tip (`coord_base`), and `--resume` does not freeze it the way it freezes the other anchors. An `owned_files` edit made between runs, even an uncommitted one in the coordination worktree, widens the scope. Either read the task files at `coord_base`, or record this as a residual. Reading them at `coord_base` is preferable, because the rest of the claim is pinned there.

## Issue 4 (nit): private cross-module import

`_planning_ownership` calls `wp_evidence._read_ownership`, which is a private name in another module. The consolidation family does this elsewhere through `__all__`-listed kernel names, but `_read_ownership` is not exported. Export it under a public name, for example `read_wp_ownership` (keep the private alias if you want), so the evidence axis and the claim visibly share one reader. Also, `_approved_planning_scope` repeats `_lane_is_approved`'s membership predicate inline. A small `_is_approved_wp(wp, work_packages)` helper in `reconciliation_kernel` would give a single definition.

## Checked and fine

- "Approved" is read from the same `work_packages` fold and the same `_APPROVED_MEMBERSHIP_LANES` (`approved`, `done`) that `_lane_is_approved` / the claim builder use. A WP that is re-opened after approval drops out.
- Rename from an owned path to a stray one (`--no-renames`): the commit is not whole and the new path is not attributed.
- Bookkeeping: a commit that changes the owned path plus `.kittify/…` and `kitty-specs/<slug>/…` enters whole. Those paths are already skipped by the gate's own `_is_bookkeeping` on both axes, so the claim is no wider than the gate. That width is the existing documented residual.
- A planning lane with an `sb_window` keeps its range. Presence axis: planning lanes are still excluded. `--resume` anchors are unchanged.
