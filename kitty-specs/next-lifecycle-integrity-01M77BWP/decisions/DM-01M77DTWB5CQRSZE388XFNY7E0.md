# Decision Moment `01M77DTWB5CQRSZE388XFNY7E0`

- **Mission:** `next-lifecycle-integrity-01M77BWP`
- **Origin flow:** `specify`
- **Slot key:** `specify.next.query_question_final`
- **Input key:** `specify.next.query_question_final`
- **Status:** `resolved`
- **Created:** `2026-11-12T08:26:21.413271+00:00`
- **Resolved:** `2026-11-12T08:26:23.598943+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Final: query envelope question contract (supersedes the 'pending research squad' entry for query_question)

## Options

- additive next_command
- fix the drop only
- mandatory question

## Final answer

additive next_command

## Rationale

Operator ruling 2026-11-12 after a two-lens research squad (consumer + history) DISPROVED 'query always carries a question'. Keep question nullable; pin invariant question!=null iff decision_id and options present; fix the drop for a first decision_required; add an additive defaulted next_command to every non-decision query envelope; amend #7553 wording in the PR.

## Change log

- `2026-11-12T08:26:21.413271+00:00` - opened
- `2026-11-12T08:26:23.598943+00:00` - resolved (final_answer="additive next_command")
