# Research: Pin the absent-lane wording (issue #7200)

## Grounding on current main (`b4d1e918e2`)

- `src/specify_cli/consolidation/wp_evidence.py::absent_lane_window_cause` is the shipped #7120 classifier. For a code-lane branch that is not confirmed absent locally (for example a sibling lane branch exists) it builds `local_fact = f"the lane branch {branch} does not exist in this checkout"`, then appends the conditional-restore paragraph naming `refs/spec-kitty/lane-tip/<branch>`, "If it did exist …", and the anti-fabrication caution.
- The never-created shape adds `", and no lane of this Mission has a branch here. …"` only when every code-lane ref is confirmed absent (`_lane_branches_absent_locally`).
- The unreadable shape is selected by failed diffs whose ref is present or whose probe raises; the sentence there is "could not be diffed", not absence.
- `branch_ref_absent` is the Git exit-1-only rule; a present-but-unreadable ref is never absence.

## Prior delivery (#7120 / PR #7146, merged `582b5697`)

PR #7146 introduced the three-shape diagnosis. Its `tests/git_ops/test_move_task_evidence_refusals.py` cases pin the lane-tip ref and "If it did exist" for the sibling shape, and pin the all-lanes-absent sentence for the never-created shape. The sibling case does **not** assert the `does not exist in this checkout` sentence, so the issue's mutation (`is unavailable`) survives the module.

## Reproduction (current main)

1. Baseline: `uv run --frozen pytest tests/git_ops/test_move_task_evidence_refusals.py -q -p no:randomly` → `3 passed`.
2. Mutate `local_fact` in `wp_evidence.py` from `does not exist in this checkout` to `is unavailable`.
3. Run `test_a_missing_lane_with_a_sibling_names_conditional_restore` → still passes (the gap).
4. Restore the source; `git diff` clean. This confirms the issue on current main and that the fix is test-only.

## Design choice

Pin the exact sentence in the same test, alongside the existing conditional-restore and never-created assertions. The assertion reads through the real move-task gate (`_mt_require_implementation_evidence`) against a real Git fixture, so it exercises the production path rather than a helper-only seam. No new fixture and no second wording owner.

## Not in scope

- Changing production wording, refusal direction, cause classification, recovery guidance, or exit codes.
- Re-pinning the never-created or unreadable sentences (already covered by the other two cases).
- Broadening the test into a full wording snapshot; only the FR-001 absence sentence is pinned.
