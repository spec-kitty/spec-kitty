# Corpus-recovery budget contract

Audience: maintainers reviewing #5716 and the existing upgrade correctness gate.

The authoritative behavioral contract remains `tests/upgrade/test_mission_corpus_recovery.py::test_original_full_corpus_residue_then_recovered_and_landed_corpus_passes`; this Mission does not introduce a production API.

- Preserve every existing audit, membership/inventory comparison, recovery gate, corruption case and healthy control. No body/assertion/helper edits.
- Apply the independently measured 450-second protocol allowance to that function only; preserve the shared 240-second floor and individual 180-second subprocess limits.
- Preserve failure propagation. No skip, xfail, quarantine, retry or scheduling-policy change.
- The bounded, unchanged-source diagnostic supplies calibration evidence, not final acceptance by itself. Normal hosted upgrade shard validation under the actual marker supplies SC-002.
- The runtime accept gate must verify genuine owned implementation and independent review. Do not attest that no implementation was owed: this WP delivered a real five-line owned-file change.

Evidence and accepted measurement limitations: `../research.md` and `../traces/final-integrity-review.md`. This is a test-budget correction, not a promise that arbitrary future workloads complete within 450 seconds.
