# Rejection Loop Checklist

Operational checklist for handling review rejections and re-implementation cycles.

## On Rejection (WP moved to planned with has_feedback)

- [ ] Reviewer attached a **rationale** to the rejection — a `--review-feedback-file <path>` (or `--note`). This is MANDATORY: it is recorded as the transition's `review_ref` / reason and travels on the event wire. A backward review-rejection edge (`* -> planned`, `in_review -> in_progress`) emitted WITHOUT a rationale is a contract-invalid status event — accepted locally but silently rejected by hosted sync, so the rejection never propagates.
- [ ] Confirmed WP lane is `planned` with `review_status: has_feedback`
- [ ] Confirmed the status change is committed. A `move-task` transition writes `kitty-specs/<mission>/status.events.jsonl` and `status.json` and commits them itself (default auto-commit), and it commits the `review-cycle-N.md` record it writes. The reviewer's draft `review-feedback-N.md` is NOT committed: the command removes it, and only it (this work package's own `review-feedback-*.md` in its `tasks/<wp>/` directory; never `notes.md`, another work package's draft or a symlink), once it has read the committed record back and found the text in it. It announces the removal on stderr and reports `retired_feedback_draft` in `--json`; there is deliberately no opt-out because the text is kept in `review-cycle-N.md`. Following the printed rejection command leaves nothing to stage. Only if you ran it with `--no-auto-commit` (or `auto_commit: false` in `.kittify/config.yaml`) is nothing committed at all — the record and the draft both stay on disk. Commit the record by name, and delete the draft — the record already holds its text, and committing it onto a review lane is what carries a deletion to the target branch — before the WP's next `--to for_review`, which otherwise refuses on the draft as uncommitted work: `spec-kitty safe-commit kitty-specs/<mission>/status.events.jsonl kitty-specs/<mission>/status.json kitty-specs/<mission>/tasks/WP##-<slug>/review-cycle-N.md -m "chore: Review feedback for WP## from <reviewer> (cycle X/3)"` (name only the files that changed), then `rm kitty-specs/<mission>/tasks/WP##-<slug>/review-feedback-N.md`
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
