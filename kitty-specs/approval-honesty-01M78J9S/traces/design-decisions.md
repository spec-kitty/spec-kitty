# Design decisions

- **[2026-11-12][research] Rulings (decisions scope, reviewer_identity, claimant_mismatch, review_cycles).** Asserted identity or refuse; approver must be the claimant; adopt + verify cycles; no backfill; no events-schema change (a null reviewer would need a spec-kitty-events release).
- **[2026-11-12][plan] No-identity refusal reuses `REVIEW_NOT_INDEPENDENT`.** The existing #6715 placeholder refusal already covers an unforced approval with no identity, so FR-004 is a ratchet, not a new code.
- **[2026-11-12][plan] The review-cycle artifact has no verdict field.** The verdict lives in the event log, so "adopt an approved cycle" is defined as valid + post-claim + same reviewer + not referenced by a recorded rejection.
- **[2026-11-12][plan] Plan squad reshaped the guard placement.** The claimant check becomes a pure sibling of `_guard_agent_ownership` (one authority) instead of a new gates-file check; the re-claim remedy was impossible (collision + no in_review->for_review edge), so the operator ruled "claimant or --force".
- **[2026-11-12][plan] Adoption keyed on event references, not timestamps.** `reviewed_at` is reviewer-written and the frontmatter has no verdict; a rejection's cycle is always referenced by its event.
