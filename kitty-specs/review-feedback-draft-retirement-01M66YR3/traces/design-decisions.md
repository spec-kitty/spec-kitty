# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude-orchestrator · Seed: retire-on-durable, not commit-the-source (C-001): review-cycle-N.md already holds the body verbatim, so the draft is staging, and committing it re-creates #6632's coord squash-deletion. One owning seam (NFR-003): review/cycle.py::create_rejected_review_cycle — covers the rejection leg, the #6652 approval-with-feedback leg and _persist_review_feedback. Safety gates: durable only; inside kitty-specs/<mission>/ only; untracked only; bytes still equal the recorded body; never fail a recorded rejection.

2026-10-30 · python-pedro · WP01 half-by-half proof: reverting the caller's durable gate turns the e2e non-durable test red; reverting the tracked guard, the mission-directory guard and the bytes comparison each turns its named unit test red. Note for reviewers: the unit test for FR-002 passes even with the caller gate removed because the helper's own 'no recorded text' arm also keeps the file — the load-bearing assertion for the gate is the e2e auto_commit:false case, which is why both exist.
