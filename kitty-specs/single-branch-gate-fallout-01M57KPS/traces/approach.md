# Approach — single-branch-gate-fallout

- **[2026-10-18][specify] Fixture/wording fallout, not a gate change.** Both reds are consumers of #5939 that its PR did not run (out-of-matrix e2e, nightly-only acceptance). Reproduce each red first (done: pytest red with SINGLE_BRANCH_EVIDENCE_WINDOW_UNCOMPUTABLE, then SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT; shell port of scenario 6 shows the move-side message without "no implementation commit"), then make the smallest change that restores each consumer without touching the gate's decisions.
- **[2026-10-18][specify] Audit sweep.** A background audit of other #5939 consumers (out-of-matrix dirs, single_branch fixtures, scenarios) runs in parallel; findings fold in or get reported.
