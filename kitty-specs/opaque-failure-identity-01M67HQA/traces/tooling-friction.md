# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · opaque-failure-identity-01M67HQA · The transition-gate parity oracle (tests/review/test_transition_gate_parity.py) asserts exact metadata equality against fixtures captured from the base commit, so the verdict exit status is surfaced through the existing 'reason' metadata field rather than a new metadata key, to avoid rewriting the oracle.
