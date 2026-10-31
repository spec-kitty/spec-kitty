# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · pi/claude-sonnet-4.5 · Grounded first: reproduced the emit-then-validate mismatch through the real CLI on main @ 35318ef51c. The edge for_review -> in_progress has no structural edge, so force is its only door and the force gate checks nothing but actor+reason; the review_ref rule lived only in the auditor. Fix belongs in WPState.check_transition with the fact shared into validate.py — not in guard_for (force bypasses guards) and not in the pipeline alone (other callers reach validate_transition directly).
