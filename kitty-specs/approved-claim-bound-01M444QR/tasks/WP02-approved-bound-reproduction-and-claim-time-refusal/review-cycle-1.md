---
affected_files: []
cycle_number: 1
mission_slug: approved-claim-bound-01M444QR
reproduction_command:
reviewed_at: '2026-10-04T21:17:24Z'
reviewer_agent: reviewer
wp_id: WP02
---

# WP02 review, cycle 1: changes requested

Reviewer: reviewer (profile reviewer-renata). Lane `kitty/mission-approved-claim-bound-01M444QR-lane-b` at `5868e8d9bf`.

The core rule is sound and well built. Red-first is proven (commit `6841d5a824` holds only the two test files; at that commit the four refusing cells fail on `exit 0` with "Reconciliation verified", the two rework controls pass). Suites are green (1918 passed, 1 skipped, 5 xfailed), `ruff`, format, `mypy --strict` and C901 are clean, no existing refusal text changed, the #5330 xfails are untouched.

Two items block approval. Both are small.

## Required changes

### 1. Remove the whole-lane skip for an attested, unstamped canceled work package (fail-open)

`src/specify_cli/consolidation/approved_bound.py:175-183` (`_attested_without_stamp`) and its use at `:252-253`.

When a canceled work package of a mixed lane is attested and no event of it carries a stamp, `check_lane` returns `None` for the whole lane. A content commit added after the approval then lands.

Proof, on the existing fixture, against the lane code:

```python
repo, fd, manifest, base, lane = _build_mixed_lane_entered_mission(tmp_path, stamp_attribution=False)
_append_attestation(repo, fd)                      # no lane_head
# one more content commit on the lane: src/late.py
claim = build_approved_wp_set(repo, fd, manifest, coord_base_ref=base,
                              excluded_canceled_wp_ids=frozenset({"WP02"}), excluded_window_base=base)
# claim.refusal is None
# merge the lane into a target, then MergeOutcomeVerifier.verify(...):
#   verify_reachability=True  -> PASS
#   verify_reachability=False -> PASS
```

With `_append_attestation(..., lane_head=<lane tip>)` the same late commit is refused with `LANE_MOVED_AFTER_APPROVAL`. So the skip is the only thing that lets it through.

Why this is not acceptable:

- It is the #5668 defect on one sub-case, and constraint C-003 says no fail-open fallback.
- Plan D-2 item 1 says a canceled work package with no stamp gives no covered point ("skip when it has none"). It does not say skip the lane.
- `canceled_attestation.attestation_stamps` already documents the rule: "`None` when no stamp could be taken — then nothing is exempted".
- The skip exists only to keep `test_attested_unstamped_mixed_lane_falls_back_to_whole_lane` green. That test's attestation has no `lane_head`, which production writes whenever the lane branch can be read. The fixture is the untruthful part, not the rule.

Do this:

1. Delete `_attested_without_stamp` and the early return. An unstamped canceled work package contributes no covered point.
2. In `tests/consolidation/test_reconciliation.py::test_attested_unstamped_mixed_lane_falls_back_to_whole_lane`, pass `lane_head=_rev(repo, lane_branch)` to `_append_attestation` (the helper already has the parameter). I checked: with the skip disabled and the attestation stamped, the three existing assertions pass unchanged.
3. Add one test: on that fixture, a content commit after the attestation is refused with `LANE_MOVED_AFTER_APPROVAL`.

### 2. The recovery command printed in all three refusals fails on a coordination mission

`src/specify_cli/consolidation/approved_bound.py:49` (`_MOVE_BACK`).

On `build_post_approval_mission(tmp_path, "coord")` with a late commit, run exactly as printed:

```
spec-kitty agent tasks move-task WP01 --to in_progress --mission <slug> --note "late content needs review"
-> exit 1: Cannot persist WP frontmatter/activity metadata on protected branch 'main' while
   coordination topology is active: activity_log. ... omit those metadata flags ...
```

Without `--note` it exits 0 ("Moved WP01 from approved to in_progress"). On the lanes fixture it works with `--note`.

NFR-004 and plan D-4 require a remedy that works and is taken from the live CLI. `tests/consolidation/test_approved_bound.py:214` (`test_recovery_command_exists_in_the_cli`) only checks that four tokens appear in `--help`, so it did not catch this.

Do this:

1. Print a command that works on both topologies (dropping `--note` is enough; if you want the rationale recorded, find a form that the coordination topology accepts).
2. Replace the token test with one that runs the rendered command through `run_terminus` on both post-approval fixtures and asserts exit 0 and the work package in `in_progress`. Remove the `--help` test; do not keep both.

## Should fix in the same pass (not blocking on their own)

3. `approved_bound.py:126-137` (`_latest_stamp`, "newest stamped event"): the rule is sound, but no test pins it. Changing it to "stamp of the newest event" leaves all 1918 tests green. Add one case to `test_mixed_lane_counts_the_canceled_work_packages_stamp_as_covered`: a stamped cancel followed by an unstamped event keeps the cancel stamp as the covered point.
4. `reconciliation.py:1890` (`lane_tips_moved_refusal`): the text says "after review approved {wps}" and lists every manifest work package of the lane, canceled ones included. Name only the approved ones, or pass them in. WP03 calls this, so settle the signature now.

## Notes for the record (no change asked in this work package)

- `approved_bound.py:238`: a claim base that does not resolve is not refused. This keeps the existing builder tolerance (`test_build_claim_tolerates_unresolvable_lane_probe`) and I could not reach it through `consolidate` (a missing mission branch is refused earlier with "Missing mission branch"). The public `approved_bound_refusal` returns `None` in that case, so WP05 must pass a resolved base.
- An approved work package with no stamp on a lane with no commit beyond the claim base is not refused. Nothing can land from it. It differs from the letter of FR-005 and SC-003; record it in the decision record (WP06).
- By plan D-2, the stamp of a `--attest-canceled-superseded` attestation is a covered point, so content added after the approval and before that attestation lands once the operator attests. Worth one sentence in the operator documentation (WP06).
- `tests/architectural/test_no_dead_symbols.py` flags five names: `approved_bound::APPROVED_REVIEWED`, `::ATTEST_APPROVED_FLAG`, `::approval_stamp` (consumer WP04), `reconciliation::approved_bound_refusal` (WP05; the builder calls `_approved_bound_verdict`, not this wrapper), `reconciliation::lane_tips_moved_refusal` (WP03). Each has a planned consumer. Accepted for this work package.
- `test_bare_slug_coord_mission_consolidates_onto_a_protected_target` is red on the root checkout too (#5651, `MERGE_UNSAFE_WORKTREE_DIRTY`). Not yours.

## What I checked and accept

- Deviation 1 (newest stamped event): sound. An event with no stamp cannot widen coverage.
- Deviation 3 (empty lane, unresolvable base): sound on the `consolidate` path, see notes.
- Deviation 4 (unresolvable lane tip skipped): sound. `_unresolvable_approved_lane_branches` refuses a missing branch of the same lane set first.
- Deviation 5: cosmetic, item 4.
- Mixed lanes: a commit between the approval and a later canceled work package's claim, and a commit before a `planned -> canceled` stamp, are both refused by the existing closed world ("outside every WP's recorded work window"), through the CLI. The delegation holds.
- Fixture restamps: the #4977, #4945, #4981, #5001, #5022 repro files and `test_canceled_content_residuals.py` are unchanged; only shared helpers restamp. Their verdicts and assertions are the same.
