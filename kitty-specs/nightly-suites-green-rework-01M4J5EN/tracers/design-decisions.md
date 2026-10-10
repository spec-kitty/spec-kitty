# Tracer: Design Decisions — nightly-suites-green-rework

Seeded at planning; append during implement.

- #5988 fixed in CODE (pins guard a real owned-checkout boundary); durable fix threads the owned root through lock/status writers once at the seam + a non-vacuous guard (FR-003), not per-call-site patching.
- #5989-context + #5990-corpus fixed by hardening test/oracle to match correct production/resolver behavior (C-002), never by weakening expected results.
- #5991 perf: shave eager --help imports at root (FR-010); the budget limit value is operator/CI-owned (C-005). FR-010 is FR-011's positive control.
