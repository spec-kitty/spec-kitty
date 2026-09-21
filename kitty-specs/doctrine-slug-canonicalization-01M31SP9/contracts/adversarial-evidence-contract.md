# Contract: adversarial evidence

Every adversarial-squad point-cut (post-plan, post-tasks, pre-merge) that surfaces a contested finding records its disposition in `research.md` (or the WP's notes for post-tasks/pre-merge). No contested finding is silently dropped.

## Disposition vocabulary
- **accepted** — the finding is valid; the plan/spec/code is changed to address it. Record the change.
- **changed** — the finding is partially valid; record what was adjusted and what was not.
- **deferred_with_rationale** — the finding is valid but out of scope for this mission; record the rationale and, where warranted, the follow-up ticket number.

## Rule
A finding may only be closed as `deferred_with_rationale` with an explicit reason. "Rejected" requires stating why the finding does not hold (evidence), not silence.
