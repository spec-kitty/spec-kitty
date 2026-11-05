# Design decisions — #7199 resume late-coordination anchor

## D1 — One condition, not a second path

`_land_late_coordination_commits` already builds and proves the window on both run kinds. Only the
last step (record the proven tip as the one teardown approved) was run-kind-gated. Dropping
`not run.is_resume` reuses the #7124 machinery instead of adding a resume-only helper, a second
window selector or a second refusal. The compare-and-swap
(`projected_tip and live ref == projected_tip`) is untouched, so a commit landing during the
projection still refuses with the branch kept.

## D2 — Why the advance is sound on a resume

`_late_window_base` gives a resume `state.pre_mutation_coord_sha`, the pre-mutation snapshot, which
is at or before the anchor the resume's own claim/bookkeeping phase captured. The resume window is
therefore a superset of the first-run window, and `assert_late_window_landed` proves every
coordination record in it byte-identical on the target before the advance. A resume that
short-circuits the phase list (#5021 residual 1) never captures `coord_tip_after_projection`; it
falls back to `checkpoint.sha`, which the advance now also replaces with the proven tip — the
advance never requires a previous value.

## D3 — Test placement: in-process for the defect, real CLI as the control

The defect needs a coordination commit that lands *after* the run's own capture and *before* its
teardown window read. A subprocess CLI test cannot order that event without racing, so the red
test drives `_teardown_coordination_triple` on the real-git fixture family the #7124 first-run twin
uses (`tests/coordination/test_projection_teardown.py`), with the late commit injected between the
capture and the teardown. The real-CLI resume test
(`tests/consolidation/test_late_teardown_projection.py`) stays as the end-to-end positive control:
it drives a real refusal, real operator commits and a real `consolidate --resume` to exit 0 with
one projection commit, and it is re-run on the consolidated head (see the PR's Tests run).

WP02's T006 was scoped down from "add an assertion" to "re-run the control and record it" after
finding that the assertion it proposed (`projection_commits() == 1`) is already made by that test;
adding a second copy of the same assertion would be churn, not coverage. The gap it cannot cover
is the concurrency window, which D3 pins in-process.

## D4 — The exempt-file surface this widens is #7198's

`assert_late_window_landed` exempts the status byte-sets and non-coordination files such as
`meta.json`. On a resume, a late window whose only changes are exempt could previously refuse at
the gate; after this change it is approved and deleted, which is exactly the behaviour a first run
has had since #7124 and a resume has had since #6791 for commits that land before its capture.
#7198 owns making the assertion prove or deliberately exclude those changes on both run kinds.
This mission does not change what the assertion proves.
