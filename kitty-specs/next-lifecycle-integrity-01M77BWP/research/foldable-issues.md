# Foldable issues (#7548: #7553, #7582)

updated: 2026-11-12. The fold set below is proposed and needs an operator ruling.

| Issue | Class | Reason |
|---|---|---|
| #5929 (P1): `next --result success` rewinds a finalized Mission to discovery after the WPs are approved | **FOLD (proposed)** | Same defect and site as #7553 (a run that the front phase never advances falls through to the DAG). It has a self-contained repro, it is an rc6 regression (b06d485483), and #7553 cannot be closed without it. |
| #7565 (P1): with all WPs approved, `next` returns discovery instead of accept | **FOLD (proposed)** | Near-duplicate of #5929 and #7553, with an rc9 repro. |
| #5797: epic, advance-mode wedge cluster in `src/runtime/next/` | REFS | Umbrella for the same files. Coordinate with it; do not deliver it. |
| #4898 (P1): `--result failed/blocked` sets a `blocked_reason` that can never be cleared | REFS | Same files, different root (snapshot recovery). |
| #5670: `next` blocked after `mission reopen` | REFS | Terminal handling, different trigger. Guard against regressing it. |
| #3932: `next` reports not_started/discovery although spec and plan are committed | REFS | Mirror case (planning completion is not projected into the run). Larger. |
| #5112: no-progress/livelock guard for the `next` loop | REFS | Class-level safety net. |
| #2513 (closed): rollback must re-block the `for_review` gate | REFS | The design reason for the #7582 reset. |
| #3578 (closed): announce the rollback subtask reset | REFS | Already ships the notice #7582 asks for (move-task). |
| #7197: move-task subtask refusal advice drops `--owned-checkout` | EXCLUDE | P3, adjacent file, different defect. |
| #2493, #6400, #5763, #3944, #7162 | EXCLUDE | Different defects (analysis staleness, actor string, `--no-auto-commit` claim, subtask advice and adding subtasks). |
| #5099: one writer per checkout | EXCLUDE | Out of scope by instruction. Propose re-homing it under #1795 so #7548 can close. |
| Assignee rebind on `--to planned --agent <reviewer>` (startup-assess F-3) | Not filed | A rejection-path defect, out of scope. File it separately; do not fold it silently. |

## Overlap with in-flight work
- **PR #7567** (consolidate/accept). No source-file overlap. It changes `git/commit_helpers.py`, which `next_cmd.py` and `tasks_move_task.py` import: do not edit it, and expect a rebase.
- **#7547** (lane verification / pre-review gate) has no PR. No overlap. Drive CLI tests in-process.
- **#7578** (review prompt assembly) has no PR. It would touch the `runtime/next` prompt builder. We stay out of it.
