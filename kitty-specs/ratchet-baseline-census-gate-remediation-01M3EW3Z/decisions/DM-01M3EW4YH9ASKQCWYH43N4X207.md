# Decision Moment `01M3EW4YH9ASKQCWYH43N4X207`

- **Mission:** `ratchet-baseline-census-gate-remediation-01M3EW3Z`
- **Origin flow:** `specify`
- **Slot key:** `scope_2631_parity`
- **Input key:** `scope_2631_parity`
- **Status:** `resolved`
- **Created:** `2026-09-26T12:48:25.129275+00:00`
- **Resolved:** `2026-09-26T12:53:49.883811+00:00`
- **Resolved by:** `operator (stijn@sddevelopment.be via AskUserQuestion)`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

#2631: act on the confirmed net-negative parity suites now (vacuous import bans, sync tombstones, private-patching context parity, stale xfails) and split test_bridge_parity (keep P0 acceptance tests; defer oracle retirement until #2633)?

## Options

- act-now-split-bridge-defer-oracle
- verdicts-only-no-remediation

## Final answer

act-now-split-bridge-defer-oracle

## Rationale

Convert/retire confirmed net-negatives; split test_bridge_parity keeping P0 acceptance tests; oracle retirement deferred to after #2633.

## Change log

- `2026-09-26T12:48:25.129275+00:00` — opened
- `2026-09-26T12:53:49.883811+00:00` — resolved (final_answer="act-now-split-bridge-defer-oracle")
