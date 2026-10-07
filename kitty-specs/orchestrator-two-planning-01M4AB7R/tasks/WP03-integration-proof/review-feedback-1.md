# WP03 review feedback — cycle 1

Reviewed head: `c8d3b7ec937234a61a36b8bd4f076565019f8dbc`.
Reviewer: `reviewer-renata`, independent of implementation.

## P1 — A pending native design input is mistaken for completed design work

`runtime_next._completion_gate` reads `query_current_state(...).step_id` as an issued action. Native query projection also puts the upcoming stage in `step_id` for `decision_required`, while the native engine persists `issued_step_id=None` until it actually returns `kind=step`. After API-authored early research enables provenance, a supported `specify.requires_inputs=[approval]` workflow reaches a pending input before its first specification action. Answering that input via `next --answer --result success` is incorrectly refused with `RUNTIME_NEXT_FAILED` / `DESIGN_PREREQUISITES_FAILED`, requiring completed specification content before the specification action is issued.

The focused real API-only counterexample produced discovery issuance, then `decision_required specify input:approval`; the answer failed and remained pending. Project template configuration happened before the first API call. No runtime state or artifacts were fabricated.

Fix: use the existing native read-only run/snapshot authority to distinguish actual issuance from a pending decision or preview, retaining the cooperative authoring lock and completion validation. Do not create an alternate cursor or state reducer. Commit a meaningful RED regression before the correction.

Acceptance: with API provenance enabled, answering the pending input must issue the first specify prompt; reporting that issued action successful with only a scaffold must still refuse without advancing it; accepted substantive specification must then permit native advancement to plan. Preserve initial query behavior and the existing native decision test.

The source/contract/status mapping review otherwise passed. Earlier command-table and runtime-index-proof P2 findings are resolved. Persistence remains explicitly cooperative, non-atomic, and host-local; full Go conformance remains unavailable.
