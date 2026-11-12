# Design decisions

- **[2026-11-12][research] Rulings (decisions scope, reviewer_identity, claimant_mismatch, review_cycles).** Asserted identity or refuse; approver must be the claimant; adopt + verify cycles; no backfill; no events-schema change (a null reviewer would need a spec-kitty-events release).
- **[2026-11-12][plan] No-identity refusal reuses `REVIEW_NOT_INDEPENDENT`.** The existing #6715 placeholder refusal already covers an unforced approval with no identity, so FR-004 is a ratchet, not a new code.
- **[2026-11-12][plan] The review-cycle artifact has no verdict field.** The verdict lives in the event log, so "adopt an approved cycle" is defined as valid + post-claim + same reviewer + not referenced by a recorded rejection.
