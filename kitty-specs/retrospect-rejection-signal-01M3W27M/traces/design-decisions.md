# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-01 · claude · D-1: any backward rework move carrying review feedback is a documented review rejection, including out of for_review / in_progress (reviewers reject without an in_review claim: 45 for_review->planned and 83 in_progress->planned events with review-cycle refs in the repo's own logs). Predicate moves to specify_cli/status/review_rejection.py so consolidate's hollow-review check can read the same authority.
