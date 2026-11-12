# Decision Moment `01M779GXDVBMA90HF8FTYT14DT`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `plan`
- **Step id:** `commit_to_target_stamp_consolidation`
- **Input key:** `commit_to_target_stamp_consolidation`
- **Status:** `resolved`
- **Created:** `2026-11-12T07:11:00.539808+00:00`
- **Resolved:** `2026-11-12T07:11:04.032201+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Q8: The commit-to-target stamp flips two consolidation verdicts: (b) canceled-content attribution REFUSE to PASS with an empty attribution, (d) --attest-approved-reviewed PASS to REFUSE. How should the Mission proceed?

## Options

- Drop the stamp, derive read-side
- Keep stamp + consolidation guards (verdicts identical)
- Accept both changes

## Final answer

Keep the commit-to-target stamp; add consolidation guards so consolidation readers ignore commit-to-target single_branch stamps: (b) canceled-content attribution keeps refusing, (d) --attest-approved-reviewed keeps passing, (c) the dependency-ref closed-world check is unchanged. Consolidation verdicts stay identical (characterization: 0 differences).

## Rationale

Operator ruling 2026-11-12: one recorded window authority on every topology, without weakening #5046 or changing attestation behaviour.

## Change log

- `2026-11-12T07:11:00.539808+00:00` - opened
- `2026-11-12T07:11:04.032201+00:00` - resolved (final_answer="Keep the commit-to-target stamp; add consolidation guards so consolidation readers ignore commit-to-target single_branch stamps: (b) canceled-content attribution keeps refusing, (d) --attest-approved-reviewed keeps passing, (c) the dependency-ref closed-world check is unchanged. Consolidation verdicts stay identical (characterization: 0 differences).")
