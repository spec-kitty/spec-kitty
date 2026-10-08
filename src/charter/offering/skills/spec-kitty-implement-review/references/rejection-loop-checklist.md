# Rejection Loop Checklist

Operational checklist for handling review rejections and re-implementation cycles.

## On Rejection (WP moved to planned with has_feedback)

- [ ] Reviewer attached a **rationale** to the rejection — a `--review-feedback-file <path>` (or `--note`). This is MANDATORY: it is recorded as the transition's `review_ref` / reason and travels on the event wire. A backward review-rejection edge (`* -> planned`, `in_review -> in_progress`) emitted WITHOUT a rationale is a contract-invalid status event — accepted locally but silently rejected by hosted sync, so the rejection never propagates.
- [ ] Confirmed WP lane is `planned` with `review_status: has_feedback`
- [ ] Confirmed the status change is committed. A `move-task` transition writes `kitty-specs/<mission>/status.events.jsonl` and `status.json` and commits them itself (default auto-commit), so nothing is left to stage. Only if you ran it with `--no-auto-commit` (or `auto_commit: false` in `.kittify/config.yaml`), or the step also wrote a review-feedback file in the repo such as `kitty-specs/<mission>/tasks/WP##-<slug>/review-cycle-N.md`, commit exactly those files by name: `spec-kitty safe-commit kitty-specs/<mission>/status.events.jsonl kitty-specs/<mission>/status.json kitty-specs/<mission>/tasks/WP##-<slug>/review-cycle-N.md -m "chore: Review feedback for WP## from <reviewer> (cycle X/3)"` (name only the files that changed)
- [ ] Noted current cycle count (1, 2, or 3)

## Re-Implementation Dispatch

- [ ] Ran `spec-kitty agent action implement WP## --agent <tool> --profile <profile>` (add `--model <model> --invocation-id <op-id>` only with correlated durable Op evidence)
- [ ] Captured workspace path and prompt file from output
- [ ] Dispatched implementing agent with cycle info in prompt
- [ ] Included note: "This is cycle X/3" so agent knows urgency

## Re-Implementation Agent Checklist

- [ ] Read the review feedback the rejection pointed at FIRST — the referenced feedback file (the rejection's `review_ref`) and the review feedback section in the WP file
- [ ] Updated `review_status: "acknowledged"` in frontmatter
- [ ] Addressed EVERY feedback item (treat as mandatory TODOs)
- [ ] Added regression tests for each issue
- [ ] Verified integration (new code wired into live entry points)
- [ ] Ran all tests
- [ ] Committed with descriptive message: `fix(WP##): <what was fixed>`
- [ ] Moved to for_review: `spec-kitty agent tasks move-task WP## --to for_review`

## Re-Review

- [ ] Dispatched review agent (same or different reviewer)
- [ ] Verified outcome: approved or planned

## Cycle Limits

| Cycle | Action |
|-------|--------|
| 1/3 | Normal re-implementation |
| 2/3 | Flag urgency in dispatch prompt |
| 3/3 | STOP. Enter arbiter mode (see SKILL.md Step 5) |

## Arbiter Mode (After Cycle 3)

- [ ] Read ALL 3 sets of review feedback
- [ ] Compared implementation attempts across cycles
- [ ] Identified root disagreement
- [ ] Made arbitration decision (approve / escalate / accept-and-move-on)
- [ ] Documented rationale in `--note`
