---
affected_files: []
cycle_number: 4
mission_slug: planning-lane-write-branch-01M8A725
reproduction_command:
reviewed_at: '2026-11-26T16:43:24Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review 4 (reviewer-renata): changes requested

The cycle-3 items are fixed. A canceled or in-flight planning work package whose `owned_files` overlap an approved pattern, or cannot be read, now empties the scope. The breadth rule is implemented by structure, as the operator ruled on 2026-11-26 (two literal leading segments, or one top-level file with an extension; `docs/**` and `docs/*.md` refused). The two residuals are recorded. `read_wp_ownership` is public. `_is_approved_wp` has exactly the old predicate in all three callers. The `globs_overlap` rename leaves `lanes/compute.py` and `ownership/validation.py` unchanged in behaviour. Taking the three names out of `__all__` is harmless: the move-task test patches `wp_evidence.target_only_owned_commits` as a module attribute, and it still passes. Every guard I mutated turned a test red (see the report).

One route is still open, and it is the cycle-3 issue 1 shape again. Two smaller wording items follow.

## Issue 1 (should fix, fail-open): a non-approved planning WP with an empty `owned_files` passes the overlap guard

`src/specify_cli/consolidation/reconciliation_authorship.py:868-881`, `_others_may_share_the_scope`. `read_wp_ownership` reads a task file that omits `owned_files` as an authored empty list (`wp_evidence.py:479`, where `WPMetadata.owned_files` defaults to `[]`). So `owned[WP03] == ()`, `_ownership_overlaps(scope, [])` is False, and the scope is kept. That WP declares no path at all, and nothing keeps it off the approved paths.

I reproduced this with a scratch probe outside the repo (nothing committed). Lane `(WP02, WP03)`. WP02 is approved and owns `curation/pkg/**`. WP03 is canceled and has `owned_files: ()`. WP03 makes a commit to `curation/pkg/x.py`. Result: that commit is in `claim.shas` and `curation/pkg/x.py` is in `claim.blobs`. Before WP05 the gate refused this content.

**Fix (fail closed):** treat an empty `owned_files` of a non-approved planning WP the same way as an unreadable one, so the scope is empty. Add a unit test next to `test_an_unreadable_non_approved_ownership_empties_the_scope`, and one integration case next to `test_an_overlapping_non_approved_work_packages_commit_stays_out_of_the_claim`. Update the wording in the module docstring, the migration doc's third case, AGENTS.md, `7860.fixed.md` and the ADR case 4 ("has `owned_files` that may share a path … , is empty, or cannot be read").

**And document the trust boundary.** The overlap guard trusts each non-approved WP to commit only inside its declared `owned_files`. I also reproduced the case where it does not: WP03 owns `docs/other/x.md`, is canceled, and commits to `curation/pkg/y.py`. That commit is attributed to WP02. A related point: the claim window starts at the planning pin, not at each approved WP's claim, so an owned-path change made before WP02 was claimed (by any commit) is attributed to WP02 as well. This is the counterpart of residual (a), on the other side of the approval. Either bound each approved WP's scope to its own window (`wp_evidence.planning_evidence_window` already computes the claim start), or record it as residual (c) in the module docstring, in the migration doc's Known residuals and in the ADR residuals. For example: "the overlap rule trusts each planning WP's declared `owned_files`, and the window starts at the planning pin, not at each approved WP's claim. So a commit on an approved path, made before that WP's claim or by a WP outside its own declared files, counts as approved authorship."

## Issue 2 (nit): the `_lane_walk_range` docstring lists only the old empty-scope cases

`reconciliation_authorship.py:752-753` lists "no approved work package, an unreadable `owned_files`, an authored empty list, or a whole-tree glob". It omits the cycle-3 overlap/unreadable-other case, and "whole-tree glob" is now the two-segment breadth rule. Point it at `_approved_planning_scope` rather than repeat the list.

## Issue 3 (nit): proposed ADR wording (`adr-wording-c3.md`) against the code

- "The scope is empty in four cases" leaves out a fifth: every approved WP has an authored empty `owned_files` (the union is empty). Issue 1 adds another clause to case 4.
- The normalisation also turns `\` into `/` (`_normalized_pattern`). Either say so ("after normalising `\` to `/`, dropping a leading `./` and a trailing `/`") or let it stay implicit, but the text should not claim to be exhaustive.
- The ADR file (`docs/adr/4.x/2026-10-04-5-…`, Amendment 2026-11-25) does not yet carry the reconciliation-claim paragraph. Make sure it lands with this WP or with the closeout.

## Checked and fine

- Overlap matcher against `matches_owned`: every path a pattern matches lies under its literal prefix or under the prefix rule's root. So two patterns that share a path always meet in `_roots_meet`. I probed `./…`, `\`-separated, `?`, `[..]`, `curation/**/x.py`, `a.py/**` and `p/*x/**` against `px/y/**`, and each was caught, including pairs that `globs_overlap` alone misses. Case is treated correctly: POSIX paths are case-sensitive, and on Windows `globs_overlap`'s fnmatch cross-check is case-insensitive.
- `src/./**` passes the breadth rule but matches nothing (narrower, harmless).
- Bookkeeping exemption, renames and merges on the spine: unchanged since review 3, and still sound. A spine merge contributes no blobs.
- ruff check, `ruff format --check --force-exclude`, C901 and mypy on the changed files are clean. No suppressions were added.
