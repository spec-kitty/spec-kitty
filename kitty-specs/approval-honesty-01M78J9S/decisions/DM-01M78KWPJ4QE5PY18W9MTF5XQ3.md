# Decision Moment `01M78KWPJ4QE5PY18W9MTF5XQ3`

- **Mission:** `approval-honesty-01M78J9S`
- **Origin flow:** `plan`
- **Slot key:** `plan.refusals.codes`
- **Input key:** `codes_and_reviewer`
- **Status:** `resolved`
- **Created:** `2026-11-12T19:31:26.916551+00:00`
- **Resolved:** `2026-11-12T19:31:28.840367+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

New refusal codes and --reviewer semantics?

## Options

_(none)_

## Final answer

APPROVER_NOT_CLAIMANT, REVIEW_CYCLE_CITATION_MISSING, REVIEW_CYCLE_NOT_ADOPTABLE; exit 1; no SINGLE_BRANCH alias; ADR 2026-10-04-5 amendment. --reviewer is a strict identity assertion: sets the actor when --agent is absent; must equal --agent and the claimant.

## Rationale

Operator ruling 2026-11-12 (D-P2, D-P3).

## Change log

- `2026-11-12T19:31:26.916551+00:00` - opened
- `2026-11-12T19:31:28.840367+00:00` - resolved (final_answer="APPROVER_NOT_CLAIMANT, REVIEW_CYCLE_CITATION_MISSING, REVIEW_CYCLE_NOT_ADOPTABLE; exit 1; no SINGLE_BRANCH alias; ADR 2026-10-04-5 amendment. --reviewer is a strict identity assertion: sets the actor when --agent is absent; must equal --agent and the claimant.")
