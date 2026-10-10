# Tracer: Approach — nightly-suites-green-rework

Seeded at planning; append during implement.

- One mission, 8 implementation concerns (IC-01..IC-08) across 5 issues / 28 tests. IC-01 (owned-checkout boundary, #5988) is the only multi-surface code change and the only genuine product regression; the rest are single-surface test/oracle/doc/derived/perf fixes.
- Red-first repro per defect (ATDD C-011, SO#4/#9). Brownfield scout on the IC-01 seam before implementing; line-trace sub-cluster B (13 tests) there.
- implement=sonnet, review=opus, profile-loaded. Targeted test surfaces only.
