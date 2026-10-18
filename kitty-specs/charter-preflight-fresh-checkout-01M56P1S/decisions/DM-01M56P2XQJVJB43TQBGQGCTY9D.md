# Decision Moment `01M56P2XQJVJB43TQBGQGCTY9D`

- **Mission:** `charter-preflight-fresh-checkout-01M56P1S`
- **Origin flow:** `specify`
- **Slot key:** `specify.fix-strategy.parity-vs-autoheal`
- **Input key:** `fix_strategy`
- **Status:** `resolved`
- **Created:** `2026-10-18T04:59:55.506403+00:00`
- **Resolved:** `2026-10-18T05:01:33.634155+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should a fresh checkout's stale synthesized_drg be prevented from terminally blocking next: write-side re-stamp parity, read-side auto-heal, or both?

## Options

- auto-heal read path (b)
- write-side re-stamp parity (a)
- both — auto-heal primary + close write-side gap
- other

## Final answer

Both: auto-heal read path is the primary resilience mechanism (references_refresh re-stamps synthesized_drg on next when charter.yaml recomputes cleanly and the derived graph is consistent, instead of returning terminal CHARTER_PREFLIGHT_FAILED), AND close the write-side re-stamp gap so every charter.yaml-mutating writer (activate/synthesize/scaffold) re-stamps bundle_content_hash at the single compute_bundle_content_hash authority.

## Rationale

_(none)_

## Change log

- `2026-10-18T04:59:55.506403+00:00` — opened
- `2026-10-18T05:01:33.634155+00:00` — resolved (final_answer="Both: auto-heal read path is the primary resilience mechanism (references_refresh re-stamps synthesized_drg on next when charter.yaml recomputes cleanly and the derived graph is consistent, instead of returning terminal CHARTER_PREFLIGHT_FAILED), AND close the write-side re-stamp gap so every charter.yaml-mutating writer (activate/synthesize/scaffold) re-stamps bundle_content_hash at the single compute_bundle_content_hash authority.")
