# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · Split the seed-id NAMESPACE root (unchanged: declared id or slug) from the carrier's ENVELOPE identity (declared id or nothing). Only the envelope moved, so no existing corpus is re-seeded.

2026-10-31 · claude · Rejected both reader-side and verifier-side fixes: the reader change would alter Mission-identity semantics for every consumer, and the verifier change would widen the tamper tolerance (C-003).

2026-10-31 · claude · Development-assist test verdict for the one file this Mission added: KEEP, renamed after the contract it guards (test_backfill_runtime_state_carrier_identity.py). Folding was rejected because the engine rows are pytest.mark.integration and the owning unit module is pytest.mark.fast, and because the tactic acceptance-criteria-non-vacuity requires the refusal rows and their positive controls to share ONE fixture — splitting them across two modules would break that pairing. The docstring keeps the #6689 provenance.
