---
type: reference
updated: 2026-11-12
audience: mission orchestrator, operator
---

# Foldable-issue discovery for #7578

Read-only triage. Done 2026-11-12 against `origin/main` `73a18543`. Searches:
`gh api search/issues` (repo-scoped, open issues) for "review prompt", "review
commands", "review diff", "requirement_refs", "requirement text", "single_branch
review", "pre-review gate", "..HEAD empty", "review context" and "git log -p". The
sub-issues of epic #7543 were also read.

## Classification

No open issue is small enough, and inside the review-prompt surface, to fold without
a gate or refusal-code change. **Recommended fold set: none.** Later addition: #7590, folded under operator ruling Q13 (row below).

| Issue | Class | Reason |
|---|---|---|
| #7590 Review prompt's worktree topology `diff_command` contradicts the REVIEW RANGE block | FOLD | Operator ruling Q13 (2026-11-12, tracer-design-decisions.md): in the review prompt the topology `diff_command` carries `WpReviewRange`'s own `git diff` command, or `unavailable: <gap>; see REVIEW RANGE`. Filed after this triage; no gate or refusal-code change. |
| #3481 Two definitions of "spec.md declares FR-NNN" disagree | REFS | Requirement-text resolution must reuse the canonical grammar (`requirement_mapping/grammar.py`, `_declaration_occurrences`). It must not add a third parser. The disagreement itself is not fixed here. |
| #3925 Repeat reviews should narrow to the delta | REFS | The window range makes delta narrowing possible later. The request itself is skill and template wording (open-packs). |
| #7120 WP implemented on the topic branch can't reach for_review | REFS | This is the window gap `lane_branch_missing`. The review range must degrade on it, never error. The gate side is out of scope. |
| #7345 `agent action review` refuses `--owned-checkout` | REFS | The same reviewer pain on owned `single_branch` checkouts. The fix is a CLI flag, not prompt content. |
| #5721 Residuals of the approval-stamp bound | REFS | Its residuals (parallel claims make an over-wide window) bound how exact the window diff can be. Cite them as a known caveat. |
| #6851 Pre-review gate never inspects target-branch WPs | EXCLUDE (Related) | Changes pre-review regression gate policy. This is sub-epic E territory (#7547). |
| #5675 single_branch for_review gate counts bookkeeping commits | EXCLUDE (Related) | Changes the for_review gate predicate (`lanes/for_review_gate.py`). |
| #5331 for_review gate counts the whole shared lane range | EXCLUDE (Related) | Gate policy. It shares the window idea, but delivering it is a gate change. |
| #7554 Lane tests import the root `src/` | EXCLUDE | Sub-epic E (#7547). |
| #3483 Requirement-extraction advisory invisible in `next --json` | EXCLUDE | It changes the pinned `Decision` JSON contract, and it concerns readiness, not review. |
| #2961 Post-merge mission-review diff anchor | EXCLUDE | It covers the post-merge Mission review, not the per-WP review prompt, and is mostly skill prose. |
| #3044, #1228 | EXCLUDE | Verdict integrity and review proof records. A different surface. |
| #2493, #5099, #7565, #7355, #7297, #7229 | EXCLUDE | Implement-loop friction, writer isolation, next-loop routing, evidence-window refusals, finalize, consolidate. None of them is review-prompt content. |

## Overlap with open work

| PR / branch | Overlap with the #7578 surface |
|---|---|
| #7567 (`[#7544]` coord closeout) | None. |
| #7562 (`[#7545]` CLI commits its own writes) | No shared source file. Same package as `prompt_builder.py` (`src/runtime/next/`), but it edits `next_invocation_lifecycle.py`. A possible fixture conflict in `tests/integration/test_single_branch_write_checkout_e2e.py`. Avoid editing it. |
| #7564 (`[#7539]` status read door) | Merged on 2026-11-12. It is on our base. Read events through `resolve_status_read`. |
| #7547 / `fix/7547-lane-code-verification` | No PR yet. Shared-file risk: `cli/commands/agent/tasks_move_task*.py` (pre-review gate) and `cli/commands/agent/workflow.py`. This Mission must not touch the pre-review gate's evidence logic. Edits to `workflow.py` stay in the review-context helpers. |

No other open PR (first 40 scanned) touches `prompt_builder.py`, `agent/workflow.py`,
`workflow_executor.py`, `status/lane_head.py`, `status/read_surface.py`,
`write_branch_bound.py`, `requirement_mapping/`, `specify_cli/review/` or `wp_window`.

## Upstream template (spec-kitty-open-packs), identified only

- The review commands are built in code, so no new placeholder is strictly needed.
- `packs/built-in/missions/mission-steps/software-dev/review/prompt.md` will go stale:
  - ~line 230 prescribes `git log --oneline <base>..HEAD -- <frozen-file>`;
  - items 4 and 6 (~222, ~232) send the reviewer to `spec.md`/`plan.md` for requirement text.
- Once core lands, file an open-packs issue to point that wording at the inlined
  diff and requirement blocks. Use Refs, not Closes.
