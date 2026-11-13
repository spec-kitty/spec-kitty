---
title: 'Grounding — #7588 move-task --agent rebinds the WP owner on a rejection'
description: 'Read-only grounding, similar-surfaces and tracked-issues verdicts for the #7588 fix: where --agent becomes the ownership slot, which paths rely on it, and what is in scope.'
doc_status: closeout
type: explanation
updated: '2026-11-13'
---
# Grounding — #7588 move-task `--agent` rebinds the WP owner on a rejection

Base: `origin/main` @ `1fb3b55fec`. Delivery shape: a governed Op (one surface, the `move-task` runtime-state emit).

## Where the defect lives

The ownership guard (`tasks_transition_core.py::_guard_agent_ownership`, the "Agent mismatch" text) is not the defect. It reads `current_agent` from the reduced snapshot's `agent` slot (`tasks_move_task.py::_mt_resolve_current_agent`). The rebind happens one layer down. `tasks_move_task_executor.py::_mt_emit_runtime_state` stamped `agent = --agent` into an off-axis `InnerStateChanged` delta on every non-claim move. On a move into `planned` it skipped the stamp only when `--agent` matched the current owner.

That delta also carries `release_runtime_claim` (#2512). The reducer (`spec_kitty_events.diary._apply_annotation_delta`) clears first and replaces second, so a differing `--agent` won over the release. The reviewer became the owner. The same stamp ran on `in_review → in_progress` and `approved → in_progress`.

Red witnessed through `move-task`, in the `_rework_loop_harness` fixture:
- After `for_review → planned --agent <reviewer>`, the slot holds the reviewer.
- After `in_review → planned`, where the review claim had already stamped the reviewer, the slot is released.
- A third implementer's `--to claimed` is refused: "Agent mismatch: WP01 is assigned to '<reviewer>'".
- The original implementer's re-claim passes through the #5196 implementer arm, which hides the defect in the common loop.

## Invariants that must survive

- **#3029 / #4786:** on every other move, `--agent` persists the acting identity in the slot. accept needs an owner in runtime state, and `done_bookkeeping.py` reads `agent` as the reviewer on an `approved` WP with no review slot.
- **#5196:** `in_review` verdicts stay with the review-claim holder. The `for_review → in_review` stamp is load-bearing.
- **#4899:** `in_review → in_progress` keeps the claim (resume-in-place). Only the `--agent` stamp is dropped there; nothing is released.
- **#2512:** a move into `planned` releases the claim.

## Similar-surfaces squad (dispositions)

| Surface | Writes the slot from who acted on a rejection? | Disposition |
|---|---|---|
| `_mt_emit_runtime_state` → `planned` | yes (the bug) | in scope, fixed |
| same → `in_review → in_progress`, `approved → in_progress` | yes | in scope ("rejection or reopen" in #7588), fixed |
| claim hop (`annotation_delta` / `policy_metadata` on `→ claimed`) | no, it is an explicit claim | untouched |
| `agent action review` review claim (`workflow_executor.review_claim_transition`) | no, it is an explicit review claim | untouched, load-bearing for #5196 |
| `agent action implement` / top-level `implement` | no | untouched |
| orchestrator-api `start-implementation` / `start-review` / `transition` | never writes the slot, and never releases it on `--to planned` | out of scope: a separate gap (no release on an API rejection), to be surfaced to the operator, not widened here |
| `agent status emit` | never writes the slot | none |
| `spec-kitty next` | no status writes; its reject commands carry no `--agent` | none |
| `tasks_verdict_persistence.py` | `--agent` feeds the review-cycle artifact only | none |
| coord-skip arm `frontmatter_fields_skipped` (`_mt_output`) | reported `agent` as bound metadata whenever `--agent` was set | in scope: now keyed off the same `_mt_agent_binds_owner` predicate. On the protected-coordination arm a hand-back move refuses before any write (the verdict cannot be committed), and `--assignee` is refused there (`_guard_unsupported_skip_metadata`). |
| `render_review_completion_commands` and skills/docs that pass `--agent <reviewer>` to a reject | callers, now get "who acted" semantics | no change needed |

## Tracked-issues squad

- **#7588:** Closes.
- **#7582, #7548:** Refs. Same tracer and same Mission family; #7548 recorded this as foldable.
- **#5196:** Refs. The implementer arm that masked the defect for the original implementer.
- **#3029, #4786:** Refs. Their invariant is kept: non-hand-back moves still bind.
- **#2512, #4673:** Refs. Claim release and the restamp suppression this fix replaces.
- **#5815:** Related, not folded. orchestrator-api rejection review-ref; a different defect.
- **No duplicates found.** Searched "Agent mismatch", "move-task --agent assignee", "rejection rebind agent", "release_runtime_claim", "re-claim rejected --force" and "review claim agent slot".

## Test expectation changed (operator-signalled)

`test_move_task_rollback_clears_claim.py::test_rollback_with_explicit_agent_replants_claim` pinned `--agent` as the re-plant. It is re-pinned as `..._explicit_assignee_replants_claim`: `--assignee` re-plants, `--agent` names the actor (option A, surfaced to the orchestrator).
