# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · The clock-skewed approval is planted by restamping the approved row in status.events.jsonl into the future and committing it; this is the narrow ADR 2026-10-15-1 decision-6 exception #6260 authorises, documented in the helper javadoc and the testing guide.

2026-11-01 · claude · approved -> in_progress refuses without a review reference (ApprovedState.guard_for), so the rejection act writes the reviewer's notes outside the repository and passes them as --review-ref, as a reviewer delivers them.
