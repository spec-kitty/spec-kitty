# Tracer: Approach

Seeded at planning; appended during implementation.

- 2026-09-26 (research→specify): ran Phase R (3 opus lenses) BEFORE committing scope, because the
  remediation approach was architecturally uncertain. Payoff: the lenses disproved the filed #5038
  symptom, proved P1/P2 byte-indistinguishable, and identified driver-replay as the only sound fix —
  and surfaced that the P2 floor itself needed operator re-adjudication. Committing scope first would
  have chased a phantom "clean single-lane" trigger.
- Approach chosen (operator Option B): driver-replay attribution — replay the SAME deterministic
  `spec-kitty merge-driver-*` command git used during the squash, and prove `landed == replay`.
  Reuses the existing driver (single canonical authority), no new merge algorithm.
- #5021-r2 kept honest xfail (stock-git manual resolution is not deterministically reconstructable).
  File-disjoint from the #5038 fix.
