# Data Model: Regression-slice test cleanup

No product data changes. The mission's working entities:

- **Ledger row** — file, test count, runtime, verdict (MARKER-ONLY | SPLIT-BY-KIND | SHIFT-LEFT | RETIRE | FIX | KEEP), covering guard, evidence id. Source: the issue body.
- **Planted-break record** — id, product file + edit, guard files run, result (RED n failed / GREEN), reverted (yes). Invariant: every RETIRE or trimmed SHIFT-LEFT test maps to ≥1 record with a RED result; a GREEN result flips the verdict to KEEP.
- **Marker state per test** — the set of markers a collected test carries. Invariant: every test keeps ≥1 tier marker routed by CI (C-004).
