# WP04 review feedback (cycle 1)

Overall: the unforced reject/rework/re-review edits, the RED guard (verified RED on 4b864257 with 6 hits + the troubleshooting assertion, GREEN now), the tool-scoped independence caveat, pack-tier hygiene and the untouched arbiter / self-review / done-override flows are all good. One blocking accuracy defect.

## Blocking

### B1 - Troubleshooting misdiagnoses "Illegal transition"

`src/charter/offering/skills/spec-kitty-implement-review/SKILL.md` (Troubleshooting, "move-task fails with \"Illegal transition\""):

> The move is not on the canonical lane path (for example, a verdict issued before the review was claimed). Move the WP along the canonical path (claim `in_review` before a verdict) ...

This does not match shipped behaviour. `move-task` accepts a verdict issued straight from `for_review` without a prior review claim:
- rejection `for_review -> planned`: backward edges are planned by `TransitionPlan` (tasks_transition_core.py, the `_is_backward_transition` branch) and succeed; this is the mission's own supported route `for_review_to_planned` in `tests/specify_cli/cli/commands/agent/_rework_loop_harness.py` / `test_rework_unforced_loop.py` (unforced, exit 0);
- approval `for_review -> approved`: forward hop expansion (`_lane_targets_for_emit`) emits `for_review -> in_review -> approved`; `test_single_hop_approval_after_resubmit_needs_no_force` proves it;
- the reviewer arm of `_ownership_role_allowance` explicitly admits `for_review -> {in_review, approved, planned}`.

So "verdict before the review was claimed" is not a cause of "Illegal transition", and a reader who hits the error will look in the wrong place.

**Fix:** replace the example with a cause that really produces it (e.g. leaving a terminal lane such as `done`/`canceled`, or a transition guard failing - the message carries the guard's reason, e.g. a rejection without a review-feedback reference). Keep the "do not reach for `--force`; follow the canonical lane path / supply what the guard asks for" direction. No test change needed beyond keeping the guard green.

## Non-blocking (recommended, fold if cheap)

- N1 (same troubleshooting block, "Agent mismatch"): add that an `in_review` verdict must come from the agent that claimed the review; the role allowance never admits `in_review -> *` for another agent, so a second reviewer must not try to relay a verdict on a WP someone else claimed.
- N2 (Arbiter Step 5): the forced `--to approved` is recorded as an override only while the WP sits in `planned` straight after the rejection. Consider one sentence: "issue the arbiter decision while the WP is still in `planned` after the third rejection". Acknowledged as residual in research R-07; not blocking.
- N3 (test): `_ORDINARY_LANES` in `tests/doctrine/test_rework_guidance_unforced.py` is defined but unused - use it or drop it.
