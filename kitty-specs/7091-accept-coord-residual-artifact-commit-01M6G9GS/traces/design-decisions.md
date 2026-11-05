# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · pi/deepseek-v4.1-flash-1017 · Chose a dedicated COORD-partition kind (MISSION_EVENT_LOG) over borrowing STATUS_STATE: is_status_state_path is deliberately narrow (status.events.jsonl/status.json) and is consumed by claim-commit bundling and coord planning staging, which must not widen to an event log the claim never wrote. Fixing the classifier fixes every consumer; an accept-local special case would leave the file None for the residue gates and contradict the router's derived-partition rule.

2026-11-05 · landing maintainer · The entry above records the initial proposal, not the accepted implementation. WP01 review cycle 1, B1/B2, rejected the new kind because it reversed #5669's keep-local ruling and its standing dirty-gate guard; #5697 also documents that the log deliberately remains unclassified. The accepted correction reuses the existing classifier and excludes only unclassified coordination-worktree residuals from accept's commit batch, leaving them dirty and reporting them in acceptance notes. It changes neither classification nor the global churn owner. Classified paths still follow commit routing and retain the existing refusal boundaries; flat-Mission residual commits remain unchanged.

The historical WP filename and the lane manifest's generated write-scope snapshot predate that review correction. WP01's current title, objectives and `owned_files` record the accepted scope: `accept.py`, its existing residual-partition test file and the changelog fragment. No artifact-kind or partition-mapping edit remains in PR #7119. The initial planning entry is preserved above rather than rewritten into an approval it never received.

The landing pass re-established the defect through the existing residual-commit entry point against main-equivalent behavior, then restored the candidate byte-exact and passed all 18 tests in the changed file. Evidence: https://github.com/spec-kitty/spec-kitty/pull/7119#issuecomment-6666337351. This records verification and the earlier review's outcome, not a new independent approval.

2026-11-05 · landing maintainer · Deferred-scope clarification: the plan's suggested taxonomy follow-up is not an unresolved defect in this change. Other primary-resident, unclassified agent-authored records keep the documented `None`/PRIMARY-partition behavior (#5697); no reclassification or new tracker is warranted here. The claimed missing-contracts limitation was already resolved by #5298's documented `contracts: none` waiver (ADR 2026-10-04-1), and this Mission ships a real residual-routing contract. Neither is deferred implementation for #7119. The separately tracked acceptance-suite baseline remains #7175; old test counts are historical, not a fresh result.
