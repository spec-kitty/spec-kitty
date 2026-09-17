# Decision Moment `01M2Q4F897ANB84HA6EHA9DG98`

- **Mission:** `blocked-planned-refusal-message-01M2Q4E0`
- **Origin flow:** `specify`
- **Slot key:** `specify.message.partition-breadth`
- **Input key:** `message_partition_breadth`
- **Status:** `resolved`
- **Created:** `2026-09-17T07:32:05.031959+00:00`
- **Resolved:** `2026-09-17T08:21:28.806209+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How broadly should the source-aware refusal message apply: only the blocked source lane, or every lane where planned is structurally unreachable?

## Options

- reachability-based (blocked+canceled+done)
- blocked-only (narrowest diff)
- Other

## Final answer

Reachability-based, message-only. Source lanes where planned is structurally unreachable (blocked, canceled, done) get a legal-targets refusal naming their real recovery (blocked -> resume via --to in_progress or cancel via --to canceled; canceled/done -> terminal, no targets). Review-family lanes where planned IS reachable (in_review, in_progress, approved, genesis) keep the existing review-feedback guidance. FSM allow/deny is untouched; the guard stays unconditional and force-proof. Operator confirmed blocked->in_progress is the intended one-hop resume and declined expanding scope to legalize blocked->planned.

## Rationale

_(none)_

## Change log

- `2026-09-17T07:32:05.031959+00:00` — opened
- `2026-09-17T08:21:28.806209+00:00` — resolved (final_answer="Reachability-based, message-only. Source lanes where planned is structurally unreachable (blocked, canceled, done) get a legal-targets refusal naming their real recovery (blocked -> resume via --to in_progress or cancel via --to canceled; canceled/done -> terminal, no targets). Review-family lanes where planned IS reachable (in_review, in_progress, approved, genesis) keep the existing review-feedback guidance. FSM allow/deny is untouched; the guard stays unconditional and force-proof. Operator confirmed blocked->in_progress is the intended one-hop resume and declined expanding scope to legalize blocked->planned.")
