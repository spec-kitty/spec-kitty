---
type: reference
updated: 2026-11-12
audience: operator (fold ruling) and mission planners
---

# Foldable issues and overlap: approval honesty slice (epic #3044)

## Evidence that the defects are live (this repo's `kitty-specs/`)

Counts below are over 3,603 approval events and 2,442 review-cycle files.

- **#7569.** After the #4670 fix (2026-09-18), 931 of 1,390 approvals record a reviewer that is not
  the acting agent. Breakdown: 557 a human git name, 146 `"Claude"`, 25 `"Test"`, 25 `"unknown"`.
  1,290 of the 1,390 carry an `auto-approval:` reference. The newest example is
  `lane-code-verification-01M76AC0` (2026-11-12).
- **#7571.** 16 work packages in 11 Missions record one approving review as two cycles. Example:
  `stale-coord-lane-base-01M67HRA` WP01 `review-cycle-2.md` (reviewer) followed by `-3.md` (tool).
- **#7570.** 75 approvals cite "cycle N" for which no `review-cycle-N.md` exists (regex heuristic);
  23 of them are after 2026-09-18.
- **#7573.** No local `reviewer_agent: kitty-orchestrator`; the issue's cited Mission lives in the
  kitty-orchestrator repo, which this session cannot read. 23 local renders written by the
  orchestrator or supervisor carry a reviewer identity. Example: `runtime-status-read-door-01M73HHB`
  WP06 `review-cycle-2.md`.

## Candidates

| # | Class | Reason |
|---|---|---|
| #7569, #7571, #7570, #7573 | CORE | — |
| #6709 approval-feedback edge semantics | **FOLD** | The fix for #7571 ("the approval path does not author a second cycle") answers its open questions on approval with feedback and on repeat approval. Small. |
| #3451 move-task double-increments cycle | **FOLD if repro** | Same symptom as #7571. Close it only if a reproduction on current `main` shows the same cause. |
| #5543 PRIMARY duplicates + numbering drift | REFS (partly fixed) | The numbering-drift half is #7571. The duplicates half is placement, which belongs to session C (#7546). |
| #5721 approved-bound residuals | REFS | Read-only for us: `approved_bound.py` is consolidation logic. Making the synthesized `review_result` honest narrows route (a). |
| #3158 review-artifact writer tidy | REFS | Wider tidy. Deleting the dead `_persist_review_feedback` is optional. |
| #5159, #3445, #1228, #5370 | REFS | Related, different root cause. |
| #5815, #4280, #7187, #5675, #5227, #5464, #5465, #5458, #2493, #3925 | EXCLUDE | Unrelated. |

## Newly found scope, not filed yet

| Finding | Recommendation |
|---|---|
| `policy_metadata.tool` = git user on every approval (`hops.py:257`) | **In scope** (same root fact as #7569). |
| `spk-run-verdict-capture/SKILL.md:24` (core) and `runtime_bridge_decision_mapping.py:318` print the approval with no `--agent` | **In scope** (the commands that teach the leaky form). |
| `review/prompt.md:292` in open-packs uses `--actor <name>` | Upstream issue in spec-kitty-open-packs; not edited here. |
| `done_bookkeeping.py` git-user actor and `lane-approved:` / `snapshot-review:` references | Follow-up issue. This is consolidation logic, a declared non-goal. |
| `acceptance/matrix.py` `verified_by` persists the fabricated reviewer | Healed at the source by this mission; there is no separate fix. Old matrices are not rewritten. |
| `agent status emit` / `orchestrator-api transition` record any asserted reviewer | Follow-up issue (they record caller assertions, not CLI fabrications). |

## Overlap with in-flight work

- **PR #7596 (session R).** It heavily rewrites `workflow.py`, `workflow_cores.py` and
  `workflow_executor.py`. `workflow_cores.py:361` handles `auto-approval:` references. **Keep this
  mission out of those three files.** Rebase onto #7596 if it lands first. The rendered completion
  commands in `workflow_executor.py` are the one tempting overlap, so leave them alone.
- **#7546 (session C, placement).** No PR yet. Do not change where review-cycle artifacts are
  written.
- **#7598 (session A2).** Low overlap (consolidation reads only).
- None of the 6 open PRs touches `tasks_move_task*.py`, `tasks_verdict_persistence.py`,
  `review/cycle.py` or `transition_pipeline.py`.
