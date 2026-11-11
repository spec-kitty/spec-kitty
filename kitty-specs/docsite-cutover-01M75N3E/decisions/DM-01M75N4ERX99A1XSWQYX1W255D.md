# Decision Moment `01M75N4ERX99A1XSWQYX1W255D`

- **Mission:** `docsite-cutover-01M75N3E`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.smoketest`
- **Input key:** `smoketest_failure`
- **Status:** `resolved`
- **Created:** `2026-11-11T15:55:26.365111+00:00`
- **Resolved:** `2026-11-11T15:55:28.927152+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does the post-deploy smoketest report a mismatch?

## Options

_(none)_

## Final answer

A job with needs: deploy, main only, read permissions only, runs python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai after every deploy and fails the run on a mismatch. No auto-filed alert issue: the operator decided a red run is the signal, so #2361's optional alert issue is not adopted. Answered from the operator brief.

## Rationale

_(none)_

## Change log

- `2026-11-11T15:55:26.365111+00:00` - opened
- `2026-11-11T15:55:28.927152+00:00` - resolved (final_answer="A job with needs: deploy, main only, read permissions only, runs python3 -m scripts.docs.site_live_probe https://docs.spec-kitty.ai after every deploy and fails the run on a mismatch. No auto-filed alert issue: the operator decided a red run is the signal, so #2361's optional alert issue is not adopted. Answered from the operator brief.")
